---
description: "Task list for whisper-service (microserviço de transcrição)"
---

# Tasks: whisper-service

**Input**: Design documents from `whisper-service/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Testes unitários para config, health e transcribe (transcriber mockado) conforme plan.md. Qualidade de transcrição e integração Docker via quickstart manual — não mockável em CI. Sem TDD obrigatório.

**Organization**: Tarefas agrupadas por user story. **MVP = US1 + US2** (transcrever + health); US3 exige deploy; US4 é calibração operacional.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências pendentes)
- **[Story]**: User story (US1–US4)
- Caminhos relativos ao repo root

## Path Conventions

Código em `whisper-service/whisper_service/`; testes em `whisper-service/tests/unit/`; deploy em `deploy/whisper-service.service`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Estrutura mínima do pacote Python isolado do Cronista.

- [x] T001 Create directory skeleton per plan.md: `whisper-service/whisper_service/`, `whisper-service/tests/unit/` with `__init__.py` files
- [x] T002 [P] Create `whisper-service/pyproject.toml` with deps (fastapi, uvicorn[standard], faster-whisper, python-dotenv) and dev deps (pytest, httpx, ruff)
- [x] T003 [P] Create `whisper-service/requirements.txt` pinned for deploy (`pip install -r requirements.txt`)
- [x] T004 [P] Create `whisper-service/.env.example` documenting WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE, WHISPER_HOST, WHISPER_PORT, WHISPER_ALLOWED_PATH_PREFIX
- [x] T005 [P] Update root `.gitignore` for `whisper-service/.venv/`, `whisper-service/.pytest_cache/`, `whisper-service/__pycache__/`

**Checkpoint**: Repo pronto para implementação do serviço.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config, modelo singleton e app FastAPI — **bloqueia todas as user stories**.

**Constitution gates**: venv isolado (V), contratos HTTP em `whisper-service/contracts/` (I — novo serviço, sem alterar Cronista).

**⚠️ CRITICAL**: Nenhuma user story começa até esta fase estar completa.

- [x] T006 Implement `whisper-service/whisper_service/config.py`: load env vars with defaults per data-model.md (model_size, compute_type, host, port, allowed_path_prefix)
- [x] T007 Implement `whisper-service/whisper_service/paths.py`: `validate_audio_path(path, prefix)` — absolute path, no `..`, under allowed prefix
- [x] T008 Implement `whisper-service/whisper_service/schemas.py`: Pydantic models TranscribeRequest, TranscribeResponse, HealthResponse, ErrorResponse per contracts/
- [x] T009 Implement `whisper-service/whisper_service/transcriber.py`: WhisperModel singleton, `load()` on startup, `transcribe(path, language) -> (text, duration_s)`, thread-safe lock for sequential calls
- [x] T010 Implement `whisper-service/whisper_service/main.py`: FastAPI app with lifespan hook that calls transcriber.load(); bind host/port from config
- [x] T011 [P] Create `whisper-service/whisper_service/__init__.py` with `__version__`
- [x] T012 [P] Create `whisper-service/whisper_service/__main__.py` entry point invoking uvicorn with `--workers 1`

**Checkpoint**: App sobe e carrega modelo; rotas ainda não expostas.

---

## Phase 3: User Story 1 - Transcrever utterances sob demanda (Priority: P1) 🎯 MVP

**Goal**: `POST /transcribe` recebe caminho de áudio e devolve texto transcrito sem recarregar modelo.

**Independent Test**: `curl -X POST http://localhost:8008/transcribe` com `.ogg` real do Cronista → HTTP 200 com `text`, `language`, `duration_s` (quickstart Scenario 2).

**Covers**: FR-001–FR-004, FR-006, FR-009, FR-010, SC-002, SC-006

### Implementation for User Story 1

- [x] T013 [US1] Implement `POST /transcribe` route in `whisper-service/whisper_service/main.py` accepting TranscribeRequest body
- [x] T014 [US1] Return HTTP 404 with `{detail: "Arquivo não encontrado: …"}` when path missing in `whisper-service/whisper_service/main.py`
- [x] T015 [US1] Return HTTP 403 when `validate_audio_path` fails in `whisper-service/whisper_service/main.py`
- [x] T016 [US1] Wire `transcriber.transcribe()` in route; concatenate segment texts with spaces in `whisper-service/whisper_service/transcriber.py`
- [x] T017 [US1] Return HTTP 500 with descriptive `detail` on transcription errors without crashing process in `whisper-service/whisper_service/main.py`
- [x] T018 [US1] Populate `duration_s` from audio metadata or segment sum in `whisper-service/whisper_service/transcriber.py`
- [x] T019 [US1] Return HTTP 503 when model not yet loaded (transcribe while startup) in `whisper-service/whisper_service/main.py`

**Checkpoint**: Transcrição local funcional via curl.

---

## Phase 4: User Story 2 - Verificar disponibilidade do serviço (Priority: P1)

**Goal**: `GET /health` reporta status e modelo carregado para monitoramento.

**Independent Test**: `curl http://localhost:8008/health` → `{status: "ok", model, compute_type}` após startup (quickstart Scenario 1).

**Covers**: FR-005, SC-001

### Implementation for User Story 2

- [x] T020 [US2] Implement `GET /health` route in `whisper-service/whisper_service/main.py`
- [x] T021 [US2] Return HTTP 200 with `{status: "ok", model, compute_type}` when transcriber ready in `whisper-service/whisper_service/main.py`
- [x] T022 [US2] Return HTTP 503 with `{status: "loading", model, compute_type}` during model load in `whisper-service/whisper_service/main.py`
- [x] T023 [US2] Expose `is_ready` property on transcriber singleton in `whisper-service/whisper_service/transcriber.py`

**Checkpoint**: Health check utilizável por cron de monitoramento.

---

## Phase 5: User Story 3 - Integrar com n8n em Docker (Priority: P1)

**Goal**: n8n em container alcança serviço no host via `host.docker.internal:8008`.

**Independent Test**: `curl` de dentro do container n8n para `/health` e `/transcribe` com path absoluto de utterance real (quickstart Phase C).

**Covers**: FR-011, FR-012, FR-014, SC-004, SC-005

### Implementation for User Story 3

- [x] T024 [US3] Review and adjust `deploy/whisper-service.service`: WorkingDirectory, EnvironmentFile, ExecStart with `--host 0.0.0.0 --workers 1`, User=adminvtt
- [x] T025 [US3] Add production install section to `whisper-service/quickstart.md` Phase B (paths `/opt/apps/whisper-service/`)
- [x] T026 [US3] Add whisper-service overview and link to quickstart in root `README.md`
- [x] T027 [US3] Document ufw rules placeholder in `whisper-service/contracts/n8n-integration.md` with `docker network inspect bridge` procedure
- [ ] T028 [US3] Verify n8n workflow node URL uses `http://host.docker.internal:8008/transcribe` per `whisper-service/contracts/n8n-integration.md` (manual checklist item)
- [ ] T029 [US3] Execute quickstart Phase C on server: health from n8n container + one transcribe call with real session path

**Checkpoint**: Integração rede host↔Docker validada em produção.

---

## Phase 6: User Story 4 - Ajustar qualidade vs velocidade (Priority: P2)

**Goal**: Operador troca modelo/compute via env sem alterar código.

**Independent Test**: Alterar `WHISPER_MODEL_SIZE`, reiniciar, health reflete novo valor; comparar qualidade em amostra (quickstart Scenario 4).

**Covers**: FR-007, FR-008, SC-003

### Implementation for User Story 4

- [x] T030 [US4] Validate `WHISPER_MODEL_SIZE` against allowed set; fail fast with clear log on invalid value in `whisper-service/whisper_service/config.py`
- [x] T031 [US4] Validate `WHISPER_COMPUTE_TYPE` against allowed set in `whisper-service/whisper_service/config.py`
- [x] T032 [US4] Document model size trade-offs (tiny→large-v3, RAM, latency) in `whisper-service/README.md`
- [x] T033 [US4] Add manual quality validation checklist to `whisper-service/quickstart.md` Scenario 4 (campaign audio, PJ names)

**Checkpoint**: Calibração operacional documentada e testável.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Testes automatizados, validação de contratos e checklist de implementação.

- [x] T034 [P] Implement `whisper-service/tests/unit/test_config.py` for env parsing and validation defaults
- [x] T035 [P] Implement `whisper-service/tests/unit/test_health.py` with FastAPI TestClient (ready vs loading states)
- [x] T036 [P] Implement `whisper-service/tests/unit/test_transcribe.py` with mocked transcriber (404, 403, 200, 500 paths)
- [x] T037 [P] Implement `whisper-service/tests/unit/test_paths.py` for path traversal and prefix validation
- [x] T038 Validate example payloads against `whisper-service/contracts/*.schema.json` (check-jsonschema or manual checklist)
- [x] T039 Create `whisper-service/checklists/implementation-validation.md` mapping quickstart scenarios to FR/SC
- [ ] T040 Run quickstart Phase A locally: health + transcribe + error cases; record results in implementation-validation checklist
- [x] T041 Port external prototype `main.py` (if available) into `whisper-service/whisper_service/` layout; remove duplication — N/A (protótipo fora do repo; implementação nova)

**Checkpoint**: Pronto para cutover de produção e sessão piloto end-to-end (quickstart Phase D).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — iniciar imediatamente
- **Foundational (Phase 2)**: Depende de Setup — **BLOQUEIA** US1–US4
- **US1 (Phase 3)**: Depende de Foundational
- **US2 (Phase 4)**: Depende de Foundational; pode paralelizar com US1 após T010 (mesmo `main.py` — sequencial recomendado)
- **US3 (Phase 5)**: Depende de US1 + US2 funcionais localmente
- **US4 (Phase 6)**: Depende de US2 (health reflete config); independente de US3
- **Polish (Phase 7)**: Depende de US1 + US2 mínimo; validação completa após US3

### User Story Dependencies

```text
Setup → Foundational → US1 ──┬──► US3 (deploy + Docker)
                      US2 ──┘
                      US4 (config tuning, após US2)
                      Polish (após US1+US2; full gate após US3)
```

### Parallel Opportunities

**Phase 1**: T002, T003, T004, T005 em paralelo após T001

**Phase 2**: T011, T012 em paralelo após T006; T007, T008 em paralelo entre si

**Phase 7**: T034–T037 em paralelo

**Cross-story**: US4 pode começar após US2 sem aguardar US3

---

## Parallel Example: Phase 1 Setup

```bash
# Após T001:
Task T002: "Create whisper-service/pyproject.toml"
Task T003: "Create whisper-service/requirements.txt"
Task T004: "Create whisper-service/.env.example"
Task T005: "Update root .gitignore"
```

---

## Parallel Example: Phase 7 Tests

```bash
Task T034: "test_config.py"
Task T035: "test_health.py"
Task T036: "test_transcribe.py"
Task T037: "test_paths.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 — transcrever via curl
4. Complete Phase 4: US2 — health check
5. **STOP and VALIDATE**: quickstart Phase A Scenarios 1–3
6. Deploy (US3) quando MVP local estiver estável

### Incremental Delivery

1. Setup + Foundational → app carrega modelo
2. US1 + US2 → MVP local (curl)
3. US3 → produção + n8n Docker
4. US4 → calibrar qualidade (small vs medium)
5. Polish → testes unitários + sessão piloto Phase D

### Suggested MVP Scope

**In scope for first demo**: T001–T023 (Setup through US2)

**Defer to production hardening**: T024–T029 (US3 deploy), T030–T033 (US4 tuning)

---

## Notes

- Serviço MUST escutar `0.0.0.0` — nunca `127.0.0.1` alone (research R4)
- uvicorn MUST usar `--workers 1` (research R2, FR-012)
- Não alterar contratos Cronista (`session.json`, `speaking_log.jsonl`, webhook)
- Protótipo externo `main.py` citado no PRD — portar em T041 se existir
- Transcrição real pesada: validação de qualidade permanece manual (Constitution II)

---

## Task Summary

| Phase | Tasks | Story |
|-------|-------|-------|
| 1 Setup | T001–T005 (5) | — |
| 2 Foundational | T006–T012 (7) | — |
| 3 US1 Transcribe | T013–T019 (7) | US1 |
| 4 US2 Health | T020–T023 (4) | US2 |
| 5 US3 n8n Docker | T024–T029 (6) | US3 |
| 6 US4 Config | T030–T033 (4) | US4 |
| 7 Polish | T034–T041 (8) | — |
| **Total** | **41 tasks** | |

**Independent test criteria**:
- **US1**: curl transcribe → 200 + text
- **US2**: curl health → ok + model
- **US3**: curl from n8n container → health + transcribe
- **US4**: env change → health reflects new model
