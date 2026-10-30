"""Fiche de detention (PDF) : rendu a partir d'un dossier a plat, sans base de donnees."""
from datetime import date

import pytest

from crud_api.services import fiche_pdf

pytestmark = pytest.mark.nodb


def dossier(**over):
    d = {
        "id": 1, "reference": "FD-2026-0007", "etape": 6, "etat": "ATTRIBUEE", "cree_le": None,
        "categorie_id": 1, "categorie_demandee": "Ordinateur", "besoin": "PC portable 16 Go de RAM pour le suivi budgétaire",
        "canal": "TICKET", "reference_canal": "TCK-4521", "demandeur": "Hery Rabe (chef de service)",
        "date_demande": date(2026, 9, 28), "valide_par": "Directeur des Finances", "date_validation": date(2026, 9, 29),
        "date_generation": date(2026, 9, 30), "statut": "SIGNEE", "date_signature": date(2026, 10, 1),
        "mode_signature": "MANUSCRITE", "signe_par": "R. Andry (Service informatique)",
        "date_remise": date(2026, 10, 2), "etat_constate": "NEUF", "accessoires": ["Chargeur", "Souris"],
        "accessoires_autre": "Câble HDMI", "observations_remise": "Rayure légère sur le capot.",
        "affectation_id": 12, "date_retour": None, "etat_retour": None, "observations": None, "saisi_par": "admin",
        "cloture": None, "motif_cloture": None,
        "materiel_id": 5, "materiel_code": "ORD-0001", "materiel_designation": "Dell Latitude 5440",
        "materiel_categorie_code": "ORDINATEUR", "materiel_categorie": "Ordinateur", "materiel_marque": "Dell",
        "materiel_modele": "Latitude 5440", "materiel_serie": "7KQ2N93",
        "materiel_caracteristiques": "RAM: 16 Go, Stockage: 512 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1235U",
        "materiel_etat": "BON", "materiel_statut": "ATTRIBUE", "materiel_localisation": "Bureau 12",
        "materiel_a_image": False, "materiel_provenance": "PROJET", "materiel_provenance_detail": "Projet PAGE",
        "materiel_date_acquisition": date(2026, 6, 15),
        "agent_id": 3, "agent_matricule": "M-1042", "agent_nom": "RAKOTO", "agent_prenom": "Jean",
        "agent_fonction": "Analyste budgétaire", "agent_email": "jean.rakoto@example.mg",
        "agent_telephone": "034 12 345 67", "agent_whatsapp": "032 12 345 67",
        "agent_adresse_domicile_exacte": "Lot II B 25 Ankadifotsy, Antananarivo",
        "service_nom": "Dette publique", "service_site": "Antananarivo", "direction_nom": "Direction Générale du Trésor",
    }
    d.update(over)
    return d


@pytest.mark.parametrize("text, expected", [
    ("RAM: 16 Go, Stockage: 512 Go SSD", "RAM: 16 Go, Stockage: 512 Go SSD"),   # tel quel, virgules comprises
    ("Taille: 24 pouces, Ports: HDMI | VGA", "Taille: 24 pouces, Ports: HDMI | VGA"),
    ("16, 32", "16, 32"),                                                       # aucune reconnaissance
    ("Ligne 1\n\n  Ligne 2 ", "Ligne 1<br/>Ligne 2"),                          # retours a la ligne conserves
    ("A & B <x>", "A &amp; B &lt;x&gt;"),                                       # echappe pour le PDF
])
def test_configuration_is_the_typed_text(text, expected):
    para = fiche_pdf._configuration(dossier(materiel_caracteristiques=text))
    assert para.text == expected


def test_configuration_empty_keeps_the_dotted_line():
    for empty in (None, "", "  \n "):
        assert "......" in fiche_pdf._configuration(dossier(materiel_caracteristiques=empty)).text
        assert fiche_pdf._configuration(dossier(materiel_caracteristiques=empty)).text.count("RAM") == 0


TYPES = [("ORDINATEUR", "Ordinateur"), ("ECRAN", "Écran"), ("PERIPHERIQUE", "Périphérique"), ("TELEPHONE", "Téléphone"),
         ("IMPRIMANTE", "Imprimante"), ("RESEAU", "Équipement réseau"), ("BAIE", "Baie"), ("SIM", "Carte SIM")]


def test_type_options_come_from_the_dictionary():
    opts = fiche_pdf._type_equipement(dossier(), TYPES)
    assert [lab for lab, _ in opts] == [lab for _, lab in TYPES]       # tout le dictionnaire, dans son ordre
    assert [lab for lab, on in opts if on] == ["Ordinateur"]           # seule la categorie du materiel est cochee
    d = dossier(materiel_categorie_code="RESEAU", materiel_categorie="Équipement réseau")
    assert [lab for lab, on in fiche_pdf._type_equipement(d, TYPES) if on] == ["Équipement réseau"]


def test_type_falls_back_to_the_equipment_category():
    assert fiche_pdf._type_equipement(dossier(), None) == [("Ordinateur", True)]
    # categorie supprimee du dictionnaire depuis : elle reste visible, cochee
    d = dossier(materiel_categorie_code="ANCIEN", materiel_categorie="Ancienne catégorie")
    assert fiche_pdf._type_equipement(d, TYPES)[-1] == ("Ancienne catégorie", True)


def test_dictionary_types_still_fit_on_one_page():
    import re
    full = TYPES + [("PDU", "PDU"), ("PASSIF", "Équipement passif"), ("CABLE", "Câble"), ("NON_GERE", "Équipement non géré"), ("CHASSIS", "Châssis")]
    pdf = fiche_pdf.build_pdf(dossier(), "Direction de la Dette publique", full)
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 1


@pytest.mark.parametrize("over", [
    {},  # dossier termine, signe, remis
    {"etape": 2, "etat": "EN_COURS", "statut": "NON_SIGNEE", "date_signature": None, "mode_signature": None,
     "signe_par": None, "date_remise": None, "etat_constate": None, "accessoires": [], "accessoires_autre": None,
     "observations_remise": None, "affectation_id": None, "date_generation": None},
    {"etat": "REFUSEE", "cloture": "REFUSEE", "motif_cloture": "Budget indisponible", "affectation_id": None},
    {"etat": "RENDUE", "date_retour": date(2026, 12, 1), "etat_retour": "A_REPARER", "observations": "Écran fissuré"},
    {"materiel_caracteristiques": None, "materiel_provenance": None, "agent_email": None, "demandeur": None},
])
def test_pdf_builds_in_every_state(over):
    pdf = fiche_pdf.build_pdf(dossier(**over), "Direction de la Dette publique")
    assert pdf[:4] == b"%PDF" and len(pdf) > 3000


def test_one_page_like_the_model():
    """Le modele Word tient sur une page : la fiche remplie doit aussi tenir sur une page."""
    from io import BytesIO
    import re
    pdf = fiche_pdf.build_pdf(dossier(), "Direction de la Dette publique")
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 1


def test_no_embedded_images():
    """Les cases a cocher sont vectorielles : aucune image integree (certaines versions de reportlab,
    notamment sous Windows, refusent les `data:` URI et la generation plantait en erreur 500)."""
    for over in ({}, {"accessoires": ["Chargeur"], "accessoires_autre": "Câble"}):
        pdf = fiche_pdf.build_pdf(dossier(**over), "")
        assert b"/Subtype /Image" not in pdf and b"/Subtype/Image" not in pdf


def test_extra_information_goes_in_existing_rows():
    d = dossier()
    assert "Origine : Projet (Projet PAGE)" in fiche_pdf._info_equipement(d)[0]
    assert fiche_pdf._info_detenteur(d) == ["Analyste budgétaire · jean.rakoto@example.mg"]
    remise, demande = fiche_pdf._info_attribution(d)
    assert "État constaté à la remise : Neuf" in remise and "Rayure" in remise
    assert "Ticket – TCK-4521" in demande and "Validée par Directeur des Finances le 29/09/2026" in demande


def test_missing_information_leaves_rows_clean():
    d = dossier(materiel_provenance=None, materiel_provenance_detail=None, materiel_date_acquisition=None,
                agent_fonction=None, agent_email=None, etat_constate=None, observations_remise=None,
                date_demande=None, valide_par=None, besoin=None, categorie_demandee=None, canal=None)
    assert fiche_pdf._info_detenteur(d) == [""]
    assert fiche_pdf._info_attribution(d) == ["", ""]
    assert fiche_pdf.build_pdf(d, "")[:4] == b"%PDF"


def test_pdf_includes_contact_and_address():
    from io import BytesIO
    from pypdf import PdfReader
    text = "".join(pg.extract_text() for pg in PdfReader(BytesIO(fiche_pdf.build_pdf(dossier(), ""))).pages)
    assert "034 12 345 67" in text and "032 12 345 67" in text and "Ankadifotsy" in text
