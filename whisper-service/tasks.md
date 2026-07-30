---
description: "Task list for whisper-service CPU threads update"
---

# Tasks: whisper-service — atualização CPU threads

**Input**: Design documents from `whisper-service/` (spec/plan atualizados 2026-07-30)

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Context**: MVP 0.2.0 já entregue. Esta lista cobre **apenas o gap** da demanda (`WHISPER_CPU_THREADS` + convivência CPU). US1–US3 = regressão; US4–US5 = implementação nova.

**Tests**: Unitários de config (default 5, inválidos); convivência CPU via quickstart Phase E (manual). Sem TDD obrigatório.

**Organization**: Foco em US4 (env) e US5 (aplicação no modelo + validação operacional).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes)
- **[Story]**: US4–US5 (novas); US1–US3 só regressão
- Caminhos relativos ao repo root

## Path Conventions

Delta em `whisper-service/whisper_service/config.py`, `transcriber.py`, `.env.example`, `tests/unit/`, docs.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirmar base do MVP antes do delta — sem recriar o serviço.

- [x] T001 Verify package layout exists per plan.md: `whisper-service/whisper_service/{config,transcriber,main}.py` and `whisper-service/tests/unit/`
- [x] T002 [P] Confirm `.gitignore` already covers `whisper-service/.venv/` and `__pycache__/`

**Checkpoint**: Repo pronto para mudança incremental.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Campo `cpu_threads` na config — **bloqueia US4 e US5**.

**⚠️ CRITICAL**: US4/US5 não começam até T003–T005 estarem feitos.

- [x] T003 Add `cpu_threads: int` to `Config` dataclass in `whisper-service/whisper_service/config.py`
- [x] T004 Load `WHISPER_CPU_THREADS` with default `5` in `load_config()` in `whisper-service/whisper_service/config.py`
- [x] T005 Validate `WHISPER_CPU_THREADS` is integer ≥ 1; raise clear `ValueError` on invalid values in `whisper-service/whisper_service/config.py`

**Checkpoint**: Config carrega `cpu_threads=5` por default.

---

## Phase 3: User Story 4 - Configurar threads via env (Priority: P2)

**Goal**: Operador controla limite de threads sem alterar código; default 5; inválidos falham no startup.

**Independent Test**: Sem env → `load_config().cpu_threads == 5`; `WHISPER_CPU_THREADS=0` → ValueError; `WHISPER_CPU_THREADS=3` → 3.

**Covers**: FR-007, FR-008, FR-016, SC-006

### Implementation for User Story 4

- [x] T006 [US4] Add `WHISPER_CPU_THREADS=5` to `whisper-service/.env.example` with comment about host compartilhado
- [x] T007 [P] [US4] Document `WHISPER_CPU_THREADS` in env table in `whisper-service/README.md`
- [x] T008 [P] [US4] Extend `whisper-service/tests/unit/test_config.py`: default 5 when unset; reject ≤0 and non-integer

**Checkpoint**: Config e docs refletem a demanda; testes unitários passam.

---

## Phase 4: User Story 5 - Convivência CPU (Priority: P1) 🎯

**Goal**: Passar `cpu_threads` ao `WhisperModel` e permitir validação operacional (sessão longa sem saturar host).

**Independent Test**: Startup log mostra threads; `WhisperModel(..., cpu_threads=N)`; quickstart Phase E com `htop` em lote longo.

**Covers**: FR-015, SC-005, SC-006

### Implementation for User Story 5

- [x] T009 [US5] Pass `cpu_threads=_config.cpu_threads` to `WhisperModel(...)` in `whisper-service/whisper_service/transcriber.py`
- [x] T010 [US5] Log model size, compute_type, and cpu_threads on successful load in `whisper-service/whisper_service/transcriber.py`
- [x] T011 [P] [US5] Confirm quickstart Phase E exists in `whisper-service/quickstart.md` (SC-005 / htop / ~2.000 utterances)
- [x] T012 [P] [US5] Add Phase E row(s) to `whisper-service/checklists/implementation-validation.md` for SC-005/SC-006

**Checkpoint**: Modelo respeita orçamento de threads; checklist de validação operacional pronto.

---

## Phase 5: Regressão US1–US3 (Priority: P1)

**Goal**: Garantir que a atualização não quebra contratos HTTP e testes existentes.

**Independent Test**: `pytest tests/ -v` green; `/health` e `/transcribe` inalterados.

**Covers**: FR-017, SC-001–SC-003 (regressão)

- [x] T013 [US1] Run existing `whisper-service/tests/unit/test_transcribe.py` and confirm 200/404/403/500 paths still pass
- [x] T014 [P] [US2] Run existing `whisper-service/tests/unit/test_health.py` and confirm ok/loading contracts unchanged
- [x] T015 [P] [US3] Confirm `deploy/whisper-service.service` still uses workers=1 / `python -m whisper_service` (no change required unless broken)

**Checkpoint**: Regressão automatizada OK; deploy unit intacto.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Docs, changelog, validação local e gate de produção.

- [x] T016 [P] Note anti-pattern (cpu_threads > host cores) in `whisper-service/README.md`
- [x] T017 [P] Update root `CHANGELOG.md` with whisper-service CPU threads entry (new patch/minor as appropriate)
- [x] T018 Run full unit suite: `cd whisper-service && .venv/bin/pytest tests/ -v`
- [x] T019 Record local config regression results in `whisper-service/checklists/implementation-validation.md`
- [ ] T020 Execute quickstart Phase E on production host (manual): lote longo + htop + convivência Foundry/Bertroldo — mark SC-005

**Checkpoint**: Pronto para cutover; SC-005 marcado após validação real.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Imediato
- **Foundational (Phase 2)**: Depende de Setup — **BLOQUEIA** US4/US5
- **US4 (Phase 3)**: Depende de Foundational
- **US5 (Phase 4)**: Depende de Foundational (idealmente após T003–T005; pode seguir T006 em paralelo com docs)
- **Regressão (Phase 5)**: Após T009 (modelo wired)
- **Polish (Phase 6)**: Após US4 + US5 código; T020 é gate manual de produção

### User Story Dependencies

```text
Setup → Foundational (cpu_threads config)
              ├─► US4 (env + docs + unit tests)
              └─► US5 (WhisperModel + logs + Phase E checklist)
                        └─► Regressão US1–US3
                              └─► Polish → T020 (manual produção)
```

### Parallel Opportunities

- T002 com T001
- T007 || T008 após T006
- T011 || T012 após T009/T010
- T014 || T015 após T013
- T016 || T017

---

## Parallel Example: US4

```bash
Task T007: "Document WHISPER_CPU_THREADS in whisper-service/README.md"
Task T008: "Extend whisper-service/tests/unit/test_config.py"
```

---

## Parallel Example: Polish docs

```bash
Task T016: "Anti-pattern note in README"
Task T017: "CHANGELOG entry"
```

---

## Implementation Strategy

### MVP desta atualização (código)

1. Phase 1–2: config `cpu_threads`
2. Phase 3–4: env docs + `WhisperModel(cpu_threads=...)`
3. Phase 5: pytest regressão
4. **STOP**: deploy + restart serviço
5. Phase 6 T020: validar SC-005 em produção

### Suggested scope for first demo

**In scope agora**: T001–T019 (código + testes + docs)

**Defer to production**: T020 (Phase E / SC-005 com sessão real)

---

## Notes

- NÃO alterar payloads de `/transcribe` ou `/health`
- Default **5** mesmo se faster-whisper default for 4 (demanda)
- `cpu_threads` no construtor — não só `OMP_NUM_THREADS` (research R9)
- T020 é evidência empírica (Constitution II) — não substituível por unit test

---

## Task Summary

| Phase | Tasks | Story |
|-------|-------|-------|
| 1 Setup | T001–T002 (2) | — |
| 2 Foundational | T003–T005 (3) | — |
| 3 US4 Config env | T006–T008 (3) | US4 |
| 4 US5 CPU convivência | T009–T012 (4) | US5 |
| 5 Regressão US1–US3 | T013–T015 (3) | US1–US3 |
| 6 Polish | T016–T020 (5) | — |
| **Total** | **20 tasks** | |

**Independent test criteria**:
- **US4**: `load_config()` default 5; inválidos falham; `.env.example` documentado
- **US5**: `WhisperModel(..., cpu_threads=N)` + log; Phase E checklist
- **US1–US3**: pytest existente green; unit systemd intacto
- **MVP update**: T001–T019; produção SC-005 = T020
