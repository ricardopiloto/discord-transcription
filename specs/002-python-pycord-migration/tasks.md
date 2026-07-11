---
description: "Task list for Migração do Cronista para Stack Python/Py-Cord"
---

# Tasks: Migração do Cronista para Stack Python/Py-Cord

**Input**: Design documents from `/specs/002-python-pycord-migration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Testes unitários para lógica pura (storage, webhook retry) conforme research R8. Captura de voz validada via spike (US1) e quickstart manual — não mockável em CI. Sem TDD obrigatório.

**Organization**: Tarefas agrupadas por user story. **US1 (spike) é gate obrigatória** — Phase 3+ só inicia após verdict PASS em `contracts/spike-acceptance.md` (Constitution Principle II).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências pendentes)
- **[Story]**: User story (US1–US5)
- Caminhos relativos ao repo root

## Path Conventions

Nova stack Python em `app/cronista/`; spike descartável em `spike/`; legado Node em `src/` (removido na US5).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar estrutura mínima para spike e app Python sem tocar no legado Node.

- [x] T001 Create directory skeleton per plan.md: `spike/`, `app/cronista/recording/`, `app/tests/unit/` with `__init__.py` files
- [x] T002 [P] Update `.gitignore` for Python artifacts (`.venv/`, `.venv-spike/`, `__pycache__/`, `*.pyc`, `spike_out/`, `.pytest_cache/`, `app/.env`)
- [x] T003 [P] Add `app/.python-version` with `3.11` and confirm `.env.example` documents all vars from `specs/002-python-pycord-migration/contracts/bot-commands.md`
- [x] T004 [P] Create `recordings/.gitkeep` if missing and add `spike_out/.gitkeep` for spike output isolation

**Checkpoint**: Repo pronto para spike e scaffolding Python.

---

## Phase 2: User Story 1 - Decidir stack com evidência real (Priority: P1) 🚦 GATE

**Goal**: Validar recepção de áudio sob DAVE com bot mínimo antes de investir no rewrite completo.

**Independent Test**: Rodar `spike/record_smoke.py` no canal real com 2+ participantes por ≥3 min; arquivos reproduzíveis com autoria correta (quickstart Phase A, SC-001).

**⚠️ CRITICAL**: Se verdict = FAIL, **parar** — não executar Phase 3+.

### Implementation for User Story 1

- [x] T005 [US1] Create `spike/record_smoke.py`: minimal py-cord bot that joins voice channel, calls `start_recording` with a basic custom sink, records for configurable duration
- [x] T006 [US1] Add CLI to `spike/record_smoke.py`: `--channel`, `--seconds` (default 180), `--output` (default `spike_out/`), `--token` (or read `DISCORD_TOKEN` env)
- [x] T007 [US1] Implement minimal sink in `spike/record_smoke.py` writing per-user audio to `{output}/{user_id}/` and counting packets received for SpikeResult
- [ ] T008 [US1] Execute spike on real Discord channel: try py-cord stable first; if FAIL, retry with PR #3202 branch or fork + `davey` per research R1
- [ ] T009 [US1] Fill SpikeResult JSON block in `specs/002-python-pycord-migration/contracts/spike-acceptance.md` with measured values and set `verdict` to PASS or FAIL
- [x] T010 [US1] If PASS: pin confirmed `pycord_source` in `app/requirements.txt`; if FAIL: document diagnosis in `contracts/spike-acceptance.md` and halt — do not proceed

**Checkpoint**: Spike PASS documentado. Rewrite liberado.

---

## Phase 3: Foundational (Blocking Prerequisites)

**Purpose**: Scaffolding Python compartilhado por US2–US5. **Prerequisite**: US1 verdict PASS.

**⚠️ CRITICAL**: Nenhuma user story de produção começa até esta fase estar completa.

**Constitution gates**: venv isolado (V), contratos preservados (I).

- [x] T011 Create `app/pyproject.toml` with dependencies: pinned py-cord (from spike), aiohttp, python-dotenv; dev deps pytest, ruff
- [x] T012 [P] Create `app/requirements.txt` matching confirmed spike `pycord_source` and run `pip install -r requirements.txt` in `app/.venv`
- [x] T013 [P] Implement `app/cronista/config.py`: load env vars with defaults (RECORDINGS_DIR=./recordings, UTTERANCE_SILENCE_MS=1000, AUTO_END_EMPTY_CHANNEL_MS=300000)
- [x] T014 [P] Implement `app/cronista/recording/storage.py`: `format_session_id`, `ensure_session_dir`, `ensure_user_dir`, `write_session_json`, `format_utterance_filename` per data-model.md
- [x] T015 [P] Implement `app/cronista/recording/speaking_log.py`: `SpeakingLog` class with async/sync `append(entry)` writing JSONL lines per `contracts/speaking-log.schema.json`
- [x] T016 [P] Define session dataclasses in `app/cronista/session.py`: `Participant`, `SessionData` matching `contracts/session-json.schema.json`
- [x] T017 [P] Create `app/cronista/__init__.py` and stub `app/cronista/__main__.py` entry point
- [x] T018 [P] Port unit tests to `app/tests/unit/test_storage.py` for `format_session_id` and `format_utterance_filename` (mirror `tests/unit/storage.test.ts`)

**Checkpoint**: Fundação Python pronta — user stories podem começar.

---

## Phase 4: User Story 2 - Preservar a experiência do GM (Priority: P1)

**Goal**: Comandos `!cronista entrar`, `!cronista status`, `!cronista encerrar` com respostas e efeitos equivalentes à versão Node.

**Independent Test**: Executar os três comandos em sessão de teste; respostas conforme `contracts/bot-commands.md` (quickstart Scenarios 1, 3, 4 parcial).

### Implementation for User Story 2

- [x] T019 [US2] Implement `SessionManager` in `app/cronista/session.py`: `start(member, channel, voice_client)`, `end()`, `active_session`, `is_recording`, single-session guard
- [x] T020 [US2] Implement `app/cronista/commands.py`: `handle_entrar`, `handle_encerrar`, `handle_status`, `handle_help` with responses from `contracts/bot-commands.md`
- [x] T021 [US2] Implement `app/cronista/bot.py`: create `discord.Bot`/`commands.Bot` with intents (guilds, voice_states, messages, message_content); route `!cronista` prefix
- [x] T022 [US2] Wire `entrar` in `app/cronista/commands.py`: validate author in voice channel, `channel.connect()` + `guild.change_voice_state(self_deaf=False, self_mute=True)`, call `SessionManager.start`, reply with session_id
- [x] T023 [US2] Wire `status` and `encerrar` in `app/cronista/commands.py`: duration formatting, participant count, session guard messages
- [x] T024 [US2] Complete `app/cronista/__main__.py`: load dotenv, create bot, `bot.run(token)`

**Checkpoint**: Bot responde aos três comandos; sessão inicia e persiste `session.json`.

---

## Phase 5: User Story 3 - Reimplementar captura sem bufferizar sessão inteira (Priority: P1)

**Goal**: Sink customizado escreve utterances incrementalmente em disco; memória estável em sessões longas.

**Independent Test**: Durante sessão ativa, arquivos `.ogg` aparecem antes do encerramento; RSS estável em teste ≥30 min (quickstart Scenarios 2, 9; SC-003).

### Implementation for User Story 3

- [x] T025 [US3] Implement `IncrementalUtteranceSink` in `app/cronista/recording/sink.py` subclassing `discord.sinks.Sink` with `write(data, user)` override
- [x] T026 [US3] In `app/cronista/recording/sink.py`: open new utterance file on first packet per user turn; track `start_ms` via `time.monotonic()` relative to session start
- [x] T027 [US3] In `app/cronista/recording/sink.py`: silence timer — close utterance after `UTTERANCE_SILENCE_MS` without packets; increment per-user seq counter
- [x] T028 [US3] In `app/cronista/recording/sink.py`: encode PCM to `.ogg` (Opus) on utterance close per research R2; write to `{session_dir}/{user_id}/{NNNN}.ogg`
- [x] T029 [US3] On utterance close in sink: append `SpeakingLogEntry` to `speaking_log.jsonl`, call `register_participant`, increment `utterance_count`, rewrite `session.json`
- [x] T030 [US3] Filter bot users in `app/cronista/recording/sink.py` (skip Cronista, Robigode, other bots)
- [x] T031 [US3] Integrate sink in `SessionManager.start()` in `app/cronista/session.py`: `voice_client.start_recording(sink, callback)`
- [x] T032 [US3] Integrate `voice_client.stop_recording()` in `SessionManager.end()`: flush open writers, finalize partial utterances

**Checkpoint**: Captura incremental funcional; arquivos por utterance durante sessão.

---

## Phase 6: User Story 4 - Manter contratos de integração e arquivos (Priority: P1)

**Goal**: `session.json`, `speaking_log.jsonl` e webhook n8n 100% compatíveis com spec 001.

**Independent Test**: Encerrar sessão e validar artefatos contra schemas; webhook payload conforme `contracts/n8n-webhook.schema.json` (quickstart Scenarios 4, 5, 8; SC-004).

### Implementation for User Story 4

- [x] T033 [US4] Implement `app/cronista/webhook.py`: `build_payload(session, paths)` and `notify_session_ended(session)` with aiohttp POST
- [x] T034 [US4] Add retry logic in `app/cronista/webhook.py`: 3 attempts, exponential backoff 1s/2s/4s; return success boolean
- [x] T035 [US4] On webhook failure in encerrar flow: set `webhook_failed=True` in session.json via `write_session_json`
- [x] T036 [US4] Wire webhook call after `SessionManager.end()` in `app/cronista/commands.py` and shared `end_active_session` helper
- [x] T037 [US4] Implement auto-end in `app/cronista/bot.py`: `on_voice_state_update` handler, empty-channel timer using `AUTO_END_EMPTY_CHANNEL_MS`, call shared end helper
- [x] T038 [P] [US4] Port webhook retry tests to `app/tests/unit/test_webhook.py` with mocked aiohttp (mirror `tests/unit/n8n-notifier.test.ts`)
- [ ] T039 [US4] Validate generated artifacts against `specs/002-python-pycord-migration/contracts/*.schema.json` using check-jsonschema or equivalent manual checklist

**Checkpoint**: Contratos downstream preservados; auto-end e webhook com retry funcionais.

---

## Phase 7: User Story 5 - Fazer cutover operacional seguro (Priority: P2)

**Goal**: Deploy Python isolado em `/opt/apps/cronista/`, coexistência com Robigode, rollback documentado, aposentar Node.

**Independent Test**: Serviço sobe em venv próprio; sessão de teste sem interferir Robigode; rollback testável (quickstart Scenarios 7, Cutover section; SC-006).

### Implementation for User Story 5

- [x] T040 [US5] Update `deploy/cronista.service`: `ExecStart=/opt/apps/cronista/.venv/bin/python -m cronista`, `WorkingDirectory=/opt/apps/cronista/app`, `User=adminvtt`, `Restart=on-failure`
- [x] T041 [US5] Document cutover and rollback procedure in `README.md` per `specs/002-python-pycord-migration/quickstart.md` Cutover section (FR-015)
- [ ] T042 [US5] Deploy to `/opt/apps/cronista/` in controlled window: rsync `app/`, create venv, install requirements, enable systemd unit
- [ ] T043 [US5] Execute quickstart Scenarios 1–6 and 8 on deployed service; record results in validation checklist
- [ ] T044 [US5] Verify Robigode coexistence per quickstart Scenario 7 (same channel, music uninterrupted)
- [x] T045 [US5] After successful pilot session (SC-007): remove Node legacy — delete `src/`, `tests/` (node), `package.json`, `package-lock.json`, `tsconfig.json`, `eslint.config.js`
- [x] T046 [US5] Rewrite `README.md` for Python-only stack: setup (`python -m venv`, `pip install`), run (`python -m cronista`), deploy, architecture pointing to `app/cronista/`

**Checkpoint**: Produção em Python; legado Node removido; rollback documentado.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validação final, testes e limpeza.

- [x] T047 [P] Run `pytest app/tests/unit/` from repo root and fix any failures
- [x] T048 Create `specs/002-python-pycord-migration/checklists/implementation-validation.md` and record all quickstart scenario results
- [ ] T049 Execute quickstart Scenario 9 (≥30 min session, monitor RSS) before first real RPG session (SC-003, SC-007)
- [ ] T050 [P] Optional cleanup: remove `spike/` and `spike_out/` after migration decision is final (FR-016 ambiguity resolved)

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 (Setup)
    ↓
Phase 2 (US1 Spike) ──FAIL──► STOP (document, re-evaluate)
    ↓ PASS
Phase 3 (Foundational) ──blocks──► Phase 4, 5, 6
    ↓
Phase 4 (US2 Commands) ──► Phase 5 (US3 Sink) ──► Phase 6 (US4 Contracts)
    ↓
Phase 7 (US5 Cutover) ──requires──► US2+US3+US4 complete
    ↓
Phase 8 (Polish)
```

### User Story Dependencies

| Story | Depends on | Can start after |
|-------|------------|-----------------|
| US1 Spike | Phase 1 | Setup complete |
| US2 Commands | US1 PASS + Foundational | Phase 3 |
| US3 Capture | US2 (session lifecycle) | T019–T024 |
| US4 Contracts | US3 (artifacts to validate) | T031–T032 |
| US5 Cutover | US2 + US3 + US4 | Phase 6 checkpoint |

### Within Each User Story

- Foundational modules before bot/commands
- SessionManager before sink integration
- Sink before webhook (needs artifacts)
- Deploy only after functional validation locally

### Parallel Opportunities

**Phase 1**: T002, T003, T004 in parallel after T001.

**Phase 3**: T012–T018 all [P] after T011.

**Phase 6**: T038 parallel with T033–T037.

**Phase 8**: T047, T050 parallel.

---

## Parallel Example: Phase 3 Foundational

```bash
# After T011 pyproject.toml exists, launch in parallel:
Task T013: "Implement app/cronista/config.py"
Task T014: "Implement app/cronista/recording/storage.py"
Task T015: "Implement app/cronista/recording/speaking_log.py"
Task T016: "Define dataclasses in app/cronista/session.py"
Task T017: "Create app/cronista/__main__.py stub"
Task T018: "Port tests to app/tests/unit/test_storage.py"
```

---

## Implementation Strategy

### MVP First (US1 Spike Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: US1 Spike
3. **STOP if FAIL** — re-evaluate stack per spec §Propostas
4. If PASS → proceed to Foundational + US2 as next increment

### Incremental Delivery

1. Setup + Spike PASS → decisão de stack documentada
2. Foundational + US2 → comandos funcionais, sessão persiste metadados
3. US3 → captura incremental de áudio
4. US4 → webhook, auto-end, contratos validados
5. US5 → cutover produção, aposentar Node
6. Polish → checklist completa, estabilidade 30 min+

### Suggested MVP Scope

**Minimum viable validation**: Phase 1 + Phase 2 (US1 spike). This alone delivers the highest-risk decision (DAVE reception) without committing to full rewrite.

**Minimum viable product**: Phase 1–6 (through US4) — bot funcional com contratos preservados, deployable locally before production cutover.

---

## Notes

- Referência funcional Node em `src/` — usar para portar comportamento, não como base de produção (FR-016)
- Sink recebe PCM decodificado (research R2) — encode Opus por utterance, não assumir passthrough Opus
- `self_deaf=False` é aplicado via `guild.change_voice_state(...)` após conectar (py-cord 2.8 não aceita esses flags em `connect()`)
- venv Cronista MUST NOT be shared with Bertroldo (Constitution V)
- Commit after each task or logical group; stop at any checkpoint to validate story independently
