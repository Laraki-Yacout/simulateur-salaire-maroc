"""Application Flask : simulateur de salaire net marocain."""

from flask import Flask, jsonify, render_template, request

import config
from calcul import calcul_salaire

app = Flask(__name__)

MESSAGE_ERREUR = (
    "Veuillez saisir un salaire brut positif et un nombre de personnes à charge valide."
)


@app.template_filter("dh")
def format_dh(montant):
    """Formate un montant à la française : 12 345,67 DH."""
    texte = f"{montant:,.2f}".replace(",", " ").replace(".", ",")
    return f"{texte} DH"


@app.template_filter("pct")
def format_pct(taux):
    """Formate un taux : 0.0448 -> 4,48 %."""
    texte = f"{taux * 100:.2f}".rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')} %"


def lire_entrees(brut_texte, personnes_texte):
    """Convertit les saisies en nombres ; lève ValueError si elles sont invalides."""
    brut = float(brut_texte.replace(" ", "").replace(" ", "").replace(",", "."))
    personnes = int(personnes_texte or 0)
    if not 0 < brut <= 10_000_000 or not 0 <= personnes <= 20:
        raise ValueError
    return brut, personnes


def simuler(brut, personnes):
    """Résultat principal + scénarios d'augmentation, tous issus de calcul.py."""
    resultat = calcul_salaire(brut, personnes)
    augmentations = []
    for pourcentage in config.AUGMENTATIONS:
        r = calcul_salaire(brut * (1 + pourcentage / 100), personnes)
        gain_brut = r["brut"] - resultat["brut"]
        gain_net = r["net"] - resultat["net"]
        augmentations.append({
            "pourcentage": pourcentage,
            "brut": r["brut"],
            "net": r["net"],
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
        erreur = MESSAGE_ERREUR

    return render_template(
        "index.html",
        resultat=simulation["resultat"] if simulation else None,
        augmentations=simulation["augmentations"] if simulation else [],
        erreur=erreur,
        brut=brut,
        personnes=personnes,
        config=config,
    )


@app.get("/api/calcul")
def api_calcul():
    try:
        brut, personnes = lire_entrees(
            request.args.get("brut", ""), request.args.get("personnes", "0")
        )
    except ValueError:
        return jsonify(erreur=MESSAGE_ERREUR), 400
    return jsonify(simuler(brut, personnes))


if __name__ == "__main__":
    app.run(debug=True)
