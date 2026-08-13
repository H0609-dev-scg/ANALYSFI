# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FaRatio(models.Model):
    """Définition paramétrable d'un ratio financier.

    La formule est une expression Python évaluée en safe_eval sur un dictionnaire
    de variables pré-résolues (codes de rubriques + agrégats calculés).
    """
    _name = 'fa.ratio'
    _description = "Définition d'un ratio financier"
    _order = 'family, sequence, id'

    code = fields.Char(string="Code", required=True, index=True)
    name = fields.Char(string="Ratio", required=True, translate=True)
    sequence = fields.Integer(string="Séquence", default=10)

    family = fields.Selection([
        ('structure', "A. Structure financière et solvabilité"),
        ('liquidity', "B. Liquidité et trésorerie"),
        ('activity', "C. Activité, rotation et gestion"),
        ('profitability', "D. Rentabilité et marges"),
        ('value_added', "E. Répartition de la valeur ajoutée"),
        ('coverage', "F. Couverture et risque"),
    ], string="Famille", required=True, index=True)

    formula = fields.Char(
        string="Formule", required=True,
        help="Expression Python. Variables disponibles : codes de rubriques (ST_CP, AC_STOCK...) "
             "et agrégats (FRNG, BFR, TN, VA, EBE, CAF, CA...). "
             "Exemple : ST_AC / ST_PC")

    applicability = fields.Char(
        string="Condition d'applicabilité",
        help="Expression Python facultative. Si elle est renseignée et qu'elle est "
             "fausse, le ratio est marqué « sans objet » plutôt que calculé : "
             "aucune appréciation ni recommandation n'est produite. À utiliser "
             "lorsqu'un ratio perd son sens dans certaines configurations, par "
             "exemple la couverture du besoin en fonds de roulement quand celui-ci "
             "est négatif.")

    na_message = fields.Text(
        string="Message si sans objet", translate=True,
        help="Commentaire affiché à la place du constat lorsque la condition "
             "d'applicabilité n'est pas remplie.")

    unit = fields.Selection([
        ('percent', "%"),
        ('times', "×"),
        ('days', "jours"),
        ('amount', "Montant"),
        ('years', "années"),
    ], string="Unité", required=True, default='times')

    direction = fields.Selection([
        ('higher', "Plus c'est élevé, mieux c'est"),
        ('lower', "Plus c'est faible, mieux c'est"),
        ('range', "Plage optimale"),
    ], string="Sens de lecture", required=True, default='higher')

    threshold_bad = fields.Float(
        string="Seuil critique",
        help="En dessous (sens 'higher') ou au dessus (sens 'lower') : situation critique.")
    threshold_watch = fields.Float(string="Seuil de vigilance")
    threshold_good = fields.Float(string="Seuil de confort")
    threshold_max = fields.Float(
        string="Borne haute", help="Utilisé uniquement pour le sens « Plage optimale ».")

    norm_label = fields.Char(
        string="Norme indicative", translate=True,
        help="Texte affiché dans les rapports, ex. « > 30 % » ou « 30 à 90 jours ».")

    annualize = fields.Boolean(
        string="Annualiser les flux", default=True,
        help="Si coché, les flux du compte de résultat d'une période infra-annuelle sont "
             "ramenés à 12 mois avant calcul. À décocher pour les ratios purement bilanciels.")

    interpretation = fields.Text(
        string="Ce que mesure le ratio", translate=True,
        help="Définition et portée de l'indicateur, en langage accessible à un "
             "lecteur non financier. Repris dans les fiches du rapport.")

    calculation_note = fields.Text(
        string="Précisions de calcul", translate=True,
        help="Numérateur et dénominateur détaillés, retraitements appliqués, "
             "données complémentaires utilisées. Permet de justifier une valeur "
             "auprès du client.")

    threshold_rationale = fields.Text(
        string="Justification des seuils", translate=True,
        help="Origine et signification des seuils retenus : pourquoi cette "
             "frontière plutôt qu'une autre, ce que traduit son franchissement.")

    limits = fields.Text(
        string="Limites d'interprétation", translate=True,
        help="Configurations dans lesquelles le ratio perd sa pertinence ou "
             "doit être lu avec précaution.")

    threshold_summary = fields.Char(
        string="Grille de lecture", compute='_compute_threshold_summary',
        help="Résumé des quatre niveaux d'appréciation, généré à partir des seuils.")

    rule_ids = fields.One2many('fa.comment.rule', 'ratio_id', string="Règles de commentaire")
    sector_norm_ids = fields.One2many(
        'fa.sector.norm', 'ratio_id', string="Normes sectorielles",
        help="Seuils spécifiques par secteur. Ils prennent le pas sur les seuils "
             "génériques ci-dessus lorsqu'ils existent pour le secteur du client.")
    sector_norm_count = fields.Integer(
        string="Nb normes sectorielles", compute='_compute_sector_norm_count')
    active = fields.Boolean(string="Actif", default=True)

    @api.depends('sector_norm_ids')
    def _compute_sector_norm_count(self):
        for rec in self:
            rec.sector_norm_count = len(rec.sector_norm_ids)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', "Le code du ratio doit être unique."),
    ]

    def name_get(self):
        return [(r.id, "%s - %s" % (r.code, r.name)) for r in self]

    @api.depends('threshold_bad', 'threshold_watch', 'threshold_good',
                 'threshold_max', 'direction', 'unit')
    def _compute_threshold_summary(self):
        """Rend la grille d'appréciation lisible d'un coup d'œil."""
        for rec in self:
            fmt = rec._format_threshold
            if rec.direction == 'higher':
                rec.threshold_summary = _(
                    "Critique < %(b)s  ·  À surveiller < %(w)s  ·  "
                    "Correct < %(g)s  ·  Solide ≥ %(g)s",
                    b=fmt(rec.threshold_bad), w=fmt(rec.threshold_watch),
                    g=fmt(rec.threshold_good))
            elif rec.direction == 'lower':
                rec.threshold_summary = _(
                    "Critique > %(b)s  ·  À surveiller > %(w)s  ·  "
                    "Correct > %(g)s  ·  Solide ≤ %(g)s",
                    b=fmt(rec.threshold_bad), w=fmt(rec.threshold_watch),
                    g=fmt(rec.threshold_good))
            else:
                rec.threshold_summary = _(
                    "Solide entre %(w)s et %(m)s  ·  À surveiller au-delà  ·  "
                    "Critique sous %(b)s",
                    w=fmt(rec.threshold_watch), m=fmt(rec.threshold_max),
                    b=fmt(rec.threshold_bad))

    def _format_threshold(self, value):
        """Met en forme un seuil selon l'unité du ratio."""
        self.ensure_one()
        if self.unit == 'percent':
            return "%g %%" % value
        if self.unit == 'days':
            return "%g j" % value
        if self.unit == 'years':
            return "%g an(s)" % value
        if self.unit == 'times':
            return "%g" % value
        return "%g" % value

    @api.constrains('threshold_bad', 'threshold_watch', 'threshold_good',
                    'threshold_max', 'direction')
    def _check_threshold_order(self):
        """Garantit que les seuils sont ordonnés selon le sens de lecture."""
        for rec in self:
            b, w, g = rec.threshold_bad, rec.threshold_watch, rec.threshold_good
            if rec.direction == 'higher' and not (b <= w <= g):
                raise ValidationError(_(
                    "Ratio %(c)s : pour un sens « plus c'est élevé, mieux c'est », "
                    "les seuils doivent être croissants (critique ≤ vigilance ≤ "
                    "confort). Valeurs saisies : %(b)s / %(w)s / %(g)s.",
                    c=rec.code, b=b, w=w, g=g))
            if rec.direction == 'lower' and not (b >= w >= g):
                raise ValidationError(_(
                    "Ratio %(c)s : pour un sens « plus c'est faible, mieux c'est », "
                    "les seuils doivent être décroissants (critique ≥ vigilance ≥ "
                    "confort). Valeurs saisies : %(b)s / %(w)s / %(g)s.",
                    c=rec.code, b=b, w=w, g=g))
            if rec.direction == 'range' and not rec.threshold_max:
                raise ValidationError(_(
                    "Ratio %(c)s : un ratio à plage optimale exige une borne haute.",
                    c=rec.code))

    def get_thresholds(self, sector=None):
        """Retourne les seuils applicables, en privilégiant la norme sectorielle.

        :param sector: recordset fa.sector (ou False pour les seuils génériques)
        :return: dict avec bad, watch, good, max, label, median, comment, is_sector
        """
        self.ensure_one()
        generic = {
            'bad': self.threshold_bad,
            'watch': self.threshold_watch,
            'good': self.threshold_good,
            'max': self.threshold_max,
            'label': self.norm_label or '',
            'median': 0.0,
            'comment': '',
            'is_sector': False,
        }
        if not sector:
            return generic
        norm = self.sector_norm_ids.filtered(
            lambda n: n.sector_id == sector and n.active)[:1]
        if not norm:
            return generic
        return {
            'bad': norm.threshold_bad,
            'watch': norm.threshold_watch,
            'good': norm.threshold_good,
            'max': norm.threshold_max,
            'label': norm.norm_label or self.norm_label or '',
            'median': norm.sector_median,
            'comment': norm.comment or '',
            'is_sector': True,
        }

    def _evaluate_appreciation(self, value, thresholds=None):
        """Retourne le niveau d'appréciation d'une valeur : bad / watch / ok / good.

        :param thresholds: dict de seuils (issu de get_thresholds). Si absent,
                           les seuils génériques du ratio sont utilisés.
        """
        self.ensure_one()
        if value is None:
            return False
        t = thresholds or self.get_thresholds()
        if self.direction == 'higher':
            if value < t['bad']:
                return 'bad'
            if value < t['watch']:
                return 'watch'
            if value < t['good']:
                return 'ok'
            return 'good'
        if self.direction == 'lower':
            if value > t['bad']:
                return 'bad'
            if value > t['watch']:
                return 'watch'
            if value > t['good']:
                return 'ok'
            return 'good'
        # Plage optimale : bon entre watch et max
        if t['watch'] <= value <= t['max']:
            return 'good'
        upper = t['max'] + abs(t['max']) * 0.5 if t['max'] else 1e12
        if t['bad'] <= value <= upper:
            return 'watch'
        return 'bad'
