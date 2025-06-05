#!/usr/bin/env python3

import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import AppConfig
from src.logger import setup_logger
from src.response_generator import ResponseGenerator
from src.telegram_notifier import TelegramNotifier


class DaemonController:
    def __init__(self):
        self.running = True
        self.config = AppConfig.load()
        self.logger = setup_logger("daemon", self.config)
        self.notifier = None

        # Configurar handler para SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        # Inicializar notificador se Telegram estiver habilitado
        if self.config.telegram.enabled:
            self.notifier = TelegramNotifier(self.config, self.logger)

    def signal_handler(self, signum, frame):
        """Handler para sinais de interrupção"""
        self.logger.info("🛑 Sinal de interrupção recebido")
        self.running = False

    def send_notification(self, notification_type: str, **kwargs):
        """Método centralizado para envio de notificações"""
        if not self.notifier:
            return False

        try:
            if notification_type == "daemon_started":
                return self.notifier.send_daemon_started(kwargs.get('interval_minutes', 30))

            elif notification_type == "daemon_stopped":
                return self.notifier.send_daemon_stopped()

            elif notification_type == "generation_success":
                return self.notifier.send_generation_cycle_success(kwargs.get('responses', []))

            elif notification_type == "generation_success_with_file":
                return self.notifier.send_responses_with_file(
                    kwargs.get('responses', []),
                    kwargs.get('file_path')
                )

            elif notification_type == "generation_no_responses":
                return self.notifier.send_generation_cycle_no_responses()

            elif notification_type == "daemon_error":
                return self.notifier.send_daemon_error(
                    kwargs.get('error_message', ''),
                    kwargs.get('context', 'Daemon de geração automática')
                )

            elif notification_type == "custom":
                return self.notifier.send_custom_message(
                    kwargs.get('title', 'Notificação'),
                    kwargs.get('content', ''),
                    kwargs.get('emoji', '📢')
                )

            else:
                self.logger.warning(f"Tipo de notificação desconhecido: {notification_type}")
                return False

        except Exception as e:
            self.logger.error(f"Erro ao enviar notificação: {e}")
            return False

    def run_generation_cycle(self):
        """Executa um ciclo de geração de respostas"""
        try:
            self.logger.info("🤖 Iniciando ciclo de geração automática")

            generator = ResponseGenerator(self.config, self.logger)
            responses, consolidated_file = generator.generate_for_latest()

            if responses:
                self.logger.info(f"✅ {len(responses)} novas respostas geradas")
                # Enviar notificação de sucesso com arquivo anexado
                if consolidated_file:
                    self.send_notification("generation_success_with_file", responses=responses, file_path=consolidated_file)
                else:
                    self.send_notification("generation_success", responses=responses)
            else:
                self.logger.info("ℹ️ Nenhuma nova resposta necessária")
                # Enviar notificação de nenhuma resposta nova
                self.send_notification("generation_no_responses")

        except Exception as e:
            self.logger.error(f"❌ Erro no ciclo de geração: {e}")
            # Enviar notificação de erro
            self.send_notification("daemon_error",
                                 error_message=str(e),
                                 context="Ciclo de geração automatica")

    def start(self, interval_minutes: int = 30):
        """Inicia o daemon com intervalo especificado"""
        self.logger.info(f"🔄 Daemon iniciado - execução a cada {interval_minutes} minutos")
        self.logger.info("Pressione Ctrl+C para parar")

        # Agendar execução
        schedule.every(interval_minutes).minutes.do(self.run_generation_cycle)

        # Enviar notificação de início
        self.send_notification("daemon_started", interval_minutes=interval_minutes)

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Verifica a cada minuto
        except KeyboardInterrupt:
            pass
        finally:
            self.logger.info("🛑 Daemon finalizado")
            # Enviar notificação de parada
            self.send_notification("daemon_stopped")

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    🤖 DAEMON AUTOMÁTICO                      ║
║              Geração Automática de Respostas                ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Verificar se há argumentos de linha de comando
    interval = 30  # padrão: 30 minutos

    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
            if interval < 1:
                print("❌ Intervalo deve ser pelo menos 1 minuto")
                sys.exit(1)
        except ValueError:
            print("❌ Intervalo deve ser um número inteiro (minutos)")
            sys.exit(1)

    # Criar e iniciar daemon
    daemon = DaemonController()
    daemon.start(interval)

if __name__ == "__main__":
    main()