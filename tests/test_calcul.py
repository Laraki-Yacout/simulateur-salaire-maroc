"""Tests du calcul de salaire net (valeurs vérifiées à la main)."""

import pytest

from app import app
from calcul import calcul_salaire


def test_4000_non_imposable():
    # Net imposable annuel 27 873,60 DH < 40 000 : pas d'IR
    r = calcul_salaire(4000)
    assert r["cnss"] == 179.20
    assert r["ipe"] == 7.60
    assert r["amo"] == 90.40
    assert r["total_cotisations"] == 277.20
    assert r["taux_frais_pro"] == 0.35
    assert r["frais_pro"] == 1400.00
    assert r["ir"] == 0
    assert r["net"] == 3722.80


def test_6500_cnss_plafonnee_frais_35():
    # Brut annuel 78 000 = seuil : frais pro à 35 %, CNSS sur 6 000
    r = calcul_salaire(6500)
    assert r["assiette_cnss"] == 6000
    assert r["cnss"] == 268.80
    assert r["ipe"] == 11.40
    assert r["amo"] == 146.90
    assert r["taux_frais_pro"] == 0.35
    assert r["frais_pro"] == 2275.00
    assert r["net_imposable"] == pytest.approx(3797.90, abs=0.01)
    assert r["ir"] == pytest.approx(46.46, abs=0.01)
    assert r["net"] == pytest.approx(6026.44, abs=0.01)


def test_12000_frais_pro_plafonnes():
    # 25 % de 144 000 = 36 000, plafonné à 35 000 ; tranche à 34 %
    r = calcul_salaire(12000)
    assert r["taux_frais_pro"] == 0.25
    assert r["frais_pro"] == pytest.approx(2916.67, abs=0.01)
    assert r["total_cotisations"] == 551.40
    assert r["ir"] == pytest.approx(1067.52, abs=0.01)
    assert r["net"] == pytest.approx(10381.08, abs=0.01)


def test_25000_tranche_37():
    r = calcul_salaire(25000)
    assert r["amo"] == 565.00
    assert r["total_cotisations"] == 845.20
    assert r["ir"] == pytest.approx(5574.78, abs=0.01)
    assert r["net"] == pytest.approx(18580.02, abs=0.01)


def test_charges_de_famille():
    # 2 personnes : 1 200 DH/an de moins d'IR, soit 100 DH/mois
    r = calcul_salaire(12000, 2)
    assert r["reduction_famille"] == 100.00
    assert r["net"] == pytest.approx(10481.08, abs=0.01)


def test_charges_de_famille_plafonnees_a_6():
    assert calcul_salaire(25000, 9)["net"] == calcul_salaire(25000, 6)["net"]
    assert calcul_salaire(25000, 9)["personnes_retenues"] == 6


def test_reduction_famille_ne_rend_pas_ir_negatif():
    r = calcul_salaire(4000, 6)
    assert r["ir"] == 0
    assert r["net"] == 3722.80


def test_page_web():
    client = app.test_client()
    assert client.get("/").status_code == 200
    reponse = client.post("/", data={"brut": "12000", "personnes": "0"})
    assert "10 381,08 DH" in reponse.get_data(as_text=True)
    erreur = client.post("/", data={"brut": "abc", "personnes": "0"})
    assert "Veuillez saisir" in erreur.get_data(as_text=True)
