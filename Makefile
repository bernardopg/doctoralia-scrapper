# Makefile para Doctoralia Scrapper - Priority 4
# ==============================================

.PHONY: help install setup test lint run daemon monitor clean dashboard api analyze quality performance secure-config

# Variáveis
PYTHON := poetry run python
PIP := poetry run pip
SRC_DIR := src
TEST_DIR := tests
CONFIG_DIR := config

# Cores para output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0moctoralia Scrapper
# ===================================

.PHONY: help install setup test lint run daemon monitor clean

# Variáveis
PYTHON := poetry run python
PIP := poetry run pip
SRC_DIR := src
TEST_DIR := tests

# Cores para output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m
# Help
help: ## Mostra esta mensagem de ajuda
	@echo "$(BLUE)Doctoralia Scrapper - Comandos Disponíveis$(NC)"
	@echo "========================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Priority 4 - Novos Recursos
dashboard: ## Inicia dashboard web Flask (porta 5000)
	@echo "$(BLUE)Iniciando dashboard web...$(NC)"
	$(PYTHON) $(SRC_DIR)/dashboard.py

api: ## Inicia API REST FastAPI (porta 8000)
	@echo "$(BLUE)Iniciando API REST...$(NC)"
	$(PYTHON) $(SRC_DIR)/api.py

api-docs: ## Abre documentação da API no navegador
	@echo "$(BLUE)Abrindo documentação da API...$(NC)"
	@if command -v xdg-open > /dev/null; then \
		xdg-open http://localhost:8000/docs; \
	elif command -v open > /dev/null; then \
		open http://localhost:8000/docs; \
	else \
		echo "$(YELLOW)Acesse: http://localhost:8000/docs$(NC)"; \
	fi

analyze: ## Executa análise de qualidade ML interativa
	@echo "$(BLUE)Iniciando análise de qualidade...$(NC)"
	$(PYTHON) $(SRC_DIR)/response_quality_analyzer.py

quality: ## Executa análise de qualidade em lote
	@echo "$(BLUE)Executando análise de qualidade em lote...$(NC)"
	$(PYTHON) $(SRC_DIR)/response_quality_analyzer.py --batch

performance: ## Inicia monitor de performance
	@echo "$(BLUE)Iniciando monitor de performance...$(NC)"
	$(PYTHON) $(SRC_DIR)/performance_monitor.py

health: ## Executa health check completo do sistema
	@echo "$(BLUE)Executando health check...$(NC)"
	$(PYTHON) -c "import asyncio; from src.health_checker import HealthChecker; from config.settings import AppConfig; asyncio.run(HealthChecker(AppConfig.load()).check_all())"

check-deps: ## Verifica dependências e vulnerabilidades
	@echo "$(BLUE)Verificando dependências...$(NC)"
	$(PYTHON) -m safety check
	@echo "$(GREEN)Verificação de dependências concluída!$(NC)"

update-requirements: ## Atualiza requirements.txt baseado no pyproject.toml
	@echo "$(BLUE)Atualizando requirements.txt...$(NC)"
	@echo "# Este arquivo é gerado automaticamente a partir do pyproject.toml" > requirements.txt
	@echo "# Para atualizar as dependências, use: poetry install" >> requirements.txt
	@echo "# Para gerar um novo requirements.txt, use: poetry show --only=main --tree" >> requirements.txt
	@echo "" >> requirements.txt
	poetry show --only=main | awk '{print $$1"=="$$2}' >> requirements.txt
	@echo "$(GREEN)requirements.txt atualizado!$(NC)"

secure-config: ## Gerencia configuração segura
	@echo "$(BLUE)Gerenciando configuração segura...$(NC)"
	$(PYTHON) $(SRC_DIR)/secure_config.py

multi-site: ## Executa scraping multi-plataforma
	@echo "$(BLUE)Executando scraping multi-plataforma...$(NC)"
	$(PYTHON) $(SRC_DIR)/multi_site_scraper.py

# Instalação e Configuração
install: ## Instala dependências de produção com Poetry
	@echo "$(BLUE)Instalando dependências de produção...$(NC)"
	poetry install --only main

install-dev: ## Instala dependências completas + setup do ambiente
	@echo "$(BLUE)Instalando dependências de desenvolvimento...$(NC)"
	poetry install
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Criando arquivo .env...$(NC)"; \
		cp .env.example .env 2>/dev/null || echo "$(YELLOW)Arquivo .env.example não encontrado$(NC)"; \
		echo "$(GREEN)Arquivo .env criado! Edite-o com suas configurações.$(NC)"; \
	fi
	$(PYTHON) scripts/setup.py
	@echo "$(GREEN)Configuração de desenvolvimento concluída!$(NC)"

install-all: ## Instala todas as dependências (main + dev)
	@echo "$(BLUE)Instalando todas as dependências...$(NC)"
	poetry install

setup: ## Executa configuração inicial do projeto
	@echo "$(BLUE)Configurando projeto...$(NC)"
	$(PYTHON) scripts/setup.py

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

# Priority 4 - Comandos de Produção
start-all: ## Inicia todos os serviços (API + Dashboard)
	@echo "$(BLUE)Iniciando todos os serviços...$(NC)"
	@echo "$(YELLOW)API REST: http://localhost:8000$(NC)"
	@echo "$(YELLOW)Dashboard: http://localhost:5000$(NC)"
	@echo "$(YELLOW)API Docs: http://localhost:8000/docs$(NC)"
	$(PYTHON) $(SRC_DIR)/api.py &
	$(PYTHON) $(SRC_DIR)/dashboard.py &
	@echo "$(GREEN)Serviços iniciados! Pressione Ctrl+C para parar.$(NC)"
	@wait

start-api-bg: ## Inicia API em background
	@echo "$(BLUE)Iniciando API em background...$(NC)"
	nohup $(PYTHON) $(SRC_DIR)/api.py > api.log 2>&1 &
	@echo "$(GREEN)API iniciada em background (PID: $$!)$(NC)"
	@echo "$(YELLOW)Acesse: http://localhost:8000/docs$(NC)"

start-dashboard-bg: ## Inicia dashboard em background
	@echo "$(BLUE)Iniciando dashboard em background...$(NC)"
	nohup $(PYTHON) $(SRC_DIR)/dashboard.py > dashboard.log 2>&1 &
	@echo "$(GREEN)Dashboard iniciado em background (PID: $$!)$(NC)"
	@echo "$(YELLOW)Acesse: http://localhost:5000$(NC)"

stop-all: ## Para todos os serviços em execução
	@echo "$(BLUE)Parando todos os serviços...$(NC)"
	-pkill -f "python.*api.py" 2>/dev/null || true
	-pkill -f "python.*dashboard.py" 2>/dev/null || true
	@echo "$(GREEN)Serviços parados.$(NC)"

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
	@read -p "Tem certeza? Esta ação não pode ser desfeita [S/N]: " confirm && [ "$$confirm" = "S" ]
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
	rm -rf .ruff_cache
	rm -rf api.log dashboard.log

clean-logs: ## Remove apenas arquivos de log
	@echo "$(BLUE)Limpando logs...$(NC)"
	rm -f api.log dashboard.log
	rm -f data/logs/*.log
	@echo "$(GREEN)Logs removidos.$(NC)"

clean-all: ## Limpeza completa (dados + cache + logs)
	@echo "$(BLUE)Limpando tudo...$(NC)"
	@read -p "ATENÇÃO: Isso removerá TODOS os dados! Continuar? [S/N]: " confirm && [ "$$confirm" = "S" ]
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
	rm -rf .ruff_cache
	rm -f api.log dashboard.log
	@echo "$(GREEN)Limpeza completa realizada.$(NC)"


# Comandos Úteis
dev: install-dev ## Configuração completa para desenvolvimento
	@echo "$(GREEN)Ambiente de desenvolvimento pronto!$(NC)"

ci: check lint test ## Executa verificações de CI/CD
	@echo "$(GREEN)Todas as verificações de CI passaram!$(NC)"

info: ## Mostra informações do ambiente
	@echo "$(BLUE)Informações do Ambiente$(NC)"
	@echo "======================"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Poetry: $$(poetry --version)"
	@echo "Pip: $$($(PIP) --version)"
	@echo "Sistema: $$(uname -a)"
	@echo "Diretório: $$(pwd)"
	@echo "Git branch: $$(git branch --show-current 2>/dev/null || echo 'N/A')"
	@echo "Git status: $$(git status --porcelain | wc -l) arquivos modificados"

# Priority 4 - Comandos de Desenvolvimento
dev-priority4: install-all ## Setup completo Priority 4
	@echo "$(BLUE)Configurando ambiente Priority 4...$(NC)"
	$(PYTHON) scripts/setup.py
	@echo "$(GREEN)Ambiente Priority 4 pronto!$(NC)"
	@echo "$(YELLOW)Comandos disponíveis:$(NC)"
	@echo "  make dashboard    - Dashboard web"
	@echo "  make api          - API REST"
	@echo "  make analyze      - Análise ML"
	@echo "  make performance  - Monitor de performance"

test-priority4: ## Testa recursos Priority 4
	@echo "$(BLUE)Testando recursos Priority 4...$(NC)"
	@echo "$(YELLOW)Verificando API...$(NC)"
	curl -s http://localhost:8000/docs > /dev/null && echo "$(GREEN)API OK$(NC)" || echo "$(RED)API não responde$(NC)"
	@echo "$(YELLOW)Verificando Dashboard...$(NC)"
	curl -s http://localhost:5000 > /dev/null && echo "$(GREEN)Dashboard OK$(NC)" || echo "$(RED)Dashboard não responde$(NC)"

# Atalhos Priority 4
priority4: dev-priority4 ## Alias para dev-priority4
p4: dev-priority4 ## Alias curto para Priority 4

# Priority 4 - Informações dos Serviços
services-info: ## Mostra informações dos serviços Priority 4
	@echo "$(BLUE)Priority 4 - Serviços Disponíveis$(NC)"
	@echo "=================================="
	@echo "$(GREEN)Dashboard Web:$(NC)    http://localhost:5000"
	@echo "$(GREEN)API REST:$(NC)         http://localhost:8000"
	@echo "$(GREEN)API Docs:$(NC)         http://localhost:8000/docs"
	@echo "$(GREEN)API ReDoc:$(NC)        http://localhost:8000/redoc"
	@echo ""
	@echo "$(YELLOW)Comandos Rápidos:$(NC)"
	@echo "  make dashboard     - Iniciar dashboard"
	@echo "  make api          - Iniciar API"
	@echo "  make start-all    - Iniciar tudo"
	@echo "  make stop-all     - Parar tudo"
	@echo "  make analyze      - Análise ML"
	@echo "  make performance  - Monitor"

# Defaults
.DEFAULT_GOAL := help
