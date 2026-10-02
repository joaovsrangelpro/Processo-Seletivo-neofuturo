from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

from app.services import openai_service
from app.services.openai_service import (
    OpenAIRateLimitError,
    OpenAIServiceError,
    OpenAITimeoutError,
    build_summary_prompt,
    generate_contact_summary,
)


def mock_openai_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_text: object = "Generated summary.",
    error: Exception | None = None,
) -> tuple[Mock, Mock]:
    create_response = Mock(
        return_value=SimpleNamespace(output_text=output_text),
        side_effect=error,
    )
    client = Mock()
    client.responses.create = create_response
    openai_constructor = Mock(return_value=client)
    monkeypatch.setattr(openai_service, "OpenAI", openai_constructor)
    return openai_constructor, create_response


def generate() -> str:
    return generate_contact_summary(
        api_key="test-api-key",
        full_name="Joao Victor Rangel",
        email="joao@example.com",
        phone="(21) 98765-4321",
        tags=["Cliente", "Lead"],
    )


def test_generate_summary_configures_single_responses_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openai_constructor, create_response = mock_openai_client(
        monkeypatch,
        output_text="  Generated summary.  ",
    )

    result = generate()

    assert result == "Generated summary."
    openai_constructor.assert_called_once_with(
        api_key="test-api-key",
        max_retries=0,
        timeout=15.0,
    )
    create_response.assert_called_once()
    request_data = create_response.call_args.kwargs
    assert request_data["model"] == "gpt-4o-mini"
    assert request_data["max_output_tokens"] == 150
    assert request_data["store"] is False
    prompt = request_data["input"]
    assert "no máximo 3 frases" in prompt
    assert "Nome: Joao Victor Rangel" in prompt
    assert "Email: joao@example.com" in prompt
    assert "Telefone: (21) 98765-4321" in prompt
    assert "Tags: Cliente, Lead" in prompt
    assert "Não invente informações" in prompt


def test_prompt_uses_none_for_empty_tags() -> None:
    prompt = build_summary_prompt(
        full_name="No Tags",
        email="no-tags@example.com",
        phone="(11) 91234-5678",
        tags=[],
    )

    assert "Tags: nenhuma" in prompt


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (
            RateLimitError(
                "rate limit",
                response=httpx.Response(
                    429,
                    request=httpx.Request("POST", "https://api.openai.com"),
                ),
                body=None,
            ),
            OpenAIRateLimitError,
        ),
        (
            APITimeoutError(
                request=httpx.Request("POST", "https://api.openai.com")
            ),
            OpenAITimeoutError,
        ),
        (
            APIConnectionError(
                request=httpx.Request("POST", "https://api.openai.com")
            ),
            OpenAIServiceError,
        ),
        (
            APIError(
                "api error",
                request=httpx.Request("POST", "https://api.openai.com"),
                body=None,
            ),
            OpenAIServiceError,
        ),
    ],
    ids=["rate-limit", "timeout", "connection", "api-error"],
)
def test_generate_summary_translates_sdk_errors(
    sdk_error: Exception,
    expected_error: type[Exception],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, create_response = mock_openai_client(
        monkeypatch,
        error=sdk_error,
    )

    with pytest.raises(expected_error):
        generate()

    create_response.assert_called_once()


@pytest.mark.parametrize("output_text", [None, "", "   ", 123])
def test_generate_summary_rejects_empty_or_invalid_response(
    output_text: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, create_response = mock_openai_client(
        monkeypatch,
        output_text=output_text,
    )

    with pytest.raises(OpenAIServiceError):
        generate()

    create_response.assert_called_once()
