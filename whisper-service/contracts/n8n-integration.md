# n8n Integration Contract: whisper-service

**Feature**: whisper-service  
**Consumer**: Workflow "Cronista - Transcrição da Sessão" (n8n)

---

## Network Topology

```text
┌─────────────────────┐         host.docker.internal:8008        ┌──────────────────────┐
│  n8n (Docker)       │  ───────────────────────────────────►  │  whisper-service     │
│  container          │         HTTP POST /transcribe            │  (host, systemd)     │
└─────────────────────┘                                        └──────────────────────┘
         │                                                                │
         │  reads speaking_log.jsonl                                      │  reads .ogg
         ▼                                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  /opt/apps/cronista/recordings/{session_id}/                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Docker Compose (n8n)

Adicionar ao serviço n8n:

```yaml
services:
  n8n:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Sem isso, `host.docker.internal` não resolve no Docker Linux.

---

## HTTP Request Node — "Transcrever utterance (Whisper)"

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://host.docker.internal:8008/transcribe` |
| Content-Type | `application/json` |
| Timeout | 120000 ms (120s) |
| Body (JSON) | Ver abaixo |

**Body template** (expressões n8n — ajustar nomes de variáveis do workflow):

```json
{
  "audio_path": "/opt/apps/cronista/recordings/{{ $json.session_id }}/{{ $json.file }}",
  "language": "pt"
}
```

> **Correção obrigatória**: substituir URL antiga `http://127.0.0.1:8008/transcribe` por `host.docker.internal`.

---

## Path Resolution

O n8n MUST montar `audio_path` como caminho **absoluto** no host:

```text
/opt/apps/cronista/recordings/{session_id}/{user_id}/{NNNN}.ogg
```

O campo `file` em `speaking_log.jsonl` é relativo (`{user_id}/0001.ogg`); prefixar com `RECORDINGS_DIR` + `session_id`.

---

## Error Handling (workflow)

| HTTP Status | Ação recomendada no workflow |
|-------------|------------------------------|
| 200 | Prosseguir com `text` na montagem do transcript |
| 404 | Registrar utterance ausente; continuar próxima |
| 500 | Registrar falha de transcrição; continuar (não abortar sessão inteira) |
| 503 | Retry após delay ou aguardar health ok |
| Timeout (120s) | Registrar timeout; continuar próxima utterance |

---

## Firewall (host)

Restringir porta 8008 — **não** expor à LAN inteira.

**Procedimento** (executar no servidor antes de aplicar regras):

```bash
# 1. Identificar sub-rede da bridge Docker
docker network inspect bridge --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
# Exemplo de saída: 172.17.0.0/16

# 2. Confirmar que o container n8n usa a rede bridge
docker inspect <n8n-container> --format '{{json .NetworkSettings.Networks}}'

# 3. Aplicar regras ufw (substituir SUBNET pelo valor do passo 1)
sudo ufw allow from SUBNET to any port 8008 proto tcp comment 'whisper-service n8n'
sudo ufw allow from 127.0.0.0/8 to any port 8008 proto tcp comment 'whisper-service localhost'
sudo ufw status numbered
```

Exemplo com sub-rede típica:

```bash
sudo ufw allow from 172.17.0.0/16 to any port 8008 proto tcp
sudo ufw allow from 127.0.0.0/8 to any port 8008 proto tcp
```

---

## Health Check (monitoramento)

Cron ou n8n schedule:

```bash
curl -sf http://localhost:8008/health | jq .
```

Esperado: `{ "status": "ok", "model": "small", "compute_type": "int8" }`

---

## Sequential Processing

O workflow MUST processar utterances **sequencialmente** (uma por vez) no MVP — alinhado a `uvicorn --workers 1` e modelo singleton em RAM.

Paralelismo futuro exige fila ou múltiplos workers (fora de escopo).
