"""
Listener: payload parsing (_parse_payload), process_one routing (mock indexing service).

Unit tests for NOTIFY listener logic.
"""

import pytest

from src.listener.concrete_listeners.food_index_listener import _parse_payload


# --- _parse_payload ---


def test_parse_payload_valid_foods_delete():
    """Valid payload foods DELETE returns (table, op, fdc_id)."""
    result = _parse_payload('{"table":"foods","op":"DELETE","fdc_id":123}')
    assert result == ("foods", "DELETE", 123)


def test_parse_payload_valid_food_nutrients_insert():
    """Valid payload food_nutrients INSERT returns (table, op, fdc_id)."""
    result = _parse_payload('{"table":"food_nutrients","op":"INSERT","fdc_id":456}')
    assert result == ("food_nutrients", "INSERT", 456)


def test_parse_payload_valid_with_whitespace():
    """Table/op with surrounding whitespace are stripped."""
    result = _parse_payload('{"table":"  foods  ","op":"  DELETE  ","fdc_id":1}')
    assert result == ("foods", "DELETE", 1)


def test_parse_payload_invalid_empty_object():
    """Empty object -> None."""
    assert _parse_payload("{}") is None


def test_parse_payload_invalid_missing_table():
    """Missing table -> None."""
    assert _parse_payload('{"op":"DELETE","fdc_id":123}') is None


def test_parse_payload_invalid_missing_op():
    """Missing op -> None."""
    assert _parse_payload('{"table":"foods","fdc_id":123}') is None


def test_parse_payload_invalid_missing_fdc_id():
    """Missing fdc_id -> None."""
    assert _parse_payload('{"table":"foods","op":"DELETE"}') is None


def test_parse_payload_invalid_fdc_id_null():
    """fdc_id null -> None."""
    assert _parse_payload('{"table":"foods","op":"DELETE","fdc_id":null}') is None


def test_parse_payload_invalid_fdc_id_non_numeric():
    """fdc_id that cannot convert to int (e.g. string 'abc', or boolean) -> None or invalid."""
    # String "abc" cannot convert to int -> None
    assert _parse_payload('{"table":"foods","op":"DELETE","fdc_id":"abc"}') is None
    # JSON true -> int(True) is 1 in Python; so we test non-numeric string only for strict None
    assert _parse_payload('{"table":"foods","op":"DELETE","fdc_id":"x"}') is None


def test_parse_payload_invalid_not_json():
    """Malformed JSON -> None."""
    assert _parse_payload("not json") is None
    assert _parse_payload("{") is None
    assert _parse_payload('{"table":') is None


def test_parse_payload_invalid_empty_table():
    """table empty string -> None (not table is falsy)."""
    assert _parse_payload('{"table":"","op":"DELETE","fdc_id":1}') is None


def test_parse_payload_invalid_empty_op():
    """op empty string -> None."""
    assert _parse_payload('{"table":"foods","op":"","fdc_id":1}') is None


# --- FoodIndexNotifyListener._process_one (mock indexing service; fixtures in conftest) ---


@pytest.mark.asyncio
async def test_process_one_foods_delete_calls_delete_not_upsert(listener, mock_indexing):
    """table=foods, op=DELETE -> delete_food_from_index called, upsert not called."""
    ok = await listener._process_one('{"table":"foods","op":"DELETE","fdc_id":99}', 0)
    assert ok is True
    mock_indexing.delete_food_from_index.assert_called_once_with(99)
    mock_indexing.upsert_food_by_fdc_id.assert_not_called()


@pytest.mark.asyncio
async def test_process_one_foods_insert_calls_upsert_not_delete(listener, mock_indexing):
    """table=foods, op=INSERT -> upsert_food_by_fdc_id called."""
    ok = await listener._process_one('{"table":"foods","op":"INSERT","fdc_id":1}', 0)
    assert ok is True
    mock_indexing.upsert_food_by_fdc_id.assert_called_once_with(1)
    mock_indexing.delete_food_from_index.assert_not_called()


@pytest.mark.asyncio
async def test_process_one_foods_update_calls_upsert(listener, mock_indexing):
    """table=foods, op=UPDATE -> upsert_food_by_fdc_id called."""
    ok = await listener._process_one('{"table":"foods","op":"UPDATE","fdc_id":2}', 0)
    assert ok is True
    mock_indexing.upsert_food_by_fdc_id.assert_called_once_with(2)
    mock_indexing.delete_food_from_index.assert_not_called()


@pytest.mark.asyncio
async def test_process_one_food_nutrients_delete_calls_upsert(listener, mock_indexing):
    """table=food_nutrients, op=DELETE -> upsert_food_by_fdc_id (reindex food with updated nutrients)."""
    ok = await listener._process_one('{"table":"food_nutrients","op":"DELETE","fdc_id":3}', 0)
    assert ok is True
    mock_indexing.upsert_food_by_fdc_id.assert_called_once_with(3)
    mock_indexing.delete_food_from_index.assert_not_called()


@pytest.mark.asyncio
async def test_process_one_food_nutrients_insert_calls_upsert(listener, mock_indexing):
    """table=food_nutrients, op=INSERT -> upsert_food_by_fdc_id called."""
    ok = await listener._process_one('{"table":"food_nutrients","op":"INSERT","fdc_id":4}', 0)
    assert ok is True
    mock_indexing.upsert_food_by_fdc_id.assert_called_once_with(4)
    mock_indexing.delete_food_from_index.assert_not_called()


@pytest.mark.asyncio
async def test_process_one_invalid_payload_neither_called(listener, mock_indexing):
    """Invalid payload -> neither delete nor upsert called, returns True (don't retry)."""
    ok = await listener._process_one("{}", 0)
    assert ok is True
    mock_indexing.delete_food_from_index.assert_not_called()
    mock_indexing.upsert_food_by_fdc_id.assert_not_called()


@pytest.mark.asyncio
async def test_process_one_failure_returns_false(listener, mock_indexing):
    """When indexing raises -> returns False (so caller can retry)."""
    mock_indexing.upsert_food_by_fdc_id.side_effect = RuntimeError("ES down")
    ok = await listener._process_one('{"table":"foods","op":"INSERT","fdc_id":1}', 0)
    assert ok is False
    mock_indexing.upsert_food_by_fdc_id.assert_called_once_with(1)
