# whisper-service

Microserviço HTTP que expõe **faster-whisper** para o workflow n8n "Cronista - Transcrição da Sessão". Carrega o modelo uma vez na inicialização e transcreve utterances `.ogg` do Cronista sob demanda.

Documentação: [spec.md](./spec.md) · [quickstart.md](./quickstart.md) · [contracts/](./contracts/)

## Requisitos

- Python **3.11–3.13**
- `ffmpeg` no PATH (decodificação de `.ogg`)
- venv **isolado** — não compartilhar com Cronista ou Bertroldo

## Setup local

```bash
cd whisper-service
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Ajuste WHISPER_ALLOWED_PATH_PREFIX para seu RECORDINGS_DIR local
python -m whisper_service
```

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/health` | Status e modelo carregado |
| POST | `/transcribe` | `{audio_path, language}` → `{text, language, duration_s}` |

## Configuração

| Variável | Default | Descrição |
|----------|---------|-----------|
| `WHISPER_MODEL_SIZE` | `small` | Tamanho do modelo Whisper |
| `WHISPER_COMPUTE_TYPE` | `int8` | Quantização CPU |
| `WHISPER_HOST` | `0.0.0.0` | Bind address (obrigatório para n8n Docker) |
| `WHISPER_PORT` | `8008` | Porta HTTP |
| `WHISPER_ALLOWED_PATH_PREFIX` | `/opt/apps/cronista/recordings/` | Prefixo permitido para `audio_path` |

### Trade-off de modelos (CPU-only)

| Modelo | RAM aprox. | Qualidade | Velocidade |
|--------|------------|-----------|------------|
| `tiny` | ~150 MB | Baixa | Muito rápida |
| `base` | ~300 MB | Razoável | Rápida |
| **`small`** | ~500 MB | **Boa (default)** | Moderada |
| `medium` | ~1.5 GB | Melhor para nomes próprios | Lenta |
| `large-v3` | ~3 GB | Máxima | Muito lenta em CPU |

Comece com `small`; se nomes de PJs/locais da campanha saírem ruins, teste `medium` via env e reinicie o serviço.

## Testes

```bash
cd whisper-service && source .venv/bin/activate
pytest tests/ -v
```

## Deploy

Ver [quickstart.md](./quickstart.md) Phase B e `deploy/whisper-service.service`.
