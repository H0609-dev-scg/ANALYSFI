# -*- coding: utf-8 -*-
from odoo import models, fields, api


class FaRatioResult(models.Model):
    """Résultat d'un ratio pour une période : valeur, appréciation, commentaire."""
    _name = 'fa.ratio.result'
    _description = "Résultat de ratio"
    _order = 'family, sequence, id'

    statement_id = fields.Many2one(
        'fa.statement', string="Période", required=True, ondelete='cascade', index=True)
    analysis_id = fields.Many2one(related='statement_id.analysis_id', store=True, string="Dossier")
    partner_id = fields.Many2one(related='statement_id.partner_id', store=True, string="Client")
    currency_id = fields.Many2one(related='statement_id.currency_id', store=True)

    ratio_id = fields.Many2one('fa.ratio', string="Ratio", required=True, ondelete='cascade')
    code = fields.Char(related='ratio_id.code', store=True, string="Code")
    name = fields.Char(related='ratio_id.name', store=True, string="Libellé")
    family = fields.Selection(related='ratio_id.family', store=True, string="Famille")
    sequence = fields.Integer(related='ratio_id.sequence', store=True)
    unit = fields.Selection(related='ratio_id.unit', store=True, string="Unité")
    formula = fields.Char(related='ratio_id.formula', string="Formule")
    norm_label = fields.Char(related='ratio_id.norm_label', string="Norme générique")
    norm_applied = fields.Char(
        string="Norme appliquée", readonly=True,
        help="Norme effectivement retenue : sectorielle si elle existe, générique sinon.")
    is_sector_norm = fields.Boolean(string="Norme sectorielle", readonly=True)
    sector_id = fields.Many2one(related='statement_id.sector_id', store=True,
                                string="Secteur")
    sector_median = fields.Float(string="Médiane du secteur", digits=(16, 4),
                                 group_operator=False, readonly=True)
    vs_median = fields.Float(string="Écart / médiane", digits=(16, 4),
                             compute='_compute_vs_median', store=True,
                             group_operator=False)
    interpretation = fields.Text(related='ratio_id.interpretation',
                                 string="Ce que mesure le ratio")
    calculation_note = fields.Text(related='ratio_id.calculation_note',
                                   string="Précisions de calcul")
    threshold_rationale = fields.Text(related='ratio_id.threshold_rationale',
                                      string="Justification des seuils")
    limits = fields.Text(related='ratio_id.limits',
                         string="Limites d'interprétation")
    threshold_summary = fields.Char(related='ratio_id.threshold_summary',
                                    string="Grille de lecture")
    annualized = fields.Boolean(related='ratio_id.annualize', string="Flux annualisés")

    # Quatre décimales en stockage : l'appréciation est calculée sur la valeur
    # exacte, il faut donc conserver assez de précision pour que la valeur
    # affichée ne semble pas contredire son appréciation. Un ratio de 1,1951
    # jugé « à surveiller » face à une norme de 1,2 s'afficherait « 1,20 »
    # avec deux décimales, ce qui paraîtrait incohérent au lecteur.
    value = fields.Float(string="Valeur", digits=(16, 4), group_operator=False)
    previous_value = fields.Float(string="Valeur N-1", digits=(16, 4), group_operator=False)
    variation = fields.Float(
        string="Variation", digits=(16, 4), compute='_compute_variation',
        store=True, group_operator=False)
    trend = fields.Selection([
        ('up', "En hausse"),
        ('down', "En baisse"),
        ('stable', "Stable"),
    ], string="Tendance", compute='_compute_variation', store=True)

    value_display = fields.Char(string="Valeur formatée", compute='_compute_display')

    is_na = fields.Boolean(string="Non calculable", default=False)
    na_reason = fields.Char(string="Motif")

    appreciation = fields.Selection([
        ('bad', "Critique"),
        ('watch', "À surveiller"),
        ('ok', "Correct"),
        ('good', "Solide"),
    ], string="Appréciation", index=True)

    priority = fields.Selection([
        ('1', "Haute"),
        ('2', "Moyenne"),
        ('3', "Basse"),
    ], string="Priorité", default='2')

    comment_auto = fields.Text(string="Commentaire généré", readonly=True)
    comment_manual = fields.Text(
        string="Commentaire du consultant",
        help="Si renseigné, remplace le commentaire généré dans le rapport.")
    comment = fields.Text(string="Commentaire retenu", compute='_compute_final', store=True)

    recommendation_auto = fields.Text(string="Recommandation générée", readonly=True)
    recommendation_manual = fields.Text(string="Recommandation du consultant")
    recommendation = fields.Text(
        string="Recommandation retenue", compute='_compute_final', store=True)

    @api.depends('value', 'sector_median')
    def _compute_vs_median(self):
        for rec in self:
            rec.vs_median = (rec.value - rec.sector_median) if rec.sector_median else 0.0

    @api.depends('value', 'previous_value')
    def _compute_variation(self):
        for rec in self:
            rec.variation = rec.value - rec.previous_value
            if not rec.previous_value:
                rec.trend = 'stable'
            elif rec.variation > abs(rec.previous_value) * 0.02:
                rec.trend = 'up'
            elif rec.variation < -abs(rec.previous_value) * 0.02:
                rec.trend = 'down'
            else:
                rec.trend = 'stable'

    @api.depends('value', 'unit', 'is_na', 'appreciation', 'ratio_id')
    def _compute_display(self):
        """Met en forme la valeur, en évitant qu'elle contredise l'appréciation.

        L'appréciation est calculée sur la valeur exacte. Si l'arrondi d'affichage
        usuel place la valeur du bon côté d'un seuil alors qu'elle est en réalité
        de l'autre, une décimale supplémentaire est ajoutée : un ratio de 1,1951
        jugé « à surveiller » face à une norme de 1,2 doit s'afficher « 1,195 »
        et non « 1,20 ».
        """
        Statement = self.env['fa.statement']
        for rec in self:
            if rec.is_na:
                rec.value_display = "N/A"
                continue
            display = Statement._fmt(rec.value, rec.unit)
            thresholds = rec._nearby_thresholds()
            if thresholds and rec._display_contradicts(display, thresholds):
                display = Statement._fmt_precise(rec.value, rec.unit)
            rec.value_display = display

    def _nearby_thresholds(self):
        """Seuils applicables au ratio, sectoriels le cas échéant."""
        self.ensure_one()
        if not self.ratio_id:
            return []
        sector = self.statement_id.analysis_id.sector_id
        t = self.ratio_id.get_thresholds(sector)
        return [t['bad'], t['watch'], t['good'], t['max']]

    def _display_contradicts(self, display, thresholds):
        """Vrai si la valeur arrondie franchit un seuil que la valeur exacte ne franchit pas."""
        self.ensure_one()
        import re as _re
        match = _re.search(r'-?[\d]+[.,]?[\d]*', display.replace('\u202f', '').replace(' ', ''))
        if not match:
            return False
        try:
            shown = float(match.group(0).replace(',', '.'))
        except ValueError:
            return False
        exact = self.value
        for threshold in thresholds:
            if not threshold:
                continue
            if (exact < threshold <= shown) or (shown <= threshold < exact):
                return True
            if (exact > threshold >= shown) or (shown >= threshold > exact):
                return True
        return False

    hide_in_report = fields.Boolean(
        string="Masquer dans le rapport", default=False,
        help="Exclut ce ratio des rapports imprimés, tout en le conservant à l'écran. "
             "Utile pour alléger un livrable client ou écarter un indicateur non "
             "pertinent pour le dossier.")

    priority_manual = fields.Selection([
        ('1', "Haute"),
        ('2', "Moyenne"),
        ('3', "Basse"),
    ], string="Priorité du consultant",
        help="Remplace la priorité déduite automatiquement pour le classement "
             "des recommandations dans le rapport.")

    priority_final = fields.Selection([
        ('1', "Haute"),
        ('2', "Moyenne"),
        ('3', "Basse"),
    ], string="Priorité retenue", compute='_compute_final', store=True)

    is_customized = fields.Boolean(
        string="Texte personnalisé", compute='_compute_final', store=True,
        help="Coché lorsque le consultant a saisi son propre commentaire "
             "ou sa propre recommandation.")

    @api.depends('comment_auto', 'comment_manual', 'recommendation_auto',
                 'recommendation_manual', 'priority', 'priority_manual')
    def _compute_final(self):
        for rec in self:
            rec.comment = rec.comment_manual or rec.comment_auto
            rec.recommendation = rec.recommendation_manual or rec.recommendation_auto
            rec.priority_final = rec.priority_manual or rec.priority or '2'
            rec.is_customized = bool(rec.comment_manual or rec.recommendation_manual
                                     or rec.priority_manual)

    def action_reset_text(self):
        """Efface la version du consultant et rétablit le texte généré."""
        self.write({
            'comment_manual': False,
            'recommendation_manual': False,
            'priority_manual': False,
        })
        return True

    def action_toggle_hide(self):
        """Bascule l'inclusion du ratio dans les rapports imprimés."""
        for rec in self:
            rec.hide_in_report = not rec.hide_in_report
        return True

    def action_copy_auto_to_manual(self):
        """Recopie le texte généré dans le champ éditable, comme point de départ."""
        for rec in self:
            rec.comment_manual = rec.comment_manual or rec.comment_auto
            rec.recommendation_manual = rec.recommendation_manual or rec.recommendation_auto
        return True

    def name_get(self):
        return [(r.id, "%s : %s" % (r.name, r.value_display)) for r in self]
