# Research: Notificação Telegram direta (DAVE alerts)

**Feature**: `005-telegram-dave-alerts` | **Date**: 2026-08-08

## R1 — Canal de entrega: Telegram Bot API vs webhook mid-session

**Decision**: Enviar `sendMessage` diretamente à Bot API; **remover** `CRONISTA_ALERT_WEBHOOK_URL` e o path mid-session em `webhook.py`.

**Rationale**: Spec/clarify Q1 — Telegram substitui o monitor externo; YAGNI (Constitution III). Payload JSON para bridge intermediário deixa de ser necessário.

**Alternatives considered**:
- Dual-send (Telegram + webhook) — rejeitado (clarify A)
- Telegram primário + webhook fallback — rejeitado (clarify A)
- SDK `python-telegram-bot` — rejeitado; um POST com aiohttp basta e evita dependência nova

---

## R2 — Endpoint e variáveis de ambiente

**Decision**:
- URL: `{CRONISTA_TELEGRAM_API_BASE}/bot{token}/sendMessage` (POST `application/json` ou form)
- Default `CRONISTA_TELEGRAM_API_BASE` = `https://api.telegram.org` (sem barra final; normalizar no código)
- Credenciais: `CRONISTA_TELEGRAM_BOT_TOKEN`, `CRONISTA_TELEGRAM_CHAT_ID` (opcionais; ambos necessários para enviar)
- Body mínimo: `{ "chat_id": "<id>", "text": "<mensagem>" }` — sem `parse_mode` (evita quebra com `_`/`*` no nome do canal)

**Rationale**: Prefixo `CRONISTA_` alinha com demais knobs do bot; override de API base cobre Bot API local; `parse_mode` off reduz risco de erro 400 em textos com caracteres especiais.

**Alternatives considered**:
- `TELEGRAM_BOT_TOKEN` sem prefixo — ok, mas inconsistente com `CRONISTA_DAVE_*`
- `parse_mode=HTML/Markdown` — rejeitado para v1 (templates já têm emoji; canal pode ter underscores)

---

## R3 — Retries e timeout

**Decision**: Reusar padrão do webhook n8n — **3 tentativas**, backoff exponencial curto (`1s`, `2s`, …), timeout HTTP total por tentativa ~10–15s (menor que 30s do n8n se desejado, para não prolongar tasks em background). Sucesso = HTTP 2xx da Bot API com `ok: true` no JSON (se corpo parseável).

**Rationale**: Clarify Q3; alinhado a `MAX_ATTEMPTS = 3` / `BASE_DELAY_S` em `webhook.py`.

**Alternatives considered**:
- 1 tentativa — rejeitado (clarify)
- Retry infinito com deadline — mais complexo, pouco ganho

---

## R4 — Paralelismo do alerta de detecção

**Decision**: Em `_run_dave_recovery`, disparar o envio do alerta `detected` com `asyncio.create_task(...)` (ou `asyncio.ensure_future`) **antes** do loop de reconnect, **sem** `await` nesse envio. Alertas `recovered` / `failed` podem `await` (recuperação já terminou) ou também task — preferir `await` para não perder a task no shutdown imediato pós-falha.

**Rationale**: Clarify Q4 — retries Telegram não alongam o gap. Task deve ter done-callback que loga exceções não tratadas.

**Alternatives considered**:
- Await detect antes do reconnect — rejeitado (clarify)
- Thread separada — desnecessário com aiohttp async

---

## R5 — Formatação de placeholders

**Decision**:
- `{channel}` → `channel_name` já disponível no recovery (fallback: `channel_id` se nome vazio)
- `{duração_do_gap}` → helper `format_gap_duration(seconds: float) -> str`:
  - `total_s = int(round(seconds))` (ou floor)
  - se `total_s < 60` → `f"{total_s}s"`
  - senão → `f"{total_s // 60}m {total_s % 60}s"`
- `{horário}` → `gap_started_at` já em ISO-8601 UTC (não reformatar além de garantir sufixo `Z` se necessário)
- `{N}` → `reconnect_attempts` / max attempts no failed

**Rationale**: Clarify Q2; corrige o formato atual `f"{duration:.0f}s"` em `build_mid_session_alert` que não atende a spec 005.

**Alternatives considered**:
- Sempre `Xm Ys` mesmo abaixo de 1 min (`0m 45s`) — rejeitado (spec permite só `Ys`)
- Horário local do servidor — rejeitado (clarify B / ISO UTC)

---

## R6 — Segurança do Token em logs

**Decision**: Nunca interpolar o token em mensagens de log; se a URL for logada, redigir como `…/bot***/sendMessage`. Em erros aiohttp, logar status/descrição sem query/body com token.

**Rationale**: FR-007 / SC-005.

**Alternatives considered**: Logar URL completa em DEBUG — rejeitado.

---

## R7 — Compatibilidade com contrato mid-session 004

**Decision**: Deprecar o schema HTTP JSON mid-session como canal de entrega. Internamente pode permanecer um builder de texto/eventos; o contrato externo vira Telegram `sendMessage` (ver `contracts/`). Documentar em 005 que `mid-session-alert.schema.json` de 004 deixa de ser o transporte em produção.

**Rationale**: Remoção do webhook é breaking só para monitores que consumiam a URL genérica — clarify assume que não há requisito de compatibilidade.

**Alternatives considered**: Manter POST JSON idêntico + Telegram — dual-send rejeitado.
