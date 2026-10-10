"""Paramètres légaux 2026 pour le calcul du salaire net au Maroc.

Tous les taux sont exprimés en fraction (0.0448 = 4,48 %).
Modifier ce fichier suffit pour mettre à jour le simulateur.
"""

ANNEE = 2026

# CNSS (part salariale) : prestations sociales + indemnité pour perte d'emploi
CNSS_TAUX = 0.0448
IPE_TAUX = 0.0019
CNSS_PLAFOND_MENSUEL = 6000.0

# AMO (part salariale), sans plafond
AMO_TAUX = 0.0226

# Frais professionnels
FRAIS_PRO_SEUIL_ANNUEL = 78000.0
FRAIS_PRO_TAUX_BAS = 0.35   # si brut annuel <= seuil
FRAIS_PRO_TAUX_HAUT = 0.25  # si brut annuel > seuil
FRAIS_PRO_PLAFOND_ANNUEL = 35000.0

# Barème IR annuel (art. 73 CGI) : (borne supérieure, taux, somme à déduire)
BAREME_IR = [
    (40000.0, 0.00, 0.0),
    (60000.0, 0.10, 4000.0),
    (80000.0, 0.20, 10000.0),
    (100000.0, 0.30, 18000.0),
    (180000.0, 0.34, 22000.0),
    (float("inf"), 0.37, 27400.0),
]

# Charges de famille (réduction d'IR)
CHARGE_FAMILLE_ANNUELLE = 600.0
CHARGES_FAMILLE_MAX = 6

# Interface du simulateur
BRUT_PAR_DEFAUT = 10000
CURSEUR_MIN = 3000
CURSEUR_MAX = 50000
CURSEUR_PAS = 100
AUGMENTATIONS = [5, 10, 20]  # scénarios « Et si j'étais augmenté ? », en %

# Contributions anonymes aux statistiques
CONTRIBUTION_BRUT_MIN = 2500
CONTRIBUTION_BRUT_MAX = 200000
CONTRIBUTION_DELAI_HEURES = 24  # une contribution par navigateur sur cette durée
STATS_GROUPE_MIN = 5  # taille minimale d'un groupe (ville, secteur) pour l'afficher
HISTOGRAMME_PAS = 2500  # largeur des barres de l'histogramme, en DH
HISTOGRAMME_MAX = 50000  # au-delà, tout est regroupé dans la dernière barre

VILLES = [
    "Casablanca", "Rabat", "Marrakech", "Fès", "Tanger", "Agadir",
    "Meknès", "Oujda", "Kénitra", "Tétouan", "Autre",
]
SECTEURS = [
    "Informatique/Télécom", "Banque/Assurance", "Industrie", "BTP",
    "Commerce/Distribution", "Offshoring/Centres d'appels", "Santé", "Éducation",
    "Administration publique", "Tourisme/Hôtellerie", "Autre",
]
EXPERIENCES = ["Moins d'1 an", "1-3 ans", "3-5 ans", "5-10 ans", "Plus de 10 ans"]
DIPLOMES = ["Bac ou moins", "Bac+2", "Bac+3", "Bac+5", "Doctorat"]
