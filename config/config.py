import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

from .base import getenv


LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)


@dataclass
class TelegramBotConfig:
    token: str


@dataclass
class Config:
    tg_bot: TelegramBotConfig


def load_config() -> Config:
    # Parse a `.env` file and load the variables into environment valriables
    load_dotenv()

    return Config(tg_bot=TelegramBotConfig(token=getenv("BOT_TOKEN")))


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            RotatingFileHandler(
                os.path.join(LOG_DIR, 'app.log'),
                maxBytes=1024 * 1024 * 1000,  # 1 GB
                backupCount=5
            ),
            logging.StreamHandler()
        ]
    )
