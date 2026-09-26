"""
Service IA — Groq (Llama 3.3 70B)
===================================
Ce module expose une seule fonction publique :

    result = analyze_dataset(question, dataframe)

Elle :
  1. Construit un prompt contenant la question + un aperçu du DataFrame.
  2. Demande au LLM de générer du code Python/pandas qui répond à la question
     en utilisant une variable ``df`` déjà chargée.
  3. Exécute ce code dans un namespace isolé.
  4. En cas d'erreur d'exécution, renvoie le code + l'erreur au LLM pour
     correction (1 seul retry).
  5. Retourne un dict :
        {
            "answer":      str,            # texte de réponse en français
            "chart_config": str | None,    # JSON sérialisé {title, labels, values}
        }

Exemple d'usage rapide (hors FastAPI) :
---------------------------------------
    import pandas as pd
    from app.services.ai_service import analyze_dataset

    df = pd.read_csv("uploads/kpi_gateway.csv")
    result = analyze_dataset("Quelle est la moyenne par groupe ?", df)
    print(result["answer"])
    print(result["chart_config"])  # JSON string ou None

Prérequis :
-----------
    pip install groq
    GROQ_API_KEY=gsk_... dans le fichier .env
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import sys
from contextlib import redirect_stdout
from typing import Any

import pandas as pd
from groq import Groq

logger = logging.getLogger(__name__)

_MODEL = "qwen/qwen3.8-27b"
_MAX_PREVIEW_ROWS = 10
_MAX_STRING_COLS = 300  # tronque les noms de colonnes si trop longs dans le prompt


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _build_dataset_summary(df: pd.DataFrame) -> str:
    """Construit un résumé textuel du DataFrame pour le prompt."""
    rows, cols = df.shape
    col_types = {col: str(df[col].dtype) for col in df.columns}

    # Aperçu des premières lignes en CSV (léger, lisible par le LLM)
    preview_csv = df.head(_MAX_PREVIEW_ROWS).to_csv(index=False)

    lines = [
        f"Dimensions : {rows} lignes × {cols} colonnes",
        f"Colonnes et types : {json.dumps(col_types, ensure_ascii=False)}",
        "",
        f"Aperçu des {min(_MAX_PREVIEW_ROWS, rows)} premières lignes (CSV) :",
        preview_csv,
    ]
    return "\n".join(lines)


def _extract_python_code(text: str) -> str:
    """
    Extrait le premier bloc de code Python d'une réponse LLM.
    Accepte ```python ... ``` ou ``` ... ``` ou le texte brut si pas de
    marqueur trouvé.
    """
    # Bloc fenced avec ou sans langage
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Parfois le LLM ne met pas de fence — on retourne tout
    return text.strip()


def _execute_code(code: str, df: pd.DataFrame) -> tuple[str, dict[str, Any] | None]:
    """
    Exécute `code` dans un namespace contenant `df` et `pd`.
    Capture stdout.

    Returns
    -------
    output : str
        Tout ce qui a été imprimé (print) pendant l'exécution.
    chart_data : dict | None
        Si le code a assigné une variable `chart_data` (dict avec keys
        title, labels, values), elle est retournée ; sinon None.
    """
    namespace: dict[str, Any] = {"df": df, "pd": pd, "json": json}
    buf = io.StringIO()

    with redirect_stdout(buf):
        exec(code, namespace)  # noqa: S102

    output = buf.getvalue().strip()

    # Le code peut renseigner chart_data = {"title": ..., "labels": [...], "values": [...]}
    chart_data: dict[str, Any] | None = namespace.get("chart_data")
    if chart_data and not isinstance(chart_data, dict):
        chart_data = None

    return output, chart_data


def _build_first_prompt(question: str, dataset_summary: str) -> str:
    return f"""Tu es un expert en analyse de données. Tu reçois un DataFrame pandas appelé `df`.

DONNÉES :
{dataset_summary}

QUESTION DE L'UTILISATEUR :
{question}

INSTRUCTIONS STRICTES :
1. Génère **uniquement** du code Python/pandas valide qui répond à la question.
2. Utilise la variable `df` telle quelle (déjà chargée).
3. Affiche le résultat avec `print(...)` pour qu'il soit capturé.
4. Si la réponse se prête à un graphique (séries numériques, comparaisons, évolutions),
   assigne également :
       chart_data = {{"title": "...", "labels": [...], "values": [...]}}
   Les labels sont des strings, les values des floats.
   Limite à 20 points maximum pour la lisibilité.
5. Ne génère PAS d'explication, SEULEMENT le bloc de code Python entre ```python et ```.
6. N'utilise que les bibliothèques : pandas, json (déjà importées).
"""


def _build_retry_prompt(
    question: str,
    dataset_summary: str,
    failed_code: str,
    error_message: str,
) -> str:
    return f"""Le code Python suivant a provoqué une erreur lors de son exécution.

DONNÉES :
{dataset_summary}

QUESTION ORIGINALE :
{question}

CODE QUI A ÉCHOUÉ :
```python
{failed_code}
```

ERREUR :
{error_message}

Corrige le code pour qu'il fonctionne correctement.
Réponds UNIQUEMENT avec le code Python corrigé entre ```python et ```.
"""


def _build_summary_prompt(question: str, code_output: str) -> str:
    return f"""Tu es un assistant data analyst. L'utilisateur a posé la question suivante sur ses données :

QUESTION : {question}

RÉSULTAT DU CALCUL (sortie Python) :
{code_output}

Rédige une réponse claire, concise et professionnelle en français (3-5 phrases maximum)
qui explique ce que les données révèlent. Ne mentionne pas le code, parle directement
des insights. Si les chiffres sont importants, cite-les.
"""


# ---------------------------------------------------------------------------
# Fonction publique principale
# ---------------------------------------------------------------------------

def analyze_dataset(question: str, df: pd.DataFrame) -> dict[str, str | None]:
    """
    Analyse un DataFrame en répondant à une question en langage naturel.

    Parameters
    ----------
    question : str
        Question posée par l'utilisateur.
    df : pd.DataFrame
        DataFrame pandas déjà chargé.

    Returns
    -------
    dict with keys:
        "answer"      : str   — réponse textuelle en français
        "chart_config": str | None — JSON sérialisé {title, labels, values} ou None

    Raises
    ------
    RuntimeError
        Si GROQ_API_KEY est absent ou si toutes les tentatives échouent.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY manquante. Ajoutez-la dans votre fichier .env."
        )

    client = Groq(api_key=api_key)
    dataset_summary = _build_dataset_summary(df)

    # ── Étape 1 : demander du code au LLM ──────────────────────────────────
    logger.info("Groq — envoi du premier prompt (question: %r)", question[:80])

    first_response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": _build_first_prompt(question, dataset_summary)}],
        temperature=0.2,
        max_tokens=1024,
    )
    generated_code = _extract_python_code(
        first_response.choices[0].message.content or ""
    )
    logger.debug("Code généré :\n%s", generated_code)

    # ── Étape 2 : exécuter le code ─────────────────────────────────────────
    code_output: str = ""
    chart_data: dict | None = None

    try:
        code_output, chart_data = _execute_code(generated_code, df)
        logger.info("Exécution réussie. Output: %r", code_output[:200])

    except Exception as exec_error:  # noqa: BLE001
        error_msg = f"{type(exec_error).__name__}: {exec_error}"
        logger.warning("Erreur d'exécution — retry. Erreur : %s", error_msg)

        # ── Retry : envoyer le code + erreur au LLM pour correction ────────
        retry_response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": _build_retry_prompt(
                        question, dataset_summary, generated_code, error_msg
                    ),
                }
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        corrected_code = _extract_python_code(
            retry_response.choices[0].message.content or ""
        )
        logger.debug("Code corrigé :\n%s", corrected_code)

        try:
            code_output, chart_data = _execute_code(corrected_code, df)
            logger.info("Retry réussi. Output: %r", code_output[:200])
        except Exception as retry_error:  # noqa: BLE001
            # Les deux tentatives ont échoué — on retourne un message d'erreur propre
            logger.error("Retry échoué également : %s", retry_error)
            return {
                "answer": (
                    "Je n'ai pas pu analyser ces données automatiquement. "
                    "Essayez de reformuler votre question ou de vérifier le "
                    "format de votre fichier."
                ),
                "chart_config": None,
            }

    # ── Étape 3 : synthétiser la réponse en français ───────────────────────
    if not code_output:
        # Le code n'a rien affiché — on utilise quand même le LLM pour synthétiser
        code_output = "(aucune sortie texte — le calcul a été effectué sans print)"

    summary_response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": _build_summary_prompt(question, code_output),
            }
        ],
        temperature=0.4,
        max_tokens=512,
    )
    answer = (summary_response.choices[0].message.content or "").strip()

    # ── Étape 4 : sérialiser chart_config ─────────────────────────────────
    chart_config_json: str | None = None
    if chart_data:
        try:
            # Validation minimale
            labels = [str(label) for label in chart_data.get("labels", [])]
            values = [float(v) for v in chart_data.get("values", [])]
            title = str(chart_data.get("title", "Résultat"))

            if labels and values and len(labels) == len(values):
                chart_config_json = json.dumps(
                    {"title": title, "labels": labels, "values": values},
                    ensure_ascii=False,
                )
        except (TypeError, ValueError) as chart_err:
            logger.warning("chart_data invalide, ignoré : %s", chart_err)

    # Fallback : si pas de chart_data mais des colonnes numériques, on génère
    # un graphique basique à partir de l'aperçu (comportement identique au mock)
    if not chart_config_json:
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            col = numeric_cols[0]
            values_fallback = df[col].dropna().head(8).tolist()
            chart_config_json = json.dumps(
                {
                    "title": col,
                    "labels": [str(i + 1) for i in range(len(values_fallback))],
                    "values": [float(v) for v in values_fallback],
                },
                ensure_ascii=False,
            )

    return {"answer": answer, "chart_config": chart_config_json}
