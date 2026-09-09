"""
Découverte d'entreprises par secteur et région.

L'interface SourceDecouverte permet de changer de fournisseur sans
toucher au reste du pipeline. Deux implémentations : Apify (Google Maps)
et un fichier CSV manuel pour tester sans consommer de crédit.
"""

import csv
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from .models import Entreprise


class SourceDecouverte(ABC):
    """Contrat commun à toutes les sources d'entreprises."""

    @abstractmethod
    def trouver(self, secteur: str, region: str, maximum: int = 50) -> List[Entreprise]:
        ...


class SourceApify(SourceDecouverte):
    """
    Découverte via Apify (actor Google Maps).

    Apify est utilisé ici parce que Google Maps bloque le scraping direct.
    L'enrichissement des sites d'entreprises, lui, est fait par notre code
    (src/scraper.py) : ces sites ne justifient pas une infrastructure de proxies.
    """

    ACTOR = "compass/crawler-google-places"

    def __init__(self, token: str | None = None):
        from apify_client import ApifyClient

        token = token or os.getenv("APIFY_TOKEN")
        if not token:
            raise ValueError("APIFY_TOKEN absent du fichier .env")
        self.client = ApifyClient(token)

    def trouver(self, secteur: str, region: str, maximum: int = 50) -> List[Entreprise]:
        run = self.client.actor(self.ACTOR).call(run_input={
            "searchStringsArray": [secteur],
            "locationQuery": region,
            "maxCrawledPlacesPerSearch": maximum,
            "language": "fr",
            "skipClosedPlaces": True,
            "scrapeContacts": True,         # courriels depuis le site de l'entreprise
            "scrapePlaceDetailPage": True,  # fiche complète
        })

        # Selon la version du client, run est un dict ou un objet
        dataset_id = (
            run["defaultDatasetId"] if isinstance(run, dict)
            else run.default_dataset_id
        )

        entreprises = []
        for item in self.client.dataset(dataset_id).iterate_items():
            emails = item.get("emails") or []
            entreprises.append(Entreprise(
                nom=(item.get("title") or "").strip(),
                ville=item.get("city"),
                domaine=self._domaine(item.get("website")),
                telephone=item.get("phone"),
                categorie=item.get("categoryName"),
                courriel=emails[0] if emails else None,
                source_decouverte="apify/google-maps",
            ))
        return [e for e in entreprises if e.nom]

    @staticmethod
    def _domaine(url: str | None) -> str | None:
        """Garde le domaine nu, sans schéma ni chemin."""
        if not url:
            return None
        net = urlparse(url if "://" in url else f"https://{url}").netloc
        return net.removeprefix("www.") or None



class SourceCSV(SourceDecouverte):
    """Liste préparée à la main. Utile pour tester sans crédit Apify."""

    def __init__(self, chemin: str | Path):
        self.chemin = Path(chemin)

    def trouver(self, secteur: str, region: str, maximum: int = 50) -> List[Entreprise]:
        entreprises = []
        with open(self.chemin, newline="", encoding="utf-8") as f:
            for ligne in csv.DictReader(f):
                entreprises.append(Entreprise(
                    nom=ligne["nom"],
                    ville=ligne.get("ville"),
                    domaine=ligne.get("domaine"),
                    categorie=ligne.get("categorie"),
                    source_decouverte=f"csv/{self.chemin.name}",
                ))
                if len(entreprises) >= maximum:
                    break
        return entreprises


def source_par_defaut() -> SourceDecouverte:
    """Apify si un jeton est configuré, sinon le CSV de test."""
    if os.getenv("APIFY_TOKEN"):
        return SourceApify()
    return SourceCSV("data/entreprises_test.csv")