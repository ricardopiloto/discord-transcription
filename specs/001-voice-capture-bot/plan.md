# Implementation Plan: Bot de Captura de Voz para Sessões de RPG

**Branch**: `001-voice-capture-bot` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-voice-capture-bot/spec.md`

## Summary

Implementar o **Cronista**, um bot Discord dedicado que entra no canal de voz da mesa de RPG, grava áudio isolado por jogador segmentado em utterances (turnos de fala), persiste metadados em disco (`session.json`, `speaking_log.jsonl`, arquivos `.ogg`) e notifica o pipeline n8n ao encerrar a sessão.

Abordagem técnica: processo Node.js long-running com `discord.js` v14 + `@discordjs/voice`, gravação Opus→Ogg sem re-encode via `prism-media`, armazenamento file-based e deploy systemd independente no Kron Mini K1. O repositório já possui scaffolding inicial em `src/`; este plano cobre a implementação completa das funcionalidades P1/P2 da spec.

## Technical Context

**Language/Version**: TypeScript 5.8 / Node.js ≥ 20 (ESM)

**Primary Dependencies**: `discord.js` v14, `@discordjs/voice` v0.18, `prism-media` v1.3, `dotenv`

**Storage**: Sistema de arquivos local — `{RECORDINGS_DIR}/{session_id}/` com JSON + JSONL + Ogg Opus

**Testing**: Validação manual end-to-end via quickstart (sessão piloto no Discord); testes unitários opcionais para utilitários puros (`storage`, `session-id`, webhook retry). Sem framework de teste configurado ainda — adicionar `node:test` na fase de tasks se necessário.

**Target Platform**: Linux (Fedora), systemd, usuário `adminvtt`, path produção `/opt/apps/cronista/`

**Project Type**: Long-running Discord bot (single-process service)

**Performance Goals**: Sessões de 3–4h contínuas; gravação I/O-bound (sem re-encode); CPU mínima durante sessão ao vivo

**Constraints**:
- Servidor Kron Mini K1 já sob carga (Foundry, Bertroldo, n8n, Odysseus)
- Uma sessão ativa por guild
- Bot mudo/surdo na conexão de voz (`selfDeaf: true`, `selfMute: true`)
- Coexistência com Robigode (conexões de voz independentes)
- FFmpeg **não** necessário (Opus nativo do Discord)

**Scale/Scope**: 1 servidor Discord, ~5–8 participantes, ~centenas de utterances/sessão, cadência semanal/quinzenal

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Constitution ratificada | ⚠️ N/A | `.specify/memory/constitution.md` ainda é template — gates interim aplicados a partir do PRD |
| Simplicidade (YAGNI) | ✅ PASS | File-based storage, single process, sem DB, sem dashboard |
| Escopo MVP delimitado | ✅ PASS | Transcrição/RAG/recuperação de crash fora do escopo |
| Testabilidade | ✅ PASS | Cenários de quickstart cobrem fluxos P1; contratos JSON validáveis |
| Observabilidade mínima | ✅ PASS | Logs stdout + `webhook_failed` em session.json |
| Independência de serviços | ✅ PASS | Bot standalone; webhook fire-and-forget com retry |

**Post-design re-check**: Design file-based + contratos explícitos mantém simplicidade. Nenhuma violação que exija Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-voice-capture-bot/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── session-json.schema.json
│   ├── speaking-log.schema.json
│   ├── n8n-webhook.schema.json
│   └── bot-commands.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
src/
├── index.ts                 # Entry point
├── bot/
│   ├── client.ts            # Discord client + event wiring
│   └── commands/
│       ├── index.ts         # Command router
│       ├── entrar.ts        # !cronista entrar
│       ├── encerrar.ts      # !cronista encerrar
│       └── status.ts        # !cronista status
├── config/
│   └── index.ts             # Env vars (DISCORD_TOKEN, RECORDINGS_DIR, etc.)
├── recording/
│   ├── session-manager.ts   # Session lifecycle (start/end/state)
│   ├── audio-recorder.ts    # Per-user utterance capture (TODO: implement)
│   ├── speaking-log.ts      # Append-only JSONL writer
│   └── storage.ts           # Paths, session.json, user dirs
├── webhook/
│   └── n8n-notifier.ts      # POST with exponential backoff
└── types/
    └── session.ts           # TypeScript interfaces

deploy/
└── cronista.service         # systemd unit

recordings/                  # Local dev output (gitignored)
tests/                       # Future: unit + integration (Phase 2 tasks)
├── unit/
└── integration/
```

**Structure Decision**: Single-project Node.js bot. Módulos alinhados às responsabilidades da spec: `bot/` (interface Discord), `recording/` (domínio de captura), `webhook/` (integração n8n). Scaffolding existente em `src/` será estendido, não reestruturado.

## Phase 0 → Research

Ver [research.md](./research.md) — todas as decisões técnicas resolvidas, sem NEEDS CLARIFICATION pendentes.

## Phase 1 → Design

| Artifact | Path | Status |
|----------|------|--------|
| Data model | [data-model.md](./data-model.md) | ✅ |
| Contracts | [contracts/](./contracts/) | ✅ |
| Quickstart | [quickstart.md](./quickstart.md) | ✅ |

## Implementation Phases (for /speckit-tasks)

### Phase A — Core recording (P1)
1. Completar `audio-recorder.ts`: subscribe por userId, Ogg Opus, speaking log
2. Integrar AudioRecorder no fluxo `entrar` via SessionManager
3. Incrementar `utterance_count` e persistir `session.json` incrementalmente

### Phase B — Session lifecycle (P1)
4. Encerramento automático: timer de canal vazio (VoiceStateUpdate)
5. Finalizar `encerrar`: destroy connection, flush files, webhook
6. Guard de sessão única por guild

### Phase C — Observability & polish (P2)
7. Comando `status` com formatação de duração
8. Logs estruturados mínimos
9. Teste de coexistência com Robigode (manual, quickstart §5)

### Phase D — Deploy
10. Validar `deploy/cronista.service` em staging
11. Documentar variáveis de produção

## Complexity Tracking

> Nenhuma violação de simplicidade identificada — seção não aplicável.
