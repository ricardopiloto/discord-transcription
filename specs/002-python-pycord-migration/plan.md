# Implementation Plan: Migração do Cronista para Stack Python/Py-Cord

**Branch**: `002-python-pycord-migration` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-python-pycord-migration/spec.md`

## Summary

Reimplementar o Cronista (bot de captura de voz para sessões de RPG) em Python 3.11+ com `py-cord`, substituindo a implementação Node/`@discordjs/voice` existente, motivada por risco de recepção de áudio sob o protocolo DAVE do Discord. A abordagem é **spike-first**: antes do rewrite completo, um bot mínimo valida que a recepção de áudio funciona no ambiente real. A migração preserva integralmente os contratos externos (comandos `!cronista`, estrutura de arquivos por sessão, `session.json`, `speaking_log.jsonl`, webhook n8n) e roda como serviço systemd com venv Python isolado, separado do Bertroldo.

**Descoberta crítica da pesquisa** (ver [research.md](./research.md) R1): a py-cord estável (v2.8.x) ainda emite `RuntimeWarning` de que a recepção de voz está quebrada sob DAVE; a correção vive em PR aberto (#3202) usando bindings `davey`. Isso torna o spike (US1) uma **gate obrigatória** — não uma formalidade — e o plano trata a seleção da versão/fonte da py-cord como decisão a ser confirmada empiricamente.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `py-cord` (com suporte de recepção sob DAVE — versão/fonte a confirmar no spike), `aiohttp` (webhook async), `python-dotenv` (config). Codec Opus via `libopus` (bindings da py-cord).

**Storage**: Sistema de arquivos local — `{RECORDINGS_DIR}/{session_id}/` com `session.json`, `speaking_log.jsonl` e `{user_id}/NNNN.ogg`

**Testing**: `pytest` para unidades puras (session id, storage paths, webhook retry com mock); validação de captura via spike + quickstart manual (áudio ao vivo não é testável em CI)

**Target Platform**: Linux (Fedora, Kron Mini K1), systemd, usuário `adminvtt`, path produção `/opt/apps/cronista/`, venv próprio

**Project Type**: Long-running Discord bot (single-process service)

**Performance Goals**: Sessões de 3–4h contínuas; escrita incremental por utterance; memória estável (sem buffer da sessão inteira em RAM); CPU baixa durante sessão ao vivo

**Constraints**:
- Recepção sob DAVE precisa funcionar no ambiente real (gate do spike)
- Sink customizado obrigatório: `WaveSink` bufferiza tudo em memória (inadequado para 3–4h)
- venv Python isolado: `py-cord` e `discord.py` (Bertroldo) colidem no namespace `discord`
- Coexistência com Robigode (conexões de voz independentes)
- Contratos downstream (n8n) imutáveis

**Scale/Scope**: 1 servidor Discord, ~5–8 participantes, centenas de utterances/sessão, cadência semanal/quinzenal

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Question | Status | Notes |
|-----------|---------------|--------|-------|
| I. Contract Stability | Contratos downstream preservados? | ✅ PASS | Schemas 001 reutilizados; spike-acceptance + bot-commands novos |
| II. Evidence Before Commitment | Spike DAVE com PASS/FAIL antes do rewrite? | ✅ PASS | Phase A gate; contrato em `contracts/spike-acceptance.md` |
| III. Simplicity & YAGNI | Single-process, file-based, escopo delimitado? | ✅ PASS | Sem DB/fila/dashboard; transcrição/RAG fora de escopo |
| IV. Incremental Durability | Gravação incremental por utterance? | ✅ PASS | Sink customizado; WaveSink rejeitado em research R2 |
| V. Operational Isolation | venv/systemd isolados; Robigode coexist? | ✅ PASS | `/opt/apps/cronista/`; rollback documentado em quickstart |

**Post-design re-check**: O design mantém contratos e adiciona uma gate de validação empírica. Nenhuma violação exige Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-python-pycord-migration/
├── plan.md              # Este arquivo
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── session-json.schema.json
│   ├── speaking-log.schema.json
│   ├── n8n-webhook.schema.json
│   ├── bot-commands.md
│   └── spike-acceptance.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — ainda não criado)
```

### Source Code (repository root)

A nova stack Python vive em `app/` (fonte) para separar claramente do `src/` Node legado durante a transição. Ao concluir o cutover (FR-016), `src/`, `package.json`, `tsconfig.json`, `eslint.config.js` e `tests/` (Node) são removidos.

```text
app/                          # Nova implementação Python
├── cronista/
│   ├── __init__.py
│   ├── __main__.py           # Entry point (python -m cronista)
│   ├── config.py             # Env vars (DISCORD_TOKEN, RECORDINGS_DIR, ...)
│   ├── bot.py                # Bot py-cord, intents, eventos, auto-end
│   ├── commands.py           # !cronista entrar | encerrar | status
│   ├── session.py            # SessionManager (ciclo de vida, participantes)
│   ├── recording/
│   │   ├── __init__.py
│   │   ├── sink.py           # Sink customizado: escrita incremental por utterance
│   │   ├── storage.py        # session_id, paths, session.json, user dirs
│   │   └── speaking_log.py   # writer JSONL append-only
│   └── webhook.py            # Notificação n8n com retry/backoff
├── tests/
│   └── unit/
│       ├── test_storage.py
│       └── test_webhook.py
├── pyproject.toml            # Deps + config pytest/ruff
├── requirements.txt          # Pin de dependências para deploy
└── .python-version

spike/                        # US1 — bot mínimo de validação (descartável)
└── record_smoke.py

deploy/
└── cronista.service          # systemd (atualizado para venv Python)

# Legado Node (removido no cutover — FR-016):
# src/, tests/ (node), package.json, tsconfig.json, eslint.config.js
```

**Structure Decision**: Projeto Python single-package em `app/cronista/`, espelhando os módulos da stack Node (bot / recording / webhook / config) para transferência de conhecimento direta. O spike fica isolado em `spike/` por ser descartável e não fazer parte do pacote de produção. Node legado coexiste apenas durante a transição e é removido ao final.

## Phase 0 → Research

Ver [research.md](./research.md) — 9 decisões, incluindo a ressalva de que a recepção py-cord sob DAVE depende de versão/PR e deve ser confirmada no spike (nenhum NEEDS CLARIFICATION bloqueante remanescente).

## Phase 1 → Design

| Artifact | Path | Status |
|----------|------|--------|
| Data model | [data-model.md](./data-model.md) | ✅ |
| Contracts | [contracts/](./contracts/) | ✅ (schemas preservados da 001 + spike + comandos) |
| Quickstart | [quickstart.md](./quickstart.md) | ✅ |

## Implementation Phases (para /speckit-tasks)

### Phase A — Spike / gate de recepção DAVE (US1) 🚦
1. Bot mínimo `spike/record_smoke.py`: entra, grava alguns minutos, valida áudio
2. Determinar versão/fonte de py-cord que recebe sob DAVE (estável vs PR #3202/`davey`)
3. Registrar resultado (PASS/FAIL) em `contracts/spike-acceptance.md`; FAIL bloqueia Phase B

### Phase B — Scaffolding Python (Foundational)
4. `pyproject.toml`, `requirements.txt`, venv, ruff/pytest
5. `config.py`, `storage.py`, `speaking_log.py`, tipos/dataclasses de sessão
6. Testes unitários de storage e webhook (portados da 001)

### Phase C — Captura e sessão (US2, US3, US4)
7. Sink customizado com escrita incremental por utterance + delimitação por silêncio
8. `SessionManager` (start/end, participantes, utterance_count)
9. Comandos `entrar` / `encerrar` / `status`
10. Auto-end por canal vazio; webhook com retry + `webhook_failed`

### Phase D — Contratos e coexistência (US4, US5)
11. Validar `session.json` / `speaking_log.jsonl` / webhook contra schemas
12. Verificar coexistência com Robigode; venv isolado

### Phase E — Cutover (US5, FR-016)
13. Atualizar `deploy/cronista.service` para venv Python
14. Runbook de cutover + rollback
15. Remover stack Node legada (`src/`, `package.json`, etc.)

## Complexity Tracking

> Nenhuma violação de simplicidade identificada — seção não aplicável.
