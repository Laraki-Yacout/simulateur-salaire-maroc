"""Application Flask : simulateur de salaire net marocain."""

import os
import re

from flask import Flask, jsonify, render_template, request, url_for
from sqlalchemy.pool import NullPool

import config
import statistiques
from calcul import alerte_seuil, brut_pour_net, calcul_salaire
from models import Contribution, db

# Sur Vercel, les fichiers statiques doivent être dans public/ : le CDN les sert
# directement à l'adresse /static/…, et Flask fait de même en local.
app = Flask(__name__, static_folder="public/static", static_url_path="/static")

MESSAGE_SAISIE_INVALIDE = (
    "Veuillez saisir un salaire brut positif et un nombre de personnes à charge valide."
)
MESSAGE_NET_INVALIDE = (
    "Veuillez saisir un salaire net positif et un nombre de personnes à charge valide."
)
BRUT_MAX_SAISIE = 10_000_000
PERSONNES_MAX_SAISIE = 20
COOKIE_CONTRIBUTION = "contribution_recente"

# Vercel définit la variable VERCEL pendant la construction et l'exécution.
EN_PRODUCTION = "VERCEL" in os.environ
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
    if EN_PRODUCTION:
        # Le disque de Vercel est en lecture seule et effacé à chaque instance :
        # une base SQLite y serait impossible à créer, ou perdue.
        raise RuntimeError("La variable d'environnement DATABASE_URL doit être définie sur Vercel.")
    os.makedirs(app.instance_path, exist_ok=True)
    return "sqlite:///" + os.path.join(app.instance_path, "simulateur.db")


def options_moteur(url):
    if url.startswith("postgresql+psycopg://"):
        # Fonctions serverless + « Transaction pooler » de Supabase (port 6543) :
        # c'est le pooler qui partage les connexions, l'application n'en garde aucune
        # ouverte (NullPool). Ce pooler ne supporte pas les requêtes préparées que
        # psycopg crée automatiquement : on les désactive.
        return {"poolclass": NullPool, "connect_args": {"prepare_threshold": None}}
    return {"pool_pre_ping": True}


def cle_secrete():
    cle = os.environ.get("SECRET_KEY")
    if cle:
        return cle
    if EN_PRODUCTION:
        raise RuntimeError("La variable d'environnement SECRET_KEY doit être définie sur Vercel.")
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


def lire_montant(texte):
    """Accepte « 12 000,50 », y compris avec l'espace fine insécable des nombres français."""
    return float(texte.replace(" ", "").replace("\u202f", "").replace(",", "."))


def lire_entrees(brut_texte, personnes_texte):
    """Convertit les saisies en nombres ; lève ValueError si elles sont invalides."""
    brut = lire_montant(brut_texte)
    personnes = int(personnes_texte or 0)
    if not 0 < brut <= BRUT_MAX_SAISIE or not 0 <= personnes <= PERSONNES_MAX_SAISIE:
        raise ValueError
    return brut, personnes


def sans_coupure(texte):
    """Espaces insécables dans les montants (« 7 008 DH », « 5 % ») : jamais coupés."""
    return re.sub(r"(?<=\d) (?=\d|DH|%)", "\u00a0", texte)


def montant_dh(montant):
    """Au dirham près quand le montant est rond, au centime sinon."""
    return format_dh_arrondi(montant) if float(montant).is_integer() else format_dh(montant)


def message_seuil(alerte):
    """Texte de l'alerte « zone piège » (voir calcul.alerte_seuil), ou None."""
    if alerte is None:
        return None
    if alerte["type"] == "zone":
        return sans_coupure(
            "Vous êtes dans la zone piège : vous toucheriez plus avec un brut de "
            f"{format_dh_arrondi(alerte['dernier_avant'])} ({format_dh(alerte['manque'])} net "
            f"de plus par mois). Il faut au moins {format_dh_arrondi(alerte['rattrapage'])} "
            "brut pour en sortir."
        )
    hausse = montant_dh(alerte["hausse_piege"])
    if alerte["variation_net"] < 0:
        debut = (
            f"Une augmentation de {hausse} vous ferait perdre "
            f"{format_dh(-alerte['variation_net'])} net par mois."
        )
    else:
        debut = (
            f"Une augmentation de {hausse} ne vous rapporterait que "
            f"{format_dh(alerte['variation_net'])} net par mois."
        )
    return sans_coupure(
        f"{debut} Négociez au moins {montant_dh(alerte['hausse_minimale'])} "
        f"(soit {format_dh_arrondi(alerte['rattrapage'])} brut)."
    )


def message_augmentation(pourcentage, brut_apres, personnes):
    """Alerte de l'encart « Et si j'étais augmenté ? » quand le scénario tombe dans la zone."""
    alerte = alerte_seuil(brut_apres, personnes)
    if alerte is None or alerte["type"] != "zone":
        return None
    return sans_coupure(
        f"Avec +{pourcentage} %, votre brut ({format_dh(brut_apres)}) tomberait dans la zone "
        f"piège : vous toucheriez plus avec {format_dh_arrondi(alerte['dernier_avant'])} brut. "
        f"Visez au moins {format_dh_arrondi(alerte['rattrapage'])}."
    )


def simuler(brut, personnes):
    """Résultat principal, alerte de seuil et scénarios d'augmentation, issus de calcul.py."""
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
            "alerte": message_augmentation(pourcentage, apres["brut"], personnes),
        })
    return {
        "resultat": resultat,
        "augmentations": augmentations,
        "alerte": message_seuil(alerte_seuil(brut, personnes)),
    }


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
        alerte=simulation["alerte"] if simulation else None,
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


@app.get("/api/brut-pour-net")
def api_brut_pour_net():
    """Mode négociation : le plus petit brut entier qui donne au moins le net voulu."""
    try:
        net_vise = lire_montant(request.args.get("net", ""))
        personnes = int(request.args.get("personnes", "0") or 0)
        if not 0 < net_vise or not 0 <= personnes <= PERSONNES_MAX_SAISIE:
            raise ValueError
    except ValueError:
        return jsonify(erreur=MESSAGE_NET_INVALIDE), 400

    brut = brut_pour_net(net_vise, personnes, brut_max=BRUT_MAX_SAISIE)
    if brut is None:
        return jsonify(erreur="Ce salaire net est trop élevé pour le simulateur."), 400

    reponse = simuler(brut, personnes)
    message = (
        f"Pour toucher au moins {format_dh(net_vise)} net par mois, "
        f"demandez un brut de {format_dh_arrondi(brut)}."
    )
    juste_avant = alerte_seuil(brut - 1, personnes) if brut > 1 else None
    if juste_avant and juste_avant["type"] == "zone":
        # Le brut proposé suit juste la zone piège : une contre-offre un peu plus basse
        # donnerait moins qu'avant le seuil. On le dit clairement.
        message += (
            f" N'acceptez pas moins : de {format_dh_arrondi(juste_avant['premier_apres'])} à "
            f"{format_dh_arrondi(juste_avant['rattrapage'] - 1)} brut, vous toucheriez moins "
            f"qu'avec {format_dh_arrondi(juste_avant['dernier_avant'])}."
        )
    reponse["negociation"] = {
        "net_vise": round(net_vise, 2), "brut": brut, "message": sans_coupure(message),
    }
    return jsonify(reponse)


def lire_choix_parametre(nom, choix_possibles):
    """Paramètre d'URL facultatif : vide -> None, valeur inconnue -> erreur."""
    valeur = request.args.get(nom, "").strip()
    if not valeur:
        return None
    if valeur not in choix_possibles:
        raise ValueError
    return valeur


@app.get("/api/position")
def api_position():
    """Part des contributeurs qui gagnent moins que ce brut. Rien n'est enregistré."""
    try:
        brut, _ = lire_entrees(request.args.get("brut", ""), "0")
        ville = lire_choix_parametre("ville", config.VILLES)
        secteur = lire_choix_parametre("secteur", config.SECTEURS)
    except ValueError:
        return jsonify(erreur="Paramètres invalides."), 400
    inclure_demo = request.args.get("demo", "1") != "0"

    requete = db.select(Contribution)
    if not inclure_demo:
        requete = requete.where(Contribution.est_demo.is_(False))
    contributions = db.session.scalars(requete).all()

    def comparer(groupe, nom=None):
        position = {"nom": nom} if nom else {}
        if len(groupe) < config.STATS_GROUPE_MIN:
            # Groupe trop petit : ni pourcentage ni effectif, comme sur la page statistiques.
            return dict(position, pourcentage=None)
        return dict(
            position,
            pourcentage=statistiques.position(brut, [c.salaire_brut for c in groupe]),
            nombre=len(groupe),
        )

    return jsonify(
        brut=round(brut, 2),
        ensemble=comparer(contributions),
        ville=comparer([c for c in contributions if c.ville == ville], ville) if ville else None,
        secteur=(
            comparer([c for c in contributions if c.secteur == secteur], secteur)
            if secteur else None
        ),
        nb_demo=sum(1 for c in contributions if c.est_demo),
    )


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


@app.get("/api/sante")
def api_sante():
    """Vérifie que la base répond. Appelée chaque jour par le cron de Vercel
    (vercel.json) : Supabase met en pause les projets gratuits inactifs."""
    try:
        db.session.scalar(db.select(db.func.count()).select_from(Contribution))
    except Exception:
        # Aucun détail renvoyé : le message d'erreur pourrait contenir l'adresse de la base.
        app.logger.exception("La base de données ne répond pas.")
        return jsonify(statut="erreur", base="indisponible"), 503
    return jsonify(statut="ok", base="ok")


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
