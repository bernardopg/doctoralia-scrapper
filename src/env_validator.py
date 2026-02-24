"""
Validação de variáveis de ambiente obrigatórias na inicialização
"""

import os
import sys
from typing import Dict, List


class EnvironmentValidationError(Exception):
    """Exceção levantada quando validação de .env falha"""

    def __init__(self, missing_vars: List[str], error_message: str = ""):
        self.missing_vars = missing_vars
        self.error_message = error_message
        super().__init__(
            f"Environment validation failed. Missing variables: {', '.join(missing_vars)}. {error_message}"
        )


class EnvironmentValidator:
    """Valida variáveis de ambiente obrigatórias e opcionais"""

    # Variáveis obrigatórias para cada serviço
    REQUIRED_VARS: Dict[str, List[str]] = {
        "api": ["API_KEY", "WEBHOOK_SIGNING_SECRET"],
        "worker": ["REDIS_URL"],
        "shared": ["REDIS_URL", "SELENIUM_REMOTE_URL"],
    }

    # Variáveis opcionais com valores padrão
    OPTIONAL_VARS: Dict[str, str] = {
        "REDIS_URL": "redis://localhost:6379/0",
        "SELENIUM_REMOTE_URL": "http://localhost:4444/wd/hub",
        "LOG_LEVEL": "INFO",
        "MASK_PII": "true",
        "DEBUG": "true",
    }

    @staticmethod
    def validate_for_service(service: str = "shared") -> Dict[str, str]:
        """
        Valida variáveis de ambiente para um serviço específico.

        Args:
            service: "api", "worker", ou "shared"

        Returns:
            Dicionário com todas as variáveis carregadas (obrigatórias + opcionais)

        Raises:
            EnvironmentValidationError: Se variáveis obrigatórias estão faltando
        """
        # Obter lista de variáveis obrigatórias para o serviço
        required = EnvironmentValidator.REQUIRED_VARS.get(service, [])

        # Verificar variáveis obrigatórias
        missing_vars = []
        loaded_vars = {}

        for var in required:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                loaded_vars[var] = value

        if missing_vars:
            raise EnvironmentValidationError(
                missing_vars,
                f"Service '{service}' requires these environment variables.",
            )

        # Carregar variáveis opcionais com padrões
        for var, default in EnvironmentValidator.OPTIONAL_VARS.items():
            value = os.getenv(var, default)
            loaded_vars[var] = value

        return loaded_vars

    @staticmethod
    def validate_all() -> Dict[str, str]:
        """
        Valida todas as variáveis de ambiente obrigatórias e opcionais.

        Returns:
            Dicionário com todas as variáveis carregadas

        Raises:
            EnvironmentValidationError: Se variáveis obrigatórias estão faltando
        """
        all_required = set()
        for vars_list in EnvironmentValidator.REQUIRED_VARS.values():
            all_required.update(vars_list)

        # Verificar variáveis obrigatórias
        missing_vars = []
        loaded_vars = {}

        for var in all_required:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                loaded_vars[var] = value

        if missing_vars:
            raise EnvironmentValidationError(
                missing_vars,
                "Please set these environment variables before running the application.",
            )

        # Carregar variáveis opcionais com padrões
        for var, default in EnvironmentValidator.OPTIONAL_VARS.items():
            value = os.getenv(var, default)
            loaded_vars[var] = value

        return loaded_vars

    @staticmethod
    def print_startup_validation(service: str = "api") -> None:
        """
        Imprime validação de startup de forma legível.

        Args:
            service: Nome do serviço ("api", "worker", "dashboard", etc.)
        """
        print(f"\n{'='*60}")
        print(f"Environment Validation for {service.upper()}")
        print(f"{'='*60}\n")

        try:
            vars_loaded = EnvironmentValidator.validate_for_service(service)

            print("✅ All required environment variables are set!\n")
            print(f"Loaded {len(vars_loaded)} variables:")
            for key, value in sorted(vars_loaded.items()):
                # Mascarar valores sensíveis
                if any(
                    sensitive in key.upper()
                    for sensitive in ["KEY", "SECRET", "TOKEN", "PASSWORD"]
                ):
                    display_value = "***" + value[-4:] if len(value) > 4 else "***"
                else:
                    display_value = value

                print(f"  • {key}: {display_value}")

            print(f"\n{'='*60}\n")
            return

        except EnvironmentValidationError as e:
            print("❌ Environment validation failed!\n")
            print(f"Error: {e.error_message}")
            print(f"\nMissing variables: {', '.join(e.missing_vars)}")
            print("\nPlease set these environment variables and try again.")
            print("Tip: Create a .env file in the project root with these variables.\n")
            print(f"{'='*60}\n")
            sys.exit(1)


if __name__ == "__main__":
    # Test validation
    try:
        EnvironmentValidator.print_startup_validation("api")
    except EnvironmentValidationError as e:
        print(f"Validation error: {e}")
        sys.exit(1)
