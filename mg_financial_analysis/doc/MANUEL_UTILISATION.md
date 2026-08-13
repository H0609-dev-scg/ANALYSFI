# Manuel d’utilisation — Analyse Financière (PCG 2005)

Module Odoo 16 destiné aux **cabinets de conseil**. Il sert à saisir les états financiers d’un client, à produire le bilan financier, les soldes intermédiaires de gestion, les ratios, une lecture croisée, puis un rapport PDF ou un export Excel.

Ce manuel décrit le travail du consultant, pas le paramétrage technique du serveur.

---

## 1. Ce que le module produit

À partir d’un bilan et d’un compte de résultat saisis (ou importés), le module calcule et rédige :

| Livrable | Où le trouver |
|---|---|
| Contrôles d’équilibre (Actif = Passif, résultat CR = résultat bilan) | Bandeau de la période |
| Bilan financier retraité (FRNG, BFR, trésorerie nette) | Onglet *Bilan financier & SIG* |
| Soldes intermédiaires de gestion et CAF | Même onglet |
| Seuil de rentabilité, point mort, marge de sécurité | Agrégats + ratios D11 à D14 |
| 51 ratios en 6 familles, avec commentaire et recommandation | Onglet *Ratios & recommandations* |
| Lecture croisée (ordre de lecture, contradictions) | Onglet *Lecture des ratios* |
| Tableau des flux (méthodes indirecte et directe) | Onglet *Flux de trésorerie* |
| Variation des capitaux propres | Onglet *Variation des capitaux propres* |
| Scores Altman Z'', Conan-Holder, note de synthèse | Onglet *Risque de défaillance* |
| Projet de conclusion | Dossier, onglet *Conclusion générale* |
| Rapport PDF mono-période et comparatif multi-périodes | Imprimer / bouton du dossier |
| Classeur Excel | Action *Exporter en Excel* |

Référentiel : **Plan Comptable Général 2005 (Madagascar)**.

---

## 2. Droits d’accès

| Groupe Odoo | Usage |
|---|---|
| Lecture seule | Consulter et imprimer |
| Consultant | Créer des dossiers, saisir, analyser, exporter |
| Manager / Associé | Paramétrer rubriques, ratios, secteurs, calibrer, recharger le référentiel |

Un consultant n’a pas besoin d’ouvrir le menu *Configuration* pour traiter un dossier.

---

## 3. Parcours type d’une mission

```
Dossier  →  Période(s)  →  Saisie ou import  →  Contrôles
    →  Analyser  →  Lecture des ratios  →  Révision des textes
    →  Conclusion  →  PDF / Excel  →  Comparatif si plusieurs exercices
```

Durée réaliste une fois le tableur prêt : **saisie ou import en quelques minutes**, analyse automatique, puis **relecture humaine** (c’est là que se joue la qualité du livrable).

---

## 4. Créer le dossier

Menu **Analyse Financière > Dossiers > Créer**.

Renseignez au minimum :

1. **Client analysé**
2. **Secteur d’activité** — Commerce/Négoce, Industrie, Services, BTP, Agro-industrie, Transport/Logistique, Microfinance, Autre  
   Le secteur **change l’appréciation** des ratios. Un même taux de VA n’est pas lu de la même façon en négoce et en industrie.
3. **Nature de l’activité** (commerciale, production, mixte)
4. **Devise** (Ariary par défaut) et **unité de saisie** (unité, milliers, millions)

Utile ensuite :

- NIF, STAT, RCS (reproduits en page de garde)
- Consultant responsable et date de mission
- Onglet **Contexte de la mission** : objet, limites, documents reçus
- Onglet **Options du rapport** : ce qui sera imprimé (voir § 12)
- **Méthode du seuil de rentabilité** : laissez *Automatique* sauf consigne contraire

Enregistrez. La référence du dossier est attribuée automatiquement.

---

## 5. Ajouter une période

Depuis le dossier, onglet **Périodes** (ou menu *États financiers*).

| Champ | Conseil |
|---|---|
| Libellé | « Exercice 2025 », « S1 2026 » |
| Type | Annuel, semestriel, trimestriel, intermédiaire |
| Du / Au | La durée en mois est calculée toute seule |
| Période de référence (N-1) | Reliez l’exercice précédent dès qu’il existe |
| États audités | Décochez si les comptes n’ont pas été audités : une réserve figure alors au rapport |

Les **lignes de saisie** (environ 76 rubriques) sont créées à l’enregistrement.

Pour un nouvel exercice à structure identique : **Dupliquer la structure** (montants vidés, N-1 pointé sur la période d’origine).

---

## 6. Saisir les états financiers

### 6.1 Saisie à l’écran

Trois onglets principaux :

1. **Bilan - Actif** — brut, amortissements, net (si l’option *Colonnes Brut / Amortissements* est active sur le dossier)
2. **Bilan - Passif**
3. **Compte de résultat**

Règles de saisie :

- Les **charges se saisissent en positif**. Le module applique le signe dans les soldes.
- Le bandeau **Écart Actif − Passif** doit être **nul** (à la tolérance près, 1 Ar par défaut).
- Le **résultat du compte de résultat** doit égaler le **résultat inscrit au passif**.
- Les lignes en gras sont des totaux : ne les forcez pas.

Tant que le bilan n’est pas équilibré, **Valider** et **Analyser** sont refusés.

### 6.2 Import depuis un tableur (recommandé)

Bouton **Importer un tableur** (période en brouillon ou validée).

1. Téléchargez le **modèle CSV** ou partez de l’export Excel du module.
2. Première colonne = **code de rubrique** : `AC_STOCK`, `PA_CAPITAL`, `PL_VENTE_MSE`, `IN_EFFECTIF`…
3. Chargez le fichier (CSV ou `.xlsx`).
4. Vérifiez l’**aperçu** : reconnue / code inconnu / hors saisie.
5. Décochez les lignes à ignorer. L’option *Écraser les montants déjà saisis* est **désactivée par défaut**.
6. **Importer**, puis contrôler l’équilibre.

Le fichier produit par **Action > Exporter en Excel** (onglet *Saisie*) peut être réimporté tel quel.

### 6.3 Informations complémentaires

Onglet dédié. Ces montants **ne figurent pas au bilan** mais conditionnent les ratios (délais TTC, effectif, crédit-bail, dividendes, investissements, charges fixes/variables…).

- **Pré-remplir depuis les états financiers** : propose les valeurs déductibles (CA TTC à 20 %, stock moyen, variation d’emprunts…). Une valeur déjà saisie n’est **jamais** écrasée.
- **Contrôler la vraisemblance** : 15 rapprochements (TVA improbable, emprunt saisi deux fois, crédit-bail sans dette, amortissements > brut, etc.).

Ce sont des **alertes**, pas des blocages. Une incohérence rouge doit toutefois être corrigée avant diffusion du rapport : elle fausse les ratios concernés.

---

## 7. Lancer l’analyse

Bouton **Analyser** (ou *Relancer l’analyse*).

Le moteur :

1. valide l’équilibre si la période est encore en brouillon ;
2. calcule agrégats, ratios, commentaires ;
3. produit la **lecture croisée** ;
4. établit flux de trésorerie et variation des capitaux propres (dès qu’une période N-1 existe) ;
5. calcule les trois scores de risque.

**Relancer l’analyse ne détruit pas** vos commentaires, recommandations, priorités ni masquages. Vous pouvez corriger une saisie après rédaction.

---

## 8. Lire les résultats — dans cet ordre

### 8.1 Onglet *Lecture des ratios* (à ouvrir en premier)

Trois types de constats :

| Type | Rôle |
|---|---|
| **À lire en premier** | Les 8 indicateurs qui portent le diagnostic |
| **Lecture croisée** | Contradictions entre familles |
| **Synthèse de famille** | Une phrase pour la structure, la liquidité, l’activité, la rentabilité, la VA, la couverture |

Exemples de lectures croisées :

- bénéfice et trésorerie négative ;
- liquidité générale « bonne » portée par les stocks ;
- EBE positif et résultat net négatif (le trou est après l’exploitation) ;
- levier élevé sans dette bancaire (crédit fournisseur) ;
- activité sous le seuil de rentabilité ;
- ROE flatté par des fonds propres trop faibles.

C’est le diagnostic à poser **en réunion**, avant de dérouler les 51 fiches.

### 8.2 *Bilan financier & SIG*

Vérifiez surtout :

- FRNG, BFR, trésorerie nette (et le contrôle TN = TA − TP) ;
- cascade des SIG : CA → marge → VA → EBE → résultat net ;
- CAF des deux méthodes (l’écart doit être quasi nul) ;
- seuil de rentabilité, point mort, marge de sécurité.

### 8.3 *Ratios & recommandations*

Quatre niveaux : **Critique / À surveiller / Correct / Solide**.

La **norme affichée** est le seuil de vigilance : l’atteindre signifie *Correct*, pas encore *Solide*.

Pour chaque ligne vous pouvez :

- modifier le commentaire et la recommandation (en ligne ou via **Réviser les commentaires**) ;
- **Partir du texte généré** puis l’adapter ;
- **Rétablir le texte généré** ;
- changer la **priorité** (classement des actions dans le rapport) ;
- **Masquer au rapport** (le ratio reste à l’écran).

Actions de masse : *Masquer les ratios bien orientés* (livrable resserré), *Tout réafficher*.

Un ratio **sans objet** (ex. couverture du BFR alors que le BFR est négatif) n’est pas jugé critique : il est neutralisé avec une explication.

### 8.4 Flux, capitaux propres, scores

- **Flux de trésorerie** : besoin d’une période N-1. Le bouclage avec la variation de trésorerie du bilan est garanti par construction. Un écart signale une saisie, pas le moteur.
- **Variation des capitaux propres** : distingue un *reclassement interne* (total inchangé) d’un *mouvement non documenté* (à justifier en annexe).
- **Risque de défaillance** : Altman Z'' (marchés émergents), Conan et Holder, note /100.  
  **Réserve obligatoire** : ces modèles n’ont pas été validés sur un échantillon malgache. Ce sont des signaux, pas un diagnostic. Une divergence entre modèles est en soi une information.

---

## 9. Conclusion générale

Sur le **dossier**, bouton **Générer un projet de conclusion**.

Le texte (six parties) s’appuie uniquement sur les chiffres calculés. Si une conclusion existe déjà, choisissez *Remplacer* ou *Ajouter à la suite*.

Complétez toujours par ce que le module ignore : marché, gouvernance, projets, événements postérieurs à la clôture. Le bandeau du texte le rappelle.

---

## 10. Comparer plusieurs périodes

Deux à cinq périodes, **durées éventuellement inégales** (exercice 12 mois + semestre).

Les ratios qui mélangent un flux et un stock sont **annualisés**. Une réserve méthodologique figure au rapport. Renseignez la **note de saisonnalité** sur les périodes courtes.

Depuis le dossier :

- **Générer le comparatif** — tableau + tendance rédigée (progression, dégradation, creux, point haut) ;
- **Rapport comparatif PDF** — A4 paysage, toutes les périodes en colonnes.

Ou menu *Analyses > Comparatif multi-périodes* pour un sous-ensemble.

---

## 11. Imprimer et exporter

### Rapport PDF d’une période

Sur la période : **Imprimer > Rapport d’analyse financière** (A4 portrait).

Sommaire type : contexte, bilan financier, SIG, capitaux propres, flux, **lecture d’ensemble puis ratios**, scores, synthèse, recommandations, annexes, glossaire.

### Rapport comparatif

Voir § 10.

### Export Excel

**Action > Exporter en Excel** : saisie, agrégats, ratios, comparatif, glossaire. Les mêmes options d’inclusion qu’à l’impression.

---

## 12. Options du rapport (onglet du dossier)

| Option | Effet |
|---|---|
| Inclure les recommandations | Décochez pour un rapport purement descriptif |
| Portée | Tous les ratios / Points d’attention (défaut) / Critiques seulement |
| Explication des ratios | Volet « Ce que mesure le ratio » |
| Formules de calcul | Ligne *Calcul :* |
| Variation des capitaux propres | État PCG chapitre 4 |
| Tableau des flux | État PCG chapitre 5 |
| Méthode directe | Encaissements / décaissements bruts |
| Score de risque | Section défaillance |
| Glossaire | Annexe |
| Synthèse des recommandations | Tableau final classé par urgence |

Ces options **n’effacent rien à l’écran**. Elles ne filtrent que le livrable.

---

## 13. Configuration (groupe Manager)

| Menu | Usage |
|---|---|
| Rubriques PCG 2005 | Ajouter, masquer, renommer un poste |
| Ratios & seuils | Formule, unité, seuils, documentation, règles de commentaire |
| Secteurs d’activité | Huit secteurs livrés + copie de normes vers un nouveau secteur |
| Normes sectorielles | Vue transversale des seuils |
| Calibrer sur mon portefeuille | Quartiles observés sur *vos* dossiers → nouveaux seuils |
| Recharger le référentiel livré | Récupérer les corrections du module sans perdre vos personnalisations (`noupdate`) |

### Calibrage

Les seuils livrés **ne sont pas des statistiques officielles malgaches**. Ils sont des références professionnelles, ajustées au contexte (import, marchés publics, crédit-bail, campagne agricole, microfinance). Chaque norme porte son **origine**.

La seule base réellement locale, ce sont vos dossiers :

1. *Configuration > Calibrer sur mon portefeuille*
2. Choisir le secteur, filtrer de préférence les exercices de 12 mois
3. Exiger un échantillon suffisant (5 à 10 dossiers)
4. Relire l’aperçu (Q1 / médiane / Q3) ligne par ligne
5. Appliquer

Recalibrez une fois par an.

### Formules de ratios

Expression Python. Variables : codes de rubriques (`ST_CP`, `AC_STOCK`…) et agrégats (`FRNG`, `BFR`, `TN`, `VA`, `EBE`, `CAF`, `CA`…).  
Protégez les divisions : `X / Y if Y else 0`.  
Dans les textes de règles : `{value}`, `{prev}`, `{norm}`, `{company}`, `{period}`.

Les conditions peuvent utiliser `t_bad`, `t_watch`, `t_good` (elles suivent alors la norme sectorielle) et les agrégats (`TN`, `CBC`, `DETTES_FIN`…).

---

## 14. Points de vigilance

1. **Charges en positif.**
2. **Périodes courtes** : annualisation + note de saisonnalité.
3. **Impôts et taxes dans le seuil EBE** : option **décochée** par défaut (déjà dans l’EBE).
4. **Normes** : références professionnelles, pas l’INSTAT. Le dire au client.
5. **Scores de défaillance** : signaux étrangers, pas un diagnostic malgache.
6. **Textes automatiques** : premier jet. Relire surtout liquidité, levier et délais fournisseurs (le module contextualise, mais le jugement reste le vôtre).
7. **Informations complémentaires aberrantes** : aucun équilibre comptable ne les rattrape. Lisez les contrôles de vraisemblance.
8. **Recharger le référentiel** après une mise à jour du module si vous voulez les nouvelles règles, tout en cochant *Conserver mes seuils personnalisés* le cas échéant.

---

## 15. Questions fréquentes

**Pourquoi un ratio « bon » à l’écran est-il « à surveiller » dans le rapport d’un autre secteur ?**  
Parce que le secteur du dossier a ses propres seuils. Vérifiez l’onglet *Identification* du dossier.

**Pourquoi la valeur affichée a plus de décimales que d’habitude ?**  
L’arrondi habituel placerait le chiffre du mauvais côté d’un seuil. Le module ajoute une décimale pour que l’appréciation reste lisible.

**Le tableau des flux est vide.**  
Reliez une période N-1, ou saisissez la trésorerie d’ouverture dans les informations complémentaires.

**Analyser a-t-il écrasé ma rédaction ?**  
Non, sauf si vous avez cliqué *Restaurer les textes générés*.

**L’installation échoue (« External ID not found »).**  
Contrôle hors Odoo :  
`python3 mg_financial_analysis/tools_check_install.py`

**Comment installer le module ?**  
Copier le dossier `mg_financial_analysis` dans les addons, redémarrer Odoo, *Mettre à jour la liste des applications*, installer *Analyse Financière*. Pour le jeu de démonstration, créer la base avec les données de démonstration.

---

## 16. Carte des menus

```
Analyse Financière
├── Dossiers
├── États financiers
└── Analyses
    ├── Bilan financier
    ├── Compte de résultat / SIG
    ├── Flux de trésorerie
    ├── Variation des capitaux propres
    ├── Ratios & marges
    ├── Lecture des ratios
    ├── Comparatif multi-périodes
    ├── Contrôles de saisie
    ├── Scores de risque
    └── Réviser les commentaires
Configuration                          (Manager)
├── Rubriques PCG 2005
├── Ratios & seuils
├── Secteurs d'activité
├── Normes sectorielles
├── Calibrer sur mon portefeuille
└── Recharger le référentiel livré
```

---

*Version du module documentée : 16.0.1.12.0. Ce manuel complète le README technique du module ; en cas d’écart, le comportement à l’écran prime.*
