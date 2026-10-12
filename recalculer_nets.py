"""Recalcule le salaire net de toutes les contributions avec le calcul.py actuel.

À lancer après une modification des règles de calcul (barème, frais professionnels…) :
    python recalculer_nets.py

Seule la colonne salaire_net change : le brut déclaré et les critères restent intacts.
"""

from app import app
from calcul import calcul_salaire
from models import Contribution, db


def recalculer():
    """Met à jour salaire_net ; retourne le nombre de lignes modifiées."""
    modifiees = 0
    for c in db.session.scalars(db.select(Contribution)):
        net = calcul_salaire(c.salaire_brut, c.personnes_charge)["net"]
        if net != c.salaire_net:
            c.salaire_net = net
            modifiees += 1
    db.session.commit()
    return modifiees


if __name__ == "__main__":
    with app.app_context():
        total = db.session.scalar(db.select(db.func.count()).select_from(Contribution))
        print(f"Salaires nets recalculés : {recalculer()} sur {total}")
