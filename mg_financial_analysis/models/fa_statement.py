# -*- coding: utf-8 -*-
import logging
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class FaStatement(models.Model):
    """État financier d'une période : porte la saisie et déclenche l'analyse."""
    _name = 'fa.statement'
    _description = "État financier d'une période"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, id desc'

    name = fields.Char(string="Libellé", required=True, tracking=True)
    analysis_id = fields.Many2one(
        'fa.analysis', string="Dossier d'analyse", required=True,
        ondelete='cascade', index=True, tracking=True)
    partner_id = fields.Many2one(related='analysis_id.partner_id', store=True, string="Client")
    company_id = fields.Many2one(related='analysis_id.company_id', store=True)
    currency_id = fields.Many2one(related='analysis_id.currency_id', store=True)
    show_gross = fields.Boolean(related='analysis_id.show_gross')
    activity_mode = fields.Selection(related='analysis_id.activity_mode')
    sector_id = fields.Many2one(related='analysis_id.sector_id', store=True,
                                string="Secteur d'activité")

    period_type = fields.Selection([
        ('annual', "Annuel"),
        ('semester', "Semestriel"),
        ('quarter', "Trimestriel"),
        ('interim', "Intermédiaire"),
    ], string="Type de période", required=True, default='annual', tracking=True)

    date_from = fields.Date(string="Du", required=True, tracking=True)
    date_to = fields.Date(string="Au", required=True, tracking=True)
    duration_months = fields.Integer(
        string="Durée (mois)", compute='_compute_duration', store=True,
        help="Sert à l'annualisation des flux pour comparer des périodes inégales.")

    is_audited = fields.Boolean(
        string="États audités", default=False,
        help="Si non coché, une réserve est mentionnée dans le rapport.")

    previous_statement_id = fields.Many2one(
        'fa.statement', string="Période de référence (N-1)",
        domain="[('analysis_id', '=', analysis_id), ('id', '!=', id)]",
        help="Période servant de base de comparaison pour les variations.")

    line_ids = fields.One2many(
        'fa.statement.line', 'statement_id', string="Lignes", copy=True)

    # Sous-ensembles pour un affichage par onglet
    asset_line_ids = fields.One2many(
        'fa.statement.line', 'statement_id', string="Bilan Actif",
        domain=[('statement_type', '=', 'bs_asset')])
    liability_line_ids = fields.One2many(
        'fa.statement.line', 'statement_id', string="Bilan Passif",
        domain=[('statement_type', '=', 'bs_liability')])
    pl_line_ids = fields.One2many(
        'fa.statement.line', 'statement_id', string="Compte de résultat",
        domain=[('statement_type', '=', 'pl')])
    extra_line_ids = fields.One2many(
        'fa.statement.line', 'statement_id', string="Informations complémentaires",
        domain=[('statement_type', '=', 'extra')])

    aggregate_ids = fields.One2many('fa.aggregate', 'statement_id', string="Agrégats")
    ratio_result_ids = fields.One2many('fa.ratio.result', 'statement_id', string="Ratios")
    restatement_ids = fields.One2many('fa.restatement.line', 'statement_id', string="Retraitements")
    score_ids = fields.One2many('fa.score', 'statement_id', string="Scores de risque")
    score_synthesis = fields.Float(
        string="Note de synthèse", compute='_compute_score_summary', store=True,
        digits=(16, 2), group_operator=False,
        help="Note sur 100. Stockée avec deux décimales : la zone de risque "
             "est déterminée par des seuils entiers, un arrondi ferait basculer "
             "une note de 64,7 en zone de sécurité.")
    risk_zone = fields.Selection([
        ('distress', "Zone de danger"),
        ('grey', "Zone d'incertitude"),
        ('safe', "Zone de sécurité"),
    ], string="Zone de risque", compute='_compute_score_summary', store=True)

    # ------------------------------------------------------------------
    # Contrôles d'équilibre
    # ------------------------------------------------------------------
    total_asset = fields.Monetary(string="Total Actif", compute='_compute_checks', store=True)
    total_liability = fields.Monetary(string="Total Passif", compute='_compute_checks', store=True)
    balance_check = fields.Monetary(string="Écart Actif - Passif", compute='_compute_checks', store=True)
    is_balanced = fields.Boolean(string="Bilan équilibré", compute='_compute_checks', store=True)

    net_result_pl = fields.Monetary(string="Résultat net (CR)", compute='_compute_checks', store=True)
    net_result_bs = fields.Monetary(string="Résultat net (Bilan)", compute='_compute_checks', store=True)
    result_check = fields.Monetary(string="Écart de résultat", compute='_compute_checks', store=True)
    is_result_ok = fields.Boolean(string="Résultat cohérent", compute='_compute_checks', store=True)

    warning_message = fields.Text(string="Avertissements", compute='_compute_checks')

    state = fields.Selection([
        ('draft', "Brouillon"),
        ('confirmed', "Validé"),
        ('analyzed', "Analysé"),
    ], string="État", default='draft', tracking=True)

    note = fields.Html(string="Notes et faits marquants")
    seasonality_note = fields.Text(
        string="Note de saisonnalité",
        help="À renseigner pour les périodes infra-annuelles : l'activité est-elle "
             "régulière sur l'année ? Cette note figure dans le rapport.")

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    @api.depends('date_from', 'date_to')
    def _compute_duration(self):
        for rec in self:
            if rec.date_from and rec.date_to:
                delta = relativedelta(rec.date_to + relativedelta(days=1), rec.date_from)
                rec.duration_months = max(1, delta.years * 12 + delta.months)
            else:
                rec.duration_months = 12

    # Rubriques strictement nécessaires aux contrôles d'équilibre : évite de
    # reconstruire le dictionnaire complet à chaque frappe dans le formulaire.
    _CHECK_CODES = (
        'AC_ECART_ACQ', 'AC_IMMO_INC', 'AC_IMMO_CORP', 'AC_IMMO_ENC', 'AC_IMMO_FIN',
        'AC_IMP_DIFF', 'AC_STOCK', 'AC_CLIENT', 'AC_AUT_CREANCE', 'AC_PLACEMENT',
        'AC_TRESO', 'PA_CAPITAL', 'PA_PRIMES', 'PA_ECART_EVAL', 'PA_ECART_EQUIV',
        'PA_AUTRES_CP', 'PA_RESULTAT', 'PA_MINORITAIRES', 'PA_EMPRUNT_NC',
        'PA_IMP_DIFF', 'PA_AUT_DETTE_NC', 'PA_PROV_NC', 'PA_FOURN', 'PA_IMPOTS',
        'PA_AUT_DETTE_C', 'PA_TRESO_PASSIF',
        'PL_VENTE_MSE', 'PL_ACHAT_MSE', 'PL_VAR_STOCK_MSE', 'PL_CA_PROD',
        'PL_PROD_STOCK', 'PL_PROD_IMMO', 'PL_ACHATS', 'PL_SERV_EXT', 'PL_SUBV_EXPL',
        'PL_PERSONNEL', 'PL_IMPOTS_TAXES', 'PL_AUT_PROD_OP', 'PL_AUT_CH_OP',
        'PL_DOTATIONS', 'PL_REPRISES', 'PL_PROD_FIN', 'PL_CH_FIN', 'PL_IMP_EXIG',
        'PL_IMP_DIFF_CR', 'PL_EXTRA_PROD', 'PL_EXTRA_CH',
        'PL_TOT_PROD', 'PL_TOT_CH',
    )

    def _get_check_values(self):
        """Dictionnaire réduit aux seules rubriques utiles aux contrôles."""
        self.ensure_one()
        v = {c: 0.0 for c in self._CHECK_CODES}
        for line in self.line_ids:
            code = line.code
            if code in v:
                v[code] = line.amount_net
        self._compute_subtotals(v)
        return v

    @api.depends('line_ids.amount_net', 'line_ids.rubric_id')
    def _compute_checks(self):
        for rec in self:
            data = rec._get_check_values()
            tol = rec.analysis_id.tolerance or 1.0
            rec.total_asset = data.get('T_ACTIF', 0.0)
            rec.total_liability = data.get('T_PASSIF', 0.0)
            rec.balance_check = rec.total_asset - rec.total_liability
            rec.is_balanced = abs(rec.balance_check) <= tol

            rec.net_result_pl = data.get('RN', 0.0)
            rec.net_result_bs = data.get('PA_RESULTAT', 0.0)
            rec.result_check = rec.net_result_pl - rec.net_result_bs
            rec.is_result_ok = abs(rec.result_check) <= tol

            warnings = []
            if not rec.is_balanced and (rec.total_asset or rec.total_liability):
                warnings.append(_(
                    "Le bilan n'est pas équilibré : écart de %(gap)s. "
                    "Vérifiez la saisie de l'actif et du passif.",
                    gap='{:,.0f}'.format(rec.balance_check).replace(',', ' ')))
            if not rec.is_result_ok and (rec.net_result_pl or rec.net_result_bs):
                warnings.append(_(
                    "Le résultat du compte de résultat (%(pl)s) diffère de celui inscrit "
                    "au bilan (%(bs)s).",
                    pl='{:,.0f}'.format(rec.net_result_pl).replace(',', ' '),
                    bs='{:,.0f}'.format(rec.net_result_bs).replace(',', ' ')))
            if data.get('ST_CP', 0.0) < 0:
                warnings.append(_(
                    "Situation nette négative : les capitaux propres sont négatifs. "
                    "Obligation de reconstitution des capitaux propres à examiner."))
            if data.get('AC_STOCK', 0.0) < 0:
                warnings.append(_("Le montant des stocks est négatif, ce qui est anormal."))

            # RG-04 : cohérence entre les totaux déclarés et le résultat calculé
            tot_prod = data.get('PL_TOT_PROD', 0.0)
            tot_ch = data.get('PL_TOT_CH', 0.0)
            if tot_prod or tot_ch:
                ecart = (tot_prod - tot_ch) - data.get('RNAO', 0.0)
                if abs(ecart) > tol:
                    warnings.append(_(
                        "Total des produits moins total des charges (%(d)s) ne "
                        "correspond pas au résultat net des activités ordinaires "
                        "calculé (%(r)s) : écart de %(e)s.",
                        d='{:,.0f}'.format(tot_prod - tot_ch).replace(',', ' '),
                        r='{:,.0f}'.format(data.get('RNAO', 0.0)).replace(',', ' '),
                        e='{:,.0f}'.format(ecart).replace(',', ' ')))

            # Anomalies de saisie fréquentes
            ca_ctrl = data.get('CA', 0.0)
            if ca_ctrl and data.get('AC_STOCK', 0.0) > ca_ctrl:
                warnings.append(_(
                    "Le stock excède le chiffre d'affaires de la période : "
                    "vérifiez la saisie ou justifiez ce niveau dans les notes."))
            capital = data.get('PA_CAPITAL', 0.0)
            if capital > 0 and 0 < data.get('ST_CP', 0.0) < capital / 2:
                warnings.append(_(
                    "Les capitaux propres sont inférieurs à la moitié du capital "
                    "social : la situation relève des dispositions relatives à la "
                    "reconstitution des capitaux propres."))
            rec.warning_message = "\n".join(warnings) if warnings else False

    # ------------------------------------------------------------------
    # Dictionnaire de valeurs : socle de tous les calculs
    # ------------------------------------------------------------------
    def _get_values_dict(self, annualized=False):
        """Retourne {code_rubrique: montant} incluant les sous-totaux et agrégats.

        :param annualized: si True, les flux du compte de résultat sont ramenés à 12 mois.
        """
        self.ensure_one()
        values = {}
        for line in self.line_ids:
            if line.rubric_id:
                values[line.rubric_id.code] = line.amount_net

        # Toutes les rubriques connues valent 0 par défaut : évite les NameError
        all_codes = self.env['fa.rubric'].search([]).mapped('code')
        for code in all_codes:
            values.setdefault(code, 0.0)

        coef = 1.0
        if annualized and self.duration_months and self.duration_months != 12:
            coef = 12.0 / self.duration_months

        self._compute_subtotals(values)
        self._compute_aggregates_dict(values, coef)
        return values

    def _compute_subtotals(self, v):
        """Calcule les sous-totaux du bilan et du compte de résultat."""
        # --- BILAN ACTIF ---
        v['ST_ANC'] = (v['AC_ECART_ACQ'] + v['AC_IMMO_INC'] + v['AC_IMMO_CORP']
                       + v['AC_IMMO_ENC'] + v['AC_IMMO_FIN'] + v['AC_IMP_DIFF'])
        v['ST_AC'] = (v['AC_STOCK'] + v['AC_CLIENT'] + v['AC_AUT_CREANCE']
                      + v['AC_PLACEMENT'] + v['AC_TRESO'])
        v['T_ACTIF'] = v['ST_ANC'] + v['ST_AC']

        # --- BILAN PASSIF ---
        v['ST_CP'] = (v['PA_CAPITAL'] + v['PA_PRIMES'] + v['PA_ECART_EVAL']
                      + v['PA_ECART_EQUIV'] + v['PA_AUTRES_CP'] + v['PA_RESULTAT']
                      + v['PA_MINORITAIRES'])
        v['ST_PNC'] = (v['PA_EMPRUNT_NC'] + v['PA_IMP_DIFF'] + v['PA_AUT_DETTE_NC']
                       + v['PA_PROV_NC'])
        v['ST_PC'] = (v['PA_FOURN'] + v['PA_IMPOTS'] + v['PA_AUT_DETTE_C']
                      + v['PA_TRESO_PASSIF'])
        v['T_PASSIF'] = v['ST_CP'] + v['ST_PNC'] + v['ST_PC']

        # --- COMPTE DE RESULTAT ---
        # Marge commerciale (activité de négoce)
        v['MC'] = v['PL_VENTE_MSE'] - v['PL_ACHAT_MSE'] - v['PL_VAR_STOCK_MSE']
        # Production de l'exercice
        v['PROD'] = v['PL_CA_PROD'] + v['PL_PROD_STOCK'] + v['PL_PROD_IMMO']
        # Chiffre d'affaires total
        v['CA'] = v['PL_VENTE_MSE'] + v['PL_CA_PROD']
        # Consommation de l'exercice
        v['CONSO'] = v['PL_ACHATS'] + v['PL_SERV_EXT']
        # Valeur ajoutée
        v['VA'] = v['MC'] + v['PROD'] - v['CONSO']
        # Excédent brut d'exploitation
        v['EBE'] = v['VA'] + v['PL_SUBV_EXPL'] - v['PL_PERSONNEL'] - v['PL_IMPOTS_TAXES']
        # Résultat opérationnel
        v['REX'] = (v['EBE'] + v['PL_AUT_PROD_OP'] - v['PL_AUT_CH_OP']
                    - v['PL_DOTATIONS'] + v['PL_REPRISES'])
        # Résultat financier
        v['RF'] = v['PL_PROD_FIN'] - v['PL_CH_FIN']
        # Résultat avant impôts
        v['RAI'] = v['REX'] + v['RF']
        # Résultat net des activités ordinaires
        v['RNAO'] = v['RAI'] - v['PL_IMP_EXIG'] - v['PL_IMP_DIFF_CR']
        # Résultat net de l'exercice
        v['RN'] = v['RNAO'] + v['PL_EXTRA_PROD'] - v['PL_EXTRA_CH']

    def _compute_aggregates_dict(self, v, coef=1.0):
        """Calcule les agrégats du bilan financier et la CAF.

        :param coef: coefficient d'annualisation appliqué aux flux.
        """
        # ---- Retraitements optionnels ----
        eene = v.get('IN_EENE', 0.0)                    # effets escomptés non échus
        cb_net = v.get('IN_CB_VNC', 0.0)                # crédit-bail : valeur nette
        cb_lt = v.get('IN_CB_DETTE_LT', 0.0)            # crédit-bail : dette > 1 an
        cb_ct = v.get('IN_CB_DETTE_CT', 0.0)            # crédit-bail : dette < 1 an
        fictif = v.get('IN_ACTIF_FICTIF', 0.0)          # actifs fictifs
        emprunt_ct = v.get('IN_EMPRUNT_MOINS_1AN', 0.0) # part < 1 an des emprunts LT
        dividendes = v.get('IN_DIVIDENDES', 0.0)

        # ---- Grandes masses du bilan financier ----
        # Le stock outil est la fraction du stock qui ne descend jamais en
        # dessous d'un plancher : elle immobilise durablement de la trésorerie
        # et relève donc de l'actif stable, non du circulant (retraitement R4).
        stock_outil = min(v.get('IN_STOCK_OUTIL', 0.0), v.get('AC_STOCK', 0.0))
        v['STOCK_OUTIL'] = stock_outil
        v['AI'] = v['ST_ANC'] + cb_net - fictif + stock_outil       # actif immobilisé retraité
        v['CP_RETRAITE'] = v['ST_CP'] - fictif - dividendes
        v['DFLT'] = v['PA_EMPRUNT_NC'] + cb_lt - emprunt_ct         # dettes financières > 1 an
        v['CAPITAUX_PERMANENTS'] = v['CP_RETRAITE'] + v['DFLT'] + v['PA_PROV_NC'] + v['PA_AUT_DETTE_NC']

        # Actif circulant
        v['ACE'] = (v['AC_STOCK'] - stock_outil) + v['AC_CLIENT'] + eene + v['AC_CCA']
        v['ACHE'] = v['AC_AUT_CREANCE'] - v['AC_CCA'] + v['AC_PLACEMENT']
        v['TA'] = v['AC_TRESO']

        # Passif circulant
        v['PCE'] = v['PA_FOURN'] + v['PA_IMPOTS'] + v['PA_AUT_DETTE_C']
        v['PCHE'] = dividendes + emprunt_ct + cb_ct
        v['TP'] = v['PA_TRESO_PASSIF'] + eene

        # ---- Équilibre financier ----
        v['FRNG'] = v['CAPITAUX_PERMANENTS'] - v['AI']
        v['BFRE'] = v['ACE'] - v['PCE']
        v['BFRHE'] = v['ACHE'] - v['PCHE']
        v['BFR'] = v['BFRE'] + v['BFRHE']
        v['TN'] = v['FRNG'] - v['BFR']
        v['TN_CTRL'] = v['TA'] - v['TP']

        # ---- Autres agrégats structurels ----
        v['DETTES_TOTALES'] = v['ST_PNC'] + v['ST_PC'] + cb_lt + cb_ct
        v['DETTES_FIN'] = v['PA_EMPRUNT_NC'] + v['PA_TRESO_PASSIF'] + cb_lt + cb_ct
        v['DETTE_FIN_NETTE'] = v['DETTES_FIN'] - v['AC_TRESO'] - v['AC_PLACEMENT']
        v['ANC'] = v['T_ACTIF'] - fictif - v['DETTES_TOTALES']
        v['CAPITAUX_EMPLOYES'] = v['AI'] + v['BFR']
        v['CAPITAL_ECONOMIQUE'] = v['AI'] + v['BFRE']
        v['IMMO_BRUT'] = v.get('IN_IMMO_BRUT', 0.0)
        v['AMORT_CUMUL'] = v.get('IN_AMORT_CUMUL', 0.0)

        # ---- Annualisation des flux ----
        if coef != 1.0:
            for key in ('CA', 'MC', 'PROD', 'CONSO', 'VA', 'EBE', 'REX', 'RF', 'RAI',
                        'RNAO', 'RN', 'PL_PERSONNEL', 'PL_CH_FIN', 'PL_PROD_FIN',
                        'PL_DOTATIONS', 'PL_REPRISES', 'PL_IMPOTS_TAXES',
                        'PL_IMP_EXIG', 'PL_ACHATS', 'PL_SERV_EXT', 'PL_VENTE_MSE',
                        'PL_ACHAT_MSE', 'PL_CA_PROD'):
                v[key] = v.get(key, 0.0) * coef
            v['ANNUALIZED'] = 1.0
        else:
            v['ANNUALIZED'] = 0.0

        # ---- Capacité d'autofinancement (après annualisation) ----
        vnc_cede = v.get('IN_VNC_CEDEE', 0.0) * coef
        prod_cession = v.get('IN_PROD_CESSION', 0.0) * coef
        qp_subv = v.get('IN_QP_SUBV', 0.0) * coef
        v['CAF'] = v['RN'] + v['PL_DOTATIONS'] - v['PL_REPRISES'] + vnc_cede - prod_cession - qp_subv
        # Méthode soustractive : contrôle
        v['CAF_SOUS'] = (v['EBE'] + v['PL_AUT_PROD_OP'] * coef - v['PL_AUT_CH_OP'] * coef
                         + v['PL_PROD_FIN'] - v['PL_CH_FIN'] - v['PL_IMP_EXIG'])
        v['CAF_ECART'] = v['CAF'] - v['CAF_SOUS']
        v['AUTOFINANCEMENT'] = v['CAF'] - dividendes * coef

        # ---- Seuil de rentabilité ----
        # Deux méthodes, selon le paramétrage du dossier :
        #
        #  * coûts variables : SR = charges fixes / taux de marge sur coûts
        #    variables. La plus précise, mais suppose une ventilation des
        #    charges rarement disponible dans les états financiers ;
        #
        #  * excédent brut d'exploitation : SR = charges de structure /
        #    taux d'EBE. S'appuie sur des données toujours saisies.
        #
        # Les impôts et taxes sont déjà déduits dans l'EBE : les réintégrer
        # aux charges de structure les compterait deux fois. Le comportement
        # est donc désactivé par défaut, activable par paramètre.
        method = self.analysis_id.sr_method or 'auto'
        cv = v.get('IN_CHARGES_VARIABLES', 0.0) * coef
        cf = v.get('IN_CHARGES_FIXES', 0.0) * coef
        has_variable_data = bool(cv and cf and v['CA'])

        v['MCV'] = 0.0
        v['TAUX_MCV'] = 0.0
        v['SR'] = 0.0
        v['SR_METHOD'] = 0.0          # 1 = coûts variables, 2 = EBE
        v['CSI'] = 0.0                # charges de structure immobiles
        v['TAUX_EBE'] = (v['EBE'] / v['CA']) if v['CA'] else 0.0

        use_variable = (method == 'variable'
                        or (method == 'auto' and has_variable_data))

        if use_variable and has_variable_data:
            v['MCV'] = v['CA'] - cv
            v['TAUX_MCV'] = v['MCV'] / v['CA']
            v['SR'] = cf / v['TAUX_MCV'] if v['TAUX_MCV'] else 0.0
            v['SR_METHOD'] = 1.0
        elif method in ('auto', 'ebe') and v['CA'] and v['TAUX_EBE'] > 0:
            # Charges de structure : postes non absorbés par l'EBE
            csi = (v['PL_DOTATIONS'] + v['PL_CH_FIN'] + v['PL_IMP_EXIG'])
            if self.analysis_id.sr_include_taxes:
                csi += v['PL_IMPOTS_TAXES']
            v['CSI'] = csi
            v['SR'] = csi / v['TAUX_EBE']
            v['SR_METHOD'] = 2.0

        # Point mort et marge de sécurité, dérivés du seuil retenu
        if v['SR'] and v['CA']:
            v['POINT_MORT'] = v['SR'] * 360.0 / v['CA']
            v['MARGE_SECURITE'] = (v['CA'] - v['SR']) / v['CA']
        else:
            v['POINT_MORT'] = 0.0
            v['MARGE_SECURITE'] = 0.0

        # ---- Divers pour les ratios ----
        v['EFFECTIF'] = v.get('IN_EFFECTIF', 0.0)
        v['CA_TTC'] = v.get('IN_CA_TTC', 0.0) * coef or v['CA'] * 1.2
        v['ACHATS_TTC'] = v.get('IN_ACHATS_TTC', 0.0) * coef or (v['PL_ACHATS'] + v['PL_SERV_EXT']) * 1.2
        v['INVESTISSEMENTS'] = v.get('IN_INVESTISSEMENTS', 0.0) * coef
        v['DIVIDENDES'] = dividendes * coef
        v['CBC'] = v['PA_TRESO_PASSIF']
        # Nombre de jours de la période pour les ratios de délai
        v['NB_JOURS'] = 360.0

    # ------------------------------------------------------------------
    # Génération des lignes
    # ------------------------------------------------------------------
    def action_generate_lines(self):
        """Crée les lignes de saisie à partir du référentiel de rubriques."""
        Rubric = self.env['fa.rubric']
        Line = self.env['fa.statement.line']
        for rec in self:
            existing = rec.line_ids.mapped('rubric_id').ids
            rubrics = Rubric.search([('line_type', '=', 'input')])
            vals = [{
                'statement_id': rec.id,
                'rubric_id': r.id,
            } for r in rubrics if r.id not in existing]
            if vals:
                Line.create(vals)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.action_generate_lines()
        return records

    def action_copy_structure(self):
        """Duplique la période en conservant la structure, sans les montants."""
        self.ensure_one()
        new = self.copy({
            'name': _("%s (copie)") % self.name,
            'state': 'draft',
            'previous_statement_id': self.id,
        })
        new.line_ids.write({'amount_gross': 0.0, 'amount_deprec': 0.0, 'amount_net': 0.0})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fa.statement',
            'res_id': new.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if not rec.is_balanced:
                raise UserError(_(
                    "Le bilan de la période « %(name)s » n'est pas équilibré.\n\n"
                    "Total Actif : %(a)s\nTotal Passif : %(p)s\nÉcart : %(gap)s\n\n"
                    "Corrigez la saisie avant de valider.",
                    name=rec.name,
                    a='{:,.0f}'.format(rec.total_asset).replace(',', ' '),
                    p='{:,.0f}'.format(rec.total_liability).replace(',', ' '),
                    gap='{:,.0f}'.format(rec.balance_check).replace(',', ' ')))
            if not rec.is_result_ok:
                raise UserError(_(
                    "Le résultat net du compte de résultat (%(pl)s) ne correspond pas "
                    "au résultat inscrit au bilan (%(bs)s).",
                    pl='{:,.0f}'.format(rec.net_result_pl).replace(',', ' '),
                    bs='{:,.0f}'.format(rec.net_result_bs).replace(',', ' ')))
            rec.state = 'confirmed'
            if rec.analysis_id.state == 'draft':
                rec.analysis_id.state = 'progress'
        return True

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_analyze(self):
        """Lance le moteur : agrégats, ratios, commentaires."""
        for rec in self:
            if rec.state == 'draft':
                rec.action_confirm()
            rec._compute_aggregate_records()
            rec._compute_ratio_records()
            rec._run_extra_checks()
            rec._compute_cashflow_records()
            rec._compute_equity_records()
            self.env['fa.score'].generate_for_statement(rec)
            rec.state = 'analyzed'
        return True

    # ------------------------------------------------------------------
    # Moteur : agrégats persistés
    # ------------------------------------------------------------------
    AGGREGATE_DEFS = [
        # (code, libellé, catégorie)
        ('AI', "Actif immobilisé net (retraité)", 'balance'),
        ('CAPITAUX_PERMANENTS', "Capitaux permanents", 'balance'),
        ('CP_RETRAITE', "Capitaux propres retraités", 'balance'),
        ('ACE', "Actif circulant d'exploitation", 'balance'),
        ('ACHE', "Actif circulant hors exploitation", 'balance'),
        ('TA', "Trésorerie active", 'balance'),
        ('PCE', "Passif circulant d'exploitation", 'balance'),
        ('PCHE', "Passif circulant hors exploitation", 'balance'),
        ('TP', "Trésorerie passive", 'balance'),
        ('FRNG', "Fonds de roulement net global", 'equilibrium'),
        ('BFRE', "Besoin en fonds de roulement d'exploitation", 'equilibrium'),
        ('BFRHE', "BFR hors exploitation", 'equilibrium'),
        ('BFR', "Besoin en fonds de roulement total", 'equilibrium'),
        ('TN', "Trésorerie nette (FRNG - BFR)", 'equilibrium'),
        ('TN_CTRL', "Trésorerie nette (contrôle : TA - TP)", 'equilibrium'),
        ('DETTES_FIN', "Dettes financières", 'balance'),
        ('DETTE_FIN_NETTE', "Dette financière nette", 'balance'),
        ('ANC', "Actif net comptable", 'balance'),
        ('CAPITAUX_EMPLOYES', "Capitaux employés", 'balance'),
        ('CA', "Chiffre d'affaires", 'sig'),
        ('PL_VENTE_MSE', "dont ventes de marchandises", 'sig'),
        ('PL_CA_PROD', "dont production vendue de biens et services", 'sig'),
        ('MC', "Marge commerciale", 'sig'),
        ('PROD', "Production de l'exercice", 'sig'),
        ('CONSO', "Consommations en provenance des tiers", 'sig'),
        ('VA', "Valeur ajoutée", 'sig'),
        ('EBE', "Excédent brut d'exploitation", 'sig'),
        ('REX', "Résultat opérationnel", 'sig'),
        ('RF', "Résultat financier", 'sig'),
        ('RAI', "Résultat avant impôts", 'sig'),
        ('RNAO', "Résultat net des activités ordinaires", 'sig'),
        ('RN', "Résultat net de l'exercice", 'sig'),
        ('CAF', "Capacité d'autofinancement (méthode additive)", 'caf'),
        ('CAF_SOUS', "CAF (méthode soustractive - contrôle)", 'caf'),
        ('CAF_ECART', "Écart entre les deux méthodes de CAF", 'caf'),
        ('AUTOFINANCEMENT', "Autofinancement (CAF - dividendes)", 'caf'),
        # Seuil de rentabilité : catégorie dédiée, unités hétérogènes
        ('TAUX_EBE', "Taux d'excédent brut d'exploitation", 'breakeven', 'percent'),
        ('TAUX_MCV', "Taux de marge sur coûts variables", 'breakeven', 'percent'),
        ('CSI', "Charges de structure immobiles", 'breakeven', 'amount'),
        ('MCV', "Marge sur coûts variables", 'breakeven', 'amount'),
        ('SR', "Seuil de rentabilité", 'breakeven', 'amount'),
        ('POINT_MORT', "Point mort", 'breakeven', 'days'),
        ('MARGE_SECURITE', "Marge de sécurité", 'breakeven', 'percent'),
    ]

    @api.depends('score_ids.value', 'score_ids.zone')
    def _compute_score_summary(self):
        for rec in self:
            synth = rec.score_ids.filtered(
                lambda s: s.model == 'synthesis' and not s.is_na)[:1]
            rec.score_synthesis = synth.value if synth else 0.0
            rec.risk_zone = synth.zone if synth else False

    def _compute_aggregate_records(self):
        self.ensure_one()
        self.aggregate_ids.unlink()
        raw = self._get_values_dict(annualized=False)
        ann = self._get_values_dict(annualized=True)
        vals = []
        for seq, definition in enumerate(self.AGGREGATE_DEFS, start=1):
            code, label, category = definition[0], definition[1], definition[2]
            unit = definition[3] if len(definition) > 3 else 'amount'
            vals.append({
                'statement_id': self.id,
                'code': code,
                'name': label,
                'category': category,
                'unit': unit,
                'sequence': seq * 10,
                'amount': raw.get(code, 0.0),
                'amount_annualized': ann.get(code, 0.0),
                # Les taux et durées sont aussi stockés en flottant : le champ
                # monétaire les arrondirait à l'unité de la devise.
                'ratio_value': raw.get(code, 0.0),
                'ratio_value_annualized': ann.get(code, 0.0),
            })
        self.env['fa.aggregate'].create(vals)

    # ------------------------------------------------------------------
    # Moteur : ratios et commentaires
    # ------------------------------------------------------------------
    def _compute_ratio_records(self, keep_manual=True):
        """Recalcule les ratios.

        :param keep_manual: conserve les commentaires et recommandations
                            saisis par le consultant. Sans cela, une simple
                            relance de l'analyse détruirait son travail
                            de rédaction.
        """
        self.ensure_one()
        # Mémorisation des textes personnalisés avant recréation des lignes
        saved = {}
        if keep_manual:
            for res in self.ratio_result_ids:
                if res.comment_manual or res.recommendation_manual or res.hide_in_report:
                    saved[res.ratio_id.id] = {
                        'comment_manual': res.comment_manual,
                        'recommendation_manual': res.recommendation_manual,
                        'hide_in_report': res.hide_in_report,
                        'priority_manual': res.priority_manual,
                    }
        self.ratio_result_ids.unlink()

        raw = self._get_values_dict(annualized=False)
        ann = self._get_values_dict(annualized=True)
        prev_vals = {}
        if self.previous_statement_id:
            prev_vals = {
                r.ratio_id.code: r.value
                for r in self.previous_statement_id.ratio_result_ids if not r.is_na
            }

        sector = self.analysis_id.sector_id
        ratios = self.env['fa.ratio'].search([])
        vals_list = []
        for ratio in ratios:
            context_vals = ann if ratio.annualize else raw
            value, is_na, na_reason = self._safe_ratio(ratio, context_vals)
            prev = prev_vals.get(ratio.code, 0.0)
            thresholds = ratio.get_thresholds(sector)

            appreciation = False
            comment = recommendation = False
            priority = '2'
            if not is_na:
                appreciation = ratio._evaluate_appreciation(value, thresholds)
                comment, recommendation, appreciation, priority = self._apply_comment_rules(
                    ratio, value, prev, appreciation, thresholds, context_vals)

            line_vals = {
                'statement_id': self.id,
                'ratio_id': ratio.id,
                'value': value if not is_na else 0.0,
                'previous_value': prev,
                'is_na': is_na,
                'na_reason': na_reason,
                'appreciation': appreciation,
                'comment_auto': comment,
                'recommendation_auto': recommendation,
                'priority': priority,
                'norm_applied': thresholds['label'],
                'is_sector_norm': thresholds['is_sector'],
                'sector_median': thresholds['median'],
            }
            # Restauration du travail de rédaction du consultant
            line_vals.update(saved.get(ratio.id, {}))
            vals_list.append(line_vals)
        if vals_list:
            self.env['fa.ratio.result'].create(vals_list)

    def _safe_ratio(self, ratio, values):
        """Évalue une formule de ratio en neutralisant les divisions par zéro.

        Si le ratio porte une condition d'applicabilité et qu'elle n'est pas
        remplie, il est déclaré sans objet : mieux vaut ne rien dire que
        produire une valeur nulle qui serait ensuite jugée critique à tort.
        """
        if ratio.applicability:
            try:
                if not safe_eval(ratio.applicability, dict(values)):
                    return 0.0, True, (ratio.na_message
                                       or _("Ratio sans objet dans cette configuration."))
            except Exception:  # noqa: BLE001
                pass
        try:
            result = safe_eval(ratio.formula, dict(values))
        except ZeroDivisionError:
            return 0.0, True, _("Dénominateur nul : ratio non calculable.")
        except (NameError, KeyError) as err:
            return 0.0, True, _("Donnée manquante : %s") % err
        except Exception as err:  # noqa: BLE001
            _logger.warning("Ratio %s : erreur d'évaluation (%s)", ratio.code, err)
            return 0.0, True, _("Erreur de formule : %s") % err
        if result is None:
            return 0.0, True, _("Résultat indéfini.")
        result = float(result)
        if ratio.unit == 'percent':
            result *= 100.0
        return result, False, False

    def _apply_comment_rules(self, ratio, value, prev, default_appreciation,
                             thresholds=None, context_vals=None):
        """Applique la première règle vraie et rend le texte formaté.

        Le commentaire est enrichi de la tendance par rapport à la période
        précédente et, le cas échéant, de la précision sectorielle.
        """
        t = thresholds or ratio.get_thresholds(self.analysis_id.sector_id)
        variation = value - prev
        # Les seuils sont exposés aux conditions : une règle écrite « value > t_watch »
        # suit automatiquement la norme sectorielle du client.
        eval_ctx = {
            'value': value, 'prev': prev, 'variation': variation, 'abs': abs,
            't_bad': t['bad'], 't_watch': t['watch'],
            't_good': t['good'], 't_max': t['max'],
            'median': t['median'],
        }
        # Les agrégats sont exposés aux conditions : une règle peut ainsi
        # nuancer son verdict selon le contexte financier. Un ratio de
        # liquidité faible n'a pas le même sens selon que l'entreprise
        # supporte ou non un découvert bancaire.
        if context_vals:
            eval_ctx.update({
                k: v for k, v in context_vals.items()
                if isinstance(v, (int, float)) and k not in eval_ctx
            })
        for rule in ratio.rule_ids.sorted('sequence'):
            try:
                if not safe_eval(rule.condition, dict(eval_ctx)):
                    continue
            except Exception:  # noqa: BLE001
                continue
            fmt = {
                'value': self._fmt(value, ratio.unit),
                'prev': self._fmt(prev, ratio.unit) if prev else _("n/a"),
                'variation': self._fmt(abs(variation), ratio.unit),
                'norm': t['label'],
                'median': self._fmt(t['median'], ratio.unit) if t['median'] else _("n/d"),
                'sector': self.analysis_id.sector_id.name or '',
                'company': self.partner_id.name or '',
                'period': self.name or '',
            }
            try:
                comment = (rule.comment_tpl or '').format(**fmt)
                reco = (rule.recommendation_tpl or '').format(**fmt)
            except (KeyError, IndexError):
                comment = rule.comment_tpl or ''
                reco = rule.recommendation_tpl or ''

            # Phrase de tendance ajoutée automatiquement
            trend_txt = self._trend_sentence(ratio, value, prev, t)
            if trend_txt:
                comment = "%s %s" % (comment, trend_txt)
            # Comparaison à la médiane du secteur
            median_txt = self._get_median_note(ratio, value, t)
            if median_txt:
                comment = "%s %s" % (comment, median_txt)
            # Précision propre au secteur
            if t['is_sector'] and t['comment']:
                comment = "%s %s" % (comment, t['comment'])
            # L'appréciation provient des seuils (sectoriels le cas échéant) :
            # ils constituent la source de vérité unique. La règle ne l'impose
            # que si elle traite un cas particulier (force_appreciation).
            appreciation = (rule.appreciation if rule.force_appreciation
                            else default_appreciation)
            return comment, reco, appreciation, rule.priority
        return False, False, default_appreciation, '2'

    def _trend_sentence(self, ratio, value, prev, thresholds):
        """Construit la phrase d'évolution par rapport à la période précédente."""
        if not prev:
            return ''
        variation = value - prev
        seuil = abs(prev) * 0.02
        favorable = None
        if ratio.direction == 'higher':
            favorable = variation > 0
        elif ratio.direction == 'lower':
            favorable = variation < 0
        val_prev = self._fmt(prev, ratio.unit)
        val_var = self._fmt(abs(variation), ratio.unit)
        if abs(variation) <= seuil:
            return _("Le ratio est stable par rapport à la période précédente (%s).") % val_prev
        sens = _("progresse de") if variation > 0 else _("recule de")
        if favorable is True:
            appre = _("Cette évolution est favorable.")
        elif favorable is False:
            appre = _("Cette évolution est défavorable et mérite un suivi rapproché.")
        else:
            appre = ''
        base = _("Il %(sens)s %(var)s par rapport à la période précédente (%(prev)s).",
                 sens=sens, var=val_var, prev=val_prev)
        return ("%s %s" % (base, appre)).strip()

    def _get_median_note(self, ratio, value, thresholds):
        """Compare la valeur à la médiane sectorielle si elle est renseignée."""
        if not thresholds.get('median'):
            return ''
        med = thresholds['median']
        sector = self.analysis_id.sector_id.name or ''
        if value > med * 1.05:
            pos = _("supérieure")
        elif value < med * 0.95:
            pos = _("inférieure")
        else:
            pos = _("comparable")
        return _("La valeur est %(pos)s à la médiane du secteur %(sec)s (%(med)s).",
                 pos=pos, sec=sector, med=self._fmt(med, ratio.unit))

    @staticmethod
    def _fmt_precise(value, unit):
        """Mise en forme avec une décimale supplémentaire.

        Utilisée lorsque l'arrondi usuel placerait la valeur du mauvais côté
        d'un seuil et rendrait l'appréciation incompréhensible.
        """
        if unit == 'percent':
            return "%.2f %%" % value
        if unit == 'days':
            return "%.1f jours" % value
        if unit == 'times':
            return "%.3f" % value
        if unit == 'years':
            return "%.2f an(s)" % value
        return '{:,.2f}'.format(value).replace(',', ' ')

    @staticmethod
    def _fmt(value, unit):
        """Met en forme une valeur selon son unité.

        Les valeurs non nulles mais inférieures à l'unité d'affichage sont
        présentées avec une décimale plutôt qu'arrondies à zéro : un fonds de
        roulement de 0,3 jour n'est pas nul, et l'écrire « 0 jours » induirait
        le lecteur en erreur.
        """
        if unit == 'percent':
            if value and abs(value) < 0.1:
                return "%.2f %%" % value
            return "%.1f %%" % value
        if unit == 'days':
            if value and abs(value) < 1:
                return "%.1f jour" % value
            return "%.0f jours" % value
        if unit == 'times':
            if value and abs(value) < 0.01:
                return "%.4f" % value
            return "%.2f" % value
        if unit == 'years':
            return "%.1f an(s)" % value
        if value and abs(value) < 1:
            return "%.2f" % value
        return '{:,.0f}'.format(value).replace(',', ' ')

    # ------------------------------------------------------------------
    # Synthèse forces / faiblesses
    # ------------------------------------------------------------------
    def get_synthesis(self):
        """Retourne les forces, faiblesses et recommandations priorisées.

        Respecte les options d'impression du dossier : ratios masqués et
        portée des recommandations.
        """
        self.ensure_one()
        results = self.ratio_result_ids.filtered(
            lambda r: not r.is_na and not r.hide_in_report)
        strengths = results.filtered(lambda r: r.appreciation == 'good')
        weaknesses = results.filtered(lambda r: r.appreciation in ('bad', 'watch'))

        scope = self.analysis_id.report_reco_scope
        recos = results.filtered(lambda r: r.recommendation)
        if scope == 'critical':
            recos = recos.filtered(lambda r: r.appreciation == 'bad')
        elif scope == 'alerts':
            recos = recos.filtered(lambda r: r.appreciation in ('bad', 'watch'))
        recos = recos.sorted(
            key=lambda r: (r.priority_final or '3', r.appreciation != 'bad'))
        return {
            'strengths': strengths[:6],
            'weaknesses': weaknesses.sorted(
                key=lambda r: 0 if r.appreciation == 'bad' else 1)[:6],
            'recommendations': recos[:10],
        }

    def get_report_ratios(self, family=None):
        """Ratios à imprimer : exclut ceux masqués par le consultant."""
        self.ensure_one()
        lines = self.ratio_result_ids.filtered(lambda r: not r.hide_in_report)
        if family:
            lines = lines.filtered(lambda r: r.family == family)
        return lines.sorted('sequence')

    def show_reco_for(self, result):
        """Indique si la recommandation d'un ratio doit être imprimée."""
        self.ensure_one()
        an = self.analysis_id
        if not an.report_show_recommendations or not result.recommendation:
            return False
        scope = an.report_reco_scope
        if scope == 'critical':
            return result.appreciation == 'bad'
        if scope == 'alerts':
            return result.appreciation in ('bad', 'watch')
        return True

    def action_hide_good_ratios(self):
        """Masque dans les rapports les ratios bien orientés : livrable resserré."""
        self.ensure_one()
        self.ratio_result_ids.filtered(
            lambda r: r.appreciation == 'good').write({'hide_in_report': True})
        return True

    def action_show_all_ratios(self):
        """Réintègre tous les ratios dans les rapports."""
        self.ensure_one()
        self.ratio_result_ids.write({'hide_in_report': False})
        return True

    def action_open_scores(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Scores de risque - %s") % self.name,
            'res_model': 'fa.score',
            'view_mode': 'tree,form',
            'domain': [('statement_id', '=', self.id)],
        }

    def action_review_comments(self):
        """Ouvre les ratios en vue plein écran pour réviser les textes."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Commentaires et recommandations - %s") % self.name,
            'res_model': 'fa.ratio.result',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('mg_financial_analysis.view_fa_ratio_result_edit_tree').id, 'tree'),
                (self.env.ref('mg_financial_analysis.view_fa_ratio_result_form').id, 'form'),
            ],
            'domain': [('statement_id', '=', self.id)],
            'context': {'search_default_group_family': 1},
        }

    def action_reset_comments(self):
        """Rétablit tous les textes générés sur la période."""
        self.ensure_one()
        self.ratio_result_ids.action_reset_text()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Textes rétablis"),
                'message': _("Les commentaires et recommandations générés "
                             "automatiquement ont été rétablis."),
                'type': 'success',
            },
        }

    def action_open_ratios(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ratios - %s") % self.name,
            'res_model': 'fa.ratio.result',
            'view_mode': 'tree,graph,pivot,form',
            'domain': [('statement_id', '=', self.id)],
            'context': {'search_default_group_family': 1},
        }
