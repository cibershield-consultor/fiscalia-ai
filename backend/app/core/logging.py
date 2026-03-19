"""
FiscalIA — Logging estructurado con Loguru
Sustituye todos los print() del proyecto por logging real.
"""
import sys
from loguru import logger

# Eliminar el handler por defecto
logger.remove()

# Handler para consola — formato limpio y legible
logger.add(
    sys.stdout,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    level="INFO",
    colorize=True,
)

# Handler para archivo — rotación diaria, retención 7 días
logger.add(
    "logs/fiscalia_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
    level="DEBUG",
    rotation="00:00",        # Rotar a medianoche
    retention="7 days",      # Guardar 7 días
    compression="zip",       # Comprimir logs viejos
    encoding="utf-8",
)


def get_logger(name: str):
    """Devuelve un logger con contexto de módulo."""
    return logger.bind(module=name)


__all__ = ["logger", "get_logger"]
