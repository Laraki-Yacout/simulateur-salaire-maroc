"""Ajoute des contributions fictives (est_demo = True) pour illustrer /statistiques.

Usage :
    python seed_demo.py              # remplace les données de démo par 300 nouvelles
    python seed_demo.py --nombre 500
    python seed_demo.py --supprimer  # retire seulement les données de démo

Les salaires suivent une loi log-normale (beaucoup de salaires modestes,
quelques très hauts), ajustée selon la ville, le secteur, l'expérience et le diplôme.
Les contributions réelles (est_demo = False) ne sont jamais touchées.
"""

import argparse
import math
import random
from datetime import date, timedelta

import config
from app import app
from calcul import calcul_salaire
from models import Contribution, db

BRUT_MEDIAN_BASE = 6500  # brut mensuel médian avant ajustements, en DH
DISPERSION = 0.38  # écart-type du logarithme du salaire

VILLES = {  # (poids de tirage, coefficient de salaire)
    "Casablanca": (34, 1.15), "Rabat": (16, 1.10), "Tanger": (10, 1.02),
    "Marrakech": (9, 0.95), "Fès": (7, 0.90), "Agadir": (5, 0.92),
    "Meknès": (4, 0.88), "Kénitra": (4, 0.92), "Oujda": (3, 0.86),
    "Tétouan": (3, 0.88), "Autre": (5, 0.85),
}
SECTEURS = {
    "Informatique/Télécom": (14, 1.30), "Banque/Assurance": (10, 1.25),
    "Industrie": (12, 1.00), "BTP": (8, 0.90), "Commerce/Distribution": (12, 0.85),
    "Offshoring/Centres d'appels": (11, 0.90), "Santé": (7, 1.05),
    "Éducation": (8, 0.95), "Administration publique": (9, 1.05),
    "Tourisme/Hôtellerie": (5, 0.80), "Autre": (4, 0.90),
}
EXPERIENCES = {
    "Moins d'1 an": (14, 0.70), "1-3 ans": (26, 0.85), "3-5 ans": (22, 1.00),
    "5-10 ans": (22, 1.30), "Plus de 10 ans": (16, 1.65),
}
DIPLOMES = {
    "Bac ou moins": (22, 0.65), "Bac+2": (20, 0.85), "Bac+3": (22, 1.00),
    "Bac+5": (32, 1.35), "Doctorat": (4, 1.55),
}
PERSONNES = {0: 40, 1: 18, 2: 20, 3: 14, 4: 6, 5: 2}

# Les données de config.py doivent couvrir exactement les mêmes choix
assert set(VILLES) == set(config.VILLES) and set(SECTEURS) == set(config.SECTEURS)
assert set(EXPERIENCES) == set(config.EXPERIENCES) and set(DIPLOMES) == set(config.DIPLOMES)


def tirer(rng, table, prob_vide=0.08):
    """Tire une valeur pondérée ; parfois None, comme un champ facultatif laissé vide."""
    valeur = rng.choices(list(table), weights=[p for p, _ in table.values()])[0]
    coefficient = table[valeur][1]
    if rng.random() < prob_vide:
        return None, coefficient
    return valeur, coefficient


def contribution_fictive(rng):
    ville, k_ville = tirer(rng, VILLES)
    secteur, k_secteur = tirer(rng, SECTEURS)
    experience, k_exp = tirer(rng, EXPERIENCES)
    diplome, k_dip = tirer(rng, DIPLOMES)

    mediane = BRUT_MEDIAN_BASE * k_ville * k_secteur * k_exp * k_dip
    brut = rng.lognormvariate(math.log(mediane), DISPERSION)
    brut = min(max(brut, config.CONTRIBUTION_BRUT_MIN + 500), config.CONTRIBUTION_BRUT_MAX)
    brut = round(brut / 50) * 50  # les salaires déclarés sont souvent ronds

    personnes = rng.choices(list(PERSONNES), weights=list(PERSONNES.values()))[0]
    return Contribution(
        date_ajout=date.today() - timedelta(days=rng.randint(0, 120)),
        salaire_brut=float(brut),
        salaire_net=calcul_salaire(brut, personnes)["net"],
        personnes_charge=personnes,
        ville=ville,
        secteur=secteur,
        experience=experience,
        diplome=diplome,
        est_demo=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nombre", type=int, default=300, help="contributions à créer (300)")
    parser.add_argument("--graine", type=int, default=2026, help="graine aléatoire (2026)")
    parser.add_argument("--supprimer", action="store_true", help="supprimer la démo sans en recréer")
    args = parser.parse_args()

    with app.app_context():
        supprimees = db.session.execute(
            db.delete(Contribution).where(Contribution.est_demo.is_(True))
        ).rowcount
        if not args.supprimer:
            rng = random.Random(args.graine)
            db.session.add_all(contribution_fictive(rng) for _ in range(args.nombre))
        db.session.commit()

        total = db.session.scalar(db.select(db.func.count()).select_from(Contribution))
        print(f"Données de démo supprimées : {supprimees}")
        if not args.supprimer:
            print(f"Données de démo ajoutées   : {args.nombre}")
        print(f"Contributions en base      : {total}")
        print(f"Base utilisée              : {app.config['SQLALCHEMY_DATABASE_URI']}")


if __name__ == "__main__":
    main()
