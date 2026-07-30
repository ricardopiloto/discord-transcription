# Implementation Plan: whisper-service — atualização CPU threads

**Branch**: `whisper-service` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: `docs/demanda-whisper-service.md` + gap analysis do MVP 0.2.0

## Summary

Atualizar o whisper-service existente para cumprir a demanda operacional: **limitar threads CPU do CTranslate2** via `WHISPER_CPU_THREADS` (default **5**), preservando o contrato HTTP e o restante do MVP. O objetivo é permitir sessões longas (~2.000 utterances) sem saturar o servidor compartilhado (Foundry, Bertroldo, n8n, blog).

**Escopo de código**: `config.py` + `transcriber.py` + `.env.example` + testes/docs. Sem mudança de endpoints.

## Technical Context

**Language/Version**: Python 3.11–3.13

**Primary Dependencies**: FastAPI, uvicorn (workers=1), faster-whisper (CTranslate2), python-dotenv

**Storage**: N/A (stateless; lê paths do Cronista)

**Testing**: pytest unitários (config/cpu_threads); validação de convivência CPU via quickstart manual + `htop`

**Target Platform**: Linux host compartilhado, systemd, `/opt/apps/whisper-service/`

**Project Type**: Atualização incremental de microserviço HTTP existente

**Performance Goals**: Default 5 threads; sessão ~2.000 utterances sem saturação total de CPU

**Constraints**:
- Não quebrar contrato `/transcribe` / `/health`
- CPU-only; workers 1
- Bind `0.0.0.0:8008`
- Convivência com demais serviços do host

**Scale/Scope**: 1 processo; lote sequencial de milhares de utterances/sessão

## Constitution Check

| Principle | Gate Question | Status | Notes |
|-----------|---------------|--------|-------|
| I. Contract Stability | Contratos HTTP e Cronista preservados? | ✅ PASS | Sem mudança de payload; Cronista intacto |
| II. Evidence Before Commitment | Validação empírica? | ✅ PASS | SC-005 exige `htop` em teste real |
| III. Simplicity & YAGNI | Escopo mínimo? | ✅ PASS | Uma env var + parâmetro no load do modelo |
| IV. Incremental Durability | N/A (serviço stateless) | ➖ N/A | — |
| V. Operational Isolation | Isolamento + convivência? | ✅ PASS | Limite de threads protege o host compartilhado |

**Post-design re-check**: Design adiciona apenas `cpu_threads` à config e ao `WhisperModel(...)`. Sem Complexity Tracking.

## Project Structure

### Documentation (esta feature)

```text
whisper-service/
├── spec.md              # Atualizado (demanda)
├── plan.md              # Este arquivo
├── research.md          # Phase 0 (R9 cpu_threads)
├── data-model.md        # RuntimeConfig + cpu_threads
├── quickstart.md        # Cenário convivência CPU
├── contracts/           # API inalterada; env documentado
└── tasks.md             # Regenerar via /speckit-tasks
```

### Source Code (delta)

```text
whisper-service/
├── whisper_service/
│   ├── config.py        # + cpu_threads / WHISPER_CPU_THREADS
│   ├── transcriber.py   # WhisperModel(..., cpu_threads=...)
│   └── ...
├── .env.example         # + WHISPER_CPU_THREADS=5
├── README.md            # documentar env
└── tests/unit/
    └── test_config.py   # default 5, invalid values
```

**Structure Decision**: Reusar pacote atual; mudança localizada, sem novos módulos.

## Phase 0 → Research

Ver [research.md](./research.md) — decisão R9: `WhisperModel(cpu_threads=...)` mapeado de `WHISPER_CPU_THREADS`.

## Phase 1 → Design

| Artifact | Path | Status |
|----------|------|--------|
| Data model | [data-model.md](./data-model.md) | ✅ atualizado |
| API contract | [contracts/api.md](./contracts/api.md) | ✅ (sem mudança de endpoints) |
| Env / ops | [contracts/n8n-integration.md](./contracts/n8n-integration.md) + `.env.example` | ✅ documentar threads |
| Quickstart | [quickstart.md](./quickstart.md) | ✅ cenário SC-005 |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Next Steps

1. `/speckit-tasks` — tarefas da atualização (config, transcriber, testes, quickstart CPU)
2. `/speckit-implement` — aplicar `cpu_threads`
3. Validar SC-005 em produção com sessão real + `htop`
