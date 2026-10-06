import json

import pandas as pd

from app.services.profiling_service import MAX_PROFILE_ROWS, profile_dataframe


def test_profile_reports_missing_duplicates_text_dates_and_column_alerts():
    dataframe = pd.DataFrame({
        "amount_text": ["10", "20", "20", "20"],
        "created_at": ["2025-01-01", "2025-01-02", "2025-01-02", "2025-01-02"],
        "mostly_empty": [None, None, "x", None],
        "constant": ["same", "same", "same", "same"],
        "category": ["a", "b", "a", "b"],
        "flag": [True, False, True, False],
        "score": [1, 1, 100, 1],
    })

    profile = profile_dataframe(dataframe)

    assert profile["row_count"] == 4
    assert profile["column_count"] == 7
    assert profile["duplicate_rows"] == 1
    columns = {column["name"]: column for column in profile["columns"]}
    assert columns["amount_text"]["detected_type"] == "numérique"
    assert round(columns["amount_text"]["statistics"]["mean"], 2) == 17.5
    assert columns["created_at"]["detected_type"] == "date"
    assert columns["created_at"]["date_range"]["min"].startswith("2025-01-01")
    assert columns["mostly_empty"]["missing_percentage"] == 75
    assert columns["constant"]["unique_count"] == 1
    assert columns["category"]["detected_type"] == "catégorie"
    assert columns["category"]["top_values"][0]["count"] == 2
    assert columns["flag"]["detected_type"] == "booléen"
    alert_types = {alert["type"] for alert in profile["alerts"]}
    assert "numeric_stored_as_text" in alert_types
    assert "date_stored_as_text" in alert_types
    assert "missing_values" in alert_types
    assert "constant_column" in alert_types
    assert "outliers" in alert_types

    json.dumps(profile, allow_nan=False)


def test_profile_preserves_duplicate_column_names_and_caps_sample_size():
    dataframe = pd.DataFrame(
        [["a", 1], ["b", 2], ["a", 3]],
        columns=["duplicate", "duplicate"],
    )
    profile = profile_dataframe(dataframe)
    assert [column["position"] for column in profile["columns"]] == [0, 1]
    assert any(alert["type"] == "duplicate_column_names" for alert in profile["alerts"])

    large_dataframe = pd.DataFrame({"value": range(MAX_PROFILE_ROWS + 25)})
    large_profile = profile_dataframe(large_dataframe)
    assert large_profile["row_count"] == MAX_PROFILE_ROWS + 25
    assert large_profile["sampled_rows"] == MAX_PROFILE_ROWS
