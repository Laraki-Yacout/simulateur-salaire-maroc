"""Tests de la route JSON /api/calcul."""

import pytest

from app import app
from calcul import calcul_salaire


@pytest.fixture
def client():
    return app.test_client()


def test_api_calcul_renvoie_le_resultat_de_calcul_py(client):
    reponse = client.get("/api/calcul?brut=12000&personnes=2")
    assert reponse.status_code == 200
    data = reponse.get_json()
    assert data["resultat"] == calcul_salaire(12000, 2)
    assert data["resultat"]["net"] == pytest.approx(10481.08, abs=0.01)


def test_api_calcul_scenarios_augmentation(client):
    data = client.get("/api/calcul?brut=12000").get_json()
    assert [a["pourcentage"] for a in data["augmentations"]] == [5, 10, 20]

    plus_10 = data["augmentations"][1]
    assert plus_10["brut"] == 13200
    assert plus_10["net"] == calcul_salaire(13200, 0)["net"]
    assert plus_10["gain_brut"] == 1200
    assert plus_10["gain_net"] == pytest.approx(plus_10["net"] - 10381.08, abs=0.01)
    assert 0 < plus_10["part_conservee"] < 100


def test_api_calcul_accepte_la_virgule(client):
    data = client.get("/api/calcul?brut=6500,00").get_json()
    assert data["resultat"]["net"] == pytest.approx(6026.44, abs=0.01)


@pytest.mark.parametrize("requete", [
    "/api/calcul",
    "/api/calcul?brut=abc",
    "/api/calcul?brut=-100",
    "/api/calcul?brut=5000&personnes=deux",
])
def test_api_calcul_refuse_les_saisies_invalides(client, requete):
    reponse = client.get(requete)
    assert reponse.status_code == 400
    assert "erreur" in reponse.get_json()
