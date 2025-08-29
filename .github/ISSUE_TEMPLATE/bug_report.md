---
name: Bug Report
about: Reporte um bug para nos ajudar a melhorar o Doctoralia Scraper
title: "[BUG] "
labels: ["bug", "triage"]
assignees: ""
---

## Descrição do Bug

**Uma descrição clara e concisa do bug.** Por exemplo: "O scraper falha ao carregar a página do Doctoralia após as últimas atualizações do site"

## Para Reproduzir

**Passos detalhados para reproduzir o comportamento:**

1. Configure o ambiente: `make setup`
2. Execute o comando: `python main.py scrape --url "https://www.doctoralia.com.br/medico/especialidade/cidade"`
3. Aguarde o carregamento da página
4. Observe o erro no console/logs

## Comportamento Esperado

**O que deveria acontecer:**

- O scraper deveria carregar a página com sucesso
- Extrair todas as avaliações disponíveis
- Salvar os dados no formato JSON esperado
- Enviar notificação via Telegram (se configurado)

## Comportamento Atual

**O que está acontecendo:**

- Erro de timeout ao carregar a página
- Elemento não encontrado na página
- Dados incompletos sendo salvos
- Falha na extração de avaliações

## Screenshots/Logs

**Se aplicável, adicione screenshots ou logs relevantes:**

### Logs de Erro

```text
2025-01-15 14:30:25 ERROR [scraper] Element not found: .review-item
Traceback (most recent call last):
  File "src/scraper.py", line 245, in extract_reviews
    reviews = self.driver.find_elements(By.CLASS_NAME, "review-item")
  File "selenium/webdriver/remote/webdriver.py", line 741, in find_elements
    return self.execute(Command.FIND_ELEMENTS, {"using": by, "value": value})['value']
selenium.common.exceptions.NoSuchElementException: Message: no such element: Unable to locate element
```

### Screenshot da Página

Adicione screenshot do erro aqui

## Ambiente (complete as informações)

- **OS**: [ex: Ubuntu 20.04 LTS / Windows 11 / macOS 12.6]
- **Python Version**: [ex: 3.11.0]
- **Browser**: [ex: Google Chrome 120.0.6099.109]
- **WebDriver**: [ex: ChromeDriver 120.0.6099.109]
- **Versão do Projeto**: [ex: v1.2.0]
- **URL Testada**: [ex: https://www.doctoralia.com.br/medico/especialidade/cidade]

## Contexto Adicional

**Informações adicionais sobre o bug:**

### Possível Causa

- Mudanças no layout do Doctoralia
- Atualização do Chrome/WebDriver
- Problemas de rede/tempo de resposta
- Configurações incorretas

### Impacto

- **Severidade**: [Crítica/Média/Baixa]
- **Frequência**: [Sempre/Às vezes/Raramente]
- **Usuários Afetados**: [Todos/Alguns/Específicos]

### Workaround Temporário

```bash
# Solução temporária se existir
python main.py scrape --url "URL" --headless=false --timeout=120
```

## Checklist de Debug

- [ ] Executei `make health` para verificar saúde do sistema
- [ ] Testei com `make test` para verificar se testes passam
- [ ] Verifiquei logs em `data/logs/`
- [ ] Executei `python scripts/system_diagnostic.py`
- [ ] Testei com diferentes URLs
- [ ] Verifiquei conectividade de rede
- [ ] Testei com navegador não-headless

## Notas Adicionais

**Qualquer informação adicional que possa ajudar:**

- Comportamento observado em diferentes horários
- Padrões específicos que trigger o bug
- Configurações customizadas sendo usadas
- Ambiente de produção vs desenvolvimento
