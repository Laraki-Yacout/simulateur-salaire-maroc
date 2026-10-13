"""Tests de la route /api/sante et du cron Vercel qui l'appelle."""

import json
from pathlib import Path

from sqlalchemy.exc import OperationalError

from models import db


def test_sante_base_disponible(client):
    reponse = client.get("/api/sante")
    assert reponse.status_code == 200
    assert reponse.get_json() == {"statut": "ok", "base": "ok"}


def test_sante_base_indisponible(client, monkeypatch):
    def panne(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("postgresql://secret@hote/base"))

    monkeypatch.setattr(db.session, "scalar", panne)
    reponse = client.get("/api/sante")
    assert reponse.status_code == 503
    assert reponse.get_json() == {"statut": "erreur", "base": "indisponible"}
    assert "secret" not in reponse.get_data(as_text=True)


def test_cron_quotidien_compatible_offre_hobby():
    config_vercel = json.loads(Path(__file__).parent.parent.joinpath("vercel.json").read_text())
    crons = config_vercel["crons"]
    assert [c["path"] for c in crons] == ["/api/sante"]
    minute, heure, jour, mois, jour_semaine = crons[0]["schedule"].split()
    # Offre Hobby : au plus une exécution par jour, donc minute et heure fixes.
    assert minute.isdigit() and heure.isdigit()
    assert (jour, mois, jour_semaine) == ("*", "*", "*")
