# -*- coding: utf-8 -*-
"""
E-AETIS staj kapanış sunumu - taslak/fikir pptx üretici.
Kapak tasarımı (sunum_kapak.png) referans alınarak tüm slaytlar için
tutarlı bir arka plan/renk/tipografi sistemi kurar.
Bu bir TASLAKTIR - kullanıcı gerçek sunumu PowerPoint'te elle üretecek.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------- palette (kapak görselinden örneklendi) ----------
NAVY   = RGBColor(0x00, 0x46, 0x94)   # ana marka mavisi (kapak yazıları + kama)
INK    = RGBColor(0x10, 0x18, 0x26)   # başlık metni
MUTED  = RGBColor(0x5b, 0x6b, 0x80)   # ikincil metin
LINEG  = RGBColor(0x9a, 0x9a, 0x9a)   # ince dekoratif çizgiler
CARDBG = RGBColor(0xf6, 0xf8, 0xfb)
CARDLN = RGBColor(0xdb, 0xe1, 0xea)
CYAN   = RGBColor(0x0e, 0x93, 0xb4)
GREEN  = RGBColor(0x17, 0x93, 0x6b)
AMBER  = RGBColor(0xb6, 0x72, 0x0f)
WHITE  = RGBColor(0xff, 0xff, 0xff)

FONT = "Calibri"

SW, SH = Inches(13.333), Inches(7.5)
MX = Inches(0.55)  # sol/sağ kenar boşluğu

TOTAL = 18

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]

ICON = os.path.join(HERE, "assets", "ehsim_icon.png")
COVER_PNG = os.path.join(HERE, "sunum_kapak.png")

CONTENT_WEDGE = [(1.0, 0.86), (0.85, 0.90), (0.90, 0.955), (0.78, 0.975), (0.78, 1.0), (1.0, 1.0)]
CONTENT_LINE = [(0.50, 0.0), (0.43, 0.055), (0.58, 0.15), (0.74, 0.30)]

BIG_WEDGE = [(1.0, 0.646), (0.599, 0.731), (0.527, 0.940), (0.0, 0.994), (0.0, 1.0), (1.0, 1.0)]
BIG_LINE1 = [(0.72, 0.0), (0.62, 0.065), (0.815, 0.21), (0.97, 0.46)]
BIG_LINE2 = [(0.0, 0.62), (0.21, 0.64), (0.30, 0.81), (0.575, 0.84), (0.85, 0.99)]


def fx(x):
    return int(x * SW)


def fy(y):
    return int(y * SH)


def no_shadow(shp):
    shp.shadow.inherit = False


def add_bg_rect(slide, color=WHITE):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    no_shadow(shp)
    return shp


def add_wedge(slide, points_frac, color=NAVY):
    pts = [(fx(x), fy(y)) for x, y in points_frac]
    fb = slide.shapes.build_freeform(pts[0][0], pts[0][1])
    fb.add_line_segments(pts[1:], close=True)
    shp = fb.convert_to_shape()
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    no_shadow(shp)
    return shp


def add_gray_line(slide, points_frac, width_pt=0.75):
    pts = [(fx(x), fy(y)) for x, y in points_frac]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
        conn.line.color.rgb = LINEG
        conn.line.width = Pt(width_pt)


def add_ring(slide, cx_f, cy_f, r_f):
    cx, cy = fx(cx_f), fy(cy_f)
    r = fx(r_f)
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, cx - r, cy - r, r * 2, r * 2)
    shp.fill.background()
    shp.line.color.rgb = LINEG
    shp.line.width = Pt(1)
    no_shadow(shp)
    return shp


def set_run(r, text, size, color=INK, bold=False, italic=False, font=FONT, mono=False):
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    r.font.name = "Consolas" if mono else font


def rich_paragraph(p, text, size, color=INK, bold=False, italic=False, font=FONT, mono=False):
    """text içinde **kalın** işaretli parçaları kalın yazar."""
    parts = text.split("**")
    for i, part in enumerate(parts):
        if not part:
            continue
        r = p.add_run()
        set_run(r, part, size, color, bold=bold or (i % 2 == 1), italic=italic, font=font, mono=mono)


def add_textbox(slide, x, y, w, h, anchor=None, wrap=True):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    if anchor:
        tf.vertical_anchor = anchor
    return tb, tf


def add_logo(slide, small=True):
    w = Inches(0.40) if small else Inches(0.62)
    x = SW - w - Inches(0.42)
    y = Inches(0.24)
    slide.shapes.add_picture(ICON, x, y, width=w)
    tb, tf = add_textbox(slide, x - Inches(0.25), y + w + Inches(0.03), w + Inches(0.5), Inches(0.3))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    set_run(r, "EHSİM", 9.5 if small else 12, NAVY, bold=True)


def add_kicker_title(slide, kicker, title, lead=None, title_size=27):
    tb, tf = add_textbox(slide, MX, Inches(0.38), Inches(9.6), Inches(0.32))
    p = tf.paragraphs[0]
    r = p.add_run()
    set_run(r, kicker.upper(), 11, CYAN, bold=True, mono=True)

    tb, tf = add_textbox(slide, MX, Inches(0.72), Inches(10.8), Inches(1.05))
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    set_run(r, title, title_size, INK, bold=True)

    y = Inches(1.55)
    if lead:
        tb, tf = add_textbox(slide, MX, y, Inches(11.2), Inches(0.6))
        tf.word_wrap = True
        p = tf.paragraphs[0]
        r = p.add_run()
        set_run(r, lead, 13.5, MUTED, italic=False)
        y = Inches(2.15)
    return y


def add_footer(slide, idx):
    tb, tf = add_textbox(slide, MX, SH - Inches(0.45), Inches(6), Inches(0.3))
    p = tf.paragraphs[0]
    r = p.add_run()
    set_run(r, "E-AETIS · Staj Sunumu", 9, MUTED)

    tb, tf = add_textbox(slide, SW - Inches(2.0) - Inches(0.35), SH - Inches(0.45), Inches(2.0), Inches(0.3))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run()
    set_run(r, "%02d / %d" % (idx, TOTAL), 9, MUTED)


def new_content_slide(idx, kicker, title, lead=None, title_size=27):
    slide = prs.slides.add_slide(BLANK)
    add_bg_rect(slide, WHITE)
    add_wedge(slide, CONTENT_WEDGE, NAVY)
    add_gray_line(slide, CONTENT_LINE)
    add_logo(slide, small=True)
    body_y = add_kicker_title(slide, kicker, title, lead, title_size=title_size)
    add_footer(slide, idx)
    return slide, body_y


# ---------- içerik blokları ----------

def add_card(slide, x, y, w, h, eyebrow=None, title=None, bullets=None, badges=None, text=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shp.adjustments[0] = 0.045
    shp.fill.solid()
    shp.fill.fore_color.rgb = CARDBG
    shp.line.color.rgb = CARDLN
    shp.line.width = Pt(1)
    no_shadow(shp)

    pad = Inches(0.22)
    cx, cy, cw = x + pad, y + pad, w - 2 * pad
    if eyebrow:
        tb, tf = add_textbox(slide, cx, cy, cw, Inches(0.24))
        p = tf.paragraphs[0]
        r = p.add_run()
        set_run(r, eyebrow.upper(), 9.5, CYAN, bold=True, mono=True)
        cy += Inches(0.30)
    if title:
        tb, tf = add_textbox(slide, cx, cy, cw, Inches(0.35))
        tf.word_wrap = True
        p = tf.paragraphs[0]
        r = p.add_run()
        set_run(r, title, 15, INK, bold=True)
        cy += Inches(0.42)
    if text:
        tb, tf = add_textbox(slide, cx, cy, cw, y + h - pad - cy)
        tf.word_wrap = True
        p = tf.paragraphs[0]
        rich_paragraph(p, text, 12.5, MUTED)
    if bullets:
        tb, tf = add_textbox(slide, cx, cy, cw, y + h - pad - cy)
        tf.word_wrap = True
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(5)
            r = p.add_run()
            set_run(r, "– ", 12.5, MUTED)
            rich_paragraph(p, b, 12.5, MUTED)
    if badges:
        bx = cx
        by = cy
        for b in badges:
            bw = Inches(0.13 * len(b) + 0.35)
            if bx + bw > x + w - pad:
                bx = cx
                by += Inches(0.36)
            bshp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, by, bw, Inches(0.3))
            bshp.adjustments[0] = 0.5
            bshp.fill.solid()
            bshp.fill.fore_color.rgb = RGBColor(0xe7, 0xec, 0xf5)
            bshp.line.color.rgb = NAVY
            bshp.line.width = Pt(0.75)
            no_shadow(bshp)
            tf = bshp.text_frame
            tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            set_run(r, b, 10, NAVY, bold=True, mono=True)
            bx += bw + Inches(0.12)


def add_cards_row(slide, y, h, cards, x0=None, w0=None, gap=Inches(0.3)):
    x0 = x0 if x0 is not None else MX
    w0 = w0 if w0 is not None else (SW - 2 * MX)
    n = len(cards)
    cw = (w0 - gap * (n - 1)) / n
    x = x0
    for c in cards:
        add_card(slide, x, y, cw, h, **c)
        x += cw + gap


def add_table(slide, x, y, w, h, headers, rows, col_widths=None, font_size=12):
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
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(0xe7, 0xec, 0xf5)
        cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.08)
        cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = cell.text_frame
        p = tf.paragraphs[0]
        r = p.add_run()
        set_run(r, htext.upper(), font_size - 2, MUTED, bold=True, mono=True)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE
            cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            p = tf.paragraphs[0]
            r = p.add_run()
            if isinstance(val, tuple):
                text, color = val
                set_run(r, text, font_size - 1, color, bold=(color != INK))
            else:
                set_run(r, val, font_size - 1, INK)
    # kenarlıkları ince gri yap (varsayılan tema kenarlıklarını basitleştir)
    return table


def add_numlist(slide, x, y, w, h, items, size=13):
    tb, tf = add_textbox(slide, x, y, w, h)
    tf.word_wrap = True
    for i, (title, desc) in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(9)
        r = p.add_run()
        set_run(r, "%d.  " % (i + 1), size, NAVY, bold=True, mono=True)
        r2 = p.add_run()
        set_run(r2, title, size, INK, bold=True)
        if desc:
            p2 = tf.add_paragraph()
            p2.space_after = Pt(9)
            r3 = p2.add_run()
            set_run(r3, "     " + desc, size - 2, MUTED)


def add_limits(slide, x, y, w, h, items, size=13.5):
    tb, tf = add_textbox(slide, x, y, w, h)
    tf.word_wrap = True
    for i, text in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        r = p.add_run()
        set_run(r, "—  ", size, AMBER, bold=True, mono=True)
        rich_paragraph(p, text, size, INK)


def add_quote(slide, x, y, w, h, quote, who):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shp.adjustments[0] = 0.06
    shp.fill.solid()
    shp.fill.fore_color.rgb = RGBColor(0x10, 0x23, 0x3f)
    shp.line.fill.background()
    no_shadow(shp)
    pad = Inches(0.35)
    tb, tf = add_textbox(slide, x + pad, y + pad, w - 2 * pad, h - 2 * pad)
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    set_run(r, quote, 15, WHITE, bold=True)
    p2 = tf.add_paragraph()
    p2.space_before = Pt(14)
    r2 = p2.add_run()
    set_run(r2, who, 11, RGBColor(0xb9, 0xc6, 0xde), bold=True, mono=True)


def add_stat_grid(slide, x, y, w, h, stats, cols=4):
    rows = (len(stats) + cols - 1) // cols
    gap = Inches(0.16)
    cw = (w - gap * (cols - 1)) / cols
    ch = (h - gap * (rows - 1)) / rows
    for i, (num, lbl) in enumerate(stats):
        r_i, c_i = divmod(i, cols)
        sx = x + c_i * (cw + gap)
        sy = y + r_i * (ch + gap)
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, sx, sy, cw, ch)
        shp.adjustments[0] = 0.08
        shp.fill.solid()
        shp.fill.fore_color.rgb = CARDBG
        shp.line.color.rgb = CARDLN
        shp.line.width = Pt(1)
        no_shadow(shp)
        tf = shp.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        set_run(r, str(num), 26, NAVY, bold=True)
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        set_run(r2, lbl, 10, MUTED)


def add_tags(slide, x, y, w, tags):
    bx, by = x, y
    for t in tags:
        bw = Inches(0.09 * len(t) + 0.4)
        if bx + bw > x + w:
            bx = x
            by += Inches(0.42)
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, by, bw, Inches(0.34))
        shp.adjustments[0] = 0.5
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor(0xdf, 0xf2, 0xea)
        shp.line.color.rgb = GREEN
        shp.line.width = Pt(0.75)
        no_shadow(shp)
        tf = shp.text_frame
        tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        set_run(r, t, 10.5, GREEN, bold=True, mono=True)
        bx += bw + Inches(0.14)


def add_picture_framed(slide, path, x, y, w, h, caption=None):
    if os.path.exists(path):
        pic = slide.shapes.add_picture(path, x, y, height=h)
        if pic.width > w:
            slide.shapes._spTree.remove(pic._element)
            pic = slide.shapes.add_picture(path, x, y, width=w)
        pic.line.color.rgb = CARDLN
        pic.line.width = Pt(1)
        pw, ph = pic.width, pic.height
        pic.left = int(x + (w - pw) / 2)
    else:
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
        shp.fill.solid(); shp.fill.fore_color.rgb = CARDBG
        shp.line.color.rgb = CARDLN
        tf = shp.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); set_run(r, "[ekran görüntüsü bulunamadı: %s]" % os.path.basename(path), 10, MUTED)
        ph = h
    if caption:
        tb, tf = add_textbox(slide, x, y + h + Inches(0.06), w, Inches(0.35))
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        set_run(r, caption, 10.5, MUTED, italic=True)


def add_arrow_flow(slide, x, y, w, h, boxes):
    n = len(boxes)
    gap = Inches(0.35)
    bw = (w - gap * (n - 1)) / n
    for i, (title, sub) in enumerate(boxes):
        bx = x + i * (bw + gap)
        accent = (i == 1)
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, y, bw, h)
        shp.adjustments[0] = 0.08
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor(0xdf, 0xf1, 0xf5) if accent else (RGBColor(0x10, 0x23, 0x3f) if i == 0 else CARDBG)
        shp.line.color.rgb = CYAN if accent else CARDLN
        shp.line.width = Pt(1.5 if accent else 1)
        no_shadow(shp)
        tf = shp.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.12); tf.margin_right = Inches(0.12)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        set_run(r, title, 13.5, WHITE if i == 0 else INK, bold=True)
        if sub:
            p2 = tf.add_paragraph()
            p2.alignment = PP_ALIGN.CENTER
            r2 = p2.add_run()
            set_run(r2, sub, 9.5, RGBColor(0xb9, 0xc6, 0xde) if i == 0 else MUTED)
        if i < n - 1:
            ax = bx + bw + Inches(0.03)
            ay = y + h / 2 - Inches(0.09)
            arr = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, ax, ay, gap - Inches(0.06), Inches(0.18))
            arr.fill.solid(); arr.fill.fore_color.rgb = MUTED
            arr.line.fill.background()
            no_shadow(arr)


def add_caption(slide, x, y, w, text):
    tb, tf = add_textbox(slide, x, y, w, Inches(0.5))
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    rich_paragraph(p, text, 11.5, MUTED, italic=True)


# ============================================================
# 1/18 — KAPAK  (kullanıcının onayladığı gerçek görsel, birebir)
# ============================================================
slide = prs.slides.add_slide(BLANK)
if os.path.exists(COVER_PNG):
    slide.shapes.add_picture(COVER_PNG, 0, 0, width=SW, height=SH)
else:
    add_bg_rect(slide, WHITE)
    add_wedge(slide, BIG_WEDGE, NAVY)

# ============================================================
# 2/18 — PROBLEM
# ============================================================
slide, y = new_content_slide(
    2, "01 · Problem",
    'Her elektronik cihazın bir "ağ dili" konuşması gerekir',
    "Bir kart ağa bağlanacaksa, veriyi doğru biçimde gönderip almasını sağlayan bir yazılım "
    "katmanına ihtiyacı vardır — buna **Ethernet sürücüsü** denir.")
add_arrow_flow(slide, MX, y + Inches(0.5), SW - 2 * MX, Inches(1.7), [
    ("Mikrodenetleyici", "sensör · motor · kamera…"),
    ("Ethernet Sürücüsü", "\"veriyi ağın anlayacağı pakete çeviren katman\""),
    ("Ağ / İnternet", None),
])
add_caption(slide, MX, y + Inches(2.5), SW - 2 * MX,
            "Hazır çözümler (işletim sistemi + ağ kütüphanesi) genelde ağırdır ve her karta doğrudan "
            "taşınmaz. Görevim: hafif, taşınabilir bir sürücüyü **sıfırdan** yazmak.")

# ============================================================
# 3/18 — NE YAPTIM
# ============================================================
slide, y = new_content_slide(
    3, "02 · Ne Yaptım", "İki parçadan oluşan bir sistem geliştirdim",
    "Kartın içine gömülen bir kütüphane ve bilgisayardan o kartı test eden bir arayüz — ikisi aynı "
    '"dil" (E-AETIS protokolü) ile konuşuyor.')
add_cards_row(slide, y + Inches(0.15), Inches(3.6), [
    dict(eyebrow="Gömülü taraf", title="Ethernet_BSP  (C)", bullets=[
        "Register seviyesi **MAC / DMA / PHY** erişimi",
        "**RTOS yok** · **LwIP yok**",
        "ARP / ICMP / UDP **elle yazılmış**",
        "İsteğe bağlı **IAP** bootloader",
    ]),
    dict(eyebrow="Masaüstü taraf", title="E-AETIS GUI  (Python / PyQt5)", bullets=[
        "**UDP** üzerinden kartla konuşur",
        "Telemetri, performans/jitter ölçümü",
        "**Hata enjeksiyonu** (fuzz testi)",
        "Ağdan **firmware güncelleme**",
    ]),
])

# ============================================================
# 4/18 — TASARIM FELSEFESİ
# ============================================================
slide, y = new_content_slide(
    4, "03 · Tasarım Felsefesi", "HAL_ETH, LwIP, FreeRTOS — bilinçli olarak yok",
    "Amaç ürünü hızlıca çıkarmak değildi; MAC / PHY / DMA seviyesinde ne olup bittiğini görebileceğim, "
    "öngörülebilir bir sistem kurmaktı.")
add_table(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(3.4),
          ["", "Bu proje", "Hazır yığın (HAL + LwIP + FreeRTOS)"],
          [
              ["Şeffaflık", ("Her register erişimi görünür", GREEN), ("Üç kütüphanenin içine inmeden bilinmez", AMBER)],
              ["Bellek", ("Statik, malloc yok", GREEN), ("Dinamik pbuf havuzu", AMBER)],
              ["Zamanlama", ("Tek bağlam, deterministik", GREEN), ("Context-switch jitter'ı", AMBER)],
              ["Taşınabilirlik", ("Tek config, 4 MCU × 3 PHY", GREEN), ("HAL ailelerde farklı API", AMBER)],
              ["Kapsam", ("Yalnızca ARP/ICMP/UDP", AMBER), ("TCP/DHCP/DNS hazır gelir", GREEN)],
          ], col_widths=[18, 41, 41])

# ============================================================
# 5/18 — MİMARİ
# ============================================================
slide, y = new_content_slide(
    5, "04 · Mimari", "Üç bağımsız eksen",
    "Bir eksende yapılan değişiklik diğerlerini etkilemez — bu, yeni bir karta geçişi tek dosyalık "
    "bir işe indirir.", title_size=27)
add_numlist(slide, MX, y + Inches(0.05), SW - 2 * MX, Inches(4.3), [
    ("eth_config.h — tek giriş noktası", "Hangi MCU/PHY seçili olduğu burada belirlenir"),
    ("eth_device.h — MCU → yetenek eşlemesi", "MAC seçimi ve PHY seçimini iki ayrı eksene dallandırır"),
    ("MAC Port Ekseni", "eth_port_eqos.c (H5/H7) veya eth_port_gmac.c (F4/F7) → sabit sözleşme: eth_port.h"),
    ("PHY Ekseni", "eth_phy_lan87xx.c (LAN8720A/8742A) veya eth_phy_ksz80xx.c (KSZ8081) → sabit sözleşme: eth_phy.h"),
    ("Çekirdek — donanımdan tamamen bağımsız", "eth_driver.c (ring + sahiplik) → eth_app.c (ARP/ICMP/UDP) → eth_iap.c (opsiyonel)"),
])

# ============================================================
# 6/18 — TAŞINABİLİRLİK
# ============================================================
slide, y = new_content_slide(6, "05 · Taşınabilirlik", "Tek config dosyası, dört farklı işlemci")
add_table(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(2.4),
          ["MCU", "Çekirdek", "MAC ailesi", "Port dosyası"],
          [
              ["STM32H563", "Cortex-M33", "Synopsys EQOS", "eth_port_eqos.c"],
              ["STM32H743", "Cortex-M7", "Synopsys EQOS", "eth_port_eqos.c"],
              ["STM32F407", "Cortex-M4", "Klasik GMAC", "eth_port_gmac.c"],
              ["STM32F767", "Cortex-M7", "Klasik GMAC", "eth_port_gmac.c"],
          ], col_widths=[25, 25, 28, 30])
add_tags(slide, MX, y + Inches(2.75), SW - 2 * MX, ["PHY: LAN8720A", "PHY: LAN8742A", "PHY: KSZ8081"])
add_caption(slide, MX, y + Inches(3.35), SW - 2 * MX,
            "Yeni bir MCU eklemek = **eth_device.h** içine birkaç satır. Port ve PHY dosyalarına "
            "**hiç dokunulmaz.**")

# ============================================================
# 7/18 — ÇEKİRDEK SÜRÜCÜ
# ============================================================
slide, y = new_content_slide(7, "06 · Çekirdek Sürücü", "Paylaşılan halka, net kurallar",
                              "8 elemanlı RX descriptor halkası (ring) — her eleman ya DMA'nın ya CPU'nun "
                              "sahipliğindedir, ikisi asla aynı anda değil.")
add_cards_row(slide, y + Inches(0.2), Inches(3.5), [
    dict(title="01  Zero-copy", text="DMA'nın tamponuna doğrudan yazılır — aradan **memcpy** geçmez."),
    dict(title="02  OWN biti", text="CPU ve DMA aynı descriptor dizisini tek bir sahiplik bitiyle paylaşır — "
                                     "kesme olmadan bile veri yarışı oluşmaz."),
    dict(title="03  MPU + non-cacheable", text="DMA'nın yazdığı veri CPU cache'ten değil, doğrudan bellekten okunur."),
])

# ============================================================
# 8/18 — PAKET İŞLEME AKIŞI
# ============================================================
slide, y = new_content_slide(8, "07 · Uygulama Katmanı", "Paket işleme akışı")
tb, tf = add_textbox(slide, MX, y + Inches(0.15), SW - 2 * MX, Inches(4.5))
tf.word_wrap = True
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
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.space_after = Pt(8)
    p.level = 0
    r = p.add_run()
    set_run(r, "     " * lvl + ("└─ " if lvl else ""), 13, MUTED, mono=True)
    rich_paragraph(p, text, 13, INK)

# ============================================================
# 9/18 — IAP BOOTLOADER
# ============================================================
slide, y = new_content_slide(9, "08 · IAP Bootloader", "Ağ üzerinden firmware güncelleme")
add_numlist(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(3.9), [
    ("GUI → Kart: START_IAP | SIZE:n | CRC:0x..", None),
    ("Kart → GUI: IAP_READY", None),
    ("Döngü (512B parça, en fazla 3 deneme): FW_DATA | SEQ:i  →  ACK:i", None),
    ("GUI → Kart: END_IAP", None),
    ("Kart: CRC32 doğrula → VTOR taşı → MSP ayarla → yeni uygulamaya atla", None),
    ("Kart → GUI: FLASH_SUCCESS | JUMP_OK", None),
])
add_caption(slide, MX, y + Inches(4.0), SW - 2 * MX,
            "Tek banka, kimlik doğrulama yok — yalnızca CRC32 bütünlük kontrolü. Sadece izole/güvenilir "
            "ağlarda kullanılmalı.")

# ============================================================
# 10/18 — TEST ARAYÜZÜ (GUI)
# ============================================================
slide, y = new_content_slide(
    10, "09 · Test Arayüzü", "Geliştirdiğim arayüzle kart canlı olarak izlenip test edilir",
    "Yedi ayrı sekme: kart verilerini izleme, bağlantı testi, performans ölçümü, arıza testi ve "
    "yazılım güncelleme.")
add_picture_framed(slide, os.path.join(ROOT, "Docs", "gui.png"), MX, y + Inches(0.1), Inches(6.6), Inches(3.6))
add_table(slide, MX + Inches(6.9), y + Inches(0.1), SW - MX - (MX + Inches(6.9)), Inches(3.6),
          ["Sekme", "İşlev"],
          [
              ["Kart G/Ç", "Otomatik değişken keşfi"],
              ["Ping (ICMP)", "Gecikme ölçümü"],
              ["UDP Konsol", "Serbest komut / log"],
              ["PHY / DMA Teşhis", "Register + istatistik"],
              ["Performans & Jitter", "min / ort / p95 / max"],
              ["Hata Enjeksiyonu", "Fuzz + parçalanma testi"],
              ["Bootloader (IAP)", "Ağdan firmware güncelleme"],
          ], col_widths=[45, 55], font_size=11)

# ============================================================
# 11/18 — GELİŞİM HİKAYESİ
# ============================================================
slide, y = new_content_slide(
    11, "10 · Süreç", "Boş bir pencereden, ölçüm yapan bir araca",
    "Arayüz de sürücü gibi gün gün, sekme sekme büyüdü — her yeni test yeteneği kartta çalışır hale "
    "geldikçe eklendi.")
imgw = Inches(5.4)
add_picture_framed(slide, os.path.join(ROOT, "arayuz_gelisim_ekran_goruntuleri", "24_agustos.png"),
                    MX, y + Inches(0.1), imgw, Inches(3.1), caption="24 Ağustos · ilk iskelet")
add_picture_framed(slide, os.path.join(ROOT, "arayuz_gelisim_ekran_goruntuleri", "28_agustos_performans.png"),
                    SW - MX - imgw, y + Inches(0.1), imgw, Inches(3.1), caption="28 Ağustos · canlı performans testi")

# ============================================================
# 12/18 — DOĞRULAMA & SONUÇLAR
# ============================================================
slide, y = new_content_slide(
    12, "11 · Doğrulama", "Kartın üzerinde çalıştırıp gerçek verilerle ölçtüm",
    '"Çalışıyor gibi görünüyor" yeterli değildi — her iddiayı donanımda ölçüp kaydettim.')
add_numlist(slide, MX, y + Inches(0.1), Inches(5.6), Inches(3.6), [
    ("MDIO alan yerleşimi", "MACMDIOAR register'ı"),
    ("RMII seçim kodu", "SBS→PMCR ETH_SEL_PHY"),
    ("DMA tail pointer semantiği", "DMACRXDTPR"),
    ("MPU alan yerleşimi", "RBAR / RLAR"),
    ("Flash sektör alanı", "yalnızca IAP kullanılıyorsa"),
])
imgx = MX + Inches(5.9)
add_picture_framed(slide, os.path.join(ROOT, "arayuz_gelisim_ekran_goruntuleri", "28_agustos_hata_enjeksiyonu.png"),
                    imgx, y + Inches(0.1), SW - MX - imgx, Inches(2.3))
add_caption(slide, imgx, y + Inches(2.55), SW - MX - imgx,
            "Kart bilerek bozuk/aşırı büyük veriyle yorulmaya çalışıldı — **hiç çökmedi.**")
add_tags(slide, imgx, y + Inches(3.05), SW - MX - imgx,
         ["gecikme ort. 0.44 ms · kayıp %0 · FLASH_SUCCESS|JUMP_OK"])

# ============================================================
# 13/18 — KARŞILAŞILAN ZORLUK
# ============================================================
slide, y = new_content_slide(13, "12 · Karşılaşılan Zorluk",
                              'En zorlayıcı an: yeni yazılıma "atlarken" kart kilitlendi')
add_quote(slide, MX, y + Inches(0.15), SW - 2 * MX, Inches(2.5),
          "Yeni yüklenen yazılıma geçiş anında kart her seferinde donuyordu. Debugger ile ilerleyerek "
          "nedenini buldum: eski yazılımdan kalan bir kesme (arka planda çalışan ağ donanımı), işlemci "
          "henüz yeni yazılıma tam geçmemişken devreye giriyor ve artık var olmayan bir adrese "
          "yönleniyordu.",
          "ÇÖZÜM → geçiş anından hemen önce donanımı durdurup tüm kesmeleri kapattım. "
          "Sorun tamamen ortadan kalktı.")
add_caption(slide, MX, y + Inches(2.9), SW - 2 * MX,
            "Bu, staj boyunca karşılaştığım en somut hata ayıklama (debugging) deneyimiydi: belirti "
            "donanımda görülüyor, kök neden kodda gizliydi.")

# ============================================================
# 14/18 — BİLİNEN SINIRLAR
# ============================================================
slide, y = new_content_slide(14, "13 · Dürüst Değerlendirme", "Bilinen sınırlar",
                              "Kapsamı bilinçli çizdim — sorulmadan kendim söylüyorum.")
add_limits(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(4), [
    "**IP fragment reassembly yok** — tasarım kararı, büyük paketler sessizce düşürülür",
    "**TCP yok** — yalnızca UDP / ICMP / ARP",
    "**Tek DMA kanalı, tek kuyruk** — QoS / VLAN önceliklendirme yok",
    "**IAP'de kimlik doğrulama yok** — yalnızca CRC32 bütünlük kontrolü",
    "**Polling tabanlı** — kesme desteği yok, gecikme çağrı sıklığına bağımlı",
    "**GMAC ailesi ve KSZ8081** — henüz ikinci bir kartta donanımda doğrulanmadı",
])

# ============================================================
# 15/18 — ARAÇLAR & TEKNOLOJİLER
# ============================================================
slide, y = new_content_slide(
    15, "14 · Araçlar & Teknolojiler", "Tek projede birçok farklı teknolojiyi bir araya getirdim",
    "Sadece C kodu yazmadım; geliştirme ortamından donanım protokollerine kadar birçok konuda "
    "uygulamalı pratik yaptım.")
add_cards_row(slide, y + Inches(0.15), Inches(3.1), [
    dict(eyebrow="Geliştirme ortamı", title="Araçlar & İş Akışı",
         badges=["CMake", "Git", "GCC & Ninja", "STM32CubeMX", "VS Code"]),
    dict(eyebrow="Donanım & protokoller", title="Nasıl Çalıştığını Öğrendiğim Katmanlar",
         badges=["DMA", "Ethernet (MAC/PHY/RMII)", "I2C", "SPI", "UART", "Interrupt (NVIC)", "FreeRTOS temelleri"]),
])
add_caption(slide, MX, y + Inches(3.45), SW - 2 * MX,
            "Bare-metal kod yazma pratiği + farklı işlemci çekirdeklerini (Cortex-M4/M7/M33) ve farklı "
            "entegreleri tek bir projede bir araya getirme deneyimi.")

# ============================================================
# 16/18 — ÖĞRENDİKLERİM
# ============================================================
slide, y = new_content_slide(16, "15 · Öğrendiklerim", "Üç boyutta öğrenme: teknik, mühendislik disiplini, kişisel")
add_cards_row(slide, y + Inches(0.15), Inches(3.6), [
    dict(title="Teknik", text="Gömülü sistemlerde donanım-yazılım ilişkisi, ağ protokollerinin temelleri, "
                               "C ile düşük seviyeli programlama, hata ayıklama disiplini."),
    dict(title="Mühendislik Pratiği", text='Gereksinim yazma, mimariyi baştan tasarlama, "her girdi düşmanca '
                                            'olabilir" ilkesiyle savunmacı kod yazma, sistemli test ve dokümantasyon.'),
    dict(title="Kişisel", text="Bağımsız çalışıp mentörle doğru zamanda geri bildirim alma, zaman/kapsam "
                                "yönetimi, teknik bir konuyu sade anlatabilme."),
])

# ============================================================
# 17/18 — STAJIN BANA KATTIKLARI
# ============================================================
slide, y = new_content_slide(
    17, "16 · Stajın Bana Kattıkları", "Bir mühendislik sürecini baştan sona yaşadım",
    "Eğitimle başlayıp gereksinimden teste uzanan tam bir döngüyü, tek bir projede kendi ellerimle "
    "tamamladım.")
add_stat_grid(slide, MX, y + Inches(0.1), SW - 2 * MX, Inches(2.7), [
    (40, "staj günü"), (4, "desteklenen MCU"), (3, "PHY çipi"), (2, "MAC ailesi"),
    (21, "port sözleşmesi fonksiyonu"), (7, "GUI test sekmesi"), (0, "malloc çağrısı"), (1, "dokunulan config dosyası"),
], cols=4)
add_tags(slide, MX, y + Inches(3.0), SW - 2 * MX, [
    "Savunma sanayiini yakından tanıma", "Uçtan uca doğrulama disiplini",
    "Sıfırdan bir kütüphane yazma özgüveni", "Karmaşık işi sade anlatma",
])

# ============================================================
# 18/18 — KAPANIŞ
# ============================================================
slide = prs.slides.add_slide(BLANK)
add_bg_rect(slide, WHITE)
add_wedge(slide, BIG_WEDGE, NAVY)
add_gray_line(slide, BIG_LINE1)
add_gray_line(slide, BIG_LINE2)
add_ring(slide, 0.90, 0.20, 0.055)
add_ring(slide, 0.90, 0.20, 0.085)
add_ring(slide, 0.90, 0.20, 0.115)
add_logo(slide, small=False)

tb, tf = add_textbox(slide, Inches(0.9), Inches(2.4), Inches(9), Inches(0.4))
p = tf.paragraphs[0]
r = p.add_run(); set_run(r, "TEŞEKKÜRLER", 13, CYAN, bold=True, mono=True)

tb, tf = add_textbox(slide, Inches(0.9), Inches(2.85), Inches(10.5), Inches(1.1))
tf.word_wrap = True
p = tf.paragraphs[0]
r = p.add_run(); set_run(r, "Sorularınızı dinliyorum", 40, INK, bold=True)

tb, tf = add_textbox(slide, Inches(0.9), Inches(3.85), Inches(9.5), Inches(0.5))
tf.word_wrap = True
p = tf.paragraphs[0]
r = p.add_run()
set_run(r, "EHSİM'e ve mentörüme, staj boyunca gösterdikleri destek için teşekkür ederim.", 14, MUTED)

tb, tf = add_textbox(slide, Inches(0.9), Inches(5.6), Inches(8), Inches(0.75))
p = tf.paragraphs[0]
r = p.add_run(); set_run(r, "Mehmet Akif Seçkin", 15, NAVY, bold=True)
p2 = tf.add_paragraph()
r2 = p2.add_run(); set_run(r2, "E-AETIS / Ethernet_BSP · Sistem ve Test Mühendisliği Stajı", 11, MUTED)

out_path = os.path.join(HERE, "EAETIS_Staj_Sunumu_Taslak.pptx")
prs.save(out_path)
print("OK:", out_path)
