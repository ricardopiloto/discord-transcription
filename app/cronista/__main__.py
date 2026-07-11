"""Entry point: python -m cronista"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from cronista.bot import create_bot
from cronista.config import load_config
from cronista.session_manager import SessionManager


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        config = load_config()
    except ValueError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        sys.exit(1)

    session_manager = SessionManager(config)
    bot = create_bot(config, session_manager)
    bot.run(config.discord_token)


if __name__ == "__main__":
    main()
