"""Tests des fonctions d'extraction (sans réseau)."""

from src.extract import (courriels, courriels_mailto, meilleur_courriel,
                         contexte, page_carrieres)


def test_courriels_dedoublonnes_et_filtres():
    html = """
    <p>Contact : Info@Entreprise.ca ou info@entreprise.ca</p>
    <img src="logo@2x.png">
    <p>support@sentry.io et rh@entreprise.ca</p>
    """
    trouves = courriels(html)
    assert trouves.count("info@entreprise.ca") == 1      # dédoublonné, minuscules
    assert "rh@entreprise.ca" in trouves
    assert not any("sentry.io" in c for c in trouves)     # faux positif rejeté
    assert not any("@2x" in c for c in trouves)


def test_courriels_mailto():
    html = '<a href="mailto:RH@Site.qc.ca?subject=Bonjour">Écrire</a>'
    assert courriels_mailto(html) == ["rh@site.qc.ca"]


def test_courriels_mailto_ignore_les_liens_ordinaires():
    html = '<a href="https://exemple.ca/contact">Contact</a>'
    assert courriels_mailto(html) == []


def test_meilleur_courriel_priorise_mailto_puis_domaine_puis_rh():
    candidats = ["jean.tremblay@entreprise.ca", "rh@entreprise.ca"]
    assert meilleur_courriel(candidats, "entreprise.ca") == "rh@entreprise.ca"
    # Un mailto volontaire passe avant tout
    assert meilleur_courriel(candidats, "entreprise.ca",
                             prioritaires=["contact@entreprise.ca"]) == "contact@entreprise.ca"


def test_meilleur_courriel_sans_candidat():
    assert meilleur_courriel([], "entreprise.ca") is None


def test_contexte_depuis_meta_description():
    html = ('<html><head><meta name="description" content="'
            'Firme de services-conseils en sécurité informatique établie à Montréal.">'
            '</head><body></body></html>')
    texte = contexte(html)
    assert "sécurité informatique" in texte


def test_contexte_repli_sur_paragraphe():
    html = ("<html><body><script>var x=1;</script>"
            "<p>Court.</p>"
            "<p>Nous accompagnons les PME québécoises dans leur transformation "
            "numérique depuis plus de dix ans.</p></body></html>")
    texte = contexte(html)
    assert "transformation numérique" in texte


def test_page_carrieres():
    pages = {"https://x.ca": "", "https://x.ca/carrieres": ""}
    assert page_carrieres(pages) == "https://x.ca/carrieres"
    assert page_carrieres({"https://x.ca": ""}) is None
