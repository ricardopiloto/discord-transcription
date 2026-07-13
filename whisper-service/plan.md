# Implementation Plan: whisper-service

**Branch**: `whisper-service` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `whisper-service/spec.md` (derived from `docs/PRD-whisper-service.md`)

## Summary

Implementar um microserviço HTTP stateless que carrega o modelo **faster-whisper** uma única vez na inicialização e transcreve utterances `.ogg` do Cronista sob demanda, consumido exclusivamente pelo workflow n8n "Cronista - Transcrição da Sessão". O serviço vive em `whisper-service/` no mesmo repositório, com venv e unit systemd próprios em `/opt/apps/whisper-service/`, escutando em `0.0.0.0:8008` para ser alcançável pelo n8n em Docker via `host.docker.internal`.

**Abordagem**: FastAPI + uvicorn (worker único) + faster-whisper (CPU, `int8`); entrada por caminho de arquivo no host (sem upload HTTP); contratos HTTP documentados em `contracts/`; validação local com `curl` antes de integração Docker.

## Technical Context

**Language/Version**: Python 3.11+ (3.11–3.13; evitar 3.14 até faster-whisper confirmar suporte)

**Primary Dependencies**: `fastapi`, `uvicorn[standard]`, `faster-whisper` (CTranslate2), `python-dotenv` (config)

**Storage**: N/A — serviço stateless; lê arquivos `.ogg` do filesystem do Cronista (`/opt/apps/cronista/recordings/...`); não persiste transcrições (responsabilidade do n8n)

**Testing**: `pytest` + `httpx`/`TestClient` para contratos HTTP e validação de paths; qualidade de transcrição e latência via quickstart manual com áudio real da campanha (não mockável em CI)

**Target Platform**: Linux (Ubuntu/Fedora, Kron Mini K1), systemd, usuário `adminvtt`, path produção `/opt/apps/whisper-service/`, venv isolado

**Project Type**: Long-running HTTP microservice (single worker, modelo residente em RAM)

**Performance Goals**: Utterance de 10–15s transcrita em << 120s (timeout n8n); sessão piloto ≥20 utterances sequenciais sem restart; modelo carregado uma vez (~dezenas de segundos na subida)

**Constraints**:
- CPU-only (`WHISPER_COMPUTE_TYPE=int8` default)
- Sem autenticação — firewall restringe porta 8008
- Bind `0.0.0.0` (não `127.0.0.1`) para tráfego Docker bridge
- uvicorn `--workers 1` (evitar duplicar modelo em RAM)
- n8n chama sequencialmente — sem fila/workers no MVP
- Não alterar contratos do Cronista (`session.json`, `speaking_log.jsonl`, webhook)

**Scale/Scope**: 1 instância, ~centenas de utterances/sessão (3–4h), cadência semanal/quinzenal, único consumidor (n8n)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Question | Status | Notes |
|-----------|---------------|--------|-------|
| I. Contract Stability | Contratos Cronista downstream preservados? | ✅ PASS | Serviço novo; não altera `session.json`, JSONL ou webhook |
| II. Evidence Before Commitment | Validação empírica antes de produção? | ✅ PASS | Quickstart: áudio real + integração Docker documentados como gate |
| III. Simplicity & YAGNI | Single-process, escopo delimitado? | ✅ PASS | Sem DB, fila, dashboard, GPU ou upload HTTP no MVP |
| IV. Incremental Durability | Gravação incremental por utterance? | ➖ N/A | Serviço de transcrição stateless; durability é do Cronista |
| V. Operational Isolation | venv/systemd isolados? | ✅ PASS | `/opt/apps/whisper-service/`; venv separado de Cronista e Bertroldo |

**Post-design re-check**: Design mantém simplicidade e isolamento. Novo contrato HTTP documentado em `contracts/` sem impacto nos schemas 001/002 do Cronista. Nenhuma violação exige Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
whisper-service/
├── spec.md
├── plan.md              # Este arquivo
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── api.md
│   ├── transcribe-request.schema.json
│   ├── transcribe-response.schema.json
│   ├── health-response.schema.json
│   └── n8n-integration.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — ainda não criado)
```

### Source Code (repository root)

```text
whisper-service/
├── whisper_service/
│   ├── __init__.py
│   ├── __main__.py          # Entry: uvicorn whisper_service.main:app
│   ├── main.py              # FastAPI app, routes /transcribe, /health
│   ├── config.py            # WHISPER_* env vars
│   └── transcriber.py       # WhisperModel singleton, transcribe()
├── tests/
│   └── unit/
│       ├── test_config.py
│       ├── test_health.py
│       └── test_transcribe.py
├── pyproject.toml
├── requirements.txt
└── .env.example

deploy/
└── whisper-service.service  # systemd unit (novo)

docs/
└── PRD-whisper-service.md   # PRD de origem (já existe)
```

**Structure Decision**: Pacote Python `whisper_service/` espelha o padrão do Cronista (`app/cronista/`). Protótipo `main.py` existente (se houver fora do repo) será portado/refatorado para este layout. Deploy em `/opt/apps/whisper-service/` com clone do repositório ou subpath — mesmo padrão operacional do Cronista.

## Phase 0 → Research

Ver [research.md](./research.md) — 8 decisões (stack, path-based I/O, rede Docker, workers, modelo, segurança, testes, integração n8n).

## Phase 1 → Design

| Artifact | Path | Status |
|----------|------|--------|
| Data model | [data-model.md](./data-model.md) | ✅ |
| API contract | [contracts/api.md](./contracts/api.md) | ✅ |
| JSON schemas | [contracts/*.schema.json](./contracts/) | ✅ |
| n8n integration | [contracts/n8n-integration.md](./contracts/n8n-integration.md) | ✅ |
| Quickstart | [quickstart.md](./quickstart.md) | ✅ |

## Complexity Tracking

> Nenhuma violação da constituição requer justificativa.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Next Steps

1. `/speckit-tasks` — gerar `tasks.md` ordenado por dependência
2. Implementar em `whisper-service/whisper_service/`
3. Validar quickstart local (curl + áudio real)
4. Deploy systemd + firewall + ajuste URL no workflow n8n
5. Sessão piloto end-to-end (Cronista → n8n → whisper-service → transcript)
