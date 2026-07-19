from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from app.api.main import app

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class TestLlmStatus:
    @pytest.mark.asyncio
    async def test_reports_configured_when_server_key_present(self):
        with patch("app.services.llm.llm_client") as mock_client:
            mock_client.has_server_key = True
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/v1/llm-status")
        assert response.status_code == 200
        assert response.json() == {"server_key_configured": True}

    @pytest.mark.asyncio
    async def test_reports_not_configured_when_no_server_key(self):
        with patch("app.services.llm.llm_client") as mock_client:
            mock_client.has_server_key = False
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/v1/llm-status")
        assert response.status_code == 200
        assert response.json() == {"server_key_configured": False}


class TestChatEndpoint:
    @staticmethod
    def _patch_chat_deps():
        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384

        mock_hit = MagicMock()
        mock_hit.payload = {"doc_id": "d1", "page": 1, "filename": "f.pdf", "text": "some text"}

        return (
            patch("app.services.embeddings.get_model", return_value=mock_model),
            patch("app.services.vector_store.search_vectors", return_value=[mock_hit]),
        )

    @pytest.mark.asyncio
    async def test_passes_request_api_key_to_llm_client(self):
        get_model_patch, search_patch = self._patch_chat_deps()
        with get_model_patch, search_patch, \
             patch("app.services.llm.llm_client") as mock_llm:
            mock_llm.generate_response.return_value = "an answer"
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/chat",
                    json={"query": "hello", "api_key": "sk-or-user-supplied"},
                )

        assert response.status_code == 200
        mock_llm.generate_response.assert_called_once()
        assert mock_llm.generate_response.call_args.kwargs["api_key"] == "sk-or-user-supplied"

    @pytest.mark.asyncio
    async def test_no_api_key_available_returns_401(self):
        from app.services.llm import LLMNotConfiguredError

        get_model_patch, search_patch = self._patch_chat_deps()
        with get_model_patch, search_patch, \
             patch("app.services.llm.llm_client") as mock_llm:
            mock_llm.generate_response.side_effect = LLMNotConfiguredError("no key")
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post("/api/v1/chat", json={"query": "hello"})

        assert response.status_code == 401
