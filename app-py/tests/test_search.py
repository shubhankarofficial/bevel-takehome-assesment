"""
Search: query sanitizer, search strategy (mock ES), SearchService hits→Food, FoodSearchResponseService.

Unit tests for search-related logic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.config import FOOD_INDEX_NAME
from src.domain import Food, FoodNutrient, NutrientAmount
from src.search.concrete_search_strategies.phrase_prefix_fuzzy_search_strategy import (
    PhrasePrefixFuzzySearchStrategy,
)
from src.search.services.query_sanitizer import sanitize_search_query
from src.services.food_search_response_service import FoodSearchResponseService
from src.services.search_service import SearchService


# --- sanitize_search_query ---


def test_sanitize_normal_text():
    """Normal text unchanged (aside from trim)."""
    assert sanitize_search_query("chicken") == "chicken"


def test_sanitize_trim_whitespace():
    """Leading/trailing whitespace stripped."""
    assert sanitize_search_query("  chicken breast  ") == "chicken breast"


def test_sanitize_allowed_chars_kept():
    """Comma, hyphen, period, %, parentheses, apostrophe kept."""
    assert sanitize_search_query("milk 2%, pan-fried (classic)") == "milk 2%, pan-fried (classic)"
    assert sanitize_search_query("don't") == "don't"


def test_sanitize_word_internal_hyphen():
    """Word-internal hyphen kept."""
    assert sanitize_search_query("pan-fried") == "pan-fried"


def test_sanitize_collapse_spaces():
    """Multiple spaces collapsed to one."""
    assert sanitize_search_query("chicken   breast") == "chicken breast"


def test_sanitize_empty_string():
    """Empty string -> ''."""
    assert sanitize_search_query("") == ""


def test_sanitize_whitespace_only():
    """Whitespace only -> ''."""
    assert sanitize_search_query("   ") == ""


def test_sanitize_none_returns_empty():
    """None -> ''."""
    assert sanitize_search_query(None) == ""


def test_sanitize_not_string_returns_empty():
    """Non-string (e.g. int) -> ''."""
    assert sanitize_search_query(123) == ""


def test_sanitize_plus_replaced():
    """Plus sign replaced with space."""
    assert sanitize_search_query("chicken+breast") == "chicken breast"


def test_sanitize_semicolon_replaced():
    """Semicolon and other reserved chars replaced."""
    assert sanitize_search_query("a;b") == "a b"
    assert ";" not in sanitize_search_query("a;b")


def test_sanitize_standalone_hyphen():
    """Space-hyphen-space -> space."""
    assert sanitize_search_query("chicken - breast") == "chicken breast"


def test_sanitize_leading_hyphen():
    """Leading hyphen removed."""
    assert sanitize_search_query("-chicken") == "chicken"


def test_sanitize_trailing_hyphen():
    """Trailing hyphen removed."""
    assert sanitize_search_query("chicken-") == "chicken"


def test_sanitize_all_special_becomes_empty():
    """Query that is only special chars -> ''."""
    result = sanitize_search_query("++;;***")
    assert result == "" or result.strip() == ""


def test_sanitize_percent_kept():
    """Percent kept (allowed)."""
    assert sanitize_search_query("milk 3%") == "milk 3%"


# --- PhrasePrefixFuzzySearchStrategy ---


@pytest.mark.asyncio
async def test_strategy_empty_query_returns_empty_no_es_call():
    """Empty query or whitespace-only -> [], no es.search call."""
    mock_es = MagicMock()
    mock_es.search = AsyncMock()
    strategy = PhrasePrefixFuzzySearchStrategy(mock_es)

    result_empty = await strategy.search("")
    result_whitespace = await strategy.search("   ")

    assert result_empty == []
    assert result_whitespace == []
    mock_es.search.assert_not_called()


@pytest.mark.asyncio
async def test_strategy_query_sanitizes_to_empty_returns_empty_no_es_call():
    """Query that becomes empty after sanitize (e.g. all special chars) -> [], no es.search."""
    mock_es = MagicMock()
    mock_es.search = AsyncMock()
    strategy = PhrasePrefixFuzzySearchStrategy(mock_es)

    result = await strategy.search("+++;;;***")

    assert result == []
    mock_es.search.assert_not_called()


@pytest.mark.asyncio
async def test_strategy_valid_query_calls_es_with_correct_params():
    """Valid query -> es.search called once with index, size, bool query, sort."""
    mock_es = MagicMock()
    mock_es.search = AsyncMock(return_value={"hits": {"hits": []}})
    strategy = PhrasePrefixFuzzySearchStrategy(mock_es, index_name=FOOD_INDEX_NAME)

    await strategy.search("chicken", size=10)

    mock_es.search.assert_called_once()
    call_kw = mock_es.search.call_args[1]
    assert call_kw["index"] == FOOD_INDEX_NAME
    assert call_kw["size"] == 10
    query = call_kw["query"]
    assert "bool" in query
    assert "should" in query["bool"]
    should = query["bool"]["should"]
    assert len(should) == 3
    assert query["bool"]["minimum_should_match"] == 1
    sort = call_kw["sort"]
    assert sort == [
        {"_score": {"order": "desc"}},
        {"name.keyword": {"order": "asc"}},
    ]


@pytest.mark.asyncio
async def test_strategy_default_size_20():
    """Default size when not passed -> es.search called with size=20."""
    mock_es = MagicMock()
    mock_es.search = AsyncMock(return_value={"hits": {"hits": []}})
    strategy = PhrasePrefixFuzzySearchStrategy(mock_es)

    await strategy.search("milk")

    mock_es.search.assert_called_once()
    assert mock_es.search.call_args[1]["size"] == 20


@pytest.mark.asyncio
async def test_strategy_custom_size():
    """Custom size -> es.search called with that size."""
    mock_es = MagicMock()
    mock_es.search = AsyncMock(return_value={"hits": {"hits": []}})
    strategy = PhrasePrefixFuzzySearchStrategy(mock_es)

    await strategy.search("milk", size=5)

    mock_es.search.assert_called_once()
    assert mock_es.search.call_args[1]["size"] == 5


@pytest.mark.asyncio
async def test_strategy_sanitized_query_passed_to_es():
    """Query with special chars is sanitized before being sent to ES."""
    mock_es = MagicMock()
    mock_es.search = AsyncMock(return_value={"hits": {"hits": []}})
    strategy = PhrasePrefixFuzzySearchStrategy(mock_es)

    await strategy.search("chicken+breast")

    mock_es.search.assert_called_once()
    query = mock_es.search.call_args[1]["query"]
    # Sanitizer replaces + with space -> "chicken breast"
    phrase = query["bool"]["should"][0]["match_phrase"]["name"]["query"]
    assert phrase == "chicken breast"


@pytest.mark.asyncio
async def test_strategy_returns_hits_from_response():
    """Strategy returns hits from response.hits.hits."""
    mock_es = MagicMock()
    hits = [
        {"_source": {"name": "Chicken", "nutrients": []}},
        {"_source": {"name": "Chicken breast", "nutrients": []}},
    ]
    mock_es.search = AsyncMock(return_value={"hits": {"hits": hits}})
    strategy = PhrasePrefixFuzzySearchStrategy(mock_es)

    result = await strategy.search("chicken")

    assert result == hits
    assert len(result) == 2
    assert result[0]["_source"]["name"] == "Chicken"


# --- SearchService (hits -> Food) ---


@pytest.mark.asyncio
async def test_search_service_one_hit_full_source():
    """One hit with name and nutrients -> one Food with correct name and NutrientAmounts."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(
        return_value=[
            {
                "_source": {
                    "name": "Chicken",
                    "nutrients": [{"type": "calories", "amount": 100.0}],
                }
            }
        ]
    )
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("chicken")
    assert len(foods) == 1
    assert foods[0].name == "Chicken"
    assert len(foods[0].nutrients) == 1
    assert foods[0].nutrients[0].type == FoodNutrient.CALORIES
    assert foods[0].nutrients[0].amount == 100.0


@pytest.mark.asyncio
async def test_search_service_empty_hits():
    """Empty hits -> empty list."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(return_value=[])
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("x")
    assert foods == []


@pytest.mark.asyncio
async def test_search_service_multiple_hits():
    """Multiple hits -> multiple Food."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(
        return_value=[
            {"_source": {"name": "A", "nutrients": []}},
            {"_source": {"name": "B", "nutrients": []}},
        ]
    )
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("x")
    assert len(foods) == 2
    assert foods[0].name == "A"
    assert foods[1].name == "B"


@pytest.mark.asyncio
async def test_search_service_hit_missing_source():
    """Hit without _source -> Food with name '', nutrients []."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(return_value=[{}])
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("x")
    assert len(foods) == 1
    assert foods[0].name == ""
    assert foods[0].nutrients == []


@pytest.mark.asyncio
async def test_search_service_nutrient_missing_type_skipped():
    """Nutrient with no type -> skipped."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(
        return_value=[
            {"_source": {"name": "X", "nutrients": [{"amount": 10.0}]}},
        ]
    )
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("x")
    assert foods[0].nutrients == []


@pytest.mark.asyncio
async def test_search_service_nutrient_missing_amount_skipped():
    """Nutrient with no amount -> skipped."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(
        return_value=[
            {"_source": {"name": "X", "nutrients": [{"type": "calories"}]}},
        ]
    )
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("x")
    assert foods[0].nutrients == []


@pytest.mark.asyncio
async def test_search_service_invalid_nutrient_type_skipped():
    """Nutrient with invalid type (not in enum) -> skipped."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(
        return_value=[
            {"_source": {"name": "X", "nutrients": [{"type": "invalid", "amount": 1.0}]}},
        ]
    )
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("x")
    assert foods[0].nutrients == []


@pytest.mark.asyncio
async def test_search_service_mix_valid_invalid_nutrients():
    """One valid and one invalid nutrient in hit -> only valid in Food."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(
        return_value=[
            {
                "_source": {
                    "name": "X",
                    "nutrients": [
                        {"type": "calories", "amount": 50.0},
                        {"type": "bad", "amount": 1.0},
                        {"amount": 2.0},
                    ],
                }
            }
        ]
    )
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("x")
    assert len(foods[0].nutrients) == 1
    assert foods[0].nutrients[0].type == FoodNutrient.CALORIES
    assert foods[0].nutrients[0].amount == 50.0


@pytest.mark.asyncio
async def test_search_service_multiple_valid_nutrients():
    """Hit with all four nutrient types -> Food has all four."""
    mock_strategy = MagicMock()
    mock_strategy.search = AsyncMock(
        return_value=[
            {
                "_source": {
                    "name": "Food",
                    "nutrients": [
                        {"type": "calories", "amount": 100.0},
                        {"type": "protein", "amount": 10.0},
                        {"type": "carbs", "amount": 5.0},
                        {"type": "fat", "amount": 3.0},
                    ],
                }
            }
        ]
    )
    svc = SearchService(mock_strategy)
    foods = await svc.search_foods("x")
    assert len(foods[0].nutrients) == 4
    types = {na.type for na in foods[0].nutrients}
    assert types == {FoodNutrient.CALORIES, FoodNutrient.PROTEIN, FoodNutrient.CARBS, FoodNutrient.FAT}


# --- FoodSearchResponseService ---


def test_response_service_empty_list():
    """Empty foods list -> FoodSearchResponse with foods=[]."""
    svc = FoodSearchResponseService()
    result = svc.from_domain_foods([])
    assert result.foods == []


def test_response_service_one_food():
    """One Food -> one FoodResponse with correct name and nutrients."""
    svc = FoodSearchResponseService()
    food = Food(name="Chicken", nutrients=[NutrientAmount(type=FoodNutrient.CALORIES, amount=100.0)])
    result = svc.from_domain_foods([food])
    assert len(result.foods) == 1
    assert result.foods[0].name == "Chicken"
    assert len(result.foods[0].nutrients) == 1
    assert result.foods[0].nutrients[0].type == FoodNutrient.CALORIES
    assert result.foods[0].nutrients[0].amount == 100.0


def test_response_service_multiple_foods():
    """Multiple Food -> correct number and content in response."""
    svc = FoodSearchResponseService()
    foods = [
        Food(name="A", nutrients=[]),
        Food(name="B", nutrients=[NutrientAmount(type=FoodNutrient.PROTEIN, amount=5.0)]),
    ]
    result = svc.from_domain_foods(foods)
    assert len(result.foods) == 2
    assert result.foods[0].name == "A"
    assert result.foods[0].nutrients == []
    assert result.foods[1].name == "B"
    assert result.foods[1].nutrients[0].type == FoodNutrient.PROTEIN
    assert result.foods[1].nutrients[0].amount == 5.0


def test_response_service_food_empty_nutrients():
    """Food with empty nutrients -> FoodResponse with nutrients=[]."""
    svc = FoodSearchResponseService()
    food = Food(name="X", nutrients=[])
    result = svc.from_domain_foods([food])
    assert result.foods[0].nutrients == []


def test_response_service_serialization_shape():
    """Response has correct shape for API (Pydantic model_dump)."""
    svc = FoodSearchResponseService()
    food = Food(
        name="Test",
        nutrients=[
            NutrientAmount(type=FoodNutrient.CALORIES, amount=200.0),
            NutrientAmount(type=FoodNutrient.FAT, amount=10.0),
        ],
    )
    result = svc.from_domain_foods([food])
    dumped = result.model_dump()
    assert "foods" in dumped
    assert len(dumped["foods"]) == 1
    assert dumped["foods"][0]["name"] == "Test"
    assert len(dumped["foods"][0]["nutrients"]) == 2
    assert dumped["foods"][0]["nutrients"][0]["type"] == "calories"
    assert dumped["foods"][0]["nutrients"][0]["amount"] == 200.0
