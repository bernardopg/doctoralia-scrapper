# Makefile para Doctoralia Scrapper
# ===================================

.PHONY: help install install-dev setup test test-unit test-integration lint format clean run daemon monitor status stop

# Variáveis
PYTHON := python3
PIP := pip3
VENV := venv
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

# Instalação
install: ## Instala dependências de produção
	@echo "$(BLUE)Instalando dependências...$(NC)"
	$(PIP) install -r requirements.txt

install-dev: ## Instala dependências de desenvolvimento
	@echo "$(BLUE)Instalando dependências de desenvolvimento...$(NC)"
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-mock black isort mypy flake8 pylint bandit safety pre-commit

# Configuração
setup: ## Executa configuração inicial do projeto
	@echo "$(BLUE)Configurando projeto...$(NC)"
	$(PYTHON) main.py setup

setup-env: ## Cria arquivo .env a partir do exemplo
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Criando arquivo .env...$(NC)"; \
		cp .env.example .env; \
		echo "$(GREEN)Arquivo .env criado! Edite-o com suas configurações.$(NC)"; \
	else \
		echo "$(YELLOW)Arquivo .env já existe.$(NC)"; \
	fi

# Testes
test: ## Executa todos os testes
	@echo "$(BLUE)Executando testes...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing

test-unit: ## Executa apenas testes unitários
	@echo "$(BLUE)Executando testes unitários...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR)/unit -v -m unit

test-integration: ## Executa apenas testes de integração
	@echo "$(BLUE)Executando testes de integração...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR)/integration -v -m integration

test-coverage: ## Executa testes com relatório de cobertura HTML
	@echo "$(BLUE)Executando testes com cobertura...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term
	@echo "$(GREEN)Relatório de cobertura salvo em htmlcov/index.html$(NC)"

# Qualidade de código
lint: ## Executa linting do código
	@echo "$(BLUE)Executando linting...$(NC)"
	flake8 $(SRC_DIR) --max-line-length=88 --extend-ignore=E203
	pylint $(SRC_DIR) --disable=C0114,C0115,C0116
	mypy $(SRC_DIR) --ignore-missing-imports

format: ## Formata o código usando black e isort
	@echo "$(BLUE)Formatando código...$(NC)"
	black .
	isort .

format-check: ## Verifica formatação sem alterar arquivos
	@echo "$(BLUE)Verificando formatação...$(NC)"
	black --check .
	isort --check-only .

security: ## Executa verificações de segurança
	@echo "$(BLUE)Verificando segurança...$(NC)"
	bandit -r $(SRC_DIR)
	safety check --file requirements.txt

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

run-full-url: ## Executa workflow completo com URL específica (uso: make run-full-url URL=<url>)
	@echo "$(BLUE)Executando workflow completo para URL...$(NC)"
	@if [ -z "$(URL)" ]; then \
		echo "$(RED)Erro: URL não fornecida. Use: make run-full-url URL=<url>$(NC)"; \
		exit 1; \
	fi
	$(PYTHON) main.py run --url "$(URL)"

generate: ## Gera respostas para avaliações
	@echo "$(BLUE)Gerando respostas...$(NC)"
	$(PYTHON) main.py generate

daemon: ## Inicia daemon em background
	@echo "$(BLUE)Iniciando daemon...$(NC)"
	$(PYTHON) main.py daemon --interval 30

daemon-debug: ## Inicia daemon em modo debug
	@echo "$(BLUE)Iniciando daemon em modo debug...$(NC)"
	$(PYTHON) main.py daemon --interval 5 --debug

# Monitoramento
monitor: ## Monitora status do scraping
	@echo "$(BLUE)Iniciando monitor...$(NC)"
	$(PYTHON) scripts/monitor_scraping.py

status: ## Mostra status do sistema
	@echo "$(BLUE)Verificando status...$(NC)"
	$(PYTHON) scripts/system_diagnostic.py

stop: ## Para daemon em execução
	@echo "$(BLUE)Parando daemon...$(NC)"
	$(PYTHON) scripts/daemon.py stop

# Limpeza
clean: ## Remove arquivos temporários e cache
	@echo "$(BLUE)Limpando arquivos temporários...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf build
	rm -rf dist
	rm -rf *.egg-info

clean-logs: ## Remove arquivos de log
	@echo "$(YELLOW)Removendo logs...$(NC)"
	rm -rf data/logs/*.log

clean-data: ## Remove dados processados (CUIDADO!)
	@echo "$(RED)Removendo dados processados...$(NC)"
	@read -p "Tem certeza? Esta ação não pode ser desfeita [y/N]: " confirm && [ "$$confirm" = "y" ]
	rm -rf data/extractions/*
	rm -rf data/responses/*

# Desenvolvimento
dev-setup: install-dev setup-env ## Configuração completa para desenvolvimento
	@echo "$(GREEN)Configuração de desenvolvimento concluída!$(NC)"

pre-commit: format lint test ## Executa verificações antes do commit
	@echo "$(GREEN)Todas as verificações passaram!$(NC)"

# Docker (opcional)
docker-build: ## Constrói imagem Docker
	@echo "$(BLUE)Construindo imagem Docker...$(NC)"
	docker build -t doctoralia-scrapper .

docker-run: ## Executa container Docker
	@echo "$(BLUE)Executando container...$(NC)"
	docker run -it --rm -v $(PWD)/data:/app/data doctoralia-scrapper

# Git helpers
git-hooks: ## Instala git hooks para desenvolvimento
	@echo "$(BLUE)Instalando git hooks...$(NC)"
	pre-commit install

# Informações
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
