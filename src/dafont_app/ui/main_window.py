from __future__ import annotations

import shutil
import traceback
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThreadPool
from PySide6.QtGui import QFont, QPixmap, QStandardItem, QStandardItemModel, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableView,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from dafont_app.db.cache_repo import CacheRepo
from dafont_app.db.repo import Repo
from dafont_app.services.downloader import download_zip, download_zip_from_url
from dafont_app.services.preview_offline import OfflinePreviewService, PreviewResult
from dafont_app.services.sync import DbSyncService, DEFAULT_REMOTE_DB_URL
from dafont_app.ui.theme import apply_theme
from dafont_app.ui.workers import FunctionWorker
from dafont_app.utils.app_logging import get_logger
from dafont_app.utils.paths import app_root, db_path, downloads_dir
from dafont_app.utils.platform import open_folder
from dafont_app.utils.settings import load_settings, save_settings


LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)] + ["#"]


@dataclass(frozen=True)
class Page:
    offset: int
    limit: int = 100


def _luma(c: QColor) -> float:
    return 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.log = get_logger()
        self.setWindowTitle("DaFont • Downloader")
        self.resize(1260, 780)

        self._downloads_target = downloads_dir()

        self.repo: Repo | None = None
        self.cache_repo = CacheRepo(app_root() / "cache" / "cache.db")
        self.syncer = DbSyncService(self.cache_repo, remote_url=DEFAULT_REMOTE_DB_URL)
        self.preview = OfflinePreviewService(auto_cleanup=False)

        self._letter = "A"
        self._page = Page(0, 100)
        self._current_slug: str | None = None
        self._current_download_url: str | None = None
        self._total = 0

        self._sync_inflight = False
        self._active_workers: set[FunctionWorker] = set()
        self._preview_token = 0
        self._did_first_show_refresh = False  # repaint workaround (Win/Fusion)

        self._build_ui()
        self._init_theme_combo()

        QTimer.singleShot(0, self._auto_sync_on_start)

        self._log("Aplicação iniciada.")
        self._log(f"Pasta de downloads: {self._downloads_target}")

    # -------------------- lifecycle --------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        # cache apagado ao fechar
        try:
            cache_root = app_root() / "cache"
            for sub in ("previews", "fonts", "zips"):
                p = cache_root / sub
                if p.exists():
                    for child in p.glob("*"):
                        try:
                            if child.is_file():
                                child.unlink()
                            else:
                                shutil.rmtree(child, ignore_errors=True)
                        except Exception:
                            pass
            self._log("Cache limpo ao fechar.")
        except Exception:
            pass
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)

        # Em alguns ambientes (Windows + Fusion), o QTableView só desenha após algum repaint global
        # (ex.: troca de tema). Isso força o primeiro paint assim que a janela aparece.
        if not self._did_first_show_refresh:
            self._did_first_show_refresh = True

            def _do():
                try:
                    if self.repo is not None:
                        # garante que o view calcule layout/colunas e pinte
                        self.model.layoutChanged.emit()
                        self.table.reset()
                    self._force_table_refresh()
                except Exception:
                    pass

            QTimer.singleShot(50, _do)

    # -------------------- helpers --------------------

    def _safe(self, fn):
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                self._show_error(traceback.format_exc())

        return wrapper

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.info(msg)
        self.console.append(f"[{ts}] {msg}")
        self.status.showMessage(msg, 5000)

    def _show_error(self, trace: str) -> None:
        self.log.error(trace)
        self._log("ERRO (ver app.log).")
        QMessageBox.critical(self, "Erro", trace)

    def _force_table_refresh(self) -> None:
        """Força o QTableView a redesenhar imediatamente (Windows/Fusion costuma atrasar repaint)."""
        try:
            # Recalcula layout do view e redesenha o viewport
            self.table.reset()
            self.table.viewport().update()
            self.table.update()
            self.table.repaint()

            # Garante que o loop de eventos processe o repaint agora
            app = QApplication.instance()
            if app:
                app.processEvents()
        except Exception:
            pass

    def _refresh_check_column(self) -> None:
        """Força o redesenho imediato da coluna de checkbox (evita aparecer só após scroll)."""
        try:
            if self.model.rowCount() <= 0:
                return
            top_left = self.model.index(0, 0)
            bottom_right = self.model.index(self.model.rowCount() - 1, 0)

            # sinal "forte" pro view atualizar o estado do checkbox
            self.model.dataChanged.emit(top_left, bottom_right, [Qt.CheckStateRole])

            # força repaint do viewport
            self.table.viewport().update()
            self.table.update()
            self.table.repaint()

            app = QApplication.instance()
            if app:
                app.processEvents()
        except Exception:
            pass

    # -------------------- UI --------------------

    def _build_ui(self) -> None:
        appbar = QFrame()
        appbar.setObjectName("Card")
        bar = QHBoxLayout(appbar)
        bar.setContentsMargins(14, 12, 14, 12)
        bar.setSpacing(10)

        title = QLabel("DaFont Downloader")
        title.setObjectName("AppTitle")

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar fonte… (nome/slug)")
        self.search.textChanged.connect(self._safe(self._debounced_search))
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(250)
        self._search_debounce.timeout.connect(self._refresh_fonts)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Sistema", "Escuro", "Claro"])
        self.theme_combo.currentIndexChanged.connect(self._safe(self._on_theme_changed))

        self.btn_sync = QToolButton()
        self.btn_sync.setText("⟳ Sync DB")
        self.btn_sync.clicked.connect(self._safe(self._on_sync_clicked))

        self.btn_link = QToolButton()
        self.btn_link.setText("🔗 Link")
        self.btn_link.clicked.connect(self._safe(self._download_link_dialog))

        self.btn_downloads = QToolButton()
        self.btn_downloads.setText("📂 Downloads")
        self.btn_downloads.clicked.connect(self._safe(self._on_open_downloads))

        bar.addWidget(title)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.theme_combo)
        bar.addWidget(self.btn_sync)
        bar.addWidget(self.btn_link)
        bar.addWidget(self.btn_downloads)

        # Main split: letters | table | detail
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(appbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        self.letters = QListWidget()
        self.letters.setFixedWidth(84)
        self.letters.setSpacing(4)
        self.letters.setSelectionMode(QAbstractItemView.SingleSelection)
        self._populate_letters()
        self.letters.currentItemChanged.connect(self._safe(self._on_letter_changed))

        center = QWidget()
        c = QVBoxLayout(center)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(10)

        pager = QFrame()
        pager.setObjectName("Card")
        pr = QHBoxLayout(pager)
        pr.setContentsMargins(14, 10, 14, 10)
        pr.setSpacing(10)

        self.lbl_section = QLabel("A")
        self.lbl_section.setObjectName("SectionTitle")
        self.lbl_count = QLabel("0 fontes")

        self.btn_mark_all = QPushButton("Marcar página")
        self.btn_unmark_all = QPushButton("Desmarcar")
        self.btn_mark_all.clicked.connect(self._safe(self._mark_all_page))
        self.btn_unmark_all.clicked.connect(self._safe(self._unmark_all_page))

        self.btn_batch = QPushButton("Baixar marcadas")
        self.btn_batch.setEnabled(False)
        self.btn_batch.clicked.connect(self._safe(self._download_marked_batch))

        self.btn_prev = QPushButton("←")
        self.btn_next = QPushButton("→")
        self.btn_prev.setFixedWidth(44)
        self.btn_next.setFixedWidth(44)
        self.btn_prev.clicked.connect(self._safe(self._prev_page))
        self.btn_next.clicked.connect(self._safe(self._next_page))

        pr.addWidget(self.lbl_section)
        pr.addWidget(self.lbl_count)
        pr.addStretch(1)
        pr.addWidget(self.btn_mark_all)
        pr.addWidget(self.btn_unmark_all)
        pr.addWidget(self.btn_batch)
        pr.addWidget(self.btn_prev)
        pr.addWidget(self.btn_next)

        # Model: [checkbox] [Fonte]
        self.model = QStandardItemModel(0, 2)
        self.model.setHorizontalHeaderLabels(["", "Fonte"])

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideNone)  # evita cortar com "…"

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        self.table.clicked.connect(self._safe(self._on_row_clicked))
        self.model.itemChanged.connect(self._safe(self._on_item_changed))

        c.addWidget(pager)
        c.addWidget(self.table, 1)

        # Detail panel
        detail = QWidget()
        d = QVBoxLayout(detail)
        d.setContentsMargins(0, 0, 0, 0)
        d.setSpacing(10)

        card = QFrame()
        card.setObjectName("Card")
        cd = QVBoxLayout(card)
        cd.setContentsMargins(14, 14, 14, 14)
        cd.setSpacing(10)

        self.lbl_name = QLabel("Selecione uma fonte")
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        self.lbl_name.setFont(f)

        self.preview_text = QLineEdit()
        self.preview_text.setPlaceholderText("Texto da prévia…")
        self.preview_text.setText("Teste")
        self.preview_text.textChanged.connect(self._safe(self._debounced_preview))
        self._preview_debounce = QTimer(self)
        self._preview_debounce.setSingleShot(True)
        self._preview_debounce.setInterval(350)
        self._preview_debounce.timeout.connect(self._render_preview_async)

        self.lbl_preview = QLabel("Prévia")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setMinimumHeight(220)

        self.btn_download = QPushButton("Baixar ZIP")
        self.btn_open_site = QPushButton("Abrir página")
        self.btn_download.setEnabled(False)
        self.btn_open_site.setEnabled(False)
        self.btn_download.clicked.connect(self._safe(self._download_selected))
        self.btn_open_site.clicked.connect(self._safe(self._open_page))

        btnrow = QHBoxLayout()
        btnrow.addWidget(self.btn_download)
        btnrow.addWidget(self.btn_open_site)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setWordWrap(True)

        cd.addWidget(self.lbl_name)
        cd.addWidget(self.preview_text)
        cd.addWidget(self.lbl_preview, 1)
        cd.addLayout(btnrow)
        cd.addWidget(self.lbl_meta)

        d.addWidget(card, 1)

        body.addWidget(self.letters, 0)
        body.addWidget(center, 3)
        body.addWidget(detail, 2)

        layout.addLayout(body, 1)
        self.setCentralWidget(root)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        dock = QDockWidget("Console", self)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        dock.setWidget(self.console)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    def _populate_letters(self) -> None:
        self.letters.blockSignals(True)
        try:
            self.letters.clear()
            for ch in LETTERS:
                it = QListWidgetItem(ch)
                it.setTextAlignment(Qt.AlignCenter)
                it.setData(Qt.UserRole, ch)
                self.letters.addItem(it)
            self.letters.setCurrentRow(0)
        finally:
            self.letters.blockSignals(False)

    # -------------------- Theme --------------------

    def _init_theme_combo(self) -> None:
        s = load_settings()
        mapping = {"system": 0, "dark": 1, "light": 2}
        self.theme_combo.blockSignals(True)
        try:
            self.theme_combo.setCurrentIndex(mapping.get(s.theme, 0))
        finally:
            self.theme_combo.blockSignals(False)
        app = QApplication.instance()
        if app:
            apply_theme(app, s.theme)

    def _on_theme_changed(self, *_args) -> None:
        idx = self.theme_combo.currentIndex()
        mode = "system" if idx == 0 else ("dark" if idx == 1 else "light")
        s = load_settings()
        s.theme = mode
        save_settings(s)

        app = QApplication.instance()
        if app:
            apply_theme(app, mode)

        self._log(f"Tema: {mode}")
        self._render_preview_async()

    # -------------------- Sync --------------------

    def _auto_sync_on_start(self) -> None:
        self._log("Sincronizando DB automaticamente ao abrir…")
        self._on_sync_clicked(auto=True)

    def _on_sync_clicked(self, auto: bool = False) -> None:
        if self._sync_inflight:
            self._log("Sync já está em andamento…")
            return

        local_db = db_path()

        if self.repo is not None:
            try:
                self.repo.close()
            except Exception:
                pass
            self.repo = None

        self._sync_inflight = True
        self.btn_sync.setEnabled(False)
        self.btn_sync.setText("⟳ Sincronizando…")

        def job(progress_cb):
            return self.syncer.sync_if_needed(local_db, progress=progress_cb)

        w = FunctionWorker(job)
        self._active_workers.add(w)

        def _cleanup(*_):
            self._active_workers.discard(w)

        w.signals.progress.connect(self._log)
        w.signals.finished.connect(self._safe(self._on_sync_finished))
        w.signals.finished.connect(_cleanup)
        w.signals.error.connect(self._safe(self._on_sync_error))
        w.signals.error.connect(_cleanup)

        QThreadPool.globalInstance().start(w)
        QTimer.singleShot(45000, self._safe(self._sync_watchdog))

    def _sync_watchdog(self) -> None:
        if self._sync_inflight:
            self._log("Sync travou/tempo excedido. Reabilitando botão (ver app.log).")
            self._sync_inflight = False
            self.btn_sync.setEnabled(True)
            self.btn_sync.setText("⟳ Sync DB")

    def _on_sync_error(self, trace: str) -> None:
        self._sync_inflight = False
        self.btn_sync.setEnabled(True)
        self.btn_sync.setText("⟳ Sync DB")
        self._show_error(trace)

    def _on_sync_finished(self, result) -> None:
        self._sync_inflight = False
        self.btn_sync.setEnabled(True)
        self.btn_sync.setText("⟳ Sync DB")

        reason = getattr(result, "reason", "ok")
        etag = getattr(result, "remote_etag", None) or getattr(result, "etag", None)
        size = getattr(result, "remote_size", None) or getattr(result, "size", None)
        self._log(f"Sync: {reason} (etag={etag}, size={size})")

        self._log("Carregando fontes do banco…")
        self.repo = Repo(db_path())
        self._page = Page(0, 100)
        self._refresh_fonts()
        self._log("Fontes carregadas.")
        QTimer.singleShot(0, self._force_table_refresh)

    # -------------------- Search/letter/paging --------------------

    def _debounced_search(self, *_args) -> None:
        self._search_debounce.start()

    def _on_letter_changed(self, curr, _prev) -> None:
        if not curr:
            return
        self._letter = curr.data(Qt.UserRole)
        self._page = Page(0, 100)
        self.lbl_section.setText(self._letter)
        self._refresh_fonts()

    def _prev_page(self) -> None:
        if self._page.offset <= 0:
            return
        self._page = Page(
            max(0, self._page.offset - self._page.limit), self._page.limit
        )
        self._refresh_fonts()

    def _next_page(self) -> None:
        if (self._page.offset + self._page.limit) >= self._total:
            return
        self._page = Page(self._page.offset + self._page.limit, self._page.limit)
        self._refresh_fonts()

    def _refresh_fonts(self) -> None:
        if self.repo is None:
            return

        q = self.search.text().strip()
        letter_key = self._letter

        self._total = self.repo.count_fonts(q, letter_key)
        rows = self.repo.search_fonts(
            q, letter_key, limit=self._page.limit, offset=self._page.offset
        )

        self.model.blockSignals(True)
        try:
            self.model.removeRows(0, self.model.rowCount())
            for f in rows:
                chk = QStandardItem("")
                chk.setCheckable(True)
                chk.setCheckState(Qt.Unchecked)
                chk.setData(f.slug, Qt.UserRole)

                name_item = QStandardItem(f.name)
                name_item.setData(f.slug, Qt.UserRole)
                name_item.setToolTip(f.name)  # mostra nome completo
                self.model.appendRow([chk, name_item])
        finally:
            self.model.blockSignals(False)

        start = self._page.offset
        end = min(self._total, start + self._page.limit)
        self.lbl_count.setText(
            f"{self._total} fontes • mostrando {0 if self._total==0 else start+1}–{end}"
        )

        self.btn_prev.setEnabled(self._page.offset > 0)
        self.btn_next.setEnabled((self._page.offset + self._page.limit) < self._total)

        self._clear_detail()
        self._update_batch_button()

        # força repaint imediato (Windows/Fusion)
        self.model.layoutChanged.emit()
        self.table.reset()
        QTimer.singleShot(0, self._force_table_refresh)

    # -------------------- marking / batch --------------------

    def _on_item_changed(self, _item: QStandardItem) -> None:
        self._update_batch_button()

    def _marked_slugs(self) -> list[str]:
        slugs: list[str] = []
        for r in range(self.model.rowCount()):
            chk = self.model.item(r, 0)
            if chk and chk.isCheckable() and chk.checkState() == Qt.Checked:
                slug = chk.data(Qt.UserRole)
                if slug:
                    slugs.append(str(slug))
        return slugs

    def _update_batch_button(self) -> None:
        self.btn_batch.setEnabled(len(self._marked_slugs()) > 0)

    def _mark_all_page(self) -> None:
        self.table.setUpdatesEnabled(False)
        self.model.blockSignals(True)
        try:
            for r in range(self.model.rowCount()):
                chk = self.model.item(r, 0)
                if chk and chk.isCheckable():
                    chk.setCheckState(Qt.Checked)
        finally:
            self.model.blockSignals(False)
            self.table.setUpdatesEnabled(True)

        self._update_batch_button()
        self._refresh_check_column()

    def _unmark_all_page(self) -> None:
        self.table.setUpdatesEnabled(False)
        self.model.blockSignals(True)
        try:
            for r in range(self.model.rowCount()):
                chk = self.model.item(r, 0)
                if chk and chk.isCheckable():
                    chk.setCheckState(Qt.Unchecked)
        finally:
            self.model.blockSignals(False)
            self.table.setUpdatesEnabled(True)

        self._update_batch_button()
        self._refresh_check_column()

    def _download_marked_batch(self) -> None:
        if self.repo is None:
            return
        slugs = self._marked_slugs()
        if not slugs:
            return

        self.btn_batch.setEnabled(False)
        self._log(f"Baixando em lote… ({len(slugs)} fontes)")

        def job(progress_cb):
            saved: list[Path] = []
            for i, slug in enumerate(slugs, start=1):
                f = self.repo.get_font(slug)
                if not f:
                    progress_cb(
                        f"[{i}/{len(slugs)}] Fonte não encontrada no DB: {slug}"
                    )
                    continue
                progress_cb(f"[{i}/{len(slugs)}] Baixando {f.name}…")
                p = download_zip(
                    f.download_url, f.slug, target_dir=self._downloads_target
                )
                saved.append(Path(p))
            return saved

        w = FunctionWorker(job)
        self._active_workers.add(w)

        def _cleanup(*_):
            self._active_workers.discard(w)
            self._update_batch_button()

        w.signals.progress.connect(self._log)
        w.signals.finished.connect(
            lambda saved: (
                self._log(f"Lote concluído. {len(saved)} arquivos."),
                _cleanup(),
            )
        )

        def _on_err(t: str):
            msg = (t or "").strip()
            if msg.startswith("Fonte não encontrada (404)"):
                self._log(msg)
                QMessageBox.warning(self, "Fonte não encontrada", msg)
            elif msg.startswith("Falha HTTP"):
                self._log(msg)
                QMessageBox.warning(self, "Falha no download", msg)
            else:
                self._show_error(t)
            _cleanup()

        w.signals.error.connect(_on_err)

        QThreadPool.globalInstance().start(w)

    # -------------------- selection & preview --------------------

    def _clear_detail(self) -> None:
        self._current_slug = None
        self._current_download_url = None
        self.lbl_name.setText("Selecione uma fonte")
        self.lbl_preview.setText("Prévia")
        self.lbl_preview.setPixmap(QPixmap())
        self.btn_download.setEnabled(False)
        self.btn_open_site.setEnabled(False)
        self.lbl_meta.setText("")

    def _on_row_clicked(self, index) -> None:
        if self.repo is None:
            return
        row = index.row()
        slug = self.model.item(row, 1).data(Qt.UserRole)
        self._current_slug = str(slug) if slug else None
        if not self._current_slug:
            return

        f = self.repo.get_font(self._current_slug)
        if not f:
            self._log("Fonte não encontrada no DB.")
            return

        self._current_download_url = f.download_url

        self.lbl_name.setText(f.name)
        self.btn_download.setEnabled(True)
        self.btn_open_site.setEnabled(True)

        self.lbl_meta.setText(
            f"Slug: {f.slug}\n" f"Página: {f.page_url}\n" f"Download: {f.download_url}"
        )

        self._log(f"Selecionado: {f.name} ({f.slug})")
        self._render_preview_async()

    def _debounced_preview(self, *_args) -> None:
        self._preview_debounce.start()

    def _current_fg_rgba(self) -> tuple[int, int, int, int]:
        pal = self.lbl_preview.palette()
        try:
            bg = pal.window().color()
        except Exception:
            bg = QColor(255, 255, 255)
        if not bg.isValid():
            bg = QColor(255, 255, 255)
        return (0, 0, 0, 235) if _luma(bg) > 140 else (255, 255, 255, 235)

    def _render_preview_async(self) -> None:
        if not self._current_slug or not self._current_download_url:
            return
        slug = self._current_slug
        dl = self._current_download_url
        text = self.preview_text.text().strip() or "Teste"
        fg = self._current_fg_rgba()

        self._preview_token += 1
        token = self._preview_token

        self.lbl_preview.setText("Gerando prévia offline…")
        self.lbl_preview.setPixmap(QPixmap())

        def job(progress_cb):
            return self.preview.render_preview(
                slug=slug,
                download_url=dl,
                text=text,
                progress=progress_cb,
                size=64,
                width=900,
                fg=fg,
            )

        w = FunctionWorker(job)
        self._active_workers.add(w)

        def _cleanup(*_):
            self._active_workers.discard(w)

        def _on_done(res: PreviewResult):
            if token != self._preview_token or slug != self._current_slug:
                return
            pm = QPixmap(str(res.image_path))
            if pm.isNull():
                self.lbl_preview.setText("Prévia não disponível.")
                return
            pm = pm.scaled(
                self.lbl_preview.width() - 8,
                self.lbl_preview.height() - 8,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.lbl_preview.setPixmap(pm)
            self.lbl_preview.setText("")

        w.signals.progress.connect(self._log)
        w.signals.finished.connect(lambda r: (_on_done(r), _cleanup()))
        w.signals.error.connect(
            lambda t: (
                self._log("Prévia falhou (ver app.log)."),
                self.log.error(t),
                _cleanup(),
            )
        )
        QThreadPool.globalInstance().start(w)

    # -------------------- actions --------------------

    def _open_page(self) -> None:
        if self.repo is None or not self._current_slug:
            return
        f = self.repo.get_font(self._current_slug)
        if not f:
            return
        webbrowser.open(f.page_url)

    def _download_selected(self) -> None:
        if self.repo is None or not self._current_slug:
            return
        f = self.repo.get_font(self._current_slug)
        if not f:
            return

        def job(progress_cb):
            progress_cb("Baixando ZIP…")
            return download_zip(
                f.download_url, f.slug, target_dir=self._downloads_target
            )

        w = FunctionWorker(job)
        self._active_workers.add(w)

        def _cleanup(*_):
            self._active_workers.discard(w)

        w.signals.progress.connect(self._log)
        w.signals.finished.connect(
            lambda p=None: (self._log(f"ZIP salvo em: {p}"), _cleanup())
        )
        w.signals.error.connect(lambda t: (self._show_error(t), _cleanup()))
        QThreadPool.globalInstance().start(w)

    def _download_link_dialog(self) -> None:
        url, ok = QInputDialog.getText(
            self,
            "Baixar por link",
            "Cole o link da fonte do DaFont (.font):",
        )

        if not ok or not (url or "").strip():
            return

        url = url.strip().replace("\n", "").replace("\r", "").replace(" ", "")

        from urllib.parse import urlparse

        parsed = urlparse(url)

        # auto adiciona https://
        if not parsed.scheme:
            url = "https://" + url
            parsed = urlparse(url)

        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()

        # valida domínio
        if "dafont.com" not in host:
            QMessageBox.warning(
                self,
                "Link inválido",
                "Somente links do DaFont são permitidos.",
            )
            return

        # valida final .font
        if not path.endswith(".font"):
            QMessageBox.warning(
                self,
                "Link inválido",
                "O link precisa terminar com .font\n\nExemplo:\nhttps://www.dafont.com/pt/a-abstract-groovy.font",
            )
            return

        parts = [p for p in (parsed.path or "").split("/") if p]
        # esperado: ["pt", "nome.font"]
        if len(parts) < 2 or parts[-1] in ("pt.font",):
            QMessageBox.warning(
                self,
                "Link inválido",
                "Esse link não parece ser de uma fonte.\n\nExemplo válido:\nhttps://www.dafont.com/pt/a-abstract-groovy.font",
            )
            return

        # slug vem do path
        import os

        slug = os.path.basename(path).replace(".font", "")

        self.btn_link.setEnabled(False)

        def job(progress_cb):
            return download_zip_from_url(
                url,
                suggested_name=slug,
                target_dir=self._downloads_target,
                progress=progress_cb,
            )

        w = FunctionWorker(job)
        self._active_workers.add(w)

        def _cleanup(*_):
            self._active_workers.discard(w)
            self.btn_link.setEnabled(True)

        w.signals.progress.connect(self._log)
        w.signals.finished.connect(
            lambda p=None: (self._log(f"ZIP salvo em: {p}"), _cleanup())
        )

        def _on_err(t: str):
            msg = (t or "").strip()

            # Erros esperados: mostra popup simples, sem stacktrace
            if msg.startswith("Fonte não encontrada (404)") or msg.startswith(
                "Falha HTTP"
            ):
                self._log(msg)
                QMessageBox.warning(self, "Falha no download", msg)
            else:
                self._show_error(t)

            _cleanup()

        w.signals.error.connect(_on_err)

        QThreadPool.globalInstance().start(w)

    def _on_open_downloads(self) -> None:
        open_folder(self._downloads_target)
        self._log("Abrindo pasta de downloads…")
