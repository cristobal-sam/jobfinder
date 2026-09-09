import os
import json
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

# 1. LE NOM A CHANGÉ ICI (Pytest va l'ignorer)
def chercher_rh(url_compagnie: str, maximum: int = 3):
    token = os.getenv("APIFY_TOKEN")
    if not token:
        print("Erreur : APIFY_TOKEN introuvable.")
        return

    client = ApifyClient(token)
    acteur = "harvestapi/linkedin-company-employees"

    print(f"Extraction ciblée (RH/Recrutement) pour : {url_compagnie}...")

    run = client.actor(acteur).call(run_input={
        "companies": [url_compagnie],
        "maxItems": maximum,
        "recentlyChangedJobs": False,
        "jobTitle": ["HR", "RH", "Recruiter", "Recruteur", "Talent Acquisition"]
    })

    dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else run.default_dataset_id

    cibles_trouvees = []
    print("Récupération des profils...")
    print("-" * 40)

    for item in client.dataset(dataset_id).iterate_items():
        print(json.dumps(item, indent=2, ensure_ascii=False)[:800])
        print("---")

        prenom = item.get("firstName", "")
        nom_famille = item.get("lastName", "")
        nom_complet = f"{prenom} {nom_famille}".strip() or item.get("fullName", "Inconnu")
        titre = item.get("headline", "") or item.get("jobTitle", "")
        lien = item.get("linkedInUrl", "") or item.get("url", "")

        cibles_trouvees.append({
            "nom": nom_complet,
            "titre": titre,
            "lien": lien
        })

    if not cibles_trouvees:
        print(f"Aucun profil RH trouvé chez cette entreprise.")
    else:
        print(f"🎯 Cibles pertinentes trouvées ({len(cibles_trouvees)}) :")
        for cible in cibles_trouvees:
            print(f"- {cible['nom']} | {cible['titre']} | {cible['lien']}")

if __name__ == "__main__":
    # 2. LE NOM A CHANGÉ ICI AUSSI
    chercher_rh("https://www.linkedin.com/company/google")