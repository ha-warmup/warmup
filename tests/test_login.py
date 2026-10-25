"""Tests for Warmup4IE login (V2 with V1 fallback) and header selection.

Imports the warmup4ie module directly by file path so that importing it
does not pull in the `custom_components.warmup` package (which depends on
`homeassistant`).
"""
import importlib.util
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "warmup", "warmup4ie", "warmup4ie.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("warmup4ie_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register it so unittest.mock.patch("warmup4ie_under_test....") can
    # resolve it via importlib.import_module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


warmup4ie = _load_module()


def _make_response(status_code=200, json_data=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data if json_data is not None else {}
    response.text = text
    return response


def _new_client_without_connect():
    """Create a Warmup4IE instance without running __init__'s network calls."""
    client = warmup4ie.Warmup4IE.__new__(warmup4ie.Warmup4IE)
    client._user = "user@example.com"
    client._password = "secretpw"
    client._warmup_access_token = None
    return client


class TestV2LoginSuccess:
    @patch("warmup4ie_under_test.requests.post")
    def test_v2_login_success_parses_token_and_sends_right_request(self, mock_post):
        mock_post.return_value = _make_response(
            200, {"status": "success", "response": {"token": "tok-123", "mobileName": "x"}}
        )
        client = _new_client_without_connect()

        result = client.connect()

        assert result is True
        assert client._warmup_access_token == "tok-123"

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["url"] == warmup4ie.Warmup4IE.LOGIN_URL
        assert kwargs["url"] == "https://apil.warmup.com/login"

        body = kwargs["json"]
        assert body == {
            "email": "user@example.com",
            "password": "secretpw",
            "appId": warmup4ie.Warmup4IE.APP_ID,
        }
        # body must be flat - no "request" wrapper
        assert "request" not in body

        headers = kwargs["headers"]
        assert headers["user-agent"] == "WARMUP_API"
        assert headers["api-token"] == warmup4ie.Warmup4IE.APP_TOKEN
        # no token yet at login time
        assert headers["warmup-authorization"] == ""


class TestV2LoginWrongCredentials:
    @pytest.mark.parametrize("status_code", [401, 403])
    @patch("warmup4ie_under_test.requests.post")
    def test_wrong_credentials_returns_false_without_v1_fallback(self, mock_post, status_code):
        mock_post.return_value = _make_response(status_code, {"status": "error"})
        client = _new_client_without_connect()

        result = client.connect()

        assert result is False
        assert client._warmup_access_token is None
        # only the V2 endpoint should have been tried
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["url"] == "https://apil.warmup.com/login"


class TestV2FallbackToV1:
    @pytest.mark.parametrize("status_code", [404, 500, 502])
    @patch("warmup4ie_under_test.requests.post")
    def test_v2_error_falls_back_to_v1_and_v1_success_works(self, mock_post, status_code):
        v2_response = _make_response(status_code, {})
        v1_response = _make_response(
            200, {"status": {"result": "success"}, "response": {"token": "v1-tok"}}
        )
        mock_post.side_effect = [v2_response, v1_response]
        client = _new_client_without_connect()

        result = client.connect()

        assert result is True
        assert client._warmup_access_token == "v1-tok"
        assert mock_post.call_count == 2

        v2_call_kwargs = mock_post.call_args_list[0][1]
        v1_call_kwargs = mock_post.call_args_list[1][1]

        assert v2_call_kwargs["url"] == "https://apil.warmup.com/login"

        assert v1_call_kwargs["url"] == warmup4ie.Warmup4IE.TOKEN_URL
        assert v1_call_kwargs["url"] == "https://api.warmup.com/apps/app/v1"
        v1_body = v1_call_kwargs["json"]
        assert v1_body["request"]["method"] == "userLogin"
        assert v1_body["request"]["email"] == "user@example.com"
        assert v1_body["request"]["password"] == "secretpw"

        v1_headers = v1_call_kwargs["headers"]
        assert v1_headers["user-agent"] == "WARMUP_APP"
        assert v1_headers["app-token"] == warmup4ie.Warmup4IE.APP_TOKEN
        assert "api-token" not in v1_headers
        assert "warmup-authorization" not in v1_headers

    @patch("warmup4ie_under_test.requests.post")
    def test_v2_unexpected_shape_falls_back_to_v1(self, mock_post):
        v2_response = _make_response(200, {"unexpected": "shape"})
        v1_response = _make_response(
            200, {"status": {"result": "success"}, "response": {"token": "v1-tok"}}
        )
        mock_post.side_effect = [v2_response, v1_response]
        client = _new_client_without_connect()

        result = client.connect()

        assert result is True
        assert client._warmup_access_token == "v1-tok"
        assert mock_post.call_count == 2


class TestGraphQLHeaders:
    @patch("warmup4ie_under_test.requests.post")
    def test_graphql_call_uses_v2_headers_including_authorization(self, mock_post):
        mock_post.return_value = _make_response(
            200, {"status": "success", "data": {"user": {"allLocations": []}}}
        )
        client = _new_client_without_connect()
        client._warmup_access_token = "my-access-token"
        client._locations = {}
        client._rooms = {}
        client._all_devices = {}

        client.update_all_devices()

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["url"] == warmup4ie.Warmup4IE.URL
        assert kwargs["url"] == "https://apil.warmup.com/graphql"

        headers = kwargs["headers"]
        assert headers["user-agent"] == "WARMUP_API"
        assert headers["api-token"] == warmup4ie.Warmup4IE.APP_TOKEN
        assert headers["warmup-authorization"] == "my-access-token"
