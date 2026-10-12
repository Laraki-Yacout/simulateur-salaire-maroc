"""Ajoute des contributions fictives (est_demo = True) pour illustrer /statistiques.

Usage :
    python seed_demo.py              # remplace les données de démo par 300 nouvelles
    python seed_demo.py --nombre 500
    python seed_demo.py --supprimer  # retire seulement les données de démo

Les salaires suivent une loi log-normale (beaucoup de salaires modestes,
quelques très hauts), ajustée selon la ville, le secteur, l'expérience et le diplôme.

Avec quelques centaines de lignes, le hasard peut placer une petite ville en tête.
Le script essaie donc des graines successives et garde le premier tirage dont les
médianes respectent la hiérarchie attendue (voir `est_coherent`) : ces données servent
à illustrer le site, pas à mesurer le marché du travail.

Les contributions réelles (est_demo = False) ne sont jamais touchées.
"""

import argparse
import math
import random
import statistics
from collections import defaultdict, namedtuple
from datetime import date, timedelta

import config
from app import app
from calcul import calcul_salaire
from models import Contribution, db

BRUT_MEDIAN_BASE = 6500  # brut mensuel médian avant ajustements, en DH
DISPERSION = 0.25  # écart-type du logarithme du salaire, une fois les critères pris en compte
ESSAIS_MAX = 5000

VILLES = {  # (poids de tirage, coefficient de salaire)
    "Casablanca": (30, 1.26), "Rabat": (16, 1.22),
    "Tanger": (10, 1.07), "Marrakech": (9, 1.05),
    "Agadir": (6, 0.96), "Kénitra": (5, 0.95), "Tétouan": (5, 0.94), "Autre": (5, 0.93),
    "Meknès": (5, 0.83), "Fès": (6, 0.82), "Oujda": (5, 0.80),
}
SECTEURS = {
    "Informatique/Télécom": (13, 1.35), "Banque/Assurance": (11, 1.32),
    "Santé": (7, 1.08), "Administration publique": (9, 1.05), "Industrie": (11, 1.00),
    "Éducation": (8, 1.00), "Offshoring/Centres d'appels": (10, 0.98),
    "Autre": (6, 0.95), "Commerce/Distribution": (11, 0.92),
    "BTP": (8, 0.82), "Tourisme/Hôtellerie": (6, 0.80),
}
EXPERIENCES = {
    "Moins d'1 an": (14, 0.72), "1-3 ans": (26, 0.86), "3-5 ans": (22, 1.00),
    "5-10 ans": (22, 1.25), "Plus de 10 ans": (16, 1.55),
}
DIPLOMES = {
    "Bac ou moins": (22, 0.68), "Bac+2": (20, 0.85), "Bac+3": (22, 1.00),
    "Bac+5": (31, 1.30), "Doctorat": (5, 1.60),
}
PERSONNES = {0: 40, 1: 18, 2: 20, 3: 14, 4: 6, 5: 2}

# Hiérarchie attendue des médianes de ville, de la plus haute à la plus basse
VILLES_PALIERS = [
    {"Casablanca", "Rabat"},
    {"Tanger", "Marrakech"},
    {"Agadir", "Kénitra", "Tétouan", "Autre"},
    {"Oujda", "Fès", "Meknès"},
]
SECTEURS_HAUTS = {"Banque/Assurance", "Informatique/Télécom"}
SECTEURS_BAS = {"Tourisme/Hôtellerie", "BTP"}

# Les données de config.py doivent couvrir exactement les mêmes choix
assert set(VILLES) == set(config.VILLES) and set(SECTEURS) == set(config.SECTEURS)
assert set(EXPERIENCES) == set(config.EXPERIENCES) and set(DIPLOMES) == set(config.DIPLOMES)


# Poids cumulés précalculés : chaque graine essayée fait plus d'un millier de tirages.
def _cumuls(table):
    total, cumuls = 0, []
    for poids, _ in table.values():
        total += poids
        cumuls.append(total)
    return list(table), cumuls


CUMULS = {id(t): _cumuls(t) for t in (VILLES, SECTEURS, EXPERIENCES, DIPLOMES)}


def tirer(rng, table, prob_vide=0.06):
    """Tire une valeur pondérée ; parfois None, comme un champ facultatif laissé vide."""
    noms, cumuls = CUMULS[id(table)]
    valeur = rng.choices(noms, cum_weights=cumuls)[0]
    coefficient = table[valeur][1]
    if rng.random() < prob_vide:
        return None, coefficient
    return valeur, coefficient


# Tirage léger (sans base de données) : on n'en fait des Contribution que s'il est retenu
Tirage = namedtuple("Tirage", "ville secteur experience diplome salaire_brut personnes anciennete")


def tirage_fictif(rng):
    ville, k_ville = tirer(rng, VILLES)
    secteur, k_secteur = tirer(rng, SECTEURS)
    experience, k_exp = tirer(rng, EXPERIENCES)
    diplome, k_dip = tirer(rng, DIPLOMES)

    mediane = BRUT_MEDIAN_BASE * k_ville * k_secteur * k_exp * k_dip
    brut = rng.lognormvariate(math.log(mediane), DISPERSION)
    brut = min(max(brut, config.CONTRIBUTION_BRUT_MIN + 500), config.CONTRIBUTION_BRUT_MAX)
    brut = round(brut / 50) * 50  # les salaires déclarés sont souvent ronds

    personnes = rng.choices(list(PERSONNES), weights=list(PERSONNES.values()))[0]
    return Tirage(ville, secteur, experience, diplome, float(brut), personnes, rng.randint(0, 120))


def en_contribution(t):
    return Contribution(
        date_ajout=date.today() - timedelta(days=t.anciennete),
        salaire_brut=t.salaire_brut,
        salaire_net=calcul_salaire(t.salaire_brut, t.personnes)["net"],
        personnes_charge=t.personnes,
        ville=t.ville,
        secteur=t.secteur,
        experience=t.experience,
        diplome=t.diplome,
        est_demo=True,
    )


def medianes_et_effectifs(contributions, attribut):
    groupes = defaultdict(list)
    for c in contributions:
        if getattr(c, attribut):
            groupes[getattr(c, attribut)].append(c.salaire_brut)
    return {nom: (statistics.median(salaires), len(salaires)) for nom, salaires in groupes.items()}


def est_coherent(contributions):
    """Vrai si tous les groupes sont affichables et si les médianes suivent la hiérarchie."""
    par_critere = {
        critere: medianes_et_effectifs(contributions, critere)
        for critere in ("ville", "secteur", "experience", "diplome")
    }
    for groupes, attendus in zip(par_critere.values(), (VILLES, SECTEURS, EXPERIENCES, DIPLOMES)):
        if set(groupes) != set(attendus) or min(n for _, n in groupes.values()) < config.STATS_GROUPE_MIN:
            return False
    medianes = {
        critere: {nom: mediane for nom, (mediane, _) in groupes.items()}
        for critere, groupes in par_critere.items()
    }

    # Villes : chaque palier strictement au-dessus du suivant
    villes = medianes["ville"]
    for haut, bas in zip(VILLES_PALIERS, VILLES_PALIERS[1:]):
        if min(villes[v] for v in haut) <= max(villes[v] for v in bas):
            return False

    # Secteurs : banque et informatique en tête, tourisme et BTP en bas
    secteurs = medianes["secteur"]
    autres = set(SECTEURS) - SECTEURS_HAUTS - SECTEURS_BAS
    if min(secteurs[x] for x in SECTEURS_HAUTS) <= max(secteurs[x] for x in autres | SECTEURS_BAS):
        return False
    if max(secteurs[x] for x in SECTEURS_BAS) >= min(secteurs[x] for x in autres):
        return False

    # Expérience et diplôme : médianes strictement croissantes
    for critere, ordre in (("experience", EXPERIENCES), ("diplome", DIPLOMES)):
        valeurs = [medianes[critere][nom] for nom in ordre]
        if any(precedente >= suivante for precedente, suivante in zip(valeurs, valeurs[1:])):
            return False
    return True


def generer(nombre, graine_depart):
    """Premier tirage cohérent à partir de la graine de départ."""
    for graine in range(graine_depart, graine_depart + ESSAIS_MAX):
        rng = random.Random(graine)
        tirages = [tirage_fictif(rng) for _ in range(nombre)]
        if est_coherent(tirages):
            return [en_contribution(t) for t in tirages], graine
    raise SystemExit(
        f"Aucun tirage cohérent en {ESSAIS_MAX} essais : augmentez --nombre "
        "pour que chaque groupe ait assez de contributions."
    )


def remplacer_demo(contributions):
    """Supprime les anciennes données de démo (jamais les vraies) et ajoute les nouvelles."""
    supprimees = db.session.execute(
        db.delete(Contribution).where(Contribution.est_demo.is_(True))
    ).rowcount
    db.session.add_all(contributions)
    db.session.commit()
    return supprimees


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nombre", type=int, default=300, help="contributions à créer (300)")
    parser.add_argument("--graine", type=int, default=2026, help="graine de départ (2026)")
    parser.add_argument("--supprimer", action="store_true", help="supprimer la démo sans en recréer")
    args = parser.parse_args()

    contributions, graine = ([], None) if args.supprimer else generer(args.nombre, args.graine)

    with app.app_context():
        supprimees = remplacer_demo(contributions)

        total = db.session.scalar(db.select(db.func.count()).select_from(Contribution))
        reelles = db.session.scalar(
            db.select(db.func.count()).select_from(Contribution).where(Contribution.est_demo.is_(False))
        )
        print(f"Données de démo supprimées : {supprimees}")
        if not args.supprimer:
            print(f"Données de démo ajoutées   : {len(contributions)} (graine {graine})")
        print(f"Contributions réelles      : {reelles} (conservées)")
        print(f"Contributions en base      : {total}")
        print(f"Base utilisée              : {app.config['SQLALCHEMY_DATABASE_URI']}")


if __name__ == "__main__":
    main()
