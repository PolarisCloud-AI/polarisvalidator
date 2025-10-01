import sys
from loguru import logger

U32_MAX = 4294967295
U16_MAX = 65535
__version__ = "9.10.0"
version_split = __version__.split(".")
__spec_version__ = 9010000  # Fixed spec version for Bittensor 9.10.0

# Configure logger
if not logger._core.handlers:
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level="INFO",
        colorize=True,
    )