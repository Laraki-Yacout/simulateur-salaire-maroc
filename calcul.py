"""Calcul du salaire net mensuel marocain à partir du brut mensuel."""

import math

import config


def calcul_ir_annuel(net_imposable_annuel):
    """Applique le barème progressif de l'IR (méthode de la somme à déduire)."""
    for borne, taux, somme_a_deduire in config.BAREME_IR:
        if net_imposable_annuel <= borne:
            return max(net_imposable_annuel * taux - somme_a_deduire, 0.0)
    return 0.0


def calcul_salaire(brut_mensuel, personnes_a_charge=0):
    """Retourne le détail du calcul, montants mensuels arrondis à 2 décimales."""
    if brut_mensuel < 0:
        raise ValueError("Le salaire brut doit être positif.")
    if personnes_a_charge < 0:
        raise ValueError("Le nombre de personnes à charge doit être positif.")

    assiette_cnss = min(brut_mensuel, config.CNSS_PLAFOND_MENSUEL)
    cnss = assiette_cnss * config.CNSS_TAUX
    ipe = assiette_cnss * config.IPE_TAUX
    amo = brut_mensuel * config.AMO_TAUX
    total_cotisations = cnss + ipe + amo

    brut_imposable = brut_mensuel - total_cotisations
    brut_imposable_annuel = brut_imposable * 12

    # Le seuil de 78 000 DH et le plafond s'appliquent au brut imposable annuel,
    # pas au brut : le taux de 35 % vaut donc jusqu'à environ 6 937 DH brut par mois.
    if brut_imposable_annuel <= config.FRAIS_PRO_SEUIL_ANNUEL:
        taux_frais_pro = config.FRAIS_PRO_TAUX_BAS
    else:
        taux_frais_pro = config.FRAIS_PRO_TAUX_HAUT
    frais_pro_annuel = min(
        brut_imposable_annuel * taux_frais_pro, config.FRAIS_PRO_PLAFOND_ANNUEL
    )

    net_imposable_annuel = max(brut_imposable_annuel - frais_pro_annuel, 0.0)
    ir_brut_annuel = calcul_ir_annuel(net_imposable_annuel)

    # La réduction pour charges de famille ne peut pas rendre l'IR négatif.
    personnes_retenues = min(personnes_a_charge, config.CHARGES_FAMILLE_MAX)
    reduction_famille_annuelle = min(
        personnes_retenues * config.CHARGE_FAMILLE_ANNUELLE, ir_brut_annuel
    )
    ir_annuel = ir_brut_annuel - reduction_famille_annuelle
    ir_mensuel = ir_annuel / 12

    net_mensuel = brut_mensuel - total_cotisations - ir_mensuel

    return {
        "brut": round(brut_mensuel, 2),
        "assiette_cnss": round(assiette_cnss, 2),
        "cnss": round(cnss, 2),
        "ipe": round(ipe, 2),
        "amo": round(amo, 2),
        "total_cotisations": round(total_cotisations, 2),
        "brut_imposable": round(brut_imposable, 2),
        "taux_frais_pro": taux_frais_pro,
        "frais_pro": round(frais_pro_annuel / 12, 2),
        "net_imposable": round(net_imposable_annuel / 12, 2),
        "ir_brut": round(ir_brut_annuel / 12, 2),
        "personnes_retenues": personnes_retenues,
        "reduction_famille": round(reduction_famille_annuelle / 12, 2),
        "ir": round(ir_mensuel, 2),
        "net": round(net_mensuel, 2),
        "net_annuel": round(net_mensuel * 12, 2),
        "taux_prelevement": round((brut_mensuel - net_mensuel) / brut_mensuel * 100, 1)
        if brut_mensuel
        else 0.0,
    }


def brut_pour_brut_imposable(brut_imposable_mensuel):
    """Brut mensuel qui donne exactement ce brut imposable (inverse du calcul des cotisations)."""
    taux_plafonnes = config.CNSS_TAUX + config.IPE_TAUX
    brut = brut_imposable_mensuel / (1 - taux_plafonnes - config.AMO_TAUX)
    if brut <= config.CNSS_PLAFOND_MENSUEL:
        return brut
    # Au-delà du plafond, CNSS et IPE sont fixes : seule l'AMO suit le brut.
    return (
        (brut_imposable_mensuel + config.CNSS_PLAFOND_MENSUEL * taux_plafonnes)
        / (1 - config.AMO_TAUX)
    )


def seuil_frais_pro():
    """Brut mensuel exact où le brut imposable annuel atteint le seuil des frais pro."""
    return brut_pour_brut_imposable(config.FRAIS_PRO_SEUIL_ANNUEL / 12)


def zone_piege(personnes_a_charge=0):
    """Bornes de la « zone piège », où le net est plus bas que juste avant le seuil.

    En franchissant le seuil, l'abattement passe de 35 % à 25 % de tout le brut imposable :
    le net baisse d'un coup. Retourne None si ce n'est pas le cas (avec beaucoup de
    personnes à charge, la réduction d'impôt peut absorber la hausse).
    """
    seuil = seuil_frais_pro()
    dernier_avant = math.floor(seuil)  # plus grand brut entier encore à 35 %
    premier_apres = dernier_avant + 1
    net_avant = calcul_salaire(dernier_avant, personnes_a_charge)["net"]
    if calcul_salaire(premier_apres, personnes_a_charge)["net"] >= net_avant:
        return None

    # Brut de rattrapage : le plus petit brut entier dont le net retrouve net_avant.
    # Le net est croissant au-dessus du seuil : recherche dichotomique.
    bas, haut = premier_apres, premier_apres + 1
    while calcul_salaire(haut, personnes_a_charge)["net"] < net_avant:
        haut *= 2
    while bas < haut:
        milieu = (bas + haut) // 2
        if calcul_salaire(milieu, personnes_a_charge)["net"] >= net_avant:
            haut = milieu
        else:
            bas = milieu + 1

    return {
        "seuil": round(seuil, 2),
        "dernier_avant": dernier_avant,
        "premier_apres": premier_apres,
        "rattrapage": bas,
        "net_avant": net_avant,
    }


def alerte_seuil(brut_mensuel, personnes_a_charge=0):
    """Situation du brut par rapport à la zone piège, ou None s'il n'y a rien à signaler.

    - « zone » : le brut est dans la zone piège ;
    - « approche » : le brut est au plus config.ZONE_PIEGE_APPROCHE DH sous le seuil.
    """
    zone = zone_piege(personnes_a_charge)
    if zone is None:
        return None
    net = calcul_salaire(brut_mensuel, personnes_a_charge)["net"]

    if brut_mensuel > zone["dernier_avant"] and net < zone["net_avant"]:
        return dict(zone, type="zone", net=net, manque=round(zone["net_avant"] - net, 2))

    if zone["seuil"] - config.ZONE_PIEGE_APPROCHE <= brut_mensuel <= zone["seuil"]:
        net_apres = calcul_salaire(zone["premier_apres"], personnes_a_charge)["net"]
        return dict(
            zone,
            type="approche",
            net=net,
            hausse_piege=round(zone["premier_apres"] - brut_mensuel, 2),
            variation_net=round(net_apres - net, 2),
            hausse_minimale=round(zone["rattrapage"] - brut_mensuel, 2),
        )
    return None


def brut_pour_net(net_vise, personnes_a_charge=0, brut_max=10_000_000):
    """Plus petit brut entier dont le net atteint net_vise ; None si c'est impossible.

    Le net n'est pas croissant partout : il baisse au seuil des frais professionnels.
    On cherche donc d'abord sous le seuil, puis au-dessus. Au-dessus, le premier brut
    qui atteint net_vise (plus grand que le net d'avant le seuil) est forcément après
    la zone piège : aucun brut de la zone n'est jamais proposé.
    """
    net_vise = round(net_vise, 2)

    def premier_brut_atteignant(bas, haut):
        if bas > haut or calcul_salaire(haut, personnes_a_charge)["net"] < net_vise:
            return None
        while bas < haut:
            milieu = (bas + haut) // 2
            if calcul_salaire(milieu, personnes_a_charge)["net"] >= net_vise:
                haut = milieu
            else:
                bas = milieu + 1
        return bas

    dernier_avant = math.floor(seuil_frais_pro())
    brut = premier_brut_atteignant(1, dernier_avant)
    if brut is None:
        brut = premier_brut_atteignant(dernier_avant + 1, brut_max)
    return brut
