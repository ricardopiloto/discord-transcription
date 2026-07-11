# Research: Migração para Python/Py-Cord

**Feature**: 002-python-pycord-migration  
**Date**: 2026-07-10

## R1 — Recepção de áudio sob DAVE (o risco central)

**Decision**: Adotar py-cord como stack alvo, mas **condicionar** a escolha a um spike empírico que confirme recepção de áudio sob DAVE no ambiente real, antes do rewrite completo.

**Rationale**: O PRD v2 afirma que py-cord lida corretamente com DAVE na recepção enquanto `@discordjs/voice` 0.19.x não. A pesquisa na documentação oficial da py-cord (v2.8.x) mostra um quadro mais matizado: `VoiceClient.start_recording`/`start_listening` ainda emitem `RuntimeWarning` de que "voice reception is currently broken due to Discord's DAVE protocol" e apontam para a issue #3139. A correção efetiva de decodificação DAVE está no PR #3202 (usa bindings `davey`, MLS), testado contra tráfego real (883 pacotes / 17.7s, zero crashes) mas possivelmente ainda não presente na versão estável instalável. Ou seja: py-cord é a aposta mais promissora, mas "funciona sob DAVE" depende de versão/fonte específica e **não pode ser assumido** — precisa ser verificado.

**Alternatives considered**:
- *Confiar no PRD e migrar direto sem spike* — rejeitada: risco de reproduzir o mesmo bloqueio da stack Node.
- *Permanecer em Node e esperar correção do `@discordjs/voice`* — rejeitada como padrão: sem evidência de correção; PRD v2 define Python como direção. Reavaliável apenas se o spike Node provar recepção funcional (fallback da spec).

**Open item para o spike**: determinar a combinação instalável de py-cord (release estável, branch com PR #3202 merґeado, ou fork/patch + `davey`) que recebe áudio sob DAVE.

---

## R2 — Sink customizado e formato de áudio (nuance importante)

**Decision**: Implementar sink customizado subclasse de `discord.sinks.Sink`, sobrescrevendo `write(self, data, user)` para escrever cada utterance em disco incrementalmente. Definir o formato de saída (Ogg/Opus vs WAV/PCM) **no spike**, conforme o que `data` entrega.

**Rationale**: O `Sink.write(data, user)` da py-cord recebe **PCM já decodificado** por usuário (não pacotes Opus crus). Isso contradiz parcialmente a nota do PRD v2 ("regravados em container Ogg sem re-encode") — para gerar `.ogg`/Opus a partir de PCM seria necessário **re-encode** (via `libopus`/ffmpeg). O `WaveSink` padrão bufferiza `io.BytesIO` por usuário até `stop_recording()` — inaceitável para 3–4h. O sink customizado deve: (a) abrir arquivo por utterance ao detectar fala, (b) escrever chunks conforme chegam, (c) fechar ao silêncio.

**Decisão de formato (a confirmar no spike)**:
- Preferência: manter extensão `.ogg` (contrato downstream) encodando PCM→Opus incrementalmente.
- Fallback aceitável: gravar PCM/WAV e converter para `.ogg` ao fechar cada utterance (ainda incremental por segmento, não por sessão).

**Alternatives considered**:
- *WaveSink padrão* — rejeitada: buffer integral em memória (viola SC-003).
- *Gravar WAV e nunca converter* — rejeitada: quebra contrato de arquivo `.ogg` (FR-004).

---

## R3 — Detecção de fala e delimitação de utterance

**Decision**: Delimitar utterances por silêncio (~1s configurável) monitorando presença/ausência de pacotes por usuário dentro do sink, em vez de depender de um `end behavior` como no `@discordjs/voice`.

**Rationale**: A py-cord não expõe o mesmo `EndBehaviorType.AfterSilence` do discord.js. O sink recebe frames por usuário; a ausência de frames por > `UTTERANCE_SILENCE_MS` sinaliza fim de turno. Um loop/timer assíncrono por usuário fecha o arquivo atual e prepara o próximo `seq`.

**Alternatives considered**:
- *`speaking` start/stop events* — considerado como sinal auxiliar; menos confiável para silêncios curtos. Pode compor a heurística.
- *VAD (voice activity detection) por energia* — rejeitada no MVP: complexidade desnecessária; ausência de pacotes já basta.

---

## R4 — Identificador de sessão e estrutura em disco

**Decision**: Preservar `session_id` `YYYYMMDD-HHmmss` e a árvore `{session_id}/{user_id}/NNNN.ogg` + `session.json` + `speaking_log.jsonl`, idênticos à implementação 001.

**Rationale**: Contrato downstream estável (FR-004, FR-008/009). Reaproveita schemas já validados em `specs/001-voice-capture-bot/contracts/`.

**Alternatives considered**:
- *Mudar layout para aproveitar a migração* — rejeitada: quebraria n8n sem ganho.

---

## R5 — Timestamps relativos

**Decision**: `start_ms`/`end_ms`/`duration_ms` relativos a `session.started_at`, em milissegundos, calculados com relógio monotônico do processo.

**Rationale**: Igual à 001; permite ao n8n intercalar falas de jogadores em ordem cronológica. `time.monotonic()` evita saltos de relógio durante a sessão.

**Alternatives considered**:
- *Timestamps absolutos por arquivo* — rejeitada: contrato exige offsets relativos.

---

## R6 — Webhook n8n com retry

**Decision**: POST assíncrono (`aiohttp`) com 3 tentativas e backoff exponencial (1s, 2s, 4s); falha persistente grava `webhook_failed: true` em `session.json`.

**Rationale**: Reproduz FR-011/FR-015 e o comportamento já validado na 001. Async evita bloquear o loop do bot no encerramento.

**Alternatives considered**:
- *`requests` síncrono* — rejeitada: bloquearia o event loop.
- *Fila persistente* — rejeitada: over-engineering para 1 sessão/semana.

---

## R7 — Isolamento de ambiente (venv) e coexistência

**Decision**: venv Python dedicado em `/opt/apps/cronista/`, token de bot próprio, `self_deaf=False` (necessário para receber) e `self_mute=True`.

**Rationale**: `py-cord` e `discord.py` (Bertroldo) importam ambos como `discord` e não coexistem no mesmo venv (restrição explícita do PRD v2). Robigode usa conexão/token próprios — coexistência no canal é suportada pelo Discord sem coordenação.

**Alternatives considered**:
- *Ambiente compartilhado com Bertroldo* — rejeitada: conflito de namespace garante quebra.
- *Container Docker* — rejeitada: stack do Kron padroniza systemd + venv.

---

## R8 — Estratégia de testes

**Decision**: `pytest` para funções puras (session_id, paths, retry de webhook com `aiohttp` mockado). Captura de voz validada por spike (US1) e quickstart manual. Sem E2E de voz em CI.

**Rationale**: Áudio ao vivo sob DAVE não é mockável de forma confiável; ROI de E2E automatizado é baixo para single-tenant. Espelha R7 da 001.

**Alternatives considered**:
- *Mock completo da py-cord* — rejeitada: não exercita o caminho DAVE, que é o risco real.

---

## R9 — Deploy e cutover

**Decision**: systemd `ExecStart=/opt/apps/cronista/.venv/bin/python -m cronista`, `Restart=on-failure`. Cutover em janela controlada com rollback documentado; stack Node removida ao final (FR-016).

**Rationale**: Alinha ao padrão Bertroldo (venv + systemd + `adminvtt`). Rollback = reativar unit Node anterior enquanto o serviço novo não passa na sessão piloto.

**Alternatives considered**:
- *Trocar in-place sem janela* — rejeitada: risco de indisponibilidade em noite de sessão.
- *Manter Node e Python em paralelo indefinidamente* — rejeitada por FR-016 (ambiguidade operacional, mesmo token).

---

## Summary

Todas as incertezas do Technical Context estão resolvidas em nível de plano. O único item que permanece deliberadamente **empírico** é a versão/fonte exata de py-cord que recebe sob DAVE — resolvido pelo spike da Phase A, que é uma gate objetiva (não um NEEDS CLARIFICATION de escopo).
