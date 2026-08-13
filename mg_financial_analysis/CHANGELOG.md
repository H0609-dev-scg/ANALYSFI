# Journal des versions

## 16.0.1.12.0

**Lecture croisée des ratios**

Les cinquante ratios étaient commentés un par un. Un consultant ne lit pas
ainsi : il cherche les contradictions et l'ordre de lecture.

- Nouvel onglet **Lecture des ratios** sur la période, menu *Analyses*.
- **Ordre de lecture** : les huit indicateurs qui déterminent le diagnostic,
  classés par gravité.
- **Constats croisés** : bénéfice sans trésorerie, liquidité générale
  portée par les stocks, EBE positif et résultat net négatif, levier sans
  dette bancaire, activité sous le seuil de rentabilité, ROE gonflé par
  des fonds propres trop faibles, etc.
- **Synthèse par famille** : une phrase d'ensemble pour la structure, la
  liquidité, l'activité, la rentabilité, la VA et la couverture.
- Repris en tête de la section 4 du rapport PDF.

## 16.0.1.11.0

**Import de la saisie depuis un tableur**

La saisie manuelle des 76 rubriques est le goulet d'étranglement du dossier.
Les états arrivent presque toujours en Excel : l'export existait, l'import
manquait.

- Assistant **Importer un tableur** sur la période (CSV ou Excel).
- Première colonne = code de rubrique (`AC_STOCK`, `PL_VENTE_MSE`…). Le
  fichier produit par l'export du module est accepté tel quel.
- **Aperçu préalable** : chaque ligne est reconnue, inconnue ou hors saisie.
  Le consultant coche ce qu'il importe et peut corriger un montant avant
  écriture.
- Option **Écraser les montants déjà saisis** désactivée par défaut : une
  valeur déjà saisie n'est jamais remplacée à l'insu du consultant.
- Modèle CSV téléchargeable, une ligne par rubrique du référentiel.

## 16.0.1.10.0

**Fiabilisation des informations complémentaires**

Ces données ne figurent pas au bilan : aucune égalité comptable ne les
contraint, une valeur aberrante y passait donc inaperçue et faussait
silencieusement les ratios qui en dépendent.

- **Quinze contrôles de vraisemblance** rapprochent chaque saisie d'une
  grandeur du bilan ou du compte de résultat : coefficient de taxe sur la
  valeur ajoutée improbable, actifs fictifs confondus avec les immobilisations
  financières, emprunt saisi deux fois, crédit-bail sans dette de contrepartie,
  amortissements supérieurs au brut, stock moyen hors bornes, écart entre
  dividendes déclarés et variation des capitaux propres.
- Chaque alerte indique la **valeur attendue**, le **motif** et les **ratios
  impactés**. Trois niveaux : incohérence, à vérifier, information.
- **Pré-remplissage automatique** des données déductibles des états financiers.
  Les valeurs suggérées portent une mention explicite et ne remplacent jamais
  une saisie existante.
- **Quatre rubriques jamais exploitées** sont désormais actives : stock outil
  (retraitement R4 du cahier des charges), acquisitions et cessions
  d'immobilisations financières, subventions d'investissement encaissées.
- Un bandeau signale les incohérences dès l'ouverture de la période.


## 16.0.1.9.0

**Rechargement du référentiel livré**

Les fichiers de données du module portent l'attribut `noupdate="1"` : vos
personnalisations survivent aux mises à jour, mais les corrections apportées
au référentiel livré ne sont pas reprises automatiquement. Une mise à jour du
module ne suffisait donc pas à récupérer les seuils rectifiés ou les nouvelles
règles de commentaire.

- Nouvel assistant **Configuration > Recharger le référentiel livré**.
- Portée au choix : ratios, règles de commentaire, secteurs, rubriques ou tout.
- **Aperçu préalable** listant précisément les écarts entre la base et les
  fichiers, champ par champ, avant toute écriture.
- Option **Conserver mes seuils personnalisés** pour ne récupérer que les
  formules et la documentation.
- Les commentaires et recommandations réécrits sur les analyses ne sont jamais
  touchés.


## 16.0.1.8.0

**Revue du référentiel de ratios et documentation des seuils**

Audit complet des 51 ratios et de leurs seuils.

- **14 normes incohérentes corrigées.** La valeur affichée comme norme ne
  désignait pas toujours le même seuil : tantôt la vigilance, tantôt le
  confort. Une entreprise atteignant la norme annoncée pouvait rester jugée
  « à surveiller ». Les 51 normes désignent désormais le seuil de vigilance.
- **Ratio B6 corrigé** : ses seuils étaient fixés à 0, 1 et 2 alors qu'il
  exprime un montant en ariary. Toute trésorerie nette comprise entre 0 et
  2 Ar aurait été jugée insuffisante. Lecture désormais binaire.
- **Contrainte d'ordre des seuils** : le module refuse un paramétrage où le
  seuil critique serait plus favorable que le seuil de confort.
- **Quatre volets de documentation** ajoutés sur chaque ratio : définition,
  précisions de calcul, justification des seuils et limites d'interprétation.
  Soit 204 textes rédigés.
- **Grille de lecture** générée automatiquement à partir des seuils, affichée
  en configuration et dans les rapports.
- **Glossaire des rapports refondu** en fiches détaillées, avec une note
  liminaire expliquant comment lire les quatre niveaux d'appréciation.


## 16.0.1.7.0

**Contextualisation des constats et précision des taux**

Corrections issues de la relecture critique d'un rapport client.

- **Bug d'affichage des taux** : les agrégats exprimés en pourcentage étaient
  stockés dans un champ monétaire, arrondi à l'unité de la devise. Un taux
  d'excédent brut d'exploitation de 11,26 % s'affichait « 11,00 % » et une
  marge de sécurité de 51,37 % devenait « 51,00 % ». Un champ flottant dédié
  conserve désormais la valeur exacte. Les calculs, eux, étaient corrects.
- **Les règles de commentaire accèdent aux agrégats financiers**. Une
  appréciation peut ainsi être nuancée selon le contexte, et non selon le
  seul niveau du ratio.
- **Liquidité immédiate** : lorsque l'entreprise ne supporte aucun découvert
  et dégage une trésorerie positive, le module n'invite plus à négocier une
  ligne de trésorerie. Il explique que le ratio est écrasé par un passif
  d'exploitation élevé et oriente vers la surveillance du crédit fournisseur.
- **Levier financier** : un multiplicateur élevé sans dette financière n'est
  plus traité comme un problème d'endettement. Le commentaire identifie le
  crédit fournisseur comme origine et recommande de sécuriser les conditions
  de paiement plutôt que de renforcer les capitaux propres en urgence.
- **Délai fournisseur** : un délai long accompagné d'une trésorerie saine est
  présenté comme un risque opérationnel de rupture d'approvisionnement, et
  non comme le symptôme d'une difficulté de trésorerie.


## 16.0.1.6.0

**Précision des valeurs et arrondis d'affichage**

Revue systématique de tous les points d'arrondi du module.

- Les ratios, scores et lignes de comparatif sont désormais stockés avec
  **quatre décimales** au lieu de deux. Avec deux décimales, un ratio de
  1,1951 était stocké 1,20 : la valeur affichée semblait respecter une norme
  de 1,2 alors que l'appréciation la jugeait « à surveiller ».
- La **note de synthèse** passe de zéro à deux décimales : arrondie, une note
  de 64,7 devenait 65 et basculait de la zone d'incertitude à la zone de
  sécurité.
- **Affichage adaptatif** : lorsque l'arrondi usuel placerait la valeur du
  mauvais côté d'un seuil, une décimale supplémentaire est ajoutée
  automatiquement. Les valeurs éloignées des seuils conservent leur format
  habituel.
- Les évolutions en pourcentage des comparatifs et des lignes de saisie
  passent à deux décimales.

Aucun calcul n'était faux : l'appréciation a toujours été déterminée sur la
valeur exacte. Ces corrections portent sur la lisibilité et la cohérence
apparente entre la valeur affichée et son appréciation.

## 16.0.1.5.0

**Ratios sans objet et arrondis d'affichage**

Corrections issues de l'audit d'un rapport client réel.

- Nouveau champ **Condition d'applicabilité** sur les ratios : lorsqu'un ratio
  perd son sens dans une configuration donnée, il est déclaré *sans objet*
  avec un message explicatif, plutôt que calculé à zéro puis jugé critique.
- Appliqué à 8 ratios dont le dénominateur peut être négatif : A2, A4, A8,
  **B8**, C7, D6, D7, F3.
- **B8 Couverture du BFR par le FR** : un besoin en fonds de roulement négatif
  signifie que le cycle d'exploitation dégage de la trésorerie. Le ratio
  affichait 0,00 et concluait à une situation critique avec une recommandation
  de financement long terme, alors que la situation est favorable.
- **B4** devient *Excédent du fonds de roulement sur le BFR (en jours de CA)* :
  la formule compare désormais le fonds de roulement au besoin, conformément à
  la norme qui était annoncée mais jamais appliquée. Le ratio équivaut à la
  trésorerie nette rapportée à l'activité.
- Les valeurs non nulles inférieures à l'unité d'affichage conservent une
  décimale : un fonds de roulement de 0,3 jour ne s'affiche plus « 0 jours ».

## 16.0.1.4.0

**Seuil de rentabilité — commentaires et recommandations**

- Deux ratios ajoutés : **D13** Couverture des charges de structure
  (EBE / charges de structure) et **D14** Chiffre d'affaires nécessaire au
  seuil (SR / CA), chacun avec explication, commentaire, recommandation et
  normes sectorielles.
- Règles dédiées aux cas extrêmes : marge de sécurité négative, point mort
  au-delà de 360 jours, excédent brut d'exploitation nul.
- Vocabulaire de D11 et D12 aligné sur la méthode EBE : on parle désormais
  de *charges de structure* et non de *charges fixes*.
- 12 normes sectorielles supplémentaires sur 6 secteurs.

## 16.0.1.3.0

**Seuil de rentabilité par l'excédent brut d'exploitation**

- Nouvelle méthode : `SR = charges de structure / taux d'EBE`, où les charges
  de structure regroupent dotations, frais financiers et impôts exigibles.
  Fonctionne sans ventilation des charges en fixes et variables.
- Trois modes : automatique (coûts variables si disponibles, sinon EBE),
  toujours EBE, toujours coûts variables.
- Option *Inclure les impôts et taxes*, désactivée par défaut : ce poste est
  déjà déduit dans l'EBE, le réintégrer majorerait le seuil d'environ 20 %.
- Catégorie d'agrégats **Seuil de rentabilité** distincte de la CAF, avec un
  champ `unit` qui met en forme montants, pourcentages et durées.
- Point mort et marge de sécurité deviennent des agrégats ; les ratios D11 et
  D12 les réutilisent, garantissant des valeurs identiques.
- Ordre des soldes intermédiaires corrigé : le chiffre d'affaires ouvre la
  cascade, avec ses composantes en détail.

## 16.0.1.2.0

**Conformité PCG 2005 complétée**

- **Tableau des flux de trésorerie** (chapitre 5, art. 250-1 à 250-5),
  méthodes directe et indirecte, trois catégories de flux. Le calcul dérive
  de l'équation du bilan : le bouclage est garanti par construction.
- **Tableau de variation des capitaux propres** (chapitre 4, art. 240-1 et
  240-2), présentation matricielle par rubrique, avec distinction entre
  reclassement interne et mouvement non documenté.
- 10 rubriques de saisie ajoutées pour les flux.

## 16.0.1.1.0

**Scoring, conclusion et options de rapport**

- Trois modèles de risque de défaillance : Altman Z'' marchés émergents,
  Conan et Holder, note de synthèse pondérée par famille de ratios.
- Génération automatique d'un projet de conclusion en six parties.
- Options d'impression au niveau du dossier : recommandations, portée,
  explications, formules, glossaire, score, flux de trésorerie.
- Masquage d'un ratio au rapport et priorité manuelle, ratio par ratio.
- Les textes personnalisés survivent désormais à une nouvelle analyse.
- Correctifs : requêtes N+1 dans le comparatif, allègement du contrôle
  d'équilibre à la saisie, règle RG-04 enfin implémentée.

## 16.0.1.0.0

**Version initiale**

- Saisie des états financiers PCG 2005, 112 rubriques.
- Bilan financier retraité, soldes intermédiaires de gestion, CAF.
- Catalogue de ratios avec commentaires et recommandations paramétrables.
- Normes par secteur d'activité et calibrage sur le portefeuille.
- Comparaison de deux à cinq périodes avec annualisation.
- Rapports PDF mono-période et comparatif, export Excel.
