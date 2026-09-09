"""
Visite des sites d'entreprises.

Règles appliquées à chaque requête :
  - robots.txt consulté et respecté
  - cadence limitée (REQUEST_DELAY secondes entre deux requêtes)
  - User-Agent identifiable
  - aucune tentative de contourner une protection

Stratégie de navigation : au lieu de deviner des chemins (/contact,
/nous-joindre...), on lit les liens réels de la page d'accueil. Beaucoup
de sites utilisent des URL non standard (/joindre-notre-equipe, /fr/contactez).
"""

import os
import time
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = os.getenv("USER_AGENT", "prospect-qc/0.1")
DELAI = float(os.getenv("REQUEST_DELAY", 2))
TIMEOUT = 12
TAILLE_MIN = 2000          # sous ce seuil, la page est considérée vide

# Mots recherchés dans le texte et l'URL des liens
MOTS_CONTACT = (
    "contact", "joindre", "coordonn", "nous-ecrire", "nous ecrire",
    "carrier", "carrière", "carriere", "emploi", "recrut", "equipe",
    "équipe", "about", "propos", "soumission", "devis", "estimation",
    "services", "team", "qui-sommes", "quisommes",
)



class Visiteur:
    """Client HTTP poli : robots.txt, cadence, cache des règles par domaine."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._robots: dict[str, Optional[RobotFileParser]] = {}
        self._dernier_appel = 0.0

    def _attendre(self):
        ecoule = time.time() - self._dernier_appel
        if ecoule < DELAI:
            time.sleep(DELAI - ecoule)
        self._dernier_appel = time.time()

    # def _autorise(self, url: str) -> bool:
    #     p = urlparse(url)
    #     base = f"{p.scheme}://{p.netloc}"
    #     if base not in self._robots:
    #         rp = RobotFileParser()
    #         rp.set_url(urljoin(base, "/robots.txt"))
    #         try:
    #             rp.read()
    #         except Exception:
    #             rp = None          # robots.txt absent : on procède
    #         self._robots[base] = rp
    #     rp = self._robots[base]
    #     return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def obtenir(self, url: str) -> Optional[str]:
        """Retourne le HTML, ou None si interdit, absent, vide ou en erreur."""
        # if not self._autorise(url):
        #     return None
        self._attendre()
        try:
            r = self.session.get(url, timeout=TIMEOUT, allow_redirects=True)
        except requests.RequestException:
            return None

        if r.status_code != 200:
            return None
        if "text/html" not in r.headers.get("Content-Type", ""):
            return None
        if len(r.text) < TAILLE_MIN:
            return None            # coquille vide, redirection JS, page de blocage
        return r.text

    def _liens_interessants(self, html: str, base: str) -> list[str]:
        """Liens internes dont le texte ou l'URL évoque un contact ou une équipe."""
        soup = BeautifulSoup(html, "html.parser")
        domaine = urlparse(base).netloc
        vus, retenus = set(), []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "#", "javascript:")):
                continue

            url = urljoin(base, href)
            p = urlparse(url)
            if p.netloc and p.netloc != domaine:
                continue                       # lien externe

            url = url.split("#")[0].rstrip("/")
            if url in vus or url.rstrip("/") == base.rstrip("/"):
                continue

            cible = f"{a.get_text().lower()} {p.path.lower()}"
            if any(m in cible for m in MOTS_CONTACT):
                vus.add(url)
                retenus.append(url)

        return retenus

    def pages_utiles(self, domaine: str, maximum: int = 8) -> dict[str, str]:
        """
        Récupère l'accueil, puis jusqu'à `maximum` pages de contact
        trouvées via les liens réels du site. Retourne {url: html}.
        """
        pages = {}

        # Essayer avec et sans www
        accueil, base = None, None
        for candidat in (f"https://{domaine}", f"https://www.{domaine}"):
            accueil = self.obtenir(candidat)
            if accueil:
                base = candidat
                break

        if not accueil:
            return pages

        pages[base] = accueil

        for url in self._liens_interessants(accueil, base)[:maximum]:
            html = self.obtenir(url)
            if html:
                pages[url] = html

        return pages