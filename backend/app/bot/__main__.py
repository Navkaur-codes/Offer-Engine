"""Local/backup runner: `python -m app.bot --polling`.

Polling deletes the production webhook. After using it, restart the Render service (it re-registers on boot).
"""

import argparse
import logging

from app import ports
from app.db import init_db

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--polling", action="store_true", help="run with long polling instead of a webhook")
    args = parser.parse_args()
    if not args.polling:
        parser.error("only --polling is supported here; production uses the webhook in app.main")
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines contain the bot token in the URL
    init_db()
    ports.build_application().run_polling(drop_pending_updates=True)
