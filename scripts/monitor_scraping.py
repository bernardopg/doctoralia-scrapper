#!/usr/bin/env python3
"""
Script para monitorar o desempenho e recursos durante o scraping
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

# Adicionar o diretório raiz do projeto ao path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import AppConfig  # noqa: E402
from src.logger import setup_logger  # noqa: E402


class ScrapingMonitor:
    def __init__(self) -> None:
        self.config = AppConfig.load()
        self.logger = setup_logger("monitor", self.config)
        self.start_time: Optional[float] = None
        self.process = None

    def get_chrome_processes(self) -> List[psutil.Process]:
        """Encontra todos os processos do Chrome/Chromium"""
        chrome_processes = []
        for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
            try:
                if proc.info["name"] and any(
                    name in proc.info["name"].lower()
                    for name in ["chrome", "chromium", "chromedriver"]
                ):
                    chrome_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return chrome_processes

    def log_system_resources(self) -> None:
        """Log dos recursos do sistema"""
        # CPU e memória geral
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        self.logger.info(
            f"💻 Sistema - CPU: {cpu_percent}% | RAM: {memory.percent}% ({memory.available // (1024**3)}GB livre)"
        )

        # Processos do Chrome
        chrome_procs = self.get_chrome_processes()
        if chrome_procs:
            total_memory = sum(
                proc.info["memory_info"].rss for proc in chrome_procs
            ) / (1024**2)
            self.logger.info(
                f"🌐 Chrome - {len(chrome_procs)} processos | Memória total: {total_memory:.1f}MB"
            )

            for proc in chrome_procs[:3]:  # Mostrar só os 3 primeiros
                try:
                    mem_mb = proc.info["memory_info"].rss / (1024**2)
                    self.logger.info(
                        f"   PID {proc.info['pid']}: {proc.info['name']} - {mem_mb:.1f}MB"
                    )
                except Exception:
                    continue

    def monitor_continuously(self, interval: int = 30) -> None:
        """Monitor contínuo durante o scraping"""
        self.logger.info("🔍 Iniciando monitoramento de recursos...")
        self.start_time = time.time()

        try:
            while True:
                self.log_system_resources()

                # Log de tempo decorrido
                elapsed = time.time() - self.start_time
                self.logger.info(f"⏱️ Tempo decorrido: {elapsed / 60:.1f} minutos")

                time.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info("🛑 Monitoramento interrompido pelo usuário")
        except Exception as e:
            self.logger.error(f"❌ Erro no monitoramento: {e}")

    def get_memory_report(self) -> Dict[str, Any]:
        """Gera relatório de uso de memória"""
        report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory": dict(psutil.virtual_memory()._asdict()),
                "disk": dict(psutil.disk_usage("/")._asdict()),
            },
            "chrome_processes": [],
        }

        for proc in self.get_chrome_processes():
            try:
                proc_info = {
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "memory_mb": proc.info["memory_info"].rss / (1024**2),
                    "cpu_percent": proc.info["cpu_percent"],
                }
                report["chrome_processes"].append(proc_info)
            except Exception:
                continue

        return report

    def cleanup_chrome_processes(self) -> None:
        """Limpa processos órfãos do Chrome"""
        self.logger.info("🧹 Limpando processos órfãos do Chrome...")

        chrome_procs = self.get_chrome_processes()
        if not chrome_procs:
            self.logger.info("✅ Nenhum processo do Chrome encontrado")
            return

        for proc in chrome_procs:
            try:
                self.logger.info(
                    f"🔄 Terminando processo {proc.info['pid']}: {proc.info['name']}"
                )
                proc.terminate()
                proc.wait(timeout=10)
            except psutil.TimeoutExpired:
                self.logger.warning(
                    f"⚠️ Forçando encerramento do processo {proc.info['pid']}"
                )
                proc.kill()
            except Exception as e:
                self.logger.error(
                    f"❌ Erro ao encerrar processo {proc.info['pid']}: {e}"
                )

        self.logger.info("✅ Limpeza concluída")


def main() -> None:
    monitor = ScrapingMonitor()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "monitor":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            monitor.monitor_continuously(interval)
        elif command == "report":
            import json

            report = monitor.get_memory_report()
            print(json.dumps(report, indent=2))
        elif command == "cleanup":
            monitor.cleanup_chrome_processes()
        else:
            print("Comandos disponíveis: monitor, report, cleanup")
    else:
        print("Uso: python monitor_scraping.py <command>")
        print("Comandos:")
        print("  monitor [interval] - Monitor contínuo (padrão: 30s)")
        print("  report            - Relatório atual de recursos")
        print("  cleanup           - Limpar processos órfãos do Chrome")


if __name__ == "__main__":
    main()
