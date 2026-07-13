# Research: whisper-service

**Feature**: whisper-service  
**Date**: 2026-07-12

## R1 — Motor de transcrição

**Decision**: `faster-whisper` (CTranslate2) com modelo carregado uma vez via `WhisperModel` no startup da aplicação.

**Rationale**: O PRD identifica o problema central — invocar Whisper via CLI recarrega o modelo a cada utterance. faster-whisper mantém o modelo em memória, usa quantização (`int8`) eficiente em CPU e entrega qualidade equivalente ao Whisper original. Já validado em protótipo funcional referenciado no PRD.

**Alternatives considered**:
- *openai-whisper CLI por utterance* — rejeitado: reload do modelo a cada arquivo; inviável para centenas de utterances/sessão.
- *whisper.cpp server* — rejeitado: stack adicional C++; faster-whisper já escolhido e com binding Python maduro.
- *Serviço cloud (OpenAI API)* — rejeitado: custo, latência de rede, dados de sessão saem do host; fora do escopo self-hosted.

---

## R2 — Framework HTTP

**Decision**: FastAPI + uvicorn, worker único (`--workers 1`).

**Rationale**: PRD especifica FastAPI; async nativo para I/O; OpenAPI automático útil para documentação; uvicorn é padrão de deploy. Worker único evita N cópias do modelo em RAM (cada worker carregaria WhisperModel independentemente).

**Alternatives considered**:
- *Flask + gunicorn* — rejeitado: sem ganho; PRD já define FastAPI.
- *uvicorn --workers 4* — rejeitado: 4× RAM para modelo; n8n não paraleliza chamadas no MVP.

---

## R3 — Entrada por caminho vs upload HTTP

**Decision**: `POST /transcribe` recebe `{audio_path, language}` — caminho absoluto no host.

**Rationale**: Cronista, n8n (via volume/bind) e whisper-service compartilham o mesmo host. Path-based evita serializar megabytes de áudio por HTTP, simplifica contrato e reduz latência. n8n monta ou resolve caminho a partir de `speaking_log.jsonl`.

**Alternatives considered**:
- *Multipart upload* — rejeitado: escopo MVP explícito no PRD; overhead desnecessário no mesmo host.
- *Shared memory / socket* — rejeitado: complexidade sem benefício vs path.

**Security note**: Validar que `audio_path` resolve dentro de diretórios permitidos (ex.: `RECORDINGS_DIR` ou prefixo configurável) para evitar path traversal — ver data-model.md.

---

## R4 — Rede Docker ↔ host

**Decision**: Serviço escuta `WHISPER_HOST=0.0.0.0`, porta `8008`. n8n chama `http://host.docker.internal:8008/transcribe` com `extra_hosts: host.docker.internal:host-gateway` no compose.

**Rationale**: PRD documenta que `127.0.0.1` no host não aceita tráfego da bridge Docker no Linux. `host.docker.internal` é o padrão de facto para container→host. Firewall (`ufw`) restringe porta 8008 à sub-rede bridge + localhost.

**Alternatives considered**:
- *Bind 127.0.0.1 + docker network host* — rejeitado: `network_mode: host` no n8n aumenta superfície; bind loopback falha com bridge default.
- *Sidecar container whisper* — rejeitado: MVP roda no host como Bertroldo/Cronista; menos moving parts.

---

## R5 — Tamanho de modelo e compute type

**Decision**: Default `WHISPER_MODEL_SIZE=small`, `WHISPER_COMPUTE_TYPE=int8`. Upgrade para `medium` via env após teste de qualidade com áudio real da campanha.

**Rationale**: Kron Mini K1 é CPU-only; `small`+`int8` equilibra RAM (~500MB–1GB modelo) e qualidade. Nomes próprios de WFRP podem exigir `medium` — decisão empírica, não bloqueante para implementação.

**Alternatives considered**:
- *`tiny` default* — rejeitado: qualidade insuficiente para nomes próprios em PT-BR de RPG.
- *`large-v3`* — rejeitado: RAM e latência proibitivas em CPU-only para centenas de utterances.

---

## R6 — Tratamento de erros HTTP

**Decision**: 404 para arquivo inexistente; 500 para falha de decodificação/transcrição; processo permanece vivo; mensagem em `detail` (padrão FastAPI).

**Rationale**: n8n workflow deve continuar ou marcar utterance falha; crash do serviço pararia toda a sessão. Contrato alinhado ao PRD §4.2.

**Alternatives considered**:
- *422 para arquivo corrompido* — rejeitado: PRD usa 500; manter compatibilidade com workflow já entregue.
- *Retry interno no serviço* — rejeitado: YAGNI; n8n pode reprocessar utterance isolada.

---

## R7 — Health check e readiness

**Decision**: `GET /health` retorna `{status, model, compute_type}` quando modelo carregado; durante startup retornar 503 ou `{status: "loading"}` até modelo pronto.

**Rationale**: Modelo demora dezenas de segundos a carregar; cron de monitoramento precisa distinguir "subindo" de "quebrado". Documentar comportamento exato no contrato.

**Alternatives considered**:
- *Sem endpoint de saúde* — rejeitado: FR-005 e monitoramento operacional existente.
- *Readiness separado de liveness* — rejeitado: MVP com endpoint único suficiente.

---

## R8 — Testes e validação

**Decision**: Unit tests com `TestClient` (paths mockados, transcriber mockado); integração manual via quickstart (curl + `.ogg` real); gate de qualidade manual antes de produção.

**Rationale**: Transcrição real depende de modelo pesado e áudio de campanha — inadequado para CI padrão. Contratos HTTP e validação de config são testáveis unitariamente.

**Alternatives considered**:
- *CI com modelo tiny* — possível fase futura; não bloqueia MVP.
- *Mock total sem quickstart manual* — rejeitado: viola princípio Evidence Before Commitment para qualidade de transcrição.

---

## Resolved Clarifications

| Item | Resolution |
|------|------------|
| Modelo definitivo | `small` default; validar empiricamente |
| Firewall | Documentar procedimento em quickstart; sub-rede confirmada no deploy |
| Timeout n8n 120s | Mantido; utterances típicas << limite |

Nenhum NEEDS CLARIFICATION bloqueante remanescente.
