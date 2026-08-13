# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestFaEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': "Client Test"})
        cls.sector_commerce = cls.env.ref('mg_financial_analysis.sector_commerce')
        cls.sector_industry = cls.env.ref('mg_financial_analysis.sector_industry')
        cls.analysis = cls.env['fa.analysis'].create({
            'partner_id': cls.partner.id,
            'sector_id': cls.sector_commerce.id,
        })
        cls.stmt = cls.env['fa.statement'].create({
            'name': "Exercice test",
            'analysis_id': cls.analysis.id,
            'period_type': 'annual',
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
        })

    def _set(self, code, amount):
        """Renseigne le montant net d'une rubrique."""
        rubric = self.env['fa.rubric'].search([('code', '=', code)], limit=1)
        self.assertTrue(rubric, "Rubrique %s absente du référentiel" % code)
        line = self.stmt.line_ids.filtered(lambda l: l.rubric_id == rubric)
        self.assertTrue(line, "Ligne %s non générée" % code)
        line.amount_net = amount

    def _fill_balanced(self):
        """Jeu minimal équilibré : Actif = Passif, RN cohérent."""
        # Actif : 1 000
        self._set('AC_IMMO_CORP', 400)
        self._set('AC_STOCK', 250)
        self._set('AC_CLIENT', 300)
        self._set('AC_TRESO', 50)
        # Compte de résultat
        self._set('PL_VENTE_MSE', 2000)
        self._set('PL_ACHAT_MSE', 1400)
        self._set('PL_SERV_EXT', 200)
        self._set('PL_PERSONNEL', 250)
        self._set('PL_IMPOTS_TAXES', 30)
        self._set('PL_DOTATIONS', 60)
        self._set('PL_CH_FIN', 20)
        self._set('PL_IMP_EXIG', 10)
        # RN = 2000-1400-200-250-30-60-20-10 = 30
        # Passif : 1 000
        self._set('PA_CAPITAL', 300)
        self._set('PA_RESULTAT', 30)
        self._set('PA_EMPRUNT_NC', 270)
        self._set('PA_FOURN', 400)

    # ------------------------------------------------------------------
    def test_01_lines_generated(self):
        """Les lignes de saisie sont créées automatiquement."""
        inputs = self.env['fa.rubric'].search_count([('line_type', '=', 'input')])
        self.assertEqual(len(self.stmt.line_ids), inputs)
        self.assertTrue(self.stmt.asset_line_ids)
        self.assertTrue(self.stmt.liability_line_ids)
        self.assertTrue(self.stmt.pl_line_ids)
        self.assertTrue(self.stmt.extra_line_ids)

    def test_02_duration(self):
        """La durée est déduite des dates."""
        self.assertEqual(self.stmt.duration_months, 12)
        semester = self.env['fa.statement'].create({
            'name': "S1", 'analysis_id': self.analysis.id, 'period_type': 'semester',
            'date_from': '2026-01-01', 'date_to': '2026-06-30',
        })
        self.assertEqual(semester.duration_months, 6)

    def test_03_balance_check(self):
        """Le contrôle d'équilibre détecte un bilan déséquilibré."""
        self._set('AC_STOCK', 100)
        self.assertFalse(self.stmt.is_balanced)
        with self.assertRaises(UserError):
            self.stmt.action_confirm()

    def test_04_balanced_confirm(self):
        """Un bilan équilibré et cohérent peut être validé."""
        self._fill_balanced()
        self.assertEqual(self.stmt.total_asset, 1000)
        self.assertEqual(self.stmt.total_liability, 1000)
        self.assertTrue(self.stmt.is_balanced)
        self.assertEqual(self.stmt.net_result_pl, 30)
        self.assertTrue(self.stmt.is_result_ok)
        self.stmt.action_confirm()
        self.assertEqual(self.stmt.state, 'confirmed')

    def test_05_sig(self):
        """Les soldes intermédiaires de gestion sont exacts."""
        self._fill_balanced()
        v = self.stmt._get_values_dict()
        self.assertEqual(v['MC'], 600)      # 2000 - 1400
        self.assertEqual(v['VA'], 400)      # 600 - 200
        self.assertEqual(v['EBE'], 120)     # 400 - 250 - 30
        self.assertEqual(v['REX'], 60)      # 120 - 60
        self.assertEqual(v['RF'], -20)
        self.assertEqual(v['RN'], 30)

    def test_06_equilibrium(self):
        """FRNG, BFR et trésorerie nette sont cohérents entre eux."""
        self._fill_balanced()
        v = self.stmt._get_values_dict()
        self.assertEqual(v['AI'], 400)
        self.assertEqual(v['CAPITAUX_PERMANENTS'], 600)   # CP 330 + emprunt 270
        self.assertEqual(v['FRNG'], 200)
        self.assertEqual(v['BFRE'], 150)                  # (250+300) - 400
        self.assertEqual(v['TN'], v['FRNG'] - v['BFR'])
        # Contrôle croisé : TN calculée = TN observée
        self.assertAlmostEqual(v['TN'], v['TN_CTRL'], places=2)

    def test_07_caf_two_methods(self):
        """Les deux méthodes de calcul de la CAF concordent."""
        self._fill_balanced()
        v = self.stmt._get_values_dict()
        self.assertAlmostEqual(v['CAF'], v['CAF_SOUS'], places=2)
        self.assertAlmostEqual(v['CAF_ECART'], 0.0, places=2)
        self.assertEqual(v['CAF'], 90)   # RN 30 + dotations 60

    def test_08_annualization(self):
        """Les flux d'un semestre sont doublés, les stocks inchangés."""
        semester = self.env['fa.statement'].create({
            'name': "S1", 'analysis_id': self.analysis.id, 'period_type': 'semester',
            'date_from': '2026-01-01', 'date_to': '2026-06-30',
        })
        rubric = self.env['fa.rubric'].search([('code', '=', 'PL_VENTE_MSE')], limit=1)
        semester.line_ids.filtered(lambda l: l.rubric_id == rubric).amount_net = 500
        stock = self.env['fa.rubric'].search([('code', '=', 'AC_STOCK')], limit=1)
        semester.line_ids.filtered(lambda l: l.rubric_id == stock).amount_net = 200

        raw = semester._get_values_dict(annualized=False)
        ann = semester._get_values_dict(annualized=True)
        self.assertEqual(raw['CA'], 500)
        self.assertEqual(ann['CA'], 1000)         # flux annualisé
        self.assertEqual(ann['AC_STOCK'], 200)    # stock non annualisé

    def test_09_analyze_full(self):
        """L'analyse produit agrégats et ratios sans erreur de formule."""
        self._fill_balanced()
        self.stmt.action_analyze()
        self.assertEqual(self.stmt.state, 'analyzed')
        self.assertTrue(self.stmt.aggregate_ids)
        self.assertTrue(self.stmt.ratio_result_ids)
        # Aucun ratio ne doit échouer sur une erreur de formule
        errors = self.stmt.ratio_result_ids.filtered(
            lambda r: r.is_na and r.na_reason and 'Erreur de formule' in r.na_reason)
        self.assertFalse(errors, "Formules en erreur : %s" % errors.mapped('code'))

    def test_10_ratio_values(self):
        """Contrôle manuel de quelques ratios."""
        self._fill_balanced()
        self.stmt.action_analyze()

        def val(code):
            return self.stmt.ratio_result_ids.filtered(lambda r: r.code == code).value

        # Autonomie financière = 330 / 1000 = 33 %
        self.assertAlmostEqual(val('A1'), 33.0, places=1)
        # Liquidité générale = 600 / 400 = 1,5
        self.assertAlmostEqual(val('B1'), 1.5, places=2)
        # Quick ratio = (600-250)/400 = 0,875
        self.assertAlmostEqual(val('B2'), 0.875, places=3)
        # Marge nette = 30 / 2000 = 1,5 %
        self.assertAlmostEqual(val('D5'), 1.5, places=2)
        # Taux de VA = 400 / 2000 = 20 %
        self.assertAlmostEqual(val('D2'), 20.0, places=1)

    def test_11_comments_generated(self):
        """Chaque ratio calculable reçoit un commentaire et une appréciation."""
        self._fill_balanced()
        self.stmt.action_analyze()
        calc = self.stmt.ratio_result_ids.filtered(lambda r: not r.is_na)
        self.assertTrue(calc)
        no_appr = calc.filtered(lambda r: not r.appreciation)
        self.assertFalse(no_appr, "Ratios sans appréciation : %s" % no_appr.mapped('code'))
        no_comment = calc.filtered(lambda r: not r.comment)
        self.assertFalse(no_comment, "Ratios sans commentaire : %s" % no_comment.mapped('code'))

    def test_12_manual_override(self):
        """Le commentaire du consultant prend le pas sur le texte généré."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B1')
        res.comment_manual = "Analyse personnalisée du consultant."
        self.assertEqual(res.comment, "Analyse personnalisée du consultant.")

    def test_13_no_division_by_zero(self):
        """Un dénominateur nul rend le ratio non calculable, pas une erreur."""
        self.stmt.action_analyze()   # tout à zéro
        na = self.stmt.ratio_result_ids.filtered(lambda r: r.is_na)
        self.assertTrue(na, "Les ratios devraient être non calculables sur un état vide")
        crash = self.stmt.ratio_result_ids.filtered(
            lambda r: r.na_reason and 'Erreur de formule' in r.na_reason)
        self.assertFalse(crash)

    def test_14_synthesis(self):
        """La synthèse retourne forces, faiblesses et recommandations."""
        self._fill_balanced()
        self.stmt.action_analyze()
        syn = self.stmt.get_synthesis()
        self.assertIn('strengths', syn)
        self.assertIn('weaknesses', syn)
        self.assertIn('recommendations', syn)

    def test_15_comparison(self):
        """Le comparatif se génère sur deux périodes de durées différentes."""
        self._fill_balanced()
        self.stmt.action_analyze()
        s1 = self.stmt.copy({
            'name': "S1 2026", 'period_type': 'semester',
            'date_from': '2026-01-01', 'date_to': '2026-06-30',
            'previous_statement_id': self.stmt.id,
        })
        s1.action_analyze()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id,
            'name': "Comparatif test",
            'statement_ids': [(6, 0, [self.stmt.id, s1.id])],
        })
        comp.action_compute()
        self.assertTrue(comp.line_ids)
        self.assertTrue(comp.aggregate_line_ids)
        self.assertTrue(comp.ratio_line_ids)
        self.assertTrue(comp.methodology_note, "La réserve méthodologique doit être générée")

    # ==================================================================
    # Normes sectorielles
    # ==================================================================
    def test_16_sector_thresholds(self):
        """Les seuils sectoriels se substituent aux seuils génériques."""
        ratio = self.env['fa.ratio'].search([('code', '=', 'A1')], limit=1)
        generic = ratio.get_thresholds()
        commerce = ratio.get_thresholds(self.sector_commerce)
        industry = ratio.get_thresholds(self.sector_industry)
        self.assertFalse(generic['is_sector'])
        self.assertTrue(commerce['is_sector'])
        self.assertTrue(industry['is_sector'])
        # Le négoce tolère moins de fonds propres que l'industrie
        self.assertLess(commerce['watch'], industry['watch'])

    def test_17_same_value_different_appreciation(self):
        """Une même valeur est appréciée différemment selon le secteur."""
        ratio = self.env['fa.ratio'].search([('code', '=', 'A1')], limit=1)
        value = 28.0   # 28 % de fonds propres
        appr_com = ratio._evaluate_appreciation(
            value, ratio.get_thresholds(self.sector_commerce))
        appr_ind = ratio._evaluate_appreciation(
            value, ratio.get_thresholds(self.sector_industry))
        self.assertNotEqual(
            appr_com, appr_ind,
            "28 %% de fonds propres ne peut pas être jugé identiquement "
            "en négoce et en industrie")

    def test_18_sector_norm_applied_in_analysis(self):
        """L'analyse mémorise la norme réellement appliquée."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'A1')
        self.assertTrue(res.norm_applied)
        self.assertTrue(res.is_sector_norm)
        self.assertIn('négoce', res.norm_applied.lower())

    def test_19_change_sector_changes_appreciation(self):
        """Changer le secteur du dossier modifie les appréciations."""
        self._fill_balanced()
        self.stmt.action_analyze()
        before = {r.code: r.appreciation for r in self.stmt.ratio_result_ids}
        self.analysis.sector_id = self.sector_industry
        self.stmt.action_analyze()
        after = {r.code: r.appreciation for r in self.stmt.ratio_result_ids}
        changed = [c for c in before if before[c] != after.get(c)]
        self.assertTrue(
            changed, "Le changement de secteur devrait modifier des appréciations")

    def test_20_appreciation_follows_thresholds(self):
        """L'appréciation dérive des seuils, pas de la règle de commentaire."""
        self._fill_balanced()
        self.stmt.action_analyze()
        for res in self.stmt.ratio_result_ids.filtered(lambda r: not r.is_na):
            expected = res.ratio_id._evaluate_appreciation(
                res.value, res.ratio_id.get_thresholds(self.analysis.sector_id))
            # Sauf pour les règles de cas particulier qui imposent l'appréciation
            rule = res.ratio_id.rule_ids.filtered(lambda r: r.force_appreciation)
            if not rule:
                self.assertEqual(
                    res.appreciation, expected,
                    "Ratio %s : appréciation %s incohérente avec les seuils (%s)"
                    % (res.code, res.appreciation, expected))

    # ==================================================================
    # Comparatif N périodes
    # ==================================================================
    def _make_three_periods(self):
        self._fill_balanced()
        self.stmt.write({'name': "Exercice 2024",
                         'date_from': '2024-01-01', 'date_to': '2024-12-31'})
        self.stmt.action_analyze()
        p2 = self.stmt.copy({
            'name': "Exercice 2025", 'period_type': 'annual',
            'date_from': '2025-01-01', 'date_to': '2025-12-31',
            'previous_statement_id': self.stmt.id})
        p2.action_analyze()
        p3 = self.stmt.copy({
            'name': "S1 2026", 'period_type': 'semester',
            'date_from': '2026-01-01', 'date_to': '2026-06-30',
            'previous_statement_id': p2.id})
        p3.action_analyze()
        return self.stmt, p2, p3

    def test_21_comparison_three_periods(self):
        """Le comparatif accepte trois périodes de durées inégales."""
        p1, p2, p3 = self._make_three_periods()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id,
            'name': "Comparatif 3 périodes",
            'statement_ids': [(6, 0, [p1.id, p2.id, p3.id])],
        })
        comp.action_compute()
        self.assertEqual(comp.statement_count, 3)
        self.assertTrue(comp.aggregate_line_ids)
        self.assertTrue(comp.ratio_line_ids)
        # Les trois colonnes sont alimentées
        line = comp.ratio_line_ids.filtered(lambda l: l.code == 'B1')[:1]
        self.assertTrue(line.value1)
        self.assertTrue(line.value2)
        self.assertTrue(line.value3)
        # Les libellés de colonnes reflètent l'ordre chronologique
        self.assertIn("2024", comp.col1_label)
        self.assertIn("2025", comp.col2_label)
        self.assertIn("2026", comp.col3_label)
        # La durée inégale est signalée
        self.assertIn("6 mois", comp.methodology_note)

    def test_22_comparison_trend_comment(self):
        """Chaque ligne du comparatif porte une analyse de tendance."""
        p1, p2, p3 = self._make_three_periods()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id, 'name': "Tendance",
            'statement_ids': [(6, 0, [p1.id, p2.id, p3.id])]})
        comp.action_compute()
        no_trend = comp.line_ids.filtered(lambda l: not l.trend_comment)
        self.assertFalse(no_trend, "Toutes les lignes doivent porter une tendance")

    def test_23_comparison_needs_two_periods(self):
        """Un comparatif sur une seule période est refusé."""
        self._fill_balanced()
        self.stmt.action_analyze()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id, 'name': "Insuffisant",
            'statement_ids': [(6, 0, [self.stmt.id])]})
        with self.assertRaises(UserError):
            comp.action_compute()

    def test_24_comparison_ordering(self):
        """Les périodes sont classées de la plus ancienne à la plus récente."""
        p1, p2, p3 = self._make_three_periods()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id, 'name': "Ordre",
            'statement_ids': [(6, 0, [p3.id, p1.id, p2.id])]})   # ordre mélangé
        sorted_stmts = comp._sorted_statements()
        self.assertEqual(sorted_stmts[0], p1)
        self.assertEqual(sorted_stmts[-1], p3)

    # ==================================================================
    # Édition des commentaires
    # ==================================================================
    def test_25_edit_comment_and_recommendation(self):
        """Le consultant peut modifier commentaire et recommandation."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B1')
        auto_com = res.comment_auto
        res.write({
            'comment_manual': "Commentaire du consultant.",
            'recommendation_manual': "Action spécifique décidée en réunion.",
        })
        self.assertEqual(res.comment, "Commentaire du consultant.")
        self.assertEqual(res.recommendation, "Action spécifique décidée en réunion.")
        self.assertTrue(res.is_customized)
        # Le texte généré reste conservé
        self.assertEqual(res.comment_auto, auto_com)

    def test_26_reset_comments(self):
        """La restauration rétablit les textes générés."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B1')
        res.comment_manual = "Texte personnalisé"
        self.assertTrue(res.is_customized)
        self.stmt.action_reset_comments()
        self.assertFalse(res.comment_manual)
        self.assertFalse(res.is_customized)
        self.assertEqual(res.comment, res.comment_auto)

    def test_27_copy_auto_to_manual(self):
        """Le texte généré peut servir de point de départ à l'édition."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D5')
        res.action_copy_auto_to_manual()
        self.assertEqual(res.comment_manual, res.comment_auto)
        self.assertTrue(res.is_customized)

    def test_28_custom_text_survives_reanalysis(self):
        """Les textes du consultant survivent à une nouvelle analyse."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B1')
        res.write({
            'comment_manual': "Mon analyse personnalisée.",
            'recommendation_manual': "Action décidée en comité.",
            'priority_manual': '1',
            'hide_in_report': True,
        })
        # Modification de la saisie puis relance complète
        self._set('AC_STOCK', 260)
        self._set('PA_FOURN', 410)
        self.stmt.action_analyze()
        new_res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B1')
        self.assertEqual(new_res.comment_manual, "Mon analyse personnalisée.")
        self.assertEqual(new_res.recommendation_manual, "Action décidée en comité.")
        self.assertEqual(new_res.priority_manual, '1')
        self.assertTrue(new_res.hide_in_report)
        # La valeur, elle, a bien été recalculée
        self.assertTrue(new_res.value)

    def test_29_trend_sentence(self):
        """La phrase de tendance qualifie le sens de l'évolution."""
        self._fill_balanced()
        self.stmt.action_analyze()
        ratio = self.env['fa.ratio'].search([('code', '=', 'B1')], limit=1)
        t = ratio.get_thresholds(self.analysis.sector_id)
        # Liquidité en hausse : favorable
        txt = self.stmt._trend_sentence(ratio, 1.5, 1.2, t)
        self.assertIn("favorable", txt)
        # Liquidité en baisse : défavorable
        txt = self.stmt._trend_sentence(ratio, 1.0, 1.4, t)
        self.assertIn("défavorable", txt)
        # Stable
        txt = self.stmt._trend_sentence(ratio, 1.20, 1.21, t)
        self.assertIn("stable", txt)

    def test_30_sector_norm_copy_wizard(self):
        """L'assistant recopie les normes d'un secteur vers un autre."""
        target = self.env['fa.sector'].create({'name': "Test", 'code': 'test_x'})
        wiz = self.env['fa.sector.norm.copy'].create({
            'source_sector_id': self.sector_commerce.id,
            'target_sector_id': target.id,
        })
        wiz.action_copy()
        self.assertEqual(target.norm_count, self.sector_commerce.norm_count)

    # ==================================================================
    # Rapport multi-périodes et calibrage
    # ==================================================================
    def test_31_comparison_report_values(self):
        """Le rapport comparatif fournit toutes ses variables de rendu."""
        p1, p2, p3 = self._make_three_periods()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id, 'name': "Rapport",
            'statement_ids': [(6, 0, [p1.id, p2.id, p3.id])]})
        comp.action_compute()
        report = self.env['report.mg_financial_analysis.report_fa_comparison']
        values = report._get_report_values(comp.ids)
        for key in ('docs', 'periods', 'agg_lines', 'ratio_families',
                    'appr', 'fmt', 'sparkline', 'bar_chart', 'synthesis'):
            self.assertIn(key, values)
        self.assertEqual(len(values['periods'](comp)), 3)
        self.assertTrue(values['ratio_families'](comp))
        self.assertTrue(values['agg_lines'](comp, 'sig'))

    def test_32_sparkline_svg(self):
        """Les micro-graphiques produisent un SVG valide, sans hauteur négative."""
        import re as _re
        p1, p2, p3 = self._make_three_periods()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id, 'name': "SVG",
            'statement_ids': [(6, 0, [p1.id, p2.id, p3.id])]})
        comp.action_compute()
        report = self.env['report.mg_financial_analysis.report_fa_comparison']
        values = report._get_report_values(comp.ids)
        spark = values['sparkline']
        for line in comp.line_ids[:20]:
            svg = spark(comp, line)
            if not svg:
                continue
            self.assertTrue(svg.startswith('<svg'))
            self.assertTrue(svg.endswith('</svg>'))
            for h in _re.findall(r'height="([\d.]+)"', svg):
                self.assertGreaterEqual(float(h), 0.0)

    def test_33_report_synthesis(self):
        """La synthèse du comparatif distingue dégradations et améliorations."""
        p1, p2, p3 = self._make_three_periods()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id, 'name': "Synthèse",
            'statement_ids': [(6, 0, [p1.id, p2.id, p3.id])]})
        comp.action_compute()
        syn = comp._get_report_synthesis()
        for key in ('strengths', 'weaknesses', 'degraded', 'improved',
                    'recommendations', 'nb_bad', 'nb_watch', 'nb_ok', 'nb_good'):
            self.assertIn(key, syn)
        total = syn['nb_bad'] + syn['nb_watch'] + syn['nb_ok'] + syn['nb_good']
        self.assertGreater(total, 0)

    def test_34_print_from_analysis(self):
        """Le dossier imprime le comparatif de toutes ses périodes."""
        p1, p2, p3 = self._make_three_periods()
        action = self.analysis.action_print_comparison()
        self.assertEqual(action.get('type'), 'ir.actions.report')

    def test_35_print_requires_two_periods(self):
        """L'impression comparative exige au moins deux périodes."""
        self._fill_balanced()
        self.stmt.action_analyze()
        with self.assertRaises(UserError):
            self.analysis.action_print_comparison()

    def test_36_calibrate_wizard(self):
        """Le calibrage calcule les quartiles du portefeuille."""
        p1, p2, p3 = self._make_three_periods()
        wiz = self.env['fa.calibrate.wizard'].create({
            'sector_id': self.sector_commerce.id,
            'min_sample': 1,
            'only_annual': True,
        })
        wiz.action_preview()
        self.assertEqual(wiz.state, 'preview')
        self.assertTrue(wiz.line_ids)
        line = wiz.line_ids[0]
        self.assertLessEqual(line.observed_q1, line.observed_median)
        self.assertLessEqual(line.observed_median, line.observed_q3)
        self.assertGreaterEqual(line.sample_size, 1)

    def test_37_calibrate_apply(self):
        """Le calibrage appliqué crée des normes tracées comme portefeuille."""
        p1, p2, p3 = self._make_three_periods()
        wiz = self.env['fa.calibrate.wizard'].create({
            'sector_id': self.sector_commerce.id, 'min_sample': 1})
        wiz.action_preview()
        code = wiz.line_ids[0].ratio_id.code
        wiz.action_apply()
        norm = self.env['fa.sector.norm'].search([
            ('sector_id', '=', self.sector_commerce.id),
            ('ratio_id.code', '=', code)], limit=1)
        self.assertTrue(norm)
        self.assertEqual(norm.source, 'portfolio')
        self.assertTrue(norm.last_calibration)
        self.assertGreaterEqual(norm.sample_size, 1)

    def test_38_calibrate_no_data(self):
        """Le calibrage refuse un secteur sans dossier analysé."""
        empty = self.env['fa.sector'].create({'name': "Vide", 'code': 'vide_x'})
        wiz = self.env['fa.calibrate.wizard'].create({'sector_id': empty.id})
        with self.assertRaises(UserError):
            wiz.action_preview()

    def test_39_norm_source_traced(self):
        """Les normes livrées sont tracées comme références générales."""
        norm = self.env['fa.sector.norm'].search([
            ('sector_id', '=', self.sector_commerce.id)], limit=1)
        self.assertEqual(norm.source, 'default')
        self.assertTrue(norm.source_note)

    def test_40_quantile(self):
        """Le calcul de quantile est exact sur un jeu connu."""
        wiz = self.env['fa.calibrate.wizard']
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(wiz._quantile(values, 0.5), 3.0)
        self.assertAlmostEqual(wiz._quantile(values, 0.25), 2.0)
        self.assertAlmostEqual(wiz._quantile(values, 0.75), 4.0)
        self.assertAlmostEqual(wiz._quantile([7.0], 0.5), 7.0)
        self.assertAlmostEqual(wiz._quantile([], 0.5), 0.0)

    # ==================================================================
    # Explication du ratio et recommandations dans les restitutions
    # ==================================================================
    def test_41_every_ratio_has_interpretation(self):
        """Chaque ratio du référentiel porte une explication pédagogique."""
        missing = self.env['fa.ratio'].search([('interpretation', '=', False)])
        self.assertFalse(
            missing, "Ratios sans explication : %s" % missing.mapped('code'))

    def test_42_every_rule_has_recommendation(self):
        """Chaque règle de commentaire propose une action, y compris si tout va bien."""
        rules = self.env['fa.comment.rule'].search([])
        self.assertTrue(rules)
        missing = rules.filtered(lambda r: not r.recommendation_tpl)
        self.assertFalse(
            missing, "Règles sans recommandation : %s" % missing.mapped('name'))
        # Y compris pour les ratios bien orientés
        good = rules.filtered(lambda r: r.appreciation == 'good')
        self.assertTrue(good)
        self.assertFalse(good.filtered(lambda r: not r.recommendation_tpl))

    def test_43_results_carry_reco_and_interpretation(self):
        """Après analyse, chaque ratio calculable porte constat, action et explication."""
        self._fill_balanced()
        self.stmt.action_analyze()
        calc = self.stmt.ratio_result_ids.filtered(lambda r: not r.is_na)
        self.assertTrue(calc)
        no_reco = calc.filtered(lambda r: not r.recommendation)
        self.assertFalse(
            no_reco, "Ratios sans recommandation : %s" % no_reco.mapped('code'))
        no_interp = calc.filtered(lambda r: not r.interpretation)
        self.assertFalse(
            no_interp, "Ratios sans explication : %s" % no_interp.mapped('code'))

    def test_44_comparison_lines_carry_reco_and_interpretation(self):
        """Les lignes du comparatif transportent explication et recommandation."""
        p1, p2, p3 = self._make_three_periods()
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id, 'name': "Restitution",
            'statement_ids': [(6, 0, [p1.id, p2.id, p3.id])]})
        comp.action_compute()
        ratio_lines = comp.ratio_line_ids
        self.assertTrue(ratio_lines)
        no_interp = ratio_lines.filtered(lambda l: not l.interpretation)
        self.assertFalse(
            no_interp, "Lignes sans explication : %s" % no_interp.mapped('code'))
        no_formula = ratio_lines.filtered(lambda l: not l.formula_text)
        self.assertFalse(no_formula, "Lignes sans formule de calcul")
        with_reco = ratio_lines.filtered(lambda l: l.recommendation)
        self.assertTrue(with_reco, "Aucune recommandation transmise au comparatif")

    def test_45_reports_render_reco_and_interpretation(self):
        """Les deux modèles de rapport exposent bien les trois volets."""
        tpl_multi = self.env.ref(
            'mg_financial_analysis.report_fa_comparison').arch
        tpl_solo = self.env.ref(
            'mg_financial_analysis.report_fa_statement').arch
        for tpl, label in ((tpl_multi, 'comparatif'), (tpl_solo, 'mono-période')):
            self.assertIn('interpretation', tpl,
                          "Explication absente du rapport %s" % label)
            self.assertIn('recommendation', tpl,
                          "Recommandation absente du rapport %s" % label)
            self.assertIn('Glossaire', tpl,
                          "Glossaire absent du rapport %s" % label)

    # ==================================================================
    # Options d'impression des recommandations
    # ==================================================================
    def test_46_report_options_defaults(self):
        """Par défaut, le rapport inclut recommandations, explications et glossaire."""
        self.assertTrue(self.analysis.report_show_recommendations)
        self.assertTrue(self.analysis.report_show_interpretation)
        self.assertTrue(self.analysis.report_show_glossary)
        self.assertEqual(self.analysis.report_reco_scope, 'alerts')

    def test_47_reco_scope_filters(self):
        """La portée restreint les recommandations imprimées."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(
            lambda r: r.appreciation == 'good' and r.recommendation)[:1]
        self.assertTrue(res, "Le jeu de test doit contenir un ratio solide")

        self.analysis.report_reco_scope = 'all'
        self.assertTrue(self.stmt.show_reco_for(res))

        self.analysis.report_reco_scope = 'alerts'
        self.assertFalse(self.stmt.show_reco_for(res))

        bad = self.stmt.ratio_result_ids.filtered(
            lambda r: r.appreciation == 'bad' and r.recommendation)[:1]
        if bad:
            self.assertTrue(self.stmt.show_reco_for(bad))
            self.analysis.report_reco_scope = 'critical'
            self.assertTrue(self.stmt.show_reco_for(bad))

    def test_48_disable_recommendations(self):
        """Désactiver l'option supprime toute recommandation du rapport."""
        self._fill_balanced()
        self.stmt.action_analyze()
        self.analysis.report_show_recommendations = False
        for res in self.stmt.ratio_result_ids[:10]:
            self.assertFalse(self.stmt.show_reco_for(res))

    def test_49_hide_ratio_in_report(self):
        """Un ratio masqué sort des rapports mais reste en base."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B1')
        res.hide_in_report = True
        printed = self.stmt.get_report_ratios()
        self.assertNotIn(res, printed)
        self.assertIn(res, self.stmt.ratio_result_ids)
        syn = self.stmt.get_synthesis()
        for key in ('strengths', 'weaknesses', 'recommendations'):
            self.assertNotIn(res, syn[key])

    def test_50_hide_good_ratios_bulk(self):
        """L'action de masse écarte les ratios bien orientés du livrable."""
        self._fill_balanced()
        self.stmt.action_analyze()
        good = self.stmt.ratio_result_ids.filtered(lambda r: r.appreciation == 'good')
        self.assertTrue(good)
        self.stmt.action_hide_good_ratios()
        self.assertTrue(all(r.hide_in_report for r in good))
        printed = self.stmt.get_report_ratios()
        self.assertFalse(printed.filtered(lambda r: r.appreciation == 'good'))
        self.stmt.action_show_all_ratios()
        self.assertFalse(self.stmt.ratio_result_ids.filtered('hide_in_report'))

    def test_51_priority_override(self):
        """La priorité du consultant prime pour le classement des actions."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(
            lambda r: r.appreciation in ('bad', 'watch'))[:1]
        self.assertTrue(res)
        res.priority_manual = '1'
        self.assertEqual(res.priority_final, '1')
        self.assertTrue(res.is_customized)
        res.action_reset_text()
        self.assertFalse(res.priority_manual)
        self.assertEqual(res.priority_final, res.priority)

    def test_52_comparison_respects_options(self):
        """Le comparatif propage masquage et priorité, et filtre la synthèse."""
        p1, p2, p3 = self._make_three_periods()
        target = p3.ratio_result_ids.filtered(lambda r: r.code == 'B1')
        target.write({'hide_in_report': True, 'priority_manual': '1'})
        comp = self.env['fa.comparison'].create({
            'analysis_id': self.analysis.id, 'name': "Options",
            'statement_ids': [(6, 0, [p1.id, p2.id, p3.id])]})
        comp.action_compute()
        line = comp.ratio_line_ids.filtered(lambda l: l.code == 'B1')
        self.assertTrue(line.hide_in_report)
        self.assertEqual(line.priority_final, '1')
        syn = comp._get_report_synthesis()
        for key in ('strengths', 'weaknesses', 'recommendations'):
            self.assertFalse(syn[key].filtered(lambda l: l.code == 'B1'))

    def test_53_toggle_hide(self):
        """Le basculement du masquage fonctionne dans les deux sens."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids[:1]
        self.assertFalse(res.hide_in_report)
        res.action_toggle_hide()
        self.assertTrue(res.hide_in_report)
        res.action_toggle_hide()
        self.assertFalse(res.hide_in_report)

    # ==================================================================
    # Scoring de défaillance
    # ==================================================================
    def test_54_scores_generated(self):
        """L'analyse produit les trois scores de risque."""
        self._fill_balanced()
        self.stmt.action_analyze()
        self.assertEqual(len(self.stmt.score_ids), 3)
        models = set(self.stmt.score_ids.mapped('model'))
        self.assertEqual(models, {'altman', 'conan', 'synthesis'})

    def test_55_altman_formula(self):
        """Altman Z'' est conforme à la formule marchés émergents."""
        Score = self.env['fa.score']
        v = {
            'T_ACTIF': 1000.0, 'ST_AC': 600.0, 'ST_PC': 400.0,
            'PA_PRIMES': 50.0, 'PA_AUTRES_CP': 30.0,
            'REX': 60.0, 'ST_CP': 330.0, 'DETTES_TOTALES': 670.0,
        }
        score, detail = Score.compute_altman(v)
        x1, x2, x3, x4 = 200 / 1000, 80 / 1000, 60 / 1000, 330 / 670
        expected = 3.25 + 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
        self.assertAlmostEqual(score, expected, places=4)
        self.assertIn('X1', detail)

    def test_56_conan_formula(self):
        """Conan-Holder est conforme à la fonction discriminante."""
        Score = self.env['fa.score']
        v = {
            'T_ACTIF': 1000.0, 'DETTES_TOTALES': 670.0, 'CA': 2000.0, 'VA': 400.0,
            'EBE': 120.0, 'CAPITAUX_PERMANENTS': 600.0,
            'AC_TRESO': 50.0, 'AC_PLACEMENT': 0.0, 'AC_CLIENT': 300.0,
            'PL_CH_FIN': 20.0, 'PL_PERSONNEL': 250.0,
        }
        score, detail = Score.compute_conan(v)
        expected = (24 * (120 / 670) + 22 * (600 / 1000) + 16 * (350 / 1000)
                    - 87 * (20 / 2000) - 10 * (250 / 400))
        self.assertAlmostEqual(score, expected, places=4)

    def test_57_score_zones(self):
        """Les seuils de zone respectent les barèmes publiés."""
        Score = self.env['fa.score']
        self.assertEqual(Score._altman_zone(0.9)[0], 'distress')
        self.assertEqual(Score._altman_zone(2.0)[0], 'grey')
        self.assertEqual(Score._altman_zone(3.0)[0], 'safe')
        self.assertEqual(Score._conan_zone(3.0)[0], 'distress')
        self.assertEqual(Score._conan_zone(12.0)[0], 'grey')
        self.assertEqual(Score._conan_zone(20.0)[0], 'safe')
        self.assertEqual(Score._synthesis_zone(30.0)[0], 'distress')
        self.assertEqual(Score._synthesis_zone(70.0)[0], 'safe')

    def test_58_synthesis_score_bounds(self):
        """La note de synthèse reste dans l'intervalle 0-100."""
        self._fill_balanced()
        self.stmt.action_analyze()
        synth = self.stmt.score_ids.filtered(lambda s: s.model == 'synthesis')
        self.assertFalse(synth.is_na)
        self.assertGreaterEqual(synth.value, 0.0)
        self.assertLessEqual(synth.value, 100.0)
        self.assertEqual(self.stmt.score_synthesis, synth.value)
        self.assertEqual(self.stmt.risk_zone, synth.zone)

    def test_59_score_no_division_by_zero(self):
        """Un état vide rend les scores non calculables, sans planter."""
        self.stmt.action_analyze()
        for sc in self.stmt.score_ids:
            if sc.is_na:
                self.assertTrue(sc.na_reason)

    def test_60_score_comment_has_caveat(self):
        """Chaque score rappelle sa réserve méthodologique."""
        self._fill_balanced()
        self.stmt.action_analyze()
        for sc in self.stmt.score_ids.filtered(lambda s: not s.is_na):
            self.assertTrue(sc.comment)
            self.assertIn('malgache', sc.comment)

    def test_61_score_history(self):
        """Le score reprend la valeur de la période précédente."""
        p1, p2, p3 = self._make_three_periods()
        sc = p2.score_ids.filtered(lambda s: s.model == 'altman')
        prev = p1.score_ids.filtered(lambda s: s.model == 'altman')
        self.assertAlmostEqual(sc.previous_value, prev.value, places=4)

    # ==================================================================
    # Conclusion automatique
    # ==================================================================
    def test_62_conclusion_generated(self):
        """La conclusion est rédigée à partir des indicateurs."""
        self._fill_balanced()
        self.stmt.action_analyze()
        self.analysis.action_generate_conclusion()
        text = self.analysis.conclusion or ''
        self.assertTrue(text)
        for marker in ("Activité et rentabilité", "Équilibre financier",
                       "Structure financière", "Projet de conclusion"):
            self.assertIn(marker, text)

    def test_63_conclusion_requires_analysis(self):
        """Sans période analysée, la génération est refusée."""
        with self.assertRaises(UserError):
            self.analysis.action_generate_conclusion()

    def test_64_conclusion_confirm_wizard(self):
        """L'assistant propose de compléter ou de remplacer."""
        self._fill_balanced()
        self.stmt.action_analyze()
        self.analysis.conclusion = "<p>Texte existant du consultant.</p>"
        action = self.analysis.action_generate_conclusion()
        self.assertEqual(action.get('res_model'), 'fa.conclusion.confirm')
        wiz = self.env['fa.conclusion.confirm'].create({
            'analysis_id': self.analysis.id, 'mode': 'append'})
        wiz.action_confirm()
        self.assertIn("Texte existant du consultant", self.analysis.conclusion)
        self.assertIn("Activité et rentabilité", self.analysis.conclusion)

    # ==================================================================
    # Correctifs : contrôles et performance
    # ==================================================================
    def test_65_rg04_products_charges_control(self):
        """RG-04 : incohérence entre totaux déclarés et résultat calculé."""
        self._fill_balanced()
        self.assertFalse(self.stmt.warning_message)
        # Totaux volontairement incohérents
        self._set('PL_TOT_PROD', 2000)
        self._set('PL_TOT_CH', 1500)   # écart = 500, or RNAO = 30
        self.assertTrue(self.stmt.warning_message)
        self.assertIn("Total des produits", self.stmt.warning_message)

    def test_66_stock_exceeds_turnover_warning(self):
        """Une anomalie de saisie sur les stocks est signalée."""
        self._fill_balanced()
        self._set('AC_STOCK', 5000)     # stock > CA de 2000
        self.assertIn("stock", (self.stmt.warning_message or '').lower())

    def test_67_capital_reconstitution_warning(self):
        """Capitaux propres sous la moitié du capital : alerte légale."""
        self._set('PA_CAPITAL', 1000)
        self._set('PA_AUTRES_CP', -700)   # CP = 300 < 500
        self.assertIn("reconstitution", (self.stmt.warning_message or '').lower())

    def test_68_check_values_subset(self):
        """Le contrôle d'équilibre n'utilise qu'un sous-ensemble de rubriques."""
        self._fill_balanced()
        light = self.stmt._get_check_values()
        full = self.stmt._get_values_dict()
        self.assertLess(len(light), len(full))
        # Mais les totaux sont identiques
        self.assertAlmostEqual(light['T_ACTIF'], full['T_ACTIF'], places=2)
        self.assertAlmostEqual(light['T_PASSIF'], full['T_PASSIF'], places=2)
        self.assertAlmostEqual(light['RN'], full['RN'], places=2)

    def test_69_comparison_no_nplus1(self):
        """Le comparatif ne requête plus le référentiel dans sa boucle."""
        import inspect
        source = inspect.getsource(
            type(self.env['fa.comparison'])._compute_trend_comments)
        self.assertNotIn("search([('code', '=', line.code)]", source)
        self.assertIn("directions", source)

    # ==================================================================
    # Tableau des flux de trésorerie (PCG 2005, chapitre 5)
    # ==================================================================
    def _two_periods_for_cashflow(self):
        """Deux exercices consécutifs avec des variations de bilan réelles."""
        self._fill_balanced()
        self.stmt.action_analyze()
        p2 = self.stmt.copy({
            'name': "Exercice N+1", 'period_type': 'annual',
            'date_from': '2026-01-01', 'date_to': '2026-12-31',
            'previous_statement_id': self.stmt.id,
        })

        def setv(stmt, code, amount):
            rubric = self.env['fa.rubric'].search([('code', '=', code)], limit=1)
            stmt.line_ids.filtered(lambda l, r=rubric: l.rubric_id == r).amount_net = amount

        # Actif : 1 150
        setv(p2, 'AC_IMMO_CORP', 450)
        setv(p2, 'AC_STOCK', 300)
        setv(p2, 'AC_CLIENT', 350)
        setv(p2, 'AC_TRESO', 50)
        # Compte de résultat : RN = 40
        setv(p2, 'PL_VENTE_MSE', 2200)
        setv(p2, 'PL_ACHAT_MSE', 1500)
        setv(p2, 'PL_SERV_EXT', 220)
        setv(p2, 'PL_PERSONNEL', 280)
        setv(p2, 'PL_IMPOTS_TAXES', 30)
        setv(p2, 'PL_DOTATIONS', 70)
        setv(p2, 'PL_CH_FIN', 25)
        setv(p2, 'PL_IMP_EXIG', 35)
        # Passif : 1 150
        setv(p2, 'PA_CAPITAL', 300)
        setv(p2, 'PA_AUTRES_CP', 30)
        setv(p2, 'PA_RESULTAT', 40)
        setv(p2, 'PA_EMPRUNT_NC', 320)
        setv(p2, 'PA_FOURN', 460)
        p2.action_analyze()
        return self.stmt, p2

    def test_70_cashflow_generated(self):
        """L'analyse produit le tableau selon les deux méthodes."""
        p1, p2 = self._two_periods_for_cashflow()
        self.assertTrue(p2.cashflow_ids)
        methods = set(p2.cashflow_ids.mapped('method'))
        self.assertEqual(methods, {'indirect', 'direct'})
        cats = set(p2.cashflow_ids.filtered(
            lambda c: c.method == 'indirect').mapped('category'))
        self.assertEqual(cats, {'operating', 'investing', 'financing', 'summary'})

    def test_71_cashflow_balances(self):
        """Le tableau boucle avec la variation de trésorerie du bilan."""
        p1, p2 = self._two_periods_for_cashflow()
        self.assertTrue(
            p2.cf_is_balanced,
            "Écart de bouclage de %s : le tableau doit boucler par construction"
            % p2.cf_gap)
        self.assertAlmostEqual(p2.cf_variation, p2.cf_variation_bs, places=2)
        self.assertAlmostEqual(
            p2.cf_operating + p2.cf_investing + p2.cf_financing,
            p2.cf_variation, places=2)

    def test_72_cashflow_matches_treasury_delta(self):
        """La variation calculée égale la différence de trésorerie nette."""
        p1, p2 = self._two_periods_for_cashflow()
        v1, v2 = p1._get_values_dict(), p2._get_values_dict()
        treso1 = v1['AC_TRESO'] + v1['AC_PLACEMENT'] - v1['PA_TRESO_PASSIF']
        treso2 = v2['AC_TRESO'] + v2['AC_PLACEMENT'] - v2['PA_TRESO_PASSIF']
        self.assertAlmostEqual(p2.cf_variation, treso2 - treso1, places=2)

    def test_73_cashflow_caf_consistency(self):
        """La CAF du tableau rejoint celle des agrégats."""
        p1, p2 = self._two_periods_for_cashflow()
        caf_line = p2.cashflow_ids.filtered(
            lambda c: c.method == 'indirect' and c.code == 'CF_CAF')
        caf_agg = p2.aggregate_ids.filtered(lambda a: a.code == 'CAF')
        self.assertAlmostEqual(caf_line.amount, caf_agg.amount, delta=1.0)

    def test_74_cashflow_needs_comparative(self):
        """Sans période de référence, le tableau signale son impossibilité."""
        self._fill_balanced()
        self.stmt.previous_statement_id = False
        for line in self.stmt.line_ids:
            line.amount_previous = 0.0
        self.stmt.action_analyze()
        na = self.stmt.cashflow_ids.filtered(lambda c: c.code == 'CF_NA')
        self.assertTrue(na)
        self.assertTrue(na.note)

    def test_75_free_cashflow(self):
        """Le flux disponible retranche les investissements du flux opérationnel."""
        p1, p2 = self._two_periods_for_cashflow()
        acq = p2.cashflow_ids.filtered(
            lambda c: c.method == 'indirect' and c.code == 'CF_ACQ')
        self.assertAlmostEqual(
            p2.cf_free_cashflow, p2.cf_operating + acq.amount, places=2)

    def test_76_direct_method_reconciliation(self):
        """La méthode directe rapproche le flux du résultat avant impôts (art. 250-3)."""
        p1, p2 = self._two_periods_for_cashflow()
        direct = p2.get_cashflow('direct')
        self.assertTrue(direct)
        net = direct.filtered(lambda c: c.code == 'CFD_OP_NET')
        rai = direct.filtered(lambda c: c.code == 'CFD_RAI')
        ecart = direct.filtered(lambda c: c.code == 'CFD_ECART')
        self.assertTrue(net and rai and ecart)
        self.assertAlmostEqual(ecart.amount, net.amount - rai.amount, places=2)

    def test_77_cashflow_balances_on_random_data(self):
        """Le bouclage tient sur des jeux de données variés."""
        import random
        random.seed(7)
        codes_actif = ['AC_IMMO_CORP', 'AC_STOCK', 'AC_CLIENT', 'AC_TRESO']
        codes_passif = ['PA_CAPITAL', 'PA_EMPRUNT_NC', 'PA_FOURN']

        def fill(stmt, seed_shift):
            random.seed(7 + seed_shift)
            actif = {c: random.randint(10, 400) for c in codes_actif}
            for c, a in actif.items():
                self._set_on(stmt, c, a)
            self._set_on(stmt, 'PL_VENTE_MSE', 2000)
            self._set_on(stmt, 'PL_ACHAT_MSE', 1400)
            self._set_on(stmt, 'PL_SERV_EXT', 200)
            self._set_on(stmt, 'PL_PERSONNEL', 250)
            self._set_on(stmt, 'PL_DOTATIONS', random.randint(20, 90))
            v = stmt._get_values_dict()
            rn = v['RN']
            self._set_on(stmt, 'PA_RESULTAT', rn)
            passif = {c: random.randint(10, 300) for c in codes_passif}
            for c, a in passif.items():
                self._set_on(stmt, c, a)
            v = stmt._get_values_dict()
            self._set_on(stmt, 'PA_AUTRES_CP', v['T_ACTIF'] - v['T_PASSIF'])

        for i in range(5):
            p1 = self.env['fa.statement'].create({
                'name': "Alea %s A" % i, 'analysis_id': self.analysis.id,
                'period_type': 'annual',
                'date_from': '2024-01-01', 'date_to': '2024-12-31'})
            fill(p1, i)
            p2 = self.env['fa.statement'].create({
                'name': "Alea %s B" % i, 'analysis_id': self.analysis.id,
                'period_type': 'annual', 'previous_statement_id': p1.id,
                'date_from': '2025-01-01', 'date_to': '2025-12-31'})
            fill(p2, i + 50)
            p1.action_analyze()
            p2.action_analyze()
            self.assertTrue(
                p2.cf_is_balanced,
                "Jeu %s : écart de bouclage de %s" % (i, p2.cf_gap))

    def _set_on(self, stmt, code, amount):
        rubric = self.env['fa.rubric'].search([('code', '=', code)], limit=1)
        stmt.line_ids.filtered(lambda l, r=rubric: l.rubric_id == r).amount_net = amount

    def test_78_cashflow_new_rubrics_exist(self):
        """Les rubriques de saisie propres aux flux sont présentes."""
        for code in ('IN_EMPRUNTS_NOUVEAUX', 'IN_REMB_EMPRUNTS', 'IN_AUGM_CAPITAL',
                     'IN_TRESO_OUVERTURE', 'IN_INTERETS_PAYES', 'IN_IMPOTS_PAYES'):
            rubric = self.env['fa.rubric'].search([('code', '=', code)], limit=1)
            self.assertTrue(rubric, "Rubrique %s absente du référentiel" % code)
            self.assertEqual(rubric.statement_type, 'extra')

    # ==================================================================
    # Variation des capitaux propres (PCG 2005, chapitre 4)
    # ==================================================================
    def test_79_equity_table_generated(self):
        """L'analyse produit le tableau de variation des capitaux propres."""
        p1, p2 = self._two_periods_for_cashflow()
        self.assertTrue(p2.equity_ids)
        codes = set(p2.equity_ids.mapped('code'))
        self.assertIn('EQ_OPENING', codes)
        self.assertIn('EQ_CLOSING', codes)
        self.assertIn('EQ_RESULT', codes)

    def test_80_equity_balances_by_column(self):
        """Ouverture + mouvements = clôture, pour chaque rubrique."""
        from odoo.addons.mg_financial_analysis.models.fa_equity import EQUITY_COLUMNS
        p1, p2 = self._two_periods_for_cashflow()
        table = p2.get_equity_table()
        opening = table.filtered(lambda l: l.code == 'EQ_OPENING')
        closing = table.filtered(lambda l: l.code == 'EQ_CLOSING')
        movements = table.filtered(lambda l: l.line_type == 'movement')
        self.assertTrue(opening and closing and movements)
        for col, _rub, label in EQUITY_COLUMNS:
            field = 'amount_%s' % col
            moved = sum(m[field] for m in movements)
            self.assertAlmostEqual(
                opening[field] + moved, closing[field], places=2,
                msg="Colonne « %s » : le tableau ne boucle pas" % label)

    def test_81_equity_matches_balance_sheet(self):
        """Les soldes correspondent aux capitaux propres du bilan."""
        p1, p2 = self._two_periods_for_cashflow()
        v1 = p1._get_values_dict()
        v2 = p2._get_values_dict()
        self.assertAlmostEqual(p2.eq_opening, v1['ST_CP'], places=2)
        self.assertAlmostEqual(p2.eq_closing, v2['ST_CP'], places=2)
        self.assertAlmostEqual(p2.eq_variation, v2['ST_CP'] - v1['ST_CP'], places=2)

    def test_82_equity_result_column(self):
        """Le résultat de la période figure bien dans sa colonne."""
        p1, p2 = self._two_periods_for_cashflow()
        result_line = p2.equity_ids.filtered(lambda l: l.code == 'EQ_RESULT')
        v2 = p2._get_values_dict()
        self.assertAlmostEqual(
            result_line.amount_resultat, v2['PA_RESULTAT'], places=2)
        self.assertEqual(result_line.movement_type, 'result')

    def test_83_equity_prior_result_reallocated(self):
        """Le résultat antérieur est transféré en report à nouveau."""
        p1, p2 = self._two_periods_for_cashflow()
        affect = p2.equity_ids.filtered(lambda l: l.code == 'EQ_AFFECT')
        if affect:
            v1 = p1._get_values_dict()
            self.assertAlmostEqual(
                affect.amount_resultat, -v1['PA_RESULTAT'], places=2)
            self.assertEqual(affect.movement_type, 'distribution')

    def test_84_equity_dividends(self):
        """Une distribution est isolée et diminue le report à nouveau."""
        p1, p2 = self._two_periods_for_cashflow()
        self._set_on(p2, 'IN_DIVIDENDES', 15)
        p2.action_analyze()
        div = p2.equity_ids.filtered(lambda l: l.code == 'EQ_DIV')
        self.assertTrue(div, "La distribution doit apparaître sur sa propre ligne")
        self.assertAlmostEqual(div.amount_report, -15, places=2)
        self.assertEqual(div.movement_type, 'distribution')

    def test_85_equity_capital_increase(self):
        """Une augmentation de capital est classée en opération en capital."""
        p1, p2 = self._two_periods_for_cashflow()
        self._set_on(p2, 'PA_CAPITAL', 400)      # 300 -> 400
        self._set_on(p2, 'PA_AUTRES_CP', -70)    # rééquilibrage du bilan
        p2.action_analyze()
        cap = p2.equity_ids.filtered(lambda l: l.code == 'EQ_CAPITAL')
        self.assertTrue(cap)
        self.assertAlmostEqual(cap.amount_capital, 100, places=2)
        self.assertEqual(cap.movement_type, 'capital')

    def test_86_equity_reclassification_detected(self):
        """Un virement entre rubriques est identifié comme reclassement."""
        p1, p2 = self._two_periods_for_cashflow()
        # On déplace 20 du report à nouveau vers les réserves : total inchangé
        v = p2._get_values_dict()
        self._set_on(p2, 'PA_PRIMES', v.get('PA_PRIMES', 0.0) + 20)
        self._set_on(p2, 'PA_AUTRES_CP', v.get('PA_AUTRES_CP', 0.0) - 20)
        p2.action_analyze()
        other = p2.equity_ids.filtered(lambda l: l.code == 'EQ_OTHER')
        self.assertTrue(other)
        # Le net est nul mais le brut ne l'est pas : c'est un reclassement
        self.assertAlmostEqual(other.amount_total, 0.0, delta=1.0)
        self.assertGreater(p2.eq_unexplained_gross, 1.0)
        self.assertIn("compensent", other.note or '')

    def test_87_equity_needs_comparative(self):
        """Sans période de référence, le tableau signale son impossibilité."""
        self._fill_balanced()
        self.stmt.previous_statement_id = False
        for line in self.stmt.line_ids:
            line.amount_previous = 0.0
        self.stmt.action_analyze()
        na = self.stmt.equity_ids.filtered(lambda l: l.code == 'EQ_NA')
        self.assertTrue(na)

    def test_88_equity_total_column(self):
        """La colonne Total est bien la somme des rubriques."""
        from odoo.addons.mg_financial_analysis.models.fa_equity import EQUITY_COLUMNS
        p1, p2 = self._two_periods_for_cashflow()
        for line in p2.equity_ids:
            expected = sum(line['amount_%s' % col] for col, _r, _l in EQUITY_COLUMNS)
            self.assertAlmostEqual(line.amount_total, expected, places=2)

    def test_89_equity_balances_on_random_data(self):
        """Le bouclage par colonne tient sur des jeux variés."""
        from odoo.addons.mg_financial_analysis.models.fa_equity import EQUITY_COLUMNS
        import random
        random.seed(23)

        def fill(stmt, shift):
            random.seed(23 + shift)
            for c in ('AC_IMMO_CORP', 'AC_STOCK', 'AC_CLIENT', 'AC_TRESO'):
                self._set_on(stmt, c, random.randint(10, 400))
            self._set_on(stmt, 'PL_VENTE_MSE', 2000)
            self._set_on(stmt, 'PL_ACHAT_MSE', 1400)
            self._set_on(stmt, 'PL_PERSONNEL', 250)
            self._set_on(stmt, 'PL_DOTATIONS', random.randint(20, 90))
            self._set_on(stmt, 'PA_CAPITAL', random.choice([300, 300, 400]))
            self._set_on(stmt, 'PA_ECART_EVAL', random.randint(0, 60))
            v = stmt._get_values_dict()
            self._set_on(stmt, 'PA_RESULTAT', v['RN'])
            self._set_on(stmt, 'PA_EMPRUNT_NC', random.randint(50, 300))
            self._set_on(stmt, 'PA_FOURN', random.randint(100, 400))
            v = stmt._get_values_dict()
            self._set_on(stmt, 'PA_AUTRES_CP', v['T_ACTIF'] - v['T_PASSIF'])

        for i in range(4):
            a = self.env['fa.statement'].create({
                'name': "EqA %s" % i, 'analysis_id': self.analysis.id,
                'period_type': 'annual',
                'date_from': '2024-01-01', 'date_to': '2024-12-31'})
            fill(a, i)
            b = self.env['fa.statement'].create({
                'name': "EqB %s" % i, 'analysis_id': self.analysis.id,
                'period_type': 'annual', 'previous_statement_id': a.id,
                'date_from': '2025-01-01', 'date_to': '2025-12-31'})
            fill(b, i + 60)
            a.action_analyze()
            b.action_analyze()
            table = b.get_equity_table()
            opening = table.filtered(lambda l: l.code == 'EQ_OPENING')
            closing = table.filtered(lambda l: l.code == 'EQ_CLOSING')
            movements = table.filtered(lambda l: l.line_type == 'movement')
            for col, _rub, label in EQUITY_COLUMNS:
                f = 'amount_%s' % col
                moved = sum(m[f] for m in movements)
                self.assertAlmostEqual(
                    opening[f] + moved, closing[f], places=2,
                    msg="Jeu %s, colonne %s : bouclage rompu" % (i, label))

    # ==================================================================
    # Intégrité de l'installation
    # ==================================================================
    def test_90_manifest_load_order(self):
        """Chaque référence XML doit être définie avant d'être utilisée.

        Ce test rejoue l'ordre de chargement du manifest et vérifie qu'aucun
        fichier ne référence un identifiant publié plus tard : c'est la cause
        de l'erreur « External ID not found in the system » à l'installation.
        """
        import ast
        import os
        import re
        import xml.etree.ElementTree as ET
        from odoo.modules import get_module_path

        base = get_module_path('mg_financial_analysis')
        src = open(os.path.join(base, '__manifest__.py'), encoding='utf-8').read()
        manifest = ast.literal_eval(src[src.index('{'):src.rindex('}') + 1])

        defined = set()
        for folder in ('models', 'wizard'):
            folder_path = os.path.join(base, folder)
            if not os.path.isdir(folder_path):
                continue
            for fname in os.listdir(folder_path):
                if not fname.endswith('.py'):
                    continue
                code = open(os.path.join(folder_path, fname), encoding='utf-8').read()
                for m in re.findall(r"^\s{4}_name\s*=\s*'([\w.]+)'", code, re.M):
                    defined.add('model_' + m.replace('.', '_'))

        problems = []
        for rel in manifest['data'] + manifest.get('demo', []):
            if not rel.endswith('.xml'):
                continue
            root = ET.parse(os.path.join(base, rel)).getroot()
            for node in root.iter():
                if node.tag not in ('record', 'menuitem', 'template'):
                    continue
                for el in node.iter():
                    ref = el.get('ref')
                    if ref and '.' not in ref and ref not in defined:
                        problems.append((rel, ref))
                for attr in ('parent', 'action'):
                    ref = node.get(attr)
                    if ref and '.' not in ref and ref not in defined:
                        problems.append((rel, ref))
                if node.get('id'):
                    defined.add(node.get('id'))
        self.assertFalse(
            problems,
            "Références utilisées avant définition : %s" % sorted(set(problems)))

    def test_91b_odoo16_syntax(self):
        """Aucune syntaxe Odoo 17 ne doit subsister dans les vues."""
        import glob
        import os
        import re
        from odoo.modules import get_module_path

        base = get_module_path('mg_financial_analysis')
        problems = []
        for path in glob.glob(os.path.join(base, '**', '*.xml'), recursive=True):
            raw = open(path, encoding='utf-8').read()
            rel = os.path.relpath(path, base)
            # column_invisible en attribut direct n'existe qu'à partir d'Odoo 17
            if re.search(r'column_invisible="(?!\[)', raw):
                problems.append("%s : column_invisible en attribut direct" % rel)
            if re.search(r'<list[\s>]', raw):
                problems.append("%s : balise <list> au lieu de <tree>" % rel)
        self.assertFalse(problems, "Syntaxes incompatibles Odoo 16 : %s" % problems)

    def test_91_view_fields_exist(self):
        """Tout champ cité dans une vue doit exister sur son modèle."""
        views = self.env['ir.ui.view'].search([
            ('model', 'like', 'fa.'),
        ])
        self.assertTrue(views)
        for view in views:
            model = self.env.get(view.model)
            if model is None:
                continue
            # postprocess lève une erreur si un champ est inconnu
            try:
                model.with_context(check_view_ids=view.ids).get_view(
                    view.id, view.type)
            except Exception as err:  # noqa: BLE001
                self.fail("Vue « %s » (%s) invalide : %s"
                          % (view.name, view.model, err))

    # ==================================================================
    # Seuil de rentabilité par l'excédent brut d'exploitation
    # ==================================================================
    def test_92_sr_by_ebe(self):
        """Le SR est calculé par le taux d'EBE quand la ventilation manque."""
        self._fill_balanced()
        self.analysis.sr_method = 'ebe'
        v = self.stmt._get_values_dict()
        # EBE = 120, CA = 2000 -> taux 6 %
        self.assertAlmostEqual(v['TAUX_EBE'], 0.06, places=4)
        # Charges de structure = dotations 60 + frais financiers 20 + impôt 10
        self.assertAlmostEqual(v['CSI'], 90.0, places=2)
        self.assertAlmostEqual(v['SR'], 90.0 / 0.06, places=2)
        self.assertEqual(v['SR_METHOD'], 2.0)

    def test_93_sr_taxes_option(self):
        """L'option ajoute les impôts et taxes aux charges de structure."""
        self._fill_balanced()
        self.analysis.sr_method = 'ebe'
        without = self.stmt._get_values_dict()['CSI']
        self.analysis.sr_include_taxes = True
        with_taxes = self.stmt._get_values_dict()['CSI']
        # Les impôts et taxes valent 30 dans le jeu de test
        self.assertAlmostEqual(with_taxes - without, 30.0, places=2)
        self.assertFalse(
            self.env['fa.analysis'].default_get(['sr_include_taxes'])
            .get('sr_include_taxes'),
            "L'option doit être désactivée par défaut : les impôts et taxes "
            "sont déjà déduits dans l'EBE")

    def test_94_sr_null_result_at_threshold(self):
        """Au seuil de rentabilité, le résultat doit être proche de zéro."""
        self._fill_balanced()
        self.analysis.sr_method = 'ebe'
        v = self.stmt._get_values_dict()
        sr = v['SR']
        self.assertTrue(sr)
        # Reconstitution du résultat pour un CA égal au seuil
        ebe = sr * v['TAUX_EBE']
        rex = (ebe - v['PL_DOTATIONS'] + v['PL_REPRISES']
               + v['PL_AUT_PROD_OP'] - v['PL_AUT_CH_OP'])
        rn = rex + v['PL_PROD_FIN'] - v['PL_CH_FIN'] - v['PL_IMP_EXIG']
        # Tolérance : les autres produits et charges opérationnels subsistent
        self.assertLess(
            abs(rn), abs(v['CA']) * 0.01,
            "Le résultat au seuil de rentabilité doit être quasi nul, obtenu %s" % rn)

    def test_95_sr_auto_switch(self):
        """Le mode automatique privilégie les coûts variables si disponibles."""
        self._fill_balanced()
        self.analysis.sr_method = 'auto'
        self.assertEqual(self.stmt._get_values_dict()['SR_METHOD'], 2.0)
        self._set('IN_CHARGES_VARIABLES', 1500)
        self._set('IN_CHARGES_FIXES', 400)
        v = self.stmt._get_values_dict()
        self.assertEqual(v['SR_METHOD'], 1.0)
        self.assertAlmostEqual(v['TAUX_MCV'], (2000 - 1500) / 2000, places=4)
        self.assertAlmostEqual(v['SR'], 400 / v['TAUX_MCV'], places=2)

    def test_96_sr_forced_methods(self):
        """Les modes forcés ignorent la disponibilité des données."""
        self._fill_balanced()
        self._set('IN_CHARGES_VARIABLES', 1500)
        self._set('IN_CHARGES_FIXES', 400)
        self.analysis.sr_method = 'ebe'
        self.assertEqual(self.stmt._get_values_dict()['SR_METHOD'], 2.0)
        self.analysis.sr_method = 'variable'
        self.assertEqual(self.stmt._get_values_dict()['SR_METHOD'], 1.0)

    def test_97_point_mort_computable(self):
        """Point mort et marge de sécurité sont désormais toujours calculables."""
        self._fill_balanced()
        self.stmt.action_analyze()
        for code in ('D11', 'D12'):
            res = self.stmt.ratio_result_ids.filtered(lambda r, c=code: r.code == c)
            self.assertTrue(res, "Ratio %s absent" % code)
            self.assertFalse(
                res.is_na, "Ratio %s non calculable : %s" % (code, res.na_reason))
            self.assertTrue(res.value, "Ratio %s reste à zéro" % code)

    def test_98_sig_order_starts_with_turnover(self):
        """La cascade des SIG commence par le chiffre d'affaires."""
        self._fill_balanced()
        self.stmt.action_analyze()
        sig = self.stmt.aggregate_ids.filtered(
            lambda a: a.category == 'sig').sorted('sequence')
        self.assertTrue(sig)
        self.assertEqual(sig[0].code, 'CA',
                         "Le chiffre d'affaires doit ouvrir les soldes intermédiaires")
        codes = sig.mapped('code')
        # Les composantes suivent immédiatement, puis la cascade
        self.assertEqual(codes[1:3], ['PL_VENTE_MSE', 'PL_CA_PROD'])
        self.assertLess(codes.index('CA'), codes.index('MC'))
        self.assertLess(codes.index('VA'), codes.index('EBE'))
        self.assertLess(codes.index('EBE'), codes.index('RN'))

    def test_99_sr_aggregates_published(self):
        """Taux d'EBE et charges de structure figurent dans les agrégats."""
        self._fill_balanced()
        self.stmt.action_analyze()
        codes = self.stmt.aggregate_ids.mapped('code')
        for code in ('TAUX_EBE', 'CSI', 'SR'):
            self.assertIn(code, codes)

    # ==================================================================
    # Présentation du seuil de rentabilité
    # ==================================================================
    def test_100_breakeven_category(self):
        """Les agrégats du seuil ont leur propre catégorie."""
        self._fill_balanced()
        self.stmt.action_analyze()
        be = self.stmt.aggregate_ids.filtered(lambda a: a.category == 'breakeven')
        self.assertTrue(be)
        codes = be.mapped('code')
        for code in ('TAUX_EBE', 'CSI', 'SR', 'POINT_MORT', 'MARGE_SECURITE'):
            self.assertIn(code, codes)
        # Ils ne doivent plus polluer la CAF
        caf_codes = self.stmt.aggregate_ids.filtered(
            lambda a: a.category == 'caf').mapped('code')
        self.assertNotIn('TAUX_EBE', caf_codes)
        self.assertNotIn('SR', caf_codes)

    def test_101_aggregate_units(self):
        """Chaque agrégat porte l'unité qui convient à sa nature."""
        self._fill_balanced()
        self.stmt.action_analyze()

        def unit_of(code):
            return self.stmt.aggregate_ids.filtered(
                lambda a, c=code: a.code == c).unit

        self.assertEqual(unit_of('TAUX_EBE'), 'percent')
        self.assertEqual(unit_of('MARGE_SECURITE'), 'percent')
        self.assertEqual(unit_of('POINT_MORT'), 'days')
        self.assertEqual(unit_of('SR'), 'amount')
        self.assertEqual(unit_of('CSI'), 'amount')
        self.assertEqual(unit_of('EBE'), 'amount')

    def test_102_value_display_formatting(self):
        """La mise en forme respecte l'unité : un taux n'est pas un montant."""
        self._fill_balanced()
        self.stmt.action_analyze()
        taux = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'TAUX_EBE')
        self.assertIn('%', taux.value_display)
        self.assertNotIn('%', taux.value_display.replace('%', '', 1))
        # EBE = 120, CA = 2000 -> 6,00 %
        self.assertIn('6', taux.value_display)

        pm = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'POINT_MORT')
        self.assertTrue(pm.value_display.endswith('j'))

        sr = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'SR')
        self.assertNotIn('%', sr.value_display)

    def test_103_point_mort_aggregate_matches_ratio(self):
        """Agrégat et ratio donnent la même valeur."""
        self._fill_balanced()
        self.stmt.action_analyze()
        agg_pm = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'POINT_MORT')
        ratio_pm = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D11')
        self.assertAlmostEqual(agg_pm.amount, ratio_pm.value, places=2)

        agg_ms = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'MARGE_SECURITE')
        ratio_ms = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D12')
        # Le ratio est en pourcentage, l'agrégat en fraction
        self.assertAlmostEqual(agg_ms.amount * 100.0, ratio_ms.value, places=2)

    def test_104_breakeven_lines_follow_method(self):
        """Les lignes affichées s'adaptent à la méthode retenue."""
        self._fill_balanced()
        self.analysis.sr_method = 'ebe'
        self.stmt.action_analyze()
        mcv = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'MCV')
        self.assertFalse(mcv.amount, "La marge sur coûts variables doit rester nulle "
                                     "en méthode EBE")
        csi = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'CSI')
        self.assertTrue(csi.amount)

        self._set('IN_CHARGES_VARIABLES', 1500)
        self._set('IN_CHARGES_FIXES', 400)
        self.analysis.sr_method = 'variable'
        self.stmt.action_analyze()
        mcv = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'MCV')
        self.assertTrue(mcv.amount, "La marge sur coûts variables doit être calculée")

    def test_105_breakeven_annualized(self):
        """Sur une période courte, le taux ne bouge pas mais les flux sont annualisés."""
        semester = self.env['fa.statement'].create({
            'name': "S1", 'analysis_id': self.analysis.id, 'period_type': 'semester',
            'date_from': '2026-01-01', 'date_to': '2026-06-30'})
        for code, amount in (('PL_VENTE_MSE', 1000), ('PL_ACHAT_MSE', 700),
                             ('PL_PERSONNEL', 125), ('PL_DOTATIONS', 30),
                             ('PL_CH_FIN', 10), ('PL_IMP_EXIG', 5)):
            self._set_on(semester, code, amount)
        raw = semester._get_values_dict(annualized=False)
        ann = semester._get_values_dict(annualized=True)
        # Le taux est un rapport : identique dans les deux jeux
        self.assertAlmostEqual(raw['TAUX_EBE'], ann['TAUX_EBE'], places=6)
        # Les montants doublent
        self.assertAlmostEqual(ann['CSI'], raw['CSI'] * 2, places=2)
        self.assertAlmostEqual(ann['SR'], raw['SR'] * 2, places=2)

    # ==================================================================
    # Ratios du seuil de rentabilité : commentaires et recommandations
    # ==================================================================
    def test_106_breakeven_ratios_exist(self):
        """Les deux ratios propres à la méthode EBE sont présents."""
        for code, unit, direction in (('D13', 'times', 'higher'),
                                      ('D14', 'percent', 'lower')):
            ratio = self.env['fa.ratio'].search([('code', '=', code)], limit=1)
            self.assertTrue(ratio, "Ratio %s absent" % code)
            self.assertEqual(ratio.family, 'profitability')
            self.assertEqual(ratio.unit, unit)
            self.assertEqual(ratio.direction, direction)
            self.assertTrue(ratio.interpretation)
            self.assertTrue(ratio.rule_ids)

    def test_107_breakeven_ratios_computed(self):
        """D13 et D14 sont calculés et cohérents avec les agrégats."""
        self._fill_balanced()
        self.stmt.action_analyze()
        v = self.stmt._get_values_dict(annualized=True)

        d13 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D13')
        self.assertFalse(d13.is_na)
        self.assertAlmostEqual(d13.value, v['EBE'] / v['CSI'], places=3)

        d14 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D14')
        self.assertFalse(d14.is_na)
        self.assertAlmostEqual(d14.value, v['SR'] / v['CA'] * 100.0, places=2)

    def test_108_breakeven_ratios_consistency(self):
        """D14 et la marge de sécurité sont complémentaires à 100 %."""
        self._fill_balanced()
        self.stmt.action_analyze()
        d12 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D12')
        d14 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D14')
        self.assertAlmostEqual(d12.value + d14.value, 100.0, places=1)
        # Une couverture supérieure à 1 implique un seuil inférieur au CA
        d13 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D13')
        if d13.value > 1:
            self.assertLess(d14.value, 100.0)
        else:
            self.assertGreaterEqual(d14.value, 100.0)

    def test_109_breakeven_comments_and_reco(self):
        """Chaque ratio du seuil porte commentaire, action et explication."""
        self._fill_balanced()
        self.stmt.action_analyze()
        for code in ('D11', 'D12', 'D13', 'D14'):
            res = self.stmt.ratio_result_ids.filtered(lambda r, c=code: r.code == c)
            self.assertTrue(res, "Ratio %s absent des résultats" % code)
            self.assertFalse(res.is_na, "%s non calculable : %s" % (code, res.na_reason))
            self.assertTrue(res.comment, "%s sans commentaire" % code)
            self.assertTrue(res.recommendation, "%s sans recommandation" % code)
            self.assertTrue(res.interpretation, "%s sans explication" % code)
            self.assertTrue(res.appreciation, "%s sans appréciation" % code)

    def test_110_negative_safety_margin_wording(self):
        """Une marge de sécurité négative reçoit le bon texte."""
        self._fill_balanced()
        # Charges de structure alourdies : le CA passe sous le seuil
        self._set('PL_DOTATIONS', 200)
        self._set('PA_RESULTAT', self.stmt._get_values_dict()['RN'])
        self.stmt._compute_ratio_records()
        d12 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D12')
        if d12.value < 0:
            self.assertIn('négative', d12.comment)
            self.assertIn('en dessous du seuil', d12.comment)
            self.assertEqual(d12.appreciation, 'bad')

    def test_111_point_mort_beyond_year_wording(self):
        """Un point mort supérieur à 360 jours est signalé comme tel."""
        self._fill_balanced()
        self._set('PL_DOTATIONS', 200)
        self._set('PA_RESULTAT', self.stmt._get_values_dict()['RN'])
        self.stmt._compute_ratio_records()
        d11 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D11')
        if d11.value > 360:
            self.assertIn("au-delà de la durée d'un exercice", d11.comment)
            self.assertEqual(d11.appreciation, 'bad')

    def test_112_breakeven_sector_norms(self):
        """D13 et D14 disposent de normes sectorielles différenciées."""
        commerce = self.env.ref('mg_financial_analysis.sector_commerce')
        industry = self.env.ref('mg_financial_analysis.sector_industry')
        for code in ('D13', 'D14'):
            ratio = self.env['fa.ratio'].search([('code', '=', code)], limit=1)
            tc = ratio.get_thresholds(commerce)
            ti = ratio.get_thresholds(industry)
            self.assertTrue(tc['is_sector'], "%s sans norme négoce" % code)
            self.assertTrue(ti['is_sector'], "%s sans norme industrie" % code)
            self.assertNotEqual(
                tc['watch'], ti['watch'],
                "%s : les seuils négoce et industrie doivent différer" % code)

    def test_113_breakeven_vocabulary_updated(self):
        """Les textes ne parlent plus de coûts variables par défaut."""
        for code in ('D11', 'D12'):
            ratio = self.env['fa.ratio'].search([('code', '=', code)], limit=1)
            texts = ' '.join(
                (r.recommendation_tpl or '') for r in ratio.rule_ids)
            self.assertIn('charges de structure', texts.lower(),
                          "%s : vocabulaire non aligné sur la méthode EBE" % code)

    # ==================================================================
    # Applicabilité des ratios et arrondis d'affichage
    # ==================================================================
    def test_114_applicability_field(self):
        """Les ratios au dénominateur signé portent une condition."""
        for code in ('A2', 'A4', 'A8', 'B8', 'C7', 'D6', 'D7', 'F3'):
            ratio = self.env['fa.ratio'].search([('code', '=', code)], limit=1)
            self.assertTrue(ratio.applicability,
                            "%s devrait porter une condition d'applicabilité" % code)
            self.assertTrue(ratio.na_message,
                            "%s devrait expliquer pourquoi il est sans objet" % code)

    def test_115_negative_bfr_makes_b8_na(self):
        """Un BFR négatif rend la couverture du BFR sans objet, pas critique."""
        self._fill_balanced()
        # Crédit fournisseur supérieur aux stocks et créances : BFR négatif
        self._set('AC_STOCK', 100)
        self._set('AC_CLIENT', 100)
        self._set('PA_FOURN', 700)
        self._set('AC_IMMO_CORP', 700)
        self._set('AC_TRESO', 100)
        v = self.stmt._get_values_dict()
        self.assertLess(v['BFR'], 0, "Le jeu de test doit produire un BFR négatif")
        self.stmt._compute_ratio_records()
        b8 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B8')
        self.assertTrue(b8.is_na, "B8 doit être sans objet quand le BFR est négatif")
        self.assertNotEqual(b8.appreciation, 'bad',
                            "Un BFR négatif est favorable, pas critique")
        self.assertIn('sans objet', (b8.na_reason or '').lower())
        self.assertFalse(b8.recommendation,
                         "Aucune recommandation ne doit être produite")

    def test_116_negative_equity_makes_ratios_na(self):
        """Des capitaux propres négatifs neutralisent les ratios concernés."""
        self._set('PA_CAPITAL', 300)
        self._set('PA_AUTRES_CP', -400)      # capitaux propres négatifs
        self._set('AC_IMMO_CORP', 400)
        self._set('PA_FOURN', 500)
        self.stmt._compute_ratio_records()
        for code in ('A2', 'A8', 'C7', 'D7'):
            res = self.stmt.ratio_result_ids.filtered(lambda r, c=code: r.code == c)
            self.assertTrue(res.is_na,
                            "%s doit être sans objet si les capitaux propres "
                            "sont négatifs" % code)

    def test_117_b4_measures_treasury(self):
        """B4 exprime bien la trésorerie nette en jours d'activité."""
        self._fill_balanced()
        self.stmt.action_analyze()
        v = self.stmt._get_values_dict(annualized=True)
        b4 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B4')
        expected = (v['FRNG'] - v['BFR']) * 360 / v['CA']
        self.assertAlmostEqual(b4.value, expected, places=2)
        # Équivalent à la trésorerie nette rapportée au chiffre d'affaires
        self.assertAlmostEqual(b4.value, v['TN'] * 360 / v['CA'], places=2)

    def test_118_small_values_not_rounded_to_zero(self):
        """Une valeur non nulle inférieure à l'unité reste lisible."""
        Statement = self.env['fa.statement']
        self.assertEqual(Statement._fmt(0.309, 'days'), "0.3 jour")
        self.assertEqual(Statement._fmt(0.0, 'days'), "0 jours")
        self.assertEqual(Statement._fmt(175.0, 'days'), "175 jours")
        self.assertEqual(Statement._fmt(-11.41, 'days'), "-11 jours")
        self.assertEqual(Statement._fmt(0.0271, 'times'), "0.03")
        self.assertEqual(Statement._fmt(0.004, 'times'), "0.0040")
        self.assertIn('0.05', Statement._fmt(0.05, 'percent'))

    def test_119_aggregate_small_days_display(self):
        """Les agrégats en jours suivent la même règle d'affichage."""
        self._fill_balanced()
        self.stmt.action_analyze()
        agg = self.stmt.aggregate_ids.filtered(lambda a: a.unit == 'days')[:1]
        if agg and 0 < abs(agg.amount) < 1:
            self.assertIn('.', agg.value_display)

    def test_120_na_ratios_excluded_from_synthesis(self):
        """Un ratio sans objet ne pollue ni la synthèse ni les recommandations."""
        self._fill_balanced()
        self._set('AC_STOCK', 100)
        self._set('AC_CLIENT', 100)
        self._set('PA_FOURN', 700)
        self._set('AC_IMMO_CORP', 700)
        self._set('AC_TRESO', 100)
        self.stmt.action_analyze()
        syn = self.stmt.get_synthesis()
        for key in ('strengths', 'weaknesses', 'recommendations'):
            self.assertFalse(
                syn[key].filtered(lambda r: r.code == 'B8'),
                "B8 sans objet ne doit pas apparaître dans %s" % key)

    # ==================================================================
    # Précision de stockage et arrondis d'affichage
    # ==================================================================
    def test_121_storage_precision(self):
        """Les valeurs sont stockées avec assez de décimales."""
        checks = [
            ('fa.ratio.result', 'value', 4),
            ('fa.ratio.result', 'previous_value', 4),
            ('fa.ratio.result', 'sector_median', 4),
            ('fa.score', 'value', 4),
            ('fa.comparison.line', 'value1', 4),
            ('fa.comparison.line', 'variation_pct', 2),
            ('fa.statement.line', 'variation_pct', 2),
        ]
        for model, fname, expected in checks:
            field = self.env[model]._fields[fname]
            digits = field.digits
            self.assertTrue(digits, "%s.%s sans précision définie" % (model, fname))
            self.assertGreaterEqual(
                digits[1], expected,
                "%s.%s : %s décimales, %s attendues" % (model, fname, digits[1], expected))

    def test_122_synthesis_score_not_rounded_to_integer(self):
        """La note de synthèse garde ses décimales : les zones sont à seuils entiers."""
        field = self.env['fa.statement']._fields['score_synthesis']
        self.assertGreaterEqual(
            field.digits[1], 2,
            "Une note de 64,7 arrondie à 65 basculerait de la zone d'incertitude "
            "à la zone de sécurité")

    def test_123_appreciation_uses_exact_value(self):
        """L'appréciation est déterminée sur la valeur exacte, pas arrondie."""
        self._fill_balanced()
        self.stmt.action_analyze()
        sector = self.analysis.sector_id
        for res in self.stmt.ratio_result_ids.filtered(lambda r: not r.is_na):
            expected = res.ratio_id._evaluate_appreciation(
                res.value, res.ratio_id.get_thresholds(sector))
            forced = res.ratio_id.rule_ids.filtered('force_appreciation')
            if not forced:
                self.assertEqual(
                    res.appreciation, expected,
                    "%s : appréciation %s incohérente avec la valeur stockée %s"
                    % (res.code, res.appreciation, res.value))

    def test_124_display_never_contradicts_appreciation(self):
        """La valeur affichée ne doit jamais sembler contredire son appréciation."""
        self._fill_balanced()
        self.stmt.action_analyze()
        import re as _re
        sector = self.analysis.sector_id
        for res in self.stmt.ratio_result_ids.filtered(lambda r: not r.is_na):
            t = res.ratio_id.get_thresholds(sector)
            match = _re.search(r'-?[\d]+[.,]?[\d]*',
                               (res.value_display or '').replace('\u202f', ''))
            if not match:
                continue
            shown = float(match.group(0).replace(',', '.'))
            for threshold in (t['bad'], t['watch'], t['good']):
                if not threshold:
                    continue
                crossed = ((res.value < threshold <= shown)
                           or (shown <= threshold < res.value)
                           or (res.value > threshold >= shown)
                           or (shown >= threshold > res.value))
                self.assertFalse(
                    crossed,
                    "%s : valeur exacte %s affichée « %s » franchit le seuil %s"
                    % (res.code, res.value, res.value_display, threshold))

    def test_125_fmt_precise(self):
        """La mise en forme précise ajoute une décimale."""
        Statement = self.env['fa.statement']
        self.assertEqual(Statement._fmt_precise(1.1951, 'times'), "1.195")
        self.assertEqual(Statement._fmt_precise(59.6, 'days'), "59.6 jours")
        self.assertEqual(Statement._fmt_precise(4.96, 'percent'), "4.96 %")

    # ==================================================================
    # Contextualisation des constats
    # ==================================================================
    def test_126_aggregates_available_in_rules(self):
        """Les règles de commentaire accèdent aux agrégats financiers."""
        self._fill_balanced()
        self.stmt.action_analyze()
        ratio = self.env['fa.ratio'].search([('code', '=', 'B3')], limit=1)
        rule = ratio.rule_ids.filtered(lambda r: 'CBC' in (r.condition or ''))
        self.assertTrue(rule, "La règle contextuelle B3 doit exister")
        # La règle ne doit pas planter faute de variable
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B3')
        self.assertTrue(res.comment, "B3 doit produire un commentaire")

    def test_127_no_credit_line_advice_without_overdraft(self):
        """Sans découvert ni dette, on ne conseille pas une ligne de trésorerie."""
        self._fill_balanced()
        # Trésorerie positive, aucun concours bancaire
        self._set('PA_TRESO_PASSIF', 0)
        self._set('PA_EMPRUNT_NC', 0)
        self._set('AC_TRESO', 50)
        self._set('PA_FOURN', 670)
        self.stmt._compute_ratio_records()
        v = self.stmt._get_values_dict()
        if v['TN'] > 0 and v['CBC'] == 0:
            b3 = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'B3')
            if b3.value < 10:  # liquidité immédiate faible
                self.assertNotIn('ligne de trésorerie', (b3.recommendation or ''),
                                 "Ne pas recommander un financement à une "
                                 "entreprise sans découvert et à trésorerie positive")

    def test_128_leverage_without_financial_debt(self):
        """Un levier élevé sans dette bancaire est expliqué, pas condamné."""
        ratio = self.env['fa.ratio'].search([('code', '=', 'A8')], limit=1)
        rule = ratio.rule_ids.filtered(
            lambda r: 'DETTES_FIN' in (r.condition or ''))
        self.assertTrue(rule, "A8 doit distinguer le levier d'exploitation")
        self.assertIn('crédit fournisseur', rule[0].comment_tpl)
        self.assertNotIn('Réduire le levier par renforcement',
                         rule[0].recommendation_tpl)

    def test_129_supplier_delay_without_cash_problem(self):
        """Un délai fournisseur long à trésorerie saine est un risque opérationnel."""
        ratio = self.env['fa.ratio'].search([('code', '=', 'C4')], limit=1)
        rule = ratio.rule_ids.filtered(lambda r: 'TN' in (r.condition or ''))
        self.assertTrue(rule)
        self.assertIn('risque opérationnel', rule[0].recommendation_tpl)
        self.assertNotIn('ressources stables', rule[0].recommendation_tpl)

    def test_130_percent_aggregate_precision(self):
        """Un agrégat en pourcentage n'est pas arrondi par le champ monétaire."""
        self._fill_balanced()
        self.stmt.action_analyze()
        taux = self.stmt.aggregate_ids.filtered(lambda a: a.code == 'TAUX_EBE')
        self.assertTrue(taux)
        v = self.stmt._get_values_dict(annualized=True)
        # La valeur exacte est conservée hors du champ Monetary
        self.assertAlmostEqual(taux.ratio_value, v['TAUX_EBE'], places=6)
        # Et l'affichage la reflète
        expected = "%.2f %%" % (v['TAUX_EBE'] * 100.0)
        self.assertEqual(taux.value_display, expected)

    def test_131_percent_display_not_rounded_to_round_number(self):
        """Un taux de 11,26 % ne doit pas s'afficher 11,00 %."""
        agg = self.env['fa.aggregate'].new({
            'unit': 'percent', 'ratio_value': 0.112576, 'amount': 0.112576,
            'name': 'test', 'code': 'T', 'category': 'breakeven',
        })
        agg._compute_value_display()
        self.assertEqual(agg.value_display, "11.26 %")

    # ==================================================================
    # Cohérence et documentation du référentiel de ratios
    # ==================================================================
    def test_132_threshold_order_enforced(self):
        """Les seuils doivent être ordonnés selon le sens de lecture."""
        for ratio in self.env['fa.ratio'].search([]):
            b, w, g = (ratio.threshold_bad, ratio.threshold_watch,
                       ratio.threshold_good)
            if ratio.direction == 'higher':
                self.assertLessEqual(b, w, "%s : critique > vigilance" % ratio.code)
                self.assertLessEqual(w, g, "%s : vigilance > confort" % ratio.code)
            elif ratio.direction == 'lower':
                self.assertGreaterEqual(b, w, "%s : critique < vigilance" % ratio.code)
                self.assertGreaterEqual(w, g, "%s : vigilance < confort" % ratio.code)
            else:
                self.assertTrue(ratio.threshold_max,
                                "%s : plage optimale sans borne haute" % ratio.code)

    def test_133_threshold_order_constraint(self):
        """La contrainte refuse un ordre de seuils incohérent."""
        from odoo.exceptions import ValidationError
        ratio = self.env['fa.ratio'].search([('direction', '=', 'higher')], limit=1)
        with self.assertRaises(ValidationError):
            ratio.write({'threshold_bad': 99.0, 'threshold_watch': 1.0,
                         'threshold_good': 2.0})

    def test_134_norm_designates_watch_threshold(self):
        """La norme affichée doit correspondre au seuil de vigilance."""
        import re as _re
        mismatches = []
        for ratio in self.env['fa.ratio'].search([]):
            label = (ratio.norm_label or '').replace(' ', '')
            match = _re.search(r'([<>])\s*([\d,\.]+)', label)
            if not match:
                continue
            value = float(match.group(2).replace(',', '.'))
            if abs(value - ratio.threshold_watch) > 0.01:
                mismatches.append(
                    "%s : norme « %s » mais vigilance à %s"
                    % (ratio.code, ratio.norm_label, ratio.threshold_watch))
        self.assertFalse(
            mismatches,
            "La norme affichée doit désigner le seuil de vigilance : %s" % mismatches)

    def test_135_every_ratio_documented(self):
        """Chaque ratio porte les quatre volets de documentation."""
        gaps = []
        for ratio in self.env['fa.ratio'].search([]):
            for field, label in (('interpretation', 'définition'),
                                 ('calculation_note', 'calcul'),
                                 ('threshold_rationale', 'justification des seuils'),
                                 ('limits', "limites")):
                if not ratio[field]:
                    gaps.append("%s : %s manquante" % (ratio.code, label))
        self.assertFalse(gaps, "Documentation incomplète : %s" % gaps)

    def test_136_documentation_is_substantial(self):
        """Les textes de documentation ne sont pas des ébauches."""
        too_short = []
        for ratio in self.env['fa.ratio'].search([]):
            if len(ratio.threshold_rationale or '') < 80:
                too_short.append(ratio.code)
        self.assertFalse(
            too_short,
            "Justification des seuils trop succincte pour : %s" % too_short)

    def test_137_threshold_summary_generated(self):
        """La grille de lecture est produite pour chaque ratio."""
        for ratio in self.env['fa.ratio'].search([], limit=20):
            self.assertTrue(ratio.threshold_summary,
                            "%s sans grille de lecture" % ratio.code)
            self.assertIn('Critique', ratio.threshold_summary)

    def test_138_norm_respected_means_not_watch(self):
        """Une valeur qui atteint la norme ne doit plus être 'à surveiller'."""
        import re as _re
        problems = []
        for ratio in self.env['fa.ratio'].search([]):
            label = (ratio.norm_label or '').replace(' ', '')
            match = _re.search(r'([<>])\s*([\d,\.]+)', label)
            if not match:
                continue
            op = match.group(1)
            value = float(match.group(2).replace(',', '.'))
            probe = value * 1.01 if op == '>' else value * 0.99
            appreciation = ratio._evaluate_appreciation(probe)
            if appreciation in ('bad', 'watch'):
                problems.append(
                    "%s : %.2f respecte « %s » mais reste %s"
                    % (ratio.code, probe, ratio.norm_label, appreciation))
        self.assertFalse(problems, "Contradiction norme/appréciation : %s" % problems)

    def test_139_documentation_reaches_results(self):
        """La documentation remonte jusqu'aux résultats et au comparatif."""
        self._fill_balanced()
        self.stmt.action_analyze()
        res = self.stmt.ratio_result_ids.filtered(lambda r: r.code == 'D3')
        self.assertTrue(res.calculation_note)
        self.assertTrue(res.threshold_rationale)
        self.assertTrue(res.limits)
        self.assertTrue(res.threshold_summary)

    # ==================================================================
    # Contrôles de vraisemblance des informations complémentaires
    # ==================================================================
    def test_140_fictif_equals_financial_assets(self):
        """Confondre immobilisations financières et actifs fictifs est signalé."""
        self._fill_balanced()
        self._set('AC_IMMO_FIN', 50)
        self._set('AC_IMMO_CORP', 350)
        self._set('IN_ACTIF_FICTIF', 50)
        self.stmt._run_extra_checks()
        check = self.stmt.extra_check_ids.filtered(
            lambda c: c.code == 'FICTIF_IMMOFIN')
        self.assertTrue(check, "La confusion doit être détectée")
        self.assertEqual(check.severity, 'error')
        self.assertIn('valeur de réalisation', check.message)

    def test_141_vat_coefficient_checked(self):
        """Un coefficient de TVA improbable est signalé."""
        self._fill_balanced()
        v = self.stmt._get_values_dict()
        self._set('IN_CA_TTC', v['CA'] * 1.60)
        self.stmt._run_extra_checks()
        self.assertTrue(
            self.stmt.extra_check_ids.filtered(lambda c: c.code == 'CATTC_COEF'))
        # Un CA TTC inférieur au HT est une incohérence
        self._set('IN_CA_TTC', v['CA'] * 0.9)
        self.stmt._run_extra_checks()
        check = self.stmt.extra_check_ids.filtered(lambda c: c.code == 'CATTC_INF')
        self.assertTrue(check)
        self.assertEqual(check.severity, 'error')

    def test_142_double_loan_entry(self):
        """Saisir le même montant en emprunt et en remboursement est signalé."""
        self._fill_balanced()
        self._set('IN_EMPRUNTS_NOUVEAUX', 500)
        self._set('IN_REMB_EMPRUNTS', 500)
        self.stmt._run_extra_checks()
        check = self.stmt.extra_check_ids.filtered(
            lambda c: c.code == 'EMPRUNT_DOUBLE')
        self.assertTrue(check)
        self.assertEqual(check.severity, 'error')

    def test_143_leasing_without_debt(self):
        """Un crédit-bail sans dette déséquilibre le bilan financier."""
        self._fill_balanced()
        self._set('IN_CB_VNC', 200)
        self.stmt._run_extra_checks()
        check = self.stmt.extra_check_ids.filtered(
            lambda c: c.code == 'CB_SANS_DETTE')
        self.assertTrue(check)
        self.assertEqual(check.severity, 'error')

    def test_144_amortisation_exceeds_gross(self):
        """Des amortissements supérieurs au brut sont impossibles."""
        self._fill_balanced()
        self._set('IN_IMMO_BRUT', 100)
        self._set('IN_AMORT_CUMUL', 150)
        self.stmt._run_extra_checks()
        check = self.stmt.extra_check_ids.filtered(lambda c: c.code == 'AMORT_SUP')
        self.assertTrue(check)
        self.assertEqual(check.severity, 'error')

    def test_145_missing_headcount_flagged(self):
        """L'absence d'effectif est signalée avec les ratios impactés."""
        self._fill_balanced()
        self.stmt._run_extra_checks()
        check = self.stmt.extra_check_ids.filtered(
            lambda c: c.code == 'EFFECTIF_VIDE')
        self.assertTrue(check)
        self.assertIn('C8', check.impact)

    def test_146_no_false_positive_on_clean_data(self):
        """Une saisie cohérente ne déclenche aucune incohérence."""
        self._fill_balanced()
        v = self.stmt._get_values_dict()
        self._set('IN_CA_TTC', v['CA'] * 1.20)
        base = v['PL_ACHATS'] + v['PL_ACHAT_MSE'] + v['PL_SERV_EXT']
        self._set('IN_ACHATS_TTC', base * 1.20)
        self._set('IN_EFFECTIF', 10)
        self._set('IN_IMMO_BRUT', 500)
        self._set('IN_AMORT_CUMUL', 100)
        self.stmt._run_extra_checks()
        errors = self.stmt.extra_check_ids.filtered(lambda c: c.severity == 'error')
        self.assertFalse(
            errors, "Aucune incohérence attendue : %s" % errors.mapped('code'))

    def test_147_suggestions_fill_empty_fields(self):
        """Le pré-remplissage déduit les valeurs des états financiers."""
        self._fill_balanced()
        self.stmt.action_suggest_extra()
        v = self.stmt._get_values_dict()
        self.assertAlmostEqual(v['IN_CA_TTC'], v['CA'] * 1.20, delta=1.0)
        base = (v['PL_ACHATS'] + v['PL_ACHAT_MSE'] + v['PL_SERV_EXT'])
        self.assertAlmostEqual(v['IN_ACHATS_TTC'], base * 1.20, delta=1.0)

    def test_148_suggestions_never_overwrite(self):
        """Une valeur déjà saisie n'est jamais remplacée."""
        self._fill_balanced()
        self._set('IN_CA_TTC', 12345)
        self.stmt.action_suggest_extra()
        self.assertAlmostEqual(
            self.stmt._get_values_dict()['IN_CA_TTC'], 12345, delta=1.0)

    def test_149_stock_outil_retreatment(self):
        """Le stock outil bascule du circulant vers l'actif stable."""
        self._fill_balanced()
        before = self.stmt._get_values_dict()
        self._set('IN_STOCK_OUTIL', 100)
        after = self.stmt._get_values_dict()
        self.assertAlmostEqual(after['AI'], before['AI'] + 100, places=2)
        self.assertAlmostEqual(after['ACE'], before['ACE'] - 100, places=2)
        # L'équilibre financier reste vérifié
        self.assertAlmostEqual(
            after['FRNG'] - after['BFR'], after['TN_CTRL'], places=2)

    def test_150_no_dead_rubrics(self):
        """Chaque rubrique complémentaire doit être exploitée quelque part."""
        import glob
        import os
        import re
        from odoo.modules import get_module_path

        base = get_module_path('mg_financial_analysis')
        sources = ''
        for folder in ('models', 'wizard'):
            for path in glob.glob(os.path.join(base, folder, '*.py')):
                sources += open(path, encoding='utf-8').read()
        formulas = ' '.join(
            self.env['fa.ratio'].search([]).mapped('formula'))
        dead = []
        for rubric in self.env['fa.rubric'].search([
                ('statement_type', '=', 'extra')]):
            if rubric.code not in sources and rubric.code not in formulas:
                dead.append(rubric.code)
        self.assertFalse(dead, "Rubriques jamais exploitées : %s" % dead)

    # ==================================================================
    # Import de la saisie depuis un tableur
    # ==================================================================
    def _import_csv(self, text, overwrite=False):
        import base64
        wiz = self.env['fa.import.wizard'].create({
            'statement_id': self.stmt.id,
            'file_name': 'saisie.csv',
            'file_data': base64.b64encode(text.encode('utf-8')),
            'overwrite': overwrite,
        })
        wiz.action_preview()
        return wiz

    def test_151_import_preview_matches_codes(self):
        """L'aperçu reconnaît les codes du référentiel."""
        csv_text = (
            "Code;Rubrique;Brut;Amort.;Net;N-1\n"
            "AC_STOCK;Stocks;;;250;200\n"
            "PL_VENTE_MSE;Ventes;;;2000;1800\n"
            "FOO_BAR;Inconnu;;;1;0\n"
        )
        wiz = self._import_csv(csv_text)
        self.assertEqual(wiz.state, 'preview')
        stock = wiz.line_ids.filtered(lambda l: l.code == 'AC_STOCK')
        self.assertEqual(stock.status, 'ok')
        self.assertAlmostEqual(stock.amount_net, 250)
        self.assertAlmostEqual(stock.amount_previous, 200)
        unknown = wiz.line_ids.filtered(lambda l: l.code == 'FOO_BAR')
        self.assertEqual(unknown.status, 'unknown')
        self.assertFalse(unknown.apply)

    def test_152_import_apply_writes_amounts(self):
        """L'import renseigne les lignes de saisie."""
        csv_text = (
            "Code;Net\n"
            "AC_IMMO_CORP;400\n"
            "AC_STOCK;250\n"
            "PA_CAPITAL;300\n"
        )
        wiz = self._import_csv(csv_text, overwrite=True)
        wiz.action_apply()
        self.assertEqual(wiz.state, 'done')
        self.assertAlmostEqual(self.stmt._get_values_dict()['AC_STOCK'], 250)
        self.assertAlmostEqual(self.stmt._get_values_dict()['PA_CAPITAL'], 300)

    def test_153_import_does_not_overwrite_by_default(self):
        """Sans option, une saisie existante est conservée."""
        self._set('AC_STOCK', 999)
        csv_text = "Code;Net\nAC_STOCK;10\nAC_TRESO;50\n"
        wiz = self._import_csv(csv_text, overwrite=False)
        stock = wiz.line_ids.filtered(lambda l: l.code == 'AC_STOCK')
        self.assertFalse(stock.apply)
        treso = wiz.line_ids.filtered(lambda l: l.code == 'AC_TRESO')
        self.assertTrue(treso.apply)
        wiz.action_apply()
        self.assertAlmostEqual(self.stmt._get_values_dict()['AC_STOCK'], 999)
        self.assertAlmostEqual(self.stmt._get_values_dict()['AC_TRESO'], 50)

    def test_154_import_template_lists_input_codes(self):
        """Le modèle CSV contient toutes les rubriques de saisie."""
        import base64
        wiz = self.env['fa.import.wizard'].create({
            'statement_id': self.stmt.id,
            'file_data': base64.b64encode(b'x'),
            'file_name': 'x.csv',
        })
        wiz.action_download_template()
        content = base64.b64decode(wiz.file_data).decode('utf-8-sig')
        inputs = self.env['fa.rubric'].search([('line_type', '=', 'input')])
        missing = [r.code for r in inputs if r.code not in content]
        self.assertFalse(missing, "Codes absents du modèle : %s" % missing)

    def test_155_import_opens_from_statement(self):
        """Le bouton de la période ouvre l'assistant pré-rempli."""
        action = self.stmt.action_open_import()
        self.assertEqual(action['res_model'], 'fa.import.wizard')
        self.assertEqual(action['context']['default_statement_id'], self.stmt.id)
