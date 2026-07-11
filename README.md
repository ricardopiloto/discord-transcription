# Cronista

Bot Discord para captura de voz em sessões de RPG. Grava o áudio de cada jogador separadamente e notifica o pipeline de transcrição (n8n) ao encerrar a sessão.

Documentação de produto: [docs/PRD-bot-cronista-transcricao_v2.md](docs/PRD-bot-cronista-transcricao_v2.md).

Changelog: [CHANGELOG.md](CHANGELOG.md) — versão atual **0.1.3**.

## Stack

Python 3.11+ / py-cord — código em `app/cronista/`

## Requisitos

- Python 3.11+
- Bot Discord configurado no Developer Portal (ver seção abaixo)
- `ffmpeg` no PATH (conversão PCM→Opus por utterance; fallback grava `.wav` se ausente)
- venv Python **isolado** — não compartilhar com Bertroldo (conflito de namespace `discord`)

## Configuração do bot Discord

O Cronista usa **token próprio**, distinto do Bertroldo e do Robigode. Siga estes passos uma vez; depois disso, só o `.env` precisa do token.

### 1. Criar a aplicação

1. Abra o [Discord Developer Portal](https://discord.com/developers/applications).
2. **New Application** → nome sugerido: `Cronista`.
3. Em **App ID** (Settings → General Information), copie o ID — é o `DISCORD_CLIENT_ID` (útil para gerar o link de convite).

### 2. Criar o usuário bot

1. Menu lateral → **Bot** → **Add Bot**.
2. **Reset Token** → copie o token e guarde em local seguro. Esse valor vai em `DISCORD_TOKEN` no `.env`.
3. **Nunca** commite o token no git.

### 3. Ativar intents (obrigatório)

Ainda em **Bot**, em **Privileged Gateway Intents**, ative:

| Intent | Obrigatório? | Motivo |
|--------|--------------|--------|
| **Message Content Intent** | **Sim** | Ler comandos `!cronista` em texto |
| Server Members Intent | Não | Cronista não usa |
| Presence Intent | Não | Cronista não usa |

As intents padrão (`Guilds`, `Guild Voice States`, `Guild Messages`) já vêm habilitadas e são usadas pelo código.

Salve as alterações no portal.

### 4. Convidar o bot para o servidor

1. Menu lateral → **OAuth2** → **URL Generator**.
2. **Scopes**: marque `bot`.
3. **Bot Permissions** (mínimo para o Cronista):

| Permissão | Uso |
|-----------|-----|
| View Channels | Ver canais de voz e texto |
| Send Messages | Responder aos comandos |
| Read Message History | Ler `!cronista` no chat |
| Connect | Entrar no canal de voz |
| Speak | Recomendado (bot entra mudo, mas alguns servidores exigem) |

4. Copie a URL gerada, abra no navegador e adicione o bot ao **servidor da mesa de RPG**.

Link manual (substitua `SEU_CLIENT_ID`):

```text
https://discord.com/api/oauth2/authorize?client_id=SEU_CLIENT_ID&permissions=3214336&scope=bot
```

(`3214336` = View Channels + Send Messages + Read Message History + Connect + Speak)

### 5. Preencher o `.env`

```bash
cp .env.example .env
```

| Variável | Valor |
|----------|-------|
| `DISCORD_TOKEN` | Token copiado no passo 2 |
| `DISCORD_CLIENT_ID` | App ID (opcional; só referência/convite) |
| `RECORDINGS_DIR` | `./recordings` (local) ou `/opt/apps/cronista/recordings` (produção) |
| `N8N_WEBHOOK_URL` | URL do webhook n8n (opcional; se vazio, notificação é ignorada) |

### 6. Verificar

1. Inicie o bot (`python -m cronista` localmente ou `systemctl start cronista` em produção).
2. No log deve aparecer: `[bot] Conectado como Cronista#XXXX`.
3. Entre em um canal de voz de teste e envie `!cronista entrar` em um canal de texto do mesmo servidor.
4. O bot deve entrar no canal e responder com o `session_id`.

**Coexistência**: Cronista, Bertroldo e Robigode podem estar no mesmo canal de voz — cada um usa token e conexão independentes.

## Setup local (Python)

```bash
cd app
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example .env   # ver seção "Configuração do bot Discord" para DISCORD_TOKEN
python -m cronista
```

## Spike DAVE (obrigatório antes do cutover)

Validar recepção de áudio sob DAVE no ambiente real (usa a mesma build do PR #3202 que produção):

```bash
python3.11 -m venv .venv-spike && source .venv-spike/bin/activate
pip install "py-cord[voice] @ git+https://github.com/Pycord-Development/pycord@refs/pull/3202/head"
export DISCORD_TOKEN=...
python spike/record_smoke.py --channel <voice_channel_id> --seconds 180
```

> **Nota**: a py-cord 2.8.0 do PyPI **não recebe áudio** em canais com DAVE ativo. O `requirements.txt` já aponta para o PR #3202 com a decodificação corrigida.

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

Serviço systemd independente, usuário `adminvtt`, com o **repositório clonado diretamente em `/opt/apps/cronista`**. O venv e o `.env` vivem na raiz do clone (ambos ignorados pelo git), nos caminhos que o `deploy/cronista.service` já espera:

```
/opt/apps/cronista/          # clone do repositório
├── app/                     # código Python (WorkingDirectory do serviço)
├── .venv/                   # venv isolado (criado no servidor, fora do git)
├── .env                     # config de produção (fora do git)
└── recordings/              # gravações (RECORDINGS_DIR)
```

### Primeira instalação

```bash
# 1. Clonar o repositório
sudo mkdir -p /opt/apps
sudo git clone <url-do-repositorio> /opt/apps/cronista
sudo chown -R adminvtt:adminvtt /opt/apps/cronista

# 2. Criar o venv isolado (não compartilhar com o Bertroldo)
cd /opt/apps/cronista
python3.11 -m venv .venv
.venv/bin/pip install -r app/requirements.txt

# 3. Configurar ambiente de produção
cp .env.example .env
# Editar .env — ver README seção "Configuração do bot Discord":
#   DISCORD_TOKEN, N8N_WEBHOOK_URL, RECORDINGS_DIR=/opt/apps/cronista/recordings

# 4. Instalar e iniciar o serviço
sudo cp deploy/cronista.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cronista

# 5. Acompanhar logs
sudo journalctl -u cronista -f
```

### Atualizações

```bash
cd /opt/apps/cronista
sudo systemctl stop cronista
git pull
.venv/bin/pip install -r app/requirements.txt   # se as dependências mudaram
sudo systemctl start cronista
```

### Rollback

Como o deploy é um clone git, voltar de versão é um checkout:

```bash
cd /opt/apps/cronista
sudo systemctl stop cronista
git log --oneline            # identificar o commit/tag estável anterior
git checkout <commit-ou-tag>
.venv/bin/pip install -r app/requirements.txt
sudo systemctl start cronista
```

Se o problema for no serviço em si, mantenha-o parado (`sudo systemctl stop cronista`) e investigue os logs antes de nova tentativa. O `.env`, o `.venv/` e as gravações em `recordings/` não são afetados por checkouts.

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
