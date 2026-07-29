"""Desktop window.

The tool list and every parameter form are built from the registry, so the GUI
never needs editing when an operation is added. Work runs on a worker thread to
keep the window responsive on large documents.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QSize, QUrl, Qt, QThread, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.pipeline import Step, run_pipeline
from ..core.registry import REGISTRY, InputSlot, Operation, Param, categories, load_operations

# ponytail: __file__ points inside PyInstaller's PYZ archive when frozen, not a
# real path on disk -- sys._MEIPASS is the actual extracted bundle root there.
_ASSETS_DIR = (
    Path(sys._MEIPASS) / "senpais_pdf_workshop" / "gui" / "assets"
    if getattr(sys, "frozen", False)
    else Path(__file__).parent / "assets"
)
APP_ICON_PATH = _ASSETS_DIR / "icon.png"

# ponytail: one flat light theme via QSS, not a full theming system --
# add prefers-color-scheme-style dark variant if users actually ask for it.
STYLE_SHEET = """
QMainWindow, QWidget { background: #f5f6fb; font-size: 13px; color: #1f2430; }
QTreeWidget, QListWidget {
    background: #ffffff; border: 1px solid #e3e5ef; border-radius: 8px;
    padding: 4px; outline: none;
}
QTreeWidget::item, QListWidget::item { padding: 6px 4px; border-radius: 6px; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #eef0ff; color: #3730a3; }
QTreeWidget::item:hover:!selected, QListWidget::item:hover:!selected { background: #f3f4fb; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff; border: 1px solid #d9dbe8; border-radius: 6px; padding: 5px 8px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #6366f1; }
QPushButton {
    background: #ffffff; border: 1px solid #d9dbe8; border-radius: 6px; padding: 6px 14px;
}
QPushButton:hover { background: #f3f4fb; }
QPushButton:pressed { background: #e9eafc; }
QPushButton:disabled { color: #a1a5b7; background: #f5f6fb; }
QPushButton#runButton {
    background: #4f46e5; color: white; font-weight: 600; border: none;
    padding: 10px 18px; font-size: 14px;
}
QPushButton#runButton:hover { background: #4338ca; }
QPushButton#runButton:disabled { background: #c7c9f5; color: #f0f0ff; }
QPushButton#linkButton {
    background: transparent; border: none; color: #4f46e5; padding: 2px; text-align: left;
}
QPushButton#linkButton:hover { color: #4338ca; text-decoration: underline; }
QFrame#card { background: #ffffff; border: 1px solid #e3e5ef; border-radius: 10px; }
QLabel#cardTitle { font-weight: 600; color: #4b4f66; }
QTextBrowser#guide { background: #ffffff; border: 1px solid #e3e5ef; border-radius: 10px; padding: 6px; }
QProgressBar { background: #eef0ff; border: none; border-radius: 3px; }
QProgressBar::chunk { background: #6366f1; border-radius: 3px; }
QStatusBar { background: #f5f6fb; }
QSplitter::handle { background: #f5f6fb; width: 8px; }
"""

CATEGORY_ICONS = {
    "Organise": "🗂️",
    "Layout": "📐",
    "Annotate": "✏️",
    "Metadata": "🏷️",
    "Forms": "📋",
    "Attachments": "📎",
    "Extract": "📤",
    "Security": "🔒",
    "Convert": "🔁",
}

# ponytail: presentation-only copy, kept in the GUI layer rather than added to
# the registry schema since it's UI phrasing, not data other front ends need.
FILE_ORDER_HINTS = {
    "insert": "Order matters — add the base PDF first, then the PDF to insert.",
    "overlay": "Order matters — add the base PDF first, then the PDF to place over/under it.",
    "watermark_image": "Order matters — add the PDF first, then the stamp image.",
    "add_attachment": "Order matters — add the PDF first, then the file to embed.",
    "merge": "Files are joined in the order you add them, so add them in the order they should appear.",
}

FILE_ICONS = {
    ".pdf": "📄",
    ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️", ".bmp": "🖼️", ".tiff": "🖼️",
    ".doc": "📝", ".docx": "📝", ".odt": "📝",
    ".xls": "📊", ".xlsx": "📊", ".ods": "📊",
    ".ppt": "📽️", ".pptx": "📽️", ".odp": "📽️",
}


class Worker(QObject):
    """Runs one operation off the UI thread."""

    done = Signal(list)
    failed = Signal(str)

    def __init__(self, op: Operation, sources: list[Path], out_dir: Path, values: dict):
        super().__init__()
        self._op, self._sources, self._out, self._values = op, sources, out_dir, values

    def run(self) -> None:
        try:
            self.done.emit(self._op.run(self._sources, self._out, **self._values))
        except Exception as exc:
            self.failed.emit(str(exc))


class BatchWorker(QObject):
    """Runs a single-file operation once per source file, independently."""

    progress = Signal(int, int)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, op: Operation, sources: list[Path], out_dir: Path, values: dict):
        super().__init__()
        self._op, self._sources, self._out, self._values = op, sources, out_dir, values

    def run(self) -> None:
        written: list[Path] = []
        total = len(self._sources)
        for index, src in enumerate(self._sources, start=1):
            try:
                written.extend(self._op.run([src], self._out, **self._values))
            except Exception as exc:
                self.failed.emit(f"{src.name}: {exc}")
                return
            self.progress.emit(index, total)
        self.done.emit(written)


def render_thumbnail_frames(path: Path, max_pages: int = 60) -> list[tuple[bytes, int, int]]:
    """RGB888 raw frames for the first `max_pages` pages, one per page, in order.

    A pure function (no Qt) so it's testable without a QApplication; ThumbnailWorker
    just wraps it for the off-thread call. ponytail: capped at 60 pages for preview
    responsiveness -- reorder still works past that, the thumbnail strip just stops.
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    frames: list[tuple[bytes, int, int]] = []
    for index, page in enumerate(pdf):
        if index >= max_pages:
            break
        width_pt, height_pt = page.get_size()
        scale = 90 / max(width_pt, height_pt, 1)
        image = page.render(scale=scale).to_pil().convert("RGB")
        frames.append((image.tobytes(), image.width, image.height))
    return frames


class ThumbnailWorker(QObject):
    """Renders page thumbnails off the UI thread (QPixmap isn't thread-safe,
    so this hands back raw bytes and the main thread builds the QImage)."""

    done = Signal(list)
    failed = Signal(str)

    def __init__(self, path: Path):
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            self.done.emit(render_thumbnail_frames(self._path))
        except Exception as exc:
            self.failed.emit(str(exc))


class FileDropList(QListWidget):
    """A file list that also accepts drag-and-dropped files."""

    filesDropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


def build_field(param: Param) -> QWidget:
    """Return the right input widget for a parameter kind."""
    if param.kind == "bool":
        box = QCheckBox()
        box.setChecked(bool(param.default))
        return box
    if param.kind == "choice":
        combo = QComboBox()
        combo.addItems(param.choices)
        if param.default in param.choices:
            combo.setCurrentText(str(param.default))
        return combo
    if param.kind == "int":
        spin = QSpinBox()
        spin.setRange(int(param.minimum or -10**6), int(param.maximum or 10**6))
        spin.setValue(int(param.default or 0))
        return spin
    if param.kind == "float":
        spin = QDoubleSpinBox()
        spin.setRange(param.minimum or -10**6, param.maximum or 10**6)
        spin.setValue(float(param.default or 0))
        return spin

    line = QLineEdit(str(param.default or ""))
    if param.kind == "password":
        line.setEchoMode(QLineEdit.EchoMode.Password)
    if param.help:
        line.setPlaceholderText(param.help)
    return line


def read_field(widget: QWidget):
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        return widget.value()
    return widget.text()


def _guide_html() -> str:
    """The home-page walkthrough, built from the registry so it can never drift
    out of sync with what the tools actually do."""
    parts = [
        "<h2>👋 Welcome to Senpai's Pdf Workshop</h2>",
        f"<p>{len(REGISTRY)} tools for working with PDFs, all running locally on this "
        "machine — nothing is uploaded anywhere.</p>",
        "<h3>How to use it</h3>",
        "<ol>"
        "<li>Search or pick a tool from the list on the left.</li>"
        "<li>Add files — drag and drop them onto the Files box, or click Add files.</li>"
        "<li>Set any options for that tool (most have sensible defaults already filled in).</li>"
        "<li>Click Run. Results are written to the output folder shown above the Run button.</li>"
        "</ol>",
        "<h3>What each tool does</h3>",
    ]
    for category, ops in categories().items():
        icon = CATEGORY_ICONS.get(category, "📄")
        parts.append(f"<p><b>{icon} {html.escape(category)}</b></p><ul>")
        for op in ops:
            parts.append(
                f"<li><b>{html.escape(op.label)}</b> — {html.escape(op.summary)}</li>"
            )
        parts.append("</ul>")
    return "".join(parts)


def _clear_layout(layout) -> None:
    while layout.count():
        widget = layout.takeAt(0).widget()
        if widget:
            widget.deleteLater()


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)
    label = QLabel(title)
    label.setObjectName("cardTitle")
    layout.addWidget(label)
    return frame, layout


class PipelineWorker(QObject):
    """Runs a pipeline off the UI thread."""

    done = Signal(list)
    failed = Signal(str)

    def __init__(self, steps: list[Step], sources: list[Path], out_dir: Path):
        super().__init__()
        self._steps, self._sources, self._out = steps, sources, out_dir

    def run(self) -> None:
        try:
            self.done.emit(run_pipeline(self._steps, self._sources, self._out))
        except Exception as exc:
            self.failed.emit(str(exc))


class PipelineDialog(QDialog):
    """Chain operations, each running with its default parameters.

    ponytail: per-step parameter customization is the obvious next step --
    this ships with each step using REGISTRY defaults, which covers a real
    slice of pipelines (rotate + watermark, compress + OCR, ...) without the
    much larger UI a full per-step form builder would need.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Build a pipeline")
        self.resize(480, 480)

        self._sources: list[Path] = []
        self._steps: list[Step] = []
        self._out_dir = Path.home() / "Senpai's Pdf Workshop"
        self._thread: QThread | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Files"))
        self.file_list = FileDropList()
        self.file_list.setMaximumHeight(80)
        self.file_list.filesDropped.connect(self._add_files)
        layout.addWidget(self.file_list)
        add_files = QPushButton("➕ Add files")
        add_files.clicked.connect(self._choose_files)
        layout.addWidget(add_files)

        layout.addWidget(QLabel("Steps (run top to bottom, each with its default options)"))
        self.step_list = QListWidget()
        layout.addWidget(self.step_list)

        add_row = QHBoxLayout()
        self.op_combo = QComboBox()
        for category, ops in categories().items():
            for op in ops:
                self.op_combo.addItem(f"[{category}] {op.label}", op.id)
        add_row.addWidget(self.op_combo, stretch=1)
        add_step = QPushButton("➕ Add step")
        add_step.clicked.connect(self._add_step)
        add_row.addWidget(add_step)
        remove_step = QPushButton("Remove step")
        remove_step.clicked.connect(self._remove_step)
        add_row.addWidget(remove_step)
        layout.addLayout(add_row)

        self.out_button = QPushButton(f"📁 Save to: {self._out_dir}")
        self.out_button.clicked.connect(self._choose_out_dir)
        layout.addWidget(self.out_button)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox()
        self.run_button = buttons.addButton("Run pipeline", QDialogButtonBox.ButtonRole.AcceptRole)
        self.run_button.clicked.connect(self._run)
        close_button = buttons.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        close_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add files", "", "PDF files (*.pdf)")
        self._add_files([Path(p) for p in paths])

    def _add_files(self, paths: list[Path]) -> None:
        for p in paths:
            self._sources.append(p)
            self.file_list.addItem(p.name)
            self.file_list.item(self.file_list.count() - 1).setToolTip(str(p))

    def _add_step(self) -> None:
        op_id = self.op_combo.currentData()
        if not op_id:
            return
        self._steps.append(Step(op_id))
        self.step_list.addItem(f"{len(self._steps)}. {REGISTRY[op_id].label}")

    def _remove_step(self) -> None:
        row = self.step_list.currentRow()
        if row < 0:
            return
        self.step_list.takeItem(row)
        del self._steps[row]
        for i in range(self.step_list.count()):
            self.step_list.item(i).setText(f"{i + 1}. {REGISTRY[self._steps[i].op_id].label}")

    def _choose_out_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if chosen:
            self._out_dir = Path(chosen)
            self.out_button.setText(f"📁 Save to: {self._out_dir}")

    def _run(self) -> None:
        if not self._sources:
            self.status_label.setText("⚠️  Add at least one file first.")
            return
        if not self._steps:
            self.status_label.setText("⚠️  Add at least one step first.")
            return
        self.run_button.setEnabled(False)
        self.status_label.setText("Running…")

        self._thread = QThread()
        self._worker = PipelineWorker(list(self._steps), list(self._sources), self._out_dir)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_done(self, written: list) -> None:
        self._finish()
        self.status_label.setText(f"✅ Wrote {len(written)} file(s) to {self._out_dir}")

    def _on_failed(self, message: str) -> None:
        self._finish()
        self.status_label.setText(f"⚠️  {message}")

    def _finish(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self.run_button.setEnabled(True)


class Window(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Senpai's Pdf Workshop")
        self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.resize(1060, 660)

        self._out_dir: Path = Path.home() / "Senpai's Pdf Workshop"
        self._fields: dict[str, QWidget] = {}
        self._op: Operation | None = None
        self._thread: QThread | None = None
        self._last_output_dir: Path | None = None
        self._slots: tuple[InputSlot, ...] = ()
        self._slot_lists: dict[str, FileDropList] = {}
        self._slot_sources: dict[str, list[Path]] = {}
        self._thumb_thread: QThread | None = None
        self._settings = QSettings("SenpaisPdfWorkshop", "SenpaisPdfWorkshop")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_tool_list())
        splitter.addWidget(self._build_workspace())
        splitter.setSizes([280, 780])
        self.setCentralWidget(splitter)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"{len(REGISTRY)} tools ready.")

    # -- left pane ------------------------------------------------------

    def _build_tool_list(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        search = QLineEdit()
        search.setPlaceholderText("🔍  Search tools…")
        search.textChanged.connect(self._filter_tools)
        layout.addWidget(search)

        pipeline_button = QPushButton("🔗 Build a pipeline…")
        pipeline_button.clicked.connect(self._open_pipeline_dialog)
        layout.addWidget(pipeline_button)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        for category, ops in categories().items():
            icon = CATEGORY_ICONS.get(category, "📄")
            parent = QTreeWidgetItem([f"{icon}  {category}"])
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            for op in ops:
                child = QTreeWidgetItem([op.label])
                child.setData(0, Qt.ItemDataRole.UserRole, op.id)
                child.setToolTip(0, op.summary)
                parent.addChild(child)
            self.tree.addTopLevelItem(parent)
        self.tree.expandAll()
        self.tree.itemClicked.connect(self._on_tool_chosen)
        layout.addWidget(self.tree)
        return panel

    def _open_pipeline_dialog(self) -> None:
        PipelineDialog(self).exec()

    def _filter_tools(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            any_visible = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                op = REGISTRY[child.data(0, Qt.ItemDataRole.UserRole)]
                match = not needle or needle in op.label.lower() or needle in op.summary.lower()
                child.setHidden(not match)
                any_visible = any_visible or match
            parent.setHidden(not any_visible)
            if needle:
                parent.setExpanded(any_visible)

    # -- right pane -----------------------------------------------------

    def _build_workspace(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.icon_label = QLabel("👋")
        self.icon_label.setStyleSheet("font-size: 30px;")
        header.addWidget(self.icon_label)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.heading = QLabel("Welcome to Senpai's Pdf Workshop")
        self.heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.summary = QLabel(
            f"{len(REGISTRY)} tools to organise, edit, and convert PDFs — "
            "search or pick one on the left to get started."
        )
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #6b7280;")
        titles.addWidget(self.heading)
        titles.addWidget(self.summary)
        header.addLayout(titles, stretch=1)
        layout.addLayout(header)

        self.home_guide = QTextBrowser()
        self.home_guide.setObjectName("guide")
        self.home_guide.setHtml(_guide_html())
        layout.addWidget(self.home_guide, stretch=1)

        self.tool_panel = QWidget()
        tool_layout = QVBoxLayout(self.tool_panel)
        tool_layout.setContentsMargins(0, 0, 0, 0)
        tool_layout.setSpacing(12)
        self.tool_panel.setVisible(False)
        layout.addWidget(self.tool_panel, stretch=1)

        files_card, files_layout = _card("Files")
        self.files_body = QWidget()
        self.files_body_layout = QVBoxLayout(self.files_body)
        self.files_body_layout.setContentsMargins(0, 0, 0, 0)
        self.files_body_layout.setSpacing(10)
        files_layout.addWidget(self.files_body)

        self.batch_checkbox = QCheckBox("Batch — run separately for each file")
        self.batch_checkbox.setVisible(False)
        self.batch_checkbox.toggled.connect(self._on_batch_toggled)
        files_layout.addWidget(self.batch_checkbox)

        out_row = QHBoxLayout()
        self.recent_button = QPushButton("🕒 Recent")
        self.recent_button.clicked.connect(self._show_recent_menu)
        out_row.addWidget(self.recent_button)
        out_row.addStretch()
        self.out_button = QPushButton(f"📁 Save to: {self._out_dir}")
        self.out_button.clicked.connect(self._choose_out_dir)
        out_row.addWidget(self.out_button)
        files_layout.addLayout(out_row)
        tool_layout.addWidget(files_card)

        self.reorder_card, reorder_layout = _card("Drag to reorder pages")
        self.reorder_thumbs = QListWidget()
        self.reorder_thumbs.setViewMode(QListWidget.ViewMode.IconMode)
        self.reorder_thumbs.setFlow(QListWidget.Flow.LeftToRight)
        self.reorder_thumbs.setWrapping(False)
        self.reorder_thumbs.setMovement(QListWidget.Movement.Snap)
        self.reorder_thumbs.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.reorder_thumbs.setIconSize(QSize(70, 90))
        self.reorder_thumbs.setSpacing(6)
        self.reorder_thumbs.setFixedHeight(140)
        self.reorder_thumbs.model().rowsMoved.connect(lambda *_: self._sync_order_field())
        reorder_layout.addWidget(self.reorder_thumbs)
        self.reorder_card.setVisible(False)
        tool_layout.addWidget(self.reorder_card)

        options_card, options_layout = _card("Options")
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        options_layout.addWidget(self.form_host)
        self.no_options_label = QLabel("This tool needs no extra options — just add files and run.")
        self.no_options_label.setStyleSheet("color: #9ca0b4;")
        options_layout.addWidget(self.no_options_label)
        tool_layout.addWidget(options_card)

        tool_layout.addStretch()

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        tool_layout.addWidget(self.progress)

        run_row = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("runButton")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._run)
        run_row.addWidget(self.run_button, stretch=1)
        self.open_folder_button = QPushButton("Open output folder ↗")
        self.open_folder_button.setObjectName("linkButton")
        self.open_folder_button.setVisible(False)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        run_row.addWidget(self.open_folder_button)
        tool_layout.addLayout(run_row)
        return panel

    # -- behaviour ------------------------------------------------------

    def _on_tool_chosen(self, item: QTreeWidgetItem) -> None:
        op_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not op_id:
            return
        self._op = REGISTRY[op_id]
        self.home_guide.setVisible(False)
        self.tool_panel.setVisible(True)
        self.icon_label.setText(CATEGORY_ICONS.get(self._op.category, "📄"))
        self.heading.setText(self._op.label)
        self.summary.setText(self._op.summary)
        self.run_button.setText(f"▶  {self._op.label}")
        self.open_folder_button.setVisible(False)

        synthetic = not self._op.input_slots
        self._slots = self._op.input_slots or (
            InputSlot("files", "Files", self._op.inputs, self._op.input_formats),
        )
        self._slot_lists.clear()
        self._slot_sources = {slot.name: [] for slot in self._slots}
        _clear_layout(self.files_body_layout)
        for slot in self._slots:
            self.files_body_layout.addWidget(
                self._build_slot_section(slot, self._slot_hint(slot, synthetic))
            )
        self.run_button.setEnabled(self._sources_ready())

        self.batch_checkbox.setChecked(False)
        self.batch_checkbox.setVisible(synthetic and self._op.inputs == "one")
        self.reorder_thumbs.clear()
        self.reorder_card.setVisible(self._op.id == "reorder")

        while self.form.rowCount():
            self.form.removeRow(0)
        self._fields.clear()
        for param in self._op.params:
            widget = build_field(param)
            self._fields[param.name] = widget
            self.form.addRow(param.label, widget)
        self.form_host.setVisible(bool(self._op.params))
        self.no_options_label.setVisible(not self._op.params)

    def _slot_hint(self, slot: InputSlot, synthetic: bool) -> str:
        if synthetic and self._op and self._op.id in FILE_ORDER_HINTS:
            return FILE_ORDER_HINTS[self._op.id]
        formats = ", ".join(ext.lstrip(".") for ext in slot.formats) if slot.formats else "any"
        if slot.arity == "many":
            return f"Add one or more files ({formats})."
        return f"Add exactly one file ({formats})."

    def _build_slot_section(self, slot: InputSlot, hint: str) -> QWidget:
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        label = QLabel(slot.label)
        label.setStyleSheet("font-weight: 600;")
        section_layout.addWidget(label)

        file_list = FileDropList()
        file_list.setMaximumHeight(90 if len(self._slots) > 1 else 150)
        file_list.filesDropped.connect(lambda paths, name=slot.name: self._add_slot_paths(name, paths))
        section_layout.addWidget(file_list)
        self._slot_lists[slot.name] = file_list

        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #9ca0b4; font-size: 11px;")
        section_layout.addWidget(hint_label)

        buttons = QHBoxLayout()
        add = QPushButton("➕ Add")
        add.clicked.connect(lambda: self._add_slot_files(slot.name))
        remove = QPushButton("Remove selected")
        remove.clicked.connect(lambda: self._remove_slot_selected(slot.name))
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self._clear_slot(slot.name))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(clear)
        buttons.addStretch()
        section_layout.addLayout(buttons)
        return section

    def _sources_ready(self) -> bool:
        return bool(self._slots) and all(self._slot_sources.get(s.name) for s in self._slots)

    def _slot_by_name(self, name: str) -> InputSlot:
        return next(s for s in self._slots if s.name == name)

    def _add_slot_files(self, slot_name: str) -> None:
        slot = self._slot_by_name(slot_name)
        pattern = " ".join(f"*{ext}" for ext in slot.formats)
        paths, _ = QFileDialog.getOpenFileNames(
            self, f"Add {slot.label}", "", f"Supported files ({pattern})"
        )
        self._add_slot_paths(slot_name, [Path(p) for p in paths])

    def _add_slot_paths(self, slot_name: str, paths: list[Path]) -> None:
        slot = self._slot_by_name(slot_name)
        matched = [p for p in paths if not slot.formats or p.suffix.lower() in slot.formats]
        if not matched:
            return
        file_list = self._slot_lists[slot_name]
        if slot.arity == "one" and not self._is_batch_active():
            matched = matched[-1:]
            file_list.clear()
            self._slot_sources[slot_name] = []
        for p in matched:
            self._slot_sources[slot_name].append(p)
            icon = FILE_ICONS.get(p.suffix.lower(), "📄")
            file_list.addItem(f"{icon}  {p.name}")
            file_list.item(file_list.count() - 1).setToolTip(str(p))
        self.run_button.setEnabled(self._sources_ready())
        self._remember_recent(matched)
        self._refresh_reorder_thumbs()

    def _remove_slot_selected(self, slot_name: str) -> None:
        file_list = self._slot_lists[slot_name]
        for item in file_list.selectedItems():
            row = file_list.row(item)
            file_list.takeItem(row)
            del self._slot_sources[slot_name][row]
        self.run_button.setEnabled(self._sources_ready())
        self._refresh_reorder_thumbs()

    def _clear_slot(self, slot_name: str) -> None:
        self._slot_lists[slot_name].clear()
        self._slot_sources[slot_name] = []
        self.run_button.setEnabled(False)
        self._refresh_reorder_thumbs()

    def _choose_out_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if chosen:
            self._out_dir = Path(chosen)
            self.out_button.setText(f"📁 Save to: {self._out_dir}")

    def _run(self) -> None:
        if not self._op:
            return
        sources = [p for slot in self._slots for p in self._slot_sources.get(slot.name, [])]
        values = {name: read_field(w) for name, w in self._fields.items()}
        self.run_button.setEnabled(False)
        self.open_folder_button.setVisible(False)
        self.progress.setVisible(True)
        self.statusBar().showMessage(f"Running {self._op.label}…")

        self._thread = QThread()
        if self._is_batch_active():
            self.progress.setRange(0, len(sources))
            self.progress.setValue(0)
            self._worker = BatchWorker(self._op, sources, self._out_dir, values)
            self._worker.progress.connect(self._on_batch_progress)
        else:
            self.progress.setRange(0, 0)
            self._worker = Worker(self._op, sources, self._out_dir, values)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_batch_progress(self, done: int, total: int) -> None:
        self.progress.setValue(done)
        self.statusBar().showMessage(f"Running {self._op.label}… ({done}/{total})")

    def _is_batch_active(self) -> bool:
        return self.batch_checkbox.isVisible() and self.batch_checkbox.isChecked()

    def _on_batch_toggled(self, _checked: bool) -> None:
        # switching modes changes whether the single-file slot accepts one file
        # or many, so start that slot over rather than leaving a stale selection
        for slot in self._slots:
            self._clear_slot(slot.name)

    def _on_done(self, written: list) -> None:
        self._finish()
        count = len(written)
        where = written[0].parent if written else self._out_dir
        self._last_output_dir = where
        self.open_folder_button.setVisible(True)
        self.statusBar().showMessage(
            f"✅ Wrote {count} file{'s' if count != 1 else ''} to {where}"
        )

    def _on_failed(self, message: str) -> None:
        self._finish()
        self.statusBar().showMessage(f"⚠️  {message}")

    def _finish(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self.progress.setVisible(False)
        self.run_button.setEnabled(True)

    def _open_output_folder(self) -> None:
        if self._last_output_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output_dir)))

    # -- recent files -----------------------------------------------------

    def _recent_files(self) -> list[str]:
        return list(self._settings.value("recentFiles", [], type=list) or [])

    def _remember_recent(self, paths: list[Path]) -> None:
        recent = self._recent_files()
        for p in paths:
            s = str(p)
            if s in recent:
                recent.remove(s)
            recent.insert(0, s)
        self._settings.setValue("recentFiles", recent[:10])

    def _show_recent_menu(self) -> None:
        recent = self._recent_files()
        menu = QMenu(self)
        if not recent:
            menu.addAction("No recent files yet").setEnabled(False)
        else:
            for path_str in recent:
                menu.addAction(path_str).triggered.connect(
                    lambda checked=False, p=path_str: self._add_recent_to_slot(p)
                )
        menu.exec(self.recent_button.mapToGlobal(self.recent_button.rect().bottomLeft()))

    def _add_recent_to_slot(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            self.statusBar().showMessage(f"⚠️  {path.name} no longer exists.")
            return
        for slot in self._slots:
            if not slot.formats or path.suffix.lower() in slot.formats:
                self._add_slot_paths(slot.name, [path])
                return

    # -- drag-to-reorder thumbnails -----------------------------------------

    def _refresh_reorder_thumbs(self) -> None:
        if not self._op or self._op.id != "reorder":
            return
        files = self._slot_sources.get("files", [])
        if len(files) == 1:
            self._load_reorder_thumbnails(files[0])
        else:
            self.reorder_thumbs.clear()

    def _load_reorder_thumbnails(self, path: Path) -> None:
        self.reorder_thumbs.clear()
        self._thumb_thread = QThread()
        self._thumb_worker = ThumbnailWorker(path)
        self._thumb_worker.moveToThread(self._thumb_thread)
        self._thumb_thread.started.connect(self._thumb_worker.run)
        self._thumb_worker.done.connect(self._on_thumbnails_ready)
        self._thumb_worker.failed.connect(
            lambda msg: self.statusBar().showMessage(f"⚠️  Couldn't preview pages: {msg}")
        )
        self._thumb_worker.done.connect(self._thumb_thread.quit)
        self._thumb_worker.failed.connect(self._thumb_thread.quit)
        self._thumb_thread.start()

    def _on_thumbnails_ready(self, frames: list) -> None:
        self.reorder_thumbs.clear()
        for index, (data, width, height) in enumerate(frames, start=1):
            image = QImage(data, width, height, width * 3, QImage.Format.Format_RGB888)
            item = QListWidgetItem(QIcon(QPixmap.fromImage(image)), "")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.reorder_thumbs.addItem(item)
        self._sync_order_field()

    def _sync_order_field(self) -> None:
        field = self._fields.get("order")
        if field is None or self.reorder_thumbs.count() == 0:
            return
        order = ",".join(
            str(self.reorder_thumbs.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.reorder_thumbs.count())
        )
        field.setText(order)


def main() -> int:
    load_operations()
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    window = Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
