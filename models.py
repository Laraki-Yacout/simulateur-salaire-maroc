"""Modèle de données : contributions anonymes aux statistiques de salaires."""

from datetime import date

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Contribution(db.Model):
    """Un salaire partagé anonymement : aucun nom, e-mail ni adresse IP."""

    __tablename__ = "contributions"

    id = db.Column(db.Integer, primary_key=True)
    date_ajout = db.Column(db.Date, nullable=False, default=date.today)
    salaire_brut = db.Column(db.Float, nullable=False)
    salaire_net = db.Column(db.Float, nullable=False)
    personnes_charge = db.Column(db.Integer, nullable=False, default=0)
    ville = db.Column(db.String(40))
    secteur = db.Column(db.String(60))
    experience = db.Column(db.String(30))
    diplome = db.Column(db.String(30))
    est_demo = db.Column(db.Boolean, nullable=False, default=False, index=True)
