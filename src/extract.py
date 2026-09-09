"""Extraction des coordonnées et du contexte à partir du HTML récupéré."""

import re
from typing import Optional

from bs4 import BeautifulSoup

MOTIF_COURRIEL = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

# Faux positifs fréquents dans le HTML
REJETS = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js",
    "example.com", "sentry.io", "wixpress.com", "@2x", "domain.com",
)

# Adresses génériques classées par ordre de préférence
PREFERENCES = ("rh@", "emploi", "carriere", "info@", "contact@", "admin@")

# Mots qui signalent une page décrivant l'entreprise
MOTS_APROPOS = ("propos", "about", "qui-sommes", "qui sommes", "entreprise", "mission")

MOTS_CARRIERE = ("carrier", "carriere", "emploi", "job", "recrut", "nous-rejoindre")


def page_carrieres(pages: dict) -> Optional[str]:
    """URL de la page carrières si le site en a une."""
    for url in pages:
        if any(m in url.lower() for m in MOTS_CARRIERE):
            return url
    return None

def courriels(html: str) -> list[str]:
    """Tous les courriels plausibles trouvés dans une page, dédoublonnés."""
    trouves = []
    for brut in MOTIF_COURRIEL.findall(html):
        adr = brut.lower().strip(".")
        if any(r in adr for r in REJETS):
            continue
        if adr not in trouves:
            trouves.append(adr)
    return trouves

def courriels_mailto(html: str) -> list[str]:
    """
    Adresses trouvées dans les liens mailto:.

    Beaucoup de sites n'affichent jamais leur courriel en texte : il n'existe
    que dans l'attribut href d'un lien cliquable. Ces adresses sont aussi les
    plus fiables, puisqu'elles sont posées là volontairement pour être utilisées.
    """
    from urllib.parse import unquote

    soup = BeautifulSoup(html, "html.parser")
    trouves = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.lower().startswith("mailto:"):
            continue

        # mailto:info@site.ca?subject=Bonjour  ->  info@site.ca
        adresse = unquote(href[7:]).split("?")[0].split(",")[0].strip().lower()

        if "@" not in adresse or any(r in adresse for r in REJETS):
            continue
        if adresse not in trouves:
            trouves.append(adresse)

    return trouves

def meilleur_courriel(candidats: list[str],
                      domaine: Optional[str] = None,
                      prioritaires: Optional[list[str]] = None) -> Optional[str]:
    """
    Choisit l'adresse la plus pertinente.

    Ordre : les adresses issues de liens mailto (posées volontairement),
    puis celles du même domaine, puis les boîtes RH, puis les génériques.
    """
    if prioritaires:
        choix = _classer(prioritaires, domaine)
        if choix:
            return choix
    return _classer(candidats, domaine)


def _classer(candidats: list[str], domaine: Optional[str]) -> Optional[str]:
    if not candidats:
        return None

    if domaine:
        propres = [c for c in candidats if c.endswith(f"@{domaine}")]
        candidats = propres or candidats

    for prefere in PREFERENCES:
        for c in candidats:
            if prefere in c:
                return c
    return candidats[0]


def contexte(html: str, longueur_max: int = 220) -> Optional[str]:
    """
    Une ou deux phrases décrivant ce que fait l'entreprise.
    Sert à personnaliser le message — c'est le coeur de l'outil.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. La meta description est souvent la meilleure source
    meta = soup.find("meta", attrs={"name": "description"}) \
        or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        texte = meta["content"].strip()
        if len(texte) > 40:
            return texte[:longueur_max].rsplit(" ", 1)[0]

    # 2. Sinon, le premier paragraphe substantiel du corps
    for balise in soup(["script", "style", "nav", "header", "footer"]):
        balise.decompose()

    for p in soup.find_all("p"):
        texte = " ".join(p.get_text().split())
        if len(texte) > 60:
            return texte[:longueur_max].rsplit(" ", 1)[0]

    return None


def meilleur_contexte(pages: dict) -> Optional[str]:
    """
    Choisit le meilleur texte descriptif parmi les pages récupérées.
    Priorité à la page « À propos », qui contient souvent la mission
    et les services, avec repli sur la page d'accueil.
    """
    # Chercher une page « à propos » parmi celles visitées
    for url, html in pages.items():
        if any(m in url.lower() for m in MOTS_APROPOS):
            texte = contexte(html, longueur_max=400)
            if texte and len(texte) > 80:
                return texte

    # Repli : la page d'accueil (première entrée du dictionnaire)
    accueil_url = list(pages)[0]
    return contexte(pages[accueil_url])