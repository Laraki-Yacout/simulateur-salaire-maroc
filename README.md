# Simulateur de salaire net — Maroc 2026

Application Flask qui calcule le salaire net mensuel à partir du brut (CNSS, IPE, AMO,
frais professionnels, impôt sur le revenu, charges de famille), avec un calcul en temps réel,
et qui permet de partager anonymement son salaire pour alimenter une page de statistiques.

## Lancer le site

```powershell
py -3.14 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed_demo.py   # facultatif : 300 contributions fictives
python app.py         # puis ouvrir http://127.0.0.1:5000
```

Tests : `pytest`

## Organisation

| Fichier | Rôle |
|---|---|
| `config.py` | Paramètres légaux 2026 et réglages du site |
| `calcul.py` | Calcul brut → net |
| `app.py` | Routes Flask, API JSON `/api/calcul` et `/api/contributions`, page `/statistiques` |
| `models.py` | Table `contributions` (aucune donnée personnelle) |
| `statistiques.py` | Médiane, quartiles, histogramme, médianes par groupe |
| `seed_demo.py` | Génère des contributions fictives (`est_demo = True`) |
| `recalculer_nets.py` | Recalcule les salaires nets enregistrés après un changement de règle de calcul |
| `analyse/` | Notebook d'analyse des données |

La base est un fichier SQLite dans `instance/`, ou la base indiquée par la variable
d'environnement `DATABASE_URL`.

## Mise en ligne (Render + Supabase)

Service web Render :

- **Build command** : `pip install -r requirements.txt`
- **Start command** : `gunicorn app:app`
- Version de Python : fixée par `.python-version` (3.13)

Variables d'environnement à définir dans Render (jamais dans le code) :

| Variable | Valeur |
|---|---|
| `DATABASE_URL` | Chaîne de connexion Supabase (*Connect* → *Session pooler*, compatible IPv4) |
| `SECRET_KEY` | Une longue valeur aléatoire, par exemple `python -c "import secrets; print(secrets.token_hex(32))"` |

Les tables sont créées automatiquement au premier démarrage. Pour ajouter les données de
démonstration dans Supabase, depuis votre PC :

```powershell
$env:DATABASE_URL = "<chaîne de connexion Supabase>"
python seed_demo.py
Remove-Item Env:DATABASE_URL
```

## Analyse des données

Le notebook [`analyse/analyse_salaires.ipynb`](analyse/analyse_salaires.ipynb) explore les salaires
partagés sur le site pour répondre à deux questions : **quel est le salaire typique des
utilisateurs, et qu'est-ce qui le fait varier ?**

Il suit une démarche d'analyse complète :

1. contexte et question ;
2. chargement de la base SQLite (en lecture seule) et aperçu des données ;
3. qualité des données : valeurs manquantes, doublons, part des données de démonstration ;
4. nettoyage : détection des valeurs aberrantes par la méthode de l'écart interquartile (IQR) ;
5. statistiques descriptives, et pourquoi la moyenne dépasse la médiane ;
6. distribution : histogrammes (échelle normale et logarithmique) et boxplot ;
7. médiane par ville, secteur, expérience et diplôme (groupes d'au moins 5 contributions) ;
8. taux de prélèvement effectif de 3 000 à 50 000 DH, calculé avec `calcul.py`
   (progressivité de l'impôt, effet de seuil des frais professionnels) ;
9. conclusions et limites, notamment le biais de sélection de l'échantillon.

**Lancer le notebook** avec Anaconda (pandas, numpy, matplotlib et sqlite3 suffisent) :

```powershell
cd analyse
jupyter notebook analyse_salaires.ipynb
```

Le notebook doit être ouvert depuis le dossier `analyse/`, car il lit la base avec le chemin relatif
`../instance/simulateur.db`. Si la base ne contient que des données de démonstration, un avertissement
le signale : les conclusions sont alors **illustratives**.
