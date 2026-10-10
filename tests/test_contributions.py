"""Tests de l'enregistrement des contributions et de la page /statistiques."""

from datetime import date

from app import app
from calcul import calcul_salaire
from models import Contribution, db

FORMULAIRE = {
    "brut": "12000",
    "personnes": "2",
    "ville": "Rabat",
    "secteur": "Informatique/Télécom",
    "experience": "3-5 ans",
    "diplome": "Bac+5",
    "consentement": "oui",
}


def contributions():
    with app.app_context():
        return db.session.scalars(db.select(Contribution)).all()


def ajouter(brut, ville=None, secteur=None, est_demo=False):
    with app.app_context():
        db.session.add(Contribution(
            salaire_brut=brut, salaire_net=calcul_salaire(brut)["net"], personnes_charge=0,
            ville=ville, secteur=secteur, est_demo=est_demo,
        ))
        db.session.commit()


def test_enregistrement(client):
    reponse = client.post("/api/contributions", data=FORMULAIRE)
    assert reponse.status_code == 201

    [c] = contributions()
    assert c.salaire_brut == 12000
    assert c.salaire_net == calcul_salaire(12000, 2)["net"]  # recalculé côté serveur
    assert c.personnes_charge == 2
    assert (c.ville, c.secteur, c.experience, c.diplome) == ("Rabat", "Informatique/Télécom", "3-5 ans", "Bac+5")
    assert c.est_demo is False
    assert c.date_ajout == date.today()
    assert "contribution_recente" in reponse.headers["Set-Cookie"]


def test_listes_facultatives(client):
    reponse = client.post("/api/contributions", data={"brut": "8000", "consentement": "oui"})
    assert reponse.status_code == 201
    [c] = contributions()
    assert c.ville is None and c.secteur is None and c.experience is None and c.diplome is None


def test_refus_sans_consentement(client):
    sans = {k: v for k, v in FORMULAIRE.items() if k != "consentement"}
    reponse = client.post("/api/contributions", data=sans)
    assert reponse.status_code == 400
    assert "consentement" in reponse.get_json()["erreur"]
    assert contributions() == []


def test_refus_hors_limites(client):
    for brut in ("2499", "200001", "-5", "abc"):
        reponse = client.post("/api/contributions", data={**FORMULAIRE, "brut": brut})
        assert reponse.status_code == 400, brut
    assert contributions() == []


def test_limites_acceptees(client):
    assert client.post("/api/contributions", data={**FORMULAIRE, "brut": "2500"}).status_code == 201
    client.delete_cookie("contribution_recente")
    assert client.post("/api/contributions", data={**FORMULAIRE, "brut": "200000"}).status_code == 201
    assert len(contributions()) == 2


def test_refus_valeur_inconnue(client):
    reponse = client.post("/api/contributions", data={**FORMULAIRE, "ville": "Paris"})
    assert reponse.status_code == 400
    assert contributions() == []


def test_une_contribution_par_24h(client):
    assert client.post("/api/contributions", data=FORMULAIRE).status_code == 201
    assert client.post("/api/contributions", data=FORMULAIRE).status_code == 429
    assert len(contributions()) == 1
    assert "déjà partagé" in client.get("/").get_data(as_text=True)


def test_calcul_en_temps_reel_n_enregistre_rien(client):
    client.get("/api/calcul?brut=12000&personnes=2")
    client.post("/", data={"brut": "12000", "personnes": "2"})
    assert contributions() == []


def test_page_statistiques_vide(client):
    reponse = client.get("/statistiques")
    assert reponse.status_code == 200
    assert "Aucune contribution" in reponse.get_data(as_text=True)


def test_page_statistiques_groupes_et_demo(client):
    for brut in (6000, 7000, 8000, 9000, 10000):
        ajouter(brut, ville="Casablanca", est_demo=True)
    for brut in (5000, 5500):
        ajouter(brut, ville="Fès")  # groupe trop petit : masqué

    page = client.get("/statistiques").get_data(as_text=True)
    assert "7 000 DH" in page  # médiane des 7 salaires
    assert "Casablanca" in page
    assert "Fès" not in page
    assert "1 ville masquée" in page
    assert "Données de démonstration." in page

    sans_demo = client.get("/statistiques?demo=0").get_data(as_text=True)
    assert "Données de démonstration." not in sans_demo
    assert "5 250 DH" in sans_demo  # médiane de 5 000 et 5 500
