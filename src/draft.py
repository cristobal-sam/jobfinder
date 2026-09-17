"""
Génération de messages personnalisés.

Deux modes :
  - gabarit fixe (rapide, prévisible, aucune dépendance)
  - Ollama en local (meilleure formulation, aucun coût, hors ligne)

L'IA ne sert QU'À reformuler le contexte déjà extrait du site.
Elle ne cherche rien et n'ajoute aucun fait — le prompt le lui interdit
explicitement, et la sortie est vérifiée avant utilisation.
"""

import os
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODELE = os.getenv("OLLAMA_MODELE", "qwen2.5:7b")
TIMEOUT = 90

# Identité de l'expéditeur : lue depuis le .env, jamais codée en dur.
# Voir .env.example pour les variables attendues.
SIGNATURE = os.getenv(
    "SENDER_SIGNATURE",
    "Prénom Nom\n000 000-0000 · linkedin.com/in/votre-profil",
)

PRESENTATION = os.getenv(
    "SENDER_PRESENTATION",
    "Je suis à la recherche d'une opportunité en cybersécurité "
    "et je serais heureux de vous présenter mon profil.",
)

# Mots très fréquents et propres à chaque langue
MOTS_FR = (" les ", " des ", " nos ", " vos ", " pour ", " avec ", " dans ",
           " sont ", " est ", " nous ", " vous ", " une ", " aux ", " par ",
           "entreprise", "services", "clientèle", "sécurité", "à", "é", "è")
MOTS_EN = (" the ", " and ", " our ", " your ", " for ", " with ", " are ",
           " you ", " we ", " that ", " this ", " from ", " have ",
           "business", "company", "solutions")
MOTS_ES = (" los ", " las ", " nuestros ", " para ", " con ", " que ",
           " una ", " sus ", "empresa", "servicios", "ñ")


def langue_de(entreprise: dict) -> str:
    """
    Détermine la langue du message à partir du TEXTE DU SITE.

    Plus fiable que la géographie : une entreprise anglophone à Montréal
    ou francophone à Toronto sera traitée correctement. Repli sur l'anglais,
    plus universel, quand le texte est trop court pour trancher.
    """
    texte = " " + (entreprise.get("contexte") or "").lower() + " "

    if len(texte.strip()) < 40:
        return "en"

    scores = {
        "fr": sum(texte.count(m) for m in MOTS_FR),
        "en": sum(texte.count(m) for m in MOTS_EN),
        "es": sum(texte.count(m) for m in MOTS_ES),
    }

    gagnante = max(scores, key=scores.get)
    return gagnante if scores[gagnante] >= 3 else "en"

def ollama_disponible() -> bool:
    """Vrai si le serveur Ollama répond."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


def accroche(nom: str, categorie: str, contexte: str) -> str | None:
    """
    Demande à Ollama une phrase d'accroche à partir du contexte extrait du site.
    Retourne None si le service est absent ou si la sortie est douteuse.
    """
    if not contexte or not ollama_disponible():
        return None

    prompt = (
        f"Entreprise : {nom}\n"
        f"Secteur : {categorie or 'non précisé'}\n"
        f"Texte relevé sur leur site : {contexte}\n\n"
        "Écris UNE seule phrase en français qui montre que j'ai lu leur site. "
        "Elle sert d'ouverture à une candidature spontanée en cybersécurité.\n\n"
        "Règles strictes :\n"
        "- une seule phrase, maximum 30 mots\n"
        "- n'invente aucun fait absent du texte ci-dessus\n"
        "- ne recopie pas de numéro de téléphone, de prix ni de slogan publicitaire\n"
        "- pas de flatterie, pas de « je suis impressionné »\n"
        "- commence par « Je vous écris parce que »\n"
        "- réponds uniquement par la phrase, sans guillemets ni commentaire"
    )

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODELE,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 80},
            },
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None

        texte = r.json().get("response", "").strip().strip('"').strip()

        # Garde-fous : longueur plausible, pas de numéro de téléphone
        if not (25 < len(texte) < 300):
            return None
        if any(c.isdigit() for c in texte) and texte.count("-") > 1:
            return None

        return texte.split("\n")[0].strip()

    except requests.RequestException:
        return None

def analyser_demande(texte: str) -> dict:
    """
    Transforme une demande en langage naturel en critères de recherche.
    Exemple : "je cherche un stage en cybersécurité autour de Montréal"
    -> {"secteur": "cybersecurite", "ville": "Montreal", "province": "Quebec"}
    """
    if not ollama_disponible():
        return {"secteur": texte[:40], "ville": "", "province": "Quebec", "auto": False}

    prompt = (
        f"Demande d'un chercheur d'emploi : \"{texte}\"\n\n"
        "Extrais les critères de recherche d'entreprises. Réponds UNIQUEMENT "
        "par un objet JSON, sans commentaire ni bloc de code, avec ces clés :\n"
        '{"secteur": "...", "ville": "...", "province": "..."}\n\n'
        "- secteur : le type d'entreprise à chercher sur Google Maps "
        "(ex: \"services informatiques\", \"cybersecurite\", \"comptabilite\")\n"
        "- ville : la ville mentionnée, sinon chaîne vide\n"
        "- province : la province, \"Quebec\" par défaut"
    )

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODELE, "prompt": prompt, "stream": False,
                  "format": "json", "options": {"temperature": 0.1}},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            raise ValueError("réponse non valide")

        import json
        data = json.loads(r.json().get("response", "{}"))

        return {
            "secteur": (data.get("secteur") or texte[:40]).strip(),
            "ville": (data.get("ville") or "").strip(),
            "province": (data.get("province") or "Quebec").strip(),
            "auto": True,
        }
    except Exception:
        return {"secteur": texte[:40], "ville": "", "province": "Quebec", "auto": False}


def message(entreprise: dict, type_gabarit: str = "emploi") -> dict:
    """
    Construit objet et corps du message.
    Utilise Ollama si disponible, sinon le gabarit fixe.
    """
    nom = entreprise.get("nom", "")
    categorie = entreprise.get("categorie", "")
    contexte = entreprise.get("contexte", "")

    phrase = accroche(nom, categorie, contexte)
    genere_par_ia = phrase is not None

    if not phrase:
        secteur = (categorie or "votre domaine").lower()
        phrase = f"Je vous écris parce que votre entreprise œuvre dans {secteur}."

    if type_gabarit == "fournisseur":
        objet = "Demande d'information — services"
        corps = (
            f"Bonjour,\n\n{phrase}\n\n"
            "Je suis à la recherche d'un fournisseur dans ce secteur et j'aimerais "
            "connaître vos services, vos délais et votre grille tarifaire.\n\n"
            "Auriez-vous quelques minutes pour en discuter ?\n\n"
            f"{SIGNATURE}"
        )
    else:
        objet = "Candidature spontanée — analyste sécurité junior"
        corps = (
            f"Bonjour,\n\n{phrase}\n\n"
            f"{PRESENTATION}\n\n"
            "Auriez-vous des besoins, même à temps partiel ou en stage ? "
            "Je serais heureux d'échanger quelques minutes.\n\n"
            f"{SIGNATURE}"
        )

    return {"objet": objet, "corps": corps, "ia": genere_par_ia}