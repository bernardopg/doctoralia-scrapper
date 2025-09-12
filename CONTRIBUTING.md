## 🤝 Contribuindo

Guia curto para colaboração eficiente e consistente.

## 📚 Referências

| Tema | Documento |
|------|-----------|
| Arquitetura | docs/overview.md |
| Quickstart | docs/quickstart.md |
| API | docs/api.md |
| n8n | docs/n8n.md |
| Dev / Padrões | docs/development.md |
| Operações | docs/operations.md |
| Templates | docs/templates.md |

## 🔧 Setup Inicial

```bash
make install-dev
pip install pre-commit && pre-commit install
make test
```

## 🚀 Fluxo de Trabalho

```bash
git checkout -b feat/nome-claro
make lint test
git commit -m "feat: descreve mudança"
git push origin feat/nome-claro
```

Abrir PR com contexto + passos de teste.

## 📝 Commits Convencionais

Prefixes: feat | fix | docs | test | chore | refactor | perf | ci | security

## ✅ Checklist Pull Request

- [ ] Testes verdes
- [ ] Lint ok
- [ ] Sem segredos
- [ ] Documentação atualizada (se necessário)
- [ ] Sem TODO crítico

## 🧪 Testes

```bash
make test
pytest -k critical
```

## 🧩 Código & Qualidade

- Type hints em novas funções
- Logs estruturados (sem PII sensível)
- Funções coesas e curtas
- Exceções específicas (ScrapingError etc.)

## 🔐 Segurança

- `.env` privado / não versionado
- Não expor chaves em exemplos reais
- Revisar logs antes de anexar em issues

## 🛡️ Revisão Prioriza

1. Corretude
2. Clareza
3. Robustez / Resiliência
4. Segurança
5. Manutenibilidade

## 🐛 Debug Rápido

```bash
python scripts/system_diagnostic.py
grep ERROR -R data/logs
```

## 📞 Suporte Interno

Abrir issue com: passos, ambiente e logs relevantes.

Obrigado por contribuir 🚀
