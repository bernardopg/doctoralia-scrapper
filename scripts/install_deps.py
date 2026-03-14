#!/usr/bin/env python3
"""
Script para instalar dependências do projeto
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command: str, description: str) -> bool:
    """Executa comando e exibe resultado"""
    print(f"\n🔧 {description}")
    print("=" * 50)

    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ {description} - Sucesso")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Erro")
        if e.stderr:
            print(e.stderr)
        return False


def install_python_packages() -> bool:
    """Instala pacotes Python"""
    requirements_file = Path(__file__).parent.parent / "requirements.txt"

    if not requirements_file.exists():
        print("❌ Arquivo requirements.txt não encontrado")
        return False

    command = f"{sys.executable} -m pip install -r {requirements_file}"
    return run_command(command, "Instalando pacotes Python")


def install_chromedriver_ubuntu() -> bool:
    """Instala ChromeDriver no Ubuntu/Debian"""
    commands = [
        ("sudo apt update", "Atualizando repositórios"),
        ("sudo apt install -y chromium-chromedriver", "Instalando ChromeDriver"),
        ("sudo apt install -y chromium-browser", "Instalando Chromium"),
    ]

    success = True
    for command, description in commands:
        if not run_command(command, description):
            success = False

    return success


def check_installation() -> bool:
    """Verifica se a instalação foi bem-sucedida"""
    print("\n🔍 VERIFICANDO INSTALAÇÃO")
    print("=" * 50)

    # Verificar pacotes Python
    required_packages = ["selenium", "beautifulsoup4", "requests", "lxml"]
    python_ok = True

    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ Python: {package}")
        except ImportError:
            print(f"❌ Python: {package}")
            python_ok = False

    # Verificar ChromeDriver
    chromedriver_paths = ["/usr/bin/chromedriver", "/usr/local/bin/chromedriver"]

    chromedriver_ok = False
    for path in chromedriver_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            print(f"✅ ChromeDriver: {path}")
            chromedriver_ok = True
            break

    if not chromedriver_ok:
        print("❌ ChromeDriver não encontrado")

    return python_ok and chromedriver_ok


def main() -> bool:
    print("""
╔══════════════════════════════════════════════════════════════╗
║                 📦 INSTALAÇÃO DE DEPENDÊNCIAS                ║
║                    Doctoralia Bot Setup                      ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print("Este script irá instalar:")
    print("• Pacotes Python necessários")
    print("• ChromeDriver (Ubuntu/Debian)")
    print("• Chromium Browser")

    choice = input("\nContinuar? (S/n): ").strip().lower()
    if choice == "n":
        print("❌ Instalação cancelada")
        return False

    success = True

    # Instalar pacotes Python
    if not install_python_packages():
        success = False

    # Detectar sistema operacional e instalar ChromeDriver
    if sys.platform.startswith("linux"):
        if not install_chromedriver_ubuntu():
            success = False
    else:
        print("\n⚠️ Sistema operacional não suportado para instalação automática")
        print("Instale manualmente:")
        print("• Chrome ou Chromium")
        print("• ChromeDriver compatível")

    # Verificar instalação
    if check_installation():
        print("\n🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!")
        print("Execute agora: python scripts/setup.py")
    else:
        print("\n❌ INSTALAÇÃO INCOMPLETA")
        print("Verifique os erros acima e instale manualmente se necessário")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
