from __future__ import annotations

from fastapi.testclient import TestClient


class TestCreateItem:
    def test_post_creates_item_returns_201(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/items",
            json={"name": "Widget", "category": "tools", "value": 9.99},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Widget"
        assert body["category"] == "tools"
        assert body["value"] == 9.99
        assert isinstance(body["id"], int)

    def test_blank_name_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/items", json={"name": ""})
        assert response.status_code == 422


class TestGetItem:
    def test_get_unknown_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/items/99999")
        assert response.status_code == 404


class TestListItems:
    def test_empty_list_returns_empty_array(self, client: TestClient) -> None:
        response = client.get("/api/v1/items")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["next_cursor"] is None

    def test_list_after_create_returns_item(self, client: TestClient) -> None:
        client.post("/api/v1/items", json={"name": "Alpha"})
        response = client.get("/api/v1/items")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["name"] == "Alpha"


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        assert client.get("/health").json() == {"status": "ok"}
