# -*- coding: utf-8 -*-
"""Calibrage des normes sectorielles sur le portefeuille réel du cabinet.

Les seuils livrés avec le module sont des références professionnelles générales.
La seule source de données véritablement malgache dont dispose un cabinet est
son propre portefeuille de dossiers. Cet assistant calcule les quartiles observés
sur les périodes déjà analysées d'un secteur, et propose de les convertir en
seuils.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FaCalibrateWizard(models.TransientModel):
    _name = 'fa.calibrate.wizard'
    _description = "Calibrage des normes sur le portefeuille"

    sector_id = fields.Many2one('fa.sector', string="Secteur à calibrer", required=True)

    date_from = fields.Date(
        string="Périodes clôturées à partir du",
        help="Limite le calibrage aux exercices récents, plus représentatifs.")
    date_to = fields.Date(string="Jusqu'au")

    only_annual = fields.Boolean(
        string="Exercices de 12 mois uniquement", default=True,
        help="Recommandé : les périodes infra-annuelles annualisées introduisent "
             "un biais de saisonnalité dans les statistiques.")

    min_sample = fields.Integer(
        string="Échantillon minimal", default=5,
        help="Un ratio observé sur moins de dossiers que ce seuil n'est pas calibré.")

    method = fields.Selection([
        ('quartile', "Quartiles (Q1 / médiane / Q3)"),
        ('median_only', "Médiane seule (sans modifier les seuils)"),
    ], string="Méthode", default='quartile', required=True,
        help="Quartiles : le premier quartile devient le seuil de vigilance et le "
             "troisième le seuil de confort, en respectant le sens de lecture du "
             "ratio. Médiane seule : renseigne le repère sans toucher aux seuils.")

    line_ids = fields.One2many('fa.calibrate.line', 'wizard_id', string="Résultats")
    state = fields.Selection([('config', "Paramétrage"), ('preview', "Aperçu")],
                             default='config')
    statement_count = fields.Integer(string="Périodes retenues", readonly=True)
    summary = fields.Text(string="Synthèse", readonly=True)

    def _get_statements(self):
        self.ensure_one()
        domain = [
            ('state', '=', 'analyzed'),
            ('analysis_id.sector_id', '=', self.sector_id.id),
        ]
        if self.date_from:
            domain.append(('date_to', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_to', '<=', self.date_to))
        if self.only_annual:
            domain.append(('duration_months', '=', 12))
        return self.env['fa.statement'].search(domain)

    @staticmethod
    def _quantile(sorted_values, q):
        """Quantile par interpolation linéaire."""
        n = len(sorted_values)
        if n == 0:
            return 0.0
        if n == 1:
            return sorted_values[0]
        pos = (n - 1) * q
        low = int(pos)
        high = min(low + 1, n - 1)
        frac = pos - low
        return sorted_values[low] * (1 - frac) + sorted_values[high] * frac

    def action_preview(self):
        """Calcule les statistiques observées, sans rien modifier."""
        self.ensure_one()
        stmts = self._get_statements()
        if not stmts:
            raise UserError(_(
                "Aucune période analysée ne correspond à ces critères pour le "
                "secteur « %s ».\n\nLe calibrage suppose d'avoir déjà traité "
                "plusieurs dossiers de ce secteur dans le module.") % self.sector_id.name)

        self.line_ids.unlink()
        results = self.env['fa.ratio.result'].search([
            ('statement_id', 'in', stmts.ids),
            ('is_na', '=', False),
        ])

        by_ratio = {}
        for res in results:
            by_ratio.setdefault(res.ratio_id, []).append(res.value)

        Norm = self.env['fa.sector.norm']
        vals = []
        retained = skipped = 0
        for ratio, values in by_ratio.items():
            if len(values) < self.min_sample:
                skipped += 1
                continue
            retained += 1
            values.sort()
            q1 = self._quantile(values, 0.25)
            med = self._quantile(values, 0.50)
            q3 = self._quantile(values, 0.75)

            existing = Norm.search([
                ('sector_id', '=', self.sector_id.id),
                ('ratio_id', '=', ratio.id),
            ], limit=1)
            current = existing or ratio

            # Sens de lecture : le « bon » côté n'est pas le même pour tous
            if self.method == 'median_only':
                new_bad = current.threshold_bad
                new_watch = current.threshold_watch
                new_good = current.threshold_good
            elif ratio.direction == 'higher':
                new_bad = self._quantile(values, 0.10)
                new_watch = q1
                new_good = q3
            elif ratio.direction == 'lower':
                new_bad = self._quantile(values, 0.90)
                new_watch = q3
                new_good = q1
            else:  # plage optimale : on encadre par les quartiles
                new_bad = self._quantile(values, 0.10)
                new_watch = q1
                new_good = med
            vals.append({
                'wizard_id': self.id,
                'ratio_id': ratio.id,
                'sample_size': len(values),
                'observed_min': values[0],
                'observed_q1': q1,
                'observed_median': med,
                'observed_q3': q3,
                'observed_max': values[-1],
                'current_bad': current.threshold_bad,
                'current_watch': current.threshold_watch,
                'current_good': current.threshold_good,
                'new_bad': new_bad,
                'new_watch': new_watch,
                'new_good': new_good,
                'apply': len(values) >= self.min_sample,
            })
        if vals:
            self.env['fa.calibrate.line'].create(vals)

        self.write({
            'state': 'preview',
            'statement_count': len(stmts),
            'summary': _(
                "%(nb)s période(s) analysée(s) retenue(s) sur %(nc)s client(s) du secteur "
                "« %(sec)s ».\n%(ret)s ratio(s) disposent d'un échantillon suffisant "
                "(au moins %(mini)s observations) ; %(skip)s ratio(s) ont été écartés.\n\n"
                "Les statistiques ci-dessous proviennent de vos propres dossiers : "
                "c'est la référence la plus pertinente pour le marché malgache. "
                "Vérifiez chaque ligne avant d'appliquer.",
                nb=len(stmts), nc=len(stmts.mapped('partner_id')),
                sec=self.sector_id.name, ret=retained, mini=self.min_sample, skip=skipped),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fa.calibrate.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply(self):
        """Crée ou met à jour les normes sectorielles retenues."""
        self.ensure_one()
        Norm = self.env['fa.sector.norm']
        created = updated = 0
        for line in self.line_ids.filtered('apply'):
            norm = Norm.search([
                ('sector_id', '=', self.sector_id.id),
                ('ratio_id', '=', line.ratio_id.id),
            ], limit=1)
            unit = line.ratio_id.unit
            suffix = {'percent': ' %', 'days': ' j', 'times': '', 'years': ' ans'}.get(unit, '')
            sense = '>' if line.ratio_id.direction == 'higher' else '<'
            label = _("%(s)s %(v).1f%(u)s (%(sec)s)",
                      s=sense, v=line.new_watch, u=suffix, sec=self.sector_id.name)
            vals = {
                'threshold_bad': line.new_bad,
                'threshold_watch': line.new_watch,
                'threshold_good': line.new_good,
                'norm_label': label,
                'sector_median': line.observed_median,
                'source': 'portfolio',
                'source_note': _("Calibré sur %(n)s dossiers du portefeuille",
                                 n=line.sample_size),
                'sample_size': line.sample_size,
                'last_calibration': fields.Date.context_today(self),
            }
            if norm:
                norm.write(vals)
                updated += 1
            else:
                vals.update({'sector_id': self.sector_id.id, 'ratio_id': line.ratio_id.id})
                Norm.create(vals)
                created += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Calibrage appliqué"),
                'message': _("%(c)s norme(s) créée(s), %(u)s mise(s) à jour pour le "
                             "secteur « %(s)s ».",
                             c=created, u=updated, s=self.sector_id.name),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class FaCalibrateLine(models.TransientModel):
    _name = 'fa.calibrate.line'
    _description = "Ligne de calibrage"
    _order = 'ratio_family, ratio_id'

    wizard_id = fields.Many2one('fa.calibrate.wizard', ondelete='cascade', required=True)
    ratio_id = fields.Many2one('fa.ratio', string="Ratio", required=True)
    ratio_code = fields.Char(related='ratio_id.code', string="Code")
    ratio_family = fields.Selection(related='ratio_id.family', string="Famille")
    unit = fields.Selection(related='ratio_id.unit', string="Unité")
    direction = fields.Selection(related='ratio_id.direction', string="Sens")

    sample_size = fields.Integer(string="Échantillon")
    observed_min = fields.Float(string="Min", digits=(16, 2))
    observed_q1 = fields.Float(string="Q1", digits=(16, 2))
    observed_median = fields.Float(string="Médiane", digits=(16, 2))
    observed_q3 = fields.Float(string="Q3", digits=(16, 2))
    observed_max = fields.Float(string="Max", digits=(16, 2))

    current_bad = fields.Float(string="Critique actuel", digits=(16, 2))
    current_watch = fields.Float(string="Vigilance actuel", digits=(16, 2))
    current_good = fields.Float(string="Confort actuel", digits=(16, 2))

    new_bad = fields.Float(string="Critique proposé", digits=(16, 2))
    new_watch = fields.Float(string="Vigilance proposé", digits=(16, 2))
    new_good = fields.Float(string="Confort proposé", digits=(16, 2))

    apply = fields.Boolean(string="Appliquer", default=True)
