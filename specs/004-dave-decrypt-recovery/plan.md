# Implementation Plan: Recuperação automática de falhas de decriptação DAVE

**Branch**: `004-dave-decrypt-recovery` | **Date**: 2026-08-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-dave-decrypt-recovery/spec.md` (+ `docs/demanda-whisper-service-dave-fix.md`)

## Summary

Estender o **Cronista** para detectar sequências de falhas de decriptação DAVE em tempo real (hoje silenciosas na lib), disparar **reconexão completa** do canal de voz (disconnect + connect + warmup + `start_recording`), validar sucesso no primeiro pacote PCM OK, registrar gaps em `recording_gaps.jsonl`, alertar via **webhook mid-session** (Telegram no monitor externo), aplicar cooldown pós-recuperação, e expor contagem de gaps no aviso/webhook de encerramento. Sessão **não** encerra automaticamente ao esgotar tentativas — sai do voz e aguarda o operador.

## Technical Context

**Language/Version**: Python 3.11+ (Cronista / py-cord)

**Primary Dependencies**: py-cord (voice + DAVE), aiohttp (webhooks), ffmpeg (inalterado)

**Storage**: Filesystem — append `recording_gaps.jsonl` na pasta da sessão; `speaking_log` / `.ogg` preservados

**Testing**: pytest unitários (contador, gap schema, cooldown, webhook mid-session); validação manual Discord via [quickstart.md](./quickstart.md)

**Target Platform**: Linux host, systemd `/opt/apps/cronista/`

**Project Type**: Extensão incremental do bot Cronista (`app/cronista/`)

**Performance Goals**: Detecção dentro da janela (default 10s após limiar); alertas mid-session sem bloquear o event loop de voz

**Constraints**:
- Não recuperar áudio do gap
- Não depender do reconnect interno superficial da lib
- Sucesso só após 1º pacote decodificado OK (timeout 30s)
- Cooldown 60s após recuperação OK
- Webhook mid-session opcional (sem URL → log only)
- Contratos Cronista aditivos (`recording_gaps.jsonl`; campos opcionais no webhook de fim)

**Scale/Scope**: 1 sessão ativa por processo; poucos gaps por sessão típica

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Principle | Gate Question | Status | Notes |
|-----------|---------------|--------|-------|
| I. Contract Stability | Contratos downstream preservados? | ✅ PASS | `speaking_log` / layout `.ogg` intactos; `recording_gaps.jsonl` **aditivo**; webhook de fim ganha campo opcional `gap_count` / paths (não breaking) |
| II. Evidence Before Commitment | Riscos empíricos com spike? | ✅ PASS | Quickstart com disconnect forçado + validação de gap/webhook; CryptoError na lib exige gancho — ver research R1 |
| III. Simplicity & YAGNI | Single-process, file-based? | ✅ PASS | Sem DB/fila; orchestrator + JSONL + webhook |
| IV. Incremental Durability | Gravação incremental? | ✅ PASS | Gaps append-only; utterances pré-gap intactas; flush antes do disconnect |
| V. Operational Isolation | Isolamento + convivência? | ✅ PASS | Mesmo venv/systemd Cronista; alert webhook separado do n8n de fim |

**Post-design re-check**: Design não adiciona Telegram Bot API nem persistência extra. Complexity Tracking vazio. Gates mantidos.

## Project Structure

### Documentation (this feature)

```text
specs/004-dave-decrypt-recovery/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── recording-gaps.schema.json
│   ├── mid-session-alert.schema.json
│   └── api.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
app/cronista/
├── config.py                 # + env DAVE/reconnect/cooldown/alert URL
├── session_manager.py        # + reconnect_voice / recovery hooks
├── commands.py               # status/encerrar: gap count
├── end_session.py            # passar gap_count ao webhook
├── webhook.py                # + notify_mid_session_alert; end payload +gap fields
├── recording/
│   ├── sink.py               # sinal de sucesso (PCM OK) → recovery counter reset
│   ├── speaking_log.py       # inalterado
│   ├── gaps_log.py           # NOVO: append recording_gaps.jsonl
│   └── dave_recovery.py      # NOVO: contador, janela, cooldown, orchestrator
└── tests/unit/
    ├── test_dave_recovery.py
    ├── test_gaps_log.py
    └── test_mid_session_webhook.py
```

**Structure Decision**: Lógica de recuperação em módulo dedicado `recording/dave_recovery.py`, orquestrada pelo `SessionManager`; gaps espelham o padrão `SpeakingLog`; alertas mid-session em `webhook.py` com URL própria.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 → Research

Ver [research.md](./research.md) — detecção de CryptoError fora do sink, reconnect completo, webhook mid-session, critério de sucesso.

## Phase 1 → Design

| Artifact | Path | Status |
|----------|------|--------|
| Data model | [data-model.md](./data-model.md) | ✅ |
| Contracts | [contracts/](./contracts/) | ✅ |
| Quickstart | [quickstart.md](./quickstart.md) | ✅ |

## Next Steps

1. `/speckit-tasks`
2. `/speckit-implement`
3. Validar quickstart em canal Discord real
4. Configurar `CRONISTA_ALERT_WEBHOOK_URL` no monitor → Telegram
