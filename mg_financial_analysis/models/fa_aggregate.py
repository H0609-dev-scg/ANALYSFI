# -*- coding: utf-8 -*-
from odoo import models, fields, api


class FaAggregate(models.Model):
    """Agrégat calculé : grandes masses du bilan financier, SIG, CAF."""
    _name = 'fa.aggregate'
    _description = "Agrégat financier calculé"
    _order = 'statement_id, sequence, id'

    statement_id = fields.Many2one(
        'fa.statement', string="État financier", required=True,
        ondelete='cascade', index=True)
    analysis_id = fields.Many2one(related='statement_id.analysis_id', store=True)
    currency_id = fields.Many2one(related='statement_id.currency_id', store=True)

    code = fields.Char(string="Code", required=True, index=True)
    name = fields.Char(string="Agrégat", required=True)
    sequence = fields.Integer(string="Séquence", default=10)

    category = fields.Selection([
        ('balance', "Bilan financier - grandes masses"),
        ('equilibrium', "Équilibre financier"),
        ('sig', "Soldes intermédiaires de gestion"),
        ('caf', "Capacité d'autofinancement"),
        ('breakeven', "Seuil de rentabilité"),
    ], string="Catégorie", required=True, index=True)

    amount = fields.Monetary(string="Montant période")
    amount_annualized = fields.Monetary(
        string="Montant annualisé",
        help="Flux ramené à 12 mois pour comparaison avec un exercice complet.")

    # Les agrégats exprimés en taux ou en durée ne sont pas des montants : le
    # champ Monetary les arrondit à l'unité de la devise, ce qui transformait
    # un taux d'EBE de 0,1126 en 0,11, soit 11,00 % au lieu de 11,26 %.
    ratio_value = fields.Float(
        string="Valeur du taux", digits=(16, 6), group_operator=False,
        help="Valeur exacte des agrégats exprimés en pourcentage ou en jours.")
    ratio_value_annualized = fields.Float(
        string="Valeur annualisée du taux", digits=(16, 6), group_operator=False)

    unit = fields.Selection([
        ('amount', "Montant"),
        ('percent', "Pourcentage"),
        ('days', "Jours"),
    ], string="Unité", default='amount', required=True,
        help="Certains agrégats sont des taux ou des durées, non des montants : "
             "l'unité pilote leur mise en forme.")

    value_display = fields.Char(
        string="Valeur", compute='_compute_value_display',
        help="Montant mis en forme selon son unité.")

    @api.depends('amount', 'ratio_value', 'unit', 'currency_id')
    def _compute_value_display(self):
        for rec in self:
            if rec.unit == 'percent':
                rec.value_display = "%.2f %%" % (rec.ratio_value * 100.0)
            elif rec.unit == 'days':
                value = rec.ratio_value
                # Une durée non nulle mais inférieure au jour reste affichée
                if value and abs(value) < 1:
                    rec.value_display = "%.1f j" % value
                else:
                    rec.value_display = "%.0f j" % value
            else:
                symbol = rec.currency_id.name or ''
                rec.value_display = "%s %s" % (
                    '{:,.0f}'.format(rec.amount).replace(',', '\u202f'), symbol)

    def name_get(self):
        return [(a.id, a.name) for a in self]
