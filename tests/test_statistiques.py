"""Tests des fonctions statistiques (médiane, quartiles, histogramme, groupes)."""

from types import SimpleNamespace

import pytest

import statistiques


def test_mediane_impair():
    assert statistiques.mediane([9000, 3000, 5000]) == 5000


def test_mediane_pair():
    assert statistiques.mediane([3000, 4000, 6000, 20000]) == 5000


def test_mediane_resiste_aux_tres_hauts_salaires():
    salaires = [4000, 5000, 6000, 7000, 150000]
    assert statistiques.mediane(salaires) == 6000
    assert statistiques.resume(salaires)["moyenne"] == 34400


def test_mediane_vide():
    assert statistiques.mediane([]) is None
    assert statistiques.resume([]) is None


def test_quartiles():
    q1, q3 = statistiques.quartiles([1000, 2000, 3000, 4000, 5000])
    assert (q1, q3) == (2000, 4000)
    assert statistiques.quartiles([7000]) == (7000, 7000)


def test_resume():
    r = statistiques.resume([2000, 4000, 6000, 8000])
    assert r["nombre"] == 4
    assert r["mediane"] == 5000
    assert r["moyenne"] == 5000
    assert r["q1"] == pytest.approx(3500)
    assert r["q3"] == pytest.approx(6500)


def test_histogramme():
    tranches = statistiques.histogramme([3000, 3100, 6000, 80000], pas=2500, maximum=10000)
    assert [(t["debut"], t["fin"], t["nombre"]) for t in tranches] == [
        (2500, 5000, 2),
        (5000, 7500, 1),
        (7500, 10000, 0),
        (10000, None, 1),  # dernière tranche ouverte
    ]


def test_medianes_par_groupe_seuil():
    lignes = [SimpleNamespace(ville="Rabat", salaire_brut=b) for b in (5000, 6000, 7000, 8000, 9000)]
    lignes += [SimpleNamespace(ville="Fès", salaire_brut=b) for b in (4000, 4500)]
    lignes += [SimpleNamespace(ville=None, salaire_brut=10000)]

    groupes, masques = statistiques.medianes_par_groupe(lignes, "ville", "salaire_brut", minimum=5)
    assert groupes == [{"nom": "Rabat", "nombre": 5, "mediane": 7000}]
    assert masques == 1
