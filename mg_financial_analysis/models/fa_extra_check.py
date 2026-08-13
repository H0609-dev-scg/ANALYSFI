# -*- coding: utf-8 -*-
"""Contrôles de vraisemblance sur les informations complémentaires.

Ces données ne figurent pas au bilan : rien ne les contraint, aucune égalité
comptable ne les vérifie. Une valeur aberrante y passe donc inaperçue et
fausse silencieusement les ratios qui en dépendent.

Chaque contrôle rapproche une saisie d'une grandeur du bilan ou du compte de
résultat et signale les écarts improbables. Il s'agit d'alertes, jamais de
blocages : le consultant reste juge.
"""
from odoo import models, fields, api, _


class FaExtraCheck(models.Model):
    _name = 'fa.extra.check'
    _description = "Contrôle de vraisemblance d'une donnée complémentaire"
    _order = 'statement_id, severity desc, sequence'

    statement_id = fields.Many2one(
        'fa.statement', string="Période", required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='statement_id.currency_id', store=True)
    sequence = fields.Integer(default=10)

    code = fields.Char(string="Contrôle", index=True)
    rubric_code = fields.Char(string="Rubrique concernée")
    name = fields.Char(string="Donnée", required=True)

    severity = fields.Selection([
        ('error', "Incohérence"),
        ('warning', "À vérifier"),
        ('info', "Information"),
    ], string="Niveau", required=True, default='warning', index=True)

    value_entered = fields.Monetary(string="Valeur saisie")
    value_expected = fields.Monetary(string="Valeur attendue")
    gap = fields.Monetary(string="Écart", compute='_compute_gap', store=True)
    gap_pct = fields.Float(string="Écart %", digits=(16, 1),
                           compute='_compute_gap', store=True, group_operator=False)

    message = fields.Text(string="Constat")
    suggestion = fields.Text(string="Que faire")
    impact = fields.Char(string="Ratios impactés")

    @api.depends('value_entered', 'value_expected')
    def _compute_gap(self):
        for rec in self:
            rec.gap = rec.value_entered - rec.value_expected
            rec.gap_pct = ((rec.gap / abs(rec.value_expected) * 100.0)
                           if rec.value_expected else 0.0)


class FaStatementExtraCheck(models.Model):
    _inherit = 'fa.statement'

    extra_check_ids = fields.One2many(
        'fa.extra.check', 'statement_id', string="Contrôles de vraisemblance")
    extra_error_count = fields.Integer(
        string="Incohérences", compute='_compute_extra_check_summary', store=True)
    extra_warning_count = fields.Integer(
        string="Points à vérifier", compute='_compute_extra_check_summary', store=True)

    @api.depends('extra_check_ids.severity')
    def _compute_extra_check_summary(self):
        for rec in self:
            rec.extra_error_count = len(
                rec.extra_check_ids.filtered(lambda c: c.severity == 'error'))
            rec.extra_warning_count = len(
                rec.extra_check_ids.filtered(lambda c: c.severity == 'warning'))

    # ------------------------------------------------------------------
    def _run_extra_checks(self):
        """Confronte chaque donnée complémentaire aux états financiers."""
        self.ensure_one()
        self.extra_check_ids.unlink()
        v = self._get_values_dict()
        prev = {}
        if self.previous_statement_id:
            prev = self.previous_statement_id._get_values_dict()
        else:
            for line in self.line_ids:
                if line.code:
                    prev[line.code] = line.amount_previous

        rows = []
        seq = [0]

        def add(code, rubric, name, severity, entered, expected,
                message, suggestion, impact=''):
            seq[0] += 10
            rows.append({
                'statement_id': self.id, 'sequence': seq[0], 'code': code,
                'rubric_code': rubric, 'name': name, 'severity': severity,
                'value_entered': entered, 'value_expected': expected,
                'message': message, 'suggestion': suggestion, 'impact': impact,
            })

        get = lambda c: v.get(c, 0.0)

        # ---------- Actifs fictifs ----------
        fictif = get('IN_ACTIF_FICTIF')
        immo_fin = get('AC_IMMO_FIN')
        if fictif:
            if immo_fin and abs(fictif - immo_fin) < 1:
                add('FICTIF_IMMOFIN', 'IN_ACTIF_FICTIF', _("Actifs fictifs"),
                    'error', fictif, 0.0,
                    _("Le montant saisi en actifs fictifs correspond exactement aux "
                      "immobilisations financières du bilan. Or les titres et prêts "
                      "possèdent une valeur de réalisation : ce ne sont pas des actifs "
                      "fictifs. Cette rubrique ne vise que les frais d'établissement "
                      "et les charges à répartir, dépourvus de valeur patrimoniale."),
                    _("Vider ce champ, sauf si l'entreprise porte réellement des frais "
                      "d'établissement non amortis pour ce montant."),
                    "A6, A7, A9, ANC, CP retraités")
            elif fictif > get('ST_ANC') * 0.5:
                add('FICTIF_ELEVE', 'IN_ACTIF_FICTIF', _("Actifs fictifs"),
                    'warning', fictif, get('ST_ANC') * 0.1,
                    _("Les actifs fictifs représentent plus de la moitié de l'actif "
                      "immobilisé, proportion inhabituelle."),
                    _("Vérifier la nature des montants retenus."),
                    "A6, A7, A9")

        # ---------- Chiffre d'affaires TTC ----------
        ca_ht = get('CA')
        ca_ttc = get('IN_CA_TTC')
        if ca_ttc and ca_ht:
            coef = ca_ttc / ca_ht
            if coef < 1.0:
                add('CATTC_INF', 'IN_CA_TTC', _("Chiffre d'affaires TTC"),
                    'error', ca_ttc, ca_ht * 1.20,
                    _("Le chiffre d'affaires TTC est inférieur au montant hors taxes, "
                      "ce qui est impossible."),
                    _("Saisir le chiffre d'affaires taxes comprises, ou laisser le "
                      "champ vide pour que le module l'estime à hauteur de 120 %% du "
                      "montant hors taxes."),
                    "C3 délai clients, C5 cycle d'exploitation")
            elif coef > 1.25 or coef < 1.15:
                add('CATTC_COEF', 'IN_CA_TTC', _("Chiffre d'affaires TTC"),
                    'warning', ca_ttc, ca_ht * 1.20,
                    _("Le rapport entre chiffre d'affaires TTC et HT ressort à "
                      "%(c).3f, alors que la taxe sur la valeur ajoutée malgache "
                      "s'établit à 20 %%, soit un coefficient de 1,200. Un écart "
                      "peut se justifier par des ventes exonérées ou à l'export, "
                      "mais mérite vérification.", c=coef),
                    _("Contrôler le montant en le rapprochant des déclarations de "
                      "taxe sur la valeur ajoutée de l'exercice."),
                    "C3 délai clients, C5 cycle d'exploitation")

        # ---------- Achats TTC ----------
        achats_ht = get('PL_ACHATS') + get('PL_ACHAT_MSE')
        achats_avec_services = achats_ht + get('PL_SERV_EXT')
        achats_ttc = get('IN_ACHATS_TTC')
        if achats_ttc and achats_ht:
            coef = achats_ttc / achats_ht
            coef_avec = achats_ttc / achats_avec_services if achats_avec_services else 0
            if coef < 1.0:
                add('ACHTTC_INF', 'IN_ACHATS_TTC', _("Achats TTC"),
                    'error', achats_ttc, achats_ht * 1.20,
                    _("Les achats TTC sont inférieurs aux achats hors taxes."),
                    _("Saisir le montant taxes comprises."),
                    "C4 délai fournisseurs, C5 cycle d'exploitation")
            elif coef > 1.30:
                expected = achats_avec_services * 1.20
                add('ACHTTC_COEF', 'IN_ACHATS_TTC', _("Achats TTC"),
                    'warning', achats_ttc, expected,
                    _("Le rapport entre achats TTC et achats hors taxes atteint "
                      "%(c).3f, très au-delà du coefficient de 1,200 correspondant "
                      "à la taxe sur la valeur ajoutée. En incluant les services "
                      "extérieurs, le rapport ressort à %(c2).3f. Si le crédit "
                      "fournisseur porte aussi sur les services, la base doit les "
                      "comprendre : %(e)s taxes comprises.",
                      c=coef, c2=coef_avec,
                      e='{:,.0f}'.format(expected).replace(',', '\u202f')),
                    _("Retenir comme base l'ensemble des achats et services facturés "
                      "par les fournisseurs figurant au poste « Fournisseurs et "
                      "comptes rattachés », taxes comprises."),
                    "C4 délai fournisseurs, C5 cycle d'exploitation")

        # ---------- Stock moyen ----------
        stock_moyen = get('IN_STOCK_MOYEN')
        stock_final = get('AC_STOCK')
        stock_prev = prev.get('AC_STOCK', 0.0)
        if stock_moyen:
            theorique = ((stock_final + stock_prev) / 2.0) if stock_prev else stock_final
            if stock_moyen > max(stock_final, stock_prev) * 1.1:
                add('STOCKMOY_HAUT', 'IN_STOCK_MOYEN', _("Stock moyen"),
                    'warning', stock_moyen, theorique,
                    _("Le stock moyen dépasse le plus élevé des stocks d'ouverture et "
                      "de clôture, ce qui suppose un pic marqué en cours d'exercice."),
                    _("Confirmer la méthode de calcul retenue, ou reprendre la moyenne "
                      "des stocks d'ouverture et de clôture."),
                    "C1 délai d'écoulement, C2 rotation, C5 cycle")
            elif theorique and abs(stock_moyen - theorique) / theorique > 0.15:
                add('STOCKMOY_ECART', 'IN_STOCK_MOYEN', _("Stock moyen"),
                    'info', stock_moyen, theorique,
                    _("Le stock moyen saisi s'écarte de %(p).1f %% de la moyenne des "
                      "stocks d'ouverture et de clôture. Un calcul sur douze mois "
                      "explique légitimement cet écart.",
                      p=abs(stock_moyen - theorique) / theorique * 100),
                    _("Aucune action si la valeur provient d'une moyenne mensuelle."),
                    "C1, C2, C5")
        elif stock_final and stock_prev:
            add('STOCKMOY_VIDE', 'IN_STOCK_MOYEN', _("Stock moyen"),
                'info', 0.0, (stock_final + stock_prev) / 2.0,
                _("Le stock moyen n'est pas renseigné : le stock de clôture est "
                  "utilisé par défaut. Pour une activité saisonnière, cette "
                  "approximation fausse la rotation."),
                _("Renseigner la moyenne des stocks d'ouverture et de clôture, soit "
                  "%(v)s, ou une moyenne mensuelle si vous en disposez.",
                  v='{:,.0f}'.format((stock_final + stock_prev) / 2.0)
                  .replace(',', '\u202f')),
                "C1, C2, C5")

        # ---------- Effectif ----------
        if not get('IN_EFFECTIF') and get('VA'):
            add('EFFECTIF_VIDE', 'IN_EFFECTIF', _("Effectif moyen"),
                'warning', 0.0, 0.0,
                _("L'effectif moyen n'est pas renseigné : trois ratios de "
                  "productivité ne peuvent être calculés."),
                _("Indiquer l'effectif moyen de la période, équivalents temps plein "
                  "compris."),
                "C8 productivité, C9 rendement, C10 intensité capitalistique")

        # ---------- Emprunts ----------
        nouveaux = get('IN_EMPRUNTS_NOUVEAUX')
        rembours = get('IN_REMB_EMPRUNTS')
        d_emprunt = get('PA_EMPRUNT_NC') - prev.get('PA_EMPRUNT_NC', 0.0)
        if nouveaux and rembours and abs(nouveaux - rembours) < 1:
            add('EMPRUNT_DOUBLE', 'IN_EMPRUNTS_NOUVEAUX', _("Emprunts"),
                'error', nouveaux, 0.0,
                _("Le même montant figure en nouveaux emprunts et en remboursements. "
                  "Le tableau des flux affiche alors trois lignes dont deux ne "
                  "correspondent à aucun mouvement réel."),
                _("Si l'emprunt a seulement été remboursé, vider le champ des "
                  "nouveaux emprunts. S'il y a eu un refinancement, saisir les "
                  "montants réellement encaissés et décaissés."),
                "Tableau des flux, section financement")
        elif (nouveaux or rembours):
            attendu = nouveaux - rembours
            if abs(attendu - d_emprunt) > max(abs(d_emprunt) * 0.02, 1.0):
                add('EMPRUNT_ECART', 'IN_EMPRUNTS_NOUVEAUX', _("Emprunts"),
                    'warning', attendu, d_emprunt,
                    _("La variation nette déclarée (%(a)s) ne correspond pas à celle "
                      "constatée au bilan (%(b)s).",
                      a='{:,.0f}'.format(attendu).replace(',', '\u202f'),
                      b='{:,.0f}'.format(d_emprunt).replace(',', '\u202f')),
                    _("Rapprocher les montants du tableau d'amortissement des "
                      "emprunts. Un écart peut provenir d'intérêts capitalisés."),
                    "Tableau des flux, section financement")

        # ---------- Dividendes ----------
        dividendes = get('IN_DIVIDENDES')
        if dividendes:
            d_cp = get('ST_CP') - prev.get('ST_CP', 0.0)
            resultat = get('PA_RESULTAT')
            attendu = resultat - dividendes
            if prev and abs(d_cp - attendu) > max(abs(attendu) * 0.05, 1.0):
                add('DIV_ECART', 'IN_DIVIDENDES', _("Dividendes"),
                    'warning', dividendes, max(0.0, resultat - d_cp),
                    _("La variation des capitaux propres (%(v)s) ne reflète pas la "
                      "distribution déclarée. Avec un résultat de %(r)s et des "
                      "dividendes de %(d)s, les capitaux propres devraient progresser "
                      "de %(a)s.",
                      v='{:,.0f}'.format(d_cp).replace(',', '\u202f'),
                      r='{:,.0f}'.format(resultat).replace(',', '\u202f'),
                      d='{:,.0f}'.format(dividendes).replace(',', '\u202f'),
                      a='{:,.0f}'.format(attendu).replace(',', '\u202f')),
                    _("Vérifier que la distribution a bien été votée et versée sur "
                      "l'exercice. Ce montant sort les dividendes des capitaux "
                      "permanents et réduit d'autant le fonds de roulement."),
                    "FRNG, A5, A6, B4, tableau des capitaux propres")

        # ---------- Investissements ----------
        inv = get('IN_INVESTISSEMENTS')
        if inv:
            d_immo = (get('AC_IMMO_CORP') + get('AC_IMMO_INC') + get('AC_IMMO_ENC')
                      - prev.get('AC_IMMO_CORP', 0.0) - prev.get('AC_IMMO_INC', 0.0)
                      - prev.get('AC_IMMO_ENC', 0.0))
            reconstitue = d_immo + get('PL_DOTATIONS') + get('IN_VNC_CEDEE')
            d_fin = get('AC_IMMO_FIN') - prev.get('AC_IMMO_FIN', 0.0)
            if prev and abs(inv - reconstitue) > max(abs(reconstitue) * 0.02, 1.0):
                extra = ''
                if d_fin and abs(inv - reconstitue - d_fin) < max(abs(d_fin) * 0.05, 1.0):
                    extra = _(" L'écart correspond à la variation des immobilisations "
                              "financières : les titres ont probablement été inclus "
                              "dans le montant déclaré.")
                add('INV_ECART', 'IN_INVESTISSEMENTS', _("Investissements"),
                    'warning', inv, reconstitue,
                    _("Le montant déclaré s'écarte de celui reconstitué à partir des "
                      "variations de bilan et des dotations.%(e)s", e=extra),
                    _("Ne retenir que les acquisitions d'immobilisations corporelles "
                      "et incorporelles. Les titres relèvent d'une rubrique distincte."),
                    "F4 taux d'investissement, F5 autofinancement, tableau des flux")

        # ---------- Immobilisations brutes et amortissements ----------
        brut = get('IN_IMMO_BRUT')
        amort = get('IN_AMORT_CUMUL')
        net = get('AC_IMMO_CORP')
        if brut and amort:
            if amort > brut:
                add('AMORT_SUP', 'IN_AMORT_CUMUL', _("Amortissements cumulés"),
                    'error', amort, brut,
                    _("Les amortissements cumulés dépassent la valeur brute."),
                    _("Vérifier les deux montants dans le tableau des immobilisations."),
                    "A10 vétusté de l'outil")
            elif net and abs((brut - amort) - net) > max(net * 0.05, 1.0):
                add('IMMO_NET_ECART', 'IN_IMMO_BRUT', _("Immobilisations brutes"),
                    'warning', brut - amort, net,
                    _("La valeur nette déduite (brut moins amortissements) ne "
                      "correspond pas au montant inscrit au bilan."),
                    _("Rapprocher du tableau des immobilisations. Les immobilisations "
                      "incorporelles et en cours peuvent expliquer l'écart."),
                    "A10 vétusté de l'outil")
        elif net and not brut:
            add('IMMO_BRUT_VIDE', 'IN_IMMO_BRUT', _("Immobilisations brutes"),
                'info', 0.0, 0.0,
                _("Les valeurs brutes et les amortissements cumulés ne sont pas "
                  "renseignés : la vétusté de l'outil ne peut être appréciée."),
                _("Reprendre les montants du tableau des immobilisations de l'annexe."),
                "A10 vétusté de l'outil")

        # ---------- Cessions ----------
        vnc = get('IN_VNC_CEDEE')
        prod_cess = get('IN_PROD_CESSION')
        if prod_cess and not vnc:
            add('CESSION_SANS_VNC', 'IN_VNC_CEDEE', _("Valeur nette des biens cédés"),
                'warning', 0.0, 0.0,
                _("Un produit de cession est déclaré sans valeur nette comptable "
                  "correspondante : la plus-value est donc supposée égale au prix "
                  "de vente."),
                _("Indiquer la valeur nette comptable des biens sortis, sans quoi la "
                  "capacité d'autofinancement est surestimée."),
                "CAF, tableau des flux")

        # ---------- Trésorerie d'ouverture ----------
        if not self.previous_statement_id and not get('IN_TRESO_OUVERTURE'):
            if any(line.amount_previous for line in self.line_ids):
                pass
            else:
                add('TRESO_OUV_VIDE', 'IN_TRESO_OUVERTURE',
                    _("Trésorerie d'ouverture"), 'warning', 0.0, 0.0,
                    _("Sans période de comparaison ni trésorerie d'ouverture, le "
                      "tableau des flux ne peut être établi."),
                    _("Renseigner la trésorerie au premier jour de la période, ou "
                      "rattacher une période de référence au dossier."),
                    "Tableau des flux de trésorerie")

        # ---------- Charges fixes et variables ----------
        cv, cf = get('IN_CHARGES_VARIABLES'), get('IN_CHARGES_FIXES')
        if cv and cf:
            total = cv + cf
            charges = (get('PL_ACHAT_MSE') + get('PL_ACHATS') + get('PL_SERV_EXT')
                       + get('PL_PERSONNEL') + get('PL_IMPOTS_TAXES')
                       + get('PL_DOTATIONS') + get('PL_CH_FIN'))
            if charges and abs(total - charges) > charges * 0.10:
                add('CHARGES_ECART', 'IN_CHARGES_VARIABLES',
                    _("Charges fixes et variables"), 'warning', total, charges,
                    _("La somme des charges fixes et variables s'écarte de plus de "
                      "dix pour cent du total des charges du compte de résultat."),
                    _("La ventilation doit couvrir l'ensemble des charges "
                      "d'exploitation et financières."),
                    "Seuil de rentabilité, D11 point mort, D12 marge de sécurité")
        elif cv and not cf:
            add('CF_MANQUANT', 'IN_CHARGES_FIXES', _("Charges fixes"),
                'warning', 0.0, 0.0,
                _("Les charges variables sont renseignées sans les charges fixes : "
                  "la méthode des coûts variables ne peut être appliquée."),
                _("Compléter la ventilation, ou vider les deux champs pour utiliser "
                  "la méthode fondée sur l'excédent brut d'exploitation."),
                "Seuil de rentabilité")

        # ---------- Crédit-bail ----------
        cb_net = get('IN_CB_VNC')
        cb_dette = get('IN_CB_DETTE_LT') + get('IN_CB_DETTE_CT')
        if cb_net and not cb_dette:
            add('CB_SANS_DETTE', 'IN_CB_DETTE_LT', _("Crédit-bail"),
                'error', 0.0, cb_net,
                _("Une valeur nette de biens en crédit-bail est déclarée sans dette "
                  "correspondante. Le retraitement inscrit alors un actif sans "
                  "contrepartie au passif et déséquilibre le bilan financier."),
                _("Renseigner la dette résiduelle, ventilée entre la part à plus "
                  "d'un an et celle à moins d'un an."),
                "AI, capitaux permanents, FRNG, A5, A6")

        if rows:
            self.env['fa.extra.check'].create(rows)
        return rows

    def action_suggest_extra(self):
        """Pré-remplit les données déductibles des états financiers.

        Ne touche jamais une valeur déjà saisie : ces suggestions servent de
        point de départ, le consultant reste maître de chaque montant.
        """
        self.ensure_one()
        v = self._get_values_dict()
        prev = {}
        if self.previous_statement_id:
            prev = self.previous_statement_id._get_values_dict()
        else:
            for line in self.line_ids:
                if line.code:
                    prev[line.code] = line.amount_previous

        g = lambda c: v.get(c, 0.0)
        suggestions = {}

        # Chiffre d'affaires TTC : taxe sur la valeur ajoutée à 20 %
        if g('CA') and not g('IN_CA_TTC'):
            suggestions['IN_CA_TTC'] = round(g('CA') * 1.20, 2)

        # Achats TTC : achats et services facturés par les fournisseurs
        base = g('PL_ACHATS') + g('PL_ACHAT_MSE') + g('PL_SERV_EXT')
        if base and not g('IN_ACHATS_TTC'):
            suggestions['IN_ACHATS_TTC'] = round(base * 1.20, 2)

        # Stock moyen : moyenne des stocks d'ouverture et de clôture
        if g('AC_STOCK') and prev.get('AC_STOCK') and not g('IN_STOCK_MOYEN'):
            suggestions['IN_STOCK_MOYEN'] = round(
                (g('AC_STOCK') + prev['AC_STOCK']) / 2.0, 2)

        # Trésorerie d'ouverture
        if prev and not g('IN_TRESO_OUVERTURE'):
            ouverture = (prev.get('AC_TRESO', 0.0) + prev.get('AC_PLACEMENT', 0.0)
                         - prev.get('PA_TRESO_PASSIF', 0.0))
            if ouverture:
                suggestions['IN_TRESO_OUVERTURE'] = round(ouverture, 2)

        # Investissements reconstitués
        if prev and not g('IN_INVESTISSEMENTS'):
            d_immo = (g('AC_IMMO_CORP') + g('AC_IMMO_INC') + g('AC_IMMO_ENC')
                      - prev.get('AC_IMMO_CORP', 0.0) - prev.get('AC_IMMO_INC', 0.0)
                      - prev.get('AC_IMMO_ENC', 0.0))
            estimation = d_immo + g('PL_DOTATIONS')
            if estimation > 0:
                suggestions['IN_INVESTISSEMENTS'] = round(estimation, 2)

        # Mouvements d'emprunts déduits de la variation de bilan
        d_emp = g('PA_EMPRUNT_NC') - prev.get('PA_EMPRUNT_NC', 0.0)
        if prev and d_emp and not (g('IN_EMPRUNTS_NOUVEAUX') or g('IN_REMB_EMPRUNTS')):
            if d_emp > 0:
                suggestions['IN_EMPRUNTS_NOUVEAUX'] = round(d_emp, 2)
            else:
                suggestions['IN_REMB_EMPRUNTS'] = round(-d_emp, 2)

        # Immobilisations brutes et amortissements
        if g('AC_IMMO_CORP') and not g('IN_IMMO_BRUT') and g('IN_AMORT_CUMUL'):
            suggestions['IN_IMMO_BRUT'] = round(
                g('AC_IMMO_CORP') + g('IN_AMORT_CUMUL'), 2)

        applied = 0
        Rubric = self.env['fa.rubric']
        for code, amount in suggestions.items():
            rubric = Rubric.search([('code', '=', code)], limit=1)
            if not rubric:
                continue
            line = self.line_ids.filtered(lambda l, r=rubric: l.rubric_id == r)
            if line and not line.amount_net:
                line.amount_net = amount
                line.note = _("Suggestion automatique, à confirmer")
                applied += 1

        self._run_extra_checks()
        if not applied:
            message = _("Aucune suggestion : les données déductibles des états "
                        "financiers sont déjà renseignées.")
        else:
            message = _(
                "%(n)s valeur(s) pré-remplie(s) à partir des états financiers. "
                "Elles portent la mention « Suggestion automatique » : vérifiez-les "
                "et corrigez-les au besoin avant de valider.", n=applied)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _("Pré-remplissage"), 'message': message,
                       'type': 'success', 'sticky': True},
        }

    def action_check_extra(self):
        """Lance les contrôles sans relancer l'analyse complète."""
        self.ensure_one()
        self._run_extra_checks()
        errors = self.extra_error_count
        warnings = self.extra_warning_count
        if not errors and not warnings:
            message = _("Aucune anomalie détectée sur les informations "
                        "complémentaires.")
            kind = 'success'
        else:
            message = _("%(e)s incohérence(s) et %(w)s point(s) à vérifier. "
                        "Consultez l'onglet « Informations complémentaires ».",
                        e=errors, w=warnings)
            kind = 'warning' if not errors else 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _("Contrôle de vraisemblance"),
                       'message': message, 'type': kind, 'sticky': bool(errors)},
        }
