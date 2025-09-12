# 🚀 Guia de Início Rápido - Doctoralia Scrapper n8n

Este guia vai te ajudar a ter o Doctoralia Scrapper rodando com n8n em menos de 10 minutos!

## 📋 Pré-requisitos

- Docker e Docker Compose instalados
- Git instalado
- Pelo menos 4GB de RAM disponível
- Portas 8000, 5678, 6379 e 4444 livres

## 🏃 Início Rápido em 5 Passos

### Passo 1: Clone e Configure

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/doctoralia-scrapper.git
cd doctoralia-scrapper

# Crie o arquivo de configuração
cp .env.example .env

# Edite o .env com suas configurações
nano .env
```

**Configurações mínimas no `.env`:**

```env
# API Configuration
API_KEY=sua-chave-api-segura-aqui
WEBHOOK_SECRET=seu-segredo-webhook-aqui

# n8n Configuration (opcional, mas recomendado)
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=senha-segura
```

### Passo 2: Inicie os Serviços

```bash
# Inicie todos os containers
docker-compose up -d

# Verifique se estão rodando
docker-compose ps
```

Você deve ver 5 serviços rodando:

- `api` (porta 8000)
- `worker`
- `redis` (porta 6379)
- `selenium` (porta 4444)
- `n8n` (porta 5678)

### Passo 3: Acesse as Interfaces

1. **API Documentation:** <http://localhost:8000/docs>
2. **n8n Interface:** <http://localhost:5678>
   - Login: `admin` (ou o que configurou)
   - Senha: `senha-segura` (ou o que configurou)

### Passo 4: Importe um Workflow de Exemplo

1. Abra o n8n em <http://localhost:5678>
2. Clique em **"Workflows"** → **"Import from File"**
3. Selecione o arquivo: `examples/n8n/sync-scraping-workflow.json`
4. Clique em **"Import"**

### Passo 5: Configure e Execute

1. **Configure a Credencial da API:**
   - No workflow importado, clique no node **"Scrape Doctor"**
   - Clique em **"Credentials"** → **"Create New"**
   - Nome: `Doctoralia API`
   - Tipo: `Header Auth`
   - Header Name: `X-API-Key`
   - Header Value: (mesma chave do .env)
   - Clique em **"Save"**

2. **Teste o Workflow:**
   - Clique no node **"Manual Trigger"**
   - Clique em **"Execute Workflow"**
   - Veja os resultados aparecendo!

## ✅ Verificação Rápida

Execute este comando para verificar se tudo está funcionando:

```bash
# Teste a API diretamente
curl -X POST http://localhost:8000/api/v1/scrape \
  -H "X-API-Key: sua-chave-api-segura-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_url": "https://www.doctoralia.com.br/medico/exemplo",
    "options": {
      "include_reviews": true,
      "max_reviews": 5
    }
  }'
```

## 🎯 Próximos Passos

### Para Uso Básico

1. **Modifique o workflow** para suas URLs de médicos
2. **Configure um Schedule** para executar periodicamente
3. **Adicione notificações** (Telegram, Email, etc.)

### Para Uso Avançado

1. **Importe o workflow completo:**

   ```bash
   examples/n8n/complete-doctoralia-workflow.json
   ```

2. **Configure integrações externas:**
   - Google Sheets para armazenar dados
   - Telegram para notificações
   - Notion para dashboard

3. **Configure processamento em lote:**

   ```bash
   examples/n8n/batch-processing-workflow.json
   ```

## 🔧 Comandos Úteis

```bash
# Ver logs
docker-compose logs -f api
docker-compose logs -f n8n

# Parar serviços
docker-compose stop

# Reiniciar serviços
docker-compose restart

# Limpar tudo (CUIDADO!)
docker-compose down -v

# Atualizar imagens
docker-compose pull
docker-compose up -d
```

## 🆘 Troubleshooting Rápido

### "Connection Refused"

```bash
# Verifique se os containers estão rodando
docker-compose ps
# Se não, inicie-os
docker-compose up -d
```

### "Invalid API Key"

```bash
# Verifique o valor no .env
cat .env | grep API_KEY
# Reinicie o container da API
docker-compose restart api
```

### "n8n não abre"

```bash
# Verifique os logs
docker-compose logs n8n
# Verifique a porta
netstat -an | grep 5678
```

### "Selenium errors"

```bash
# Reinicie o Selenium
docker-compose restart selenium
# Verifique memória disponível
free -h
```

## 📚 Documentação Completa

- [Guia Completo de Workflows](./n8n-workflows-guide.md)
- [API Documentation](http://localhost:8000/docs)
- [Exemplos de Integração](../examples/n8n/)

## 💡 Dicas de Ouro

1. **Sempre teste em modo manual** antes de agendar
2. **Use rate limiting** para evitar bloqueios
3. **Configure alertas** para falhas
4. **Faça backup dos workflows** regularmente
5. **Monitore o uso de recursos** com `docker stats`

## 🎉 Parabéns

Você tem agora o Doctoralia Scrapper rodando com n8n!

**Próximas ações recomendadas:**

1. ✅ Teste com uma URL real de médico
2. ✅ Configure um workflow agendado
3. ✅ Adicione suas primeiras notificações
4. ✅ Explore os workflows avançados

Precisa de ajuda? Crie uma issue no GitHub ou consulte a documentação completa!
