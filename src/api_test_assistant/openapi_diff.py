from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
import json
import subprocess

import yaml

from .git_changes import GitAnalysisError, _git


class OpenAPIAnalysisError(RuntimeError):
    """Error al recuperar o interpretar una especificación OpenAPI."""


_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
_RESTRICTIONS = {
    "enum",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "format",
    "maxItems",
    "maxLength",
    "maximum",
    "minItems",
    "minLength",
    "minimum",
    "pattern",
    "required",
    "type",
    "uniqueItems",
}


def _load_spec_text(text: str, source: str) -> dict[str, object]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise OpenAPIAnalysisError(f"No se pudo analizar OpenAPI en {source}: {error}") from error
    if not isinstance(parsed, dict):
        raise OpenAPIAnalysisError(f"La especificación OpenAPI de {source} debe ser un objeto.")
    if not isinstance(parsed.get("paths"), dict):
        raise OpenAPIAnalysisError(f"La especificación OpenAPI de {source} no contiene un objeto 'paths'.")
    if not isinstance(parsed.get("openapi"), str) and not isinstance(parsed.get("swagger"), str):
        raise OpenAPIAnalysisError(f"La especificación de {source} no declara una versión OpenAPI o Swagger.")
    for path, path_item in parsed["paths"].items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            raise OpenAPIAnalysisError(f"La especificación de {source} contiene una ruta no válida.")
        if "$ref" in path_item:
            raise OpenAPIAnalysisError(
                f"La ruta {path} en {source} usa un Path Item $ref, que este comparador no resuelve."
            )
        for method, operation in path_item.items():
            if not isinstance(method, str):
                raise OpenAPIAnalysisError(f"La ruta {path} en {source} tiene una clave no textual.")
            if method.lower() in _HTTP_METHODS and not isinstance(operation, dict):
                raise OpenAPIAnalysisError(
                    f"La operación {method.upper()} {path} en {source} no es un objeto."
                )
    components = parsed.get("components")
    if components is not None and not isinstance(components, dict):
        raise OpenAPIAnalysisError(f"El objeto 'components' de {source} debe ser un mapa.")
    if isinstance(components, dict) and "schemas" in components and not isinstance(
        components["schemas"], dict
    ):
        raise OpenAPIAnalysisError(f"El objeto 'components.schemas' de {source} debe ser un mapa.")
    if isinstance(components, dict) and isinstance(components.get("schemas"), dict):
        if not all(isinstance(name, str) for name in components["schemas"]):
            raise OpenAPIAnalysisError(f"Los nombres de 'components.schemas' en {source} deben ser texto.")
    return parsed


def load_spec_from_revision(
    repo_path: str,
    revision: str,
    spec_path: str,
) -> dict[str, object]:
    normalized_path = PurePosixPath(spec_path.replace("\\", "/"))
    if normalized_path.is_absolute() or ".." in normalized_path.parts:
        raise OpenAPIAnalysisError(f"La ruta de especificación debe ser relativa al repositorio: {spec_path}")
    try:
        result = _git(Path(repo_path), "show", f"{revision}:{normalized_path.as_posix()}", check=False)
    except GitAnalysisError as error:
        raise OpenAPIAnalysisError(f"No se pudo recuperar OpenAPI de {revision}: {error}") from error
    if result.returncode != 0:
        raise OpenAPIAnalysisError(
            f"No se encontró la especificación versionada '{normalized_path}' en la revisión {revision}."
        )
    try:
        return _load_spec_text(result.stdout, f"{revision}:{normalized_path}")
    except OpenAPIAnalysisError:
        raise
    except (UnicodeDecodeError, ValueError) as error:
        raise OpenAPIAnalysisError(
            f"No se pudo analizar OpenAPI en {revision}:{normalized_path}: {error}"
        ) from error


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _identity_map(values: Sequence[object]) -> dict[str, object] | None:
    if not all(isinstance(value, dict) for value in values):
        return None
    result: dict[str, object] = {}
    for value in values:
        assert isinstance(value, dict)
        if "name" not in value or "in" not in value:
            return None
        key = f"{value['in']}:{value['name']}"
        result[key] = value
    return result


def _diff_values(before: object, after: object, pointer: str = "") -> list[dict[str, object]]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict[str, object]] = []
        keys = sorted(set(before) | set(after))
        for key in keys:
            child_pointer = f"{pointer}/{_escape_pointer(str(key))}"
            if key not in before:
                changes.append({"change": "added", "path": child_pointer, "after": after[key]})
            elif key not in after:
                changes.append({"change": "removed", "path": child_pointer, "before": before[key]})
            else:
                changes.extend(_diff_values(before[key], after[key], child_pointer))
        return changes

    if isinstance(before, list) and isinstance(after, list):
        before_map = _identity_map(before)
        after_map = _identity_map(after)
        if before_map is not None and after_map is not None:
            return _diff_values(before_map, after_map, pointer)
        if before == after:
            return []
        if all(not isinstance(value, (dict, list)) for value in [*before, *after]):
            return [{"change": "modified", "path": pointer or "/", "before": before, "after": after}]
        changes = []
        for index in range(max(len(before), len(after))):
            child_pointer = f"{pointer}/{index}"
            if index >= len(before):
                changes.append({"change": "added", "path": child_pointer, "after": after[index]})
            elif index >= len(after):
                changes.append({"change": "removed", "path": child_pointer, "before": before[index]})
            else:
                changes.extend(_diff_values(before[index], after[index], child_pointer))
        return changes

    if before != after:
        return [{"change": "modified", "path": pointer or "/", "before": before, "after": after}]
    return []


def _section(path: str) -> str:
    parts = {part for part in path.split("/") if part}
    if "parameters" in parts:
        return "parameters"
    if "requestBody" in parts:
        return "request_body"
    if "responses" in parts:
        return "responses"
    return "operation"


def _category(path: str) -> str:
    parts = {part for part in path.split("/") if part}
    if parts & _RESTRICTIONS:
        return "restrictions"
    return _section(path)


def _operation_id(operation: Mapping[str, object]) -> str | None:
    value = operation.get("operationId")
    return value if isinstance(value, str) else None


def _operation_changes(before: object, after: object) -> list[dict[str, object]]:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    return [
        {
            **change,
            "category": _category(str(change["path"])),
            "section": _section(str(change["path"])),
        }
        for change in _diff_values(before, after)
    ]


def _referenced_schemas(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/components/schemas/"):
            found.add(reference.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~"))
        for nested in value.values():
            found.update(_referenced_schemas(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_referenced_schemas(nested))
    return found


def compare_openapi(
    base_spec: Mapping[str, object],
    head_spec: Mapping[str, object],
) -> dict[str, object]:
    base_paths = base_spec.get("paths")
    head_paths = head_spec.get("paths")
    if not isinstance(base_paths, dict) or not isinstance(head_paths, dict):
        raise OpenAPIAnalysisError("Ambas especificaciones deben contener un objeto 'paths'.")

    base_operations: dict[tuple[str, str], object] = {}
    head_operations: dict[tuple[str, str], object] = {}
    for spec_paths, operations in (
        (base_paths, base_operations),
        (head_paths, head_operations),
    ):
        for path, path_item in spec_paths.items():
            if not isinstance(path, str) or not isinstance(path_item, dict):
                raise OpenAPIAnalysisError("Las especificaciones contienen una ruta no válida.")
            for method, operation in path_item.items():
                if not isinstance(method, str):
                    raise OpenAPIAnalysisError(f"La ruta {path} contiene una clave no textual.")
                if method.lower() in _HTTP_METHODS:
                    if not isinstance(operation, dict):
                        raise OpenAPIAnalysisError(f"La operación {method.upper()} {path} no es un objeto.")
                    operations[(path, method.lower())] = operation

    operations: list[dict[str, object]] = []
    for path, method in sorted(set(base_operations) | set(head_operations)):
        before = base_operations.get((path, method))
        after = head_operations.get((path, method))
        if before is None:
            assert isinstance(after, dict)
            operations.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "change": "added",
                    "operation_id": _operation_id(after),
                    "schema_names": sorted(_referenced_schemas(after)),
                    "changes": [{"change": "added", "path": "/", "after": after, "category": "operation"}],
                }
            )
        elif after is None:
            assert isinstance(before, dict)
            operations.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "change": "removed",
                    "operation_id": _operation_id(before),
                    "schema_names": sorted(_referenced_schemas(before)),
                    "changes": [{"change": "removed", "path": "/", "before": before, "category": "operation"}],
                }
            )
        elif isinstance(before, dict) and isinstance(after, dict):
            changes = _operation_changes(before, after)
            if changes:
                operations.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "change": "modified",
                        "operation_id": _operation_id(after) or _operation_id(before),
                        "schema_names": sorted(_referenced_schemas(before) | _referenced_schemas(after)),
                        "changes": changes,
                    }
                )

    base_components = base_spec.get("components")
    head_components = head_spec.get("components")
    base_schemas = base_components.get("schemas", {}) if isinstance(base_components, dict) else {}
    head_schemas = head_components.get("schemas", {}) if isinstance(head_components, dict) else {}
    if not isinstance(base_schemas, dict) or not isinstance(head_schemas, dict):
        raise OpenAPIAnalysisError("El objeto components.schemas debe ser un mapa.")

    schemas: list[dict[str, object]] = []
    for name in sorted(set(base_schemas) | set(head_schemas)):
        before = base_schemas.get(name)
        after = head_schemas.get(name)
        if name not in base_schemas:
            schemas.append(
                {
                    "name": name,
                    "change": "added",
                    "changes": [
                        {"change": "added", "path": "/", "after": after, "category": "restrictions"}
                    ],
                }
            )
        elif name not in head_schemas:
            schemas.append(
                {
                    "name": name,
                    "change": "removed",
                    "changes": [
                        {"change": "removed", "path": "/", "before": before, "category": "restrictions"}
                    ],
                }
            )
        else:
            changes = [
                {**change, "category": "restrictions", "section": "schema"}
                for change in _diff_values(before, after)
            ]
            if changes:
                schemas.append({"name": name, "change": "modified", "changes": changes})

    return {
        "status": "cambios" if operations or schemas else "sin_cambios",
        "operations": operations,
        "schemas": schemas,
    }


def load_and_compare_openapi(
    repo_path: str,
    base: str,
    head: str,
    spec_path: str,
) -> dict[str, object]:
    try:
        base_spec = load_spec_from_revision(repo_path, base, spec_path)
        head_spec = load_spec_from_revision(repo_path, head, spec_path)
    except subprocess.SubprocessError as error:
        raise OpenAPIAnalysisError(f"No se pudo analizar OpenAPI: {error}") from error
    return compare_openapi(base_spec, head_spec)
