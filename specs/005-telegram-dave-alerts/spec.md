# Feature Specification: Notificação Telegram direta para alertas DAVE Recovery

**Feature Branch**: `005-telegram-dave-alerts`

**Created**: 2026-08-08

**Status**: Draft

**Input**: User description: "Vamos implementar a notificação de falha (DAVE Recovery) diretamente pelo telegram, então temos que configurar a API, Token e ChatID." + modelos de mensagem oficiais da demanda DAVE (detectar / recuperar / esgotar tentativas).

## Context

A feature `004-dave-decrypt-recovery` já detecta falhas de decriptação DAVE, reconecta o canal e registra gaps. Os alertas mid-session (detecção, recuperação e falha crítica) hoje saem por webhook HTTP genérico (`CRONISTA_ALERT_WEBHOOK_URL`), com entrega ao Telegram a cargo de um monitor externo.

Esta feature muda o canal de entrega: o Cronista envia as mensagens de alerta DAVE Recovery **diretamente** ao Telegram, usando a API do Bot, com Token e Chat ID configuráveis no deploy — sem depender do bridge externo para esse fluxo. As mensagens saem **assim que o gap for detectado / resolvido / falhar** — não no fim da sessão. O webhook mid-session (`CRONISTA_ALERT_WEBHOOK_URL`) é **substituído** por este envio Telegram (não há dual-send).

## Clarifications

### Session 2026-08-08

- Q: Relação com `CRONISTA_ALERT_WEBHOOK_URL` → A: Telegram substitui o webhook mid-session (sem dual-send); remove/depreca a variável de webhook de alerta
- Q: Formato de `{duração_do_gap}` e `{horário}` → A: Duração legível (`2m 15s`); horário ISO-8601 UTC
- Q: Retentativas se o envio Telegram falhar → A: Até 3 tentativas com espera curta; depois log e segue
- Q: O envio do alerta atrasa o início da reconexão? → A: Não — reconexão inicia sem esperar o Telegram; alerta de detecção em paralelo

## Message Templates *(mandatory)*

Placeholders são substituídos em tempo de envio. O texto literal (incluindo emoji) MUST corresponder aos modelos abaixo, salvo a substituição dos placeholders.

| Evento | Modelo |
|--------|--------|
| Ao detectar | `⚠️ Cronista: falha de decriptação DAVE detectada no canal {channel}, tentando reconectar...` |
| Ao recuperar | `✅ Reconexão bem-sucedida, gravação retomada após {duração_do_gap}` |
| Ao esgotar tentativas | `🔴 Falha ao reconectar após {N} tentativas — gravação da sessão comprometida a partir de {horário}` |

**Placeholders**:

- `{channel}` — nome (ou identificação legível) do canal de voz da sessão
- `{duração_do_gap}` — duração do intervalo sem captura utilizável em formato legível `Xm Ys` (ex. `2m 15s`; se < 1 minuto, pode ser só `Ys`)
- `{N}` — número de tentativas de reconexão esgotadas
- `{horário}` — início do gap em ISO-8601 UTC (ex. `2026-08-08T22:15:00Z`)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receber alertas DAVE no Telegram em tempo real (Priority: P1)

Como operador/GM, quero receber no Telegram os avisos de detecção, recuperação e falha crítica da recuperação DAVE assim que ocorrem, para intervir durante a sessão sem olhar log do servidor nem manter um monitor webhook intermediário.

**Why this priority**: É o valor central da feature — alerta operacional direto no canal já usado pela mesa.

**Independent Test**: Com Token e Chat ID válidos configurados, disparar um ciclo controlado de recuperação DAVE (ou simular os três eventos de alerta) e verificar as mensagens no chat Telegram alvo antes do fim da sessão.

**Acceptance Scenarios**:

1. **Given** Token e Chat ID do Telegram configurados e gravação ativa, **When** o limiar de falha DAVE é atingido, **Then** a reconexão inicia sem aguardar o Telegram e o chat recebe o modelo de detecção com `{channel}` preenchido (envio em paralelo).
2. **Given** a reconexão teve sucesso, **When** a gravação retoma, **Then** o chat recebe exatamente o modelo de recuperação com `{duração_do_gap}` preenchido — ainda antes do fim da sessão.
3. **Given** as tentativas de reconexão se esgotaram sem sucesso, **When** o Cronista desiste, **Then** o chat recebe exatamente o modelo de falha crítica com `{N}` e `{horário}` preenchidos.

---

### User Story 2 - Configurar API, Token e Chat ID no deploy (Priority: P1)

Como operador de deploy, quero declarar a URL base da API do Bot, o Token e o Chat ID por configuração de ambiente, para apontar o Cronista ao bot/chat de monitoração sem alterar código.

**Why this priority**: Sem configuração explícita e documentada, a entrega direta não é operável nem segura.

**Independent Test**: Preencher as três configurações em ambiente de teste, reiniciar o bot e confirmar que um alerta de teste (ou o primeiro evento DAVE) chega ao chat esperado; omitir Token ou Chat ID e confirmar que o bot continua a recuperação/gaps sem travar.

**Acceptance Scenarios**:

1. **Given** URL base da API (ou default oficial), Token e Chat ID preenchidos, **When** um alerta mid-session DAVE é gerado, **Then** a mensagem é enviada usando essas credenciais/destino.
2. **Given** Token ou Chat ID ausente, **When** um alerta mid-session DAVE seria enviado, **Then** o Cronista registra em log que o alerta Telegram foi omitido e MUST continuar detecção, recuperação e registro de gaps.
3. **Given** URL base da API não informada, **When** o envio ocorre, **Then** o Cronista usa a URL oficial padrão da API do Bot Telegram.

---

### User Story 3 - Falha de entrega não compromete a gravação (Priority: P2)

Como operador, quero que uma API Telegram indisponível ou credencial inválida não interrompa a recuperação DAVE nem o encerramento da sessão, para priorizar captura sobre notificação.

**Why this priority**: Alerta é observabilidade; recuperação e gaps são o caminho crítico.

**Independent Test**: Apontar Token inválido ou API inalcançável, forçar evento de alerta e verificar que recuperação/gaps seguem e apenas o envio falha de forma registrada.

**Acceptance Scenarios**:

1. **Given** a API Telegram responde erro ou timeout, **When** o Cronista tenta enviar um alerta, **Then** a falha é registrada em log, a recuperação DAVE e o `recording_gaps.jsonl` seguem normalmente, e a sessão não é encerrada por causa do alerta.
2. **Given** Token ou Chat ID inválidos, **When** o envio falha, **Then** o Cronista MUST NOT registrar o valor do Token em logs (apenas indicação de falha de autenticação/envio).

---

### Edge Cases

- Token ou Chat ID ausentes → omitir envio Telegram; log claro; recuperação/gaps intactos.
- API Telegram lenta ou indisponível → até 3 tentativas com espera curta; se todas falharem, log e segue (recuperação/gaps não param).
- Alerta de detecção ainda em retry → reconexão já pode estar em andamento; falha/atraso do Telegram MUST NOT adiar o início do `disconnect`/`connect`.
- Chat ID de grupo vs privado → ambos válidos desde que o bot tenha permissão de enviar mensagens no destino.
- Múltiplos gaps na mesma sessão → cada evento (detecção / recuperação / falha crítica) gera sua própria mensagem Telegram.
- Webhook n8n de fim de sessão → permanece independente; esta feature não altera o aviso de sessão encerrada via n8n.
- `CRONISTA_ALERT_WEBHOOK_URL` configurada (legado) → ignorada / removida da configuração documentada; alertas DAVE saem só via Telegram.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O Cronista MUST enviar alertas mid-session de DAVE Recovery (detecção, recuperação bem-sucedida e falha crítica após esgotar tentativas) diretamente via API do Bot Telegram ao Chat ID configurado, assim que cada evento ocorrer — MUST NOT esperar o fim da sessão.
- **FR-011**: O início da reconexão completa MUST NOT aguardar a conclusão (nem os retries) do envio do alerta de detecção; o alerta de detecção MUST ser disparado em paralelo à recuperação.
- **FR-002**: O texto enviado MUST seguir os Message Templates desta spec (emoji + redação fixa), substituindo apenas `{channel}`, `{duração_do_gap}`, `{N}` e `{horário}` conforme o evento; `{duração_do_gap}` MUST usar formato legível `Xm Ys` (ou só segundos se < 1 min) e `{horário}` MUST ser ISO-8601 UTC.
- **FR-003**: Token do bot Telegram, Chat ID de destino e URL base da API do Bot MUST ser configuráveis por variáveis de ambiente.
- **FR-004**: Se a URL base da API não for informada, o Cronista MUST usar a URL oficial padrão da API do Bot Telegram.
- **FR-005**: Se Token ou Chat ID estiverem ausentes, o Cronista MUST omitir o envio Telegram, registrar a omissão em log, e MUST NOT interromper detecção, recuperação nem registro de gaps.
- **FR-006**: Em falha de rede, timeout ou erro da API Telegram, o Cronista MUST reintentar o envio até 3 tentativas com espera curta entre elas; se todas falharem, MUST registrar em log e MUST NOT impedir recuperação DAVE, persistência de gaps nem encerramento normal da sessão.
- **FR-007**: O valor do Token MUST NOT aparecer em logs de aplicação (nem em mensagens de erro verbosas).
- **FR-008**: O webhook n8n de fim de sessão (`N8N_WEBHOOK_URL`) MUST permanecer inalterado por esta feature.
- **FR-009**: O webhook mid-session (`CRONISTA_ALERT_WEBHOOK_URL`) MUST ser removido/deprecado: alertas DAVE Recovery MUST usar somente Telegram; MUST NOT haver dual-send nem fallback para esse webhook.
- **FR-010**: Documentação de deploy (exemplo de ambiente / README) MUST listar as novas variáveis de configuração Telegram, o comportamento quando estiverem ausentes, e MUST deixar de documentar `CRONISTA_ALERT_WEBHOOK_URL` como canal de alerta mid-session.

### Key Entities

- **Credencial Telegram**: Token do bot + Chat ID de destino + URL base da API (opcional com default oficial).
- **Alerta DAVE mid-session**: Mensagem operacional nos estados detecção, recuperação ou falha crítica, com texto conforme Message Templates, gerada pelo fluxo 004 e entregue via Telegram.
- **Resultado de envio**: Sucesso ou falha/omissão do envio, sem efeito sobre o estado da sessão de gravação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em teste controlado com Token e Chat ID válidos, 100% dos eventos DAVE disparados (detecção e recuperação, ou detecção e falha crítica) produzem no chat Telegram alvo, antes do fim da sessão, mensagens que batem com os Message Templates; recuperação inclui duração `Xm Ys` (ou só `Ys`) e falha crítica inclui `{horário}` em ISO-8601 UTC.
- **SC-002**: Com Token ou Chat ID ausentes, um ciclo completo de recuperação DAVE ainda registra o gap e completa detecção/recuperação; zero mensagens Telegram são esperadas.
- **SC-003**: Com API Telegram inacessível ou credencial inválida, após até 3 tentativas de envio a recuperação DAVE e o registro de gap concluem sem intervenção manual; a falha de envio aparece apenas no log operacional; a primeira tentativa de reconexão não fica bloqueada à espera do Telegram.
- **SC-004**: Operador consegue configurar URL base (ou aceitar o default), Token e Chat ID só por variáveis de ambiente, sem editar código, e a primeira mensagem de teste chega ao chat correto.
- **SC-005**: Inspeção dos logs de um envio (sucesso ou falha) não revela o Token completo.

## Assumptions

- Os três eventos mid-session já definidos em 004 (detecção, recuperação, falha crítica) são o conjunto a notificar; “notificação de falha DAVE Recovery” refere-se a esse canal de alerta, não só ao evento crítico.
- Existe (ou será criado) um bot Telegram e um chat/grupo de monitoração onde o bot pode enviar mensagens; reaproveitar o bot de monitoração já citado na demanda original é o caso preferido.
- A URL oficial padrão da API do Bot Telegram é adequada; override da URL base cobre Bot API local/self-hosted se necessário.
- Sessão-end via n8n e contagem de gaps no aviso final permanecem como em 004; esta feature só muda a entrega mid-session para Telegram direto (substituindo o webhook mid-session).
- Secrets ficam só em variáveis de ambiente do host/serviço (não em repositório).
- Não há requisito de manter compatibilidade com monitores que consumiam `CRONISTA_ALERT_WEBHOOK_URL`.

## Out of Scope

- Alterar a lógica de detecção, reconexão, cooldown ou formato de `recording_gaps.jsonl` (permanecem em 004).
- Notificar outros eventos do Cronista (início/fim de sessão, erros genéricos) via Telegram — apenas alertas DAVE Recovery mid-session.
- UI, botões inline, edição/ deleção de mensagens ou múltiplos Chat IDs.
- Substituir ou redesenhar o webhook n8n de fim de sessão.
- Hospedar ou provisionar o bot Telegram em si (criação do bot e obtenção de Token/Chat ID são manuais).

## Dependencies

- Feature 004 (DAVE decrypt recovery) entregando os eventos mid-session de alerta.
- Bot Telegram com Token válido e Chat ID onde o bot possa enviar mensagens.
- Acesso de rede do host do Cronista à URL base da API do Bot configurada.
