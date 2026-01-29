from __future__ import annotations

import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dafont_app.db.repo import Repo
from dafont_app.services.catalog import CATEGORIES, CATEGORY_BY_KEY
from dafont_app.services.dafont_client import DaFontClient
from dafont_app.services.downloader import download_zip
from dafont_app.services.updater import DatabaseUpdater, UpdateResult
from dafont_app.ui.workers import FunctionWorker
from dafont_app.utils.paths import db_path, downloads_dir
from dafont_app.utils.preview import preview_image_url
from dafont_app.utils.app_logging import get_logger, log_path


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.log = get_logger()
        self.setWindowTitle("DaFont Downloader")
        self.resize(1150, 720)

        self._init_state()
        self._build_ui()

        QTimer.singleShot(0, self._safe(self._refresh_fonts))

        self._log("Aplicação iniciada.")
        self._log(f"Pasta de downloads: {self._downloads_target}")
        self._log(f"Arquivo de log: {log_path()}")

    # =============================================================
    # STATE
    # =============================================================

    def _init_state(self) -> None:
        self.thread_pool = QThreadPool.globalInstance()

        self.repo = Repo(db_path())
        self.client = DaFontClient()
        self.repo.upsert_categories(CATEGORIES)

        self._downloads_target = downloads_dir()

        self._is_updating_db = False
        self._current_font_slug: str | None = None

        # preview control
        self._preview_tokens: list[str] = []
        self._preview_token_index = 0
        self._preview_request_url: str | None = None
        self._preview_reply = None
        self._preview_generation = 0
        self._details_generation = 0

        self._net: QNetworkAccessManager | None = None

        # debounce typing
        self._preview_debounce = QTimer(self)
        self._preview_debounce.setSingleShot(True)
        self._preview_debounce.setInterval(350)
        self._preview_debounce.timeout.connect(self._refresh_preview)

        # widgets
        self.search = None
        self.categories = None
        self.model = None
        self.table = None

        self.lbl_title = None
        self.preview_text = None
        self.lbl_preview = None
        self.lbl_meta = None

        self.btn_download = None
        self.btn_open_page = None
        self.btn_update = None
        self.btn_choose_dir = None

        self.link_input = None
        self.btn_link_download = None
        self.link_log = None

        self.status = None
        self.console = None

    # =============================================================
    # HELPERS
    # =============================================================

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
        if self.console:
            self.console.append(f"[{ts}] {msg}")

    def _show_error(self, trace: str) -> None:
        self.log.error(trace)
        QMessageBox.critical(self, "Erro", trace)

    # =============================================================
    # UI
    # =============================================================

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)

        top = QHBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar fontes…")

        self.btn_update = QPushButton("Atualizar Banco")
        self.btn_choose_dir = QPushButton("Pasta Download…")

        top.addWidget(self.search, 1)
        top.addWidget(self.btn_update)
        top.addWidget(self.btn_choose_dir)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)

        # cria tabs (model/table antes!)
        tabs = QTabWidget()
        tabs.addTab(self._build_tab_browser(), "Fontes")
        tabs.addTab(self._build_tab_link(), "Baixar por link")

        # categorias
        self.categories = QListWidget()
        self.categories.setMaximumWidth(220)
        self._populate_categories_safely()
        self.categories.itemSelectionChanged.connect(self._safe(self._refresh_fonts))

        splitter.addWidget(self.categories)
        splitter.addWidget(tabs)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        dock = QDockWidget("Console", self)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(
            "QTextEdit{background:#0f1117;color:#ddd;font-family:Consolas;font-size:11px;}"
        )
        dock.setWidget(self.console)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        # conecta topo depois
        self.search.textChanged.connect(self._safe(self._refresh_fonts))
        self.btn_update.clicked.connect(self._safe(self._on_update_database))
        self.btn_choose_dir.clicked.connect(self._safe(self._on_choose_download_dir))

    # -------------------------------------------------------------

    def _build_tab_browser(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)

        self.model = QStandardItemModel(0, 3)
        self.model.setHorizontalHeaderLabels(["Nome", "Categoria", "Slug"])

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.clicked.connect(self._safe(self._on_row_selected))

        detail = QWidget()
        d = QVBoxLayout(detail)

        self.lbl_title = QLabel("Selecione uma fonte")
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        self.lbl_title.setFont(f)

        self.preview_text = QLineEdit()
        self.preview_text.setText("Teste")
        self.preview_text.textChanged.connect(self._safe(self._on_preview_text_changed))

        self.lbl_preview = QLabel("(prévia)")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setMinimumHeight(160)

        self.btn_download = QPushButton("Download")
        self.btn_download.setEnabled(False)
        self.btn_download.clicked.connect(self._safe(self._on_download_selected))

        self.btn_open_page = QPushButton("Abrir no site")
        self.btn_open_page.setEnabled(False)
        self.btn_open_page.clicked.connect(self._safe(self._on_open_page))

        self.lbl_meta = QLabel("")
        self.lbl_meta.setWordWrap(True)

        d.addWidget(self.lbl_title)
        d.addWidget(self.preview_text)
        d.addWidget(self.lbl_preview, 1)
        d.addWidget(self.lbl_meta)

        row = QHBoxLayout()
        row.addWidget(self.btn_download)
        row.addWidget(self.btn_open_page)
        d.addLayout(row)

        layout.addWidget(self.table, 2)
        layout.addWidget(detail, 1)
        return w

    # -------------------------------------------------------------

    def _build_tab_link(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)

        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("Cole link .font ou dl/?f=…")

        self.btn_link_download = QPushButton("Baixar")
        self.btn_link_download.clicked.connect(self._safe(self._on_download_by_link))

        self.link_log = QTextEdit()
        self.link_log.setReadOnly(True)

        l.addWidget(self.link_input)
        l.addWidget(self.btn_link_download)
        l.addWidget(self.link_log, 1)
        return w

    # =============================================================
    # CATEGORIES
    # =============================================================

    def _populate_categories_safely(self) -> None:
        self.categories.blockSignals(True)
        try:
            self.categories.clear()

            all_item = QListWidgetItem("Todas")
            all_item.setData(Qt.UserRole, "all")
            self.categories.addItem(all_item)

            for c in CATEGORIES:
                it = QListWidgetItem(c.name_pt)
                it.setData(Qt.UserRole, c.key)
                self.categories.addItem(it)

            self.categories.setCurrentRow(0)
        finally:
            self.categories.blockSignals(False)

    def _current_category_key(self) -> str:
        items = self.categories.selectedItems()
        if not items:
            return "all"
        return str(items[0].data(Qt.UserRole))

    # =============================================================
    # LIST
    # =============================================================

    def _refresh_fonts(self) -> None:
        if self._is_updating_db:
            return
        if not self.search or not self.model or not self.table:
            return

        q = self.search.text()
        cat_key = self._current_category_key()

        fonts = self.repo.search_fonts(q, cat_key, limit=4000)

        self.model.removeRows(0, self.model.rowCount())

        for f in fonts:
            cat_name = (
                CATEGORY_BY_KEY.get(f.category_key).name_pt
                if f.category_key in CATEGORY_BY_KEY
                else f.category_key
            )
            row = [
                QStandardItem(f.name),
                QStandardItem(cat_name),
                QStandardItem(f.slug),
            ]
            for it in row:
                it.setData(f.slug, Qt.UserRole)
            self.model.appendRow(row)

        self.table.resizeColumnsToContents()
        self._clear_detail()

    def _clear_detail(self) -> None:
        self._current_font_slug = None
        self._preview_tokens = []
        self._preview_token_index = 0
        if self.lbl_preview:
            self.lbl_preview.setText("(prévia)")
        if self.btn_download:
            self.btn_download.setEnabled(False)
        if self.btn_open_page:
            self.btn_open_page.setEnabled(False)

    # =============================================================
    # SELECTION
    # =============================================================

    def _selected_slug(self) -> str | None:
        sel = self.table.selectionModel()
        if not sel:
            return None
        rows = sel.selectedRows()
        if not rows:
            return None
        return self.model.item(rows[0].row(), 0).data(Qt.UserRole)

    def _on_row_selected(self, *_args) -> None:
        slug = self._selected_slug()
        if not slug:
            return

        self._preview_generation += 1
        self._details_generation += 1

        try:
            if self._preview_reply:
                self._preview_reply.abort()
                self._preview_reply.deleteLater()
                self._preview_reply = None
        except Exception:
            pass

        f = self.repo.get_font(slug)
        if not f:
            return

        self._current_font_slug = slug

        self.lbl_title.setText(f.name)
        self.btn_download.setEnabled(True)
        self.btn_open_page.setEnabled(True)

        self._log(f"Selecionado: {f.name} ({slug})")

        self._load_details_and_preview(f)

    # =============================================================
    # DETAILS / PREVIEW
    # =============================================================

    def _on_preview_text_changed(self) -> None:
        self._preview_debounce.start()

    def _load_details_and_preview(self, font) -> None:
        gen = self._details_generation

        def job(progress_cb):
            return self.client.fetch_font_details(font.page_url)

        worker = FunctionWorker(job)
        worker.signals.finished.connect(
            lambda d: self._on_details_loaded_guarded(gen, font.slug, d)
        )
        worker.signals.error.connect(self._show_error)
        self.thread_pool.start(worker)

    def _on_details_loaded_guarded(self, gen: int, slug: str, details: dict) -> None:
        if gen != self._details_generation:
            return
        self._on_details_loaded(slug, details)

    def _on_details_loaded(self, slug: str, details: dict) -> None:
        tokens = details.get("preview_tokens") or []
        self._preview_tokens = list(tokens)
        self._preview_token_index = 0

        if not self._preview_tokens:
            self.lbl_preview.setText("(prévia indisponível)")
            return

        self._preview_request_url = None
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not self._current_font_slug or not self._preview_tokens:
            return

        token = self._preview_tokens[self._preview_token_index]
        text = self.preview_text.text().strip() or " "
        url = preview_image_url(text, token, size=63)

        if self._preview_request_url == url:
            return

        self._preview_request_url = url
        self._preview_generation += 1
        gen = self._preview_generation

        if self._net is None:
            self._net = QNetworkAccessManager(self)

        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", b"Mozilla/5.0")

        reply = self._net.get(req)
        self._preview_reply = reply
        reply.finished.connect(lambda: self._on_preview_reply_guarded(gen, reply))

    def _on_preview_reply_guarded(self, gen: int, reply) -> None:
        if gen != self._preview_generation:
            reply.deleteLater()
            return
        self._on_preview_reply(reply)

    def _on_preview_reply(self, reply) -> None:
        data = bytes(reply.readAll())
        pix = QPixmap()
        pix.loadFromData(data)

        if pix.isNull():
            self._preview_token_index += 1
            if self._preview_token_index < len(self._preview_tokens):
                self._preview_request_url = None
                reply.deleteLater()
                self._refresh_preview()
                return
            self.lbl_preview.setText("(prévia indisponível)")
        else:
            self.lbl_preview.setPixmap(
                pix.scaled(
                    self.lbl_preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

        reply.deleteLater()
        self._preview_reply = None

    # =============================================================
    # ACTIONS
    # =============================================================

    def _on_open_page(self) -> None:
        f = self.repo.get_font(self._current_font_slug)
        if f:
            webbrowser.open(f.page_url)

    def _on_choose_download_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Escolha pasta", str(self._downloads_target)
        )
        if d:
            self._downloads_target = Path(d)

    def _on_download_selected(self) -> None:
        f = self.repo.get_font(self._current_font_slug)
        if not f:
            return

        def job(progress_cb):
            return download_zip(
                f.download_url, f.slug, target_dir=self._downloads_target
            )

        worker = FunctionWorker(job)
        worker.signals.finished.connect(
            lambda p: QMessageBox.information(self, "Download", f"Salvo em:\n{p}")
        )
        worker.signals.error.connect(self._show_error)
        self.thread_pool.start(worker)

    def _on_download_by_link(self) -> None:
        link = self.link_input.text().strip()
        if not link:
            return

        def job(progress_cb):
            details = self.client.normalize_any_link(link)
            p = download_zip(
                details["download_url"],
                details["slug"],
                target_dir=self._downloads_target,
            )
            return details, p

        worker = FunctionWorker(job)
        worker.signals.finished.connect(
            lambda r: self.link_log.append(f"OK: {r[0]['slug']} -> {r[1]}")
        )
        worker.signals.error.connect(self._show_error)
        self.thread_pool.start(worker)

    # =============================================================
    # UPDATE DB
    # =============================================================

    def _on_update_database(self) -> None:
        if self._is_updating_db:
            return

        self._is_updating_db = True
        self._log("Iniciando atualização do banco…")

        def job(progress_cb):
            updater = DatabaseUpdater(self.repo, self.client, progress_cb)
            return updater.update_all_categories()

        worker = FunctionWorker(job)
        worker.signals.finished.connect(self._on_update_done)
        worker.signals.error.connect(self._show_error)
        self.thread_pool.start(worker)

    def _on_update_done(self, result: UpdateResult) -> None:
        self._is_updating_db = False
        self._refresh_fonts()
        self._log(
            f"Banco atualizado: +{result.new_fonts} novas "
            f"(vistas: {result.total_seen})"
        )
