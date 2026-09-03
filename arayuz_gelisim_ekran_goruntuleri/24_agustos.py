#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E-AETIS - EHSIM Advanced Ethernet Testing & Inspection System
=============================================================
GELISIM DURUMU: 24 Agustos 2026 - Staj 21. Gun

Bu dosya, staj defterinde 24 Agustos icin anlatilan gelisim asamasini
yansitir: Protocol katmani, ana pencere ve sekmeli (tab) yapinin
iskeleti kuruldu; DiscoveryWorker ve TelemetryWorker sinif iskeletleri
yazildi. Ping / PHY-DMA Teshis / Performans & Jitter / Hata Enjeksiyonu
/ Bootloader (IAP) sekmeleri henuz icerik kazanmadigi icin bu surumde
"gelistirme asamasinda" olarak gorunur.

Ekran goruntusu almak icin:  python 24_agustos.py
(Gereksinim: pip install PyQt5 pyqtgraph)
"""

import sys
import os
import csv
import time
import socket
import platform
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit, QTableWidget,
    QTableWidgetItem, QTabWidget, QProgressBar, QFileDialog, QHeaderView,
    QSpinBox, QComboBox, QCheckBox, QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPixmap, QTextCursor

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False


# =============================================================================
#  PROTOKOL KATMANI
#  Tum soket islemleri buradan gecer. Arayuz asla dogrudan socket kullanmaz.
# =============================================================================

class Protocol:
    """E-AETIS UDP sozlesmesi. Firmware tarafi eth_app.c icindedir."""

    DEFAULT_PORT = 5000

    def __init__(self, ip="192.168.1.50", port=DEFAULT_PORT, timeout=1.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout

    # --- Dusuk seviye ---------------------------------------------------

    def _sock(self, broadcast=False, timeout=None):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if broadcast:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(timeout if timeout is not None else self.timeout)
        return s

    def request(self, payload, expect_reply=True, timeout=None, ip=None):
        """Tek istek/yanit. (yanit_bytes, gecikme_ms) veya (None, None)."""
        if isinstance(payload, str):
            payload = payload.encode("utf-8")

        target = ip or self.ip
        s = self._sock(timeout=timeout)
        try:
            t0 = time.perf_counter()
            s.sendto(payload, (target, self.port))
            if not expect_reply:
                return b"", 0.0
            data, _ = s.recvfrom(4096)
            return data, (time.perf_counter() - t0) * 1000.0
        except socket.timeout:
            return None, None
        finally:
            s.close()

    def fire(self, payload, ip=None):
        """Yanit beklemeden gonder (fuzzing icin, ileride kullanilacak)."""
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        s = self._sock()
        try:
            s.sendto(payload, (ip or self.ip, self.port))
        finally:
            s.close()

    # --- Yanit ayristirma -----------------------------------------------

    @staticmethod
    def parse(data):
        """'HEADER|K:V|K:V' -> (header, {K: V}). Bozuk yanitta cokmez."""
        if not data:
            return None, {}
        text = data.decode("utf-8", errors="replace").strip()
        parts = text.split("|")
        header = parts[0] if parts else ""
        kv = {}
        for p in parts[1:]:
            if ":" in p:
                k, _, v = p.partition(":")   # split degil partition: cok kolonlu
                kv[k.strip()] = v.strip()    # degerler guvenli
        return header, kv

    # --- Komutlar --------------------------------------------------------

    def discover(self, timeout=2.0):
        """Agda cihaz ara. [(ip, bilgi_dict), ...] doner."""
        s = self._sock(broadcast=True, timeout=timeout)
        found = []
        try:
            s.sendto(b"DISCOVER_STM32_REQ", ("255.255.255.255", self.port))
            deadline = time.time() + timeout
            while time.time() < deadline:
                s.settimeout(max(0.05, deadline - time.time()))
                try:
                    data, addr = s.recvfrom(1024)
                except socket.timeout:
                    break
                header, kv = self.parse(data)
                if header.startswith("STM32_ACK"):
                    found.append((addr[0], kv))
        finally:
            s.close()
        return found

    def get_phy_stats(self):
        data, _ = self.request("GET_PHY_DMA_STATS", timeout=1.5)
        return self.parse(data)[1] if data else None

    def get_stats(self):
        data, _ = self.request("GET_STATS", timeout=1.5)
        return self.parse(data)[1] if data else None

    def reset_stats(self):
        data, _ = self.request("RESET_STATS")
        return data is not None

    # --- Telemetri ---

    def get_vars(self):
        """Cihazdaki degiskenleri kesfet.
        [{'index','name','type','access','unit'}, ...] veya None."""
        data, _ = self.request("GET_VARS", timeout=2.0)
        if not data:
            return None
        header, kv = self.parse(data)
        if header != "VARS":
            return None

        out = []
        for key, val in kv.items():
            if not key.startswith("V") or key == "VARS":
                continue
            # val = "ad:tip:erisim:birim"
            fields = val.split(":")
            if len(fields) < 4:
                continue
            try:
                idx = int(key[1:])
            except ValueError:
                continue
            out.append({
                "index": idx,
                "name": fields[0],
                "type": fields[1],
                "access": fields[2],
                "unit": "" if fields[3] == "-" else fields[3],
            })
        out.sort(key=lambda d: d["index"])
        return out

    def read_all(self):
        """{'ad': 'deger', ...} veya None."""
        data, _ = self.request("READ_ALL", timeout=1.5)
        if not data:
            return None
        header, kv = self.parse(data)
        return kv if header == "VALS" else None

    def read_var(self, name):
        data, _ = self.request("READ|VAR:%s" % name)
        if not data:
            return None
        header, kv = self.parse(data)
        return kv.get(name) if header == "VAL" else None

    def write_var(self, name, value):
        """(basarili, geri_okunan_deger_veya_hata)"""
        data, _ = self.request("WRITE|VAR:%s|VAL:%s" % (name, value), timeout=2.0)
        if not data:
            return False, "yanit yok"
        header, kv = self.parse(data)
        if header == "WOK":
            return True, kv.get(name, "?")
        return False, data.decode("utf-8", "replace")


# =============================================================================
#  ARKA PLAN ISCILERI  (bugun sadece iki tanesi yazildi)
# =============================================================================

class DiscoveryWorker(QThread):
    log = pyqtSignal(str)
    found = pyqtSignal(str, dict)

    def __init__(self, proto):
        super().__init__()
        self.proto = proto

    def run(self):
        self.log.emit("Agda cihaz araniyor (UDP broadcast :%d)..." % self.proto.port)
        try:
            results = self.proto.discover()
        except Exception as e:
            self.log.emit("Kesif hatasi: %s" % e)
            return

        if not results:
            self.log.emit("Cihaz bulunamadi. Kontrol edin: kablo, ayni alt ag, "
                          "firmware'de ETH_ENABLE_EAETIS_CMD=1, guvenlik duvari.")
            return

        for ip, info in results:
            desc = ", ".join("%s=%s" % kv for kv in info.items())
            self.log.emit("Cihaz bulundu: %s  (%s)" % (ip, desc))
            self.found.emit(ip, info)


class TelemetryWorker(QThread):
    """Kayitli degiskenleri periyodik olarak okur."""
    log = pyqtSignal(str)
    values = pyqtSignal(dict)

    def __init__(self, proto, interval_ms):
        super().__init__()
        self.proto = proto
        self.interval = interval_ms / 1000.0
        self._stop = False
        self._fail_streak = 0

    def stop(self):
        self._stop = True

    def run(self):
        while not self._stop:
            vals = self.proto.read_all()
            if vals is None:
                self._fail_streak += 1
                if self._fail_streak == 3:
                    self.log.emit("Telemetri okunamiyor (3 ardisik hata). "
                                  "Firmware'de ETH_ENABLE_TELEMETRY=1 mi?")
            else:
                self._fail_streak = 0
                self.values.emit(vals)
            time.sleep(self.interval)


# =============================================================================
#  ANA PENCERE
# =============================================================================

MONO = QFont("Consolas", 9)


class EAETISWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.proto = Protocol()
        self.workers = []
        self.latencies = []
        self.last_summary = {}

        self.setWindowTitle("E-AETIS - EHSIM Advanced Ethernet Testing & "
                            "Inspection System")
        self.resize(1180, 780)

        self._build_ui()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_link)
        self.poll_timer.setInterval(2000)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_connection_bar())

        split = QSplitter(Qt.Vertical)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_io(),      "Kart G/Ç (Telemetri)")
        self.tabs.addTab(self._tab_placeholder(
            "Ping (ICMP) sekmesi henuz gelistirilme asamasinda."), "Ping (ICMP)")
        self.tabs.addTab(self._tab_console(), "UDP Konsol")
        self.tabs.addTab(self._tab_placeholder(
            "PHY / DMA Teshis sekmesi henuz gelistirilme asamasinda."), "PHY / DMA Teshis")
        self.tabs.addTab(self._tab_placeholder(
            "Performans & Jitter sekmesi henuz gelistirilme asamasinda."), "Performans & Jitter")
        self.tabs.addTab(self._tab_placeholder(
            "Hata Enjeksiyonu sekmesi henuz gelistirilme asamasinda."), "Hata Enjeksiyonu")
        self.tabs.addTab(self._tab_placeholder(
            "Bootloader (IAP) sekmesi henuz gelistirilme asamasinda."), "Bootloader (IAP)")
        split.addWidget(self.tabs)

        split.addWidget(self._build_log_panel())
        split.setSizes([520, 220])
        outer.addWidget(split)

        self.setCentralWidget(root)

    def _build_header(self):
        row = QHBoxLayout()

        logo = QLabel()
        for candidate in ("ehsim_logo.png", "logo.png"):
            if os.path.exists(candidate):
                pix = QPixmap(candidate)
                if not pix.isNull():
                    logo.setPixmap(pix.scaledToHeight(48, Qt.SmoothTransformation))
                break
        row.addWidget(logo)

        title = QLabel("E-AETIS")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        row.addWidget(title)

        sub = QLabel("Advanced Ethernet Testing & Inspection System")
        sub.setStyleSheet("color: #666;")
        row.addWidget(sub)

        row.addStretch()

        self.link_badge = QLabel("BAGLANTI YOK")
        self.link_badge.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.link_badge.setStyleSheet(
            "background:#c0392b; color:white; padding:6px 14px; border-radius:4px;")
        row.addWidget(self.link_badge)
        return row

    def _build_connection_bar(self):
        box = QGroupBox("Hedef Cihaz")
        lay = QHBoxLayout(box)

        lay.addWidget(QLabel("IP:"))
        self.ip_input = QLineEdit("192.168.1.50")
        self.ip_input.setFixedWidth(130)
        lay.addWidget(self.ip_input)

        lay.addWidget(QLabel("Port:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(Protocol.DEFAULT_PORT)
        self.port_input.setFixedWidth(80)
        lay.addWidget(self.port_input)

        btn_disc = QPushButton("Otomatik Kesif")
        btn_disc.clicked.connect(self.do_discover)
        lay.addWidget(btn_disc)

        btn_ping = QPushButton("Baglantiyi Test Et")
        btn_ping.clicked.connect(self.do_ping)
        lay.addWidget(btn_ping)

        self.chk_poll = QCheckBox("Link durumunu surekli izle")
        self.chk_poll.stateChanged.connect(self._toggle_poll)
        lay.addWidget(self.chk_poll)

        lay.addStretch()
        return box

    def _build_log_panel(self):
        box = QGroupBox("Olay Gunlugu")
        lay = QVBoxLayout(box)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(MONO)
        lay.addWidget(self.log_text)

        row = QHBoxLayout()
        b1 = QPushButton("Temizle")
        b1.clicked.connect(self.log_text.clear)
        row.addWidget(b1)

        b2 = QPushButton("Gunlugu Kaydet (.log)")
        b2.clicked.connect(self.save_log)
        row.addWidget(b2)

        b3 = QPushButton("Test Raporu (.csv)")
        b3.clicked.connect(self.export_csv)
        row.addWidget(b3)

        row.addStretch()
        lay.addLayout(row)
        return box

    # ------------------------------------------------------- Tab: Kart G/Ç

    def _tab_io(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        info = QLabel(
            "Karttaki degiskenler otomatik kesfedilir. Sensor degerleri salt "
            "okunur, cikislar (LED, role) yazilabilir. Yeni bir degisken "
            "eklemek icin sadece main.c'de ETH_BSP_RegisterVar() cagirmaniz "
            "yeterlidir - arayuzde hicbir degisiklik gerekmez.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#555;")
        lay.addWidget(info)

        row = QHBoxLayout()
        b_disc = QPushButton("Degiskenleri Kesfet")
        b_disc.clicked.connect(self.do_discover_vars)
        row.addWidget(b_disc)

        b_read = QPushButton("Bir Kez Oku")
        b_read.clicked.connect(self.do_read_vars_once)
        row.addWidget(b_read)

        row.addWidget(QLabel("Periyot (ms):"))
        self.io_interval = QSpinBox()
        self.io_interval.setRange(50, 10000)
        self.io_interval.setValue(500)
        self.io_interval.setFixedWidth(90)
        row.addWidget(self.io_interval)

        self.io_live = QCheckBox("Canli izle")
        self.io_live.stateChanged.connect(self._toggle_telemetry)
        row.addWidget(self.io_live)
        row.addStretch()
        lay.addLayout(row)

        self.io_table = QTableWidget(0, 5)
        self.io_table.setHorizontalHeaderLabels(
            ["Degisken", "Deger", "Birim", "Tip / Erisim", "Kontrol"])
        self.io_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.io_table)

        # --- Yazma kutusu ---
        wbox = QGroupBox("Karta Deger Yaz")
        g = QHBoxLayout(wbox)
        g.addWidget(QLabel("Degisken:"))
        self.io_write_name = QComboBox()
        self.io_write_name.setEditable(True)
        self.io_write_name.setMinimumWidth(160)
        g.addWidget(self.io_write_name)

        g.addWidget(QLabel("Deger:"))
        self.io_write_val = QLineEdit("1")
        self.io_write_val.setFixedWidth(100)
        g.addWidget(self.io_write_val)

        b_w = QPushButton("Yaz")
        b_w.clicked.connect(self.do_write_var)
        g.addWidget(b_w)
        g.addStretch()
        lay.addWidget(wbox)

        if HAS_PYQTGRAPH:
            hrow = QHBoxLayout()
            hrow.addWidget(QLabel("Grafige alinacak degisken:"))
            self.io_plot_var = QComboBox()
            self.io_plot_var.setMinimumWidth(160)
            hrow.addWidget(self.io_plot_var)
            hb = QPushButton("Grafigi Temizle")
            hb.clicked.connect(self._clear_io_plot)
            hrow.addWidget(hb)
            hrow.addStretch()
            lay.addLayout(hrow)

            self.io_plot = pg.PlotWidget(title="Canli degisken izleme")
            self.io_plot.showGrid(x=True, y=True, alpha=0.3)
            self.io_curve = self.io_plot.plot(pen=pg.mkPen(width=2))
            self.io_history = []
            lay.addWidget(self.io_plot)
        else:
            self.io_curve = None
            self.io_history = []

        self.io_vars = []
        return w

    # ---------------------------------------------------------- Tab: Konsol

    def _tab_console(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        info = QLabel("Cihaza ham komut gonderin. Bilinmeyen komutlar firmware "
                      "tarafindan sessizce yok sayilir; genel yankilama icin "
                      "ECHO| onekini kullanin.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#555;")
        lay.addWidget(info)

        row = QHBoxLayout()
        self.cmd_combo = QComboBox()
        self.cmd_combo.setEditable(True)
        self.cmd_combo.addItems([
            "GET_PHY_DMA_STATS",
            "GET_STATS",
            "RESET_STATS",
            "GET_VARS",
            "READ_ALL",
            "READ|VAR:sicaklik",
            "WRITE|VAR:led|VAL:1",
            "ECHO|merhaba",
            "DISCOVER_STM32_REQ",
        ])
        row.addWidget(self.cmd_combo, 1)

        btn = QPushButton("Gonder")
        btn.clicked.connect(self.do_send_command)
        row.addWidget(btn)
        lay.addLayout(row)

        self.console_out = QTextEdit()
        self.console_out.setReadOnly(True)
        self.console_out.setFont(MONO)
        lay.addWidget(self.console_out)
        return w

    # ------------------------------------------------------ Tab: Placeholder

    def _tab_placeholder(self, text):
        """Henuz gelistirilmemis sekmeler icin gecici bosluk tutucu."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#999; font-style: italic; padding: 60px;")
        lay.addWidget(lbl)
        return w

    # ------------------------------------------------------------- Yardimci

    def log(self, msg):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append("[%s] %s" % (stamp, msg))
        self.log_text.moveCursor(QTextCursor.End)

    def _sync_proto(self):
        self.proto.ip = self.ip_input.text().strip()
        self.proto.port = self.port_input.value()

    def _run(self, worker):
        worker.log.connect(self.log)
        worker.finished.connect(lambda: self.workers.remove(worker)
                                if worker in self.workers else None)
        self.workers.append(worker)
        worker.start()
        return worker

    def _set_link_badge(self, up, detail=""):
        if up:
            self.link_badge.setText("LINK UP  " + detail)
            self.link_badge.setStyleSheet(
                "background:#27ae60; color:white; padding:6px 14px; border-radius:4px;")
        else:
            self.link_badge.setText("BAGLANTI YOK")
            self.link_badge.setStyleSheet(
                "background:#c0392b; color:white; padding:6px 14px; border-radius:4px;")

    def _apply_summary(self, kv):
        """PHY/DMA teshis tablosu bu asamada henuz yok; sadece link rozeti guncellenir."""
        link = kv.get("LINK", "").upper()
        detail = "%s %s" % (kv.get("SPEED", ""), kv.get("DUPLEX", ""))
        self._set_link_badge(link == "UP", detail.strip())

    # --------------------------------------------------------------- Eylem

    def do_discover(self):
        self._sync_proto()
        w = DiscoveryWorker(self.proto)
        w.found.connect(self._on_discovered)
        self._run(w)

    def _on_discovered(self, ip, info):
        self.ip_input.setText(ip)
        self._sync_proto()

    def do_ping(self):
        self._sync_proto()
        data, ms = self.proto.request("GET_PHY_DMA_STATS", timeout=1.5)
        if data is None:
            self.log("Cihaz yanit vermiyor (%s:%d)." % (self.proto.ip, self.proto.port))
            self._set_link_badge(False)
            return
        header, kv = self.proto.parse(data)
        self.log("Yanit alindi (%.2f ms): %s" % (ms, header))
        self._apply_summary(kv)

    def _toggle_poll(self, state):
        if state == Qt.Checked:
            self._sync_proto()
            self.poll_timer.start()
            self.log("Surekli link izleme acildi (2 sn araliklarla).")
        else:
            self.poll_timer.stop()
            self.log("Surekli link izleme kapatildi.")

    def _poll_link(self):
        kv = self.proto.get_phy_stats()
        if kv is None:
            self._set_link_badge(False)
            return
        self._apply_summary(kv)

    def do_send_command(self):
        self._sync_proto()
        cmd = self.cmd_combo.currentText().strip()
        if not cmd:
            return
        data, ms = self.proto.request(cmd, timeout=3.0)
        self.console_out.append("> %s" % cmd)
        if data is None:
            self.console_out.append("  (yanit yok / zaman asimi)\n")
        else:
            self.console_out.append("< %s   [%.2f ms]\n"
                                    % (data.decode("utf-8", "replace"), ms))
        self.console_out.moveCursor(QTextCursor.End)

    # ------------------------------------------------------- Eylem: Kart G/Ç

    def do_discover_vars(self):
        self._sync_proto()
        variables = self.proto.get_vars()
        if variables is None:
            self.log("Degisken listesi alinamadi. Firmware'de "
                     "ETH_ENABLE_TELEMETRY=1 olmali ve main.c'de en az bir "
                     "ETH_BSP_RegisterVar() cagrisi bulunmali.")
            return
        if not variables:
            self.log("Cihazda kayitli degisken yok. main.c'de "
                     "ETH_BSP_RegisterVar() cagirin.")
            self.io_table.setRowCount(0)
            return

        self.io_vars = variables
        self.io_table.setRowCount(len(variables))
        self.io_write_name.clear()
        if HAS_PYQTGRAPH:
            self.io_plot_var.clear()

        for i, v in enumerate(variables):
            self.io_table.setItem(i, 0, QTableWidgetItem(v["name"]))

            val_item = QTableWidgetItem("-")
            val_item.setFont(MONO)
            self.io_table.setItem(i, 1, val_item)

            self.io_table.setItem(i, 2, QTableWidgetItem(v["unit"] or "-"))
            self.io_table.setItem(i, 3, QTableWidgetItem(
                "%s / %s" % (v["type"], "yazilabilir" if v["access"] == "rw"
                             else "salt okunur")))

            if v["access"] == "rw":
                btn = QPushButton("Ac / Kapat" if v["type"] == "u8" else "Yaz")
                btn.clicked.connect(
                    lambda _, name=v["name"], t=v["type"]: self._quick_write(name, t))
                self.io_table.setCellWidget(i, 4, btn)
                self.io_write_name.addItem(v["name"])
            else:
                self.io_table.setItem(i, 4, QTableWidgetItem("-"))

            if HAS_PYQTGRAPH:
                self.io_plot_var.addItem(v["name"])

        rw = sum(1 for v in variables if v["access"] == "rw")
        self.log("%d degisken bulundu (%d yazilabilir): %s"
                 % (len(variables), rw, ", ".join(v["name"] for v in variables)))

    def _quick_write(self, name, vtype):
        """u8 degiskenler icin ac/kapat, digerleri icin kutudaki degeri yaz."""
        self._sync_proto()
        if vtype == "u8":
            current = self._current_value(name)
            try:
                new = 0 if float(current) >= 0.5 else 1
            except (TypeError, ValueError):
                new = 1
            value = str(new)
        else:
            value = self.io_write_val.text().strip() or "0"

        ok, result = self.proto.write_var(name, value)
        if ok:
            self.log("%s <- %s  (karttan geri okunan: %s)" % (name, value, result))
            self.do_read_vars_once()
        else:
            self.log("%s yazilamadi: %s" % (name, result))

    def _current_value(self, name):
        for i in range(self.io_table.rowCount()):
            if self.io_table.item(i, 0) and self.io_table.item(i, 0).text() == name:
                item = self.io_table.item(i, 1)
                return item.text() if item else None
        return None

    def do_write_var(self):
        name = self.io_write_name.currentText().strip()
        if not name:
            self.log("Once bir degisken secin.")
            return
        self._sync_proto()
        value = self.io_write_val.text().strip()
        ok, result = self.proto.write_var(name, value)
        if ok:
            self.log("%s <- %s  (karttan geri okunan: %s)" % (name, value, result))
            self.do_read_vars_once()
        else:
            self.log("%s yazilamadi: %s" % (name, result))

    def do_read_vars_once(self):
        self._sync_proto()
        vals = self.proto.read_all()
        if vals is None:
            self.log("Degerler okunamadi.")
            return
        self._apply_values(vals)

    def _apply_values(self, vals):
        for i in range(self.io_table.rowCount()):
            name_item = self.io_table.item(i, 0)
            if not name_item:
                continue
            v = vals.get(name_item.text())
            if v is not None:
                item = QTableWidgetItem(v)
                item.setFont(MONO)
                self.io_table.setItem(i, 1, item)

        if HAS_PYQTGRAPH and self.io_curve is not None:
            sel = self.io_plot_var.currentText()
            if sel and sel in vals:
                try:
                    self.io_history.append(float(vals[sel]))
                except ValueError:
                    return
                if len(self.io_history) > 600:
                    self.io_history = self.io_history[-600:]
                self.io_curve.setData(list(range(len(self.io_history))),
                                      self.io_history)
                self.io_plot.setTitle("Canli izleme: %s" % sel)

    def _clear_io_plot(self):
        self.io_history = []
        if self.io_curve is not None:
            self.io_curve.setData([], [])

    def _toggle_telemetry(self, state):
        if state == Qt.Checked:
            if not self.io_vars:
                self.log("Once 'Degiskenleri Kesfet' butonuna basin.")
                self.io_live.setChecked(False)
                return
            self._sync_proto()
            self.telemetry_worker = TelemetryWorker(self.proto,
                                                    self.io_interval.value())
            self.telemetry_worker.values.connect(self._apply_values)
            self._run(self.telemetry_worker)
            self.log("Canli telemetri baslatildi (%d ms)." % self.io_interval.value())
        else:
            if getattr(self, "telemetry_worker", None):
                self.telemetry_worker.stop()
                self.telemetry_worker = None
                self.log("Canli telemetri durduruldu.")

    # ------------------------------------------------------------- Disari

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Gunlugu kaydet", "", "Log (*.log)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.log_text.toPlainText())
        self.log("Gunluk kaydedildi: %s" % path)

    def export_csv(self):
        if not self.last_summary and not self.latencies:
            self.log("Once bir performans testi calistirin.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Raporu kaydet", "", "CSV (*.csv)")
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(["E-AETIS Test Raporu"])
            wr.writerow(["Tarih", datetime.now().isoformat(timespec="seconds")])
            wr.writerow(["Hedef", "%s:%d" % (self.proto.ip, self.proto.port)])
            wr.writerow([])
            wr.writerow(["Metrik", "Deger"])
            for k, v in self.last_summary.items():
                wr.writerow([k, v])
            wr.writerow([])
            wr.writerow(["Paket #", "Gecikme (ms)"])
            for i, ms in enumerate(self.latencies):
                wr.writerow([i, "%.3f" % ms])

        self.log("Rapor kaydedildi: %s" % path)

    def closeEvent(self, event):
        self.poll_timer.stop()
        if getattr(self, "telemetry_worker", None):
            self.telemetry_worker.stop()
        for w in list(self.workers):
            if hasattr(w, "stop"):
                w.stop()
            w.wait(1500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = EAETISWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
