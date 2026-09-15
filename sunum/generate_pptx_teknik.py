# -*- coding: utf-8 -*-
"""
eaetis_sunum_slaytlari.html (12 slaytlik teknik deck) -> pptx donusturucu.
Orijinal HTML'in "muhendislik kagidi" temasi (yesil/bakir, IBM Plex) korunarak
PowerPoint'in native sekilleriyle yeniden olusturulur. Diyagramlar (mimari, ring,
paket akisi, IAP sequence) sadelestirilmis metin/liste olarak temsil edilir.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------- palette (eaetis_sunum_slaytlari.html --root degiskenlerinden) ----------
PAPER      = RGBColor(0xf5, 0xf6, 0xf3)
INK        = RGBColor(0x16, 0x20, 0x1c)
MUTED      = RGBColor(0x52, 0x62, 0x5a)
ACCENT     = RGBColor(0x0d, 0x6e, 0x56)
ACCENT_INK = RGBColor(0x08, 0x40, 0x2f)
ACCENT_SOFT= RGBColor(0xdc, 0xec, 0xe5)
COPPER     = RGBColor(0xa8, 0x57, 0x1a)
COPPER_SOFT= RGBColor(0xf3, 0xe3, 0xd3)
LINE       = RGBColor(0xd7, 0xde, 0xd9)
WHITE      = RGBColor(0xff, 0xff, 0xff)

FONT = "Calibri"
TOTAL = 12

SW, SH = Inches(13.333), Inches(7.5)
MX = Inches(0.6)

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]


def no_shadow(shp):
    shp.shadow.inherit = False


def add_bg(slide):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    shp.fill.solid(); shp.fill.fore_color.rgb = PAPER
    shp.line.fill.background()
    no_shadow(shp)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Pt(3))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    no_shadow(bar)


def set_run(r, text, size, color=INK, bold=False, italic=False, font=FONT, mono=False):
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    r.font.name = "Consolas" if mono else font


def rich_paragraph(p, text, size, color=INK, bold=False, italic=False, mono=False):
    parts = text.split("**")
    for i, part in enumerate(parts):
        if not part:
            continue
        r = p.add_run()
        set_run(r, part, size, color, bold=bold or (i % 2 == 1), italic=italic, mono=mono)


def add_textbox(slide, x, y, w, h, wrap=True):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    return tb, tf


def add_kicker_title(slide, kicker, title, lead=None, title_size=30):
    tb, tf = add_textbox(slide, MX, Inches(0.45), Inches(10), Inches(0.32))
    p = tf.paragraphs[0]
    r = p.add_run(); set_run(r, kicker.upper(), 11.5, ACCENT, bold=True, mono=True)

    tb, tf = add_textbox(slide, MX, Inches(0.8), Inches(11.5), Inches(1.05))
    p = tf.paragraphs[0]
    r = p.add_run(); set_run(r, title, title_size, INK, bold=True)

    y = Inches(1.65)
    if lead:
        tb, tf = add_textbox(slide, MX, y, Inches(11.5), Inches(0.6))
        p = tf.paragraphs[0]
        r = p.add_run(); set_run(r, lead, 14, MUTED)
        y = Inches(2.2)
    return y


def add_footer(slide, idx, label):
    tb, tf = add_textbox(slide, MX, SH - Inches(0.45), Inches(6), Inches(0.3))
    p = tf.paragraphs[0]
    r = p.add_run(); set_run(r, label, 9.5, MUTED, mono=True)
    tb, tf = add_textbox(slide, SW - Inches(2.0) - Inches(0.4), SH - Inches(0.45), Inches(2.0), Inches(0.3))
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
    r = p.add_run(); set_run(r, "%02d / %d" % (idx, TOTAL), 9.5, MUTED, mono=True)


def new_slide(idx, kicker, title, footer_label, lead=None, title_size=30):
    slide = prs.slides.add_slide(BLANK)
    add_bg(slide)
    y = add_kicker_title(slide, kicker, title, lead, title_size=title_size)
    add_footer(slide, idx, footer_label)
    return slide, y


def add_card(slide, x, y, w, h, eyebrow=None, title=None, bullets=None, text=None, badges=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shp.adjustments[0] = 0.035
    shp.fill.solid(); shp.fill.fore_color.rgb = WHITE
    shp.line.color.rgb = LINE; shp.line.width = Pt(1)
    no_shadow(shp)
    pad = Inches(0.26)
    cx, cy, cw = x + pad, y + pad, w - 2 * pad
    if eyebrow:
        tb, tf = add_textbox(slide, cx, cy, cw, Inches(0.24))
        p = tf.paragraphs[0]
        r = p.add_run(); set_run(r, eyebrow.upper(), 10, ACCENT, bold=True, mono=True)
        cy += Inches(0.32)
    if title:
        tb, tf = add_textbox(slide, cx, cy, cw, Inches(0.4))
        p = tf.paragraphs[0]
        r = p.add_run(); set_run(r, title, 17, INK, bold=True)
        cy += Inches(0.46)
    if text:
        tb, tf = add_textbox(slide, cx, cy, cw, y + h - pad - cy)
        p = tf.paragraphs[0]
        rich_paragraph(p, text, 13, MUTED)
    if bullets:
        tb, tf = add_textbox(slide, cx, cy, cw, y + h - pad - cy)
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(6)
            r = p.add_run(); set_run(r, "– ", 13, MUTED)
            rich_paragraph(p, b, 13, MUTED)
    if badges:
        bx, by = cx, cy
        for b in badges:
            bw = Inches(0.1 * len(b) + 0.4)
            if bx + bw > x + w - pad:
                bx = cx; by += Inches(0.38)
            bshp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, by, bw, Inches(0.32))
            bshp.adjustments[0] = 0.5
            bshp.fill.solid(); bshp.fill.fore_color.rgb = ACCENT_SOFT
            bshp.line.color.rgb = ACCENT; bshp.line.width = Pt(0.75)
            no_shadow(bshp)
            tf = bshp.text_frame
            tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); set_run(r, b, 10.5, ACCENT_INK, bold=True, mono=True)
            bx += bw + Inches(0.12)


def add_cards_row(slide, y, h, cards, gap=Inches(0.35)):
    n = len(cards)
    w0 = SW - 2 * MX
    cw = (w0 - gap * (n - 1)) / n
    x = MX
    for c in cards:
        add_card(slide, x, y, cw, h, **c)
        x += cw + gap


def add_table(slide, x, y, w, h, headers, rows, col_widths=None, font_size=13):
    n_rows = len(rows) + 1
    n_cols = len(headers)
    gshape = slide.shapes.add_table(n_rows, n_cols, x, y, w, h)
    table = gshape.table
    if col_widths:
        total = sum(col_widths)
        for i, cw in enumerate(col_widths):
            table.columns[i].width = int(w * cw / total)
    for j, htext in enumerate(headers):
        cell = table.cell(0, j)
        cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(0xea, 0xef, 0xec)
        cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.08)
        cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        r = p.add_run(); set_run(r, htext.upper(), font_size - 2, MUTED, bold=True, mono=True)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.fill.solid(); cell.fill.fore_color.rgb = WHITE
            cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            r = p.add_run()
            if isinstance(val, tuple):
                text, color = val
                set_run(r, text, font_size - 1, color, bold=(color != INK))
            else:
                set_run(r, val, font_size - 1, INK)
    return table


def add_numlist(slide, x, y, w, h, items, size=13.5):
    tb, tf = add_textbox(slide, x, y, w, h)
    for i, (title, desc) in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(9)
        r = p.add_run(); set_run(r, "%d.  " % (i + 1), size, ACCENT, bold=True, mono=True)
        r2 = p.add_run(); set_run(r2, title, size, INK, bold=bool(desc))
        if desc:
            p2 = tf.add_paragraph()
            p2.space_after = Pt(9)
            r3 = p2.add_run(); set_run(r3, "     " + desc, size - 2.5, MUTED)


def add_limits(slide, x, y, w, h, items, size=14.5):
    tb, tf = add_textbox(slide, x, y, w, h)
    for i, text in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        r = p.add_run(); set_run(r, "—  ", size, COPPER, bold=True, mono=True)
        rich_paragraph(p, text, size, INK)


def add_stat_grid(slide, x, y, w, h, stats, cols=4):
    rows = (len(stats) + cols - 1) // cols
    gap = Inches(0.18)
    cw = (w - gap * (cols - 1)) / cols
    ch = (h - gap * (rows - 1)) / rows
    for i, (num, lbl) in enumerate(stats):
        r_i, c_i = divmod(i, cols)
        sx = x + c_i * (cw + gap); sy = y + r_i * (ch + gap)
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, sx, sy, cw, ch)
        shp.adjustments[0] = 0.09
        shp.fill.solid(); shp.fill.fore_color.rgb = WHITE
        shp.line.color.rgb = LINE; shp.line.width = Pt(1)
        no_shadow(shp)
        tf = shp.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); set_run(r, str(num), 30, ACCENT, bold=True, mono=True)
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run(); set_run(r2, lbl, 10.5, MUTED)


def add_badges_row(slide, x, y, w, badges):
    bx, by = x, y
    for b in badges:
        bw = Inches(0.095 * len(b) + 0.4)
        if bx + bw > x + w:
            bx = x; by += Inches(0.4)
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, by, bw, Inches(0.34))
        shp.adjustments[0] = 0.5
        shp.fill.solid(); shp.fill.fore_color.rgb = ACCENT_SOFT
        shp.line.color.rgb = ACCENT; shp.line.width = Pt(0.75)
        no_shadow(shp)
        tf = shp.text_frame
        tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); set_run(r, b, 10.5, ACCENT_INK, bold=True, mono=True)
        bx += bw + Inches(0.14)


def add_caption(slide, x, y, w, text):
    tb, tf = add_textbox(slide, x, y, w, Inches(0.5))
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    rich_paragraph(p, text, 12, MUTED, italic=True)


def add_picture_framed(slide, path, x, y, w, h):
    if os.path.exists(path):
        pic = slide.shapes.add_picture(path, x, y, height=h)
        if pic.width > w:
            slide.shapes._spTree.remove(pic._element)
            pic = slide.shapes.add_picture(path, x, y, width=w)
        pic.line.color.rgb = LINE; pic.line.width = Pt(1)
        pic.left = int(x + (w - pic.width) / 2)
    else:
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
        shp.fill.solid(); shp.fill.fore_color.rgb = WHITE
        shp.line.color.rgb = LINE
        tf = shp.text_frame
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); set_run(r, "[ekran görüntüsü bulunamadı]", 10, MUTED)


def flow_line(tf, first, lvl, text, size=14):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(9)
    r = p.add_run()
    set_run(r, "     " * lvl + ("└─ " if lvl else ""), size, MUTED, mono=True)
    rich_paragraph(p, text, size, INK)


# ============================================================
# 1/12 — KAPAK
# ============================================================
slide = prs.slides.add_slide(BLANK)
add_bg(slide)
tb, tf = add_textbox(slide, Inches(1.1), Inches(1.7), Inches(10), Inches(0.3))
p = tf.paragraphs[0]; r = p.add_run(); set_run(r, "STAJ SUNUMU", 12, ACCENT, bold=True, mono=True)

tb, tf = add_textbox(slide, Inches(1.1), Inches(2.05), Inches(10), Inches(1.3))
p = tf.paragraphs[0]; r = p.add_run(); set_run(r, "E-AETIS", 62, INK, bold=True)

tb, tf = add_textbox(slide, Inches(1.1), Inches(3.15), Inches(10.5), Inches(0.6))
p = tf.paragraphs[0]
r = p.add_run(); set_run(r, "Ethernet_BSP — bare-metal STM32 Ethernet BSP'si ve ağ üzerinden test/teşhis arayüzü", 17, MUTED)

add_badges_row(slide, Inches(1.1), Inches(3.9), Inches(10), ["STM32 H5 / H7 / F4 / F7", "RTOS yok · LwIP yok", "10 dakika"])

# basit 3 dugumlu sema: MCU - PHY - GUI
cy = Inches(5.3)
nodes = [("MCU", ACCENT_SOFT, ACCENT), ("PHY", WHITE, LINE), ("GUI", ACCENT_SOFT, ACCENT)]
labels = [None, "RMII", "UDP"]
r_ = Inches(0.5)
xs = [Inches(1.5), Inches(4.0), Inches(6.5)]
for i in range(len(xs) - 1):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, xs[i] + r_ * 2, cy + r_, xs[i + 1], cy + r_)
    conn.line.color.rgb = MUTED; conn.line.width = Pt(1.25)
for i, (name, fillc, linec) in enumerate(nodes):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, xs[i], cy, r_ * 2, r_ * 2)
    shp.fill.solid(); shp.fill.fore_color.rgb = fillc
    shp.line.color.rgb = linec; shp.line.width = Pt(1.5)
    no_shadow(shp)
    tf = shp.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); set_run(r, name, 13, INK, bold=True)
add_footer(slide, 1, "E-AETIS / Ethernet_BSP")

# ============================================================
# 2/12 — GENEL BAKIŞ
# ============================================================
slide, y = new_slide(2, "01 · Genel Bakış", "Bir Ethernet BSP + bir test arayüzü", "Genel Bakış",
                      "RTOS ve hazır ağ yığını olmadan çalışan gömülü bir Ethernet sürücüsü, karşısında UDP üzerinden konuşan bir masaüstü teşhis arayüzü.")
add_cards_row(slide, y + Inches(0.15), Inches(3.7), [
    dict(eyebrow="Gömülü taraf", title="Ethernet_BSP  (C)", bullets=[
        "Register seviyesi **MAC / DMA / PHY** erişimi",
        "**RTOS yok** · **LwIP yok**",
        "ARP / ICMP / UDP **elle yazılmış**",
        "İsteğe bağlı **IAP** bootloader",
    ]),
    dict(eyebrow="Masaüstü taraf", title="E-AETIS GUI  (Python/PyQt5)", bullets=[
        "**UDP** üzerinden kartla konuşur",
        "Telemetri, performans/jitter ölçümü",
        "**Hata enjeksiyonu** (fuzz testi)",
        "Ağdan **firmware güncelleme**",
    ]),
])

# ============================================================
# 3/12 — TASARIM FELSEFESİ
# ============================================================
slide, y = new_slide(3, "02 · Tasarım Felsefesi", "HAL_ETH, LwIP, FreeRTOS — bilinçli olarak yok", "Tasarım Felsefesi")
add_table(slide, MX, y + Inches(0.15), SW - 2 * MX, Inches(3.3),
          ["", "Bu proje", "Hazır yığın (HAL + LwIP + FreeRTOS)"],
          [
              ["Şeffaflık", ("Her register erişimi görünür", ACCENT_INK), ("Üç kütüphanenin içine inmeden bilinmez", COPPER)],
              ["Bellek", ("Statik, malloc yok", ACCENT_INK), ("Dinamik pbuf havuzu", COPPER)],
              ["Zamanlama", ("Tek bağlam, deterministik", ACCENT_INK), ("Context-switch jitter'ı", COPPER)],
              ["Taşınabilirlik", ("Tek config, 4 MCU × 3 PHY", ACCENT_INK), ("HAL ailelerde farklı API", COPPER)],
              ["Kapsam", ("Yalnızca ARP/ICMP/UDP", COPPER), ("TCP/DHCP/DNS hazır gelir", ACCENT_INK)],
          ], col_widths=[18, 41, 41])
add_caption(slide, MX, y + Inches(3.6), SW - 2 * MX,
            "Üretim ürünü olsaydı LwIP + FreeRTOS muhtemelen daha pragmatik olurdu — burada hedef ürünü "
            "hızlıca çıkarmak değil, MAC/PHY/DMA seviyesinde ne olduğunu göstermekti.")

# ============================================================
# 4/12 — TAŞINABİLİRLİK
# ============================================================
slide, y = new_slide(4, "03 · Taşınabilirlik", "Tek config dosyası, dört MCU", "Taşınabilirlik")
add_table(slide, MX, y + Inches(0.15), SW - 2 * MX, Inches(2.4),
          ["MCU", "Çekirdek", "MAC ailesi", "Port dosyası"],
          [
              ["STM32H563", "Cortex-M33", "Synopsys EQOS", "eth_port_eqos.c"],
              ["STM32H743", "Cortex-M7", "Synopsys EQOS", "eth_port_eqos.c"],
              ["STM32F407", "Cortex-M4", "Klasik GMAC", "eth_port_gmac.c"],
              ["STM32F767", "Cortex-M7", "Klasik GMAC", "eth_port_gmac.c"],
          ], col_widths=[25, 25, 28, 30])
add_badges_row(slide, MX, y + Inches(2.75), SW - 2 * MX, ["PHY: LAN8720A", "PHY: LAN8742A", "PHY: KSZ8081"])
add_caption(slide, MX, y + Inches(3.35), SW - 2 * MX,
            "Yeni bir MCU eklemek = **eth_device.h** içine birkaç satır. Port ve PHY dosyalarına **hiç dokunulmaz.**")

# ============================================================
# 5/12 — MİMARİ
# ============================================================
slide, y = new_slide(5, "04 · Mimari", "Üç bağımsız eksen", "Mimari")
tf = add_textbox(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(4.0))[1]
add_numlist(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(4.0), [
    ("eth_config.h — tek giriş noktası", "Hangi MCU/PHY seçili olduğu burada belirlenir"),
    ("eth_device.h — MCU → yetenek eşlemesi", "MAC seçimi ve PHY seçimini iki ayrı eksene dallandırır"),
    ("MAC Port Ekseni", "eth_port_eqos.c (H5/H7) veya eth_port_gmac.c (F4/F7) → sabit sözleşme: eth_port.h"),
    ("PHY Ekseni", "eth_phy_lan87xx.c (LAN8720A/8742A) veya eth_phy_ksz80xx.c (KSZ8081) → sabit sözleşme: eth_phy.h"),
    ("Çekirdek — donanımdan tamamen bağımsız", "eth_driver.c (ring + sahiplik) → eth_app.c (ARP/ICMP/UDP) → eth_iap.c (opsiyonel)"),
])
add_caption(slide, MX, y + Inches(4.1), SW - 2 * MX,
            "Kesikli ok = derleme zamanı seçimi · düz ok = kullanır (çalışma zamanı) · vurgulu = bu kartın "
            "örnek seçimi (H563 + EQOS + LAN8742A)")

# ============================================================
# 6/12 — ÇEKİRDEK SÜRÜCÜ
# ============================================================
slide, y = new_slide(6, "05 · Çekirdek Sürücü", "Paylaşılan halka, net kurallar", "Çekirdek Sürücü",
                      "8 elemanlı RX descriptor halkası (ring) — her eleman ya DMA'nın ya CPU'nun sahipliğindedir.")
add_cards_row(slide, y + Inches(0.2), Inches(3.5), [
    dict(title="01  Zero-copy", text="DMA'nın tamponuna doğrudan yazılır — aradan **memcpy** geçmez."),
    dict(title="02  OWN biti", text="CPU ve DMA aynı descriptor dizisini tek bir sahiplik bitiyle paylaşır — kesme olmadan bile veri yarışı oluşmaz."),
    dict(title="03  MPU + non-cacheable", text="DMA'nın yazdığı veriyi CPU cache'ten değil, doğrudan bellekten okur."),
])

# ============================================================
# 7/12 — PAKET İŞLEME AKIŞI
# ============================================================
slide, y = new_slide(7, "06 · Uygulama Katmanı", "Paket işleme akışı", "Paket İşleme Akışı")
tb, tf = add_textbox(slide, MX, y + Inches(0.15), SW - 2 * MX, Inches(4.5))
lines = [
    (0, "Gelen çerçeve (zero-copy, DMA) → **EtherType?**"),
    (1, "ARP  →  arp_handle  (cache güncelle + yanıt)"),
    (1, "IPv4  →  **IP proto?**"),
    (2, "parçalanmış (MF=1 / offset≠0)  →  sessizce düşür — reassembly yok, **bilinçli kısıt**"),
    (2, "ICMP echo  →  icmp_handle  (yanıt hesapla)"),
    (2, "UDP  →  **hedef port?**"),
    (3, "5000  →  eaetis_handle  (komut dağıtımı)"),
    (3, "diğer  →  kullanıcı callback  (RegisterUDPCallback)"),
]
for i, (lvl, text) in enumerate(lines):
    flow_line(tf, i == 0, lvl, text, size=14)

# ============================================================
# 8/12 — IAP BOOTLOADER
# ============================================================
slide, y = new_slide(8, "07 · IAP Bootloader", "Ağ üzerinden firmware güncelleme", "IAP Bootloader")
add_numlist(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(3.9), [
    ("GUI → Kart: START_IAP | SIZE:n | CRC:0x..", None),
    ("Kart → GUI: IAP_READY", None),
    ("Döngü (512B parça, en fazla 3 deneme): FW_DATA | SEQ:i  →  ACK:i", None),
    ("GUI → Kart: END_IAP", None),
    ("Kart: CRC32 doğrula → VTOR taşı → MSP ayarla → yeni uygulamaya atla", None),
    ("Kart → GUI: FLASH_SUCCESS | JUMP_OK", None),
])
add_caption(slide, MX, y + Inches(4.0), SW - 2 * MX,
            "Tek banka, kimlik doğrulama yok — yalnızca CRC32 bütünlük kontrolü. Sadece izole/güvenilir ağlarda kullanılmalı.")

# ============================================================
# 9/12 — MASAÜSTÜ ARAYÜZ (GUI)
# ============================================================
slide, y = new_slide(9, "08 · Masaüstü Arayüz", "E-AETIS GUI", "Masaüstü Arayüz")
add_picture_framed(slide, os.path.join(ROOT, "Docs", "gui.png"), MX, y + Inches(0.1), Inches(6.7), Inches(4.4))
add_table(slide, MX + Inches(7.0), y + Inches(0.1), SW - MX - (MX + Inches(7.0)), Inches(4.0),
          ["Sekme", "İşlev"],
          [
              ["Kart G/Ç", "Otomatik değişken keşfi"],
              ["Ping (ICMP)", "Gecikme ölçümü"],
              ["UDP Konsol", "Serbest komut / log"],
              ["PHY / DMA Teşhis", "Register + istatistik"],
              ["Performans & Jitter", "min / ort / p95 / max"],
              ["Hata Enjeksiyonu", "Fuzz + parçalanma testi"],
              ["Bootloader (IAP)", "Ağdan firmware güncelleme"],
          ], col_widths=[45, 55], font_size=12)

# ============================================================
# 10/12 — DOĞRULAMA
# ============================================================
slide, y = new_slide(10, "09 · Doğrulama", "Bring-up sırası ve fuzz testi", "Doğrulama")
add_numlist(slide, MX, y + Inches(0.1), Inches(5.9), Inches(3.6), [
    ("MDIO alan yerleşimi (MACMDIOAR)", None),
    ("RMII seçim register kodu", None),
    ("DMA tail pointer semantiği", None),
    ("MPU RBAR / RLAR alanları", None),
    ("Flash sektör alanı (IAP kullanılıyorsa)", None),
    ("RMII pin haritası (kart şemasından)", None),
])
add_caption(slide, MX, y + Inches(3.75), Inches(5.9),
            "PHY ID okunabiliyorsa (**ETH_PHY_ScanAddress**) → RMII saati, GPIO, clock, SMI zamanlaması hepsi doğru demektir.")
tx = MX + Inches(6.2)
add_table(slide, tx, y + Inches(0.1), SW - MX - tx, Inches(2.0),
          ["Senaryo", "Beklenen davranış"],
          [
              ["2048B parçalanmış paket", "Sessizce düşür, timeout"],
              ["Kesik / tutarsız IAP başlığı", "Parser sınır kontrolü reddeder"],
              ["Rastgele fuzz baytları", "Kart hayatta kalır (canlılık)"],
          ], col_widths=[50, 50], font_size=12.5)

# ============================================================
# 11/12 — BİLİNEN SINIRLAR
# ============================================================
slide, y = new_slide(11, "10 · Dürüst Değerlendirme", "Bilinen sınırlar", "Bilinen Sınırlar")
add_limits(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(3), [
    "**IP fragment reassembly yok** — tasarım kararı, büyük paketler sessizce düşürülür",
    "**TCP yok** — yalnızca UDP / ICMP / ARP",
    "**Tek DMA kanalı, tek kuyruk** — QoS / VLAN önceliklendirme yok",
    "**IAP'de kimlik doğrulama yok** — yalnızca CRC32 bütünlük kontrolü",
    "**Polling tabanlı** — kesme desteği yok, gecikme çağrı sıklığına bağımlı",
])
add_caption(slide, MX, y + Inches(3.3), SW - 2 * MX, "Kapsamı bilinçli çizdik — jüri sormadan biz söylüyoruz.")

# ============================================================
# 12/12 — KAPANIŞ
# ============================================================
slide, y = new_slide(12, "11 · Kapanış", "Rakamlarla proje", "E-AETIS / Ethernet_BSP")
add_stat_grid(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(2.7), [
    (4, "desteklenen MCU"), (2, "MAC ailesi"), (3, "PHY çipi"), (0, "malloc çağrısı"),
    (3, "protokol (ARP/ICMP/UDP)"), (21, "port sözleşmesi fonksiyonu"), (7, "GUI test sekmesi"), (1, "dokunulan config dosyası"),
], cols=4)
tb, tf = add_textbox(slide, MX, y + Inches(3.2), SW - 2 * MX, Inches(1.2))
p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
r = p.add_run(); set_run(r, "Teşekkürler", 34, INK, bold=True)
p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
r2 = p2.add_run(); set_run(r2, "Sorular?", 15, MUTED)

out_path = os.path.join(HERE, "EAETIS_Teknik_Sunum.pptx")
prs.save(out_path)
print("OK:", out_path)
