# Dashboard Workspace & Geração de Respostas

## Visão Geral

O dashboard foi reorganizado em um workspace operacional com páginas separadas por tarefa:

- `/`:
  overview consolidado com volume de rastreios, perfis monitorados, pendências, favoritos e linha do tempo.
- `/profiles`:
  análise por perfil com filtros por data, favoritos, avaliação média, histórico de rastreios e últimos comentários.
- `/responses`:
  fila de comentários sem resposta, com geração manual de sugestões, edição e persistência no snapshot local.
- `/me`:
  perfil do operador, nome de exibição, username e favoritos para acelerar scraping e priorização.
- `/history`:
  inventário de snapshots persistidos, com status `latest` vs `outdated`, exclusão individual e prune global.
- `/reports`:
  visão analítica com timeline, top perfis, inventário de arquivos e candidatos de limpeza.
- `/settings`:
  configuração central de scraping, integrações, segurança e geração automática.

## Modos de Geração

A geração de respostas agora aceita quatro modos:

- `local`:
  usa templates e heurísticas locais, sem dependência de provedor externo.
- `openai`:
  usa `OPENAI_API_KEY` e o modelo configurado em `generation.openai_model`.
- `gemini`:
  usa `GEMINI_API_KEY` ou `GOOGLE_API_KEY` e `generation.gemini_model`.
- `claude`:
  usa `CLAUDE_API_KEY` ou `ANTHROPIC_API_KEY` e `generation.claude_model`.

Os parâmetros expostos na UI incluem:

- provedor padrão (`generation.mode`)
- API keys por provedor
- modelo por provedor
- `temperature`
- `max_tokens`
- `system_prompt`

## Persistência de Configuração

O arquivo `config/config.json` passou a concentrar também:

- `generation`
- `user_profile`

No Docker Compose, `api`, `worker` e `dashboard` compartilham `./config:/app/config`, então alterações feitas na UI ficam disponíveis para toda a stack sem divergência entre containers.

## Fluxo de Jobs e Snapshot

O workspace do dashboard depende de snapshots persistidos em `data/`. O comportamento esperado é:

- o `worker` conclui o scrape
- normaliza os reviews e converte seus IDs para `string`
- salva um snapshot JSON local
- só então o perfil passa a aparecer em `/`, `/profiles`, `/responses`, `/history` e `/reports`

Com isso:

- jobs que terminam com `status=failed` não poluem mais o workspace
- `/history` reflete o status lógico do job em vez de assumir `completed` apenas porque o RQ encerrou a execução
- snapshots antigos podem ser limpos com prune sem apagar o último estado válido de cada perfil

Se um perfil não aparecer nas páginas do workspace após o scraping:

1. confira `/history` e o inventário de snapshots
2. confira `/api/tasks/<job_id>` para ver o `status` lógico
3. valide se o arquivo JSON foi salvo em `data/`
4. se necessário, execute prune dos snapshots antigos antes de um novo scrape

## Favoritos e Operação

Os favoritos do operador ficam em `user_profile.favorite_profiles` e são usados para:

- priorizar navegação e visualização na sidebar
- destacar perfis nas páginas de overview e perfis
- filtrar a fila de respostas pendentes
- acelerar o preenchimento de novos scrapes e atalhos operacionais

## Fluxo Recomendado

1. Configure o modo padrão de geração e as chaves em `/settings`.
2. Cadastre seus médicos prioritários em `/me`.
3. Use `/history` para remover snapshots antigos e manter a base sem sobreposição.
4. Use `/profiles` para acompanhar histórico e pendências por perfil.
5. Use `/responses` para gerar, editar e salvar sugestões para reviews sem resposta.
6. Use `/reports` para monitorar o inventário agregado e identificar novos excessos de snapshots.

## Próximos Passos Sugeridos

- mascarar segredos na UI
- adicionar geração em lote por perfil
- registrar custo/uso por provedor externo
