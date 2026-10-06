from __future__ import annotations

import math
import re
import warnings
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

MAX_PROFILE_ROWS = 100_000
DATE_NAME_HINT = re.compile(r"date|time|jour|mois|année|annee|timestamp", re.IGNORECASE)
DATE_VALUE_HINT = re.compile(r"[-/:T]")


def _json_safe(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _date_values(series: pd.Series, name: str) -> pd.Series | None:
    values = series.dropna()
    if values.empty or not (DATE_NAME_HINT.search(name) or values.astype(str).str.contains(DATE_VALUE_HINT).any()):
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(values, format="mixed", errors="coerce", utc=True)
    if len(parsed) and parsed.notna().mean() >= 0.8:
        return parsed
    return None


def _column_profile(series: pd.Series, name: str, position: int) -> tuple[dict[str, Any], list[dict[str, str]]]:
    total = len(series)
    missing_count = int(series.isna().sum())
    missing_percentage = (missing_count / total * 100) if total else 0.0
    present = series.dropna()
    unique_count = int(present.nunique(dropna=True))
    alerts: list[dict[str, str]] = []

    if missing_percentage > 50:
        alerts.append({
            "type": "missing_values",
            "severity": "warning",
            "column": name,
            "message": f"La colonne « {name} » contient {missing_percentage:.1f} % de valeurs manquantes.",
        })
    if not present.empty and unique_count == 1:
        alerts.append({
            "type": "constant_column",
            "severity": "info",
            "column": name,
            "message": f"La colonne « {name} » contient une seule valeur distincte.",
        })

    result: dict[str, Any] = {
        "name": name,
        "position": position,
        "detected_type": "texte",
        "missing_count": missing_count,
        "missing_percentage": round(missing_percentage, 2),
        "unique_count": unique_count,
    }
    if present.empty:
        result["detected_type"] = "texte"
        return result, alerts

    if is_bool_dtype(series.dtype):
        result["detected_type"] = "booléen"
        return result, alerts

    if is_numeric_dtype(series.dtype):
        numeric = pd.to_numeric(present, errors="coerce").dropna()
        result["detected_type"] = "numérique"
        result["statistics"] = {
            "min": _json_safe(numeric.min()) if not numeric.empty else None,
            "max": _json_safe(numeric.max()) if not numeric.empty else None,
            "mean": _json_safe(numeric.mean()) if not numeric.empty else None,
            "median": _json_safe(numeric.median()) if not numeric.empty else None,
        }
        _add_outlier_alert(name, numeric, alerts)
        return result, alerts

    text_values = present.astype(str).str.strip()
    nonempty_text = text_values[text_values.ne("")]
    normalized_tokens = set(nonempty_text.str.lower().unique())
    boolean_tokens = {"true", "false", "yes", "no", "oui", "non"}
    if normalized_tokens and normalized_tokens.issubset(boolean_tokens):
        result["detected_type"] = "booléen"
        return result, alerts

    numeric_values = pd.to_numeric(nonempty_text, errors="coerce")
    numeric_ratio = float(numeric_values.notna().mean()) if len(nonempty_text) else 0.0
    if len(nonempty_text) >= 2 and numeric_ratio >= 0.9:
        numeric = numeric_values.dropna()
        result["detected_type"] = "numérique"
        result["statistics"] = {
            "min": _json_safe(numeric.min()) if not numeric.empty else None,
            "max": _json_safe(numeric.max()) if not numeric.empty else None,
            "mean": _json_safe(numeric.mean()) if not numeric.empty else None,
            "median": _json_safe(numeric.median()) if not numeric.empty else None,
        }
        alerts.append({
            "type": "numeric_stored_as_text",
            "severity": "warning",
            "column": name,
            "message": f"La colonne « {name} » contient des nombres stockés comme texte.",
        })
        _add_outlier_alert(name, numeric, alerts)
        return result, alerts

    dates = _date_values(present, name)
    if dates is not None:
        result["detected_type"] = "date"
        result["date_range"] = {
            "min": _json_safe(dates.min()),
            "max": _json_safe(dates.max()),
        }
        if not pd.api.types.is_datetime64_any_dtype(series.dtype):
            alerts.append({
                "type": "date_stored_as_text",
                "severity": "warning",
                "column": name,
                "message": f"La colonne « {name} » contient des dates stockées comme texte.",
            })
        return result, alerts

    result["detected_type"] = (
        "catégorie"
        if unique_count <= min(50, max(10, int(len(present) * 0.2)))
        else "texte"
    )
    if result["detected_type"] == "catégorie":
        result["top_values"] = [
            {"value": _json_safe(value), "count": int(count)}
            for value, count in present.value_counts(dropna=True).head(3).items()
        ]
    return result, alerts


def _add_outlier_alert(name: str, values: pd.Series, alerts: list[dict[str, str]]) -> None:
    if len(values) < 4:
        return
    first_quartile = values.quantile(0.25)
    third_quartile = values.quantile(0.75)
    interquartile_range = third_quartile - first_quartile
    if not np.isfinite(interquartile_range) or interquartile_range == 0:
        return
    lower_bound = first_quartile - 1.5 * interquartile_range
    upper_bound = third_quartile + 1.5 * interquartile_range
    outlier_count = int(((values < lower_bound) | (values > upper_bound)).sum())
    if outlier_count:
        alerts.append({
            "type": "outliers",
            "severity": "info",
            "column": name,
            "message": f"La colonne « {name} » contient {outlier_count} valeur(s) atypique(s) selon la méthode IQR.",
        })


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """Profile at most 100,000 rows and return JSON-safe summary statistics."""
    sample = df.head(MAX_PROFILE_ROWS)
    columns: list[dict[str, Any]] = []
    alerts: list[dict[str, str]] = []
    duplicate_names: set[str] = set()
    seen_names: set[str] = set()

    for position, raw_name in enumerate(sample.columns):
        name = str(raw_name)
        if name in seen_names:
            duplicate_names.add(name)
        seen_names.add(name)
        column_profile, column_alerts = _column_profile(sample.iloc[:, position], name, position)
        columns.append(column_profile)
        alerts.extend(column_alerts)

    for name in sorted(duplicate_names):
        alerts.append({
            "type": "duplicate_column_names",
            "severity": "warning",
            "column": name,
            "message": f"Le nom de colonne « {name} » apparaît plusieurs fois.",
        })

    return _json_safe({
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "duplicate_rows": int(sample.duplicated().sum()),
        "sampled_rows": int(len(sample)),
        "columns": columns,
        "alerts": alerts,
    })
