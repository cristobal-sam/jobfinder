"""
Envoi de courriels via Gmail SMTP.

Aucun envoi n'est déclenché ailleurs que depuis l'endpoint /api/send,
lui-même appelé uniquement après approbation explicite dans l'interface.
Un journal empêche de recontacter deux fois la même adresse.
"""

import csv
import os
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

JOURNAL = Path("data/envois.csv")
CHAMPS = ["date_heure", "destinataire", "entreprise", "objet"]


def envois_du_jour() -> int:
    """Combien de courriels ont déjà été envoyés aujourd'hui."""
    if not JOURNAL.exists():
        return 0
    aujourdhui = date.today().isoformat()
    with open(JOURNAL, encoding="utf-8", newline="") as f:
        return sum(1 for l in csv.DictReader(f)
                   if l["date_heure"].startswith(aujourdhui))


def deja_contacte(destinataire: str) -> bool:
    """Vrai si cette adresse a déjà reçu un message."""
    if not JOURNAL.exists():
        return False
    with open(JOURNAL, encoding="utf-8", newline="") as f:
        return any(l["destinataire"].lower() == destinataire.lower()
                   for l in csv.DictReader(f))


def journaliser(destinataire: str, entreprise: str, objet: str):
    JOURNAL.parent.mkdir(exist_ok=True)
    nouveau = not JOURNAL.exists()
    with open(JOURNAL, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS)
        if nouveau:
            w.writeheader()
        w.writerow({
            "date_heure": datetime.now().isoformat(timespec="seconds"),
            "destinataire": destinataire,
            "entreprise": entreprise,
            "objet": objet,
        })


def envoyer(destinataire: str, objet: str, corps: str, entreprise: str = "") -> dict:
    """Envoie un courriel et le journalise. Lève une exception en cas d'échec."""
    expediteur = os.getenv("GMAIL_ADDRESS")
    mot_de_passe = os.getenv("GMAIL_APP_PASSWORD")

    if not expediteur or not mot_de_passe:
        raise ValueError("GMAIL_ADDRESS ou GMAIL_APP_PASSWORD absent du .env")

    msg = EmailMessage()
    msg["From"] = expediteur
    msg["To"] = destinataire
    msg["Subject"] = objet
    msg.set_content(corps)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
        serveur.login(expediteur, mot_de_passe.replace(" ", ""))
        serveur.send_message(msg)

    journaliser(destinataire, entreprise, objet)
    return {"envoye": True, "destinataire": destinataire}