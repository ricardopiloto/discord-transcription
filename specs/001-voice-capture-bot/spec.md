# Feature Specification: Bot de Captura de Voz para Sessões de RPG

**Feature Branch**: `001-voice-capture-bot`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "Leia o documento docs/PRD-bot-cronista-transcricao.md — bot Discord dedicado que captura áudio de sessões de RPG por jogador, segmenta por turnos de fala, persiste metadados de sessão e notifica pipeline externo de transcrição ao encerrar."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Iniciar captura da sessão (Priority: P1)

Como GM, quero acionar o bot para entrar no canal de voz da mesa e começar a gravar, para que o conteúdo da sessão seja registrado sem exigir configuração técnica durante o jogo.

**Why this priority**: Sem início de captura não há valor algum; é o ponto de entrada de todo o pipeline de transcrição e automações downstream (blog, RAG).

**Independent Test**: GM entra em um canal de voz, emite o comando de início e verifica que o bot confirma gravação ativa com identificador de sessão. Entregável: sessão criada com horário de início registrado.

**Acceptance Scenarios**:

1. **Given** o GM está em um canal de voz e nenhuma sessão está ativa, **When** emite o comando de início, **Then** o bot entra no canal, confirma o início da gravação e cria uma nova sessão com identificador único baseado no horário de início.
2. **Given** já existe uma sessão em andamento, **When** alguém tenta iniciar outra gravação, **Then** o bot informa que já está gravando e não inicia sessão duplicada.
3. **Given** o autor do comando não está em canal de voz, **When** emite o comando de início, **Then** o bot orienta o usuário a entrar em um canal antes de tentar novamente.

---

### User Story 2 - Capturar áudio por jogador e segmentar por fala (Priority: P1)

Como GM, quero que cada jogador tenha suas falas gravadas separadamente e divididas em turnos naturais de fala, para que a transcrição posterior possa atribuir corretamente quem disse o quê e reconstruir a ordem cronológica da mesa.

**Why this priority**: A captura segmentada por pessoa é o diferencial do produto frente a uma gravação monolítica; alimenta diretamente qualidade do texto e das automações que dependem dele.

**Independent Test**: Durante uma sessão de teste com dois ou mais participantes falando alternadamente, verificar que existem arquivos de áudio distintos por jogador e que cada pausa prolongada entre falas gera um novo segmento, com registro de timestamps relativos ao início da sessão.

**Acceptance Scenarios**:

1. **Given** uma sessão ativa com múltiplos participantes no canal, **When** um jogador fala, **Then** o áudio desse jogador é capturado em arquivo(s) associados exclusivamente a ele.
2. **Given** um jogador conclui um turno de fala e permanece em silêncio por aproximadamente um segundo, **When** volta a falar, **Then** a nova fala é registrada como segmento separado do anterior, com numeração sequencial.
3. **Given** um jogador entra no canal no meio da sessão, **When** fala pela primeira vez, **Then** passa a constar como participante da sessão e suas falas são capturadas a partir desse momento.
4. **Given** segmentos gravados durante a sessão, **When** a sessão é consultada, **Then** cada segmento possui timestamp de início e fim relativos ao início da sessão, permitindo ordenação cronológica entre jogadores diferentes.

---

### User Story 3 - Encerrar sessão e acionar pipeline de transcrição (Priority: P1)

Como GM, quero que a sessão seja finalizada automaticamente ou manualmente e que o sistema de transcrição seja notificado com todos os metadados necessários, para que o processamento ocorra sem trabalho manual após o jogo.

**Why this priority**: Fechar o ciclo e disparar o pipeline é o objetivo de negócio principal — transformar áudio ao vivo em insumo pronto para transcrição.

**Independent Test**: Encerrar uma sessão de teste (manual ou por canal vazio) e verificar que metadados de sessão, log de falas e notificação externa são produzidos corretamente.

**Acceptance Scenarios**:

1. **Given** uma sessão ativa, **When** o GM emite o comando de encerramento, **Then** a gravação para, horário de fim é registrado, arquivos de sessão são finalizados e o pipeline externo recebe notificação única com identificador da sessão, participantes e localização dos artefatos gravados.
2. **Given** uma sessão ativa e o canal de voz fica sem ninguém por um período configurável (padrão: 5 minutos), **When** o tempo expira, **Then** a sessão é encerrada automaticamente com o mesmo comportamento de finalização e notificação.
3. **Given** a notificação externa falha na primeira tentativa, **When** o serviço de destino permanece indisponível após novas tentativas, **Then** a sessão é marcada como falha de notificação nos metadados, preservando gravações para reprocessamento manual posterior.
4. **Given** uma sessão encerrada com sucesso, **When** o pipeline externo recebe a notificação, **Then** o payload contém identificador da sessão, servidor, canal, horários de início/fim, lista de participantes com contagem de segmentos de fala e referências aos artefatos persistidos.

---

### User Story 4 - Consultar status durante a sessão (Priority: P2)

Como GM, quero verificar se a gravação está ativa, há quanto tempo e quantos participantes foram registrados, para ter confiança de que a sessão está sendo capturada durante partidas longas (3–4 horas).

**Why this priority**: Reduz ansiedade operacional em sessões longas sem exigir inspeção manual de arquivos em disco.

**Independent Test**: Durante sessão ativa, emitir comando de status e validar resposta com duração, identificador de sessão e contagem de participantes.

**Acceptance Scenarios**:

1. **Given** uma sessão ativa, **When** o GM consulta status, **Then** recebe confirmação de gravação, identificador da sessão, duração decorrida e número de participantes registrados.
2. **Given** nenhuma sessão ativa, **When** alguém consulta status, **Then** recebe mensagem informando que não há gravação em andamento.

---

### User Story 5 - Coexistir com bot de música no mesmo canal (Priority: P2)

Como GM, quero usar o bot de música (Robigode) e o bot de captura simultaneamente no mesmo canal de voz, para manter a ambientação sonora da mesa sem sacrificar o registro da sessão.

**Why this priority**: A mesa já usa música durante o jogo; conflito entre bots inviabilizaria adoção na rotina real de campanha.

**Independent Test**: Conectar ambos os bots ao mesmo canal, reproduzir música e conduzir falas de teste; verificar que captura e reprodução funcionam sem interferência mútua.

**Acceptance Scenarios**:

1. **Given** o bot de música já está no canal de voz, **When** o bot de captura é iniciado, **Then** ambos permanecem conectados e operacionais.
2. **Given** ambos os bots estão no canal durante sessão ativa, **When** jogadores falam enquanto música toca, **Then** as falas continuam sendo capturadas por jogador sem exigir coordenação entre os bots.

---

### Edge Cases

- O que acontece quando apenas o bot permanece no canal (todos os jogadores saíram)? Após período configurável de canal vazio, a sessão encerra automaticamente.
- O que acontece se o bot cai no meio da sessão? Segmentos já fechados permanecem íntegros; a sessão não é finalizada nem notificada automaticamente (recuperação manual fica fora do escopo desta fase).
- O que acontece se duas sessões forem solicitadas no mesmo servidor? Apenas uma sessão ativa por servidor é suportada; tentativa de segunda sessão é rejeitada.
- O que acontece se o serviço externo de transcrição estiver offline no encerramento? Retentativas com intervalo crescente; falha persistente registra marcador nos metadados da sessão.
- O que acontece com jogadores que ficam mudo ou só escutam? Apenas quem fala gera segmentos; participantes sem fala podem não aparecer na lista até falarem.
- O que acontece em sessões de 3–4 horas contínuas? O bot deve permanecer estável sem degradação perceptível de desempenho ou consumo descontrolado de recursos.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST permitir que o GM inicie a captura de voz mediante comando explícito enquanto estiver em um canal de voz.
- **FR-002**: O sistema MUST impedir o início de uma nova sessão de gravação enquanto já existir sessão ativa no mesmo servidor.
- **FR-003**: O sistema MUST conectar-se ao canal de voz indicado pelo GM e permanecer conectado durante toda a sessão ativa.
- **FR-004**: O sistema MUST capturar áudio de forma isolada por participante que fala, sem misturar streams de jogadores diferentes no mesmo arquivo.
- **FR-005**: O sistema MUST segmentar a fala de cada participante em turnos contínuos, fechando um segmento após período configurável de silêncio (padrão: 1 segundo) e abrindo novo segmento na próxima fala.
- **FR-006**: O sistema MUST numerar segmentos de fala sequencialmente por participante dentro de cada sessão.
- **FR-007**: O sistema MUST registrar timestamps de início e fim de cada segmento relativos ao horário de início da sessão, em milissegundos.
- **FR-008**: O sistema MUST gerar identificador único de sessão baseado no horário de início (formato legível por data e hora).
- **FR-009**: O sistema MUST persistir metadados de sessão contendo: identificador, servidor, canal, horário de início, horário de fim (quando encerrada), e lista de participantes com nome exibido e contagem de segmentos de fala.
- **FR-010**: O sistema MUST persistir log cronológico de segmentos de fala (um registro por segmento) associando participante, sequência, arquivo correspondente e timestamps.
- **FR-011**: O sistema MUST permitir encerramento manual da sessão mediante comando, independentemente de jogadores ainda estarem no canal.
- **FR-012**: O sistema MUST encerrar automaticamente a sessão quando o canal de voz permanecer vazio por período configurável (padrão: 5 minutos).
- **FR-013**: Ao encerrar sessão, o sistema MUST enviar notificação única ao pipeline externo de transcrição com payload contendo identificador da sessão, contexto (servidor/canal), horários, participantes e referências aos artefatos gravados.
- **FR-014**: O sistema MUST permitir configurar a URL de destino da notificação externa sem expor esse valor fixo no código-fonte.
- **FR-015**: Se a notificação externa falhar, o sistema MUST realizar até 3 tentativas com intervalo crescente entre elas; persistindo falha, MUST marcar a sessão como falha de notificação nos metadados.
- **FR-016**: O sistema MUST responder a comando de status informando se há gravação ativa, identificador da sessão, duração decorrida e quantidade de participantes registrados.
- **FR-017**: O sistema MUST operar como serviço independente de outros bots da mesa, podendo compartilhar o mesmo canal de voz sem exigir coordenação entre eles.
- **FR-018**: O sistema MUST limitar-se a uma sessão de gravação simultânea por servidor Discord.
- **FR-019**: O sistema MUST registrar participantes conforme forem detectados falando durante a sessão, incluindo quem entrar no canal após o início.

### Key Entities

- **Sessão**: Representa uma partida de RPG gravada; atributos principais: identificador, servidor, canal, horários de início e fim, lista de participantes, indicador opcional de falha de notificação externa.
- **Participante**: Jogador ou GM cuja voz foi capturada; atributos: identificador do usuário, nome exibido, contagem de segmentos de fala na sessão.
- **Segmento de fala (utterance)**: Unidade mínima de áudio capturada — um turno contínuo de fala de um participante; atributos: sequência, arquivo de áudio, timestamps relativos de início/fim e duração.
- **Log de falas**: Sequência ordenável de registros de segmentos, permitindo reconstruir a linha do tempo da mesa cruzando múltiplos participantes.
- **Notificação de encerramento**: Mensagem única enviada ao pipeline externo ao final da sessão, consolidando metadados e referências aos artefatos produzidos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em sessões piloto, pelo menos 95% das falas percebidas pelo GM estão presentes como segmentos de áudio válidos e reproduzíveis.
- **SC-002**: 100% dos segmentos capturados são atribuídos ao participante correto (garantido pela separação estrutural por origem de áudio, sem dependência de inferência por IA).
- **SC-003**: Em 100% das sessões de teste encerradas normalmente, o pipeline externo recebe a notificação de fim de sessão sem intervenção manual do GM.
- **SC-004**: O bot completa sessões de 3–4 horas contínuas sem interrupção, crash ou degradação perceptível de desempenho durante a partida.
- **SC-005**: O GM consegue iniciar a captura em menos de 30 segundos após entrar no canal de voz (comando único, sem passos adicionais de configuração).
- **SC-006**: Após encerramento bem-sucedido, o GM não precisa realizar nenhuma ação manual adicional para que o pipeline de transcrição tenha acesso aos metadados e localização dos arquivos gravados.

## Assumptions

- O nome provisório **Cronista** será usado até decisão formal entre "Cronista" e "Escriba"; comandos e mensagens do bot seguirão o prefixo acordado (`!cronista`).
- **Início manual** via comando é suficiente para o MVP; detecção automática ao GM entrar em canal configurado fica como melhoria futura, não bloqueante para esta entrega.
- **Recuperação de sessão órfã** após crash do bot (comando de retomar/fechar manualmente) está fora do escopo desta fase; segmentos já fechados permanecem utilizáveis manualmente.
- **Retenção e exclusão** de áudio bruto após transcrição confirmada ficam a cargo do workflow externo (n8n), não deste bot.
- **Transcrição, resumo e ingestão em RAG** são responsabilidade de sistemas downstream já especificados; este bot entrega apenas captura organizada e notificação.
- **Consentimento** do grupo para gravação de voz já foi obtido; não faz parte do escopo desta feature implementar fluxo de consentimento.
- **Uma sessão por servidor** atende à cadência atual da campanha (sessões semanais/quinzenais, uma mesa por servidor).
- O servidor de hospedagem já opera outros serviços da mesa; a captura deve priorizar operações leves de disco sobre processamento intensivo, para não competir com a sessão ao vivo.
- O bot de música (Robigode) utiliza credencial e conexão de voz próprias; coexistência depende apenas de múltiplas conexões simultâneas permitidas pela plataforma.

## Out of Scope

- Transcrição de áudio para texto
- Geração de resumos ou ingestão em base de conhecimento (RAG)
- Interface visual ou dashboard de administração
- Múltiplas sessões simultâneas no mesmo servidor Discord
- Recuperação automática ou comando de retomada após crash mid-session
- Diarização por inteligência artificial (identificação de falante por modelo)
- Rotina de limpeza ou política de retenção de arquivos de áudio bruto
