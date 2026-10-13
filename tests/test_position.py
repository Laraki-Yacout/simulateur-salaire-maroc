"""Tests de « Où je me situe » : statistiques.position et route /api/position."""

from app import app
from models import Contribution, db
import statistiques


def ajouter(*contributions):
    with app.app_context():
        for brut, ville, secteur, demo in contributions:
            db.session.add(Contribution(
                salaire_brut=brut, salaire_net=brut * 0.8, personnes_charge=0,
                ville=ville, secteur=secteur, est_demo=demo,
            ))
        db.session.commit()


def nombre_contributions():
    with app.app_context():
        return db.session.scalar(db.select(db.func.count()).select_from(Contribution))


def test_position_strictement_inferieurs():
    assert statistiques.position(5000, [3000, 4000, 5000, 6000]) == 50
    assert statistiques.position(2000, [3000, 4000]) == 0
    assert statistiques.position(9000, [3000, 4000]) == 100
    assert statistiques.position(5000, []) is None


def test_position_arrondie_a_l_unite_inferieure():
    assert statistiques.position(5000, [4000, 6000, 7000]) == 33


def test_api_position_ensemble_ville_et_secteur(client):
    ajouter(
        *[(4000 + 1000 * i, "Rabat", "BTP", False) for i in range(6)],  # 4 000 à 9 000
        *[(20000, "Fès", "Santé", False) for _ in range(4)],
    )
    data = client.get("/api/position?brut=6500&ville=Rabat&secteur=Santé").get_json()
    assert data["ensemble"] == {"pourcentage": 30, "nombre": 10}
    assert data["ville"] == {"nom": "Rabat", "pourcentage": 50, "nombre": 6}
    # 4 contributions seulement : ni pourcentage ni effectif.
    assert data["secteur"] == {"nom": "Santé", "pourcentage": None}
    assert data["nb_demo"] == 0


def test_api_position_sans_ville_ni_secteur(client):
    ajouter(*[(8000, None, None, False) for _ in range(5)])
    data = client.get("/api/position?brut=9000").get_json()
    assert data["ensemble"]["pourcentage"] == 100
    assert data["ville"] is None and data["secteur"] is None


def test_api_position_signale_les_donnees_de_demo(client):
    ajouter(*[(8000, None, None, True) for _ in range(5)], *[(8000, None, None, False) for _ in range(5)])
    assert client.get("/api/position?brut=9000").get_json()["nb_demo"] == 5
    sans_demo = client.get("/api/position?brut=9000&demo=0").get_json()
    assert sans_demo["nb_demo"] == 0
    assert sans_demo["ensemble"]["nombre"] == 5


def test_api_position_base_vide(client):
    data = client.get("/api/position?brut=9000").get_json()
    assert data["ensemble"] == {"pourcentage": None}


def test_api_position_n_enregistre_rien(client):
    ajouter(*[(8000, "Rabat", None, False) for _ in range(5)])
    reponse = client.get("/api/position?brut=9000&ville=Rabat")
    assert reponse.status_code == 200
    assert nombre_contributions() == 5
    assert "Set-Cookie" not in reponse.headers


def test_api_position_parametres_invalides(client):
    for requete in ("/api/position", "/api/position?brut=abc",
                    "/api/position?brut=9000&ville=Paris"):
        assert client.get(requete).status_code == 400
