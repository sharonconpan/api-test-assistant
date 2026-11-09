from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from api_test_assistant.case_generation import (
    API_COLUMNS,
    BASE_COLUMNS,
    CASE_COLUMNS,
    GeminiClient,
    GeminiConfig,
    GeminiConfigurationError,
    GeminiQuotaError,
    GeminiResponseError,
    _response_schema,
    generate_cases,
    load_gemini_config,
    validate_cases,
)
from api_test_assistant.cli import main


SECRET = "test-key-not-for-output"
REQUIREMENT = {
    "id": "RF01.1",
    "description": "Crear un elemento",
    "method": "POST",
    "path": "/items",
    "operation_id": "create_item",
}
SPEC = {
    "openapi": "3.1.0",
    "paths": {
        "/items": {
            "post": {
                "operationId": "create_item",
                "parameters": [
                    {
                        "name": "dry_run",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean"},
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ItemInput",
                            }
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Elemento creado",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Item"}
                            }
                        },
                    },
                    "422": {"description": "Entrada inválida"},
                },
            }
        }
    },
    "components": {
        "schemas": {
            "ItemInput": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 80}},
            },
            "Item": {"type": "object", "properties": {"id": {"type": "integer"}}},
            "Unused": {"type": "object"},
        }
    },
}
IMPACT = {
    "clasificacion": "concordante",
    "operacion": {
        "metodo": "POST",
        "ruta": "/items",
        "operationId": "create_item",
        "esquemas": ["ItemInput", "Item"],
    },
    "cambio_openapi": "modified",
    "evidencia": {
        "openapi": [{"change": "modified", "path": "/parameters/0"}],
        "codigo": [{"archivo": "src/items.py", "tipo": "operationId", "coincidencia": "create_item"}],
    },
}


def _valid_case() -> dict[str, Any]:
    return {
        "ID": "CP-RF01.1-01",
        "Técnica": "EP (valida)",
        "Descripción del Caso": "Crear un elemento con nombre válido.",
        "Precondiciones": "La API está disponible.",
        "Datos de Entrada": "name='ejemplo', dry_run=false",
        "Pasos": "Enviar POST /items con la entrada indicada.",
        "Resultado Esperado": "Se crea el elemento y se responde con código 201.",
        "Estado": "No ejecutado",
        "Automatizado": "No",
        "Método HTTP": "POST",
        "Endpoint": "/items",
        "Parámetros": {"dry_run": False},
        "Cuerpo": {"name": "ejemplo"},
        "Código de respuesta esperado": 201,
        "Decisión de revisión": "Pendiente",
    }


def _provider_response(text: str, **extra: Any) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}]},
                "finishReason": "STOP",
            }
        ],
        **extra,
    }


class FakeCaseClient:
    model = "gemini-test"

    def __init__(self, response: object, metadata: dict[str, int | str] | None = None) -> None:
        self.response = response
        self.metadata = metadata or {}
        self.prompt = ""

    def generate(self, prompt: str) -> tuple[dict[str, Any], dict[str, int | str]]:
        self.prompt = prompt
        if not isinstance(self.response, dict):
            raise GeminiResponseError("Respuesta simulada inválida.")
        return self.response, self.metadata


def _commit(repo: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", message],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _generation_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    sample = repo / "examples" / "sample_api"
    sample.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "tests@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "API Test Assistant tests"],
        check=True,
    )
    (sample / "openapi.json").write_text(json.dumps(SPEC), encoding="utf-8")
    (sample / "rf_map.yaml").write_text(
        "module: Gestión de elementos\n"
        "requirements:\n"
        "  - id: RF01.1\n"
        "    description: Crear un elemento\n"
        "    method: POST\n"
        "    path: /items\n"
        "    operation_id: create_item\n",
        encoding="utf-8",
    )
    head = _commit(repo, "fixture")
    impacts_path = tmp_path / "impacts.json"
    impacts_path.write_text(
        json.dumps(
            {
                "git": {"repository": str(repo), "base": head, "head": head},
                "openapi": {"status": "cambios"},
                "impacts": [IMPACT],
            }
        ),
        encoding="utf-8",
    )
    return repo, impacts_path, head


def test_load_config_uses_dotenv_default_and_environment_override(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text('GEMINI_API_KEY="dotenv-key"\nGEMINI_MODEL=gemini-example\n', encoding="utf-8")

    config = load_gemini_config(dotenv, environ={})
    overridden = load_gemini_config(
        dotenv,
        environ={"GEMINI_API_KEY": "environment-key", "GEMINI_MODEL": "gemini-override"},
    )

    assert config.api_key == "dotenv-key"
    assert config.model == "gemini-example"
    assert overridden.api_key == "environment-key"
    assert overridden.model == "gemini-override"
    assert "dotenv-key" not in repr(config)


def test_config_errors_are_explicit(tmp_path: Path) -> None:
    with pytest.raises(GeminiConfigurationError, match="Falta GEMINI_API_KEY"):
        load_gemini_config(tmp_path / "missing.env", environ={})

    invalid_dotenv = tmp_path / "invalid.env"
    invalid_dotenv.write_text("GEMINI_API_KEY\n", encoding="utf-8")
    with pytest.raises(GeminiConfigurationError, match="Formato inválido"):
        load_gemini_config(invalid_dotenv, environ={})

    with pytest.raises(GeminiConfigurationError, match="GEMINI_MODEL"):
        load_gemini_config(
            tmp_path / "missing.env",
            environ={"GEMINI_API_KEY": SECRET, "GEMINI_MODEL": "invalid model"},
        )


def test_client_requests_structured_json_and_returns_safe_metadata() -> None:
    request_data: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        request_data["url"] = str(request.url)
        request_data["headers"] = dict(request.headers)
        request_data["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=_provider_response(
                '{"casos":[]}',
                usageMetadata={
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 50,
                    "totalTokenCount": 150,
                    "cachedContentTokenCount": 9,
                },
                modelVersion="gemini-test-version",
            ),
        )

    client = GeminiClient(
        GeminiConfig(api_key=SECRET, model="gemini-3.8-flash"),
        transport=httpx.MockTransport(handler),
    )
    response, metadata = client.generate("solicitud")

    assert response == {"casos": []}
    assert request_data["url"].endswith("/models/gemini-3.8-flash:generateContent")
    assert request_data["headers"]["x-goog-api-key"] == SECRET
    assert request_data["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert request_data["body"]["generationConfig"]["responseSchema"] == _response_schema()
    assert metadata == {
        "promptTokenCount": 100,
        "candidatesTokenCount": 50,
        "totalTokenCount": 150,
        "modelVersion": "gemini-test-version",
    }


def test_client_surfaces_quota_auth_and_invalid_responses() -> None:
    quota_client = GeminiClient(
        GeminiConfig(api_key=SECRET, model="gemini-test"),
        transport=httpx.MockTransport(lambda request: httpx.Response(429)),
    )
    with pytest.raises(GeminiQuotaError, match="cuota"):
        quota_client.generate("solicitud")

    auth_client = GeminiClient(
        GeminiConfig(api_key=SECRET, model="gemini-test"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(403, json={"error": {"message": SECRET}})
        ),
    )
    with pytest.raises(GeminiConfigurationError, match="HTTP 403") as error:
        auth_client.generate("solicitud")
    assert SECRET not in str(error.value)

    invalid_json_client = GeminiClient(
        GeminiConfig(api_key=SECRET, model="gemini-test"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=_provider_response("no es JSON"))
        ),
    )
    with pytest.raises(GeminiResponseError, match="JSON estricto"):
        invalid_json_client.generate("solicitud")

    blocked_client = GeminiClient(
        GeminiConfig(api_key=SECRET, model="gemini-test"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
        ),
    )
    with pytest.raises(GeminiResponseError, match="bloqueó"):
        blocked_client.generate("solicitud")


def test_validator_enforces_catalog_order_ids_technique_and_http_contract() -> None:
    case = _valid_case()
    validated = validate_cases(
        {"casos": [case]},
        [REQUIREMENT],
        SPEC,
    )

    assert BASE_COLUMNS == [
        "ID",
        "Técnica",
        "Descripción del Caso",
        "Precondiciones",
        "Datos de Entrada",
        "Pasos",
        "Resultado Esperado",
        "Estado",
        "Automatizado",
    ]
    assert API_COLUMNS == [
        "Método HTTP",
        "Endpoint",
        "Parámetros",
        "Cuerpo",
        "Código de respuesta esperado",
    ]
    assert list(validated[0]) == CASE_COLUMNS

    invalid_cases: list[tuple[str, dict[str, Any]]] = []
    bad_technique = deepcopy(case)
    bad_technique["Técnica"] = "Valores límite (valida)"
    invalid_cases.append(("Técnica no permitida", bad_technique))
    bad_id = deepcopy(case)
    bad_id["ID"] = "CP-RF01.1-1"
    invalid_cases.append(("ID inválido", bad_id))
    bad_rf = deepcopy(case)
    bad_rf["ID"] = "CP-RF99.1-01"
    invalid_cases.append(("no pertenece al mapa", bad_rf))
    bad_method = deepcopy(case)
    bad_method["Método HTTP"] = "GET"
    invalid_cases.append(("no usa la operación asignada", bad_method))
    bad_status = deepcopy(case)
    bad_status["Código de respuesta esperado"] = 200
    invalid_cases.append(("no está declarado", bad_status))
    bad_state = deepcopy(case)
    bad_state["Estado"] = "Exitoso"
    invalid_cases.append(("No ejecutado", bad_state))
    extra_field = deepcopy(case)
    extra_field["suposicion"] = "no permitida"
    invalid_cases.append(("exactamente las columnas", extra_field))

    for message, invalid_case in invalid_cases:
        with pytest.raises(GeminiResponseError, match=message):
            validate_cases({"casos": [invalid_case]}, [REQUIREMENT], SPEC)


def test_generate_persists_cases_with_safe_metadata_and_relevant_prompt(tmp_path: Path) -> None:
    _, impacts_path, head = _generation_fixture(tmp_path)
    output_path = tmp_path / "cases.json"
    fake_client = FakeCaseClient(
        {"casos": [_valid_case()]},
        {"totalTokenCount": 123, "modelVersion": "gemini-test-version"},
    )

    document = generate_cases(impacts_path, output_path, client=fake_client)
    saved_text = output_path.read_text(encoding="utf-8")
    saved = json.loads(saved_text)

    assert document == saved
    assert saved["metadata"]["model"] == "gemini-test"
    assert saved["metadata"]["source"]["head"] == head
    assert saved["metadata"]["source"]["requirements"] == ["RF01.1"]
    assert saved["metadata"]["provider"]["totalTokenCount"] == 123
    assert saved["casos"][0]["Estado"] == "No ejecutado"
    assert saved["casos"][0]["Automatizado"] == "No"
    assert saved["casos"][0]["Decisión de revisión"] == "Pendiente"
    assert SECRET not in saved_text
    assert "openapi_pertinente" in fake_client.prompt
    assert "rf_map_pertinente" in fake_client.prompt
    assert "maxLength" in fake_client.prompt
    assert "Unused" not in fake_client.prompt


def test_invalid_cases_are_rejected_without_writing_output(tmp_path: Path) -> None:
    _, impacts_path, _ = _generation_fixture(tmp_path)
    output_path = tmp_path / "invalid-cases.json"
    invalid = _valid_case()
    invalid["Técnica"] = "equivalence"

    with pytest.raises(GeminiResponseError, match="Técnica no permitida"):
        generate_cases(
            impacts_path,
            output_path,
            client=FakeCaseClient({"casos": [invalid]}),
        )

    assert not output_path.exists()


def test_generate_cli_writes_cases_with_injected_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, impacts_path, _ = _generation_fixture(tmp_path)
    output_path = tmp_path / "cli-cases.json"
    fake_client = FakeCaseClient({"casos": [_valid_case()]})
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = main(
        ["generate", "--impacts", str(impacts_path), "--output", str(output_path)],
        client=fake_client,
    )

    assert result == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["casos"][0]["ID"] == "CP-RF01.1-01"


@pytest.mark.skipif(
    os.environ.get("RUN_GEMINI_INTEGRATION") != "1",
    reason="Integración real con Gemini desactivada por defecto.",
)
def test_optional_real_gemini_integration(tmp_path: Path) -> None:
    _, impacts_path, _ = _generation_fixture(tmp_path)
    output_path = tmp_path / "gemini-integration-cases.json"

    result = generate_cases(impacts_path, output_path)

    assert result["casos"]
