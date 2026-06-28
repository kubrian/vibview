"""Tests for the ModeSelectorPanel table widget."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHeaderView

from vibview.models import Mode
from vibview.renderers.qt_window import ModeSelectorPanel


class TestModeSelectorPanel:
    """Tests for the mode selector panel table widget."""

    @pytest.fixture(autouse=True)
    def _panel(self, _qapp):
        self.Panel = ModeSelectorPanel

    def test_columns_always_visible(self):
        p = self.Panel([Mode(0, [[0.0, 0.0, 0.0]])])
        assert not p.table.isColumnHidden(1)
        assert not p.table.isColumnHidden(2)

    @pytest.mark.parametrize(
        ("mode_kwargs", "col", "expected_text", "expect_italic"),
        [
            ({"frequency": None}, 1, "\u2014", True),
            ({"frequency": 1550.0}, 1, "1550.0", False),
            ({"label": None}, 2, "\u2014", True),
            ({"label": "test"}, 2, "test", False),
        ],
    )
    def test_missing_value_display(
        self, mode_kwargs, col, expected_text, expect_italic
    ):
        mode = Mode(0, [[0.0, 0.0, 0.0]], **mode_kwargs)
        p = self.Panel([mode])
        item = p.table.item(0, col)
        assert item.text() == expected_text
        assert item.font().italic() == expect_italic
        if expect_italic:
            assert item.toolTip() != ""
        else:
            assert item.toolTip() == ""

    def test_mix_of_present_and_missing_values(self):
        modes = [
            Mode(0, [[0.0, 0.0, 0.0]], frequency=1550.0, label="test"),
            Mode(1, [[0.0, 0.0, 0.0]]),
        ]
        p = self.Panel(modes)

        assert p.table.item(0, 1).text() == "1550.0"
        assert not p.table.item(0, 1).font().italic()
        assert p.table.item(0, 2).text() == "test"
        assert not p.table.item(0, 2).font().italic()

        assert p.table.item(1, 1).text() == "\u2014"
        assert p.table.item(1, 1).font().italic()
        assert p.table.item(1, 2).text() == "\u2014"
        assert p.table.item(1, 2).font().italic()

    def test_missing_freq_does_not_hide_freq_column(self):
        modes = [Mode(0, [[1.0, 0.0, 0.0]])]
        p = self.Panel(modes)
        assert not p.table.isColumnHidden(1)
        assert p.table.horizontalHeaderItem(1).text() == "Freq (?)"

    def test_empty_label_not_removed_from_layout(self):
        modes = [Mode(0, [[1.0, 0.0, 0.0]])]
        p = self.Panel(modes)
        assert not p.table.isColumnHidden(2)
        assert p.table.horizontalHeaderItem(2).text() == "Label"
        assert p.table.item(0, 2) is not None

    def test_natural_column_expands_to_fill_space(self):
        modes = [
            Mode(0, [[0.0, 0.0, 0.0]], frequency=1550.0, label="test"),
            Mode(1, [[0.0, 0.0, 0.0]]),
        ]
        p = self.Panel(modes)
        header = p.table.horizontalHeader()
        assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.ResizeToContents
        assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.ResizeToContents
        assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch

    def test_mode_buttons_exist(self):
        p = self.Panel([Mode(0, [[0.0, 0.0, 0.0]])])
        assert p._mode_buttons["animate"] is not None
        assert p._mode_buttons["static"] is not None
        assert p._mode_buttons["overlay"] is not None
        assert p._mode_buttons["animate"].isChecked()
        assert not p._mode_buttons["static"].isChecked()

    def test_mode_buttons_update_ui_instantly(self):
        p = self.Panel([Mode(0, [[0.0, 0.0, 0.0]])])
        assert p.current_mode == "animate"
        p._mode_buttons["static"].click()
        assert p.current_mode == "static"
        assert not p._mode_buttons["animate"].isChecked()
        assert p._mode_buttons["static"].isChecked()
        assert p.amplitude_spin.value() == 0.5

    def test_amplitude_is_saved_per_mode(self):
        p = self.Panel([Mode(0, [[0.0, 0.0, 0.0]])])

        assert p.amplitude_spin.value() == 0.1

        p.amplitude_spin.setValue(0.75)

        p._mode_buttons["static"].click()
        assert p.amplitude_spin.value() == 0.5

        p._mode_buttons["animate"].click()
        assert p.amplitude_spin.value() == 0.75

    def test_save_buttons_exist_and_visible_in_vib_mode(self):
        p = self.Panel([Mode(0, [[0.0, 0.0, 0.0]])])
        assert p.btn_save_gif is not None
        assert p.btn_save_gif.text() == "GIF"
        assert not p.btn_save_gif.isHidden()
        assert p.btn_save_png is not None
        assert p.btn_save_png.text() == "PNG"
        assert not p.btn_save_png.isHidden()

    def test_save_buttons_hidden_in_static_mode(self):
        p = self.Panel([Mode(0, [[0.0, 0.0, 0.0]])], initial_mode="static")
        assert p.btn_save_container.isHidden()

    def test_default_sort_by_column_0_ascending(self):
        modes = [
            Mode(1, [[1.0, 0.0, 0.0]]),
            Mode(0, [[0.0, 0.0, 1.0]]),
        ]
        p = self.Panel(modes)
        assert p._sort_column == 0
        assert p._sort_ascending is True
        assert p.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 0
        assert p.table.item(1, 0).data(Qt.ItemDataRole.UserRole) == 1

    def test_sort_by_column_1_ascending(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], frequency=1550.0),
            Mode(1, [[1.0, 0.0, 0.0]], frequency=500.0),
        ]
        p = self.Panel(modes)
        p.table.horizontalHeader().sectionClicked.emit(1)
        assert p._sort_column == 1
        assert p._sort_ascending is True
        assert p.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 1
        assert p.table.item(1, 0).data(Qt.ItemDataRole.UserRole) == 0

    def test_toggle_sort_direction(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]]),
            Mode(1, [[1.0, 0.0, 0.0]]),
        ]
        p = self.Panel(modes)
        p.table.horizontalHeader().sectionClicked.emit(0)
        assert p._sort_ascending is False
        assert p.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 1
        assert p.table.item(1, 0).data(Qt.ItemDataRole.UserRole) == 0
        p.table.horizontalHeader().sectionClicked.emit(0)
        assert p._sort_ascending is True
        assert p.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 0
        assert p.table.item(1, 0).data(Qt.ItemDataRole.UserRole) == 1

    def test_sort_column_1_then_column_0_resets(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], frequency=1550.0),
            Mode(1, [[1.0, 0.0, 0.0]], frequency=500.0),
        ]
        p = self.Panel(modes)
        p.table.horizontalHeader().sectionClicked.emit(1)
        assert p._sort_column == 1
        p.table.horizontalHeader().sectionClicked.emit(0)
        assert p._sort_column == 0
        assert p._sort_ascending is True

    def test_none_frequencies_sort_to_end_ascending(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], frequency=1550.0),
            Mode(1, [[1.0, 0.0, 0.0]], frequency=None),
            Mode(2, [[0.0, 1.0, 0.0]], frequency=500.0),
        ]
        p = self.Panel(modes)
        p.table.horizontalHeader().sectionClicked.emit(1)
        assert p.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 2
        assert p.table.item(1, 0).data(Qt.ItemDataRole.UserRole) == 0
        assert p.table.item(2, 0).data(Qt.ItemDataRole.UserRole) == 1

    def test_none_labels_sort_to_end_ascending(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], label="z"),
            Mode(1, [[1.0, 0.0, 0.0]], label=None),
            Mode(2, [[0.0, 1.0, 0.0]], label="a"),
        ]
        p = self.Panel(modes)
        p.table.horizontalHeader().sectionClicked.emit(2)
        assert p.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 2
        assert p.table.item(1, 0).data(Qt.ItemDataRole.UserRole) == 0
        assert p.table.item(2, 0).data(Qt.ItemDataRole.UserRole) == 1

    def test_on_cell_changed_stores_pending_index(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], frequency=1550.0),
            Mode(1, [[1.0, 0.0, 0.0]], frequency=500.0),
        ]
        p = self.Panel(modes)
        p.table.horizontalHeader().sectionClicked.emit(1)
        p.table.currentCellChanged.emit(0, 0, -1, -1)
        assert p._pending_mode_index == 1

    def test_initial_selection_finds_correct_row_after_sort(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], frequency=1550.0),
            Mode(1, [[1.0, 0.0, 0.0]], frequency=500.0),
        ]
        p = self.Panel(modes, initial_index=0)
        current = p.table.currentItem()
        assert current is not None
        assert current.data(Qt.ItemDataRole.UserRole) == 0

    def test_initial_selection_with_non_zero_index(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], frequency=1550.0),
            Mode(1, [[1.0, 0.0, 0.0]], frequency=500.0),
        ]
        p = self.Panel(modes, initial_index=1)
        current = p.table.currentItem()
        assert current is not None
        assert current.data(Qt.ItemDataRole.UserRole) == 1

    @pytest.mark.parametrize("row_idx,expect_colored", [(0, True), (1, False)])
    def test_imaginary_frequency_colored(self, row_idx, expect_colored):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], frequency=-500.0),
            Mode(1, [[1.0, 0.0, 0.0]], frequency=500.0),
        ]
        p = self.Panel(modes, imaginary_color="#ff4444")
        for col in range(3):
            item = p.table.item(row_idx, col)
            assert item is not None
            if expect_colored:
                assert item.foreground().color().name() == "#ff4444"
            else:
                assert item.foreground().color().name() != "#ff4444"

    def test_imaginary_colored_persists_after_sort(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]], frequency=-500.0),
            Mode(1, [[1.0, 0.0, 0.0]], frequency=500.0),
            Mode(2, [[0.0, 0.0, 0.0]], frequency=-200.0),
        ]
        p = self.Panel(modes, imaginary_color="#ff4444")
        p.table.horizontalHeader().sectionClicked.emit(1)
        for row in range(p.table.rowCount()):
            idx = p.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            is_imag = any(
                m.frequency is not None and m.frequency < 0
                for m in modes
                if m.index == idx
            )
            for col in range(3):
                item = p.table.item(row, col)
                assert item is not None
                if is_imag:
                    assert item.foreground().color().name() == "#ff4444"
                else:
                    assert item.foreground().color().name() != "#ff4444"

    def test_sort_indicator_shown_on_header(self):
        p = self.Panel([Mode(0, [[0.0, 0.0, 0.0]])])
        header = p.table.horizontalHeader()
        assert header.isSortIndicatorShown()

    def test_sort_indicator_order_matches_state(self):
        modes = [
            Mode(0, [[0.0, 0.0, 1.0]]),
            Mode(1, [[1.0, 0.0, 0.0]]),
        ]
        p = self.Panel(modes)
        header = p.table.horizontalHeader()
        assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        assert p._sort_ascending is True
        p.table.horizontalHeader().sectionClicked.emit(0)
        assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
        assert p._sort_ascending is False
        p.table.horizontalHeader().sectionClicked.emit(0)
        assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        assert p._sort_ascending is True

    def test_header_labels_bold(self):
        p = self.Panel([Mode(0, [[0.0, 0.0, 0.0]])])
        for i in range(3):
            item = p.table.horizontalHeaderItem(i)
            assert item is not None
            assert item.font().bold()

    def test_display_shows_mode_index_not_row_number(self):
        modes = [
            Mode(5, [[1.0, 0.0, 0.0]]),
            Mode(0, [[0.0, 0.0, 1.0]]),
        ]
        p = self.Panel(modes)
        assert p.table.item(0, 0).text() == "0"
        assert p.table.item(1, 0).text() == "5"
