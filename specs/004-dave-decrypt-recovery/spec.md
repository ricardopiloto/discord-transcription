# Feature Specification: Recuperação automática de falhas de decriptação DAVE

**Feature Branch**: `004-dave-decrypt-recovery`

**Created**: 2026-08-08

**Status**: Draft

**Input**: `docs/demanda-whisper-service-dave-fix.md` — detectar falha silenciosa de decriptação de voz após reconnect/renegociação DAVE e recuperar via reconexão completa do canal, com registro de gaps e alerta imediato.

## Context

Em sessão real (~50 min), um fechamento anormal da conexão de voz foi seguido de reconnect “leve” que restabeleceu o canal sem renegociar corretamente as chaves de decriptação. O bot continuou “gravando”, mas todo áudio falhou em silêncio por mais de 2 horas — sem derrubar o processo nem o fim de sessão — e o diagnóstico só veio no dia seguinte pelos logs.

Essa classe de falha tende a se repetir: a renegociação de chaves pode ocorrer não só em reconnect do bot, mas quando a lista de participantes do canal muda (comum em sessões longas com vários jogadores).

## Clarifications

### Session 2026-08-08

- Q: Após esgotar as tentativas de reconexão → A: Manter sessão aberta; sair do voz; só alerta crítico (sem auto-encerrar)
- Q: Canal dos alertas em tempo real → A: Webhook HTTP mid-session; Telegram via monitor externo
- Q: Cooldown após recuperação bem-sucedida → A: Cooldown 60s (configurável) após recuperação OK
- Q: Relógio nos campos de `recording_gaps.jsonl` → A: Parede ISO-8601 UTC e ms relativos à sessão
- Q: Quando a recuperação conta como sucesso → A: Sucesso no 1º pacote decodificado OK (timeout default 30s)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detectar falha de decriptação em tempo real (Priority: P1)

Como operador/GM, quero que o Cronista perceba imediatamente uma sequência de falhas de decriptação de voz durante uma gravação ativa, para não descobrir horas depois que nada foi capturado.

**Why this priority**: Sem detecção, qualquer recuperação ou alerta é impossível; foi a causa do incidente de 07/08.

**Independent Test**: Em gravação de teste, forçar cenário que produza falhas consecutivas de decriptação/decodificação de pacote; o sistema marca o incidente dentro da janela configurada sem intervenção manual.

**Acceptance Scenarios**:

1. **Given** uma gravação ativa com pacotes sendo decodificados com sucesso, **When** ocorrem falhas consecutivas de decriptação/decodificação atingindo o limiar dentro da janela de tempo configurada, **Then** o Cronista inicia o fluxo de recuperação automaticamente.
2. **Given** falhas isoladas espaçadas além da janela configurada, **When** cada falha ocorre, **Then** o contador não dispara recuperação (tratado como ruído).
3. **Given** uma falha seguida de pacote decodificado com sucesso, **When** o sucesso ocorre, **Then** o contador de falhas consecutivas é zerado.

---

### User Story 2 - Recuperar a captura com reconexão completa (Priority: P1)

Como operador/GM, quero que o bot saia e entre de novo no canal de voz por completo (não um reconnect interno superficial), para que a captura volte a gravar áudio utilizável após a falha de chave.

**Why this priority**: O reconnect leve já falhou em produção; a mitigação acordada é forçar handshake completo.

**Independent Test**: Após disparo da detecção em sessão de teste, o bot reconecta sem comando manual e novas falas voltam a gerar entradas no log de falantes e arquivos de áudio.

**Acceptance Scenarios**:

1. **Given** o limiar de falhas foi atingido, **When** a recuperação roda, **Then** o bot desconecta completamente do canal e reconecta do zero (sem depender do reconnect interno superficial).
2. **Given** a primeira tentativa de reconexão falha, **When** ainda há tentativas restantes, **Then** o bot tenta de novo com espera crescente entre tentativas, até o limite configurado.
3. **Given** a reconexão foi bem-sucedida (1º pacote decodificado com sucesso após o connect), **When** participantes falam depois disso, **Then** novas utterances aparecem normalmente no log de falantes e nos arquivos da sessão.
4. **Given** utterances já fechadas antes do gap, **When** a recuperação ocorre, **Then** esses arquivos e metadados já gravados permanecem intactos.
5. **Given** uma recuperação acabou de ter sucesso, **When** novas falhas de decriptação ocorrem dentro do cooldown configurável (default 60s), **Then** um novo ciclo de recuperação automática NÃO é disparado até o cooldown expirar.
6. **Given** o `connect` completou mas nenhum pacote decodifica com sucesso até o timeout de validação (default 30s), **When** o timeout expira, **Then** a tentativa conta como falha e o backoff/próxima tentativa segue normalmente.

---

### User Story 3 - Registrar o buraco de captura de forma explícita (Priority: P1)

Como operador do pipeline de transcrição, quero um registro dedicado de cada intervalo sem captura, para não interpretar silêncio no log como “ninguém falou”.

**Why this priority**: A ausência dessa informação atrasou o diagnóstico do incidente.

**Independent Test**: Após um ciclo detecção→recuperação (ou falha definitiva), existe ao menos uma linha no registro de gaps da sessão com início, fim (se aplicável), motivo, tentativas e sucesso/fracasso.

**Acceptance Scenarios**:

1. **Given** um gap foi detectado e a reconexão concluiu (sucesso ou esgotamento), **When** consulto o registro de gaps da sessão, **Then** vejo início/fim em ISO-8601 UTC e em ms relativos ao início da sessão, motivo de falha de decriptação DAVE, número de tentativas e se teve sucesso.
2. **Given** uma sessão com um ou mais gaps, **When** o pipeline/analista inspeciona os artefatos da sessão, **Then** consegue distinguir “ninguém falou” de “falha de captura”.

---

### User Story 4 - Alertar em tempo real via webhook (Priority: P1)

Como operador, quero avisos no momento da detecção, da recuperação e da falha definitiva (entregues por webhook HTTP ao monitor externo, tipicamente Telegram), para intervir sem olhar log do servidor.

**Why this priority**: Detecção sem alerta ainda deixa o problema invisível durante a sessão.

**Independent Test**: No teste controlado, o endpoint de webhook mid-session recebe os payloads/textos de detecção e de recuperação (ou de falha definitiva) antes do fim da sessão.

**Acceptance Scenarios**:

1. **Given** o limiar foi atingido, **When** a recuperação começa, **Then** o webhook mid-session recebe alerta de falha de decriptação DAVE detectada no canal, indicando que está tentando reconectar.
2. **Given** a reconexão teve sucesso, **When** a gravação retoma, **Then** o webhook mid-session recebe confirmação com a duração do gap.
3. **Given** as tentativas se esgotaram sem sucesso, **When** o Cronista desiste, **Then** o webhook mid-session recebe alerta crítico de gravação comprometida a partir do horário do início do gap; a sessão permanece aberta, o bot sai do canal de voz, e o operador pode recuperar ou encerrar manualmente.

---

### User Story 5 - Visibilidade de gaps no encerramento da sessão (Priority: P2)

Como GM/operador, quero ver no aviso de “sessão encerrada” se houve gaps de captura, para não depender só de abrir o arquivo de gaps.

**Why this priority**: Fecha o ciclo de observabilidade; útil mesmo quando o alerta mid-session foi ignorado.

**Independent Test**: Encerrar uma sessão de teste que teve ≥1 gap e verificar que a notificação final menciona a contagem de gaps.

**Acceptance Scenarios**:

1. **Given** a sessão encerrou com N ≥ 1 gaps registrados, **When** o aviso final de sessão é enviado, **Then** ele inclui a contagem de gaps (além do resumo já existente).
2. **Given** a sessão encerrou sem gaps, **When** o aviso final é enviado, **Then** o comportamento atual se mantém (sem alarme falso de gaps).

---

### Edge Cases

- Falha isolada ocasional (rede) dentro da janela mas abaixo do limiar → não dispara recuperação.
- Múltiplos gaps na mesma sessão → cada incidente gera registro e alertas próprios; limiar/contadores reiniciam após recuperação bem-sucedida.
- Reconexão bem-sucedida mas falhas voltam → novo ciclo só após o cooldown (default 60s); durante o cooldown, falhas são logadas mas não disparam nova recuperação automática.
- Sessão encerrada enquanto a recuperação ainda tenta reconectar → registrar gap com sucesso=false (ou fim no encerramento) e não deixar tentativas órfãs bloqueando o shutdown de forma indefinida.
- Canal sem permissão / connect impossível → esgotar tentativas, alerta crítico via webhook, registrar gap com sucesso=false, **sair do canal de voz**, manter sessão aberta para intervenção manual (`!cronista entrar` / `encerrar`).
- Webhook mid-session indisponível → registrar falha de alerta em log; não impedir recuperação/reconexão; gaps e aviso final de sessão continuam obrigatórios.
- Participante entra/sai causando renegociação saudável → não deve disparar se pacotes voltam a decodificar antes do limiar.
- Canal silencioso após reconnect (ninguém fala no timeout de validação) → tentativa conta como falha (não há pacote OK para confirmar chaves); operador pode precisar falar ou ajustar timeout.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Durante gravação ativa, o Cronista MUST monitorar falhas de decriptação/decodificação de pacotes de voz por conexão ativa.
- **FR-002**: O Cronista MUST manter contagem de falhas consecutivas e MUST zerar essa contagem a cada pacote decodificado com sucesso.
- **FR-003**: O Cronista MUST iniciar recuperação somente quando o número de falhas consecutivas atingir o limiar configurável **dentro** da janela de tempo configurável (falhas fora da janela não acumulam o mesmo incidente).
- **FR-004**: Na recuperação, o Cronista MUST desconectar completamente do canal de voz e reconectar do zero (MUST NOT depender apenas do reconnect interno superficial da biblioteca de voz).
- **FR-005**: Falhas de reconexão MUST ser reintentadas com espera crescente entre tentativas, até um máximo configurável; ao esgotar, MUST escalar alerta crítico, registrar o gap como sem sucesso, MUST sair completamente do canal de voz, e MUST NOT encerrar a sessão automaticamente — o operador recupera ou encerra via comandos existentes.
- **FR-016**: Uma tentativa de reconexão MUST ser considerada bem-sucedida somente após o primeiro pacote de voz decodificado com sucesso após o connect; se esse pacote não ocorrer dentro do timeout de validação configurável (default 30s), a tentativa MUST contar como falha.
- **FR-006**: Utterances e metadados já persistidos antes do gap MUST permanecer intactos; a recuperação afeta apenas a captura a partir do momento da falha.
- **FR-007**: Cada gap MUST ser registrado em artefato dedicado da sessão (`recording_gaps.jsonl`, uma linha JSON por evento), contendo pelo menos: `started_at` / `finished_at` (ISO-8601 UTC), `start_ms` / `end_ms` (relativos ao início da sessão), motivo (`dave_decrypt_failure`), número de tentativas de reconexão e indicador de sucesso.
- **FR-008**: Ao detectar o gap, o Cronista MUST enviar alerta mid-session via webhook HTTP configurável (mensagem de detecção: canal + tentativa de reconectar), sem esperar o fim da sessão. Entrega a Telegram (ou outro canal) fica a cargo do monitor externo.
- **FR-009**: Após recuperação bem-sucedida, o Cronista MUST enviar via mesmo webhook a confirmação de retomada e a duração do gap.
- **FR-010**: Se as tentativas se esgotarem sem sucesso, o Cronista MUST enviar via webhook alerta crítico com número de tentativas e horário a partir do qual a gravação ficou comprometida.
- **FR-011**: Após reconexão bem-sucedida, novas falas MUST voltar a gerar utterances e entradas no `speaking_log.jsonl` como em operação normal.
- **FR-012**: Se a sessão encerrar com um ou mais gaps registrados, o aviso final de “sessão encerrada” MUST incluir a contagem desses gaps.
- **FR-013**: Limiar de falhas, janela de tempo, máximo de tentativas de reconexão, espera-base entre tentativas, cooldown pós-recuperação e timeout de validação pós-connect MUST ser configuráveis por variáveis de ambiente, com defaults: limiar 5, janela 10s, máx. tentativas 5, espera-base 3s (multiplicada por tentativa), cooldown 60s, validação pós-connect 30s.
- **FR-014**: URL do webhook mid-session MUST ser configurável por variável de ambiente; se ausente, o Cronista MUST registrar em log que o alerta foi omitido e MUST continuar detecção/recuperação/registro de gaps.
- **FR-015**: Após recuperação bem-sucedida, o Cronista MUST aplicar cooldown configurável (default 60s) durante o qual MUST NOT iniciar novo ciclo automático de recuperação; ao expirar, a detecção volta ao comportamento normal.

### Key Entities

- **Incidente de decriptação**: Sequência de falhas consecutivas dentro da janela que dispara recuperação.
- **Gap de gravação**: Intervalo sem captura utilizável, persistido em `recording_gaps.jsonl` (parede UTC + ms relativos à sessão).
- **Tentativa de reconexão**: Uma saída+entrada completa no canal, com resultado sucesso/falha.
- **Alerta operacional**: Payload/texto via webhook mid-session (detecção, recuperação ou falha crítica) e menção de gaps no encerramento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em teste controlado que simula perda de captura por falha de decriptação/reconexão, a detecção e o início da recuperação ocorrem sem intervenção manual, dentro da janela configurada (default 10s após atingir o limiar).
- **SC-002**: No mesmo teste, recuperação só é marcada sucesso após decodificação OK pós-reconnect; em seguida ao menos uma nova utterance com áudio utilizável é registrada no log de falantes.
- **SC-003**: 100% dos gaps disparados no teste geram linha correspondente em `recording_gaps.jsonl` com os campos mínimos exigidos (UTC + ms relativos + motivo + tentativas + sucesso).
- **SC-004**: Em teste com recuperação bem-sucedida, o webhook mid-session recebe as duas notificações (detecção e recuperação) antes do encerramento da sessão.
- **SC-005**: Em teste com esgotamento de tentativas, o webhook mid-session recebe a notificação crítica, nenhuma reconexão adicional é tentada além do máximo, o bot não está mais no canal de voz, e a sessão permanece aberta até encerramento manual.
- **SC-006**: Sessão de teste encerrada (manual) com ≥1 gap inclui a contagem de gaps no aviso final de sessão.
- **SC-007**: Artefatos de áudio/metadados fechados antes do gap permanecem legíveis e inalterados após a recuperação.

## Assumptions

- Alertas mid-session usam webhook HTTP configurável; o bridge para Telegram (ou outro destino) é responsabilidade do monitor externo já existente — o Cronista não embute Bot API Telegram neste ciclo.
- O teste de aceite pode forçar desconexão completa do canal durante gravação (ou injeção equivalente de falhas de decriptação) para simular o incidente sem depender de WebSocket 1006 espontâneo.
- Defaults de configuração da demanda são adequados para sessão típica de RPG (vários participantes, horas); cooldown pós-recuperação default 60s; validação pós-connect default 30s.
- Contratos existentes (`session.json`, `speaking_log.jsonl`, layout de `.ogg`) permanecem; `recording_gaps.jsonl` é artefato **aditivo**.
- Não é possível recuperar áudio do intervalo do gap; o valor está em detectar, recuperar e documentar o buraco.
- Esgotar tentativas de reconexão: sair do voz + alerta crítico; sessão permanece aberta para o operador.

## Out of Scope

- Recuperar o áudio perdido durante o gap.
- Reimplementar negociação/rotação de chaves DAVE em baixo nível.
- Prevenir a causa de rede (ex.: WebSocket 1006) — apenas detectar e recuperar a consequência (chave/captura quebrada).
- Integração nativa com Bot API Telegram dentro do processo Cronista.
- Alterar o pipeline whisper-service/n8n além do consumo eventual do novo artefato de gaps (integração no workflow de transcrição fica para evolução futura, salvo leitura humana do arquivo).

## Dependencies

- Bot Cronista em gravação ativa (conexão de voz + sink/gravação).
- URL de webhook mid-session configurável no deploy (monitor externo → Telegram ou equivalente).
- Biblioteca de voz capaz de `disconnect` completo e novo `connect` no canal.
