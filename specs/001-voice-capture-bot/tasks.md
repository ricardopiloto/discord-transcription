---
description: "Task list for Bot de Captura de Voz (Cronista)"
---

# Tasks: Bot de Captura de Voz para Sessões de RPG

**Input**: Design documents from `/specs/001-voice-capture-bot/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Testes automatizados são OPCIONAIS nesta feature. Validação primária é manual via `quickstart.md` (sessão piloto Discord). Tarefas de teste unitário aparecem apenas na fase Polish, cobrindo funções puras (research R7).

**Organization**: Tarefas agrupadas por user story. O scaffolding inicial já existe em `src/`; muitas tarefas completam stubs em vez de criar arquivos do zero.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências pendentes)
- **[Story]**: User story (US1–US5)
- Caminhos de arquivo são absolutos ao repo root: `src/...`

## Path Conventions

Single project Node.js/TypeScript: código em `src/`, testes futuros em `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Estrutura base já existe; validar e preparar ambiente.

- [x] T001 Verificar dependências instaladas e build limpo: rodar `npm install` e `npm run typecheck` a partir do repo root; corrigir qualquer erro pré-existente
- [x] T002 [P] Confirmar variáveis de ambiente em `.env.example` cobrem todas de `contracts/bot-commands.md` (DISCORD_TOKEN, RECORDINGS_DIR, UTTERANCE_SILENCE_MS, AUTO_END_EMPTY_CHANNEL_MS, N8N_WEBHOOK_URL)
- [x] T003 [P] Criar diretório `tests/unit/` com `.gitkeep` para tarefas de teste da fase Polish

**Checkpoint**: Projeto compila, env documentado.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura central que TODAS as user stories dependem — storage, tipos e config.

**⚠️ CRITICAL**: Nenhuma user story pode ser concluída até esta fase estar completa.

- [x] T004 [P] Validar tipos em `src/types/session.ts` contra `contracts/session-json.schema.json`, `contracts/speaking-log.schema.json` e `contracts/n8n-webhook.schema.json` (campos e opcionalidade coincidem)
- [x] T005 [P] Revisar helpers de storage em `src/recording/storage.ts` (formatSessionId, ensureSessionDir, ensureUserDir, writeSessionJson, formatUtteranceFilename) e garantir conformidade de path/regex com `data-model.md`
- [x] T006 [P] Revisar `src/config/index.ts` para expor todos os parâmetros configuráveis (silêncio, auto-end, recordings dir, webhook url) com defaults do contrato
- [x] T007 Validar `SpeakingLog.append` em `src/recording/speaking-log.ts` produz JSONL conforme schema (uma linha por utterance, campos ordenados)

**Checkpoint**: Fundação pronta — user stories podem começar.

---

## Phase 3: User Story 1 - Iniciar captura da sessão (Priority: P1) 🎯 MVP

**Goal**: GM aciona `!cronista entrar`; bot entra no canal de voz, cria sessão com `session_id` e persiste `session.json`.

**Independent Test**: Entrar em canal de voz, enviar `!cronista entrar`, verificar resposta com session_id e criação de `recordings/{session_id}/session.json` (quickstart Scenario 1).

### Implementation for User Story 1

- [x] T008 [US1] Completar `SessionManager.start()` em `src/recording/session-manager.ts`: gerar session_id, criar diretório, inicializar SpeakingLog, gravar session.json inicial e guardar VoiceConnection
- [x] T009 [US1] Implementar guard de sessão única em `SessionManager.start()` (lançar/rejeitar se `isRecording`) — cobre FR-002/FR-018
- [x] T010 [US1] Finalizar comando `src/bot/commands/entrar.ts`: validar autor em canal de voz, `joinVoiceChannel` com `selfDeaf`/`selfMute`, chamar `sessionManager.start`, responder com session_id e nome do canal
- [x] T011 [US1] Garantir wiring de intents e roteamento em `src/bot/client.ts` e `src/bot/commands/index.ts` para o comando `entrar` (GuildVoiceStates, MessageContent)

**Checkpoint**: US1 funcional — sessão inicia e persiste metadados independentemente.

---

## Phase 4: User Story 2 - Capturar áudio por jogador e segmentar por fala (Priority: P1)

**Goal**: Cada participante tem falas gravadas isoladamente em `.ogg` por utterance, com timestamps relativos e log JSONL.

**Independent Test**: Com sessão ativa e 2+ falantes alternando, verificar arquivos `{user_id}/NNNN.ogg`, linhas em `speaking_log.jsonl` e `utterance_count` em session.json (quickstart Scenario 2).

### Implementation for User Story 2

- [x] T012 [US2] Implementar resolução de participante em `src/recording/audio-recorder.ts`: `resolveUser` via `guild.members.fetch(userId)` com fallback para username (FR-019, research R9)
- [x] T013 [US2] Implementar captura de utterance em `src/recording/audio-recorder.ts`: `connection.receiver.subscribe(userId, { end: { behavior: EndBehaviorType.AfterSilence, duration: config.recording.utteranceSilenceMs } })` (FR-004, FR-005, research R1)
- [x] T014 [US2] Empacotar Opus em Ogg sem re-encode em `src/recording/audio-recorder.ts`: pipe do stream Opus → `prism-media` `OggLogicalBitstream` → arquivo `{user_id}/NNNN.ogg` (research R2)
- [x] T015 [US2] Numerar utterances sequencialmente por usuário via `utteranceCounters` e `formatUtteranceFilename` em `src/recording/audio-recorder.ts` (FR-006)
- [x] T016 [US2] Calcular `start_ms`/`end_ms`/`duration_ms` relativos a `sessionStartedAtMs` e escrever `SpeakingLogEntry` no fechamento do stream em `src/recording/audio-recorder.ts` (FR-007, FR-010)
- [x] T017 [US2] Registrar participante e incrementar `utterance_count` via `SessionManager.registerParticipant` + novo método de incremento em `src/recording/session-manager.ts`, persistindo session.json (FR-009, FR-019)
- [x] T018 [US2] Instanciar e anexar `AudioRecorder` ao fluxo de `SessionManager.start()` em `src/recording/session-manager.ts`, passando sessionDir, sessionStartedAtMs, speakingLog e callback onParticipant

**Checkpoint**: US1 + US2 funcionam — áudio segmentado por jogador é persistido.

---

## Phase 5: User Story 3 - Encerrar sessão e acionar pipeline (Priority: P1)

**Goal**: Encerramento manual/automático finaliza gravação, grava `ended_at`, dispara webhook n8n com retry e marca falha se necessário.

**Independent Test**: Encerrar sessão (manual ou canal vazio) e verificar `ended_at`, saída do canal e POST ao webhook conforme schema (quickstart Scenarios 4, 5, 8).

### Implementation for User Story 3

- [x] T019 [US3] Completar `SessionManager.end()` em `src/recording/session-manager.ts`: setar `ended_at`, finalizar streams de áudio ativos, persistir session.json e limpar estado
- [x] T020 [US3] Finalizar comando `src/bot/commands/encerrar.ts`: chamar `sessionManager.end`, destruir VoiceConnection, disparar webhook e responder conforme casos de `contracts/bot-commands.md`
- [x] T021 [US3] Validar payload do webhook em `src/webhook/n8n-notifier.ts` contra `contracts/n8n-webhook.schema.json` (paths absolutos, participants, timestamps) — FR-013
- [x] T022 [US3] Confirmar lógica de retry com backoff (3 tentativas) e marcação `webhook_failed` em session.json em `src/webhook/n8n-notifier.ts` + persistência no `encerrar.ts` (FR-015)
- [x] T023 [US3] Implementar encerramento automático por canal vazio em `src/bot/client.ts`: no evento `VoiceStateUpdate`, contar membros humanos (excluir bots) e agendar/cancelar timer `AUTO_END_EMPTY_CHANNEL_MS` que chama o mesmo fluxo de `encerrar` (FR-012, research R4)

**Checkpoint**: US1–US3 (todas P1) completas — ciclo de captura end-to-end funcional. **MVP entregável.**

---

## Phase 6: User Story 4 - Consultar status durante a sessão (Priority: P2)

**Goal**: `!cronista status` retorna estado, session_id, duração e nº de participantes.

**Independent Test**: Com sessão ativa, `!cronista status` mostra duração > 0 e contagem de participantes; sem sessão, informa ausência (quickstart Scenario 3).

### Implementation for User Story 4

- [x] T024 [US4] Finalizar comando `src/bot/commands/status.ts`: usar `sessionManager.activeSession` e `elapsedMs()`, formatar duração (Xh Ym Zs) e contagem de participantes (FR-016)
- [x] T025 [US4] Confirmar roteamento de `status` e `help` em `src/bot/commands/index.ts`

**Checkpoint**: US4 funcional — observabilidade operacional durante sessão.

---

## Phase 7: User Story 5 - Coexistir com bot de música (Priority: P2)

**Goal**: Cronista opera no mesmo canal que o Robigode sem interferência.

**Independent Test**: Ambos bots no canal, música tocando, falas capturadas normalmente (quickstart Scenario 6).

### Implementation for User Story 5

- [x] T026 [US5] Garantir que `AudioRecorder` ignora o próprio bot e outros bots ao registrar participantes/streams em `src/recording/audio-recorder.ts` (não gravar áudio de bots) — FR-017
- [x] T027 [US5] Validar em `src/bot/commands/entrar.ts` que a `VoiceConnection` do Cronista é independente e não desconecta conexões existentes de outros bots no canal

**Checkpoint**: US5 verificada — coexistência com Robigode garantida.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Robustez, testes de funções puras e validação final.

- [x] T028 [P] Adicionar logs estruturados mínimos (início/fim de sessão, utterance count, falha de webhook) em `src/bot/client.ts` e `src/recording/session-manager.ts`
- [x] T029 [P] Teste unitário de `formatSessionId` e `formatUtteranceFilename` em `tests/unit/storage.test.ts` (node:test) — validar regex `^\d{8}-\d{6}$` e padding 4 dígitos
- [x] T030 [P] Teste unitário da lógica de retry/backoff do webhook com `fetch` mockado em `tests/unit/n8n-notifier.test.ts` (research R7)
- [x] T031 Tratar erros de I/O de disco (falha ao escrever .ogg/JSONL) sem derrubar a sessão em `src/recording/audio-recorder.ts` e `src/recording/session-manager.ts`
- [x] T032 [P] Atualizar `README.md` marcando itens implementados (gravação, auto-end) na seção "Status do projeto"
- [ ] T033 Executar validação completa do `quickstart.md` (Scenarios 1–5, 7) e registrar resultados na checklist — **pendente: requer sessão Discord ao vivo** (checklist em `checklists/implementation-validation.md`)
- [ ] T034 Smoke test de estabilidade ≥30min monitorando RSS (quickstart Scenario 9, SC-004) — **pendente: validação manual**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: Depende de Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3–7)**: Dependem de Foundational
  - US1 (P1) → base para as demais (SessionManager.start)
  - US2 (P1) depende de US1 (recorder anexado no start)
  - US3 (P1) depende de US1 (encerra o que US1 inicia); integra US2 para flush de streams
  - US4 (P2) depende de US1 (lê estado da sessão)
  - US5 (P2) depende de US2 (filtragem de bots no recorder)
- **Polish (Phase 8)**: Depende das stories desejadas concluídas

### User Story Dependencies

- **US1 (P1)**: Após Foundational — sem dependência de outras stories
- **US2 (P1)**: Após US1 (recorder é anexado em `start`)
- **US3 (P1)**: Após US1; usa US2 para finalizar streams
- **US4 (P2)**: Após US1 (consulta estado)
- **US5 (P2)**: Após US2 (comportamento do recorder)

### Within Each User Story

- Domínio (session-manager/audio-recorder) antes de comandos (bot/commands)
- Core antes de integração/wiring

### Parallel Opportunities

- Setup: T002, T003 em paralelo
- Foundational: T004, T005, T006 em paralelo (arquivos diferentes)
- US2: T012 e (T013→T014→T015→T016) parcialmente sequenciais por editarem o mesmo arquivo `audio-recorder.ts`; T017 no session-manager pode andar em paralelo a T012
- Polish: T028, T029, T030, T032 em paralelo

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Podem rodar juntas (arquivos distintos):
Task: "T004 Validar tipos em src/types/session.ts contra contracts/"
Task: "T005 Revisar helpers em src/recording/storage.ts"
Task: "T006 Revisar src/config/index.ts"
```

---

## Implementation Strategy

### MVP First (User Stories P1)

1. Phase 1: Setup
2. Phase 2: Foundational (CRÍTICO)
3. Phase 3: US1 (iniciar captura)
4. Phase 4: US2 (gravação por jogador) — coração do produto
5. Phase 5: US3 (encerrar + webhook)
6. **STOP e VALIDATE**: quickstart Scenarios 1–5, 7 → MVP entregável

### Incremental Delivery

1. Setup + Foundational → base pronta
2. US1 → US2 → US3 (P1) → MVP funcional, validar e demo
3. US4 (status) → melhora operação
4. US5 (coexistência) → validação de produção
5. Polish → logs, testes, estabilidade

---

## Notes

- Scaffolding em `src/` já existe: a maioria das tarefas completa stubs (ver comentários `// TODO` no código atual)
- [P] = arquivos diferentes, sem dependências pendentes
- Áudio ao vivo do Discord não é testável em CI — validação via quickstart manual
- Commit após cada tarefa ou grupo lógico
- Bloco de gravação deve priorizar I/O leve (constraint Kron Mini K1)
