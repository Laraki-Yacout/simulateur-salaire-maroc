"""Tests du mode négociation (net -> brut) et de la route /api/brut-pour-net."""

import pytest

from calcul import alerte_seuil, brut_pour_net, calcul_salaire, zone_piege


def texte(message):
    """Message avec des espaces ordinaires (l'API met des espaces insécables)."""
    return message.replace("\u00a0", " ")


@pytest.mark.parametrize("net_vise", [3000, 5000, 8000, 8857.69, 15000, 40000])
def test_plus_petit_brut_entier(net_vise):
    brut = brut_pour_net(net_vise)
    assert calcul_salaire(brut)["net"] >= net_vise
    assert calcul_salaire(brut - 1)["net"] < net_vise


def test_aller_retour_avec_le_simulateur():
    assert brut_pour_net(calcul_salaire(10000)["net"]) == 10000
    assert brut_pour_net(calcul_salaire(12000, 2)["net"], 2) == 12000


def test_net_juste_sous_le_seuil():
    # Le net de 6 936 DH brut s'obtient sous le seuil, pas dans la zone piège.
    assert brut_pour_net(6409.94) == 6936


def test_net_juste_au_dessus_du_seuil_saute_la_zone_piege():
    # 6 409,95 DH : impossible sous le seuil. Les bruts 6 937 à 7 007 donnent moins
    # que 6 409,94 DH : le premier brut qui convient est 7 008, après la zone.
    brut = brut_pour_net(6409.95)
    assert brut == 7008
    assert alerte_seuil(brut) is None


def test_aucun_brut_propose_dans_la_zone_piege():
    zone = zone_piege(0)
    for centimes in range(630000, 645000, 25):  # nets de 6 300 à 6 450 DH
        brut = brut_pour_net(centimes / 100)
        assert not zone["premier_apres"] <= brut < zone["rattrapage"]


def test_net_inaccessible():
    assert brut_pour_net(10_000_000) is None


def test_api_brut_pour_net(client):
    data = client.get("/api/brut-pour-net?net=8000&personnes=0").get_json()
    assert data["negociation"]["brut"] == 8914
    assert data["resultat"] == calcul_salaire(8914, 0)
    assert calcul_salaire(8913)["net"] < 8000 <= data["resultat"]["net"]
    assert texte(data["negociation"]["message"]) == (
        "Pour toucher au moins 8 000,00 DH net par mois, demandez un brut de 8 914 DH."
    )


def test_api_brut_pour_net_pres_du_seuil_previent_de_la_zone(client):
    data = client.get("/api/brut-pour-net?net=6410").get_json()
    assert data["negociation"]["brut"] == 7008
    assert "N'acceptez pas moins : de 6 937 DH à 7 007 DH brut" in texte(data["negociation"]["message"])
    assert data["alerte"] is None


def test_api_brut_pour_net_accepte_la_virgule(client):
    data = client.get("/api/brut-pour-net?net=6 409,94").get_json()
    assert data["negociation"]["brut"] == 6936


@pytest.mark.parametrize("requete", [
    "/api/brut-pour-net",
    "/api/brut-pour-net?net=abc",
    "/api/brut-pour-net?net=-100",
    "/api/brut-pour-net?net=8000&personnes=-1",
    "/api/brut-pour-net?net=99999999",
])
def test_api_brut_pour_net_saisie_invalide(client, requete):
    reponse = client.get(requete)
    assert reponse.status_code == 400
    assert "erreur" in reponse.get_json()
