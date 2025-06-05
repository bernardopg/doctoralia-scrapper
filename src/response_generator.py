import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.templates import QUALITY_KEYWORDS, RESPONSE_TEMPLATES


class ResponseGenerator:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.templates = RESPONSE_TEMPLATES
        self.quality_keywords = QUALITY_KEYWORDS
        self.processed_file = self.config.data_dir / "processed_reviews.json"

    def load_processed_reviews(self) -> set:
        """Carrega IDs dos comentários já processados"""
        if self.processed_file.exists():
            try:
                with open(self.processed_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("processed_ids", []))
            except Exception:
                return set()
        return set()

    def save_processed_reviews(self, processed_ids: set):
        """Salva IDs dos comentários processados"""
        self.processed_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "processed_ids": list(processed_ids),
            "last_updated": datetime.now().isoformat()
        }
        with open(self.processed_file, 'w', encoding='utf-8') as f:
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

    def generate_response(self, review: Dict[str, Any]) -> str:
        """Gera uma resposta personalizada para o comentário"""
        author = review.get('author', '')
        comment = review.get('comment', '')

        # Extrair nome para saudação
        first_name = self.extract_first_name(author)

        response_parts = []

        # 1. Saudação
        if first_name:
            greeting = random.choice([t for t in self.templates['saudacoes'] if '{nome}' in t])
            response_parts.append(greeting.format(nome=first_name))
        else:
            greeting = random.choice([t for t in self.templates['saudacoes'] if '{nome}' not in t])
            response_parts.append(greeting)

        # 2. Agradecimento
        thanks = random.choice(self.templates['agradecimentos'])
        response_parts.append(thanks)

        # 3. Resposta específica às qualidades mencionadas
        qualities = self.identify_mentioned_qualities(comment)
        if qualities:
            quality_response = self.templates['qualidades_mencionadas'].get(
                random.choice(qualities)
            )
            if quality_response:
                response_parts.append(quality_response)

        # 4. Expressão de satisfação
        satisfaction = random.choice(self.templates['satisfacao'])
        response_parts.append(satisfaction)

        # 5. Disponibilidade
        availability = random.choice(self.templates['disponibilidade'])
        response_parts.append(availability)

        # 6. Assinatura
        response_parts.append(self.templates['assinatura'])

        return ' '.join(response_parts)

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
        return latest_dir

    def create_consolidated_file(self, responses_data: List[Dict], timestamp: str) -> Path:
        """Cria arquivo consolidado com todas as respostas geradas"""
        responses_dir = self.config.data_dir / "responses"
        consolidated_file = responses_dir / f"respostas_consolidadas_{timestamp}.txt"

        with open(consolidated_file, 'w', encoding='utf-8') as f:
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
                f.write(response['response'])
                f.write("\n\n" + "=" * 60 + "\n\n")

            f.write("INSTRUÇÕES:\n")
            f.write("1. Copie cada resposta e cole no comentário correspondente no Doctoralia\n")
            f.write("2. Verifique se o autor corresponde antes de colar\n")
            f.write("3. Personalize se necessário antes de publicar\n")
            f.write("\n" + "=" * 80 + "\n")

        self.logger.info(f"📁 Arquivo consolidado criado: {consolidated_file.name}")
        return consolidated_file

    def generate_for_latest(self) -> tuple[List[Dict[str, Any]], Optional[Path]]:
        """Gera respostas para a extração mais recente"""
        latest_dir = self.find_latest_extraction()
        if not latest_dir:
            self.logger.warning("Nenhuma extração encontrada")
            return [], None

        # Procurar arquivo sem respostas
        without_replies_file = latest_dir / "without_replies.json"
        if not without_replies_file.exists():
            self.logger.info("Nenhum comentário sem resposta encontrado")
            return [], None

        with open(without_replies_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        reviews = data.get('reviews', [])
        if not reviews:
            self.logger.info("Nenhum comentário para processar")
            return [], None

        # Carregar comentários já processados
        processed_ids = self.load_processed_reviews()

        # Filtrar apenas novos comentários
        new_reviews = [r for r in reviews if r.get('id') not in processed_ids]

        if not new_reviews:
            self.logger.info("Nenhum comentário novo encontrado")
            return [], None

        self.logger.info(f"Processando {len(new_reviews)} novos comentários")

        # Criar pasta de respostas
        responses_dir = self.config.data_dir / "responses"
        responses_dir.mkdir(parents=True, exist_ok=True)

        generated_responses = []
        consolidated_content = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for review in new_reviews:
            try:
                # Gerar resposta
                response_text = self.generate_response(review)

                # Criar arquivo individual (mantém compatibilidade)
                author = review.get('author', 'Unknown')
                review_id = review.get('id', 'unknown')

                filename = f"response_{timestamp}_{review_id}_{author.replace(' ', '_')}.txt"
                response_file = responses_dir / filename

                # Salvar arquivo individual
                with open(response_file, 'w', encoding='utf-8') as f:
                    f.write(f"RESPOSTA PARA: {author}\n")
                    f.write(f"COMENTÁRIO: {review.get('comment', '')}\n")
                    f.write(f"DATA: {review.get('date', '')}\n")
                    f.write(f"NOTA: {review.get('rating', '')}\n")
                    f.write(f"GERADO EM: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n")
                    f.write("RESPOSTA SUGERIDA:\n\n")
                    f.write(response_text)

                # Adicionar ao arquivo consolidado
                consolidated_content.append({
                    'author': author,
                    'comment': review.get('comment', ''),
                    'date': review.get('date', ''),
                    'rating': review.get('rating', ''),
                    'response': response_text,
                    'review_id': review_id
                })

                response_data = {
                    'file': filename,
                    'author': author,
                    'comment': review.get('comment', ''),
                    'response': response_text,
                    'review_id': review_id
                }

                generated_responses.append(response_data)
                processed_ids.add(review_id)

                self.logger.info(f"✓ Resposta gerada para {author}")

            except Exception as e:
                self.logger.error(f"Erro ao gerar resposta para {review.get('author', 'Unknown')}: {e}")
                continue

        # Criar arquivo consolidado se houver respostas
        consolidated_file = None
        if generated_responses:
            consolidated_file = self.create_consolidated_file(consolidated_content, timestamp)

        # Salvar IDs processados
        self.save_processed_reviews(processed_ids)

        if generated_responses:
            self.logger.info(f"✅ {len(generated_responses)} respostas geradas")

        return generated_responses, consolidated_file