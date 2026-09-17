# JobFinder (prospect-qc)

Outil de prospection pour la recherche d'emploi en cybersécurité au Québec.
Il découvre des entreprises par secteur et région, visite leurs sites pour en
extraire les courriels et le contexte, rédige un message de candidature
spontanée personnalisé, et n'envoie rien sans approbation explicite.

## Ce que fait le pipeline

1. **Analyse de la demande** — une phrase en langage naturel
   (« je cherche un stage en cybersécurité autour de Montréal ») est convertie
   en critères de recherche par un LLM local (Ollama), avec repli hors ligne.
2. **Découverte** (`src/search.py`) — entreprises trouvées via Apify
   (actor Google Maps) : nom, ville, site, téléphone, catégorie. Un mode CSV
   (`data/entreprises_test.csv`) permet de tester sans crédit Apify.
3. **Enrichissement** (`src/scraper.py`, `src/extract.py`) — visite polie du
   site de chaque entreprise : robots.txt respecté, cadence limitée,
   User-Agent identifiable. Extraction des courriels (priorité aux liens
   `mailto:` et aux boîtes RH), du contexte descriptif et de la page carrières.
4. **Rédaction** (`src/draft.py`) — accroche générée par Ollama **uniquement
   à partir du texte réellement lu sur le site** (le prompt interdit
   d'inventer des faits et la sortie est vérifiée). Repli sur un gabarit fixe
   si Ollama est absent. Langue du message (fr/en/es) détectée depuis le
   texte du site.
5. **Envoi contrôlé** (`src/send.py`) — Gmail SMTP, uniquement après
   approbation dans l'interface, avec limite quotidienne (`DAILY_LIMIT`) et
   journal (`data/envois.csv`) empêchant de recontacter deux fois la même
   adresse.
6. **Interface web** (`web/`) — FastAPI + carte Leaflet : résultats groupés
   par ville (arrondissements fusionnés), enrichissement à la demande,
   sauvegarde cumulative sans doublons, envoi validé à la main.

## Choix d'éthique

- **Pas de scraping LinkedIn** : retiré du projet (données personnelles sans
  consentement, violation des CGU LinkedIn).
- **L'IA n'invente rien** : elle reformule seulement ce qui a été lu.
- **Pas d'envoi en masse** : chaque courriel part après validation humaine.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # puis remplir les valeurs
```

## Lancement

```bash
uvicorn web.app:app --reload --port 8000
```

Ouvrir http://localhost:8000 — la page de connexion est une **maquette
visuelle** : n'importe quelle saisie mène à l'application (outil personnel,
aucune authentification réelle).

## Configuration (`.env`)

| Variable | Rôle | Requis |
|---|---|---|
| `APIFY_TOKEN` | Découverte Google Maps via Apify | non (repli CSV) |
| `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` | Envoi SMTP (mot de passe d'application Google) | pour l'envoi |
| `SENDER_SIGNATURE` / `SENDER_PRESENTATION` | Identité insérée dans les messages | oui |
| `OLLAMA_URL` / `OLLAMA_MODELE` | LLM local pour l'analyse et les accroches | non (gabarit fixe) |
| `DAILY_LIMIT` | Quota d'envois par jour (défaut 5) | non |
| `REQUEST_DELAY` / `USER_AGENT` | Politesse du scraper | non |

## Tests

```bash
pytest
```

## Structure

```
src/
  models.py    dataclass Entreprise partagée
  search.py    sources de découverte (Apify, CSV)
  scraper.py   client HTTP poli (robots.txt, cadence)
  extract.py   courriels, contexte, page carrières
  draft.py     analyse de la demande, génération du message
  send.py      envoi Gmail + journal anti-doublon
web/
  app.py       API FastAPI
  static/      interface (carte Leaflet)
tests/         tests unitaires (extraction, rédaction)
```
