# Feature Specification: Transcrição assíncrona por sessão (whisper-service v2)

**Feature Branch**: `003-whisper-session-async`

**Created**: 2026-08-08

**Status**: Draft

**Input**: `docs/demanda-whisper-service-v2.md` — mover o processamento em lote para dentro do whisper-service, reduzindo a interação com o n8n a poucas chamadas por sessão.

## Context

Na v1, o workflow n8n chama o serviço uma vez por utterance (centenas a milhares de requisições HTTP atravessando a rede Docker). Em produção isso gerou timeouts, execuções duplicadas e falhas difíceis de diagnosticar.

Esta feature muda o fluxo principal: o n8n envia **uma** solicitação com os dados da sessão; o serviço processa todas as utterances localmente, monta o arquivo de transcrição no formato já esperado pelo pipeline e notifica o n8n ao terminar. Os endpoints pontuais da v1 (`/transcribe` por utterance e `/health`) permanecem disponíveis para debug, mas deixam de ser o caminho principal.

## Clarifications

### Session 2026-08-08

- Q: Linhas sem texto na `transcricao.txt` → A: Incluir marcador explícito `[HH:MM:SS] Nome: (silêncio)`
- Q: Idioma da transcrição no lote de sessão → A: Sempre `pt` no lote (sem campo `language` no request)
- Q: Validação de paths da sessão → A: Validar `recordings_path` e `speaking_log_path` sob `WHISPER_ALLOWED_PATH_PREFIX`
- Q: Erro fatal no meio do lote → A: `failed` + sem arquivo; callback com erro e `processed` parcial
- Q: `user_id` sem `display_name` nos participantes → A: Fallback: usar `user_id` como nome na linha

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Aceitar sessão e processar em segundo plano (Priority: P1)

Como workflow n8n, quero enviar os dados de uma sessão completa e receber confirmação imediata de aceite, para não ficar bloqueado esperando centenas de transcrições HTTP.

**Why this priority**: Elimina o gargalo e a fragilidade da v1 (loop de milhares de chamadas).

**Independent Test**: Enviar solicitação de sessão com `speaking_log` e pasta de gravações válidos; a resposta de aceite chega em menos de 1 segundo; o processamento continua após a resposta.

**Acceptance Scenarios**:

1. **Given** uma sessão com `speaking_log` e arquivos de áudio acessíveis, **When** o n8n solicita transcrição da sessão, **Then** recebe aceite imediato com o identificador da sessão.
2. **Given** o aceite foi emitido, **When** o processamento corre em segundo plano, **Then** o arquivo final de transcrição é escrito na pasta da sessão no formato `[HH:MM:SS] Nome: texto` (ou `[HH:MM:SS] Nome: (silêncio)` quando o texto transcrito estiver vazio).
3. **Given** o processamento terminou com sucesso, **When** o serviço notifica o `callback_url`, **Then** o payload inclui sessão, status concluído, caminho do arquivo, totais e canal.

---

### User Story 2 - Impedir processamento duplicado da mesma sessão (Priority: P1)

Como operador do pipeline, quero que uma segunda solicitação para a mesma sessão em andamento seja rejeitada, para não repetir o incidente de duas execuções concorrentes sobrecarregando o serviço e corrompendo contagens.

**Why this priority**: Causa raiz do incidente recente em produção.

**Independent Test**: Com uma sessão `in_progress`, enviar a mesma `session_id` de novo e verificar rejeição sem segundo processamento.

**Acceptance Scenarios**:

1. **Given** a sessão S está em processamento, **When** chega nova solicitação para S, **Then** a resposta indica conflito e nenhum segundo lote é iniciado.
2. **Given** a sessão S já terminou (`done` ou `failed`), **When** chega nova solicitação para S, **Then** o comportamento é previsível e documentado (aceitar reprocessamento ou rejeitar — ver Assumptions).

---

### User Story 3 - Acompanhar progresso da sessão (Priority: P1)

Como operador ou workflow, quero consultar o status de uma sessão e ver progresso incremental (processadas / total), para diagnosticar sem grepar logs e para o n8n poder aguardar de forma controlada se necessário.

**Why this priority**: Substitui a opacidade das falhas silenciosas da v1.

**Independent Test**: Durante um lote longo, consultas periódicas mostram `processed` aumentando até `total`; ao fim, status `done` com caminho do arquivo.

**Acceptance Scenarios**:

1. **Given** o processamento está a meio caminho, **When** consulto o status da sessão, **Then** vejo `in_progress` com `processed` entre 0 e `total` e horário de início.
2. **Given** o lote concluiu, **When** consulto o status, **Then** vejo `done`, totais, caminho do `transcricao.txt` e horário de fim.
3. **Given** o lote falhou, **When** consulto o status, **Then** vejo `failed`, mensagem de erro e quantas utterances já tinham sido processadas.
4. **Given** uma `session_id` nunca solicitada (ou perdida após reinício do serviço), **When** consulto o status, **Then** recebo indicação de sessão desconhecida.

---

### User Story 4 - Manter o serviço responsivo durante o lote (Priority: P1)

Como operador, quero que saúde e status continuem respondendo enquanto uma sessão é transcrita, para monitorar o serviço e não “matar” o processo achando que travou.

**Why this priority**: Processamento de CPU não pode bloquear o atendimento HTTP do serviço.

**Independent Test**: Com uma sessão longa em andamento, consultas de saúde e de status respondem normalmente (sem timeout prolongado).

**Acceptance Scenarios**:

1. **Given** uma sessão está sendo processada, **When** consulto a saúde do serviço, **Then** a resposta chega em tempo normal de operação.
2. **Given** uma sessão está sendo processada, **When** consulto o status dessa sessão, **Then** a resposta reflete progresso atual sem esperar o fim do lote.

---

### User Story 5 - Notificar conclusão com retry (Priority: P2)

Como workflow n8n, quero receber um callback ao término (sucesso ou falha), com novas tentativas se o webhook estiver temporariamente indisponível.

**Why this priority**: Fecha o ciclo do pipeline; retry evita perda por reinício momentâneo do n8n.

**Independent Test**: Simular falha temporária no `callback_url` e verificar novas tentativas; após esgotar, o status da sessão permanece consultável.

**Acceptance Scenarios**:

1. **Given** o lote terminou com sucesso e o callback responde OK, **When** o serviço notifica, **Then** uma única notificação bem-sucedida encerra o ciclo.
2. **Given** o callback falha nas primeiras tentativas, **When** o serviço reintenta com backoff (até 3 tentativas), **Then** eventual sucesso ou registro de falha no log.
3. **Given** todas as tentativas de callback falharam, **When** o operador consulta o status, **Then** ainda consegue obter resultado (`done`/`failed`) e caminho ou erro.

---

### Edge Cases

- `speaking_log` ou pasta de gravações inexistente / ilegível → sessão falha com erro claro; callback `failed` se possível.
- `recordings_path` ou `speaking_log_path` fora de `WHISPER_ALLOWED_PATH_PREFIX` → rejeitar a solicitação (sem iniciar lote); mesmo tipo de proteção da v1.
- Utterance referenciada no log sem arquivo de áudio → registrar falha pontual ou pular conforme comportamento documentado; não derrubar o lote inteiro sem necessidade (Assumption: continuar e contar falhas no total processado).
- Utterance silenciosa / texto vazio → escrever linha `[HH:MM:SS] Nome: (silêncio)`; contagem `utterances_com_texto` reflete só as com conteúdo real (não conta o marcador de silêncio).
- Reinício do processo no meio do lote → status em memória se perde; arquivo final só existe se a escrita completa tiver ocorrido (escrita só ao final nesta fase).
- Duas sessões *diferentes* ao mesmo tempo → permitidas, mas compartilham a mesma CPU limitada; aceitável nesta fase.
- `callback_url` inválido → falha de callback após retries; status local permanece.
- Erro fatal não recuperável no meio do lote (exceção do modelo, falha de I/O ao montar resultado, etc.) → status `failed`; **não** escrever `transcricao.txt`; callback `failed` com mensagem e `processed` parcial.
- `user_id` ausente ou sem `display_name` em `participants` → usar o `user_id` como nome na linha da transcrição; não falhar o lote.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O serviço MUST aceitar solicitação de transcrição de sessão completa contendo pelo menos: identificador da sessão, caminho das gravações, caminho do `speaking_log`, lista de participantes (com mapeamento id→nome), identificador do canal e URL de callback. O lote de sessão MUST usar idioma `pt` fixo (sem campo `language` no request).
- **FR-002**: A resposta de aceite da solicitação de sessão MUST ser imediata (não aguardar o fim do lote) e incluir o identificador da sessão.
- **FR-003**: Enquanto uma sessão estiver em andamento, uma nova solicitação com a mesma `session_id` MUST ser rejeitada com conflito (sem iniciar segundo processamento).
- **FR-004**: O serviço MUST ler o `speaking_log` do disco e transcrever cada utterance localmente (sem nova ida HTTP por arquivo).
- **FR-005**: Ao concluir o lote com sucesso, o serviço MUST escrever `transcricao.txt` na pasta da sessão, com linhas no formato `[HH:MM:SS] Nome: texto`, ordenadas por início relativo (`start_ms`), usando o nome de exibição dos participantes. Quando o texto transcrito estiver vazio, a linha MUST usar o marcador `(silêncio)` no lugar do texto. Se o `user_id` não tiver `display_name` em `participants`, o serviço MUST usar o próprio `user_id` como nome na linha.
- **FR-006**: O serviço MUST expor consulta de status por `session_id` com estados: em andamento, concluído, falhou, ou desconhecido.
- **FR-007**: Durante o processamento, o status MUST refletir progresso incremental (`processed` / `total`), não apenas início e fim.
- **FR-008**: Ao terminar (sucesso ou falha total), o serviço MUST notificar o `callback_url` com payload contendo sessão, status, totais e, se sucesso, caminho do arquivo e canal; se falha, mensagem de erro.
- **FR-009**: Falhas de callback MUST ser reintentadas com backoff, até 3 tentativas; se persistirem, MUST ser registradas em log sem impedir consulta posterior via status.
- **FR-010**: Saúde do serviço e consulta de status MUST permanecer utilizáveis enquanto um lote CPU-intensivo está em execução.
- **FR-011**: Os endpoints de utterance única e saúde da v1 MUST permanecer disponíveis (caminho de debug / regressão), sem serem o fluxo principal do pipeline.
- **FR-012**: Status de sessão MUST ser mantido em memória nesta fase (sem persistência obrigatória); perda após reinício do processo é aceitável e documentada.
- **FR-013**: `recordings_path` e `speaking_log_path` MUST estar sob o prefixo permitido (`WHISPER_ALLOWED_PATH_PREFIX`); caminhos fora MUST ser rejeitados na solicitação (antes do aceite/processamento).
- **FR-014**: Em erro fatal não recuperável durante o lote, o serviço MUST marcar a sessão como `failed`, MUST NOT escrever `transcricao.txt`, e MUST notificar o `callback_url` com status de falha, mensagem de erro e contagem `processed` parcial.

### Key Entities

- **Solicitação de sessão**: Dados enviados pelo n8n para iniciar o lote (ids, paths, participantes, callback).
- **Estado de sessão**: Progresso em memória (`status`, processadas, total, horários, erro, caminho de saída).
- **Transcrição final**: Arquivo `transcricao.txt` no diretório da sessão, formato legado do node n8n.
- **Notificação de conclusão**: Payload POST ao callback do n8n após o lote.
- **Participante**: Mapeamento `user_id` → `display_name` para formatação das linhas; se ausente, fallback para o próprio `user_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Aceite de solicitação de sessão retorna em menos de 1 segundo sob carga normal (não espera o lote).
- **SC-002**: Segunda solicitação da mesma sessão em andamento é rejeitada em 100% dos casos de teste de conflito (sem segundo lote).
- **SC-003**: Durante um lote de ≥100 utterances, pelo menos 3 consultas de status em momentos distintos mostram `processed` estritamente crescente.
- **SC-004**: Ao final bem-sucedido, o arquivo de transcrição existe no caminho esperado e o formato das linhas bate com o padrão do pipeline (`[HH:MM:SS] Nome: texto`), usando `(silêncio)` quando não houver texto.
- **SC-005**: Callback de sucesso chega ao destino configurado com totais coerentes com o `speaking_log` (total e `utterances_com_texto` excluindo linhas só com marcador de silêncio).
- **SC-006**: Durante o processamento de uma sessão completa, consultas de saúde do serviço continuam respondendo sem falha de disponibilidade atribuída ao bloqueio do atendimento.
- **SC-007**: Em falha simulada do callback nas 2 primeiras tentativas, a 3ª tentativa ou o fallback via status ainda permite o operador/workflow obter o resultado da sessão.

## Assumptions

- O whisper-service continua rodando no mesmo host que as gravações do Cronista (paths locais válidos).
- `recordings_path` e `speaking_log_path` seguem a mesma proteção de path da v1 (`WHISPER_ALLOWED_PATH_PREFIX`).
- Idioma do lote de sessão é sempre `pt` (pipeline Cronista/RPG em português); o endpoint v1 `/transcribe` pode continuar aceitando `language` por utterance para debug.
- O formato de saída `[HH:MM:SS] Nome: texto` (com `(silêncio)` para texto vazio) é o contrato estável com o n8n (migração do node “Montar transcrição final”).
- Timestamps nas linhas usam `start_ms` relativo ao início da sessão, convertidos para `HH:MM:SS`.
- Após sessão `done`/`failed`, uma nova solicitação com a mesma `session_id` **pode reiniciar** o processamento (substitui estado anterior) — útil para reprocessar; conflito 409 aplica-se só a `in_progress`.
- Utterances sem arquivo: o lote **continua**; falhas pontuais incrementam `processed` e não geram linha de texto (não entram em `utterances_com_texto`).
- Escrita de `transcricao.txt` ocorre ao final do lote com sucesso (não incremental nesta fase); em `failed` o arquivo não é criado/atualizado nesta execução.
- Callback retry: 3 tentativas com backoff; detalhes de intervalo ficam no plano técnico.
- Limitação de CPU (`WHISPER_CPU_THREADS`) da v1 permanece; duas sessões distintas podem coexistir e disputar CPU.
- Autenticação do serviço permanece fora de escopo (isolamento por rede/firewall).
- Nome de exibição ausente: fallback para `user_id` na linha (não aborta o lote).

## Out of Scope

- Persistência durável de status (SQLite/arquivo) ou escrita incremental de `transcricao.txt`.
- Fila multi-worker / paralelismo real entre utterances da mesma sessão.
- Remoção dos endpoints v1 `/transcribe` e `/health`.
- Alteração do contrato de gravação do Cronista (`session.json`, `speaking_log.jsonl`).
- GPU, diarização, tradução, upload HTTP de áudio.
- Dashboard ou UI de acompanhamento.

## Dependencies

- whisper-service v1 (modelo carregado, CPU threads, paths permitidos).
- Artefatos Cronista: `speaking_log.jsonl` + `{user_id}/NNNN.ogg`.
- Workflow n8n atualizado para chamar o fluxo por sessão + webhook de conclusão.
- Rede: callback tipicamente para n8n no host (`127.0.0.1` ou equivalente acessível do processo).
