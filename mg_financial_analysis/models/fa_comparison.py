# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FaComparison(models.Model):
    """Comparatif portant sur N périodes, de durées éventuellement inégales.

    Exemple type : Exercice 2024 (12 mois), Exercice 2025 (12 mois) et
    Semestre 1 2026 (6 mois). Les flux du semestre sont annualisés pour
    permettre une lecture homogène de la tendance.
    """
    _name = 'fa.comparison'
    _description = "Comparatif multi-périodes"
    _order = 'create_date desc'

    name = fields.Char(string="Libellé", required=True)
    analysis_id = fields.Many2one(
        'fa.analysis', string="Dossier", required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='analysis_id.currency_id', store=True)
    partner_id = fields.Many2one(related='analysis_id.partner_id', store=True)
    sector_id = fields.Many2one(related='analysis_id.sector_id', store=True)

    statement_ids = fields.Many2many(
        'fa.statement', 'fa_comparison_statement_rel', 'comparison_id', 'statement_id',
        string="Périodes comparées",
        domain="[('analysis_id', '=', analysis_id)]",
        help="Sélectionnez deux périodes ou plus. Elles sont classées par date de clôture.")
    statement_count = fields.Integer(string="Nb périodes", compute='_compute_counts', store=True)

    mode = fields.Selection([
        ('annualized', "Annualisation des flux (base 12 mois)"),
        ('raw', "Valeurs brutes (aucun ajustement)"),
    ], string="Mode de comparaison", default='annualized', required=True,
        help="L'annualisation ramène les flux d'une période infra-annuelle à douze mois, "
             "ce qui rend un semestre comparable à un exercice complet. "
             "Les postes de bilan ne sont jamais annualisés.")

    show_vertical = fields.Boolean(
        string="Analyse verticale", default=True,
        help="Exprime chaque poste en pourcentage du total (bilan) ou du chiffre "
             "d'affaires (résultat). Neutralise l'effet de taille et de durée.")

    line_ids = fields.One2many('fa.comparison.line', 'comparison_id', string="Lignes")
    aggregate_line_ids = fields.One2many(
        'fa.comparison.line', 'comparison_id', string="Agrégats comparés",
        domain=[('line_kind', '=', 'aggregate')])
    ratio_line_ids = fields.One2many(
        'fa.comparison.line', 'comparison_id', string="Ratios comparés",
        domain=[('line_kind', '=', 'ratio')])

    # Libellés de colonnes, pour l'affichage dynamique
    col1_label = fields.Char(string="Période 1", compute='_compute_counts', store=True)
    col2_label = fields.Char(string="Période 2", compute='_compute_counts', store=True)
    col3_label = fields.Char(string="Période 3", compute='_compute_counts', store=True)
    col4_label = fields.Char(string="Période 4", compute='_compute_counts', store=True)
    col5_label = fields.Char(string="Période 5", compute='_compute_counts', store=True)

    methodology_note = fields.Text(
        string="Réserve méthodologique", compute='_compute_note', store=True)

    @api.depends('statement_ids', 'statement_ids.name', 'statement_ids.duration_months')
    def _compute_counts(self):
        for rec in self:
            stmts = rec._sorted_statements()
            rec.statement_count = len(stmts)
            for i in range(5):
                label = False
                if i < len(stmts):
                    s = stmts[i]
                    label = s.name
                    if s.duration_months != 12:
                        label = "%s (%s m.)" % (s.name, s.duration_months)
                rec['col%d_label' % (i + 1)] = label

    def _sorted_statements(self):
        """Périodes triées par date de clôture croissante (la plus ancienne d'abord)."""
        self.ensure_one()
        return self.statement_ids.sorted(lambda s: (s.date_to or fields.Date.today()))

    @api.depends('statement_ids', 'mode')
    def _compute_note(self):
        for rec in self:
            notes = []
            stmts = rec._sorted_statements()
            durations = set(stmts.mapped('duration_months'))
            if len(durations) > 1 and rec.mode == 'annualized':
                short = stmts.filtered(lambda s: s.duration_months != 12)
                notes.append(_(
                    "Les périodes comparées sont de durées inégales. Les flux du compte "
                    "de résultat des périodes infra-annuelles (%(list)s) ont été annualisés, "
                    "c'est-à-dire ramenés à douze mois. Cette extrapolation suppose une "
                    "activité régulière sur l'année : en cas de saisonnalité marquée, la "
                    "tendance doit être interprétée avec prudence. Les postes de bilan, "
                    "qui sont des soldes à une date donnée, ne sont jamais annualisés.",
                    list=", ".join("%s : %s mois" % (s.name, s.duration_months) for s in short)))
            elif len(durations) > 1:
                notes.append(_(
                    "Attention : les périodes comparées sont de durées inégales et le mode "
                    "« valeurs brutes » est actif. Les flux ne sont donc pas directement "
                    "comparables entre eux."))
            for stmt in stmts:
                if not stmt.is_audited:
                    notes.append(_("Les états de la période « %s » ne sont pas audités.") % stmt.name)
                if stmt.seasonality_note:
                    notes.append("%s : %s" % (stmt.name, stmt.seasonality_note))
            rec.methodology_note = "\n\n".join(notes) if notes else False

    @api.onchange('analysis_id')
    def _onchange_analysis(self):
        """Pré-sélectionne toutes les périodes du dossier."""
        if self.analysis_id:
            self.statement_ids = [(6, 0, self.analysis_id.statement_ids.ids)]

    # ------------------------------------------------------------------
    def action_compute(self):
        """Construit le tableau comparatif sur N périodes."""
        Line = self.env['fa.comparison.line']
        for rec in self:
            rec.line_ids.unlink()
            stmts = rec._sorted_statements()
            if len(stmts) < 2:
                raise UserError(_(
                    "Sélectionnez au moins deux périodes à comparer."))
            if len(stmts) > 5:
                raise UserError(_(
                    "Le comparatif est limité à cinq périodes. "
                    "Vous en avez sélectionné %s.") % len(stmts))

            for stmt in stmts:
                if stmt.state != 'analyzed':
                    stmt.action_analyze()

            use_ann = rec.mode == 'annualized'
            ref = stmts[-1]          # période la plus récente : porte l'appréciation
            base = stmts[0]          # période la plus ancienne : base d'évolution
            vals = []
            seq = 0

            # ---------- Agrégats ----------
            maps = [{a.code: a for a in s.aggregate_ids} for s in stmts]
            for agg in ref.aggregate_ids.sorted('sequence'):
                seq += 10
                row = {
                    'comparison_id': rec.id,
                    'line_kind': 'aggregate',
                    'sequence': seq,
                    'code': agg.code,
                    'name': agg.name,
                    'category': agg.category,
                    'category_label': dict(
                        self.env['fa.aggregate']._fields['category'].selection).get(agg.category, ''),
                    'agg_unit': agg.unit,
                }
                for i in range(len(stmts)):
                    a = maps[i].get(agg.code)
                    v = 0.0
                    if a:
                        v = a.amount_annualized if use_ann else a.amount
                    row['value%d' % (i + 1)] = v
                vals.append(row)

            # ---------- Ratios ----------
            rmaps = [{r.code: r for r in s.ratio_result_ids} for s in stmts]
            fam_sel = dict(self.env['fa.ratio']._fields['family'].selection)
            for res in ref.ratio_result_ids.sorted(lambda r: (r.family or '', r.sequence)):
                seq += 10
                row = {
                    'comparison_id': rec.id,
                    'line_kind': 'ratio',
                    'sequence': seq,
                    'code': res.code,
                    'name': res.name,
                    'category': res.family,
                    'category_label': fam_sel.get(res.family, ''),
                    'unit': res.unit,
                    'norm_label': res.norm_applied or res.norm_label,
                    'appreciation': res.appreciation,
                    'comment': res.comment,
                    'recommendation': res.recommendation,
                    'sector_median': res.sector_median,
                    'interpretation': res.interpretation,
                    'formula_text': res.formula,
                    'threshold_rationale': res.threshold_rationale,
                    'limits': res.limits,
                    'threshold_summary': res.threshold_summary,
                    'hide_in_report': res.hide_in_report,
                    'priority_final': res.priority_final,
                }
                for i in range(len(stmts)):
                    r = rmaps[i].get(res.code)
                    row['value%d' % (i + 1)] = (r.value if (r and not r.is_na) else 0.0)
                vals.append(row)

            if vals:
                Line.create(vals)
            rec._compute_trend_comments(stmts)
        return True

    def _compute_trend_comments(self, stmts):
        """Rédige le commentaire de tendance sur l'ensemble de la série."""
        self.ensure_one()
        n = len(stmts)
        # Un seul accès au référentiel, indexé par code : évite une requête par ligne
        directions = {
            r['code']: r['direction']
            for r in self.env['fa.ratio'].search_read([], ['code', 'direction'])
        }
        for line in self.line_ids:
            series = [line['value%d' % (i + 1)] for i in range(n)]
            first, last = series[0], series[-1]
            if line.line_kind == 'ratio':
                direction = directions.get(line.code, 'higher')
            else:
                direction = 'higher'

            # Monotonie de la série
            increasing = all(series[i] <= series[i + 1] for i in range(n - 1))
            decreasing = all(series[i] >= series[i + 1] for i in range(n - 1))
            delta = last - first
            pct = (delta / abs(first) * 100.0) if first else 0.0

            if abs(pct) < 2:
                shape = _("Tendance stable sur les %s périodes.") % n
            elif increasing:
                shape = _("Progression continue sur les %s périodes (%+.1f %% au total).") % (n, pct)
            elif decreasing:
                shape = _("Dégradation continue sur les %s périodes (%+.1f %% au total).") % (n, pct)
            else:
                peak = max(series)
                trough = min(series)
                if series.index(peak) not in (0, n - 1):
                    shape = _("Évolution non linéaire : point haut en période %(p)s, "
                              "puis inflexion (%(pct)+.1f %% entre la première et la "
                              "dernière période).",
                              p=series.index(peak) + 1, pct=pct)
                elif series.index(trough) not in (0, n - 1):
                    shape = _("Évolution en creux : point bas en période %(p)s, "
                              "puis redressement (%(pct)+.1f %% au total).",
                              p=series.index(trough) + 1, pct=pct)
                else:
                    shape = _("Évolution irrégulière (%+.1f %% entre la première et la "
                              "dernière période).") % pct

            if abs(pct) >= 2 and line.line_kind == 'ratio':
                if direction == 'higher':
                    judge = _("Orientation favorable.") if delta > 0 else _("Orientation défavorable.")
                elif direction == 'lower':
                    judge = _("Orientation favorable.") if delta < 0 else _("Orientation défavorable.")
                else:
                    judge = ''
                shape = ("%s %s" % (shape, judge)).strip()

            line.trend_comment = shape

    def _get_report_synthesis(self):
        """Synthèse du comparatif : forces, faiblesses, tendances, recommandations."""
        self.ensure_one()
        ratios = self.ratio_line_ids
        n = self.statement_count or 2

        def total_pct(line):
            first = line.value1
            last = line['value%d' % min(n, 5)]
            return ((last - first) / abs(first) * 100.0) if first else 0.0

        ratios = ratios.filtered(lambda l: not l.hide_in_report)
        strengths = ratios.filtered(lambda l: l.appreciation == 'good')
        weaknesses = ratios.filtered(lambda l: l.appreciation in ('bad', 'watch'))

        # Dégradations les plus marquées, tous sens de lecture confondus
        directions = {
            r['code']: r['direction']
            for r in self.env['fa.ratio'].search_read([], ['code', 'direction'])
        }
        degraded, improved = [], []
        for line in ratios:
            direction = directions.get(line.code)
            if not direction:
                continue
            pct = total_pct(line)
            if abs(pct) < 5:
                continue
            unfavourable = ((direction == 'higher' and pct < 0)
                            or (direction == 'lower' and pct > 0))
            (degraded if unfavourable else improved).append((abs(pct), line))
        degraded.sort(key=lambda t: t[0], reverse=True)
        improved.sort(key=lambda t: t[0], reverse=True)

        scope = self.analysis_id.report_reco_scope
        recos = ratios.filtered(lambda l: l.recommendation and not l.hide_in_report)
        if scope == 'critical':
            recos = recos.filtered(lambda l: l.appreciation == 'bad')
        elif scope == 'alerts':
            recos = recos.filtered(lambda l: l.appreciation in ('bad', 'watch'))
        recos = recos.sorted(
            key=lambda l: (l.priority_final or '2',
                           0 if l.appreciation == 'bad' else 1))

        return {
            'strengths': strengths[:6],
            'weaknesses': weaknesses.sorted(
                key=lambda l: 0 if l.appreciation == 'bad' else 1)[:8],
            'degraded': [l for _p, l in degraded[:6]],
            'improved': [l for _p, l in improved[:5]],
            'recommendations': recos[:12],
            'nb_bad': len(ratios.filtered(lambda l: l.appreciation == 'bad')),
            'nb_watch': len(ratios.filtered(lambda l: l.appreciation == 'watch')),
            'nb_ok': len(ratios.filtered(lambda l: l.appreciation == 'ok')),
            'nb_good': len(strengths),
        }

    def action_print_report(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_compute()
        return self.env.ref(
            'mg_financial_analysis.action_report_fa_comparison').report_action(self)

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Détail du comparatif"),
            'res_model': 'fa.comparison.line',
            'view_mode': 'tree,pivot,graph',
            'domain': [('comparison_id', '=', self.id)],
        }


class FaComparisonLine(models.Model):
    _name = 'fa.comparison.line'
    _description = "Ligne de comparatif multi-périodes"
    _order = 'comparison_id, sequence, id'

    comparison_id = fields.Many2one(
        'fa.comparison', string="Comparatif", required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='comparison_id.currency_id', store=True)
    sequence = fields.Integer(string="Séquence")

    line_kind = fields.Selection([
        ('aggregate', "Agrégat"),
        ('ratio', "Ratio"),
    ], string="Nature", required=True, index=True)

    code = fields.Char(string="Code")
    name = fields.Char(string="Libellé", required=True)
    category = fields.Char(string="Catégorie")
    category_label = fields.Char(string="Rubrique")
    unit = fields.Char(string="Unité")
    agg_unit = fields.Char(
        string="Unité de l'agrégat",
        help="amount, percent ou days : pilote la mise en forme dans les rapports.")
    norm_label = fields.Char(string="Norme")
    sector_median = fields.Float(string="Médiane secteur", digits=(16, 4), group_operator=False)
    interpretation = fields.Text(
        string="Ce que mesure le ratio",
        help="Explication pédagogique du ratio, reprise du référentiel.")
    formula_text = fields.Char(string="Formule de calcul")
    threshold_rationale = fields.Text(string="Justification des seuils")
    limits = fields.Text(string="Limites d'interprétation")
    threshold_summary = fields.Char(string="Grille de lecture")
    hide_in_report = fields.Boolean(string="Masqué dans le rapport")
    priority_final = fields.Selection([
        ('1', "Haute"), ('2', "Moyenne"), ('3', "Basse"),
    ], string="Priorité")

    # Cinq colonnes de valeurs : couvre jusqu'à cinq périodes
    value1 = fields.Float(string="Période 1", digits=(16, 4), group_operator=False)
    value2 = fields.Float(string="Période 2", digits=(16, 4), group_operator=False)
    value3 = fields.Float(string="Période 3", digits=(16, 4), group_operator=False)
    value4 = fields.Float(string="Période 4", digits=(16, 4), group_operator=False)
    value5 = fields.Float(string="Période 5", digits=(16, 4), group_operator=False)

    variation = fields.Float(
        string="Évolution totale", digits=(16, 4), compute='_compute_var',
        store=True, group_operator=False,
        help="Écart entre la première et la dernière période de la série.")
    variation_pct = fields.Float(
        string="Évol. %", digits=(16, 2), compute='_compute_var',
        store=True, group_operator=False)
    trend = fields.Selection([
        ('up', "En hausse"),
        ('down', "En baisse"),
        ('stable', "Stable"),
    ], string="Tendance", compute='_compute_var', store=True)

    appreciation = fields.Selection([
        ('bad', "Critique"), ('watch', "À surveiller"),
        ('ok', "Correct"), ('good', "Solide"),
    ], string="Appréciation (dernière période)")

    comment = fields.Text(string="Commentaire")
    recommendation = fields.Text(string="Recommandation")
    trend_comment = fields.Text(
        string="Analyse de la tendance",
        help="Lecture de l'évolution sur l'ensemble des périodes comparées.")

    @api.depends('value1', 'value2', 'value3', 'value4', 'value5',
                 'comparison_id.statement_count')
    def _compute_var(self):
        for rec in self:
            n = rec.comparison_id.statement_count or 2
            first = rec.value1
            last = rec['value%d' % min(n, 5)]
            rec.variation = last - first
            rec.variation_pct = (rec.variation / abs(first) * 100.0) if first else 0.0
            if rec.variation > abs(first) * 0.02:
                rec.trend = 'up'
            elif rec.variation < -abs(first) * 0.02:
                rec.trend = 'down'
            else:
                rec.trend = 'stable'
