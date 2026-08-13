# -*- coding: utf-8 -*-
from odoo import models, fields, api


class FaRubric(models.Model):
    """Référentiel paramétrable des rubriques des états financiers PCG 2005.

    Chaque rubrique correspond à une ligne du bilan ou du compte de résultat.
    Le référentiel étant en base (et non codé en dur), le consultant peut
    ajouter/masquer un poste sans redéveloppement.
    """
    _name = 'fa.rubric'
    _description = "Rubrique des états financiers (PCG 2005)"
    _order = 'statement_type, sequence, id'
    _parent_store = True

    code = fields.Char(
        string="Code", required=True, index=True,
        help="Code interne stable utilisé dans les formules de ratios (ex. AC_STOCK).")
    name = fields.Char(string="Libellé", required=True, translate=True)
    sequence = fields.Integer(string="Séquence", default=10)

    statement_type = fields.Selection([
        ('bs_asset', "Bilan - Actif"),
        ('bs_liability', "Bilan - Passif"),
        ('pl', "Compte de résultat"),
        ('extra', "Informations complémentaires"),
    ], string="État", required=True, index=True)

    section = fields.Selection([
        # Actif
        ('anc', "Actifs non courants"),
        ('ac', "Actifs courants"),
        # Passif
        ('cp', "Capitaux propres"),
        ('pnc', "Passifs non courants"),
        ('pc', "Passifs courants"),
        # Compte de résultat
        ('pl_expl', "Exploitation"),
        ('pl_op', "Opérationnel"),
        ('pl_fin', "Financier"),
        ('pl_imp', "Impôts"),
        ('pl_extra', "Éléments extraordinaires"),
        # Divers
        ('info', "Données complémentaires"),
    ], string="Section", required=True)

    line_type = fields.Selection([
        ('input', "Saisissable"),
        ('subtotal', "Sous-total (calculé)"),
        ('total', "Total (calculé)"),
        ('title', "Titre de section"),
    ], string="Type de ligne", required=True, default='input')

    formula = fields.Char(
        string="Formule",
        help="Pour les sous-totaux et totaux : expression sur les codes de rubriques. "
             "Exemple : ST_ANC + ST_AC")

    sign = fields.Integer(
        string="Signe", default=1,
        help="+1 pour un produit / un actif, -1 pour une charge. "
             "Les charges sont saisies en positif et soustraites par les agrégats.")

    parent_id = fields.Many2one('fa.rubric', string="Rubrique parente", ondelete='cascade', index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('fa.rubric', 'parent_id', string="Sous-rubriques")

    is_detail = fields.Boolean(
        string="Poste de détail", default=False,
        help="Poste « dont ... » : informatif, non additionné dans les sous-totaux.")

    has_gross = fields.Boolean(
        string="Colonnes Brut/Amort.", default=False,
        help="Coché pour les postes du bilan actif présentés en Brut / Amortissements / Net.")

    pcg_accounts = fields.Char(
        string="Comptes PCG 2005",
        help="Comptes rattachés, pour mémoire et futur mapping automatique.")

    note = fields.Text(string="Aide à la saisie", translate=True)
    active = fields.Boolean(string="Actif", default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', "Le code de rubrique doit être unique."),
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s - %s" % (rec.code, rec.name)

    def name_get(self):
        return [(r.id, "%s - %s" % (r.code, r.name)) for r in self]
