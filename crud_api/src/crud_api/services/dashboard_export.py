# Exports du tableau de bord : PDF (reportlab) et Excel (openpyxl, graphiques natifs)
# Les deux partent du rapport JSON produit par dashboard_service.compute() : un seul calcul, trois sorties.
import re
from datetime import date
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from crud_api.config import get_settings
from crud_api.services.dashboard_service import Report, fmt

PINE = colors.HexColor("#1e3a38")
HEAD = colors.HexColor("#a9c4ee")
SOFT = colors.HexColor("#eef1ea")
LINE = colors.HexColor("#9aa9a3")
OK = colors.HexColor("#3f7d3a")
BAD = colors.HexColor("#c8501f")
PRIO = {"Haute": colors.HexColor("#c0392b"), "Moyenne": colors.HexColor("#d9822b"), "Basse": colors.HexColor("#3f7d3a")}
SERIES = [colors.HexColor("#1e3a38"), colors.HexColor("#c98a1b"), colors.HexColor("#5b8fd6")]

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ----------------------------------------------------------------- formats communs
def _fr(v: float, nd: int = 1) -> str:
    s = f"{v:,.{nd}f}".replace(",", "\u00a0").replace(".", ",")
    return s.rstrip("0").rstrip(",") if "," in s else s


def _signed(v: float | None) -> str:
    if v is None:
        return "—"
    if v == 0:
        return "0"
    return ("+" if v > 0 else "−") + _fr(abs(v))


def _objective(o: dict | None) -> str:
    if not o:
        return "—"
    if o["op"] == "between":
        return f"{_fr(o['min'])}-{_fr(o['max'])} %"
    return f"{'≥' if o['op'] == '>=' else '≤'} {_fr(o['value'])}"


def _value(row: dict) -> str:
    return _fr(row["value"]) + (" %" if row["unit"] == "%" else "")


def _cell_text(key: str, v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, str) and _ISO.match(v):
        return date.fromisoformat(v).strftime("%d/%m/%Y")
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return _fr(v, 3 if key in ("stock", "seuil", "manque") else 1)
    return fmt(v)


def _month_label(iso: str) -> str:
    y, m = iso.split("-")
    return f"{m}/{y[2:]}"


def _title(report: Report) -> str:
    name = get_settings().structure_name.strip()
    return "Tableau de bord du parc informatique" + (f" — {name}" if name else "")


# ----------------------------------------------------------------- PDF
_base = dict(fontName="Helvetica", fontSize=8.5, leading=11)
S_TXT = ParagraphStyle("txt", **_base)
S_CELL_R = ParagraphStyle("cellr", **{**_base, "alignment": 2})
S_HEAD = ParagraphStyle("head", **{**_base, "fontName": "Helvetica-Bold", "alignment": TA_CENTER})
S_SEC = ParagraphStyle("sec", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 11.5, "leading": 14,
                                 "textColor": PINE, "spaceBefore": 10, "spaceAfter": 4})
S_NOTE = ParagraphStyle("note", **{**_base, "fontName": "Helvetica-Oblique", "fontSize": 7.5, "textColor": colors.HexColor("#4a5a54")})
S_TITLE = ParagraphStyle("title", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 16, "leading": 20,
                                     "textColor": colors.white, "alignment": TA_CENTER})
S_SUB = ParagraphStyle("sub", **{**_base, "textColor": colors.white, "alignment": TA_CENTER})


def _safe(value: Any) -> str:
    """Texte compatible avec la police standard (WinAnsi), puis echappe pour Paragraph."""
    s = "" if value is None else str(value)
    for a, b in (("≥", ">="), ("≤", "<="), ("−", "-"), ("→", "->")):  # absents de WinAnsi
        s = s.replace(a, b)
    return escape(s.encode("cp1252", errors="replace").decode("cp1252"))


def _p(text: Any, style: ParagraphStyle = S_TXT) -> Paragraph:
    return Paragraph(_safe(text), style)


def _grid(data: list[list], widths: list[float], extra: list | None = None, header: bool = True) -> Table:
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD))
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def _widths(n: int, total: float, first: float = 0.34) -> list[float]:
    if n == 1:
        return [total]
    rest = total * (1 - first) / (n - 1)
    return [total * first] + [rest] * (n - 1)


def _pdf_table(tbl: dict, width: float) -> list:
    cols = tbl["columns"]
    rows = [[_p(c["label"], S_HEAD) for c in cols]]
    for r in tbl["rows"]:
        rows.append([_p(_cell_text(c["key"], r.get(c["key"])), S_CELL_R if c["align"] == "right" else S_TXT) for c in cols])
    extra: list = []
    if tbl.get("total"):
        t = tbl["total"]
        bold = ParagraphStyle("b", **{**_base, "fontName": "Helvetica-Bold"})
        boldr = ParagraphStyle("br", **{**_base, "fontName": "Helvetica-Bold", "alignment": 2})
        rows.append([_p(_cell_text(c["key"], t.get(c["key"])) if t.get(c["key"]) is not None else "",
                        boldr if c["align"] == "right" else bold) for c in cols])
        extra.append(("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), HEAD))
    out: list = [Paragraph(_safe(tbl["title"]), S_SEC)]
    if not tbl["rows"]:
        out.append(_p("Aucune donnée à afficher.", S_NOTE))
    else:
        out.append(_grid(rows, _widths(len(cols), width), extra))
    if tbl.get("note"):
        out += [Spacer(1, 2), _p(fmt(tbl["note"]), S_NOTE)]
    return [KeepTogether(out)]


def _chart(chart: dict, labels: list[str], width: float) -> Drawing:
    height = 6.2 * cm
    d = Drawing(width, height + 0.9 * cm)
    n = len(labels)
    step = max(1, -(-n // 12))  # au plus ~12 libelles sur l'axe
    names = [_month_label(lab) if i % step == 0 else "" for i, lab in enumerate(labels)]
    vals = [tuple(s["values"]) for s in chart["series"]]
    top = max((max(v) for v in vals if v), default=0)
    if chart.get("band"):
        top = max(top, chart["band"][1])
    top = max(top, 1)
    c = VerticalBarChart() if chart["kind"] == "bar" else HorizontalLineChart()
    c.x, c.y, c.width, c.height = 1.3 * cm, 0.9 * cm, width - 1.8 * cm, height - 0.6 * cm
    c.data = vals
    c.categoryAxis.categoryNames = names
    c.categoryAxis.labels.fontSize = 7
    c.categoryAxis.labels.fontName = c.valueAxis.labels.fontName = "Helvetica"
    c.categoryAxis.labels.angle = 0
    c.valueAxis.labels.fontSize = 7
    c.valueAxis.valueMin = 0
    c.valueAxis.valueMax = top * 1.15
    c.valueAxis.visibleGrid = True
    c.valueAxis.gridStrokeColor = colors.HexColor("#d5dbd4")
    for i in range(len(vals)):
        if chart["kind"] == "bar":
            c.bars[i].fillColor = SERIES[i % len(SERIES)]
        else:
            c.lines[i].strokeColor = SERIES[i % len(SERIES)]
            c.lines[i].strokeWidth = 1.8
    if chart["kind"] == "bar":
        c.barSpacing, c.groupSpacing = 0.5, 6
    if chart.get("band"):  # bande de l'objectif (derriere la courbe)
        lo, hi = chart["band"]
        scale = c.height / (top * 1.15)
        d.add(Rect(c.x, c.y + lo * scale, c.width, (hi - lo) * scale, fillColor=colors.HexColor("#dcebd9"),
                   strokeColor=None))
    d.add(c)
    x = 1.3 * cm
    for i, s in enumerate(chart["series"]):  # legende
        d.add(Rect(x, height + 0.2 * cm, 0.3 * cm, 0.3 * cm, fillColor=SERIES[i % len(SERIES)], strokeColor=None))
        d.add(String(x + 0.45 * cm, height + 0.22 * cm, _safe(s["name"]).replace("&amp;", "&"), fontSize=7.5, fontName="Helvetica"))
        x += 0.45 * cm + 0.17 * cm * len(s["name"]) + 0.5 * cm
    return d


def build_pdf(report: Report) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                            title=_title(report), author="Parc informatique")
    width = A4[0] - 3.2 * cm
    tables = {t["code"]: t for t in report["tables"]}
    story: list = []

    banner = Table([[_p(_title(report), S_TITLE)],
                    [_p(f"Édité le {date.fromisoformat(report['generated_at']).strftime('%d/%m/%Y')} · "
                        f"évolution sur {report['months']} mois", S_SUB)]], colWidths=[width])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PINE), ("TOPPADDING", (0, 0), (-1, -1), 7),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [banner]

    # vue d'ensemble
    story.append(Paragraph("Vue d’ensemble du parc", S_SEC))
    head = [_p(h, S_HEAD) for h in ("Indicateur", "Valeur", "Objectif", "Écart", "Statut")]
    data = [head]
    for r in report["overview"]:
        if r["tone"] == "none":
            statut = _p(r["statut"], S_HEAD)
        else:
            color = "#3f7d3a" if r["tone"] == "ok" else "#c8501f"
            statut = Paragraph(f'<font color="{color}"><b>{_safe(r["statut"])}</b></font>', S_HEAD)
        data.append([_p(fmt(r["label"])), _p(_value(r), S_CELL_R), _p(_objective(r["objective"]), S_CELL_R),
                     _p(_signed(r["ecart"]), S_CELL_R), statut])
    story.append(_grid(data, _widths(5, width, 0.38)))

    # alertes
    story.append(Paragraph("Alertes et actions recommandées", S_SEC))
    if report["alerts"]:
        data = [[_p(h, S_HEAD) for h in ("Priorité", "Alerte", "Action recommandée")]]
        for a in report["alerts"]:
            col = PRIO[a["priorite"]].hexval()[2:]
            data.append([Paragraph(f'<font color="#{col}"><b>{a["priorite"]}</b></font>', S_HEAD),
                         _p(fmt(a["alerte"])), _p(fmt(a["action"]))])
        story.append(_grid(data, [width * 0.15, width * 0.42, width * 0.43]))
    else:
        story.append(_p("Aucune alerte : tous les indicateurs sont dans leurs objectifs.", S_NOTE))

    # tableaux
    groups = [
        ("Répartition du parc", ["categories", "etats", "ages", "provenances"]),
        ("Détention et dossiers d’attribution", ["services", "detentions", "dossiers"]),
        ("Consommables et licences", ["consommables", "licences", "licences_echeance"]),
    ]
    for _heading, codes in groups:
        for code in codes:
            story += _pdf_table(tables[code], width)

    # evolution : graphiques uniquement pour les series temporelles
    story += [PageBreak(), Paragraph("Évolution dans le temps", S_SEC)]
    labels = report["evolution"]["labels"]
    for ch in report["evolution"]["charts"]:
        block = [_p(ch["title"], ParagraphStyle("ct", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 9.5, "leading": 12})),
                 _chart(ch, labels, width)]
        if ch.get("note"):
            block.append(_p(ch["note"], S_NOTE))
        story += [KeepTogether(block + [Spacer(1, 6)])]

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#4a5a54"))
        canvas.drawString(1.6 * cm, 0.8 * cm, _safe(_title(report)).replace("&amp;", "&"))
        canvas.drawRightString(A4[0] - 1.6 * cm, 0.8 * cm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ----------------------------------------------------------------- Excel
X_HEAD = PatternFill("solid", fgColor="A9C4EE")
X_BAND = PatternFill("solid", fgColor="1E3A38")
X_TOTAL = PatternFill("solid", fgColor="DCE6F5")
X_TONE = {"ok": Font(bold=True, color="3F7D3A"), "bad": Font(bold=True, color="C8501F")}
X_PRIO = {"Haute": "C0392B", "Moyenne": "D9822B", "Basse": "3F7D3A"}
THIN = Side(style="thin", color="9AA9A3")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
_DEC = {"part": "0.0", "stock": "#,##0.###", "seuil": "#,##0.###", "manque": "#,##0.###", "anciennete": "0.0"}


def _xl_value(key: str, v: Any):
    if isinstance(v, str) and _ISO.match(v):
        return date.fromisoformat(v)
    if isinstance(v, dict):
        return fmt(v)
    return v


def _xl_header(ws, row: int, labels: list[str]) -> None:
    for i, lab in enumerate(labels, start=1):
        c = ws.cell(row=row, column=i, value=lab)
        c.fill, c.font, c.border = X_HEAD, Font(bold=True), BOX
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _xl_section(ws, row: int, title: str) -> int:
    ws.cell(row=row, column=1, value=title).font = Font(bold=True, size=12, color="1E3A38")
    return row + 1


def _xl_table(ws, row: int, tbl: dict) -> int:
    row = _xl_section(ws, row, tbl["title"])
    cols = tbl["columns"]
    _xl_header(ws, row, [c["label"] for c in cols])
    row += 1
    for r in tbl["rows"] + ([tbl["total"]] if tbl.get("total") else []):
        is_total = r is tbl.get("total")
        for i, c in enumerate(cols, start=1):
            v = _xl_value(c["key"], r.get(c["key"]))
            cell = ws.cell(row=row, column=i, value=v)
            cell.border = BOX
            if isinstance(v, date):
                cell.number_format = "dd/mm/yyyy"
            elif isinstance(v, float):
                cell.number_format = _DEC.get(c["key"], "#,##0.0")
            elif isinstance(v, int):
                cell.number_format = "#,##0"
            cell.alignment = Alignment(horizontal="left" if c["align"] == "left" else "right")
            if is_total:
                cell.fill, cell.font = X_TOTAL, Font(bold=True)
        row += 1
    if not tbl["rows"]:
        ws.cell(row=row, column=1, value="Aucune donnée à afficher.").font = Font(italic=True, color="666666")
        row += 1
    if tbl.get("note"):
        ws.cell(row=row, column=1, value=fmt(tbl["note"])).font = Font(italic=True, size=9, color="666666")
        row += 1
    return row + 1


def _xl_sheet(wb: Workbook, title: str, report: Report, heading: str | None = None, first: bool = False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.sheet_view.showGridLines = False
    ws["A1"] = heading or _title(report)
    ws["A1"].font = Font(bold=True, size=15, color="FFFFFF")
    ws["A1"].fill = X_BAND
    ws.merge_cells("A1:F1")
    ws.row_dimensions[1].height = 26
    ws["A2"] = f"Édité le {date.fromisoformat(report['generated_at']).strftime('%d/%m/%Y')}"
    ws["A2"].font = Font(italic=True, color="666666")
    return ws


def _xl_widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build_xlsx(report: Report) -> bytes:
    wb = Workbook()
    tables = {t["code"]: t for t in report["tables"]}

    # --- Synthese : vue d'ensemble + alertes
    ws = _xl_sheet(wb, "Synthèse", report, first=True)
    row = _xl_section(ws, 4, "Vue d’ensemble du parc")
    _xl_header(ws, row, ["Indicateur", "Valeur", "Objectif", "Écart", "Statut"])
    row += 1
    for r in report["overview"]:
        pct = r["unit"] == "%"
        vals = [fmt(r["label"]), r["value"], _objective(r["objective"]), r["ecart"], r["statut"]]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=i, value=v)
            c.border = BOX
            c.alignment = Alignment(horizontal="left" if i == 1 else "right" if i < 5 else "center")
        ws.cell(row=row, column=2).number_format = '0.0" %"' if pct else ("#,##0.0" if isinstance(r["value"], float) and not float(r["value"]).is_integer() else "#,##0")
        ws.cell(row=row, column=4).number_format = '+0.0;-0.0;0' if isinstance(r["ecart"], float) else '+0;-0;0'
        if r["tone"] in X_TONE:
            ws.cell(row=row, column=5).font = X_TONE[r["tone"]]
        row += 1
    _xl_widths(ws, [38, 16, 18, 12, 12])

    # --- Alertes (feuille a part : colonnes de texte larges)
    ws = _xl_sheet(wb, "Alertes", report)
    row = _xl_section(ws, 4, "Alertes et actions recommandées")
    _xl_header(ws, row, ["Priorité", "Alerte", "Action recommandée"])
    row += 1
    for a in report["alerts"] or [None]:
        vals = ["", "Aucune alerte.", ""] if a is None else [a["priorite"], fmt(a["alerte"]), fmt(a["action"])]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=i, value=v)
            c.border, c.alignment = BOX, Alignment(wrap_text=True, vertical="top", horizontal="center" if i == 1 else "left")
        if a:
            ws.cell(row=row, column=1).font = Font(bold=True, color=X_PRIO[a["priorite"]])
        row += 1
    _xl_widths(ws, [12, 70, 60])

    # --- Repartitions / Organisation / Stocks et licences
    for title, codes, widths in [
        ("Répartitions", ["categories", "etats", "ages", "provenances"], [30, 14, 14, 14, 14, 16]),
        ("Détention", ["services", "detentions", "dossiers"], [34, 30, 22, 16, 18, 12]),
        ("Stocks et licences", ["consommables", "licences", "licences_echeance"], [36, 18, 16, 16, 16, 12]),
    ]:
        ws = _xl_sheet(wb, title, report)
        row = 4
        for code in codes:
            row = _xl_table(ws, row, tables[code])
        _xl_widths(ws, widths)

    # --- Evolution : tableau de donnees + graphiques natifs (donnees temporelles uniquement)
    ws = _xl_sheet(wb, "Évolution", report)
    labels = report["evolution"]["labels"]
    row = 4
    anchor_col = 8
    chart_row = 4
    for ch in report["evolution"]["charts"]:
        row = _xl_section(ws, row, ch["title"])
        _xl_header(ws, row, ["Mois"] + [s["name"] for s in ch["series"]])
        head_row = row
        for i, lab in enumerate(labels, start=1):
            ws.cell(row=row + i, column=1, value=lab).border = BOX
            for j, s in enumerate(ch["series"], start=2):
                c = ws.cell(row=row + i, column=j, value=s["values"][i - 1])
                c.border = BOX
                c.number_format = "0.0" if ch["unit"] == "%" else "#,##0.###"
        last = row + len(labels)
        chart = BarChart() if ch["kind"] == "bar" else LineChart()
        chart.title, chart.height, chart.width = ch["title"], 7.5, 16
        chart.add_data(Reference(ws, min_col=2, max_col=1 + len(ch["series"]), min_row=head_row, max_row=last),
                       titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=head_row + 1, max_row=last))
        chart.y_axis.delete = chart.x_axis.delete = False
        if ch["unit"] == "%":
            chart.y_axis.scaling.min, chart.y_axis.scaling.max = 0, 100
        ws.add_chart(chart, f"{get_column_letter(anchor_col)}{chart_row}")
        chart_row += 17
        row = last + 3
    _xl_widths(ws, [14, 22, 22, 22, 4, 4, 4])
    ws.freeze_panes = "A4"

    out = BytesIO()
    wb.save(out)
    return out.getvalue()
