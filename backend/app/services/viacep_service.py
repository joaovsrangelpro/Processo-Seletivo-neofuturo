import httpx
from pydantic import ValidationError

from app.schemas.contact import AddressEnrichmentResponse


VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
VIACEP_TIMEOUT_SECONDS = 5.0


class ViaCEPNotFoundError(Exception):
    pass


class ViaCEPTimeoutError(Exception):
    pass


class ViaCEPServiceError(Exception):
    pass


async def fetch_address(cep: str) -> AddressEnrichmentResponse:
    try:
        async with httpx.AsyncClient(timeout=VIACEP_TIMEOUT_SECONDS) as client:
            response = await client.get(VIACEP_URL.format(cep=cep))
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise ViaCEPTimeoutError from error
    except httpx.HTTPError as error:
        raise ViaCEPServiceError from error

    try:
        data = response.json()
    except ValueError as error:
        raise ViaCEPServiceError from error

    if not isinstance(data, dict):
        raise ViaCEPServiceError
    if data.get("erro") is True:
        raise ViaCEPNotFoundError

    try:
        return AddressEnrichmentResponse(
            cep=f"{cep[:5]}-{cep[5:]}",
            logradouro=data["logradouro"],
            bairro=data["bairro"],
            cidade=data["localidade"],
            uf=data["uf"],
        )
    except (KeyError, ValidationError) as error:
        raise ViaCEPServiceError from error
