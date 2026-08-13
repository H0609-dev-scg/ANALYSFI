# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FaAnalysis(models.Model):
    """Dossier d'analyse financière : regroupe les périodes d'un même client."""
    _name = 'fa.analysis'
    _description = "Dossier d'analyse financière"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string="Référence", required=True, copy=False, readonly=True,
        default=lambda self: _('Nouveau'))
    partner_id = fields.Many2one(
        'res.partner', string="Client analysé", required=True, tracking=True)

    sector_id = fields.Many2one(
        'fa.sector', string="Secteur d'activité", required=True, tracking=True,
        default=lambda self: self.env.ref('mg_financial_analysis.sector_commerce',
                                          raise_if_not_found=False),
        help="Détermine les normes de ratios appliquées. Les seuils sectoriels "
             "se substituent aux seuils génériques lorsqu'ils sont définis.")
    sector_description = fields.Text(
        related='sector_id.description', string="Caractéristiques du secteur")
    sector_norm_count = fields.Integer(
        related='sector_id.norm_count', string="Normes sectorielles")

    activity_mode = fields.Selection([
        ('commercial', "Commerciale (achat-revente)"),
        ('production', "Production (industrie, BTP, services)"),
        ('mixed', "Mixte"),
    ], string="Nature de l'activité", default='mixed', required=True,
        help="Mixte : les blocs marge commerciale et production sont tous deux affichés.")

    nif = fields.Char(string="NIF")
    stat = fields.Char(string="N° Statistique")
    rcs = fields.Char(string="RCS")

    company_id = fields.Many2one(
        'res.company', string="Société", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string="Devise", required=True,
        default=lambda self: self.env.ref('base.MGA', raise_if_not_found=False)
        or self.env.company.currency_id)

    scale = fields.Selection([
        ('unit', "Ariary"),
        ('thousand', "Milliers d'Ariary"),
        ('million', "Millions d'Ariary"),
    ], string="Unité de saisie", default='unit', required=True)

    show_gross = fields.Boolean(
        string="Colonnes Brut / Amortissements", default=True,
        help="Décocher pour ne saisir que les montants nets.")

    user_id = fields.Many2one(
        'res.users', string="Consultant responsable",
        default=lambda self: self.env.user, tracking=True)

    date_mission = fields.Date(string="Date de la mission", default=fields.Date.context_today)

    statement_ids = fields.One2many('fa.statement', 'analysis_id', string="États financiers")
    statement_count = fields.Integer(string="Nb périodes", compute='_compute_statement_count')

    comparison_ids = fields.One2many('fa.comparison', 'analysis_id', string="Comparatifs")

    state = fields.Selection([
        ('draft', "Brouillon"),
        ('progress', "En cours"),
        ('done', "Finalisé"),
    ], string="État", default='draft', tracking=True)

    note = fields.Html(string="Contexte de la mission")
    conclusion = fields.Html(
        string="Conclusion générale",
        help="Synthèse rédigée par le consultant, reprise en fin de rapport.")

    # ------------------------------------------------------------------
    # Options d'impression du rapport
    # ------------------------------------------------------------------
    report_show_recommendations = fields.Boolean(
        string="Inclure les recommandations", default=True,
        help="Décochez pour produire un rapport purement descriptif, sans "
             "préconisations. Utile lorsque les actions sont présentées "
             "oralement ou dans un document distinct.")

    report_reco_scope = fields.Selection([
        ('all', "Tous les ratios"),
        ('alerts', "Uniquement les points d'attention"),
        ('critical', "Uniquement les ratios critiques"),
    ], string="Portée des recommandations", default='alerts', required=True,
        help="Détermine les ratios pour lesquels une recommandation est imprimée "
             "dans les fiches de la section Analyse par les ratios.")

    report_show_interpretation = fields.Boolean(
        string="Inclure l'explication des ratios", default=True,
        help="Volet « Ce que mesure le ratio » dans chaque fiche. "
             "À conserver pour un lecteur non financier.")

    report_show_equity = fields.Boolean(
        string="Inclure la variation des capitaux propres", default=True,
        help="État obligatoire au PCG 2005 (chapitre 4).")

    report_show_cashflow = fields.Boolean(
        string="Inclure le tableau des flux de trésorerie", default=True,
        help="État obligatoire au PCG 2005 (chapitre 5).")

    report_show_cashflow_direct = fields.Boolean(
        string="Ajouter la méthode directe", default=False,
        help="La méthode indirecte suffit dans la plupart des cas. "
             "Cochez pour présenter également le détail des encaissements "
             "et décaissements bruts.")

    report_show_score = fields.Boolean(
        string="Inclure le score de risque", default=True,
        help="Section dédiée aux modèles de détection du risque de défaillance.")

    report_show_glossary = fields.Boolean(
        string="Inclure le glossaire", default=True,
        help="Annexe reprenant la définition et la formule de tous les ratios.")

    report_show_formula = fields.Boolean(
        string="Afficher les formules de calcul", default=True)

    report_show_reco_summary = fields.Boolean(
        string="Inclure la synthèse des recommandations", default=True,
        help="Tableau récapitulatif des actions classées par urgence, "
             "en fin de rapport.")

    report_hidden_count = fields.Integer(
        string="Ratios masqués", compute='_compute_hidden_count')

    # ------------------------------------------------------------------
    # Paramètres du seuil de rentabilité
    # ------------------------------------------------------------------
    sr_method = fields.Selection([
        ('auto', "Automatique : coûts variables si disponibles, sinon EBE"),
        ('ebe', "Toujours par le taux d'excédent brut d'exploitation"),
        ('variable', "Toujours par les coûts variables"),
    ], string="Méthode du seuil de rentabilité", default='auto', required=True,
        help="La méthode par les coûts variables est plus précise mais suppose "
             "de ventiler les charges en fixes et variables. La méthode par l'EBE "
             "s'appuie sur des données toujours disponibles.")

    sr_include_taxes = fields.Boolean(
        string="Inclure les impôts et taxes dans les charges de structure",
        default=False,
        help="Méthode EBE uniquement. Les impôts, taxes et versements assimilés "
             "sont déjà déduits dans le calcul de l'excédent brut d'exploitation "
             "(EBE = VA + subventions − personnel − impôts et taxes). Les rajouter "
             "aux charges de structure revient à les compter deux fois et majore "
             "le seuil de rentabilité. À n'activer que si votre méthodologie "
             "l'impose explicitement.")

    # Tolérance d'arrondi pour les contrôles d'équilibre
    tolerance = fields.Float(
        string="Tolérance d'équilibre", default=1.0,
        help="Écart maximal admis entre le total actif et le total passif.")

    @api.depends('statement_ids')
    def _compute_statement_count(self):
        for rec in self:
            rec.statement_count = len(rec.statement_ids)

    @api.depends('statement_ids.ratio_result_ids.hide_in_report')
    def _compute_hidden_count(self):
        for rec in self:
            last = rec.statement_ids.sorted('date_to')[-1:]
            rec.report_hidden_count = len(
                last.ratio_result_ids.filtered('hide_in_report'))

    def action_view_hidden_ratios(self):
        """Ouvre la liste des ratios exclus des rapports."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ratios masqués dans les rapports"),
            'res_model': 'fa.ratio.result',
            'view_mode': 'tree,form',
            'domain': [('analysis_id', '=', self.id)],
            'context': {'search_default_hidden': 1},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fa.analysis') or _('Nouveau')
        return super().create(vals_list)

    def action_view_statements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("États financiers"),
            'res_model': 'fa.statement',
            'view_mode': 'tree,form',
            'domain': [('analysis_id', '=', self.id)],
            'context': {'default_analysis_id': self.id},
        }

    def action_start(self):
        self.write({'state': 'progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generate_comparison(self):
        """Crée un comparatif portant sur toutes les périodes analysées du dossier."""
        self.ensure_one()
        stmts = self.statement_ids.sorted('date_to')
        if len(stmts) < 2:
            raise UserError(_(
                "Le comparatif nécessite au moins deux périodes. "
                "Le dossier n'en compte que %s.") % len(stmts))
        comparison = self.env['fa.comparison'].create({
            'analysis_id': self.id,
            'name': _("Comparatif %(n)s - %(p)s périodes",
                      n=self.name, p=len(stmts)),
            'statement_ids': [(6, 0, stmts.ids)],
        })
        comparison.action_compute()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Comparatif multi-périodes"),
            'res_model': 'fa.comparison',
            'res_id': comparison.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_print_comparison(self):
        """Génère le comparatif de toutes les périodes et imprime le rapport PDF."""
        self.ensure_one()
        stmts = self.statement_ids.sorted('date_to')
        if len(stmts) < 2:
            raise UserError(_(
                "Le rapport comparatif nécessite au moins deux périodes analysées."))
        comparison = self.comparison_ids.filtered(
            lambda c: len(c.statement_ids) == len(stmts))[:1]
        if not comparison:
            comparison = self.env['fa.comparison'].create({
                'analysis_id': self.id,
                'name': _("Comparatif %(n)s - %(p)s périodes", n=self.name, p=len(stmts)),
                'statement_ids': [(6, 0, stmts.ids)],
            })
        comparison.action_compute()
        return self.env.ref(
            'mg_financial_analysis.action_report_fa_comparison').report_action(comparison)

    def action_generate_conclusion(self):
        """Rédige un projet de conclusion à partir des indicateurs calculés."""
        self.ensure_one()
        analyzed = self.statement_ids.filtered(lambda s: s.state == 'analyzed')
        if not analyzed:
            raise UserError(_(
                "Lancez d'abord l'analyse d'au moins une période : la conclusion "
                "s'appuie sur les indicateurs calculés."))
        if self.conclusion and not self.env.context.get('force_conclusion'):
            return {
                'type': 'ir.actions.act_window',
                'name': _("Remplacer la conclusion existante ?"),
                'res_model': 'fa.conclusion.confirm',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_analysis_id': self.id},
            }
        self.conclusion = self.env['fa.conclusion.builder'].build(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Projet de conclusion généré"),
                'message': _("Relisez et adaptez le texte dans l'onglet "
                             "« Conclusion générale » avant diffusion."),
                'type': 'success',
            },
        }

    def action_view_sector_norms(self):
        """Ouvre les normes du secteur du client."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Normes du secteur %s") % self.sector_id.name,
            'res_model': 'fa.sector.norm',
            'view_mode': 'tree,form',
            'domain': [('sector_id', '=', self.sector_id.id)],
            'context': {'default_sector_id': self.sector_id.id},
        }
