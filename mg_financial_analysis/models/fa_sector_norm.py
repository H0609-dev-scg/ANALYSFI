# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class FaSector(models.Model):
    """Secteur d'activité du client, porteur de ses propres normes de ratios."""
    _name = 'fa.sector'
    _description = "Secteur d'activité"
    _order = 'sequence, name'

    name = fields.Char(string="Secteur", required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    sequence = fields.Integer(string="Séquence", default=10)

    description = fields.Text(
        string="Caractéristiques financières", translate=True,
        help="Traits structurels du secteur : intensité capitalistique, cycle "
             "d'exploitation, saisonnalité. Repris en tête du rapport.")

    norm_ids = fields.One2many('fa.sector.norm', 'sector_id', string="Normes sectorielles")
    norm_count = fields.Integer(string="Nb normes", compute='_compute_norm_count')

    active = fields.Boolean(string="Actif", default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', "Le code du secteur doit être unique."),
    ]

    @api.depends('norm_ids')
    def _compute_norm_count(self):
        for rec in self:
            rec.norm_count = len(rec.norm_ids)

    def action_view_norms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Normes de %s") % self.name,
            'res_model': 'fa.sector.norm',
            'view_mode': 'tree,form',
            'domain': [('sector_id', '=', self.id)],
            'context': {'default_sector_id': self.id},
        }

    def action_calibrate(self):
        """Ouvre l'assistant de calibrage sur le portefeuille du cabinet."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Calibrer les normes de %s") % self.name,
            'res_model': 'fa.calibrate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sector_id': self.id},
        }

    def action_duplicate_norms(self):
        """Ouvre l'assistant de copie des normes depuis un autre secteur."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Copier les normes d'un autre secteur"),
            'res_model': 'fa.sector.norm.copy',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_target_sector_id': self.id},
        }


class FaSectorNorm(models.Model):
    """Seuils d'appréciation d'un ratio propres à un secteur d'activité.

    Lorsqu'une norme sectorielle existe pour un ratio, elle se substitue aux
    seuils génériques définis sur le ratio lui-même.
    """
    _name = 'fa.sector.norm'
    _description = "Norme sectorielle d'un ratio"
    _order = 'sector_id, ratio_family, ratio_id'
    _rec_name = 'ratio_id'

    sector_id = fields.Many2one(
        'fa.sector', string="Secteur", required=True, ondelete='cascade', index=True)
    ratio_id = fields.Many2one(
        'fa.ratio', string="Ratio", required=True, ondelete='cascade', index=True)
    ratio_code = fields.Char(related='ratio_id.code', store=True, string="Code")
    ratio_family = fields.Selection(related='ratio_id.family', store=True, string="Famille")
    unit = fields.Selection(related='ratio_id.unit', string="Unité")
    direction = fields.Selection(related='ratio_id.direction', string="Sens")

    threshold_bad = fields.Float(string="Seuil critique")
    threshold_watch = fields.Float(string="Seuil de vigilance")
    threshold_good = fields.Float(string="Seuil de confort")
    threshold_max = fields.Float(string="Borne haute")

    norm_label = fields.Char(
        string="Norme affichée", translate=True,
        help="Texte repris dans les tableaux et le rapport, ex. « > 25 % (négoce) ».")

    sector_median = fields.Float(
        string="Médiane de référence",
        help="Valeur de référence du secteur. Renseignez-la à partir de votre "
             "propre portefeuille de dossiers (bouton « Calibrer sur mon "
             "portefeuille ») pour disposer d'un repère réellement local.")

    source = fields.Selection([
        ('default', "Référence professionnelle générale"),
        ('portfolio', "Calibré sur le portefeuille du cabinet"),
        ('study', "Étude ou statistique sectorielle"),
        ('expert', "Jugement d'expert du cabinet"),
    ], string="Origine du seuil", default='default', required=True,
        help="Trace l'origine du seuil. Les valeurs livrées avec le module sont "
             "des références professionnelles générales, ajustées au contexte "
             "malgache par appréciation, et non des statistiques officielles.")

    source_note = fields.Char(
        string="Référence de la source",
        help="Ex. « INSTAT, enquête entreprises 2005 », « calibrage 12 dossiers "
             "négoce Analamanga 2024-2026 ».")

    sample_size = fields.Integer(
        string="Taille de l'échantillon",
        help="Nombre de dossiers ayant servi au calibrage. En dessous de 5, la "
             "médiane n'est qu'indicative.")

    last_calibration = fields.Date(string="Dernier calibrage")

    comment = fields.Text(
        string="Précision sectorielle", translate=True,
        help="Nuance ajoutée au commentaire généré, ex. « en négoce, un stock de "
             "60 jours reste acceptable compte tenu des délais d'importation ».")

    active = fields.Boolean(string="Actif", default=True)

    _sql_constraints = [
        ('sector_ratio_uniq', 'unique(sector_id, ratio_id)',
         "Une seule norme par ratio et par secteur."),
    ]

    def name_get(self):
        return [(n.id, "%s / %s" % (n.sector_id.name, n.ratio_id.code)) for n in self]


class FaSectorNormCopy(models.TransientModel):
    """Assistant : recopier le jeu de normes d'un secteur vers un autre."""
    _name = 'fa.sector.norm.copy'
    _description = "Copie de normes sectorielles"

    source_sector_id = fields.Many2one('fa.sector', string="Secteur source", required=True)
    target_sector_id = fields.Many2one('fa.sector', string="Secteur cible", required=True)
    overwrite = fields.Boolean(
        string="Écraser les normes existantes", default=False,
        help="Si décoché, seules les normes absentes du secteur cible sont créées.")

    def action_copy(self):
        self.ensure_one()
        Norm = self.env['fa.sector.norm']
        existing = {
            n.ratio_id.id: n
            for n in Norm.search([('sector_id', '=', self.target_sector_id.id)])
        }
        created = updated = 0
        for src in self.source_sector_id.norm_ids:
            vals = {
                'sector_id': self.target_sector_id.id,
                'ratio_id': src.ratio_id.id,
                'threshold_bad': src.threshold_bad,
                'threshold_watch': src.threshold_watch,
                'threshold_good': src.threshold_good,
                'threshold_max': src.threshold_max,
                'norm_label': src.norm_label,
                'sector_median': src.sector_median,
                'comment': src.comment,
            }
            if src.ratio_id.id in existing:
                if self.overwrite:
                    existing[src.ratio_id.id].write(vals)
                    updated += 1
            else:
                Norm.create(vals)
                created += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Normes copiées"),
                'message': _("%(c)s créée(s), %(u)s mise(s) à jour.",
                             c=created, u=updated),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
