from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)


OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TIMEOUT_SECONDS = 15.0
OPENAI_MAX_OUTPUT_TOKENS = 150


class OpenAIRateLimitError(Exception):
    pass


class OpenAITimeoutError(Exception):
    pass


class OpenAIServiceError(Exception):
    pass


def build_summary_prompt(
    *,
    full_name: str,
    email: str,
    phone: str,
    tags: list[str],
) -> str:
    tags_text = ", ".join(tags) if tags else "nenhuma"
    return (
        "Gere um resumo conciso, em tom profissional, de no máximo 3 frases, "
        "usando exclusivamente as informações fornecidas abaixo.\n\n"
        "Não presuma profissão, cargo, experiência, empresa, interesses, "
        "qualificações ou qualquer outra informação que não esteja "
        "explicitamente presente nos dados.\n"
        "A ausência de tags significa somente que não há tags associadas; "
        "não a interprete como ausência de experiência ou informações "
        "profissionais.\n\n"
        f"Nome: {full_name}\n"
        f"Email: {email}\n"
        f"Telefone: {phone}\n"
        f"Tags: {tags_text}\n\n"
        "Não invente informações que não estejam presentes nos dados. "
        "Descreva somente os fatos fornecidos."
    )


def generate_contact_summary(
    *,
    api_key: str,
    full_name: str,
    email: str,
    phone: str,
    tags: list[str],
) -> str:
    prompt = build_summary_prompt(
        full_name=full_name,
        email=email,
        phone=phone,
        tags=tags,
    )
    client = OpenAI(
        api_key=api_key,
        max_retries=0,
        timeout=OPENAI_TIMEOUT_SECONDS,
    )

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
            max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
            store=False,
        )
    except RateLimitError as error:
        raise OpenAIRateLimitError from error
    except APITimeoutError as error:
        raise OpenAITimeoutError from error
    except (APIConnectionError, APIError) as error:
        raise OpenAIServiceError from error

    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        raise OpenAIServiceError
    return output_text.strip()
