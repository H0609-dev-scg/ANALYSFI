# -*- coding: utf-8 -*-
"""Lecture croisée des ratios.

Un ratio isolé ment souvent : une liquidité générale confortable peut masquer
un stock qui ne tourne pas ; un résultat net positif peut coexister avec une
trésorerie négative. Ce module relit les résultats ensemble et produit les
constats qu'un consultant formulerait en premier en réunion.
"""
from odoo import models, fields, api, _


class FaRatioInsight(models.Model):
    _name = 'fa.ratio.insight'
    _description = "Constat de lecture croisée des ratios"
    _order = 'statement_id, sequence, id'

    statement_id = fields.Many2one(
        'fa.statement', string="Période", required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(string="Code", index=True)
    kind = fields.Selection([
        ('priority', "À lire en premier"),
        ('cross', "Lecture croisée"),
        ('family', "Synthèse de famille"),
    ], string="Type", required=True, default='cross')
    family = fields.Selection([
        ('structure', "A. Structure financière et solvabilité"),
        ('liquidity', "B. Liquidité et trésorerie"),
        ('activity', "C. Activité, rotation et gestion"),
        ('profitability', "D. Rentabilité et marges"),
        ('value_added', "E. Répartition de la valeur ajoutée"),
        ('coverage', "F. Couverture et risque"),
    ], string="Famille")
    severity = fields.Selection([
        ('alert', "Point d'attention"),
        ('watch', "À nuancer"),
        ('ok', "Favorable"),
        ('info', "Lecture"),
    ], string="Niveau", default='info')
    name = fields.Char(string="Constat", required=True)
    message = fields.Text(string="Analyse")
    ratio_codes = fields.Char(string="Ratios concernés")


class FaStatementRatioInsight(models.Model):
    _inherit = 'fa.statement'

    insight_ids = fields.One2many(
        'fa.ratio.insight', 'statement_id', string="Lecture des ratios")
    insight_alert_count = fields.Integer(
        string="Constats d'attention", compute='_compute_insight_summary', store=True)

    @api.depends('insight_ids.severity')
    def _compute_insight_summary(self):
        for rec in self:
            rec.insight_alert_count = len(
                rec.insight_ids.filtered(lambda i: i.severity == 'alert'))

    def action_open_insights(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Lecture des ratios - %s") % self.name,
            'res_model': 'fa.ratio.insight',
            'view_mode': 'tree,form',
            'domain': [('statement_id', '=', self.id)],
        }

    def get_priority_insights(self):
        self.ensure_one()
        return self.insight_ids.filtered(lambda i: i.kind == 'priority')

    def get_cross_insights(self):
        self.ensure_one()
        return self.insight_ids.filtered(lambda i: i.kind == 'cross')

    def get_family_insights(self):
        self.ensure_one()
        return self.insight_ids.filtered(lambda i: i.kind == 'family')

    def _compute_ratio_insights(self):
        """Construit la lecture d'ensemble à partir des résultats de ratios."""
        self.ensure_one()
        self.insight_ids.unlink()
        by_code = {r.code: r for r in self.ratio_result_ids}
        v = self._get_values_dict(annualized=True)
        rows = []
        seq = [0]

        def add(code, kind, name, message, severity='info', family=False, ratios=''):
            seq[0] += 10
            rows.append({
                'statement_id': self.id,
                'sequence': seq[0],
                'code': code,
                'kind': kind,
                'name': name,
                'message': message,
                'severity': severity,
                'family': family or False,
                'ratio_codes': ratios,
            })

        def appr(code):
            r = by_code.get(code)
            if not r or r.is_na:
                return False
            return r.appreciation

        def val(code):
            r = by_code.get(code)
            if not r or r.is_na:
                return None
            return r.value

        def disp(code):
            r = by_code.get(code)
            return r.value_display if r else "n/a"

        # ----- Ordre de lecture : les ratios qui changent la décision -----
        ranked = self.ratio_result_ids.filtered(
            lambda r: not r.is_na and not r.hide_in_report
            and r.appreciation in ('bad', 'watch'))
        ranked = ranked.sorted(
            key=lambda r: (0 if r.appreciation == 'bad' else 1,
                           r.priority_final or '3',
                           r.sequence))
        if ranked:
            lines = []
            for r in ranked[:8]:
                lines.append(_("%(c)s %(n)s : %(v)s (%(a)s)",
                              c=r.code, n=r.name, v=r.value_display,
                              a=dict(r._fields['appreciation'].selection).get(
                                  r.appreciation, '')))
            add('READ_FIRST', 'priority',
                _("Commencer par ces indicateurs"),
                _("Avant de parcourir les cinquante ratios, tenez ces "
                  "constats : ils déterminent le diagnostic.\n%s")
                % "\n".join("• %s" % x for x in lines),
                'alert' if any(r.appreciation == 'bad' for r in ranked[:8]) else 'watch',
                ratios=", ".join(ranked[:8].mapped('code')))
        else:
            add('READ_FIRST', 'priority',
                _("Aucun point d'attention majeur"),
                _("Les ratios calculables se situent dans les normes. La lecture "
                  "peut porter sur la trajectoire et les réserves méthodologiques, "
                  "plutôt que sur un risque immédiat."),
                'ok')

        # ----- Lectures croisées -----
        tn = v.get('TN', 0.0)
        rn = v.get('RN', 0.0)
        ebe = v.get('EBE', 0.0)
        caf = v.get('CAF', 0.0)
        frng = v.get('FRNG', 0.0)
        bfr = v.get('BFR', 0.0)

        if rn > 0 and tn < 0:
            add('PROFIT_NO_CASH', 'cross',
                _("Bénéfice sans trésorerie"),
                _("Le résultat net est positif (%s) alors que la trésorerie nette "
                  "est négative (%s). L'entreprise gagne sur le papier et se "
                  "finance au jour le jour. Cherchez le besoin en fonds de "
                  "roulement (stocks, clients) et le poids des concours bancaires "
                  "avant de parler de performance.")
                % (disp('D5') if val('D5') is not None else '{:,.0f}'.format(rn),
                   disp('B6') if val('B6') is not None else '{:,.0f}'.format(tn)),
                'alert', 'liquidity', 'D5, B4, B6, C5')

        if ebe > 0 and rn < 0:
            add('EBE_VS_RN', 'cross',
                _("L'exploitation gagne, le bas de compte perd"),
                _("L'excédent brut d'exploitation est positif alors que le "
                  "résultat net est négatif. Le trou se situe après l'exploitation : "
                  "dotations, frais financiers ou impôt. Relisez D3, D5 et F1 avant "
                  "de conclure à une activité non viable."),
                'alert', 'profitability', 'D3, D5, F1')

        b1, b2, b3 = appr('B1'), appr('B2'), appr('B3')
        if b1 in ('ok', 'good') and (b2 == 'bad' or b3 == 'bad'):
            add('LIQ_STOCK', 'cross',
                _("Liquidité générale trompeuse"),
                _("La liquidité générale (B1 = %s) paraît acceptable, mais la "
                  "liquidité réduite ou immédiate est critique (B2 = %s, B3 = %s). "
                  "Ce sont les stocks, ou des créances peu liquides, qui portent "
                  "le ratio. En cas de tension, l'entreprise ne pourra pas payer "
                  "sans céder du stock à vil prix.")
                % (disp('B1'), disp('B2'), disp('B3')),
                'alert', 'liquidity', 'B1, B2, B3, C1')

        if appr('C4') in ('watch', 'bad') and tn > 0:
            add('SUPPLIER_RISK', 'cross',
                _("Crédit fournisseur long, trésorerie saine"),
                _("Le délai fournisseurs (C4 = %s) est allongé alors que la "
                  "trésorerie nette reste positive. Ce n'est pas un symptôme de "
                  "détresse de paiement : c'est un risque opérationnel de rupture "
                  "d'approvisionnement si les fournisseurs resserrent leurs "
                  "conditions.")
                % disp('C4'),
                'watch', 'activity', 'C4, B6')

        if appr('A8') in ('watch', 'bad') and v.get('DETTES_FIN', 0.0) <= 0:
            add('LEV_EXPLOIT', 'cross',
                _("Levier élevé sans dette bancaire"),
                _("Le levier financier paraît tendu (A8 = %s) alors qu'il n'y a "
                  "pas de dette financière. L'effet vient du crédit d'exploitation. "
                  "La recommandation n'est pas de recapitaliser dans l'urgence, "
                  "mais de sécuriser les délais fournisseurs.")
                % disp('A8'),
                'watch', 'structure', 'A8, A2, C4')

        if frng > 0 and bfr > frng:
            add('FR_INSUFF', 'cross',
                _("Fonds de roulement insuffisant face au BFR"),
                _("Le fonds de roulement (%s) ne couvre pas le besoin d'exploitation "
                  "(%s). L'écart est financé par la trésorerie ou les concours "
                  "bancaires. B4 et B8 disent la même chose sous un autre angle : "
                  "allonger les ressources stables ou raccourcir le cycle.")
                % ('{:,.0f}'.format(frng).replace(',', ' '),
                   '{:,.0f}'.format(bfr).replace(',', ' ')),
                'alert', 'liquidity', 'B4, B8, C5')

        if appr('D12') == 'bad' or (val('D12') is not None and val('D12') < 0):
            add('BELOW_SR', 'cross',
                _("Activité sous le seuil de rentabilité"),
                _("La marge de sécurité (D12 = %s) est négative : le chiffre "
                  "d'affaires ne couvre pas les charges de structure. Tant que "
                  "le point mort (D11 = %s) n'est pas ramené dans l'exercice, "
                  "toute discussion sur la distribution ou l'investissement "
                  "est prématurée.")
                % (disp('D12'), disp('D11')),
                'alert', 'profitability', 'D11, D12, D13, D14')

        if caf <= 0 and rn != 0:
            add('NO_CAF', 'cross',
                _("Aucune ressource interne"),
                _("La capacité d'autofinancement est nulle ou négative. Les ratios "
                  "de couverture (A4, F2, F5) n'ont plus de sens opératoire : "
                  "l'entreprise ne peut ni rembourser ni investir sur ses propres "
                  "flux. Le diagnostic se joue sur l'EBE et le BFR."),
                'alert', 'coverage', 'A4, F2, F5')

        if appr('A1') == 'bad' and appr('D7') in ('ok', 'good'):
            add('ROE_LEVERAGE', 'cross',
                _("Rentabilité des fonds propres gonflée par le levier"),
                _("L'autonomie financière est critique (A1 = %s) alors que la "
                  "rentabilité des capitaux propres paraît correcte (D7 = %s). "
                  "Le ROE est élevé parce que le dénominateur est faible, non "
                  "parce que l'activité est performante. Lisez D6 (rentabilité "
                  "économique) avant de parler de création de valeur.")
                % (disp('A1'), disp('D7')),
                'watch', 'profitability', 'A1, D6, D7')

        if appr('C1') == 'bad' and appr('D2') in ('ok', 'good'):
            add('STOCK_MARGIN', 'cross',
                _("Marge correcte, stock trop lourd"),
                _("Le taux de valeur ajoutée tient (D2 = %s) mais les stocks "
                  "s'écoulent trop lentement (C1 = %s). La rentabilité affichée "
                  "est immobilisée dans le magasin. C'est un sujet d'exploitation, "
                  "pas de prix de vente.")
                % (disp('D2'), disp('C1')),
                'watch', 'activity', 'C1, C2, D2')

        # ----- Synthèse par famille -----
        fam_sel = dict(self.env['fa.ratio']._fields['family'].selection)
        for fam_key, fam_label in self.env['fa.ratio']._fields['family'].selection:
            lines = self.ratio_result_ids.filtered(
                lambda r, k=fam_key: r.family == k and not r.is_na)
            if not lines:
                continue
            n_bad = len(lines.filtered(lambda r: r.appreciation == 'bad'))
            n_watch = len(lines.filtered(lambda r: r.appreciation == 'watch'))
            n_ok = len(lines.filtered(lambda r: r.appreciation == 'ok'))
            n_good = len(lines.filtered(lambda r: r.appreciation == 'good'))
            if n_bad >= 2:
                sev, tone = 'alert', _(
                    "La famille est dégradée : %(b)s indicateur(s) critique(s) "
                    "et %(w)s à surveiller sur %(n)s calculables.")
            elif n_bad == 1 or n_watch >= 2:
                sev, tone = 'watch', _(
                    "Lecture contrastée : %(b)s critique, %(w)s à surveiller, "
                    "%(g)s solide(s) sur %(n)s calculables.")
            elif n_good and not n_bad:
                sev, tone = 'ok', _(
                    "Famille globalement saine : %(g)s indicateur(s) solide(s), "
                    "%(o)s correct(s) sur %(n)s calculables.")
            else:
                sev, tone = 'info', _(
                    "%(g)s solide(s), %(o)s correct(s), %(w)s à surveiller "
                    "sur %(n)s calculables.")
            worst = lines.filtered(
                lambda r: r.appreciation in ('bad', 'watch')).sorted(
                key=lambda r: 0 if r.appreciation == 'bad' else 1)
            detail = ""
            if worst:
                detail = " " + _("Points à ouvrir : %s.") % ", ".join(
                    "%s (%s)" % (r.code, r.value_display) for r in worst[:4])
            add('FAM_%s' % fam_key.upper(), 'family', fam_label,
                tone % {'b': n_bad, 'w': n_watch, 'g': n_good,
                        'o': n_ok, 'n': len(lines)} + detail,
                sev, fam_key,
                ratios=", ".join(worst[:4].mapped('code')))

        if not any(r['kind'] == 'cross' for r in rows):
            add('NO_CROSS', 'cross',
                _("Pas de contradiction majeure entre familles"),
                _("Les ratios se lisent dans le même sens. Vous pouvez suivre "
                  "l'ordre des familles sans craindre qu'un indicateur « solide » "
                  "en masque un autre."),
                'ok')

        if rows:
            self.env['fa.ratio.insight'].create(rows)
        return rows
