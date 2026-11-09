from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_API = ROOT / "examples" / "sample_api"
sys.path.insert(0, str(ROOT / "src"))

from api_test_assistant.git_changes import GitAnalysis, GitAnalysisError, analyze_git_changes
from api_test_assistant.impact import correlate_impact
from api_test_assistant.openapi_diff import (
    OpenAPIAnalysisError,
    compare_openapi,
    load_and_compare_openapi,
    load_spec_from_revision,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _new_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "API Test Assistant tests")
    shutil.copytree(
        SAMPLE_API,
        repo / "examples" / "sample_api",
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    return repo


def _refresh_spec(repo: Path) -> None:
    subprocess.run(
        [sys.executable, "examples/sample_api/export_openapi.py"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _changes_for_repo(
    repo: Path,
    base: str,
    head: str,
) -> tuple[GitAnalysis, dict[str, object], dict[str, object], dict[str, object]]:
    git_analysis = analyze_git_changes(repo, base, head)
    openapi_diff = load_and_compare_openapi(
        str(repo),
        git_analysis.base,
        git_analysis.head,
        "examples/sample_api/openapi.json",
    )
    base_spec = load_spec_from_revision(str(repo), git_analysis.base, "examples/sample_api/openapi.json")
    head_spec = load_spec_from_revision(str(repo), git_analysis.head, "examples/sample_api/openapi.json")
    return (
        git_analysis,
        openapi_diff,
        base_spec,
        {"impacts": correlate_impact(git_analysis, openapi_diff, base_spec, head_spec)},
    )


def test_git_diff_reports_added_modified_deleted_and_renamed_files(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    (repo / "deleted.txt").write_text("eliminar\n", encoding="utf-8")
    base = _commit(repo, "base")
    item_app = repo / "examples" / "sample_api" / "app" / "main.py"
    item_app.write_text(item_app.read_text(encoding="utf-8") + "\n# cambio\n", encoding="utf-8")
    (repo / "added.txt").write_text("nuevo\n", encoding="utf-8")
    (repo / "deleted.txt").unlink()
    renamed_from = repo / "examples" / "sample_api" / "rf_map.yaml"
    renamed_to = repo / "examples" / "sample_api" / "requirements-map.yaml"
    renamed_from.rename(renamed_to)
    head = _commit(repo, "changes")

    changes = analyze_git_changes(repo, base, head).changes
    by_path = {change.path: change for change in changes}

    assert by_path["added.txt"].status == "added"
    assert by_path["deleted.txt"].status == "deleted"
    assert by_path["examples/sample_api/app/main.py"].status == "modified"
    assert by_path["examples/sample_api/requirements-map.yaml"].status == "renamed"
    assert by_path["examples/sample_api/requirements-map.yaml"].previous_path == "examples/sample_api/rf_map.yaml"


def test_git_analysis_reports_non_repository_and_unknown_revision(tmp_path: Path) -> None:
    with pytest.raises(GitAnalysisError, match="no pertenece a un repositorio"):
        analyze_git_changes(tmp_path, "HEAD", "HEAD")

    repo = _new_repo(tmp_path)
    base = _commit(repo, "base")
    with pytest.raises(GitAnalysisError, match="no existe"):
        analyze_git_changes(repo, base, "missing-reference")


def test_openapi_diff_distinguishes_no_changes_and_invalid_spec(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    revision = _commit(repo, "base")

    unchanged = load_and_compare_openapi(
        str(repo), revision, revision, "examples/sample_api/openapi.json"
    )
    assert unchanged == {"status": "sin_cambios", "operations": [], "schemas": []}

    with pytest.raises(OpenAPIAnalysisError, match="No se encontró la especificación"):
        load_and_compare_openapi(str(repo), revision, revision, "missing-openapi.json")

    with pytest.raises(OpenAPIAnalysisError, match="deben contener un objeto 'paths'"):
        compare_openapi({"openapi": "3.1.0", "paths": []}, {"openapi": "3.1.0", "paths": []})


def test_added_operation_is_correlated_with_code_evidence(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    base = _commit(repo, "base")
    app_path = repo / "examples" / "sample_api" / "app" / "main.py"
    source = app_path.read_text(encoding="utf-8")
    marker = '    @app.get("/items/{item_id}", response_model=Item, operation_id="get_item")'
    addition = (
        '    @app.get("/items/search", response_model=list[Item], operation_id="search_items")\n'
        "    def search_items() -> list[Item]:\n"
        "        return list(items.values())\n\n"
    )
    assert marker in source
    app_path.write_text(source.replace(marker, addition + marker), encoding="utf-8")
    _refresh_spec(repo)
    head = _commit(repo, "add search operation")

    _, openapi_diff, _, correlated = _changes_for_repo(repo, base, head)
    operation = next(item for item in openapi_diff["operations"] if item["path"] == "/items/search")
    impact = next(
        item
        for item in correlated["impacts"]
        if item["operacion"] and item["operacion"]["ruta"] == "/items/search"
    )

    assert operation["change"] == "added"
    assert impact["clasificacion"] == "concordante"
    assert {evidence["tipo"] for evidence in impact["evidencia"]["codigo"]} >= {"ruta", "operationId"}


def test_changed_parameter_is_reported_with_concordant_evidence(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    base = _commit(repo, "base")
    app_path = repo / "examples" / "sample_api" / "app" / "main.py"
    source = app_path.read_text(encoding="utf-8")
    old_decorator = '@app.get("/items", response_model=list[Item], operation_id="list_items")'
    new_decorator = (
        '@app.get("/items", response_model=list[Item], operation_id="list_items", '
        'summary="List items with optional limit")'
    )
    old_handler = "    def list_items() -> list[Item]:\n        return list(items.values())"
    new_handler = (
        "    def list_items(limit: int = 100) -> list[Item]:\n"
        "        return list(items.values())[:limit]"
    )
    assert old_decorator in source and old_handler in source
    app_path.write_text(
        source.replace(old_decorator, new_decorator).replace(old_handler, new_handler),
        encoding="utf-8",
    )
    _refresh_spec(repo)
    head = _commit(repo, "add list limit")

    _, openapi_diff, _, correlated = _changes_for_repo(repo, base, head)
    operation = next(item for item in openapi_diff["operations"] if item["path"] == "/items")
    impact = next(
        item
        for item in correlated["impacts"]
        if item["operacion"] and item["operacion"]["ruta"] == "/items"
    )

    assert operation["change"] == "modified"
    assert any(change["category"] == "parameters" for change in operation["changes"])
    assert impact["clasificacion"] == "concordante"
    assert any(evidence["tipo"] == "operationId" for evidence in impact["evidencia"]["codigo"])


def test_removed_response_is_reported_with_concordant_evidence(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    app_path = repo / "examples" / "sample_api" / "app" / "main.py"
    source = app_path.read_text(encoding="utf-8")
    get_decorator = '@app.get("/items/{item_id}", response_model=Item, operation_id="get_item")'
    with_response = (
        '@app.get("/items/{item_id}", response_model=Item, operation_id="get_item", '
        'responses={404: {"description": "Elemento no encontrado"}})'
    )
    assert get_decorator in source
    app_path.write_text(source.replace(get_decorator, with_response), encoding="utf-8")
    _refresh_spec(repo)
    base = _commit(repo, "document not found response")

    source = app_path.read_text(encoding="utf-8")
    assert with_response in source
    app_path.write_text(source.replace(with_response, get_decorator), encoding="utf-8")
    _refresh_spec(repo)
    head = _commit(repo, "remove documented response")

    _, openapi_diff, _, correlated = _changes_for_repo(repo, base, head)
    operation = next(item for item in openapi_diff["operations"] if item["path"] == "/items/{item_id}")
    impact = next(
        item
        for item in correlated["impacts"]
        if item["operacion"] and item["operacion"]["ruta"] == "/items/{item_id}"
    )

    assert operation["change"] == "modified"
    assert any(
        change["category"] == "responses" and change["change"] == "removed"
        for change in operation["changes"]
    )
    assert impact["clasificacion"] == "concordante"


def test_code_only_change_is_correlated_to_matching_operation(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    base = _commit(repo, "base")
    app_path = repo / "examples" / "sample_api" / "app" / "main.py"
    source = app_path.read_text(encoding="utf-8")
    old_decorator = '@app.get("/items", response_model=list[Item], operation_id="list_items")'
    new_decorator = (
        '@app.get("/items", response_model=list[Item], operation_id="list_items", '
        'summary="List items")'
    )
    assert old_decorator in source
    app_path.write_text(source.replace(old_decorator, new_decorator), encoding="utf-8")
    head = _commit(repo, "change implementation metadata only")

    _, openapi_diff, _, correlated = _changes_for_repo(repo, base, head)
    impact = next(
        item
        for item in correlated["impacts"]
        if item["operacion"] and item["operacion"]["ruta"] == "/items"
        and item["operacion"]["metodo"] == "GET"
    )

    assert openapi_diff["status"] == "sin_cambios"
    assert impact["clasificacion"] == "solo_codigo"
    assert any(evidence["tipo"] == "operationId" for evidence in impact["evidencia"]["codigo"])


def test_route_prefix_does_not_create_an_unsupported_match(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    base = _commit(repo, "base")
    app_path = repo / "examples" / "sample_api" / "app" / "main.py"
    source = app_path.read_text(encoding="utf-8")
    old_decorator = '@app.get("/items/{item_id}", response_model=Item, operation_id="get_item")'
    new_decorator = (
        '@app.get("/items/{item_id}", response_model=Item, operation_id="get_item", '
        'summary="Get one item")'
    )
    assert old_decorator in source
    app_path.write_text(source.replace(old_decorator, new_decorator), encoding="utf-8")
    head = _commit(repo, "change detail operation metadata")

    _, openapi_diff, _, correlated = _changes_for_repo(repo, base, head)

    assert openapi_diff["status"] == "sin_cambios"
    impacts_by_route = {
        item["operacion"]["ruta"]: item
        for item in correlated["impacts"]
        if item["clasificacion"] == "solo_codigo" and item["operacion"] is not None
    }
    assert set(impacts_by_route) == {"/items", "/items/{item_id}"}
    assert all(
        evidence["tipo"] != "ruta"
        for evidence in impacts_by_route["/items"]["evidencia"]["codigo"]
    )
    assert any(
        evidence["tipo"] == "ruta" and evidence["coincidencia"] == "/items/{item_id}"
        for evidence in impacts_by_route["/items/{item_id}"]["evidencia"]["codigo"]
    )


def test_schema_change_is_correlated_by_schema_name(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    base = _commit(repo, "base")
    app_path = repo / "examples" / "sample_api" / "app" / "main.py"
    source = app_path.read_text(encoding="utf-8")
    assert "ItemInput" in source
    app_path.write_text(source.replace("ItemInput", "ItemPayload"), encoding="utf-8")
    _refresh_spec(repo)
    head = _commit(repo, "rename request schema")

    _, openapi_diff, _, correlated = _changes_for_repo(repo, base, head)
    impact = next(
        item
        for item in correlated["impacts"]
        if item["operacion"] and item["operacion"]["ruta"] == "/items"
        and item["operacion"]["metodo"] == "POST"
    )

    assert {schema["name"] for schema in openapi_diff["schemas"]} >= {"ItemInput", "ItemPayload"}
    assert impact["clasificacion"] == "concordante"
    assert any(evidence["tipo"] == "esquema" for evidence in impact["evidencia"]["codigo"])


def test_openapi_only_change_is_not_attributed_to_code(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    base = _commit(repo, "base")
    snapshot_path = repo / "examples" / "sample_api" / "openapi.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["paths"]["/items/audit"] = {
        "get": {
            "operationId": "audit_items",
            "responses": {"200": {"description": "Auditoría"}},
        }
    }
    snapshot["components"]["schemas"]["AuditRecord"] = {
        "type": "object",
        "properties": {"event": {"type": "string"}},
    }
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    head = _commit(repo, "add contract-only operation")

    _, openapi_diff, _, correlated = _changes_for_repo(repo, base, head)
    impact = next(
        item
        for item in correlated["impacts"]
        if item["operacion"] and item["operacion"]["ruta"] == "/items/audit"
    )

    assert openapi_diff["status"] == "cambios"
    assert impact["clasificacion"] == "solo_openapi"
    assert impact["evidencia"]["codigo"] == []
    schema_impact = next(
        item
        for item in correlated["impacts"]
        if item["operacion"] is None and item["cambio_openapi"] == "schema_added"
    )
    assert schema_impact["clasificacion"] == "solo_openapi"
    assert schema_impact["evidencia"]["openapi"][0]["name"] == "AuditRecord"


def test_openapi_diff_reports_body_restrictions_and_responses() -> None:
    base = {
        "openapi": "3.1.0",
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "string", "maxLength": 80}
                            }
                        }
                    },
                    "responses": {"201": {"description": "Creado"}},
                }
            }
        },
    }
    head = {
        "openapi": "3.1.0",
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "string", "maxLength": 120}
                            }
                        }
                    },
                    "responses": {
                        "201": {"description": "Creado"},
                        "400": {"description": "Inválido"},
                    },
                }
            }
        },
    }

    result = compare_openapi(base, head)
    changes = result["operations"][0]["changes"]

    assert result["status"] == "cambios"
    assert any(
        change["category"] == "restrictions" and change["section"] == "request_body"
        for change in changes
    )
    assert any(
        change["section"] == "responses" and change["change"] == "added"
        for change in changes
    )


def test_unrelated_code_change_is_not_claimed_as_openapi_impact(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    base = _commit(repo, "base")
    (repo / "examples" / "sample_api" / "app" / "unrelated.py").write_text(
        "VALUE = 'independiente'\n",
        encoding="utf-8",
    )
    head = _commit(repo, "unrelated change")

    git_analysis, openapi_diff, _, correlated = _changes_for_repo(repo, base, head)

    assert openapi_diff["status"] == "sin_cambios"
    assert len(git_analysis.changes) == 1
    assert correlated["impacts"] == [
        {
            "clasificacion": "solo_codigo",
            "operacion": None,
            "cambio_openapi": None,
            "evidencia": {
                "codigo": [
                    {
                        "archivo": "examples/sample_api/app/unrelated.py",
                        "estado_git": "added",
                        "diff": ["VALUE = 'independiente'"],
                    }
                ],
                "openapi": [],
            },
        }
    ]


def test_cli_writes_json_impacts_and_reports_unanalyzable_openapi(
    tmp_path: Path,
) -> None:
    repo = _new_repo(tmp_path)
    revision = _commit(repo, "base")
    output_path = tmp_path / "impacts.json"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "api_test_assistant",
            "--repo",
            str(repo),
            "--base",
            revision,
            "--head",
            revision,
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["openapi"]["status"] == "sin_cambios"
    assert result["impacts"] == []

    failed = subprocess.run(
        [
            sys.executable,
            "-m",
            "api_test_assistant",
            "--repo",
            str(repo),
            "--base",
            revision,
            "--head",
            revision,
            "--spec",
            "missing.json",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert failed.returncode == 2
    error_result = json.loads(output_path.read_text(encoding="utf-8"))
    assert error_result["openapi"]["status"] == "no_se_pudo_analizar"

    invalid_revision = subprocess.run(
        [
            sys.executable,
            "-m",
            "api_test_assistant",
            "--repo",
            str(repo),
            "--base",
            revision,
            "--head",
            "missing-reference",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert invalid_revision.returncode == 2
    assert "La referencia Git no existe" in json.loads(invalid_revision.stderr)["error"]
