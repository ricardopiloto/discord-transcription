# Implementation Plan: Notificação Telegram direta para alertas DAVE Recovery

**Branch**: `005-telegram-dave-alerts` | **Date**: 2026-08-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-telegram-dave-alerts/spec.md`

## Summary

Substituir o webhook mid-session (`CRONISTA_ALERT_WEBHOOK_URL`) por envio **direto** à Telegram Bot API (`sendMessage`) com Token, Chat ID e URL base configuráveis. Reusar os eventos DAVE de 004; ajustar textos aos Message Templates (duração `Xm Ys`, horário ISO-8601 UTC); até 3 retries; alerta de **detecção em paralelo** à reconexão (não atrasa recovery). Webhook n8n de fim de sessão permanece intacto.

## Technical Context

**Language/Version**: Python 3.11+ (Cronista / py-cord)

**Primary Dependencies**: aiohttp (HTTP à Bot API); py-cord inalterado; sem SDK Telegram dedicado

**Storage**: N/A (sem novos artefatos de sessão; gaps/webhook n8n de 004 intactos)

**Testing**: pytest unitários (formatação de mensagem, omitir sem credenciais, retries, token não vazado em logs); quickstart manual com bot/chat reais

**Target Platform**: Linux host, systemd `/opt/apps/cronista/`

**Project Type**: Extensão incremental do bot Cronista (`app/cronista/`)

**Performance Goals**: Alerta de detecção não atrasa início do reconnect; retries Telegram ≤ ~poucos segundos no total; event loop de voz não bloqueado por I/O síncrono

**Constraints**:
- Telegram-only para mid-session (sem dual-send / sem fallback webhook)
- Token nunca em logs
- Token/Chat ID ausentes → omitir envio + log; recovery/gaps seguem
- Message Templates literais (emoji + redação)
- Contratos n8n / `recording_gaps.jsonl` / layout `.ogg` preservados

**Scale/Scope**: 1 sessão ativa; poucos alertas por sessão; 1 Chat ID

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Principle | Gate Question | Status | Notes |
|-----------|---------------|--------|-------|
| I. Contract Stability | Contratos downstream preservados? | ✅ PASS | n8n session-end, gaps, speaking_log, paths intactos; remove apenas canal interno mid-session (webhook genérico → Telegram); sem breaking para n8n |
| II. Evidence Before Commitment | Riscos empíricos com spike? | ✅ PASS / N/A | Risco = credenciais/rede Telegram; validado por quickstart + unit tests com mock HTTP — sem spike DAVE novo |
| III. Simplicity & YAGNI | Single-process, file-based? | ✅ PASS | aiohttp `sendMessage`; sem monitor externo, sem DB, sem lib Telegram extra |
| IV. Incremental Durability | Gravação incremental? | ✅ N/A | Só canal de alerta; não altera sink/utterances |
| V. Operational Isolation | Isolamento + convivência? | ✅ PASS | Mesmo venv/systemd; secrets em env; bot Telegram separado do Discord token |

**Post-design re-check**: Design não adiciona dual-send nem persistência. Complexity Tracking vazio. Gates mantidos.

## Project Structure

### Documentation (this feature)

```text
specs/005-telegram-dave-alerts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md
│   └── telegram-sendmessage.schema.json
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
app/cronista/
├── config.py                 # - alert_webhook_url; + telegram_bot_token, telegram_chat_id, telegram_api_base
├── telegram_alert.py         # NOVO: format templates, sendMessage + retries, redact token
├── webhook.py                # remover notify_mid_session_alert / alert webhook path (n8n end permanece)
├── session_manager.py        # disparar alerta detecção em paralelo; recovered/failed via telegram_alert
└── …

app/tests/unit/
├── test_telegram_alert.py    # NOVO
└── test_mid_session_webhook.py  # remover ou migrar asserções para telegram

.env.example / README.md      # vars Telegram; deprecar CRONISTA_ALERT_WEBHOOK_URL
```

**Structure Decision**: Módulo dedicado `telegram_alert.py` para envio/formatação; `webhook.py` volta a cuidar só do n8n de fim; `SessionManager` troca a chamada mid-session e usa `asyncio.create_task` (ou equivalente) no alerta de detecção.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 → Research

Ver [research.md](./research.md) — Bot API `sendMessage`, env vars, paralelismo, formatação duração, remoção do webhook mid-session.

## Phase 1 → Design

| Artifact | Path | Status |
|----------|------|--------|
| Data model | [data-model.md](./data-model.md) | ✅ |
| Contracts | [contracts/](./contracts/) | ✅ |
| Quickstart | [quickstart.md](./quickstart.md) | ✅ |

## Next Steps

1. `/speckit-tasks`
2. `/speckit-implement`
3. Validar [quickstart.md](./quickstart.md) com bot/chat reais
4. Remover `CRONISTA_ALERT_WEBHOOK_URL` do deploy
