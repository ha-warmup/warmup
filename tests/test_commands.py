"""Tests for the Warmup4IE command methods."""

from unittest.mock import patch

import pytest

from .test_login import _make_response, _new_client_without_connect, warmup4ie

PATCH_POST = "warmup4ie_under_test.requests.post"


def _client():
    client = _new_client_without_connect()
    client._warmup_access_token = "tok-123"
    client.update_all_devices = lambda: pytest.fail("commands must not refresh")
    return client


@patch(PATCH_POST)
def test_set_new_temperature_sends_fixed_programme(mock_post):
    """A fixed temperature is sent in tenths of a degree, with no refresh."""
    mock_post.return_value = _make_response(200, {"status": {"result": "success"}})

    assert _client().set_new_temperature(42, 21.5) is None

    request = mock_post.call_args.kwargs["json"]["request"]
    assert request == {
        "method": "setProgramme",
        "roomId": 42,
        "roomMode": "fixed",
        "fixed": {"fixedTemp": "215"},
    }


@pytest.mark.parametrize(
    "response",
    [
        _make_response(200, {"status": {"result": "error"}}),
        _make_response(500, {"status": {"result": "success"}}),
        _make_response(200, {"unexpected": True}),
    ],
)
@patch(PATCH_POST)
def test_rejected_command_raises(mock_post, response):
    """A command Warmup doesn't accept raises WarmupCommandError."""
    mock_post.return_value = response

    with pytest.raises(warmup4ie.WarmupCommandError, match="room 42 to prog"):
        _client().set_temperature_to_auto(42)


@patch(PATCH_POST)
def test_command_without_login_raises(mock_post):
    """A command before logging in raises without calling Warmup."""
    client = _new_client_without_connect()

    with pytest.raises(warmup4ie.WarmupCommandError, match="not logged in"):
        client.set_location_to_off(7)
    mock_post.assert_not_called()


@pytest.mark.parametrize(
    ("method", "mutation"),
    [("set_room_to_off", "deviceOff"), ("set_room_to_frost", "deviceFrost")],
)
@patch(PATCH_POST)
def test_room_mutation(mock_post, method, mutation):
    """Off and frost for one room use the GraphQL mutation for that room."""
    mock_post.return_value = _make_response(
        200, {"status": "success", "data": {mutation: True}}
    )
    client = _client()

    getattr(client, method)(20595, 39768)

    assert mock_post.call_args.kwargs["url"] == client.URL
    assert mock_post.call_args.kwargs["json"] == {
        "query": f"mutation {{ {mutation}(lid: 20595, rid: 39768) }}"
    }


@pytest.mark.parametrize(
    "response",
    [
        _make_response(200, {"status": "success", "data": {"deviceOff": False}}),
        _make_response(200, {"status": "success", "errors": [{"message": "no"}]}),
        _make_response(401, {}),
    ],
)
@patch(PATCH_POST)
def test_rejected_room_mutation_raises(mock_post, response):
    """A room mutation Warmup doesn't accept raises WarmupCommandError."""
    mock_post.return_value = response

    with pytest.raises(warmup4ie.WarmupCommandError, match="Turning off room 39768"):
        _client().set_room_to_off(20595, 39768)
