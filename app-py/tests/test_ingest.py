"""
Ingest: NutrientMappingService, FoodIndexingService (doc building, upsert/delete logic).

Unit tests for ingest-related logic. CsvLoadService not tested (stdlib/thin glue).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.domain import FoodNutrient, NutrientAmount
from src.services.nutrient_mapping_service import NutrientMappingService
from src.services.food_indexing_service import FoodIndexingService


# --- NutrientMappingService ---


def test_map_usda_all_four_nutrients():
    """Positive: all four USDA IDs map to correct NutrientAmounts."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients(
        {1008: 200.0, 1003: 10.0, 2039: 5.0, 1085: 3.0}
    )
    assert len(result) == 4
    types = {na.type for na in result}
    assert types == {FoodNutrient.CALORIES, FoodNutrient.PROTEIN, FoodNutrient.CARBS, FoodNutrient.FAT}
    by_type = {na.type: na.amount for na in result}
    assert by_type[FoodNutrient.CALORIES] == 200.0
    assert by_type[FoodNutrient.PROTEIN] == 10.0
    assert by_type[FoodNutrient.CARBS] == 5.0
    assert by_type[FoodNutrient.FAT] == 3.0


def test_map_usda_partial_subset():
    """Positive: only a subset of mapped IDs present."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: 100.0, 1003: 5.0})
    assert len(result) == 2
    by_type = {na.type: na.amount for na in result}
    assert by_type[FoodNutrient.CALORIES] == 100.0
    assert by_type[FoodNutrient.PROTEIN] == 5.0


def test_map_usda_empty_dict():
    """Positive: empty dict returns empty list."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({})
    assert result == []


def test_map_usda_single_nutrient():
    """Positive: single nutrient (fat)."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1085: 12.5})
    assert len(result) == 1
    assert result[0].type == FoodNutrient.FAT
    assert result[0].amount == 12.5


def test_map_usda_zero_amount():
    """Positive: zero amount is valid."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: 0.0})
    assert len(result) == 1
    assert result[0].amount == 0.0


def test_map_usda_custom_mapping_override():
    """Positive: custom mapping param is used."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients(
        {999: 50.0}, mapping={999: "calories"}
    )
    assert len(result) == 1
    assert result[0].type == FoodNutrient.CALORIES
    assert result[0].amount == 50.0


# --- NutrientMappingService: negative ---


def test_map_usda_unknown_nutrient_id_omitted():
    """Negative: nutrient_id not in mapping is omitted."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({9999: 1.0})
    assert result == []


def test_map_usda_unknown_and_known_mixed():
    """Negative: mix of known and unknown IDs; only known in result."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: 1.0, 9999: 2.0})
    assert len(result) == 1
    assert result[0].type == FoodNutrient.CALORIES
    assert result[0].amount == 1.0


def test_map_usda_invalid_amount_non_numeric_skipped():
    """Negative: non-numeric amount is skipped, no crash."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: "bad"})
    assert result == []


def test_map_usda_invalid_amount_none_skipped():
    """Negative: None amount is skipped."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: None})
    assert result == []


def test_map_usda_invalid_amount_list_skipped():
    """Negative: amount as list causes skip (float() raises)."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: [1, 2]})
    assert result == []


def test_map_usda_invalid_amount_dict_skipped():
    """Negative: amount as dict causes skip."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: {"x": 1}})
    assert result == []


def test_map_usda_invalid_api_key_in_mapping_skipped():
    """Negative: mapping has invalid enum value for key -> skip that entry."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients(
        {1008: 1.0}, mapping={1008: "invalid_key"}
    )
    assert result == []


def test_map_usda_empty_mapping_override():
    """Negative: custom mapping empty -> all omitted."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: 1.0}, mapping={})
    assert result == []


def test_map_usda_string_key_not_matched():
    """Negative: usda_amounts has string key (e.g. '1008'); default mapping has int keys -> omitted."""
    svc = NutrientMappingService()
    # Default USDA_NUTRIENT_MAPPING uses int keys; so 1008 (int) is in mapping, "1008" (str) is not.
    result = svc.map_usda_to_food_nutrients({"1008": 1.0})
    assert result == []


def test_map_usda_one_valid_one_invalid_amount():
    """Negative: two nutrients, one valid one invalid amount -> only valid in result."""
    svc = NutrientMappingService()
    result = svc.map_usda_to_food_nutrients({1008: 10.0, 1003: "nope"})
    assert len(result) == 1
    assert result[0].type == FoodNutrient.CALORIES
    assert result[0].amount == 10.0


def test_map_usda_none_input_raises():
    """Negative: usda_amounts None -> raises (no guard in service)."""
    svc = NutrientMappingService()
    with pytest.raises((TypeError, AttributeError)):
        svc.map_usda_to_food_nutrients(None)


# --- FoodIndexingService: reindex_all ---


@pytest.mark.asyncio
async def test_reindex_all_one_valid_batch_builds_doc_and_calls_bulk_index():
    """Positive: one valid batch -> one doc built, bulk_index_foods called once."""
    food_repo = MagicMock()
    food_repo.list_foundation_foods_batch = AsyncMock(
        side_effect=[
            [{"fdc_id": 1, "description": "Food A", "data_type": "foundation_food"}],
            [],
        ]
    )
    food_nutrient_repo = MagicMock()
    food_nutrient_repo.get_usda_nutrient_amounts_for_foods = AsyncMock(
        return_value={1: {1008: 100.0}}
    )
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.bulk_index_foods = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.reindex_all()

    search_index.bulk_index_foods.assert_called_once()
    call_args = search_index.bulk_index_foods.call_args[0][0]
    assert len(call_args) == 1
    doc = call_args[0]
    assert doc["fdc_id"] == 1
    assert doc["name"] == "Food A"
    assert doc["nutrients"] == [{"type": "calories", "amount": 100.0}]


@pytest.mark.asyncio
async def test_reindex_all_empty_batch_no_bulk_index():
    """Positive: empty batch -> no bulk_index_foods call."""
    food_repo = MagicMock()
    food_repo.list_foundation_foods_batch = AsyncMock(return_value=[])
    food_nutrient_repo = MagicMock()
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.bulk_index_foods = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.reindex_all()

    search_index.bulk_index_foods.assert_not_called()


@pytest.mark.asyncio
async def test_reindex_all_row_invalid_fdc_id_skipped():
    """Negative: row without valid fdc_id is skipped, no crash."""
    food_repo = MagicMock()
    food_repo.list_foundation_foods_batch = AsyncMock(
        side_effect=[
            [{"description": "No fdc_id", "data_type": "foundation_food"}],
            [],
        ]
    )
    food_nutrient_repo = MagicMock()
    food_nutrient_repo.get_usda_nutrient_amounts_for_foods = AsyncMock(return_value={})
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.bulk_index_foods = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.reindex_all()

    search_index.bulk_index_foods.assert_not_called()


@pytest.mark.asyncio
async def test_reindex_all_row_fdc_id_not_int_skipped():
    """Negative: fdc_id as non-int (e.g. string) is skipped."""
    food_repo = MagicMock()
    food_repo.list_foundation_foods_batch = AsyncMock(
        side_effect=[
            [{"fdc_id": "not_an_int", "description": "X", "data_type": "foundation_food"}],
            [],
        ]
    )
    food_nutrient_repo = MagicMock()
    food_nutrient_repo.get_usda_nutrient_amounts_for_foods = AsyncMock(return_value={})
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.bulk_index_foods = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.reindex_all()

    search_index.bulk_index_foods.assert_not_called()


@pytest.mark.asyncio
async def test_reindex_all_missing_description_empty_name():
    """Negative/edge: row without description -> doc has name ''."""
    food_repo = MagicMock()
    food_repo.list_foundation_foods_batch = AsyncMock(
        side_effect=[
            [{"fdc_id": 1, "data_type": "foundation_food"}],
            [],
        ]
    )
    food_nutrient_repo = MagicMock()
    food_nutrient_repo.get_usda_nutrient_amounts_for_foods = AsyncMock(return_value={1: {}})
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.bulk_index_foods = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.reindex_all()

    search_index.bulk_index_foods.assert_called_once()
    doc = search_index.bulk_index_foods.call_args[0][0][0]
    assert doc["name"] == ""


@pytest.mark.asyncio
async def test_reindex_all_foundation_food_no_nutrients_empty_list():
    """Positive: foundation food with no nutrient rows -> doc with nutrients []."""
    food_repo = MagicMock()
    food_repo.list_foundation_foods_batch = AsyncMock(
        side_effect=[
            [{"fdc_id": 1, "description": "Food", "data_type": "foundation_food"}],
            [],
        ]
    )
    food_nutrient_repo = MagicMock()
    food_nutrient_repo.get_usda_nutrient_amounts_for_foods = AsyncMock(return_value={1: {}})
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.bulk_index_foods = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.reindex_all()

    doc = search_index.bulk_index_foods.call_args[0][0][0]
    assert doc["nutrients"] == []


@pytest.mark.asyncio
async def test_reindex_all_missing_fdc_id_in_nutrient_amounts_uses_empty():
    """Negative: get_usda_nutrient_amounts_for_foods omits fdc_id -> .get(fdc_id, {}) gives {}."""
    food_repo = MagicMock()
    food_repo.list_foundation_foods_batch = AsyncMock(
        side_effect=[
            [{"fdc_id": 1, "description": "Food", "data_type": "foundation_food"}],
            [],
        ]
    )
    food_nutrient_repo = MagicMock()
    food_nutrient_repo.get_usda_nutrient_amounts_for_foods = AsyncMock(return_value={})
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.bulk_index_foods = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.reindex_all()

    doc = search_index.bulk_index_foods.call_args[0][0][0]
    assert doc["nutrients"] == []


# --- FoodIndexingService: upsert_food_by_fdc_id ---


@pytest.mark.asyncio
async def test_upsert_food_missing_calls_delete_not_index():
    """Negative: get_food_by_fdc_id returns None -> delete_food called, index_food not called."""
    food_repo = MagicMock()
    food_repo.get_food_by_fdc_id = AsyncMock(return_value=None)
    food_nutrient_repo = MagicMock()
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.delete_food = AsyncMock()
    search_index.index_food = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.upsert_food_by_fdc_id(99)

    search_index.delete_food.assert_called_once_with(99)
    search_index.index_food.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_food_not_foundation_calls_delete_not_index():
    """Negative: data_type != foundation_food -> delete_food called."""
    food_repo = MagicMock()
    food_repo.get_food_by_fdc_id = AsyncMock(
        return_value={"fdc_id": 1, "description": "X", "data_type": "survey_food"}
    )
    food_nutrient_repo = MagicMock()
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.delete_food = AsyncMock()
    search_index.index_food = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.upsert_food_by_fdc_id(1)

    search_index.delete_food.assert_called_once_with(1)
    search_index.index_food.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_food_data_type_empty_string_calls_delete():
    """Negative: data_type '' or whitespace -> not foundation_food, delete called."""
    food_repo = MagicMock()
    food_repo.get_food_by_fdc_id = AsyncMock(
        return_value={"fdc_id": 1, "description": "X", "data_type": "  "}
    )
    food_nutrient_repo = MagicMock()
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.delete_food = AsyncMock()
    search_index.index_food = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.upsert_food_by_fdc_id(1)

    search_index.delete_food.assert_called_once_with(1)
    search_index.index_food.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_food_data_type_none_calls_delete():
    """Negative: data_type None -> treated as not foundation_food."""
    food_repo = MagicMock()
    food_repo.get_food_by_fdc_id = AsyncMock(
        return_value={"fdc_id": 1, "description": "X"}
    )
    food_nutrient_repo = MagicMock()
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.delete_food = AsyncMock()
    search_index.index_food = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.upsert_food_by_fdc_id(1)

    search_index.delete_food.assert_called_once_with(1)
    search_index.index_food.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_food_foundation_with_nutrients_calls_index():
    """Positive: foundation_food with nutrients -> index_food called with correct doc."""
    food_repo = MagicMock()
    food_repo.get_food_by_fdc_id = AsyncMock(
        return_value={"fdc_id": 1, "description": "Chicken", "data_type": "foundation_food"}
    )
    food_nutrient_repo = MagicMock()
    food_nutrient_repo.get_usda_nutrient_amounts_for_food = AsyncMock(
        return_value={1008: 50.0, 1003: 10.0}
    )
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.delete_food = AsyncMock()
    search_index.index_food = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.upsert_food_by_fdc_id(1)

    search_index.index_food.assert_called_once()
    call_args = search_index.index_food.call_args[0]
    assert call_args[0] == 1
    doc = call_args[1]
    assert doc["fdc_id"] == 1
    assert doc["name"] == "Chicken"
    assert len(doc["nutrients"]) == 2


@pytest.mark.asyncio
async def test_upsert_food_foundation_no_nutrients_calls_index_with_empty_nutrients():
    """Positive: foundation_food with no nutrients -> index_food with nutrients []."""
    food_repo = MagicMock()
    food_repo.get_food_by_fdc_id = AsyncMock(
        return_value={"fdc_id": 1, "description": "Food", "data_type": "foundation_food"}
    )
    food_nutrient_repo = MagicMock()
    food_nutrient_repo.get_usda_nutrient_amounts_for_food = AsyncMock(return_value={})
    search_index = MagicMock()
    search_index.ensure_index = AsyncMock()
    search_index.index_food = AsyncMock()

    svc = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    await svc.upsert_food_by_fdc_id(1)

    doc = search_index.index_food.call_args[0][1]
    assert doc["nutrients"] == []
