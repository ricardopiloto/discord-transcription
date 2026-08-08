"""Background session batch transcription worker."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whisper_service import callback, transcriber
from whisper_service.session_store import SessionStore, get_store
from whisper_service.transcript_format import (
    counts_as_com_texto,
    format_transcript_line,
    resolve_display_name,
)

logger = logging.getLogger(__name__)

SESSION_LANGUAGE = "pt"

_executor: ThreadPoolExecutor | None = None


@dataclass(frozen=True)
class SessionJob:
    session_id: str
    recordings_path: Path
    speaking_log_path: Path
    participants: dict[str, str]
    channel_id: str
    callback_url: str


def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="session-batch")
    return _executor


def shutdown_executor(*, wait: bool = False) -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait, cancel_futures=False)
        _executor = None


def submit_session(job: SessionJob, store: SessionStore | None = None) -> None:
    """Queue session processing on the single-worker executor (non-blocking)."""
    target_store = store or get_store()
    get_executor().submit(process_session, job, target_store)


def process_session(job: SessionJob, store: SessionStore | None = None) -> None:
    """Run the full session batch synchronously (called from worker thread)."""
    target = store or get_store()
    processed = 0
    total = 0
    try:
        entries = _read_speaking_log(job.speaking_log_path)
        total = len(entries)
        target.set_total(job.session_id, total)

        lines: list[tuple[int, str]] = []
        com_texto = 0

        for entry in entries:
            user_id = str(entry.get("user_id", ""))
            rel_file = str(entry.get("file", ""))
            start_ms = int(entry.get("start_ms", 0))
            audio_path = job.recordings_path / rel_file

            if not audio_path.is_file():
                logger.warning(
                    "Áudio ausente session=%s file=%s — pulando",
                    job.session_id,
                    audio_path,
                )
                processed += 1
                target.set_processed(job.session_id, processed)
                continue

            try:
                text, _duration = transcriber.transcribe(str(audio_path), SESSION_LANGUAGE)
            except Exception:
                logger.exception(
                    "Falha ao transcrever session=%s file=%s",
                    job.session_id,
                    audio_path,
                )
                processed += 1
                target.set_processed(job.session_id, processed)
                continue

            name = resolve_display_name(user_id, job.participants)
            line = format_transcript_line(start_ms, name, text)
            lines.append((start_ms, line))
            if counts_as_com_texto(text):
                com_texto += 1

            processed += 1
            target.set_processed(job.session_id, processed)

        lines.sort(key=lambda item: item[0])
        output_path = job.recordings_path / "transcricao.txt"
        try:
            output_path.write_text(
                "\n".join(line for _, line in lines) + ("\n" if lines else ""),
                encoding="utf-8",
            )
        except OSError as exc:
            raise RuntimeError(f"Falha ao escrever transcricao.txt: {exc}") from exc

        state = target.mark_done(
            job.session_id,
            processed=processed,
            total=total,
            utterances_com_texto=com_texto,
            output_path=str(output_path),
        )
        payload = {
            "session_id": job.session_id,
            "status": "done",
            "output_path": str(output_path),
            "total_utterances": total,
            "utterances_com_texto": com_texto,
            "channel_id": job.channel_id,
        }
        callback.notify(job.callback_url, payload)
        logger.info(
            "Sessão concluída session=%s processed=%s total=%s com_texto=%s state=%s",
            job.session_id,
            processed,
            total,
            com_texto,
            state.status if state else None,
        )
    except Exception as exc:
        logger.exception("Falha fatal no lote session=%s", job.session_id)
        target.mark_failed(
            job.session_id,
            error=str(exc),
            processed=processed,
            total=total,
        )
        fail_payload: dict[str, Any] = {
            "session_id": job.session_id,
            "status": "failed",
            "error": str(exc),
            "total_utterances": total,
            "channel_id": job.channel_id,
        }
        callback.notify(job.callback_url, fail_payload)


def _read_speaking_log(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"speaking_log ilegível ou inexistente: {path}")
    entries: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"Linha inválida no speaking_log ({line_no}): {exc}"
                    ) from exc
                if not isinstance(obj, dict):
                    raise RuntimeError(f"Linha {line_no} do speaking_log não é objeto JSON")
                entries.append(obj)
    except OSError as exc:
        raise RuntimeError(f"Falha ao ler speaking_log: {exc}") from exc
    return entries
