"""FastAPI application — /transcribe and /health endpoints."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from whisper_service import transcriber
from whisper_service.config import Config, load_config
from whisper_service.paths import PathValidationError, validate_audio_path
from whisper_service.schemas import HealthResponse, TranscribeRequest, TranscribeResponse

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
    yield


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
