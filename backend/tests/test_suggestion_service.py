import json
from types import SimpleNamespace

import pandas as pd

from app.services import suggestion_service


def _sales_dataframe():
    return pd.DataFrame({
        "date": ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"],
        "produit": ["Essentiel", "Premium", "Essentiel", "Premium"],
        "région": ["Nord", "Sud", "Sud", "Nord"],
        "montant": [100, 240, 180, 310],
    })


def _suggestion(question, category="classement", columns=None, chart=False):
    return {
        "question": question,
        "category": category,
        "columns": columns or ["montant"],
        "chart": chart,
    }


def _mock_groq(monkeypatch, content, prompt_capture=None):
    class FakeCompletions:
        def create(self, **kwargs):
            if prompt_capture is not None:
                prompt_capture.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(suggestion_service, "Groq", FakeGroq)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")


def test_build_data_context_contains_sales_categories_and_date_range():
    context = suggestion_service.build_data_context(_sales_dataframe(), ["ventes.csv"])
    columns = {column["name"]: column for column in context["columns"]}

    assert context["row_count"] == 4
    assert columns["date"]["first_date"].startswith("2026-01-01")
    assert columns["date"]["last_date"].startswith("2026-04-01")
    assert columns["date"]["granularity"] == "mois"
    assert {"Essentiel", "Premium"} == set(columns["produit"]["categories"])
    assert {"Nord", "Sud"} == set(columns["région"]["categories"])
    assert columns["montant"]["min"] == 100
    assert columns["montant"]["max"] == 310
    assert len(json.dumps(context, ensure_ascii=False)) < 10_000


def test_context_reports_shared_and_file_specific_columns():
    first = pd.DataFrame({"region": ["Nord"], "montant": [10], "__source_file": ["one.csv"]})
    second = pd.DataFrame({"region": ["Sud"], "produit": ["Pro"], "__source_file": ["two.csv"]})
    dataframe = pd.concat([first, second], ignore_index=True, sort=False)

    context = suggestion_service.build_data_context(
        dataframe,
        file_columns=[("one.csv", ["region", "montant"]), ("two.csv", ["region", "produit"])],
    )

    assert context["multiple_files"]["common_columns"] == ["region"]
    assert context["multiple_files"]["file_specific_columns"] == {
        "one.csv": ["montant"],
        "two.csv": ["produit"],
    }


def test_invalid_llm_json_falls_back_to_data_specific_rules(monkeypatch):
    suggestion_service.clear_suggestion_cache()
    _mock_groq(monkeypatch, "not json")
    context = suggestion_service.build_data_context(_sales_dataframe(), ["ventes.csv"])

    result = suggestion_service.get_suggestions(context, user_id=10)

    assert result.source == "rules"
    assert len(result.suggestions) >= 3
    assert any("Premium" in item.question for item in result.suggestions)
    assert any("montant" in item.question for item in result.suggestions)


def test_suggestions_reject_invented_columns_and_fallback(monkeypatch):
    suggestion_service.clear_suggestion_cache()
    valid = [
        _suggestion("Quel produit a le plus grand montant ?", columns=["produit", "montant"]),
        _suggestion("Comment évolue montant ?", "evolution", ["date", "montant"], True),
        _suggestion("Comment varie montant selon région ?", "comparaison", ["région", "montant"]),
        _suggestion("Quelle est la répartition du montant par produit ?", "repartition", ["produit", "montant"]),
        _suggestion("Quelles anomalies apparaissent dans montant ?", "qualite", ["montant"]),
        _suggestion("Quel chiffre clé ressort pour Premium ?", "synthese", ["produit"]),
        _suggestion("Question sur colonne_fantome", columns=["colonne_fantome"]),
    ]
    _mock_groq(monkeypatch, json.dumps({"suggestions": valid}, ensure_ascii=False))
    context = suggestion_service.build_data_context(_sales_dataframe(), ["ventes.csv"])

    result = suggestion_service.get_suggestions(context, user_id=11)

    assert all("fantome" not in item.question for item in result.suggestions)
    assert all("colonne_fantome" not in item.columns for item in result.suggestions)
    assert 3 <= len(result.suggestions) <= 6


def test_pii_values_are_not_sent_to_groq(monkeypatch):
    suggestion_service.clear_suggestion_cache()
    captured = []
    _mock_groq(monkeypatch, "malformed", captured)
    dataframe = _sales_dataframe()
    dataframe["email"] = ["alice@example.com"] * 4
    dataframe["content"] = [
        "Contact alice@example.com au +33 6 12 34 56 78, IBAN FR7630006000011234567890189."
    ] * 4
    context = suggestion_service.build_data_context(dataframe, ["ventes.csv"])

    suggestion_service.get_suggestions(context, user_id=12)

    prompt = captured[0]["messages"][0]["content"]
    assert "alice@example.com" not in prompt
    assert "+33 6 12 34 56 78" not in prompt
    assert "FR7630006000011234567890189" not in prompt
    assert "[DONNÉE PERSONNELLE]" in prompt
    assert "Contact" in prompt


def test_pii_in_late_category_value_is_not_sent_to_groq(monkeypatch):
    suggestion_service.clear_suggestion_cache()
    captured = []
    _mock_groq(monkeypatch, "malformed", captured)
    dataframe = pd.DataFrame({
        "region": ["Nord"] * 1200 + ["private.person@example.com"],
        "montant": list(range(1201)),
    })
    context = suggestion_service.build_data_context(dataframe)

    suggestion_service.get_suggestions(context, user_id=13)

    prompt = captured[0]["messages"][0]["content"]
    assert "private.person@example.com" not in prompt
    assert "[DONNÉE PERSONNELLE]" in prompt


def test_missing_groq_key_uses_rules_and_cache_is_user_scoped(monkeypatch):
    suggestion_service.clear_suggestion_cache()
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    context = suggestion_service.build_data_context(_sales_dataframe(), ["ventes.csv"])

    first = suggestion_service.get_suggestions(context, user_id=21)
    second = suggestion_service.get_suggestions(context, user_id=21)
    other_user = suggestion_service.get_suggestions(context, user_id=22)

    assert first.source == "rules"
    assert second.source == "cache"
    assert other_user.source == "rules"


def test_identical_context_calls_groq_once_per_user(monkeypatch):
    suggestion_service.clear_suggestion_cache()
    calls = []
    valid = {"suggestions": [
        _suggestion(f"Question {index} sur montant", columns=["montant"])
        for index in range(1, 7)
    ]}
    _mock_groq(monkeypatch, json.dumps(valid, ensure_ascii=False), calls)
    context = suggestion_service.build_data_context(_sales_dataframe(), ["ventes.csv"])

    first = suggestion_service.get_suggestions(context, user_id=31)
    second = suggestion_service.get_suggestions(context, user_id=31)

    assert first.source == "ai"
    assert second.source == "cache"
    assert len(calls) == 1


def test_identifiers_are_profiled_but_not_suggested():
    dataframe = _sales_dataframe()
    dataframe["customer_id"] = ["user-1", "user-2", "user-3", "user-4"]
    context = suggestion_service.build_data_context(dataframe)
    columns = {column["name"]: column for column in context["columns"]}

    assert columns["customer_id"]["type"] == "identifiant"
    assert columns["customer_id"]["suggestible"] is False
    assert all("customer_id" not in item.columns for item in suggestion_service.generate_rule_suggestions(context))


def test_duplicate_columns_are_not_used_in_suggestions():
    dataframe = pd.DataFrame([["Nord", 10], ["Sud", 20]], columns=["region", "region"])
    context = suggestion_service.build_data_context(dataframe)

    assert all(column["suggestible"] is False for column in context["columns"])
    assert all("region" not in item.columns for item in suggestion_service.generate_rule_suggestions(context))


def test_refresh_is_limited_to_one_call_per_ten_seconds(monkeypatch):
    suggestion_service.clear_suggestion_cache()
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    context = suggestion_service.build_data_context(_sales_dataframe())

    suggestion_service.get_suggestions(context, user_id=41, refresh=True)

    try:
        suggestion_service.get_suggestions(context, user_id=41, refresh=True)
    except ValueError as error:
        assert str(error) == "refresh_too_soon"
    else:
        raise AssertionError("A refresh inside the ten-second window must be rejected.")
