"""FastAPI application — v1 + session-async endpoints."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from whisper_service import session_worker, transcriber
from whisper_service.config import Config, load_config
from whisper_service.paths import PathValidationError, validate_audio_path, validate_session_path
from whisper_service.schemas import (
    HealthResponse,
    SessionAcceptedResponse,
    SessionStatusResponse,
    SessionTranscribeRequest,
    TranscribeRequest,
    TranscribeResponse,
)
from whisper_service.session_store import get_store
from whisper_service.session_worker import SessionJob

logger = logging.getLogger(__name__)

_config: Config | None = None


def get_config() -> Config:
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    _config = load_config()
    transcriber.init(_config)
    transcriber.load()
    session_worker.get_executor()
    try:
        yield
    finally:
        session_worker.shutdown_executor(wait=False)


app = FastAPI(title="whisper-service", lifespan=lifespan)


@app.get("/health", response_model=None)
def health() -> JSONResponse:
    cfg = get_config()
    body = HealthResponse(
        status="ok" if transcriber.is_ready_state() else "loading",
        model=cfg.model_size,
        compute_type=cfg.compute_type,
    )
    status_code = 200 if transcriber.is_ready_state() else 503
    return JSONResponse(status_code=status_code, content=body.model_dump())


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe_audio(body: TranscribeRequest) -> TranscribeResponse:
    cfg = get_config()

    if not transcriber.is_ready_state():
        raise HTTPException(status_code=503, detail="Modelo ainda carregando")

    try:
        resolved = validate_audio_path(body.audio_path, cfg.allowed_path_prefix)
    except PathValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not resolved.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Arquivo não encontrado: {body.audio_path}",
        )

    try:
        text, duration_s = transcriber.transcribe(str(resolved), body.language)
    except Exception as exc:
        logger.exception("Falha na transcrição de %s", resolved)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return TranscribeResponse(
        text=text,
        language=body.language,
        duration_s=duration_s,
    )


@app.post("/transcribe-session", response_model=None)
def transcribe_session(body: SessionTranscribeRequest) -> JSONResponse:
    cfg = get_config()

    if not transcriber.is_ready_state():
        raise HTTPException(status_code=503, detail="Modelo ainda carregando")

    try:
        recordings_path = validate_session_path(body.recordings_path, cfg.allowed_path_prefix)
        speaking_log_path = validate_session_path(
            body.speaking_log_path, cfg.allowed_path_prefix
        )
    except PathValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    store = get_store()
    callback_url = str(body.callback_url)
    if not store.try_start(
        body.session_id,
        channel_id=body.channel_id,
        callback_url=callback_url,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Sessão {body.session_id} já está sendo processada",
        )

    participants = {p.user_id: p.display_name for p in body.participants}
    job = SessionJob(
        session_id=body.session_id,
        recordings_path=recordings_path,
        speaking_log_path=speaking_log_path,
        participants=participants,
        channel_id=body.channel_id,
        callback_url=callback_url,
    )
    session_worker.submit_session(job, store)

    accepted = SessionAcceptedResponse(session_id=body.session_id)
    return JSONResponse(status_code=202, content=accepted.model_dump())


@app.get("/status/{session_id}", response_model=None)
def session_status(session_id: str) -> JSONResponse:
    state = get_store().get(session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sessão desconhecida: {session_id}",
        )
    body = SessionStatusResponse.model_validate(state.to_status_dict())
    return JSONResponse(status_code=200, content=body.model_dump(exclude_none=True))
