# Makefile para Doctoralia Scrapper
# ===================================

.PHONY: help install setup test lint run daemon monitor clean

# Variáveis
PYTHON := python3
PIP := pip3
SRC_DIR := src
TEST_DIR := tests

# Cores para output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Help
help: ## Mostra esta mensagem de ajuda
	@echo "$(BLUE)Doctoralia Scrapper - Comandos Disponíveis$(NC)"
	@echo "========================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Instalação e Configuração
install: ## Instala dependências de produção
	@echo "$(BLUE)Instalando dependências...$(NC)"
	$(PIP) install -r requirements.txt

install-dev: ## Instala dependências completas + setup do ambiente
	@echo "$(BLUE)Instalando dependências de desenvolvimento...$(NC)"
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-mock black isort mypy flake8 pylint bandit safety pre-commit
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Criando arquivo .env...$(NC)"; \
		cp .env.example .env; \
		echo "$(GREEN)Arquivo .env criado! Edite-o com suas configurações.$(NC)"; \
	fi
	$(PYTHON) main.py setup
	@echo "$(GREEN)Configuração de desenvolvimento concluída!$(NC)"

setup: ## Executa configuração inicial do projeto
	@echo "$(BLUE)Configurando projeto...$(NC)"
	$(PYTHON) main.py setup

# Testes e Qualidade
test: ## Executa todos os testes com cobertura
	@echo "$(BLUE)Executando testes...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing

test-html: ## Executa testes com relatório HTML
	@echo "$(BLUE)Executando testes com cobertura HTML...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term
	@echo "$(GREEN)Relatório de cobertura salvo em htmlcov/index.html$(NC)"

lint: ## Executa linting, formatação e verificação de segurança
	@echo "$(BLUE)Formatando código...$(NC)"
	black .
	isort .
	@echo "$(BLUE)Executando linting...$(NC)"
	flake8 $(SRC_DIR) --extend-ignore=E203 --max-line-length=120
	pylint $(SRC_DIR) --disable=C0114,C0115,C0116
	mypy $(SRC_DIR) --ignore-missing-imports
	@echo "$(BLUE)Verificando segurança...$(NC)"
	bandit -r $(SRC_DIR)
	safety check --file requirements.txt

check: ## Verifica formatação sem alterar arquivos
	@echo "$(BLUE)Verificando formatação...$(NC)"
	black --check .
	isort --check-only .

# Execução
run: ## Executa scraping uma vez
	@echo "$(BLUE)Executando scraping...$(NC)"
	$(PYTHON) main.py scrape

run-url: ## Executa scraping com URL específica (uso: make run-url URL=<url>)
	@echo "$(BLUE)Executando scraping para URL...$(NC)"
	@if [ -z "$(URL)" ]; then \
		echo "$(RED)Erro: URL não fornecida. Use: make run-url URL=<url>$(NC)"; \
		exit 1; \
	fi
	$(PYTHON) main.py scrape --url "$(URL)"

run-full: ## Executa workflow completo com URL específica (uso: make run-full URL=<url>)
	@echo "$(BLUE)Executando workflow completo para URL...$(NC)"
	@if [ -z "$(URL)" ]; then \
		echo "$(RED)Erro: URL não fornecida. Use: make run-full URL=<url>$(NC)"; \
		exit 1; \
	fi
	$(PYTHON) main.py run --url "$(URL)"

generate: ## Gera respostas para avaliações
	@echo "$(BLUE)Gerando respostas...$(NC)"
	$(PYTHON) main.py generate

# Daemon e Monitoramento
daemon: ## Inicia daemon em background
	@echo "$(BLUE)Iniciando daemon...$(NC)"
	$(PYTHON) main.py daemon --interval 30

daemon-debug: ## Inicia daemon em modo debug
	@echo "$(BLUE)Iniciando daemon em modo debug...$(NC)"
	$(PYTHON) main.py daemon --interval 5 --debug

monitor: ## Monitora status do scraping e sistema
	@echo "$(BLUE)Iniciando monitor...$(NC)"
	$(PYTHON) scripts/monitor_scraping.py

status: ## Mostra status do sistema
	@echo "$(BLUE)Verificando status...$(NC)"
	$(PYTHON) scripts/system_diagnostic.py

stop: ## Para daemon em execução
	@echo "$(BLUE)Parando daemon...$(NC)"
	$(PYTHON) scripts/daemon.py stop

# Limpeza
clean: ## Remove dados/arquivos temporários/cache
	@echo "$(BLUE)Limpando arquivos temporários...$(NC)"
	@read -p "Tem certeza? Esta ação não pode ser desfeita [y/N]: " confirm && [ "$$confirm" = "y" ]
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf build
	rm -rf dist
	rm -rf *.egg-info
	rm -rf data/

# Comandos Úteis
dev: install-dev ## Configuração completa para desenvolvimento
	@echo "$(GREEN)Ambiente de desenvolvimento pronto!$(NC)"

ci: check lint test ## Executa verificações de CI/CD
	@echo "$(GREEN)Todas as verificações de CI passaram!$(NC)"

info: ## Mostra informações do ambiente
	@echo "$(BLUE)Informações do Ambiente$(NC)"
	@echo "======================"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Pip: $$($(PIP) --version)"
	@echo "Sistema: $$(uname -a)"
	@echo "Diretório: $$(pwd)"
	@echo "Git branch: $$(git branch --show-current 2>/dev/null || echo 'N/A')"
	@echo "Git status: $$(git status --porcelain | wc -l) arquivos modificados"

# Defaults
.DEFAULT_GOAL := help
