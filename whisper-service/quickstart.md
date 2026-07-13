# Quickstart: Validação do whisper-service

**Feature**: whisper-service  
**Purpose**: Validar transcrição local, contratos HTTP e integração n8n↔host antes de produção.

Referências: [spec.md](./spec.md) · [research.md](./research.md) · [data-model.md](./data-model.md) · [contracts/](./contracts/)

---

## Prerequisites

1. **Python 3.11+** (3.11–3.13 recomendado)
2. **ffmpeg** no PATH (decodificação de `.ogg` se necessário)
3. **Arquivo de áudio de teste** — idealmente um `.ogg` real gravado pelo Cronista
4. **(Produção)** Docker com n8n + `extra_hosts` configurado
5. **(Produção)** Acesso sudo para systemd e ufw

---

## Phase A — Desenvolvimento local 🚦

**Covers**: US1, US2, FR-001–FR-008, SC-001, SC-002

### Setup

```bash
cd /home/ricardosobral/Documents/Desenvolvimento/discord-transcription/whisper-service
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Ajustar WHISPER_ALLOWED_PATH_PREFIX para seu RECORDINGS_DIR local se necessário
```

### Start (dev)

```bash
source .venv/bin/activate
uvicorn whisper_service.main:app --host 0.0.0.0 --port 8008 --reload
```

**Expected**: logs indicando carregamento do modelo; após ~30–60s, modelo pronto.

### Scenario 1 — Health check

```bash
curl -s http://localhost:8008/health | jq .
```

**Expected**:

```json
{
  "status": "ok",
  "model": "small",
  "compute_type": "int8"
}
```

Se retornar 503/`loading`, aguardar fim do carregamento e repetir.

---

### Scenario 2 — Transcrever utterance real

Substituir pelo caminho de um `.ogg` existente:

```bash
AUDIO="/opt/apps/cronista/recordings/20260712-171116/236502177789509633/0001.ogg"

curl -s -X POST http://localhost:8008/transcribe \
  -H "Content-Type: application/json" \
  -d "{\"audio_path\": \"$AUDIO\", \"language\": \"pt\"}" | jq .
```

**Expected**:
- HTTP 200
- `text` com conteúdo reconhecível (ou vazio se utterance silenciosa)
- `duration_s` > 0
- Tempo de resposta << 120s para utterance de 10–15s

**Verify quality (manual)**: ouvir o `.ogg` e comparar com `text` — nomes de PJs/locais aceitáveis?

---

### Scenario 3 — Erros previsíveis

**Arquivo inexistente**:

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8008/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_path": "/tmp/nao-existe.ogg", "language": "pt"}'
```

**Expected**: `404`

**Path fora do prefixo** (se validação habilitada):

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8008/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_path": "/etc/passwd", "language": "pt"}'
```

**Expected**: `403`

---

### Scenario 4 — Modelo alternativo (opcional)

```bash
# .env
WHISPER_MODEL_SIZE=medium
```

Reiniciar serviço; confirmar via health; repetir Scenario 2 e comparar qualidade vs latência.

**Checklist de qualidade (manual)**:

- [ ] Ouvir o `.ogg` original e ler o `text` retornado
- [ ] Nomes de PJs reconhecíveis (ex.: personagens da campanha)
- [ ] Nomes de locais/facções aceitáveis
- [ ] Jargão de mesa (dados, iniciativa) transcrito de forma útil
- [ ] Se qualidade insuficiente: testar `WHISPER_MODEL_SIZE=medium` e comparar latência

---

## Phase B — Deploy produção

**Covers**: US3, US4, FR-011–FR-014, SC-004–SC-006

### Instalação

Monorepo: clone em `/opt/apps/discord-transcription` ou copie apenas `whisper-service/` + `deploy/whisper-service.service`.

```bash
sudo mkdir -p /opt/apps/whisper-service
sudo git clone <url-do-repositorio> /opt/apps/whisper-service
sudo chown -R adminvtt:adminvtt /opt/apps/whisper-service

cd /opt/apps/whisper-service/whisper-service
python3.11 -m venv /opt/apps/whisper-service/.venv
/opt/apps/whisper-service/.venv/bin/pip install -r requirements.txt

cp .env.example /opt/apps/whisper-service/.env
# Editar /opt/apps/whisper-service/.env:
#   WHISPER_ALLOWED_PATH_PREFIX=/opt/apps/cronista/recordings/
```

### systemd

```bash
sudo cp deploy/whisper-service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now whisper-service
sudo journalctl -u whisper-service -f
```

**Expected**: modelo carrega; `/health` retorna ok.

### Firewall

```bash
docker network inspect bridge | grep Subnet
# Aplicar regras ufw conforme contracts/n8n-integration.md
```

---

## Phase C — Integração n8n (Docker)

**Covers**: US3, SC-005

1. Confirmar `extra_hosts` no compose do n8n
2. Atualizar URL do node para `http://host.docker.internal:8008/transcribe`
3. Executar workflow com sessão piloto (≥20 utterances)

**Expected**:
- 0 erros de conexão
- Transcript montado com textos por utterance
- Serviço não reiniciado durante a sessão

**Verify from inside n8n container** (debug):

```bash
docker exec -it <n8n-container> curl -s http://host.docker.internal:8008/health
```

---

## Phase D — Sessão piloto end-to-end

**Covers**: SC-003, SC-004, SC-006

1. Sessão real ou replay: Cronista grava → webhook n8n → transcrição sequencial
2. Validar tempo total de transcrição vs duração da sessão
3. GM revisa qualidade do transcript final

**Gate para produção**:
- [ ] Health ok após restart
- [ ] ≥20 utterances transcritas sem restart do serviço
- [ ] Qualidade aceitável para nomes da campanha
- [ ] n8n alcança serviço via Docker
- [ ] Firewall aplicado na porta 8008

---

## Schema Validation (optional)

```bash
pip install check-jsonschema

check-jsonschema --schemafile whisper-service/contracts/transcribe-response.schema.json \
  <<< '{"text":"teste","language":"pt","duration_s":1.0}'
```

---

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| Connection refused (n8n) | Bind em 127.0.0.1 ou firewall | Confirmar `WHISPER_HOST=0.0.0.0`; ufw |
| host.docker.internal não resolve | Falta extra_hosts | Adicionar ao compose n8n |
| 503 persistente | Modelo não carregou | Ver journalctl; RAM insuficiente? |
| Transcrição lenta | Modelo grande em CPU | Tentar `small`; medir latência |
| Texto vazio | Utterance silenciosa | Normal; Cronista pode ter descartado silêncio |
| 403 path | Prefixo incorreto | Ajustar `WHISPER_ALLOWED_PATH_PREFIX` |

---

## Rollback

```bash
sudo systemctl stop whisper-service
sudo systemctl disable whisper-service
# Workflow n8n: desabilitar node Whisper ou reverter URL
```

Transcrição manual/CLI permanece fallback temporário.
