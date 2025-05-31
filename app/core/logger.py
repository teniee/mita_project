
from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, level="INFO")

def get_logger(name: str = "app"):
    return logger.bind(name=name)
