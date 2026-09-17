"""
Serveur web de prospect-qc.

Sert l'interface et expose les endpoints appelés par le navigateur.
Le pipeline vit dans src/ — le serveur ne fait que l'orchestrer.

Lancer :  uvicorn web.app:app --reload --port 8000
"""

import csv
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

CHAMPS = ["nom", "ville", "domaine", "courriel", "telephone",
          "categorie", "contexte", "carrieres", "date_ajout"]

load_dotenv()

STATIC = Path(__file__).parent / "static"
FICHIER_DONNEES = Path("data/entreprises.csv")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 5))

app = FastAPI(title="prospect-qc")


# ---------- modèles ----------

class RequeteRecherche(BaseModel):
    secteur: str
    region: str
    maximum: int = 2          # défaut prudent


class RequeteEnrichir(BaseModel):
    domaine: str


class RequeteEnvoi(BaseModel):
    destinataire: str
    objet: str
    message: str
    entreprise: str = ""

class RequeteAnalyse(BaseModel):
    texte: str


@app.post("/api/analyser")
def analyser(req: RequeteAnalyse):
    """Transforme une demande en langage naturel en critères de recherche."""
    from src.draft import analyser_demande
    return analyser_demande(req.texte)


@app.post("/api/villes")
def par_ville(req: RequeteRecherche):
    """
    Découverte, puis regroupement par ville — sans enrichissement.
    Les entreprises déjà présentes dans le CSV sont écartées, et on
    demande davantage de résultats à Apify pour compenser.
    """
    from src.search import source_par_defaut

    # Arrondissements et secteurs regroupés sous leur ville
    FUSIONS = {
        # Montréal
        "lachine": "Montreal", "verdun": "Montreal", "lasalle": "Montreal",
        "saint-laurent": "Montreal", "saint-leonard": "Montreal",
        "anjou": "Montreal", "outremont": "Montreal", "westmount": "Montreal",
        "montreal-nord": "Montreal", "riviere-des-prairies": "Montreal",
        "pierrefonds": "Montreal", "ahuntsic": "Montreal", "cartierville": "Montreal",
        "cote-des-neiges": "Montreal", "hochelaga": "Montreal", "rosemont": "Montreal",
        "villeray": "Montreal", "mercier": "Montreal", "ville-marie": "Montreal",
        "le plateau-mont-royal": "Montreal", "le sud-ouest": "Montreal",
        # Québec
        "sainte-foy": "Quebec", "beauport": "Quebec", "charlesbourg": "Quebec",
        "sillery": "Quebec", "loretteville": "Quebec",
        # Autres
        "chicoutimi": "Saguenay", "jonquiere": "Saguenay",
        "hull": "Gatineau", "aylmer": "Gatineau",
        "saint-hubert": "Longueuil", "greenfield park": "Longueuil",
    }

    def normaliser_ville(ville: str) -> str:
        """Ramène un arrondissement à sa ville. Google Maps les distingue."""
        if not ville:
            return "Non precise"

        v = ville.strip()
        cle = (v.lower()
               .replace("é", "e").replace("è", "e").replace("ê", "e")
               .replace("î", "i").replace("ô", "o").replace("à", "a")
               .replace("ç", "c").replace("û", "u"))

        for arr, principale in FUSIONS.items():
            if arr in cle:
                return principale

        # Normaliser aussi les villes principales, pour que « Montréal »
        # et « Montreal » ne fassent pas deux groupes distincts
        for principale in set(FUSIONS.values()):
            if principale.lower() in cle:
                return principale

        return v

    # Ce qu'on connaît déjà
    connus = set()
    if FICHIER_DONNEES.exists():
        with open(FICHIER_DONNEES, encoding="utf-8", newline="") as f:
            for l in csv.DictReader(f):
                if l.get("domaine"):
                    connus.add(l["domaine"].lower())
                if l.get("nom"):
                    connus.add(l["nom"].lower())

    # Marge de 60 % pour compenser les doublons écartés
    demande = req.maximum + max(3, int(req.maximum * 0.6)) if connus else req.maximum

    entreprises = source_par_defaut().trouver(req.secteur, req.region, maximum=demande)

    nouvelles, ecartes = [], 0
    for e in entreprises:
        cle_dom = (e.domaine or "").lower()
        cle_nom = (e.nom or "").lower()
        if (cle_dom and cle_dom in connus) or (cle_nom and cle_nom in connus):
            ecartes += 1
            continue
        nouvelles.append(e)
        if len(nouvelles) >= req.maximum:
            break

    groupes = {}
    for i, e in enumerate(nouvelles, start=1):
        e.id = i
        ville = normaliser_ville(e.ville)
        groupes.setdefault(ville, []).append(e.to_dict())

    return {
        "total": len(nouvelles),
        "ecartes": ecartes,
        "villes": [
            {"ville": v, "nombre": len(lst), "entreprises": lst}
            for v, lst in sorted(groupes.items(), key=lambda x: -len(x[1]))
        ],
    }
# ---------- pages ----------

@app.get("/")
def accueil():
    return FileResponse(STATIC / "login.html")


@app.get("/app")
def application():
    return FileResponse(STATIC / "Page.html")


# ---------- pipeline ----------

@app.post("/api/search")
def rechercher(req: RequeteRecherche):
    """Découverte seulement — rapide, retourne la liste sans enrichissement."""
    from src.search import source_par_defaut

    entreprises = source_par_defaut().trouver(req.secteur, req.region, maximum=req.maximum)
    for i, e in enumerate(entreprises, start=1):
        e.id = i
        e.statut = "attente" if e.courriel else "a-enrichir"
    return [e.to_dict() for e in entreprises]


@app.post("/api/enrich")
def enrichir(req: RequeteEnrichir):
    """Visite un seul site et retourne courriel + contexte."""
    from src.scraper import Visiteur
    from src.extract import (courriels, courriels_mailto,
                             meilleur_courriel, meilleur_contexte)

    pages = Visiteur().pages_utiles(req.domaine)
    if not pages:
        return {"courriel": None, "contexte": None, "pages": 0}

    tous, mailtos = [], []
    for html in pages.values():
        tous += courriels(html)
        mailtos += courriels_mailto(html)

    from src.extract import page_carrieres
    return {
        "courriel": meilleur_courriel(tous, req.domaine, prioritaires=mailtos),
        "contexte": meilleur_contexte(pages),
        "carrieres": page_carrieres(pages),
        "pages": len(pages),
    }


# ---------- persistance ----------

@app.post("/api/save")
def sauvegarder(donnees: list[dict]):
    """Ajoute les résultats au CSV cumulatif, sans doublons."""
    FICHIER_DONNEES.parent.mkdir(exist_ok=True)

    existants = set()
    if FICHIER_DONNEES.exists():
        with open(FICHIER_DONNEES, encoding="utf-8", newline="") as f:
            existants = {l.get("domaine") or l.get("nom") for l in csv.DictReader(f)}

    nouveaux = [d for d in donnees if (d.get("domaine") or d.get("nom")) not in existants]

    with open(FICHIER_DONNEES, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS, extrasaction="ignore")
        if not existants:
            w.writeheader()
        for d in nouveaux:
            w.writerow({**d, "date_ajout": date.today().isoformat()})

    return {"ajoutes": len(nouveaux), "ignores": len(donnees) - len(nouveaux)}


@app.get("/api/historique")
def historique():
    """Tout ce qui a été sauvegardé jusqu'ici."""
    if not FICHIER_DONNEES.exists():
        return []
    with open(FICHIER_DONNEES, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

class RequeteSupprimer(BaseModel):
    cles: list[str]          # domaines ou noms à retirer

@app.get("/api/contactes")
def contactes():
    """Liste des adresses déjà contactées, pour marquer l'interface."""
    from src.send import JOURNAL
    if not JOURNAL.exists():
        return []
    with open(JOURNAL, encoding="utf-8", newline="") as f:
        return [l["destinataire"].lower() for l in csv.DictReader(f)]
@app.post("/api/delete")
def supprimer(req: RequeteSupprimer):
    """Retire des lignes du CSV cumulatif."""
    if not FICHIER_DONNEES.exists():
        return {"supprimes": 0}

    with open(FICHIER_DONNEES, encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))

    a_retirer = set(req.cles)
    gardees = [l for l in lignes
               if (l.get("domaine") or l.get("nom")) not in a_retirer]

    with open(FICHIER_DONNEES, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS, extrasaction="ignore")
        w.writeheader()
        w.writerows(gardees)

    return {"supprimes": len(lignes) - len(gardees)}

# ---------- envoi ----------

@app.get("/api/quota")
def quota():
    """Combien d'envois restent aujourd'hui."""
    from src.send import envois_du_jour
    utilises = envois_du_jour()
    return {"utilises": utilises, "limite": DAILY_LIMIT,
            "restants": max(0, DAILY_LIMIT - utilises)}


@app.post("/api/send")
def envoyer_message(req: RequeteEnvoi):
    """Envoi APRÈS approbation explicite. Limite vérifiée côté serveur."""
    from src.send import envoyer, deja_contacte

    etat = quota()
    if etat["utilises"] >= etat["limite"]:
        raise HTTPException(429, f"Limite quotidienne atteinte ({etat['limite']} envois).")

    if deja_contacte(req.destinataire):
        raise HTTPException(409, f"{req.destinataire} a déjà été contacté.")

    try:
        return envoyer(req.destinataire, req.objet, req.message, req.entreprise)
    except Exception as e:
        raise HTTPException(500, f"Échec de l'envoi : {e}")


# Note : la recherche de profils LinkedIn a été retirée du projet — elle
# collecte des données personnelles d'individus sans consentement et viole
# les conditions d'utilisation de LinkedIn.

class RequeteMessage(BaseModel):
    entreprise: dict
    type_gabarit: str = "emploi"


@app.post("/api/message")
def generer_message(req: RequeteMessage):
    """Génère objet et corps pour une entreprise."""
    from src.draft import message
    return message(req.entreprise, req.type_gabarit)


@app.get("/api/ollama")
def etat_ollama():
    from src.draft import ollama_disponible, OLLAMA_MODELE
    return {"disponible": ollama_disponible(), "modele": OLLAMA_MODELE}


@app.get("/api/identite")
def identite():
    """Signature et présentation de l'expéditeur (lues du .env)."""
    from src.draft import SIGNATURE, PRESENTATION
    return {"signature": SIGNATURE, "presentation": PRESENTATION}
# doit rester la dernière ligne : sinon ce montage intercepte les routes ci-dessus
app.mount("/static", StaticFiles(directory=STATIC), name="static")