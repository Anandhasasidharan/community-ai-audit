"""Configure logging with optional JSON output."""

import logging
import os
import sys


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    if os.environ.get("COMMUNITY_AI_AUDIT_LOG_FORMAT", "").lower() == "json":
        _setup_json_logging(level)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def _setup_json_logging(level: int) -> None:
    import json as _json

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            return _json.dumps(
                {
                    "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                }
            )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
