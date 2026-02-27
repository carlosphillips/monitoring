#!/usr/bin/env python3
"""
Generate a beautiful PDF explaining Carino Linking methodology.
"""

import math
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, Image
)
from reportlab.graphics.shapes import Drawing, Line, Rect, String, Circle, Polygon
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ──────────────────────────────────────────────────────────────
# Color palette
# ──────────────────────────────────────────────────────────────
DARK_BG      = colors.HexColor("#1a1a2e")
ACCENT_BLUE  = colors.HexColor("#4361ee")
ACCENT_TEAL  = colors.HexColor("#3a86a8")
ACCENT_GREEN = colors.HexColor("#2ec4b6")
ACCENT_RED   = colors.HexColor("#e63946")
WARM_ORANGE  = colors.HexColor("#f4845f")
LIGHT_BG     = colors.HexColor("#f8f9fa")
MID_GRAY     = colors.HexColor("#6c757d")
DARK_TEXT     = colors.HexColor("#212529")
SOFT_BLUE_BG = colors.HexColor("#e8f0fe")
SOFT_GREEN_BG= colors.HexColor("#e6f7f5")
SOFT_RED_BG  = colors.HexColor("#fde8ea")
SOFT_ORANGE_BG = colors.HexColor("#fff3e0")
BORDER_BLUE  = colors.HexColor("#90b4ce")
TABLE_HEADER = colors.HexColor("#2c3e50")
TABLE_ALT    = colors.HexColor("#f0f4f8")


# ──────────────────────────────────────────────────────────────
# Styles
# ──────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "CustomTitle", parent=styles["Title"],
    fontSize=28, leading=34, textColor=DARK_TEXT,
    spaceAfter=6, alignment=TA_CENTER,
    fontName="Helvetica-Bold"
)

subtitle_style = ParagraphStyle(
    "CustomSubtitle", parent=styles["Normal"],
    fontSize=13, leading=18, textColor=MID_GRAY,
    spaceAfter=30, alignment=TA_CENTER,
    fontName="Helvetica"
)

h1_style = ParagraphStyle(
    "H1", parent=styles["Heading1"],
    fontSize=22, leading=28, textColor=ACCENT_BLUE,
    spaceBefore=24, spaceAfter=12,
    fontName="Helvetica-Bold",
    borderWidth=0, borderPadding=0,
)

h2_style = ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontSize=16, leading=22, textColor=DARK_TEXT,
    spaceBefore=18, spaceAfter=8,
    fontName="Helvetica-Bold"
)

h3_style = ParagraphStyle(
    "H3", parent=styles["Heading3"],
    fontSize=13, leading=18, textColor=ACCENT_TEAL,
    spaceBefore=12, spaceAfter=6,
    fontName="Helvetica-Bold"
)

body_style = ParagraphStyle(
    "CustomBody", parent=styles["Normal"],
    fontSize=10.5, leading=16, textColor=DARK_TEXT,
    spaceAfter=8, alignment=TA_JUSTIFY,
    fontName="Helvetica"
)

body_indent_style = ParagraphStyle(
    "BodyIndent", parent=body_style,
    leftIndent=20,
)

formula_style = ParagraphStyle(
    "Formula", parent=styles["Normal"],
    fontSize=11, leading=18, textColor=DARK_TEXT,
    spaceBefore=6, spaceAfter=6, alignment=TA_CENTER,
    fontName="Courier",
    backColor=SOFT_BLUE_BG,
    borderWidth=1, borderColor=BORDER_BLUE,
    borderPadding=10, borderRadius=4,
)

callout_style = ParagraphStyle(
    "Callout", parent=styles["Normal"],
    fontSize=10.5, leading=16, textColor=DARK_TEXT,
    spaceBefore=8, spaceAfter=8,
    fontName="Helvetica",
    backColor=SOFT_GREEN_BG,
    borderWidth=1, borderColor=ACCENT_GREEN,
    borderPadding=12, borderRadius=4,
    leftIndent=10, rightIndent=10,
)

warning_style = ParagraphStyle(
    "Warning", parent=callout_style,
    backColor=SOFT_RED_BG,
    borderColor=ACCENT_RED,
)

insight_style = ParagraphStyle(
    "Insight", parent=callout_style,
    backColor=SOFT_ORANGE_BG,
    borderColor=WARM_ORANGE,
)

caption_style = ParagraphStyle(
    "Caption", parent=styles["Normal"],
    fontSize=9, leading=13, textColor=MID_GRAY,
    alignment=TA_CENTER, spaceAfter=12,
    fontName="Helvetica-Oblique"
)

small_style = ParagraphStyle(
    "Small", parent=body_style,
    fontSize=9.5, leading=14, textColor=MID_GRAY,
)

code_style = ParagraphStyle(
    "Code", parent=styles["Code"],
    fontSize=9, leading=13,
    fontName="Courier",
    backColor=colors.HexColor("#f5f5f5"),
    borderWidth=0.5, borderColor=colors.HexColor("#ddd"),
    borderPadding=8,
    spaceAfter=8,
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def hr():
    return HRFlowable(
        width="100%", thickness=0.5, color=colors.HexColor("#dee2e6"),
        spaceBefore=8, spaceAfter=8
    )

def spacer(h=12):
    return Spacer(1, h)

def make_table(data, col_widths=None, header_rows=1):
    """Create a styled table."""
    t = Table(data, colWidths=col_widths, repeatRows=header_rows)
    style_cmds = [
        ('FONTNAME', (0, 0), (-1, header_rows - 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEADING', (0, 0), (-1, -1), 14),
        ('BACKGROUND', (0, 0), (-1, header_rows - 1), TABLE_HEADER),
        ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    # Alternate row colors
    for i in range(header_rows, len(data)):
        if (i - header_rows) % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), colors.white))
        else:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), TABLE_ALT))
    t.setStyle(TableStyle(style_cmds))
    return t

def highlight_table(data, col_widths=None, highlight_col=None, highlight_color=SOFT_GREEN_BG):
    """Table with a highlighted column."""
    t = make_table(data, col_widths)
    if highlight_col is not None:
        t.setStyle(TableStyle([
            ('BACKGROUND', (highlight_col, 1), (highlight_col, -1), highlight_color),
            ('FONTNAME', (highlight_col, 1), (highlight_col, -1), 'Helvetica-Bold'),
        ]))
    return t

def bold(text):
    return f"<b>{text}</b>"

def italic(text):
    return f"<i>{text}</i>"

def code(text):
    return f'<font face="Courier" size="9" color="#e63946">{text}</font>'

def blue(text):
    return f'<font color="#4361ee">{text}</font>'

def teal(text):
    return f'<font color="#3a86a8">{text}</font>'

def green(text):
    return f'<font color="#2ec4b6">{text}</font>'

def red(text):
    return f'<font color="#e63946">{text}</font>'

def orange(text):
    return f'<font color="#f4845f">{text}</font>'


# ──────────────────────────────────────────────────────────────
# Carino math helpers
# ──────────────────────────────────────────────────────────────
def carino_k(r):
    """Per-day Carino coefficient."""
    if abs(r) < 1e-12:
        return 1.0
    return math.log(1 + r) / r

def carino_K(R):
    """Full-window Carino coefficient."""
    if abs(R) < 1e-12:
        return 1.0
    return math.log(1 + R) / R

def geometric_return(daily_returns):
    """Compute geometric total return from daily returns."""
    prod = 1.0
    for r in daily_returns:
        prod *= (1 + r)
    return prod - 1.0


# ──────────────────────────────────────────────────────────────
# Chart: bar chart comparing simple vs Carino
# ──────────────────────────────────────────────────────────────
def make_comparison_bar_chart(simple_contribs, carino_contribs, labels, title_text=""):
    """Create a grouped bar chart comparing simple vs Carino contributions."""
    d = Drawing(460, 200)

    bc = VerticalBarChart()
    bc.x = 60
    bc.y = 30
    bc.width = 370
    bc.height = 140
    bc.data = [simple_contribs, carino_contribs]
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.valueAxis.valueMin = min(min(simple_contribs), min(carino_contribs)) * 1.3
    bc.valueAxis.valueMax = max(max(simple_contribs), max(carino_contribs)) * 1.3
    bc.valueAxis.labels.fontSize = 8
    bc.valueAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labelTextFormat = "%0.4f"
    bc.groupSpacing = 15
    bc.barSpacing = 2
    bc.bars[0].fillColor = ACCENT_BLUE
    bc.bars[1].fillColor = ACCENT_GREEN
    bc.barWidth = 18

    d.add(bc)

    # Legend
    d.add(Rect(65, 180, 12, 8, fillColor=ACCENT_BLUE, strokeColor=None))
    d.add(String(82, 181, "Simple Sum", fontSize=8, fontName="Helvetica"))
    d.add(Rect(165, 180, 12, 8, fillColor=ACCENT_GREEN, strokeColor=None))
    d.add(String(182, 181, "Carino-Linked", fontSize=8, fontName="Helvetica"))

    if title_text:
        d.add(String(230, 193, title_text, fontSize=10, fontName="Helvetica-Bold",
                      textAnchor="middle"))

    return d


# ──────────────────────────────────────────────────────────────
# Build the document
# ──────────────────────────────────────────────────────────────
def build_pdf():
    output_path = "/workspaces/monitoring/docs/carino-linking-explained.pdf"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        leftMargin=0.8*inch,
        rightMargin=0.8*inch,
    )

    story = []

    # ═══════════════════════════════════════════════════════════
    # TITLE PAGE
    # ═══════════════════════════════════════════════════════════
    story.append(spacer(80))

    # Decorative top line
    story.append(HRFlowable(width="60%", thickness=3, color=ACCENT_BLUE,
                            spaceBefore=0, spaceAfter=20))

    story.append(Paragraph("Carino Linking", title_style))
    story.append(Paragraph("A Visual Guide to Multi-Period<br/>Return Attribution",
                          subtitle_style))

    story.append(HRFlowable(width="60%", thickness=3, color=ACCENT_BLUE,
                            spaceBefore=0, spaceAfter=40))

    story.append(Paragraph(
        "How to decompose portfolio returns into factor contributions<br/>"
        "that sum exactly to the total geometric return over any time window.",
        ParagraphStyle("TitleBody", parent=body_style,
                      fontSize=12, leading=20, alignment=TA_CENTER,
                      textColor=MID_GRAY)
    ))

    story.append(spacer(60))

    # Quick TOC
    toc_data = [
        ["Section", "Page"],
        ["1.  The Problem: Why Simple Sums Fail", "2"],
        ["2.  The Carino Linking Solution", "4"],
        ["3.  Step-by-Step Formula Walkthrough", "5"],
        ["4.  Example 1: Two-Day Window", "7"],
        ["5.  Example 2: Five-Day Multi-Factor", "9"],
        ["6.  Example 3: Edge Cases", "12"],
        ["7.  Different Window Sizes", "14"],
        ["8.  Summary & Key Properties", "15"],
    ]
    toc_table = make_table(toc_data, col_widths=[380, 60])
    story.append(toc_table)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 1: THE PROBLEM
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("1. The Problem: Why Simple Sums Fail", h1_style))
    story.append(hr())

    story.append(Paragraph(
        "Suppose you manage a portfolio and want to understand how much each factor "
        "(market exposure, value tilt, size tilt, etc.) contributed to your total return "
        "over a quarter. On any " + bold("single day") + ", this is straightforward:",
        body_style
    ))

    story.append(Paragraph(
        "Daily Contribution = Starting Exposure  x  Factor Return",
        formula_style
    ))

    story.append(Paragraph(
        "For example, if your market exposure at the open is " + code("1.05") + " and the market "
        "returns " + code("+0.80%") + " that day, then the market contributed roughly "
        + code("1.05 x 0.008 = 0.0084") + " (or 84 basis points) to your portfolio return.",
        body_style
    ))

    story.append(spacer(8))
    story.append(Paragraph("So What's the Problem?", h2_style))

    story.append(Paragraph(
        "The trouble starts when you try to extend this to " + bold("multiple days") + ". "
        "The natural instinct is to simply sum the daily contributions:",
        body_style
    ))

    story.append(Paragraph(
        'Simple Sum = c&#8321; + c&#8322; + c&#8323; + ... + c&#8345;'
        '&nbsp;&nbsp;&nbsp;where c&#8345; = exposure&#8345; x factor_return&#8345;',
        formula_style
    ))

    story.append(Paragraph(
        "But portfolio returns " + bold("compound geometrically") + ", not arithmetically. "
        "The total return over N days is:",
        body_style
    ))

    story.append(Paragraph(
        "R = (1 + r&#8321;)(1 + r&#8322;)...(1 + r&#8345;) - 1"
        "&nbsp;&nbsp;&nbsp;&nbsp;(geometric, not additive!)",
        formula_style
    ))

    story.append(Paragraph(
        "This mismatch means that " + red("simple sums of daily contributions will NOT equal "
        "the actual portfolio return") + " over multi-day periods. The gap grows with "
        "volatility and window length.",
        warning_style
    ))

    story.append(spacer(8))

    # Concrete numeric example of the problem
    story.append(Paragraph("A Concrete Example of the Gap", h2_style))

    story.append(Paragraph(
        "Consider a simple portfolio with a single factor (market) over 3 days:",
        body_style
    ))

    # 3-day problem example
    days_3 = [
        (0.0100, 1.02),  # day 1: mkt +1.00%, exposure 1.02
        (-0.0050, 1.01), # day 2: mkt -0.50%, exposure 1.01
        (0.0150, 1.03),  # day 3: mkt +1.50%, exposure 1.03
    ]

    # Compute daily contributions and portfolio returns
    # For simplicity: portfolio return ≈ exposure * factor_return (single factor, small residual)
    p_returns_3 = [exp * fr for fr, exp in days_3]
    simple_contribs_3 = [exp * fr for fr, exp in days_3]
    simple_total = sum(simple_contribs_3)
    geo_total_3 = geometric_return(p_returns_3)

    data_3day = [
        ["Day", "Factor Return", "Exposure", "Daily Contribution", "Portfolio Return"],
        ["1", "+1.00%", "1.02", f"{simple_contribs_3[0]:+.5f}", f"{p_returns_3[0]:+.5f}"],
        ["2", "-0.50%", "1.01", f"{simple_contribs_3[1]:+.5f}", f"{p_returns_3[1]:+.5f}"],
        ["3", "+1.50%", "1.03", f"{simple_contribs_3[2]:+.5f}", f"{p_returns_3[2]:+.5f}"],
    ]
    story.append(make_table(data_3day, col_widths=[40, 90, 70, 120, 120]))
    story.append(spacer(6))

    compare_data = [
        ["Method", "Value", ""],
        ["Simple Sum of Contributions", f"{simple_total:+.6f}", "c1 + c2 + c3"],
        ["Geometric Portfolio Return", f"{geo_total_3:+.6f}", "(1+r1)(1+r2)(1+r3) - 1"],
        ["Gap (Error)", f"{simple_total - geo_total_3:+.6f}", red("Does not sum to total!")],
    ]
    t = make_table(compare_data, col_widths=[180, 100, 170])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 3), (-1, 3), SOFT_RED_BG),
        ('TEXTCOLOR', (2, 3), (2, 3), ACCENT_RED),
    ]))
    story.append(t)

    story.append(spacer(8))
    story.append(Paragraph(
        bold("Why does this happen?") + " On Day 1, the portfolio earned +1.02%. That gain "
        "then " + italic("compounds") + " on Days 2 and 3. A dollar invested grew to $1.0102 "
        "after Day 1 — so Day 2's return applies to a larger base. Simple sums ignore this "
        "compounding effect entirely.",
        insight_style
    ))

    story.append(spacer(8))
    story.append(Paragraph(
        "The gap may seem small here (a few basis points), but over longer windows "
        "(quarterly, annual, 3-year) and with volatile portfolios, it can become "
        + bold("material") + " — enough to distort risk attribution and threshold monitoring.",
        body_style
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 2: THE SOLUTION
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("2. The Carino Linking Solution", h1_style))
    story.append(hr())

    story.append(Paragraph(
        "Carino linking (developed by David Carino) provides an elegant way to "
        + bold("rescale daily contributions") + " so they sum " + bold("exactly")
        + " to the geometric total return over any multi-day window.",
        body_style
    ))

    story.append(spacer(4))
    story.append(Paragraph("The Core Idea in Plain English", h2_style))

    story.append(Paragraph(
        "Think of the total geometric return as a " + blue("pie") + ". Each day contributed "
        "some portion to that pie. The question is: how do we fairly slice it?",
        body_style
    ))

    story.append(Paragraph(
        "Carino's insight is to use the " + bold("logarithmic return") + " as a fair "
        "measuring stick. Here's why: log returns " + italic("do") + " add up over time "
        "(that's a mathematical property of logarithms), so they give us a natural way to "
        "measure each day's relative importance. A day where the portfolio moved a lot "
        "gets a bigger slice; a day where it barely moved gets a smaller one.",
        body_style
    ))

    story.append(spacer(6))

    # Visual analogy
    story.append(Paragraph(
        bold("Visual Analogy:") + " Imagine pouring water into a bucket over several days. "
        "The total water in the bucket is the geometric return. Each day you poured some water "
        "(the log return for that day). Carino linking figures out what " + italic("fraction")
        + " of the total water each day contributed, then uses those fractions to rescale "
        "the raw daily factor contributions so everything adds up perfectly.",
        callout_style
    ))

    story.append(spacer(8))
    story.append(Paragraph("Three Steps to Carino Linking", h2_style))

    steps = [
        (bold("Step 1: Compute Carino coefficients for each day.") +
         " Each day gets a coefficient that translates between arithmetic and logarithmic "
         "returns. This coefficient is close to 1 for small returns and adjusts as returns "
         "grow larger."),
        (bold("Step 2: Compute the Carino coefficient for the full window.") +
         " The same formula applied to the total geometric return of the entire window."),
        (bold("Step 3: Form the linking weight and rescale.") +
         " The ratio of each day's coefficient to the window's coefficient gives you the "
         "linking weight. Multiply each daily contribution by its weight, then sum."),
    ]
    for step in steps:
        story.append(Paragraph(step, body_indent_style))
        story.append(spacer(4))

    story.append(Paragraph(
        "The result is a set of " + green("linked contributions") + " that sum to "
        + bold("exactly") + " the geometric total return. No gap, no approximation error.",
        callout_style
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 3: STEP-BY-STEP FORMULA
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("3. Step-by-Step Formula Walkthrough", h1_style))
    story.append(hr())

    story.append(Paragraph("Inputs", h2_style))

    story.append(Paragraph(
        "For a trailing window of N days, you have:", body_style
    ))

    inputs_data = [
        ["Symbol", "Meaning", "Source"],
        ["r(p,t)", "Portfolio return on day t", "exposures.csv: portfolio_return column"],
        ["e(l,f,t)", "Exposure to factor f in layer l on day t", "exposures.csv: {layer}_{factor} columns"],
        ["r(f,t)", "Return of factor f on day t", "factor_returns.csv"],
        ["c(l,f,t)", "Daily contribution = e(l,f,t) x r(f,t)", "Computed"],
        ["R(p)", "Geometric total portfolio return", "Product of (1 + r(p,t)) minus 1"],
    ]
    story.append(make_table(inputs_data, col_widths=[70, 200, 195]))

    story.append(spacer(12))
    story.append(Paragraph("Step 1: Per-Day Carino Coefficient", h2_style))

    story.append(Paragraph(
        "For each day t in the window, compute:",
        body_style
    ))

    story.append(Paragraph(
        "k(t) = ln(1 + r(p,t)) / r(p,t)",
        formula_style
    ))

    story.append(Paragraph(
        bold("What does k(t) do?") + " It converts between the arithmetic return r(p,t) and the "
        "log return ln(1 + r(p,t)). When r(p,t) is small (say under 2%), k(t) is very close "
        "to 1. As returns get larger (positive or negative), k(t) adjusts to account for the "
        "non-linearity of the log function.",
        body_style
    ))

    # Show k(t) for various returns
    k_examples = [
        ["r(p,t)", "ln(1+r)", "k(t) = ln(1+r)/r", "Interpretation"],
    ]
    for r in [-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05, 0.10]:
        if abs(r) < 1e-12:
            k_examples.append([
                "0.00%",
                "0.00000",
                "1.00000  (limit)",
                "No return; k = 1 by convention"
            ])
        else:
            lr = math.log(1 + r)
            k = lr / r
            k_examples.append([
                f"{r:+.2%}",
                f"{lr:+.5f}",
                f"{k:.5f}",
                "Log < arith" if r > 0 else ("Log > arith (absolute)" if r < 0 else "")
            ])
    story.append(make_table(k_examples, col_widths=[65, 80, 120, 195]))
    story.append(spacer(4))
    story.append(Paragraph(
        italic("Notice: k(t) is always close to 1 for typical daily returns. "
               "It's a gentle correction, not a dramatic rescaling."),
        caption_style
    ))

    story.append(spacer(12))
    story.append(Paragraph("Step 2: Full-Window Carino Coefficient", h2_style))

    story.append(Paragraph(
        "Compute the same formula, but for the total geometric return of the entire window:",
        body_style
    ))

    story.append(Paragraph(
        "K = ln(1 + R(p)) / R(p)",
        formula_style
    ))

    story.append(Paragraph(
        "Where R(p) is the geometric total: R(p) = (1+r(p,1))(1+r(p,2))...(1+r(p,N)) - 1",
        body_style
    ))

    story.append(spacer(12))
    story.append(Paragraph("Step 3: Linking Weight & Linked Contribution", h2_style))

    story.append(Paragraph(
        "The linking weight for day t is the ratio of the daily coefficient to the window coefficient:",
        body_style
    ))

    story.append(Paragraph(
        "w(t) = k(t) / K",
        formula_style
    ))

    story.append(Paragraph(
        "The Carino-linked contribution for a (layer, factor) pair over the window is:",
        body_style
    ))

    story.append(Paragraph(
        "C(l,f) = SUM over t of:  w(t) x e(l,f,t) x r(f,t)"
        "<br/><br/>"
        "       = SUM over t of:  w(t) x c(l,f,t)",
        formula_style
    ))

    story.append(spacer(8))
    story.append(Paragraph(
        bold("The Key Property:") + " The sum of all linked contributions across all layers, "
        "factors, and residual equals " + bold("exactly") + " the geometric total return:<br/><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;" + code("SUM(all C(l,f)) + C(residual) = R(p)") + "<br/><br/>"
        "This is the entire point of Carino linking: " + green("exact additivity under "
        "geometric compounding") + ".",
        callout_style
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 4: EXAMPLE 1 — TWO-DAY
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("4. Example 1: Two-Day Window", h1_style))
    story.append(hr())

    story.append(Paragraph(
        "Let's walk through the simplest non-trivial case: a portfolio with "
        + bold("one factor (market)") + " over " + bold("two days") + ". "
        "This makes the mechanics crystal clear before adding complexity.",
        body_style
    ))

    story.append(spacer(6))
    story.append(Paragraph("Setup", h2_style))

    # Two-day example data
    d1_mkt_ret = 0.0120   # market return day 1
    d1_exp     = 1.05      # market exposure day 1
    d2_mkt_ret = -0.0080   # market return day 2
    d2_exp     = 1.02      # market exposure day 2

    d1_port_ret = d1_exp * d1_mkt_ret   # portfolio return day 1 (assuming single factor, no residual for clarity)
    d2_port_ret = d2_exp * d2_mkt_ret   # portfolio return day 2

    # Actually let's make it more realistic: portfolio return includes a small residual
    d1_port_ret = 0.0130   # slightly more than exposure*factor (residual = +0.0004)
    d2_port_ret = -0.0080  # slightly more than exposure*factor (residual = +0.0002)

    d1_contrib = d1_exp * d1_mkt_ret   # 1.05 * 0.012 = 0.0126
    d2_contrib = d2_exp * d2_mkt_ret   # 1.02 * -0.008 = -0.00816

    d1_resid = d1_port_ret - d1_contrib
    d2_resid = d2_port_ret - d2_contrib

    setup_data = [
        ["", "Day 1", "Day 2"],
        ["Portfolio Return  r(p,t)", f"{d1_port_ret:+.4f}  (+1.30%)", f"{d2_port_ret:+.4f}  (-0.80%)"],
        ["Market Factor Return  r(f,t)", f"{d1_mkt_ret:+.4f}  (+1.20%)", f"{d2_mkt_ret:+.4f}  (-0.80%)"],
        ["Market Exposure  e(t)", f"{d1_exp:.2f}", f"{d2_exp:.2f}"],
        ["Daily Market Contrib  c(t)", f"{d1_contrib:+.6f}", f"{d2_contrib:+.6f}"],
        ["Daily Residual", f"{d1_resid:+.6f}", f"{d2_resid:+.6f}"],
    ]
    story.append(make_table(setup_data, col_widths=[180, 140, 140]))

    story.append(spacer(12))
    story.append(Paragraph("Step 1: Compute Per-Day Carino Coefficients", h2_style))

    k1 = carino_k(d1_port_ret)
    k2 = carino_k(d2_port_ret)

    story.append(Paragraph(
        f"k(1) = ln(1 + {d1_port_ret:+.4f}) / {d1_port_ret:+.4f} = "
        f"ln({1+d1_port_ret:.4f}) / {d1_port_ret:.4f} = "
        f"{math.log(1+d1_port_ret):.6f} / {d1_port_ret:.4f} = " + bold(f"{k1:.6f}"),
        formula_style
    ))
    story.append(spacer(4))
    story.append(Paragraph(
        f"k(2) = ln(1 + {d2_port_ret:+.4f}) / {d2_port_ret:+.4f} = "
        f"ln({1+d2_port_ret:.4f}) / {d2_port_ret:.4f} = "
        f"{math.log(1+d2_port_ret):.6f} / {d2_port_ret:.4f} = " + bold(f"{k2:.6f}"),
        formula_style
    ))

    story.append(spacer(4))
    story.append(Paragraph(
        "Both are very close to 1 — typical for daily returns. "
        f"Day 1 (positive return): k slightly below 1 ({k1:.6f}). "
        f"Day 2 (negative return): k slightly above 1 ({k2:.6f}).",
        small_style
    ))

    story.append(spacer(12))
    story.append(Paragraph("Step 2: Compute Geometric Return & Window Coefficient", h2_style))

    R_p = (1 + d1_port_ret) * (1 + d2_port_ret) - 1
    K_window = carino_K(R_p)

    story.append(Paragraph(
        f"R(p) = (1 + {d1_port_ret:+.4f}) x (1 + {d2_port_ret:+.4f}) - 1 = "
        f"{1+d1_port_ret:.4f} x {1+d2_port_ret:.4f} - 1 = " + bold(f"{R_p:+.6f}"),
        formula_style
    ))
    story.append(spacer(4))
    story.append(Paragraph(
        f"K = ln(1 + {R_p:+.6f}) / {R_p:+.6f} = " + bold(f"{K_window:.6f}"),
        formula_style
    ))

    story.append(spacer(12))
    story.append(Paragraph("Step 3: Compute Linking Weights", h2_style))

    w1 = k1 / K_window
    w2 = k2 / K_window

    story.append(Paragraph(
        f"w(1) = k(1) / K = {k1:.6f} / {K_window:.6f} = " + bold(f"{w1:.6f}"),
        formula_style
    ))
    story.append(spacer(4))
    story.append(Paragraph(
        f"w(2) = k(2) / K = {k2:.6f} / {K_window:.6f} = " + bold(f"{w2:.6f}"),
        formula_style
    ))

    story.append(spacer(4))
    story.append(Paragraph(
        f"Note that w(1) = {w1:.6f} and w(2) = {w2:.6f}. Day 1 (larger absolute return) "
        f"gets a slightly {'larger' if abs(d1_port_ret) > abs(d2_port_ret) else 'different'} "
        f"weight. These are NOT proportions that sum to 1 — they are " + italic("scaling factors") + ".",
        small_style
    ))

    story.append(spacer(12))
    story.append(Paragraph("Step 4: Compute Linked Contributions", h2_style))

    linked_mkt = w1 * d1_contrib + w2 * d2_contrib
    linked_resid = w1 * d1_resid + w2 * d2_resid
    simple_mkt = d1_contrib + d2_contrib
    simple_resid = d1_resid + d2_resid

    result_data = [
        ["", "Simple Sum", "Carino-Linked", "Difference"],
        ["Market Contribution", f"{simple_mkt:+.6f}", f"{linked_mkt:+.6f}",
         f"{linked_mkt - simple_mkt:+.6f}"],
        ["Residual", f"{simple_resid:+.6f}", f"{linked_resid:+.6f}",
         f"{linked_resid - simple_resid:+.6f}"],
        ["Total", f"{simple_mkt + simple_resid:+.6f}", f"{linked_mkt + linked_resid:+.6f}",
         f"{(linked_mkt + linked_resid) - (simple_mkt + simple_resid):+.6f}"],
        ["Geometric Return R(p)", "", f"{R_p:+.6f}", ""],
    ]
    t = highlight_table(result_data, col_widths=[120, 100, 100, 100],
                        highlight_col=2, highlight_color=SOFT_GREEN_BG)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 4), (-1, 4), SOFT_BLUE_BG),
        ('FONTNAME', (0, 4), (-1, 4), 'Helvetica-Bold'),
    ]))
    story.append(t)

    story.append(spacer(8))
    story.append(Paragraph(
        "The Carino-linked total (" + green(f"{linked_mkt + linked_resid:+.6f}") +
        ") matches the geometric return (" + blue(f"{R_p:+.6f}") +
        ") " + bold("exactly") + ". The simple sum (" +
        red(f"{simple_mkt + simple_resid:+.6f}") + ") does not.",
        callout_style
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 5: EXAMPLE 2 — FIVE-DAY MULTI-FACTOR
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("5. Example 2: Five-Day Multi-Factor Window", h1_style))
    story.append(hr())

    story.append(Paragraph(
        "Now a more realistic scenario: a portfolio with " + bold("two layers")
        + " (benchmark, tactical), " + bold("two factors") + " (Market, HML), and a "
        + bold("five-day window") + ".",
        body_style
    ))

    story.append(spacer(6))
    story.append(Paragraph("Raw Data", h2_style))

    # 5-day multi-factor example
    np.random.seed(42)

    # Factor returns
    mkt_rets = [0.0085, -0.0042, 0.0120, 0.0030, -0.0065]
    hml_rets = [-0.0015, 0.0028, -0.0010, 0.0045, 0.0012]

    # Exposures
    bench_mkt_exp = [1.00, 1.00, 1.00, 1.00, 1.00]  # benchmark: market beta ~1
    bench_hml_exp = [0.10, 0.10, 0.10, 0.10, 0.10]   # slight value tilt
    tact_mkt_exp  = [0.05, 0.03, 0.08, -0.02, 0.04]  # active market bets
    tact_hml_exp  = [-0.03, -0.02, 0.05, 0.06, -0.01] # active value bets

    # Compute daily contributions
    bench_mkt_c = [e * r for e, r in zip(bench_mkt_exp, mkt_rets)]
    bench_hml_c = [e * r for e, r in zip(bench_hml_exp, hml_rets)]
    tact_mkt_c  = [e * r for e, r in zip(tact_mkt_exp, mkt_rets)]
    tact_hml_c  = [e * r for e, r in zip(tact_hml_exp, hml_rets)]

    # Portfolio returns (sum of all contributions + small residual)
    residuals = [0.0002, -0.0001, 0.0003, 0.0001, -0.0002]
    port_rets = [
        bench_mkt_c[i] + bench_hml_c[i] + tact_mkt_c[i] + tact_hml_c[i] + residuals[i]
        for i in range(5)
    ]

    # Display raw data
    raw_data = [
        ["Day", "Mkt Ret", "HML Ret", "Port Ret", "BM-Mkt Exp", "BM-HML Exp", "Tact-Mkt Exp", "Tact-HML Exp"],
    ]
    for i in range(5):
        raw_data.append([
            f"{i+1}",
            f"{mkt_rets[i]:+.4f}",
            f"{hml_rets[i]:+.4f}",
            f"{port_rets[i]:+.6f}",
            f"{bench_mkt_exp[i]:.2f}",
            f"{bench_hml_exp[i]:.2f}",
            f"{tact_mkt_exp[i]:+.2f}",
            f"{tact_hml_exp[i]:+.2f}",
        ])
    story.append(make_table(raw_data, col_widths=[30, 60, 60, 75, 65, 65, 70, 70]))

    story.append(spacer(8))
    story.append(Paragraph("Daily Contributions (exposure x factor return)", h2_style))

    contrib_data = [
        ["Day", "BM-Mkt", "BM-HML", "Tact-Mkt", "Tact-HML", "Residual", "Total (= Port Ret)"],
    ]
    for i in range(5):
        total = bench_mkt_c[i] + bench_hml_c[i] + tact_mkt_c[i] + tact_hml_c[i] + residuals[i]
        contrib_data.append([
            f"{i+1}",
            f"{bench_mkt_c[i]:+.6f}",
            f"{bench_hml_c[i]:+.6f}",
            f"{tact_mkt_c[i]:+.6f}",
            f"{tact_hml_c[i]:+.6f}",
            f"{residuals[i]:+.6f}",
            f"{total:+.6f}",
        ])
    story.append(make_table(contrib_data, col_widths=[30, 75, 75, 75, 75, 65, 95]))

    story.append(spacer(8))
    story.append(Paragraph(
        italic("Each row sums horizontally to the portfolio return for that day — "
               "this is where factor attribution begins. The challenge is extending this "
               "to the full 5-day window."),
        caption_style
    ))

    story.append(spacer(8))
    story.append(Paragraph("Carino Coefficients & Weights", h2_style))

    # Compute Carino
    R_p_5 = geometric_return(port_rets)
    K_5 = carino_K(R_p_5)
    k_vals = [carino_k(r) for r in port_rets]
    w_vals = [k / K_5 for k in k_vals]

    carino_data = [
        ["Day", "r(p,t)", "k(t) = ln(1+r)/r", "w(t) = k(t)/K", "Interpretation"],
    ]
    for i in range(5):
        interp = ""
        if port_rets[i] > 0.005:
            interp = "Large + return: weight > 1"
        elif port_rets[i] < -0.005:
            interp = "Large - return: weight > 1"
        elif abs(port_rets[i]) < 0.001:
            interp = "Small return: weight near 1"
        else:
            interp = "Moderate return"
        carino_data.append([
            f"{i+1}",
            f"{port_rets[i]:+.6f}",
            f"{k_vals[i]:.6f}",
            f"{w_vals[i]:.6f}",
            interp,
        ])

    story.append(make_table(carino_data, col_widths=[30, 80, 110, 90, 160]))
    story.append(spacer(4))
    story.append(Paragraph(
        f"Geometric total return: R(p) = {R_p_5:+.6f}  |  "
        f"Window coefficient: K = {K_5:.6f}",
        ParagraphStyle("CenteredSmall", parent=small_style, alignment=TA_CENTER)
    ))

    story.append(PageBreak())

    story.append(Paragraph("Linked Contributions: The Final Result", h2_style))

    # Compute linked contributions
    linked_bm_mkt = sum(w_vals[i] * bench_mkt_c[i] for i in range(5))
    linked_bm_hml = sum(w_vals[i] * bench_hml_c[i] for i in range(5))
    linked_ta_mkt = sum(w_vals[i] * tact_mkt_c[i] for i in range(5))
    linked_ta_hml = sum(w_vals[i] * tact_hml_c[i] for i in range(5))
    linked_resid  = sum(w_vals[i] * residuals[i] for i in range(5))

    simple_bm_mkt = sum(bench_mkt_c)
    simple_bm_hml = sum(bench_hml_c)
    simple_ta_mkt = sum(tact_mkt_c)
    simple_ta_hml = sum(tact_hml_c)
    simple_resid  = sum(residuals)

    linked_total = linked_bm_mkt + linked_bm_hml + linked_ta_mkt + linked_ta_hml + linked_resid
    simple_total = simple_bm_mkt + simple_bm_hml + simple_ta_mkt + simple_ta_hml + simple_resid

    result5_data = [
        ["Component", "Simple Sum", "Carino-Linked", "Difference"],
        ["Benchmark - Market", f"{simple_bm_mkt:+.6f}", f"{linked_bm_mkt:+.6f}",
         f"{linked_bm_mkt - simple_bm_mkt:+.6f}"],
        ["Benchmark - HML", f"{simple_bm_hml:+.6f}", f"{linked_bm_hml:+.6f}",
         f"{linked_bm_hml - simple_bm_hml:+.6f}"],
        ["Tactical - Market", f"{simple_ta_mkt:+.6f}", f"{linked_ta_mkt:+.6f}",
         f"{linked_ta_mkt - simple_ta_mkt:+.6f}"],
        ["Tactical - HML", f"{simple_ta_hml:+.6f}", f"{linked_ta_hml:+.6f}",
         f"{linked_ta_hml - simple_ta_hml:+.6f}"],
        ["Residual", f"{simple_resid:+.6f}", f"{linked_resid:+.6f}",
         f"{linked_resid - simple_resid:+.6f}"],
        ["TOTAL", f"{simple_total:+.6f}", f"{linked_total:+.6f}",
         f"{linked_total - simple_total:+.6f}"],
        ["Geometric Return R(p)", "", f"{R_p_5:+.6f}", ""],
    ]
    t = highlight_table(result5_data, col_widths=[130, 100, 100, 100],
                        highlight_col=2, highlight_color=SOFT_GREEN_BG)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 7), (-1, 7), SOFT_BLUE_BG),
        ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor("#e8e8e8")),
        ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),
        ('LINEABOVE', (0, 6), (-1, 6), 1.5, DARK_TEXT),
    ]))
    story.append(t)

    story.append(spacer(8))

    match_diff = abs(linked_total - R_p_5)
    gap_simple = abs(simple_total - R_p_5)

    story.append(Paragraph(
        bold("Verification:") + f" Carino-linked total = {linked_total:+.10f}, "
        f"Geometric return = {R_p_5:+.10f}. "
        f"Difference = {match_diff:.2e} (floating point only).<br/><br/>"
        f"Simple sum gap = {gap_simple:.6f} ({gap_simple*10000:.2f} basis points of error).",
        callout_style
    ))

    story.append(spacer(12))

    # Bar chart comparison
    chart_simple = [simple_bm_mkt, simple_bm_hml, simple_ta_mkt, simple_ta_hml, simple_resid]
    chart_linked = [linked_bm_mkt, linked_bm_hml, linked_ta_mkt, linked_ta_hml, linked_resid]
    chart_labels = ["BM-Mkt", "BM-HML", "Tact-Mkt", "Tact-HML", "Residual"]

    chart = make_comparison_bar_chart(chart_simple, chart_linked, chart_labels,
                                      "Simple Sum vs. Carino-Linked Contributions")
    story.append(chart)
    story.append(Paragraph(
        italic("Visual comparison: differences are small at the component level, "
               "but they compound to create a meaningful gap at the total level."),
        caption_style
    ))

    story.append(spacer(8))
    story.append(Paragraph("Reading the Results", h2_style))

    story.append(Paragraph(
        "The " + bold("Benchmark-Market") + f" row shows that market beta contributed "
        f"{linked_bm_mkt:+.4f} ({linked_bm_mkt*100:+.2f}%) to the portfolio's "
        f"total {R_p_5*100:+.2f}% return over the 5-day window. "
        "This is the largest contributor, which makes sense — the benchmark has a "
        "market exposure of 1.00 and the market had net positive returns over the period.",
        body_style
    ))

    story.append(Paragraph(
        "The " + bold("Tactical") + " contributions show the " + italic("active") + " bets. "
        f"Tactical-Market contributed {linked_ta_mkt:+.4f} and Tactical-HML contributed "
        f"{linked_ta_hml:+.4f}. These are the numbers you'd threshold-check to see if "
        "active bets are within acceptable bounds.",
        body_style
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 6: EDGE CASES
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("6. Example 3: Edge Cases", h1_style))
    story.append(hr())

    story.append(Paragraph(
        "Carino linking handles several edge cases that arise in practice. "
        "Understanding these ensures the methodology works robustly.",
        body_style
    ))

    # Edge Case 1: Zero daily return
    story.append(spacer(6))
    story.append(Paragraph("Edge Case A: Zero Daily Return", h2_style))

    story.append(Paragraph(
        "What happens when " + code("r(p,t) = 0") + " on some day? "
        "The formula " + code("k(t) = ln(1+r)/r") + " becomes " + code("0/0") + " — undefined!",
        body_style
    ))

    story.append(Paragraph(
        bold("The fix:") + " We use the mathematical limit. As r approaches 0:<br/><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;ln(1 + r) / r &nbsp; approaches &nbsp; 1<br/><br/>"
        "This can be proven via L'Hopital's rule or Taylor expansion: "
        "ln(1+r) = r - r^2/2 + r^3/3 - ..., so ln(1+r)/r = 1 - r/2 + r^2/3 - ... which "
        "goes to 1 as r goes to 0.<br/><br/>"
        + bold("In code:") + " When |r(p,t)| &lt; some tiny epsilon (e.g., 10^-12), set k(t) = 1.",
        callout_style
    ))

    story.append(spacer(6))
    story.append(Paragraph("Worked example with a zero-return day:", body_style))

    # Worked example
    zero_rets = [0.005, 0.0, -0.003]
    zero_R = geometric_return(zero_rets)
    zero_K = carino_K(zero_R)
    zero_ks = [carino_k(r) for r in zero_rets]
    zero_ws = [k / zero_K for k in zero_ks]

    zero_data = [
        ["Day", "r(p,t)", "k(t)", "w(t)", "Note"],
        ["1", "+0.0050", f"{zero_ks[0]:.6f}", f"{zero_ws[0]:.6f}", "Normal positive day"],
        ["2", "0.0000", f"{zero_ks[1]:.6f}", f"{zero_ws[1]:.6f}", "Zero return: k = 1 (limit)"],
        ["3", "-0.0030", f"{zero_ks[2]:.6f}", f"{zero_ws[2]:.6f}", "Normal negative day"],
    ]
    story.append(make_table(zero_data, col_widths=[35, 65, 80, 80, 200]))
    story.append(spacer(4))
    story.append(Paragraph(
        italic("The zero-return day gets k=1 and a valid linking weight. "
               "The method continues to work seamlessly."),
        caption_style
    ))

    # Edge Case 2: Zero total window return
    story.append(spacer(12))
    story.append(Paragraph("Edge Case B: Zero Total Window Return", h2_style))

    story.append(Paragraph(
        "What if the portfolio returns to exactly its starting value over the window? "
        "Then " + code("R(p) = 0") + " and " + code("K = ln(1+0)/0 = 0/0") + ".",
        body_style
    ))

    story.append(Paragraph(
        bold("Same fix:") + " The limit of ln(1+R)/R as R approaches 0 is 1, so K = 1.<br/><br/>"
        "When K = 1, the linking weights w(t) = k(t)/1 = k(t). The contributions are simply "
        "rescaled by each day's Carino coefficient, and they'll sum to 0 (= R(p)).<br/><br/>"
        + bold("Intuition:") + " If the portfolio went nowhere, the linked contributions from "
        "all factors and residual must net to zero — which is exactly what happens.",
        callout_style
    ))

    story.append(spacer(6))

    # Worked example: returns that cancel out
    cancel_rets = [0.02, -0.01, 0.005, -0.014851]  # Carefully chosen to get R_p ≈ 0
    # Actually compute what the last return needs to be
    prod_3 = (1 + 0.02) * (1 + (-0.01)) * (1 + 0.005)
    last_r = (1.0 / prod_3) - 1  # This makes the total return exactly 0
    cancel_rets = [0.02, -0.01, 0.005, last_r]
    cancel_R = geometric_return(cancel_rets)

    story.append(Paragraph(
        f"Example: r = [+2.00%, -1.00%, +0.50%, {last_r*100:+.4f}%]  gives  "
        f"R(p) = {cancel_R:.2e}  (essentially zero)",
        ParagraphStyle("CenteredFormula", parent=formula_style, fontSize=10)
    ))
    story.append(Paragraph(
        f"K = 1.000000 (by limit), so w(t) = k(t) for all days.",
        ParagraphStyle("CenteredSmall", parent=small_style, alignment=TA_CENTER)
    ))

    # Edge Case 3: Large returns
    story.append(spacer(12))
    story.append(Paragraph("Edge Case C: Large Returns", h2_style))

    story.append(Paragraph(
        "During market stress (2008, 2020 March), daily returns can be 5-10% or more. "
        "The Carino correction becomes more significant:",
        body_style
    ))

    large_data = [
        ["r(p,t)", "k(t)", "Deviation from 1", "Correction Magnitude"],
        ["+0.1%", f"{carino_k(0.001):.6f}", f"{carino_k(0.001)-1:+.6f}", "Negligible"],
        ["+1.0%", f"{carino_k(0.01):.6f}", f"{carino_k(0.01)-1:+.6f}", "Tiny"],
        ["+5.0%", f"{carino_k(0.05):.6f}", f"{carino_k(0.05)-1:+.6f}", "Noticeable"],
        ["+10.0%", f"{carino_k(0.10):.6f}", f"{carino_k(0.10)-1:+.6f}", "Material"],
        ["-5.0%", f"{carino_k(-0.05):.6f}", f"{carino_k(-0.05)-1:+.6f}", "Noticeable"],
        ["-10.0%", f"{carino_k(-0.10):.6f}", f"{carino_k(-0.10)-1:+.6f}", "Material"],
        ["-20.0%", f"{carino_k(-0.20):.6f}", f"{carino_k(-0.20)-1:+.6f}", "Significant"],
    ]
    story.append(make_table(large_data, col_widths=[70, 90, 110, 130]))

    story.append(spacer(6))
    story.append(Paragraph(
        bold("Takeaway:") + " For typical daily returns (under 2%), Carino linking is a small "
        "adjustment. But it matters over long windows (where the cumulative return can be "
        "large) and during stress periods. The methodology is " + bold("always exact")
        + " regardless of return magnitude.",
        insight_style
    ))

    # Edge Case 4: Negative total return
    story.append(spacer(12))
    story.append(Paragraph("Edge Case D: Negative Total Return", h2_style))

    story.append(Paragraph(
        "When R(p) &lt; 0, the formula still works perfectly. "
        "ln(1 + R(p)) is defined as long as R(p) &gt; -1 (i.e., the portfolio hasn't lost "
        "more than 100%). For a negative R(p):",
        body_style
    ))

    neg_examples = [
        ["R(p)", "ln(1+R(p))", "K = ln(1+R)/R", "Valid?"],
        ["-5%", f"{math.log(0.95):.6f}", f"{carino_K(-0.05):.6f}", "Yes"],
        ["-20%", f"{math.log(0.80):.6f}", f"{carino_K(-0.20):.6f}", "Yes"],
        ["-50%", f"{math.log(0.50):.6f}", f"{carino_K(-0.50):.6f}", "Yes"],
        ["-90%", f"{math.log(0.10):.6f}", f"{carino_K(-0.90):.6f}", "Yes"],
        ["-100%", "undefined (-inf)", "undefined", "No (total loss)"],
    ]
    story.append(make_table(neg_examples, col_widths=[60, 100, 120, 60]))

    story.append(spacer(4))
    story.append(Paragraph(
        italic("K increases as R(p) becomes more negative, which amplifies the linking "
               "weights. The math handles this gracefully as long as R(p) > -1."),
        caption_style
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 7: DIFFERENT WINDOW SIZES
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("7. Carino Linking Across Different Window Sizes", h1_style))
    story.append(hr())

    story.append(Paragraph(
        "In the portfolio monitor, the same Carino linking formula is applied to each "
        "of the five trailing windows. The window size affects how large the cumulative "
        "return R(p) becomes, which in turn affects the magnitude of the Carino correction.",
        body_style
    ))

    story.append(spacer(6))
    story.append(Paragraph("Window Definitions (Trailing)", h2_style))

    window_data = [
        ["Window", "End Date", "Start Date", "Typical |R(p)|", "Carino Correction Size"],
        ["Daily", "t", "t", "0-3%", "Negligible (k = K, w = 1)"],
        ["Monthly", "t", "t - 1 month + 1 day", "1-8%", "Small but measurable"],
        ["Quarterly", "t", "t - 3 months + 1 day", "2-15%", "Moderate"],
        ["Annual", "t", "t - 1 year + 1 day", "5-40%", "Significant"],
        ["3-Year", "t", "t - 3 years + 1 day", "10-100%+", "Large and essential"],
    ]
    story.append(make_table(window_data, col_widths=[65, 55, 120, 85, 150]))

    story.append(spacer(8))
    story.append(Paragraph(
        bold("For the daily window") + " (single day), Carino linking is trivially exact — "
        "there's only one day, so k(t) = K, w(t) = 1, and the linked contribution equals "
        "the raw daily contribution. No correction is needed.",
        body_style
    ))

    story.append(Paragraph(
        bold("For longer windows") + ", the correction grows. Over a year with R(p) = +20%, "
        f"K = {carino_K(0.20):.4f}. Over 3 years with R(p) = +60%, "
        f"K = {carino_K(0.60):.4f}. The linking weights deviate further from 1, and "
        "simple summation error grows to multiple percentage points.",
        body_style
    ))

    story.append(spacer(8))
    story.append(Paragraph("Impact by Window Length (Simulated)", h2_style))

    story.append(Paragraph(
        "To illustrate how the simple-sum error grows with window length, here's a "
        "simulation using a portfolio with average daily return of +0.04% and daily "
        "volatility of 1%:",
        body_style
    ))

    # Simulation
    np.random.seed(123)
    sim_daily = np.random.normal(0.0004, 0.01, 756)  # ~3 years of data

    window_lengths = [1, 21, 63, 252, 756]
    window_names = ["Daily (1d)", "Monthly (21d)", "Quarterly (63d)", "Annual (252d)", "3-Year (756d)"]

    sim_results = [
        ["Window", "Days", "R(p) Geometric", "Simple Sum Error", "Error (bps)"],
    ]

    for wl, wn in zip(window_lengths, window_names):
        rets = sim_daily[:wl].tolist()
        R_geo = geometric_return(rets)
        simple_sum = sum(rets)
        error = simple_sum - R_geo
        sim_results.append([
            wn,
            str(wl),
            f"{R_geo:+.4%}",
            f"{error:+.6f}",
            f"{error * 10000:+.1f}",
        ])

    t = make_table(sim_results, col_widths=[100, 45, 100, 110, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (3, 1), (4, 1), SOFT_GREEN_BG),  # Daily: green (no error)
        ('BACKGROUND', (3, 4), (4, 4), SOFT_ORANGE_BG),  # Annual: orange
        ('BACKGROUND', (3, 5), (4, 5), SOFT_RED_BG),     # 3-Year: red
    ]))
    story.append(t)

    story.append(spacer(6))
    story.append(Paragraph(
        bold("Key insight:") + " The simple-sum error is essentially zero for daily windows, "
        "small for monthly, but grows to " + bold("dozens of basis points") + " for annual "
        "and " + bold("hundreds of basis points") + " for 3-year windows. This is exactly "
        "the range where threshold monitoring operates, making Carino linking essential "
        "for accurate breach detection.",
        insight_style
    ))

    story.append(spacer(12))
    story.append(Paragraph("Same Formula, Different Windows", h2_style))

    story.append(Paragraph(
        "A beautiful property of Carino linking: " + bold("the same formula works identically "
        "for any window size") + ". Whether you're linking 1 day or 756 days:",
        body_style
    ))

    steps_summary = [
        "1. Gather all daily portfolio returns in the window",
        "2. Compute R(p) = geometric product - 1",
        "3. Compute K = ln(1+R(p)) / R(p)",
        "4. For each day: k(t) = ln(1+r(p,t)) / r(p,t),  w(t) = k(t) / K",
        "5. For each (layer, factor): C(l,f) = SUM of w(t) x e(l,f,t) x r(f,t)",
    ]
    for s in steps_summary:
        story.append(Paragraph(s, body_indent_style))

    story.append(spacer(6))
    story.append(Paragraph(
        "The only difference is how many days t you sum over. The methodology "
        "scales naturally from 1 day to 3+ years.",
        small_style
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 8: SUMMARY & KEY PROPERTIES
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("8. Summary & Key Properties", h1_style))
    story.append(hr())

    story.append(Paragraph("What Carino Linking Gives You", h2_style))

    props = [
        (bold("Exact Additivity") + " — Linked contributions across all layers, factors, "
         "and residual sum to " + italic("exactly") + " the geometric portfolio return. "
         "No unexplained residual from the linking process itself."),

        (bold("Works for Any Window") + " — Daily, monthly, quarterly, annual, 3-year, "
         "or any custom period. Same formula, same exactness guarantee."),

        (bold("Handles All Return Regimes") + " — Positive, negative, zero, large, small. "
         "The only requirement is R(p) > -100% (the portfolio hasn't been completely wiped out)."),

        (bold("Preserves Factor Structure") + " — Each (layer, factor) pair gets its own "
         "linked contribution. You can compare contributions across layers and factors "
         "within a window, or track how a single contribution evolves across different windows."),

        (bold("Smooth & Stable") + " — The linking weights change gradually. A small change "
         "in one day's return produces a small change in linked contributions. No discontinuities "
         "or numerical instabilities."),
    ]

    for i, prop in enumerate(props):
        bg = SOFT_BLUE_BG if i % 2 == 0 else SOFT_GREEN_BG
        bc = BORDER_BLUE if i % 2 == 0 else ACCENT_GREEN
        story.append(Paragraph(
            f"{i+1}. {prop}",
            ParagraphStyle(f"Prop{i}", parent=body_style,
                          backColor=bg, borderColor=bc,
                          borderWidth=1, borderPadding=10,
                          spaceBefore=4, spaceAfter=4,
                          leftIndent=10, rightIndent=10)
        ))

    story.append(spacer(12))
    story.append(Paragraph("The Complete Formula on One Card", h2_style))

    summary_formula = (
        bold("Given:") + " Daily portfolio returns {r(p,t)}, exposures {e(l,f,t)}, "
        "factor returns {r(f,t)} for t = 1..N<br/><br/>" +

        bold("Compute:") + "<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;R(p) = PRODUCT(1 + r(p,t)) - 1"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "<i>[geometric total return]</i><br/>"

        "&nbsp;&nbsp;&nbsp;&nbsp;k(t) = ln(1 + r(p,t)) / r(p,t)"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "<i>[per-day coefficient; = 1 if r(p,t) = 0]</i><br/>"

        "&nbsp;&nbsp;&nbsp;&nbsp;K &nbsp;&nbsp; = ln(1 + R(p)) / R(p)"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "<i>[window coefficient; = 1 if R(p) = 0]</i><br/>"

        "&nbsp;&nbsp;&nbsp;&nbsp;w(t) = k(t) / K"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "&nbsp;&nbsp;&nbsp;&nbsp;"
        "<i>[linking weight]</i><br/><br/>" +

        bold("Result:") + "<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;C(l,f) = SUM_t [ w(t) x e(l,f,t) x r(f,t) ]"
        "&nbsp;&nbsp;&nbsp;&nbsp;"
        "<i>[linked contribution per layer-factor]</i><br/><br/>" +

        bold("Property:") + " &nbsp; SUM(all C(l,f)) + C(residual)  =  R(p) &nbsp;&nbsp; " +
        green("(exact)")
    )

    story.append(Paragraph(
        summary_formula,
        ParagraphStyle("SummaryCard", parent=body_style,
                      fontSize=10, leading=17,
                      backColor=colors.HexColor("#f0f4ff"),
                      borderColor=ACCENT_BLUE,
                      borderWidth=2, borderPadding=16,
                      borderRadius=6,
                      fontName="Courier",
                      leftIndent=10, rightIndent=10)
    ))

    story.append(spacer(16))
    story.append(Paragraph("How It Fits in the Portfolio Monitor", h2_style))

    story.append(Paragraph(
        "In the monitoring system, Carino linking is the bridge between raw daily data "
        "and threshold checks:",
        body_style
    ))

    flow_data = [
        ["Stage", "Input", "Output"],
        ["1. Load", "exposures.csv + factor_returns.csv", "Daily exposures & returns per portfolio"],
        ["2. Compute", "Daily data + window definition", "Per-day contributions c(l,f,t)"],
        ["3. Link", "Daily contributions + portfolio returns", "Carino-linked C(l,f) per window"],
        ["4. Threshold", "Linked C(l,f) + thresholds.yaml", "Breach flags per (portfolio, layer, factor, window)"],
        ["5. Report", "Breach flags across all portfolios", "Summary + per-portfolio detail reports"],
    ]
    t = make_table(flow_data, col_widths=[60, 195, 215])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 3), (-1, 3), SOFT_GREEN_BG),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
    ]))
    story.append(t)

    story.append(spacer(6))
    story.append(Paragraph(
        italic("Stage 3 (highlighted) is where Carino linking operates. "
               "It transforms daily contributions into window-level linked "
               "contributions that can be meaningfully compared against thresholds."),
        caption_style
    ))

    story.append(spacer(20))
    story.append(HRFlowable(width="60%", thickness=3, color=ACCENT_BLUE,
                            spaceBefore=10, spaceAfter=10))
    story.append(Paragraph(
        italic("Carino linking: the mathematically exact way to attribute "
               "multi-period returns to their factor sources."),
        ParagraphStyle("Closing", parent=subtitle_style, fontSize=11, textColor=ACCENT_TEAL)
    ))

    # Build
    doc.build(story)
    print(f"PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    build_pdf()
