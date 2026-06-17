"""Tests for ResponseGenerator API call methods and error handling."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.response_generator import ResponseGenerator


def _make_generation_config(**overrides):
    defaults = dict(
        mode="local",
        openai_api_key="sk-test-key",
        openai_model="gpt-4.1-mini",
        claude_api_key="claude-test-key",
        claude_model="claude-3-5-sonnet-latest",
        gemini_api_key="gemini-test-key",
        gemini_model="gemini-2.5-flash",
        system_prompt="Test system prompt",
        temperature=0.35,
        max_tokens=300,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def gen_config():
    return _make_generation_config()


@pytest.fixture
def generator(gen_config):
    config = SimpleNamespace(
        data_dir=Path("/tmp/test-response-gen"),
        generation=gen_config,
        security=SimpleNamespace(openai_api_key="sk-test-key"),
    )
    logger = MagicMock()
    return ResponseGenerator(config, logger)


@pytest.fixture
def generator_no_keys():
    config = SimpleNamespace(
        data_dir=Path("/tmp/test-response-gen"),
        generation=_make_generation_config(
            openai_api_key="",
            claude_api_key="",
            gemini_api_key="",
        ),
        security=SimpleNamespace(openai_api_key=""),
    )
    return ResponseGenerator(config, MagicMock())


OPENAI_SUCCESS_RESPONSE = {
    "choices": [{"message": {"content": "Obrigado pelo feedback!"}}]
}

CLAUDE_SUCCESS_RESPONSE = {
    "content": [{"type": "text", "text": "Obrigado pelo feedback!"}]
}

GEMINI_SUCCESS_RESPONSE = {
    "candidates": [{"content": {"parts": [{"text": "Obrigado pelo feedback!"}]}}]
}

CALL_ARGS = ("test prompt", "system prompt", 0.35, 300)


def _mock_ok_response(json_data):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = json_data
    return resp


def _mock_error_response(status_code=429, text="rate limited"):
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status_code
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class TestCallOpenAI:
    @patch("src.providers.openai.requests.post")
    def test_success(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response(OPENAI_SUCCESS_RESPONSE)

        text, model = generator._call_openai(*CALL_ARGS)

        assert text == "Obrigado pelo feedback!"
        assert model == "gpt-4.1-mini"
        mock_post.assert_called_once()

    @patch("src.providers.openai.requests.post")
    def test_timeout(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.Timeout()

        with pytest.raises(ValueError, match="timeout"):
            generator._call_openai(*CALL_ARGS)

    @patch("src.providers.openai.requests.post")
    def test_connection_error(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(ValueError, match="conexão"):
            generator._call_openai(*CALL_ARGS)

    @patch("src.providers.openai.requests.post")
    def test_request_exception(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.RequestException("socket closed")

        with pytest.raises(ValueError, match="rede"):
            generator._call_openai(*CALL_ARGS)

    @patch("src.providers.openai.requests.post")
    def test_http_error(self, mock_post, generator):
        mock_post.return_value = _mock_error_response(429, "rate limited")

        with pytest.raises(ValueError, match="429"):
            generator._call_openai(*CALL_ARGS)

    @patch("src.providers.openai.requests.post")
    def test_invalid_json(self, mock_post, generator):
        resp = MagicMock()
        resp.ok = True
        resp.json.side_effect = ValueError("no JSON")
        mock_post.return_value = resp

        with pytest.raises(ValueError, match="não-JSON"):
            generator._call_openai(*CALL_ARGS)

    @patch("src.providers.openai.requests.post")
    def test_empty_response_text(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response({"choices": []})

        with pytest.raises(ValueError, match="não retornou texto"):
            generator._call_openai(*CALL_ARGS)

    def test_missing_api_key(self, generator_no_keys):
        with pytest.raises(ValueError, match="não configurada"):
            generator_no_keys._call_openai(*CALL_ARGS)


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------


class TestCallClaude:
    @patch("src.providers.claude.requests.post")
    def test_success(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response(CLAUDE_SUCCESS_RESPONSE)

        text, model = generator._call_claude(*CALL_ARGS)

        assert text == "Obrigado pelo feedback!"
        assert model == "claude-3-5-sonnet-latest"

    @patch("src.providers.claude.requests.post")
    def test_timeout(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.Timeout()

        with pytest.raises(ValueError, match="timeout"):
            generator._call_claude(*CALL_ARGS)

    @patch("src.providers.claude.requests.post")
    def test_connection_error(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(ValueError, match="conexão"):
            generator._call_claude(*CALL_ARGS)

    @patch("src.providers.claude.requests.post")
    def test_request_exception(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.RequestException("reset")

        with pytest.raises(ValueError, match="rede"):
            generator._call_claude(*CALL_ARGS)

    @patch("src.providers.claude.requests.post")
    def test_http_error(self, mock_post, generator):
        mock_post.return_value = _mock_error_response(500, "internal error")

        with pytest.raises(ValueError, match="500"):
            generator._call_claude(*CALL_ARGS)

    @patch("src.providers.claude.requests.post")
    def test_invalid_json(self, mock_post, generator):
        resp = MagicMock()
        resp.ok = True
        resp.json.side_effect = ValueError("bad json")
        mock_post.return_value = resp

        with pytest.raises(ValueError, match="não-JSON"):
            generator._call_claude(*CALL_ARGS)

    @patch("src.providers.claude.requests.post")
    def test_empty_response_text(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response({"content": []})

        with pytest.raises(ValueError, match="não retornou texto"):
            generator._call_claude(*CALL_ARGS)

    def test_missing_api_key(self, generator_no_keys):
        with pytest.raises(ValueError, match="não configurada"):
            generator_no_keys._call_claude(*CALL_ARGS)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


class TestCallGemini:
    @patch("src.providers.gemini.requests.post")
    def test_success(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response(GEMINI_SUCCESS_RESPONSE)

        text, model = generator._call_gemini(*CALL_ARGS)

        assert text == "Obrigado pelo feedback!"
        assert model == "gemini-2.5-flash"

    @patch("src.providers.gemini.requests.post")
    def test_timeout(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.Timeout()

        with pytest.raises(ValueError, match="timeout"):
            generator._call_gemini(*CALL_ARGS)

    @patch("src.providers.gemini.requests.post")
    def test_connection_error(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(ValueError, match="conexão"):
            generator._call_gemini(*CALL_ARGS)

    @patch("src.providers.gemini.requests.post")
    def test_request_exception(self, mock_post, generator):
        mock_post.side_effect = requests.exceptions.RequestException("dns failure")

        with pytest.raises(ValueError, match="rede"):
            generator._call_gemini(*CALL_ARGS)

    @patch("src.providers.gemini.requests.post")
    def test_http_error(self, mock_post, generator):
        mock_post.return_value = _mock_error_response(403, "forbidden")

        with pytest.raises(ValueError, match="403"):
            generator._call_gemini(*CALL_ARGS)

    @patch("src.providers.gemini.requests.post")
    def test_invalid_json(self, mock_post, generator):
        resp = MagicMock()
        resp.ok = True
        resp.json.side_effect = ValueError("not json")
        mock_post.return_value = resp

        with pytest.raises(ValueError, match="não-JSON"):
            generator._call_gemini(*CALL_ARGS)

    @patch("src.providers.gemini.requests.post")
    def test_empty_response_text(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response({"candidates": []})

        with pytest.raises(ValueError, match="não retornou texto"):
            generator._call_gemini(*CALL_ARGS)

    def test_missing_api_key(self, generator_no_keys):
        with pytest.raises(ValueError, match="não configurada"):
            generator_no_keys._call_gemini(*CALL_ARGS)


# ---------------------------------------------------------------------------
# generate_response_with_metadata
# ---------------------------------------------------------------------------


class TestGenerateResponseWithMetadata:
    def test_local_mode(self, generator):
        review = {"author": "Maria Silva", "comment": "Excelente atendimento!"}

        result = generator.generate_response_with_metadata(
            review, generation_mode="local"
        )

        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0
        assert result["model"]["provider"] == "local"
        assert result["model"]["type"] == "template"
        assert result["model"]["mode"] == "local"

    @patch("src.providers.openai.requests.post")
    def test_openai_mode(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response(OPENAI_SUCCESS_RESPONSE)
        review = {"author": "Carlos", "comment": "Bom"}

        result = generator.generate_response_with_metadata(
            review, generation_mode="openai"
        )

        assert result["text"] == "Obrigado pelo feedback!"
        assert result["model"]["provider"] == "openai"
        assert result["model"]["type"] == "third-party"
        assert result["model"]["name"] == "gpt-4.1-mini"

    @patch("src.providers.claude.requests.post")
    def test_claude_mode(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response(CLAUDE_SUCCESS_RESPONSE)
        review = {"author": "Ana", "comment": "Boa consulta"}

        result = generator.generate_response_with_metadata(
            review, generation_mode="claude"
        )

        assert result["text"] == "Obrigado pelo feedback!"
        assert result["model"]["provider"] == "claude"

    @patch("src.providers.gemini.requests.post")
    def test_gemini_mode(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response(GEMINI_SUCCESS_RESPONSE)
        review = {"author": "Pedro", "comment": "Recomendo"}

        result = generator.generate_response_with_metadata(
            review, generation_mode="gemini"
        )

        assert result["text"] == "Obrigado pelo feedback!"
        assert result["model"]["provider"] == "gemini"

    def test_invalid_mode_falls_back_to_local(self, generator):
        review = {"author": "João", "comment": "Bom"}

        result = generator.generate_response_with_metadata(
            review, generation_mode="invalid_provider"
        )

        assert result["model"]["provider"] == "local"
        assert result["model"]["mode"] == "local"

    def test_default_mode_uses_config(self, generator):
        review = {"author": "Lucia", "comment": "Boa"}

        result = generator.generate_response_with_metadata(review)

        assert result["model"]["provider"] == "local"

    @patch("src.providers.openai.requests.post")
    def test_metadata_includes_temperature_and_tokens(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response(OPENAI_SUCCESS_RESPONSE)
        review = {"author": "Test", "comment": "Test"}

        result = generator.generate_response_with_metadata(
            review, generation_mode="openai"
        )

        assert result["model"]["temperature"] == 0.35
        assert result["model"]["max_tokens"] == 300


# ---------------------------------------------------------------------------
# generate_response
# ---------------------------------------------------------------------------


class TestGenerateResponse:
    def test_returns_string(self, generator):
        review = {"author": "Maria", "comment": "Ótima doutora!"}

        result = generator.generate_response(review)

        assert isinstance(result, str)
        assert len(result) > 0

    @patch("src.providers.openai.requests.post")
    def test_delegates_to_metadata_method(self, mock_post, generator):
        mock_post.return_value = _mock_ok_response(OPENAI_SUCCESS_RESPONSE)
        review = {"author": "Test", "comment": "Test"}

        result = generator.generate_response(review, generation_mode="openai")

        assert result == "Obrigado pelo feedback!"


# ---------------------------------------------------------------------------
# _generate_local_response
# ---------------------------------------------------------------------------


class TestLocalResponse:
    def test_with_author_and_comment(self, generator):
        review = {"author": "Maria Silva", "comment": "Excelente atendimento!"}

        result = generator._generate_local_response(review)

        assert isinstance(result, str)
        assert len(result) > 20
        assert "Maria" in result
        assert "satisfeita" in result

    def test_with_doctor_context(self, generator):
        review = {"author": "Carlos", "comment": "Muito bom"}
        doctor_context = {"name": "Dr. João Mendes"}

        result = generator._generate_local_response(review, doctor_context)

        assert "Dr. João Mendes" in result

    def test_with_empty_author(self, generator):
        review = {"author": "", "comment": "Bom atendimento"}

        result = generator._generate_local_response(review)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_missing_comment(self, generator):
        review = {"author": "Ana Costa"}

        result = generator._generate_local_response(review)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_empty_review(self, generator):
        review = {}

        result = generator._generate_local_response(review)

        assert isinstance(result, str)

    def test_with_dict_author(self, generator):
        review = {"author": {"name": "Fernanda Lima"}, "comment": "Ótima consulta"}

        result = generator._generate_local_response(review)

        assert "Fernanda" in result

    def test_without_doctor_context_uses_template_signature(self, generator):
        review = {"author": "Teste", "comment": "Bom"}

        result = generator._generate_local_response(review)

        assert "Atenciosamente" in result


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


class TestExtractionHelpers:
    def test_extract_openai_text_standard(self):
        payload = {"choices": [{"message": {"content": "Hello"}}]}
        assert ResponseGenerator._extract_openai_text(payload) == "Hello"

    def test_extract_openai_text_list_content(self):
        payload = {
            "choices": [
                {"message": {"content": [{"type": "text", "text": "Hello list"}]}}
            ]
        }
        assert ResponseGenerator._extract_openai_text(payload) == "Hello list"

    def test_extract_openai_text_empty_choices(self):
        assert ResponseGenerator._extract_openai_text({"choices": []}) == ""

    def test_extract_claude_text(self):
        payload = {"content": [{"type": "text", "text": "Claude says hi"}]}
        assert ResponseGenerator._extract_claude_text(payload) == "Claude says hi"

    def test_extract_claude_text_empty(self):
        assert ResponseGenerator._extract_claude_text({"content": []}) == ""

    def test_extract_gemini_text(self):
        payload = {"candidates": [{"content": {"parts": [{"text": "Gemini reply"}]}}]}
        assert ResponseGenerator._extract_gemini_text(payload) == "Gemini reply"

    def test_extract_gemini_text_empty_candidates(self):
        assert ResponseGenerator._extract_gemini_text({"candidates": []}) == ""

    def test_extract_gemini_text_no_text_in_parts(self):
        payload = {"candidates": [{"content": {"parts": [{"code": "x=1"}]}}]}
        assert ResponseGenerator._extract_gemini_text(payload) == ""


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------


class TestHelperMethods:
    def test_resolve_generation_mode_explicit(self, generator):
        assert generator._resolve_generation_mode("openai") == "openai"
        assert generator._resolve_generation_mode("claude") == "claude"
        assert generator._resolve_generation_mode("gemini") == "gemini"
        assert generator._resolve_generation_mode("local") == "local"

    def test_resolve_generation_mode_invalid_falls_back(self, generator):
        assert generator._resolve_generation_mode("gpt5") == "local"

    def test_resolve_generation_mode_none_uses_config(self, generator):
        result = generator._resolve_generation_mode(None)
        assert result == "local"

    def test_coerce_float(self):
        assert ResponseGenerator._coerce_float(0.5, 0.35) == 0.5
        assert ResponseGenerator._coerce_float("0.7", 0.35) == 0.7
        assert ResponseGenerator._coerce_float("bad", 0.35) == 0.35
        assert ResponseGenerator._coerce_float(None, 0.35) == 0.35
        assert ResponseGenerator._coerce_float(True, 0.35) == 0.35

    def test_coerce_int(self):
        assert ResponseGenerator._coerce_int(500, 300) == 500
        assert ResponseGenerator._coerce_int("200", 300) == 200
        assert ResponseGenerator._coerce_int("bad", 300) == 300
        assert ResponseGenerator._coerce_int(None, 300) == 300
        assert ResponseGenerator._coerce_int(True, 300) == 300

    def test_extract_first_name(self, generator):
        assert generator.extract_first_name("Maria Silva") == "Maria"
        assert generator.extract_first_name("") is None
        assert generator.extract_first_name("AB") is None
        assert generator.extract_first_name("M") is None

    def test_identify_mentioned_qualities(self, generator):
        qualities = generator.identify_mentioned_qualities(
            "Doutora muito atenciosa e profissional"
        )
        assert "atenciosa" in qualities
        assert "profissional" in qualities

    def test_identify_no_qualities(self, generator):
        qualities = generator.identify_mentioned_qualities("Consulta ok")
        assert qualities == []
