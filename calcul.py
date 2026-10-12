"""Calcul du salaire net mensuel marocain à partir du brut mensuel."""

import config


def calcul_ir_annuel(net_imposable_annuel):
    """Applique le barème progressif de l'IR (méthode de la somme à déduire)."""
    for borne, taux, deduction in config.BAREME_IR:
        if net_imposable_annuel <= borne:
            return max(net_imposable_annuel * taux - deduction, 0.0)
    return 0.0


def calcul_salaire(brut_mensuel, personnes_a_charge=0):
    """Retourne le détail du calcul, montants mensuels arrondis à 2 décimales."""
    if brut_mensuel < 0:
        raise ValueError("Le salaire brut doit être positif.")
    if personnes_a_charge < 0:
        raise ValueError("Le nombre de personnes à charge doit être positif.")

    # Cotisations sociales mensuelles
    assiette_cnss = min(brut_mensuel, config.CNSS_PLAFOND_MENSUEL)
    cnss = assiette_cnss * config.CNSS_TAUX
    ipe = assiette_cnss * config.IPE_TAUX
    amo = brut_mensuel * config.AMO_TAUX
    total_cotisations = cnss + ipe + amo

    # Brut imposable : salaire brut moins les cotisations salariales
    brut_imposable = brut_mensuel - total_cotisations
    brut_imposable_annuel = brut_imposable * 12

    # Frais professionnels (calculés sur l'année, sur le brut imposable)
    if brut_imposable_annuel <= config.FRAIS_PRO_SEUIL_ANNUEL:
        taux_frais_pro = config.FRAIS_PRO_TAUX_BAS
    else:
        taux_frais_pro = config.FRAIS_PRO_TAUX_HAUT
    frais_pro_annuel = min(
        brut_imposable_annuel * taux_frais_pro, config.FRAIS_PRO_PLAFOND_ANNUEL
    )

    # Revenu net imposable et IR
    net_imposable_annuel = max(brut_imposable_annuel - frais_pro_annuel, 0.0)
    ir_brut_annuel = calcul_ir_annuel(net_imposable_annuel)

    personnes_retenues = min(personnes_a_charge, config.CHARGES_FAMILLE_MAX)
    reduction_famille_annuelle = min(
        personnes_retenues * config.CHARGE_FAMILLE_ANNUELLE, ir_brut_annuel
    )
    ir_annuel = ir_brut_annuel - reduction_famille_annuelle
    ir = ir_annuel / 12

    net = brut_mensuel - total_cotisations - ir

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
        "ir": round(ir, 2),
        "net": round(net, 2),
        "net_annuel": round(net * 12, 2),
        "taux_prelevement": round((brut_mensuel - net) / brut_mensuel * 100, 1)
        if brut_mensuel
        else 0.0,
    }
