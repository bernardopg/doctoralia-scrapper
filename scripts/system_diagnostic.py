#!/usr/bin/env python3
"""
Script de diagnóstico para verificar configuração do sistema
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Adicionar o diretório raiz do projeto ao path
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import AppConfig


class SystemDiagnostic:
    def __init__(self):
        self.config = AppConfig.load()
        self.issues = []
        self.warnings = []

    def check_chrome_installation(self):
        """Verifica instalação do Chrome/Chromium"""
        print("🔍 Verificando instalação do Chrome...")

        chrome_commands = ['google-chrome', 'chromium-browser', 'chromium', 'chrome']
        chrome_found = False

        for cmd in chrome_commands:
            if shutil.which(cmd):
                try:
                    result = subprocess.run([cmd, '--version'],
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        print(f"✅ Chrome encontrado: {result.stdout.strip()}")
                        chrome_found = True
                        break
                except:
                    continue

        if not chrome_found:
            self.issues.append("Chrome/Chromium não encontrado")
            print("❌ Chrome/Chromium não encontrado")
            print("💡 Instale com: sudo apt install chromium-browser")

    def check_chromedriver(self):
        """Verifica ChromeDriver"""
        print("\n🔍 Verificando ChromeDriver...")

        chromedriver_paths = [
            "/usr/bin/chromedriver",
            "/usr/local/bin/chromedriver",
            shutil.which("chromedriver")
        ]

        driver_found = False
        for path in chromedriver_paths:
            if path and os.path.exists(path) and os.access(path, os.X_OK):
                try:
                    result = subprocess.run([path, '--version'],
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        print(f"✅ ChromeDriver encontrado: {result.stdout.strip()}")
                        print(f"   Localização: {path}")
                        driver_found = True
                        break
                except:
                    continue

        if not driver_found:
            self.issues.append("ChromeDriver não encontrado ou não executável")
            print("❌ ChromeDriver não encontrado")
            print("💡 Baixe em: https://chromedriver.chromium.org/")
            print("💡 Ou instale com: sudo apt install chromium-chromedriver")

    def check_memory(self):
        """Verifica memória disponível"""
        print("\n🔍 Verificando recursos do sistema...")

        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_gb = memory.total / (1024**3)
            available_gb = memory.available / (1024**3)

            print(f"💾 Memória total: {memory_gb:.1f}GB")
            print(f"💾 Memória disponível: {available_gb:.1f}GB ({memory.percent}% usado)")

            if available_gb < 1:
                self.warnings.append(f"Pouca memória disponível: {available_gb:.1f}GB")
                print("⚠️ Pouca memória disponível - pode causar timeouts")
            elif available_gb < 2:
                self.warnings.append(f"Memória limitada: {available_gb:.1f}GB")
                print("⚠️ Memória limitada - considere fechar outras aplicações")
            else:
                print("✅ Memória suficiente")

        except ImportError:
            self.warnings.append("psutil não disponível para verificar memória")

    def check_network(self):
        """Verifica conectividade"""
        print("\n🔍 Verificando conectividade...")

        try:
            import urllib.request
            urllib.request.urlopen('https://www.doctoralia.com.br', timeout=10)
            print("✅ Conectividade com Doctoralia OK")
        except Exception as e:
            self.issues.append(f"Problema de conectividade: {e}")
            print(f"❌ Erro de conectividade: {e}")

    def check_permissions(self):
        """Verifica permissões de arquivo"""
        print("\n🔍 Verificando permissões...")

        # Verificar diretórios necessários
        dirs_to_check = [
            self.config.data_dir,
            self.config.logs_dir,
            self.config.data_dir / "extractions",
            self.config.data_dir / "responses"
        ]

        for dir_path in dirs_to_check:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                # Testar escrita
                test_file = dir_path / "test_write.tmp"
                test_file.write_text("test")
                test_file.unlink()
                print(f"✅ Permissões OK: {dir_path}")
            except Exception as e:
                self.issues.append(f"Erro de permissão em {dir_path}: {e}")
                print(f"❌ Erro de permissão: {dir_path}")

    def check_dependencies(self):
        """Verifica dependências Python"""
        print("\n🔍 Verificando dependências Python...")

        required_packages = [
            ('selenium', 'selenium'),
            ('beautifulsoup4', 'bs4'),
            ('requests', 'requests'),
            ('psutil', 'psutil')
        ]

        for package_name, import_name in required_packages:
            try:
                __import__(import_name)
                print(f"✅ {package_name}")
            except ImportError:
                self.issues.append(f"Pacote não encontrado: {package_name}")
                print(f"❌ {package_name} não encontrado")

    def test_simple_scraping(self):
        """Teste simples de scraping"""
        print("\n🔍 Testando configuração básica do Selenium...")

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")

            # Tentar encontrar chromedriver
            chromedriver_paths = [
                "/usr/bin/chromedriver",
                "/usr/local/bin/chromedriver",
                "chromedriver"
            ]

            driver = None
            for path in chromedriver_paths:
                try:
                    service = Service(path)
                    driver = webdriver.Chrome(service=service, options=options)
                    break
                except Exception:
                    continue

            if not driver:
                self.issues.append("Falha ao inicializar WebDriver")
                print("❌ Falha ao inicializar WebDriver")
                return

            # Teste simples
            driver.get("https://www.google.com")
            print("✅ Teste básico do Selenium OK")

            driver.quit()
            print("✅ Encerramento do driver OK")

        except Exception as e:
            self.issues.append(f"Erro no teste do Selenium: {e}")
            print(f"❌ Erro no teste do Selenium: {e}")

    def print_configuration(self):
        """Mostra configuração atual"""
        print("\n📋 Configuração atual:")
        print(f"   Timeout: {self.config.scraping.timeout}s")
        print(f"   Page Load Timeout: {self.config.scraping.page_load_timeout}s")
        print(f"   Implicit Wait: {self.config.scraping.implicit_wait}s")
        print(f"   Explicit Wait: {self.config.scraping.explicit_wait}s")
        print(f"   Max Retries: {self.config.scraping.max_retries}")
        print(f"   Delay: {self.config.scraping.delay_min}-{self.config.scraping.delay_max}s")
        print(f"   Headless: {self.config.scraping.headless}")

    def run_full_diagnostic(self):
        """Executa diagnóstico completo"""
        print("🏥 DIAGNÓSTICO DO SISTEMA DOCTORALIA SCRAPER")
        print("=" * 50)

        self.check_dependencies()
        self.check_chrome_installation()
        self.check_chromedriver()
        self.check_memory()
        self.check_network()
        self.check_permissions()
        self.test_simple_scraping()
        self.print_configuration()

        print("\n" + "=" * 50)
        print("📊 RESUMO DO DIAGNÓSTICO")

        if not self.issues and not self.warnings:
            print("✅ Sistema configurado corretamente!")
        else:
            if self.issues:
                print(f"❌ {len(self.issues)} problema(s) crítico(s) encontrado(s):")
                for issue in self.issues:
                    print(f"   • {issue}")

            if self.warnings:
                print(f"⚠️ {len(self.warnings)} aviso(s):")
                for warning in self.warnings:
                    print(f"   • {warning}")

        print("\n💡 Próximos passos:")
        if self.issues:
            print("   1. Corrija os problemas críticos listados acima")
            print("   2. Execute o diagnóstico novamente")
        else:
            print("   1. Tente executar o scraping normalmente")
            print("   2. Use 'python scripts/monitor_scraping.py monitor' para monitorar recursos")


def main():
    diagnostic = SystemDiagnostic()
    diagnostic.run_full_diagnostic()


if __name__ == "__main__":
    main()
