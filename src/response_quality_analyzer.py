"""
Response quality analysis using machine learning and rule-based scoring.
Provides intelligent analysis of review responses for quality and effectiveness.
"""

import re
import string
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import sent_tokenize, word_tokenize

# Download required NLTK data
try:
    nltk.data.find("vader_lexicon")
except LookupError:
    nltk.download("vader_lexicon", quiet=True)

try:
    nltk.data.find("punkt")
except LookupError:
    nltk.download("punkt", quiet=True)


@dataclass
class QualityScore:
    """Quality score breakdown for a response."""

    overall_score: float  # 0-100
    sentiment_score: float  # -1 to 1
    length_score: float  # 0-100
    empathy_score: float  # 0-100
    clarity_score: float  # 0-100
    professionalism_score: float  # 0-100
    actionability_score: float  # 0-100

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_score": self.overall_score,
            "sentiment_score": self.sentiment_score,
            "length_score": self.length_score,
            "empathy_score": self.empathy_score,
            "clarity_score": self.clarity_score,
            "professionalism_score": self.professionalism_score,
            "actionability_score": self.actionability_score,
        }


@dataclass
class QualityAnalysis:
    """Complete quality analysis for a response."""

    score: QualityScore
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    keywords: List[str]
    sentiment: str  # "positive", "negative", "neutral"
    readability_score: float  # Flesch reading ease score


class ResponseQualityAnalyzer:
    """
    Analyzes the quality of responses to medical reviews using ML and rule-based methods.
    """

    def __init__(self) -> None:
        self.sia = SentimentIntensityAnalyzer()

        # Empathy keywords
        self.empathy_keywords = {
            "high": [
                "compreendo",
                "entendo",
                "sinto muito",
                "lamento",
                "preocupado",
                "cuidar",
                "ajudar",
                "apoio",
                "acompanho",
                "compartilho",
            ],
            "medium": [
                "obrigado",
                "agradecido",
                "importante",
                "valorizo",
                "considero",
                "avaliar",
                "verificar",
                "cuidado",
            ],
        }

        # Professional keywords
        self.professional_keywords = [
            "dr.",
            "dra.",
            "médico",
            "médica",
            "especialista",
            "profissional",
            "clínica",
            "hospital",
            "tratamento",
            "diagnóstico",
            "exame",
            "consulta",
            "paciente",
            "saúde",
            "médico",
        ]

        # Action words
        self.action_words = [
            "recomendo",
            "sugiro",
            "oriento",
            "indico",
            "prescrevo",
            "avalio",
            "examino",
            "verificarei",
            "entrarei",
            "agendarei",
            "retornarei",
            "farei",
            "realizarei",
            "providenciarei",
        ]

    def analyze_response(
        self, response_text: str, original_review: Optional[str] = None
    ) -> QualityAnalysis:
        """
        Analyze the quality of a response to a medical review.

        Args:
            response_text: The doctor's response text
            original_review: The original patient review (optional)

        Returns:
            QualityAnalysis: Complete analysis of the response
        """
        if not response_text or not response_text.strip():
            return self._create_empty_analysis()

        # Calculate individual scores
        sentiment_score = self._calculate_sentiment(response_text)
        length_score = self._calculate_length_score(response_text)
        empathy_score = self._calculate_empathy_score(response_text)
        clarity_score = self._calculate_clarity_score(response_text)
        professionalism_score = self._calculate_professionalism_score(response_text)
        actionability_score = self._calculate_actionability_score(response_text)

        # Calculate overall score (weighted average)
        weights = {
            "sentiment": 0.2,
            "length": 0.1,
            "empathy": 0.25,
            "clarity": 0.15,
            "professionalism": 0.15,
            "actionability": 0.15,
        }

        # Calculate overall score (weighted average)
        overall_score = (
            sentiment_score * weights["sentiment"]
            + length_score * weights["length"]
            + empathy_score * weights["empathy"]
            + clarity_score * weights["clarity"]
            + professionalism_score * weights["professionalism"]
            + actionability_score * weights["actionability"]
        )

        # Normalize sentiment score to 0-100 scale for overall calculation
        # normalized_sentiment = (sentiment_score + 1) * 50

        score = QualityScore(
            overall_score=round(overall_score, 2),
            sentiment_score=round(sentiment_score, 3),
            length_score=round(length_score, 2),
            empathy_score=round(empathy_score, 2),
            clarity_score=round(clarity_score, 2),
            professionalism_score=round(professionalism_score, 2),
            actionability_score=round(actionability_score, 2),
        )

        # Generate analysis components
        strengths = self._identify_strengths(score)
        weaknesses = self._identify_weaknesses(score)
        suggestions = self._generate_suggestions(score, response_text)
        keywords = self._extract_keywords(response_text)
        sentiment = self._classify_sentiment(sentiment_score)
        readability = self._calculate_readability(response_text)

        return QualityAnalysis(
            score=score,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            keywords=keywords,
            sentiment=sentiment,
            readability_score=round(readability, 2),
        )

    def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score using VADER."""
        scores = self.sia.polarity_scores(text)
        return scores["compound"]  # -1 to 1

    def _calculate_length_score(self, text: str) -> float:
        """Calculate score based on response length."""
        word_count = len(text.split())

        if word_count < 10:
            return 20.0  # Too short
        elif word_count < 30:
            return 60.0  # Short but acceptable
        elif word_count < 100:
            return 90.0  # Good length
        elif word_count < 200:
            return 85.0  # Long but still good
        else:
            return 70.0  # Too long

    def _calculate_empathy_score(self, text: str) -> float:
        """Calculate empathy score based on empathetic language."""
        text_lower = text.lower()
        score = 0

        # High empathy keywords
        high_empathy_count = sum(
            1 for word in self.empathy_keywords["high"] if word in text_lower
        )
        score += high_empathy_count * 20

        # Medium empathy keywords
        medium_empathy_count = sum(
            1 for word in self.empathy_keywords["medium"] if word in text_lower
        )
        score += medium_empathy_count * 10

        # Check for personal pronouns (shows engagement)
        personal_pronouns = ["eu", "meu", "minha", "nós", "nosso", "nossa"]
        pronoun_count = sum(1 for pronoun in personal_pronouns if pronoun in text_lower)
        score += pronoun_count * 5

        return min(score, 100.0)

    def _calculate_clarity_score(self, text: str) -> float:
        """Calculate clarity score based on readability and structure."""
        sentences = sent_tokenize(text, language="portuguese")
        words = word_tokenize(text, language="portuguese")

        if not sentences or not words:
            return 0.0

        # Average words per sentence
        avg_words_per_sentence = len(words) / len(sentences)

        # Ideal range: 10-20 words per sentence
        if 10 <= avg_words_per_sentence <= 20:
            clarity = 90.0
        elif 5 <= avg_words_per_sentence <= 25:
            clarity = 70.0
        else:
            clarity = 40.0

        # Bonus for using paragraphs (line breaks)
        if "\n\n" in text or "\n" in text:
            clarity += 10

        return min(clarity, 100.0)

    def _calculate_professionalism_score(self, text: str) -> float:
        """Calculate professionalism score."""
        text_lower = text.lower()
        score = 50  # Base score

        # Professional keywords
        prof_keyword_count = sum(
            1 for keyword in self.professional_keywords if keyword in text_lower
        )
        score += prof_keyword_count * 5

        # Check for medical jargon (moderate use is good)
        medical_terms = [
            "diagnóstico",
            "tratamento",
            "exame",
            "sintomas",
            "medicação",
            "consulta",
        ]
        medical_count = sum(1 for term in medical_terms if term in text_lower)

        if medical_count > 0:
            score += 20
        if medical_count > 3:  # Too much jargon
            score -= 10

        # Penalize casual language
        casual_words = ["tipo", "né", "tá", "vou", "vamos", "aí"]
        casual_count = sum(1 for word in casual_words if word in text_lower)
        score -= casual_count * 10

        return max(0, min(score, 100))

    def _calculate_actionability_score(self, text: str) -> float:
        """Calculate how actionable the response is."""
        text_lower = text.lower()
        score = 0

        # Action words
        action_count = sum(1 for word in self.action_words if word in text_lower)
        score += action_count * 15

        # Future tense indicators
        future_indicators = ["irei", "farei", "vou", "vamos", "pretendo", "planejo"]
        future_count = sum(
            1 for indicator in future_indicators if indicator in text_lower
        )
        score += future_count * 10

        # Contact information
        contact_patterns = [
            r"\b\d{2,3}[\s\-\.]?\d{4,5}[\s\-\.]?\d{4}\b",  # Phone
            r"\S+@\S+\.\S+",  # Email
        ]

        for pattern in contact_patterns:
            if re.search(pattern, text):
                score += 20
                break

        return min(score, 100.0)

    def _identify_strengths(self, score: QualityScore) -> List[str]:
        """Identify strengths based on scores."""
        strengths = []

        if score.empathy_score >= 70:
            strengths.append("Alta empatia demonstrada")
        if score.professionalism_score >= 80:
            strengths.append("Tom profissional adequado")
        if score.clarity_score >= 80:
            strengths.append("Resposta clara e bem estruturada")
        if score.actionability_score >= 70:
            strengths.append("Inclui ações concretas")
        if score.sentiment_score > 0.1:
            strengths.append("Tom positivo e reconfortante")
        if 30 <= score.length_score <= 90:
            strengths.append("Comprimento adequado")

        return strengths

    def _identify_weaknesses(self, score: QualityScore) -> List[str]:
        """Identify weaknesses based on scores."""
        weaknesses = []

        if score.empathy_score < 40:
            weaknesses.append("Falta demonstrar empatia")
        if score.professionalism_score < 60:
            weaknesses.append("Tom muito casual ou informal")
        if score.clarity_score < 60:
            weaknesses.append("Resposta confusa ou mal estruturada")
        if score.actionability_score < 40:
            weaknesses.append("Falta orientação prática")
        if score.sentiment_score < -0.1:
            weaknesses.append("Tom negativo ou defensivo")
        if score.length_score < 30:
            weaknesses.append("Resposta muito curta")

        return weaknesses

    def _generate_suggestions(self, score: QualityScore, text: str) -> List[str]:
        """Generate improvement suggestions."""
        suggestions = []

        if score.empathy_score < 50:
            suggestions.append(
                "Adicione frases que demonstrem compreensão dos sentimentos do paciente"
            )

        if score.professionalism_score < 70:
            suggestions.append(
                "Mantenha tom formal e use terminologia médica apropriada"
            )

        if score.actionability_score < 50:
            suggestions.append("Inclua próximos passos ou orientações práticas")

        if score.clarity_score < 70:
            suggestions.append(
                "Quebre a resposta em parágrafos e use frases mais curtas"
            )

        if score.length_score < 40:
            suggestions.append("Expanda a resposta com mais detalhes sobre o caso")

        if not any(word in text.lower() for word in ["obrigado", "agradecido"]):
            suggestions.append("Inclua agradecimento pela avaliação")

        return suggestions

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from the response."""
        words = word_tokenize(text.lower(), language="portuguese")

        # Remove punctuation and common words
        stop_words = {
            "de",
            "da",
            "do",
            "dos",
            "das",
            "a",
            "o",
            "os",
            "as",
            "e",
            "ou",
            "mas",
            "por",
            "para",
            "com",
            "em",
            "um",
            "uma",
            "uns",
            "umas",
        }
        filtered_words = [
            word
            for word in words
            if word not in stop_words and word not in string.punctuation
        ]

        # Get most common words
        word_counts = Counter(filtered_words)
        return [word for word, count in word_counts.most_common(10)]

    def _classify_sentiment(self, sentiment_score: float) -> str:
        """Classify sentiment as positive, negative, or neutral."""
        if sentiment_score > 0.1:
            return "positive"
        elif sentiment_score < -0.1:
            return "negative"
        else:
            return "neutral"

    def _calculate_readability(self, text: str) -> float:
        """Calculate Flesch reading ease score (simplified version)."""
        sentences = sent_tokenize(text, language="portuguese")
        words = word_tokenize(text, language="portuguese")

        if not sentences:
            return 0.0

        avg_words_per_sentence = len(words) / len(sentences)
        avg_syllables_per_word = 1.5  # Simplified approximation

        # Simplified Flesch formula
        score = (
            206.835 - (1.015 * avg_words_per_sentence) - (84.6 * avg_syllables_per_word)
        )

        return max(0, min(100, score))

    def _create_empty_analysis(self) -> QualityAnalysis:
        """Create empty analysis for invalid input."""
        empty_score = QualityScore(0, 0, 0, 0, 0, 0, 0)
        return QualityAnalysis(
            score=empty_score,
            strengths=[],
            weaknesses=["Resposta vazia ou inválida"],
            suggestions=["Forneça uma resposta válida para análise"],
            keywords=[],
            sentiment="neutral",
            readability_score=0.0,
        )

    def compare_responses(self, response1: str, response2: str) -> Dict[str, Any]:
        """
        Compare two responses and provide detailed comparison.

        Returns:
            Dictionary with comparison results
        """
        analysis1 = self.analyze_response(response1)
        analysis2 = self.analyze_response(response2)

        return {
            "response1_score": analysis1.score.overall_score,
            "response2_score": analysis2.score.overall_score,
            "better_response": (
                "response1"
                if analysis1.score.overall_score > analysis2.score.overall_score
                else "response2"
            ),
            "score_difference": abs(
                analysis1.score.overall_score - analysis2.score.overall_score
            ),
            "response1_strengths": analysis1.strengths,
            "response2_strengths": analysis2.strengths,
            "recommendations": self._generate_comparison_recommendations(
                analysis1, analysis2
            ),
        }

    def _generate_comparison_recommendations(
        self, analysis1: QualityAnalysis, analysis2: QualityAnalysis
    ) -> List[str]:
        """Generate recommendations based on comparison."""
        recommendations = []

        score_diff = analysis1.score.overall_score - analysis2.score.overall_score

        if abs(score_diff) < 10:
            recommendations.append("Ambas as respostas têm qualidade similar")
        elif score_diff > 10:
            recommendations.append("Primeira resposta é significativamente melhor")
            recommendations.extend(analysis2.suggestions[:2])
        else:
            recommendations.append("Segunda resposta é significativamente melhor")
            recommendations.extend(analysis1.suggestions[:2])

        return recommendations
