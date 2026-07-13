"""Entry point: python -m whisper_service"""

from __future__ import annotations

import uvicorn

from whisper_service.config import load_config


def main() -> None:
    cfg = load_config()
    uvicorn.run(
        "whisper_service.main:app",
        host=cfg.host,
        port=cfg.port,
        workers=1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
