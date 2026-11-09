from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Protocol
from urllib.parse import quote

import httpx
import yaml

from .git_changes import GitAnalysisError, _git


class CaseGenerationError(RuntimeError):
    """Error general del flujo de generación de casos."""


class GeminiConfigurationError(CaseGenerationError):
    """Falta o no es válida la configuración del cliente Gemini."""


class GeminiQuotaError(CaseGenerationError):
    """Gemini rechazó la solicitud por cuota o límite de uso."""


class GeminiRequestError(CaseGenerationError):
    """Gemini no pudo completar la solicitud."""


class GeminiResponseError(CaseGenerationError):
    """Gemini devolvió una respuesta ausente o inválida."""


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = field(repr=False)
    model: str


class CaseGeneratorClient(Protocol):
    @property
    def model(self) -> str: ...

    def generate(self, prompt: str) -> tuple[dict[str, Any], dict[str, int | str]]: ...


TECHNIQUES = {
    "T. Decisión (valida)",
    "T. Decisión (invalida)",
    "EP (valida)",
    "EP (invalida)",
}
BASE_COLUMNS = [
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
API_COLUMNS = [
    "Método HTTP",
    "Endpoint",
    "Parámetros",
    "Cuerpo",
    "Código de respuesta esperado",
]
CASE_COLUMNS = [*BASE_COLUMNS, *API_COLUMNS, "Decisión de revisión"]
_CASE_ID = re.compile(r"CP-(RF\d{2}(?:\.\d+)?)-(\d{2})\Z")
_MAX_RESPONSE_BYTES = 2_000_000


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if not path.is_file():
        raise GeminiConfigurationError(f"La ruta de configuración no es un archivo: {path}")

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise GeminiConfigurationError(f"No se pudo leer el archivo de entorno {path}: {error}") from error

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise GeminiConfigurationError(
                f"Formato inválido en {path}, línea {line_number}; se esperaba CLAVE=VALOR."
            )
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise GeminiConfigurationError(
                f"Nombre de variable inválido en {path}, línea {line_number}."
            )
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_gemini_config(
    dotenv_path: str | Path = ".env",
    environ: dict[str, str] | None = None,
) -> GeminiConfig:
    dotenv_values = _read_dotenv(Path(dotenv_path))
    environment = os.environ if environ is None else environ
    api_key = environment.get("GEMINI_API_KEY") or dotenv_values.get("GEMINI_API_KEY", "")
    model = (
        environment.get("GEMINI_MODEL")
        or dotenv_values.get("GEMINI_MODEL")
        or "gemini-3.8-flash"
    )
    if not api_key.strip():
        raise GeminiConfigurationError(
            "Falta GEMINI_API_KEY. Configúrala en el entorno o en un archivo .env local no versionado."
        )
    if not model.strip() or any(character.isspace() for character in model):
        raise GeminiConfigurationError("GEMINI_MODEL debe ser un identificador no vacío sin espacios.")
    return GeminiConfig(api_key=api_key.strip(), model=model.strip())


_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "casos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "ID": {"type": "STRING"},
                    "Técnica": {"type": "STRING", "enum": sorted(TECHNIQUES)},
                    "Descripción del Caso": {"type": "STRING"},
                    "Precondiciones": {"type": "STRING"},
                    "Datos de Entrada": {"type": "STRING"},
                    "Pasos": {"type": "STRING"},
                    "Resultado Esperado": {"type": "STRING"},
                    "Estado": {"type": "STRING", "enum": ["No ejecutado"]},
                    "Automatizado": {"type": "STRING", "enum": ["No"]},
                    "Método HTTP": {"type": "STRING"},
                    "Endpoint": {"type": "STRING"},
                    "Parámetros": {"type": "OBJECT"},
                    "Cuerpo": {
                        "type": "OBJECT",
                        "nullable": True,
                    },
                    "Código de respuesta esperado": {"type": "INTEGER"},
                    "Decisión de revisión": {"type": "STRING", "enum": ["Pendiente"]},
                },
                "required": CASE_COLUMNS,
                "additionalProperties": False,
            },
        }
    },
    "required": ["casos"],
    "additionalProperties": False,
}


def _response_schema() -> dict[str, object]:
    return _RESPONSE_SCHEMA


class GeminiClient:
    def __init__(
        self,
        config: GeminiConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._config = config
        self._transport = transport
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._config.model

    def generate(self, prompt: str) -> tuple[dict[str, Any], dict[str, int | str]]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(self._config.model, safe='')}:generateContent"
        )
        request = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _response_schema(),
                "temperature": 0.2,
            },
        }
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                response = client.post(
                    url,
                    headers={"x-goog-api-key": self._config.api_key},
                    json=request,
                )
        except httpx.TimeoutException as error:
            raise GeminiRequestError("La solicitud a Gemini excedió el tiempo de espera.") from error
        except httpx.RequestError as error:
            raise GeminiRequestError(f"No se pudo conectar con Gemini: {error}") from error

        if response.status_code == 429:
            raise GeminiQuotaError(
                "Gemini rechazó la solicitud por cuota o límite de uso (HTTP 429)."
            )
        if response.status_code in {401, 403}:
            raise GeminiConfigurationError(
                f"Gemini rechazó la autenticación o los permisos (HTTP {response.status_code}). "
                "Verifica GEMINI_API_KEY y el acceso al modelo."
            )
        if response.status_code >= 400:
            detail = _safe_provider_message(response, self._config.api_key)
            raise GeminiRequestError(
                f"Gemini devolvió HTTP {response.status_code}"
                + (f": {detail}" if detail else ".")
            )
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise GeminiResponseError("La respuesta de Gemini excede el tamaño permitido.")

        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError) as error:
            raise GeminiResponseError("Gemini devolvió un cuerpo que no es JSON válido.") from error
        if not isinstance(body, dict):
            raise GeminiResponseError("La respuesta de Gemini debe ser un objeto JSON.")
        prompt_feedback = body.get("promptFeedback")
        if isinstance(prompt_feedback, dict) and prompt_feedback.get("blockReason"):
            raise GeminiResponseError(
                f"Gemini bloqueó la solicitud: {prompt_feedback['blockReason']}."
            )
        candidates = body.get("candidates")
        if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
            raise GeminiResponseError("Gemini no devolvió candidatos de contenido.")
        candidate = candidates[0]
        if candidate.get("finishReason") == "MAX_TOKENS":
            raise GeminiResponseError("La respuesta de Gemini se truncó por alcanzar el límite de tokens.")
        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise GeminiResponseError("La respuesta de Gemini no contiene partes de texto.")
        text = next(
            (part.get("text") for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)),
            None,
        )
        if text is None:
            raise GeminiResponseError("La respuesta de Gemini no contiene JSON textual.")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise GeminiResponseError("Gemini devolvió contenido que no es JSON estricto.") from error
        if not isinstance(parsed, dict):
            raise GeminiResponseError("El JSON de Gemini debe tener un objeto como raíz.")

        usage = body.get("usageMetadata")
        metadata: dict[str, int | str] = {}
        if isinstance(usage, dict):
            for key in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount"):
                value = usage.get(key)
                if isinstance(value, int):
                    metadata[key] = value
        model_version = body.get("modelVersion")
        if isinstance(model_version, str):
            metadata["modelVersion"] = model_version
        return parsed, metadata


def _safe_provider_message(response: httpx.Response, api_key: str) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return ""
    return message.replace(api_key, "[redactado]").strip()[:500]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise CaseGenerationError(f"No se pudo leer {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise CaseGenerationError(f"{path} no contiene JSON válido: {error}") from error
    if not isinstance(value, dict):
        raise CaseGenerationError(f"{path} debe contener un objeto JSON.")
    return value


def _load_yaml_mapping(text: str, source: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise CaseGenerationError(f"No se pudo analizar {source}: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("requirements"), list):
        raise CaseGenerationError(f"{source} debe definir una lista 'requirements'.")
    return value


def _revision_file(repository: Path, revision: str, relative_path: str) -> str:
    normalized = PurePosixPath(relative_path.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise CaseGenerationError(f"La ruta debe ser relativa al repositorio: {relative_path}")
    try:
        result = _git(repository, "show", f"{revision}:{normalized.as_posix()}", check=False)
    except GitAnalysisError as error:
        raise CaseGenerationError(f"No se pudo leer {relative_path} en {revision}: {error}") from error
    if result.returncode:
        raise CaseGenerationError(f"No existe {relative_path} en la revisión {revision}.")
    return result.stdout


def _matching_impacts(impacts: dict[str, Any]) -> list[dict[str, Any]]:
    entries = impacts.get("impacts")
    if not isinstance(entries, list):
        raise CaseGenerationError("impacts.json debe contener una lista 'impacts'.")
    relevant: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for impact in entries:
        if not isinstance(impact, dict):
            raise CaseGenerationError("Cada elemento de 'impacts' debe ser un objeto.")
        operation = impact.get("operacion")
        if not isinstance(operation, dict):
            continue
        method = operation.get("metodo")
        endpoint = operation.get("ruta")
        if not isinstance(method, str) or not isinstance(endpoint, str):
            raise CaseGenerationError("Los impactos de operación requieren método HTTP y ruta.")
        key = (method.upper(), endpoint)
        if key not in seen:
            relevant.append(impact)
            seen.add(key)
    if not relevant:
        raise CaseGenerationError("impacts.json no contiene impactos asociados a operaciones OpenAPI.")
    return relevant


def _operation_map(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise CaseGenerationError("La especificación OpenAPI no contiene 'paths'.")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() in {"get", "put", "post", "delete", "patch", "options", "head", "trace"}:
                if isinstance(operation, dict):
                    result[(method.upper(), path)] = operation
    return result


def _referenced_schemas(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/components/schemas/"):
            names.add(reference.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~"))
        for nested in value.values():
            names.update(_referenced_schemas(nested))
    elif isinstance(value, list):
        for nested in value:
            names.update(_referenced_schemas(nested))
    return names


def _relevant_context(
    impacts: dict[str, Any],
    openapi_text: str,
    rf_map_text: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    try:
        spec = json.loads(openapi_text)
    except json.JSONDecodeError as error:
        raise CaseGenerationError(f"La especificación OpenAPI no es JSON válido: {error}") from error
    if not isinstance(spec, dict):
        raise CaseGenerationError("La especificación OpenAPI debe ser un objeto.")
    mapping = _load_yaml_mapping(rf_map_text, "rf_map.yaml")
    relevant_impacts = _matching_impacts(impacts)
    operations = _operation_map(spec)
    mapping_items = mapping["requirements"]
    requirements: dict[tuple[str, str], dict[str, Any]] = {}
    for item in mapping_items:
        if not isinstance(item, dict):
            raise CaseGenerationError("Cada entrada de rf_map.yaml debe ser un objeto.")
        requirement_id = item.get("id")
        method = item.get("method")
        path = item.get("path")
        if not all(isinstance(value, str) for value in (requirement_id, method, path)):
            raise CaseGenerationError("Cada RF del mapa requiere id, method y path textuales.")
        key = (method.upper(), path)
        if key in requirements:
            raise CaseGenerationError(f"Hay más de un RF asignado a {key[0]} {key[1]}.")
        requirements[key] = item

    relevant_operations: dict[str, Any] = {}
    relevant_requirements: list[dict[str, Any]] = []
    schema_names: set[str] = set()
    for impact in relevant_impacts:
        operation = impact["operacion"]
        key = (operation["metodo"].upper(), operation["ruta"])
        contract_operation = operations.get(key)
        requirement = requirements.get(key)
        if contract_operation is None:
            raise CaseGenerationError(
                f"El impacto {key[0]} {key[1]} no existe en el contrato de la revisión destino."
            )
        if requirement is None:
            raise CaseGenerationError(f"No hay RF del SUT en rf_map.yaml para {key[0]} {key[1]}.")
        operation_id = contract_operation.get("operationId")
        if requirement.get("operation_id") and requirement["operation_id"] != operation_id:
            raise CaseGenerationError(
                f"El operationId de {key[0]} {key[1]} no coincide con rf_map.yaml."
            )
        path_item = spec["paths"][key[1]]
        relevant_operations.setdefault(key[1], {})[key[0].lower()] = {
            **contract_operation,
            **(
                {"_path_parameters": path_item["parameters"]}
                if isinstance(path_item, dict) and "parameters" in path_item
                else {}
            ),
        }
        relevant_requirements.append(requirement)
        schema_names.update(_referenced_schemas(contract_operation))

    components = spec.get("components", {})
    schemas = components.get("schemas", {}) if isinstance(components, dict) else {}
    if not isinstance(schemas, dict):
        raise CaseGenerationError("El objeto components.schemas de OpenAPI debe ser un mapa.")
    selected_schemas: dict[str, Any] = {}
    while schema_names:
        name = schema_names.pop()
        if name in selected_schemas or name not in schemas:
            continue
        schema = schemas[name]
        selected_schemas[name] = schema
        schema_names.update(_referenced_schemas(schema) - selected_schemas.keys())

    relevant_spec: dict[str, Any] = {
        "openapi": spec.get("openapi"),
        "paths": relevant_operations,
    }
    if selected_schemas:
        relevant_spec["components"] = {"schemas": selected_schemas}
    return relevant_spec, mapping, relevant_requirements


def _build_prompt(
    impacts: list[dict[str, Any]],
    relevant_spec: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> str:
    instructions = (
        "Genera casos de prueba para una API REST usando solamente la evidencia proporcionada. "
        "Devuelve exclusivamente el objeto JSON requerido por el esquema de respuesta. "
        "Cada caso debe cubrir un impacto y usar el RF asignado en rf_map; no inventes rutas, "
        "campos, reglas, códigos de respuesta ni resultados observados. Incluye escenarios válidos "
        "e inválidos y límites solo cuando el contrato los sustente. "
        "Usa exactamente estas columnas y estados: Estado='No ejecutado', Automatizado='No', "
        "Decisión de revisión='Pendiente'. El código esperado debe existir en responses de la operación. "
        "Usa IDs únicos secuenciales por RF con el patrón CP-<RF>-NN. "
        "Las técnicas permitidas son T. Decisión (valida), T. Decisión (invalida), "
        "EP (valida) y EP (invalida). No añadas propiedades."
    )
    context = {
        "impactos": impacts,
        "openapi_pertinente": relevant_spec,
        "rf_map_pertinente": requirements,
    }
    return instructions + "\n\nContexto JSON:\n" + json.dumps(
        context,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _json_value(value: object, field_name: str, case_id: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise GeminiResponseError(f"{field_name} de {case_id} no es un valor JSON válido.") from error


def validate_cases(
    response: object,
    requirements: list[dict[str, Any]],
    relevant_spec: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(response, dict) or set(response) != {"casos"}:
        raise GeminiResponseError("La respuesta debe tener únicamente la propiedad 'casos'.")
    cases = response["casos"]
    if not isinstance(cases, list) or not cases:
        raise GeminiResponseError("'casos' debe ser una lista no vacía.")

    requirements_by_rf = {item["id"]: item for item in requirements}
    spec_operations = _operation_map(relevant_spec)
    counters: dict[str, int] = {}
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict) or set(case) != set(CASE_COLUMNS):
            raise GeminiResponseError(
                f"El caso {index} debe contener exactamente las columnas requeridas."
            )
        if not all(isinstance(case[column], str) for column in BASE_COLUMNS):
            raise GeminiResponseError(f"Las nueve columnas base del caso {index} deben ser texto.")
        if not all(
            case[column].strip()
            for column in (
                "ID",
                "Descripción del Caso",
                "Datos de Entrada",
                "Pasos",
                "Resultado Esperado",
            )
        ):
            raise GeminiResponseError(f"El caso {index} contiene campos de texto obligatorios vacíos.")
        if case["Técnica"] not in TECHNIQUES:
            raise GeminiResponseError(f"Técnica no permitida en el caso {index}: {case['Técnica']!r}.")
        if case["Estado"] != "No ejecutado" or case["Automatizado"] != "No":
            raise GeminiResponseError(
                f"El caso {index} debe iniciar como No ejecutado y Automatizado No."
            )
        if case["Decisión de revisión"] != "Pendiente":
            raise GeminiResponseError(f"El caso {index} debe iniciar con revisión Pendiente.")

        match = _CASE_ID.fullmatch(case["ID"])
        if match is None:
            raise GeminiResponseError(f"ID inválido en el caso {index}: {case['ID']!r}.")
        requirement_id, sequence_text = match.groups()
        requirement = requirements_by_rf.get(requirement_id)
        if requirement is None:
            raise GeminiResponseError(f"El ID {case['ID']} usa un RF que no pertenece al mapa del SUT.")
        sequence = int(sequence_text)
        counters[requirement_id] = counters.get(requirement_id, 0) + 1
        if sequence != counters[requirement_id]:
            raise GeminiResponseError(
                f"Los IDs del requisito {requirement_id} deben ser secuenciales desde 01."
            )
        if case["ID"] in seen_ids:
            raise GeminiResponseError(f"ID duplicado: {case['ID']}.")
        seen_ids.add(case["ID"])

        method = case["Método HTTP"]
        endpoint = case["Endpoint"]
        expected_key = (requirement["method"].upper(), requirement["path"])
        if (method.upper(), endpoint) != expected_key:
            raise GeminiResponseError(
                f"El caso {case['ID']} no usa la operación asignada a {requirement_id}."
            )
        operation = spec_operations.get(expected_key)
        if operation is None:
            raise GeminiResponseError(f"La operación de {case['ID']} no está en el contrato pertinente.")
        status_code = case["Código de respuesta esperado"]
        if not isinstance(status_code, int) or isinstance(status_code, bool):
            raise GeminiResponseError(f"El código esperado de {case['ID']} debe ser un entero HTTP.")
        responses = operation.get("responses")
        if not isinstance(responses, dict) or str(status_code) not in responses:
            raise GeminiResponseError(
                f"El código {status_code} de {case['ID']} no está declarado en OpenAPI."
            )
        if not isinstance(case["Parámetros"], dict):
            raise GeminiResponseError(f"Parámetros de {case['ID']} debe ser un objeto.")
        if case["Cuerpo"] is not None and not isinstance(case["Cuerpo"], (dict, list)):
            raise GeminiResponseError(f"Cuerpo de {case['ID']} debe ser un objeto, una lista o null.")
        _json_value(case["Parámetros"], "Parámetros", case["ID"])
        _json_value(case["Cuerpo"], "Cuerpo", case["ID"])
        normalized.append({column: case[column] for column in CASE_COLUMNS})

    return normalized


def generate_cases(
    impacts_path: str | Path,
    output_path: str | Path,
    *,
    client: CaseGeneratorClient | None = None,
    dotenv_path: str | Path = ".env",
) -> dict[str, Any]:
    source_path = Path(impacts_path)
    impacts_document = _load_json(source_path)
    relevant_impacts = _matching_impacts(impacts_document)
    git_data = impacts_document.get("git")
    if not isinstance(git_data, dict) or not isinstance(git_data.get("repository"), str):
        raise CaseGenerationError("impacts.json debe contener git.repository.")
    repository = Path(git_data["repository"]).resolve()
    if not repository.is_dir():
        raise CaseGenerationError(f"No existe el repositorio indicado en impacts.json: {repository}")
    head = git_data.get("head")
    if not isinstance(head, str) or not head:
        raise CaseGenerationError("impacts.json debe contener git.head.")

    openapi_text = _revision_file(
        repository,
        head,
        "examples/sample_api/openapi.json",
    )
    rf_map_text = _revision_file(
        repository,
        head,
        "examples/sample_api/rf_map.yaml",
    )
    relevant_spec, _, relevant_requirements = _relevant_context(
        impacts_document,
        openapi_text,
        rf_map_text,
    )
    prompt = _build_prompt(relevant_impacts, relevant_spec, relevant_requirements)
    if client is None:
        config = load_gemini_config(dotenv_path)
        client = GeminiClient(config)
    response, provider_metadata = client.generate(prompt)
    cases = validate_cases(response, relevant_requirements, relevant_spec)
    document: dict[str, Any] = {
        "schema_version": 1,
        "metadata": {
            "model": client.model,
            "generated_at": datetime.now(UTC).isoformat(),
            "source": {
                "impacts_file": source_path.name,
                "base": git_data.get("base"),
                "head": head,
                "impact_count": len(relevant_impacts),
                "requirements": [item["id"] for item in relevant_requirements],
            },
            "provider": provider_metadata,
        },
        "casos": cases,
    }
    destination = Path(output_path)
    try:
        destination.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise CaseGenerationError(f"No se pudo escribir {destination}: {error}") from error
    return document
