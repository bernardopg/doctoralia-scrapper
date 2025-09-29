# GitHub Configuration

Esta pasta contém todas as configurações e automações do GitHub para o projeto Doctoralia Scrapper.

## 📁 Estrutura

```text
.github/
├── workflows/          # GitHub Actions workflows
│   ├── ci.yml         # Integração contínua
│   ├── docker.yml     # Build e push de imagens Docker
│   └── release.yml    # Processo de release automático
├── ISSUE_TEMPLATE/    # Templates para issues
│   ├── bug_report.md
│   └── feature_request.md
├── PULL_REQUEST_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── dependabot.yml     # Configuração do Dependabot
└── README.md          # Este arquivo
```

## 🔄 Workflows

### CI Workflow (`ci.yml`)

**Trigger:** Push e PR para `main`, dispatch manual

**Jobs:**

- **lint**: Verifica formatação (Black, isort, Flake8, MyPy)
- **security**: Scans de segurança (Bandit, Safety, TruffleHog)
- **test**: Executa testes em múltiplas versões do Python (3.10, 3.11, 3.12)
- **build**: Build do pacote Python
- **all-checks-passed**: Verifica se todos os jobs passaram

**Recursos:**

- Cache de dependências Poetry
- Coverage report para Codecov
- Artifacts de testes e build
- Matrix strategy para múltiplas versões Python

### Docker Workflow (`docker.yml`)

**Trigger:** Push para `main`, tags `v*`, PRs, dispatch manual

**Jobs:**

- **build-and-push**: Build de imagens Docker (api e worker)
- **scan-vulnerabilities**: Scan de vulnerabilidades com Trivy
- **integration-test**: Testes de integração com Docker

**Recursos:**

- Multi-stage build (api e worker)
- GHCR (GitHub Container Registry)
- SBOM generation
- Trivy security scanning
- Build cache com GitHub Actions

### Release Workflow (`release.yml`)

**Trigger:** Tags `v*.*.*`, dispatch manual

**Jobs:**

- **create-release**: Cria release no GitHub com changelog
- **build-and-publish**: Build e publicação no PyPI
- **build-docker**: Build de imagens Docker versionadas
- **notify**: Notificações e sumário

**Recursos:**

- Changelog automático
- Publicação no PyPI
- Docker images versionadas
- Suporte a pre-releases

## 🤖 Dependabot

O Dependabot está configurado para atualizar automaticamente:

- **Python dependencies**: Semanalmente às segundas, 09:00
- **GitHub Actions**: Semanalmente às segundas, 09:00
- **Docker base images**: Semanalmente às segundas, 09:00

Configurações:

- Limite de 10 PRs abertos para Python
- Limite de 5 PRs abertos para Actions e Docker
- Auto-assign para @bernardopg
- Labels automáticos por tipo

## 📝 Issue Templates

### Bug Report

Template detalhado para reportar bugs incluindo:

- Descrição e reprodução
- Comportamento esperado vs atual
- Logs e screenshots
- Informações de ambiente
- Checklist de debug

### Feature Request

Template para solicitar novas funcionalidades (existente)

## 📋 Pull Request Template

Template padronizado incluindo:

- Tipo de mudança
- Como foi testado
- Checklist de verificação
- Screenshots (se aplicável)
- Notas adicionais

## 🔐 Secrets Necessários

Configure os seguintes secrets no GitHub:

### Para Release Workflow

- `PYPI_TOKEN`: Token de autenticação do PyPI
- `CODECOV_TOKEN`: Token do Codecov (opcional mas recomendado)

### Para Workflows em Geral

- `GITHUB_TOKEN`: Fornecido automaticamente pelo GitHub

## 🚀 Como Usar

### Executar Workflows Manualmente

Workflows com `workflow_dispatch` podem ser executados manualmente:

```bash
# Via GitHub CLI
gh workflow run ci.yml
gh workflow run docker.yml
gh workflow run release.yml --field version=v1.2.3
```

### Criar um Release

1. **Via Git Tag:**

```bash
git tag -a v1.2.3 -m "Release v1.2.3"
git push origin v1.2.3
```

2. **Via Workflow Dispatch:**

- Acesse Actions → Release → Run workflow
- Insira a versão (ex: v1.2.3)
- Execute

### Workflow Status Badges

Adicione ao README principal:

```markdown
![CI](https://github.com/bernardopg/doctoralia-scrapper/workflows/CI/badge.svg)
![Docker](https://github.com/bernardopg/doctoralia-scrapper/workflows/Docker%20Build%20%26%20Push/badge.svg)
```

## 🔍 Troubleshooting

### Workflow Falhou - O Que Fazer?

1. **Check logs:** Acesse Actions → Workflow → Job → Step
2. **Re-run:** Clique em "Re-run all jobs"
3. **Dependências:** Verifique se Poetry.lock está atualizado
4. **Secrets:** Confirme que secrets estão configurados

### Erros Comuns

**Poetry install falha:**

- Limpe cache: Settings → Actions → Caches
- Verifique poetry.lock está commitado

**Docker build falha:**

- Verifique Dockerfile syntax
- Confirme que targets (api, worker) existem
- Check build context

**Tests falham:**

- Execute localmente: `poetry run pytest`
- Verifique dependências de teste
- Confirme que Redis está configurado

## 📚 Referências

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Poetry Docs](https://python-poetry.org/docs/)
- [Dependabot Config](https://docs.github.com/en/code-security/dependabot)

## 🤝 Contribuindo

Para modificar workflows:

1. Teste localmente quando possível (ex: com [act](https://github.com/nektos/act))
2. Use `workflow_dispatch` para testes
3. Documente mudanças importantes
4. Siga as melhores práticas do GitHub Actions

## 📞 Suporte

Para questões sobre workflows:

- Abra uma issue com label `github-actions`
- Consulte os logs detalhados em Actions
- Verifique este README primeiro
