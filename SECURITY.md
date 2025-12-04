# 🛡️ Política de Segurança

## Índice

- [Versões Suportadas](#versões-suportadas)
- [Reportando Vulnerabilidades](#reportando-vulnerabilidades)
- [Processo de Divulgação](#processo-de-divulgação)
- [Práticas de Segurança](#práticas-de-segurança)
- [Configuração Segura](#configuração-segura)
- [Checklist de Segurança](#checklist-de-segurança)

---

## 📋 Versões Suportadas

| Versão | Suportada          | Notas |
|--------|-------------------|-------|
| 0.1.x  | ✅ Sim            | Versão atual em desenvolvimento ativo |
| < 0.1  | ❌ Não            | Versões anteriores não recebem patches |

Recomendamos sempre utilizar a versão mais recente do projeto para garantir que você tenha todas as correções de segurança aplicadas.

---

## 🔐 Reportando Vulnerabilidades

A segurança deste projeto é tratada com seriedade. Agradecemos sua ajuda em reportar vulnerabilidades de forma responsável.

### Como Reportar

**⚠️ NÃO abra issues públicas para vulnerabilidades de segurança.**

1. **Email**: Envie detalhes para o mantenedor do projeto via issue privada
2. **GitHub Security Advisories**: Use a aba "Security" do repositório para reportar diretamente

### O Que Incluir no Relatório

Por favor, inclua o máximo de informações possível:

```markdown
## Descrição da Vulnerabilidade
[Descrição clara e concisa]

## Passos para Reproduzir
1. [Primeiro passo]
2. [Segundo passo]
3. [...]

## Impacto Esperado
[Qual o impacto potencial desta vulnerabilidade?]

## Ambiente
- Versão do projeto: [ex: 0.1.0]
- Sistema Operacional: [ex: Ubuntu 22.04]
- Python: [ex: 3.10.12]
- Outros detalhes relevantes

## Evidências (se aplicável)
[Screenshots, logs sanitizados, PoC]

## Sugestão de Correção (opcional)
[Se você tiver uma sugestão de como corrigir]
```

---

## 📢 Processo de Divulgação

Seguimos um processo de divulgação responsável:

| Etapa | Prazo | Descrição |
|-------|-------|-----------|
| **Confirmação** | 48h | Confirmamos o recebimento do relatório |
| **Triagem** | 7 dias | Avaliamos a severidade e validade |
| **Correção** | 30 dias | Desenvolvemos e testamos a correção |
| **Release** | 7 dias | Publicamos a correção |
| **Divulgação** | 30 dias | Divulgação pública após o patch |

### Níveis de Severidade

| Nível | CVSS Score | Tempo de Resposta |
|-------|------------|-------------------|
| 🔴 **Crítico** | 9.0 - 10.0 | 24 - 48 horas |
| 🟠 **Alto** | 7.0 - 8.9 | 7 dias |
| 🟡 **Médio** | 4.0 - 6.9 | 30 dias |
| 🟢 **Baixo** | 0.1 - 3.9 | 90 dias |

---

## 🔒 Práticas de Segurança

### Autenticação & Autorização

- **API Keys**: Todas as chamadas à API requerem autenticação via header `X-API-Key`
- **Rate Limiting**: Proteção contra ataques de força bruta e DDoS
- **HMAC Signing**: Webhooks são assinados para verificação de origem

```python
# Exemplo de verificação de webhook
import hmac
import hashlib

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### Proteção de Dados

- **Masking de PII**: Dados pessoais são mascarados em logs
- **Sanitização**: Inputs são sanitizados antes do processamento
- **Encriptação**: Dados sensíveis em config são criptografados

### Análise de Código

O projeto utiliza ferramentas automatizadas de segurança:

| Ferramenta | Propósito | Comando |
|------------|-----------|---------|
| **Bandit** | Análise estática de segurança | `bandit -r src/` |
| **Safety** | Verificação de dependências | `safety check` |
| **Dependabot** | Atualizações automáticas | Configurado no GitHub |
| **CodeQL** | Análise semântica de código | GitHub Actions |

---

## ⚙️ Configuração Segura

### Variáveis de Ambiente

**Nunca commite credenciais no repositório.** Use variáveis de ambiente:

```bash
# .env (não versionado)
API_KEY=<chave-forte-32-caracteres>
WEBHOOK_SECRET=<segredo-hmac-256-bits>
TELEGRAM_BOT_TOKEN=<token-do-bot>
REDIS_URL=redis://localhost:6379/0
```

### Geração de Chaves Seguras

```bash
# Gerar API_KEY segura
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Gerar WEBHOOK_SECRET
python -c "import secrets; print(secrets.token_hex(32))"
```

### Configurações Recomendadas

```json
{
  "security": {
    "rate_limit": "100/minute",
    "max_request_size": "10MB",
    "allowed_origins": ["https://seu-dominio.com"],
    "ssl_verify": true,
    "log_pii": false
  },
  "scraping": {
    "headless": true,
    "disable_dev_shm": true,
    "sandbox": false
  }
}
```

### Docker Security

```dockerfile
# Use usuário não-root
USER 1000:1000

# Minimize a superfície de ataque
FROM python:3.10-slim

# Não exponha portas desnecessárias
EXPOSE 8000
```

---

## ✅ Checklist de Segurança

### Antes do Deploy

- [ ] **Credenciais**: Todas as credenciais estão em variáveis de ambiente
- [ ] **API Key**: Chave API com pelo menos 32 caracteres
- [ ] **WEBHOOK_SECRET**: Segredo HMAC configurado
- [ ] **HTTPS**: Apenas conexões HTTPS em produção
- [ ] **Rate Limiting**: Limites apropriados configurados
- [ ] **Logs**: PII masking ativado
- [ ] **Dependências**: Verificadas com `safety check`
- [ ] **Código**: Analisado com `bandit`

### Em Produção

- [ ] **Firewall**: Portas não-essenciais bloqueadas
- [ ] **Atualizações**: Dependências atualizadas regularmente
- [ ] **Monitoramento**: Alertas de segurança configurados
- [ ] **Backup**: Backups criptografados e testados
- [ ] **Logs**: Logs de auditoria habilitados
- [ ] **Rotação**: Credenciais rotacionadas periodicamente

### Comandos de Verificação

```bash
# Verificar segurança completa
make security

# Análise estática
bandit -r src/ -ll

# Dependências vulneráveis
safety check --full-report

# Verificar configuração
python scripts/system_diagnostic.py
```

---

## 🚨 Incidentes de Segurança Conhecidos

| Data | Descrição | Severidade | Status |
|------|-----------|------------|--------|
| - | Nenhum incidente reportado | - | - |

---

## 📚 Recursos Adicionais

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python-security.readthedocs.io/)
- [Docker Security](https://docs.docker.com/engine/security/)
- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)

---

## 🙏 Agradecimentos

Agradecemos a todos os pesquisadores de segurança que ajudam a manter este projeto seguro através de divulgação responsável.

### Hall of Fame

Contribuidores de segurança serão reconhecidos aqui (com permissão):

| Nome | Contribuição | Data |
|------|--------------|------|
| - | Seja o primeiro! | - |

---

## 📞 Contato

Para questões de segurança, use os canais mencionados em [Reportando Vulnerabilidades](#reportando-vulnerabilidades).

**Não use canais públicos (issues, discussions) para reportar vulnerabilidades.**

---

*Última atualização: Abril 2025*
