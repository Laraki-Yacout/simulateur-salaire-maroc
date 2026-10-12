"""Application Flask : simulateur de salaire net marocain."""

import os

from flask import Flask, jsonify, render_template, request, url_for

import config
import statistiques
from calcul import calcul_salaire
from models import Contribution, db

app = Flask(__name__)

MESSAGE_SAISIE_INVALIDE = (
    "Veuillez saisir un salaire brut positif et un nombre de personnes à charge valide."
)
BRUT_MAX_SAISIE = 10_000_000
PERSONNES_MAX_SAISIE = 20
COOKIE_CONTRIBUTION = "contribution_recente"

# Render définit toujours la variable RENDER sur ses serveurs.
EN_PRODUCTION = "RENDER" in os.environ
CLE_SECRETE_LOCALE = "cle-de-developpement-local-uniquement"


def normaliser_url_base(url):
    """Force le pilote psycopg 3 : SQLAlchemy choisirait sinon psycopg2, non installé.

    Accepte aussi l'ancien préfixe « postgres:// » que donnent certains hébergeurs.
    """
    for prefixe in ("postgres://", "postgresql://"):
        if url.startswith(prefixe):
            return "postgresql+psycopg://" + url[len(prefixe):]
    return url


def adresse_base():
    """DATABASE_URL si elle existe (PostgreSQL Supabase en ligne), sinon SQLite dans instance/."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return normaliser_url_base(url)
    os.makedirs(app.instance_path, exist_ok=True)
    return "sqlite:///" + os.path.join(app.instance_path, "simulateur.db")


def options_moteur(url):
    # pool_pre_ping écarte les connexions coupées par Supabase pendant une période d'inactivité.
    options = {"pool_pre_ping": True}
    if url.startswith("postgresql+psycopg://"):
        # Le pooler de Supabase en mode « transaction » ne supporte pas les requêtes
        # préparées que psycopg crée automatiquement : on les désactive.
        options["connect_args"] = {"prepare_threshold": None}
    return options


def cle_secrete():
    cle = os.environ.get("SECRET_KEY")
    if cle:
        return cle
    if EN_PRODUCTION:
        raise RuntimeError("La variable d'environnement SECRET_KEY doit être définie sur Render.")
    return CLE_SECRETE_LOCALE


app.config["SECRET_KEY"] = cle_secrete()
app.config["SQLALCHEMY_DATABASE_URI"] = adresse_base()
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = options_moteur(app.config["SQLALCHEMY_DATABASE_URI"])
db.init_app(app)
with app.app_context():
    # Ne crée que les tables absentes : sans effet sur une base déjà en place.
    db.create_all()


@app.context_processor
def outils_gabarits():
    def asset(nom):
        """URL d'un fichier statique avec sa date de modification : le navigateur
        recharge automatiquement le fichier quand il change."""
        chemin = os.path.join(app.static_folder, nom)
        version = int(os.path.getmtime(chemin)) if os.path.exists(chemin) else 0
        return url_for("static", filename=nom, v=version)

    return {"asset": asset}


@app.template_filter("dh")
def format_dh(montant):
    """Formate un montant à la française : 12 345,67 DH."""
    texte = f"{montant:,.2f}".replace(",", " ").replace(".", ",")
    return f"{texte} DH"


@app.template_filter("dh0")
def format_dh_arrondi(montant):
    """Montant arrondi au dirham : 12 346 DH."""
    return f"{montant:,.0f} DH".replace(",", " ")


@app.template_filter("pct")
def format_pct(taux):
    """Formate un taux : 0.0448 -> 4,48 %."""
    texte = f"{taux * 100:.2f}".rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')} %"


def lire_entrees(brut_texte, personnes_texte):
    """Convertit les saisies en nombres ; lève ValueError si elles sont invalides."""
    # Accepte « 12 000,50 », y compris avec l'espace fine insécable des nombres français.
    brut = float(brut_texte.replace(" ", "").replace("\u202f", "").replace(",", "."))
    personnes = int(personnes_texte or 0)
    if not 0 < brut <= BRUT_MAX_SAISIE or not 0 <= personnes <= PERSONNES_MAX_SAISIE:
        raise ValueError
    return brut, personnes


def simuler(brut, personnes):
    """Résultat principal + scénarios d'augmentation, tous issus de calcul.py."""
    resultat = calcul_salaire(brut, personnes)
    augmentations = []
    for pourcentage in config.AUGMENTATIONS:
        apres = calcul_salaire(brut * (1 + pourcentage / 100), personnes)
        gain_brut = apres["brut"] - resultat["brut"]
        gain_net = apres["net"] - resultat["net"]
        augmentations.append({
            "pourcentage": pourcentage,
            "brut": apres["brut"],
            "net": apres["net"],
            "gain_brut": round(gain_brut, 2),
            "gain_net": round(gain_net, 2),
            "part_conservee": round(gain_net / gain_brut * 100, 1) if gain_brut else 0.0,
        })
    return {"resultat": resultat, "augmentations": augmentations}


@app.route("/", methods=["GET", "POST"])
def index():
    erreur = None
    simulation = None
    brut = str(config.BRUT_PAR_DEFAUT)
    personnes = "0"

    if request.method == "POST":
        brut = request.form.get("brut", "").strip()
        personnes = request.form.get("personnes", "0").strip() or "0"

    try:
        simulation = simuler(*lire_entrees(brut, personnes))
    except ValueError:
        erreur = MESSAGE_SAISIE_INVALIDE

    return render_template(
        "index.html",
        resultat=simulation["resultat"] if simulation else None,
        augmentations=simulation["augmentations"] if simulation else [],
        erreur=erreur,
        brut=brut,
        personnes=personnes,
        deja_contribue=COOKIE_CONTRIBUTION in request.cookies,
        config=config,
    )


@app.get("/api/calcul")
def api_calcul():
    try:
        brut, personnes = lire_entrees(
            request.args.get("brut", ""), request.args.get("personnes", "0")
        )
    except ValueError:
        return jsonify(erreur=MESSAGE_SAISIE_INVALIDE), 400
    return jsonify(simuler(brut, personnes))


def lire_choix(nom, choix_possibles):
    """Liste déroulante facultative : vide -> None, valeur inconnue -> erreur."""
    valeur = request.form.get(nom, "").strip()
    if not valeur:
        return None
    if valeur not in choix_possibles:
        raise ValueError("Une des listes déroulantes contient une valeur inconnue.")
    return valeur


@app.post("/api/contributions")
def api_contributions():
    """Enregistre un salaire, uniquement après un clic explicite et avec consentement."""
    if COOKIE_CONTRIBUTION in request.cookies:
        return jsonify(erreur=(
            "Vous avez déjà partagé un salaire depuis ce navigateur "
            f"au cours des dernières {config.CONTRIBUTION_DELAI_HEURES} heures."
        )), 429

    if request.form.get("consentement") not in ("oui", "on", "true", "1"):
        return jsonify(erreur=(
            "Cochez la case de consentement pour ajouter votre salaire aux statistiques."
        )), 400

    try:
        brut, personnes = lire_entrees(
            request.form.get("brut", ""), request.form.get("personnes", "0")
        )
    except ValueError:
        return jsonify(erreur=MESSAGE_SAISIE_INVALIDE), 400

    if not config.CONTRIBUTION_BRUT_MIN <= brut <= config.CONTRIBUTION_BRUT_MAX:
        return jsonify(erreur=(
            f"Seuls les salaires bruts entre {format_dh_arrondi(config.CONTRIBUTION_BRUT_MIN)} "
            f"et {format_dh_arrondi(config.CONTRIBUTION_BRUT_MAX)} par mois sont acceptés."
        )), 400

    try:
        contribution = Contribution(
            salaire_brut=round(brut, 2),
            salaire_net=calcul_salaire(brut, personnes)["net"],
            personnes_charge=personnes,
            ville=lire_choix("ville", config.VILLES),
            secteur=lire_choix("secteur", config.SECTEURS),
            experience=lire_choix("experience", config.EXPERIENCES),
            diplome=lire_choix("diplome", config.DIPLOMES),
            est_demo=False,
        )
    except ValueError as erreur:
        return jsonify(erreur=str(erreur)), 400

    db.session.add(contribution)
    db.session.commit()

    reponse = jsonify(message="Merci, votre salaire a été ajouté anonymement aux statistiques.")
    reponse.status_code = 201
    reponse.set_cookie(
        COOKIE_CONTRIBUTION, "1",
        max_age=config.CONTRIBUTION_DELAI_HEURES * 3600,
        httponly=True, samesite="Lax", secure=EN_PRODUCTION,
    )
    return reponse


def etiquette_k(montant):
    """7500 -> « 7,5 k »."""
    return f"{montant / 1000:g}".replace(".", ",") + " k"


@app.get("/statistiques")
def page_statistiques():
    inclure_demo = request.args.get("demo", "1") != "0"
    mesure = "net" if request.args.get("mesure") == "net" else "brut"
    colonne = "salaire_net" if mesure == "net" else "salaire_brut"

    requete = db.select(Contribution)
    if not inclure_demo:
        requete = requete.where(Contribution.est_demo.is_(False))
    contributions = db.session.scalars(requete).all()
    valeurs = [getattr(c, colonne) for c in contributions]

    resume = statistiques.resume(valeurs)
    tranches = statistiques.histogramme(valeurs)
    histogramme = {
        "etiquettes": [
            etiquette_k(t["debut"]) + (" +" if t["fin"] is None else "") for t in tranches
        ],
        "titres": [
            f"{format_dh_arrondi(t['debut'])} et plus" if t["fin"] is None
            else f"{format_dh_arrondi(t['debut'])} à {format_dh_arrondi(t['fin'])}"
            for t in tranches
        ],
        "valeurs": [t["nombre"] for t in tranches],
        "indexMediane": next(
            (i for i, t in enumerate(tranches)
             if resume and (t["fin"] is None or resume["mediane"] < t["fin"])),
            None,
        ),
    }
    villes, villes_masquees = statistiques.medianes_par_groupe(contributions, "ville", colonne)
    secteurs, secteurs_masques = statistiques.medianes_par_groupe(contributions, "secteur", colonne)

    nb_demo_total = db.session.scalar(
        db.select(db.func.count()).select_from(Contribution).where(Contribution.est_demo.is_(True))
    )

    return render_template(
        "statistiques.html",
        resume=resume,
        histogramme=histogramme,
        villes=villes,
        villes_masquees=villes_masquees,
        secteurs=secteurs,
        secteurs_masques=secteurs_masques,
        inclure_demo=inclure_demo,
        mesure=mesure,
        nb_demo_affiches=sum(1 for c in contributions if c.est_demo),
        nb_demo_total=nb_demo_total,
        config=config,
    )


if __name__ == "__main__":
    app.run(debug=not EN_PRODUCTION)
