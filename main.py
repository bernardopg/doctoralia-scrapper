#!/usr/bin/env python3
"""
Doctoralia Bot - Interface Principal
Sistema completo para scraping e geração de respostas
"""

import argparse

from config.settings import AppConfig
from src.logger import setup_logger
from src.response_generator import ResponseGenerator
from src.scraper import DoctoraliaScraper
from src.telegram_notifier import TelegramNotifier


def print_banner() -> None:
    """Exibe banner do aplicativo"""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║                    🏥 DOCTORALIA BOT                         ║
║              Sistema de Respostas Automáticas                ║
╚══════════════════════════════════════════════════════════════╝
    """
    )


def setup_command(config: AppConfig) -> None:
    """Comando de configuração inicial"""
    print("🔧 Configuração Inicial")
    print("=" * 50)

    # Configurar Telegram
    print("\n📱 Configuração do Telegram (opcional)")
    print("Para receber notificações, você precisa:")
    print("1. Criar um bot com @BotFather")
    print("2. Obter o token do bot")
    print("3. Obter seu chat_id com @userinfobot")

    token = input("\n🤖 Token do bot (Enter para pular): ").strip()
    chat_id = input("💬 Chat ID (Enter para pular): ").strip()

    if token and chat_id:
        config.telegram.token = token
        config.telegram.chat_id = chat_id
        config.telegram.enabled = True
        print("✅ Telegram configurado!")

        # Testar configuração
        logger = setup_logger("setup", config)
        notifier = TelegramNotifier(config, logger)
        if notifier.send_message("🎉 Doctoralia Bot configurado!"):
            print("✅ Teste de notificação enviado!")
    else:
        print("⚠️ Telegram não configurado - notificações desabilitadas")

    # Configurar scraping
    print("\n🕷️ Configuração do Scraping")
    headless = input("Executar em modo headless? (S/n): ").strip().lower()
    config.scraping.headless = headless != "n"

    config.save()
    print("\n✅ Configuração salva!")


def scrape_command(config: AppConfig, args: argparse.Namespace) -> bool:
    """Comando de scraping"""
    logger = setup_logger("scraper", config, args.verbose)

    if not args.url:
        url = input("🔗 URL do médico no Doctoralia: ").strip()
    else:
        url = args.url

    if not url.startswith("https://www.doctoralia.com.br/"):
        logger.error("❌ URL deve ser do Doctoralia")
        return False

    logger.info("🚀 Iniciando scraping...")

    scraper = DoctoraliaScraper(config, logger)
    data = scraper.scrape_reviews(url)

    if not data:
        logger.error("❌ Falha no scraping")
        return False

    save_path = scraper.save_data(data)

    # Estatísticas
    total = data.get("total_reviews", 0)
    without_replies = len(
        [r for r in data.get("reviews", []) if not r.get("doctor_reply")]
    )

    logger.info(f"📊 Resumo: {total} comentários, {without_replies} sem resposta")

    # Notificar via Telegram se configurado
    if config.telegram.enabled:
        notifier = TelegramNotifier(config, logger)
        notifier.send_scraping_complete(data, save_path)

    return True


def generate_command(config: AppConfig, args: argparse.Namespace) -> None:
    """Comando de geração de respostas"""
    logger = setup_logger("generator", config, args.verbose)

    logger.info("🤖 Gerando respostas automáticas...")

    generator = ResponseGenerator(config, logger)
    responses, consolidated_file = generator.generate_for_latest()

    if responses:
        logger.info(f"✅ {len(responses)} respostas geradas")

        # Notificar via Telegram
        if config.telegram.enabled:
            notifier = TelegramNotifier(config, logger)
            if consolidated_file:
                notifier.send_responses_with_file(responses, consolidated_file)
            else:
                notifier.send_responses_generated(responses)
    else:
        logger.info("ℹ️ Nenhuma nova resposta necessária")


def status_command(config: AppConfig, args: argparse.Namespace) -> None:
    """Mostra status do sistema"""
    print("📊 STATUS DO SISTEMA")
    print("=" * 50)

    # Status das configurações
    telegram_status = (
        "✅ Configurado" if config.telegram.enabled else "❌ Não configurado"
    )
    print(f"� Telegram: {telegram_status}")

    scraping_mode = "Headless" if config.scraping.headless else "Com interface"
    print(f"🕷️ Scraping: {scraping_mode}")

    # Status dos dados
    extractions_dir = config.data_dir / "extractions"
    if extractions_dir.exists():
        extractions = list(extractions_dir.iterdir())
        print(f"📁 Extrações: {len(extractions)} pasta(s)")
        if extractions:
            latest = sorted(extractions, key=lambda x: x.name)[-1]
            print(f"📅 Última extração: {latest.name}")
    else:
        print("📁 Extrações: Nenhuma")

    responses_dir = config.data_dir / "responses"
    if responses_dir.exists():
        responses = list(responses_dir.glob("*.txt"))
        print(f"💬 Respostas geradas: {len(responses)} arquivo(s)")
    else:
        print("💬 Respostas geradas: Nenhuma")


def main() -> None:
    parser = argparse.ArgumentParser(description="Doctoralia Bot")
    parser.add_argument("-v", "--verbose", action="store_true", help="Modo verbose")

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # Comando setup
    subparsers.add_parser("setup", help="Configuração inicial")

    # Comando scrape
    scrape_parser = subparsers.add_parser("scrape", help="Fazer scraping")
    scrape_parser.add_argument("--url", help="URL do médico")

    # Comando generate
    subparsers.add_parser("generate", help="Gerar respostas")

    # Comando run (scrape + generate)
    run_parser = subparsers.add_parser("run", help="Executar workflow completo")
    run_parser.add_argument("--url", help="URL do médico")

    # Comando status
    subparsers.add_parser("status", help="Mostrar status do sistema")

    args = parser.parse_args()

    # Carregar configurações
    config = AppConfig.load()

    if not args.command:
        print_banner()
        print("Uso: python main.py <comando>")
        print("\nComandos disponíveis:")
        print("  setup     - Configuração inicial")
        print("  scrape    - Fazer scraping de comentários")
        print("  generate  - Gerar respostas automáticas")
        print("  run       - Executar workflow completo")
        print("  status    - Mostrar status do sistema")
        print("\nUse --help para mais informações")
        return

    if args.command == "setup":
        setup_command(config)
    elif args.command == "scrape":
        scrape_command(config, args)
    elif args.command == "generate":
        generate_command(config, args)
    elif args.command == "status":
        status_command(config, args)
    elif args.command == "run":
        print_banner()
        print("🚀 Executando workflow completo...")
        if scrape_command(config, args):
            generate_command(config, args)


if __name__ == "__main__":
    main()
