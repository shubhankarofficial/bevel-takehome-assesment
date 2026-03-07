import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from src.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the health check endpoint."""
    with patch('src.main.get_engine') as mock_get_engine, \
         patch('src.main.es_client') as mock_es:

        # Mock database (SQLAlchemy engine + connection)
        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value='2024-01-01 00:00:00')
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        # Mock Elasticsearch response
        mock_es.info = AsyncMock(return_value={
            'version': {'number': '8.6.2', 'build_flavor': 'default'}
        })

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "dbTime" in data
        assert "esVersion" in data


@pytest.mark.asyncio
async def test_search_endpoint(app_with_search_mocks):
    """Test the search endpoint (uses shared fixture for app state)."""
    async with AsyncClient(app=app_with_search_mocks, base_url="http://test") as client:
        response = await client.get("/search?query=test")

    assert response.status_code == 200
    data = response.json()
    assert "foods" in data


@pytest.mark.asyncio
async def test_search_missing_query_400(app_with_search_mocks):
    """Missing query param -> 400."""
    async with AsyncClient(app=app_with_search_mocks, base_url="http://test") as client:
        response = await client.get("/search")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data or "message" in data or "detail" in data


@pytest.mark.asyncio
async def test_search_empty_query_400(app_with_search_mocks):
    """Empty or whitespace-only query -> 400."""
    async with AsyncClient(app=app_with_search_mocks, base_url="http://test") as client:
        r1 = await client.get("/search?query=")
        r2 = await client.get("/search?query=%20%20")
    assert r1.status_code == 400
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_search_invalid_size_zero_400(app_with_search_mocks):
    """size=0 -> 400."""
    async with AsyncClient(app=app_with_search_mocks, base_url="http://test") as client:
        response = await client.get("/search?query=test&size=0")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_search_invalid_size_over_100_400(app_with_search_mocks):
    """size=101 -> 400."""
    async with AsyncClient(app=app_with_search_mocks, base_url="http://test") as client:
        response = await client.get("/search?query=test&size=101")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_search_failure_503(app_with_search_mocks):
    """When search_service raises (e.g. connection error) -> 503."""
    app_with_search_mocks.state.search_service.search_foods = AsyncMock(
        side_effect=Exception("connection refused")
    )
    async with AsyncClient(app=app_with_search_mocks, base_url="http://test") as client:
        response = await client.get("/search?query=test")
    assert response.status_code == 503


# --- Demo CRUD (mocked food_service / food_nutrient_service) ---


@pytest.mark.asyncio
async def test_demo_add_food_200(app_with_demo_mocks):
    """POST /demo/foods -> 200, ok True, fdc_id."""
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.post(
            "/demo/foods",
            json={"fdc_id": 999, "data_type": "foundation_food", "description": "Test"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True
    assert data.get("fdc_id") == 999


@pytest.mark.asyncio
async def test_demo_update_food_200(app_with_demo_mocks):
    """PUT /demo/foods/{fdc_id} -> 200 when updated."""
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.put(
            "/demo/foods/1",
            json={"description": "Updated"},
        )
    assert response.status_code == 200
    assert response.json().get("ok") is True
    assert response.json().get("fdc_id") == 1


@pytest.mark.asyncio
async def test_demo_update_food_404(app_with_demo_mocks):
    """PUT /demo/foods/{fdc_id} -> 404 when not found."""
    app_with_demo_mocks.state.food_service.update_food = AsyncMock(return_value=False)
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.put("/demo/foods/999", json={})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_demo_delete_food_200(app_with_demo_mocks):
    """DELETE /demo/foods/{fdc_id} -> 200 when deleted."""
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.delete("/demo/foods/1")
    assert response.status_code == 200
    assert response.json().get("ok") is True


@pytest.mark.asyncio
async def test_demo_delete_food_404(app_with_demo_mocks):
    """DELETE /demo/foods/{fdc_id} -> 404 when not found."""
    app_with_demo_mocks.state.food_service.delete_food = AsyncMock(return_value=False)
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.delete("/demo/foods/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_demo_add_food_nutrient_200(app_with_demo_mocks):
    """POST /demo/food-nutrients -> 200, ok True, id, fdc_id."""
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.post(
            "/demo/food-nutrients",
            json={"fdc_id": 1, "nutrient_id": 1008, "amount": 100.0},
        )
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True
    assert data.get("id") == 1
    assert data.get("fdc_id") == 1


@pytest.mark.asyncio
async def test_demo_update_food_nutrient_200(app_with_demo_mocks):
    """PUT /demo/food-nutrients/{id} -> 200 when updated."""
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.put(
            "/demo/food-nutrients/1",
            json={"amount": 50.0},
        )
    assert response.status_code == 200
    assert response.json().get("ok") is True


@pytest.mark.asyncio
async def test_demo_update_food_nutrient_404(app_with_demo_mocks):
    """PUT /demo/food-nutrients/{id} -> 404 when not found."""
    app_with_demo_mocks.state.food_nutrient_service.update_food_nutrient = AsyncMock(
        return_value=False
    )
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.put("/demo/food-nutrients/999", json={})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_demo_delete_food_nutrient_200(app_with_demo_mocks):
    """DELETE /demo/food-nutrients/{id} -> 200 when deleted."""
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.delete("/demo/food-nutrients/1")
    assert response.status_code == 200
    assert response.json().get("ok") is True


@pytest.mark.asyncio
async def test_demo_delete_food_nutrient_404(app_with_demo_mocks):
    """DELETE /demo/food-nutrients/{id} -> 404 when not found."""
    app_with_demo_mocks.state.food_nutrient_service.delete_food_nutrient = AsyncMock(
        return_value=False
    )
    async with AsyncClient(app=app_with_demo_mocks, base_url="http://test") as client:
        response = await client.delete("/demo/food-nutrients/999")
    assert response.status_code == 404