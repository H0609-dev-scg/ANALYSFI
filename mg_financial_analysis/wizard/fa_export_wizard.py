# -*- coding: utf-8 -*-
import base64
import io

from odoo import models, fields, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class FaExportWizard(models.TransientModel):
    _name = 'fa.export.wizard'
    _description = "Export Excel de l'analyse financière"

    statement_ids = fields.Many2many('fa.statement', string="Périodes à exporter", required=True)
    include_input = fields.Boolean(string="Inclure la saisie détaillée", default=True)
    include_aggregates = fields.Boolean(string="Inclure le bilan financier et les SIG", default=True)
    include_ratios = fields.Boolean(string="Inclure les ratios et commentaires", default=True)
    include_recommendations = fields.Boolean(
        string="Inclure les recommandations", default=True,
        help="Décochez pour un export purement descriptif.")
    include_interpretation = fields.Boolean(
        string="Inclure l'explication des ratios", default=True)
    include_glossary = fields.Boolean(string="Inclure l'onglet glossaire", default=True)
    respect_hidden = fields.Boolean(
        string="Respecter les ratios masqués", default=True,
        help="Exclut de l'export les ratios que vous avez masqués au rapport.")

    file_data = fields.Binary(string="Fichier", readonly=True)
    file_name = fields.Char(string="Nom du fichier", readonly=True)
    state = fields.Selection([('config', "Configuration"), ('done', "Terminé")], default='config')

    def action_export(self):
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_("La bibliothèque xlsxwriter n'est pas disponible sur ce serveur."))
        if not self.statement_ids:
            raise UserError(_("Sélectionnez au moins une période à exporter."))

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})

        f_title = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1F3A5F'})
        f_head = wb.add_format({'bold': True, 'bg_color': '#1F3A5F', 'font_color': 'white',
                                'border': 1, 'text_wrap': True, 'valign': 'vcenter'})
        f_sub = wb.add_format({'bold': True, 'bg_color': '#E9ECEF', 'border': 1})
        f_num = wb.add_format({'num_format': '# ##0', 'border': 1})
        f_num_b = wb.add_format({'num_format': '# ##0', 'border': 1, 'bold': True,
                                 'bg_color': '#E9ECEF'})
        f_txt = wb.add_format({'border': 1, 'text_wrap': True, 'valign': 'top'})
        f_dec = wb.add_format({'num_format': '0.00', 'border': 1})
        f_bad = wb.add_format({'border': 1, 'bg_color': '#F8D7DA'})
        f_watch = wb.add_format({'border': 1, 'bg_color': '#FFF3CD'})
        f_good = wb.add_format({'border': 1, 'bg_color': '#D1E7DD'})
        appr_fmt = {'bad': f_bad, 'watch': f_watch, 'good': f_good}
        appr_lbl = {'bad': "Critique", 'watch': "À surveiller",
                    'ok': "Correct", 'good': "Solide"}

        for stmt in self.statement_ids:
            if stmt.state != 'analyzed':
                stmt.action_analyze()
            prefix = (stmt.name or 'P')[:20]

            # ----- Saisie -----
            if self.include_input:
                ws = wb.add_worksheet(("Saisie %s" % prefix)[:31])
                ws.set_column(0, 0, 12)
                ws.set_column(1, 1, 55)
                ws.set_column(2, 5, 18)
                ws.write(0, 0, "%s - %s" % (stmt.partner_id.name or '', stmt.name), f_title)
                row = 2
                for label, lines in [
                    ("BILAN - ACTIF", stmt.asset_line_ids),
                    ("BILAN - PASSIF", stmt.liability_line_ids),
                    ("COMPTE DE RÉSULTAT", stmt.pl_line_ids),
                    ("INFORMATIONS COMPLÉMENTAIRES", stmt.extra_line_ids),
                ]:
                    ws.write(row, 0, label, f_sub)
                    ws.write(row, 1, '', f_sub)
                    row += 1
                    for h, c in [("Code", 0), ("Rubrique", 1), ("Brut", 2),
                                 ("Amort.", 3), ("Net", 4), ("N-1", 5)]:
                        ws.write(row, c, h, f_head)
                    row += 1
                    for ln in lines.sorted('sequence'):
                        ws.write(row, 0, ln.code or '', f_txt)
                        ws.write(row, 1, ln.rubric_id.name or '', f_txt)
                        ws.write_number(row, 2, ln.amount_gross or 0.0, f_num)
                        ws.write_number(row, 3, ln.amount_deprec or 0.0, f_num)
                        ws.write_number(row, 4, ln.amount_net or 0.0, f_num)
                        ws.write_number(row, 5, ln.amount_previous or 0.0, f_num)
                        row += 1
                    row += 1

            # ----- Bilan financier et SIG -----
            if self.include_aggregates:
                ws = wb.add_worksheet(("Analyse %s" % prefix)[:31])
                ws.set_column(0, 0, 55)
                ws.set_column(1, 2, 20)
                ws.write(0, 0, "Bilan financier et soldes intermédiaires de gestion", f_title)
                row = 2
                cats = [('balance', "GRANDES MASSES DU BILAN FINANCIER"),
                        ('equilibrium', "ÉQUILIBRE FINANCIER"),
                        ('sig', "SOLDES INTERMÉDIAIRES DE GESTION"),
                        ('caf', "CAPACITÉ D'AUTOFINANCEMENT")]
                for cat, label in cats:
                    ws.write(row, 0, label, f_sub)
                    ws.write(row, 1, '', f_sub)
                    ws.write(row, 2, '', f_sub)
                    row += 1
                    ws.write(row, 0, "Agrégat", f_head)
                    ws.write(row, 1, "Montant période", f_head)
                    ws.write(row, 2, "Annualisé (12 mois)", f_head)
                    row += 1
                    for a in stmt.aggregate_ids.filtered(
                            lambda x, c=cat: x.category == c).sorted('sequence'):
                        ws.write(row, 0, a.name, f_txt)
                        ws.write_number(row, 1, a.amount or 0.0, f_num_b)
                        ws.write_number(row, 2, a.amount_annualized or 0.0, f_num)
                        row += 1
                    row += 1

            # ----- Ratios -----
            if self.include_ratios:
                ws = wb.add_worksheet(("Ratios %s" % prefix)[:31])
                ws.set_column(0, 0, 10)
                ws.set_column(1, 1, 40)
                ws.set_column(2, 2, 60)
                ws.set_column(3, 6, 14)
                ws.set_column(7, 7, 16)
                ws.set_column(8, 9, 65)
                ws.set_column(10, 10, 10)
                ws.write(0, 0, "Ratios, commentaires et recommandations", f_title)
                row = 2
                heads = ["Code", "Ratio"]
                if self.include_interpretation:
                    heads.append("Ce que mesure le ratio")
                heads += ["Valeur", "N-1", "Norme appliquée", "Médiane secteur",
                          "Appréciation", "Constat"]
                if self.include_recommendations:
                    heads.append("Recommandation")
                heads.append("Modifié")
                last_col = len(heads) - 1
                for c, h in enumerate(heads):
                    ws.write(row, c, h, f_head)
                row += 1
                fam_sel = dict(self.env['fa.ratio']._fields['family'].selection)
                current_fam = None
                ratio_lines = stmt.ratio_result_ids
                if self.respect_hidden:
                    ratio_lines = ratio_lines.filtered(lambda x: not x.hide_in_report)
                for r in ratio_lines.sorted(lambda x: (x.family or '', x.sequence)):
                    if r.family != current_fam:
                        current_fam = r.family
                        ws.merge_range(row, 0, row, last_col,
                                       fam_sel.get(current_fam, ''), f_sub)
                        row += 1
                    fmt = appr_fmt.get(r.appreciation, f_txt)
                    col = 0
                    ws.write(row, col, r.code or '', fmt); col += 1
                    ws.write(row, col, r.name or '', fmt); col += 1
                    if self.include_interpretation:
                        ws.write(row, col, r.interpretation or '', f_txt); col += 1
                    ws.write(row, col, r.value_display or '', fmt); col += 1
                    if r.previous_value:
                        ws.write_number(row, col, r.previous_value, f_dec)
                    else:
                        ws.write(row, col, '', fmt)
                    col += 1
                    label = r.norm_applied or r.norm_label or ''
                    if r.is_sector_norm:
                        label += ' *'
                    ws.write(row, col, label, fmt); col += 1
                    if r.sector_median:
                        ws.write_number(row, col, r.sector_median, f_dec)
                    else:
                        ws.write(row, col, '', fmt)
                    col += 1
                    ws.write(row, col, appr_lbl.get(r.appreciation, ''), fmt); col += 1
                    ws.write(row, col, r.comment or '', f_txt); col += 1
                    if self.include_recommendations:
                        ws.write(row, col, r.recommendation or '', f_txt); col += 1
                    ws.write(row, col, "Oui" if r.is_customized else '', fmt)
                    row += 1

        # ----- Comparatif si plusieurs périodes -----
        if len(self.statement_ids) > 1:
            ws = wb.add_worksheet("Comparatif")
            ws.set_column(0, 0, 50)
            ws.set_column(1, 6, 18)
            ws.write(0, 0, "Comparatif multi-périodes", f_title)
            stmts = self.statement_ids.sorted('date_to')
            row = 2
            ws.write(row, 0, "Agrégat", f_head)
            for i, s in enumerate(stmts):
                ws.write(row, i + 1, "%s (%s mois)" % (s.name, s.duration_months), f_head)
            row += 1
            codes = [(a.code, a.name) for a in stmts[-1].aggregate_ids.sorted('sequence')]
            for code, label in codes:
                ws.write(row, 0, label, f_txt)
                for i, st in enumerate(stmts):
                    a = st.aggregate_ids.filtered(lambda x, c=code: x.code == c)[:1]
                    ws.write_number(row, i + 1, a.amount_annualized if a else 0.0, f_num)
                row += 1

            # Ratios comparés sur toutes les périodes
            row += 2
            ws.write(row, 0, "RATIOS", f_sub)
            for i, st in enumerate(stmts):
                ws.write(row, i + 1, '', f_sub)
            row += 1
            ws.write(row, 0, "Ratio", f_head)
            for i, st in enumerate(stmts):
                ws.write(row, i + 1, "%s (%s m.)" % (st.name, st.duration_months), f_head)
            ws.write(row, len(stmts) + 1, "Norme appliquée", f_head)
            row += 1
            for res in stmts[-1].ratio_result_ids.sorted(lambda x: (x.family or '', x.sequence)):
                ws.write(row, 0, res.name or '', f_txt)
                for i, st in enumerate(stmts):
                    rr = st.ratio_result_ids.filtered(lambda x, c=res.code: x.code == c)[:1]
                    ws.write_number(row, i + 1, rr.value if (rr and not rr.is_na) else 0.0, f_dec)
                ws.write(row, len(stmts) + 1, res.norm_applied or '', f_txt)
                row += 1

        # ----- Onglet glossaire : définition de tous les ratios -----
        if self.include_ratios and self.include_glossary:
            ws = wb.add_worksheet("Glossaire")
            ws.set_column(0, 0, 8)
            ws.set_column(1, 1, 40)
            ws.set_column(2, 2, 34)
            ws.set_column(3, 3, 78)
            ws.set_column(4, 4, 22)
            ws.write(0, 0, "Glossaire des ratios financiers", f_title)
            row = 2
            for c, h in enumerate(["Code", "Ratio", "Formule de calcul",
                                   "Ce que mesure le ratio", "Norme de référence"]):
                ws.write(row, c, h, f_head)
            row += 1
            fam_sel = dict(self.env['fa.ratio']._fields['family'].selection)
            current = None
            for ratio in self.env['fa.ratio'].search([], order='family, sequence'):
                if ratio.family != current:
                    current = ratio.family
                    ws.merge_range(row, 0, row, 4, fam_sel.get(current, ''), f_sub)
                    row += 1
                ws.write(row, 0, ratio.code or '', f_txt)
                ws.write(row, 1, ratio.name or '', f_txt)
                ws.write(row, 2, ratio.formula or '', f_txt)
                ws.write(row, 3, ratio.interpretation or '', f_txt)
                ws.write(row, 4, ratio.norm_label or '', f_txt)
                row += 1

        wb.close()
        data = base64.b64encode(buf.getvalue())
        buf.close()

        name = "Analyse_financiere_%s.xlsx" % (
            self.statement_ids[0].partner_id.name or 'client').replace(' ', '_')
        self.write({'file_data': data, 'file_name': name, 'state': 'done'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fa.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
