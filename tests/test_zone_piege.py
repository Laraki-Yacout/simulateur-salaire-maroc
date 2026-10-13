"""Tests de l'alerte « zone piège » : seuil des frais professionnels (art. 59 CGI)."""

import pytest

import config
from calcul import alerte_seuil, calcul_salaire, seuil_frais_pro, zone_piege


def texte(message):
    """Message avec des espaces ordinaires (l'API met des espaces insécables)."""
    return message.replace("\u00a0", " ")


@pytest.fixture
def sans_ipe(monkeypatch):
    """Le simulateur de référence ne retient pas l'IPE : même hypothèse ici."""
    monkeypatch.setattr(config, "IPE_TAUX", 0.0)


def test_seuil_exact_avec_ipe():
    # Brut imposable = 6 500 DH/mois = 78 000 DH/an
    assert seuil_frais_pro() == pytest.approx(6936.98, abs=0.01)
    assert calcul_salaire(seuil_frais_pro())["taux_frais_pro"] == 0.35


def test_6936_6937_avec_ipe():
    avant, apres = calcul_salaire(6936), calcul_salaire(6937)
    assert (avant["taux_frais_pro"], apres["taux_frais_pro"]) == (0.35, 0.25)
    assert avant["net"] == pytest.approx(6409.94, abs=0.01)
    assert apres["net"] == pytest.approx(6345.86, abs=0.01)


def test_6925_6926_sans_ipe_comme_le_simulateur_de_reference(sans_ipe):
    assert seuil_frais_pro() == pytest.approx(6925.31, abs=0.01)
    avant, apres = calcul_salaire(6925), calcul_salaire(6926)
    assert (avant["taux_frais_pro"], apres["taux_frais_pro"]) == (0.35, 0.25)
    # Référence : 6 410,54 et 6 346,45 DH. Elle arrondit chaque ligne (AMO, IR) avant de
    # soustraire ; calcul.py n'arrondit que le net final, d'où au plus 1 centime d'écart.
    assert avant["net"] == pytest.approx(6410.54, abs=0.011)
    assert apres["net"] == pytest.approx(6346.45, abs=0.011)


def test_zone_piege_sans_ipe(sans_ipe):
    zone = zone_piege(0)
    assert (zone["dernier_avant"], zone["premier_apres"]) == (6925, 6926)
    assert calcul_salaire(zone["rattrapage"])["net"] >= zone["net_avant"]
    assert calcul_salaire(zone["rattrapage"] - 1)["net"] < zone["net_avant"]


def test_zone_piege_et_brut_de_rattrapage():
    zone = zone_piege(0)
    assert zone["dernier_avant"] == 6936
    assert zone["premier_apres"] == 6937
    assert zone["rattrapage"] == 7008
    assert zone["net_avant"] == pytest.approx(6409.94, abs=0.01)
    assert calcul_salaire(7007)["net"] < zone["net_avant"] <= calcul_salaire(7008)["net"]


def test_pas_de_zone_quand_la_reduction_famille_absorbe_la_hausse():
    # Avec 4 personnes à charge, l'IR reste nul de part et d'autre du seuil.
    assert zone_piege(4) is None
    assert alerte_seuil(6936, 4) is None
    assert alerte_seuil(6937, 4) is None


def test_alerte_approche_perte():
    alerte = alerte_seuil(6900)
    assert alerte["type"] == "approche"
    assert alerte["hausse_piege"] == 37  # 6 900 -> 6 937
    assert alerte["variation_net"] < 0
    assert alerte["hausse_minimale"] == 108  # 6 900 -> 7 008


def test_alerte_approche_limite_a_150_dh_sous_le_seuil():
    assert alerte_seuil(6787)["type"] == "approche"
    assert alerte_seuil(6786) is None
    assert alerte_seuil(5000) is None


def test_alerte_dans_la_zone():
    for brut in (6937, 6970, 7007):
        alerte = alerte_seuil(brut)
        assert alerte["type"] == "zone"
        assert alerte["manque"] > 0
    assert alerte_seuil(7008) is None
    assert alerte_seuil(12000) is None


def test_api_calcul_message_d_approche(client):
    data = client.get("/api/calcul?brut=6900").get_json()
    assert texte(data["alerte"]).startswith("Une augmentation de 37 DH vous ferait perdre 31,18 DH net")
    assert "Négociez au moins 108 DH (soit 7 008 DH brut)." in texte(data["alerte"])


def test_api_calcul_message_d_approche_sans_perte(client):
    data = client.get("/api/calcul?brut=6800").get_json()
    assert texte(data["alerte"]).startswith("Une augmentation de 137 DH ne vous rapporterait que")


def test_api_calcul_message_zone_piege(client):
    data = client.get("/api/calcul?brut=6937").get_json()
    assert texte(data["alerte"]).startswith(
        "Vous êtes dans la zone piège : vous toucheriez plus avec un brut de 6 936 DH"
    )


def test_api_calcul_pas_d_alerte_loin_du_seuil(client):
    data = client.get("/api/calcul?brut=12000").get_json()
    assert data["alerte"] is None
    assert all(a["alerte"] is None for a in data["augmentations"])


def test_augmentation_qui_tombe_dans_la_zone(client):
    # 6 400 DH + 10 % = 7 040 DH : hors zone ; + 5 % = 6 720 DH : sous le seuil.
    # 6 650 DH + 5 % = 6 982,50 DH : dans la zone.
    data = client.get("/api/calcul?brut=6650").get_json()
    plus_5 = data["augmentations"][0]
    assert texte(plus_5["alerte"]).startswith("Avec +5 %, votre brut (6 982,50 DH) tomberait dans la zone")


def test_page_affiche_l_alerte_et_l_explication(client):
    page = client.post("/", data={"brut": "6937", "personnes": "0"}).get_data(as_text=True)
    assert "Vous êtes dans la zone piège" in page
    assert "Pourquoi&nbsp;?" in page
    assert "article 59" in page
