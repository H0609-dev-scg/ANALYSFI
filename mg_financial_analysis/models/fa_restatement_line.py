# -*- coding: utf-8 -*-
from odoo import models, fields


class FaRestatementLine(models.Model):
    """Trace d'un retraitement de passage du bilan comptable au bilan financier."""
    _name = 'fa.restatement.line'
    _description = "Retraitement financier"
    _order = 'statement_id, sequence, id'

    statement_id = fields.Many2one(
        'fa.statement', string="État financier", required=True,
        ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='statement_id.currency_id', store=True)
    sequence = fields.Integer(string="Séquence", default=10)

    restatement_type = fields.Selection([
        ('fictif', "Élimination des actifs fictifs"),
        ('leasing', "Réintégration du crédit-bail"),
        ('eene', "Effets escomptés non échus"),
        ('stock_outil', "Reclassement du stock outil"),
        ('dette_ct', "Part à moins d'un an des dettes financières"),
        ('creance_lt', "Créances à plus d'un an"),
        ('dividende', "Dividendes à distribuer"),
        ('imp_diff', "Impôts différés"),
        ('other', "Autre retraitement"),
    ], string="Type de retraitement", required=True)

    name = fields.Char(string="Libellé", required=True)
    amount = fields.Monetary(string="Montant")
    account_debit = fields.Char(string="Poste augmenté")
    account_credit = fields.Char(string="Poste diminué")
    note = fields.Text(string="Justification")
