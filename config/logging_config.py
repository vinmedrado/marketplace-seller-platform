"""config/logging_config.py — Logging estruturado."""
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from config.settings import LOG_LEVEL, LOG_DIR


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": datetime.utcnow().isoformat(),
            "level":     record.levelname,
            "module":    record.module,
            "message":   record.getMessage(),
        }
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        # Mascara tokens
        msg = json.dumps(log)
        for pat in ("access_token", "refresh_token", "password", "secret"):
            import re
            msg = re.sub(rf'"{pat}":\s*"[^"]*"', f'"{pat}": "***"', msg)
        return msg


def setup_logging(name: str = "msp") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(ch)

    # Arquivo rotativo
    fh = logging.handlers.RotatingFileHandler(
        LOG_DIR / f"{name}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    fh.setFormatter(JSONFormatter())
    logger.addHandler(fh)

    return logger


log = setup_logging()
