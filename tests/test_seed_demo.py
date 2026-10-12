"""Tests du script de données de démonstration."""

import pytest

from app import app
from models import Contribution, db
from seed_demo import est_coherent, generer, remplacer_demo


@pytest.fixture(scope="module")
def demo():
    return generer(300, 2026)[0]


def test_demo_coherente(demo):
    contributions = demo
    assert len(contributions) == 300
    assert all(c.est_demo for c in contributions)
    assert all(2500 <= c.salaire_brut <= 200000 for c in contributions)
    assert est_coherent(contributions)


def test_remplacement_ne_touche_pas_aux_vraies_donnees(demo):
    with app.app_context():
        db.session.add(Contribution(salaire_brut=9000, salaire_net=8100, est_demo=False))
        db.session.add(Contribution(salaire_brut=7000, salaire_net=6400, est_demo=True))
        db.session.commit()

        assert remplacer_demo(demo) == 1  # seule l'ancienne ligne de démo est supprimée

        reelles = db.session.scalars(
            db.select(Contribution).where(Contribution.est_demo.is_(False))
        ).all()
        assert [c.salaire_brut for c in reelles] == [9000]
        assert db.session.scalar(db.select(db.func.count()).select_from(Contribution)) == 301
