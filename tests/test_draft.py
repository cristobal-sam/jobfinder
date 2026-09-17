"""Tests de la détection de langue et du gabarit fixe (sans Ollama)."""

from src.draft import langue_de, message


def test_langue_francais():
    e = {"contexte": "Nous offrons des services de sécurité pour les entreprises "
                     "et nos clients sont dans les secteurs des finances et de la santé."}
    assert langue_de(e) == "fr"


def test_langue_anglais():
    e = {"contexte": "We provide security solutions for businesses and our clients "
                     "are in the finance and the health sectors with the best team."}
    assert langue_de(e) == "en"


def test_langue_repli_anglais_si_texte_court():
    assert langue_de({"contexte": ""}) == "en"
    assert langue_de({"contexte": None}) == "en"


def test_message_gabarit_fixe_sans_ollama(monkeypatch):
    # Forcer l'absence d'Ollama : accroche() doit retourner None
    monkeypatch.setattr("src.draft.ollama_disponible", lambda: False)
    e = {"nom": "Acme", "categorie": "Services informatiques", "contexte": ""}
    m = message(e)
    assert m["ia"] is False
    assert "Candidature spontanée" in m["objet"]
    assert "services informatiques" in m["corps"]
    assert "SIGNATURE" not in m["corps"]        # la signature est bien incluse
