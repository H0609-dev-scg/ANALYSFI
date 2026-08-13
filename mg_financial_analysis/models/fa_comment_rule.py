# -*- coding: utf-8 -*-
from odoo import models, fields


class FaCommentRule(models.Model):
    """Règle de génération de commentaire et de recommandation pour un ratio.

    La première règle dont la condition est vraie (dans l'ordre de séquence)
    fournit le commentaire et la recommandation.
    """
    _name = 'fa.comment.rule'
    _description = "Règle de commentaire et de recommandation"
    _order = 'ratio_id, sequence, id'

    ratio_id = fields.Many2one('fa.ratio', string="Ratio", required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string="Séquence", default=10)
    name = fields.Char(string="Intitulé de la règle", required=True)

    condition = fields.Char(
        string="Condition", required=True,
        help="Expression Python portant sur « value » (valeur du ratio) et « prev » "
             "(valeur de la période précédente). Exemple : value < 1")

    appreciation = fields.Selection([
        ('bad', "Critique"),
        ('watch', "À surveiller"),
        ('ok', "Correct"),
        ('good', "Solide"),
    ], string="Appréciation", required=True, default='ok')

    comment_tpl = fields.Text(
        string="Modèle de commentaire", required=True, translate=True,
        help="Texte avec variables entre accolades : {value}, {prev}, {variation}, "
             "{norm}, {company}, {period}.")

    recommendation_tpl = fields.Text(
        string="Modèle de recommandation", translate=True,
        help="Action préconisée. Mêmes variables disponibles que le commentaire.")

    force_appreciation = fields.Boolean(
        string="Imposer l'appréciation", default=False,
        help="Par défaut, l'appréciation est calculée à partir des seuils du ratio "
             "(sectoriels s'ils existent), la règle ne fournissant que le texte. "
             "Cochez cette case pour les cas particuliers où l'appréciation ci-dessus "
             "doit primer, par exemple lorsqu'une donnée source est absente.")

    priority = fields.Selection([
        ('1', "Haute"),
        ('2', "Moyenne"),
        ('3', "Basse"),
    ], string="Priorité de la recommandation", default='2')

    active = fields.Boolean(string="Actif", default=True)
