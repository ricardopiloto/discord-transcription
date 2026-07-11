# Cronista

Bot Discord para captura de voz em sessões de RPG. Grava o áudio de cada jogador separadamente e notifica o pipeline de transcrição (n8n) ao encerrar a sessão.

Documentação de produto: [docs/PRD-bot-cronista-transcricao_v2.md](docs/PRD-bot-cronista-transcricao_v2.md).

Changelog: [CHANGELOG.md](CHANGELOG.md) — versão atual **0.1.0** (pré-validação).

## Stack

Python 3.11+ / py-cord — código em `app/cronista/`

## Requisitos

- Python 3.11+
- Token de bot Discord com intents: `Guilds`, `Guild Voice States`, `Guild Messages`, `Message Content`
- `ffmpeg` no PATH (conversão PCM→Opus por utterance; fallback grava `.wav` se ausente)
- venv Python **isolado** — não compartilhar com Bertroldo (conflito de namespace `discord`)

## Setup local (Python)

```bash
cd app
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example .env   # ajustar DISCORD_TOKEN, N8N_WEBHOOK_URL
python -m cronista
```

## Spike DAVE (obrigatório antes do cutover)

Validar recepção de áudio sob DAVE no ambiente real:

```bash
python3.11 -m venv .venv-spike && source .venv-spike/bin/activate
pip install "py-cord[voice]"
export DISCORD_TOKEN=...
python spike/record_smoke.py --channel <voice_channel_id> --seconds 180
```

Ver [specs/002-python-pycord-migration/contracts/spike-acceptance.md](specs/002-python-pycord-migration/contracts/spike-acceptance.md).

## Comandos

| Comando | Descrição |
|---|---|
| `!cronista entrar` | Entra no canal de voz e inicia a gravação |
| `!cronista encerrar` | Finaliza a sessão e dispara webhook para o n8n |
| `!cronista status` | Mostra duração e participantes da sessão atual |

## Estrutura de gravações

```
recordings/
  {session_id}/
    session.json
    speaking_log.jsonl
    {discord_user_id}/
      0001.ogg
      0002.ogg
```

## Testes

```bash
cd app && source .venv/bin/activate
pytest tests/unit/ -v
```

Validação manual end-to-end: [specs/002-python-pycord-migration/quickstart.md](specs/002-python-pycord-migration/quickstart.md)

## Deploy (produção)

Serviço systemd independente em `/opt/apps/cronista/`, venv próprio, usuário `adminvtt`.

```bash
sudo mkdir -p /opt/apps/cronista
sudo rsync -a app/ /opt/apps/cronista/app/
cd /opt/apps/cronista/app && python3.11 -m venv ../.venv
source ../.venv/bin/activate && pip install -r requirements.txt
sudo cp deploy/cronista.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now cronista
```

### Rollback

Se o cutover falhar antes da sessão piloto:

1. `sudo systemctl stop cronista`
2. Restaurar versão anterior do serviço a partir do histórico git (`deploy/cronista.service`) ou manter serviço parado
3. Investigar spike/logs antes de nova tentativa

## Arquitetura (Python)

```
app/cronista/
├── bot.py              # Cliente Discord, auto-end
├── commands.py         # !cronista entrar | encerrar | status
├── session_manager.py  # Ciclo de vida da sessão
├── webhook.py          # Notificação n8n com retry
├── config.py
└── recording/
    ├── sink.py         # Captura incremental por utterance
    ├── storage.py
    └── speaking_log.py
```

## Status do projeto

- [x] Spike script (`spike/record_smoke.py`)
- [x] Implementação Python (comandos, sink incremental, webhook, auto-end)
- [x] Testes unitários storage + webhook
- [x] systemd unit para Python
- [x] Stack Node removida (FR-016)
- [ ] Spike DAVE executado no ambiente real (verdict PASS)
- [ ] Validação manual quickstart (Discord ao vivo)
- [ ] Cutover produção

Constituição do projeto: [.specify/memory/constitution.md](.specify/memory/constitution.md)
