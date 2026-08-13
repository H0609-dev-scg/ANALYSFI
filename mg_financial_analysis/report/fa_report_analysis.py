# -*- coding: utf-8 -*-
from odoo import models, api


class FaReportAnalysis(models.AbstractModel):
    _name = 'report.mg_financial_analysis.report_fa_statement'
    _description = "Rapport d'analyse financière"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['fa.statement'].browse(docids)
        FAMILIES = dict(self.env['fa.ratio']._fields['family'].selection)
        APPR = {
            'bad': ("Critique", "table-danger"),
            'watch': ("À surveiller", "table-warning"),
            'ok': ("Correct", "table-info"),
            'good': ("Solide", "table-success"),
        }

        def grouped_ratios(stmt):
            """Regroupe les ratios par famille pour l'affichage."""
            out = []
            for key, label in self.env['fa.ratio']._fields['family'].selection:
                lines = stmt.ratio_result_ids.filtered(lambda r, k=key: r.family == k)
                if lines:
                    out.append({
                        'label': label,
                        'lines': lines.sorted('sequence'),
                        'nb_bad': len(lines.filtered(lambda r: r.appreciation == 'bad')),
                        'nb_watch': len(lines.filtered(lambda r: r.appreciation == 'watch')),
                        'nb_good': len(lines.filtered(lambda r: r.appreciation == 'good')),
                    })
            return out

        def agg(stmt, category):
            return stmt.aggregate_ids.filtered(lambda a, c=category: a.category == c).sorted('sequence')

        def line_val(stmt, code):
            ln = stmt.line_ids.filtered(lambda l, c=code: l.code == c)
            return ln[:1].amount_net or 0.0

        return {
            'doc_ids': docids,
            'doc_model': 'fa.statement',
            'docs': docs,
            'families': FAMILIES,
            'appr': APPR,
            'grouped_ratios': grouped_ratios,
            'agg': agg,
            'line_val': line_val,
            'synthesis': lambda s: s.get_synthesis(),
        }
