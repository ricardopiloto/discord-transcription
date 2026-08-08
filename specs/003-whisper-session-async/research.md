# Research: Transcrição assíncrona por sessão (whisper-service v2)

**Feature**: `003-whisper-session-async`  
**Date**: 2026-08-08  
**Spec**: [spec.md](./spec.md)

## R1 — Processamento em background sem bloquear FastAPI

**Decision**: Executar o lote em `concurrent.futures.ThreadPoolExecutor` com **max_workers=1** (ou thread dedicada equivalente). A rota `POST /transcribe-session` valida, registra estado `in_progress` e faz `submit`/`start`; retorna **202** imediatamente.

**Rationale**: `faster-whisper` / CTranslate2 é síncrono e CPU-bound. Rodar no event loop async bloquearia `/health` e `/status`. Um worker único serializa utterances da mesma forma que o loop n8n serializava HTTP, preservando previsibilidade de CPU (`WHISPER_CPU_THREADS`).

**Alternatives considered**:
- `asyncio.to_thread` por utterance — válido, mas um executor de 1 worker deixa o ciclo de vida do lote mais explícito e evita pile-up de threads se duas sessões distintas coexistirem (cada submit espera a fila).
- Processo separado / fila Redis — viola YAGNI e constitution (sem fila persistente nesta fase).
- `BackgroundTasks` do FastAPI — ainda corre no mesmo worker async se a task for sync longa; inadequado sem offload.

## R2 — Lock e estado por `session_id`

**Decision**: Dicionário em memória thread-safe (`threading.Lock` protegendo mutações) mapeando `session_id` → `SessionState`. Se status atual for `in_progress` → HTTP **409**. Se `done`/`failed` → **substituir** e reiniciar (reprocessamento permitido pela spec).

**Rationale**: Demanda e incidente de produção exigem trava só para a mesma sessão em andamento. Persistência (SQLite/arquivo) está out of scope.

**Alternatives considered**:
- File lock por sessão — útil pós-crash; adiado.
- 409 também após `done` — rejeitado; reprocessar é útil operacionalmente.

## R3 — Cliente HTTP do callback + backoff

**Decision**: Usar **stdlib `urllib.request`** para `POST` JSON ao `callback_url`. **3 tentativas** com backoff **2s, 5s, 10s** entre falhas. Sucesso = HTTP 2xx. Esgotadas as tentativas → log ERROR; status da sessão permanece `done`/`failed` consultável.

**Rationale**: Evita nova dependência de runtime (`httpx` hoje só em `dev`). Timeouts curtos (ex. 10s connect+read) bastam para webhook local n8n. Intervalos resolvem o deferimento da spec clarificada.

**Alternatives considered**:
- Promover `httpx` a dep runtime — mais ergonomia; desnecessário para 3 POSTs.
- Backoff exponencial 1/2/4 — equivalente; 2/5/10 dá mais margem a restart do n8n.

## R4 — Formatação de `transcricao.txt`

**Decision**:
- Ordenar entries do `speaking_log.jsonl` por `start_ms` ascendente.
- Timestamp: `start_ms` → `HH:MM:SS` (horas podem exceder 24 se sessão longa; usar divisão inteira total de segundos).
- Linha: `[HH:MM:SS] {display_name}: {text}`  
- Texto vazio / só whitespace → `[HH:MM:SS] {display_name}: (silêncio)`  
- `display_name` ausente → usar `user_id`.
- `utterances_com_texto`: conta linhas cujo texto **não** é o marcador de silêncio e não está vazio (após trim); áudio ausente não gera linha e não conta.

**Rationale**: Clarifications Session 2026-08-08 + contrato legado n8n.

**Alternatives considered**: Omitir silêncio / linha vazia — rejeitado na clarify.

## R5 — Validação de paths da sessão

**Decision**: Reusar a lógica de `validate_audio_path` (prefixo + resolve + bloquear `..`) para **diretórios/arquivos** `recordings_path` e `speaking_log_path`. Rejeitar com **403** se fora do prefixo (mesmo código da v1). Existência ilegível do log/dir após aceite → falha de lote (`failed`), não 202.

**Rationale**: Spec FR-013; alinhado à proteção já em produção. Validar **antes** do 202.

**Alternatives considered**: Sem prefixo no fluxo sessão — rejeitado na clarify.

## R6 — Áudio ausente vs erro fatal

**Decision**:
- Arquivo `.ogg` ausente/ilegível: log warning, incrementar `processed`, **sem** linha no transcript; continuar.
- Exceção não recuperável (modelo, I/O ao escrever arquivo final, log JSONL ilegível no início): status `failed`, **não** escrever `transcricao.txt`, callback `failed` com `error` + `processed` parcial.

**Rationale**: Spec FR-014 + assumptions.

## R7 — Idioma e resolução de arquivo

**Decision**: Lote sempre `language="pt"`. Path de áudio = `Path(recordings_path) / entry["file"]` (campo relativo `{user_id}/NNNN.ogg` do speaking_log).

**Rationale**: Clarify + contrato Cronista existente.

## R8 — Coexistência com `/transcribe` v1

**Decision**: Manter rotas sync atuais. Lotes de sessão e `/transcribe` pontual compartilham o mesmo modelo em memória; se ambos rodarem, disputam CPU/threads CTranslate2 — aceitável. Opcionalmente serializar acesso ao modelo com o mesmo lock do worker (recomendado na implementação para evitar reentrância no CTranslate2).

**Rationale**: YAGNI de fila global; risco baixo (debug pontual vs pipeline).

**Alternatives considered**: Bloquear `/transcribe` durante sessão — desnecessário para MVP v2.

## R9 — Versionamento

**Decision**: Bump whisper-service para **0.3.0** (feature endpoints); documentar breaking change do workflow n8n (não do contrato v1).

**Rationale**: Semver: nova capability + mudança operacional do pipeline.
