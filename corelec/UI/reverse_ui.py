from __future__ import annotations

from corelec.UI.qt_compat import (
    Qt, Signal,
    QColor, QBrush, QFontDatabase,
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QPushButton, QListWidget, QLabel,
)
from typing import Dict, Any, List


class ReverseByteTable(QTableWidget):
    # emit when a checkbox is toggled: dict contains type, offset, label, checked
    itemToggled = Signal(dict)
    interpretToggled = Signal(dict)  # {'type':int,'offsets':list,'interpretation':str,'checked':bool}

    def __init__(self, typ: int, parent=None):
        super().__init__(17, 6, parent)
        self.typ = typ
        self.setHorizontalHeaderLabels(['Plot', 'Offset', 'Int', 'Hex', 'Known', 'Name'])
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.horizontalHeader().setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_ctx)
        self.cellChanged.connect(self._on_cell_changed)
        self.known_offsets: List[int] = []
        self._suppress_signal = False
        self.checked_offsets: set[int] = set()
        self._interpret_checks: dict[tuple[tuple[int, ...], str], bool] = {}
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

    def populate(self, parsed: Dict[str, Any]):
        # parsed contains raw_b0..raw_b16, _known_offsets, _offset_names
        raw = [parsed.get(f'raw_b{i}', 0) for i in range(17)]
        self.known_offsets = parsed.get('_known_offsets', []) or []
        offset_names: Dict[int, str] = parsed.get('_offset_names', {}) or {}

        self._suppress_signal = True
        for i in range(17):
            # Plot checkbox
            item_chk = QTableWidgetItem('')
            item_chk.setFlags(item_chk.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item_chk.setCheckState(Qt.CheckState.Checked if i in self.checked_offsets else Qt.CheckState.Unchecked)
            self.setItem(i, 0, item_chk)
            # offset
            off = QTableWidgetItem(str(i))
            off.setFlags(off.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(i, 1, off)
            # int
            val = raw[i]
            it_val = QTableWidgetItem(str(val))
            it_val.setFlags(it_val.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(i, 2, it_val)
            # hex
            it_hex = QTableWidgetItem(hex(val))
            it_hex.setFlags(it_hex.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(i, 3, it_hex)
            # known
            known = i in self.known_offsets
            it_known = QTableWidgetItem('yes' if known else 'no')
            it_known.setFlags(it_known.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(i, 4, it_known)
            # name
            it_name = QTableWidgetItem(offset_names.get(i, ''))
            it_name.setFlags(it_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(i, 5, it_name)
            # color rows by known/unknown
            bg_color = QColor('#d7f0dc') if known else QColor('#f7dfcf')
            fg_color = QColor('#1a2a1a') if known else QColor('#3a1500')
            bg_brush = QBrush(bg_color)
            fg_brush = QBrush(fg_color)
            for col in range(6):
                cell = self.item(i, col)
                if cell is not None:
                    cell.setBackground(bg_brush)
                    cell.setForeground(fg_brush)
        self._suppress_signal = False

    def _on_cell_changed(self, row, column):
        if self._suppress_signal:
            return
        if column == 0:
            item = self.item(row, 0)
            checked = item.checkState() == Qt.CheckState.Checked
            if checked:
                self.checked_offsets.add(row)
            else:
                self.checked_offsets.discard(row)
            payload = {'type': self.typ, 'offset': row, 'label': f'{self.typ}[{row}]', 'checked': checked}
            self.itemToggled.emit(payload)

    def _on_ctx(self, pos):
        rows = sorted({idx.row() for idx in self.selectedIndexes()})
        if not rows:
            return
        # check if consecutive
        consecutive = all(rows[i] + 1 == rows[i + 1] for i in range(len(rows) - 1))
        unknown_only = all(r not in self.known_offsets for r in rows)
        menu = QMenu(self)
        if consecutive and unknown_only:
            # offer interpretations
            actions = [
                ('int16_be', 'Interpret as int16 BE'),
                ('int16_le', 'Interpret as int16 LE'),
                ('uint16_be', 'Interpret as uint16 BE'),
                ('float16_be', 'Interpret as float16 BE'),
                ('string', 'Interpret as ASCII string'),
                ('bitmask', 'Interpret as bitmask')
            ]
            row_key = tuple(rows)
            for key, label in actions:
                a = menu.addAction(label)
                a.setCheckable(True)
                a.setChecked(self._interpret_checks.get((row_key, key), False))
                a.toggled.connect(lambda checked, k=key, r=rows: self._request_interp(r, k, checked))
        menu.exec(self.mapToGlobal(pos))

    def _request_interp(self, rows: List[int], kind: str, checked: bool):
        self._interpret_checks[(tuple(rows), kind)] = checked
        self.interpretToggled.emit({'type': self.typ, 'offsets': rows, 'interpretation': kind, 'checked': checked})

    def set_checked(self, offset: int, checked: bool):
        self._suppress_signal = True
        if checked:
            self.checked_offsets.add(offset)
        else:
            self.checked_offsets.discard(offset)
        item = self.item(offset, 0)
        if item:
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._suppress_signal = False

    def set_interpret_checked(self, offsets: List[int], kind: str, checked: bool):
        self._interpret_checks[(tuple(offsets), kind)] = checked


class ReversePanel(QWidget):
    addSeries = Signal(dict)  # {'label':..., 'type':..., 'offsets':..., 'color':...}
    removeSeries = Signal(str)  # label

    def __init__(self, typ: int, parent=None):
        super().__init__(parent)
        self.typ = typ
        self.layout = QVBoxLayout()
        self.raw_text = QLabel('')
        self.raw_text.setWordWrap(True)
        self.toggle_raw_btn = QPushButton('Masquer / Afficher trame brute')
        self.toggle_raw_btn.setCheckable(True)
        self.toggle_raw_btn.setChecked(True)
        self.toggle_raw_btn.clicked.connect(self._toggle_raw)
        self.table = ReverseByteTable(typ)
        self.table.itemToggled.connect(self._on_item_toggled)
        self.table.interpretToggled.connect(self._on_interpret_requested)
        self.layout.addWidget(self.toggle_raw_btn)
        self.layout.addWidget(self.raw_text)
        self.layout.addWidget(self.table)
        self.setLayout(self.layout)

    def _toggle_raw(self):
        self.raw_text.setVisible(self.toggle_raw_btn.isChecked())

    def update_from_parsed(self, parsed: Dict[str, Any]):
        # parsed: dict from ctypes_frames
        pretty = ', '.join(f"{k}={v}" for k, v in parsed.items() if not k.startswith('raw_b'))
        self.raw_text.setText(pretty)
        self.table.populate(parsed)

    def _on_item_toggled(self, payload: dict):
        # forward as addSeries/removeSeries
        if payload['checked']:
            self.addSeries.emit({'label': payload['label'], 'type': payload['type'], 'offsets': [payload['offset']]})
        else:
            self.removeSeries.emit(payload['label'])

    def _on_interpret_requested(self, info: dict):
        # simply emit as addSeries for now, label includes interp
        label = f"{info['type']}[{info['offsets'][0]}-{info['offsets'][-1]}] {info['interpretation']}"
        if info.get('checked', False):
            self.addSeries.emit({'label': label, 'type': info['type'], 'offsets': info['offsets'], 'interpretation': info['interpretation']})
        else:
            self.removeSeries.emit(label)


class GraphSelectionPanel(QWidget):
    removeRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout()
        self.list = QListWidget()
        self.remove_btn = QPushButton('Supprimer sélection')
        self.remove_btn.clicked.connect(self._remove_selected)
        self.layout.addWidget(QLabel('Séries ajoutées au graphe:'))
        self.layout.addWidget(self.list)
        self.layout.addWidget(self.remove_btn)
        self.setLayout(self.layout)

    def add_item(self, label: str):
        for i in range(self.list.count()):
            if self.list.item(i).text() == label:
                return
        self.list.addItem(label)

    def remove_item(self, label: str):
        for i in range(self.list.count()):
            if self.list.item(i).text() == label:
                self.list.takeItem(i)
                break

    def _remove_selected(self):
        items = self.list.selectedItems()
        for it in items:
            label = it.text()
            self.removeRequested.emit(label)
            self.remove_item(label)
