from __future__ import annotations

import ipaddress
import re
from collections import Counter
from typing import Any, Literal

import pandas as pd

PiiPreference = Literal["exclude", "mask", "allow"]

_COLUMN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"(?<![a-z])(?:e[\s_-]?mail|courriel)(?![a-z])", re.I)),
    ("téléphone", re.compile(r"(?<![a-z])(?:tel|téléphone|telephone|mobile|portable|phone|fax)(?![a-z])", re.I)),
    ("iban", re.compile(r"(?<![a-z])iban(?![a-z])", re.I)),
    ("carte bancaire", re.compile(r"(?<![a-z])(?:carte|card|cc)[\s_-]?(?:bancaire|credit|crédit|number|numero|numéro)?(?![a-z])", re.I)),
    ("CIN", re.compile(r"(?<![a-z])(?:cin|identité|identite|national[\s_-]?id)(?![a-z])", re.I)),
    ("adresse", re.compile(r"(?<![a-z])(?:adresse|address|street|rue)(?![a-z])", re.I)),
    ("nom", re.compile(r"(?<![a-z])(?:nom|prénom|prenom|name|surname|lastname|firstname)(?![a-z])", re.I)),
)
_EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.I)
_IBAN_RE = re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,30}(?![A-Z0-9])", re.I)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_CIN_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")
_IP_RE = re.compile(
    r"(?<![\w:])(?:"
    r"(?:\d{1,3}\.){3}\d{1,3}"
    r"|(?:[A-Fa-f0-9]{0,4}:){2,7}[A-Fa-f0-9]{0,4}"
    r")(?![\w:])"
)
_PHONE_RE = re.compile(r"(?<!\w)\+?(?:\d[\d\s().-]{5,}\d)(?!\w)")
_DATE_RE = re.compile(r"^\s*(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s*$")
_MASKS = {
    "email": "[EMAIL]",
    "téléphone": "[TEL]",
    "iban": "[IBAN]",
    "carte bancaire": "[CARTE]",
    "CIN": "[CIN]",
    "IP": "[IP]",
    "nom": "[NOM]",
    "adresse": "[ADRESSE]",
    "donnée personnelle": "[DONNÉE PERSONNELLE]",
}


def _luhn_valid(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _iban_valid(value: str) -> bool:
    compact = re.sub(r"[\s-]", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
        return False
    rearranged = compact[4:] + compact[:4]
    digits = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    remainder = 0
    for start in range(0, len(digits), 7):
        remainder = int(f"{remainder}{digits[start:start + 7]}") % 97
    return remainder == 1


def _value_categories(value: str) -> set[str]:
    categories: set[str] = set()
    if _EMAIL_RE.search(value):
        categories.add("email")
    if any(_iban_valid(match.group(0)) for match in _IBAN_RE.finditer(value)):
        categories.add("iban")
    if any(_luhn_valid(match.group(0)) for match in _CARD_RE.finditer(value)):
        categories.add("carte bancaire")
    if _CIN_RE.search(value):
        categories.add("CIN")
    for match in _IP_RE.finditer(value):
        try:
            ipaddress.ip_address(match.group(0))
            categories.add("IP")
        except ValueError:
            continue
    if not categories and not _DATE_RE.fullmatch(value):
        for match in _PHONE_RE.finditer(value):
            digits = re.sub(r"\D", "", match.group(0))
            if 8 <= len(digits) <= 15:
                categories.add("téléphone")
                break
    return categories


def detect_pii(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Détecte les colonnes et cellules susceptibles de contenir des données personnelles."""
    columns = []
    for position, name_value in enumerate(dataframe.columns):
        name = str(name_value)
        series = dataframe.iloc[:, position]
        header_category = next(
            (category for category, pattern in _COLUMN_RULES if pattern.search(name)),
            None,
        )
        value_categories: Counter[str] = Counter()
        affected = 0
        non_null_count = int(series.notna().sum())
        for raw_value in series.dropna():
            value = str(raw_value)
            categories = _value_categories(value)
            if categories:
                affected += 1
                value_categories.update(categories)
        if header_category or affected:
            category = header_category or value_categories.most_common(1)[0][0]
            columns.append({
                "name": name,
                "position": position,
                "category": category,
                "values_touched": non_null_count if header_category else affected,
                "confidence": "high" if header_category or affected > 0 else "medium",
            })
    return {
        "columns": columns,
        "column_count": len(columns),
        "values_touched": sum(item["values_touched"] for item in columns),
    }


def _redact_text_value(value: str) -> str:
    value = _EMAIL_RE.sub(_MASKS["email"], value)
    value = _IBAN_RE.sub(
        lambda match: _MASKS["iban"] if _iban_valid(match.group(0)) else match.group(0),
        value,
    )
    value = _CARD_RE.sub(
        lambda match: _MASKS["carte bancaire"] if _luhn_valid(match.group(0)) else match.group(0),
        value,
    )
    value = _CIN_RE.sub(_MASKS["CIN"], value)
    value = _IP_RE.sub(
        lambda match: _MASKS["IP"]
        if _valid_ip(match.group(0))
        else match.group(0),
        value,
    )
    value = _PHONE_RE.sub(
        lambda match: _MASKS["téléphone"]
        if 8 <= len(re.sub(r"\D", "", match.group(0))) <= 15 and not _DATE_RE.fullmatch(match.group(0))
        else match.group(0),
        value,
    )
    return value


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def prepare_dataframes(
    dataframe: pd.DataFrame,
    report: dict[str, Any] | None = None,
    preferences: dict[str, PiiPreference] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], list[str]]:
    """Returns local execution data, a prompt-safe copy, the PII report and masked values."""
    report = report or detect_pii(dataframe)
    preferences = preferences or {}
    execution = dataframe.copy()
    prompt = dataframe.copy()
    sensitive_values: list[str] = []
    drop_positions: set[int] = set()

    for item in report["columns"]:
        name = item["name"]
        position = int(item["position"])
        preference = preferences.get(name, "mask")
        if preference == "exclude":
            drop_positions.add(position)
            continue
        if preference == "allow":
            continue
        series = dataframe.iloc[:, position]
        sensitive_values.extend(
            str(value)
            for value in series.dropna().unique()
            if len(str(value)) >= 3
        )
        category = item["category"]
        mask = _MASKS.get(category, _MASKS["donnée personnelle"])
        prompt.iloc[:, position] = series.map(
            lambda value: None if pd.isna(value) else _redact_text_value(str(value))
            if _value_categories(str(value))
            else mask
        )

    if drop_positions:
        keep_positions = [index for index in range(dataframe.shape[1]) if index not in drop_positions]
        execution = execution.iloc[:, keep_positions].copy()
        prompt = prompt.iloc[:, keep_positions].copy()

    return execution, prompt, report, sensitive_values


def sanitize_text(text: str, sensitive_values: list[str] | None = None) -> str:
    """Redacts recognized PII patterns and exact values from masked columns."""
    cleaned = _redact_text_value(str(text))
    for value in sorted(set(sensitive_values or []), key=len, reverse=True):
        if len(value) >= 3:
            cleaned = re.sub(re.escape(value), "[DONNÉE PERSONNELLE]", cleaned, flags=re.I)
    return cleaned
