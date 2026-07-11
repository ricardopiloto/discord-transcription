---
document: Product Brief
project: Cronista (nome provisório)
autor: Mary (PO Virtual) + Ricardo
data: 2026-07-10
escopo: Fase 1 — bot de captura de voz (exclui pipeline n8n/Whisper/RAG, já especificados separadamente)
---

# PRD — Bot de Captura de Voz para Sessões de RPG

## 1. Problem statement

Ricardo mestra uma campanha de WFRP4e via Foundry VTT com um grupo regular, usando Discord como canal de voz. Não existe hoje nenhum registro estruturado do que acontece durante as sessões — o conteúdo narrado, os diálogos e os eventos da mesa só existem na memória dos jogadores. Isso cria duas dores:

1. **Perda de contexto para automações já existentes** — o bot Bertroldo (RAG) e o pipeline de geração de episódios do blog (Eber Saltbock) dependem de um registro textual da sessão que hoje não existe de forma automática.
2. **Fricção manual** — sem captura automática, alimentar essas ferramentas exigiria transcrição manual, o que não escala com a cadência semanal/quinzenal das sessões.

O bot de captura resolve a ponta de entrada desse pipeline: transformar o áudio ao vivo do canal de voz em arquivos gravados, organizados e prontos para transcrição posterior.

## 2. Proposta e escopo do MVP

Um bot Discord (Node.js) dedicado — **não** o Robigode — que entra no canal de voz da sessão, grava o áudio de cada jogador separadamente, e avisa um sistema externo (n8n) quando a sessão termina, com os metadados necessários para o pipeline de transcrição.

### Funcionalidades incluídas (Fase 1)

| # | Funcionalidade | Descrição |
|---|---|---|
| F1 | Entrar no canal de voz | Via comando (`!cronista entrar`) ou automaticamente ao detectar o GM entrando num canal configurado |
| F2 | Captura de áudio por jogador | Assina o stream de cada usuário que fala, grava em arquivos separados por pessoa |
| F3 | Segmentação por fala (utterances) | Cada "turno de fala" vira um arquivo próprio, delimitado por silêncio, com timestamps relativos ao início da sessão |
| F4 | Metadados de sessão | Gera um arquivo de sessão com participantes, horário de início/fim, canal, servidor |
| F5 | Encerramento de sessão | Detecta quando o canal fica vazio (ou via comando manual) e finaliza a gravação |
| F6 | Notificação via webhook | Dispara um POST para o n8n com o payload da sessão encerrada, pronto para o pipeline de transcrição |
| F7 | Coexistência com o Robigode | Roda como processo/serviço independente; não interfere na reprodução de música no mesmo canal |

### Fora de escopo nesta fase (não-objetivos)

- Transcrição (fica no n8n/Whisper, já especificado)
- Geração de resumo/RAG (fica no Bertroldo/ChromaDB)
- Interface visual/dashboard
- Suporte a múltiplas sessões simultâneas no mesmo servidor Discord
- Recuperação de gravação em caso de crash do bot no meio da sessão (ver Perguntas em aberto)
- Diarização por IA — não é necessária, pois o Discord já entrega áudio segmentado por usuário

## 3. Usuários-alvo e casos de uso

**Usuário primário:** Ricardo, como GM, operando o bot antes/depois da sessão.
**Usuários indiretos:** os jogadores do grupo, cujas vozes são gravadas (cientes e de acordo, conforme já combinado).

**Caso de uso principal:** GM inicia a sessão de RPG no Discord → aciona o Cronista → joga normalmente por 3-4h → encerra o canal → o bot finaliza a gravação e notifica o pipeline de transcrição automaticamente, sem intervenção manual adicional.

## 4. Especificação técnica detalhada

### 4.1 Stack

- **Runtime:** Node.js + `discord.js` v14 + `@discordjs/voice`
- **Decodificação de áudio:** `prism-media` (Opus)
- **Deploy:** processo systemd independente em `/opt/apps/cronista/`, seguindo o mesmo padrão do Bertroldo (venv/serviço próprio, usuário `adminvtt`)

### 4.2 Estrutura de dados em disco

```
/opt/apps/cronista/recordings/
  {session_id}/
    session.json
    speaking_log.jsonl
    {discord_user_id}/
      0001.ogg
      0002.ogg
      0003.ogg
      ...
```

- **`session_id`**: formato `YYYYMMDD-HHmmss` baseado no horário de início da sessão (ex: `20260710-2201`), gerado no relógio do servidor.
- **`{discord_user_id}/NNNN.ogg`**: um arquivo por *utterance* (turno de fala contínuo) daquele usuário, numerado sequencialmente. Contém os pacotes Opus recebidos do Discord, empacotados diretamente em um container Ogg (sem re-encode, usando `prism-media`'s `OggLogicalBitstream`) — preserva qualidade e poupa CPU.
- **Delimitação de utterance:** usa `EndBehaviorType.AfterSilence` do `@discordjs/voice`, com `duration: 1000` (1s de silêncio fecha o arquivo atual e abre o próximo na próxima fala).

### 4.3 `session.json` (schema)

```json
{
  "session_id": "20260710-2201",
  "guild_id": "string",
  "channel_id": "string",
  "started_at": "2026-07-10T22:01:00Z",
  "ended_at": "2026-07-10T23:58:00Z",
  "participants": [
    { "user_id": "string", "display_name": "string", "utterance_count": 42 }
  ]
}
```

### 4.4 `speaking_log.jsonl` (uma linha por utterance, formato JSON Lines)

```json
{"user_id": "123456789", "seq": 1, "file": "123456789/0001.ogg", "start_ms": 4210, "end_ms": 7890, "duration_ms": 3680}
```

- `start_ms` / `end_ms`: milissegundos relativos a `session.started_at` — é isso que permite ao pipeline de transcrição (n8n) intercalar as falas de diferentes jogadores em ordem cronológica.

### 4.5 Contrato do webhook para o n8n

Disparado uma única vez, ao final da sessão (F5), método `POST`, `Content-Type: application/json`:

```json
{
  "session_id": "20260710-2201",
  "guild_id": "string",
  "channel_id": "string",
  "started_at": "2026-07-10T22:01:00Z",
  "ended_at": "2026-07-10T23:58:00Z",
  "recordings_path": "/opt/apps/cronista/recordings/20260710-2201",
  "session_json_path": "/opt/apps/cronista/recordings/20260710-2201/session.json",
  "speaking_log_path": "/opt/apps/cronista/recordings/20260710-2201/speaking_log.jsonl",
  "participants": [
    { "user_id": "123456789", "display_name": "Ricardo", "utterance_count": 42 }
  ]
}
```

- **URL do webhook:** configurável via variável de ambiente `N8N_WEBHOOK_URL` (não hardcoded no código).
- **Retry:** se o POST falhar (n8n fora do ar), o bot tenta novamente com backoff exponencial (3 tentativas) e, se persistir, grava um marcador `webhook_failed: true` em `session.json` para reprocessamento manual posterior.

### 4.6 Comandos do bot (MVP)

| Comando | Efeito |
|---|---|
| `!cronista entrar` | Bot entra no canal de voz do autor do comando e inicia a gravação |
| `!cronista encerrar` | Finaliza a sessão manualmente, mesmo com o canal ainda ocupado |
| `!cronista status` | Retorna se está gravando, há quanto tempo, quantos participantes |

Encerramento automático (F5) também ocorre se o canal ficar vazio por um período configurável (ex: 5 minutos), evitando depender só do comando manual.

### 4.7 Coexistência com o Robigode

Cada bot mantém sua própria `VoiceConnection` independente (conexão de voz própria, via token de bot próprio). Não há necessidade de coordenação entre eles — o Discord permite múltiplas conexões de bot simultâneas no mesmo canal.

## 5. Métricas de sucesso

- **Cobertura de captura:** ≥95% das falas da sessão presentes como arquivos `.ogg` válidos (validação manual em sessões piloto, comparando com percepção do GM).
- **Atribuição correta de autor:** 100% — garantido estruturalmente pelo isolamento de stream por usuário do Discord (não depende de acurácia de modelo).
- **Confiabilidade do webhook:** o n8n recebe a notificação de fim de sessão em 100% das sessões de teste, sem intervenção manual.
- **Estabilidade:** o bot roda uma sessão completa (3-4h) sem crash ou vazamento de memória perceptível.

## 6. Restrições, não-objetivos e perguntas em aberto

### Restrições
- Hardware do servidor (Kron Mini K1) já está sob carga com Foundry/Bertroldo/n8n/Odysseus — a gravação deve ser leve o suficiente (I/O, não CPU) para não competir por recursos durante a sessão ao vivo.
- Consentimento do grupo já é um pré-requisito assumido, não parte do escopo técnico deste PRD.

### Não-objetivos (reforço)
- Transcrição, resumo e ingestão em RAG — fora deste bot, tratados no pipeline n8n já especificado.

### Perguntas em aberto
1. **Nome definitivo do bot** — "Cronista" ou "Escriba"?
2. **Início automático vs. manual** — vale detectar automaticamente quando o GM entra num canal específico, ou o comando manual (`!cronista entrar`) é suficiente para o MVP?
3. **Recuperação de crash** — se o processo cair no meio da sessão, os arquivos já gravados ficam íntegros (cada utterance é um arquivo fechado), mas a sessão não é finalizada automaticamente nem o webhook é disparado. Vale um comando de recuperação (`!cronista retomar {session_id}`) para fechar manualmente uma sessão órfã, ou isso fica para uma fase futura?
4. **Retenção do áudio bruto** — quem/quando deleta os `.ogg` após a transcrição ser confirmada como boa? Fica a cargo do workflow n8n ou o próprio Cronista tem uma rotina de limpeza por idade de arquivo?
