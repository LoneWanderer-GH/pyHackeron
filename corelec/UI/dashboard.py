# dashboard.py
from __future__ import annotations
import struct
import threading
from collections import deque
from datetime import datetime
import logging
from html import escape

import pyqtgraph as pg
import bisect
from corelec.UI.qt_compat import (
    Qt, QTimer, QFontDatabase,
    QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QTextEdit,
    QProgressBar, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)
import functools

from corelec.Analyse.database import Database
from corelec.Analyse.model import RegulatorState
from corelec.BLE.types import ConnectionInfo, DecodedBase
from corelec.core_logging import attach_qt_log_emitter
from corelec.ReverseEngineering.ctypes_frames import FrameBase as CFrameBase, Frame65 as CFrame65, Frame69 as CFrame69, Frame77 as CFrame77, Frame83 as CFrame83
from corelec.UI.reverse_ui import ReverseByteTable, GraphSelectionPanel
from corelec.UI.signals import signals
from corelec.net_protocol import FRAME_LABELS

logger = logging.getLogger(__name__)


class Dashboard(QWidget):
    
    def __init__(
            self,
            state: RegulatorState,
            database: Database,
            network_client=None,   # NetworkClient optionnel (mode réseau)
    ):
        super().__init__()
        self._network_client = network_client
        
        self.state = state
        self.database: Database = database
        self.re_bytes_history: dict[int, dict[int, deque[bytes]]] = {
                65: {i: deque(maxlen=200) for i in range(17)},
                77: {i: deque(maxlen=200) for i in range(17)},
                83: {i: deque(maxlen=200) for i in range(17)},
                69: {i: deque(maxlen=200) for i in range(17)},
        }
        self.reverse_time_history: dict[tuple[int, int], deque[tuple[float, int]]] = {
            (t, i): deque(maxlen=2000) for t in (65, 69, 77, 83) for i in range(17)
        }
        self.reverse_series_items: dict[str, pg.PlotDataItem] = {}
        self.reverse_series_meta: dict[str, dict] = {}
        self._reverse_palette = [
            '#00bcd4', '#ff9800', '#8bc34a', '#e91e63', '#ffd54f', '#9c27b0', '#4caf50', '#ff5722', '#03a9f4'
        ]
        self.setWindowTitle("Corelec Monitor")
        #
        # layout = QVBoxLayout()
        #
        # self.label = QLabel()
        # layout.addWidget(self.label)
        #
        # self.ph_graph = pg.PlotWidget()
        # self.redox_graph = pg.PlotWidget()
        #
        # layout.addWidget(self.ph_graph)
        # layout.addWidget(self.redox_graph)
        #
        # self.ph_curve = self.ph_graph.plot()
        # self.redox_curve = self.redox_graph.plot()
        #
        # self.setLayout(layout)
        #
        # self.timer = QTimer()
        # self.timer.timeout.connect(self.refresh)
        # self.timer.start(2000)
        
        self.connection_label = QLabel("Déconnecté")
        self.retry_label = QLabel("Retries: 0")
        
        self.connection_progress = QProgressBar()
        self.connection_progress.setMaximum(100)

        self.retry_button = QPushButton("Reconnecter")
        self.cancel_button = QPushButton("Annuler")
        self.sync_db_button = QPushButton("Sync DB")
        self.sync_db_button.setToolTip("Télécharger la base de données depuis le daemon réseau")
        self.sync_db_button.setVisible(False)  # affiché uniquement en mode réseau
        self._redecode_button = QPushButton("Re-décoder DB")
        self._redecode_button.setToolTip("Efface et re-décode tous les raw_frames → decoded_frames")
        self.retry_button.clicked.connect(lambda _: signals.retry_requested.emit())
        self.cancel_button.clicked.connect(lambda _: signals.cancel_requested.emit())
        self.sync_db_button.clicked.connect(self._on_sync_db)
        self._redecode_button.clicked.connect(self._on_redecode_clicked)

        # Indicateur ZMQ (mode réseau uniquement)
        self.zmq_status_label = QLabel("")
        self.zmq_status_label.setVisible(False)
        self._network_client = None

        top = QHBoxLayout()
        top.addWidget(self.connection_label)
        top.addWidget(self.retry_label)
        top.addWidget(self.connection_progress)
        top.addWidget(self.zmq_status_label)
        top.addWidget(self.retry_button)
        top.addWidget(self.cancel_button)
        top.addWidget(self.sync_db_button)
        top.addWidget(self._redecode_button)
        self.tabs = QTabWidget()
        
        dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout()
        
        dashboard_info = QWidget()
        dashboard_info_layout = QGridLayout()
        dashboard_info.setLayout(dashboard_info_layout)
        
        self.ph_value = QLabel("-")
        self.redox_value = QLabel("-")
        self.temp_value = QLabel("-")
        self.sel_value = QLabel("-")
        self.electro_value = QLabel("-")
        self.boost_remaining_value = QLabel("-")
        self.inversion_timer_value = QLabel("-")
        self.ph_consigne_value = QLabel("-")
        self.redox_consigne_value = QLabel("-")
        self.alarme_value = QLabel("-")
        self.warning_value = QLabel("-")
        self.pompe_moins_value = QLabel("-")
        self.regulation_active_value = QLabel("-")
        self.pompes_forcees_value = QLabel("-")
        self.inversion_period_value = QLabel("-")
        self.shutter_mode_value = QLabel("-")
        self.elx_fault_value = QLabel("-")
        
        self.boost_active_checkbox = QCheckBox("Boost actif")
        self.flow_switch_checkbox = QCheckBox("Flow switch")
        self.volet_actif_checkbox = QCheckBox("Volet actif")
        self.volet_force_checkbox = QCheckBox("Volet forcé")
        self.polarity_phase_a_checkbox = QCheckBox("Phase A (polarité)")
        for checkbox in [
                self.boost_active_checkbox,
                self.flow_switch_checkbox,
                self.volet_actif_checkbox,
                self.volet_force_checkbox,
                self.polarity_phase_a_checkbox,
        ]:
            checkbox.setEnabled(False)
        
        dashboard_info_layout.addWidget(QLabel("pH:"), 0, 0)
        dashboard_info_layout.addWidget(self.ph_value, 0, 1)
        dashboard_info_layout.addWidget(QLabel("pH consigne:"), 0, 2)
        dashboard_info_layout.addWidget(self.ph_consigne_value, 0, 3)
        
        dashboard_info_layout.addWidget(QLabel("Redox:"), 1, 0)
        dashboard_info_layout.addWidget(self.redox_value, 1, 1)
        dashboard_info_layout.addWidget(QLabel("Redox consigne:"), 1, 2)
        dashboard_info_layout.addWidget(self.redox_consigne_value, 1, 3)
        
        dashboard_info_layout.addWidget(QLabel("Température:"), 2, 0)
        dashboard_info_layout.addWidget(self.temp_value, 2, 1)
        dashboard_info_layout.addWidget(QLabel("Sel:"), 2, 2)
        dashboard_info_layout.addWidget(self.sel_value, 2, 3)
        
        dashboard_info_layout.addWidget(QLabel("Electrolyse:"), 3, 0)
        dashboard_info_layout.addWidget(self.electro_value, 3, 1)
        dashboard_info_layout.addWidget(QLabel("Boost restant:"), 3, 2)
        dashboard_info_layout.addWidget(self.boost_remaining_value, 3, 3)
        
        dashboard_info_layout.addWidget(QLabel("Cpt. inv. polarité:"), 4, 0)
        dashboard_info_layout.addWidget(self.inversion_timer_value, 4, 1)

        dashboard_info_layout.addWidget(QLabel("Alarme:"), 5, 0)
        dashboard_info_layout.addWidget(self.alarme_value, 5, 1)
        dashboard_info_layout.addWidget(QLabel("Warning:"), 5, 2)
        dashboard_info_layout.addWidget(self.warning_value, 5, 3)

        dashboard_info_layout.addWidget(QLabel("Pompe pH-:"), 6, 0)
        dashboard_info_layout.addWidget(self.pompe_moins_value, 6, 1)
        dashboard_info_layout.addWidget(QLabel("Régulation active:"), 6, 2)
        dashboard_info_layout.addWidget(self.regulation_active_value, 6, 3)

        dashboard_info_layout.addWidget(QLabel("Pompes forcées:"), 7, 0)
        dashboard_info_layout.addWidget(self.pompes_forcees_value, 7, 1)
        dashboard_info_layout.addWidget(QLabel("Pér. inv. pol. conf.:"), 7, 2)
        dashboard_info_layout.addWidget(self.inversion_period_value, 7, 3)

        dashboard_info_layout.addWidget(QLabel("Mode volet %:"), 8, 0)
        dashboard_info_layout.addWidget(self.shutter_mode_value, 8, 1)
        dashboard_info_layout.addWidget(QLabel("Code défaut elx:"), 8, 2)
        dashboard_info_layout.addWidget(self.elx_fault_value, 8, 3)
        
        bool_group = QGroupBox("État des commutateurs")
        bool_layout = QHBoxLayout()
        bool_layout.addWidget(self.boost_active_checkbox)
        bool_layout.addWidget(self.flow_switch_checkbox)
        bool_layout.addWidget(self.volet_actif_checkbox)
        bool_layout.addWidget(self.volet_force_checkbox)
        bool_layout.addWidget(self.polarity_phase_a_checkbox)
        bool_group.setLayout(bool_layout)
        
        dashboard_layout.addWidget(dashboard_info)
        dashboard_layout.addWidget(bool_group)
        dashboard_tab.setStyleSheet(
            "QLabel { font-size: 15px; }"
            "QCheckBox { font-size: 14px; }"
            "QGroupBox { font-size: 14px; font-weight: 600; }"
        )
        
        dashboard_tab.setLayout(dashboard_layout)
        
        graphs_tab = QWidget()
        graphs_layout = QVBoxLayout()
        
        self.ph_date_axis = pg.DateAxisItem(orientation='bottom')
        self.electro_date_axis = pg.DateAxisItem(orientation='bottom')
        self.cycle_date_axis = pg.DateAxisItem(orientation='bottom')
        # top axes to show day ticks when data spans multiple days
        self.ph_top_date_axis = pg.DateAxisItem(orientation='top')
        self.electro_top_date_axis = pg.DateAxisItem(orientation='top')
        self.cycle_top_date_axis = pg.DateAxisItem(orientation='top')
        
        self.ph_graph: pg.PlotWidget | pg.PlotItem = pg.PlotWidget(
            title="pH et consigne pH",
            axisItems={'bottom': self.ph_date_axis, 'top': self.ph_top_date_axis}
        )
        logger.debug("ph_graph type=%s plot_item=%s", type(self.ph_graph), type(self.ph_graph.getPlotItem()))
        self.ph_graph.addLegend()
        self.ph_graph.showGrid(x=True, y=True, alpha=0.3)
        self.ph_graph.setLabel('bottom', 'Date / heure')
        self.ph_graph.setLabel('left', 'pH')
        self.ph_curve = self.ph_graph.plot(pen=pg.mkPen(color='y', width=2), name='pH')
        self.ph_setpoint_curve = self.ph_graph.plot(pen=pg.mkPen(color='w', width=2), name='pH consigne')
        # create a right-hand ViewBox for discrete/binary series (pompe pH-)
        pw = self.ph_graph.getPlotItem()
        self.ph_right_vb = pg.ViewBox()
        pw.showAxis('right')
        pw.getAxis('right').setLabel('Pompe pH- (0/1)')
        pw.getAxis('right').setPen(pg.mkPen(color='r'))
        pw.getAxis('right').setTicks([[(0.0, 'OFF'), (1.0, 'ON')]])
        pw.scene().addItem(self.ph_right_vb)
        pw.getAxis('right').linkToView(self.ph_right_vb)
        self.ph_right_vb.setXLink(pw.getViewBox())

        def _update_ph_right_vb():
            self.ph_right_vb.setGeometry(pw.getViewBox().sceneBoundingRect())
            self.ph_right_vb.setYRange(-0.05, 1.05, padding=0)

        pw.getViewBox().sigResized.connect(_update_ph_right_vb)
        _update_ph_right_vb()
        # PlotDataItem added to right viewbox
        self.ph_pump_curve = pg.PlotDataItem(
            pen=pg.mkPen(color='r', width=2),
            symbol='o',
            symbolBrush='r',
            symbolSize=6,
            name='pompe pH- (0/1)'
        )
        self.ph_right_vb.addItem(self.ph_pump_curve)
        self.ph_warning_line = pg.InfiniteLine(
            pos=6.8, angle=0, pen=pg.mkPen(color=(180, 180, 180), width=1, style=Qt.PenStyle.DashLine)
            )
        self.ph_alarm_line = pg.InfiniteLine(
            pos=7.4, angle=0, pen=pg.mkPen(color=(120, 120, 120), width=1, style=Qt.PenStyle.DashLine)
            )
        self.ph_graph.addItem(self.ph_warning_line)
        self.ph_graph.addItem(self.ph_alarm_line)
        # store series mapping for interactive crosshair
        self._plot_series = {}
        
        self.electro_graph: pg.PlotWidget | pg.PlotItem = pg.PlotWidget(
            title="Electrolyse % et consigne",
            axisItems={'bottom': self.electro_date_axis, 'top': self.electro_top_date_axis}
        )
        self.electro_graph.addLegend()
        self.electro_graph.showGrid(x=True, y=True, alpha=0.3)
        self.electro_graph.setLabel('bottom', 'Date / heure')
        self.electro_graph.setLabel('left', '%')
        self.electro_curve = self.electro_graph.plot(pen=pg.mkPen(color='lime', width=2), name='Consigne Electrolyse %')
        self.electro_setpoint_curve = self.electro_graph.plot(
            pen=pg.mkPen(color='red', width=2), name='Consigne Electrolyse Volet %'
            )
        
        self.cycle_graph: pg.PlotWidget | pg.PlotItem = pg.PlotWidget(
                title="Inversion de polarité",
                axisItems={'bottom': self.cycle_date_axis}
        )
        self.cycle_graph.addLegend()
        self.cycle_graph.showGrid(x=True, y=True, alpha=0.3)
        self.cycle_graph.setLabel('bottom', 'Date / heure')
        self.cycle_graph.setLabel('left', 'Min')
        self.inversion_timer_curve = self.cycle_graph.plot(pen=pg.mkPen(color='cyan', width=2), name='Compteur (min)')
        self.inversion_period_curve = self.cycle_graph.plot(pen=pg.mkPen(color='lime', width=2), name='Période conf. (min)')
        # axe droit binaire pour la phase de polarité (A=1 / B=0)
        _cpw = self.cycle_graph.getPlotItem()
        self.cycle_right_vb = pg.ViewBox()
        _cpw.showAxis('right')
        _cpw.getAxis('right').setLabel('Phase A (1=A / 0=B)')
        _cpw.getAxis('right').setPen(pg.mkPen(color=(180, 100, 255)))
        _cpw.getAxis('right').setTicks([[(0.0, 'B'), (1.0, 'A')]])
        _cpw.scene().addItem(self.cycle_right_vb)
        _cpw.getAxis('right').linkToView(self.cycle_right_vb)
        self.cycle_right_vb.setXLink(_cpw.getViewBox())

        def _update_cycle_right_vb():
            self.cycle_right_vb.setGeometry(_cpw.getViewBox().sceneBoundingRect())
            self.cycle_right_vb.setYRange(-0.05, 1.05, padding=0)

        _cpw.getViewBox().sigResized.connect(_update_cycle_right_vb)
        _update_cycle_right_vb()
        self.polarity_phase_curve = pg.PlotDataItem(
            pen=pg.mkPen(color=(180, 100, 255), width=2),
            name='Phase polarité (A=1/B=0)'
        )
        self.cycle_right_vb.addItem(self.polarity_phase_curve)

        self.boost_date_axis = pg.DateAxisItem(orientation='bottom')
        self.boost_graph: pg.PlotWidget = pg.PlotWidget(
                title="Boost restant",
                axisItems={'bottom': self.boost_date_axis}
        )
        self.boost_graph.addLegend()
        self.boost_graph.showGrid(x=True, y=True, alpha=0.3)
        self.boost_graph.setLabel('bottom', 'Date / heure')
        self.boost_graph.setLabel('left', 'Min')
        self.boost_curve = self.boost_graph.plot(pen=pg.mkPen(color='orange', width=2), name='Boost restant (min)')

        graphs_layout.addWidget(self.ph_graph)
        graphs_layout.addWidget(self.electro_graph)
        graphs_layout.addWidget(self.cycle_graph)
        graphs_layout.addWidget(self.boost_graph)

        # prepare interactive series lists
        self._plot_series[self.ph_graph] = [
            {'x':'ph_x','y':'ph_y','color':'yellow','name':'pH'},
            {'x':'ph_cons_x','y':'ph_cons_y','color':'white','name':'pH consigne'},
            {'x':'pump_x','y':'pump_state_y','color':'red','name':'Pompe pH-','binary':True},
        ]
        self._plot_series[self.electro_graph] = [
            {'x':'electro_x','y':'electro_y','color':'lime','name':'Electrolyse %'},
            {'x':'electro_cons_x','y':'electro_cons_y','color':'red','name':'Consigne %'},
        ]
        self._plot_series[self.cycle_graph] = [
            {'x':'inversion_timer_x','y':'inversion_timer_y','color':'cyan','name':'Compteur (min)'},
            {'x':'inversion_period_x','y':'inversion_period_y','color':'lime','name':'Période conf. (min)'},
            {'x':'polarity_phase_x','y':'polarity_phase_state_y','color':'#b464ff','name':'Phase A','binary':True},
        ]
        self._plot_series[self.boost_graph] = [
            {'x':'boost_x','y':'boost_y','color':'orange','name':'Boost restant (min)'},
        ]

        # setup interactive crosshairs for graphs
        # _crosshair_proxies : maintenir les références pour éviter le GC
        self._crosshair_proxies: list = []
        self._setup_crosshair(self.ph_graph)
        self._setup_crosshair(self.electro_graph)
        self._setup_crosshair(self.cycle_graph)
        self._setup_crosshair(self.boost_graph)

        graphs_tab.setLayout(graphs_layout)
        
        log_tab = QWidget()
        
        log_layout = QVBoxLayout()
        
        self.log_view = QTextEdit()
        self.log_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.log_view.setStyleSheet("QTextEdit { background: #101316; color: #d7e3f4; }")
        
        self.log_view.setReadOnly(True)
        
        log_layout.addWidget(self.log_view)
        
        log_tab.setLayout(log_layout)
        
        re_tab = QWidget()
        re_layout = QVBoxLayout()
        
        self.byte_date_axis = pg.DateAxisItem(orientation='bottom')
        self.byte_graph : pg.PlotWidget | pg.PlotItem = pg.PlotWidget(title="Reverse Engineering", axisItems={'bottom': self.byte_date_axis})
        self.byte_graph.addLegend()
        self.byte_graph.showGrid(x=True, y=True, alpha=0.3)
        self.byte_graph.setLabel('bottom', 'Date / heure')
        self.byte_graph.setLabel('left', 'Valeur')

        self.reverse_tables_tabs = QTabWidget()
        self.reverse_tables: dict[int, ReverseByteTable] = {}
        for typ in (65, 69, 77, 83):
            table = ReverseByteTable(typ=typ)
            table.itemToggled.connect(self._on_reverse_byte_toggled)
            table.interpretToggled.connect(self._on_reverse_interpret_toggled)
            table_host = QWidget()
            table_layout = QVBoxLayout()
            table_layout.addWidget(table)
            table_host.setLayout(table_layout)
            self.reverse_tables_tabs.addTab(table_host, FRAME_LABELS.get(typ, f"Frame {typ}"))
            self.reverse_tables[typ] = table

        self.reverse_selected_panel = GraphSelectionPanel()
        self.reverse_selected_panel.removeRequested.connect(self._on_reverse_series_remove_requested)

        # Place table tabs on the side to avoid overloading the bottom area.
        re_content = QHBoxLayout()
        re_content.addWidget(self.reverse_tables_tabs, 2)

        re_right = QVBoxLayout()
        re_right.addWidget(self.byte_graph, 3)
        re_right.addWidget(self.reverse_selected_panel, 2)
        re_content.addLayout(re_right, 3)

        re_layout.addLayout(re_content)
        
        re_tab.setLayout(re_layout)
        
        self.tabs.addTab(dashboard_tab, "Dashboard")
        
        self.tabs.addTab(graphs_tab, "Graphiques")
        
        self.tabs.addTab(log_tab, "Logs")
        
        self.tabs.addTab(re_tab, "Reverse Engineering")
        
        layout = QVBoxLayout()
        
        layout.addLayout(top)
        
        layout.addWidget(self.tabs)
        
        self.setLayout(layout)
        
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        
        signals.connection.connect(self.update_connection)
        signals.state_updated.connect(self._refresh_labels)  # rapide : pas de DB
        signals.db_sync_complete.connect(self._on_db_sync_complete)
        
        signals.log.connect(self.append_log)
        signals.reverse.connect(self.update_reverse)
        attach_qt_log_emitter(signals.log.emit)
        self._load_reverse_history()
    
    def _load_reverse_history(self) -> None:
        """Pré-remplit reverse_time_history et les tables RE depuis raw_frames en DB."""
        try:
            rows = self.database.load_raw_frames_history(limit=8000)
        except Exception:
            return
        _parsers = {77: CFrame77, 83: CFrame83, 65: CFrame65, 69: CFrame69}
        last_raw: dict[int, bytearray] = {}
        for ts_iso, frame_type, frame_hex in rows:
            try:
                raw = bytearray.fromhex(frame_hex)
                ts = datetime.fromisoformat(ts_iso).timestamp()
            except Exception:
                continue
            for i, b in enumerate(raw[:17]):
                key = (frame_type, i)
                if key in self.reverse_time_history:
                    self.reverse_time_history[key].append((ts, int(b)))
            last_raw[frame_type] = raw
        # Pré-remplir chaque table RE avec la dernière trame connue du type
        for frame_type, raw in last_raw.items():
            table = self.reverse_tables.get(frame_type)
            if table is None:
                continue
            parser = _parsers.get(frame_type, CFrameBase)
            try:
                parsed = parser.from_bytes(raw).as_dict()
            except Exception:
                parsed = CFrameBase.from_bytes(raw).as_dict()
            if 'raw_b0' not in parsed:
                parsed = {**CFrameBase.from_bytes(raw).as_dict(), **parsed}
            table.populate(parsed)

    def append_log(self, msg: str):
        text = msg.strip()
        if text.startswith("<"):
            self.log_view.append(text)
        else:
            self.log_view.append(f"<span style='font-family:Consolas,\"Courier New\",monospace;color:#d7e3f4;'>{escape(text)}</span>")
    
    def update_connection(self, info: ConnectionInfo):
        self.connection_label.setText(info.message)
        self.retry_label.setText(f"Retries: {info.retry_count}")
        self.retry_button.setEnabled(info.state != "connecting")
        
        if info.state == "connected":
            self.connection_label.setStyleSheet("color:green;font-weight:bold;")
            self.connection_progress.setRange(0, 1)
            self.connection_progress.setValue(1)
            self.connection_progress.setFormat("Connected")
        elif info.state == "connecting":
            self.connection_progress.setInvertedAppearance(True)
            self.connection_progress.setMaximum(info.timeout)
            self.connection_progress.setMinimum(0)
            self.connection_progress.setValue(info.remaining)
            self.connection_progress.setFormat("%v")
            self.connection_label.setStyleSheet("color:orange;font-weight:bold;")
        elif info.state == "error":
            self.connection_label.setStyleSheet("color:red;font-weight:bold;")
            self.connection_progress.setRange(0, 1)
            self.connection_progress.setValue(0)
            self.connection_progress.setFormat("Error")
        elif info.state == "disconnected":
            self.connection_label.setStyleSheet("color:gray;font-weight:bold;")
            self.connection_progress.setRange(0, 1)
            self.connection_progress.setValue(0)
            self.connection_progress.setFormat("Disconnected")

    def set_network_client(self, client) -> None:
        """Attache un NetworkClient, active Sync DB et l’indicateur ZMQ."""
        self._network_client = client
        self.sync_db_button.setVisible(True)
        self.zmq_status_label.setVisible(True)
        self._zmq_refresh_timer = QTimer(self)
        self._zmq_refresh_timer.setInterval(2000)
        self._zmq_refresh_timer.timeout.connect(self._refresh_zmq_status)
        self._zmq_refresh_timer.start()

    def _refresh_zmq_status(self) -> None:
        """Met à jour l’indicateur de connexion ZMQ dans la barre du haut."""
        import time as _time
        client = self._network_client
        if client is None:
            return
        age = _time.monotonic() - client.last_msg_time if client.last_msg_time > 0 else float('inf')
        total = client.frames_received
        if age < 5:
            color, dot = "#2ecc71", "●"
        elif age < 30:
            color, dot = "#e67e22", "●"
        else:
            color, dot = "#e74c3c", "●"
        self.zmq_status_label.setStyleSheet(f"color:{color}; font-weight:bold;")
        age_str = f"{int(age)}s" if age < float('inf') else "?"
        self.zmq_status_label.setText(f"{dot} ZMQ  msgs:{total}  ({age_str} ago)")

    def _on_sync_db(self) -> None:
        if self._network_client is not None:
            self._network_client.request_db_sync("raw_frames")

    def _on_redecode_clicked(self) -> None:
        self._redecode_button.setEnabled(False)
        self._redecode_button.setText("En cours…")
        self._redecoding = True

        def _worker() -> None:
            try:
                n = self.database.force_redecode()
                logger.info("Re-décodage terminé : %d trames dans decoded_frames", n)
            except Exception as e:  # noqa: BLE001
                logger.warning("Re-décodage erreur : %s", e)
            signals.db_sync_complete.emit("decoded_frames")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_db_sync_complete(self, table: str) -> None:
        """Appelé quand le dernier chunk DB sync est reçu → recharge graphiques et historique RE."""
        logger.debug("DB sync complet (table=%s) → refresh dashboard", table)
        if getattr(self, '_redecoding', False):
            self._redecoding = False
            self._redecode_button.setEnabled(True)
            self._redecode_button.setText("Re-décoder DB")
        self._load_reverse_history()
        self.refresh()

    def _setup_crosshair(self, graph: pg.PlotWidget):
        vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color='w', width=1))
        vline.setVisible(False)  # caché tant que le curseur n'est pas dans la vue
        graph.addItem(vline, ignoreBounds=True)  # ne doit pas influencer l'autoRange

        texts = []
        for s in self._plot_series.get(graph, []):
            t = pg.TextItem('', anchor=(0,1))
            graph.addItem(t, ignoreBounds=True)  # idem
            texts.append((s, t))

        # Cacher la vline et les labels quand la souris quitte ce widget
        # (sinon la ligne reste affichée quand on passe sur un autre graphe)
        _orig_leave = graph.leaveEvent
        def _leave(event, _v=vline, _ts=texts, _orig=_orig_leave):
            _v.setVisible(False)
            for _, ti in _ts:
                ti.setText('')
            _orig(event)
        graph.leaveEvent = _leave

        cb = functools.partial(self._on_mouse_moved, graph, vline, texts)
        # SignalProxy : limite à 60 événements/s pour ne pas saturer le thread Qt
        proxy = pg.SignalProxy(graph.scene().sigMouseMoved, rateLimit=60,
                               slot=lambda args: cb(args[0]))
        self._crosshair_proxies.append(proxy)  # maintenir la référence

    def _on_mouse_moved(self, graph: pg.PlotWidget, vline: pg.InfiniteLine, texts, evt):
        try:
            vb = graph.getViewBox()
            in_view = vb.sceneBoundingRect().contains(evt)
            if not in_view:
                # Masquer la ligne et les labels quand le curseur sort de la vue
                if vline.isVisible():
                    vline.setVisible(False)
                    for _, text_item in texts:
                        text_item.setText('')
                return
            pos = vb.mapSceneToView(evt)
            x = pos.x()
        except Exception:
            return

        if not vline.isVisible():
            vline.setVisible(True)
        # position the vertical line directly at the mouse cursor
        vline.setPos(x)

        # for each series, find nearest point
        for series_idx, (s, text_item) in enumerate(texts):
            xs = getattr(self, s['x'], None)
            ys = getattr(self, s['y'], None)
            if not xs or not ys:
                text_item.setText('')
                continue
            # xs should be increasing; find nearest index
            idx = bisect.bisect_left(xs, x)
            if idx >= len(xs):
                idx = len(xs) - 1
            if idx > 0 and idx < len(xs):
                if abs(xs[idx] - x) > abs(xs[idx - 1] - x):
                    idx = idx - 1

            xval = xs[idx]
            yval = ys[idx]
            if s.get('binary'):
                value_txt = 'ON' if yval >= 0.5 else 'OFF'
            else:
                value_txt = f"{yval:.3f}"
            html = f"<div style='color:{s['color']};font-weight:bold'>{s['name']}: {value_txt}</div>"
            text_item.setHtml(html)
            # keep binary labels visible in the main pH view despite right-axis scaling
            if s.get('binary'):
                y_top = vb.viewRange()[1][1]
                text_item.setPos(xval, y_top - 0.15 * (series_idx + 1))
            else:
                text_item.setPos(xval, yval)

    def _next_reverse_color(self) -> str:
        idx = len(self.reverse_series_items) % len(self._reverse_palette)
        return self._reverse_palette[idx]

    def _compute_interpret_value(self, values: list[int], kind: str):
        if not values:
            return None
        try:
            if kind == 'int16_be' and len(values) >= 2:
                v = (values[0] << 8) | values[1]
                if v >= 0x8000:
                    v -= 0x10000
                return float(v)
            if kind == 'int16_le' and len(values) >= 2:
                v = (values[1] << 8) | values[0]
                if v >= 0x8000:
                    v -= 0x10000
                return float(v)
            if kind == 'uint16_be' and len(values) >= 2:
                return float((values[0] << 8) | values[1])
            if kind == 'float16_be' and len(values) >= 2:
                return float(struct.unpack('>e', bytes(values[:2]))[0])
            if kind == 'string':
                # numeric proxy for plotting string payloads
                return float(sum(v << (8 * (len(values) - 1 - i)) for i, v in enumerate(values)))
            if kind == 'bitmask':
                return float(sum(bin(v).count('1') for v in values))
        except Exception:
            return None
        return float(values[0])

    def _refresh_reverse_series(self, label: str):
        meta = self.reverse_series_meta.get(label)
        item = self.reverse_series_items.get(label)
        if not meta or not item:
            return

        typ = meta['type']
        offsets = meta['offsets']
        kind = meta.get('interpretation')
        bit = meta.get('bit')

        histories = [self.reverse_time_history[(typ, o)] for o in offsets if (typ, o) in self.reverse_time_history]
        if not histories:
            item.setData([], [])
            return

        n = min(len(h) for h in histories)
        if n == 0:
            item.setData([], [])
            return

        xs: list[float] = []
        ys: list[float] = []
        for idx in range(n):
            ts = histories[0][idx][0]
            if bit is not None:
                # Série booléenne : isole le bit demandé de l'octet
                y = float((int(histories[0][idx][1]) >> bit) & 1)
            elif kind:
                vals = [histories[j][idx][1] for j in range(len(histories))]
                y = self._compute_interpret_value(vals, kind)
                if y is None:
                    continue
            else:
                y = float(histories[0][idx][1])
            xs.append(ts)
            ys.append(y)
        item.setData(xs, ys)

    def _add_reverse_series(self, *, typ: int, offsets: list[int], label: str,
                             interpretation: str | None = None, bit: int | None = None):
        if label in self.reverse_series_items:
            return

        color = self._next_reverse_color()
        item = self.byte_graph.plot(pen=pg.mkPen(color=color, width=2), name=label)
        self.reverse_series_items[label] = item
        self.reverse_series_meta[label] = {
            'type': typ,
            'offsets': offsets,
            'interpretation': interpretation,
            'bit': bit,
        }
        self.reverse_selected_panel.add_item(label)
        self._refresh_reverse_series(label)

    def _remove_reverse_series(self, label: str):
        item = self.reverse_series_items.pop(label, None)
        meta = self.reverse_series_meta.pop(label, None)
        if item is not None:
            # Supprimer l’entrée de la légende avant de retirer l’item du graphe
            legend = self.byte_graph.plotItem.legend
            if legend is not None:
                try:
                    legend.removeItem(item)
                except Exception:
                    pass
            self.byte_graph.removeItem(item)
        self.reverse_selected_panel.remove_item(label)

        if meta is not None:
            table = self.reverse_tables.get(meta['type'])
            if table is not None:
                if meta.get('interpretation'):
                    table.set_interpret_checked(meta['offsets'], meta['interpretation'], False)
                elif meta.get('bit') is not None:
                    for o in meta['offsets']:
                        table.set_checked_bit(o, meta['bit'], False)
                else:
                    for o in meta['offsets']:
                        table.set_checked(o, False)

    def _on_reverse_byte_toggled(self, payload: dict):
        label = payload['label']
        if payload.get('checked'):
            self._add_reverse_series(
                typ=payload['type'],
                offsets=[payload['offset']],
                label=label,
                bit=payload.get('bit'),
            )
        else:
            self._remove_reverse_series(label)

    def _on_reverse_interpret_toggled(self, payload: dict):
        label = f"{payload['type']}[{payload['offsets'][0]}-{payload['offsets'][-1]}] {payload['interpretation']}"
        if payload.get('checked'):
            self._add_reverse_series(
                typ=payload['type'],
                offsets=payload['offsets'],
                label=label,
                interpretation=payload['interpretation'],
            )
        else:
            self._remove_reverse_series(label)

    def _on_reverse_series_remove_requested(self, label: str):
        self._remove_reverse_series(label)

    # ------------------------------------------------------------------
    # Helper : historique des trames décodées
    # ------------------------------------------------------------------

    # Champs utiles par type de trame (= colonnes lues dans decoded_frames)
    _DECODED_FIELDS: dict[int, list[str]] = {
        77: ['ph', 'redox', 'temp', 'sel', 'alarme', 'warning',
             'regulation_active', 'pompe_moins_active', 'pompes_forcees',
             'config_capteur_sel_actif'],
        65: ['current_electrolyse_percent', 'boost_remaining_min',
             'inversion_period_min', 'inversion_timer_min',
             'shutter_mode_electrolyse_percent',
             'flow_switch', 'volet_actif', 'volet_force', 'polarity_phase_a', 'elx_fault_code'],
        83: ['ph_consigne', 'err_max', 'err_min'],
        69: ['redox_consigne'],
    }

    def _decode_frames_history(self, frame_type: int, limit: int) -> dict:
        """Lit les valeurs décodées depuis decoded_frames (via json_extract SQL).
        Aucun décodage ctypes côté Python — les trames sont pré-décodées à la
        réception (store_frame) ou au premier démarrage (backfill one-shot).
        """
        fields = self._DECODED_FIELDS.get(frame_type)
        if not fields:
            return {}
        return self.database.load_decoded_frames_by_type(frame_type, fields, limit)

    def _refresh_labels(self):
        """Mise à jour rapide des labels/checkboxes uniquement — sans accès DB.
        Appelé à chaque trame BLE reçue (via state_updated).
        """
        s: RegulatorState = self.state

        def _fmt(v) -> str:
            return "-" if v is None else str(v)

        self.ph_value.setText(_fmt(s.ph))
        self.redox_value.setText(_fmt(s.redox))
        self.temp_value.setText(_fmt(s.temp))
        self.sel_value.setText(_fmt(s.sel))
        self.electro_value.setText(_fmt(s.current_electrolyse_percent) + " %")
        self.boost_remaining_value.setText(_fmt(s.boost_remaining_time_min))
        self.inversion_timer_value.setText(_fmt(s.inversion_timer_min))
        self.ph_consigne_value.setText(_fmt(s.ph_consigne))
        self.redox_consigne_value.setText(_fmt(s.redox_consigne))
        self.alarme_value.setText(_fmt(s.alarme))
        self.warning_value.setText(_fmt(s.warning))
        self.pompe_moins_value.setText("ON" if bool(s.pompe_moins_active) else "OFF")
        self.regulation_active_value.setText("OUI" if bool(s.regulation_active) else "NON")
        self.regulation_active_value.setStyleSheet(
            "color:orange;font-weight:bold;" if not s.regulation_active else ""
        )
        self.pompes_forcees_value.setText("ON" if bool(s.pompes_forcees) else "OFF")
        self.inversion_period_value.setText(_fmt(s.inversion_period_min))
        self.shutter_mode_value.setText(_fmt(s.shutter_mode_electrolyse_percent) + " %")
        self.elx_fault_value.setText(_fmt(s.elx_fault_code))
        self.elx_fault_value.setStyleSheet(
            "color:orange;font-weight:bold;" if s.elx_fault_code != 0 else ""
        )
        self.boost_active_checkbox.setChecked(bool(s.boost_active))
        self.flow_switch_checkbox.setChecked(bool(s.flow_switch))
        self.volet_actif_checkbox.setChecked(bool(s.volet_actif))
        self.volet_force_checkbox.setChecked(bool(s.volet_force))
        self.polarity_phase_a_checkbox.setChecked(bool(s.polarity_phase_a))

    def refresh(self):
        """Rafraîchissement complet : labels + graphiques (accès DB).
        Appelé par le timer toutes les 2 s et après un DB sync.
        Ne pas connecter à state_updated (trop fréquent).
        """
        self._refresh_labels()

        _h77 = self._decode_frames_history(77, 100_000)
        _h83 = self._decode_frames_history(83, 100_000)
        _h65 = self._decode_frames_history(65, 100_000)

        ph = _h77.get('ph', [])
        ph_consigne = _h83.get('ph_consigne', [])
        electrolyse_consigne_courante = _h65.get('current_electrolyse_percent', [])
        electrolyse_consigne_volet_courante = _h65.get('shutter_mode_electrolyse_percent', [])
        inversion_timer = _h65.get('inversion_timer_min', [])
        inversion_period = _h65.get('inversion_period_min', [])
        boost_remain = _h65.get('boost_remaining_min', [])
        polarity_phase = _h65.get('polarity_phase_a', [])
        
        def to_plot_points(history: list[tuple[str, float]], gap_threshold_seconds: float = 300.0) -> tuple[list[float], list[float]]:
            xs: list[float] = []
            ys: list[float] = []
            previous_ts: float | None = None
            for ts, value in history:
                try:
                    x = datetime.fromisoformat(ts).timestamp()
                except Exception:
                    continue

                if previous_ts is not None and x - previous_ts > gap_threshold_seconds:
                    # insert a NaN to break the line when a large time gap occurs
                    xs.append(x)
                    ys.append(float('nan'))

                xs.append(x)
                ys.append(value)
                previous_ts = x
            return xs, ys

        ph_x, ph_y = to_plot_points(ph)
        ph_cons_x, ph_cons_y = to_plot_points(ph_consigne)
        pump_hist = _h77.get('pompe_moins_active', [])
        pump_x, pump_y = to_plot_points(pump_hist)
        electro_x, electro_y = to_plot_points(electrolyse_consigne_courante)
        electro_cons_x, electro_cons_y = to_plot_points(electrolyse_consigne_volet_courante)
        inversion_timer_x, inversion_timer_y = to_plot_points(inversion_timer)
        inversion_period_x, inversion_period_y = to_plot_points(inversion_period)
        boost_x, boost_y = to_plot_points(boost_remain)
        polarity_phase_x, polarity_phase_y = to_plot_points(polarity_phase)

        # expose arrays for crosshair nearest-point lookup
        self.ph_x, self.ph_y = ph_x, ph_y
        self.ph_cons_x, self.ph_cons_y = ph_cons_x, ph_cons_y
        self.pump_x = pump_x
        self.electro_x, self.electro_y = electro_x, electro_y
        self.electro_cons_x, self.electro_cons_y = electro_cons_x, electro_cons_y
        self.inversion_timer_x, self.inversion_timer_y = inversion_timer_x, inversion_timer_y
        self.inversion_period_x, self.inversion_period_y = inversion_period_x, inversion_period_y
        self.boost_x, self.boost_y = boost_x, boost_y
        self.polarity_phase_x = polarity_phase_x

        self.ph_curve.setData(ph_x, ph_y, connect='finite')
        self.ph_setpoint_curve.setData(ph_cons_x, ph_cons_y, connect='finite')
        # plot pump state on secondary right axis as binary 0/1
        pump_state_y = []
        for val in pump_y:
            if val != val:
                pump_state_y.append(float('nan'))
            else:
                pump_state_y.append(1.0 if val else 0.0)
        self.pump_state_y = pump_state_y
        self.ph_pump_curve.setData(pump_x, pump_state_y, connect='finite')
        self.ph_right_vb.setYRange(-0.05, 1.05, padding=0)
        self.electro_curve.setData(electro_x, electro_y, connect='finite')
        self.electro_setpoint_curve.setData(electro_cons_x, electro_cons_y, connect='finite')
        self.inversion_timer_curve.setData(inversion_timer_x, inversion_timer_y, connect='finite')
        self.inversion_period_curve.setData(inversion_period_x, inversion_period_y, connect='finite')
        # courbe binaire phase de polarité sur l'axe droit
        polarity_state_y = []
        for val in polarity_phase_y:
            if val != val:  # NaN
                polarity_state_y.append(float('nan'))
            else:
                polarity_state_y.append(1.0 if val else 0.0)
        self.polarity_phase_state_y = polarity_state_y
        self.polarity_phase_curve.setData(polarity_phase_x, polarity_state_y, connect='finite')
        self.cycle_right_vb.setYRange(-0.05, 1.05, padding=0)
        self.boost_curve.setData(boost_x, boost_y, connect='finite')

        # Mettre à jour les courbes RE actives avec le dernier historique
        for _lbl in list(self.reverse_series_items):
            self._refresh_reverse_series(_lbl)
    
    def update_reverse(self, payload: DecodedBase):
        
        t = payload.type
        raw = payload.raw

        # Mise à jour de l’historique temporel (utilisé par le graphe RE)
        now_ts = datetime.now().timestamp()
        for i, b in enumerate(raw[:17]):
            key = (t, i)
            if key in self.reverse_time_history:
                self.reverse_time_history[key].append((now_ts, int(b)))

        if t == 65:
            for i, b in enumerate(raw[:17]):
                self.re_bytes_history[65][i].append(b)
        
        # -------------------------
        # Update per-frame panel using ctypes-based parsers
        # -------------------------
        parsed = None
        try:
            if t == 77:
                parsed = CFrame77.from_bytes(raw).as_dict()
            elif t == 83:
                parsed = CFrame83.from_bytes(raw).as_dict()
            elif t == 65:
                parsed = CFrame65.from_bytes(raw).as_dict()
            elif t == 69:
                parsed = CFrame69.from_bytes(raw).as_dict()
            else:
                parsed = {'type': t, 'raw': list(raw)}
        except Exception:
            parsed = {'type': t, 'raw': list(raw)}

        if parsed:
            # log parsed dict (panels removed from dashboard)
            self.append_log(f"DECODED {t}: {parsed}")
            # update reverse byte table for this frame type
            if 'raw_b0' not in parsed:
                parsed = {**CFrameBase.from_bytes(raw).as_dict(), **parsed}
            table = self.reverse_tables.get(t)
            if table is not None:
                table.populate(parsed)

            # refresh selected series tied to the incoming frame type
            labels = [lbl for lbl, meta in self.reverse_series_meta.items() if meta.get('type') == t]
            for lbl in labels:
                self._refresh_reverse_series(lbl)

        # style not applicable (raw panel removed)
