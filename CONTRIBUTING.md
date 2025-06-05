# 🤝 Contribuindo para o Doctoralia Scrapper

Obrigado por considerar contribuir para o projeto! Este guia ajudará você a entender como contribuir de forma efetiva.

## 📋 Índice

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Processo de Development](#processo-de-development)
- [Padrões de Código](#padrões-de-código)
- [Testes](#testes)
- [Documentação](#documentação)

## 📜 Código de Conduta

Este projeto segue um código de conduta. Ao participar, você concorda em manter um ambiente respeitoso e colaborativo.

## 🚀 Como Contribuir

### Reportando Bugs

1. Verifique se o bug já foi reportado nas [Issues](../../issues)
2. Use o template de bug report
3. Inclua informações detalhadas:
   - Versão do Python
   - Sistema operacional
   - Logs relevantes
   - Passos para reproduzir

### Sugerindo Melhorias

1. Abra uma issue com o label "enhancement"
2. Descreva claramente a melhoria proposta
3. Explique por que seria útil
4. Considere implementações alternativas

### Pull Requests

1. Fork o repositório
2. Crie uma branch a partir da `main`
3. Faça suas mudanças
4. Adicione testes se necessário
5. Atualize a documentação
6. Faça commit com mensagens descritivas
7. Abra um Pull Request

## 🔧 Processo de Development

### Setup do Ambiente

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/doctoralia-scrapper.git
cd doctoralia-scrapper

# Instale dependências
pip install -r requirements.txt

# Configure o ambiente
python main.py setup
```

### Estrutura de Branches

- `main`: Branch principal (protegida)
- `develop`: Branch de desenvolvimento
- `feature/nome-da-feature`: Features novas
- `bugfix/nome-do-bug`: Correções de bugs
- `hotfix/nome-do-hotfix`: Correções urgentes

### Workflow

1. **Crie uma branch**:

   ```bash
   git checkout -b feature/nova-funcionalidade
   ```

2. **Desenvolva e teste**:

   ```bash
   # Faça suas mudanças
   python main.py test  # Execute testes
   ```

3. **Commit suas mudanças**:

   ```bash
   git add .
   git commit -m "feat: adiciona nova funcionalidade"
   ```

4. **Push e PR**:

   ```bash
   git push origin feature/nova-funcionalidade
   # Abra PR via GitHub
   ```

## 📝 Padrões de Código

### Python Style Guide

- Siga a [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints quando possível
- Docstrings para funções e classes
- Máximo de 88 caracteres por linha (Black formatter)

### Convenções de Commit

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `style:` Formatação
- `refactor:` Refatoração
- `test:` Testes
- `chore:` Manutenção

Exemplos:

```text
feat: adiciona suporte a novos templates de resposta
fix: corrige timeout no scraping de páginas
docs: atualiza README com instruções de instalação
```

### Estrutura de Código

```python
"""
Módulo de exemplo
Descrição do que o módulo faz
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ExampleClass:
    """
    Classe de exemplo com documentação

    Args:
        param1: Descrição do parâmetro
        param2: Outro parâmetro
    """

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
