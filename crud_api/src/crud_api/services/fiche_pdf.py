# Generation du PDF « Fiche de detention individuelle » a partir des donnees de la base.
# Reproduit le modele Word (Fiche_Detention_Individuelle.docx) : memes titres, memes lignes, memes textes,
# memes tailles ; couleurs du theme de l'application. Seules les valeurs changent : les points de remplissage sont remplaces par
# les donnees du dossier quand elles existent, et restent tels quels sinon.
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
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# palette de l'application (theme vert) ; dimensions du modele Word
PINE = colors.HexColor("#1e3a38")
RULE = PINE
LABEL_BG = colors.HexColor("#eef1ea")
MUTED = colors.HexColor("#4a5a54")
GRID = colors.HexColor("#9aa9a3")
OK_INK, WARN_INK = "#25502a", "#8a5a00"
DOT = "#AAAAAA"
MARGIN = 36  # 0,5 pouce, comme le modele
WIDTH = A4[0] - 2 * MARGIN
LABEL_W = WIDTH * 3400 / 10466  # colonnes du modele : 3400 / 7066

_font = dict(fontName="Helvetica")  # Helvetica = Arial pour reportlab
S_LABEL = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=PINE)
S_VAL = ParagraphStyle("val", **_font, fontSize=9, leading=11)
S_CHK = ParagraphStyle("chk", **_font, fontSize=8.5, leading=11)
S_SEC = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=PINE)
S_TXT = ParagraphStyle("txt", **_font, fontSize=9, leading=11)
S_BUL = ParagraphStyle("bul", **_font, fontSize=8.5, leading=10.5, leftIndent=10, spaceAfter=2)
S_BOXT = ParagraphStyle("boxt", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=PINE, leftIndent=4, spaceBefore=4, spaceAfter=2)
S_BOXT_S = ParagraphStyle("boxts", fontName="Helvetica-Bold", fontSize=8.5, leading=10.5, textColor=PINE, leftIndent=4, spaceBefore=4, spaceAfter=2)
S_BOX = ParagraphStyle("box", **_font, fontSize=8, leading=10, leftIndent=4, spaceAfter=2)
S_BOX_S = ParagraphStyle("boxs", **_font, fontSize=7.5, leading=9.5, leftIndent=4, spaceAfter=2)
S_REF = ParagraphStyle("ref", **_font, fontSize=8, leading=10, textColor=MUTED, alignment=2, spaceBefore=6, spaceAfter=3)
S_HINT = ParagraphStyle("hint", **_font, fontSize=7.5, leading=9.5, textColor=MUTED)
S_NOTE = ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=7.5, leading=9, textColor=MUTED, alignment=TA_CENTER)
S_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=colors.white, alignment=TA_CENTER)
S_SUB = ParagraphStyle("sub", **_font, fontSize=9, leading=11, textColor=colors.white, alignment=TA_CENTER)


def _safe(value: Any) -> str:
    """Texte compatible avec la police standard (WinAnsi), puis echappe pour Paragraph."""
    s = "" if value is None else str(value)
    s = s.encode("cp1252", errors="replace").decode("cp1252")
    return escape(s)


def _dots(n: int) -> str:
    return f'<font color="{DOT}">{"." * n}</font>'


def _fr(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def _value(text: Any, dots: int = 52, sub: list[str] | None = None):
    """Valeur du dossier (ou points de remplissage du modele si vide), suivie de lignes d'information
    en petit texte : meme ligne du modele, simplement plus d'information."""
    s = "" if text is None else str(text).strip()
    main = Paragraph(_safe(s) if s else _dots(dots), S_VAL)
    lines = [x for x in (sub or []) if x]
    return [main, *[Paragraph(_safe(x), S_HINT) for x in lines]] if lines else main


# ----------------------------- cases a cocher (☐ du modele) -----------------------------
# Dessinees en vectoriel (carre + texte) : la police standard n'a pas le glyphe ☐ et les images integrees
# ne sont pas acceptees par toutes les versions de reportlab.
def _plain(value: Any) -> str:
    return ("" if value is None else str(value)).encode("cp1252", errors="replace").decode("cp1252")


class CheckRow(Flowable):
    """Ligne d'options « ☐ A    ☐ B » avec retour a la ligne ; une case cochee porte une coche bleue."""

    BOX, BOX_GAP, LEADING = 7.5, 3.0, 10.5

    def __init__(self, options: list[tuple[str, bool]], gap: int = 4, font: str = "Helvetica", size: float = 8.5):
        super().__init__()
        self.font, self.size, self.gap = font, size, gap
        self.items: list[tuple[str, str, bool]] = []  # (texte, points de remplissage, coche)
        for label, checked in options:
            m = re.match(r"^(.*?)(\.{3,})$", label)
            self.items.append((_plain(m.group(1)), m.group(2), checked) if m else (_plain(label), "", checked))
        self._lines: list[list[tuple[float, tuple[str, str, bool]]]] = []

    def _item_width(self, it: tuple[str, str, bool]) -> float:
        return self.BOX + self.BOX_GAP + stringWidth(it[0], self.font, self.size) + stringWidth(it[1], self.font, self.size)

    def wrap(self, availWidth: float, availHeight: float):
        gap_w = self.gap * stringWidth(" ", self.font, self.size)
        self._lines, line, x = [], [], 0.0
        for it in self.items:
            w = self._item_width(it)
            if line and x + w > availWidth:
                self._lines.append(line)
                line, x = [], 0.0
            line.append((x, it))
            x += w + gap_w
        if line:
            self._lines.append(line)
        self.width, self.height = availWidth, max(1, len(self._lines)) * self.LEADING
        return self.width, self.height

    def draw(self):
        c = self.canv
        for n, line in enumerate(self._lines):
            base = self.height - (n + 1) * self.LEADING + 3  # ligne de base du texte
            for x, (text, dots, checked) in line:
                c.setStrokeColor(colors.HexColor("#282828"))
                c.setLineWidth(0.6)
                c.rect(x, base - 0.5, self.BOX, self.BOX, stroke=1, fill=0)
                if checked:
                    c.setStrokeColor(PINE)
                    c.setLineWidth(1.4)
                    p = c.beginPath()
                    p.moveTo(x + 1.6, base + 3.4)
                    p.lineTo(x + 3.3, base + 1.4)
                    p.lineTo(x + 6.6, base + 6.2)
                    c.drawPath(p, stroke=1, fill=0)
                tx = x + self.BOX + self.BOX_GAP
                c.setFillColor(colors.black)
                c.setFont(self.font, self.size)
                c.drawString(tx, base, text)
                if dots:
                    c.setFillColor(colors.HexColor(DOT))
                    c.drawString(tx + stringWidth(text, self.font, self.size), base, dots)


def _checks(options: list[tuple[str, bool]], gap: int = 4) -> CheckRow:
    return CheckRow(options, gap)


# ----------------------------- donnees -----------------------------
def _type_equipement(d: dict[str, Any], types: list[tuple[str, str]] | None) -> list[tuple[str, bool]]:
    """Options de la ligne « Type d'equipement » : les categories du dictionnaire, celle du materiel cochee.
    Si le dictionnaire n'est pas fourni (ou ne contient pas la categorie), la categorie du materiel est ajoutee."""
    code, label = d["materiel_categorie_code"], d["materiel_categorie"]
    options = [(lib, c == code) for c, lib in (types or [])]
    if label and not any(checked for _, checked in options):
        options.append((label, True))
    return options


def _etat_dossier(d: dict[str, Any]) -> str:
    return f"En cours – étape {d['etape']}/6" if d["etat"] == "EN_COURS" else _ETAT_DOSSIER.get(d["etat"], d["etat"])


def _info_equipement(d: dict[str, Any]) -> list[str]:
    """Designation, origine et date d'acquisition : sous le numero d'inventaire."""
    names = [x for x in dict.fromkeys([d["materiel_designation"], d["materiel_categorie"]]) if x]
    origine = _PROVENANCE.get(d["materiel_provenance"] or "", d["materiel_provenance"] or "")
    if d["materiel_provenance_detail"]:
        origine = f"{origine} ({d['materiel_provenance_detail']})" if origine else d["materiel_provenance_detail"]
    parts = [" / ".join(names)]
    if origine:
        parts.append(f"Origine : {origine}")
    if d["materiel_date_acquisition"]:
        parts.append(f"Acquis le {_fr(d['materiel_date_acquisition'])}")
    return [" · ".join(p for p in parts if p)]


def _info_detenteur(d: dict[str, Any]) -> list[str]:
    return [" · ".join(x for x in (d["agent_fonction"], d["agent_email"]) if x)]


def _info_attribution(d: dict[str, Any]) -> list[str]:
    """Remise (etat constate, observations) puis demande et validation : sous la date d'attribution."""
    remise = []
    if d["etat_constate"]:
        remise.append(f"État constaté à la remise : {_ETAT_REMISE.get(d['etat_constate'], d['etat_constate'])}")
    if d["observations_remise"]:
        remise.append(f"Observations : {d['observations_remise']}")
    demande = []
    if d["date_demande"]:
        canal = _CANAL.get(d["canal"], d["canal"] or "")
        if d["reference_canal"]:
            canal = f"{canal} – {d['reference_canal']}" if canal else d["reference_canal"]
        txt = f"Demande du {_fr(d['date_demande'])}" + (f" ({canal})" if canal else "")
        if d["demandeur"]:
            txt += f" par {d['demandeur']}"
        demande.append(txt)
    if d["categorie_demandee"]:
        demande.append(f"Équipement demandé : {d['categorie_demandee']}")
    if d["besoin"]:
        demande.append(f"Besoin : {d['besoin']}")
    if d["valide_par"]:
        demande.append(f"Validée par {d['valide_par']}" + (f" le {_fr(d['date_validation'])}" if d["date_validation"] else ""))
    return [" · ".join(remise), " · ".join(demande)]


def _configuration(d: dict[str, Any]) -> Paragraph:
    """Ligne « Configuration » : les caracteristiques saisies, telles quelles (texte brut, retours a la ligne conserves).
    Aucun decoupage ni gabarit : le champ est deja libre, il n'y a rien a reconnaitre. Points de remplissage si vide."""
    text = (d["materiel_caracteristiques"] or "").strip()
    if not text:
        return Paragraph(_dots(52), S_CHK)
    return Paragraph("<br/>".join(_safe(line.strip()) for line in text.splitlines() if line.strip()), S_CHK)


_ETAT_DOSSIER = {"ATTRIBUEE": "Attribué", "RENDUE": "Rendu", "REFUSEE": "Demande refusée", "ANNULEE": "Dossier annulé"}
_CANAL = {"MAIL": "Mail", "TICKET": "Ticket", "FORMULAIRE": "Formulaire"}
_PROVENANCE = {"ACHAT": "Achat", "DOTATION": "Dotation", "AFFECTATION": "Affectation", "PROJET": "Projet", "DON": "Don", "AUTRE": "Autre"}
_ETAT_REMISE = {"NEUF": "Neuf", "BON": "Bon état", "A_REPARER": "À réparer"}
_ETAT_CONSTATE = {"NEUF": "Bon état", "BON": "Bon état", "A_REPARER": "Dégradé", "EN_PANNE": "Hors service", "REFORME": "Hors service"}
_ACCESSOIRES = ["Chargeur", "Sacoche", "Docking", "Souris", "Clavier"]
DATE_BLANK = "....../....../.........."


# ----------------------------- composants du modele -----------------------------
def _kv(rows: list[tuple[str, Any]]) -> Table:
    data = [[Paragraph(_safe(k), S_LABEL), v] for k, v in rows]
    t = Table(data, colWidths=[LABEL_W, WIDTH - LABEL_W])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("BACKGROUND", (0, 0), (0, -1), LABEL_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def _section(title: str) -> list:
    """Titre de section : texte bleu gras 10 pt, filet bleu dessous."""
    bar = Table([[Paragraph(_safe(title), S_SEC)]], colWidths=[WIDTH])
    bar.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.75, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return [Spacer(1, 7), bar, Spacer(1, 3)]


def _signature_box(left: list, right: list, height: float) -> Table:
    t = Table([[left, right]], colWidths=[WIDTH / 2, WIDTH / 2], rowHeights=[height])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRID), ("INNERGRID", (0, 0), (-1, -1), 0.5, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build_pdf(d: dict[str, Any], structure_name: str = "", types: list[tuple[str, str]] | None = None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=50, bottomMargin=48,
        title=f"Fiche de détention {d['reference']}", author=structure_name or "Parc informatique",
    )
    story: list = []
    signee = d["statut"] == "SIGNEE" and bool(d["date_signature"])
    statut_fiche = f"Signée le {_fr(d['date_signature'])}" if signee else "Non signée"

    # ---- bandeau titre
    banner = Table(
        [[Paragraph("FICHE DE DÉTENTION INDIVIDUELLE", S_TITLE)],
         [Paragraph(_safe(f"Parc informatique – {structure_name or '[Nom de la structure]'}"), S_SUB)]],
        colWidths=[WIDTH],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PINE), ("BOX", (0, 0), (-1, -1), 1.5, PINE),
        ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 0), ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
    ]))
    story += [
        banner,
        Paragraph(
            f'Réf. : {_safe(d["reference"])} &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; Date d’édition : {_fr(date.today())}'
            f' &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; Fiche : <font color="{OK_INK if signee else WARN_INK}"><b>{_safe(statut_fiche)}</b></font>'
            f' &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; Dossier : {_safe(_etat_dossier(d))}', S_REF),
    ]

    # ---- 1. identification de l'equipement
    marque, modele = d["materiel_marque"], d["materiel_modele"]
    if marque and modele and marque.strip().lower() == modele.strip().lower():
        modele = None  # « DELL / DELL » -> « DELL »
    marque_modele = " / ".join(x for x in (marque, modele) if x) or d["materiel_designation"]
    provided = d["accessoires"]
    accessoires = [("Docking station" if a == "Docking" else a, a in provided) for a in _ACCESSOIRES]
    accessoires.append((f"Autre : {d['accessoires_autre']}" if d["accessoires_autre"] else "Autre : ...............",
                        bool(d["accessoires_autre"])))
    story += _section("1. IDENTIFICATION DE L’ÉQUIPEMENT") + [_kv([
        ("N° d’inventaire", _value(d["materiel_code"], sub=_info_equipement(d))),
        ("Marque / Modèle", _value(marque_modele)),
        ("N° de série constructeur", _value(d["materiel_serie"])),
        ("Type d’équipement", _checks(_type_equipement(d, types), gap=3)),
        ("Configuration", _configuration(d)),
        ("Accessoires fournis", _checks(accessoires)),
    ])]

    # ---- 2. identification du detenteur
    nom = f'{d["agent_nom"]} {d["agent_prenom"]}'.strip()
    service = " / ".join(x for x in (d["service_nom"], d["direction_nom"]) if x)
    lieu = " – ".join(x for x in (d["service_site"], d["materiel_localisation"]) if x)
    story += _section("2. IDENTIFICATION DU DÉTENTEUR") + [_kv([
        ("Nom et prénom", _value(nom, 48, sub=_info_detenteur(d))),
        ("Service / Direction", _value(service, 48)),
        ("Matricule / Identifiant", _value(d["agent_matricule"], 48)),
        ("Site / Localisation / Bureau", _value(lieu, 48)),
        ("Date d’attribution", _value(_fr(d["date_remise"]), 48, sub=_info_attribution(d))),
    ])]

    # ---- 3. engagements
    engagements = [
        "L’utiliser exclusivement à des fins professionnelles ;",
        "En prendre soin et le restituer en bon état de fonctionnement ;",
        "Signaler immédiatement toute panne, dégradation, perte ou vol au service informatique ;",
        "Ne pas céder, prêter ou confier le matériel à un tiers sans autorisation préalable ;",
        "Restituer l’équipement et ses accessoires lors de mon départ ou sur demande du service informatique.",
    ]
    story.append(KeepTogether(_section("3. ENGAGEMENTS DU DÉTENTEUR") + [
        Paragraph("Je soussigné(e) reconnais avoir reçu l’équipement désigné ci-dessus en bon état de fonctionnement et m’engage à :", S_TXT),
        Spacer(1, 4),
        *[Paragraph(f"•&nbsp;&nbsp;{_safe(e)}", S_BUL) for e in engagements],
    ]))

    # ---- 4. signatures d'attribution (nom et date pre-remplis si la fiche est deja signee)
    date_line = f"Date : {_fr(d['date_signature'])}" if signee else f"Date : {DATE_BLANK}"

    def party(titre: str, nom_: str, sign_label: str) -> list:
        return [Paragraph(_safe(titre), S_BOXT),
                Paragraph(f"Nom : {_safe(nom_) if nom_ else '........................................'}", S_BOX),
                Paragraph(date_line, S_BOX), Spacer(1, 3), Paragraph(sign_label, S_BOX)]

    story.append(KeepTogether(_section("4. SIGNATURES D’ATTRIBUTION") + [_signature_box(
        party("Le détenteur", nom, "Signature :"),
        party("Le service informatique", d["signe_par"] or d["saisi_par"] or "", "Signature / Cachet :"),
        height=56,
    )]))

    # ---- 5. zone de restitution
    rendue = d["date_retour"] is not None
    constate = _ETAT_CONSTATE.get(d["etat_retour"] or d["materiel_etat"], "") if rendue else ""
    resti = _kv([
        ("Date de restitution", _value(_fr(d["date_retour"]) if rendue else "", 48)),
        ("État constaté", _checks([(x, constate == x) for x in ("Bon état", "Dégradé", "Incomplet", "Hors service")], gap=6)),
        ("Observations", _value((d["observations"] or "") if rendue else "", 48)),
        ("Accessoires restitués", _checks([(a, False) for a in _ACCESSOIRES] + [("Autre : ...............", False)])),
    ])
    sig2 = _signature_box(
        [Paragraph("Signature du détenteur", S_BOXT_S), Paragraph(f"Date : {DATE_BLANK}", S_BOX_S)],
        [Paragraph("Signature service informatique", S_BOXT_S), Paragraph(f"Date : {DATE_BLANK}", S_BOX_S)],
        height=42,
    )
    story.append(KeepTogether(
        _section("5. ZONE DE RESTITUTION  (à remplir uniquement lors de la restitution)") + [resti, Spacer(1, 6), sig2]
    ))

    story += [
        Spacer(1, 7),
        Paragraph("Ce document doit être signé en deux exemplaires (un pour le détenteur, un pour le service informatique).", S_NOTE),
        Spacer(1, 2),
        Paragraph("Conservation : minimum 5 ans après la restitution de l’équipement.", S_NOTE),
    ]

    def chrome(canvas, _doc):
        """En-tete et pied de page du modele : texte gris 7 pt, filet bleu."""
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.setFillColor(MUTED)
        top = A4[1] - 36
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.drawString(MARGIN, top - 4, "Document interne – Gestion du parc informatique")
        canvas.line(MARGIN, top - 9, A4[0] - MARGIN, top - 9)
        canvas.line(MARGIN, 40, A4[0] - MARGIN, 40)
        canvas.setFont("Helvetica", 7)
        canvas.drawCentredString(A4[0] / 2, 30, "Fiche de détention individuelle – À conserver 5 ans après restitution")
        canvas.restoreState()

    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return buf.getvalue()
