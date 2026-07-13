# Implementation Validation: whisper-service

**Purpose**: Track quickstart scenarios and manual gates before production cutover  
**Created**: 2026-07-12  
**Feature**: [spec.md](../spec.md)

## Automated (CI/local)

| Check | Command | Status |
|-------|---------|--------|
| Unit tests | `cd whisper-service && pytest tests/ -v` | ☑ 15 passed |
| Config defaults | `test_config.py` | ☑ |
| Path validation | `test_paths.py` | ☑ |
| Health contract | `test_health.py` | ☑ |
| Transcribe contract | `test_transcribe.py` | ☑ |
| JSON schemas | Examples match Pydantic models | ☑ |

## Quickstart Phase A — Local (manual)

| Scenario | FR/SC | Status |
|----------|-------|--------|
| 1 Health after startup | FR-005, SC-001 | ☐ |
| 2 Transcribe real `.ogg` | FR-001–004, SC-002 | ☐ |
| 3 Error cases (404, 403) | FR-003 | ☐ |

## Quickstart Phase B — Production install

| Step | FR/SC | Status |
|------|-------|--------|
| systemd unit active | FR-014 | ☐ |
| `/health` on server | SC-001 | ☐ |

## Quickstart Phase C — n8n Docker

| Step | FR/SC | Status |
|------|-------|--------|
| `extra_hosts` in n8n compose | FR-011 | ☐ |
| URL `host.docker.internal:8008/transcribe` | FR-011 | ☐ |
| curl health from n8n container | SC-005 | ☐ |
| One transcribe from container | SC-005 | ☐ |
| ufw rules applied | Assumptions | ☐ |

## Quickstart Phase D — End-to-end

| Step | FR/SC | Status |
|------|-------|--------|
| Session ≥20 utterances sequential | SC-004 | ☐ |
| GM quality review (PJ names) | SC-003 | ☐ |

## Notes

- Phase A–D require faster-whisper model download on first run (~500MB for `small`).
- Prototype `main.py` externo ao repo: N/A — implementação nova em `whisper_service/`.
