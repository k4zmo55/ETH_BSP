#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E-AETIS - EHSIM Advanced Ethernet Testing & Inspection System
=============================================================
GELISIM DURUMU: 25 Agustos 2026 - Staj 22. Gun

Bir onceki gune (24 Agustos) ek olarak bugun:
  - PingWorker tamamlandi -> "Ping (ICMP)" sekmesi calisir hale geldi.
  - BenchmarkWorker yazildi -> "Performans & Jitter" sekmesi calisir hale geldi.
  - "PHY / DMA Teshis" sekmesinin altyapisi (ozet tablo + ham register
    tablosu + loopback kontrolu) kuruldu.
"Hata Enjeksiyonu" ve "Bootloader (IAP)" sekmeleri hala gelistirilme
asamasinda (yarinki gune birakildi).

Ekran goruntusu almak icin:  python 25_agustos.py
(Gereksinim: pip install PyQt5 pyqtgraph)
"""

import sys
import os
import csv
import time
import socket
import platform
import subprocess
import re
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

    def phy_read(self, reg):
        data, _ = self.request("PHY_READ|REG:%d" % reg)
        if not data:
            return None
        header, kv = self.parse(data)
        if header != "PHY_REG":
            return None
        try:
            return int(kv.get("VAL", "0"), 16)
        except ValueError:
            return None

    def phy_write(self, reg, value):
        data, _ = self.request("PHY_WRITE|REG:%d|VAL:0x%04X" % (reg, value))
        return data is not None and self.parse(data)[0] == "PHY_WOK"

    def phy_scan(self):
        data, _ = self.request("PHY_SCAN", timeout=3.0)
        return self.parse(data)[1] if data else None

    def loopback(self, enable):
        data, _ = self.request("LOOPBACK|EN:%d" % (1 if enable else 0))
        return data is not None

    def echo(self, payload):
        return self.request(b"ECHO|" + payload.encode("utf-8"))

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
#  ARKA PLAN ISCILERI
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


class PingWorker(QThread):
    """ICMP ping. Ham soket yerine isletim sisteminin ping komutunu kullanir;
    boylece yonetici/root yetkisi gerekmez."""
    log = pyqtSignal(str)
    sample = pyqtSignal(float)
    summary = pyqtSignal(dict)

    def __init__(self, ip, count, size):
        super().__init__()
        self.ip = ip
        self.count = count
        self.size = size
        self._stop = False

    def stop(self):
        self._stop = True

    def _build_cmd(self, seq_size):
        win = platform.system().lower().startswith("win")
        if win:
            return ["ping", "-n", "1", "-l", str(seq_size), "-w", "1000", self.ip]
        if platform.system().lower() == "darwin":
            return ["ping", "-c", "1", "-s", str(seq_size), "-W", "1000", self.ip]
        return ["ping", "-c", "1", "-s", str(seq_size), "-W", "1", self.ip]

    def run(self):
        self.log.emit("ICMP ping: %s, %d paket x %d bayt payload"
                      % (self.ip, self.count, self.size))
        self.log.emit("Not: ICMP yaniti BSP'nin eth_app.c icindeki icmp_handle() "
                      "fonksiyonundan gelir - IP/checksum yolunu dogrular.")

        rtts, lost = [], 0
        rx = re.compile(r"(?:time[<=]|zaman[<=])\s*([\d\.,]+)\s*ms", re.IGNORECASE)

        for i in range(self.count):
            if self._stop:
                self.log.emit("Ping durduruldu.")
                break
            try:
                out = subprocess.run(self._build_cmd(self.size),
                                     capture_output=True, text=True, timeout=5)
                text = (out.stdout or "") + (out.stderr or "")
                m = rx.search(text)
                if out.returncode == 0 and m:
                    ms = float(m.group(1).replace(",", "."))
                    rtts.append(ms)
                    self.sample.emit(ms)
                    self.log.emit("  #%d  yanit  %.2f ms" % (i + 1, ms))
                else:
                    lost += 1
                    self.log.emit("  #%d  yanit yok" % (i + 1))
            except subprocess.TimeoutExpired:
                lost += 1
                self.log.emit("  #%d  zaman asimi" % (i + 1))
            except FileNotFoundError:
                self.log.emit("Sistemde 'ping' komutu bulunamadi.")
                return
            time.sleep(0.15)

        total = len(rtts) + lost
        if not rtts:
            self.log.emit("Hic ICMP yaniti alinamadi. Kontrol edin: kablo, ayni "
                          "alt ag, eth_config.h'de ETH_ENABLE_ICMP=1.")
            return

        mean = sum(rtts) / len(rtts)
        var = sum((x - mean) ** 2 for x in rtts) / len(rtts)
        res = {
            "sent": total, "received": len(rtts), "lost": lost,
            "loss_pct": lost / total * 100.0 if total else 0.0,
            "min_ms": min(rtts), "max_ms": max(rtts),
            "avg_ms": mean, "jitter_ms": var ** 0.5,
        }
        self.log.emit("Ping sonucu: %d/%d yanit, kayip %.1f%% | min %.2f / "
                      "ort %.2f / max %.2f ms | jitter %.2f ms"
                      % (res["received"], total, res["loss_pct"], res["min_ms"],
                         res["avg_ms"], res["max_ms"], res["jitter_ms"]))
        self.summary.emit(res)


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


class BenchmarkWorker(QThread):
    """Gecikme / jitter / bant genisligi olcumu."""
    log = pyqtSignal(str)
    sample = pyqtSignal(float)
    finished_summary = pyqtSignal(dict)
    progress = pyqtSignal(int)

    def __init__(self, proto, count, payload_size, interval_ms):
        super().__init__()
        self.proto = proto
        self.count = count
        self.payload_size = payload_size
        self.interval = interval_ms / 1000.0
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        # PERF_TEST_ oneki firmware tarafinda echo'ya yonlendirilir.
        filler = "A" * max(0, self.payload_size - len("PERF_TEST_"))
        payload = ("PERF_TEST_" + filler).encode("utf-8")

        self.log.emit("Benchmark: %d paket x %d bayt, aralik %d ms"
                      % (self.count, len(payload), int(self.interval * 1000)))

        # Once sayaclari sifirla ki donanim kaybi bu teste ait olsun.
        if self.proto.reset_stats():
            self.log.emit("Cihaz sayaclari sifirlandi.")

        lat = []
        lost = 0
        t_start = time.perf_counter()

        for i in range(self.count):
            if self._stop:
                self.log.emit("Test kullanici tarafindan durduruldu.")
                break

            data, ms = self.proto.request(payload, timeout=0.5)
            if data is None:
                lost += 1
            else:
                lat.append(ms)
                self.sample.emit(ms)

            self.progress.emit(int((i + 1) * 100 / self.count))
            if self.interval > 0:
                time.sleep(self.interval)

        elapsed = time.perf_counter() - t_start
        sent = len(lat) + lost

        if not lat:
            self.log.emit("Hic yanit alinamadi. Cihaz ulasilabilir mi?")
            return

        lat_sorted = sorted(lat)
        mean = sum(lat) / len(lat)
        var = sum((x - mean) ** 2 for x in lat) / len(lat)

        # Bant genisligi: gidis + donus, iki yonlu.
        total_bytes = len(lat) * len(payload) * 2
        mbps = (total_bytes * 8) / elapsed / 1e6 if elapsed > 0 else 0.0

        summary = {
            "sent": sent,
            "received": len(lat),
            "lost": lost,
            "loss_pct": (lost / sent * 100.0) if sent else 0.0,
            "min_ms": lat_sorted[0],
            "max_ms": lat_sorted[-1],
            "avg_ms": mean,
            "jitter_ms": var ** 0.5,
            "p95_ms": lat_sorted[int(len(lat_sorted) * 0.95) - 1],
            "mbps": mbps,
            "elapsed_s": elapsed,
        }

        self.log.emit(
            "Sonuc: %d/%d yanit, kayip %.1f%% | min %.2f / ort %.2f / p95 %.2f "
            "/ max %.2f ms | jitter %.2f ms | ~%.2f Mbps"
            % (summary["received"], sent, summary["loss_pct"],
               summary["min_ms"], summary["avg_ms"], summary["p95_ms"],
               summary["max_ms"], summary["jitter_ms"], summary["mbps"]))

        # Yazilim tarafi kaybi ile donanim tarafi kaybini ayirmak kritik.
        hw = self.proto.get_stats()
        if hw:
            self.log.emit(
                "Cihaz sayaclari -> RX %s frame, dusen %s, donanim kayip %s, "
                "CRC hata %s, TX desc yok %s"
                % (hw.get("RX_FRAMES", "?"), hw.get("RX_DROP", "?"),
                   hw.get("RX_MISS", "?"), hw.get("CRC_ERR", "?"),
                   hw.get("TX_NODESC", "?")))
            if hw.get("RX_MISS", "0") not in ("0", "?"):
                self.log.emit(
                    "UYARI: donanim missed-frame sayaci sifir degil. Paket kaybi "
                    "kablodan degil, ProcessEvents'in gec cagrilmasindan kaynaklaniyor.")
            summary.update({"hw_" + k: v for k, v in hw.items()})

        self.finished_summary.emit(summary)


# =============================================================================
#  ANA PENCERE
# =============================================================================

MONO = QFont("Consolas", 9)

PHY_REGISTERS = [
    (0x00, "BMCR",   "Basic Mode Control"),
    (0x01, "BMSR",   "Basic Mode Status"),
    (0x02, "PHYID1", "PHY Identifier 1"),
    (0x03, "PHYID2", "PHY Identifier 2"),
    (0x04, "ANAR",   "Auto-Neg Advertisement"),
    (0x05, "ANLPAR", "Link Partner Ability"),
    (0x06, "ANER",   "Auto-Neg Expansion"),
    (0x1E, "VND1E",  "Vendor (KSZ: PHY Control 1)"),
    (0x1F, "VND1F",  "Vendor (LAN: Special Ctrl/Status)"),
]


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
        self.tabs.addTab(self._tab_io(),        "Kart G/Ç (Telemetri)")
        self.tabs.addTab(self._tab_ping(),      "Ping (ICMP)")
        self.tabs.addTab(self._tab_console(),   "UDP Konsol")
        self.tabs.addTab(self._tab_phy(),       "PHY / DMA Teshis")
        self.tabs.addTab(self._tab_benchmark(), "Performans & Jitter")
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

    # ------------------------------------------------------------ Tab: Ping

    def _tab_ping(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        info = QLabel(
            "ICMP echo testi. Yanit, BSP'nin eth_app.c dosyasindaki "
            "icmp_handle() fonksiyonundan gelir; yani bu test IP basligi "
            "olusturmayi, checksum hesabini ve TX/RX yolunu birlikte "
            "dogrular. Isletim sisteminin ping komutu kullanilir, yonetici "
            "yetkisi gerekmez.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#555;")
        lay.addWidget(info)

        cfg = QGroupBox("Parametreler")
        g = QGridLayout(cfg)

        g.addWidget(QLabel("Paket sayisi:"), 0, 0)
        self.ping_count = QSpinBox()
        self.ping_count.setRange(1, 1000)
        self.ping_count.setValue(10)
        g.addWidget(self.ping_count, 0, 1)

        g.addWidget(QLabel("Payload (bayt):"), 0, 2)
        self.ping_size = QSpinBox()
        self.ping_size.setRange(0, 1400)
        self.ping_size.setValue(32)
        g.addWidget(self.ping_size, 0, 3)

        self.ping_start = QPushButton("Ping Baslat")
        self.ping_start.clicked.connect(self.do_ping_test)
        g.addWidget(self.ping_start, 0, 4)

        self.ping_stop = QPushButton("Durdur")
        self.ping_stop.setEnabled(False)
        g.addWidget(self.ping_stop, 0, 5)

        lay.addWidget(cfg)

        self.ping_result = QLabel("Henuz ping calistirilmadi.")
        self.ping_result.setFont(MONO)
        lay.addWidget(self.ping_result)

        if HAS_PYQTGRAPH:
            self.ping_plot = pg.PlotWidget(title="ICMP gidis-donus suresi (ms)")
            self.ping_plot.showGrid(x=True, y=True, alpha=0.3)
            self.ping_curve = self.ping_plot.plot(
                pen=pg.mkPen(width=2), symbol="o", symbolSize=5)
            lay.addWidget(self.ping_plot)
        else:
            self.ping_curve = None
        self.ping_samples = []
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
            "PHY_SCAN",
            "PHY_READ|REG:1",
            "PHY_WRITE|REG:0|VAL:0x1200",
            "LOOPBACK|EN:1",
            "LOOPBACK|EN:0",
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

    # ------------------------------------------------------------- Tab: PHY

    def _tab_phy(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        row = QHBoxLayout()
        b1 = QPushButton("Ozet Teshis Oku")
        b1.clicked.connect(self.do_phy_summary)
        row.addWidget(b1)

        b2 = QPushButton("Tum Register'lari Tara")
        b2.clicked.connect(self.do_phy_dump)
        row.addWidget(b2)

        b3 = QPushButton("SMI Adres Taramasi")
        b3.clicked.connect(self.do_phy_scan)
        row.addWidget(b3)

        b4 = QPushButton("Loopback Ac")
        b4.clicked.connect(lambda: self.do_loopback(True))
        row.addWidget(b4)

        b5 = QPushButton("Loopback Kapat")
        b5.clicked.connect(lambda: self.do_loopback(False))
        row.addWidget(b5)
        row.addStretch()
        lay.addLayout(row)

        # --- Ozet tablo ---
        self.summary_table = QTableWidget(7, 2)
        self.summary_table.setHorizontalHeaderLabels(["Parametre", "Deger"])
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.summary_keys = ["BCR", "BSR", "LINK", "SPEED", "DUPLEX",
                             "DMA_RX_ERR", "DMA_TX_ERR"]
        labels = ["PHY BMCR (Basic Control)", "PHY BMSR (Basic Status)",
                  "Link Durumu", "Anlasilan Hiz", "Duplex Modu",
                  "DMA RX Kayip / Dusen", "DMA TX Descriptor Hatasi"]
        for i, lbl in enumerate(labels):
            self.summary_table.setItem(i, 0, QTableWidgetItem(lbl))
            self.summary_table.setItem(i, 1, QTableWidgetItem("-"))
        lay.addWidget(self.summary_table)

        # --- Ham register tablosu ---
        lay.addWidget(QLabel("Ham PHY Register'lari (cift tiklayarak yazabilirsiniz)"))
        self.reg_table = QTableWidget(len(PHY_REGISTERS), 4)
        self.reg_table.setHorizontalHeaderLabels(
            ["Adres", "Isim", "Aciklama", "Deger"])
        self.reg_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i, (addr, name, desc) in enumerate(PHY_REGISTERS):
            self.reg_table.setItem(i, 0, QTableWidgetItem("0x%02X" % addr))
            self.reg_table.setItem(i, 1, QTableWidgetItem(name))
            self.reg_table.setItem(i, 2, QTableWidgetItem(desc))
            self.reg_table.setItem(i, 3, QTableWidgetItem("-"))
        self.reg_table.cellDoubleClicked.connect(self.do_reg_write_prompt)
        lay.addWidget(self.reg_table)
        return w

    # ------------------------------------------------------- Tab: Benchmark

    def _tab_benchmark(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        cfg = QGroupBox("Test Parametreleri")
        g = QGridLayout(cfg)

        g.addWidget(QLabel("Paket sayisi:"), 0, 0)
        self.bm_count = QSpinBox(); self.bm_count.setRange(1, 100000)
        self.bm_count.setValue(200)
        g.addWidget(self.bm_count, 0, 1)

        g.addWidget(QLabel("Payload (bayt):"), 0, 2)
        self.bm_size = QSpinBox(); self.bm_size.setRange(16, 1400)
        self.bm_size.setValue(64)
        g.addWidget(self.bm_size, 0, 3)

        g.addWidget(QLabel("Aralik (ms):"), 0, 4)
        self.bm_interval = QSpinBox(); self.bm_interval.setRange(0, 1000)
        self.bm_interval.setValue(5)
        g.addWidget(self.bm_interval, 0, 5)

        self.bm_start = QPushButton("Testi Baslat")
        self.bm_start.clicked.connect(self.do_benchmark)
        g.addWidget(self.bm_start, 0, 6)

        self.bm_stop = QPushButton("Durdur")
        self.bm_stop.setEnabled(False)
        g.addWidget(self.bm_stop, 0, 7)

        lay.addWidget(cfg)

        self.bm_progress = QProgressBar()
        lay.addWidget(self.bm_progress)

        if HAS_PYQTGRAPH:
            self.plot = pg.PlotWidget(title="Gidis-donus gecikmesi (ms)")
            self.plot.setLabel("left", "Gecikme", units="ms")
            self.plot.setLabel("bottom", "Paket")
            self.plot.showGrid(x=True, y=True, alpha=0.3)
            self.curve = self.plot.plot(pen=pg.mkPen(width=2))
            lay.addWidget(self.plot)
        else:
            warn = QLabel("pyqtgraph kurulu degil - canli grafik devre disi.\n"
                          "Kurmak icin:  pip install pyqtgraph")
            warn.setAlignment(Qt.AlignCenter)
            warn.setStyleSheet("color:#b58900; padding:40px;")
            lay.addWidget(warn)
            self.curve = None

        self.bm_result = QLabel("Henuz test calistirilmadi.")
        self.bm_result.setFont(MONO)
        lay.addWidget(self.bm_result)
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

    # --------------------------------------------------------- Eylem: Ping

    def do_ping_test(self):
        self._sync_proto()
        self.ping_samples = []
        if self.ping_curve:
            self.ping_curve.setData([], [])

        w = PingWorker(self.proto.ip, self.ping_count.value(),
                       self.ping_size.value())
        w.sample.connect(self._on_ping_sample)
        w.summary.connect(self._on_ping_done)
        w.finished.connect(lambda: self.ping_start.setEnabled(True))
        w.finished.connect(lambda: self.ping_stop.setEnabled(False))

        self.ping_start.setEnabled(False)
        self.ping_stop.setEnabled(True)
        try:
            self.ping_stop.clicked.disconnect()
        except TypeError:
            pass
        self.ping_stop.clicked.connect(w.stop)
        self._run(w)

    def _on_ping_sample(self, ms):
        self.ping_samples.append(ms)
        if self.ping_curve:
            self.ping_curve.setData(list(range(len(self.ping_samples))),
                                    self.ping_samples)

    def _on_ping_done(self, res):
        self.ping_result.setText(
            "Gonderilen %d | Alinan %d | Kayip %.1f%%\n"
            "min %.2f ms   ort %.2f ms   max %.2f ms   jitter %.2f ms"
            % (res["sent"], res["received"], res["loss_pct"],
               res["min_ms"], res["avg_ms"], res["max_ms"], res["jitter_ms"]))

    def do_phy_summary(self):
        self._sync_proto()
        kv = self.proto.get_phy_stats()
        if kv is None:
            self.log("PHY teshis verisi alinamadi.")
            return
        self._apply_summary(kv)
        self.log("PHY/DMA teshis verileri guncellendi.")

    def _apply_summary(self, kv):
        for i, key in enumerate(self.summary_keys):
            self.summary_table.setItem(i, 1, QTableWidgetItem(kv.get(key, "-")))

        link = kv.get("LINK", "").upper()
        detail = "%s %s" % (kv.get("SPEED", ""), kv.get("DUPLEX", ""))
        self._set_link_badge(link == "UP", detail.strip())

    def do_phy_dump(self):
        self._sync_proto()
        self.log("Tum PHY register'lari okunuyor...")
        ok = 0
        for i, (addr, name, _) in enumerate(PHY_REGISTERS):
            val = self.proto.phy_read(addr)
            if val is None:
                self.reg_table.setItem(i, 3, QTableWidgetItem("okunamadi"))
            else:
                item = QTableWidgetItem("0x%04X   (0b%s)" % (val, format(val, "016b")))
                item.setFont(MONO)
                self.reg_table.setItem(i, 3, item)
                ok += 1
        self.log("%d/%d register okundu." % (ok, len(PHY_REGISTERS)))

    def do_reg_write_prompt(self, rowidx, col):
        if col != 3:
            return
        addr, name, _ = PHY_REGISTERS[rowidx]
        current = self.reg_table.item(rowidx, 3).text()
        QMessageBox.information(
            self, "PHY Register Yazma",
            "%s (0x%02X) yazmak icin UDP Konsol sekmesinde:\n\n"
            "PHY_WRITE|REG:%d|VAL:0x1234\n\n"
            "Mevcut deger: %s" % (name, addr, addr, current))

    def do_phy_scan(self):
        self._sync_proto()
        self.log("SMI bus'inda PHY adresi taraniyor (0-31)...")
        kv = self.proto.phy_scan()
        if kv is None:
            self.log("Tarama yaniti alinamadi.")
            return
        addr = kv.get("ADDR", "NONE")
        if addr == "NONE":
            self.log("Hicbir adreste PHY bulunamadi. RMII saati, MDC/MDIO "
                     "baglantisi veya PHY beslemesini kontrol edin.")
            return
        cfg = kv.get("CONFIGURED", "?")
        self.log("PHY bulundu: adres %s (eth_config.h'de tanimli: %s)" % (addr, cfg))
        if addr != cfg:
            self.log("UYARI: eth_config.h icindeki PHY_ADDRESS yanlis. "
                     "%s olarak duzeltip yeniden derleyin." % addr)

    def do_loopback(self, enable):
        self._sync_proto()
        if self.proto.loopback(enable):
            self.log("PHY dahili loopback %s." % ("acildi" if enable else "kapatildi"))
        else:
            self.log("Loopback komutu basarisiz.")

    def do_benchmark(self):
        self._sync_proto()
        self.latencies = []
        if self.curve:
            self.curve.setData([], [])
        self.bm_progress.setValue(0)

        w = BenchmarkWorker(self.proto, self.bm_count.value(),
                            self.bm_size.value(), self.bm_interval.value())
        w.sample.connect(self._on_sample)
        w.progress.connect(self.bm_progress.setValue)
        w.finished_summary.connect(self._on_bm_done)
        w.finished.connect(lambda: self.bm_start.setEnabled(True))
        w.finished.connect(lambda: self.bm_stop.setEnabled(False))

        self.bm_start.setEnabled(False)
        self.bm_stop.setEnabled(True)
        try:
            self.bm_stop.clicked.disconnect()
        except TypeError:
            pass
        self.bm_stop.clicked.connect(w.stop)
        self._run(w)

    def _on_sample(self, ms):
        self.latencies.append(ms)
        if self.curve:
            self.curve.setData(list(range(len(self.latencies))), self.latencies)

    def _on_bm_done(self, summary):
        self.last_summary = summary
        self.bm_result.setText(
            "Gonderilen %d | Alinan %d | Kayip %.2f%%\n"
            "min %.2f ms   ort %.2f ms   p95 %.2f ms   max %.2f ms   "
            "jitter %.2f ms\nTahmini bant genisligi: %.2f Mbps  (%.1f sn)"
            % (summary["sent"], summary["received"], summary["loss_pct"],
               summary["min_ms"], summary["avg_ms"], summary["p95_ms"],
               summary["max_ms"], summary["jitter_ms"],
               summary["mbps"], summary["elapsed_s"]))

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
