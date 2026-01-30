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
    def run(self):
        try:
            result = self.fn(self.signals.progress.emit)
            self.signals.finished.emit(result)
        except RuntimeError as e:
            # Erros "esperados" (ex: 404, validações) -> mensagem curta
            msg = str(e).strip() or "Falha ao executar tarefa."
            self.signals.error.emit(msg)
        except Exception:
            import traceback

            self.signals.error.emit(traceback.format_exc())
