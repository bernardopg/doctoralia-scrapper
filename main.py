#!/usr/bin/env python3
"""
Doctoralia Scrapper - CLI Principal
===================================

Script principal para executar o scraper do Doctoralia via linha de comando.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Adicionar o diretório src ao path para imports
project_root = Path(__file__).parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from config.settings import AppConfig
from scripts.daemon import DaemonController
from scripts.health_check import HealthChecker as LegacyHealthChecker
from scripts.system_diagnostic import SystemDiagnostic
from src.api.v1.main import start_api
from src.dashboard import start_dashboard
from src.health_checker import HealthChecker  # Async health checker
from src.response_generator import ResponseGenerator
from src.scraper import DoctoraliaScraper
from src.telegram_notifier import TelegramNotifier

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/main.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class DoctoraliaCLI:
    """Interface de linha de comando para o Doctoralia Scrapper."""

    def __init__(self):
        self.config = AppConfig.load()

    def setup(self):
        """Configuração inicial do projeto."""
        logger.info("🔧 Iniciando configuração inicial...")

        # Criar diretórios necessários
        directories = [
            self.config.data_dir,
            Path("logs"),
            Path("backups"),
            Path("temp"),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Diretório criado: {directory}")

        # Verificar configuração
        # Validate configuration (method added in AppConfig)
        if not self.config.validate():
            logger.error("❌ Configuração inválida. Verifique o arquivo .env")
            sys.exit(1)

        logger.info("✅ Configuração inicial concluída!")

    def scrape(self, url: Optional[str] = None):
        """Executa scraping de avaliações."""
        if not url:
            logger.error("URL não fornecida. Use: --url <url>")
            sys.exit(1)

        logger.info(f"🚀 Iniciando scraping para: {url}")

        scraper = DoctoraliaScraper(self.config, logger)
        data = scraper.scrape_reviews(url)

        if data:
            logger.info(
                f"✅ Scraping concluído! {data.get('total_reviews', 0)} avaliações extraídas"
            )

            # Salvar dados
            file_path = scraper.save_data(data)
            if file_path:
                logger.info(f"💾 Dados salvos em: {file_path}")

            # Exibir resumo
            self._show_summary(data)
        else:
            logger.error("❌ Falha no scraping")
            sys.exit(1)

    def run(self, url: Optional[str] = None):
        """Executa workflow completo: scraping + geração de respostas."""
        if not url:
            logger.error("URL não fornecida. Use: --url <url>")
            sys.exit(1)

        logger.info(f"🚀 Executando workflow completo para: {url}")

        # 1. Scraping
        scraper = DoctoraliaScraper(self.config, logger)
        data = scraper.scrape_reviews(url)

        if not data:
            logger.error("❌ Falha no scraping")
            sys.exit(1)

        # 2. Geração de respostas
        if data.get("reviews"):
            logger.info("🤖 Gerando respostas para avaliações...")
            generator = ResponseGenerator(self.config, logger)

            # Filtrar avaliações sem resposta
            reviews_to_process = [
                review for review in data["reviews"] if not review.get("doctor_reply")
            ]

            if reviews_to_process:
                # The current ResponseGenerator supports batch processing through generate_for_latest.
                # For direct list processing, fall back to per-review generation.
                responses = [generator.generate_response(r) for r in reviews_to_process]

                # Adicionar respostas aos dados
                for review, response in zip(reviews_to_process, responses):
                    review["generated_response"] = response

                logger.info(f"✅ {len(responses)} respostas geradas")

                # Salvar dados atualizados
                file_path = scraper.save_data(data)
                if file_path:
                    logger.info(f"💾 Dados com respostas salvos em: {file_path}")
            else:
                logger.info("ℹ️ Todas as avaliações já possuem respostas")

        self._show_summary(data, show_responses=True)

    def generate(self):
        """Gera respostas para avaliações existentes."""
        logger.info("🤖 Iniciando geração de respostas...")

        # Buscar arquivos de dados recentes
        data_files = list(self.config.data_dir.glob("*.json"))
        if not data_files:
            logger.error("❌ Nenhum arquivo de dados encontrado")
            sys.exit(1)

        # Usar arquivo mais recente
        latest_file = max(data_files, key=lambda f: f.stat().st_mtime)
        logger.info(f"📁 Processando arquivo: {latest_file}")

        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data.get("reviews"):
            logger.info("ℹ️ Nenhuma avaliação para processar")
            return

        # Filtrar avaliações sem resposta
        reviews_to_process = [
            review for review in data["reviews"] if not review.get("doctor_reply")
        ]

        if not reviews_to_process:
            logger.info("ℹ️ Todas as avaliações já possuem respostas")
            return

        generator = ResponseGenerator(self.config, logger)
        responses = [generator.generate_response(r) for r in reviews_to_process]

        # Adicionar respostas
        for review, response in zip(reviews_to_process, responses):
            review["generated_response"] = response

        # Salvar arquivo atualizado
        output_file = latest_file.parent / f"{latest_file.stem}_with_responses.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ {len(responses)} respostas geradas e salvas em: {output_file}")

    def daemon(self, interval: int = 30, debug: bool = False):
        """Inicia o daemon de monitoramento."""
        logger.info(f"🔄 Iniciando daemon (intervalo: {interval}s, debug: {debug})")

        # Use existing DaemonController implementation
        controller = DaemonController()
        controller.start(interval_minutes=interval)

    def notify(self):
        """Envia notificações via Telegram."""
        logger.info("📱 Enviando notificações...")

        notifier = TelegramNotifier(self.config, logger)
        # Use existing generation cycle notification as a placeholder daily summary
        success = notifier.send_custom_message(
            title="Resumo Diário",
            content="Execução de notificação manual realizada.",
            emoji="📱",
        )

        if success:
            logger.info("✅ Notificações enviadas com sucesso")
        else:
            logger.error("❌ Falha ao enviar notificações")

    def health(self):
        """Verifica saúde do sistema."""
        logger.info("🏥 Verificando saúde do sistema...")

        # Prefer the async HealthChecker (src) if available
        try:
            import asyncio

            async_checker = HealthChecker(self.config)

            async def run_checks():
                results = await async_checker.check_all()
                # Summarize
                unhealthy = [k for k, v in results.items() if v.status != "healthy"]
                if not unhealthy:
                    logger.info("✅ Todos os componentes saudáveis")
                else:
                    logger.error("❌ Componentes com problemas:")
                    for name in unhealthy:
                        comp = results[name]
                        logger.error(
                            f"  - {name}: {comp.status} ({comp.details or 'sem detalhes'})"
                        )

            asyncio.run(run_checks())
        except Exception:
            # Fallback to legacy synchronous checker script
            legacy = LegacyHealthChecker()
            legacy.run_full_check()

    def diagnostic(self):
        """Executa diagnóstico completo."""
        logger.info("🔍 Executando diagnóstico completo...")

        diagnostic = SystemDiagnostic()
        report = diagnostic.run_full_diagnostic()

        logger.info("📊 Relatório de diagnóstico:")
        logger.info(json.dumps(report, indent=2, ensure_ascii=False))

    def dashboard(self):
        """Inicia dashboard web."""
        logger.info("🌐 Iniciando dashboard...")
        start_dashboard()

    def api(self):
        """Inicia API REST."""
        logger.info("🔌 Iniciando API REST...")
        start_api()

    def _show_summary(self, data: dict, show_responses: bool = False):
        """Exibe resumo dos dados extraídos."""
        logger.info("\n" + "=" * 50)
        logger.info("📊 RESUMO DA EXTRAÇÃO")
        logger.info("=" * 50)
        logger.info(f"👨‍⚕️ Médico: {data.get('doctor_name', 'N/A')}")
        logger.info(f"🔗 URL: {data.get('url', 'N/A')}")
        logger.info(f"📅 Extração: {data.get('extraction_timestamp', 'N/A')}")
        logger.info(f"💬 Total de avaliações: {data.get('total_reviews', 0)}")

        if show_responses and data.get("reviews"):
            with_responses = sum(
                1 for r in data["reviews"] if r.get("generated_response")
            )
            logger.info(f"🤖 Respostas geradas: {with_responses}")

        logger.info("=" * 50)

        # Mostrar amostra de avaliações
        if data.get("reviews"):
            logger.info("\n📋 Amostra de avaliações:")
            for i, review in enumerate(data["reviews"][:3]):
                logger.info(f"\n--- Avaliação {i + 1} ---")
                logger.info(f"Autor: {review.get('author', 'Anônimo')}")
                logger.info(f"Nota: {review.get('rating', 'N/A')}/5")
                logger.info(f"Data: {review.get('date', 'N/A')}")
                logger.info(f"Comentário: {review.get('comment', '')[:100]}...")
                if review.get("doctor_reply"):
                    logger.info(f"Resposta: {review.get('doctor_reply')[:100]}...")
                if show_responses and review.get("generated_response"):
                    logger.info(
                        f"Resposta gerada: {review.get('generated_response')[:100]}..."
                    )


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Doctoralia Scrapper - Ferramenta de scraping de avaliações médicas"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # Comando setup
    subparsers.add_parser("setup", help="Configuração inicial")

    # Comando scrape
    scrape_parser = subparsers.add_parser("scrape", help="Executa scraping")
    scrape_parser.add_argument("--url", help="URL do perfil do médico")

    # Comando run
    run_parser = subparsers.add_parser("run", help="Executa workflow completo")
    run_parser.add_argument("--url", required=True, help="URL do perfil do médico")

    # Comando generate
    subparsers.add_parser("generate", help="Gera respostas para avaliações")

    # Comando daemon
    daemon_parser = subparsers.add_parser("daemon", help="Inicia daemon")
    daemon_parser.add_argument(
        "--interval", type=int, default=30, help="Intervalo em segundos"
    )
    daemon_parser.add_argument("--debug", action="store_true", help="Modo debug")

    # Comando notify
    subparsers.add_parser("notify", help="Envia notificações")

    # Comando health
    subparsers.add_parser("health", help="Verifica saúde do sistema")

    # Comando diagnostic
    subparsers.add_parser("diagnostic", help="Executa diagnóstico")

    # Comando dashboard
    subparsers.add_parser("dashboard", help="Inicia dashboard web")

    # Comando api
    subparsers.add_parser("api", help="Inicia API REST")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = DoctoraliaCLI()

    try:
        if args.command == "setup":
            cli.setup()
        elif args.command == "scrape":
            cli.scrape(args.url)
        elif args.command == "run":
            cli.run(args.url)
        elif args.command == "generate":
            cli.generate()
        elif args.command == "daemon":
            cli.daemon(args.interval, args.debug)
        elif args.command == "notify":
            cli.notify()
        elif args.command == "health":
            cli.health()
        elif args.command == "diagnostic":
            cli.diagnostic()
        elif args.command == "dashboard":
            cli.dashboard()
        elif args.command == "api":
            cli.api()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Operação cancelada pelo usuário")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Erro inesperado: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
