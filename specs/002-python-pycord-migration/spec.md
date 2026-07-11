# Feature Specification: Migração do Cronista para Stack Python/Py-Cord

**Feature Branch**: `002-python-pycord-migration`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "Leia o documento docs/PRD-bot-cronista-transcricao_v2.md, veja as diferenças entre a implementação atual e a nova, e crie as propostas, estamos alterando toda a stack de tecnologia."

## Context & Change Proposal

O PRD v2 mantém o objetivo de produto do Cronista: capturar áudio de sessões de RPG no Discord, separar falas por jogador, gerar metadados e notificar o pipeline n8n ao final. A mudança central é operacional e de confiabilidade: a implementação atual foi construída em Node.js com `discord.js`, `@discordjs/voice` e `prism-media`, mas o PRD v2 determina uma migração para Python 3.11+ com `py-cord` por risco confirmado na recepção de áudio sob o protocolo DAVE do Discord.

### Diferenças identificadas entre implementação atual e PRD v2

- **Stack de runtime**: atual usa Node.js/TypeScript; PRD v2 propõe Python 3.11+.
- **Biblioteca Discord**: atual usa `discord.js` + `@discordjs/voice`; PRD v2 propõe `py-cord`, com suporte de recepção por sinks.
- **Recepção de áudio**: atual depende de receiver do `@discordjs/voice`, apontado como instável para recepção sob DAVE; PRD v2 exige validar e usar caminho que receba áudio de forma confiável no ambiente real.
- **Gravação de utterances**: atual faz pipeline Opus para Ogg por stream; PRD v2 requer sink customizado que escreva incrementalmente em disco, evitando o comportamento de buffer integral de `WaveSink`.
- **Deploy**: atual usa `node dist/index.js`; PRD v2 exige venv Python próprio em `/opt/apps/cronista/`, separado do venv do Bertroldo por conflito de namespace `discord`.
- **Artefatos de sessão**: permanecem compatíveis (`session.json`, `speaking_log.jsonl`, `{user_id}/NNNN.ogg`, webhook n8n).

### Propostas

**Proposta recomendada — migração completa para Python/Py-Cord**

Recriar o runtime do Cronista em Python mantendo os mesmos contratos externos, comandos de usuário, estrutura de arquivos e webhook. A implementação Node atual passa a ser referência funcional e não base de produção.

**Proposta de mitigação — spike obrigatório antes do rewrite completo**

Antes da migração completa, executar um bot mínimo que entra no canal, grava alguns minutos de áudio real e comprova integridade dos arquivos no ambiente do servidor. Esse spike valida o requisito mais arriscado: recepção de áudio sob DAVE.

**Proposta fallback — manter Node apenas se o risco DAVE desaparecer**

Se o spike demonstrar que a recepção Node atual foi corrigida no ambiente real e atende os critérios de captura, o time pode reavaliar a migração. A decisão padrão desta spec continua sendo Python/Py-Cord, pois o PRD v2 declara a mudança de stack como direção atual.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Decidir stack com evidência real (Priority: P1)

Como responsável pelo Cronista, quero validar a recepção de áudio no ambiente real antes de reimplementar o bot inteiro, para evitar investir em uma stack que não capture voz de forma confiável durante sessões reais.

**Why this priority**: O problema central do PRD v2 é risco de recepção de áudio sob DAVE. Sem uma validação mínima, a migração pode repetir o mesmo problema da stack atual.

**Independent Test**: Rodar um bot mínimo no servidor alvo, conectá-lo a um canal de voz real, capturar alguns minutos com dois participantes e reproduzir os arquivos gerados confirmando áudio íntegro e autoria correta.

**Acceptance Scenarios**:

1. **Given** um canal de voz real com pelo menos dois participantes, **When** o bot mínimo de validação entra e grava alguns minutos, **Then** os arquivos produzidos contêm áudio audível dos participantes esperados.
2. **Given** a validação mínima falha em receber áudio, **When** o resultado é analisado, **Then** a migração completa é bloqueada até haver diagnóstico documentado ou alternativa aprovada.
3. **Given** a validação mínima passa, **When** o time inicia o rewrite, **Then** a nova stack é tratada como caminho de implementação principal.

---

### User Story 2 - Preservar a experiência do GM (Priority: P1)

Como GM, quero continuar usando os mesmos comandos e o mesmo fluxo operacional do Cronista, para que a mudança de stack não altere minha rotina antes, durante ou depois da sessão.

**Why this priority**: A migração é técnica; o valor para o usuário depende de manter o fluxo já especificado e esperado.

**Independent Test**: Em uma sessão de teste, executar `!cronista entrar`, `!cronista status` e `!cronista encerrar` e verificar que as respostas e efeitos observáveis continuam equivalentes à versão anterior.

**Acceptance Scenarios**:

1. **Given** o GM está em um canal de voz e nenhuma sessão está ativa, **When** usa `!cronista entrar`, **Then** o bot entra no canal e confirma o início da sessão.
2. **Given** há sessão ativa, **When** o GM usa `!cronista status`, **Then** recebe duração, identificador da sessão e quantidade de participantes registrados.
3. **Given** há sessão ativa, **When** o GM usa `!cronista encerrar`, **Then** a sessão é finalizada, metadados são persistidos e o pipeline externo é notificado.

---

### User Story 3 - Reimplementar captura sem bufferizar sessão inteira (Priority: P1)

Como operador do servidor, quero que a nova captura escreva utterances incrementalmente em disco, para que sessões de 3–4 horas não acumulem áudio inteiro em memória.

**Why this priority**: O PRD v2 alerta que o sink padrão bufferiza a sessão inteira, o que é incompatível com sessões longas e servidor sob carga.

**Independent Test**: Executar uma gravação prolongada de teste com falas intermitentes e verificar que arquivos por utterance são criados durante a sessão, antes do encerramento, sem crescimento contínuo de memória proporcional ao tempo total.

**Acceptance Scenarios**:

1. **Given** uma sessão ativa com falas intermitentes, **When** um participante termina um turno de fala, **Then** o segmento correspondente é fechado e fica disponível em disco sem aguardar o fim da sessão.
2. **Given** uma sessão de teste prolongada, **When** a memória do processo é monitorada, **Then** não há crescimento linear compatível com armazenamento de todo o áudio em RAM.
3. **Given** vários participantes falam alternadamente, **When** os segmentos são inspecionados, **Then** cada arquivo permanece associado ao participante correto.

---

### User Story 4 - Manter contratos de integração e arquivos (Priority: P1)

Como mantenedor do pipeline n8n/Whisper/RAG, quero que a migração preserve o formato dos arquivos, metadados e webhook, para que os sistemas downstream continuem funcionando sem reescrita.

**Why this priority**: O Cronista é a ponta de entrada de automações existentes. Quebrar contratos downstream aumentaria o escopo e atrasaria o uso real.

**Independent Test**: Encerrar uma sessão gravada pela nova stack e comparar `session.json`, `speaking_log.jsonl`, organização de áudio e payload do webhook com os contratos da spec anterior.

**Acceptance Scenarios**:

1. **Given** uma sessão finalizada na nova stack, **When** `session.json` é lido, **Then** contém identificador, servidor, canal, início, fim e participantes com contagem de utterances.
2. **Given** há utterances gravadas, **When** `speaking_log.jsonl` é lido, **Then** cada linha contém usuário, sequência, arquivo, início, fim e duração relativa ao início da sessão.
3. **Given** a sessão é encerrada, **When** o webhook é enviado, **Then** o payload preserva os mesmos campos esperados pelo n8n.

---

### User Story 5 - Fazer cutover operacional seguro (Priority: P2)

Como operador do servidor, quero substituir a versão Node pela versão Python com deploy isolado e reversível, para reduzir risco de conflito com Bertroldo, Robigode e demais serviços da máquina.

**Why this priority**: O PRD v2 exige venv próprio e processo systemd separado; o cutover precisa ser claro para evitar conflito de dependências e indisponibilidade durante sessão.

**Independent Test**: Instalar a nova versão em ambiente de staging ou janela controlada, iniciar serviço isolado, validar comandos básicos e confirmar que o serviço antigo não está competindo pelo mesmo token/conexão.

**Acceptance Scenarios**:

1. **Given** a nova versão está instalada, **When** o serviço inicia, **Then** usa ambiente isolado próprio e não depende do venv do Bertroldo.
2. **Given** o serviço novo está ativo, **When** uma sessão de teste é executada, **Then** não há interferência com Robigode no mesmo canal.
3. **Given** o cutover falha antes da primeira sessão real, **When** o operador executa rollback, **Then** há um caminho documentado para restaurar a versão anterior ou adiar a migração.

---

### Edge Cases

- Se o spike Python não receber áudio sob DAVE, a migração completa deve parar e registrar o resultado antes de qualquer rewrite amplo.
- Se a versão Node passar a receber áudio corretamente no ambiente real, a decisão de migração pode ser reavaliada, mas isso precisa de evidência equivalente à validação Python.
- Se o sink customizado acumular áudio em memória, a implementação deve ser rejeitada mesmo que gere arquivos corretos ao final.
- Se o webhook n8n receber campos diferentes do contrato anterior, a migração não está completa.
- Se o venv Python compartilhar namespace `discord` com o Bertroldo, o deploy deve ser considerado inválido.
- Se uma sessão cair no meio, segmentos já fechados devem permanecer íntegros; recuperação automática continua fora do escopo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O projeto MUST produzir uma decisão documentada de stack baseada em validação real de recepção de áudio no ambiente do Discord usado pela mesa.
- **FR-002**: O projeto MUST executar um spike mínimo de captura antes da reimplementação completa, comprovando que áudio de pelo menos dois participantes é recebido e reproduzível.
- **FR-003**: A nova implementação MUST preservar os comandos de usuário `!cronista entrar`, `!cronista status` e `!cronista encerrar`.
- **FR-004**: A nova implementação MUST preservar a estrutura de diretórios e nomes de arquivos por sessão e por participante.
- **FR-005**: A nova implementação MUST gravar utterances por participante sem misturar áudio de usuários diferentes.
- **FR-006**: A nova implementação MUST fechar segmentos por silêncio configurável, com valor padrão de aproximadamente 1 segundo.
- **FR-007**: A nova implementação MUST escrever segmentos em disco incrementalmente durante a sessão, não apenas no encerramento.
- **FR-008**: A nova implementação MUST manter `session.json` compatível com o contrato existente.
- **FR-009**: A nova implementação MUST manter `speaking_log.jsonl` compatível com o contrato existente.
- **FR-010**: A nova implementação MUST manter o webhook de encerramento compatível com o contrato existente do n8n.
- **FR-011**: A nova implementação MUST manter retry de webhook com marcação de falha persistente nos metadados da sessão.
- **FR-012**: A nova implementação MUST manter encerramento automático quando o canal de voz ficar vazio por período configurável.
- **FR-013**: A nova implementação MUST rodar como serviço independente com ambiente Python isolado próprio, separado do Bertroldo.
- **FR-014**: A nova implementação MUST manter coexistência com Robigode no mesmo canal de voz.
- **FR-015**: O cutover MUST incluir instruções de operação e rollback suficientes para uma janela controlada antes da primeira sessão real.
- **FR-016**: A implementação Node atual MUST ser tratada como substituível; código, documentação e scripts de deploy antigos devem ser removidos ou marcados como legados para evitar ambiguidade operacional.

### Key Entities

- **Proposta de Migração**: Decisão documentada que descreve caminho recomendado, mitigação por spike e fallback possível.
- **Spike de Recepção de Áudio**: Validação curta que prova se a stack escolhida recebe áudio real sob DAVE no servidor/canal usados pelo grupo.
- **Sessão de Gravação**: Partida capturada pelo Cronista, com início, fim, canal, servidor, participantes e artefatos.
- **Utterance**: Segmento individual de fala por usuário, persistido incrementalmente em disco.
- **Contrato Downstream**: Conjunto de arquivos e payloads consumidos pelo pipeline n8n/Whisper/RAG.
- **Cutover Operacional**: Passagem controlada do serviço antigo para o novo, incluindo ambiente isolado, systemd e rollback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O spike de recepção grava pelo menos 3 minutos de áudio real com 2 ou mais participantes, com arquivos reproduzíveis e autoria correta.
- **SC-002**: Em sessão piloto da nova stack, pelo menos 95% das falas percebidas pelo GM aparecem como segmentos de áudio válidos.
- **SC-003**: A memória do processo permanece estável durante teste prolongado de pelo menos 30 minutos, sem crescimento linear proporcional à duração total da sessão.
- **SC-004**: 100% dos campos esperados em `session.json`, `speaking_log.jsonl` e webhook permanecem compatíveis com a spec anterior.
- **SC-005**: O GM consegue executar os três comandos principais sem mudança de fluxo operacional em comparação à versão anterior.
- **SC-006**: O serviço novo sobe em ambiente isolado e não compartilha dependências Python com o Bertroldo.
- **SC-007**: A nova versão completa uma sessão piloto de 3–4 horas sem crash ou perda perceptível de áudio.

## Assumptions

- A direção preferida é migrar para Python/Py-Cord, conforme PRD v2, salvo evidência forte em contrário após spike real.
- A implementação Node atual foi útil como protótipo de contratos e fluxo, mas não deve ser considerada suficiente para produção enquanto houver risco de recepção sob DAVE.
- A estrutura de arquivos, nomes de comandos e payload n8n são contratos estáveis e devem ser preservados.
- O nome provisório continua sendo **Cronista**.
- Início manual por comando continua sendo suficiente para o MVP; auto-start permanece fora do caminho crítico.
- Recuperação automática de sessão órfã após crash continua fora do escopo desta fase.
- Retenção e limpeza de áudio bruto continuam responsabilidade do workflow externo.
- O consentimento do grupo para gravação já existe e não será implementado como fluxo de produto nesta feature.

## Out of Scope

- Alterar o pipeline de transcrição, resumo ou RAG.
- Adicionar dashboard visual.
- Suportar múltiplas sessões simultâneas no mesmo servidor.
- Implementar rotina de retenção/limpeza de áudio bruto.
- Implementar recuperação automática de crash mid-session.
- Criar diarização por IA.
- Manter duas implementações produtivas em paralelo por tempo indefinido.
