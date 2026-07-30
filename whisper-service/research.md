# Research: whisper-service — atualização CPU threads

**Feature**: whisper-service (update)  
**Date**: 2026-07-30  
**Source**: `docs/demanda-whisper-service.md`

## R9 — Limite de threads CPU (`WHISPER_CPU_THREADS`)

**Decision**: Expor `WHISPER_CPU_THREADS` (default **5**) e passar ao construtor `WhisperModel(..., device="cpu", compute_type=..., cpu_threads=N)`.

**Rationale**: Sem limite, CTranslate2/OpenMP tende a usar todos os núcleos por chamada. No host compartilhado (Foundry VTT, Bertroldo, n8n, blog), um lote de ~2.000 utterances deixa o servidor saturado. A demanda fixa default 5 para deixar núcleos livres. faster-whisper documenta `cpu_threads` como o controle de threads OpenMP por worker do modelo (default da lib é tipicamente 4; o produto exige **5**).

**Alternatives considered**:
- *`OMP_NUM_THREADS` só via systemd Environment* — rejeitado como única solução: menos explícito no `.env` do serviço e fácil de esquecer no deploy; `cpu_threads` no construtor é a API oficial.
- *`num_workers` > 1* — rejeitado: demanda e MVP exigem processamento sequencial; mais workers aumentam RAM e pressão de CPU.
- *cgroup/systemd `CPUQuota`* — útil como defesa em profundidade futura, mas não substitui o controle no modelo; fora do escopo mínimo da demanda.
- *Default da biblioteca sem override* — rejeitado: não garante o orçamento documentado (5) nem previsibilidade operacional.

**Implementation notes**:
- Validar inteiro ≥ 1 na carga de config; falhar fast se inválido.
- Logar `cpu_threads` no startup junto com model/compute.
- Não obrigatório expor no `/health` (demanda não lista o campo).

---

## R1–R8 (MVP) — reafirmados

Decisões anteriores permanecem válidas e não são reabertas por esta atualização:

| ID | Decision |
|----|----------|
| R1 | faster-whisper, modelo carregado uma vez |
| R2 | FastAPI + uvicorn workers=1 |
| R3 | Entrada por `audio_path` (sem upload) |
| R4 | Bind `0.0.0.0` + `host.docker.internal` |
| R5 | Default model `small` / compute `int8` |
| R6 | 404 / 500 sem derrubar processo |
| R7 | `/health` ok vs loading |
| R8 | Unit tests mockados + quickstart manual |

---

## Resolved Clarifications

| Item | Resolution |
|------|------------|
| Default threads | 5 (demanda) |
| Health inclui `cpu_threads`? | Não nesta atualização |
| Aceite de convivência | Manual via `htop` + sessão piloto (SC-005) |

Nenhum NEEDS CLARIFICATION bloqueante remanescente.
