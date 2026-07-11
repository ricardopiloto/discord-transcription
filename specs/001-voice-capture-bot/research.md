# Research: Bot de Captura de Voz (Cronista)

**Feature**: 001-voice-capture-bot  
**Date**: 2026-07-10

## R1 — Captura de áudio por usuário no Discord

**Decision**: Usar `connection.receiver.subscribe(userId, { end: { behavior: EndBehaviorType.AfterSilence, duration: UTTERANCE_SILENCE_MS } })` do `@discordjs/voice`.

**Rationale**: O Discord entrega streams Opus isolados por `userId`. O receiver nativo do `@discordjs/voice` suporta delimitação por silêncio, alinhado ao FR-005 da spec e ao PRD (1s default). Não requer diarização por IA.

**Alternatives considered**:
- *Gravação monolítica do canal mixado* — rejeitada: perde atribuição por jogador (SC-002).
- *Diarização Whisper/pyannote* — rejeitada: CPU intensiva, fora de escopo, inferior ao stream nativo.

---

## R2 — Formato de arquivo: Opus em container Ogg sem re-encode

**Decision**: Pipe dos pacotes Opus recebidos do Discord diretamente para `OggLogicalBitstream` do `prism-media`, gravando `{user_id}/NNNN.ogg`.

**Rationale**: Preserva qualidade original, minimiza CPU (constraint do Kron Mini K1). Pacotes Opus do Discord já estão codificados — re-encode para PCM/WAV seria custoso e desnecessário para pipeline Whisper downstream.

**Alternatives considered**:
- *WAV/PCM via decoder* — rejeitada: CPU + disco maiores.
- *MP3* — rejeitada: re-encode lossy desnecessário; Whisper aceita Ogg Opus.

---

## R3 — Identificador de sessão

**Decision**: Formato `YYYYMMDD-HHmmss` gerado no relógio local do servidor no momento do `start`.

**Rationale**: Legível, ordenável, único na prática para cadência semanal/quinzenal. Já implementado em `storage.formatSessionId()`.

**Alternatives considered**:
- *UUID* — rejeitada: menos legível para GM e paths manuais.
- *Snowflake Discord* — rejeitada: não reflete horário de início.

---

## R4 — Encerramento automático por canal vazio

**Decision**: Escutar `VoiceStateUpdate`; quando nenhum membro humano permanecer no canal alvo por `AUTO_END_EMPTY_CHANNEL_MS` (default 300000 = 5 min), disparar mesmo fluxo de `encerrar`.

**Rationale**: Atende FR-012 e caso de uso principal (GM encerra canal ao fim da noite). Timer resetado a cada entrada de membro humano no canal.

**Alternatives considered**:
- *Apenas comando manual* — rejeitada: risco de sessões órfãs se GM esquecer `!cronista encerrar`.
- *Encerrar quando GM sai* — rejeitada: GM pode reconectar; canal vazio é sinal mais confiável de fim.

**Implementation note**: Excluir bots (incluindo Cronista e Robigode) da contagem de "membros humanos".

---

## R5 — Notificação n8n com retry

**Decision**: `fetch` POST com 3 tentativas, backoff exponencial (1s, 2s, 4s). Falha persistente → `webhook_failed: true` em `session.json`. Já esboçado em `n8n-notifier.ts`.

**Rationale**: Atende FR-015; n8n pode estar temporariamente indisponível. Marcador permite reprocessamento manual sem perder gravações.

**Alternatives considered**:
- *Fila persistente (Redis/BullMQ)* — rejeitada: over-engineering para 1 sessão/semana.
- *Retry infinito* — rejeitada: bloquearia encerramento limpo.

---

## R6 — Coexistência com Robigode

**Decision**: Conexão de voz independente com token de bot próprio; `selfDeaf: true`, `selfMute: true` no Cronista.

**Rationale**: Discord permite múltiplas `VoiceConnection` no mesmo canal. Cronista só recebe (receiver), Robigode só transmite — sem conflito de recursos.

**Alternatives considered**:
- *Bot único com dual-purpose* — rejeitada: acoplamento indesejado, PRD exige processo separado.

---

## R7 — Estratégia de testes

**Decision**: Validação primária via quickstart manual (sessão piloto Discord). Testes unitários para funções puras (`formatSessionId`, path helpers, webhook retry logic com mock fetch). Sem testes E2E automatizados de voz no CI (requer Discord live).

**Rationale**: Integração com Discord Voice não é mockável de forma confiável sem fixtures Opus complexas. ROI de E2E automatizado baixo para MVP single-tenant.

**Alternatives considered**:
- *discord.js mock completo* — rejeitada: não valida streams Opus reais.
- *Testcontainers + bot de teste* — rejeitada: complexidade desproporcional.

---

## R8 — Deploy e runtime

**Decision**: systemd unit (`deploy/cronista.service`), usuário `adminvtt`, working dir `/opt/apps/cronista`, recordings em `/opt/apps/cronista/recordings`.

**Rationale**: Alinhado ao padrão Bertroldo e PRD §4.1. Restart on failure cobre crashes (recuperação de sessão órfã continua manual/out-of-scope).

**Alternatives considered**:
- *Docker* — rejeitada: stack existente usa systemd nativo no Kron.
- *PM2* — rejeitada: systemd já presente e padronizado.

---

## R9 — Resolução de participante (display name)

**Decision**: Ao detectar fala, resolver `GuildMember` via `guild.members.fetch(userId)` com fallback para `user.username`. Registrar em `session.participants` na primeira fala.

**Rationale**: Atende FR-019; display name pode mudar mid-session — snapshot no momento da primeira fala é suficiente para transcrição.

**Alternatives considered**:
- *Atualizar display name a cada utterance* — rejeitada: complexidade sem valor para pipeline downstream.

---

## Summary

Todas as incertezas técnicas do Technical Context foram resolvidas. Nenhum NEEDS CLARIFICATION pendente para Phase 1.
