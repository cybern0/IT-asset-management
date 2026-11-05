# Exports de la Repartition du materiel : PDF (reportlab) et Excel (openpyxl).
# Ils partent du meme rapport JSON que l'ecran (dashboard_service.repartition) : un seul calcul, trois sorties.
from datetime import date
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from crud_api.config import get_settings
from crud_api.services.dashboard_export import (
    BOX, PINE, S_NOTE, S_SEC, S_SUB, S_TITLE, S_TXT, S_CELL_R, S_HEAD, X_BAND, X_HEAD, X_TOTAL, _base, _grid, _p, _xl_header,
)
from reportlab.lib.styles import ParagraphStyle

Rep = dict[str, Any]
S_BOLD = ParagraphStyle("repb", **{**_base, "fontName": "Helvetica-Bold"})
S_BOLD_R = ParagraphStyle("repbr", **{**_base, "fontName": "Helvetica-Bold", "alignment": 2})


def _title() -> str:
    name = get_settings().structure_name.strip()
    return "Répartition du matériel" + (f" — {name}" if name else "")


def _date(rep: Rep) -> str:
    return date.fromisoformat(rep["generated_at"]).strftime("%d/%m/%Y")


def _used(rep: Rep) -> list[dict]:
    """Categories qui ont au moins un materiel detenu (comme l'ecran)."""
    return [c for c in rep["categories"] if c["nb_materiels"] > 0]


def _sentence(rep: Rep) -> str:
    t = rep["total"]
    return f"Matériel actuellement détenu par service : {t['nb_materiels']} matériels, {t['nb_agents_detenteurs']} agents détenteurs."


# ----------------------------------------------------------------- PDF
def build_pdf(rep: Rep) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.4 * cm, title=_title())
    width = landscape(A4)[0] - 2.4 * cm
    used = _used(rep)

    band = Table([[_p(_title(), S_TITLE)], [_p(f"Édité le {_date(rep)}", S_SUB)]], colWidths=[width])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PINE), ("TOPPADDING", (0, 0), (-1, -1), 5),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story: list = [band, Spacer(1, 6), _p(_sentence(rep))]

    # --- par categorie du dictionnaire
    story.append(_p("Par catégorie du dictionnaire", S_SEC))
    rows = [[_p("Catégorie", S_HEAD), _p("Matériels", S_HEAD), _p("Agents", S_HEAD)]]
    rows += [[_p(c["libelle"]), _p(c["nb_materiels"], S_CELL_R), _p(c["nb_agents"], S_CELL_R)] for c in rep["categories"]]
    story.append(_grid(rows, [width * 0.5, width * 0.15, width * 0.15]))

    # --- par service et par categorie
    story.append(_p("Par service et par catégorie", S_SEC))
    head = [_p("Service", S_HEAD), _p("Agents", S_HEAD)] + [_p(c["libelle"], S_HEAD) for c in used] + [_p("Total", S_HEAD)]
    rows = [head]
    for s in rep["services"]:
        rows.append([_p(s["nom"]), _p(f"{s['nb_agents_detenteurs']}/{s['nb_agents']}", S_CELL_R)]
                    + [_p(s["par_categorie"].get(c["code"], {}).get("nb_materiels") or "—", S_CELL_R) for c in used]
                    + [_p(s["nb_materiels"], S_BOLD_R)])
    total = rep["total"]
    rows.append([_p("Total", S_BOLD), _p(total["nb_agents_detenteurs"], S_BOLD_R)]
                + [_p(c["nb_materiels"], S_BOLD_R) for c in used] + [_p(total["nb_materiels"], S_BOLD_R)])
    first, narrow = 5.2 * cm, 1.9 * cm
    cat_w = min(3.2 * cm, max(1.3 * cm, (width - first - 2 * narrow) / max(1, len(used))))
    widths = [first, narrow] + [cat_w] * len(used) + [narrow]
    scale = min(1.0, width / sum(widths))  # beaucoup de categories : les colonnes se resserrent
    story.append(_grid(rows, [w * scale for w in widths],
                       [("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), colors.HexColor("#a9c4ee"))]))
    story += [Spacer(1, 4), _p("Agents : détenteurs / total du service. Chaque cellule compte les matériels en cours de détention.", S_NOTE)]

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#4a5a54"))
        canvas.drawString(1.2 * cm, 0.7 * cm, f"{_title()} — {_date(rep)}".encode("cp1252", "replace").decode("cp1252"))
        canvas.drawRightString(landscape(A4)[0] - 1.2 * cm, 0.7 * cm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ----------------------------------------------------------------- Excel
def _head(ws, row: int, labels: list[str]) -> None:
    _xl_header(ws, row, labels)


def _sheet(wb: Workbook, title: str, rep: Rep, first: bool = False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.sheet_view.showGridLines = False
    ws["A1"] = _title()
    ws["A1"].font = Font(bold=True, size=15, color="FFFFFF")
    ws["A1"].fill = X_BAND
    ws.merge_cells("A1:F1")
    ws.row_dimensions[1].height = 26
    ws["A2"] = f"Édité le {_date(rep)}"
    ws["A2"].font = Font(italic=True, color="666666")
    return ws


def _put(ws, row: int, values: list, *, bold: bool = False, fill=None) -> None:
    for i, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.border = BOX
        c.alignment = Alignment(horizontal="left" if i == 1 else "right")
        if isinstance(v, int):
            c.number_format = "#,##0"
        if bold:
            c.font = Font(bold=True)
        if fill is not None:
            c.fill = fill


def build_xlsx(rep: Rep) -> bytes:
    wb = Workbook()
    used = _used(rep)
    total = rep["total"]

    # --- Par service et par categorie (le tableau principal de l'ecran)
    ws = _sheet(wb, "Par service", rep, first=True)
    ws["A3"] = _sentence(rep)
    ws["A3"].font = Font(size=10)
    _head(ws, 5, ["Service", "Agents détenteurs", "Agents du service"] + [c["libelle"] for c in used] + ["Total matériels"])
    row = 6
    for s in rep["services"]:
        _put(ws, row, [s["nom"], s["nb_agents_detenteurs"], s["nb_agents"]]
             + [s["par_categorie"].get(c["code"], {}).get("nb_materiels", 0) for c in used] + [s["nb_materiels"]])
        row += 1
    last = row - 1
    # ligne de total : formules, pour que le tableau reste juste si on le modifie dans Excel
    n = 3 + len(used) + 1
    _put(ws, row, ["Total", total["nb_agents_detenteurs"], sum(s["nb_agents"] for s in rep["services"])]
         + [f"=SUM({get_column_letter(i)}6:{get_column_letter(i)}{last})" for i in range(4, n + 1)], bold=True, fill=X_TOTAL)
    ws.cell(row=row, column=2).value = f"=SUM(B6:B{last})" if last >= 6 else 0
    ws.cell(row=row, column=3).value = f"=SUM(C6:C{last})" if last >= 6 else 0
    ws.cell(row=row + 2, column=1, value="Chaque cellule compte les matériels en cours de détention.").font = Font(italic=True, size=9, color="666666")
    ws.freeze_panes = "B6"
    ws.column_dimensions["A"].width = 34
    for i in range(2, n + 1):
        ws.column_dimensions[get_column_letter(i)].width = 16
    ws.row_dimensions[5].height = 32

    # --- Par categorie du dictionnaire
    ws = _sheet(wb, "Par catégorie", rep)
    _head(ws, 4, ["Catégorie", "Matériels", "Agents"])
    for i, c in enumerate(rep["categories"], start=5):
        _put(ws, i, [c["libelle"], c["nb_materiels"], c["nb_agents"]])
    end = 4 + len(rep["categories"])
    _put(ws, end + 1, ["Total", total["nb_materiels"], total["nb_agents_detenteurs"]], bold=True, fill=X_TOTAL)
    ws.cell(row=end + 1, column=2).value = f"=SUM(B5:B{end})" if end >= 5 else 0
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = ws.column_dimensions["C"].width = 14
    wb.active = 0
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
