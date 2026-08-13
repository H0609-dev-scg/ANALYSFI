# -*- coding: utf-8 -*-
"""Tableau des flux de trésorerie — PCG 2005, chapitre 5 (art. 250-1 à 250-5).

Le tableau présente les entrées et sorties de trésorerie de la période selon
leur origine, en trois catégories :

* **activités opérationnelles** : celles qui génèrent des produits, et toutes
  celles qui ne relèvent ni de l'investissement ni du financement ;
* **activités d'investissement** : acquisitions et cessions d'actifs à long
  terme et de placements non assimilés à de la trésorerie ;
* **activités de financement** : opérations modifiant l'importance et la
  composition des capitaux propres et des emprunts.

Les deux méthodes prévues par l'article 250-3 sont produites :

* la **méthode indirecte** part du résultat net et neutralise les charges et
  produits sans effet sur la trésorerie ainsi que les variations du besoin en
  fonds de roulement ;
* la **méthode directe** présente les rubriques brutes d'encaissement et de
  décaissement (clients, fournisseurs, personnel, impôts).

Un contrôle de bouclage compare systématiquement la variation de trésorerie
calculée à celle constatée au bilan.
"""
from odoo import models, fields, api, _


class FaCashflow(models.Model):
    _name = 'fa.cashflow'
    _description = "Tableau des flux de trésorerie"
    _order = 'statement_id, sequence, id'

    statement_id = fields.Many2one(
        'fa.statement', string="Période", required=True, ondelete='cascade', index=True)
    analysis_id = fields.Many2one(related='statement_id.analysis_id', store=True)
    currency_id = fields.Many2one(related='statement_id.currency_id', store=True)

    method = fields.Selection([
        ('indirect', "Méthode indirecte"),
        ('direct', "Méthode directe"),
    ], string="Méthode", required=True, index=True)

    category = fields.Selection([
        ('operating', "Flux liés aux activités opérationnelles"),
        ('investing', "Flux liés aux activités d'investissement"),
        ('financing', "Flux liés aux activités de financement"),
        ('summary', "Variation de trésorerie"),
    ], string="Catégorie", required=True, index=True)

    code = fields.Char(string="Code", index=True)
    name = fields.Char(string="Libellé", required=True)
    sequence = fields.Integer(string="Séquence", default=10)

    amount = fields.Monetary(string="Montant")
    amount_previous = fields.Monetary(string="Montant N-1")

    line_type = fields.Selection([
        ('detail', "Ligne de détail"),
        ('subtotal', "Sous-total"),
        ('total', "Total"),
        ('control', "Contrôle"),
    ], string="Type", default='detail')

    note = fields.Char(string="Précision")

    def name_get(self):
        return [(r.id, r.name) for r in self]


class FaStatementCashflow(models.Model):
    """Extension de la période : calcul et contrôle du tableau de flux."""
    _inherit = 'fa.statement'

    cashflow_ids = fields.One2many('fa.cashflow', 'statement_id', string="Flux de trésorerie")

    cf_operating = fields.Monetary(
        string="Flux opérationnels", compute='_compute_cashflow_summary', store=True)
    cf_investing = fields.Monetary(
        string="Flux d'investissement", compute='_compute_cashflow_summary', store=True)
    cf_financing = fields.Monetary(
        string="Flux de financement", compute='_compute_cashflow_summary', store=True)
    cf_variation = fields.Monetary(
        string="Variation de trésorerie", compute='_compute_cashflow_summary', store=True)
    cf_variation_bs = fields.Monetary(
        string="Variation constatée au bilan", compute='_compute_cashflow_summary', store=True)
    cf_gap = fields.Monetary(
        string="Écart de bouclage", compute='_compute_cashflow_summary', store=True)
    cf_is_balanced = fields.Boolean(
        string="Tableau bouclé", compute='_compute_cashflow_summary', store=True)
    cf_free_cashflow = fields.Monetary(
        string="Flux de trésorerie disponible", compute='_compute_cashflow_summary', store=True,
        help="Flux opérationnels diminués des investissements corporels et incorporels. "
             "Mesure ce qui reste réellement disponible pour rémunérer les apporteurs "
             "de capitaux.")

    @api.depends('cashflow_ids.amount', 'cashflow_ids.code', 'cashflow_ids.method')
    def _compute_cashflow_summary(self):
        for rec in self:
            lines = rec.cashflow_ids.filtered(lambda c: c.method == 'indirect')

            def val(code):
                line = lines.filtered(lambda c, k=code: c.code == k)[:1]
                return line.amount if line else 0.0

            rec.cf_operating = val('CF_OP_NET')
            rec.cf_investing = val('CF_INV_NET')
            rec.cf_financing = val('CF_FIN_NET')
            rec.cf_variation = val('CF_VARIATION')
            rec.cf_variation_bs = val('CF_VAR_BILAN')
            rec.cf_gap = rec.cf_variation - rec.cf_variation_bs
            tol = rec.analysis_id.tolerance or 1.0
            rec.cf_is_balanced = abs(rec.cf_gap) <= tol
            rec.cf_free_cashflow = val('CF_FREE')

    # ------------------------------------------------------------------
    # Variations de bilan
    # ------------------------------------------------------------------
    def _get_bs_variations(self):
        """Variations des postes de bilan entre la période précédente et celle-ci.

        Convention retenue : une augmentation d'actif consomme de la trésorerie,
        une augmentation de passif en dégage.
        """
        self.ensure_one()
        cur = self._get_values_dict()
        prev_stmt = self.previous_statement_id
        if prev_stmt:
            prev = prev_stmt._get_values_dict()
        else:
            # Sans période antérieure, on s'appuie sur la colonne N-1 saisie
            prev = {}
            for line in self.line_ids:
                if line.code:
                    prev[line.code] = line.amount_previous
            self._compute_subtotals(prev)
            self._compute_aggregates_dict(prev, 1.0)
        return cur, prev

    def _has_comparative(self):
        """Le tableau de flux exige un point de départ."""
        self.ensure_one()
        if self.previous_statement_id:
            return True
        return any(line.amount_previous for line in self.line_ids)

    # ------------------------------------------------------------------
    # Calcul
    # ------------------------------------------------------------------
    def _compute_cashflow_records(self):
        """Construit les deux tableaux, indirect et direct."""
        self.ensure_one()
        self.cashflow_ids.unlink()
        if not self._has_comparative():
            self.env['fa.cashflow'].create({
                'statement_id': self.id,
                'method': 'indirect',
                'category': 'summary',
                'code': 'CF_NA',
                'name': _("Tableau non calculable : aucune période de comparaison"),
                'line_type': 'control',
                'note': _("Renseignez la période de référence N-1 ou la colonne N-1 "
                          "des postes de bilan."),
            })
            return

        cur, prev = self._get_bs_variations()
        vals = []
        vals += self._build_indirect(cur, prev)
        vals += self._build_direct(cur, prev)
        self.env['fa.cashflow'].create(vals)

    def _delta(self, cur, prev, code):
        return cur.get(code, 0.0) - prev.get(code, 0.0)

    # ---------- Méthode indirecte ----------
    def _build_indirect(self, cur, prev):
        """Flux dérivés de l'équation du bilan : le bouclage est garanti.

        On part de l'identité comptable

            Trésorerie = Passifs (hors trésorerie passif)
                       − Actifs (hors trésorerie active)

        et l'on ventile la variation de chaque poste dans la catégorie de flux
        qui lui correspond. La somme des trois catégories égale donc par
        construction la variation de trésorerie constatée au bilan : un écart
        de bouclage ne peut provenir que d'une incohérence de saisie, jamais
        de la mécanique du tableau.
        """
        self.ensure_one()
        L = []
        seq = [0]

        def add(cat, code, name, amount, ltype='detail', note=False):
            seq[0] += 10
            L.append({
                'statement_id': self.id, 'method': 'indirect', 'category': cat,
                'code': code, 'name': name, 'amount': amount,
                'sequence': seq[0], 'line_type': ltype, 'note': note,
            })

        d = lambda code: self._delta(cur, prev, code)

        # ===== Éléments de base =====
        rn = cur.get('PA_RESULTAT', 0.0) or cur.get('RN', 0.0)
        dot = cur.get('PL_DOTATIONS', 0.0)
        rep = cur.get('PL_REPRISES', 0.0)
        vnc = cur.get('IN_VNC_CEDEE', 0.0)
        prod_cess = cur.get('IN_PROD_CESSION', 0.0)
        plus_value = prod_cess - vnc

        d_prov = d('PA_PROV_NC')
        d_immo = (d('AC_ECART_ACQ') + d('AC_IMMO_INC') + d('AC_IMMO_CORP')
                  + d('AC_IMMO_ENC'))
        d_immo_fin = d('AC_IMMO_FIN')

        # ===== A. Activités opérationnelles =====
        add('operating', 'CF_RN', _("Résultat net de l'exercice"), rn, 'subtotal')
        add('operating', 'CF_DOT',
            _("Dotations aux amortissements, provisions et pertes de valeur"), dot)
        add('operating', 'CF_REP', _("Reprises sur provisions et pertes de valeur"), -rep)
        if plus_value:
            add('operating', 'CF_PV',
                _("Résultat de cession d'immobilisations (éliminé)"), -plus_value,
                note=_("Neutralisé ici : le produit de cession est présenté en flux "
                       "d'investissement."))
        caf = rn + dot - rep - plus_value
        add('operating', 'CF_CAF', _("Capacité d'autofinancement"), caf, 'subtotal')

        # Variation du besoin en fonds de roulement
        d_stock, d_client, d_creance = d('AC_STOCK'), d('AC_CLIENT'), d('AC_AUT_CREANCE')
        d_fourn, d_impots, d_dettes = d('PA_FOURN'), d('PA_IMPOTS'), d('PA_AUT_DETTE_C')
        add('operating', 'CF_D_STOCK', _("Variation des stocks"), -d_stock)
        add('operating', 'CF_D_CLIENT', _("Variation des créances clients"), -d_client)
        add('operating', 'CF_D_AUTCREANCE', _("Variation des autres créances"), -d_creance)
        add('operating', 'CF_D_FOURN', _("Variation des dettes fournisseurs"), d_fourn)
        add('operating', 'CF_D_IMPOTS', _("Variation des dettes fiscales"), d_impots)
        add('operating', 'CF_D_AUTDETTE',
            _("Variation des autres dettes d'exploitation"), d_dettes)
        var_bfr = (-d_stock - d_client - d_creance + d_fourn + d_impots + d_dettes)
        add('operating', 'CF_VAR_BFR',
            _("Variation nette du besoin en fonds de roulement"), var_bfr, 'subtotal')

        # Impôts différés et autres dettes non courantes
        d_imp_diff = d('PA_IMP_DIFF') - d('AC_IMP_DIFF') + d('PA_AUT_DETTE_NC')
        if d_imp_diff:
            add('operating', 'CF_IMPDIFF',
                _("Variation des impôts différés et autres dettes non courantes"),
                d_imp_diff)

        op_net = caf + var_bfr + d_imp_diff
        add('operating', 'CF_OP_NET',
            _("Flux net de trésorerie généré par les activités opérationnelles (A)"),
            op_net, 'total')

        # ===== B. Activités d'investissement =====
        # Acquisitions reconstituées : variation nette + amortissements de la
        # période affectés aux immobilisations + valeur nette des biens sortis.
        dot_immo = dot - rep - d_prov
        acquisitions = d_immo + dot_immo + vnc
        declared = cur.get('IN_INVESTISSEMENTS', 0.0)
        note_acq = False
        if declared and abs(declared - acquisitions) > (self.analysis_id.tolerance or 1.0):
            note_acq = _(
                "Montant reconstitué à partir des variations de bilan. Les "
                "investissements déclarés dans les informations complémentaires "
                "s'élèvent à %(d)s : l'écart de %(e)s mérite vérification.",
                d='{:,.0f}'.format(declared).replace(',', ' '),
                e='{:,.0f}'.format(declared - acquisitions).replace(',', ' '))
        add('investing', 'CF_ACQ',
            _("Acquisitions d'immobilisations corporelles et incorporelles"),
            -acquisitions, note=note_acq)
        if prod_cess:
            add('investing', 'CF_CESS',
                _("Produits de cession d'immobilisations"), prod_cess)
        acq_fin = cur.get('IN_ACQ_IMMO_FIN', 0.0)
        cess_fin = cur.get('IN_CESS_IMMO_FIN', 0.0)
        if acq_fin or cess_fin:
            add('investing', 'CF_ACQFIN',
                _("Acquisitions d'immobilisations financières"), -acq_fin)
            add('investing', 'CF_CESSFIN',
                _("Cessions d'immobilisations financières"), cess_fin)
            residu_fin = d_immo_fin - acq_fin + cess_fin
            if abs(residu_fin) > (self.analysis_id.tolerance or 1.0):
                add('investing', 'CF_IMMOFIN_AUTRE',
                    _("Autres variations des immobilisations financières"),
                    -residu_fin)
        else:
            add('investing', 'CF_IMMOFIN',
                _("Variation des immobilisations financières"), -d_immo_fin,
                note=_("Un montant négatif traduit une acquisition de titres ou "
                       "l'octroi de prêts."))
        inv_net = -acquisitions + prod_cess - d_immo_fin
        add('investing', 'CF_INV_NET',
            _("Flux net de trésorerie lié aux activités d'investissement (B)"),
            inv_net, 'total')

        # ===== C. Activités de financement =====
        # Apports nets = variation des capitaux propres diminuée du résultat
        # de la période. Positif : augmentation de capital ; négatif :
        # distribution de dividendes ou prélèvements.
        d_cp = d('ST_CP')
        apports_nets = d_cp - rn
        dividendes = cur.get('IN_DIVIDENDES', 0.0)
        augm_capital = cur.get('IN_AUGM_CAPITAL', 0.0)
        if augm_capital or dividendes:
            add('financing', 'CF_CAPITAL',
                _("Augmentation de capital en numéraire"), augm_capital)
            subv = cur.get('IN_SUBV_RECUES', 0.0)
            if subv:
                add('financing', 'CF_SUBV',
                    _("Subventions d'investissement encaissées"), subv)
            add('financing', 'CF_DIV',
                _("Dividendes versés aux actionnaires"), -dividendes)
            residu = apports_nets - augm_capital + dividendes
            if abs(residu) > (self.analysis_id.tolerance or 1.0):
                add('financing', 'CF_CP_AUTRE',
                    _("Autres mouvements de capitaux propres"), residu,
                    note=_("Écarts de réévaluation, corrections d'erreurs ou "
                           "affectations directes en capitaux propres."))
        elif apports_nets:
            label = (_("Apports nets des associés")
                     if apports_nets > 0
                     else _("Distributions et prélèvements des associés"))
            add('financing', 'CF_CP_NET', label, apports_nets,
                note=_("Variation des capitaux propres hors résultat de la période. "
                       "Détaillez les dividendes et l'augmentation de capital dans "
                       "l'onglet « Informations complémentaires » pour une "
                       "présentation ventilée."))

        d_emprunt = d('PA_EMPRUNT_NC')
        nouveaux = cur.get('IN_EMPRUNTS_NOUVEAUX', 0.0)
        rembours = cur.get('IN_REMB_EMPRUNTS', 0.0)
        if nouveaux or rembours:
            add('financing', 'CF_EMPRUNTS', _("Emprunts contractés"), nouveaux)
            add('financing', 'CF_REMB', _("Remboursements d'emprunts"), -rembours)
            residu_emp = d_emprunt - nouveaux + rembours
            if abs(residu_emp) > (self.analysis_id.tolerance or 1.0):
                add('financing', 'CF_EMP_AUTRE',
                    _("Autres variations des emprunts"), residu_emp)
        else:
            label = (_("Nouveaux emprunts (net)") if d_emprunt >= 0
                     else _("Remboursements d'emprunts (net)"))
            add('financing', 'CF_EMP_NET', label, d_emprunt,
                note=_("Variation nette des emprunts. Renseignez les encaissements "
                       "et remboursements dans les informations complémentaires "
                       "pour les présenter séparément."))

        fin_net = apports_nets + d_emprunt
        add('financing', 'CF_FIN_NET',
            _("Flux net de trésorerie lié aux activités de financement (C)"),
            fin_net, 'total')

        # ===== Variation et bouclage =====
        variation = op_net + inv_net + fin_net
        add('summary', 'CF_VARIATION',
            _("Variation de trésorerie de la période (A + B + C)"), variation, 'total')

        treso_ouv = (prev.get('AC_TRESO', 0.0) + prev.get('AC_PLACEMENT', 0.0)
                     - prev.get('PA_TRESO_PASSIF', 0.0))
        if not treso_ouv and cur.get('IN_TRESO_OUVERTURE'):
            treso_ouv = cur.get('IN_TRESO_OUVERTURE', 0.0)
        treso_clo = (cur.get('AC_TRESO', 0.0) + cur.get('AC_PLACEMENT', 0.0)
                     - cur.get('PA_TRESO_PASSIF', 0.0))
        add('summary', 'CF_OUV', _("Trésorerie nette à l'ouverture"), treso_ouv, 'subtotal')
        add('summary', 'CF_CLO', _("Trésorerie nette à la clôture"), treso_clo, 'subtotal')
        add('summary', 'CF_VAR_BILAN', _("Variation constatée au bilan (contrôle)"),
            treso_clo - treso_ouv, 'control')
        add('summary', 'CF_ECART', _("Écart de bouclage"),
            variation - (treso_clo - treso_ouv), 'control',
            note=_("Doit être nul. Un écart signale une incohérence entre les "
                   "montants saisis et les variations de bilan."))
        add('summary', 'CF_FREE', _("Flux de trésorerie disponible (free cash flow)"),
            op_net - acquisitions, 'subtotal',
            note=_("Flux opérationnels diminués des investissements corporels "
                   "et incorporels."))
        return L

    # ---------- Méthode directe ----------
    def _build_direct(self, cur, prev):
        self.ensure_one()
        L = []
        seq = [0]

        def add(cat, code, name, amount, ltype='detail', note=False):
            seq[0] += 10
            L.append({
                'statement_id': self.id, 'method': 'direct', 'category': cat,
                'code': code, 'name': name, 'amount': amount,
                'sequence': seq[0], 'line_type': ltype, 'note': note,
            })

        # --- Encaissements clients ---
        ca_ttc = cur.get('IN_CA_TTC', 0.0) or cur.get('CA', 0.0) * 1.2
        d_client = self._delta(cur, prev, 'AC_CLIENT')
        encaissements = ca_ttc - d_client
        add('operating', 'CFD_CLIENT', _("Encaissements reçus des clients"), encaissements,
            note=_("Chiffre d'affaires TTC diminué de la variation des créances clients."))

        # --- Décaissements fournisseurs ---
        achats_ttc = cur.get('IN_ACHATS_TTC', 0.0) or (
            cur.get('PL_ACHATS', 0.0) + cur.get('PL_SERV_EXT', 0.0)
            + cur.get('PL_ACHAT_MSE', 0.0)) * 1.2
        d_fourn = self._delta(cur, prev, 'PA_FOURN')
        d_stock = self._delta(cur, prev, 'AC_STOCK')
        decaiss_fourn = achats_ttc + d_stock - d_fourn
        add('operating', 'CFD_FOURN', _("Sommes versées aux fournisseurs"), -decaiss_fourn,
            note=_("Achats TTC corrigés de la variation des stocks et du crédit fournisseur."))

        # --- Personnel ---
        personnel = cur.get('PL_PERSONNEL', 0.0)
        d_dettes_soc = self._delta(cur, prev, 'PA_AUT_DETTE_C')
        add('operating', 'CFD_PERSONNEL', _("Sommes versées au personnel et organismes sociaux"),
            -(personnel - d_dettes_soc))

        # --- Autres charges opérationnelles ---
        autres = cur.get('PL_AUT_CH_OP', 0.0) - cur.get('PL_AUT_PROD_OP', 0.0)
        add('operating', 'CFD_AUTRES', _("Autres décaissements opérationnels nets"), -autres)

        # --- Impôts et taxes ---
        taxes = cur.get('PL_IMPOTS_TAXES', 0.0)
        add('operating', 'CFD_TAXES', _("Impôts et taxes versés"), -taxes)

        interets = cur.get('IN_INTERETS_PAYES', 0.0) or cur.get('PL_CH_FIN', 0.0)
        add('operating', 'CFD_INTERETS', _("Intérêts payés"), -interets)

        recus = cur.get('IN_DIVIDENDES_RECUS', 0.0) or cur.get('PL_PROD_FIN', 0.0)
        add('operating', 'CFD_RECUS', _("Intérêts et dividendes reçus"), recus)

        impot = cur.get('IN_IMPOTS_PAYES', 0.0) or cur.get('PL_IMP_EXIG', 0.0)
        d_dette_fisc = self._delta(cur, prev, 'PA_IMPOTS')
        add('operating', 'CFD_IMPOT', _("Impôts sur les résultats payés"),
            -(impot - d_dette_fisc))

        net_direct = (encaissements - decaiss_fourn - (personnel - d_dettes_soc)
                      - autres - taxes - interets + recus - (impot - d_dette_fisc))
        add('operating', 'CFD_OP_NET',
            _("Flux net de trésorerie généré par les activités opérationnelles"),
            net_direct, 'total')

        # --- Rapprochement exigé par l'article 250-3 ---
        rai = cur.get('RAI', 0.0)
        add('summary', 'CFD_RAI', _("Résultat avant impôts de la période"), rai, 'subtotal')
        add('summary', 'CFD_ECART',
            _("Écart entre le flux opérationnel et le résultat avant impôts"),
            net_direct - rai, 'control',
            note=_("Cet écart traduit les charges et produits sans incidence sur la "
                   "trésorerie ainsi que les décalages d'encaissement et de "
                   "décaissement. Le rapprochement est requis par l'article 250-3."))
        return L

    # ------------------------------------------------------------------
    def get_cashflow(self, method='indirect', category=None):
        """Lignes du tableau, filtrées pour l'affichage et les rapports."""
        self.ensure_one()
        lines = self.cashflow_ids.filtered(lambda c: c.method == method)
        if category:
            lines = lines.filtered(lambda c: c.category == category)
        return lines.sorted('sequence')

    def action_open_cashflow(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Flux de trésorerie - %s") % self.name,
            'res_model': 'fa.cashflow',
            'view_mode': 'tree,form',
            'domain': [('statement_id', '=', self.id)],
            'context': {'search_default_indirect': 1, 'search_default_g_cat': 1},
        }
