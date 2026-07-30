"""Tests automatisés des outils publics du Stock MCP."""

import asyncio

import pytest
from fastmcp import Client
from sqlalchemy.exc import OperationalError

import server


FREJUS = {
    "branch_id": 1,
    "branch_name": "Fréjus Centre",
    "city": "Fréjus",
}


def test_serveur_expose_des_outils_aux_descriptions_compactes():
    async def list_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())

    assert {tool.name for tool in tools} == {
        "find_branches",
        "get_stock_by_branch_name",
        "get_stock_by_product",
        "get_stock_by_branch",
        "check_availability",
    }
    assert sum(len(tool.description or "") for tool in tools) < 1000


def _ajouter_succursale(nom, ville):
    """Ajoute une succursale active au catalogue de test."""
    with server.SessionLocal() as session:
        branch = server.Branch(name=nom, city=ville)
        session.add(branch)
        session.commit()
        return branch.id


@pytest.mark.parametrize(
    "recherche",
    ["Fréjus", "fréjus", "FRÉJUS", "frejus", "jus cen", "  Fréjus  "],
)
def test_find_branches_accepte_casse_accents_et_nom_partiel(recherche):
    result = server.find_branches(recherche)

    assert result["success"] is True
    assert result["count"] == 1
    assert result["branches"] == [FREJUS]


def test_find_branches_sans_nom_liste_les_succursales_actives():
    _ajouter_succursale("Laval Gare", "Laval")

    result = server.find_branches("")

    assert result["success"] is True
    assert result["count"] == 2
    assert [branch["branch_name"] for branch in result["branches"]] == [
        "Fréjus Centre",
        "Laval Gare",
    ]
    # La succursale désactivée n'est jamais proposée.
    assert all(
        branch["branch_name"] != "Ancienne boutique"
        for branch in result["branches"]
    )


def test_find_branches_retourne_plusieurs_correspondances_triees():
    second = _ajouter_succursale("Fréjus Plage", "Fréjus")

    result = server.find_branches("frejus")

    assert result["success"] is True
    assert result["count"] == 2
    assert [branch["branch_id"] for branch in result["branches"]] == [
        FREJUS["branch_id"],
        second,
    ]


def test_find_branches_sans_correspondance_reste_un_succes():
    result = server.find_branches("Bordeaux")

    assert result["success"] is True
    assert result["count"] == 0
    assert result["branches"] == []
    assert result["error"] is None


@pytest.mark.parametrize("recherche", [None, 3, ["Fréjus"]])
def test_find_branches_refuse_un_nom_non_textuel(recherche):
    result = server.find_branches(recherche)

    assert result["success"] is False
    assert result["branches"] == []
    assert result["error"]


class SessionInjoignable:
    """Session dont la requête échoue, comme si PostgreSQL était arrêté.

    SQLAlchemy ouvre la connexion paresseusement : la panne se
    manifeste à l'exécution de la requête, pas à la création de la
    session.
    """

    def query(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connexion"))

    def close(self):
        pass


def test_find_branches_signale_une_base_injoignable(monkeypatch):
    monkeypatch.setattr(server, "SessionLocal", SessionInjoignable)
    result = server.find_branches("Fréjus")

    assert result["success"] is False
    assert result["count"] == 0
    assert result["branches"] == []
    assert "base de donnees" in result["error"]


@pytest.mark.parametrize(
    "recherche",
    ["Fréjus", "frejus", "FRÉJUS CENTRE", "  fréjus  "],
)
def test_stock_par_nom_evite_deux_appels_sequentiels(recherche):
    result = server.get_stock_by_branch_name(recherche)

    assert result == {
        "success": True,
        "query": recherche,
        "count": 1,
        "branches": [{
            **FREJUS,
            "products": [{"product_id": 1, "quantity": 5}],
        }],
        "error": None,
    }


def test_stock_par_nom_accepte_la_ville():
    branch_id = _ajouter_succursale("Boutique du Centre", "Laval")
    _remplir(branch_id, {7: 3})

    result = server.get_stock_by_branch_name("laval")

    assert result["count"] == 1
    assert result["branches"] == [{
        "branch_id": branch_id,
        "branch_name": "Boutique du Centre",
        "city": "Laval",
        "products": [{"product_id": 7, "quantity": 3}],
    }]


def test_stock_par_nom_sans_correspondance_reste_un_succes():
    result = server.get_stock_by_branch_name("Bordeaux")

    assert result["success"] is True
    assert result["count"] == 0
    assert result["branches"] == []


@pytest.mark.parametrize("recherche", ["", "   ", None, 3])
def test_stock_par_nom_refuse_une_recherche_invalide(recherche):
    result = server.get_stock_by_branch_name(recherche)

    assert result["success"] is False
    assert result["count"] == 0
    assert result["branches"] == []
    assert result["error"]


def test_stock_par_nom_signale_une_base_injoignable(monkeypatch):
    monkeypatch.setattr(server, "SessionLocal", SessionInjoignable)

    result = server.get_stock_by_branch_name("Fréjus")

    assert result["success"] is False
    assert "base de donnees" in result["error"]


def test_get_stock_by_branch_utilise_l_identifiant_de_find_branches():
    """Le contrat entre les deux outils reste utilisable tel quel."""
    trouvee = server.find_branches("Fréjus")["branches"][0]

    result = server.get_stock_by_branch(trouvee["branch_id"])

    assert result["success"] is True
    assert result["branch_name"] == trouvee["branch_name"]


def test_get_stock_by_product_exclut_stock_nul_et_succursale_inactive():
    result = server.get_stock_by_product(1)

    assert result["success"] is True
    assert result["branches"] == [{
        "branch_id": 1,
        "branch_name": "Fréjus Centre",
        "city": "Fréjus",
        "quantity": 5,
    }]


def test_get_stock_by_branch_exclut_les_quantites_nulles():
    result = server.get_stock_by_branch(1)

    assert result["success"] is True
    assert result["products"] == [{"product_id": 1, "quantity": 5}]


@pytest.mark.parametrize("identifier", [0, -1, True, "1", None])
def test_identifiants_invalides_sont_refuses(identifier):
    product = server.get_stock_by_product(identifier)
    branch = server.get_stock_by_branch(identifier)

    assert product["success"] is False
    assert branch["success"] is False


@pytest.mark.parametrize(
    "items",
    [
        [],
        None,
        [{}],
        [{"product_id": 0, "quantity": 1}],
        [{"product_id": 1, "quantity": 0}],
        [{"product_id": 1, "quantity": -2}],
        [
            {"product_id": 1, "quantity": 1},
            {"product_id": 1, "quantity": 2},
        ],
    ],
)
def test_disponibilite_refuse_les_demandes_invalides(items):
    result = server.check_availability(items)

    assert result["success"] is False
    assert result["fully_available_branches"] == []
    assert result["error"]


def test_disponibilite_ne_retient_que_les_stocks_suffisants():
    result = server.check_availability([
        {"product_id": 1, "quantity": 4},
        {"product_id": 2, "quantity": 1},
    ])

    assert result["success"] is True
    assert result["fully_available_branches"] == []
    assert result["per_branch_breakdown"] == [{
        "branch_id": 1,
        "branch_name": "Fréjus Centre",
        "city": "Fréjus",
        "items": [
            {
                "product_id": 1,
                "requested": 4,
                "available": 5,
                "sufficient": True,
            },
            {
                "product_id": 2,
                "requested": 1,
                "available": 0,
                "sufficient": False,
            },
        ],
    }]


def test_disponibilite_trouve_une_succursale_pour_toute_la_liste():
    with server.SessionLocal() as session:
        branch = session.query(server.Branch).filter_by(
            name="Fréjus Centre"
        ).one()
        session.add_all([
            server.Stock(branch_id=branch.id, product_id=3, quantity=2),
            server.Stock(branch_id=branch.id, product_id=7, quantity=4),
        ])
        session.commit()

    result = server.check_availability([
        {"product_id": 1, "quantity": 3},
        {"product_id": 3, "quantity": 2},
        {"product_id": 7, "quantity": 4},
    ])

    assert result["success"] is True
    assert result["fully_available_branches"] == [{
        "branch_id": 1,
        "branch_name": "Fréjus Centre",
        "city": "Fréjus",
    }]
    # Une succursale suffit : le plan ne fait visiter qu'elle.
    assert result["branches_needed"] == 1
    assert result["fully_covered"] is True
    assert result["unfulfillable"] == []
    assert result["pickup_plan"] == [{
        "branch_id": 1,
        "branch_name": "Fréjus Centre",
        "city": "Fréjus",
        "items": [
            {"product_id": 1, "quantity": 3, "available": 5},
            {"product_id": 3, "quantity": 2, "available": 2},
            {"product_id": 7, "quantity": 4, "available": 4},
        ],
    }]


def _remplir(branch_id, quantites):
    """Ajoute des lignes de stock à une succursale existante."""
    with server.SessionLocal() as session:
        session.add_all([
            server.Stock(
                branch_id=branch_id,
                product_id=product_id,
                quantity=quantity,
            )
            for product_id, quantity in quantites.items()
        ])
        session.commit()


def test_repartition_sur_deux_succursales_quand_aucune_ne_suffit():
    """Fréjus a le produit 1, Laval le produit 9 : il faut les deux."""
    laval = _ajouter_succursale("Laval Gare", "Laval")
    _remplir(laval, {9: 6})

    result = server.check_availability([
        {"product_id": 1, "quantity": 4},
        {"product_id": 9, "quantity": 2},
    ])

    assert result["success"] is True
    assert result["fully_available_branches"] == []
    assert result["branches_needed"] == 2
    assert result["fully_covered"] is True
    assert result["unfulfillable"] == []
    assert result["pickup_plan"] == [
        {
            "branch_id": 1,
            "branch_name": "Fréjus Centre",
            "city": "Fréjus",
            "items": [
                {"product_id": 1, "quantity": 4, "available": 5},
            ],
        },
        {
            "branch_id": laval,
            "branch_name": "Laval Gare",
            "city": "Laval",
            "items": [
                {"product_id": 9, "quantity": 2, "available": 6},
            ],
        },
    ]


def test_repartition_signale_la_partie_impossible():
    """Le plan retire ce qui existe et déclare le reste introuvable."""
    laval = _ajouter_succursale("Laval Gare", "Laval")
    _remplir(laval, {1: 2})

    result = server.check_availability([
        {"product_id": 1, "quantity": 10},
    ])

    assert result["success"] is True
    assert result["fully_covered"] is False
    assert result["branches_needed"] == 2
    assert [stop["branch_id"] for stop in result["pickup_plan"]] == [1, laval]
    assert result["unfulfillable"] == [{
        "product_id": 1,
        "requested": 10,
        "covered": 7,
        "missing": 3,
    }]


def test_repartition_declare_un_produit_inconnu_introuvable():
    """Un product_id absent de tout stock n'est jamais inventé."""
    result = server.check_availability([
        {"product_id": 1, "quantity": 2},
        {"product_id": 999, "quantity": 1},
    ])

    assert result["success"] is True
    assert result["fully_covered"] is False
    assert result["fully_available_branches"] == []
    assert result["pickup_plan"] == [{
        "branch_id": 1,
        "branch_name": "Fréjus Centre",
        "city": "Fréjus",
        "items": [{"product_id": 1, "quantity": 2, "available": 5}],
    }]
    assert result["unfulfillable"] == [{
        "product_id": 999,
        "requested": 1,
        "covered": 0,
        "missing": 1,
    }]


@pytest.mark.parametrize(
    "items",
    [
        [{"product_id": 1, "quantity": 0}],
        [{"product_id": 1, "quantity": -3}],
        [{"product_id": 1, "quantity": 2.5}],
        [{"product_id": 1, "quantity": True}],
        [{"product_id": 1, "quantity": "2"}],
    ],
)
def test_repartition_refuse_une_quantite_invalide(items):
    result = server.check_availability(items)

    assert result["success"] is False
    assert result["pickup_plan"] == []
    assert result["branches_needed"] == 0
    assert result["fully_covered"] is False
    assert result["error"]


def test_repartition_departage_deux_solutions_equivalentes():
    """À égalité stricte, le plus petit branch_id est toujours choisi."""
    laval = _ajouter_succursale("Laval Gare", "Laval")
    _remplir(laval, {1: 5})

    premier = server.check_availability([{"product_id": 1, "quantity": 3}])
    second = server.check_availability([{"product_id": 1, "quantity": 3}])

    assert premier["branches_needed"] == 1
    assert premier["pickup_plan"][0]["branch_id"] == 1
    assert premier["pickup_plan"][0]["branch_id"] < laval
    # Le résultat ne dépend pas de l'ordre de parcours : il est stable.
    assert premier == second


def test_repartition_reste_valide_meme_sans_etre_minimale():
    """L'heuristique n'est pas optimale, mais son plan reste exploitable.

    Succursale 1 : 5 X ; succursale 2 : 5 Y ; succursale 3 : 3 X + 3 Y.
    Pour 5 X et 5 Y, le glouton commence par la succursale 3 (6 unités
    couvertes, le meilleur premier pas) puis doit compléter avec les
    deux autres : TROIS arrêts là où DEUX suffiraient. C'est la limite
    assumée de l'heuristique. Ce test verrouille ce qui est réellement
    garanti : commande couverte, aucune succursale visitée deux fois,
    jamais plus que le stock disponible, résultat stable.
    """
    x, y = 11, 12
    demande = [
        {"product_id": x, "quantity": 5},
        {"product_id": y, "quantity": 5},
    ]
    _remplir(1, {x: 5})
    deuxieme = _ajouter_succursale("Laval Gare", "Laval")
    _remplir(deuxieme, {y: 5})
    troisieme = _ajouter_succursale("Toulouse Capitole", "Toulouse")
    _remplir(troisieme, {x: 3, y: 3})

    result = server.check_availability(demande)

    assert result["success"] is True
    assert result["fully_covered"] is True
    assert result["unfulfillable"] == []

    visitees = [stop["branch_id"] for stop in result["pickup_plan"]]
    assert set(visitees) <= {1, deuxieme, troisieme}
    assert len(visitees) == len(set(visitees))
    assert result["branches_needed"] == len(visitees)

    # Chaque ligne du plan tient dans le stock réel de la succursale...
    ramasse = {x: 0, y: 0}
    for stop in result["pickup_plan"]:
        for item in stop["items"]:
            assert 0 < item["quantity"] <= item["available"]
            ramasse[item["product_id"]] += item["quantity"]
    # ... et l'ensemble couvre exactement la commande, sans excédent.
    assert ramasse == {x: 5, y: 5}

    # Le plan ne dépend pas de l'ordre de parcours : il est stable.
    assert server.check_availability(demande) == result


def test_repartition_impossible_recupere_tout_le_stock_disponible():
    """Commande impossible : le plan ramasse quand même tout ce qui existe.

    Succursale 1 : 4 X ; succursale 2 : 4 X ; succursale 3 : 2 X, soit
    10 unités en tout pour une demande de 12. La commande ne peut pas
    être honorée en entier : le plan doit quand même récupérer les 10
    unités disponibles, ce qui impose ici les trois succursales.
    """
    x = 21
    _remplir(1, {x: 4})
    deuxieme = _ajouter_succursale("Laval Gare", "Laval")
    _remplir(deuxieme, {x: 4})
    troisieme = _ajouter_succursale("Toulouse Capitole", "Toulouse")
    _remplir(troisieme, {x: 2})

    result = server.check_availability([{"product_id": x, "quantity": 12}])

    assert result["success"] is True
    assert result["fully_covered"] is False
    # Les 10 unités disponibles exigent les trois succursales.
    assert result["branches_needed"] == 3
    assert [stop["branch_id"] for stop in result["pickup_plan"]] == [
        1, deuxieme, troisieme,
    ]
    assert result["unfulfillable"] == [
        {"product_id": x, "requested": 12, "covered": 10, "missing": 2},
    ]


def test_repartition_impossible_ignore_une_succursale_inutile():
    """Une succursale sans le produit demandé n'apparaît pas dans le plan.

    Succursale 1 : 6 X ; succursale 2 : 2 X. Pour 10 X, la couverture
    plafonne à 8 unités et mobilise ces deux succursales ; une
    troisième, qui ne stocke pas X, n'apporterait rien et ne doit pas
    faire partie des arrêts.
    """
    x = 31
    _remplir(1, {x: 6})
    deuxieme = _ajouter_succursale("Laval Gare", "Laval")
    _remplir(deuxieme, {x: 2})
    inutile = _ajouter_succursale("Toulouse Capitole", "Toulouse")
    _remplir(inutile, {99: 50})

    result = server.check_availability([{"product_id": x, "quantity": 10}])

    assert result["fully_covered"] is False
    assert result["branches_needed"] == 2
    assert [stop["branch_id"] for stop in result["pickup_plan"]] == [
        1, deuxieme,
    ]
    assert inutile not in [stop["branch_id"] for stop in result["pickup_plan"]]
