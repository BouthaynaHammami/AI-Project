from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import Counter
from datetime import date, datetime
from typing import Any, Literal

import pandas as pd
from groq import Groq
from pydantic import BaseModel, Field, ValidationError

from app.services.ai_service import _MODEL

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_LIMIT = 512
_MAX_CONTEXT_CHARS = 10_000
_cache: dict[str, tuple[float, list["Suggestion"]]] = {}
_refresh_times: dict[int, float] = {}
_cache_lock = threading.RLock()
_PII_COLUMN = re.compile(r"(?<![a-z])(?:nom|prenom|prénom|email|e-mail|tel|telephone|téléphone|cin|iban|adresse)(?![a-z])", re.I)
_ID_COLUMN = re.compile(r"^(?:id|uuid|guid)(?:[_\s-].*)?$", re.I)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_ISO_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b", re.I)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_CIN = re.compile(r"(?<!\d)\d{8}(?!\d)")
_STOP_WORDS = set("""
le la les un une des du de d au aux et ou en dans sur pour par avec sans est sont
ce ces cette qui que quoi comment pourquoi quand où est-il sont-ils votre vos notre nos
a à comme plus moins très aussi mais donc car the a an and or in on for with without
from to of is are was were this that these those what how why when where
""".split())


class Suggestion(BaseModel):
    question: str = Field(min_length=1, max_length=160)
    category: Literal["classement", "evolution", "comparaison", "repartition", "qualite", "synthese"]
    columns: list[str] = Field(default_factory=list)
    chart: bool = False


class SuggestionResponse(BaseModel):
    suggestions: list[Suggestion]
    source: Literal["ai", "rules", "cache"]


def _json_safe(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _mask_personal_text(value: str) -> str:
    value = _EMAIL.sub("[DONNÉE PERSONNELLE]", value)
    value = _IBAN.sub("[DONNÉE PERSONNELLE]", value)
    value = _CARD.sub("[DONNÉE PERSONNELLE]", value)
    value = _CIN.sub("[DONNÉE PERSONNELLE]", value)
    return _PHONE.sub(
        lambda match: "[DONNÉE PERSONNELLE]"
        if len(re.sub(r"\D", "", match.group(0))) >= 9 and not _ISO_DATE.fullmatch(match.group(0))
        else match.group(0),
        value,
    )


def _contains_personal_data(value: str) -> bool:
    if any(pattern.search(value) for pattern in (_EMAIL, _IBAN, _CARD, _CIN)):
        return True
    return any(
        len(re.sub(r"\D", "", match.group(0))) >= 9 and not _ISO_DATE.fullmatch(match.group(0))
        for match in _PHONE.finditer(value)
    )


def _looks_like_identifier(name: str, series: pd.Series, unique_count: int) -> bool:
    normalized_name = name.strip().lower()
    if _ID_COLUMN.search(normalized_name):
        return True
    if normalized_name.endswith(("_id", " uuid", "-uuid", "_uuid", "_guid")):
        return True
    count = int(series.notna().sum())
    return count > 0 and unique_count == count and count >= 20


def _detected_type(column: dict[str, Any], identifier: bool) -> str:
    return "identifiant" if identifier else str(column.get("detected_type", "texte"))


def _date_granularity(series: pd.Series) -> str:
    dates = pd.to_datetime(series, errors="coerce", format="mixed").dropna()
    if dates.empty:
        return "inconnue"
    if bool((dates.dt.month.eq(1) & dates.dt.day.eq(1)).all()):
        return "année"
    if bool((dates.dt.day == 1).all()):
        return "mois"
    return "jour"


def _text_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", text.casefold())
    ignored = _STOP_WORDS | {"donnee", "donnée", "personnelle"}
    return [word for word, _ in Counter(word for word in tokens if word not in ignored).most_common(10)]


def build_data_context(
    dataframe: pd.DataFrame,
    file_names: list[str] | None = None,
    file_columns: list[tuple[str, list[str]]] | None = None,
) -> dict[str, Any]:
    """Build a compact, PII-scrubbed profile; raw records are never returned."""
    from app.services.profiling_service import profile_dataframe

    sample = dataframe.head(100_000)
    profile = profile_dataframe(sample)
    profiles = profile["columns"]
    safe_files = file_names or (
        [str(value) for value in sample["__source_file"].dropna().unique()]
        if "__source_file" in sample.columns
        else []
    )
    safe_files = [_mask_personal_text(filename) for filename in safe_files]
    columns: list[dict[str, Any]] = []
    profile_names = [str(column["name"]) for column in profiles if column["name"] != "__source_file"]
    profile_name_counts = Counter(profile_names)
    numeric_columns: list[str] = []
    category_columns: list[str] = []
    date_columns: list[str] = []
    text_columns: list[str] = []
    for column in profiles:
        name = str(column["name"])
        if name == "__source_file":
            continue
        series = sample.iloc[:, int(column["position"])]
        identifier = _looks_like_identifier(name, series, int(column["unique_count"]))
        name_is_personal = bool(_PII_COLUMN.search(name))
        data_looks_personal = any(_contains_personal_data(str(value)) for value in series.dropna())
        sensitive = name_is_personal or (data_looks_personal and name.casefold() != "content")
        duplicate_name = profile_name_counts[name] > 1
        detected_type = "texte" if name.casefold() == "content" else _detected_type(column, identifier)
        item: dict[str, Any] = {
            "name": name,
            "type": detected_type,
            "missing_percent": column["missing_percentage"],
            "unique_count": column["unique_count"],
            "suggestible": not identifier and not sensitive and not duplicate_name,
        }
        if duplicate_name:
            item["values"] = "[COLONNE AMBIGUË]"
        elif sensitive:
            item["values"] = "[DONNÉE PERSONNELLE]"
        elif not identifier and detected_type == "numérique":
            stats = column.get("statistics", {})
            item.update({
                "min": stats.get("min"),
                "max": stats.get("max"),
                "mean": stats.get("mean"),
                "median": stats.get("median"),
            })
            numeric_columns.append(name)
        elif not identifier and detected_type == "date":
            date_range = column.get("date_range", {})
            item.update({
                "first_date": date_range.get("min"),
                "last_date": date_range.get("max"),
                "granularity": _date_granularity(series),
            })
            date_columns.append(name)
        elif not identifier and detected_type in {"catégorie", "booléen"}:
            if int(column["unique_count"]) <= 30:
                top = series.value_counts(dropna=True).head(5)
                item["top_values"] = [
                    {
                        "value": _json_safe(value)[:100] if isinstance(value, str) else _json_safe(value),
                        "count": int(count),
                    }
                    for value, count in top.items()
                ]
                item["categories"] = [
                    _json_safe(value)[:100] if isinstance(value, str) else _json_safe(value)
                    for value in series.dropna().unique()[:30]
                ]
            category_columns.append(name)
        elif not identifier and detected_type == "texte":
            text_columns.append(name)
        columns.append(item)

    safe_text = ""
    text_column = next((name for name in text_columns if name.casefold() == "content"), None)
    if text_column is not None:
        text = " ".join(sample[text_column].dropna().astype(str).tolist())
        safe_text = _mask_personal_text(text)[:800]

    numeric_safe = [name for name in numeric_columns if not _PII_COLUMN.search(name)]
    correlations: list[dict[str, Any]] = []
    if len(numeric_safe) > 1:
        corr = sample[numeric_safe].corr(numeric_only=True).abs()
        for left_index, left in enumerate(numeric_safe):
            for right in numeric_safe[left_index + 1:]:
                value = corr.loc[left, right]
                if pd.notna(value) and float(value) >= 0.7:
                    correlations.append({"columns": [left, right], "correlation": round(float(value), 3)})
        correlations.sort(key=lambda item: item["correlation"], reverse=True)

    files: dict[str, int] = {}
    if "__source_file" in sample.columns:
        files = {
            _mask_personal_text(str(name)): int(count)
            for name, count in sample["__source_file"].value_counts().items()
        }
    per_file_columns: dict[str, set[str]] = {}
    if file_columns:
        for filename, names in file_columns:
            label = _mask_personal_text(filename)
            if label in per_file_columns:
                label = f"{label} ({len(per_file_columns) + 1})"
            per_file_columns[label] = set(names)
    elif "__source_file" in sample.columns:
        for filename, group in sample.groupby("__source_file", dropna=True):
            per_file_columns[_mask_personal_text(str(filename))] = {
                str(name) for name in group.columns if name != "__source_file"
            }
    common = sorted(set.intersection(*per_file_columns.values())) if per_file_columns else []
    file_specific = {
        filename: sorted(names - set(common))
        for filename, names in per_file_columns.items()
    }

    context: dict[str, Any] = {
        "files": [{"name": name, "rows": count} for name, count in files.items()] or [
            {"name": name, "rows": len(sample)} for name in safe_files
        ],
        "row_count": int(len(dataframe)),
        "column_count": int(len(columns)),
        "columns": columns,
        "candidate_pairs": {
            "category_numeric": [
                {"category": category, "numeric": numeric}
                for category in category_columns for numeric in numeric_columns
                if not _PII_COLUMN.search(category) and not _PII_COLUMN.search(numeric)
            ][:30],
            "date_numeric": [
                {"date": date_name, "numeric": numeric}
                for date_name in date_columns for numeric in numeric_columns
                if not _PII_COLUMN.search(date_name) and not _PII_COLUMN.search(numeric)
            ][:30],
            "strong_correlations": correlations[:3],
        },
        "multiple_files": {
            "common_columns": common,
            "file_specific_columns": file_specific,
        } if len(per_file_columns) > 1 else None,
    }
    if safe_text:
        context["document"] = {
            "excerpt": safe_text,
            "frequent_keywords": _text_keywords(safe_text),
        }

    # Retain the useful structural facts while enforcing a compact prompt payload.
    serialized = json.dumps(_json_safe(context), ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > _MAX_CONTEXT_CHARS:
        for column in context["columns"]:
            categories = column.get("categories")
            if categories:
                column["categories"] = categories[:10]
            top_values = column.get("top_values")
            if top_values:
                column["top_values"] = top_values[:3]
        if "document" in context:
            context["document"]["excerpt"] = context["document"]["excerpt"][:400]
        context["candidate_pairs"]["category_numeric"] = context["candidate_pairs"]["category_numeric"][:10]
        context["candidate_pairs"]["date_numeric"] = context["candidate_pairs"]["date_numeric"][:10]
        serialized = json.dumps(_json_safe(context), ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > _MAX_CONTEXT_CHARS:
        context["columns"] = context["columns"][:100]
        serialized = json.dumps(_json_safe(context), ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > _MAX_CONTEXT_CHARS:
        context = {
            "files": context["files"][:10],
            "row_count": context["row_count"],
            "column_count": context["column_count"],
            "columns": [
                {
                    key: value
                    for key, value in column.items()
                    if key in {"name", "type", "missing_percent", "unique_count", "suggestible", "values"}
                }
                for column in context["columns"][:40]
            ],
        }
    return _json_safe(context)


def _get_values(context: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    columns = {column["name"] for column in context.get("columns", []) if column.get("suggestible")}
    category_values = {
        str(value)
        for column in context.get("columns", [])
        if column.get("suggestible")
        for value in column.get("categories", [])
    }
    periods = {
        str(period)
        for column in context.get("columns", [])
        for period in (column.get("first_date"), column.get("last_date"))
        if period
    }
    return columns, category_values, periods


def generate_rule_suggestions(context: dict[str, Any]) -> list[Suggestion]:
    columns = {
        column["name"]: column
        for column in context.get("columns", [])
        if column.get("suggestible") and not _PII_COLUMN.search(column["name"])
    }
    numeric = [name for name, column in columns.items() if column["type"] == "numérique"]
    dates = [name for name, column in columns.items() if column["type"] == "date"]
    categories = [
        name for name, column in columns.items()
        if column["type"] in {"catégorie", "booléen"} and column.get("categories")
    ]
    text_columns = [name for name, column in columns.items() if column["type"] == "texte"]
    suggestions: list[Suggestion] = []

    def add(question: str, category: str, used_columns: list[str], chart: bool = False) -> None:
        if len(question) <= 160:
            suggestions.append(Suggestion(
                question=question,
                category=category,
                columns=used_columns,
                chart=chart,
            ))

    if categories and numeric:
        category = categories[0]
        values = columns[category].get("categories", [])
        add(f"Quelle valeur de {category} a le plus grand {numeric[0]} ?", "classement", [category, numeric[0]], True)
        if values:
            add(
                f"Quelle part du {numeric[0]} revient à « {values[0]} » dans {category} ?",
                "repartition",
                [category, numeric[0]],
                True,
            )
            if len(values) > 1:
                add(
                    f"Le {numeric[0]} est-il plus élevé pour « {values[0]} » ou « {values[1]} » ?",
                    "comparaison",
                    [category, numeric[0]],
                    True,
                )
            else:
                add(f"Comment varie le {numeric[0]} selon {category} ?", "comparaison", [category, numeric[0]], True)
    elif categories:
        category = categories[0]
        values = columns[category].get("categories", [])
        if values:
            add(f"Quelle valeur revient le plus souvent dans {category} ?", "classement", [category])
            add(
                f"Quelle part des lignes correspond à « {values[0]} » dans {category} ?",
                "repartition",
                [category],
                True,
            )
            if len(values) > 1:
                add(
                    f"Quelle valeur est la plus fréquente entre « {values[0]} » et « {values[1]} » ?",
                    "comparaison",
                    [category],
                )
    if dates and numeric:
        date_column = dates[0]
        granularity = columns[date_column].get("granularity", "mois")
        date_range = columns[date_column]
        start = str(date_range.get("first_date") or "")[:10]
        end = str(date_range.get("last_date") or "")[:10]
        period = f" entre {start} et {end}" if start and end else ""
        add(
            f"Comment évolue le {numeric[0]} par {granularity}{period} selon {date_column} ?",
            "evolution",
            [date_column, numeric[0]],
            True,
        )
    elif dates:
        date_column = dates[0]
        start = str(columns[date_column].get("first_date") or "")[:10]
        end = str(columns[date_column].get("last_date") or "")[:10]
        period = f" entre {start} et {end}" if start and end else ""
        add(f"Quelle période couvre {date_column}{period} ?", "synthese", [date_column])
        add(f"Combien de dates distinctes contient {date_column} ?", "classement", [date_column])
        add(f"Combien de dates manquent dans {date_column} ?", "qualite", [date_column])
    if numeric:
        add(f"Quelles sont les valeurs les plus élevées de {numeric[0]} ?", "classement", [numeric[0]], True)
        add(f"Quelles valeurs atypiques apparaissent dans {numeric[0]} ?", "qualite", [numeric[0]])
        add(f"Combien de valeurs manquent dans {numeric[0]} ?", "qualite", [numeric[0]])
    if text_columns:
        keywords = context.get("document", {}).get("frequent_keywords", [])
        if keywords:
            for keyword in keywords[:3]:
                add(f"Que dit {text_columns[0]} au sujet de « {keyword} » ?", "synthese", [text_columns[0]])
        else:
            add(f"Quels thèmes ressortent du contenu de {text_columns[0]} ?", "synthese", [text_columns[0]])
            add(f"Quels chiffres clés sont mentionnés dans {text_columns[0]} ?", "synthese", [text_columns[0]])
            add(f"Quelles conclusions présente {text_columns[0]} ?", "synthese", [text_columns[0]])
    if not suggestions and columns:
        first = next(iter(columns))
        add(f"Quelles sont les valeurs les plus fréquentes de {first} ?", "classement", [first])
    unique_suggestions: list[Suggestion] = []
    seen_questions: set[str] = set()
    for suggestion in suggestions:
        normalized = suggestion.question.casefold()
        if normalized not in seen_questions:
            unique_suggestions.append(suggestion)
            seen_questions.add(normalized)
    if len(unique_suggestions) < 5:
        for name in columns:
            for question, category_name in (
                (f"Combien de valeurs manquent dans {name} ?", "qualite"),
                (f"Combien de valeurs distinctes contient {name} ?", "classement"),
            ):
                normalized = question.casefold()
                if len(question) <= 160 and normalized not in seen_questions:
                    unique_suggestions.append(Suggestion(
                        question=question,
                        category=category_name,
                        columns=[name],
                    ))
                    seen_questions.add(normalized)
                if len(unique_suggestions) >= 5:
                    break
            if len(unique_suggestions) >= 5:
                break
    return unique_suggestions[:6]


def _strip_code_fence(raw: str) -> str:
    value = raw.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, re.I | re.S)
    return match.group(1).strip() if match else value


def _validate_suggestions(raw: str, context: dict[str, Any]) -> list[Suggestion]:
    payload = json.loads(_strip_code_fence(raw))
    if not isinstance(payload, dict) or not isinstance(payload.get("suggestions"), list):
        raise ValueError("The LLM response is missing its suggestions array.")
    valid_columns, categories, periods = _get_values(context)
    results: list[Suggestion] = []
    seen: set[str] = set()
    for entry in payload["suggestions"]:
        try:
            suggestion = Suggestion.model_validate(entry)
        except (ValidationError, TypeError):
            continue
        question = suggestion.question.strip()
        key = question.casefold()
        if key in seen or len(question.split()) >= 18:
            continue
        if len(set(suggestion.columns)) != len(suggestion.columns):
            continue
        if any(column not in valid_columns or not column.strip() for column in suggestion.columns):
            continue
        if any(_PII_COLUMN.search(column) for column in suggestion.columns):
            continue
        reference_pool = valid_columns | categories | periods
        if reference_pool and not any(value.casefold() in question.casefold() for value in reference_pool):
            continue
        if re.search(
            r"\b(?:email|e-mail|téléphone|telephone|iban|cin|carte bancaire)\b"
            r"|\b(?:quel|quelle|qui)\s+(?:client|personne|utilisateur|employé|employe|patient)\b",
            question,
            re.I,
        ):
            continue
        seen.add(key)
        results.append(suggestion.model_copy(update={"question": question}))
        if len(results) == 6:
            break
    if len(results) < 3:
        for suggestion in generate_rule_suggestions(context):
            if suggestion.question.casefold() not in seen:
                results.append(suggestion)
                seen.add(suggestion.question.casefold())
            if len(results) == 6:
                break
    return results[:6]


def _call_groq(context: dict[str, Any], language: str) -> list[Suggestion] | None:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    prompt = f"""Tu es un analyste de données senior. Voici le profil d'un jeu de données (aucune ligne brute) :
{context_json}

Génère exactement 6 questions en {language} que l'utilisateur pourrait poser à ces données.
RÈGLES STRICTES :
1. Chaque question doit mentionner au moins un nom de colonne, une valeur de catégorie ou une période réellement présents dans le profil.
2. Chaque question doit être répondable par un calcul pandas sur ces colonnes (agrégation, classement, évolution, comparaison, répartition, corrélation).
3. Varie les types : au moins 1 classement, 1 évolution dans le temps (si une date existe), 1 comparaison entre catégories, 1 répartition ou part du total, 1 qualité/anomalie, et 1 question qui se prête à un graphique.
4. Ne suppose aucune colonne absente. Ne pose pas de question sur les personnes individuelles. Les colonnes identifiantes ou contenant des données personnelles ne doivent jamais être ciblées.
5. Si plusieurs fichiers : au moins 1 question de comparaison entre fichiers, seulement si des colonnes communes existent.
6. Si le contenu est un document texte : questions de synthèse, d'extraction de chiffres clés, de thèmes.
7. Questions courtes (< 18 mots), sans jargon, formulées comme un utilisateur non technique.
Réponds UNIQUEMENT avec ce JSON, sans texte autour :
{{"suggestions":[{{"question":"...","category":"classement|evolution|comparaison|repartition|qualite|synthese","columns":["col1","col2"],"chart":true}}]}}"""
    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=600,
        )
        content = response.choices[0].message.content or ""
        return _validate_suggestions(content, context)
    except Exception as error:
        # No user data or provider response is included in logs.
        logger.warning("Suggestion generation fell back to rules (%s).", type(error).__name__)
        return None


def get_suggestions(
    context: dict[str, Any],
    user_id: int,
    refresh: bool = False,
) -> SuggestionResponse:
    context_hash = hashlib.sha256(
        json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    key = f"{user_id}:{context_hash}"
    now = time.monotonic()

    with _cache_lock:
        cached = _cache.get(key)
        if not refresh and cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return SuggestionResponse(suggestions=cached[1], source="cache")
        if refresh:
            previous_refresh = _refresh_times.get(user_id, 0.0)
            if now - previous_refresh < 10:
                raise ValueError("refresh_too_soon")
            _refresh_times[user_id] = now

    generated = _call_groq(context, "fr")
    source: Literal["ai", "rules"] = "ai" if generated is not None else "rules"
    suggestions = generated if generated is not None else generate_rule_suggestions(context)
    with _cache_lock:
        if len(_cache) >= _CACHE_LIMIT:
            oldest = min(_cache, key=lambda cache_key: _cache[cache_key][0])
            _cache.pop(oldest, None)
        _cache[key] = (time.monotonic(), suggestions)
    return SuggestionResponse(suggestions=suggestions[:6], source=source)


def clear_suggestion_cache() -> None:
    with _cache_lock:
        _cache.clear()
        _refresh_times.clear()
