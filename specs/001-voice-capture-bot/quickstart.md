# Quickstart: Validação End-to-End

**Feature**: 001-voice-capture-bot  
**Purpose**: Provar que a captura de voz funciona de ponta a ponta antes de deploy em produção.

Referências: [spec.md](./spec.md) · [data-model.md](./data-model.md) · [contracts/](./contracts/)

---

## Prerequisites

1. **Bot Discord** criado no [Developer Portal](https://discord.com/developers/applications)
   - Intents habilitados: Server Members, Message Content, Voice
   - Token copiado para `.env`
2. **Node.js ≥ 20** instalado
3. **Canal de voz de teste** em servidor Discord com permissão do bot: Connect, Speak (join), View Channel, Send Messages
4. **(Opcional)** Webhook n8n de teste ou [webhook.site](https://webhook.site) para capturar POST

---

## Setup

```bash
cd /home/ricardosobral/Documents/Desenvolvimento/discord-transcription

cp .env.example .env
# Editar .env:
#   DISCORD_TOKEN=<token>
#   N8N_WEBHOOK_URL=<url de teste>   # opcional
#   RECORDINGS_DIR=./recordings
#   AUTO_END_EMPTY_CHANNEL_MS=60000  # 1 min para testes rápidos de auto-end

npm install
npm run dev
```

**Expected**: Console exibe `[bot] Conectado como Cronista#XXXX`.

---

## Scenario 1 — Iniciar captura (User Story 1)

**Covers**: FR-001, FR-002, FR-003, FR-008, SC-005

1. Entre no canal de voz `#teste-voz` com sua conta
2. No chat do servidor, envie: `!cronista entrar`

**Expected**:
- Bot responde com confirmação contendo `session_id` (formato `YYYYMMDD-HHmmss`)
- Bot aparece no canal de voz (ícone surdo/mudo)
- Diretório criado: `recordings/{session_id}/session.json`

**Verify**:

```bash
ls recordings/
cat recordings/*/session.json
```

`session.json` deve conter `started_at`, `guild_id`, `channel_id`, `participants: []`.

---

## Scenario 2 — Captura por jogador (User Story 2)

**Covers**: FR-004, FR-005, FR-006, FR-007, FR-010, FR-019, SC-001, SC-002

**Requires**: 2+ contas Discord no canal (ou 1 conta + amigo)

1. Com sessão ativa (Scenario 1), cada participante fala frases separadas com pausa > 1s entre turnos
2. Alterne falantes (A fala → pausa → B fala → pausa → A fala)

**Expected**:
- Arquivos `.ogg` criados em `recordings/{session_id}/{user_id}/0001.ogg`, `0002.ogg`, etc.
- `speaking_log.jsonl` ganha uma linha por utterance fechada
- `session.json` lista participantes com `utterance_count` incrementado

**Verify**:

```bash
SESSION=$(ls recordings/ | tail -1)
find "recordings/$SESSION" -name "*.ogg" | head
wc -l "recordings/$SESSION/speaking_log.jsonl"
cat "recordings/$SESSION/speaking_log.jsonl" | head -3
```

Cada linha do log deve ter `start_ms`, `end_ms`, `duration_ms` coerentes. Ordenar por `start_ms` deve refletir ordem de fala na mesa.

**Audio check** (opcional):

```bash
ffplay "recordings/$SESSION/<user_id>/0001.ogg"
```

---

## Scenario 3 — Status durante sessão (User Story 4)

**Covers**: FR-016

1. Com sessão ativa, envie: `!cronista status`

**Expected**:
- Resposta indica gravação ativa
- Mostra `session_id`, duração (> 0), contagem de participantes

---

## Scenario 4 — Encerrar manualmente + webhook (User Story 3)

**Covers**: FR-011, FR-013, FR-014, FR-015, SC-003, SC-006

1. Envie: `!cronista encerrar`

**Expected**:
- Bot sai do canal de voz
- `session.json` contém `ended_at`
- Se `N8N_WEBHOOK_URL` configurada: webhook recebe POST JSON conforme [n8n-webhook.schema.json](./contracts/n8n-webhook.schema.json)
- Resposta confirma notificação (ou falha marcada)

**Verify webhook** (webhook.site ou logs n8n):

```json
{
  "session_id": "...",
  "recordings_path": "...",
  "participants": [...]
}
```

---

## Scenario 5 — Encerramento automático (User Story 3)

**Covers**: FR-012

1. Inicie sessão (`!cronista entrar`)
2. Todos os humanos saem do canal de voz
3. Aguarde `AUTO_END_EMPTY_CHANNEL_MS` (use 60000 no `.env` de teste)

**Expected**:
- Sessão encerrada automaticamente sem comando manual
- Mesmos artefatos que Scenario 4

---

## Scenario 6 — Coexistência com Robigode (User Story 5)

**Covers**: FR-017, SC-004 (parcial)

1. Conecte Robigode ao canal e inicie música
2. Inicie Cronista (`!cronista entrar`)
3. Fale enquanto música toca
4. Encerre Cronista

**Expected**:
- Ambos bots permanecem no canal
- Música continua sem interrupção
- Falas capturadas normalmente (Scenario 2)

---

## Scenario 7 — Guard de sessão duplicada

**Covers**: FR-002, FR-018

1. Com sessão ativa, envie novamente: `!cronista entrar`

**Expected**: Mensagem de rejeição; sessão original continua intacta.

---

## Scenario 8 — Webhook failure

**Covers**: FR-015

1. Configure `N8N_WEBHOOK_URL` com URL inválida (ex: `http://127.0.0.1:1/nope`)
2. Inicie e encerre sessão curta

**Expected**:
- Gravações preservadas
- `session.json` contém `"webhook_failed": true`
- Resposta ao GM indica falha de notificação

---

## Scenario 9 — Sessão longa (smoke test)

**Covers**: SC-004

1. Deixe sessão ativa por ≥ 30 min com falas esporádicas (proxy para 3–4h)
2. Monitore memória do processo: `ps -o rss= -p $(pgrep -f "tsx watch")`

**Expected**: RSS estável (sem crescimento linear descontrolado); bot responsivo a `!cronista status`.

---

## Validation Checklist

| # | Scenario | Pass |
|---|----------|------|
| 1 | Iniciar captura | ☐ |
| 2 | Captura por jogador | ☐ |
| 3 | Status | ☐ |
| 4 | Encerrar + webhook | ☐ |
| 5 | Auto-end canal vazio | ☐ |
| 6 | Coexistência Robigode | ☐ |
| 7 | Sessão duplicada rejeitada | ☐ |
| 8 | Webhook failure marcado | ☐ |
| 9 | Estabilidade 30min+ | ☐ |

**MVP ready** when scenarios 1–5 and 7 pass. Scenarios 6, 8, 9 recommended before produção.

---

## Production Deploy (after validation)

```bash
npm run build
sudo mkdir -p /opt/apps/cronista
sudo cp -r dist package.json package-lock.json /opt/apps/cronista/
sudo cp .env /opt/apps/cronista/   # produção: RECORDINGS_DIR=/opt/apps/cronista/recordings
sudo cp deploy/cronista.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cronista
sudo journalctl -u cronista -f
```
