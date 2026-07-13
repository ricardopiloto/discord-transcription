# Feature Specification: whisper-service (microserviço de transcrição)

**Feature Directory**: `whisper-service/`

**Created**: 2026-07-12

**Status**: Draft

**Input**: PRD `docs/PRD-whisper-service.md` — microserviço HTTP local que expõe transcrição de utterances para o workflow n8n do Cronista.

## Context

O pipeline "Cronista - Transcrição da Sessão" (n8n) precisa transcrever dezenas de arquivos de áudio curtos por sessão de RPG (3–4 horas). Invocar o motor de transcrição como processo isolado a cada arquivo recarregaria o modelo repetidamente, tornando o pipeline lento e inviável em CPU-only.

Este serviço complementa o Cronista (captura de voz): o Cronista grava utterances em disco e notifica o n8n; o whisper-service recebe caminhos de arquivo já existentes no host e devolve texto transcrito. Vive no mesmo repositório, em pasta separada, com deploy e venv próprios — mesmo padrão operacional do Cronista e do Bertroldo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transcrever utterances sob demanda (Priority: P1)

Como workflow n8n de transcrição, quero enviar o caminho de um arquivo de áudio já gravado e receber o texto transcrito, para montar o transcript final da sessão sem recarregar o modelo a cada arquivo.

**Why this priority**: É o valor central do serviço — sem transcrição confiável por arquivo, o pipeline downstream não funciona.

**Independent Test**: Enviar requisição com caminho válido de um `.ogg` real da campanha e verificar resposta com texto não vazio, idioma informado e duração coerente com o áudio.

**Acceptance Scenarios**:

1. **Given** o serviço está em execução com modelo carregado, **When** o workflow envia `{audio_path, language: "pt"}` para um arquivo `.ogg` existente, **Then** a resposta contém `text`, `language` e `duration_s` preenchidos.
2. **Given** o caminho informado não existe, **When** o workflow solicita transcrição, **Then** recebe erro claro indicando arquivo não encontrado (sem crash do processo).
3. **Given** o arquivo existe mas está corrompido ou em formato inválido, **When** o workflow solicita transcrição, **Then** recebe erro descritivo e o serviço permanece disponível para a próxima utterance.

---

### User Story 2 - Verificar disponibilidade do serviço (Priority: P1)

Como operador do servidor (via cron de monitoramento ou n8n), quero consultar o status do serviço e qual modelo está carregado, para detectar falhas de inicialização antes que uma sessão inteira fique sem transcrição.

**Why this priority**: O modelo demora a carregar na subida; sem health check, falhas silenciosas só aparecem no meio do pipeline.

**Independent Test**: Após iniciar o processo, chamar endpoint de saúde e confirmar resposta consistente com modelo e configuração esperados.

**Acceptance Scenarios**:

1. **Given** o serviço terminou de inicializar, **When** o operador consulta saúde, **Then** recebe status positivo e identificação do modelo em uso.
2. **Given** o serviço ainda está carregando o modelo, **When** saúde é consultada, **Then** o comportamento é previsível (indisponível ou status que indique não pronto — documentado no quickstart).
3. **Given** o serviço está saudável, **When** o cron de monitoramento consulta periodicamente, **Then** consegue distinguir serviço ok de serviço parado ou com modelo ausente.

---

### User Story 3 - Integrar com n8n em Docker (Priority: P1)

Como workflow n8n rodando em container, quero alcançar o serviço no host via rede interna, para transcrever arquivos que o Cronista gravou no filesystem do servidor.

**Why this priority**: n8n e whisper-service não compartilham o mesmo runtime; falha de conectividade bloqueia 100% das transcrições em produção.

**Independent Test**: Com n8n em Docker e serviço no host, executar uma chamada de transcrição usando o hostname de bridge documentado (`host.docker.internal`) e confirmar sucesso.

**Acceptance Scenarios**:

1. **Given** n8n configurado com `extra_hosts: host.docker.internal:host-gateway`, **When** o node HTTP chama o serviço na porta configurada, **Then** a conexão é estabelecida sem erro de rede.
2. **Given** o serviço escuta em todas as interfaces do host (não apenas loopback), **When** tráfego vem da bridge Docker, **Then** a requisição é aceita.
3. **Given** o workflow processa `speaking_log.jsonl` sequencialmente, **When** transcreve N utterances de uma sessão, **Then** todas completam sem necessidade de reiniciar o serviço entre arquivos.

---

### User Story 4 - Ajustar qualidade vs velocidade sem redeploy de código (Priority: P2)

Como operador, quero alterar tamanho do modelo e perfil de computação via variáveis de ambiente, para calibrar qualidade da transcrição (nomes de PJs, jargão de campanha) versus tempo de processamento em CPU-only.

**Why this priority**: O modelo `small` é ponto de partida; só testes reais definem se `medium` compensa — isso não deve exigir mudança de código.

**Independent Test**: Alterar variável de modelo, reiniciar serviço, confirmar via health check que o novo modelo está ativo e comparar qualidade em amostra de áudio real.

**Acceptance Scenarios**:

1. **Given** variáveis de ambiente definidas no `.env` ou unit systemd, **When** o serviço reinicia, **Then** carrega o modelo e compute type configurados.
2. **Given** operador troca de `small` para `medium`, **When** health é consultado, **Then** reflete o novo tamanho de modelo.
3. **Given** configuração inválida (modelo inexistente), **When** o serviço tenta iniciar, **Then** falha de forma explícita nos logs (não fica em estado silenciosamente quebrado).

---

### Edge Cases

- Arquivo de áudio referenciado no `speaking_log.jsonl` foi removido ou movido antes da transcrição → erro 404 claro, workflow continua ou registra falha por utterance.
- Utterance com silêncio ou áudio muito curto → texto vazio ou mínimo, sem travar o serviço.
- Utterance longa (ex.: pausa de fala curta gerou segmento grande) → transcrição completa dentro do timeout configurado no n8n (120s default) ou erro timeout documentado.
- Serviço reiniciado no meio de uma sessão → modelo recarrega uma vez; utterances pendentes podem ser reprocessadas pelo workflow.
- Múltiplas requisições simultâneas (futuro) → fora do escopo MVP; comportamento deve ser previsível (serialização ou fila explícita em fase futura).
- Porta exposta em `0.0.0.0` sem firewall → risco de acesso indevido na LAN; mitigação operacional obrigatória (ver Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O serviço MUST expor endpoint `POST /transcribe` que aceita `audio_path` (caminho absoluto no host) e `language` (código ISO, ex.: `pt`).
- **FR-002**: Resposta bem-sucedida de transcrição MUST incluir `text` (string transcrita), `language` (eco do solicitado ou detectado) e `duration_s` (duração do áudio processado).
- **FR-003**: O serviço MUST retornar erro claro quando `audio_path` não existe no filesystem.
- **FR-004**: O serviço MUST retornar erro descritivo quando a transcrição falha (arquivo corrompido, formato não suportado, etc.) sem derrubar o processo.
- **FR-005**: O serviço MUST expor endpoint `GET /health` reportando disponibilidade e modelo carregado (e tipo de computação em uso).
- **FR-006**: O modelo de transcrição MUST ser carregado uma única vez na inicialização do processo e reutilizado em todas as chamadas subsequentes.
- **FR-007**: Tamanho do modelo, tipo de computação, host de escuta e porta MUST ser configuráveis via variáveis de ambiente sem alteração de código.
- **FR-008**: Valores default MUST ser: modelo `small`, compute `int8`, host `0.0.0.0`, porta `8008`.
- **FR-009**: O serviço MUST aceitar arquivos de áudio já presentes em disco — MUST NOT exigir upload binário via HTTP no MVP.
- **FR-010**: O serviço MUST operar em CPU-only nesta fase (sem dependência de GPU).
- **FR-011**: O serviço MUST ser invocável pelo workflow n8n a partir de container Docker via `host.docker.internal` (com `extra_hosts` configurado no compose do n8n).
- **FR-012**: O serviço MUST rodar com worker único nesta fase, evitando duplicação do modelo em memória.
- **FR-013**: O serviço MUST viver em pasta e venv próprios no repositório, independentes do código do Cronista.
- **FR-014**: Deploy MUST seguir padrão systemd existente (usuário `adminvtt`, venv isolado), alinhado aos demais serviços do host.

### Key Entities

- **Requisição de transcrição**: Par `{audio_path, language}` enviada pelo n8n para um utterance.
- **Resposta de transcrição**: Par `{text, language, duration_s}` consumida pelo workflow para montagem do transcript.
- **Status de saúde**: Indicador operacional `{status, model, compute_type}` para monitoramento.
- **Utterance**: Arquivo de áudio curto (tipicamente `.ogg`) gerado pelo Cronista, referenciado em `speaking_log.jsonl`.
- **Configuração de runtime**: Variáveis de ambiente que controlam modelo, compute, bind de rede e porta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Após subida do processo, `/health` responde consistentemente confirmando modelo carregado (100% das tentativas em janela de 5 minutos pós-start).
- **SC-002**: Utterance de 10–15 segundos transcreve em tempo significativamente menor que 120 segundos (limite do timeout n8n), em hardware alvo (Kron Mini K1, CPU-only).
- **SC-003**: Em teste com áudio real da campanha, nomes próprios de personagens e locais são reconhecidos em taxa aceitável para o GM (validação manual piloto — critério qualitativo documentado no teste).
- **SC-004**: Workflow n8n completa transcrição de sessão piloto (≥20 utterances) sequencialmente sem reiniciar o serviço.
- **SC-005**: n8n em Docker alcança o serviço via `host.docker.internal:8008` com 0 erros de conexão em teste de integração documentado.
- **SC-006**: Segunda utterance da mesma sessão é processada mais rápido que recarregar modelo do zero (evidência: tempo total de sessão compatível com modelo residente em memória).

## Assumptions

- Único consumidor do serviço é o workflow n8n "Cronista - Transcrição da Sessão" — não há usuários humanos diretos.
- Arquivos de áudio já existem no host no caminho informado (gravados pelo Cronista em `/opt/apps/cronista/recordings/...`).
- Idioma padrão das sessões é português (`pt`).
- Diarização (quem falou) já é resolvida pela segmentação por usuário do Cronista — o serviço só transcreve áudio.
- Não há tradução — transcreve no idioma informado.
- Sem autenticação no MVP — isolamento depende de firewall restringindo porta 8008 à bridge Docker e localhost.
- Modelo `small` + `int8` é ponto de partida; upgrade para `medium` é decisão operacional após teste de qualidade.
- n8n chama `/transcribe` sequencialmente (uma utterance por vez) — sem paralelismo no MVP.
- Timeout HTTP de 120s no n8n é suficiente para utterances típicas; utterances anormalmente longas podem exigir ajuste futuro.
- Existe protótipo funcional (`main.py`) como referência de implementação, sujeito a revisão formal nesta feature.

## Out of Scope

- Upload de arquivo binário via HTTP.
- Fila de processamento / múltiplos workers concorrentes.
- Interface web ou dashboard.
- Suporte a GPU (evolução futura com hardware dedicado).
- Autenticação por token ou API key (revisitar se exposição de rede mudar).
- Diarização ou identificação de falante.
- Tradução para outro idioma.
- Retenção ou limpeza de arquivos transcritos.
- Alteração do contrato de gravação do Cronista ou do webhook n8n de encerramento de sessão.

## Dependencies

- **Cronista**: produz utterances `.ogg` e `speaking_log.jsonl` consumidos pelo workflow n8n.
- **n8n**: orquestra chamadas sequenciais a `/transcribe` e montagem do transcript final.
- **Infraestrutura host**: systemd, venv Python isolado, `ffmpeg`/libs de áudio se necessário para decodificação de formatos de entrada.
- **Rede Docker**: `extra_hosts` no compose do n8n para resolução de `host.docker.internal`.
- **Firewall (ufw)**: regra restritiva na porta 8008 — sub-rede bridge Docker + localhost (sub-rede exata confirmada no deploy).

## Open Questions (resolved by defaults in this spec)

| Tema | Decisão provisória |
|------|-------------------|
| Tamanho de modelo definitivo | `small` default; validar com áudio real; escalar via env se qualidade insuficiente |
| Regra de firewall exata | Confirmar sub-rede com `docker network inspect bridge` no deploy; documentar em quickstart |
| Timeout n8n vs utterances problemáticas | 120s mantido; workflow MUST tratar erro HTTP e continuar ou marcar utterance falha |
