"""Tests for OpenSubtitles client (unit tests with mocked HTTP)."""

from unittest.mock import MagicMock, patch

import pytest


def test_search_builds_correct_params():
    """Verify search constructs the right query params."""
    with patch("backend.pipeline.subtitles.settings") as mock_settings:
        mock_settings.opensubtitles_api_key = "test-key"
        mock_settings.opensubtitles_username = ""
        mock_settings.opensubtitles_password = ""
        mock_settings.app_name = "test"

        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            # Mock a successful response
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": [], "total_pages": 1}
            mock_client.request.return_value = mock_resp

            from backend.pipeline.subtitles import OpenSubtitlesClient

            client = OpenSubtitlesClient.__new__(OpenSubtitlesClient)
            client._client = mock_client
            client._token = None

            result = client.search("Breaking Bad", season=1, language="en")

            call_args = mock_client.request.call_args
            assert call_args[0] == ("GET", "/subtitles")
            params = call_args[1]["params"]
            assert params["query"] == "Breaking Bad"
            assert params["season_number"] == "1"
            assert params["type"] == "episode"
