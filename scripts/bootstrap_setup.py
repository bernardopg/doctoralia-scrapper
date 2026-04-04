#!/usr/bin/env python3
"""
Script de configuração inicial do Doctoralia Bot
"""

import os
import sys
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import depois do path insert para evitar E402
from config.settings import AppConfig  # noqa: E402


def print_banner() -> None:
    print("""
╔══════════════════════════════════════════════════════════════╗
║                 🔧 CONFIGURAÇÃO INICIAL                      ║
║                  Doctoralia Bot Setup                        ║
╚══════════════════════════════════════════════════════════════╝
    """)


def setup_directories(config: AppConfig) -> None:
    """Cria estrutura de diretórios necessária"""
    directories = [
        config.data_dir,
        config.data_dir / "extractions",
        config.data_dir / "responses",
        config.data_dir / "logs",
        config.base_dir / "config",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ Diretório criado: {directory}")


def setup_telegram(config: AppConfig) -> None:
    """Configura integração com Telegram"""
    print("\n📱 CONFIGURAÇÃO DO TELEGRAM")
    print("=" * 50)
    print("Para receber notificações automáticas, você precisa:")
    print("1. Criar um bot no Telegram com @BotFather")
    print("2. Obter o token do bot")
    print("3. Obter seu chat_id com @userinfobot")
    print("4. (Opcional) Você pode pular esta etapa")

    token = input("\n🤖 Token do bot Telegram (Enter para pular): ").strip()
    chat_id = input("💬 Chat ID do Telegram (Enter para pular): ").strip()

    if token and chat_id:
        config.telegram.token = token
        config.telegram.chat_id = chat_id
        config.telegram.enabled = True
        print("✅ Telegram configurado com sucesso!")

        # Testar configuração do Telegram
        from src.logger import setup_logger  # noqa: E402
        from src.telegram_notifier import TelegramNotifier  # noqa: E402

        logger = setup_logger("setup", config)
        notifier = TelegramNotifier(config, logger)

        print("\n🔧 Validando configuração do Telegram...")
        validation = notifier.validate_config()

        if validation["valid"]:
            print("✅ Configuração válida!")
            print("🔗 Testando conexão...")
            if notifier.test_connection():
                print("✅ Conexão estabelecida com sucesso!")
                if notifier.send_message("🎉 Doctoralia Bot configurado com sucesso!"):
                    print("✅ Teste de notificação enviado!")
                else:
                    print("⚠️ Erro no envio de teste - verifique permissões do bot")
            else:
                print("❌ Erro na conexão - verifique token e chat_id")
                config.telegram.enabled = False
        else:
            print("❌ Problemas na configuração:")
            for issue in validation["issues"]:
                print(f"   - {issue}")
            config.telegram.enabled = False
    else:
        print("⚠️ Telegram não configurado - notificações desabilitadas")


def setup_scraping(config: AppConfig) -> None:
    """Configura opções de scraping"""
    print("\n🕷️ CONFIGURAÇÃO DO SCRAPING")
    print("=" * 50)

    headless = input("Executar navegador em modo headless? (S/n): ").strip().lower()
    config.scraping.headless = headless != "n"

    if config.scraping.headless:
        print("✅ Modo headless ativado (sem interface gráfica)")
    else:
        print("✅ Modo com interface gráfica ativado")

    # Timeout
    try:
        timeout = input(
            f"Timeout para carregamento (atual: {config.scraping.timeout}s, Enter para manter): "
        ).strip()
        if timeout:
            config.scraping.timeout = int(timeout)
    except ValueError:
        print("⚠️ Valor inválido, mantendo configuração atual")


def check_dependencies() -> bool:
    """Verifica se as dependências estão instaladas"""
    print("\n🔍 VERIFICANDO DEPENDÊNCIAS")
    print("=" * 50)

    # Mapeamento módulo -> nome do pacote
    required_packages = {
        "selenium": "selenium",
        "bs4": "beautifulsoup4",
        "requests": "requests",
        "lxml": "lxml",
    }

    missing_packages = []

    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
            print(f"✅ {package_name}")
        except ImportError:
            print(f"❌ {package_name}")
            missing_packages.append(package_name)

    if missing_packages:
        print(f"\n⚠️ Pacotes em falta: {', '.join(missing_packages)}")
        print("Execute: pip install -r requirements.txt")
        return False
    else:
        print("\n✅ Todas as dependências estão instaladas!")
        return True


def check_chromedriver() -> bool:
    """Verifica se o ChromeDriver está disponível"""
    print("\n🌐 VERIFICANDO CHROMEDRIVER")
    print("=" * 50)

    chromedriver_paths = ["/usr/bin/chromedriver", "/usr/local/bin/chromedriver"]

    found = False
    for path in chromedriver_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            print(f"✅ ChromeDriver encontrado: {path}")
            found = True
            break

    if not found:
        print("❌ ChromeDriver não encontrado")
        print("Instale com:")
        print("  Ubuntu/Debian: sudo apt install chromium-chromedriver")
        print("  ou baixe de: https://chromedriver.chromium.org/")
        return False

    return True


def main() -> bool:
    print_banner()

    # Carregar configurações
    config = AppConfig.load()

    # Verificar dependências
    if not check_dependencies():
        print("\n❌ Configure as dependências antes de continuar")
        return False

    if not check_chromedriver():
        print("\n❌ Configure o ChromeDriver antes de continuar")
        return False

    # Criar diretórios
    print("\n📁 CRIANDO ESTRUTURA DE DIRETÓRIOS")
    print("=" * 50)
    setup_directories(config)

    # Configurar Telegram
    setup_telegram(config)

    # Configurar scraping
    setup_scraping(config)

    # Salvar configurações
    config.save()

    print("\n🎉 CONFIGURAÇÃO CONCLUÍDA!")
    print("=" * 50)
    print("Próximos passos:")
    print("1. Execute: python main.py scrape --url <URL_DO_MEDICO>")
    print("2. Execute: python main.py generate")
    print("3. Ou execute tudo: python main.py run --url <URL_DO_MEDICO>")
    print("\nPara ajuda: python main.py --help")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
