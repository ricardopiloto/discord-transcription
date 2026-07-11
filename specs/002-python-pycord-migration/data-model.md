# Data Model: Migração Python/Py-Cord

**Feature**: 002-python-pycord-migration  
**Date**: 2026-07-10

## Overview

O modelo de dados **não muda** em relação à implementação 001 — a migração preserva os contratos em disco e o webhook. Este documento reafirma as entidades no vocabulário Python e destaca o que é novo (sink incremental, gate de spike).

```text
{RECORDINGS_DIR}/
  {session_id}/
    session.json           # Metadados da sessão (atualizado incrementalmente)
    speaking_log.jsonl     # Append-only, uma linha por utterance
    {discord_user_id}/
      0001.ogg
      0002.ogg
      ...
```

---

## Entity: Session

Partida de RPG gravada. Schema idêntico ao contrato 001.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | str | yes | `YYYYMMDD-HHmmss`, único por deployment |
| `guild_id` | str | yes | Discord guild snowflake |
| `channel_id` | str | yes | Discord voice channel snowflake |
| `started_at` | str (ISO 8601 UTC) | yes | Início da sessão |
| `ended_at` | str (ISO 8601 UTC) | no | Definido no encerramento |
| `participants` | list[Participant] | yes | Cresce conforme usuários falam |
| `webhook_failed` | bool | no | `true` se o POST ao n8n falhou após retries |

### State Transitions

```text
[none] ──start()──► [recording]
[recording] ──end()──► [ended]
[recording] ──crash──► [orphaned]   (fora de escopo: sem auto-recovery)
```

### Validation Rules

- `session_id` casa com `^\d{8}-\d{6}$`
- Uma única sessão `[recording]` por processo (single-tenant)
- `ended_at` ≥ `started_at` quando presente
- Representação Python: `dataclass` serializada com `json.dump(..., ensure_ascii=False, indent=2)`

---

## Entity: Participant

Jogador/GM registrado ao falar.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | str | yes | Discord user snowflake |
| `display_name` | str | yes | Nome de exibição na primeira fala |
| `utterance_count` | int ≥ 0 | yes | Incrementado ao fechar cada utterance |

### Validation Rules

- `user_id` único na lista de participantes
- Adicionado na primeira fala detectada (não apenas ao entrar no canal)
- Bots (Cronista, Robigode) nunca viram participantes

---

## Entity: Utterance (Segmento de fala)

Turno contínuo de fala de um participante.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | str | yes | Dono do segmento |
| `seq` | int ≥ 1 | yes | Sequencial por usuário na sessão |
| `file` | str | yes | Relativo: `{user_id}/{NNNN}.ogg` |
| `start_ms` | int ≥ 0 | yes | Ms desde `session.started_at` |
| `end_ms` | int ≥ 0 | yes | Ms desde `session.started_at` |
| `duration_ms` | int ≥ 0 | yes | `end_ms - start_ms` |

### File Naming

- Padrão: `{user_id}/{seq zero-padded 4}.ogg` → `123456789/0042.ogg`

### Persistence (NOVO na migração)

- **Binário**: escrito **incrementalmente** pelo sink customizado durante o turno de fala (não bufferizado até o fim da sessão — SC-003).
- **Formato**: `.ogg` (Opus). Como o sink py-cord entrega **PCM decodificado**, o encode PCM→Opus é feito por utterance (ver research R2). Fallback: gravar e converter ao fechar o segmento.
- **Metadata**: uma linha em `speaking_log.jsonl` ao fechar o utterance.

---

## Entity: SpeakingLog

Log append-only para reconstrução cronológica entre participantes. Schema idêntico à 001 (JSON Lines).

| Property | Value |
|----------|-------|
| Formato | JSON Lines |
| Arquivo | `{session_dir}/speaking_log.jsonl` |
| Ordenação | Inserção ≈ cronológica; ordenar por `start_ms` para merge |

---

## Entity: SpikeResult (NOVO — gate de migração)

Resultado da validação de recepção sob DAVE. Não é artefato de produção; documentado em `contracts/spike-acceptance.md`.

| Field | Type | Description |
|-------|------|-------------|
| `pycord_source` | str | Versão/branch/fork de py-cord testada |
| `dave_active` | bool | DAVE estava ativo no canal de teste |
| `packets_received` | int | Pacotes de áudio recebidos |
| `duration_s` | number | Duração da captura de teste |
| `audio_playable` | bool | Arquivos reproduzíveis com áudio audível |
| `authorship_correct` | bool | Áudio atribuído ao usuário correto |
| `verdict` | enum | `PASS` \| `FAIL` |

### Gate Rule

- `verdict = FAIL` **bloqueia** a implementação completa (Phase B+).
- `verdict = PASS` libera o rewrite com a `pycord_source` confirmada.

---

## Entity: WebhookNotification

Payload POST único ao encerrar. Derivado da Session; schema idêntico à 001 (ver `contracts/n8n-webhook.schema.json`).

---

## Runtime State (in-memory only)

| State | Owner | Description |
|-------|-------|-------------|
| `active_session` | SessionManager | SessionData atual ou None |
| `session_dir` | SessionManager | Path absoluto da sessão |
| `started_monotonic` | SessionManager | `time.monotonic()` base p/ offsets |
| `voice_client` | SessionManager | `discord.VoiceClient` ativo |
| `utterance_counters` | Sink | dict user_id → último seq |
| `open_writers` | Sink | dict user_id → arquivo/encoder aberto |
| `empty_channel_task` | Bot | asyncio task de auto-end |

---

## Contract Compatibility Matrix

| Artefato | Schema | Muda na migração? |
|----------|--------|-------------------|
| `session.json` | `contracts/session-json.schema.json` | ❌ idêntico à 001 |
| `speaking_log.jsonl` | `contracts/speaking-log.schema.json` | ❌ idêntico à 001 |
| Webhook n8n | `contracts/n8n-webhook.schema.json` | ❌ idêntico à 001 |
| Comandos | `contracts/bot-commands.md` | ❌ mesmos comandos/respostas |
| Sink incremental | — | ✅ novo (implementação interna) |
| Spike gate | `contracts/spike-acceptance.md` | ✅ novo |
