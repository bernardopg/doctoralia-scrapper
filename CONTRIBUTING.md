# 🤝 Contribuindo para o Doctoralia Scraper

Obrigado por considerar contribuir para o projeto! Este guia ajudará você a entender como contribuir de forma efetiva e manter a qualidade do código.

## 📋 Índice

- [Código de Conduta](#código-de-conduta)
- [Como Começar](#como-começar)
- [Processo de Desenvolvimento](#processo-de-desenvolvimento)
- [Padrões de Código](#padrões-de-código)
- [Testes](#testes)
- [Documentação](#documentação)
- [Code Review](#code-review)
- [Debugging](#debugging)
- [Suporte](#suporte)

## 📜 Código de Conduta

Este projeto segue um código de conduta profissional. Ao participar, você concorda em manter um ambiente colaborativo e respeitoso para todos os contribuidores.

### 🎯 **Compromissos**

- **Respeito**: Tratar todos com cortesia e respeito
- **Inclusividade**: Valorizar diferentes perspectivas e experiências
- **Profissionalismo**: Manter comunicação profissional
- **Qualidade**: Priorizar código de alta qualidade e bem testado

## 🚀 Como Começar

### 📋 **Pré-requisitos**

Antes de contribuir, certifique-se de ter:

- **Python 3.10+** instalado
- **Git** configurado
- **Google Chrome** para Selenium
- Familiaridade com desenvolvimento Python

### 🛠️ **Setup Inicial**

```bash
# 1. Fork o repositório
# 2. Clone seu fork
git clone https://github.com/SEU_USERNAME/doctoralia-scraper.git
cd doctoralia-scraper

# 3. Configure ambiente de desenvolvimento
make install-dev

# 4. Configure pre-commit hooks
pip install pre-commit
pre-commit install

# 5. Execute testes para verificar setup
make test
```

### 📝 **Encontrando Tarefas**

- **Issues**: Verifique [Issues](../../issues) para tarefas abertas
- **Labels**: Use labels para filtrar por tipo de tarefa
  - `good first issue`: Ideal para iniciantes
  - `enhancement`: Melhorias e novas funcionalidades
  - `bug`: Correções de bugs
  - `documentation`: Melhorias na documentação

## 🔧 Processo de Desenvolvimento

### 📋 **Fluxo de Trabalho**

1. **Escolha uma tarefa** no GitHub Issues
2. **Crie uma branch** descritiva
3. **Desenvolva** seguindo os padrões
4. **Teste** suas mudanças
5. **Commit** com mensagens convencionais
6. **Push** e crie um Pull Request
7. **Code Review** e ajustes
8. **Merge** após aprovação

### 🌿 **Branches**

```bash
# Para features
git checkout -b feature/nome-da-funcionalidade

# Para correções
git checkout -b fix/nome-do-bug

# Para documentação
git checkout -b docs/melhoria-na-documentacao

# Para manutenção
git checkout -b chore/atualizacao-dependencias
```

### 📝 **Commits**

Use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Features
git commit -m "feat: adiciona suporte a múltiplas plataformas de scraping"

# Fixes
git commit -m "fix: corrige timeout no scraping de páginas grandes"

# Documentation
git commit -m "docs: atualiza guia de instalação no README"

# Tests
git commit -m "test: adiciona testes para response generator"

# Maintenance
git commit -m "chore: atualiza dependências de desenvolvimento"
```

### 🔄 **Pull Requests**

**Template de PR** deve incluir:

- ✅ **Descrição clara** do que foi implementado
- ✅ **Motivação** para as mudanças
- ✅ **Como testar** as alterações
- ✅ **Screenshots** se aplicável
- ✅ **Checklist** completo

**Exemplo de PR bem escrito:**

```markdown
## 📋 Descrição
Adiciona suporte a análise de sentimento usando NLTK VADER para melhorar a qualidade das respostas automáticas.

## 🎯 Problema Resolvido
As respostas automáticas não consideravam o sentimento da avaliação original, resultando em respostas genéricas.

## ✅ Como Testar
1. Execute `make test` para verificar testes existentes
2. Teste manual: `python -c "from src.response_quality_analyzer import ResponseQualityAnalyzer; print('OK')"`
3. Verifique análise: `make analyze`

## 📸 Screenshots
[Adicionar screenshots da interface ou resultados]

## ☑️ Checklist
- [x] Testes passando
- [x] Documentação atualizada
- [x] Linting aprovado
- [x] Funcionalidade testada manualmente
```

## 📝 Padrões de Código

### 🎯 **Princípios Gerais**

- **Legibilidade**: Código deve ser claro e autoexplicativo
- **Consistência**: Seguir padrões estabelecidos no projeto
- **Simplicidade**: Soluções simples são preferidas
- **Testabilidade**: Código deve ser facilmente testável
- **Manutenibilidade**: Facilitar futuras modificações

### 🐍 **Python Style Guide**

#### **PEP 8 Compliance**

```python
# ✅ Correto
def calculate_quality_score(response_text, original_review):
    """Calcula pontuação de qualidade da resposta."""
    if not response_text or not original_review:
        return 0.0

    # Implementação
    score = analyze_sentiment(response_text)
    return round(score, 2)

# ❌ Incorreto
def calcQualScr(resp,orig): # Sem docstring, nomes ruins
    if not resp or not orig: return 0
    scr=analizeSentiment(resp) # Erro de digitação
    return scr
```

#### **Type Hints Obrigatórios**

```python
# ✅ Com type hints
from typing import Optional, Dict, List, Any

def process_reviews(reviews: List[Dict[str, Any]],
                   doctor_name: str,
                   max_reviews: Optional[int] = None) -> Dict[str, Any]:
    """Processa lista de avaliações médicas."""
    pass

# ❌ Sem type hints
def process_reviews(reviews, doctor_name, max_reviews=None):
    pass
```

#### **Docstrings Completas**

```python
def scrape_doctor_page(url: str,
                      wait_time: float = 2.0,
                      headless: bool = True) -> Optional[Dict[str, Any]]:
    """
    Realiza scraping de página de médico no Doctoralia.

    Args:
        url: URL completa da página do médico
        wait_time: Tempo de espera entre ações (segundos)
        headless: Executar navegador em modo headless

    Returns:
        Dicionário com dados extraídos ou None se falhar

    Raises:
        ScrapingError: Quando ocorre erro no scraping
        RateLimitError: Quando atingido limite de requisições

    Example:
        >>> data = scrape_doctor_page(
        ...     "https://www.doctoralia.com.br/medico",
        ...     wait_time=3.0
        ... )
        >>> print(data['doctor_name'])
        'Dr. João Silva'
    """
```

### 🏗️ **Estrutura de Código**

#### **Organização de Imports**

```python
# 1. Imports padrão da biblioteca
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

# 2. Imports de terceiros
import requests
from bs4 import BeautifulSoup
from selenium import webdriver

# 3. Imports locais
from .config import settings
from .errors import ScrapingError
from .utils import setup_logger
```

#### **Classes e Métodos**

```python
class DoctoraliaScraper:
    """Scraper para plataforma Doctoralia."""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.driver = None
        self._setup_driver()

    def __del__(self):
        """Cleanup do webdriver."""
        if self.driver:
            self.driver.quit()

    def scrape_reviews(self, doctor_url: str) -> Dict[str, Any]:
        """Método principal para scraping de avaliações."""
        try:
            self.logger.info(f"Iniciando scraping: {doctor_url}")
            return self._perform_scraping(doctor_url)
        except Exception as e:
            self.logger.error(f"Erro no scraping: {e}")
            raise ScrapingError(f"Falha no scraping: {e}") from e
```

### 🛡️ **Tratamento de Erros**

#### **Hierarquia de Exceções**

```python
class ScrapingError(Exception):
    """Erro base para operações de scraping."""
    pass

class RateLimitError(ScrapingError):
    """Erro quando atingido limite de requisições."""
    pass

class PageNotFoundError(ScrapingError):
    """Erro quando página não é encontrada."""
    pass

class NetworkError(ScrapingError):
    """Erro de conectividade de rede."""
    pass
```

#### **Padrões de Tratamento**

```python
def safe_scraping_operation(url: str) -> Dict[str, Any]:
    """Operação de scraping com tratamento robusto."""
    try:
        # Tentativa principal
        return perform_scraping(url)
    except RateLimitError:
        # Backoff específico para rate limit
        time.sleep(60)
        return perform_scraping(url)
    except NetworkError as e:
        # Retry com exponential backoff
        for attempt in range(3):
            try:
                time.sleep(2 ** attempt)
                return perform_scraping(url)
            except NetworkError:
                continue
        raise ScrapingError(f"Falha de rede após 3 tentativas: {e}")
    except Exception as e:
        # Log detalhado para debugging
        logger.error(f"Erro inesperado: {e}", exc_info=True)
        raise ScrapingError(f"Erro inesperado: {e}") from e
```

### 📊 **Logging**

#### **Níveis Apropriados**

```python
logger = logging.getLogger(__name__)

def scrape_with_logging(url: str) -> Dict[str, Any]:
    """Scraping com logging apropriado."""
    logger.info(f"🚀 Iniciando scraping: {url}")

    try:
        # Operação normal
        data = perform_scraping(url)
        logger.info(f"✅ Scraping concluído: {len(data.get('reviews', []))} avaliações")
        return data

    except RateLimitError as e:
        logger.warning(f"⚠️ Rate limit atingido, tentando novamente: {e}")
        raise

    except Exception as e:
        logger.error(f"❌ Erro crítico no scraping: {e}", exc_info=True)
        raise
```

#### **Logs Estruturados**

```python
# Para produção, use logs estruturados
logger.info("Scraping completed", extra={
    "url": doctor_url,
    "reviews_count": len(reviews),
    "duration_ms": duration,
    "status": "success"
})
```

    def __init__(self, param1: str, param2: Optional[int] = None):
        self.param1 = param1
        self.param2 = param2

    def example_method(self) -> Dict[str, Any]:
        """
        Método de exemplo

        Returns:
            Dicionário com resultado
        """
        logger.info(f"Executando método com {self.param1}")
        return {"status": "success"}

```

## 🧪 Testes

### Executando Testes

```bash
# Todos os testes
python -m pytest

# Testes específicos
python -m pytest tests/test_scraper.py

# Com coverage
python -m pytest --cov=src
```

### Escrevendo Testes

- Use pytest
- Testes unitários em `tests/unit/`
- Testes de integração em `tests/integration/`
- Mocks para dependências externas

Exemplo:

```python
import pytest
from unittest.mock import Mock, patch
from src.scraper import DoctoraliaScraper


class TestDoctoraliaScraper:

    def test_scraper_initialization(self):
        """Testa inicialização do scraper"""
        config = Mock()
        logger = Mock()
        scraper = DoctoraliaScraper(config, logger)
        assert scraper.config == config

    @patch('src.scraper.webdriver.Chrome')
    def test_scraper_start(self, mock_webdriver):
        """Testa início do scraper"""
        # Setup
        config = Mock()
        logger = Mock()
        scraper = DoctoraliaScraper(config, logger)

        # Execute
        scraper.start()

        # Assert
        mock_webdriver.assert_called_once()
```

## 📚 Documentação

### Atualizando README

- Mantenha instruções atualizadas
- Inclua exemplos de uso
- Documente novas funcionalidades

### Docstrings

Use formato Google:

```python
def complex_function(param1: str, param2: int = 10) -> Dict[str, Any]:
    """
    Função complexa que faz algo importante.

    Esta função realiza operações complexas com os parâmetros
    fornecidos e retorna um resultado estruturado.

    Args:
        param1: String de entrada para processamento
        param2: Número inteiro para configuração (padrão: 10)

    Returns:
        Dicionário contendo:
            - status: Status da operação
            - result: Resultado do processamento
            - metadata: Informações adicionais

    Raises:
        ValueError: Quando param1 está vazio
        RuntimeError: Quando processamento falha

    Example:
        >>> result = complex_function("test", 20)
        >>> print(result["status"])
        success
    """
```

## 🔍 Code Review

### Checklist para PRs

- [ ] Código segue padrões estabelecidos
- [ ] Testes passando
- [ ] Documentação atualizada
- [ ] Sem código commented out
- [ ] Sem prints de debug
- [ ] Logs apropriados
- [ ] Tratamento de erros
- [ ] Performance considerada

### O que Revisar

1. **Funcionalidade**: O código faz o que deveria?
2. **Legibilidade**: Código é claro e bem documentado?
3. **Performance**: Há otimizações óbvias?
4. **Segurança**: Não expõe dados sensíveis?
5. **Manutenibilidade**: Código é fácil de manter?

## 🐛 Debugging

### Logs de Debug

```python
# Use logging em vez de print
logger.debug("Informação de debug")
logger.info("Operação realizada")
logger.warning("Algo suspeito")
logger.error("Erro não crítico")
logger.critical("Erro crítico")
```

### Tools Úteis

- `scripts/system_diagnostic.py`: Diagnóstico completo
- `scripts/monitor_scraping.py`: Monitor em tempo real
- Logs em `data/logs/`: Análise detalhada

## 📞 Suporte

- **Issues**: Para bugs e features
- **Discussions**: Para dúvidas gerais
- **Email**: Para questões privadas

Obrigado por contribuir! 🚀
