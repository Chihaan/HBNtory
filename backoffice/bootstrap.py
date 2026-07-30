"""Initialise le backoffice.

Complète les données de démonstration manquantes, sans jamais écraser
celles qui existent déjà.
"""

from init_db import configure_readonly_role, create_tables
from seed import main as seed_database


def main() -> None:
    """Prépare le schéma, puis complète ce qui manque en base.

    La seed est une fusion : elle ne crée que les succursales, comptes et
    stocks absents, ne modifie aucun mot de passe et ne supprime rien.
    On peut donc la relancer à chaque démarrage sans risque.

    C'est même nécessaire : une base peut contenir des utilisateurs sans
    aucune succursale ni stock (schéma créé avant la seed, comptes créés
    à la main, seed interrompue). Conditionner la seed à « la base
    est-elle vide ? » laisserait ces bases incomplètes pour toujours.
    """
    create_tables()
    configure_readonly_role()
    seed_database()


if __name__ == "__main__":
    main()
