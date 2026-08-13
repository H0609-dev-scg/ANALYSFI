# -*- coding: utf-8 -*-
"""Rechargement du référentiel livré avec le module.

Les fichiers de données sont marqués ``noupdate="1"`` afin que vos
personnalisations — seuils ajustés, textes réécrits, normes sectorielles
calibrées sur votre portefeuille — survivent aux mises à jour du module.

La contrepartie est qu'une correction apportée au référentiel livré n'est pas
reprise automatiquement. Cet assistant permet de la récupérer, en choisissant
précisément ce qui doit être écrasé.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import convert_file
from odoo.modules import get_module_path

import logging
import os

_logger = logging.getLogger(__name__)


class FaReloadData(models.TransientModel):
    _name = 'fa.reload.data'
    _description = "Recharger le référentiel livré"

    scope = fields.Selection([
        ('ratios', "Ratios : formules, seuils et documentation"),
        ('rules', "Règles de commentaire et de recommandation"),
        ('sectors', "Secteurs et normes sectorielles"),
        ('rubrics', "Rubriques des états financiers"),
        ('all', "Tout le référentiel"),
    ], string="Éléments à recharger", default='ratios', required=True)

    keep_thresholds = fields.Boolean(
        string="Conserver mes seuils personnalisés", default=False,
        help="Préserve les seuils que vous avez modifiés et ne recharge que les "
             "formules, libellés et textes de documentation. À décocher pour "
             "récupérer les seuils corrigés livrés avec la mise à jour.")

    keep_manual_texts = fields.Boolean(
        string="Conserver mes textes réécrits", default=True,
        help="Les commentaires et recommandations que vous avez personnalisés "
             "sur les résultats d'analyse ne sont jamais touchés. Cette option "
             "concerne les modèles de texte du référentiel.")

    preview = fields.Text(string="Ce qui va changer", readonly=True)
    state = fields.Selection([('draft', "Paramétrage"), ('preview', "Aperçu")],
                             default='draft')

    FILES = {
        'ratios': ['data/fa_ratio_data.xml'],
        'rules': ['data/fa_comment_rule_data.xml'],
        'sectors': ['data/fa_sector_data.xml'],
        'rubrics': ['data/fa_rubric_data.xml'],
    }

    def _files_to_load(self):
        self.ensure_one()
        if self.scope == 'all':
            # L'ordre importe : les normes référencent les ratios
            return (self.FILES['rubrics'] + self.FILES['ratios']
                    + self.FILES['rules'] + self.FILES['sectors'])
        return self.FILES[self.scope]

    def action_preview(self):
        """Compare le référentiel en base au contenu des fichiers livrés."""
        self.ensure_one()
        import xml.etree.ElementTree as ET

        base = get_module_path('mg_financial_analysis')
        lines = []
        for rel in self._files_to_load():
            path = os.path.join(base, rel)
            if not os.path.exists(path):
                continue
            root = ET.parse(path).getroot()
            for rec in root.iter('record'):
                model = rec.get('model')
                xmlid = rec.get('id')
                if model != 'fa.ratio':
                    continue
                current = self.env.ref('mg_financial_analysis.%s' % xmlid,
                                       raise_if_not_found=False)
                if not current:
                    lines.append(_("NOUVEAU  %s") % xmlid)
                    continue
                changes = []
                for field in ('norm_label', 'formula', 'applicability',
                              'threshold_watch', 'threshold_good', 'threshold_bad'):
                    node = rec.find("field[@name='%s']" % field)
                    if node is None:
                        continue
                    new = node.text
                    old = current[field]
                    if field.startswith('threshold'):
                        try:
                            if abs(float(new or 0) - float(old or 0)) < 0.001:
                                continue
                        except (TypeError, ValueError):
                            continue
                    elif (new or '') == (old or ''):
                        continue
                    changes.append("%s : %s -> %s" % (field, old, new))
                if changes:
                    lines.append("%-6s %s" % (current.code, " | ".join(changes)))

        if not lines:
            summary = _("Le référentiel en base est déjà identique aux fichiers "
                        "livrés : aucun rechargement nécessaire.")
        else:
            summary = _(
                "%(n)s élément(s) diffèrent entre la base et les fichiers livrés :\n\n%(d)s",
                n=len(lines), d="\n".join(lines[:60]))
            if len(lines) > 60:
                summary += _("\n\n… et %s autres.") % (len(lines) - 60)

        self.write({'preview': summary, 'state': 'preview'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fa.reload.data',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reload(self):
        """Recharge les fichiers en forçant la mise à jour des enregistrements."""
        self.ensure_one()
        if not self.env.user.has_group('mg_financial_analysis.group_fa_manager'):
            raise UserError(_("Seul un manager peut recharger le référentiel."))

        base = get_module_path('mg_financial_analysis')
        saved = {}
        if self.keep_thresholds:
            saved = {
                r.id: {
                    'threshold_bad': r.threshold_bad,
                    'threshold_watch': r.threshold_watch,
                    'threshold_good': r.threshold_good,
                    'threshold_max': r.threshold_max,
                    'norm_label': r.norm_label,
                }
                for r in self.env['fa.ratio'].search([])
            }

        loaded = []
        for rel in self._files_to_load():
            path = os.path.join(base, rel)
            if not os.path.exists(path):
                continue
            # mode 'init' force la réécriture malgré noupdate="1"
            convert_file(
                self.env.cr, 'mg_financial_analysis', rel, {},
                mode='init', noupdate=False, kind='data')
            loaded.append(rel)
            _logger.info("Référentiel rechargé : %s", rel)

        if saved:
            for ratio in self.env['fa.ratio'].browse(list(saved)).exists():
                ratio.write(saved[ratio.id])

        self.env['ir.ui.view'].clear_caches()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Référentiel rechargé"),
                'message': _(
                    "%(n)s fichier(s) rechargé(s). Relancez l'analyse de vos "
                    "périodes pour appliquer les nouveaux seuils et commentaires.",
                    n=len(loaded)),
                'type': 'success',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
