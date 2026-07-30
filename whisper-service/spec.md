# Feature Specification: whisper-service — atualização (CPU threads + convivência)

**Feature Directory**: `whisper-service/`

**Created**: 2026-07-12  
**Updated**: 2026-07-30

**Status**: Draft (atualização sobre MVP 0.2.0)

**Input**: `docs/demanda-whisper-service.md` — formalização operacional do whisper-service, com ênfase em limite de threads CPU no servidor compartilhado.

## Context

O whisper-service MVP já existe (`POST /transcribe`, `GET /health`, modelo único em memória, bind `0.0.0.0:8008`, worker único). A demanda formaliza o contrato e adiciona um requisito operacional crítico: **limitar threads do CTranslate2** para que uma sessão de ~2.000 utterances não sature todos os núcleos e degrade Foundry, Bertroldo, n8n e demais serviços no mesmo host.

### Gap vs implementação atual

| Item da demanda | Status atual |
|-----------------|--------------|
| Contrato `/transcribe` e `/health` | Já implementado |
| Modelo único + workers 1 | Já implementado |
| Bind `0.0.0.0` | Já implementado |
| Config modelo/compute/host/porta | Já implementado |
| **`WHISPER_CPU_THREADS` (default 5)** | **Ausente** — WhisperModel sem `cpu_threads` |
| Aceite: sessão longa sem saturamento perceptível | **Não validado / não especificado** |

Esta atualização NÃO altera o contrato HTTP externo (request/response de `/transcribe` e campos mínimos de `/health`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transcrever utterances sob demanda (Priority: P1) — mantido

Como workflow n8n, quero enviar caminho de áudio e receber texto, sem recarregar o modelo a cada arquivo.

**Independent Test**: `POST /transcribe` com `.ogg` real → 200 com `text`, `language`, `duration_s`; caminho inexistente → 404.

*(Comportamento já entregue no MVP; regressão obrigatória nesta atualização.)*

---

### User Story 2 - Verificar disponibilidade (Priority: P1) — mantido

Como operador, quero `/health` confirmando modelo carregado.

**Independent Test**: Após startup, `/health` → `{status: "ok", model, compute_type}`.

*(Já entregue; regressão obrigatória.)*

---

### User Story 3 - Integrar com n8n em Docker (Priority: P1) — mantido

Como n8n em container, quero alcançar o serviço via `host.docker.internal:8008`.

**Independent Test**: curl de dentro do container → health + transcribe.

*(Já documentado; validação em produção permanece gate operacional.)*

---

### User Story 4 - Ajustar qualidade vs velocidade via env (Priority: P2) — estendido

Como operador, quero configurar modelo, compute type **e limite de threads CPU** via env, sem alterar código.

**Why this priority**: Em servidor compartilhado, threads ilimitadas são risco operacional maior do que escolha de modelo.

**Independent Test**: Definir `WHISPER_CPU_THREADS=5`, reiniciar, confirmar nos logs/config efetiva; alterar para outro valor válido e observar impacto em `htop` durante transcrição.

**Acceptance Scenarios**:

1. **Given** `WHISPER_CPU_THREADS` ausente, **When** o serviço inicia, **Then** usa default **5**.
2. **Given** `WHISPER_CPU_THREADS=3`, **When** o serviço reinicia e processa uma utterance, **Then** a carga CPU observada não usa todos os núcleos do host de forma sustentada.
3. **Given** valor inválido (não inteiro ou ≤ 0), **When** o serviço tenta iniciar, **Then** falha com mensagem explícita.

---

### User Story 5 - Convivência CPU em sessão completa (Priority: P1) 🎯 foco da atualização

Como operador do servidor compartilhado, quero que uma sessão completa de transcrição (~2.000 utterances) não deixe Foundry/Bertroldo/blog/n8n perceptivelmente lentos.

**Why this priority**: Motivação central da demanda — o host (Kron Mini / stack VTT) não é dedicado ao Whisper.

**Independent Test**: Rodar lote real ou simulado de utterances com `htop` aberto; demais serviços devem permanecer responsivos; CPU do whisper limitada ao orçamento de threads.

**Acceptance Scenarios**:

1. **Given** serviço com `WHISPER_CPU_THREADS=5` e worker único, **When** n8n processa sequência longa de `/transcribe`, **Then** núcleos remanescentes permanecem disponíveis para outros processos.
2. **Given** sessão piloto com volume da ordem de milhares de utterances, **When** operador observa o servidor, **Then** não há saturação total de CPU de forma contínua.
3. **Given** outros serviços (Foundry, Bertroldo) ativos, **When** a transcrição roda em paralelo, **Then** não há indisponibilidade perceptível atribuída ao whisper-service (validação manual do operador).

---

### Edge Cases

- `WHISPER_CPU_THREADS` maior que núcleos do host → aceito, mas documentado como anti-padrão (pode piorar latência e convivência).
- Valor `1` → serviço funciona, porém mais lento; ainda válido.
- Ausência da variável após deploy antigo → default 5 ao reiniciar (sem exigir mudança de `.env` se defaults bastarem).
- Demais edge cases do MVP (404, arquivo corrompido, loading 503) permanecem válidos.

## Requirements *(mandatory)*

### Functional Requirements

**Mantidos (regressão):**

- **FR-001**–**FR-006**, **FR-009**–**FR-014**: inalterados em intenção (API path-based, health, modelo único, CPU-only, Docker host, workers 1, venv/systemd isolados).

**Atualizados / novos:**

- **FR-007**: Tamanho do modelo, tipo de computação, host, porta **e número de threads CPU** MUST ser configuráveis via variáveis de ambiente sem alteração de código.
- **FR-008**: Defaults MUST ser: modelo `small`, compute `int8`, host `0.0.0.0`, porta `8008`, **`cpu_threads` = 5**.
- **FR-015**: O serviço MUST passar `cpu_threads` ao carregar o modelo faster-whisper / CTranslate2, usando o valor de `WHISPER_CPU_THREADS`.
- **FR-016**: `WHISPER_CPU_THREADS` MUST ser inteiro ≥ 1; valores inválidos MUST falhar na inicialização com erro explícito.
- **FR-017**: O contrato HTTP de `/transcribe` (request/response 200/404/500) MUST permanecer compatível com a demanda e com o workflow n8n existente.

### Key Entities

- **Requisição / Resposta de transcrição**: inalteradas (`audio_path`, `language` → `text`, `language`, `duration_s`).
- **Status de saúde**: `{status, model, compute_type}` (mínimo da demanda; campos extras opcionais não exigidos).
- **Configuração de runtime**: inclui `cpu_threads` (`WHISPER_CPU_THREADS`, default 5).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `/health` responde ok após startup com modelo carregado (regressão).
- **SC-002**: `/transcribe` com `.ogg` real retorna texto coerente em português (regressão).
- **SC-003**: `/transcribe` com caminho inexistente retorna 404 com mensagem clara (regressão).
- **SC-004**: Serviço acessível via `host.docker.internal` a partir de container Docker na mesma máquina (regressão / gate de produção).
- **SC-005**: Com default `WHISPER_CPU_THREADS=5`, uma sessão completa na ordem de ~2.000 utterances NÃO deixa a CPU saturada a ponto de outros serviços do servidor ficarem perceptivelmente lentos (validação com `htop` em teste real).
- **SC-006**: Após a atualização, o serviço inicia com `cpu_threads=5` sem exigir configuração manual quando a variável está ausente.

## Assumptions

- Stack e layout atuais (`whisper-service/whisper_service/`) permanecem a base.
- n8n continua chamando `/transcribe` sequencialmente.
- Default 5 threads é orçamento adequado ao host compartilhado; operador pode ajustar via env.
- “Perceptivelmente lentos” é julgamento do operador com `htop` + uso real de Foundry/Bertroldo durante o lote.
- Sem autenticação permanece restrição conhecida (firewall), não pendência.
- Prefixo de path (`WHISPER_ALLOWED_PATH_PREFIX`) permanece como proteção; fora do texto mínimo da demanda, mas já em produção.

## Out of Scope

- Upload HTTP de áudio.
- Fila / concorrência real / múltiplos workers.
- GPU.
- Diarização e tradução.
- Mudança de contrato de request/response do `/transcribe`.
- Autenticação por token.

## Dependencies

- faster-whisper / CTranslate2 (`cpu_threads` no construtor de `WhisperModel`).
- Cronista (artefatos `.ogg`) e n8n (consumidor).
- Host compartilhado com Foundry, Bertroldo, blog, n8n Docker.

## Open Questions (resolved by defaults)

| Tema | Decisão |
|------|---------|
| Default de threads | **5** (demanda) |
| Expor `cpu_threads` no `/health` | Não obrigatório nesta atualização; demanda não exige |
| Valor máximo de threads | Sem teto rígido; documentar anti-padrão > núcleos do host |
