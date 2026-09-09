"""Structures de données partagées par tout le pipeline."""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Entreprise:
    """Une entreprise trouvée, enrichie au fil du pipeline."""

    # Phase 1 — découverte
    nom: str
    id: int = 0
    ville: Optional[str] = None
    domaine: Optional[str] = None
    telephone: Optional[str] = None
    categorie: Optional[str] = None
    source_decouverte: str = ""

    # Phase 2 — enrichissement (notre code)
    courriel: Optional[str] = None
    page_source: Optional[str] = None

    # Phase 3 — contexte
    contexte: Optional[str] = None

    # Phase 4 — message
    objet: Optional[str] = None
    message: Optional[str] = None

    # Suivi
    statut: str = "nouveau"   # nouveau | attente | envoye | sans-courriel | retire

    def to_dict(self) -> dict:
        return asdict(self)