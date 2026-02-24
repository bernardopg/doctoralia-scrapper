# Quickstart

Este guia mostra o fluxo mínimo para colocar o sistema em funcionamento.

## 1. Pré-requisitos

- Python 3.10+
- Google Chrome instalado
- Git
- (Opcional) Docker + Docker Compose

## 2. Clonar e Instalar

```bash
git clone <REPO_URL>
cd doctoralia-scrapper
make install
```

## 3. Configuração Essencial

```bash
cp .env.example .env
cp config/config.example.json config/config.json
```

Edite `.env` com `API_KEY` e, opcionalmente, credenciais do Telegram.

## 4. Primeiro Scraping

```bash
make run-url URL=https://www.doctoralia.com.br/medico/exemplo/especialidade/cidade
```

Saída esperada: JSON da extração em `data/` + logs em `logs/`.

## 5. Geração de Respostas (Opcional)

```bash
make generate
```

## 6. Dashboard

```bash
make dashboard   # http://localhost:5000
```

## 7. API

```bash
make api         # http://localhost:8000/docs
```

Teste rápido (substitua pela sua chave configurada no `.env`):

```bash
make run-url URL="https://www.doctoralia.com.br/medico/exemplo/especialidade/cidade"
```

Ou via API diretamente — consulte `docs/api.md` para exemplos com autenticação.

## 8. Execução Contínua

```bash
make daemon      # Loop de scraping agendado
make status      # Estado atual
make stop        # Parar daemon
```

## 9. Modo Docker (Recomendado para Produção)

```bash
cp .env.example .env
# Edite .env com suas chaves

docker-compose up -d
docker-compose ps
```

Serviços disponíveis:
- **API**: http://localhost:8000/docs
- **n8n**: http://localhost:5678
- **Selenium VNC**: http://localhost:7900

Para importar workflows n8n: abra o n8n e importe os JSONs de `examples/n8n/`.

## 10. Troubleshooting Rápido

| Sintoma | Ação |
|---------|------|
| Chrome/WebDriver erro | Verificar versão do Chrome, reinstalar driver |
| Timeout frequente | Aumentar `scraping.timeout` em `config/config.json` |
| Bloqueio/site lento | Ajustar `delay_min`/`delay_max` no config |
| Sem avaliações detectadas | Validar URL no navegador manualmente |
| Connection refused (Docker) | `docker-compose ps` e verificar logs |
| Invalid API key | Conferir `API_KEY` no `.env` e reiniciar: `docker-compose restart api` |

## 11. Próximos Passos

- Referência da API: `docs/api.md`
- Workflows n8n: `docs/n8n.md`
- Operações e monitoramento: `docs/operations.md`
- Deploy em produção: `docs/deployment.md`
- Desenvolvimento: `docs/development.md`

---

Para diagnóstico rápido: `python scripts/system_diagnostic.py` ou `make health`.
