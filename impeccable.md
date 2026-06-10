# Impeccable — Design System

Design system do Doctoralia Scrapper. Guia canônico de tokens, componentes e padrões visuais.

---

## 1. Philosophy

Interface operacional para profissionais. Sem decoração gratuita. Cada elemento serve uma função.

- **Clareza primeiro** — hierarquia visual clara, densidade informacional alta sem ruído
- **Tema-agnóstico** — light e dark de primeira classe; nenhum elemento hardcoded
- **Acessibilidade** — contrast ratio ≥ 4.5:1 (WCAG AA), focus rings visíveis, reduced-motion respeitado
- **Médico + dados** — ECG heartbeat (medicina) + data point circular (análise); sem stock art

---

## 2. Color System

### Brand Tokens

| Token | Light | Dark | Uso |
|-------|-------|------|-----|
| `--apple-blue` | `#146C94` | `#6BB7D6` | Ações primárias, links, focus |
| `--apple-blue-hover` | `#0C4D6F` | `#8DCCE5` | Hover em elementos azuis |
| `--apple-green` | `#168C61` | `#68D39B` | Sucesso, status positivo, dot de dados |
| `--apple-red` | `#C9362B` | `#FF8B82` | Erros, alertas destrutivos |
| `--apple-orange` | `#B65F00` | `#FFB86A` | Avisos, bootstrap hints |
| `--apple-yellow` | `#A37400` | `#FFD86B` | Alertas secundários |
| `--apple-purple` | `#6750A4` | `#B5A7E8` | Tags, badges alternativos |

### Semantic Tokens

| Token | Light | Dark | Uso |
|-------|-------|------|-----|
| `--bg-primary` | `#FEFFFD` | `#101815` | Fundo do conteúdo principal |
| `--bg-secondary` | `#F8FAF9` | `#0B1210` | Fundo do body |
| `--bg-tertiary` | `#EEF3F1` | `#18231F` | Fundo de elementos agrupados |
| `--surface-raised` | `#FFFFFF` | `#141F1B` | Cards, modais, inputs |
| `--surface-muted` | `#F4F8F6` | `#111C18` | Surface alternativa suave |
| `--text-primary` | `#111B17` | `#F7FBF9` | Texto principal |
| `--text-secondary` | `#455750` | `#C8D5D1` | Labels, descrições |
| `--text-tertiary` | `#62746E` | `#9AADA6` | Placeholders, metadata |
| `--border-color` | `#DDE7E4` | `#263833` | Bordas de containers |
| `--divider-color` | `#DDE7E4` | `#263833` | Divisores horizontais |
| `--sidebar-bg` | `#F7FBF9` | `#0E1714` | Fundo da sidebar |
| `--sidebar-hover` | `#EEF3F1` | `#18231F` | Hover nos itens de nav |
| `--focus-ring` | `rgba(20,108,148,.28)` | `rgba(107,183,214,.34)` | Anel de foco (outline) |
| `--overlay-backdrop` | `rgba(8,18,16,.56)` | `rgba(2,8,7,.72)` | Backdrop de modal |

### Neutral Scale

| Token | Light | Dark |
|-------|-------|------|
| `--gray-50` | `#F8FAF9` | `#111A17` |
| `--gray-100` | `#EEF3F1` | `#18231F` |
| `--gray-200` | `#DDE7E4` | `#24332E` |
| `--gray-300` | `#C3D1CD` | `#385049` |
| `--gray-400` | `#8FA09A` | `#8AA099` |
| `--gray-500` | `#62746E` | `#A8BBB5` |
| `--gray-600` | `#455750` | `#C8D5D1` |
| `--gray-700` | `#30413B` | `#DDE6E3` |
| `--gray-800` | `#1F2C27` | `#EEF4F1` |
| `--gray-900` | `#111B17` | `#F7FBF9` |

---

## 3. Typography

### Font Stack

```css
--font-sans: ui-sans-serif, -apple-system, BlinkMacSystemFont,
             'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
--font-mono: 'SF Mono', Monaco, 'Cascadia Code', 'Courier New', monospace;
```

### Scale

| Uso | Size | Weight | Letter-spacing |
|-----|------|--------|----------------|
| Stat value grande | `40px` | `700` | `-0.04em` |
| Heading de página | `26–30px` | `700` | `-0.03em` |
| Card title | `18px` | `600` | `-0.01em` |
| Body padrão | `15px` | `400` | `0` |
| Label de form | `13–14px` | `500` | `0` |
| Badge / nav section | `11px` | `600` | `0.5px` |
| Metadata / mono | `12–13px` | `400` | `0` |

---

## 4. Spacing & Radius

### Spacing

Base 4px. Escala: `4 8 12 16 20 24 28 32 40 48 64`.

Padding interno de cards: `20–24px`. Gap entre cards: `16–20px`. Padding de página: `24px`.

### Border Radius

| Token | Value | Uso |
|-------|-------|-----|
| `--radius-sm` | `6px` | Tags, badges, chips |
| `--radius-md` | `10px` | Inputs, botões, tooltips |
| `--radius-lg` | `14px` | Cards, dropdowns |
| `--radius-xl` | `20px` | Modais, painéis |
| `--radius-full` | `9999px` | Pills, avatares |

---

## 5. Shadows

| Token | Value | Uso |
|-------|-------|-----|
| `--shadow-xs` | `0 1px 2px rgba(0,0,0,.05)` | Hover sutil |
| `--shadow-sm` | `0 1px 3px rgba(0,0,0,.10)` | Cards em repouso |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,.10)` | Dropdowns |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,.10)` | Modais pequenos |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,.10)` | Modais grandes |

Dark mode: sombras com opacidade mais alta (`.24`–`.42`) compensando o fundo escuro.

---

## 6. Dark Theme

### Implementação

Tema controlado pelo atributo `data-theme` no `<html>`:

```html
<html data-theme="light">
```

Toggled via JS, persistido em `localStorage`:

```javascript
// Hidratação inline no <head> — previne flash (FOUC)
(() => {
  const theme = localStorage.getItem('dashboard-theme') ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = theme;
})();
```

### Regra CSS

```css
:root[data-theme="dark"] {
  color-scheme: dark;
  --apple-blue: #6BB7D6;
  /* ... demais overrides */
}
```

`color-scheme: dark` instrui o browser a usar estilos nativos escuros (scrollbars, inputs, select).

### Webkit Autofill Override

```css
:root[data-theme="dark"] input:-webkit-autofill,
:root[data-theme="dark"] input:-webkit-autofill:hover,
:root[data-theme="dark"] input:-webkit-autofill:focus {
  -webkit-box-shadow: 0 0 0 1000px var(--surface-raised) inset !important;
  -webkit-text-fill-color: var(--text-primary) !important;
}
```

### Regra de desenvolvimento

**Nunca use cores hardcoded.** Toda cor deve referenciar um token CSS. Se uma cor nova for necessária, adicionar ao bloco `:root` e ao bloco `:root[data-theme="dark"]`.

---

## 7. Logo

### Conceito

ECG heartbeat wave (medicina/saúde) + data point circular com glow (análise/dados).
Paleta: `#146C94` (azul teal) + `#168C61` (verde esmeralda).

### Variantes disponíveis

| Arquivo | Uso | Fundo |
|---------|-----|-------|
| `static/icon.svg` | Ícone 512×512 padrão | Gradiente azul |
| `static/icon-dark.svg` | Ícone em dark mode | Gradiente navy |
| `static/icon-black.svg` | Ícone monocromático | Preto |
| `static/icon-white.svg` | Ícone monocromático | Branco |
| `static/logo.svg` | Logo horizontal 720×160 | Light |
| `static/logo-dark.svg` | Logo horizontal dark | Dark |
| `static/favicon.svg` | Favicon SVG 32×32 | Gradiente azul |

### Alternância light/dark em HTML

```html
<img src="/static/logo.svg" class="sidebar-brand-img sidebar-brand-light" alt="Doctoralia Scrapper">
<img src="/static/logo-dark.svg" class="sidebar-brand-img sidebar-brand-dark" alt="Doctoralia Scrapper">
```

```css
.sidebar-brand-dark { display: none; }
[data-theme="dark"] .sidebar-brand-light { display: none; }
[data-theme="dark"] .sidebar-brand-dark  { display: block; }
```

### Clearspace

Mínimo de `16px` em todos os lados. Nunca distorcer proporções. Não usar sobre fundos com contraste insuficiente.

### Usos incorretos

- Não recolorizar os elementos do ícone individualmente
- Não usar `icon-white.svg` em fundo branco
- Não reduzir abaixo de `24px` de altura

---

## 8. Component Patterns

### Cards

```css
.card {
  background: var(--surface-raised);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: var(--shadow-sm);
}
```

### Botões

```css
/* Primário */
.btn-primary {
  background: var(--apple-blue);
  color: var(--bg-primary);
  border-radius: var(--radius-md);
  padding: 10px 18px;
  font-weight: 600;
}

/* Secundário */
.btn-secondary {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

/* Destrutivo */
.btn-danger {
  background: var(--apple-red);
  color: white;
}
```

### Badges de status

| Variante | Background | Text |
|----------|-----------|------|
| Success | `color-mix(in srgb, var(--apple-green) 16%, var(--bg-primary))` | `var(--apple-green)` |
| Warning | `color-mix(in srgb, var(--apple-orange) 16%, var(--bg-primary))` | `var(--apple-orange)` |
| Error | `color-mix(in srgb, var(--apple-red) 16%, var(--bg-primary))` | `var(--apple-red)` |
| Neutral | `var(--bg-tertiary)` | `var(--text-secondary)` |

### Alertas

```html
<div class="alert alert-success">
  <i class="fas fa-check-circle"></i>
  <div>Mensagem de sucesso</div>
</div>
```

Variantes: `alert-success`, `alert-error`, `alert-warning`, `alert-info`.

### Modais

Estrutura: `.modal-overlay` > `.modal-container` > `.modal-header` + `.modal-body` + `.modal-footer`.

Backdrop: `var(--overlay-backdrop)`. Fechar via click no overlay ou `Escape`.

---

## 9. Transitions

| Token | Value | Uso |
|-------|-------|-----|
| `--transition-fast` | `150ms cubic-bezier(0.16,1,0.3,1)` | Hover, badges |
| `--transition-base` | `220ms cubic-bezier(0.16,1,0.3,1)` | Abertura de elementos |
| `--transition-slow` | `320ms cubic-bezier(0.16,1,0.3,1)` | Sidebar, modais |

`cubic-bezier(0.16, 1, 0.3, 1)` = ease-out pronunciado — rápido no início, suave no fim. Sensação responsiva.

---

## 10. Accessibility

### Contraste

Todos os pares text/background respeitam WCAG AA (≥ 4.5:1 para texto normal, ≥ 3:1 para grande).

- `--text-primary` sobre `--bg-primary` light: `#111B17` / `#FEFFFD` → 19.5:1
- `--text-primary` sobre `--bg-primary` dark: `#F7FBF9` / `#101815` → 18.1:1
- `--apple-blue` light sobre `--surface-raised`: `#146C94` / `#FFFFFF` → 5.2:1 ✓
- `--apple-green` light sobre `--surface-raised`: `#168C61` / `#FFFFFF` → 4.6:1 ✓

### Focus rings

Todos os elementos interativos têm `:focus-visible` com `outline: 3px solid var(--focus-ring)`. Nunca remover sem substituição.

### Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### ARIA

- Ícones decorativos: `aria-hidden="true"`
- Botões sem texto visível: `aria-label` obrigatório
- Regiões de navegação: `aria-label` na `<nav>`
- Skip link: `.skip-link` no topo do body

---

## 11. Favicon & PWA

```html
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
<link rel="icon" type="image/x-icon" href="/static/favicon.ico">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.svg">
```

SVG favicon suporta `prefers-color-scheme` nativo via `<style>` interno quando necessário.
ICO fallback para browsers legados. Apple touch icon para iOS bookmarks.
