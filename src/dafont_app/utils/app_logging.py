from __future__ import annotations

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import qInstallMessageHandler, QtMsgType

from dafont_app.utils.paths import app_root

_LOGGER_NAME = "dafont_app"


def log_path() -> Path:
    p = app_root() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p / "app.log"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(log_path(), maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(level)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    logger.info("Logging iniciado. Arquivo: %s", log_path())
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def install_excepthooks() -> None:
    logger = get_logger()

    def _fmt(exc_type, exc, tb) -> str:
        return "".join(traceback.format_exception(exc_type, exc, tb))

    def _sys_hook(exc_type, exc, tb):
        logger.critical("Exceção não tratada (sys.excepthook):\n%s", _fmt(exc_type, exc, tb))

    sys.excepthook = _sys_hook

    try:
        import threading

        def _thread_hook(args):
            logger.critical(
                "Exceção não tratada (threading.excepthook):\n%s",
                _fmt(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = _thread_hook  # type: ignore[attr-defined]
    except Exception:
        pass


def install_qt_message_handler() -> None:
    logger = get_logger()

    def handler(mode: QtMsgType, ctx, message: str) -> None:
        if mode == QtMsgType.QtDebugMsg:
            logger.debug("Qt: %s", message)
        elif mode == QtMsgType.QtInfoMsg:
            logger.info("Qt: %s", message)
        elif mode == QtMsgType.QtWarningMsg:
            logger.warning("Qt: %s", message)
        elif mode == QtMsgType.QtCriticalMsg:
            logger.error("Qt: %s", message)
        elif mode == QtMsgType.QtFatalMsg:
            logger.critical("Qt(FATAL): %s", message)
        else:
            logger.info("Qt: %s", message)

    qInstallMessageHandler(handler)
