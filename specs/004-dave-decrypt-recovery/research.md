# Research: Recuperação automática de falhas de decriptação DAVE

**Feature**: `004-dave-decrypt-recovery`  
**Date**: 2026-08-08  
**Spec**: [spec.md](./spec.md)

## R1 — Como observar falhas de decriptação (CryptoError)

**Decision**: Instrumentar a camada de recepção da py-cord **antes** do sink, porque `IncrementalUtteranceSink.write()` só recebe PCM já decriptado/decodificado. Estratégia em duas partes:

1. **Falha**: gancho no caminho de decrypt/receive (wrapper/monkey-patch estável no ponto onde a lib registra `CryptoError` / “Decryption failed”, ou callback/hook documentado se existir na versão em uso) que chama `DaveRecovery.on_decrypt_failure()`.
2. **Sucesso**: após PCM não-silencioso aceito em `IncrementalUtteranceSink.write()`, chamar `DaveRecovery.on_decode_success()`.

Validar no implement o ponto exato na versão py-cord pinada em `app/requirements.txt` (spike de 15–30 min: forçar disconnect e confirmar que o gancho vê falhas).

**Rationale**: O incidente 07/08 foi silencioso exatamente porque o erro nunca chega ao sink. Contar só “ausência de PCM” é ambíguo (silêncio real da mesa).

**Alternatives considered**:
- Só logging.Handler em `discord`/`davey` — frágil a mudança de mensagem; aceitável como fallback se patch quebrar.
- Inferir só por starvation de PCM — alto falso positivo em mesas quietas.
- Patch de `recording_finished` Opus — já existe soft-restart; não cobre DAVE key rot.

## R2 — Reconexão completa vs soft-restart

**Decision**: Novo `SessionManager.reconnect_voice_full()`:

1. Marcar recovery in-progress (bloquear segundo ciclo / cooldown).
2. Flush utterances abertas no sink (`flush_all` / stop timers) **sem** encerrar `SessionData`.
3. `stop_recording` se ativo.
4. `voice_client.disconnect(force=True)`.
5. `channel.connect()` + `change_voice_state(self_mute=True)` (mesmo padrão de `handle_entrar`).
6. `_wait_dave_warmup` + `start_recording` com sink re-inicializado no mesmo `session_dir`.
7. Aguardar 1º `on_decode_success` dentro de `CRONISTA_RECONNECT_VALIDATE_TIMEOUT_S` (default 30).

Manter o soft-restart de Opus/`corrupted stream` em `_make_recording_finished_callback` **apenas** para esse caso — não reutilizar para DAVE.

**Rationale**: Spec/clarify e incidente: reconnect leve da lib não renegocia chaves.

**Alternatives considered**:
- Só `start_recording` de novo — rejeitado (já falhou em prod).
- Encerrar sessão e pedir `!cronista entrar` — rejeitado (perda de UX; clarify escolheu sessão aberta).

## R3 — Contador, janela e cooldown

**Decision**: Estrutura em memória no processo:

- Lista/deque de timestamps de falha consecutivas; reset total em sucesso.
- Disparo quando `len(falhas) >= threshold` e `(última - primeira) <= window_s`.
- Falhas fora da janela: descartar as antigas (janela deslizante) antes de contar.
- Após sucesso validado: `cooldown_until = now + cooldown_s`; durante cooldown, falhas só logam.
- Durante recovery: ignorar novos disparos (já em curso).

Defaults: threshold 5, window 10s, cooldown 60s, max attempts 5, backoff base 3s × attempt.

**Rationale**: Spec FR-002/003/015 + clarifications.

## R4 — Webhook mid-session

**Decision**: Nova env `CRONISTA_ALERT_WEBHOOK_URL` (opcional). Função `notify_mid_session_alert(config, payload)` em `webhook.py` com 3 retries (mesmo padrão aiohttp do fim de sessão). **Não** reutilizar `N8N_WEBHOOK_URL` (pipeline de transcrição ≠ alertas operacionais).

Payload tipado: `event` ∈ `dave_decrypt_detected` | `dave_decrypt_recovered` | `dave_decrypt_failed` + campos de contexto + `message` human-readable (para bridge Telegram).

**Rationale**: Clarify Q2; evita misturar alertas com corte n8n.

**Alternatives considered**: Bot API Telegram no Cronista — out of scope; Discord text channel — rejeitado na clarify.

## R5 — Critério de sucesso pós-connect

**Decision**: Tentativa só vira sucesso após `on_decode_success` dentro do timeout; senão conta falha e aplica backoff. Canal silencioso = risco conhecido (edge case na spec); operador pode falar ou aumentar timeout.

**Rationale**: Clarify Q5.

## R6 — Gaps e contrato de fim de sessão

**Decision**:

- `GapsLog` append-only → `{session_dir}/recording_gaps.jsonl`.
- Campos: UTC + ms relativos + reason + attempts + success (+ session_id).
- Webhook/aviso de fim: incluir `gap_count` e `recording_gaps_path` de forma **aditiva** (consumidores antigos ignoram campos extras).
- Contagem também no reply Discord de `!cronista encerrar` / status quando N>0.

**Rationale**: Constitution I (additive); US3/US5.

## R7 — Esgotamento de tentativas

**Decision**: Alerta `dave_decrypt_failed`, escrever gap `success=false`, `disconnect` voz, **manter** `SessionManager.session` ativo sem recording. Operador: `!cronista encerrar` ou fluxo futuro de reentrada (se `entrar` com sessão aberta for bloqueado hoje, documentar: encerrar e reentrar, ou estender `entrar` para retomar — preferir documentar no quickstart o caminho atual sem expandir escopo além do necessário; se `entrar` rejeita sessão ativa, operador encerra e inicia nova).

Verificar comportamento atual de `handle_entrar` com sessão ativa no implement; se bloquear, quickstart orienta `encerrar` + `entrar`.

**Rationale**: Clarify Q1 option A.
