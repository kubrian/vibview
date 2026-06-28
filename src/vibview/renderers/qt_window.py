"""Qt UI components for the mode selector panel and main window."""

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from vispy.scene import SceneCanvas

from vibview.models import Mode


class ModeSelectorPanel(QWidget):
    """Side panel with a sortable mode table and animation controls."""

    PANEL_WIDTH = 260

    MODE_NAMES = ["animate", "static", "overlay"]

    def __init__(
        self,
        modes: list[Mode],
        initial_index: int = 0,
        initial_mode: str = "animate",
        initial_amplitudes: dict[str, float] | None = None,
        initial_period: float = 1.0,
        frequency_units: str = "?",
        imaginary_color: str = "#ff4444",
        qpoints: list[list[float]] | None = None,
        initial_qpoint: int = 0,
        initial_supercell: tuple[int, int, int] = (1, 1, 1),
    ):
        super().__init__()
        self.on_apply: Callable[[], None] | None = None
        self.on_save_animation: (
            Callable[[str, str, Callable[[int, int], None]], None] | None
        ) = None

        self.current_mode = initial_mode
        self.amplitudes = initial_amplitudes or {
            "animate": 0.1,
            "static": 0.5,
            "overlay": 0.5,
        }
        self._modes = modes
        self._pending_mode_index = initial_index
        self._imaginary_color = imaginary_color
        self._sort_column = 0
        self._sort_ascending = True

        self._qpoints = qpoints or []

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)

        self._build_data_section(layout, initial_qpoint, initial_supercell)
        self._build_mode_table(layout, frequency_units)
        self._add_separator(layout)
        self._build_animation_controls(layout, initial_mode, initial_period)
        self._add_separator(layout)
        self._build_view_mode_buttons(layout, initial_mode)
        self._build_apply_button(layout)

        self.setLayout(layout)
        self._finalize_init(initial_index, initial_mode)

    def _build_data_section(self, layout, initial_qpoint, initial_supercell):
        layout.addWidget(QLabel("<b>Data</b>"))
        self._structure_container = QWidget()
        struct_layout = QVBoxLayout(self._structure_container)
        struct_layout.setContentsMargins(0, 0, 0, 0)

        qp_row = QHBoxLayout()
        self._qpoint_spin = QSpinBox()
        self._qpoint_spin.setRange(0, max(len(self._qpoints) - 1, 0))
        self._qpoint_spin.setValue(initial_qpoint)
        self._qpoint_spin.valueChanged.connect(self._update_qpoint_pos_label)
        self._qpoint_label = QLabel("q-point:")
        self._qpoint_pos_label = QLabel("")
        self._update_qpoint_pos_label(initial_qpoint)
        qp_row.addWidget(self._qpoint_label)
        qp_row.addWidget(self._qpoint_spin)
        qp_row.addWidget(self._qpoint_pos_label, stretch=1)
        struct_layout.addLayout(qp_row)

        sc_row = QHBoxLayout()
        sc_row.addWidget(QLabel("Supercell"))
        self._sc_nx = QSpinBox()
        self._sc_nx.setRange(1, 5)
        self._sc_nx.setValue(initial_supercell[0])
        self._sc_ny = QSpinBox()
        self._sc_ny.setRange(1, 5)
        self._sc_ny.setValue(initial_supercell[1])
        self._sc_nz = QSpinBox()
        self._sc_nz.setRange(1, 5)
        self._sc_nz.setValue(initial_supercell[2])
        sc_row.addWidget(self._sc_nx)
        sc_row.addWidget(self._sc_ny)
        sc_row.addWidget(self._sc_nz)
        struct_layout.addLayout(sc_row)

        is_periodic = len(self._qpoints) > 0
        self._structure_container.setVisible(is_periodic)
        layout.addWidget(self._structure_container)

    def _build_mode_table(self, layout, frequency_units):
        self.table = QTableWidget(0, 3)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        self.table.setHorizontalHeaderLabels(
            ["#", f"Freq ({frequency_units})", "Label"]
        )

        hheader = self.table.horizontalHeader()
        hheader.setSortIndicatorShown(True)
        hheader.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        hheader.sectionClicked.connect(self._on_header_clicked)

        for i in range(3):
            item = self.table.horizontalHeaderItem(i)
            if item is not None:
                f = item.font()
                f.setBold(True)
                item.setFont(f)

        self._set_stretch_columns()
        self.table.currentCellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table, stretch=1)

    def _build_animation_controls(self, layout, initial_mode, initial_period):
        initial_amplitude = self.amplitudes[initial_mode]
        layout.addWidget(QLabel("<b>Animation</b>"))

        self.amplitude_spin = QDoubleSpinBox()
        self.amplitude_spin.setRange(0.05, 1.0)
        self.amplitude_spin.setSingleStep(0.05)
        self.amplitude_spin.setDecimals(2)
        self.amplitude_spin.setValue(initial_amplitude)
        self.amplitude_spin.setSuffix(" \u00c5")
        self.amp_container = QWidget()
        amp_row = QHBoxLayout(self.amp_container)
        amp_row.setContentsMargins(0, 0, 0, 0)
        amp_row.addWidget(QLabel("Amplitude:"))
        amp_row.addWidget(self.amplitude_spin)
        layout.addWidget(self.amp_container)

        self.period_spin = QDoubleSpinBox()
        self.period_spin.setRange(0.1, 5.0)
        self.period_spin.setSingleStep(0.1)
        self.period_spin.setDecimals(1)
        self.period_spin.setValue(initial_period)
        self.period_spin.setSuffix(" s")
        self.period_container = QWidget()
        period_row = QHBoxLayout(self.period_container)
        period_row.setContentsMargins(0, 0, 0, 0)
        period_row.addWidget(QLabel("Period:"))
        period_row.addWidget(self.period_spin)
        layout.addWidget(self.period_container)

        self.btn_save_gif = QPushButton("GIF")
        self.btn_save_gif.clicked.connect(lambda: self._on_save("gif"))
        self.btn_save_png = QPushButton("PNG")
        self.btn_save_png.clicked.connect(
            lambda: self._on_save("png", is_sequence=True)
        )
        self.btn_save_mp4 = QPushButton("MP4")
        self.btn_save_mp4.clicked.connect(lambda: self._on_save("mp4"))

        btn_save_layout = QHBoxLayout()
        btn_save_layout.setContentsMargins(0, 0, 0, 0)
        btn_save_layout.addWidget(QLabel("Save as:"))
        btn_save_layout.addWidget(self.btn_save_gif)
        btn_save_layout.addWidget(self.btn_save_png)
        btn_save_layout.addWidget(self.btn_save_mp4)
        self.btn_save_container = QWidget()
        self.btn_save_container.setLayout(btn_save_layout)
        layout.addWidget(self.btn_save_container)

    def _build_view_mode_buttons(self, layout, initial_mode):
        layout.addWidget(QLabel("<b>View Mode</b>"))
        self.mode_button_group = QButtonGroup()
        self.mode_button_group.setExclusive(True)
        self._mode_buttons: dict[str, QPushButton] = {}

        btn_layout = QHBoxLayout()
        for name in self.MODE_NAMES:
            btn = QPushButton(name.capitalize())
            btn.setCheckable(True)
            btn.setChecked(initial_mode == name)
            btn.clicked.connect(lambda checked, n=name: self._on_mode_button_clicked(n))
            self.mode_button_group.addButton(btn)
            self._mode_buttons[name] = btn
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

    def _build_apply_button(self, layout):
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self._on_apply)
        layout.addWidget(self.btn_apply)

    def _finalize_init(self, initial_index, initial_mode):
        self._rebuild_table()

        if self._modes:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if (
                    item is not None
                    and item.data(Qt.ItemDataRole.UserRole) == initial_index
                ):
                    self.table.setCurrentCell(row, 0)
                    self.table.scrollToItem(item)
                    break

        is_vibration = initial_mode == "animate"
        self.period_container.setVisible(is_vibration)
        self.btn_save_container.setVisible(is_vibration)

        self._update_button_styles()

    def _set_stretch_columns(self):
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(1)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

    @staticmethod
    def _add_separator(layout: QVBoxLayout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

    @staticmethod
    def _make_placeholder(tooltip: str) -> QTableWidgetItem:
        item = QTableWidgetItem("\u2014")
        f = item.font()
        f.setItalic(True)
        item.setFont(f)
        item.setToolTip(tooltip)
        return item

    def _on_header_clicked(self, section: int):
        if section == self._sort_column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = section
            self._sort_ascending = True
        order = (
            Qt.SortOrder.AscendingOrder
            if self._sort_ascending
            else Qt.SortOrder.DescendingOrder
        )
        self.table.horizontalHeader().setSortIndicator(section, order)
        self._rebuild_table()

    def _rebuild_table(self):
        current_item = self.table.currentItem()
        current_index = (
            current_item.data(Qt.ItemDataRole.UserRole)
            if current_item is not None
            else None
        )

        self.table.setRowCount(0)

        sorted_modes = list(self._modes)
        if self._sort_column == 0:
            sorted_modes.sort(key=lambda m: m.index, reverse=not self._sort_ascending)
        elif self._sort_column == 1:

            def freq_key(m):
                f = m.frequency
                return (1, 0.0) if f is None else (0, f)

            sorted_modes.sort(key=freq_key, reverse=not self._sort_ascending)
        elif self._sort_column == 2:

            def label_key(m):
                lab = m.label
                return (1, "") if lab is None else (0, lab)

            sorted_modes.sort(key=label_key, reverse=not self._sort_ascending)

        self.table.setRowCount(len(sorted_modes))
        for row, m in enumerate(sorted_modes):
            item = QTableWidgetItem(str(m.index))
            item.setData(Qt.ItemDataRole.UserRole, m.index)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 0, item)

            if m.frequency is not None:
                freq_item = QTableWidgetItem(str(m.frequency))
                freq_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, 1, freq_item)
            else:
                self.table.setItem(row, 1, self._make_placeholder("No frequency data"))

            if m.label is not None:
                self.table.setItem(row, 2, QTableWidgetItem(m.label))
            else:
                self.table.setItem(row, 2, self._make_placeholder("No label"))

        imag_color = QColor(self._imaginary_color)
        for row, m in enumerate(sorted_modes):
            if m.frequency is not None and m.frequency < 0:
                for col in range(3):
                    item = self.table.item(row, col)
                    if item is not None:
                        item.setForeground(imag_color)

        if current_index is not None:
            self.table.currentCellChanged.disconnect(self._on_cell_changed)
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if (
                    item is not None
                    and item.data(Qt.ItemDataRole.UserRole) == current_index
                ):
                    self.table.setCurrentCell(row, 0)
                    break
            self.table.currentCellChanged.connect(self._on_cell_changed)

    def _on_mode_button_clicked(self, mode_name: str):
        self.amplitudes[self.current_mode] = self.amplitude_spin.value()

        self.current_mode = mode_name
        self._update_button_styles()

        self.amplitude_spin.blockSignals(True)
        self.amplitude_spin.setValue(self.amplitudes[mode_name])
        self.amplitude_spin.blockSignals(False)

        is_vibration = mode_name == "animate"
        self.amp_container.setVisible(True)
        self.period_container.setVisible(is_vibration)
        self.btn_save_container.setVisible(is_vibration)

    def _update_button_styles(self):
        active_style = "background-color: #555; color: white;"
        inactive_style = ""
        for btn in self._mode_buttons.values():
            btn.setStyleSheet(active_style if btn.isChecked() else inactive_style)

    def _on_cell_changed(self, row: int, col: int, prev_row: int, prev_col: int):
        item = self.table.item(row, 0)
        if item is not None:
            self._pending_mode_index = item.data(Qt.ItemDataRole.UserRole)

    def _update_qpoint_pos_label(self, idx: int):
        if 0 <= idx < len(self._qpoints):
            pos = self._qpoints[idx]
            self._qpoint_pos_label.setText(
                f"[{pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}]"
            )

    def _on_apply(self):
        if self.on_apply:
            self.on_apply()

    def set_modes(self, modes: list[Mode]):
        self._modes = modes
        self._rebuild_table()
        self._pending_mode_index = min(self._pending_mode_index, max(0, len(modes) - 1))

    @staticmethod
    def _progress_task(progress: QProgressDialog, current: int, total: int):
        progress.setValue(int(current / total * 100))
        QApplication.processEvents()

    def _on_save(self, fmt: str, is_sequence: bool = False):
        if not self.on_save_animation:
            return

        if is_sequence:
            path = QFileDialog.getExistingDirectory(
                self, f"Save {fmt.upper()} Sequence To"
            )
            if not path:
                return
            name = str(Path(path) / "frame")
        else:
            ext = fmt.upper()
            path, _ = QFileDialog.getSaveFileName(
                self, f"Save As {ext}", "", f"{ext} (*.{fmt})"
            )
            if not path:
                return
            if not path.lower().endswith(f".{fmt}"):
                path += f".{fmt}"
            name = str(Path(path).with_suffix(""))

        progress = QProgressDialog(f"Exporting {fmt.upper()}\u2026", None, 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        progress.setMinimumDuration(0)
        progress.show()

        self.on_save_animation(
            fmt,
            name,
            progress_callback=lambda c, t: self._progress_task(progress, c, t),
        )
        progress.close()


class VibviewWindow(QMainWindow):
    """Main window with a fixed mode panel on the left and 3D canvas."""

    TITLE_BAR_OVERHEAD = 80

    def __init__(
        self,
        canvas: SceneCanvas,
        modes: list[Mode],
        initial_index: int = 0,
        initial_mode: str = "animate",
        initial_amplitudes: dict[str, float] | None = None,
        initial_period: float = 1.0,
        frequency_units: str = "?",
        imaginary_color: str = "#ff4444",
        qpoints: list[list[float]] | None = None,
        initial_qpoint: int = 0,
        initial_supercell: tuple[int, int, int] = (1, 1, 1),
    ):
        super().__init__()
        self.setWindowTitle("VibView")
        self.on_camera_reset: Callable[[], None] | None = None

        self.panel = ModeSelectorPanel(
            modes,
            initial_index=initial_index,
            initial_mode=initial_mode,
            initial_amplitudes=initial_amplitudes,
            initial_period=initial_period,
            frequency_units=frequency_units,
            imaginary_color=imaginary_color,
            qpoints=qpoints,
            initial_qpoint=initial_qpoint,
            initial_supercell=initial_supercell,
        )
        self.panel.setMinimumWidth(self.panel.PANEL_WIDTH)

        canvas.native.setMinimumSize(400, 300)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.addWidget(self.panel)
        splitter.addWidget(canvas.native)
        splitter.setSizes([self.panel.PANEL_WIDTH, 580])

        self.setCentralWidget(splitter)
        self._min_width = (
            self.panel.minimumWidth()
            + canvas.native.minimumWidth()
            + splitter.handleWidth()
        )
        self._min_height = max(
            canvas.native.minimumHeight() + self.TITLE_BAR_OVERHEAD, 480
        )
        self.setMinimumSize(self._min_width, self._min_height)
        self.resize(800, 600)

    def resizeEvent(self, event):
        new_w = max(event.size().width(), self._min_width)
        new_h = max(event.size().height(), self._min_height)
        if new_w != event.size().width() or new_h != event.size().height():
            self.resize(new_w, new_h)
            return
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key.Key_R:
            if self.on_camera_reset:
                self.on_camera_reset()
        else:
            super().keyPressEvent(event)
