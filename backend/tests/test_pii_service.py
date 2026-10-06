from types import SimpleNamespace

import pandas as pd

from app.services import ai_service
from app.services.pii_service import detect_pii, prepare_dataframes


def test_detect_pii_reports_sensitive_columns_and_value_counts():
    dataframe = pd.DataFrame({
        "email": ["amina@example.test", "not-an-email"],
        "phone": ["+216 20 123 456", "no phone"],
        "iban": ["GB82WEST12345698765432", "invalid"],
        "card": ["4111111111111111", "invalid"],
        "cin": ["12345678", "invalid"],
        "ip": ["192.168.1.10", "invalid"],
        "ip_v6": ["2001:db8::1", "invalid"],
    })

    report = detect_pii(dataframe)

    assert report["column_count"] == 7
    assert [column["category"] for column in report["columns"]] == [
        "email", "téléphone", "iban", "carte bancaire", "CIN", "IP", "IP",
    ]
    assert report["values_touched"] == 12


def test_prepare_dataframes_keeps_execution_values_and_masks_prompt_values():
    dataframe = pd.DataFrame({
        "customer_email": ["amina@example.test"],
        "amount": [42],
    })
    report = detect_pii(dataframe)

    execution, prompt, _, sensitive_values = prepare_dataframes(dataframe, report)

    assert execution.iloc[0]["customer_email"] == "amina@example.test"
    assert prompt.iloc[0]["customer_email"] == "[EMAIL]"
    assert "amina@example.test" in sensitive_values


def test_all_groq_prompts_mask_values_from_detected_pii_columns(monkeypatch):
    pii_values = [
        "amina@example.test",
        "+216 20 123 456",
        "GB82WEST12345698765432",
        "4111111111111111",
        "12345678",
        "192.168.1.10",
        "Amira Ben Salah",
        "2001:db8::1",
    ]
    dataframe = pd.DataFrame({
        "email": [pii_values[0]],
        "phone": [pii_values[1]],
        "iban": [pii_values[2]],
        "card": [pii_values[3]],
        "cin": [pii_values[4]],
        "ip": [pii_values[5]],
        "ip_v6": [pii_values[7]],
        "customer_name": [pii_values[6]],
        "amount": [125],
    })
    report = detect_pii(dataframe)
    execution, prompt_dataframe, _, sensitive_values = prepare_dataframes(dataframe, report)
    captured_prompts = []
    responses = iter([
        "```python\nprint('total')\n```",
        '{"answer":"Total calculé.","code_explanation":"Le code calcule le total."}',
    ])

    class FakeCompletions:
        def create(self, **kwargs):
            captured_prompts.extend(
                message["content"]
                for message in kwargs["messages"]
                if message["role"] == "user"
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=next(responses)))]
            )

    class FakeGroq:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "Groq", FakeGroq)
    monkeypatch.setattr(
        ai_service,
        "_execute_code",
        lambda _code, _dataframe: (" ".join(pii_values), None, None),
    )

    ai_service.analyze_dataset(
        "Calcule les données pour Amira Ben Salah, amina@example.test",
        execution,
        prompt_dataframe=prompt_dataframe,
        sensitive_values=sensitive_values,
        pii_column_count=report["column_count"],
    )

    assert captured_prompts
    for prompt in captured_prompts:
        for value in pii_values:
            assert value.casefold() not in prompt.casefold()
