# -*- coding: utf-8 -*-
"""Tableau de variation des capitaux propres — PCG 2005, chapitre 4 (art. 240-1 et 240-2).

Le tableau analyse les mouvements ayant affecté chacune des rubriques
constituant les capitaux propres au cours de l'exercice.

L'article 240-2 fixe les informations minimales à présenter :

1. le résultat net de l'exercice ;
2. les changements de méthodes comptables et corrections d'erreurs
   fondamentales imputés directement en capitaux propres ;
3. les autres produits et charges enregistrés directement en capitaux propres ;
4. les opérations en capital (augmentation, diminution, remboursement) ;
5. les distributions de résultat et affectations décidées au cours de l'exercice.

Comme pour le tableau des flux, le bouclage est garanti par construction :
une ligne d'ajustement résiduelle absorbe, colonne par colonne, tout écart
entre les mouvements identifiés et la variation réellement constatée au bilan.
Le consultant est ainsi immédiatement alerté d'un mouvement non documenté.
"""
from odoo import models, fields, api, _


# Colonnes du tableau : (code interne, rubrique de bilan, libellé)
EQUITY_COLUMNS = [
    ('capital', 'PA_CAPITAL', "Capital émis"),
    ('primes', 'PA_PRIMES', "Primes et réserves"),
    ('ecart_eval', 'PA_ECART_EVAL', "Écarts de réévaluation"),
    ('ecart_equiv', 'PA_ECART_EQUIV', "Écarts d'équivalence"),
    ('report', 'PA_AUTRES_CP', "Report à nouveau"),
    ('resultat', 'PA_RESULTAT', "Résultat de l'exercice"),
    ('minoritaires', 'PA_MINORITAIRES', "Intérêts minoritaires"),
]


class FaEquity(models.Model):
    _name = 'fa.equity'
    _description = "Ligne du tableau de variation des capitaux propres"
    _order = 'statement_id, sequence, id'

    statement_id = fields.Many2one(
        'fa.statement', string="Période", required=True, ondelete='cascade', index=True)
    analysis_id = fields.Many2one(related='statement_id.analysis_id', store=True)
    currency_id = fields.Many2one(related='statement_id.currency_id', store=True)

    code = fields.Char(string="Code", index=True)
    name = fields.Char(string="Mouvement", required=True)
    sequence = fields.Integer(string="Séquence", default=10)

    movement_type = fields.Selection([
        ('opening', "Solde d'ouverture"),
        ('result', "Résultat net de l'exercice"),
        ('method_change', "Changement de méthode ou correction d'erreur"),
        ('direct_equity', "Produits et charges imputés en capitaux propres"),
        ('capital', "Opérations en capital"),
        ('distribution', "Distributions et affectations"),
        ('other', "Autres mouvements"),
        ('closing', "Solde de clôture"),
    ], string="Nature du mouvement", required=True, index=True,
        help="Correspond aux catégories minimales de l'article 240-2 du PCG 2005.")

    # Une colonne par rubrique de capitaux propres
    amount_capital = fields.Monetary(string="Capital émis")
    amount_primes = fields.Monetary(string="Primes et réserves")
    amount_ecart_eval = fields.Monetary(string="Écarts de réévaluation")
    amount_ecart_equiv = fields.Monetary(string="Écarts d'équivalence")
    amount_report = fields.Monetary(string="Report à nouveau")
    amount_resultat = fields.Monetary(string="Résultat de l'exercice")
    amount_minoritaires = fields.Monetary(string="Intérêts minoritaires")
    amount_total = fields.Monetary(
        string="Total", compute='_compute_total', store=True)

    line_type = fields.Selection([
        ('balance', "Solde"),
        ('movement', "Mouvement"),
        ('control', "Contrôle"),
    ], string="Type de ligne", default='movement')

    note = fields.Char(string="Précision")

    @api.depends('amount_capital', 'amount_primes', 'amount_ecart_eval',
                 'amount_ecart_equiv', 'amount_report', 'amount_resultat',
                 'amount_minoritaires')
    def _compute_total(self):
        for rec in self:
            rec.amount_total = sum(
                rec['amount_%s' % col] for col, _r, _l in EQUITY_COLUMNS)

    def name_get(self):
        return [(r.id, r.name) for r in self]


class FaStatementEquity(models.Model):
    """Extension de la période : construction du tableau et contrôle de bouclage."""
    _inherit = 'fa.statement'

    equity_ids = fields.One2many('fa.equity', 'statement_id',
                                 string="Variation des capitaux propres")

    eq_opening = fields.Monetary(
        string="Capitaux propres à l'ouverture", compute='_compute_equity_summary', store=True)
    eq_closing = fields.Monetary(
        string="Capitaux propres à la clôture", compute='_compute_equity_summary', store=True)
    eq_variation = fields.Monetary(
        string="Variation des capitaux propres", compute='_compute_equity_summary', store=True)
    eq_unexplained = fields.Monetary(
        string="Mouvements non documentés", compute='_compute_equity_summary', store=True,
        help="Écart net entre les mouvements identifiés et la variation constatée.")
    eq_unexplained_gross = fields.Monetary(
        string="Reclassements internes", compute='_compute_equity_summary', store=True,
        help="Somme des écarts en valeur absolue, colonne par colonne. Un total net "
             "nul peut masquer un virement d'une rubrique à une autre, par exemple "
             "une mise en réserve : ce champ le révèle.")
    eq_is_documented = fields.Boolean(
        string="Variation entièrement documentée",
        compute='_compute_equity_summary', store=True)

    @api.depends('equity_ids.amount_total', 'equity_ids.code')
    def _compute_equity_summary(self):
        for rec in self:
            def line_of(code):
                return rec.equity_ids.filtered(lambda l, k=code: l.code == k)[:1]

            rec.eq_opening = (line_of('EQ_OPENING').amount_total
                              if line_of('EQ_OPENING') else 0.0)
            rec.eq_closing = (line_of('EQ_CLOSING').amount_total
                              if line_of('EQ_CLOSING') else 0.0)
            rec.eq_variation = rec.eq_closing - rec.eq_opening

            other = line_of('EQ_OTHER')
            rec.eq_unexplained = other.amount_total if other else 0.0
            # Le net peut être nul alors que des rubriques se compensent :
            # on mesure aussi le brut, colonne par colonne.
            rec.eq_unexplained_gross = sum(
                abs(other['amount_%s' % col]) for col, _r, _l in EQUITY_COLUMNS
            ) if other else 0.0
            tol = rec.analysis_id.tolerance or 1.0
            rec.eq_is_documented = rec.eq_unexplained_gross <= tol

    # ------------------------------------------------------------------
    def _compute_equity_records(self):
        """Construit le tableau de variation des capitaux propres."""
        self.ensure_one()
        self.equity_ids.unlink()
        if not self._has_comparative():
            self.env['fa.equity'].create({
                'statement_id': self.id,
                'code': 'EQ_NA',
                'name': _("Tableau non calculable : aucune période de comparaison"),
                'movement_type': 'opening',
                'line_type': 'control',
                'note': _("Renseignez la période de référence N-1 ou la colonne N-1 "
                          "des postes de capitaux propres."),
            })
            return

        cur, prev = self._get_bs_variations()
        vals = []
        seq = [0]

        def add(code, name, mtype, amounts, ltype='movement', note=False):
            seq[0] += 10
            row = {
                'statement_id': self.id, 'code': code, 'name': name,
                'movement_type': mtype, 'sequence': seq[0],
                'line_type': ltype, 'note': note,
            }
            for col, _rub, _lab in EQUITY_COLUMNS:
                row['amount_%s' % col] = amounts.get(col, 0.0)
            vals.append(row)
            return row

        # ===== Solde d'ouverture =====
        opening = {col: prev.get(rub, 0.0) for col, rub, _l in EQUITY_COLUMNS}
        add('EQ_OPENING', _("Solde au début de la période"), 'opening',
            opening, 'balance')

        # Cumul des mouvements identifiés, colonne par colonne
        moved = {col: 0.0 for col, _r, _l in EQUITY_COLUMNS}

        def register(amounts):
            for col, amount in amounts.items():
                moved[col] = moved.get(col, 0.0) + amount

        # ===== 1. Affectation du résultat antérieur =====
        # Le résultat de la période précédente quitte sa colonne : il est
        # distribué, mis en réserve ou reporté à nouveau.
        prev_result = prev.get('PA_RESULTAT', 0.0)
        dividendes = cur.get('IN_DIVIDENDES', 0.0)
        if prev_result:
            mise_en_reserve = prev_result - dividendes
            amounts = {'resultat': -prev_result, 'report': mise_en_reserve}
            add('EQ_AFFECT', _("Affectation du résultat de la période précédente"),
                'distribution', amounts,
                note=_("Le résultat antérieur est transféré en report à nouveau, "
                       "sous déduction des distributions décidées."))
            register(amounts)

        # ===== 2. Distributions de dividendes =====
        if dividendes:
            amounts = {'report': -dividendes}
            add('EQ_DIV', _("Dividendes distribués"), 'distribution', amounts)
            register(amounts)

        # ===== 3. Opérations en capital =====
        augm = cur.get('IN_AUGM_CAPITAL', 0.0)
        if augm:
            amounts = {'capital': augm}
            add('EQ_CAPITAL', _("Augmentation de capital en numéraire"),
                'capital', amounts)
            register(amounts)
        else:
            # Variation de capital constatée au bilan, non documentée par ailleurs
            d_capital = cur.get('PA_CAPITAL', 0.0) - prev.get('PA_CAPITAL', 0.0)
            if d_capital:
                label = (_("Augmentation de capital") if d_capital > 0
                         else _("Réduction ou remboursement de capital"))
                amounts = {'capital': d_capital}
                add('EQ_CAPITAL', label, 'capital', amounts,
                    note=_("Mouvement déduit de la variation du poste au bilan."))
                register(amounts)

        # ===== 4. Écarts de réévaluation et d'équivalence =====
        # Produits et charges enregistrés directement en capitaux propres.
        for col, rub, lab in (('ecart_eval', 'PA_ECART_EVAL',
                               _("Variation des écarts de réévaluation")),
                              ('ecart_equiv', 'PA_ECART_EQUIV',
                               _("Variation des écarts d'équivalence"))):
            delta = cur.get(rub, 0.0) - prev.get(rub, 0.0)
            if delta:
                amounts = {col: delta}
                add('EQ_%s' % col.upper(), lab, 'direct_equity', amounts)
                register(amounts)

        # ===== 5. Résultat net de la période =====
        result = cur.get('PA_RESULTAT', 0.0)
        if result:
            amounts = {'resultat': result}
            add('EQ_RESULT', _("Résultat net de la période"), 'result', amounts)
            register(amounts)

        # ===== 6. Intérêts minoritaires =====
        d_mino = cur.get('PA_MINORITAIRES', 0.0) - prev.get('PA_MINORITAIRES', 0.0)
        if d_mino:
            amounts = {'minoritaires': d_mino}
            add('EQ_MINO', _("Variation des intérêts minoritaires"), 'other', amounts)
            register(amounts)

        # ===== 7. Ajustement résiduel : garantit le bouclage =====
        closing = {col: cur.get(rub, 0.0) for col, rub, _l in EQUITY_COLUMNS}
        residual = {
            col: closing[col] - opening[col] - moved.get(col, 0.0)
            for col, _r, _l in EQUITY_COLUMNS
        }
        tol = self.analysis_id.tolerance or 1.0
        has_residual = any(abs(x) > tol for x in residual.values())
        net_residual = sum(residual.values())
        is_reclass = has_residual and abs(net_residual) <= tol

        if is_reclass:
            # Les colonnes se compensent : il s'agit d'un virement interne,
            # typiquement une mise en réserve ou une incorporation au capital.
            moved_cols = [lab for col, _r, lab in EQUITY_COLUMNS
                          if abs(residual[col]) > tol]
            label = _("Reclassements entre rubriques de capitaux propres")
            note = _(
                "Ces mouvements se compensent : le total des capitaux propres est "
                "inchangé, seule leur répartition évolue (%(cols)s). Il s'agit le "
                "plus souvent d'une mise en réserve ou d'une incorporation au "
                "capital. À confirmer avec le procès-verbal d'assemblée.",
                cols=", ".join(moved_cols))
            mtype = 'other'
        elif has_residual:
            label = _("Autres mouvements non documentés")
            note = _(
                "Écart entre les mouvements identifiés et la variation constatée "
                "au bilan. Il peut s'agir d'un changement de méthode comptable, "
                "d'une correction d'erreur fondamentale ou d'un mouvement non "
                "renseigné dans les informations complémentaires. "
                "À expliquer dans l'annexe des états financiers.")
            mtype = 'method_change'
        else:
            label = _("Autres mouvements")
            note = False
            mtype = 'other'
        add('EQ_OTHER', label, mtype, residual, note=note)

        # ===== Solde de clôture =====
        add('EQ_CLOSING', _("Solde à la fin de la période"), 'closing',
            closing, 'balance')

        # ===== Contrôle =====
        total_open = sum(opening.values())
        total_close = sum(closing.values())
        add('EQ_CONTROL', _("Variation nette des capitaux propres"), 'closing',
            {col: closing[col] - opening[col] for col, _r, _l in EQUITY_COLUMNS},
            'control',
            note=_("Passage de %(o)s à %(c)s.",
                   o='{:,.0f}'.format(total_open).replace(',', '\u202f'),
                   c='{:,.0f}'.format(total_close).replace(',', '\u202f')))

        self.env['fa.equity'].create(vals)

    def get_equity_table(self):
        """Lignes du tableau pour l'affichage et les rapports."""
        self.ensure_one()
        return self.equity_ids.sorted('sequence')

    def action_open_equity(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Variation des capitaux propres - %s") % self.name,
            'res_model': 'fa.equity',
            'view_mode': 'tree',
            'domain': [('statement_id', '=', self.id)],
        }
