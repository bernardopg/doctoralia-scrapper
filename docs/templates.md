# 📝 Templates & Mensagens

## Objetivo

Centralizar customização de respostas automáticas e notificações.

## Estrutura de Templates

Local principal: `config/templates.py` e `config/telegram_templates.py`.

## Tipos de Template

| Tipo | Uso |
|------|-----|
| Resposta Positiva | Agradecimento direto |
| Resposta Neutra | Reforço de disponibilidade |
| Resposta Negativa Leve | Empatia + convite para contato |
| Resposta Negativa Forte | Mitigação + canal privado |
| Notificação Telegram | Resumo rápido evento |

## Placeholders Suportados (Exemplos)

| Placeholder | Significado |
|-------------|------------|
| `{doctor_name}` | Nome do(a) médico(a) |
| `{review_rating}` | Nota da avaliação |
| `{review_excerpt}` | Trecho reduzido da avaliação |
| `{sentiment_label}` | rótulo (positive/neutral/negative) |
| `{response_quality}` | Score de qualidade calculado |

## Exemplo de Template de Resposta

```python
TEMPLATES = {
  "positive": [
    "Muito obrigado pelo seu feedback, {patient_name}! Ficamos felizes em saber que sua experiência foi positiva.",
    "Agradecemos sua avaliação, {patient_name}. Seguimos à disposição!"
  ],
  "negative": [
    "Sentimos muito por não atender totalmente suas expectativas, {patient_name}. Gostaríamos de entender melhor para melhorar."
  ]
}
```

## Seleção de Template (Heurística Simplificada)

1. Classificação de sentimento (VADER compound)
2. Mapeamento para categoria (`compound >= 0.3 -> positive`, `<= -0.3 -> negative`, resto neutro)
3. Escolha aleatória (ou determinística futura) dentro da categoria

## Personalização Recomendada

- Criar variações suficientes para evitar repetição visível
- Evitar promessas legais/sensíveis automáticas
- Manter tom consistente (profissional + acolhedor)

## Notificações Telegram Exemplo

```python
TELEGRAM_TEMPLATES = {
  "new_review": "🆕 Nova avaliação para {doctor_name} | ⭐ {review_rating}\n{review_excerpt}",
  "alert_negative": "⚠️ Avaliação negativa detectada ({review_rating}⭐)\nTrecho: {review_excerpt}",
  "summary_daily": "📊 Resumo diário: {total_reviews} avaliações, {positive_pct}% positivas"
}
```

## Boas Práticas

| Tema | Dica |
|------|------|
| Neutralidade | Evitar nomes ou dados sensíveis em logs |
| Consistência | Revisar tom textual periodicamente |
| Evolução | Registrar mudanças em `docs/changelog.md` |
| Escalabilidade | Introduzir camada de seleção com pesos |

## Extensões Futuras

| Ideia | Descrição |
|-------|-----------|
| Suporte LLM | Gerar variação dinâmica com verificação |
| A/B Testing | Medir engajamento por variante |
| Score Adaptativo | Ajustar resposta conforme histórico paciente |

## Campo para Qualidade de Resposta

Score exemplo (0..1) considerando:

- Entrega (agradecimento/empathia)
- Clareza (frases diretas)
- Concisão (limite de caracteres)
- Adequação (tom vs sentimento original)

## Checklist ao Criar Novo Template

- [ ] Variáveis existem e são suportadas
- [ ] Sem informações sensíveis fixas
- [ ] Sem menção a diagnóstico
- [ ] Tom consistente
- [ ] Adicionado teste se necessário

---
Mais detalhes de análise em `src/response_quality_analyzer.py`.
