# 📆 Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.

Formato inspirado em Keep a Changelog. Sem versionamento semântico formal ainda; adotamos marcos funcionais.

## [2025-09-12] Reestruturação Documentação

### Adicionado

- Nova estrutura modular em `docs/` (overview, api, n8n, operations, development, templates, quickstart, changelog)
- README enxuto com links

### Alterado

- Conteúdo de melhorias (antigo IMPROVEMENTS.md) migrado para este changelog
- Consolidação de arquivos n8n em único `docs/n8n.md`
- Simplificação de instruções redundantes de instalação / uso

### Removido

- `README_OPTIMIZED.md`
- `README_N8N.md`
- `README_N8N_INTEGRATION.md`
- `IMPROVEMENTS.md`
- `DAILY_AUTOMATION.md` (conteúdo incorporado em operations)
- `ROLLOUT_PLAN.md` (marcos incorporados em overview/changelog)
- Documentos duplicados de quickstart / n8n integration

## [2025-09-11] Otimização v2.0 (Resumo Migrado)

### Adicionado

- Cache de extrações
- Make targets: dashboard, api, diagnostic, health, optimize

### Alterado

- Redução de dependências (≈40%)
- Padronização de docstrings e type hints

### Removido

- Arquivos de debug e scripts temporários

## Estrutura Futuras Entradas (Template)

```markdown
## [YYYY-MM-DD] <Resumo Curto>
### Adicionado
-
### Alterado
-
### Corrigido
-
### Removido
-
```

---
Para histórico anterior informal, consultar logs de commits do repositório.
