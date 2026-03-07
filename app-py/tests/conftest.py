"""
Shared pytest fixtures for tests.

Fixtures here are auto-discovered by pytest; any test in tests/ can use them by name as an argument.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.main import app
from src.listener.concrete_listeners.food_index_listener import FoodIndexNotifyListener


# --- App (for API tests) ---


@pytest.fixture
def app_with_search_mocks():
    """FastAPI app with search_service and food_search_response_service set to mocks (for /search tests)."""
    mock_search = AsyncMock()
    mock_search.search_foods = AsyncMock(return_value=[])
    mock_response_service = MagicMock()
    mock_response_service.from_domain_foods = MagicMock(return_value={"foods": []})
    app.state.search_service = mock_search
    app.state.food_search_response_service = mock_response_service
    return app


@pytest.fixture
def app_with_demo_mocks():
    """FastAPI app with food_service and food_nutrient_service set to mocks (for demo CRUD tests)."""
    mock_food = AsyncMock()
    mock_food.add_food = AsyncMock()
    mock_food.update_food = AsyncMock(return_value=True)
    mock_food.delete_food = AsyncMock(return_value=True)
    mock_fn = AsyncMock()
    mock_fn.add_food_nutrient = AsyncMock(return_value=1)
    mock_fn.update_food_nutrient = AsyncMock(return_value=True)
    mock_fn.delete_food_nutrient = AsyncMock(return_value=True)
    app.state.food_service = mock_food
    app.state.food_nutrient_service = mock_fn
    return app


# --- Listener (for test_listener) ---


@pytest.fixture
def mock_indexing():
    """Mock FoodIndexingService with async delete_food_from_index and upsert_food_by_fdc_id."""
    m = MagicMock()
    m.delete_food_from_index = AsyncMock()
    m.upsert_food_by_fdc_id = AsyncMock()
    return m


@pytest.fixture
def mock_listen_conn():
    """Minimal mock for asyncpg connection (only needed for listener constructor)."""
    return MagicMock()


@pytest.fixture
def listener(mock_indexing, mock_listen_conn):
    """FoodIndexNotifyListener with mocked indexing and conn."""
    return FoodIndexNotifyListener(mock_indexing, mock_listen_conn)
