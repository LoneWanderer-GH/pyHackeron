from __future__ import annotations

from corelec.UI.qt_compat import (
    Qt, Signal,
    QColor, QBrush, QFontDatabase,
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QMenu, QPushButton, QListWidget, QLabel,
)
from typing import Dict, Any, List

# Octets structurels du protocole — non cochables, non sélectionnables
_STRUCTURAL_OFFSETS: frozenset[int] = frozenset({0, 1, 15, 16})


class ReverseByteTable(QTreeWidget):
    # Émis quand une case est cochée/décochée.
    # Payload octet  : {'type':int, 'offset':int, 'label':str, 'checked':bool}
    # Payload bit    : {'type':int, 'offset':int, 'bit':int, 'label':str, 'checked':bool}
    itemToggled = Signal(dict)
    # {'type':int,'offsets':list,'interpretation':str,'checked':bool}
    interpretToggled = Signal(dict)

    def __init__(self, typ: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.typ = typ
        self.setColumnCount(6)
        self.setHeaderLabels(['Plot', 'Offset', 'Valeur', 'Hex', 'Known', 'Nom'])
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.header().setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_ctx)
        self.itemChanged.connect(self._on_item_changed)
        self.known_offsets: List[int] = []
        self._suppress_signal = False
        self.checked_offsets: set[int] = set()
        self._checked_bits: set[tuple[int, int]] = set()   # (byte_offset, bit_index)
        self._interpret_checks: dict[tuple[tuple[int, ...], str], bool] = {}
        self._byte_items: list[QTreeWidgetItem] = []     # indexé par byte offset
        self.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setIndentation(14)
        self.setUniformRowHeights(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate(self, parsed: Dict[str, Any]):
        """Reconstruit la table depuis un dict as_dict() de ctypes_frames."""
        raw = [parsed.get(f'raw_b{i}', 0) for i in range(17)]
        self.known_offsets = parsed.get('_known_offsets', []) or []
        offset_names: Dict[int, str] = parsed.get('_offset_names', {}) or {}
        bit_names: Dict[int, Dict[int, str]] = parsed.get('_bit_names', {}) or {}

        # Mémoriser les lignes dépliées avant de vider
        expanded: set[int] = {i for i, it in enumerate(self._byte_items) if it.isExpanded()}

        self._suppress_signal = True
        self.clear()
        self._byte_items = []

        for i in range(17):
            is_structural = i in _STRUCTURAL_OFFSETS
            known = i in self.known_offsets
            val = raw[i]

            # --- Ligne principale (octet) ---
            it = QTreeWidgetItem()
            it.setData(0, Qt.ItemDataRole.UserRole, ('byte', i))
            if not is_structural:
                it.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                it.setCheckState(
                    0,
                    Qt.CheckState.Checked if i in self.checked_offsets else Qt.CheckState.Unchecked,
                )
            else:
                it.setFlags(Qt.ItemFlag.NoItemFlags)
            it.setText(1, str(i))
            it.setText(2, str(val))
            it.setText(3, hex(val))
            it.setText(4, 'yes' if known else 'no')
            it.setText(5, offset_names.get(i, ''))
            self._style_byte_item(it, is_structural, known)
            self.addTopLevelItem(it)
            self._byte_items.append(it)

            # --- Sous-lignes de bits (bit 7 → bit 0) ---
            if not is_structural:
                byte_bit_names = bit_names.get(i, {})
                for bit in range(7, -1, -1):
                    bit_val = (val >> bit) & 1
                    bit_name = byte_bit_names.get(bit)
                    bi = QTreeWidgetItem(it)
                    bi.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    bi.setData(0, Qt.ItemDataRole.UserRole, ('bit', i, bit))
                    bi.setCheckState(
                        0,
                        Qt.CheckState.Checked if (i, bit) in self._checked_bits
                        else Qt.CheckState.Unchecked,
                    )
                    bi.setText(1, f'  ↳ bit{bit}')
                    bi.setText(2, str(bit_val))
                    bi.setText(3, '—')
                    bi.setText(4, 'yes' if bit_name else '?')
                    bi.setText(5, bit_name if bit_name else f'bit {bit}')
                    self._style_bit_item(bi, known, bit_val, bit_known=bit_name is not None)

            if i in expanded:
                it.setExpanded(True)

        self._suppress_signal = False

    def set_checked(self, offset: int, checked: bool):
        """Cocher/décocher programmatiquement la case d'un octet."""
        self._suppress_signal = True
        if checked:
            self.checked_offsets.add(offset)
        else:
            self.checked_offsets.discard(offset)
        if offset < len(self._byte_items):
            self._byte_items[offset].setCheckState(
                0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
        self._suppress_signal = False

    def set_checked_bit(self, offset: int, bit: int, checked: bool):
        """Cocher/décocher programmatiquement la case d'un bit d'un octet."""
        self._suppress_signal = True
        if checked:
            self._checked_bits.add((offset, bit))
        else:
            self._checked_bits.discard((offset, bit))
        if offset < len(self._byte_items):
            # bits ajoutés dans l'ordre 7..0 → child index = 7 - bit
            bi = self._byte_items[offset].child(7 - bit)
            if bi is not None:
                bi.setCheckState(
                    0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
        self._suppress_signal = False

    def set_interpret_checked(self, offsets: List[int], kind: str, checked: bool):
        self._interpret_checks[(tuple(offsets), kind)] = checked

    # ------------------------------------------------------------------
    # Styling helpers
    # ------------------------------------------------------------------

    def _style_byte_item(self, item: QTreeWidgetItem, is_structural: bool, known: bool) -> None:
        if is_structural:
            bg, fg = QColor('#404040'), QColor('#909090')
        elif known:
            bg, fg = QColor('#d7f0dc'), QColor('#1a2a1a')
        else:
            bg, fg = QColor('#f7dfcf'), QColor('#3a1500')
        bg_b, fg_b = QBrush(bg), QBrush(fg)
        for col in range(6):
            item.setBackground(col, bg_b)
            item.setForeground(col, fg_b)

    def _style_bit_item(self, item: QTreeWidgetItem, parent_known: bool, bit_val: int,
                         bit_known: bool = False) -> None:
        if bit_known:
            # Bit avec un nom connu : couleur plus saturée
            bg = QColor('#7ecf8a') if bit_val else QColor('#cdebd2')
            fg = QColor('#051205') if bit_val else QColor('#1a3a1f')
        elif parent_known:
            bg = QColor('#b0e0b8') if bit_val else QColor('#e4f3e6')
            fg = QColor('#0a1a0a') if bit_val else QColor('#3a4a3a')
        else:
            bg = QColor('#f0c8a8') if bit_val else QColor('#faeee6')
            fg = QColor('#3a1500') if bit_val else QColor('#5a3020')
        bg_b, fg_b = QBrush(bg), QBrush(fg)
        for col in range(6):
            item.setBackground(col, bg_b)
            item.setForeground(col, fg_b)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        if self._suppress_signal or column != 0:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        checked = item.checkState(0) == Qt.CheckState.Checked
        if data[0] == 'byte':
            offset = data[1]
            if checked:
                self.checked_offsets.add(offset)
            else:
                self.checked_offsets.discard(offset)
            self.itemToggled.emit({
                'type': self.typ, 'offset': offset,
                'label': f'{self.typ}[{offset}]', 'checked': checked,
            })
        elif data[0] == 'bit':
            _, offset, bit = data
            if checked:
                self._checked_bits.add((offset, bit))
            else:
                self._checked_bits.discard((offset, bit))
            self.itemToggled.emit({
                'type': self.typ, 'offset': offset, 'bit': bit,
                'label': f'{self.typ}[{offset}].bit{bit}', 'checked': checked,
            })

    def _on_ctx(self, pos: Any):
        # Menu contextuel uniquement sur les lignes d'octets (pas les bits)
        selected_byte_items = [
            it for it in self.selectedItems()
            if it.data(0, Qt.ItemDataRole.UserRole) is not None
            and it.data(0, Qt.ItemDataRole.UserRole)[0] == 'byte'
        ]
        rows = sorted(it.data(0, Qt.ItemDataRole.UserRole)[1] for it in selected_byte_items)
        rows = [r for r in rows if r not in _STRUCTURAL_OFFSETS]
        if not rows:
            return
        consecutive = all(rows[i] + 1 == rows[i + 1] for i in range(len(rows) - 1))
        unknown_only = all(r not in self.known_offsets for r in rows)
        menu = QMenu(self)
        if consecutive and unknown_only:
            row_key = tuple(rows)
            if len(rows) == 2:
                for key, label in [
                    ('int16_be',   'Interpreter comme int16 BE'),
                    ('int16_le',   'Interpreter comme int16 LE'),
                    ('uint16_be',  'Interpreter comme uint16 BE'),
                    ('float16_be', 'Interpreter comme float16 BE'),
                ]:
                    a = menu.addAction(label)
                    a.setCheckable(True)
                    a.setChecked(self._interpret_checks.get((row_key, key), False))
                    a.toggled.connect(lambda checked, k=key, r=list(rows): self._request_interp(r, k, checked))
            for key, label in [
                ('string',  'Interpreter comme chaîne ASCII'),
                ('bitmask', 'Interpreter comme masque de bits'),
            ]:
                a = menu.addAction(label)
                a.setCheckable(True)
                a.setChecked(self._interpret_checks.get((row_key, key), False))
                a.toggled.connect(lambda checked, k=key, r=list(rows): self._request_interp(r, k, checked))
        if not menu.isEmpty():
            menu.exec(self.mapToGlobal(pos))

    def _request_interp(self, rows: List[int], kind: str, checked: bool):
        self._interpret_checks[(tuple(rows), kind)] = checked
        self.interpretToggled.emit(
            {'type': self.typ, 'offsets': rows, 'interpretation': kind, 'checked': checked}
        )


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
