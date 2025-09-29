import pytest

from src import response_quality_analyzer as rqa
from src.response_quality_analyzer import QualityScore, ResponseQualityAnalyzer


@pytest.fixture(autouse=True)
def stub_nltk_tokenizers(monkeypatch):
    """Stub sentence and word tokenizers to avoid downloading large language-specific resources.
    Keeps test fast and deterministic.
    """

    def fake_sent_tokenize(text, language=None):  # noqa: D401
        # Very naive split for testing only
        return [s for s in text.replace("\n", " ").split(".") if s.strip()]

    def fake_word_tokenize(text, language=None):  # noqa: D401
        return [w for w in text.replace("\n", " ").split() if w]

    monkeypatch.setattr("nltk.tokenize.sent_tokenize", fake_sent_tokenize, raising=True)
    monkeypatch.setattr("nltk.tokenize.word_tokenize", fake_word_tokenize, raising=True)
    # Patch the names imported into the module namespace
    monkeypatch.setattr(rqa, "sent_tokenize", fake_sent_tokenize, raising=True)
    monkeypatch.setattr(rqa, "word_tokenize", fake_word_tokenize, raising=True)


@pytest.fixture
def analyzer():
    return ResponseQualityAnalyzer()


def test_empty_response(analyzer):
    analysis = analyzer.analyze_response("")
    assert analysis.score.overall_score == 0
    assert "Resposta vazia" in analysis.weaknesses[0]


def test_positive_empathic_response(analyzer):
    text = (
        "Olá, compreendo sua preocupação e agradeço pelo retorno. "
        "Vou avaliar seu caso e providenciarei os próximos exames."
    )
    analysis = analyzer.analyze_response(text)
    assert analysis.score.empathy_score > 0
    assert analysis.sentiment in {"positive", "neutral"}
    assert analysis.score.actionability_score > 0
    assert analysis.score.overall_score > 10


def test_compare_responses(analyzer):
    r1 = "Obrigado pelo retorno, avaliarei seu caso e entrarei em contato."
    r2 = "Ok"
    result = analyzer.compare_responses(r1, r2)
    # Better response should likely be r1
    assert result["better_response"] in {"response1", "response2"}
    assert isinstance(result["score_difference"], (int, float))


def test_generate_suggestions_low_scores(monkeypatch, analyzer):
    # Force internal scoring pieces by monkeypatching helper methods
    monkeypatch.setattr(analyzer, "_calculate_sentiment", lambda t: 0)
    monkeypatch.setattr(analyzer, "_calculate_length_score", lambda t: 10)
    monkeypatch.setattr(analyzer, "_calculate_empathy_score", lambda t: 0)
    monkeypatch.setattr(analyzer, "_calculate_clarity_score", lambda t: 10)
    monkeypatch.setattr(analyzer, "_calculate_professionalism_score", lambda t: 10)
    monkeypatch.setattr(analyzer, "_calculate_actionability_score", lambda t: 0)
    analysis = analyzer.analyze_response("Sem agradecimento")
    # Should trigger multiple suggestions
    assert any("compreensão" in s for s in analysis.suggestions)
    assert any("agradecimento" in s for s in analysis.suggestions)


def test_quality_score_to_dict():
    qs = QualityScore(1, 0.1, 2, 3, 4, 5, 6)
    d = qs.to_dict()
    assert d["overall_score"] == 1
    assert set(d.keys()) == {
        "overall_score",
        "sentiment_score",
        "length_score",
        "empathy_score",
        "clarity_score",
        "professionalism_score",
        "actionability_score",
    }
