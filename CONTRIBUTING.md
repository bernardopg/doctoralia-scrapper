# 🤝 Guia de Contribuição

Obrigado pelo interesse em contribuir com o **Doctoralia Scraper**! Este documento descreve as diretrizes e processos para contribuir com o projeto.

## 📋 Índice

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Ambiente de Desenvolvimento](#ambiente-de-desenvolvimento)
- [Padrões de Código](#padrões-de-código)
- [Commits e Pull Requests](#commits-e-pull-requests)
- [Testes](#testes)
- [Documentação](#documentação)
- [Segurança](#segurança)

---

## 📜 Código de Conduta

Este projeto adota o [Contributor Covenant](CODE_OF_CONDUCT.md) como código de conduta. Ao participar, você concorda em manter um ambiente respeitoso e inclusivo.

**TL;DR**: Seja gentil, respeitoso e profissional.

---

## 🚀 Como Contribuir

### Tipos de Contribuição

| Tipo | Descrição |
|------|-----------|
| 🐛 **Bug Report** | Encontrou um bug? [Abra uma issue](https://github.com/bernardopg/doctoralia-scrapper/issues/new?template=bug_report.md) |
| 💡 **Feature Request** | Tem uma ideia? [Sugira uma feature](https://github.com/bernardopg/doctoralia-scrapper/issues/new?template=feature_request.md) |
| 📝 **Documentação** | Melhorias na documentação são sempre bem-vindas |
| 🔧 **Código** | Correções, melhorias ou novas features |
| 🧪 **Testes** | Aumento de cobertura de testes |

### Fluxo de Trabalho

```bash
# 1. Fork o repositório no GitHub

# 2. Clone seu fork
git clone https://github.com/seu-usuario/doctoralia-scrapper.git
cd doctoralia-scrapper

# 3. Configure o upstream
git remote add upstream https://github.com/bernardopg/doctoralia-scrapper.git

# 4. Crie uma branch para sua feature
git checkout -b feat/minha-feature

# 5. Faça suas alterações e commits
# ... código ...
git add .
git commit -m "feat: adiciona minha feature"

# 6. Mantenha sua branch atualizada
git fetch upstream
git rebase upstream/main

# 7. Push para seu fork
git push origin feat/minha-feature

# 8. Abra um Pull Request no GitHub
```

---

## 🛠️ Ambiente de Desenvolvimento

### Pré-requisitos

- Python 3.11+
- [Poetry](https://python-poetry.org/) (recomendado)
- Chrome/Chromium
- Redis (opcional)
- Git

### Setup Inicial

```bash
# Instalar dependências de desenvolvimento
make install-dev

# Configurar pre-commit hooks
pip install pre-commit
pre-commit install

# Copiar arquivos de configuração
cp .env.example .env
cp config/config.example.json config/config.json

# Verificar instalação
make health
```

### Comandos Úteis

```bash
make lint          # Verificar estilo de código
make format        # Formatar código automaticamente
make test          # Executar testes
make test-coverage # Testes com cobertura
make security      # Verificação de segurança
make docs          # Gerar documentação
```

---

## 📏 Padrões de Código

### Estilo

- **Formatter**: [Black](https://black.readthedocs.io/) (line-length: 88)
- **Import Sort**: [isort](https://pycqa.github.io/isort/) (profile: black)
- **Linter**: [Flake8](https://flake8.pycqa.org/)
- **Type Checker**: [mypy](https://mypy.readthedocs.io/)

### Convenções

```python
# ✅ BOM: Type hints em funções
def process_review(review: dict, options: dict | None = None) -> str:
    """Processa uma avaliação e retorna resposta formatada.

    Args:
        review: Dicionário com dados da avaliação
        options: Opções de processamento (opcional)

    Returns:
        Resposta formatada como string

    Raises:
        ValueError: Se review estiver vazio
    """
    if not review:
        raise ValueError("Review não pode estar vazio")
    return format_response(review)

# ✅ BOM: Exceções específicas
class ScrapingError(Exception):
    """Erro durante operação de scraping."""
    pass

# ✅ BOM: Logs estruturados
logger.info("Processando review", extra={
    "review_id": review_id,
    "doctor_id": doctor_id
})

# ❌ EVITAR: Logs com PII
logger.info(f"Email do paciente: {email}")  # NÃO!
```

### Estrutura de Arquivos

```python
# Ordem de imports (automático com isort)
# 1. Standard library
import os
from typing import Optional

# 2. Third-party
from fastapi import APIRouter
import requests

# 3. Local
from src.scraper import Scraper
from src.utils import format_date
```

---

## 📝 Commits e Pull Requests

### Conventional Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/) para mensagens de commit:

```bash
# Formato
<tipo>(<escopo>): <descrição>

[corpo opcional]

[rodapé opcional]
```

### Tipos de Commit

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `feat` | Nova feature | `feat(api): adiciona endpoint de batch` |
| `fix` | Correção de bug | `fix(scraper): corrige timeout em páginas lentas` |
| `docs` | Documentação | `docs: atualiza README com novos badges` |
| `style` | Formatação | `style: aplica black em todos os arquivos` |
| `refactor` | Refatoração | `refactor(parser): simplifica lógica de extração` |
| `test` | Testes | `test: adiciona testes para circuit breaker` |
| `chore` | Manutenção | `chore: atualiza dependências` |
| `perf` | Performance | `perf: otimiza cache de extrações` |
| `ci` | CI/CD | `ci: adiciona job de security scan` |
| `security` | Segurança | `security: corrige vulnerabilidade XSS` |

### Pull Request Checklist

Antes de abrir um PR, verifique:

- [ ] 🧪 Testes passando (`make test`)
- [ ] 📏 Lint sem erros (`make lint`)
- [ ] 🔒 Sem credenciais/segredos no código
- [ ] 📝 Documentação atualizada (se aplicável)
- [ ] 📜 CHANGELOG.md atualizado (se aplicável)
- [ ] 💬 Descrição clara do que foi alterado
- [ ] 🔗 Issue relacionada linkada (se aplicável)

### Template de PR

```markdown
## Descrição
[Descreva as mudanças de forma clara e concisa]

## Tipo de Mudança
- [ ] 🐛 Bug fix
- [ ] ✨ Nova feature
- [ ] 💥 Breaking change
- [ ] 📝 Documentação
- [ ] 🔧 Refatoração

## Como Testar
1. [Passo 1]
2. [Passo 2]
3. [Passo 3]

## Screenshots (se aplicável)
[Adicione screenshots se houver mudanças visuais]

## Checklist
- [ ] Testes passando
- [ ] Lint sem erros
- [ ] Documentação atualizada

Fixes #[número da issue]
```

---

## 🧪 Testes

### Executando Testes

```bash
# Todos os testes
make test

# Com cobertura
make test-coverage

# Testes específicos
pytest tests/test_scraper.py -v

# Por marcador
pytest -m "not slow"

# Por nome
pytest -k "test_circuit_breaker"
```

### Escrevendo Testes

```python
# tests/test_example.py
import pytest
from src.example import MyClass

class TestMyClass:
    """Testes para MyClass."""

    @pytest.fixture
    def instance(self):
        """Cria instância para testes."""
        return MyClass()

    def test_basic_operation(self, instance):
        """Testa operação básica."""
        result = instance.do_something()
        assert result == expected_value

    @pytest.mark.parametrize("input,expected", [
        ("a", 1),
        ("b", 2),
        ("c", 3),
    ])
    def test_parametrized(self, instance, input, expected):
        """Testa com múltiplos inputs."""
        assert instance.process(input) == expected

    @pytest.mark.slow
    def test_slow_operation(self, instance):
        """Teste demorado, marcado como slow."""
        result = instance.heavy_operation()
        assert result is not None
```

### Cobertura Mínima

- **Novas features**: Mínimo 80% de cobertura
- **Bug fixes**: Teste que reproduz o bug + correção
- **Refatoração**: Manter cobertura existente

---

## 📚 Documentação

### Onde Documentar

| Tipo | Local |
|------|-------|
| API Reference | `docs/api.md` |
| Guias | `docs/*.md` |
| Código | Docstrings (Google style) |
| Mudanças | `CHANGELOG.md` |

### Docstrings

```python
def scrape_reviews(
    url: str,
    max_pages: int = 10,
    timeout: int = 30
) -> list[dict]:
    """Extrai avaliações de uma página do Doctoralia.

    Realiza scraping da URL fornecida, navegando por múltiplas
    páginas se necessário, com proteções contra bloqueio.

    Args:
        url: URL completa do perfil do médico no Doctoralia
        max_pages: Número máximo de páginas a processar (default: 10)
        timeout: Timeout em segundos para cada requisição (default: 30)

    Returns:
        Lista de dicionários contendo os dados das avaliações.
        Cada dicionário contém: rating, text, date, author.

    Raises:
        ScrapingError: Se ocorrer erro durante o scraping
        ValueError: Se a URL for inválida

    Example:
        >>> reviews = scrape_reviews("https://doctoralia.com.br/...")
        >>> len(reviews)
        25
        >>> reviews[0]["rating"]
        5.0
    """
```

---

## 🔒 Segurança

### Reportando Vulnerabilidades

⚠️ **NÃO abra issues públicas para vulnerabilidades de segurança.**

Consulte [SECURITY.md](SECURITY.md) para instruções de como reportar.

### Boas Práticas

- Nunca commite credenciais ou segredos
- Use variáveis de ambiente para dados sensíveis
- Valide e sanitize todos os inputs
- Mantenha dependências atualizadas
- Execute `make security` antes de PRs

---

## 📖 Referências

| Documento | Descrição |
|-----------|-----------|
| [README.md](README.md) | Visão geral do projeto |
| [SECURITY.md](SECURITY.md) | Política de segurança |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Código de conduta |
| [CHANGELOG.md](CHANGELOG.md) | Histórico de mudanças |
| [docs/](docs/) | Documentação completa |

---

## ❓ Dúvidas?

- 💬 [Abra uma Discussion](https://github.com/bernardopg/doctoralia-scrapper/discussions)
- 🐛 [Abra uma Issue](https://github.com/bernardopg/doctoralia-scrapper/issues)

---

## 🙏 Agradecimentos

Obrigado por dedicar seu tempo para contribuir! Toda contribuição, grande ou pequena, é valorizada.

**Juntos construímos um projeto melhor! 🚀**
