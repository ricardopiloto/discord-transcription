---
description: "Task list for Cronista DAVE decrypt recovery"
---

# Tasks: Recuperação automática de falhas de decriptação DAVE

**Input**: Design documents from `/specs/004-dave-decrypt-recovery/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unitários no polish e onde indicado (plan.md); cenários Discord = [quickstart.md](./quickstart.md). Sem TDD obrigatório.

**Organization**: Por user story (US1–US5). Código em `app/cronista/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência incompleta)
- **[Story]**: US1–US5 conforme spec.md
- Caminhos relativos ao repo root

## Path Conventions

```text
app/cronista/                  # implementação
app/cronista/recording/        # sink, gaps, recovery
app/tests/unit/                # unitários
specs/004-dave-decrypt-recovery/  # design
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirmar layout Cronista e docs de env — sem recriar o bot.

- [x] T001 Verify Cronista package layout exists: `app/cronista/{config,session_manager,webhook,commands,end_session}.py` and `app/cronista/recording/{sink,speaking_log,storage}.py`
- [x] T002 [P] Document new env vars (`CRONISTA_DAVE_*`, reconnect, cooldown, validate timeout, `CRONISTA_ALERT_WEBHOOK_URL`) in `app/.env.example` (create if missing) or root deploy env docs referenced by README
- [x] T003 [P] Note feature version bump intent for Cronista in `CHANGELOG.md` under Unreleased (validation-only line OK until implement)

**Checkpoint**: Repo pronto para módulos de recovery.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config, contador/janela/cooldown, gaps writer, gancho de falha — **bloqueia todas as stories**.

**⚠️ CRITICAL**: Nenhuma story começa até esta fase estar completa.

**Constitution**: Artefato `recording_gaps.jsonl` aditivo; schemas em `specs/004-dave-decrypt-recovery/contracts/` já existem.

- [x] T004 Extend `Config` / `load_config()` with DAVE threshold, window, reconnect max/backoff, cooldown, validate timeout, `alert_webhook_url` in `app/cronista/config.py`
- [x] T005 [P] Implement `GapsLog` append-only writer for `recording_gaps.jsonl` in `app/cronista/recording/gaps_log.py` per `specs/004-dave-decrypt-recovery/contracts/recording-gaps.schema.json`
- [x] T006 Implement `DaveRecovery` state machine (failure window, threshold, cooldown, in-progress flag, attempt counter, gap open/close helpers) in `app/cronista/recording/dave_recovery.py`
- [x] T007 Wire decode-success callback from non-silent PCM path in `app/cronista/recording/sink.py` to `DaveRecovery.on_decode_success()`
- [x] T008 Install decrypt-failure hook for py-cord DAVE path (patch/wrapper per research R1) that calls `DaveRecovery.on_decrypt_failure()` — document exact hook site in module docstring in `app/cronista/recording/dave_recovery.py` or small `app/cronista/recording/dave_hooks.py`
- [x] T009 Attach/reset `DaveRecovery` (+ `GapsLog`) lifecycle on session start/end in `app/cronista/session_manager.py`

**Checkpoint**: Falhas e sucessos alimentam o contador; gaps writer pronto; config carrega defaults.

---

## Phase 3: User Story 1 - Detectar falha em tempo real (Priority: P1) 🎯 MVP parcial

**Goal**: Atingir limiar dentro da janela dispara o sinal de recuperação (callback/evento), sem depender de análise de log no dia seguinte.

**Independent Test**: Injetar N falhas consecutivas no hook; `DaveRecovery` entra em estado de disparo dentro da janela; falha isolada fora da janela não dispara; sucesso zera contador.

**Covers**: FR-001, FR-002, FR-003, SC-001 (detecção)

### Implementation for User Story 1

- [x] T010 [US1] Expose `should_start_recovery()` / event callback when threshold+window met in `app/cronista/recording/dave_recovery.py`
- [x] T011 [US1] Ensure sliding window drops stale failures before counting in `app/cronista/recording/dave_recovery.py`
- [x] T012 [P] [US1] Unit tests for threshold/window/reset in `app/tests/unit/test_dave_recovery.py`

**Checkpoint**: Detecção testável em unitário sem Discord.

---

## Phase 4: User Story 2 - Reconexão completa (Priority: P1) 🎯 MVP

**Goal**: Disconnect+connect+warmup+start_recording; sucesso só no 1º PCM OK; backoff; cooldown; ao esgotar sair do voz sem encerrar sessão.

**Independent Test**: Após disparo, bot reconecta; validação por PCM OK; esgotamento deixa sessão aberta fora do voz.

**Covers**: FR-004, FR-005, FR-016, FR-006, FR-011, FR-015, SC-002, SC-005, SC-007

### Implementation for User Story 2

- [x] T013 [US2] Implement `SessionManager.reconnect_voice_full()` (flush sink, stop_recording, disconnect force, connect, self_mute, DAVE warmup, start_recording) in `app/cronista/session_manager.py`
- [x] T014 [US2] Orchestrate recovery loop (attempts, backoff `base * attempt`, validate timeout, cooldown on success, leave voice on exhaust) in `app/cronista/recording/dave_recovery.py` + `session_manager.py`
- [x] T015 [US2] Keep Opus/`corrupted stream` soft-restart separate from DAVE full reconnect in `app/cronista/session_manager.py`
- [x] T016 [US2] On exhaust: disconnect voice, keep `SessionData` active, set compromised/idle-recording state visible to status in `app/cronista/session_manager.py`
- [x] T017 [P] [US2] Unit tests for attempt/backoff/cooldown/validate-timeout state transitions in `app/tests/unit/test_dave_recovery.py`

**Checkpoint**: MVP operacional — detect + full reconnect (+ fail-safe exhaust).

---

## Phase 5: User Story 3 - Registrar gaps (Priority: P1)

**Goal**: Cada incidente fecha com linha em `recording_gaps.jsonl` (UTC + ms relativos + reason + attempts + success).

**Independent Test**: Após recover ou exhaust, arquivo existe com campos do schema.

**Covers**: FR-007, SC-003

### Implementation for User Story 3

- [x] T018 [US3] On recovery start, capture `started_at` / `start_ms`; on success or exhaust, append gap line via `GapsLog` in `app/cronista/recording/dave_recovery.py`
- [x] T019 [US3] Compute relative ms from `session.started_at` consistently with speaking_log clock in `app/cronista/recording/gaps_log.py` or recovery helper
- [x] T020 [P] [US3] Unit tests for gap line fields / append in `app/tests/unit/test_gaps_log.py`

**Checkpoint**: Artefato auditável por sessão.

---

## Phase 6: User Story 4 - Webhook mid-session (Priority: P1)

**Goal**: Alertas `detected` / `recovered` / `failed` via `CRONISTA_ALERT_WEBHOOK_URL` sem bloquear recovery se URL ausente/falhar.

**Independent Test**: Receptor HTTP recebe payloads; sem URL → só log.

**Covers**: FR-008, FR-009, FR-010, FR-014, SC-004, SC-005 (alerta)

### Implementation for User Story 4

- [x] T021 [US4] Implement `notify_mid_session_alert()` with retries in `app/cronista/webhook.py` per `specs/004-dave-decrypt-recovery/contracts/mid-session-alert.schema.json`
- [x] T022 [US4] Build human-readable `message` strings (detect / recover / fail) and fire alerts from recovery orchestrator in `app/cronista/recording/dave_recovery.py` or `session_manager.py`
- [x] T023 [US4] Skip HTTP when `alert_webhook_url` unset; log omit; continue recovery in `app/cronista/webhook.py`
- [x] T024 [P] [US4] Unit tests for mid-session webhook success/retry/skip in `app/tests/unit/test_mid_session_webhook.py`

**Checkpoint**: Operador recebe alerta em tempo real via monitor externo.

---

## Phase 7: User Story 5 - Gaps no encerramento (Priority: P2)

**Goal**: Aviso final Discord + webhook n8n incluem `gap_count` (e path se >0).

**Independent Test**: Encerrar sessão com ≥1 gap → reply e payload mostram contagem; sem gaps → comportamento atual.

**Covers**: FR-012, SC-006

### Implementation for User Story 5

- [x] T025 [US5] Extend `build_payload()` with additive `gap_count` and optional `recording_gaps_path` in `app/cronista/webhook.py`
- [x] T026 [US5] Include gap count in `!cronista encerrar` Discord reply when N>0 in `app/cronista/commands.py` / `end_session.py`
- [x] T027 [P] [US5] Surface compromised/recovery/gap summary in `!cronista status` when relevant in `app/cronista/commands.py`
- [x] T028 [P] [US5] Update unit tests for end webhook payload fields in `app/tests/unit/test_webhook.py`

**Checkpoint**: Observabilidade fecha o ciclo mesmo se mid-session foi ignorado.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Docs, regressão, validação quickstart.

- [x] T029 [P] Update `README.md` with DAVE recovery env vars and `recording_gaps.jsonl` artifact
- [x] T030 [P] Move Unreleased note to a dated Cronista bump section in `CHANGELOG.md` when version bumps (or keep Unreleased until release)
- [x] T031 [P] Align `specs/002-python-pycord-migration/contracts/n8n-webhook.schema.json` or document additive fields in `specs/004-dave-decrypt-recovery/contracts/api.md` (already drafted — verify consistency)
- [x] T032 Run `pytest` under `app/tests/unit/` for recovery/gaps/webhook/sink regressions
- [x] T033 Execute applicable scenarios from `specs/004-dave-decrypt-recovery/quickstart.md` and tick checklist
- [x] T034 Verify Opus soft-restart path still works (no accidental coupling to DAVE full reconnect) in `app/cronista/session_manager.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: imediato
- **Foundational (Phase 2)**: após Setup — **bloqueia** US1–US5
- **US1 (Phase 3)**: após Foundational
- **US2 (Phase 4)**: após US1 (usa sinal de disparo)
- **US3 (Phase 5)**: após US2 (fecha gap no fim do ciclo) — pode esboçar writer na foundation
- **US4 (Phase 6)**: após US2 (mesmos pontos de lifecycle)
- **US5 (Phase 7)**: após US3 (precisa gap_count)
- **Polish (Phase 8)**: após stories desejadas

### User Story Dependencies

```text
Phase 2 Foundational
        │
        ▼
       US1 (detecção)
        │
        ▼
       US2 (reconnect completo)  ← MVP
      / | \
   US3  US4  (gaps + alerts)
      \
      US5 (encerramento)
```

### Parallel Opportunities

- Phase 1: T002 // T003
- Phase 2: T005 // T004; T007/T008 após T006
- Phase 8: T029–T031 em paralelo
- US4 tests (T024) // US3 tests (T020) após código correspondente

### Parallel Example: Foundational

```bash
Task: T004 config.py
Task: T005 gaps_log.py
# Depois:
Task: T006 dave_recovery.py
Task: T007 sink.py success hook
Task: T008 decrypt failure hook
Task: T009 session_manager lifecycle
```

---

## Implementation Strategy

### MVP First

1. Phase 1 + Phase 2  
2. US1 + US2 (T010–T017)  
3. **STOP**: validar Scenario 1/2 do quickstart  
4. US3 → US4 → US5 → Polish  

### Suggested MVP scope

**US1 + US2** (detecção + reconexão completa). Gaps e webhooks elevam observabilidade mas a mitigação do incidente 07/08 começa no reconnect.

### Incremental Delivery

1. Foundation  
2. Detect + reconnect → demo  
3. Gaps file  
4. Mid-session alerts  
5. End-session visibility  
6. Docs + quickstart  

---

## Notes

- CryptoError **não** chega ao sink — gancho R1 é obrigatório  
- Soft-restart Opus ≠ full reconnect DAVE  
- Sem Bot API Telegram no Cronista  
- `CRONISTA_ALERT_WEBHOOK_URL` ≠ `N8N_WEBHOOK_URL`  
- Canal silencioso no validate timeout conta como falha da tentativa  
- Commit por task ou grupo lógico  
