# Analyse Financière — PCG 2005 Malagasy

Module Odoo 16 pour cabinets de conseil : saisie des états financiers, bilan financier,
soldes intermédiaires de gestion, ratios, commentaires et recommandations automatiques.

**Manuel d’utilisation (consultants)** : [doc/MANUEL_UTILISATION.md](doc/MANUEL_UTILISATION.md)

## Installation

```bash
# 1. Copier le module dans le répertoire des addons
cp -r mg_financial_analysis /chemin/vers/odoo/addons/

# 2. Redémarrer le service Odoo
sudo systemctl restart odoo

# 3. Dans Odoo : Applications > Mettre à jour la liste des applications
#    puis rechercher « Analyse Financière » et installer.
```

Pour charger le jeu de démonstration (société malagasy fictive, exercice 2025 + S1 2026),
créer la base avec l'option « données de démonstration » activée.

## Prise en main

1. **Analyse Financière > Dossiers** — créer un dossier, sélectionner le client et le secteur.
2. Onglet *Périodes* — ajouter une période (ex. « Exercice 2025 », 01/01 au 31/12).
   Les 76 lignes de saisie sont générées automatiquement.
3. Saisir le bilan (onglets Actif / Passif), le compte de résultat, puis les
   informations complémentaires — ou bouton **Importer un tableur** pour charger
   un CSV / Excel dont la première colonne porte les codes de rubrique.
   Un aperçu permet de vérifier chaque ligne avant écriture ; les montants
   déjà saisis ne sont pas écrasés par défaut. Le bandeau de contrôle affiche
   en permanence l'écart Actif − Passif : il doit être nul pour pouvoir valider.
4. Bouton **Analyser** — calcule agrégats, ratios, commentaires et recommandations.
5. Consulter d'abord l'onglet *Lecture des ratios* (ordre de lecture et
   contradictions entre familles), puis *Bilan financier & SIG* et
   *Ratios & recommandations*.
6. **Imprimer > Rapport d'analyse financière** pour le PDF d'une période,
   ou **Action > Exporter en Excel** pour le classeur multi-onglets.
7. Depuis le dossier, bouton **Rapport comparatif PDF** : génère le comparatif de
   toutes les périodes et imprime directement le rapport multi-périodes.

## Conformité PCG 2005

Le module produit l'ensemble des états financiers exigés :

| État | Référence | Statut |
|---|---|---|
| Bilan (actif / passif, courant / non courant) | chapitre 2 | ✅ |
| Compte de résultat par nature | chapitre 3 | ✅ |
| Tableau de variation des capitaux propres | chapitre 4, art. 240-1 et 240-2 | ✅ |
| Tableau des flux de trésorerie | chapitre 5, art. 250-1 à 250-5 | ✅ |

## Tableau de variation des capitaux propres

État **obligatoire** au PCG 2005 (chapitre 4), généré automatiquement dès qu'une
période de comparaison existe. Onglet *Variation des capitaux propres*.

Présentation matricielle : une **colonne par rubrique** de capitaux propres
(capital émis, primes et réserves, écarts de réévaluation, écarts d'équivalence,
report à nouveau, résultat, intérêts minoritaires) et une **ligne par mouvement**.

Les cinq catégories minimales de l'article 240-2 sont couvertes :

1. résultat net de l'exercice ;
2. changements de méthode comptable et corrections d'erreurs fondamentales ;
3. autres produits et charges imputés directement en capitaux propres
   (écarts de réévaluation et d'équivalence) ;
4. opérations en capital — augmentation, diminution, remboursement ;
5. distributions de résultat et affectations décidées sur la période.

Le module reconstitue automatiquement l'**affectation du résultat antérieur** :
le résultat de la période précédente quitte sa colonne pour rejoindre le report
à nouveau, sous déduction des dividendes distribués.

> **Bouclage garanti colonne par colonne.** Une ligne d'ajustement résiduelle
> absorbe tout écart entre les mouvements identifiés et la variation réellement
> constatée au bilan. Vérifié sur 300 jeux de données aléatoires.

Le module distingue deux situations que le total seul masquerait :

- un **reclassement** — les colonnes se compensent, le total est inchangé :
  typiquement une mise en réserve ou une incorporation au capital. Le module
  l'identifie, nomme les rubriques concernées et invite à confirmer avec le
  procès-verbal d'assemblée ;
- un **mouvement non documenté** — le total varie sans explication : changement
  de méthode, correction d'erreur ou donnée manquante. Signalé en orange, à
  justifier dans l'annexe.

Le champ *Reclassements internes* mesure la somme des écarts en valeur absolue :
un total net nul n'y échappe pas.

## Tableau des flux de trésorerie

État **obligatoire** au PCG 2005 (chapitre 5, articles 250-1 à 250-5), produit
automatiquement dès qu'une période de comparaison existe. Onglet
*Flux de trésorerie* de la période.

Les **deux méthodes** prévues à l'article 250-3 sont générées :

- **méthode indirecte** — part du résultat net, neutralise les charges et
  produits sans effet de trésorerie, puis intègre la variation du besoin en
  fonds de roulement ;
- **méthode directe** — présente les encaissements et décaissements bruts
  (clients, fournisseurs, personnel, impôts, intérêts), avec le rapprochement
  au résultat avant impôts exigé par l'article 250-3.

Les trois catégories réglementaires sont respectées : activités
opérationnelles, d'investissement et de financement.

> **Bouclage garanti.** Le calcul dérive de l'équation du bilan plutôt que
> d'une addition de postes indépendants. La somme des trois catégories égale
> donc *par construction* la variation de trésorerie constatée au bilan. Vérifié
> sur 300 jeux de données aléatoires : 300 bouclages exacts. Un écart signalé
> ne peut venir que d'une incohérence de saisie, jamais de la mécanique.

Le module calcule également le **flux de trésorerie disponible** (free cash
flow) : flux opérationnels diminués des investissements corporels et
incorporels — ce qui reste réellement pour rémunérer les apporteurs de capitaux.

Quand les informations complémentaires (emprunts nouveaux, remboursements,
augmentation de capital, dividendes) sont renseignées, les flux sont présentés
ventilés ; sinon le module les reconstitue en net à partir des variations de
bilan, en le signalant.

## Seuil de rentabilité

Deux méthodes, pilotées par le champ *Méthode du seuil de rentabilité* du dossier.

**Par le taux d'excédent brut d'exploitation** (défaut) — ne dépend que de
données toujours saisies :

```
Taux d'EBE            = EBE / Chiffre d'affaires
Charges de structure  = Dotations aux amortissements
                      + Frais financiers
                      + Impôts exigibles sur les résultats
Seuil de rentabilité  = Charges de structure / Taux d'EBE
```

**Par les coûts variables** — plus précise, mais suppose de ventiler les charges :

```
Seuil de rentabilité = Charges fixes / Taux de marge sur coûts variables
```

En mode *Automatique*, le module retient les coûts variables si les charges
fixes et variables sont renseignées, et bascule sinon sur l'EBE. Les ratios
**D11 Point mort** et **D12 Marge de sécurité** sont donc toujours exploitables.

> **Impôts et taxes.** Ils sont **déjà déduits** dans le calcul de l'EBE
> (`EBE = VA + subventions − personnel − impôts et taxes`). Les réintégrer aux
> charges de structure reviendrait à les compter deux fois et majorerait le
> seuil d'environ 20 %. L'option *Inclure les impôts et taxes* existe pour les
> méthodologies qui l'exigent, mais elle est **décochée par défaut**.
>
> Contrôle de cohérence : au niveau du seuil calculé, le résultat net
> reconstitué doit être nul. C'est vérifié par le test `test_94`.

Les indicateurs sont regroupés dans une catégorie dédiée **Seuil de rentabilité**,
distincte de la capacité d'autofinancement, avec une mise en forme adaptée à
chaque unité :

| Élément | 2024 | 2025 | S1 2026 |
|---|---|---|---|
| Taux d'EBE | 9,92 % | 8,16 % | 5,83 % |
| Charges de structure | 115 M | 130 M | 128 M |
| Seuil de rentabilité | 1 159 M | 1 593 M | 2 197 M |
| Point mort | 282 j | 352 j | 495 j |
| Marge de sécurité | +21,8 % | +2,3 % | −37,6 % |

### Ratios associés, avec commentaire et recommandation

Quatre ratios de la famille **D. Rentabilité et marges** analysent le seuil,
chacun avec son explication, son commentaire contextualisé, sa recommandation
d'action et ses normes sectorielles :

| Code | Ratio | Formule | Norme négoce |
|---|---|---|---|
| D11 | Point mort | SR × 360 / CA | < 300 jours |
| D12 | Marge de sécurité | (CA − SR) / CA | > 20 % |
| **D13** | **Couverture des charges de structure** | EBE / Charges de structure | > 1,4 |
| **D14** | **Chiffre d'affaires nécessaire au seuil** | SR / CA | < 88 % |

**D13** répond à la question « l'exploitation finance-t-elle les amortissements
et la dette ? ». En dessous de 1, la réponse est non.

**D14** se lit immédiatement en réunion : « il vous faut 137 % de votre chiffre
d'affaires actuel rien que pour atteindre l'équilibre ». Contrôle de cohérence
intégré : D14 + D12 = 100 %.

Les cas extrêmes sont traités par des règles dédiées : marge de sécurité
négative, point mort au-delà de 360 jours, excédent brut d'exploitation nul.
Le vocabulaire des recommandations est aligné sur la méthode EBE — on parle de
*charges de structure*, non de *charges fixes*.

En méthode coûts variables, les lignes s'adaptent : le taux de marge sur coûts
variables et la marge sur coûts variables remplacent les charges de structure.

Sur le jeu de démonstration, la trajectoire est parlante :

| Période | Taux d'EBE | Charges de structure | Point mort | Marge de sécurité |
|---|---|---|---|---|
| Exercice 2024 | 9,92 % | 115 M | 282 jours | +21,8 % |
| Exercice 2025 | 8,16 % | 130 M | 352 jours | +2,3 % |
| S1 2026 | 5,83 % | 128 M | 495 jours | −37,6 % |

## Score de risque de défaillance

Chaque analyse produit trois scores indépendants, dans l'onglet
*Risque de défaillance* :

| Modèle | Nature | Zones |
|---|---|---|
| **Altman Z''** marchés émergents | 4 ratios + constante 3,25 ; variante adaptée aux sociétés non cotées et non industrielles | danger < 1,10 · incertitude · sécurité > 2,60 |
| **Conan et Holder** | Fonction discriminante à 5 ratios, sensible aux frais financiers et à la masse salariale | danger < 9 · incertitude · sécurité > 16 |
| **Note de synthèse** | Agrégation des appréciations de tous les ratios, pondérée par famille | /100, cinq niveaux |

Le détail du calcul est affiché composante par composante, avec la contribution
de chaque ratio au score final. Une **divergence entre les modèles** est en soi
une information : elle signale une situation contrastée selon l'angle d'analyse,
et le commentaire généré le dit explicitement.

> **Réserve.** Ces modèles ont été calibrés sur des populations d'entreprises
> européennes et américaines. Aucun n'a été validé sur un échantillon malgache.
> Ce sont des signaux d'alerte statistiques, jamais des diagnostics. Chaque
> commentaire généré rappelle cette limite.

## Projet de conclusion automatique

Le bouton **Générer un projet de conclusion** (onglet *Conclusion générale* du
dossier) rédige un premier jet structuré en six parties : cadrage de la mission,
activité et rentabilité, équilibre financier, structure et solvabilité, risque
de défaillance, et trois priorités d'action tirées des recommandations les mieux
classées.

Le texte s'appuie exclusivement sur les valeurs calculées : aucune affirmation
sans support chiffré. Si une conclusion existe déjà, un assistant propose de la
remplacer ou d'ajouter le projet à la suite.

Il reste un **brouillon** : à compléter par les éléments qualitatifs que le
module ne connaît pas — marché, gouvernance, projets en cours, événements
postérieurs à la clôture.

## Les deux rapports PDF

| Rapport | Portée | Format | Où le lancer |
|---|---|---|---|
| **Analyse financière** | Une période | A4 portrait | Période > Imprimer |
| **Comparatif multi-périodes** | 2 à 5 périodes en colonnes | A4 paysage | Dossier > *Rapport comparatif PDF*, ou Comparatif > *Imprimer le rapport* |

Le rapport comparatif comprend :

1. **Page de garde** — tableau des périodes avec durées et mention d'audit, plus
   un tableau de bord comptant les ratios critiques, à surveiller, corrects et solides.
2. **Contexte et méthodologie** — caractéristiques du secteur, réserve sur
   l'annualisation des périodes infra-annuelles, origine des normes.
3. **Bilan financier** — grandes masses et équilibre financier, toutes périodes
   en colonnes, avec évolution en pourcentage, micro-graphique de tendance par
   ligne et histogramme groupé FRNG / BFR / Trésorerie nette.
4. **Compte de résultat** — soldes intermédiaires de gestion et capacité
   d'autofinancement, avec histogramme CA / VA / EBE / Résultat net.
5. **Ratios par famille** — valeurs sur toutes les périodes, tendance, norme
   appliquée, appréciation en couleur, puis le commentaire détaillé de chaque ratio
   suivi de son analyse de tendance.
6. **Synthèse de la trajectoire** — indicateurs les plus dégradés et les plus
   améliorés sur la série, points forts et points de vigilance.
7. **Recommandations** — classées par urgence, avec l'indicateur concerné.

Les graphiques sont des SVG générés côté serveur : aucune dépendance externe,
rendu identique en PDF et à l'écran.

## Contenu

| Élément | Volume |
|---|---|
| Rubriques PCG 2005 | 102 (dont 76 saisissables) |
| Ratios financiers | 51 en 6 familles |
| Règles de commentaire | 172 |
| Agrégats calculés | 35 |
| Secteurs d'activité | 8 |
| Normes sectorielles | 71 |
| Tests unitaires | 160 |
| Modèles de scoring | 3 |

## Comparaison de plusieurs périodes

Le module compare **deux à cinq périodes** de durées quelconques. Cas type :
Exercice 2024 (12 mois), Exercice 2025 (12 mois) et Semestre 1 2026 (6 mois).

Chaque période possède ses propres dates de début et de fin ; la durée en mois
en est déduite automatiquement et pilote l'annualisation.

Depuis le dossier, le bouton **Générer le comparatif** crée un tableau reprenant
toutes les périodes en colonnes, avec l'évolution entre la plus ancienne et la
plus récente, et une **analyse de tendance rédigée** pour chaque ligne :
progression continue, dégradation continue, évolution en creux ou point haut
suivi d'une inflexion.

Le comparatif peut aussi être créé manuellement via
*Analyses > Comparatif multi-périodes* pour choisir un sous-ensemble de périodes.

## ⚠️ Origine des normes de ratios — à lire avant usage

**Les seuils livrés avec le module ne sont pas des statistiques officielles
malgaches.** Aucune base publique de ratios financiers sectoriels n'existe pour
Madagascar : l'INSTAT publie des agrégats macroéconomiques (chiffre d'affaires
et valeur ajoutée par branche), pas des quartiles de ratios exploitables comme
normes d'analyse.

Les seuils fournis sont donc des **références professionnelles générales**,
issues de la pratique de l'analyse financière, ajustées par appréciation aux
réalités structurelles du contexte malgache :

- délais d'importation allongeant la durée de stockage en négoce ;
- délais de règlement des marchés publics dépassant fréquemment 90 jours en BTP ;
- recours massif au crédit-bail dans le transport ;
- saisonnalité de campagne en agro-industrie ;
- normes prudentielles distinctes pour la microfinance.

Chaque norme porte un champ **Origine du seuil** qui trace sa provenance :
*Référence professionnelle générale*, *Calibré sur le portefeuille du cabinet*,
*Étude sectorielle* ou *Jugement d'expert*. Le rapport PDF mentionne
explicitement cette réserve.

### Calibrer les normes sur votre portefeuille

C'est la réponse concrète au problème : **vos propres dossiers constituent la
seule source de données réellement malgache dont vous disposez.**

*Configuration > Calibrer sur mon portefeuille* (ou le bouton du même nom sur la
fiche secteur) analyse les périodes déjà traitées d'un secteur, calcule les
quartiles observés et propose de les convertir en seuils :

- le premier quartile devient le seuil de vigilance, le troisième le seuil de
  confort — en respectant le sens de lecture de chaque ratio ;
- la médiane observée devient le repère affiché dans les rapports ;
- les ratios dont l'échantillon est inférieur  au moins 5 à 10
dossiers par secteur. Recalibrez une fois par an. Après deux ou trois exercices
de pratique, vos normes vaudront mieux que n'importe quelle référence importée.

## Normes par secteur d'activité

Un même ratio ne se juge pas de la même façon selon l'activité. Le module fournit
huit secteurs pré-paramétrés — Commerce/Négoce, Industrie, Services, BTP,
Agro-industrie, Transport/Logistique, Microfinance, Autre — dont **59 seuils
spécifiques** qui se substituent aux seuils génériques.

Exemples de divergences volontaires :

| Ratio | Négoce | Industrie | Services |
|---|---|---|---|
| Autonomie financière | > 25 % | > 35 % | > 25 % |
| Taux de valeur ajoutée | > 12 % | > 30 % | > 45 % |
| Marge brute d'exploitation | > 5 % | > 12 % | > 10 % |
| Écoulement des stocks | < 60 j | < 100 j | < 30 j |
| Part du personnel dans la VA | < 55 % | < 62 % | < 75 % |

Sur un jeu de test, **8 ratios sur 10 changent d'appréciation** entre le négoce et
l'industrie à valeurs identiques.

Chaque norme sectorielle porte en outre une **médiane de référence** et une
**précision rédigée** qui vient enrichir le commentaire — par exemple, pour le
négoce : « compte tenu des délais d'importation à Madagascar, un stock de 50 à
70 jours reste courant sur les produits importés ».

Le paramétrage se fait dans *Configuration > Secteurs d'activité*. Un assistant
permet de recopier le jeu de normes d'un secteur vers un autre pour créer une
variante rapidement.

> **Architecture des seuils.** L'appréciation (Critique / À surveiller / Correct /
> Solide) est toujours dérivée des seuils applicables au client, jamais figée dans
> la règle de commentaire. Les conditions des règles s'écrivent avec les variables
> `t_bad`, `t_watch`, `t_good`, `t_max` : elles suivent donc automatiquement la
> norme sectorielle. Seules les règles marquées *Imposer l'appréciation* font
> exception, pour les cas particuliers du type donnée manquante ou valeur négative.

## Commentaires et recommandations

Chaque ratio produit automatiquement :

1. un **commentaire** décrivant la valeur au regard de la norme applicable,
2. la **phrase de tendance** par rapport à la période précédente, avec
   qualification favorable ou défavorable selon le sens de lecture du ratio,
3. la **comparaison à la médiane du secteur** lorsqu'elle est renseignée,
4. la **précision sectorielle** éventuelle,
5. une **recommandation d'action** hiérarchisée en priorité haute, moyenne ou basse.

Les deux textes sont **modifiables** de trois manières :

- directement dans l'onglet *Ratios & recommandations* de la période (colonnes
  « Modifier le commentaire » et « Modifier la recommandation », éditables en ligne) ;
- via le bouton **Réviser les commentaires**, qui ouvre une vue plein écran plus
  confortable, avec le texte généré affiché en regard du champ de saisie ;
- dans le formulaire détaillé d'un ratio, onglets *Commentaire* et *Recommandation*.

Le bouton *Partir du texte généré* recopie la version automatique dans le champ
éditable pour l'adapter plutôt que la réécrire. Le bouton *Rétablir le texte
généré* annule la personnalisation. Une colonne **Modifié** signale les lignes
retouchées.

> **Vos textes sont conservés.** Relancer *Analyser* recalcule les valeurs et
> régénère les textes automatiques, mais **préserve** vos commentaires,
> recommandations, priorités et masquages. Vous pouvez donc corriger une saisie
> après avoir rédigé, sans perdre votre travail.

## Rendre les recommandations optionnelles

Tout est réglable, à deux niveaux.

### Au niveau du dossier — onglet *Options du rapport*

| Option | Effet |
|---|---|
| **Inclure les recommandations** | Décochée, produit un rapport purement descriptif |
| **Portée des recommandations** | *Tous les ratios* · *Points d'attention* (défaut) · *Ratios critiques uniquement* |
| **Inclure la synthèse des recommandations** | Le tableau récapitulatif de fin de rapport |
| **Inclure l'explication des ratios** | Le volet « Ce que mesure le ratio » |
| **Afficher les formules de calcul** | La ligne *Calcul :* sous l'explication |
| **Inclure le tableau des flux** | L'état de trésorerie PCG 2005 |
| **Ajouter la méthode directe** | Le détail des encaissements et décaissements bruts |
| **Inclure le score de risque** | La section dédiée aux modèles de défaillance |
| **Inclure le glossaire** | L'annexe de définition des ratios |

Effet mesuré sur le jeu de démonstration (49 ratios) :

| Configuration | Recommandations imprimées |
|---|---|
| Tous les ratios | 49 |
| Points d'attention (défaut) | 28 |
| Ratios critiques uniquement | 10 |
| Recommandations désactivées | 0 |

### Au niveau de chaque ratio — onglet *Ratios & recommandations*

- **Masquer au rapport** : exclut un ratio des documents imprimés sans le
  supprimer de l'analyse ; il reste consultable à l'écran.
- **Priorité** : remplace la priorité automatique pour le classement des
  actions dans le tableau de synthèse.
- Deux actions de masse : **Masquer les ratios bien orientés** (resserre le
  livrable sur les points d'attention) et **Tout réafficher**.

Ces réglages sont indépendants de l'affichage à l'écran : même exclues du
livrable, les recommandations restent disponibles dans le module pour votre
propre travail.

### À l'export Excel

Les mêmes options sont proposées dans l'assistant d'export : inclusion des
recommandations, de l'explication, de l'onglet glossaire, et respect des
ratios masqués.

## Points d'attention

**Saisie des charges** — toujours en positif : le module applique le signe lors du
calcul des soldes.

**Périodes de durées inégales** — les ratios mêlant un flux et un stock sont
annualisés automatiquement (attribut `annualize` de chaque ratio). Le rapport
mentionne systématiquement la réserve méthodologique. Renseigner la *note de
saisonnalité* dans l'onglet Notes.

**Contrôles croisés** — la trésorerie nette est calculée par deux voies
(FRNG − BFR et Trésorerie active − passive) et la CAF par les méthodes additive
et soustractive. Un écart signale une incohérence de saisie.

## Paramétrage

Les référentiels sont modifiables sans développement par le groupe *Manager* :

- **Configuration > Rubriques PCG 2005** — ajouter, masquer ou renommer un poste.
- **Configuration > Secteurs d'activité** — secteurs et leurs seuils spécifiques.
- **Configuration > Normes sectorielles** — vue transversale de tous les seuils.
- **Configuration > Ratios & seuils** — formule, unité, seuils, normes sectorielles.
  Variables disponibles dans les formules : tous les codes de rubriques
  (`ST_CP`, `AC_STOCK`…) et les agrégats (`FRNG`, `BFR`, `TN`, `VA`, `EBE`, `CAF`,
  `CA`, `AI`, `CAPITAUX_PERMANENTS`, `DETTES_FIN`, `CAPITAUX_EMPLOYES`…).
  Protéger les divisions : `X / Y if Y else 0`.
- Onglet *Règles de commentaire* de chaque ratio — conditions et textes,
  avec variables `{value}`, `{prev}`, `{variation}`, `{norm}`, `{company}`, `{period}`.

## Droits

| Groupe | Portée |
|---|---|
| Lecture seule | Consultation et impression |
| Consultant | Saisie, analyse, création de dossiers |
| Manager / Associé | Paramétrage des référentiels, suppression |

## Tests

```bash
odoo -d ma_base -i mg_financial_analysis --test-enable --stop-after-init
```

114 tests couvrent la génération des lignes, les contrôles d'équilibre, les SIG,
l'équilibre financier, la CAF par deux méthodes, l'annualisation, l'absence de
division par zéro, les normes sectorielles, le comparatif à trois périodes et
l'édition des commentaires, le rapport multi-périodes, le calibrage, les options
d'impression et la préservation des textes personnalisés.

## Vérification avant installation

Un script de contrôle est fourni pour valider l'intégrité du module sans
démarrer Odoo :

```bash
python3 mg_financial_analysis/tools_check_install.py
```

Il vérifie que chaque identifiant XML est défini **avant** d'être référencé,
en rejouant l'ordre de chargement du manifest. C'est la cause de l'erreur
`External ID not found in the system` rencontrée à l'installation.

Le même contrôle est également exécuté par les tests unitaires
(`test_90_manifest_load_order`), ainsi qu'une validation de toutes les vues
(`test_91_view_fields_exist`) qui détecte les champs supprimés d'un modèle
mais encore cités dans une vue.

### Contrôles effectués par le script

| Contrôle | Détecte |
|---|---|
| Ordre de chargement | `External ID not found in the system` |
| Syntaxe Odoo 16 | `column_invisible`, `<list>`, expressions dans `invisible` — syntaxes Odoo 17 |
| Champs des vues | `Définition de vue invalide` après renommage ou suppression d'un champ |
| Intégrité générale | Fichiers absents, modules non importés, droits manquants, doublons d'identifiant |
ssions dans `invisible` — syntaxes Odoo 17 |
| Champs des vues | `Définition de vue invalide` après renommage ou suppression d'un champ |
| Intégrité générale | Fichiers absents, modules non importés, droits manquants, doublons d'identifiant |
