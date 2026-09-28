"""
Service IA — Groq

Analyse un ou plusieurs datasets avec pandas.

Pour plusieurs fichiers, le DataFrame contient une colonne spéciale:
    __source_file

Cette colonne indique le fichier d'origine de chaque ligne.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from contextlib import redirect_stdout
from typing import Any

import pandas as pd
from groq import Groq

logger = logging.getLogger(__name__)

_MODEL = "qwen/qwen3.8-27b"
_MAX_PREVIEW_ROWS = 10


# ============================================================================
# HELPERS
# ============================================================================

def _build_dataset_summary(df: pd.DataFrame) -> str:
    """Construit un résumé des données pour le prompt IA."""

    rows, cols = df.shape

    source_info = ""

    if "__source_file" in df.columns:
        source_counts = (
            df["__source_file"]
            .value_counts(dropna=False)
            .to_dict()
        )

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

    return text.strip()


def _execute_code(
    code: str,
    df: pd.DataFrame,
) -> tuple[str, dict[str, Any] | None]:
    """
    Exécute le code généré par le LLM.

    Variables disponibles:
        df
        pd
        json
    """

    namespace: dict[str, Any] = {
        "df": df,
        "pd": pd,
        "json": json,
    }

    buffer = io.StringIO()

    with redirect_stdout(buffer):
        exec(code, namespace)  # noqa: S102

    output = buffer.getvalue().strip()

    chart_data = namespace.get("chart_data")

    if chart_data and not isinstance(chart_data, dict):
        chart_data = None

    return output, chart_data


# ============================================================================
# PROMPTS
# ============================================================================

def _build_first_prompt(
    question: str,
    dataset_summary: str,
) -> str:
    """Construit le prompt principal."""

    return f"""
Tu es un expert senior en analyse de données avec Python et pandas.

Tu reçois un DataFrame pandas appelé `df`.

IMPORTANT :
Le DataFrame peut contenir les données de PLUSIEURS fichiers.

Lorsqu'il y a plusieurs fichiers, la colonne spéciale
`__source_file` indique le fichier d'origine de chaque ligne.

DONNÉES :

{dataset_summary}

QUESTION DE L'UTILISATEUR :

{question}

INSTRUCTIONS STRICTES :

1. Génère UNIQUEMENT du code Python/pandas valide.

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

8. Affiche les résultats importants avec `print(...)`.

9. Si la question nécessite un graphique, crée une variable
   `chart_data` sous cette forme :

chart_data = {{
    "title": "Titre du graphique",
    "labels": ["A", "B"],
    "values": [10, 20]
}}

10. Les labels doivent être des chaînes.

11. Les values doivent être numériques.

12. Limite les graphiques à 20 points maximum.

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
) -> str:
    """Construit le prompt de correction."""

    return f"""
Le code Python suivant a provoqué une erreur.

DONNÉES :

{dataset_summary}

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
"""


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def analyze_dataset(
    question: str,
    df: pd.DataFrame,
) -> dict[str, str | None]:
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

    # ------------------------------------------------------------------------
    # DATASET SUMMARY
    # ------------------------------------------------------------------------

    dataset_summary = _build_dataset_summary(df)

    logger.info(
        "Analyse IA démarrée : %s lignes, %s colonnes",
        len(df),
        len(df.columns),
    )

    # ------------------------------------------------------------------------
    # STEP 1 — GENERATE PYTHON
    # ------------------------------------------------------------------------

    logger.info(
        "Groq — envoi du premier prompt : %r",
        question[:100],
    )

    first_response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": _build_first_prompt(
                    question,
                    dataset_summary,
                ),
            }
        ],
        temperature=0.2,
        max_tokens=2048,
    )

    generated_code = _extract_python_code(
        first_response.choices[0].message.content or ""
    )

    logger.debug(
        "Code généré :\n%s",
        generated_code,
    )

    # ------------------------------------------------------------------------
    # STEP 2 — EXECUTE CODE
    # ------------------------------------------------------------------------

    code_output = ""
    chart_data: dict[str, Any] | None = None

    try:
        code_output, chart_data = _execute_code(
            generated_code,
            df,
        )

        logger.info(
            "Exécution réussie : %r",
            code_output[:300],
        )

    except Exception as exec_error:

        error_message = (
            f"{type(exec_error).__name__}: {exec_error}"
        )

        logger.warning(
            "Erreur d'exécution — retry : %s",
            error_message,
        )

        # --------------------------------------------------------------------
        # RETRY
        # --------------------------------------------------------------------

        retry_response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": _build_retry_prompt(
                        question,
                        dataset_summary,
                        generated_code,
                        error_message,
                    ),
                }
            ],
            temperature=0.1,
            max_tokens=2048,
        )

        corrected_code = _extract_python_code(
            retry_response.choices[0].message.content or ""
        )

        logger.debug(
            "Code corrigé :\n%s",
            corrected_code,
        )

        try:
            code_output, chart_data = _execute_code(
                corrected_code,
                df,
            )

            logger.info(
                "Retry réussi : %r",
                code_output[:300],
            )

        except Exception as retry_error:

            logger.error(
                "Retry échoué : %s",
                retry_error,
            )

            return {
                "answer": (
                    "Je n'ai pas pu analyser ces données automatiquement. "
                    "Essayez de reformuler votre question ou de vérifier "
                    "le format de vos fichiers."
                ),
                "chart_config": None,
            }

    # ------------------------------------------------------------------------
    # STEP 3 — SUMMARY
    # ------------------------------------------------------------------------

    if not code_output:
        code_output = (
            "(Aucune sortie texte. "
            "Le calcul a peut-être été effectué sans print.)"
        )

    summary_response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": _build_summary_prompt(
                    question,
                    code_output,
                ),
            }
        ],
        temperature=0.4,
        max_tokens=768,
    )

    answer = (
        summary_response.choices[0].message.content or ""
    ).strip()

    # ------------------------------------------------------------------------
    # STEP 4 — CHART
    # ------------------------------------------------------------------------

    chart_config_json: str | None = None

    if chart_data:
        try:
            labels = [
                str(label)
                for label in chart_data.get("labels", [])
            ]

            values = [
                float(value)
                for value in chart_data.get("values", [])
            ]

            title = str(
                chart_data.get(
                    "title",
                    "Résultat",
                )
            )

            if (
                labels
                and values
                and len(labels) == len(values)
            ):
                chart_config_json = json.dumps(
                    {
                        "title": title,
                        "labels": labels,
                        "values": values,
                    },
                    ensure_ascii=False,
                )

        except (TypeError, ValueError) as chart_error:
            logger.warning(
                "chart_data invalide : %s",
                chart_error,
            )

    # ------------------------------------------------------------------------
    # STEP 5 — FALLBACK CHART
    # ------------------------------------------------------------------------

    if not chart_config_json:

        numeric_cols = [
            column
            for column in df.select_dtypes(
                include="number"
            ).columns
            if column != "__source_file"
        ]

        if numeric_cols:

            column = numeric_cols[0]

            values_fallback = (
                df[column]
                .dropna()
                .head(8)
                .tolist()
            )

            chart_config_json = json.dumps(
                {
                    "title": column,
                    "labels": [
                        str(index + 1)
                        for index in range(
                            len(values_fallback)
                        )
                    ],
                    "values": [
                        float(value)
                        for value in values_fallback
                    ],
                },
                ensure_ascii=False,
            )

    # ------------------------------------------------------------------------
    # RETURN
    # ------------------------------------------------------------------------

    return {
        "answer": answer,
        "chart_config": chart_config_json,
    }