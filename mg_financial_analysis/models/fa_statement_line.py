# -*- coding: utf-8 -*-
from odoo import models, fields, api


class FaStatementLine(models.Model):
    """Ligne de saisie : montant d'une rubrique pour une période donnée."""
    _name = 'fa.statement.line'
    _description = "Ligne d'état financier"
    _order = 'statement_type, sequence, id'

    statement_id = fields.Many2one(
        'fa.statement', string="État financier", required=True,
        ondelete='cascade', index=True)
    rubric_id = fields.Many2one(
        'fa.rubric', string="Rubrique", required=True, ondelete='restrict', index=True)

    # Champs liés au référentiel : permettent le groupement et le tri dans les vues
    code = fields.Char(related='rubric_id.code', store=True, string="Code")
    sequence = fields.Integer(related='rubric_id.sequence', store=True)
    statement_type = fields.Selection(related='rubric_id.statement_type', store=True)
    section = fields.Selection(related='rubric_id.section', store=True, string="Section")
    line_type = fields.Selection(related='rubric_id.line_type', store=True)
    is_detail = fields.Boolean(related='rubric_id.is_detail', store=True)
    has_gross = fields.Boolean(related='rubric_id.has_gross', store=True)
    rubric_note = fields.Text(related='rubric_id.note', string="Aide")

    currency_id = fields.Many2one(related='statement_id.currency_id', store=True)
    company_id = fields.Many2one(related='statement_id.company_id', store=True)
    show_gross = fields.Boolean(related='statement_id.show_gross')

    amount_gross = fields.Monetary(string="Brut", default=0.0)
    amount_deprec = fields.Monetary(
        string="Amort. / Pertes de valeur", default=0.0,
        help="Amortissements et pertes de valeur cumulés. Saisir en positif.")
    amount_net = fields.Monetary(
        string="Net", compute='_compute_amount_net',
        store=True, readonly=False, default=0.0,
        help="Calculé automatiquement (Brut - Amortissements) dès qu'un montant brut "
             "est saisi. Reste saisissable directement si vous ne disposez que du net.")

    amount_previous = fields.Monetary(
        string="Net N-1", compute='_compute_previous', store=True, readonly=False)
    variation = fields.Monetary(string="Variation", compute='_compute_variation', store=True)
    variation_pct = fields.Float(
        string="Var. %", compute='_compute_variation', store=True,
        digits=(16, 2), group_operator=False)

    note = fields.Char(string="Commentaire de saisie")

    _sql_constraints = [
        ('rubric_statement_uniq', 'unique(statement_id, rubric_id)',
         "Une rubrique ne peut être saisie qu'une seule fois par période."),
    ]

    @api.depends('amount_gross', 'amount_deprec')
    def _compute_amount_net(self):
        for line in self:
            if line.amount_gross or line.amount_deprec:
                line.amount_net = line.amount_gross - line.amount_deprec
            else:
                line.amount_net = line.amount_net or 0.0

    @api.depends('statement_id.previous_statement_id', 'rubric_id')
    def _compute_previous(self):
        for line in self:
            prev_stmt = line.statement_id.previous_statement_id
            if prev_stmt and line.rubric_id:
                prev_line = prev_stmt.line_ids.filtered(
                    lambda l, r=line.rubric_id: l.rubric_id == r)
                line.amount_previous = prev_line[:1].amount_net or 0.0
            else:
                line.amount_previous = line.amount_previous or 0.0

    @api.depends('amount_net', 'amount_previous')
    def _compute_variation(self):
        for line in self:
            line.variation = line.amount_net - line.amount_previous
            line.variation_pct = (
                (line.variation / abs(line.amount_previous)) * 100.0
                if line.amount_previous else 0.0)

    def name_get(self):
        return [(l.id, l.rubric_id.name or '') for l in self]
