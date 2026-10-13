"""Tests du calcul de salaire net (valeurs vérifiées à la main)."""

import pytest

from app import app
from calcul import calcul_salaire


def test_4000_non_imposable():
    # Net imposable annuel 29 037,84 DH < 40 000 : pas d'IR
    r = calcul_salaire(4000)
    assert r["cnss"] == 179.20
    assert r["ipe"] == 7.60
    assert r["amo"] == 90.40
    assert r["total_cotisations"] == 277.20
    assert r["taux_frais_pro"] == 0.35
    assert r["brut_imposable"] == 3722.80
    assert r["frais_pro"] == 1302.98
    assert r["ir"] == 0
    assert r["net"] == 3722.80


def test_6500_cnss_plafonnee_frais_35():
    # CNSS et IPE calculées sur 6 000 DH seulement
    r = calcul_salaire(6500)
    assert r["assiette_cnss"] == 6000
    assert r["cnss"] == 268.80
    assert r["ipe"] == 11.40
    assert r["amo"] == 146.90


def test_6500_frais_pro_sur_brut_imposable():
    # Brut imposable 6 072,90 DH/mois = 72 874,80 DH/an <= 78 000 : frais pro à 35 %
    r = calcul_salaire(6500, 0)
    assert r["brut_imposable"] == 6072.90
    assert r["taux_frais_pro"] == 0.35
    assert r["frais_pro"] == pytest.approx(2125.52, abs=0.01)  # 25 506,18 DH/an
    assert r["net_imposable"] == pytest.approx(3947.39, abs=0.01)
    assert r["ir"] == pytest.approx(61.41, abs=0.01)
    assert r["net"] == pytest.approx(6011.49, abs=0.01)


def test_6600_frais_pro_sur_brut_imposable():
    # Brut annuel 79 200 > 78 000, mais brut imposable 74 047,68 DH/an : toujours 35 %
    r = calcul_salaire(6600, 0)
    assert r["total_cotisations"] == 429.36
    assert r["brut_imposable"] == 6170.64
    assert r["taux_frais_pro"] == 0.35
    assert r["ir"] == pytest.approx(67.76, abs=0.01)
    assert r["net"] == pytest.approx(6102.88, abs=0.01)


def test_seuil_frais_pro_vers_6937():
    # Brut imposable = 78 000 DH/an pour un brut d'environ 6 936,97 DH
    assert calcul_salaire(6936)["taux_frais_pro"] == 0.35
    assert calcul_salaire(6937)["taux_frais_pro"] == 0.25


def test_12000_frais_pro_25():
    # 25 % de 137 383,20 = 34 345,80 DH/an, sous le plafond ; tranche à 34 %
    r = calcul_salaire(12000)
    assert r["taux_frais_pro"] == 0.25
    assert r["brut_imposable"] == 11448.60
    assert r["frais_pro"] == pytest.approx(2862.15, abs=0.01)
    assert r["total_cotisations"] == 551.40
    assert r["ir"] == pytest.approx(1086.06, abs=0.01)
    assert r["net"] == pytest.approx(10362.54, abs=0.01)


def test_25000_frais_pro_plafonnes_tranche_37():
    # 25 % de 289 857,60 = 72 464 DH/an, plafonné à 35 000
    r = calcul_salaire(25000)
    assert r["amo"] == 565.00
    assert r["total_cotisations"] == 845.20
    assert r["frais_pro"] == pytest.approx(2916.67, abs=0.01)
    assert r["ir"] == pytest.approx(5574.78, abs=0.01)
    assert r["net"] == pytest.approx(18580.02, abs=0.01)


def test_charges_de_famille():
    # 2 personnes : 1 200 DH/an de moins d'IR, soit 100 DH/mois
    r = calcul_salaire(12000, 2)
    assert r["reduction_famille"] == 100.00
    assert r["net"] == pytest.approx(10462.54, abs=0.01)


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
    assert "10 362,54 DH" in reponse.get_data(as_text=True)
    erreur = client.post("/", data={"brut": "abc", "personnes": "0"})
    assert "Veuillez saisir" in erreur.get_data(as_text=True)


def test_sous_titre_reprend_le_brut_saisi():
    client = app.test_client()
    page = client.post("/", data={"brut": "7500", "personnes": "0"}).get_data(as_text=True)
    assert "vos <span data-lede-brut>7 500,00 DH</span>" in page
