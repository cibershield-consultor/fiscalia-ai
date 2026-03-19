"""
FiscalIA — Structured logging with loguru
"""
import sys
from loguru import logger


def setup_logging():
    logger.remove()  # Remove default handler

    # Console — human-readable in dev, JSON-friendly in prod
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=False,  # Don't expose variable values in prod
    )

    # File — persistent logs, rotated daily, kept 7 days
    logger.add(
        "logs/fiscalia_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} — {message}",
        level="INFO",
        rotation="00:00",
        retention="7 days",
        compression="zip",
        backtrace=True,
        diagnose=False,
    )

    return logger


# Singleton logger for the whole app
log = setup_logging()
