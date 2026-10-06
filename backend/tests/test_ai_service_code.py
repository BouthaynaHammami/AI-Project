from types import SimpleNamespace

import pandas as pd

from app.services import ai_service


def test_analyze_dataset_returns_the_successfully_retried_code(monkeypatch):
    responses = iter([
        "```python\nprint('initial')\n```",
        "```python\nprint('corrected')\n```",
        '{"answer":"Résultat calculé.","code_explanation":"Le code sélectionne les lignes utiles puis calcule leur total."}',
    ])

    class FakeCompletions:
        def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=next(responses)))]
            )

    class FakeGroq:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "Groq", FakeGroq)
    calls = []

    def fake_execute(code, _dataframe):
        calls.append(code)
        if code == "print('initial')":
            raise ValueError("synthetic failure")
        return "total=42", None, None

    monkeypatch.setattr(ai_service, "_execute_code", fake_execute)

    result = ai_service.analyze_dataset("Calcule le total", pd.DataFrame({"value": [42]}))

    assert calls == ["print('initial')", "print('corrected')"]
    assert result["code"] == calls[-1]
    assert result["retried"] is True
    assert result["answer"] == "Résultat calculé."
    assert result["code_explanation"] == "Le code sélectionne les lignes utiles puis calcule leur total."


def test_summary_parser_supports_legacy_plain_text():
    answer, explanation = ai_service._parse_summary("Réponse simple en français.")

    assert answer == "Réponse simple en français."
    assert explanation == ""


def test_execute_code_captures_json_safe_result_table_up_to_one_thousand_rows():
    dataframe = pd.DataFrame({
        "value": range(1001),
        "optional": [None] * 1000 + [float("nan")],
    })

    _, _, result_table = ai_service._execute_code("result_table = df", dataframe)
    serialized = ai_service._serialize_result_table(result_table)

    assert serialized is not None
    assert serialized["columns"] == ["value", "optional"]
    assert len(serialized["rows"]) == 1000
    assert serialized["rows"][0] == [0, None]


def test_chart_validator_accepts_multiple_series_and_limits_points():
    chart = ai_service._validate_chart_data({
        "type": "line",
        "title": "Ventes mensuelles",
        "x_label": "Mois",
        "y_label": "Montant (€)",
        "labels": ["Janvier", "Février"],
        "series": [
            {"name": "Nord", "values": [12, 18]},
            {"name": "Sud", "values": [9, 15]},
        ],
    })

    assert chart == {
        "type": "line",
        "title": "Ventes mensuelles",
        "x_label": "Mois",
        "y_label": "Montant (€)",
        "labels": ["Janvier", "Février"],
        "series": [
            {"name": "Nord", "values": [12.0, 18.0]},
            {"name": "Sud", "values": [9.0, 15.0]},
        ],
    }


def test_chart_validator_converts_legacy_single_series_chart():
    chart = ai_service._validate_chart_data({
        "title": "Ventes",
        "labels": ["Nord", "Sud"],
        "values": [10, 20],
    })

    assert chart is not None
    assert chart["type"] == "bar"
    assert chart["series"] == [{"name": "Ventes", "values": [10.0, 20.0]}]


def test_chart_validator_rejects_invalid_types_lengths_values_and_point_limits():
    base = {
        "type": "bar",
        "title": "Ventes",
        "labels": ["Nord", "Sud"],
        "series": [{"name": "Ventes", "values": [10, 20]}],
    }
    invalid_charts = [
        {**base, "type": "radar"},
        {**base, "series": [{"name": "Ventes", "values": [10]}]},
        {**base, "series": [{"name": "Ventes", "values": [10, float("nan")]}]},
        {**base, "series": [{"name": "Montant", "values": [10, 20]}, {"name": "Montant", "values": [30, 40]}]},
        {**base, "labels": [str(index) for index in range(21)], "series": [{"name": "Ventes", "values": list(range(21))}]},
        {**base, "type": "pie", "labels": [str(index) for index in range(9)], "series": [{"name": "Ventes", "values": list(range(9))}]},
        {**base, "type": "scatter"},
    ]

    assert all(ai_service._validate_chart_data(chart) is None for chart in invalid_charts)


def test_chart_validator_allows_fifty_scatter_points_only_with_numeric_x_values():
    valid = ai_service._validate_chart_data({
        "type": "scatter",
        "title": "Relation",
        "labels": [str(index) for index in range(50)],
        "series": [{"name": "Mesure", "values": list(range(50))}],
    })
    too_many = ai_service._validate_chart_data({
        "type": "scatter",
        "title": "Relation",
        "labels": [str(index) for index in range(51)],
        "series": [{"name": "Mesure", "values": list(range(51))}],
    })
    non_numeric_x = ai_service._validate_chart_data({
        "type": "scatter",
        "title": "Relation",
        "labels": ["Nord", "Sud"],
        "series": [{"name": "Mesure", "values": [1, 2]}],
    })

    assert valid is not None
    assert len(valid["labels"]) == 50
    assert too_many is None
    assert non_numeric_x is None


def test_analyze_dataset_does_not_create_a_chart_from_unrelated_column_values(monkeypatch):
    responses = iter([
        "```python\nprint('Total : 300')\n```",
        '{"answer":"Le total est 300.","code_explanation":"Le code calcule le total demandé."}',
    ])

    class FakeCompletions:
        def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=next(responses)))]
            )

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "Groq", FakeGroq)
    monkeypatch.setattr(ai_service, "_execute_code", lambda *_args: ("Total : 300", None, None))

    result = ai_service.analyze_dataset(
        "Quel est le total des ventes ?",
        pd.DataFrame({"sales": [100, 200]}),
        generate_chart=True,
    )

    assert result["chart_config"] is None


def test_follow_up_question_uses_only_bounded_text_history_and_filters_south(monkeypatch):
    responses = iter([
        "```python\nprint(df.groupby('produit')['montant'].sum().idxmax())\n```",
        '{"answer":"Le meilleur produit est Premium.","code_explanation":"Le code additionne les ventes par produit."}',
        '{"status":"ready","question":"Quel produit a le montant total le plus élevé dans la région Sud ?"}',
        "```python\nsud = df[df['region'].str.casefold() == 'sud']\nprint(sud.groupby('produit')['montant'].sum().idxmax())\n```",
        '{"answer":"En région Sud, Premium arrive en tête.","code_explanation":"Le code filtre la région Sud puis classe les ventes par produit."}',
    ])
    captured_prompts = []

    class FakeCompletions:
        def create(self, **kwargs):
            captured_prompts.append(kwargs["messages"][0]["content"])
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=next(responses)))]
            )

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "Groq", FakeGroq)
    dataframe = pd.DataFrame({
        "produit": ["Essentiel", "Premium", "Essentiel", "Premium"],
        "region": ["Nord", "Nord", "Sud", "Sud"],
        "montant": [120, 290, 180, 410],
    })

    first = ai_service.analyze_dataset("Quel est le meilleur produit ?", dataframe)
    second = ai_service.analyze_dataset(
        "Et en Sud ?",
        dataframe,
        conversation_history=[{
            "question": "Quel est le meilleur produit ?",
            "answer": first["answer"],
            "code": first["code"],
        }],
    )

    assert first["answer"] == "Le meilleur produit est Premium."
    assert second["answer"] == "En région Sud, Premium arrive en tête."
    assert "Et en Sud ?" in captured_prompts[2]
    assert "Quel produit a le montant total le plus élevé dans la région Sud ?" in captured_prompts[3]
    assert second["code"] == (
        "sud = df[df['region'].str.casefold() == 'sud']\n"
        "print(sud.groupby('produit')['montant'].sum().idxmax())"
    )


def test_ambiguous_follow_up_returns_clarification_without_executing_code(monkeypatch):
    class FakeCompletions:
        def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"status":"clarify","question":"De quelle région parlez-vous ?"}'))]
            )

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "Groq", FakeGroq)
    monkeypatch.setattr(
        ai_service,
        "_execute_code",
        lambda *_args: (_ for _ in ()).throw(AssertionError("code must not be generated for an unclear question")),
    )

    result = ai_service.analyze_dataset(
        "Et là-bas ?",
        pd.DataFrame({"region": ["Sud"], "montant": [10]}),
        conversation_history=[{"question": "Total ?", "answer": "12", "code": "print(12)"}],
    )

    assert result["answer"] == "De quelle région parlez-vous ?"
    assert result["code"] is None
