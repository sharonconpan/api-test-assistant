from collections.abc import Iterator
from pathlib import Path
import re

from fastapi.testclient import TestClient
import pytest
import yaml

from examples.sample_api.app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_create_item_accepts_maximum_name_length(client: TestClient) -> None:
    response = client.post("/items", json={"name": "x" * 80})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "x" * 80, "description": None}


@pytest.mark.parametrize("name", ["", "x" * 81])
def test_create_item_rejects_name_outside_limits(client: TestClient, name: str) -> None:
    response = client.post("/items", json={"name": name})

    assert response.status_code == 422


def test_create_item_rejects_description_over_maximum(client: TestClient) -> None:
    response = client.post("/items", json={"name": "válido", "description": "x" * 201})

    assert response.status_code == 422


def test_list_items_returns_created_items(client: TestClient) -> None:
    client.post("/items", json={"name": "Primero"})
    client.post("/items", json={"name": "Segundo"})

    response = client.get("/items")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Primero", "Segundo"]


def test_get_item_returns_not_found_for_unknown_id(client: TestClient) -> None:
    response = client.get("/items/99")

    assert response.status_code == 404


def test_update_and_delete_item(client: TestClient) -> None:
    created = client.post("/items", json={"name": "Antes"}).json()

    updated = client.put("/items/1", json={"name": "Después"})
    deleted = client.delete("/items/1")
    missing = client.get("/items/1")

    assert updated.status_code == 200
    assert updated.json() == {"id": created["id"], "name": "Después", "description": None}
    assert deleted.status_code == 204
    assert missing.status_code == 404


def test_rf_map_matches_openapi_operations() -> None:
    map_path = Path(__file__).parents[1] / "rf_map.yaml"
    rf_map = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    openapi = create_app().openapi()
    requirements = rf_map["requirements"]

    assert len(requirements) == 5
    assert len({requirement["id"] for requirement in requirements}) == 5
    for requirement in requirements:
        assert re.fullmatch(r"RF\d{2}\.\d", requirement["id"])
        operation = openapi["paths"][requirement["path"]][requirement["method"].lower()]
        assert operation["operationId"] == requirement["operation_id"]
