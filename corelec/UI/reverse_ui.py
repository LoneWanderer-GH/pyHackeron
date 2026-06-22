from __future__ import annotations

from corelec.UI.qt_compat import (
    Qt, Signal,
    QColor, QBrush, QFontDatabase,
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QPushButton, QListWidget, QLabel,
)
from typing import Dict, Any, List

# Octets structurels du protocole — non cochables, non sélectionnables
_STRUCTURAL_OFFSETS: frozenset[int] = frozenset({0, 1, 15, 16})


class ReverseByteTable(QTableWidget):
    # emit when a checkbox is toggled: dict contains type, offset, label, checked
    itemToggled = Signal(dict)
    # {'type':int,'offsets':list,'interpretation':str,'checked':bool}
    interpretToggled = Signal(dict)

    def __init__(self, typ: int, parent: QWidget | None = None):
        super().__init__(17, 6, parent)
        self.typ = typ
        self.setHorizontalHeaderLabels(
            ['Plot', 'Offset', 'Int', 'Hex', 'Known', 'Name'])
        self.setFont(QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont))
        self.horizontalHeader().setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
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

        # Sauvegarder la sélection avant de recréer les items (setItem() détruit le modèle de sélection)
        selected_rows = {idx.row() for idx in self.selectedIndexes()}

        self._suppress_signal = True
        for i in range(17):
            is_structural = i in _STRUCTURAL_OFFSETS
            # Plot checkbox — désactivé pour les octets structurels
            item_chk = QTableWidgetItem('')
            if not is_structural:
                item_chk.setFlags(
                    item_chk.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                item_chk.setCheckState(
                    Qt.CheckState.Checked if i in self.checked_offsets else Qt.CheckState.Unchecked)
            else:
                item_chk.setFlags(Qt.ItemFlag.NoItemFlags)
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
            # color rows by known/unknown; grey for structural
            if is_structural:
                bg_color = QColor('#404040')
                fg_color = QColor('#909090')
            elif known:
                bg_color = QColor('#d7f0dc')
                fg_color = QColor('#1a2a1a')
            else:
                bg_color = QColor('#f7dfcf')
                fg_color = QColor('#3a1500')
            bg_brush = QBrush(bg_color)
            fg_brush = QBrush(fg_color)
            for col in range(6):
                cell = self.item(i, col)
                if cell is not None:
                    cell.setBackground(bg_brush)
                    cell.setForeground(fg_brush)
                    if is_structural:
                        cell.setFlags(Qt.ItemFlag.NoItemFlags)
        self._suppress_signal = False

        # Restaurer la sélection après recréation des items
        if selected_rows:
            for row in selected_rows:
                if row in _STRUCTURAL_OFFSETS:
                    continue
                for col in range(self.columnCount()):
                    cell = self.item(row, col)
                    if cell and bool(cell.flags() & Qt.ItemFlag.ItemIsSelectable):
                        cell.setSelected(True)

    def _on_cell_changed(self, row:int, column:int):
        if self._suppress_signal:
            return
        if column == 0:
            item = self.item(row, 0)
            assert(item is not None)
            checked = item.checkState() == Qt.CheckState.Checked
            if checked:
                self.checked_offsets.add(row)
            else:
                self.checked_offsets.discard(row)
            payload : dict[str, Any] = {'type': self.typ, 'offset': row,
                       'label': f'{self.typ}[{row}]', 'checked': checked}
            self.itemToggled.emit(payload)

    def _on_ctx(self, pos):
        rows = sorted({idx.row() for idx in self.selectedIndexes()})
        # Exclure les octets structurels de toute interprétation
        rows = [r for r in rows if r not in _STRUCTURAL_OFFSETS]
        if not rows:
            return
        consecutive = all(rows[i] + 1 == rows[i + 1]
                          for i in range(len(rows) - 1))
        unknown_only = all(r not in self.known_offsets for r in rows)
        menu = QMenu(self)
        if consecutive and unknown_only:
            row_key = tuple(rows)
            # Interprétations 16 bits : exactement 2 octets adjacents requis
            if len(rows) == 2:
                for key, label in [
                    ('int16_be',   'Interpreter comme int16 BE'),
                    ('int16_le',   'Interpreter comme int16 LE'),
                    ('uint16_be',  'Interpreter comme uint16 BE'),
                    ('float16_be', 'Interpreter comme float16 BE'),
                ]:
                    a = menu.addAction(label)
                    a.setCheckable(True)
                    a.setChecked(self._interpret_checks.get(
                        (row_key, key), False))
                    a.toggled.connect(lambda checked, k=key, r=list(
                        rows): self._request_interp(r, k, checked))
            # Interprétations multi-octets : toute sélection consécutive
            for key, label in [
                ('string',  'Interpreter comme chaîne ASCII'),
                ('bitmask', 'Interpreter comme masque de bits'),
            ]:
                a = menu.addAction(label)
                a.setCheckable(True)
                a.setChecked(self._interpret_checks.get((row_key, key), False))
                a.toggled.connect(lambda checked, k=key, r=list(
                    rows): self._request_interp(r, k, checked))
        if not menu.isEmpty():
            menu.exec(self.mapToGlobal(pos))

    def _request_interp(self, rows: List[int], kind: str, checked: bool):
        self._interpret_checks[(tuple(rows), kind)] = checked
        self.interpretToggled.emit(
            {'type': self.typ, 'offsets': rows, 'interpretation': kind, 'checked': checked})

    def set_checked(self, offset: int, checked: bool):
        self._suppress_signal = True
        if checked:
            self.checked_offsets.add(offset)
        else:
            self.checked_offsets.discard(offset)
        item = self.item(offset, 0)
        if item:
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._suppress_signal = False

    def set_interpret_checked(self, offsets: List[int], kind: str, checked: bool):
        self._interpret_checks[(tuple(offsets), kind)] = checked


class ReversePanel(QWidget):
    # {'label':..., 'type':..., 'offsets':..., 'color':...}
    addSeries = Signal(dict)
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
        pretty = ', '.join(
            f"{k}={v}" for k, v in parsed.items() if not k.startswith('raw_b'))
        self.raw_text.setText(pretty)
        self.table.populate(parsed)

    def _on_item_toggled(self, payload: dict[str, Any]):
        # forward as addSeries/removeSeries
        if payload['checked']:
            self.addSeries.emit(
                {'label': payload['label'], 'type': payload['type'], 'offsets': [payload['offset']]})
        else:
            self.removeSeries.emit(payload['label'])

    def _on_interpret_requested(self, info: dict[str, Any]):
        # simply emit as addSeries for now, label includes interp
        label = f"{info['type']}[{info['offsets'][0]}-{info['offsets'][-1]}] {info['interpretation']}"
        if info.get('checked', False):
            self.addSeries.emit(
                {'label': label, 'type': info['type'], 'offsets': info['offsets'], 'interpretation': info['interpretation']})
        else:
            self.removeSeries.emit(label)


class GraphSelectionPanel(QWidget):
    removeRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
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
