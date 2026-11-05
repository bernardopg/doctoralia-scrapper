# Inventário de integração n8n (REL-07)

Este inventário é parcial. Preservar serviço, volume, endpoints e exemplos até que responsáveis confirmem os consumidores e uma migração com retorno tenha sido ensaiada. Os exemplos descrevem possibilidades no repositório, não provam que workflows estejam instalados ou em uso.

## Observado no repositório

| Fluxo ou consumidor | Dados, gatilhos e destinos | Possível substituição e dependências |
| --- | --- | --- |
| `examples/n8n/sync-scraping-workflow.json` | Manual; URL do perfil, `/v1/scrape:run`, resultado e sentimento; Telegram. | Cliente da API e envio de relatório; requer credenciais, tratamento de erros e equivalência de dados. |
| `examples/n8n/async-webhook-workflow.json` | Webhook de entrada, URL, `/v1/jobs`, receptor de callback, verificação de assinatura, resumo e Telegram. | Cliente de jobs e receptor próprio ou polling; requer HMAC, política de URL, entrega/retry e confirmação dos chamadores. |
| `examples/n8n/batch-processing-workflow.json` | Lista de URLs em Google Sheets, lotes síncronos, agregação, atualização de planilha e Telegram. | Processador de lotes e conectores Sheets/Telegram; requer limites, credenciais e reconciliação de falhas. |
| `examples/n8n/complete-doctoralia-workflow.json` | Manual, webhook e agenda; URLs, jobs e polling, métricas/sentimento, alertas; Sheets, Notion, Telegram, email e Slack. | Scheduler interno cobre apenas parte do caso de notificações Telegram; os demais conectores, filtros, retries, alertas e responsáveis precisam de substituição validada. |
| API e dashboard | `POST /v1/scrape:run`, `POST /v1/jobs`, `GET /v1/jobs/{job_id}` e proxy do dashboard; URL, opções, resultado e status. `POST /v1/hooks/n8n/scrape` aceita trigger assinado e cria job. | Contratos continuam disponíveis independentemente do n8n; consumidores e chaves devem ser identificados. |
| Worker | Callback opcional em sucesso ou falha com resultado e assinatura HMAC; políticas de TLS/domínios e retries existentes. | Polling ou receptor compatível exige migração dos destinos e validação da assinatura e falhas. |
| Scheduler Telegram | Usa dados extraídos do scraper e possui sua própria configuração de notificações. | Pode cobrir apenas agendamento/Telegram suportados, não planilhas, callbacks ou todos os conectores. |

Os resultados podem conter dados pessoais de autores e avaliações, dados do perfil, análise e respostas geradas. Migração e testes devem respeitar as configurações de privacidade existentes. As credenciais e destinatários reais não estão neste inventário. O código de normalização compartilhada está em `src/normalization.py`; o caminho anterior continua como shim. A integração futura com REL-02/PR #211 deve reaplicar os imports sobre a implementação então vigente e verificar estados parcial, desconhecido e falha sem incorporar aquele trabalho aqui.

No Compose base, n8n usa `n8n-data`, depende da API saudável e publica 5678 apenas em loopback. O overlay de produção remove a porta e configura HTTPS/URLs para o domínio n8n; `caddy/Caddyfile` encaminha o domínio n8n ao serviço. O overlay GHCR troca imagens da API e worker. Revisão de configuração não comprova acesso externo ou ausência de consumidores. `docs/n8n.md`, `docs/api.md`, `docs/operations.md` e `docs/telegram-notifications.md` descrevem integrações adicionais.

## Observado localmente

Em 2026-11-05, com a instalação parada apenas para leitura, o banco SQLite do n8n (`database.sqlite` com `-wal` e `-shm`, copiados do volume `doctoralia-scrapper_n8n-data` para fora do checkout e lidos em cópia) continha:

| Tabela | Registros |
| --- | --- |
| `workflow_entity` | 0 |
| `shared_workflow` | 0 |
| `credentials_entity` | 0 |
| `webhook_entity` | 0 |
| `execution_entity` | 0 |

`n8n list:workflow` também não listou workflows, e o backup `scripts/backup_restore.sh backup` registrou exportação vazia. Portanto esta instalação nunca executou workflows nem registrou webhooks no n8n. Chamadores externos dos endpoints da API (`/v1/hooks/n8n/scrape`, `/v1/jobs`) continuam fora do alcance desta verificação; os endpoints permanecem disponíveis.

## Exportação, migração e retorno planejados

1. Identificar responsáveis por instância, workflows, credenciais, gatilhos e destinos; inventariar também chamadores externos e endpoints expostos. Obter acesso apropriado por canal seguro, sem registrar segredos.
2. Planejar janela e backup consistente do banco e do volume, incluindo a chave de criptografia e configuração necessária em armazenamento seguro separado. Usar procedimento de backup apropriado à versão e ao banco, validado pelo operador; preservar cópias e controlar acesso e retenção. Não copiar banco ativo de forma inconsistente nem executar CLI que migre a instalação real.
3. Exportar workflows e credenciais apenas com procedimento aprovado e compatível com a versão, para diretório privado fora do checkout. Exportações podem conter URLs, código, dados pessoais e segredos: não publicar arquivos brutos; compartilhar apenas inventário sanitizado. Preservar IDs, ligações, configurações e material necessário para restaurar. Limpar temporários após verificação.
4. Restaurar e importar primeiro numa stack descartável isolada, com fixtures sintéticas, credenciais e destinos falsos e saída de rede bloqueada. Conferir IDs, estados, triggers, conexões e dados sem ativar gatilhos; testar contratos e retorno apenas no ambiente descartável. Não usar dados de produção como fixtures.
5. Migrar cada consumidor com responsável, destino, substituto, teste de equivalência, observabilidade e plano de reversão registrados. Validar estados completos, parciais e falhas, autenticação, assinatura, privacidade, retries e duplicatas antes de qualquer troca.
6. Para retorno, desviar consumidores para a instância anterior preservada; se for necessária restauração, usar backup consistente, versão e chave compatíveis, em ambiente isolado primeiro, e verificar workflows, credenciais e conectividade antes de reativar sob controle do operador.

## Gates para tornar opcional ou remover

**Opcional (2.8.0):** atendido para esta instalação pelo inventário acima. O serviço passa a subir só com `docker compose --profile n8n up -d`; volume `n8n-data`, exemplos, endpoints e o proxy do Caddy são preservados. As credenciais do n8n só são exigidas quando o serviço sobe.

**Remoção do serviço e do volume:** continua bloqueada. Exige confirmação de que nenhuma outra instalação ou chamador externo depende do n8n, e exportação/restauração ensaiadas onde houver workflows. Nada é removido nesta versão.
