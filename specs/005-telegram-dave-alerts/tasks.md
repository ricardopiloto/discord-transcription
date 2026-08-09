---
description: "Task list for Telegram DAVE mid-session alerts"
---

# Tasks: Notificação Telegram direta para alertas DAVE Recovery

**Input**: Design documents from `/specs/005-telegram-dave-alerts/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unitários indicados no plan/quickstart (sem TDD obrigatório). Discord/Telegram real = [quickstart.md](./quickstart.md).

**Organization**: Por user story (US1–US3). Código em `app/cronista/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência incompleta)
- **[Story]**: US1–US3 conforme spec.md
- Caminhos relativos ao repo root

## Path Conventions

```text
app/cronista/                     # implementação
app/tests/unit/                   # unitários
specs/005-telegram-dave-alerts/   # design
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirmar layout Cronista 004 e preparar docs de env — sem recriar o bot.

- [x] T001 Verify Cronista DAVE recovery path exists: `app/cronista/{config,session_manager,webhook}.py` and mid-session call sites in `app/cronista/session_manager.py`
- [x] T002 [P] Add Telegram env placeholders (`CRONISTA_TELEGRAM_BOT_TOKEN`, `CRONISTA_TELEGRAM_CHAT_ID`, `CRONISTA_TELEGRAM_API_BASE`) and remove/comment `CRONISTA_ALERT_WEBHOOK_URL` in root `.env.example`
- [x] T003 [P] Note feature version bump intent under Unreleased in `CHANGELOG.md` (validation-only line OK until implement)

**Checkpoint**: Env docs apontam para Telegram; código 004 localizado.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config Telegram + módulo de formatação/envio + remoção do webhook mid-session — **bloqueia todas as stories**.

**⚠️ CRITICAL**: Nenhuma story começa até esta fase estar completa.

**Constitution**: n8n session-end e `recording_gaps.jsonl` intactos; schemas em `specs/005-telegram-dave-alerts/contracts/`.

- [x] T004 Replace `alert_webhook_url` with `telegram_bot_token`, `telegram_chat_id`, `telegram_api_base` (default `https://api.telegram.org`) in `app/cronista/config.py`
- [x] T005 [P] Create `app/cronista/telegram_alert.py` with `format_gap_duration()`, message builders for the three Message Templates (spec), and redacted URL helper (never log token)
- [x] T006 Implement `notify_dave_alert(config, …)` / `send_telegram_message` with aiohttp POST to `{api_base}/bot{token}/sendMessage` and body per `specs/005-telegram-dave-alerts/contracts/telegram-sendmessage.schema.json` in `app/cronista/telegram_alert.py` (omit + log if token/chat_id missing; 3 retries with short backoff)
- [x] T007 Remove mid-session webhook path (`notify_mid_session_alert`, `build_mid_session_alert`, `alert_webhook_url` usage) from `app/cronista/webhook.py`; keep n8n session-end only
- [x] T008 Update imports/call sites that still reference mid-session webhook helpers to use `telegram_alert` in `app/cronista/session_manager.py` (wire behavior in US1; compile-safe stub OK)

**Checkpoint**: Config carrega vars Telegram; módulo envia/omitte; webhook.py só n8n.

---

## Phase 3: User Story 1 - Receber alertas DAVE no Telegram em tempo real (Priority: P1) 🎯 MVP

**Goal**: Nos eventos detected / recovered / failed, o chat Telegram recebe as mensagens com os templates oficiais (placeholders preenchidos).

**Independent Test**: Com Token+Chat ID mockados (ou unit com aiohttp mock), disparar os três builders/envios e assertar textos; em runtime, recovery dispara mensagens antes do fim da sessão.

**Covers**: FR-001, FR-002, FR-011, SC-001

### Implementation for User Story 1

- [x] T009 [US1] On DAVE recovery start in `app/cronista/session_manager.py`, fire detected alert via `asyncio.create_task` (no await before reconnect loop); add done-callback logging for task exceptions
- [x] T010 [US1] After successful recovery in `app/cronista/session_manager.py`, await Telegram recovered message with `{duração_do_gap}` via `format_gap_duration`
- [x] T011 [US1] After exhausted attempts in `app/cronista/session_manager.py`, await Telegram failed message with `{N}` and `{horário}` ISO-8601 UTC
- [x] T012 [P] [US1] Unit tests for Message Templates + `format_gap_duration` in `app/tests/unit/test_telegram_alert.py`

**Checkpoint**: Três eventos produzem textos corretos; detecção não bloqueia reconnect.

---

## Phase 4: User Story 2 - Configurar API, Token e Chat ID no deploy (Priority: P1)

**Goal**: Operador configura só por env; default de API base; ausência de credenciais omite envio sem quebrar recovery.

**Independent Test**: Config com/without vars; omit path logado; docs README/.env.example listam as três vars.

**Covers**: FR-003, FR-004, FR-005, FR-010, SC-002, SC-004

### Implementation for User Story 2

- [x] T013 [US2] Document Telegram vars (and removal of `CRONISTA_ALERT_WEBHOOK_URL`) in `README.md` env table
- [x] T014 [P] [US2] Unit test: missing token or chat_id skips HTTP and returns omitted/ok in `app/tests/unit/test_telegram_alert.py`
- [x] T015 [P] [US2] Unit test: empty `telegram_api_base` uses `https://api.telegram.org` in `app/tests/unit/test_telegram_alert.py` or `app/tests/unit/test_config.py` if config helpers tested there
- [x] T016 [US2] Migrate or delete obsolete `app/tests/unit/test_mid_session_webhook.py` so suite does not require `CRONISTA_ALERT_WEBHOOK_URL` / mid-session webhook helpers

**Checkpoint**: Deploy documentado; suite verde sem webhook mid-session.

---

## Phase 5: User Story 3 - Falha de entrega não compromete a gravação (Priority: P2)

**Goal**: Erro/timeout Telegram após retries só gera log; recovery/gaps seguem; Token nunca aparece em logs.

**Independent Test**: Mock HTTP 500/timeout → 3 attempts → recovery path still callable; caplog sem token.

**Covers**: FR-006, FR-007, SC-003, SC-005

### Implementation for User Story 3

- [x] T017 [US3] Ensure send failures after 3 attempts log without token and return false without raising in `app/cronista/telegram_alert.py`
- [x] T018 [P] [US3] Unit test retries (3 attempts) + failure does not raise in `app/tests/unit/test_telegram_alert.py`
- [x] T019 [P] [US3] Unit test that log records for failed send do not contain the bot token string in `app/tests/unit/test_telegram_alert.py`

**Checkpoint**: Entrega falha de forma segura e observável.

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: Versão monorepo, limpeza, validação.

- [x] T020 [P] Bump monorepo package versions consistently (`app/pyproject.toml`, `whisper-service/pyproject.toml`) and add dated `CHANGELOG.md` section for Telegram DAVE alerts (follow single-repo semver after current release)
- [x] T021 [P] Grep/remove leftover `CRONISTA_ALERT_WEBHOOK_URL` / `alert_webhook_url` / `notify_mid_session_alert` references from `app/`, `README.md`, `.env.example`
- [x] T022 Run `app` unit suite (`pytest app/tests/unit -q`) and fix regressions
- [x] T023 [P] Align `specs/005-telegram-dave-alerts/quickstart.md` checklist with final env var names if anything drifted

**Checkpoint**: Pronto para `/speckit-implement` close-out e quickstart manual.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → Phase 2 → US1 (Phase 3) → US2 (Phase 4) / US3 (Phase 5) → Polish
- US2 e US3 podem avançar em paralelo após T012 (MVP de envio) se T006 já existir; na prática US2 docs podem começar após T004

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 | MVP — envio real nos 3 eventos + paralelo |
| US2 | Phase 2 (+ US1 preferred) | Config/docs/omit; testes de config |
| US3 | Phase 2 (+ T006) | Retries/segurança de log |

### Parallel Opportunities

- T002 ∥ T003
- T005 ∥ T004 (depois integrar T006)
- T012 ∥ docs T013 após builders estáveis
- T014 ∥ T015 ∥ T018 ∥ T019 (arquivos de teste)
- T020 ∥ T021 ∥ T023

### Parallel Example: User Story 1

```bash
# Após Phase 2:
# 1) T009–T011 session_manager wiring
# 2) T012 unit tests templates (paralelo após T005)
```

---

## Implementation Strategy

### MVP (User Story 1)

1. Completar Phase 1–2  
2. Wire três alertas + `create_task` na detecção (T009–T011)  
3. Unit templates (T012)  
4. Validar com mock; opcionalmente quickstart parcial com bot real  

### Incremental Delivery

1. US1 → alertas chegam com texto certo  
2. US2 → deploy/config/omit documentados + suite limpa  
3. US3 → retries + sem vazamento de token  
4. Polish → versão + CHANGELOG + pytest verde  

### Suggested MVP Scope

**US1 apenas** (com Phase 1–2): operador já recebe Telegram nos eventos DAVE.

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 23 |
| US1 | 4 (T009–T012) |
| US2 | 4 (T013–T016) |
| US3 | 3 (T017–T019) |
| Setup + Foundational + Polish | 5 + 5 + 4 |
| Parallelizable marked [P] | 12 |
| Format validation | All tasks use `- [ ] Tnnn …` with paths |

**Independent tests**:
- **US1**: templates + create_task wiring / mock send  
- **US2**: omit sem credenciais + README/.env  
- **US3**: 3 retries + token redaction in logs  

**Next**: `/speckit-implement`
