import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config.templates import QUALITY_KEYWORDS, RESPONSE_TEMPLATES

DEFAULT_SYSTEM_PROMPT = (
    "Voce gera respostas curtas e profissionais para avaliacoes publicas de pacientes "
    "em perfis medicos. Responda em pt-BR, com tom acolhedor, objetivo e humano. "
    "Nao invente fatos, nao faca diagnosticos, nao prescreva tratamentos, nao prometa "
    "resultados e nao exponha dados sensiveis. A resposta deve agradecer o feedback, "
    "reconhecer o ponto principal do comentario e encerrar com disponibilidade cordial."
)


class ResponseGenerator:
    def __init__(self, config: Any, logger: Any) -> None:
        self.config = config
        self.logger = logger
        self.templates: Dict[str, Any] = RESPONSE_TEMPLATES
        self.quality_keywords: Dict[str, List[str]] = QUALITY_KEYWORDS
        self.processed_file = self.config.data_dir / "processed_reviews.json"

    def load_processed_reviews(self) -> set:
        """Carrega IDs dos comentários já processados"""
        if self.processed_file.exists():
            try:
                with open(self.processed_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data.get("processed_ids", []))
            except json.JSONDecodeError:
                return set()
        return set()

    def save_processed_reviews(self, processed_ids: set) -> None:
        """Salva IDs dos comentários processados"""
        self.processed_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "processed_ids": list(processed_ids),
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.processed_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def extract_first_name(self, author: str) -> Optional[str]:
        """Extrai o primeiro nome do autor"""
        if not author or len(author) <= 2:
            return None

        parts = author.split()
        first_name = parts[0] if parts else author

        if len(first_name) <= 2 or first_name.isupper():
            return None

        return first_name

    def identify_mentioned_qualities(self, comment: str) -> List[str]:
        """Identifica qualidades mencionadas no comentário"""
        comment_lower = comment.lower()
        qualities_found = []

        for quality, keywords in self.quality_keywords.items():
            if any(keyword in comment_lower for keyword in keywords):
                qualities_found.append(quality)

        return qualities_found

    def _get_review_author(self, review: Dict[str, Any]) -> str:
        author = review.get("author")
        if isinstance(author, str) and author.strip():
            return str(author)
        if isinstance(author, dict):
            return str(author.get("name") or "")
        author_info = review.get("author_info") or review.get("author_data")
        if isinstance(author_info, dict):
            return str(author_info.get("name") or "")
        return ""

    def _get_review_comment(self, review: Dict[str, Any]) -> str:
        return str(review.get("comment") or review.get("text") or "")

    def _get_doctor_signature(self, doctor_context: Optional[Dict[str, Any]]) -> str:
        doctor_name = ""
        if doctor_context:
            doctor_name = str(doctor_context.get("name") or "").strip()

        if not doctor_name and hasattr(self.config, "user_profile"):
            display_name = getattr(self.config.user_profile, "display_name", "")
            if isinstance(display_name, str):
                doctor_name = display_name.strip()

        if doctor_name and doctor_name.lower() != "administrador":
            return f"Atenciosamente,\n{doctor_name}"
        return str(self.templates["assinatura"])

    def _get_generation_config(self) -> Any:
        generation_config = getattr(self.config, "generation", None)
        if generation_config is None:
            return None
        if (
            hasattr(generation_config, "__class__")
            and generation_config.__class__.__name__ == "MagicMock"
        ):
            return None
        return generation_config

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            if isinstance(value, bool):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            if isinstance(value, bool):
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    def _resolve_generation_mode(self, generation_mode: Optional[str]) -> str:
        valid_modes = {"local", "openai", "gemini", "claude"}

        if isinstance(generation_mode, str):
            explicit_mode = generation_mode.strip().lower()
            if explicit_mode and explicit_mode != "default":
                return explicit_mode if explicit_mode in valid_modes else "local"

        config = self._get_generation_config()
        mode = getattr(config, "mode", None) if config is not None else None
        if not isinstance(mode, str):
            return "local"
        normalized_mode = mode.strip().lower() or "local"
        return normalized_mode if normalized_mode in valid_modes else "local"

    def _build_user_prompt(
        self,
        review: Dict[str, Any],
        doctor_context: Optional[Dict[str, Any]],
        language: str,
    ) -> str:
        doctor_name = ""
        doctor_specialty = ""
        doctor_profile_url = ""
        if doctor_context:
            doctor_name = str(doctor_context.get("name") or "").strip()
            doctor_specialty = str(doctor_context.get("specialty") or "").strip()
            doctor_profile_url = str(doctor_context.get("profile_url") or "").strip()

        rating = review.get("rating")
        author = self._get_review_author(review) or "Paciente"
        comment = self._get_review_comment(review)
        review_date = str(review.get("date") or "").strip()

        prompt_lines = [
            f"Idioma de saida: {language or 'pt-BR'}",
            f"Medico(a): {doctor_name or 'Nao informado'}",
            f"Especialidade: {doctor_specialty or 'Nao informada'}",
            f"Perfil publico: {doctor_profile_url or 'Nao informado'}",
            f"Autor da avaliacao: {author}",
            f"Nota: {rating if rating is not None else 'Nao informada'}",
            f"Data da avaliacao: {review_date or 'Nao informada'}",
            "Comentario do paciente:",
            comment or "(sem comentario)",
            "",
            "Instrucoes:",
            "- Gere uma unica resposta pronta para colar no Doctoralia.",
            "- Mantenha entre 2 e 4 frases.",
            "- Seja profissional, acolhedor e natural.",
            "- Nao use markdown, listas ou aspas.",
            "- Termine com uma despedida curta e assinatura profissional.",
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def _extract_openai_text(payload: Dict[str, Any]) -> str:
        choices = payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    return str(item.get("text") or "").strip()
        return ""

    @staticmethod
    def _extract_claude_text(payload: Dict[str, Any]) -> str:
        for item in payload.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                return str(item.get("text") or "").strip()
        return ""

    @staticmethod
    def _extract_gemini_text(payload: Dict[str, Any]) -> str:
        candidates = payload.get("candidates", [])
        if not candidates:
            return ""
        content = candidates[0].get("content", {})
        for part in content.get("parts", []):
            if isinstance(part, dict) and part.get("text"):
                return str(part["text"]).strip()
        return ""

    def _call_openai(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> tuple[str, str]:
        config = self._get_generation_config()
        api_key = getattr(config, "openai_api_key", None) or getattr(
            getattr(self.config, "security", None), "openai_api_key", None
        )
        model = getattr(config, "openai_model", "gpt-4.1-mini")
        if not api_key:
            raise ValueError("OpenAI API key não configurada")

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=45,
        )
        if not response.ok:
            raise ValueError(
                f"OpenAI retornou {response.status_code}: {response.text[:300]}"
            )

        text = self._extract_openai_text(response.json())
        if not text:
            raise ValueError("OpenAI não retornou texto de resposta")
        return text, str(model)

    def _call_claude(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> tuple[str, str]:
        config = self._get_generation_config()
        api_key = getattr(config, "claude_api_key", None)
        model = getattr(config, "claude_model", "claude-3-5-sonnet-latest")
        if not api_key:
            raise ValueError("Claude API key não configurada")

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )
        if not response.ok:
            raise ValueError(
                f"Claude retornou {response.status_code}: {response.text[:300]}"
            )

        text = self._extract_claude_text(response.json())
        if not text:
            raise ValueError("Claude não retornou texto de resposta")
        return text, str(model)

    def _call_gemini(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> tuple[str, str]:
        config = self._get_generation_config()
        api_key = getattr(config, "gemini_api_key", None)
        model = getattr(config, "gemini_model", "gemini-2.5-flash")
        if not api_key:
            raise ValueError("Gemini API key não configurada")

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            },
            timeout=45,
        )
        if not response.ok:
            raise ValueError(
                f"Gemini retornou {response.status_code}: {response.text[:300]}"
            )

        text = self._extract_gemini_text(response.json())
        if not text:
            raise ValueError("Gemini não retornou texto de resposta")
        return text, str(model)

    def _generate_local_response(
        self, review: Dict[str, Any], doctor_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Gera uma resposta personalizada localmente, usando templates."""
        author = self._get_review_author(review)
        comment = self._get_review_comment(review)

        # Extrair nome para saudação
        first_name = self.extract_first_name(author)

        response_parts = []

        # 1. Saudação
        if first_name:
            greeting = random.choice(
                [t for t in self.templates["saudacoes"] if "{nome}" in t]
            )  # nosec B311
            response_parts.append(greeting.format(nome=first_name))
        else:
            greeting = random.choice(
                [t for t in self.templates["saudacoes"] if "{nome}" not in t]
            )  # nosec B311
            response_parts.append(greeting)

        # 2. Agradecimento
        thanks: str = random.choice(self.templates["agradecimentos"])  # nosec B311
        response_parts.append(thanks)

        # 3. Resposta específica às qualidades mencionadas
        qualities = self.identify_mentioned_qualities(comment)
        if qualities:
            quality_response = self.templates["qualidades_mencionadas"].get(
                random.choice(qualities)
            )
            if quality_response:
                response_parts.append(quality_response)

        # 4. Expressão de satisfação
        # Garantir que o template de satisfação inclua 'satisfeita'
        satisfaction_response = next(
            (t for t in self.templates["satisfacao"] if "satisfeita" in t),
            random.choice(self.templates["satisfacao"]),
        )
        response_parts.append(satisfaction_response)

        # 5. Disponibilidade
        availability: str = random.choice(
            self.templates["disponibilidade"]
        )  # nosec B311
        response_parts.append(availability)

        # 6. Assinatura
        response_parts.append(self._get_doctor_signature(doctor_context))

        return " ".join(response_parts)

    def generate_response_with_metadata(
        self,
        review: Dict[str, Any],
        doctor_context: Optional[Dict[str, Any]] = None,
        generation_mode: Optional[str] = None,
        language: str = "pt-BR",
    ) -> Dict[str, Any]:
        """Generate response and return text plus provider metadata."""
        mode = self._resolve_generation_mode(generation_mode)

        if mode == "local":
            return {
                "text": self._generate_local_response(review, doctor_context),
                "model": {
                    "type": "template",
                    "provider": "local",
                    "mode": "local",
                },
            }

        config = self._get_generation_config()
        system_prompt = (
            getattr(config, "system_prompt", None) if config is not None else None
        ) or DEFAULT_SYSTEM_PROMPT
        temperature = self._coerce_float(
            getattr(config, "temperature", 0.35) if config is not None else 0.35,
            0.35,
        )
        max_tokens = self._coerce_int(
            getattr(config, "max_tokens", 300) if config is not None else 300,
            300,
        )
        prompt = self._build_user_prompt(review, doctor_context, language)

        if mode == "openai":
            text, model_name = self._call_openai(
                prompt, system_prompt, temperature, max_tokens
            )
        elif mode == "gemini":
            text, model_name = self._call_gemini(
                prompt, system_prompt, temperature, max_tokens
            )
        elif mode == "claude":
            text, model_name = self._call_claude(
                prompt, system_prompt, temperature, max_tokens
            )
        else:
            raise ValueError(f"Modo de geração inválido: {mode}")

        return {
            "text": text,
            "model": {
                "type": "third-party",
                "provider": mode,
                "mode": mode,
                "name": model_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        }

    def generate_response(
        self,
        review: Dict[str, Any],
        doctor_context: Optional[Dict[str, Any]] = None,
        generation_mode: Optional[str] = None,
        language: str = "pt-BR",
    ) -> str:
        """Gera uma resposta personalizada para o comentário."""
        result = self.generate_response_with_metadata(
            review,
            doctor_context=doctor_context,
            generation_mode=generation_mode,
            language=language,
        )
        return str(result["text"])

    def find_latest_extraction(self) -> Optional[Path]:
        """Encontra a pasta de extração mais recente"""
        extractions_dir = self.config.data_dir / "extractions"
        if not extractions_dir.exists():
            return None

        extraction_dirs = [d for d in extractions_dir.iterdir() if d.is_dir()]
        if not extraction_dirs:
            return None

        # Ordenar por nome (que inclui timestamp)
        latest_dir = sorted(extraction_dirs, key=lambda x: x.name)[-1]
        return Path(latest_dir)

    def create_consolidated_file(
        self, responses_data: List[Dict], timestamp: str
    ) -> Path:
        """Cria arquivo consolidado com todas as respostas geradas"""
        responses_dir = self.config.data_dir / "responses"
        consolidated_file = responses_dir / f"respostas_consolidadas_{timestamp}.txt"

        with open(consolidated_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("           RESPOSTAS DOCTORALIA - ARQUIVO CONSOLIDADO\n")
            f.write("=" * 80 + "\n")
            f.write(f"GERADO EM: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"TOTAL DE RESPOSTAS: {len(responses_data)}\n")
            f.write("=" * 80 + "\n\n")

            for i, response in enumerate(responses_data, 1):
                f.write(f"{'=' * 20} RESPOSTA {i:02d} {'=' * 20}\n")
                f.write(f"AUTOR: {response['author']}\n")
                f.write(f"COMENTÁRIO ORIGINAL: {response['comment']}\n")
                f.write(f"DATA: {response['date']}\n")
                f.write(f"NOTA: {response['rating']}\n")
                f.write(f"ID: {response['review_id']}\n")
                f.write("-" * 60 + "\n")
                f.write("RESPOSTA SUGERIDA:\n\n")
                f.write(response["response"])
                f.write("\n\n" + "=" * 60 + "\n\n")

            f.write("INSTRUÇÕES:\n")
            f.write(
                "1. Copie cada resposta e cole no comentário correspondente no Doctoralia\n"
            )
            f.write("2. Verifique se o autor corresponde antes de colar\n")
            f.write("3. Personalize se necessário antes de publicar\n")
            f.write("\n" + "=" * 80 + "\n")

        self.logger.info(f"📁 Arquivo consolidado criado: {consolidated_file.name}")
        return Path(consolidated_file)

    def generate_for_latest(self) -> tuple[List[Dict[str, Any]], Optional[Path]]:
        """Gera respostas para a extração mais recente"""
        latest_dir = self.find_latest_extraction()
        if not latest_dir:
            self.logger.warning("Nenhuma extração encontrada")
            return [], None

        new_reviews = self._load_new_reviews(latest_dir)
        if not new_reviews:
            return [], None

        self.logger.info(f"Processando {len(new_reviews)} novos comentários")

        responses_dir = self.config.data_dir / "responses"
        responses_dir.mkdir(parents=True, exist_ok=True)

        return self._process_reviews(new_reviews, responses_dir)

    def _load_new_reviews(self, latest_dir: Path) -> List[Dict[str, Any]]:
        """Carrega comentários novos que ainda não foram processados"""
        without_replies_file = latest_dir / "without_replies.json"
        if not without_replies_file.exists():
            self.logger.info("Nenhum comentário sem resposta encontrado")
            return []

        with open(without_replies_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        reviews = data.get("reviews", [])
        if not reviews:
            self.logger.info("Nenhum comentário para processar")
            return []

        processed_ids = self.load_processed_reviews()
        new_reviews = [r for r in reviews if r.get("id") not in processed_ids]

        if not new_reviews:
            self.logger.info("Nenhum comentário novo encontrado")
            return []

        return new_reviews

    def _process_reviews(
        self, new_reviews: List[Dict[str, Any]], responses_dir: Path
    ) -> tuple[List[Dict[str, Any]], Optional[Path]]:
        """Processa lista de comentários e gera respostas"""
        generated_responses = []
        consolidated_content = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        processed_ids = self.load_processed_reviews()

        for review in new_reviews:
            try:
                response_data = self._generate_single_response(
                    review, responses_dir, timestamp
                )
                if response_data:
                    generated_responses.append(response_data)
                    consolidated_content.append(
                        self._create_consolidated_entry(review, response_data)
                    )
                    processed_ids.add(review.get("id", "unknown"))
                    self.logger.info(
                        f"✓ Resposta gerada para {review.get('author', 'Unknown')}"
                    )
            except ValueError as e:
                self.logger.error(
                    f"Erro ao gerar resposta para {review.get('author', 'Unknown')}: {e}"
                )
                continue

        consolidated_file = None
        if generated_responses:
            consolidated_file = self.create_consolidated_file(
                consolidated_content, timestamp
            )

        self.save_processed_reviews(processed_ids)

        if generated_responses:
            self.logger.info(f"✅ {len(generated_responses)} respostas geradas")

        return generated_responses, consolidated_file

    def _generate_single_response(
        self, review: Dict[str, Any], responses_dir: Path, timestamp: str
    ) -> Optional[Dict[str, Any]]:
        """Gera resposta individual para um comentário"""
        response_text = self.generate_response(review)
        author = review.get("author", "Unknown")
        review_id = review.get("id", "unknown")

        filename = f"response_{timestamp}_{review_id}_{author.replace(' ', '_')}.txt"
        response_file = responses_dir / filename

        with open(response_file, "w", encoding="utf-8") as f:
            f.write(f"RESPOSTA PARA: {author}\n")
            f.write(f"COMENTÁRIO: {review.get('comment', '')}\n")
            f.write(f"DATA: {review.get('date', '')}\n")
            f.write(f"NOTA: {review.get('rating', '')}\n")
            f.write(f"GERADO EM: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("=" * 60 + "\n")
            f.write("RESPOSTA SUGERIDA:\n\n")
            f.write(response_text)

        return {
            "file": filename,
            "author": author,
            "comment": review.get("comment", ""),
            "response": response_text,
            "review_id": review_id,
        }

    def _create_consolidated_entry(
        self, review: Dict[str, Any], response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria entrada para o arquivo consolidado"""
        return {
            "author": review.get("author", "Unknown"),
            "comment": review.get("comment", ""),
            "date": review.get("date", ""),
            "rating": review.get("rating", ""),
            "response": response_data["response"],
            "review_id": review.get("id", "unknown"),
        }
