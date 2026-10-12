"""
Service IA — Groq

Analyse un ou plusieurs datasets avec pandas.

Pour plusieurs fichiers, le DataFrame contient une colonne spéciale:
    __source_file

Cette colonne indique le fichier d'origine de chaque ligne.
"""

from __future__ import annotations

import ast
import io
import json
import logging
import math
import os
import re
from contextlib import redirect_stdout
from typing import Any

import pandas as pd
from groq import Groq

from app.core.groq_limit import acquire_groq_slot
from app.services.pii_service import sanitize_text

logger = logging.getLogger(__name__)

_MODEL = "qwen/qwen3.8-27b"
_MAX_PREVIEW_ROWS = 10
_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}
_BLOCKED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}
_BLOCKED_ATTRIBUTES = {
    "read_clipboard",
    "read_csv",
    "read_excel",
    "read_json",
    "read_pickle",
    "read_sql",
    "plot",
    "savefig",
    "system",
    "popen",
    "run",
    "Popen",
    "socket",
    "urlopen",
    "to_csv",
    "to_excel",
    "to_json",
    "to_pickle",
    "to_sql",
}
_SAFE_MODULE_ATTRIBUTES = {
    "json": {"dumps", "loads"},
    "pd": {
        "DataFrame",
        "Series",
        "Timestamp",
        "Timedelta",
        "Grouper",
        "concat",
        "crosstab",
        "cut",
        "isna",
        "notna",
        "qcut",
        "to_datetime",
        "to_numeric",
    },
}


class _GeneratedCodeValidator(ast.NodeVisitor):
    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__"):
            raise ValueError(f"Generated code cannot access name {node.id!r}.")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        raise ValueError("Generated code cannot import modules.")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise ValueError("Generated code cannot import modules.")

    def visit_While(self, node: ast.While) -> None:
        raise ValueError("Generated code cannot use unbounded loops.")

    def visit_For(self, node: ast.For) -> None:
        raise ValueError("Generated code cannot use unbounded loops.")

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        raise ValueError("Generated code cannot use unbounded loops.")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        raise ValueError("Generated code cannot define asynchronous functions.")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_") or node.attr in _BLOCKED_ATTRIBUTES:
            raise ValueError(f"Generated code cannot access attribute {node.attr!r}.")
        if isinstance(node.value, ast.Name):
            allowed = _SAFE_MODULE_ATTRIBUTES.get(node.value.id)
            if allowed is not None and node.attr not in allowed:
                raise ValueError(
                    f"Generated code cannot access {node.value.id}.{node.attr}."
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_CALLS:
            raise ValueError(f"Generated code cannot call {node.func.id!r}.")
        self.generic_visit(node)


def _validate_generated_code(code: str) -> ast.AST:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as error:
        raise ValueError("Generated code contains invalid Python syntax.") from error
    _GeneratedCodeValidator().visit(tree)
    return tree


def _create_completion(client: Groq, usage_totals: dict[str, int], **kwargs: Any):
    acquire_groq_slot()
    response = client.chat.completions.create(**kwargs)
    usage = getattr(response, "usage", None)
    if usage is not None:
        usage_totals["tokens_in"] += int(getattr(usage, "prompt_tokens", 0) or 0)
        usage_totals["tokens_out"] += int(getattr(usage, "completion_tokens", 0) or 0)
    return response


# ============================================================================
# HELPERS
# ============================================================================

def _build_dataset_summary(df: pd.DataFrame) -> str:
    """Construit un résumé des données pour le prompt IA."""

    rows, cols = df.shape

    source_info = ""

    if "__source_file" in df.columns:
        source_counts = df["__source_file"].value_counts(dropna=False).to_dict()
        source_counts = {
            sanitize_text(str(filename)): int(count)
            for filename, count in source_counts.items()
        }

        source_info = (
            "\nFICHIERS SOURCES :\n"
            + json.dumps(
                source_counts,
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )

    col_types = {
        str(column): str(df[column].dtype)
        for column in df.columns
    }

    preview = df.head(_MAX_PREVIEW_ROWS)
    preview_csv = preview.to_csv(index=False)
    if "content" in df.columns and len(preview_csv) > 10000:
        preview_csv = preview_csv[:10000] + "\n[Contenu tronqué pour respecter la limite du service IA.]"

    return "\n".join(
        [
            f"Dimensions globales : {rows} lignes × {cols} colonnes",
            source_info,
            "Colonnes et types :",
            json.dumps(
                col_types,
                ensure_ascii=False,
                indent=2,
            ),
            "",
            f"Aperçu des {min(_MAX_PREVIEW_ROWS, rows)} premières lignes :",
            preview_csv,
        ]
    )


def _extract_python_code(text: str) -> str:
    """Extrait le code Python généré par le LLM."""

    match = re.search(
        r"```(?:python)?\s*(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    open_fence = re.search(
        r"```(?:python)?\s*(.*)$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if open_fence:
        return open_fence.group(1).strip()

    return text.strip()


def _execute_code(
    code: str,
    df: pd.DataFrame,
) -> tuple[str, dict[str, Any] | None, pd.DataFrame | None]:
    """
    Exécute le code généré par le LLM.

    Variables disponibles:
        df
        pd
        json
    """

    tree = _validate_generated_code(code)
    namespace: dict[str, Any] = {
        "df": df,
        "pd": pd,
        "json": json,
        "__builtins__": _SAFE_BUILTINS,
    }

    buffer = io.StringIO()

    with redirect_stdout(buffer):
        exec(compile(tree, "<generated-analysis>", "exec"), namespace)  # noqa: S102

    output = buffer.getvalue().strip()

    chart_data = namespace.get("chart_data")
    result_table = namespace.get("result_table")

    if chart_data and not isinstance(chart_data, dict):
        chart_data = None
    if not isinstance(result_table, pd.DataFrame):
        result_table = None
    elif len(result_table) > 1000:
        result_table = result_table.head(1000).copy()

    return output, chart_data, result_table


# ============================================================================
# PROMPTS
# ============================================================================

def _build_first_prompt(
    question: str,
    dataset_summary: str,
    generate_chart: bool,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Construit le prompt principal."""
    chart_instruction = (
        "9. Un fichier CSV/Excel est présent. Crée un graphique pertinent si possible en agrégeant les données, sans parcourir ni imprimer chaque ligne."
        if generate_chart
        else "9. Si la question nécessite un graphique, crée une variable"
    )

    return f"""
Tu es un expert senior en analyse de données avec Python et pandas.

Tu reçois un DataFrame pandas appelé `df`.

IMPORTANT :
Le DataFrame peut contenir les données de PLUSIEURS fichiers.

Lorsqu'il y a plusieurs fichiers, la colonne spéciale
`__source_file` indique le fichier d'origine de chaque ligne.

DONNÉES :

{dataset_summary}

ÉCHANGES PRÉCÉDENTS (textes produits précédemment; aucune ligne brute) :

{_serialize_conversation_history(conversation_history or [])}

QUESTION DE L'UTILISATEUR :

{question}

INSTRUCTIONS STRICTES :

1. Génère uniquement du code Python/pandas valide, très concis (moins de 400 tokens), sans commentaire ni Markdown. La question fournie est autonome; utilise l'historique uniquement pour interpréter ses références.

2. Utilise la variable `df` telle quelle.

3. Si plusieurs fichiers sont présents, utilise
   `__source_file` pour distinguer les fichiers.

4. Ne suppose PAS que les différents fichiers ont les mêmes colonnes.

5. Si les fichiers ont des structures différentes, analyse-les
   séparément lorsque cela est pertinent.

6. Si l'utilisateur demande une comparaison entre plusieurs fichiers,
   compare explicitement les données de chaque fichier.

7. Si l'utilisateur demande d'analyser plusieurs documents,
   prends en compte TOUS les fichiers disponibles.

8. Affiche une réponse courte à la question avec `print(...)`. Ne réimprime pas toutes les lignes ni le contenu intégral des documents.

8a. Si tu produis un tableau comme résultat, affecte le DataFrame final à `result_table` (maximum 1 000 lignes).

{chart_instruction} Dans ce cas, crée une variable `chart_data` sous cette forme :

chart_data = {{
    "type": "bar",
    "title": "Titre du graphique",
    "x_label": "Axe horizontal",
    "y_label": "Axe vertical",
    "labels": ["A", "B"],
    "series": [
        {{"name": "Série 1", "values": [10, 20]}}
    ]
}}

10. Choisis le type selon ces règles : évolution temporelle -> "line" ; parts d'un tout avec au plus 8 catégories -> "pie" ; relation entre deux colonnes numériques -> "scatter" ; sinon -> "bar".

11. Les labels doivent être des chaînes; chaque série contient des nombres finis dans le même ordre et en même nombre que les labels.

12. Limite à 20 points (50 pour "scatter"); agrège les données au lieu de tronquer arbitrairement les premières lignes.

13. Utilise uniquement les bibliothèques :
    - pandas
    - json

14. Ne génère aucune explication.

15. Réponds uniquement avec du code Python.
"""


def _build_retry_prompt(
    question: str,
    dataset_summary: str,
    failed_code: str,
    error_message: str,
    generate_chart: bool,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Construit le prompt de correction."""
    chart_instruction = (
        "- Comme des données CSV/Excel sont présentes, ajoute un graphique agrégé avec chart_data si possible."
        if generate_chart
        else ""
    )

    return f"""
Le code Python suivant a provoqué une erreur.

DONNÉES :

{dataset_summary}

ÉCHANGES PRÉCÉDENTS (textes produits précédemment; aucune ligne brute) :

{_serialize_conversation_history(conversation_history or [])}

QUESTION :

{question}

CODE QUI A ÉCHOUÉ :

{failed_code}

ERREUR :

{error_message}

Corrige le code pour qu'il fonctionne correctement.

IMPORTANT :

- Utilise `df`.
- Si plusieurs fichiers sont présents, utilise `__source_file`.
- Ne suppose pas que les fichiers ont les mêmes colonnes.
- Utilise uniquement pandas et json.
- Affiche le résultat avec print(...).
- Si tu produis un tableau, affecte le DataFrame final à `result_table` (maximum 1 000 lignes).
- Garde le code sous 400 tokens, sans commentaires; n'imprime pas toutes les lignes ou le contenu intégral des documents.
{chart_instruction}
- Si tu crées un graphique, utilise la forme chart_data suivante : {{"type":"bar|line|pie|scatter","title":"...","x_label":"...","y_label":"...","labels":["..."],"series":[{{"name":"...","values":[1]}}]}}.
- Choisis "line" pour une évolution temporelle, "pie" pour les parts d'un tout avec au plus 8 catégories, "scatter" pour deux variables numériques avec labels x numériques, sinon "bar".
- Une série doit avoir une valeur finie par label; limite à 20 points (50 pour scatter), en agrégeant plutôt qu'en tronquant.
- Réponds uniquement avec du code Python.
"""


def _build_summary_prompt(
    question: str,
    code_output: str,
) -> str:
    """Construit le prompt pour la réponse finale."""

    return f"""
Tu es un assistant expert en analyse de données.

QUESTION DE L'UTILISATEUR :

{question}

RÉSULTAT DU CALCUL PYTHON :

{code_output}

Rédige une réponse claire, concise et professionnelle en français.

IMPORTANT :

- Réponds directement à la question.
- Si plusieurs fichiers ont été analysés, mentionne les fichiers
  lorsque c'est pertinent.
- Si une comparaison a été demandée, explique les différences.
- Cite les chiffres importants.
- Ne mentionne pas le code Python.
- Ne parle pas de détails techniques inutiles.
- Maximum 5 phrases.
- Après la réponse, fournis aussi une explication très simple du code : quelles données sont filtrées, puis quel calcul est fait.
- Réponds uniquement avec un JSON strict de la forme {{"answer":"réponse à l'utilisateur","code_explanation":"explication du calcul en une phrase"}}.
"""


def _parse_summary(text: str) -> tuple[str, str]:
    """Read the answer and code explanation from the same LLM response."""
    cleaned = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned, ""
    if not isinstance(payload, dict):
        return cleaned, ""
    answer = payload.get("answer")
    explanation = payload.get("code_explanation")
    if not isinstance(answer, str):
        return cleaned, ""
    return answer.strip(), explanation.strip() if isinstance(explanation, str) else ""


def _bounded_conversation_history(
    history: list[dict[str, str]],
    max_chars: int = 2400,
) -> list[dict[str, str]]:
    """Retient uniquement trois échanges récents et borne leur taille."""
    bounded = []
    used_chars = 0
    for exchange in history[-3:]:
        item = {
            "question": str(exchange.get("question", ""))[:350],
            "answer": str(exchange.get("answer", ""))[:500],
            "code": str(exchange.get("code", ""))[:450],
        }
        item_size = sum(len(value) for value in item.values())
        if used_chars + item_size > max_chars:
            remaining = max_chars - used_chars
            if remaining <= 0:
                break
            for key in ("question", "answer", "code"):
                item[key] = item[key][:remaining]
                remaining -= len(item[key])
            item_size = sum(len(value) for value in item.values())
        bounded.append(item)
        used_chars += item_size
    return bounded


def _serialize_conversation_history(history: list[dict[str, str]]) -> str:
    return json.dumps(_bounded_conversation_history(history), ensure_ascii=False)


def _resolve_follow_up(
    client: Groq,
    question: str,
    history: list[dict[str, str]],
    usage_totals: dict[str, int] | None = None,
) -> tuple[str | None, str | None]:
    """Réécrit une question contextuelle en question autonome ou demande une précision."""
    response = _create_completion(client, usage_totals if usage_totals is not None else {"tokens_in": 0, "tokens_out": 0},
        model=_MODEL,
        messages=[{
            "role": "user",
            "content": f"""
Tu reformules les questions de suivi d'un assistant d'analyse de données.
Historique récent (textes déjà produits uniquement; aucune ligne brute) :
{_serialize_conversation_history(history)}

Nouvelle question : {question[:1000]}

Réponds en JSON strict uniquement :
{{"status":"ready","question":"question autonome"}}
ou
{{"status":"clarify","question":"question courte pour lever l'ambiguïté"}}
N'invente jamais de filtre, catégorie ou mesure absent de l'historique. Si une référence ne peut pas être résolue sans deviner, demande une clarification.
""",
        }],
        temperature=0,
        max_tokens=300,
    )
    text = (response.choices[0].message.content or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return None, "Pouvez-vous préciser votre question pour que je puisse l’analyser sans supposer le contexte ?"
    if not isinstance(result, dict) or not isinstance(result.get("question"), str):
        return None, "Pouvez-vous préciser votre question pour que je puisse l’analyser sans supposer le contexte ?"
    resolved = result["question"].strip()[:1000]
    if result.get("status") == "ready" and resolved:
        return resolved, None
    if result.get("status") == "clarify" and resolved:
        return None, resolved
    return None, "Pouvez-vous préciser votre question pour que je puisse l’analyser sans supposer le contexte ?"


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def analyze_dataset(
    question: str,
    df: pd.DataFrame,
    generate_chart: bool = False,
    conversation_history: list[dict[str, str]] | None = None,
    prompt_dataframe: pd.DataFrame | None = None,
    sensitive_values: list[str] | None = None,
    pii_column_count: int = 0,
) -> dict[str, Any]:
    """
    Analyse un ou plusieurs datasets.

    Parameters
    ----------
    question:
        Question posée par l'utilisateur.

    df:
        DataFrame contenant les données.
        Pour plusieurs fichiers, __source_file identifie
        le fichier d'origine.

    generate_chart:
        Génère un graphique complémentaire quand des données
        CSV/Excel sont présentes.

    Returns
    -------
    dict
        answer:
            Réponse textuelle.

        chart_config:
            Configuration JSON du graphique ou None.
    """

    # ------------------------------------------------------------------------
    # API KEY
    # ------------------------------------------------------------------------

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY manquante. Ajoutez-la dans votre fichier .env."
        )

    client = Groq(api_key=api_key)
    usage_totals = {"tokens_in": 0, "tokens_out": 0}
    safe_question = sanitize_text(question, sensitive_values)
    safe_history = [
        {
            key: sanitize_text(str(value), sensitive_values)
            for key, value in exchange.items()
        }
        for exchange in (conversation_history or [])
    ]
    conversation_history = _bounded_conversation_history(safe_history)
    resolved_question = question
    if conversation_history:
        resolved_question, clarification = _resolve_follow_up(
            client,
            sanitize_text(resolved_question, sensitive_values),
            conversation_history,
            usage_totals,
        )
        if resolved_question is None:
            return {
                "answer": sanitize_text(
                    clarification or "Pouvez-vous préciser votre question ?",
                    sensitive_values,
                ),
                "chart_config": None,
                "code": None,
                "retried": False,
                "code_explanation": None,
                "tokens_in": usage_totals["tokens_in"],
                "tokens_out": usage_totals["tokens_out"],
                "model": _MODEL,
            }

    # ------------------------------------------------------------------------
    # DATASET SUMMARY
    # ------------------------------------------------------------------------

    dataset_summary = _build_dataset_summary(prompt_dataframe if prompt_dataframe is not None else df)

    logger.info(
        "Analyse IA démarrée : %s lignes, %s colonnes",
        len(df),
        len(df.columns),
    )

    # ------------------------------------------------------------------------
    # STEP 1 — GENERATE PYTHON
    # ------------------------------------------------------------------------

    logger.info(
        "Groq prompt prepared: rows=%s columns=%s pii_columns=%s",
        len(df),
        len(df.columns),
        pii_column_count,
    )

    first_response = _create_completion(client, usage_totals,
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": _build_first_prompt(
                    sanitize_text(resolved_question, sensitive_values),
                    dataset_summary,
                    generate_chart,
                    conversation_history,
                ),
            }
        ],
        temperature=0.2,
        max_tokens=768,
    )

    generated_code = _extract_python_code(
        first_response.choices[0].message.content or ""
    )

    # ------------------------------------------------------------------------
    # STEP 2 — EXECUTE CODE
    # ------------------------------------------------------------------------

    code_output = ""
    chart_data: dict[str, Any] | None = None
    result_table: pd.DataFrame | None = None
    executed_code = generated_code
    code_retried = False

    try:
        code_output, chart_data, result_table = _execute_code(executed_code, df)

        logger.info(
            "Local code execution succeeded: output_chars=%s",
            len(code_output),
        )

    except Exception as exec_error:

        error_message = (
            f"{type(exec_error).__name__}: {sanitize_text(str(exec_error), sensitive_values)}"
        )

        logger.warning(
            "Local execution failed; retrying: error_type=%s",
            type(exec_error).__name__,
        )

        # --------------------------------------------------------------------
        # RETRY
        # --------------------------------------------------------------------

        retry_response = _create_completion(client, usage_totals,
            model=_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": _build_retry_prompt(
                        safe_question,
                        dataset_summary,
                        sanitize_text(generated_code, sensitive_values),
                        error_message,
                        generate_chart,
                        conversation_history,
                    ),
                }
            ],
            temperature=0.1,
            max_tokens=768,
        )

        corrected_code = _extract_python_code(
            retry_response.choices[0].message.content or ""
        )

        try:
            code_output, chart_data, result_table = _execute_code(
                corrected_code,
                df,
            )
            executed_code = corrected_code
            code_retried = True

            logger.info(
                "Local retry succeeded: output_chars=%s",
                len(code_output),
            )

        except Exception as retry_error:

            logger.error(
                "Retry échoué : %s",
                type(retry_error).__name__,
            )

            return {
                "answer": (
                    "Je n'ai pas pu analyser ces données automatiquement. "
                    "Essayez de reformuler votre question ou de vérifier "
                    "le format de vos fichiers."
                ),
                "chart_config": None,
                "code": None,
                "retried": True,
                "code_explanation": None,
                "tokens_in": usage_totals["tokens_in"],
                "tokens_out": usage_totals["tokens_out"],
                "model": _MODEL,
            }

    # ------------------------------------------------------------------------
    # STEP 3 — SUMMARY
    # ------------------------------------------------------------------------

    if not code_output:
        code_output = (
            "(Aucune sortie texte. "
            "Le calcul a peut-être été effectué sans print.)"
        )

    summary_response = _create_completion(client, usage_totals,
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": _build_summary_prompt(
                    safe_question,
                    sanitize_text(code_output, sensitive_values),
                ),
            }
        ],
        temperature=0.4,
        max_tokens=768,
    )

    summary_text = (
        summary_response.choices[0].message.content or ""
    ).strip()
    answer, code_explanation = _parse_summary(summary_text)
    answer = sanitize_text(answer, sensitive_values)
    code_explanation = sanitize_text(code_explanation, sensitive_values)

    # ------------------------------------------------------------------------
    # STEP 4 — CHART
    # ------------------------------------------------------------------------

    chart_config_json: str | None = None
    if chart_data is not None:
        try:
            validated_chart = _validate_chart_data(chart_data)
            if validated_chart is not None:
                chart_config_json = json.dumps(
                    validated_chart,
                    ensure_ascii=False,
                    allow_nan=False,
                )
            else:
                logger.info("Graphique ignoré : configuration invalide")
        except (TypeError, ValueError) as chart_error:
            logger.warning("Graphique ignoré : configuration invalide (%s)", type(chart_error).__name__)

    # ------------------------------------------------------------------------
    # RETURN
    # ------------------------------------------------------------------------

    return {
        "answer": answer,
        "chart_config": chart_config_json,
        "code": executed_code,
        "retried": code_retried,
        "code_explanation": code_explanation,
        "result_table": _serialize_result_table(result_table),
        "tokens_in": usage_totals["tokens_in"],
        "tokens_out": usage_totals["tokens_out"],
        "model": _MODEL,
    }


def _serialize_result_table(result_table: pd.DataFrame | None) -> dict[str, Any] | None:
    """Convertit le tableau en données JSON sûres, limitées à 1 000 lignes."""
    if result_table is None:
        return None

    def json_value(value: Any) -> Any:
        if hasattr(value, "item"):
            value = value.item()
        if value is None:
            return None
        if isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_value(item) for item in value]
        try:
            missing = pd.isna(value)
            if isinstance(missing, bool) and missing:
                return None
        except (TypeError, ValueError):
            pass
        return str(value)

    limited = result_table.head(1000)
    return {
        "columns": [str(column) for column in limited.columns],
        "rows": [
            [json_value(value) for value in row]
            for row in limited.itertuples(index=False, name=None)
        ],
    }


def _validate_chart_data(chart_data: dict[str, Any]) -> dict[str, Any] | None:
    """Valide les données du graphique et convertit le format historique."""
    chart_type = chart_data.get("type", "bar")
    if not isinstance(chart_type, str) or chart_type not in {"bar", "line", "pie", "scatter"}:
        return None

    labels = chart_data.get("labels")
    if not isinstance(labels, list) or not labels:
        return None

    if "series" not in chart_data and isinstance(chart_data.get("values"), list):
        series = [{"name": str(chart_data.get("title") or "Valeur"), "values": chart_data["values"]}]
    else:
        series = chart_data.get("series")
    if not isinstance(series, list) or not 1 <= len(series) <= 8:
        return None

    max_points = 50 if chart_type == "scatter" else 20
    if len(labels) > max_points:
        return None

    normalized_series: list[dict[str, Any]] = []
    series_names: set[str] = set()
    for item in series:
        if not isinstance(item, dict) or not isinstance(item.get("values"), list):
            return None
        values = item["values"]
        if len(values) != len(labels) or not isinstance(item.get("name", ""), str):
            return None
        normalized_values = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                return None
            normalized_values.append(numeric_value)
        name = item.get("name") or f"Série {len(normalized_series) + 1}"
        if name in series_names:
            return None
        series_names.add(name)
        normalized_series.append({
            "name": name,
            "values": normalized_values,
        })

    if chart_type == "pie" and (
        len(labels) > 8
        or len(normalized_series) != 1
        or any(value < 0 for value in normalized_series[0]["values"])
    ):
        return None
    if chart_type == "scatter":
        try:
            [float(label) for label in labels]
        except (TypeError, ValueError):
            return None

    return {
        "type": chart_type,
        "title": str(chart_data.get("title") or "Résultat"),
        "x_label": str(chart_data.get("x_label") or ""),
        "y_label": str(chart_data.get("y_label") or ""),
        "labels": [str(label) for label in labels],
        "series": normalized_series,
    }