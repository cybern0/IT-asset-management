# Generation du PDF « Fiche de detention individuelle » a partir des donnees de la base
import re
from datetime import date
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PINE = colors.HexColor("#1e3a38")
LINE = colors.HexColor("#9aa9a3")
SOFT = colors.HexColor("#eef1ea")
DOTS = "." * 46

_base = dict(fontName="Helvetica", fontSize=9.5, leading=12.5)
S_TXT = ParagraphStyle("txt", **_base)
S_LBL = ParagraphStyle("lbl", **{**_base, "fontName": "Helvetica-Bold"})
S_SEC = ParagraphStyle("sec", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 11, "textColor": PINE, "spaceBefore": 7, "spaceAfter": 3})
S_TITLE = ParagraphStyle("title", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 16, "leading": 20, "textColor": colors.white, "alignment": TA_CENTER})
S_SUB = ParagraphStyle("sub", **{**_base, "textColor": colors.white, "alignment": TA_CENTER})
S_SMALL = ParagraphStyle("small", **{**_base, "fontSize": 8.5, "leading": 11, "textColor": colors.HexColor("#4a5a54")})
S_NOTE = ParagraphStyle("note", **{**_base, "fontName": "Helvetica-Oblique", "fontSize": 8.5, "textColor": colors.HexColor("#4a5a54")})


def _safe(value: Any) -> str:
    """Texte compatible avec la police standard (WinAnsi), puis echappe pour Paragraph."""
    s = "" if value is None else str(value)
    s = s.encode("cp1252", errors="replace").decode("cp1252")
    return escape(s)


def _p(text: Any, style: ParagraphStyle = S_TXT) -> Paragraph:
    return Paragraph(_safe(text).replace("\n", "<br/>"), style)


def _raw(markup: str, style: ParagraphStyle = S_TXT) -> Paragraph:
    return Paragraph(markup, style)


def _box(checked: bool) -> str:
    return "<b>[X]</b>" if checked else "[&nbsp;&nbsp;]"


def _checks(options: list[tuple[str, bool]]) -> Paragraph:
    return _raw("&nbsp;&nbsp;&nbsp;".join(f"{_box(c)} {_safe(label)}" for label, c in options))


def _fr(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def _parse_caracteristiques(text: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (text or "").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out.setdefault(k.strip().lower(), v.strip())
    return out


def _type_equipement(d: dict[str, Any]) -> list[tuple[str, bool]]:
    cat = d["materiel_categorie_code"]
    hay = f'{d["materiel_designation"]} {d["materiel_modele"] or ""} {d["materiel_caracteristiques"] or ""}'.lower()
    portable = bool(re.search(r"portable|laptop|notebook|latitude|thinkpad|probook|elitebook|macbook|vostro|aspire", hay))
    fixe = bool(re.search(r"\bfixe\b|desktop|prodesk|optiplex|tour\b|\btower\b|imac", hay))
    tablette = bool(re.search(r"tablette|tablet|ipad", hay))
    autre = ""
    if cat == "ORDINATEUR" and not (portable or fixe):
        autre = d["materiel_categorie"]
    elif cat not in ("ORDINATEUR", "ECRAN", "TELEPHONE"):
        autre = d["materiel_categorie"]
    return [
        ("PC Portable", cat == "ORDINATEUR" and portable),
        ("PC Fixe", cat == "ORDINATEUR" and fixe and not portable),
        ("Écran", cat == "ECRAN"),
        ("Smartphone", cat == "TELEPHONE" and not tablette),
        ("Tablette", cat == "TELEPHONE" and tablette),
        (f"Autre : {autre}" if autre else "Autre : ..........", bool(autre)),
    ]


_ETAT_CONSTATE = {"NEUF": "Bon état", "BON": "Bon état", "A_REPARER": "Dégradé", "EN_PANNE": "Hors service", "REFORME": "Hors service"}
_ACCESSOIRES = ["Chargeur", "Sacoche", "Docking", "Souris", "Clavier"]


def _kv(rows: list[tuple[str, Paragraph | str]], width: float) -> Table:
    data = [[_p(k, S_LBL), v if isinstance(v, Paragraph) else _p(v or DOTS)] for k, v in rows]
    t = Table(data, colWidths=[5.0 * cm, width - 5.0 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (0, -1), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def build_pdf(d: dict[str, Any], structure_name: str = "") -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.2 * cm, bottomMargin=1.5 * cm,
        title=f"Fiche de détention {d['reference']}", author=structure_name or "Parc informatique",
    )
    width = A4[0] - 3.6 * cm
    story: list = [_p("Document interne – Gestion du parc informatique", S_NOTE), Spacer(1, 4)]

    head = Table(
        [[_p("FICHE DE DÉTENTION INDIVIDUELLE", S_TITLE)],
         [_p(f"Parc informatique – {structure_name or '[Nom de la structure]'}", S_SUB)]],
        colWidths=[width],
    )
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PINE),
        ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    story.append(head)

    signee = d["statut"] == "SIGNEE"
    statut = f"Signée le {_fr(d['date_signature'])}" if signee else "Non signée"
    color = "#25502a" if signee else "#8a5a00"
    story += [
        Spacer(1, 6),
        _raw(
            f'<b>Réf. :</b> {_safe(d["reference"])} &nbsp;|&nbsp; <b>Date d’édition :</b> {_fr(date.today())}'
            f' &nbsp;|&nbsp; <b>Statut :</b> <font color="{color}"><b>{_safe(statut)}</b></font>'
        ),
    ]

    # ---- 1. equipement
    car = _parse_caracteristiques(d["materiel_caracteristiques"])
    marque_modele = " / ".join(x for x in (d["materiel_marque"], d["materiel_modele"]) if x) or d["materiel_designation"]
    config = _raw(
        f'RAM : {_safe(car["ram"]) if "ram" in car else "........ Go"} &nbsp;|&nbsp; '
        f'Stockage : {_safe(car.get("stockage", "........ Go"))} &nbsp;|&nbsp; '
        f'OS : {_safe(car["os"]) if "os" in car else "........................"}'
    )
    story += [
        _p("1. IDENTIFICATION DE L’ÉQUIPEMENT", S_SEC),
        _kv([
            ("N° d’inventaire", d["materiel_code"]),
            ("Marque / Modèle", marque_modele),
            ("N° de série constructeur", d["materiel_serie"] or ""),
            ("Type d’équipement", _checks(_type_equipement(d))),
            ("Configuration", config),
            ("Accessoires fournis", _checks([(a, False) for a in _ACCESSOIRES] + [("Autre : ...............", False)])),
        ], width),
    ]

    # ---- 2. detenteur
    nom = f'{d["agent_nom"]} {d["agent_prenom"]}'.strip()
    service = " / ".join(x for x in (d["service_nom"], d["direction_nom"]) if x)
    lieu = " – ".join(x for x in (d["service_site"], d["materiel_localisation"]) if x)
    story += [
        _p("2. IDENTIFICATION DU DÉTENTEUR", S_SEC),
        _kv([
            ("Nom et prénom", nom),
            ("Service / Direction", service),
            ("Matricule / Identifiant", d["agent_matricule"]),
            ("Site / Localisation / Bureau", lieu),
            ("Date d’attribution", _fr(d["date_remise"])),
        ], width),
    ]

    # ---- 3. engagements
    engagements = [
        "L’utiliser exclusivement à des fins professionnelles ;",
        "En prendre soin et le restituer en bon état de fonctionnement ;",
        "Signaler immédiatement toute panne, dégradation, perte ou vol au service informatique ;",
        "Ne pas céder, prêter ou confier le matériel à un tiers sans autorisation préalable ;",
        "Restituer l’équipement et ses accessoires lors de mon départ ou sur demande du service informatique.",
    ]
    story += [
        _p("3. ENGAGEMENTS DU DÉTENTEUR", S_SEC),
        _p("Je soussigné(e) reconnais avoir reçu l’équipement désigné ci-dessus en bon état de fonctionnement et m’engage à :"),
        Spacer(1, 3),
        *[_raw(f"•&nbsp;&nbsp;{_safe(e)}") for e in engagements],
    ]

    # ---- 4. signatures d'attribution
    def sign_cell(titre: str, nom_: str) -> list:
        return [_p(titre, S_LBL), Spacer(1, 3), _p(f"Nom : {nom_ or '........................................'}"),
                _p("Date : ....../....../.........."), Spacer(1, 3), _p("Signature :"), Spacer(1, 16)]

    sig = Table(
        [[sign_cell("Le détenteur", nom), sign_cell("Le service informatique", d["saisi_par"] or "")]],
        colWidths=[width / 2, width / 2],
    )
    sig.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                             ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story.append(KeepTogether([_p("4. SIGNATURES D’ATTRIBUTION", S_SEC), sig]))

    # ---- 5. restitution
    rendue = d["date_retour"] is not None
    constate = _ETAT_CONSTATE.get(d["etat_retour"] or d["materiel_etat"], "") if rendue else ""
    resti = _kv([
        ("Date de restitution", _fr(d["date_retour"]) if rendue else ""),
        ("État constaté", _checks([(x, constate == x) for x in ("Bon état", "Dégradé", "Incomplet", "Hors service")])),
        ("Observations", (d["observations"] or "") if rendue else ""),
        ("Accessoires restitués", _checks([(a, False) for a in _ACCESSOIRES] + [("Autre : ...............", False)])),
    ], width)
    sig2 = Table(
        [[[_p("Signature du détenteur", S_LBL), _p("Date : ....../....../.........."), Spacer(1, 14)],
          [_p("Signature service informatique", S_LBL), _p("Date : ....../....../.........."), Spacer(1, 14)]]],
        colWidths=[width / 2, width / 2],
    )
    sig2.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story.append(KeepTogether([
        _p("5. ZONE DE RESTITUTION  (à remplir uniquement lors de la restitution)", S_SEC), resti, Spacer(1, 6), sig2,
    ]))

    story += [
        Spacer(1, 4),
        _p("Ce document doit être signé en deux exemplaires (un pour le détenteur, un pour le service informatique).", S_NOTE),
        _p("Conservation : minimum 5 ans après la restitution de l’équipement.", S_NOTE),
    ]

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#4a5a54"))
        canvas.drawCentredString(A4[0] / 2, 0.9 * cm, f"Fiche de détention individuelle {d['reference']} – À conserver 5 ans après restitution")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
