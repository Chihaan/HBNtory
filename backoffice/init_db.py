"""Crée toutes les tables dans la base.

À lancer une fois après le démarrage de PostgreSQL, et à relancer
après toute modification des modèles (voir README pour la remise à zéro).
"""

from db import Base, engine
import models  # noqa: F401 — enregistre les modèles dans Base.metadata


def main() -> None:
    Base.metadata.create_all(engine)
    print("Tables créées :", ", ".join(Base.metadata.tables))


if __name__ == "__main__":
    main()
