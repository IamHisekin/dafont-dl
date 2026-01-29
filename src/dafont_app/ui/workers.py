from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)


class FunctionWorker(QRunnable):
    def __init__(self, fn: Callable[[Callable[[str], None]], Any]):
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn(self.signals.progress.emit)
            self.signals.finished.emit(result)
        except Exception:
            self.signals.error.emit(traceback.format_exc())
