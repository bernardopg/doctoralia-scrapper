# Makefile para Doctoralia Scrapper
# ===================================

.PHONY: help install setup test lint run daemon monitor clean venv format security deps-sync analyze run-full-url

# Variáveis
# Detecta se .venv existe e usa o Python do venv, caso contrário usa python3 do sistema
VENV_PYTHON := .venv/bin/python
PYTHON := $(shell [ -f $(VENV_PYTHON) ] && echo $(VENV_PYTHON) || echo python3)
PIP := $(shell [ -f .venv/bin/pip ] && echo .venv/bin/pip || echo pip3)
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
	@echo "\nUse 'make venv' para criar/atualizar o ambiente virtual (.venv) com Poetry para melhor integração com a IDE."

# Instalação e Configuração
install: ## Instala dependências de produção
	@echo "$(BLUE)Instalando dependências...$(NC)"
	@if command -v poetry >/dev/null 2>&1; then \
		echo "$(YELLOW)Poetry encontrado. Use 'make venv' para instalar dependências.$(NC)"; \
		exit 1; \
	else \
		$(PIP) install -r requirements.txt --break-system-packages || $(PIP) install -r requirements.txt; \
	fi

install-dev: ## Instala dependências completas + setup do ambiente
	@echo "$(BLUE)Instalando dependências de desenvolvimento...$(NC)"
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-mock black isort mypy flake8 pylint bandit safety pre-commit
venv: ## Cria ambiente virtual local (.venv) usando Poetry e instala deps
	@echo "$(BLUE)Configurando ambiente virtual com Poetry...$(NC)"
	@if command -v poetry >/dev/null 2>&1; then \
		poetry config virtualenvs.in-project true >/dev/null 2>&1; \
		poetry install --no-root; \
		echo "$(GREEN)Ambiente virtual criado em .venv. Aponte sua IDE para .venv/bin/python$(NC)"; \
	else \
		echo "$(YELLOW)Poetry não encontrado. Instalando com pip...$(NC)"; \
		$(PIP) install poetry && poetry config virtualenvs.in-project true && poetry install --no-root; \
	fi
	@echo "$(BLUE)Exportando requirements atualizados (production)...$(NC)"
	@poetry export --without-hashes --format=requirements.txt --output requirements.txt --only main 2>/dev/null || true
	@echo "$(GREEN)Ambiente virtual pronto!$(NC)"
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

format: ## Apenas formata o código (black + isort)
	@echo "$(BLUE)Formatando código (black + isort)...$(NC)"
	black .
	isort .
	@echo "$(GREEN)Formatação concluída!$(NC)"

security: ## Executa apenas verificações de segurança (bandit + safety)
	@echo "$(BLUE)Executando bandit...$(NC)"
	bandit -r $(SRC_DIR)
	@echo "$(BLUE)Executando safety...$(NC)"
	safety check --file requirements.txt || true
	@echo "$(GREEN)Verificações de segurança concluídas!$(NC)"

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

run-full-url: run-full ## Alias compatível com README antigo
	@true

generate: ## Gera respostas para avaliações
	@echo "$(BLUE)Gerando respostas...$(NC)"
	$(PYTHON) main.py generate

analyze: ## Analisa qualidade de respostas (smoke test do analisador)
	@echo "$(BLUE)Executando análise de qualidade (smoke test)...$(NC)"
	$(PYTHON) -c "from src.response_quality_analyzer import ResponseQualityAnalyzer;print('Analyzer OK:', bool(ResponseQualityAnalyzer()))"

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
	rm -rf .ruff_cache


# Comandos Priority 4 - Dashboard e API
dashboard: ## Inicia dashboard web (Priority 4)
	@echo "$(BLUE)Iniciando dashboard web...$(NC)"
	PYTHONPATH=. $(PYTHON) src/dashboard.py

api: ## Inicia API REST (Priority 4)
	@echo "$(BLUE)Iniciando API REST...$(NC)"
	$(PYTHON) -c "from src.api.v1.main import start_api; start_api()"

api-docs: ## Abre documentação da API no navegador
	@echo "$(BLUE)Abrindo documentação da API...$(NC)"
	@which xdg-open > /dev/null && xdg-open http://localhost:8000/docs || \
	 which open > /dev/null && open http://localhost:8000/docs || \
	 echo "$(YELLOW)Abra http://localhost:8000/docs no seu navegador$(NC)"

# Sincronização de dependências
deps-sync: ## Sincroniza requirements.txt a partir do pyproject.toml (Poetry necessário)
	@echo "$(BLUE)Exportando dependências do Poetry...$(NC)"
	@if command -v poetry >/dev/null 2>&1; then \
		poetry export --without-hashes --format=requirements.txt --output requirements.txt --only main; \
		echo "$(GREEN)requirements.txt atualizado a partir do pyproject.toml$(NC)"; \
	else \
		echo "$(YELLOW)Poetry não encontrado. Instale para usar deps-sync.$(NC)"; \
	fi

# ===================================
# Comandos de Update
# ===================================

update: ## 🔄 Atualiza TUDO: dependências, chromedriver e verifica sistema
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)       🔄 DOCTORALIA SCRAPPER - ATUALIZAÇÃO COMPLETA        $(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@$(MAKE) update-deps
	@echo ""
	@$(MAKE) update-drivers
	@echo ""
	@$(MAKE) update-nltk
	@echo ""
	@$(MAKE) deps-sync
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)       ✅ ATUALIZAÇÃO COMPLETA FINALIZADA!                  $(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@$(MAKE) info

update-deps: ## 📦 Atualiza dependências Python via Poetry
	@echo "$(BLUE)📦 Atualizando dependências Python...$(NC)"
	@if command -v poetry >/dev/null 2>&1; then \
		echo "$(YELLOW)→ Verificando atualizações disponíveis...$(NC)"; \
		poetry show --outdated 2>/dev/null || true; \
		echo ""; \
		echo "$(YELLOW)→ Atualizando dependências...$(NC)"; \
		poetry update; \
		echo "$(GREEN)✅ Dependências Python atualizadas!$(NC)"; \
	else \
		echo "$(RED)❌ Poetry não encontrado!$(NC)"; \
		echo "$(YELLOW)Instalando Poetry...$(NC)"; \
		$(PIP) install poetry --break-system-packages 2>/dev/null || $(PIP) install poetry; \
		poetry update; \
	fi

update-deps-dry: ## 📦 Mostra atualizações disponíveis (sem instalar)
	@echo "$(BLUE)📦 Verificando atualizações disponíveis...$(NC)"
	@if command -v poetry >/dev/null 2>&1; then \
		poetry show --outdated; \
	else \
		echo "$(YELLOW)Poetry não encontrado. Use: make update-deps$(NC)"; \
	fi

update-drivers: ## 🌐 Atualiza ChromeDriver para versão mais recente
	@echo "$(BLUE)🌐 Atualizando ChromeDriver...$(NC)"
	@$(PYTHON) scripts/update_drivers.py chromedriver
	@echo "$(GREEN)✅ ChromeDriver atualizado!$(NC)"

update-nltk: ## 📚 Atualiza recursos NLTK (tokenizers, stopwords)
	@echo "$(BLUE)📚 Atualizando recursos NLTK...$(NC)"
	@$(PYTHON) scripts/update_drivers.py nltk
	@echo "$(GREEN)✅ NLTK atualizado!$(NC)"

update-poetry: ## 🔧 Atualiza o próprio Poetry para última versão
	@echo "$(BLUE)🔧 Atualizando Poetry...$(NC)"
	@if command -v poetry >/dev/null 2>&1; then \
		poetry self update; \
		echo "$(GREEN)✅ Poetry atualizado!$(NC)"; \
	else \
		echo "$(YELLOW)Poetry não encontrado. Instalando...$(NC)"; \
		$(PIP) install poetry --break-system-packages 2>/dev/null || $(PIP) install poetry; \
	fi

update-check: ## 🔍 Verifica status de todas as atualizações disponíveis
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)       🔍 VERIFICAÇÃO DE ATUALIZAÇÕES DISPONÍVEIS          $(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(YELLOW)📦 Dependências Python desatualizadas:$(NC)"
	@poetry show --outdated 2>/dev/null || echo "  (Poetry não disponível)"
	@echo ""
	@echo "$(YELLOW)🐍 Versão do Python:$(NC)"
	@$(PYTHON) --version
	@echo ""
	@echo "$(YELLOW)📝 Versão do Poetry:$(NC)"
	@poetry --version 2>/dev/null || echo "  Poetry não instalado"
	@echo ""
	@echo "$(YELLOW)🌐 Chrome/Chromium instalado:$(NC)"
	@google-chrome --version 2>/dev/null || chromium --version 2>/dev/null || chromium-browser --version 2>/dev/null || echo "  Chrome não encontrado"
	@echo ""
	@echo "$(YELLOW)📊 Status do Git:$(NC)"
	@git fetch --quiet 2>/dev/null; \
	LOCAL=$$(git rev-parse HEAD 2>/dev/null); \
	REMOTE=$$(git rev-parse @{u} 2>/dev/null); \
	if [ "$$LOCAL" = "$$REMOTE" ]; then \
		echo "  ✅ Repositório atualizado"; \
	else \
		BEHIND=$$(git rev-list --count HEAD..@{u} 2>/dev/null || echo "0"); \
		echo "  ⚠️  $$BEHIND commit(s) atrás do remoto. Use: git pull"; \
	fi
	@echo ""
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)💡 Use 'make update' para atualizar tudo automaticamente$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"

update-git: ## 📥 Atualiza código do repositório (git pull)
	@echo "$(BLUE)📥 Atualizando código do repositório...$(NC)"
	@git fetch --all
	@git pull --rebase
	@echo "$(GREEN)✅ Código atualizado!$(NC)"

update-all: update-git update ## 🚀 Atualização completa incluindo git pull
	@echo "$(GREEN)✅ Sistema completamente atualizado!$(NC)"

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

# Comandos de diagnóstico
diagnostic: ## Executa diagnóstico completo do sistema
	@echo "$(BLUE)Executando diagnóstico completo...$(NC)"
	$(PYTHON) scripts/system_diagnostic.py

health: ## Verifica saúde do sistema
	@echo "$(BLUE)Verificando saúde do sistema...$(NC)"
	$(PYTHON) scripts/health_check.py

# Comandos de backup
backup: ## Cria backup dos dados
	@echo "$(BLUE)Criando backup dos dados...$(NC)"
	$(PYTHON) scripts/backup_restore.sh backup

restore: ## Restaura dados do backup
	@echo "$(BLUE)Restaurando dados do backup...$(NC)"
	$(PYTHON) scripts/backup_restore.sh restore

# Comandos de otimização
optimize: ## Otimiza performance do sistema
	@echo "$(BLUE)Otimizando sistema...$(NC)"
	$(PYTHON) -c "import psutil; print(f'CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%')"

# Defaults
.DEFAULT_GOAL := help
