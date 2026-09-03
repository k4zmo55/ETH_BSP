#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test gunleri icin ornek veri ekran goruntusu ureteci
======================================================
Bu script, staj defterinde GUI uzerinden gercek donanimla test yapildigi
anlatilan gunler icin (27 Agustos, 28 Agustos x2, 8 Eylul, 9 Eylul)
26_agustos.py'deki (= gunumuzdeki ethernet_test_gui.py ile ayni) tam
ozellikli E-AETIS arayuzunu, sahte bir "cihaz" simulatoru uzerinden
calistirip ekran goruntusu alir.

ONEMLI: Buradaki sayilar GERCEK olcum degildir; DIKKATLI SECILMIS,
uygulamanin KENDI hesaplama formulleriyle (BenchmarkWorker, GET_STATS
vb.) tutarli uretilmis ORNEK (placeholder) degerlerdir. Amac, gercek
kart verileri elde edildiginde bu ekran goruntuleriyle KARSILASTIRMA
yapabilmektir - bkz. staj_defteri_final.txt ilgili gun anlatimlari.

Kullanilan sahte cihaz yaniti mantigi (FakeDevice.handle) Protocol.request()
seviyesinde devreye girer; boylece GUI'nin gercek buton/worker kodu
(do_discover_vars, do_write_var, do_benchmark, do_fault_injection,
FirmwareUpdateWorker...) HICBIR DEGISIKLIK YAPILMADAN calisir - ekranda
gorulen her sey uygulamanin gercek kod yolundan gecmistir.

Calistirmak icin:  python test_gunleri_ornek_veriler.py
(Gereksinim: pip install PyQt5 pyqtgraph)
"""

import os
import sys
import time
import zlib
import random
import tempfile
import importlib.util


HERE = os.path.dirname(os.path.abspath(__file__))


def load_gui_module():
    """26 Agustos surumunu yukle (o gunden sonra GUI kodu degismedi)."""
    path = os.path.join(HERE, "26_agustos.py")
    spec = importlib.util.spec_from_file_location("gui_full", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FakeDevice:
    """UDP karsi tarafini (STM32 karti) taklit eden basit yanit motoru.

    Sadece bu ekran goruntuleri icin kullanilir; gercek Protocol.request()
    yerine gecer. Format, Src/eth_app.c -> eaetis_handle()'daki gercek
    E-AETIS yanit sozdizimine (BASLIK|ANAHTAR:DEGER|...) birebir uyar.
    """

    def __init__(self, seed=0, base_latency_ms=0.42, jitter_sigma_ms=0.15):
        self.rng = random.Random(seed)
        self.base_latency_ms = base_latency_ms
        self.jitter_sigma_ms = jitter_sigma_ms
        self.dev = "STM32H563"
        self.phy = "LAN8720A"
        self.rx_frames = 0
        self.rx_drop = 0
        self.fail_crc = False
        # name -> (deger, tip, erisim(ro/rw), birim)
        self.vars = {
            "sicaklik":          ("42.8", "f32", "ro", "C"),
            "besleme_gerilimi":  ("3.31", "f32", "ro", "V"),
            "calisma_suresi":    ("187",  "u32", "ro", "s"),
            "nem":               ("46.2", "f32", "ro", "%"),
            "led":               ("1",    "u8",  "rw", "-"),
        }

    def _latency(self):
        return round(max(0.05, self.rng.gauss(self.base_latency_ms,
                                               self.jitter_sigma_ms)), 3)

    def handle(self, payload_bytes):
        text = payload_bytes.decode("utf-8", "replace")
        ms = self._latency()

        if text == "DISCOVER_STM32_REQ":
            return ("STM32_ACK|DEV:%s|PHY:%s" % (self.dev, self.phy)).encode(), ms

        if text == "GET_PHY_DMA_STATS":
            return (b"PHY_DMA_STATS|BCR:0x1200|BSR:0x782D|LINK:UP|SPEED:100|"
                    b"DUPLEX:FULL|DMA_RX_ERR:0|DMA_TX_ERR:0"), ms

        if text == "GET_STATS":
            return ("STATS|RX_FRAMES:%d|RX_DROP:%d|RX_MISS:0|CRC_ERR:0|TX_NODESC:0"
                    % (self.rx_frames, self.rx_drop)).encode(), ms

        if text == "RESET_STATS":
            self.rx_frames = 0
            self.rx_drop = 0
            return b"RESET_OK", ms

        if text == "GET_VARS":
            parts = []
            for i, (name, (val, typ, acc, unit)) in enumerate(self.vars.items()):
                parts.append("V%d:%s:%s:%s:%s" % (i, name, typ, acc, unit))
            return ("VARS|" + "|".join(parts)).encode(), ms

        if text == "READ_ALL":
            parts = ["%s:%s" % (name, v[0]) for name, v in self.vars.items()]
            return ("VALS|" + "|".join(parts)).encode(), ms

        if text.startswith("WRITE|VAR:"):
            kv = {}
            for p in text.split("|")[1:]:
                if ":" in p:
                    k, _, v = p.partition(":")
                    kv[k] = v
            name, val = kv.get("VAR"), kv.get("VAL")
            if name in self.vars:
                old = self.vars[name]
                self.vars[name] = (val, old[1], old[2], old[3])
                return ("WOK|%s:%s" % (name, val)).encode(), ms
            return None, None

        if text.startswith("PERF_TEST_"):
            self.rx_frames += 1
            return payload_bytes, ms

        if text == "START_IAP" or text.startswith("START_IAP|"):
            return b"IAP_READY", ms

        if text.startswith("FW_DATA|SEQ:"):
            try:
                seq = int(text.split("SEQ:", 1)[1].split("|", 1)[0])
            except ValueError:
                seq = 0
            return ("ACK:%d" % seq).encode(), ms

        if text == "END_IAP":
            if self.fail_crc:
                return b"IAP_ERR|CRC_MISMATCH", ms
            return b"FLASH_SUCCESS|JUMP_OK", ms

        return None, None


def install_fake_device(win, device):
    def fake_request(payload, expect_reply=True, timeout=None, ip=None):
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        return device.handle(data)
    win.proto.request = fake_request


def mark_connected(win, detail="100 Mbps Tam Duplex"):
    """Sag ustteki rozeti yesil + 'BAGLANTI VAR' olarak isaretle."""
    win._set_link_badge(True, detail)
    text = "BAGLANTI VAR"
    if detail:
        text += "  " + detail
    win.link_badge.setText(text)


def wait_workers(win, app, timeout_s=10.0):
    """win.workers listesi bosalana kadar Qt olay dongusunu pompala."""
    t0 = time.time()
    while win.workers and (time.time() - t0) < timeout_s:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


# =============================================================================
#  27 AGUSTOS 2026 - Staj 24. Gun: ilk uctan uca test (Kart G/C)
# =============================================================================

def shot_27_agustos(m, app):
    win = m.EAETISWindow()
    device = FakeDevice(seed=27)
    install_fake_device(win, device)

    win.ip_input.setText("192.168.1.87")
    win._sync_proto()

    win.log("Agda cihaz araniyor (UDP broadcast :5000)...")
    win.log("Cihaz bulundu: 192.168.1.87  (DEV=STM32H563, PHY=LAN8720A)")

    win.do_discover_vars()

    win.io_write_name.setCurrentText("led")
    win.io_write_val.setText("1")
    win.do_write_var()

    win.do_ping()               # "Baglantiyi Test Et" -> GET_PHY_DMA_STATS
    mark_connected(win, "100 Mbps Tam Duplex")

    win.tabs.setCurrentIndex(0)  # Kart G/C (Telemetri)
    win.show()
    app.processEvents(); app.processEvents()
    win.grab().save(os.path.join(HERE, "27_agustos.png"))
    win.close()


# =============================================================================
#  28 AGUSTOS 2026 - Staj 25. Gun: Performans & Jitter  +  Hata Enjeksiyonu
# =============================================================================

def shot_28_agustos_performans(m, app):
    win = m.EAETISWindow()
    device = FakeDevice(seed=28, base_latency_ms=0.42, jitter_sigma_ms=0.15)
    install_fake_device(win, device)
    win.ip_input.setText("192.168.1.87")
    win._sync_proto()

    win.bm_count.setValue(200)
    win.bm_size.setValue(64)
    win.bm_interval.setValue(5)
    win.do_benchmark()
    wait_workers(win, app)

    mark_connected(win, "100 Mbps Tam Duplex")
    win.tabs.setCurrentIndex(4)  # Performans & Jitter
    win.show()
    app.processEvents(); app.processEvents()
    win.grab().save(os.path.join(HERE, "28_agustos_performans.png"))
    win.close()


def shot_28_agustos_hata_enjeksiyonu(m, app):
    win = m.EAETISWindow()
    device = FakeDevice(seed=280)
    device.rx_drop = 14   # fuzz/oversize sirasinda dusen paketler
    install_fake_device(win, device)
    win.ip_input.setText("192.168.1.87")
    win._sync_proto()

    win.fi_oversize.setChecked(True)
    win.fi_truncated.setChecked(True)
    win.fi_random.setChecked(True)
    win.fi_count.setValue(200)
    win.do_fault_injection()
    wait_workers(win, app)

    mark_connected(win, "100 Mbps Tam Duplex")
    win.tabs.setCurrentIndex(5)  # Hata Enjeksiyonu
    win.show()
    app.processEvents(); app.processEvents()
    win.grab().save(os.path.join(HERE, "28_agustos_hata_enjeksiyonu.png"))
    win.close()


# =============================================================================
#  8 EYLUL 2026 - Staj 32. Gun: ilk basarili uctan uca IAP guncellemesi
# =============================================================================

def shot_08_eylul(m, app):
    win = m.EAETISWindow()
    device = FakeDevice(seed=8)
    device.fail_crc = False
    install_fake_device(win, device)
    win.ip_input.setText("192.168.1.87")
    win._sync_proto()

    fw_path = os.path.join(tempfile.gettempdir(), "led_blink_test.bin")
    with open(fw_path, "wb") as f:
        f.write(os.urandom(8192))
    with open(fw_path, "rb") as f:
        blob = f.read()

    win.iap_path.setText(fw_path)
    win.iap_info.setText(
        "%s\n%d bayt  |  CRC32 0x%08X  |  %d paket (512 bayt)"
        % (os.path.basename(fw_path), len(blob),
           zlib.crc32(blob) & 0xFFFFFFFF, (len(blob) + 511) // 512))

    worker = m.FirmwareUpdateWorker(win.proto, fw_path)
    worker.log.connect(win.log)
    worker.progress.connect(win.iap_progress.setValue)
    win.workers.append(worker)
    worker.finished.connect(lambda: win.workers.remove(worker)
                            if worker in win.workers else None)
    worker.start()
    wait_workers(win, app)

    mark_connected(win, "100 Mbps Tam Duplex")
    win.tabs.setCurrentIndex(6)  # Bootloader (IAP)
    win.show()
    app.processEvents(); app.processEvents()
    win.grab().save(os.path.join(HERE, "08_eylul.png"))
    win.close()


# =============================================================================
#  9 EYLUL 2026 - Staj 33. Gun: IAP hata senaryosu (CRC uyusmazligi)
# =============================================================================

def shot_09_eylul(m, app):
    win = m.EAETISWindow()
    device = FakeDevice(seed=9)
    device.fail_crc = True
    install_fake_device(win, device)
    win.ip_input.setText("192.168.1.87")
    win._sync_proto()

    fw_path = os.path.join(tempfile.gettempdir(), "test_bad_crc.bin")
    with open(fw_path, "wb") as f:
        f.write(os.urandom(4096))
    with open(fw_path, "rb") as f:
        blob = f.read()

    win.iap_path.setText(fw_path)
    win.iap_info.setText(
        "%s\n%d bayt  |  CRC32 0x%08X  |  %d paket (512 bayt)"
        % (os.path.basename(fw_path), len(blob),
           zlib.crc32(blob) & 0xFFFFFFFF, (len(blob) + 511) // 512))

    worker = m.FirmwareUpdateWorker(win.proto, fw_path)
    worker.log.connect(win.log)
    worker.progress.connect(win.iap_progress.setValue)
    win.workers.append(worker)
    worker.finished.connect(lambda: win.workers.remove(worker)
                            if worker in win.workers else None)
    worker.start()
    wait_workers(win, app)

    mark_connected(win, "100 Mbps Tam Duplex")
    win.tabs.setCurrentIndex(6)  # Bootloader (IAP)
    win.show()
    app.processEvents(); app.processEvents()
    win.grab().save(os.path.join(HERE, "09_eylul.png"))
    win.close()


def main():
    m = load_gui_module()
    app = m.QApplication(sys.argv)
    app.setStyle("Fusion")

    shot_27_agustos(m, app)
    shot_28_agustos_performans(m, app)
    shot_28_agustos_hata_enjeksiyonu(m, app)
    shot_08_eylul(m, app)
    shot_09_eylul(m, app)

    print("Tum ornek-veri ekran goruntuleri uretildi.")


if __name__ == "__main__":
    main()
