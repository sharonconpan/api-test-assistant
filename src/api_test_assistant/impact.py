from __future__ import annotations

from collections.abc import Mapping
import re

from .git_changes import GitAnalysis


def _changed_lines(patch: str) -> list[str]:
    return [
        line[1:]
        for line in patch.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


def _schema_names(operation: Mapping[str, object]) -> set[str]:
    value = operation.get("schema_names", [])
    return {name for name in value if isinstance(name, str)} if isinstance(value, list) else set()


def _code_evidence(
    path: str,
    patch: str,
    operation: Mapping[str, object],
) -> list[dict[str, str]]:
    route = operation.get("path")
    operation_id = operation.get("operation_id")
    tokens: list[tuple[str, str]] = []
    if isinstance(route, str):
        tokens.append(("ruta", route))
        for component in re.findall(r"\{([^{}]+)\}", route):
            tokens.append(("parametro_ruta", component))
    if isinstance(operation_id, str):
        tokens.append(("operationId", operation_id))
    tokens.extend(("esquema", name) for name in sorted(_schema_names(operation)))

    evidence: list[dict[str, str]] = []
    for line in _changed_lines(patch):
        for kind, token in tokens:
            if kind == "ruta":
                pattern = rf"(?<![\w/.~-]){re.escape(token)}(?=$|[\s\"',)\]])"
            else:
                pattern = rf"(?<!\w){re.escape(token)}(?!\w)"
            if token and re.search(pattern, line):
                evidence.append(
                    {
                        "archivo": path,
                        "tipo": kind,
                        "coincidencia": token,
                        "linea_diff": line[:500],
                    }
                )
    return evidence


def _file_evidence(change: Mapping[str, object]) -> dict[str, object]:
    return {
        "archivo": change["path"],
        "estado_git": change["status"],
        **(
            {"ruta_anterior": change["previous_path"]}
            if change.get("previous_path")
            else {}
        ),
    }


def correlate_impact(
    git_analysis: GitAnalysis,
    openapi_diff: Mapping[str, object],
    base_spec: Mapping[str, object],
    head_spec: Mapping[str, object],
) -> list[dict[str, object]]:
    changes = [change.__dict__ for change in git_analysis.changes]
    patches = git_analysis.code_diffs
    operations = openapi_diff.get("operations", [])
    schema_changes = openapi_diff.get("schemas", [])
    if not isinstance(operations, list) or not isinstance(schema_changes, list):
        raise ValueError("El diff OpenAPI debe contener listas de operaciones y esquemas.")

    impacts: list[dict[str, object]] = []
    related_code_paths: set[str] = set()

    for raw_operation in operations:
        if not isinstance(raw_operation, dict):
            continue
        operation = dict(raw_operation)
        code_matches: list[dict[str, str]] = []
        for path, patch in patches.items():
            code_matches.extend(_code_evidence(path, patch, operation))
        for change in changes:
            path = str(change["path"])
            if path in patches:
                continue
            if path.lower().endswith(".py") and _code_evidence(path, "", operation):
                code_matches.append({"archivo": path, "tipo": "archivo", "coincidencia": path, "linea_diff": ""})

        if code_matches:
            related_code_paths.update(match["archivo"] for match in code_matches)
            classification = "concordante"
        else:
            classification = "solo_openapi"

        impacts.append(
            {
                "clasificacion": classification,
                "operacion": {
                    "metodo": operation.get("method"),
                    "ruta": operation.get("path"),
                    "operationId": operation.get("operation_id"),
                    "esquemas": operation.get("schema_names", []),
                },
                "cambio_openapi": operation.get("change"),
                "evidencia": {
                    "openapi": operation.get("changes", []),
                    "codigo": code_matches,
                },
            }
        )

    changed_schema_names = {
        str(schema["name"])
        for schema in schema_changes
        if isinstance(schema, dict) and isinstance(schema.get("name"), str)
    }
    represented_schema_names: set[str] = set()
    if changed_schema_names:
        for path, method in _all_operations(base_spec, head_spec):
            operation = {
                "path": path,
                "operation_id": method.get("operationId"),
                "schema_names": sorted(_schema_references(method)),
            }
            matching_schemas = sorted(_schema_names(operation) & changed_schema_names)
            if not matching_schemas:
                continue
            represented_schema_names.update(matching_schemas)
            code_matches = [
                match
                for file_path, patch in patches.items()
                for match in _code_evidence(file_path, patch, operation)
                if match["tipo"] == "esquema"
            ]
            matching_impact = next(
                (
                    impact
                    for impact in impacts
                    if impact.get("operacion", {}).get("metodo") == method.get("_method")
                    and impact.get("operacion", {}).get("ruta") == path
                ),
                None,
            )
            schema_evidence = [
                schema
                for schema in schema_changes
                if isinstance(schema, dict) and schema.get("name") in matching_schemas
            ]
            if matching_impact is not None:
                matching_impact["evidencia"]["openapi"].extend(schema_evidence)
                matching_impact["evidencia"]["codigo"].extend(code_matches)
                if code_matches:
                    matching_impact["clasificacion"] = "concordante"
            else:
                impacts.append(
                    {
                        "clasificacion": "concordante" if code_matches else "solo_openapi",
                        "operacion": {
                            "metodo": method.get("_method"),
                            "ruta": path,
                            "operationId": operation["operation_id"],
                            "esquemas": matching_schemas,
                        },
                        "cambio_openapi": "schema_modified",
                        "evidencia": {"openapi": schema_evidence, "codigo": code_matches},
                    }
                )
            related_code_paths.update(match["archivo"] for match in code_matches)

    for schema in schema_changes:
        if not isinstance(schema, dict) or schema.get("name") in represented_schema_names:
            continue
        schema_name = str(schema["name"])
        code_matches = [
            {
                "archivo": path,
                "tipo": "esquema",
                "coincidencia": schema_name,
                "linea_diff": line[:500],
            }
            for path, patch in patches.items()
            for line in _changed_lines(patch)
            if schema_name in line
        ]
        related_code_paths.update(match["archivo"] for match in code_matches)
        impacts.append(
            {
                "clasificacion": "concordante" if code_matches else "solo_openapi",
                "operacion": None,
                "cambio_openapi": "schema_" + str(schema.get("change")),
                "evidencia": {"openapi": [schema], "codigo": code_matches},
            }
        )

    for path, patch in patches.items():
        if path in related_code_paths:
            continue
        matching_operations: list[tuple[str, dict[str, object], list[dict[str, str]]]] = []
        for route, operation in _all_operations(base_spec, head_spec):
            operation_data = {
                "path": route,
                "operation_id": operation.get("operationId"),
                "schema_names": sorted(_schema_references(operation)),
            }
            evidence = _code_evidence(path, patch, operation_data)
            if evidence:
                matching_operations.append((route, operation, evidence))
        if matching_operations:
            for route, operation, evidence in matching_operations:
                impacts.append(
                    {
                        "clasificacion": "solo_codigo",
                        "operacion": {
                            "metodo": operation.get("_method"),
                            "ruta": route,
                            "operationId": operation.get("operationId"),
                            "esquemas": sorted(_schema_references(operation)),
                        },
                        "cambio_openapi": None,
                        "evidencia": {"codigo": evidence, "openapi": []},
                    }
                )
            related_code_paths.add(path)

    for change in changes:
        path = str(change["path"])
        if path in related_code_paths:
            continue
        patch = patches.get(path, "")
        evidence = _file_evidence(change)
        if patch:
            evidence["diff"] = _changed_lines(patch)[:20]
        impacts.append(
            {
                "clasificacion": "solo_codigo",
                "operacion": None,
                "cambio_openapi": None,
                "evidencia": {"codigo": [evidence], "openapi": []},
            }
        )

    return impacts


def _all_operations(
    base_spec: Mapping[str, object],
    head_spec: Mapping[str, object],
) -> list[tuple[str, dict[str, object]]]:
    operations: dict[tuple[str, str], dict[str, object]] = {}
    for spec in (base_spec, head_spec):
        paths = spec.get("paths")
        if not isinstance(paths, dict):
            continue
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.lower() in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}:
                    if isinstance(operation, dict):
                        operations[(str(path), method.upper())] = {**operation, "_method": method.upper()}
    return [(path, operation) for (path, _), operation in sorted(operations.items())]


def _schema_references(value: object) -> set[str]:
    references: set[str] = set()
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/components/schemas/"):
            references.add(reference.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~"))
        for nested in value.values():
            references.update(_schema_references(nested))
    elif isinstance(value, list):
        for nested in value:
            references.update(_schema_references(nested))
    return references
