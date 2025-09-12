# 🚀 Quickstart

Este guia mostra o fluxo mínimo para colocar o sistema em funcionamento em poucos minutos.

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

Copie o template e ajuste se necessário:

```bash
cp config/config.example.json config/config.json
```

Edite campos de `telegram` apenas se for usar notificações.

## 4. Primeiro Scraping

```bash
make run-url URL=https://www.doctoralia.com.br/medico/exemplo/especialidade/cidade
```

Saída esperada: registro da extração em `data/extractions/` + logs em `logs/main.log` (ou data/logs dependendo da configuração).

## 5. Geração de Respostas (Opcional)

```bash
make generate   # gera respostas para avaliações sem resposta
```

## 6. Dashboard

```bash
make dashboard   # http://localhost:5000
```

## 7. API

```bash
make api         # http://localhost:8000/docs
```

## 8. Execução Contínua

```bash
make daemon
make status
make stop
```

## 9. Estrutura Produzida

```text
data/
  extractions/<timestamp>_...  # JSONs da execução
  responses/                   # Respostas geradas
  logs/                        # Logs rotacionados
```

## 10. Troubleshooting Rápido

| Sintoma | Ação |
|---------|------|
| Chrome/WebDriver erro | Verificar versão do Chrome, reinstalar driver |
| Timeout frequente | Aumentar `scraping.timeout` em config.json |
| Bloqueio/site lento | Ajustar `delay_min/delay_max` |
| Sem avaliações detectadas | Validar URL; testar no navegador manualmente |

## 11. Próximos Passos

- Ler `docs/api.md` para integração
- Configurar workflows n8n `docs/n8n.md`
- Monitorar saúde e métricas `docs/operations.md`
- Práticas de desenvolvimento `docs/development.md`

---
Para dúvidas rápidas: `python scripts/system_diagnostic.py` ou ver logs em `data/logs/`.
