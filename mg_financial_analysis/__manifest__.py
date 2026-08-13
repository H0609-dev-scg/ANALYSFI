# -*- coding: utf-8 -*-
{
    'name': "Analyse Financière (PCG 2005 Malagasy)",
    'summary': "Saisie des états financiers PCG 2005, bilan financier, SIG, ratios, "
               "commentaires et recommandations automatiques",
    'description': """
Module d'analyse financière pour cabinets de conseil
====================================================
* Saisie guidée des états financiers conformes au PCG 2005 malagasy
  (Bilan Actif / Passif en courant - non courant, Compte de résultat par nature)
* Contrôles d'équilibre automatiques (Actif = Passif, Résultat CR = Résultat bilan)
* Retraitements financiers traçables (crédit-bail, actifs fictifs, EENE, stock outil...)
* Bilan financier en grandes masses : FRNG, BFRE, BFRHE, Trésorerie nette
* Compte de résultat financier : Soldes Intermédiaires de Gestion et CAF (2 méthodes)
* Plus de 50 ratios répartis en 6 familles, formules et seuils paramétrables
* Commentaires et recommandations générés par moteur de règles, éditables
* Comparaison multi-périodes avec annualisation (ex. exercice 12 mois vs semestre)
* Rapport PDF et export Excel

Conformité PCG 2005
-------------------
* Bilan (chapitre 2) et compte de résultat par nature (chapitre 3)
* Tableau de variation des capitaux propres (chapitre 4, art. 240-1 et 240-2)
* Tableau des flux de trésorerie (chapitre 5, art. 250-1 à 250-5),
  méthodes directe et indirecte, bouclage garanti par construction

Analyse avancée
---------------
* Seuil de rentabilité par le taux d'excédent brut d'exploitation ou par
  les coûts variables, avec point mort et marge de sécurité
* Scoring du risque de défaillance : Altman Z'' marchés émergents,
  Conan et Holder, note de synthèse pondérée
* Projet de conclusion rédigé automatiquement à partir des indicateurs
* Calibrage des normes sectorielles sur le portefeuille du cabinet
    """,
    'author': "Cabinet de conseil financier",
    'website': "https://www.example.mg",
    'category': 'Accounting/Accounting',
    'version': '16.0.1.12.0',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/fa_security.xml',
        'security/ir.model.access.csv',
        'data/fa_sequence.xml',
        'data/fa_rubric_data.xml',
        'data/fa_ratio_data.xml',
        'data/fa_comment_rule_data.xml',
        # Les normes sectorielles référencent les ratios : à charger après eux
        'data/fa_sector_data.xml',
        'views/fa_rubric_views.xml',
        'views/fa_sector_views.xml',
        'views/fa_statement_views.xml',
        'views/fa_analysis_views.xml',
        'views/fa_ratio_views.xml',
        'views/fa_insight_views.xml',
        'views/fa_score_views.xml',
        'views/fa_cashflow_views.xml',
        'views/fa_equity_views.xml',
        'views/fa_extra_check_views.xml',
        'views/fa_comparison_views.xml',
        'wizard/fa_export_wizard_views.xml',
        'wizard/fa_import_wizard_views.xml',
        'wizard/fa_calibrate_wizard_views.xml',
        'wizard/fa_reload_data_views.xml',
        'report/fa_report_action.xml',
        'report/fa_report_templates.xml',
        'report/fa_report_comparison_templates.xml',
        'views/fa_menus.xml',
    ],
    'demo': [
        'data/fa_demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
