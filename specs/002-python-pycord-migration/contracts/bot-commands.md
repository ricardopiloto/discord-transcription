# Contract: Bot Commands (Python/Py-Cord)

**Feature**: 002-python-pycord-migration  
**Interface**: mensagens de texto no Discord (comandos com prefixo)

Comandos e respostas observáveis são **idênticos** à spec 001 (FR-003). A migração não altera a experiência do GM.

## General Rules

- **Prefixo**: `!cronista` (match case-insensitive na palavra-chave)
- **Guild-only**: comandos ignorados em DMs
- **Autorização**: qualquer membro do servidor (grupo confiável single-tenant); sem role gate no MVP
- **Requisito de voz**: `entrar` exige o autor estar em canal de voz
- **Conexão de voz**: `self_deaf=False` (necessário para receber áudio), `self_mute=True`

## Commands

### `!cronista entrar`

Inicia gravação no canal de voz do autor.

| Condition | Response |
|-----------|----------|
| Autor fora de canal de voz | "Entre em um canal de voz antes de usar este comando." |
| Sessão já ativa | "Já estou gravando uma sessão. Use `!cronista encerrar` para finalizar." |
| Sucesso | "Gravação iniciada — sessão `{session_id}` no canal **{channel_name}**." |

**Side effects**:
- Bot entra no canal e aplica voice state `self_deaf=False`, `self_mute=True`
- Cria `{RECORDINGS_DIR}/{session_id}/session.json`
- Inicia recording com sink customizado (`vc.start_recording(sink, callback)`)

---

### `!cronista encerrar`

Finaliza sessão ativa manualmente.

| Condition | Response |
|-----------|----------|
| Sem sessão ativa | "Não há sessão em andamento." |
| Sucesso + webhook OK | "Sessão `{session_id}` encerrada. Pipeline de transcrição notificado." |
| Sucesso + webhook falhou | "Sessão `{session_id}` encerrada, mas a notificação ao n8n falhou (marcado em session.json)." |

**Side effects**:
- `stop_recording()`, flush/close de writers abertos
- Define `ended_at` em session.json
- Desconecta a voice connection
- POST webhook para `N8N_WEBHOOK_URL` (se configurado)

---

### `!cronista status`

Consulta estado da gravação.

| Condition | Response |
|-----------|----------|
| Sem sessão ativa | "Nenhuma sessão em andamento." |
| Sessão ativa | Multi-linha: status, session_id, duração (Xh Ym Zs), nº de participantes |

---

### `!cronista` / `!cronista help`

Lista comandos disponíveis.

## Auto-End Behavior (não é comando)

Quando o canal de voz fica com zero membros humanos por `AUTO_END_EMPTY_CHANNEL_MS` (default 5 min):
- Mesmos side effects de `encerrar`
- Sem resposta obrigatória no chat (opcional: log em stdout)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | yes | — | Token do bot |
| `RECORDINGS_DIR` | no | `./recordings` | Diretório de saída |
| `UTTERANCE_SILENCE_MS` | no | `1000` | Silêncio para fechar utterance |
| `AUTO_END_EMPTY_CHANNEL_MS` | no | `300000` | Auto-end com canal vazio (5 min) |
| `N8N_WEBHOOK_URL` | no | — | Destino do webhook; se ausente, notificação é pulada |

Ver também: [session-json.schema.json](./session-json.schema.json), [speaking-log.schema.json](./speaking-log.schema.json), [n8n-webhook.schema.json](./n8n-webhook.schema.json), [spike-acceptance.md](./spike-acceptance.md)
