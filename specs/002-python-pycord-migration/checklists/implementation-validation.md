# Implementation Validation Checklist

**Feature**: 002-python-pycord-migration  
**Date started**: 2026-07-10

Manual scenarios from [quickstart.md](../quickstart.md). Code implementation complete; live Discord validation pending.

| # | Scenario | Pass | Notes |
|---|----------|------|-------|
| A | Spike DAVE (gate) | ☐ | Run `spike/record_smoke.py` — see spike-acceptance.md |
| 1 | Iniciar captura | ☐ | `!cronista entrar` |
| 2 | Captura incremental por jogador | ☐ | `.ogg` during session |
| 3 | Status | ☐ | `!cronista status` |
| 4 | Encerrar + webhook | ☐ | `!cronista encerrar` |
| 5 | Compatibilidade downstream | ☐ | Schema validation |
| 6 | Auto-end canal vazio | ☐ | Empty channel timer |
| 7 | Coexistência Robigode + venv isolado | ☐ | Same channel test |
| 8 | Webhook failure marcado | ☐ | Invalid N8N_WEBHOOK_URL |
| 9 | Estabilidade / memória (≥30 min) | ☐ | RSS monitoring |

## Automated tests

| Suite | Pass | Notes |
|-------|------|-------|
| `pytest app/tests/unit/` | ☑ | 5 passed |

## Cutover

| Step | Pass | Notes |
|------|------|-------|
| systemd unit updated | ☑ | `deploy/cronista.service` → Python |
| Deploy to `/opt/apps/cronista/` | ☐ | Manual, controlled window |
| Pilot session 3–4h (SC-007) | ☐ | Before removing Node legacy |
| Node legacy removed (FR-016) | ☑ | src/, tests/, package.json, tsconfig, eslint removed |
