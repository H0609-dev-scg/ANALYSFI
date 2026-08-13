# -*- coding: utf-8 -*-
from odoo import models, api, _


class FaReportComparison(models.AbstractModel):
    """Rapport d'analyse portant sur plusieurs périodes en colonnes."""
    _name = 'report.mg_financial_analysis.report_fa_comparison'
    _description = "Rapport d'analyse financière multi-périodes"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['fa.comparison'].browse(docids)
        fam_sel = self.env['fa.ratio']._fields['family'].selection
        appr = {
            'bad': ("Critique", "#F8D7DA", "#842029"),
            'watch': ("À surveiller", "#FFF3CD", "#664D03"),
            'ok': ("Correct", "#CFE2FF", "#084298"),
            'good': ("Solide", "#D1E7DD", "#0F5132"),
        }

        def periods(comp):
            return comp._sorted_statements()

        def fmt(value, unit):
            return self.env['fa.statement']._fmt(value, unit or 'amount')

        def be_fmt(line, index):
            """Met en forme une valeur d'agrégat selon son unité."""
            value = line['value%d' % index]
            unit = line.agg_unit or 'amount'
            if unit == 'percent':
                return "%.2f %%" % (value * 100.0)
            if unit == 'days':
                return "%.0f j" % value
            return '{:,.0f}'.format(value).replace(',', '\u202f')

        def agg_lines(comp, category):
            return comp.aggregate_line_ids.filtered(
                lambda l, c=category: l.category == c).sorted('sequence')

        def ratio_families(comp):
            out = []
            for key, label in fam_sel:
                lines = comp.ratio_line_ids.filtered(lambda l, k=key: l.category == k)
                if lines:
                    out.append({
                        'label': label,
                        'lines': lines.sorted('sequence'),
                        'nb_bad': len(lines.filtered(lambda l: l.appreciation == 'bad')),
                        'nb_watch': len(lines.filtered(lambda l: l.appreciation == 'watch')),
                        'nb_good': len(lines.filtered(lambda l: l.appreciation == 'good')),
                    })
            return out

        def sparkline(comp, line):
            """Micro-graphique SVG en barres, tracé pour une ligne du comparatif."""
            n = comp.statement_count or 2
            vals = [line['value%d' % (i + 1)] for i in range(min(n, 5))]
            if not vals or all(v == 0 for v in vals):
                return ''
            lo, hi = min(vals), max(vals)
            span = (hi - lo) or (abs(hi) or 1.0)
            w, h, gap = 46, 16, 3
            bw = (w - gap * (len(vals) - 1)) / len(vals)
            zero_y = h if lo >= 0 else (h * hi / span if hi > 0 else 0)
            bars = []
            for i, v in enumerate(vals):
                ratio = (v - lo) / span if span else 0.5
                bh = max(1.5, ratio * (h - 2) + 1)
                x = i * (bw + gap)
                y = h - bh
                colour = '#0F5132' if i == len(vals) - 1 else '#9EC5AB'
                if len(vals) > 1 and vals[-1] < vals[0]:
                    colour = '#842029' if i == len(vals) - 1 else '#E4A9AE'
                bars.append(
                    '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" rx="0.8"/>'
                    % (x, y, bw, bh, colour))
            return ('<svg width="%d" height="%d" viewBox="0 0 %d %d" '
                    'xmlns="http://www.w3.org/2000/svg">%s</svg>'
                    % (w, h, w, h, ''.join(bars)))

        def bar_chart(comp, codes, title):
            """Histogramme groupé pour quelques agrégats clés."""
            n = comp.statement_count or 2
            lines = [l for c in codes
                     for l in comp.aggregate_line_ids.filtered(lambda x, cc=c: x.code == cc)]
            if not lines:
                return ''
            allv = [l['value%d' % (i + 1)] for l in lines for i in range(min(n, 5))]
            hi = max(allv + [0])
            lo = min(allv + [0])
            span = (hi - lo) or 1.0
            W, H = 520, 150
            pad_l, pad_b, pad_t = 8, 26, 8
            gw = (W - pad_l) / len(lines)
            bw = (gw - 14) / min(n, 5)
            zero = pad_t + (H - pad_t - pad_b) * hi / span
            palette = ['#B7C9DC', '#5B7FA6', '#1F3A5F', '#0F5132', '#842029']
            svg = ['<svg width="%d" height="%d" viewBox="0 0 %d %d" '
                   'xmlns="http://www.w3.org/2000/svg">' % (W, H, W, H)]
            svg.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#adb5bd" '
                       'stroke-width="0.8"/>' % (zero, W, zero))
            for gi, l in enumerate(lines):
                for i in range(min(n, 5)):
                    v = l['value%d' % (i + 1)]
                    bh = abs(v) / span * (H - pad_t - pad_b)
                    x = pad_l + gi * gw + i * bw + 4
                    y = zero - bh if v >= 0 else zero
                    svg.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                               'fill="%s" rx="1"/>' % (x, y, bw - 1.5, bh, palette[i % 5]))
                svg.append('<text x="%.1f" y="%d" font-size="7" text-anchor="middle" '
                           'fill="#495057">%s</text>'
                           % (pad_l + gi * gw + gw / 2 - 4, H - 10,
                              (l.name or '')[:26]))
            svg.append('</svg>')
            return ''.join(svg)

        zone_labels = dict(self.env['fa.score']._fields['zone'].selection)
        model_labels = dict(self.env['fa.score']._fields['model'].selection)

        def score_rows(comp, pers):
            """Une ligne par modèle, une colonne par période."""
            rows = []
            last = pers[-1]
            for key in ('altman', 'conan', 'synthesis'):
                cells = []
                for stmt in pers:
                    sc = stmt.score_ids.filtered(lambda s, k=key: s.model == k)[:1]
                    cells.append(sc.value_display if (sc and not sc.is_na) else "N/A")
                ref = last.score_ids.filtered(lambda s, k=key: s.model == k)[:1]
                rows.append({
                    'label': model_labels.get(key, key),
                    'values': cells,
                    'zone': ref.zone if ref else False,
                    'zone_label': zone_labels.get(ref.zone, '') if ref else '',
                })
            return rows

        CF_ROWS = [
            ('CF_CAF', True), ('CF_VAR_BFR', True), ('CF_OP_NET', True),
            ('CF_ACQ', False), ('CF_INV_NET', True),
            ('CF_FIN_NET', True), ('CF_VARIATION', True),
            ('CF_OUV', False), ('CF_CLO', False), ('CF_FREE', True),
        ]

        def cashflow_rows(pers):
            """Une ligne par rubrique clé, une colonne par période."""
            rows = []
            for code, bold in CF_ROWS:
                cells, label = [], ''
                for stmt in pers:
                    line = stmt.cashflow_ids.filtered(
                        lambda c, k=code: c.method == 'indirect' and c.code == k)[:1]
                    if line:
                        label = label or line.name
                        cells.append('{:,.0f}'.format(line.amount).replace(',', '\u202f'))
                    else:
                        cells.append("—")
                if label:
                    rows.append({'label': label, 'values': cells, 'bold': bold})
            return rows

        return {
            'be_fmt': be_fmt,
            'cashflow_rows': cashflow_rows,
            'score_rows': score_rows,
            'doc_ids': docids,
            'doc_model': 'fa.comparison',
            'docs': docs,
            'periods': periods,
            'agg_lines': agg_lines,
            'ratio_families': ratio_families,
            'appr': appr,
            'fmt': fmt,
            'sparkline': sparkline,
            'bar_chart': bar_chart,
            'synthesis': lambda c: c._get_report_synthesis(),
        }
