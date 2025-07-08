import json
import os
from pathlib import Path

from config.settings import AppConfig


class TestAppConfig:
    """Testes para a classe AppConfig"""

    def test_config_loading(self):
        """Testa se a configuração é carregada corretamente"""
        config = AppConfig.load()
        assert config is not None
        assert hasattr(config, "telegram")
        assert hasattr(config, "scraping")

    def test_config_file_exists(self):
        """Verifica se o arquivo de configuração existe"""
        config_path = Path("config/config.json")
        assert config_path.exists() or Path("config/config.example.json").exists()

    def test_config_json_format(self):
        """Verifica se o arquivo de configuração está em formato JSON válido"""
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert isinstance(data, dict)

    def test_environment_variables(self):
        """Testa se as variáveis de ambiente necessárias podem ser definidas"""
        # Testa se podemos definir uma variável de ambiente
        test_var = "TEST_TELEGRAM_TOKEN"
        test_value = "test_token_123"

        os.environ[test_var] = test_value
        assert os.environ.get(test_var) == test_value

        # Limpa a variável de teste
        del os.environ[test_var]
