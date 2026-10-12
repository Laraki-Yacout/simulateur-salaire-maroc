"""Statistiques descriptives sur les salaires partagés."""

import statistics
from collections import defaultdict

import config


def mediane(valeurs):
    """Valeur du milieu (moyenne des deux valeurs centrales si le nombre est pair)."""
    if not valeurs:
        return None
    return statistics.median(valeurs)


def quartiles(valeurs):
    """1er et 3e quartile (interpolation linéaire, comme un tableur)."""
    if not valeurs:
        return None, None
    if len(valeurs) == 1:
        return valeurs[0], valeurs[0]
    q1, _, q3 = statistics.quantiles(valeurs, n=4, method="inclusive")
    return q1, q3


def resume(valeurs):
    """Nombre, médiane, moyenne et quartiles ; None si la liste est vide."""
    if not valeurs:
        return None
    q1, q3 = quartiles(valeurs)
    return {
        "nombre": len(valeurs),
        "mediane": mediane(valeurs),
        "moyenne": statistics.fmean(valeurs),
        "q1": q1,
        "q3": q3,
    }


def histogramme(valeurs, pas=config.HISTOGRAMME_PAS, maximum=config.HISTOGRAMME_MAX):
    """Compte les salaires par tranche de `pas` DH ; la dernière tranche est ouverte."""
    if not valeurs:
        return []
    nb_tranches = maximum // pas
    comptes = [0] * (nb_tranches + 1)
    for v in valeurs:
        comptes[min(int(v // pas), nb_tranches)] += 1

    tranches = []
    for i, n in enumerate(comptes):
        debut = i * pas
        fin = None if i == nb_tranches else debut + pas
        tranches.append({"debut": debut, "fin": fin, "nombre": n})

    # Les tranches vides aux deux extrémités n'apportent rien au graphique.
    remplies = [i for i, t in enumerate(tranches) if t["nombre"]]
    return tranches[remplies[0]: remplies[-1] + 1]


def medianes_par_groupe(contributions, attribut, colonne, minimum=config.STATS_GROUPE_MIN):
    """Médiane par groupe (ville, secteur…), seulement pour les groupes assez grands.

    Retourne (groupes affichés triés par médiane décroissante, nombre de groupes masqués).
    """
    groupes = defaultdict(list)
    for c in contributions:
        cle = getattr(c, attribut)
        if cle:
            groupes[cle].append(getattr(c, colonne))

    affiches = [
        {"nom": nom, "nombre": len(salaires), "mediane": mediane(salaires)}
        for nom, salaires in groupes.items()
        if len(salaires) >= minimum
    ]
    affiches.sort(key=lambda g: g["mediane"], reverse=True)
    return affiches, len(groupes) - len(affiches)
