# Quickstart: Validação da Migração Python/Py-Cord

**Feature**: 002-python-pycord-migration  
**Purpose**: Provar que a stack Python captura voz sob DAVE e preserva os contratos, antes de aposentar a stack Node.

Referências: [spec.md](./spec.md) · [research.md](./research.md) · [data-model.md](./data-model.md) · [contracts/](./contracts/)

---

## Prerequisites

1. **Python 3.11+** com `venv`
2. **Bot Discord** configurado no Developer Portal (intents + convite) — ver README seção "Configuração do bot Discord"
3. **Canal de voz de teste** com DAVE ativo e permissões: Connect, View Channel, Send Messages
4. **2+ contas** para falar durante os testes
5. **(Opcional)** webhook n8n de teste ou [webhook.site](https://webhook.site)

---

## Phase A — Spike (gate obrigatória) 🚦

**Covers**: US1, FR-001, FR-002, SC-001 — ver [contracts/spike-acceptance.md](./contracts/spike-acceptance.md)

```bash
cd /home/ricardosobral/Documents/Desenvolvimento/discord-transcription
python3.11 -m venv .venv-spike
. .venv-spike/bin/activate
pip install "py-cord"        # substituir pela pycord_source candidata (release/branch/fork + davey)
export DISCORD_TOKEN=...
python spike/record_smoke.py --channel <voice_channel_id> --seconds 180
```

**Expected**:
- Bot entra no canal; 2 participantes falam ~3 min
- Arquivos de áudio gerados e reproduzíveis, com autoria correta

**Verify**:

```bash
ls -R spike_out/
ffplay spike_out/<user_id>/*.ogg   # ou aplay/vlc
```

Preencher o `SpikeResult` e decidir o `verdict`:
- **PASS** → prosseguir para Phase B, fixando a `pycord_source` em `app/requirements.txt`
- **FAIL** → parar; registrar diagnóstico; ver opções no contrato do spike

> Se FAIL, **não** prosseguir com o rewrite. As fases abaixo pressupõem spike PASS.

---

## Setup (após spike PASS)

```bash
cd /home/ricardosobral/Documents/Desenvolvimento/discord-transcription/app
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example .env    # ajustar DISCORD_TOKEN, N8N_WEBHOOK_URL, RECORDINGS_DIR
python -m cronista
```

**Expected**: log `Conectado como Cronista#XXXX`.

---

## Scenario 1 — Iniciar captura (US2)

**Covers**: FR-003, FR-005, FR-008

1. Entre no canal de voz de teste
2. Envie `!cronista entrar`

**Expected**: resposta com `session_id`; bot no canal; `recordings/{session_id}/session.json` criado.

```bash
cat recordings/*/session.json
```

---

## Scenario 2 — Captura incremental por jogador (US2, US3)

**Covers**: FR-004, FR-005, FR-006, FR-007, FR-009, SC-002

1. 2+ participantes falam alternadamente com pausas > 1s
2. **Durante** a sessão (antes de encerrar), verifique que arquivos já aparecem:

```bash
SESSION=$(ls recordings/ | tail -1)
find "recordings/$SESSION" -name "*.ogg"      # devem surgir DURANTE a sessão
wc -l "recordings/$SESSION/speaking_log.jsonl"
```

**Expected**: `.ogg` por utterance em `{user_id}/NNNN.ogg`; linhas no JSONL com `start_ms`/`end_ms`/`duration_ms`; escrita incremental confirmada (arquivos existem antes do encerramento — valida FR-007/SC-003).

---

## Scenario 3 — Status (US2)

**Covers**: FR-003

1. `!cronista status` durante a sessão

**Expected**: status ativo, session_id, duração > 0, nº de participantes.

---

## Scenario 4 — Encerrar + webhook (US3, US4)

**Covers**: FR-010, FR-011, SC-004

1. `!cronista encerrar`

**Expected**: bot sai do canal; `ended_at` em session.json; POST ao n8n conforme [n8n-webhook.schema.json](./contracts/n8n-webhook.schema.json).

**Verify contrato** (SC-004):

```bash
# comparar campos com a spec 001 (mesmos schemas)
python -c "import json,sys; d=json.load(open('recordings/$SESSION/session.json')); print(sorted(d))"
```

---

## Scenario 5 — Compatibilidade downstream (US4)

**Covers**: FR-008, FR-009, FR-010, SC-004

Validar os três artefatos contra os schemas (idênticos à 001):

```bash
pip install check-jsonschema
check-jsonschema --schemafile specs/002-python-pycord-migration/contracts/session-json.schema.json recordings/$SESSION/session.json
# speaking_log: validar linha a linha contra speaking-log.schema.json
```

**Expected**: 100% dos campos compatíveis; n8n consumiria sem alteração.

---

## Scenario 6 — Auto-end por canal vazio (US3)

**Covers**: FR-012

1. Inicie sessão; todos os humanos saem; aguarde `AUTO_END_EMPTY_CHANNEL_MS` (use 60000 em teste)

**Expected**: encerramento automático com os mesmos artefatos do Scenario 4.

---

## Scenario 7 — Coexistência com Robigode (US5)

**Covers**: FR-014, FR-013

1. Robigode tocando música no canal; inicie Cronista; fale; encerre

**Expected**: ambos permanecem; música sem interrupção; falas capturadas; Cronista roda em venv próprio (não o do Bertroldo).

---

## Scenario 8 — Webhook failure (US4)

**Covers**: FR-011

1. `N8N_WEBHOOK_URL` inválida; sessão curta; encerrar

**Expected**: gravações preservadas; `"webhook_failed": true` em session.json.

---

## Scenario 9 — Estabilidade / memória (US3)

**Covers**: SC-003, SC-007

1. Sessão ≥ 30 min com falas intermitentes
2. Monitore RSS:

```bash
watch -n 30 'ps -o rss= -p $(pgrep -f "python -m cronista")'
```

**Expected**: RSS estável — **sem** crescimento linear proporcional à duração (prova de que não bufferiza a sessão em RAM).

---

## Validation Checklist

| # | Scenario | Pass |
|---|----------|------|
| A | Spike DAVE (gate) | ☐ |
| 1 | Iniciar captura | ☐ |
| 2 | Captura incremental por jogador | ☐ |
| 3 | Status | ☐ |
| 4 | Encerrar + webhook | ☐ |
| 5 | Compatibilidade downstream | ☐ |
| 6 | Auto-end canal vazio | ☐ |
| 7 | Coexistência Robigode + venv isolado | ☐ |
| 8 | Webhook failure marcado | ☐ |
| 9 | Estabilidade / memória | ☐ |

**Migração pronta para cutover** quando A e 1–6, 8 passam. 7 e 9 recomendados antes da primeira sessão real.

---

## Cutover & Rollback (US5, FR-015, FR-016)

Deploy por **clone git direto no servidor** em `/opt/apps/cronista` (venv e `.env` na raiz do clone, fora do git). Passo a passo completo na seção "Deploy (produção)" do `README.md`.

```bash
# Resumo
sudo git clone <url-do-repositorio> /opt/apps/cronista
sudo chown -R adminvtt:adminvtt /opt/apps/cronista
cd /opt/apps/cronista
python3.11 -m venv .venv && .venv/bin/pip install -r app/requirements.txt
cp .env.example .env    # DISCORD_TOKEN, N8N_WEBHOOK_URL, RECORDINGS_DIR=/opt/apps/cronista/recordings
sudo cp deploy/cronista.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now cronista
sudo journalctl -u cronista -f
```

**Atualização**: `git pull` + reinstalar requirements (se mudaram) + `systemctl restart cronista`.

**Rollback**: `git checkout <commit-ou-tag estável>` no clone, reinstalar requirements e reiniciar o serviço — `.env`, `.venv/` e `recordings/` não são afetados. Se a sessão piloto falhar, manter o serviço parado e investigar logs antes de nova tentativa.

**Nota (FR-016)**: a stack Node legada já foi removida do repositório; a referência histórica permanece em `specs/001-voice-capture-bot/`.
