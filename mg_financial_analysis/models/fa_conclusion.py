# -*- coding: utf-8 -*-
"""Rédaction automatique d'un projet de conclusion.

Le texte produit est un **premier jet** destiné à être relu et corrigé par le
consultant. Il s'appuie exclusivement sur les valeurs calculées : aucune
affirmation n'est avancée sans support chiffré.
"""
from odoo import models, fields, api, _


class FaConclusionMixin(models.AbstractModel):
    _name = 'fa.conclusion.builder'
    _description = "Génération du projet de conclusion"

    @api.model
    def _fmt_amount(self, value, currency=None):
        txt = '{:,.0f}'.format(value).replace(',', '\u202f')
        return "%s %s" % (txt, currency.name) if currency else txt

    @api.model
    def build(self, analysis):
        """Retourne le projet de conclusion en HTML pour un dossier."""
        stmts = analysis.statement_ids.filtered(
            lambda s: s.state == 'analyzed').sorted('date_to')
        if not stmts:
            return _("<p>Aucune période analysée : lancez d'abord l'analyse "
                     "d'au moins un exercice.</p>")
        last = stmts[-1]
        first = stmts[0]
        multi = len(stmts) > 1
        cur = analysis.currency_id
        name = analysis.partner_id.name or _("L'entreprise")
        paras = []

        v = last._get_values_dict(annualized=True)

        # ---------- 1. Cadrage de la mission ----------
        if multi:
            periods = ", ".join(s.name for s in stmts)
            intro = _(
                "<p>La présente analyse porte sur %(n)s, société du secteur "
                "« %(sec)s », et couvre %(nb)s périodes : %(per)s.",
                n=name, sec=analysis.sector_id.name or '', nb=len(stmts), per=periods)
            if any(s.duration_months != 12 for s in stmts):
                intro += _(
                    " Les flux des périodes infra-annuelles ont été annualisés afin de "
                    "permettre une lecture homogène de la trajectoire.")
        else:
            intro = _(
                "<p>La présente analyse porte sur %(n)s, société du secteur "
                "« %(sec)s », et couvre la période %(per)s.",
                n=name, sec=analysis.sector_id.name or '', per=last.name)
        if not last.is_audited:
            intro += _(
                " Les états financiers examinés n'ont pas fait l'objet d'un audit : "
                "les conclusions qui suivent reposent sur les documents communiqués "
                "par la direction.")
        paras.append(intro + "</p>")

        # ---------- 2. Activité et rentabilité ----------
        ca = v.get('CA', 0.0)
        ebe = v.get('EBE', 0.0)
        rn = v.get('RN', 0.0)
        marge_ebe = (ebe / ca * 100) if ca else 0.0
        marge_nette = (rn / ca * 100) if ca else 0.0

        act = _("<p><b>Activité et rentabilité.</b> ")
        if multi:
            ca_first = first._get_values_dict(annualized=True).get('CA', 0.0)
            evol = ((ca - ca_first) / abs(ca_first) * 100) if ca_first else 0.0
            sens = _("progressé") if evol > 1 else _("reculé") if evol < -1 else _("stagné")
            act += _(
                "Le chiffre d'affaires a %(s)s de %(e).1f %% entre %(p1)s et %(p2)s, "
                "pour atteindre %(ca)s en base annuelle. ",
                s=sens, e=abs(evol), p1=first.name, p2=last.name,
                ca=self._fmt_amount(ca, cur))
        else:
            act += _("Le chiffre d'affaires s'établit à %(ca)s. ",
                     ca=self._fmt_amount(ca, cur))
        act += _(
            "L'excédent brut d'exploitation ressort à %(ebe)s, soit %(m).1f %% du chiffre "
            "d'affaires, et le résultat net à %(rn)s (%(mn).1f %%). ",
            ebe=self._fmt_amount(ebe, cur), m=marge_ebe,
            rn=self._fmt_amount(rn, cur), mn=marge_nette)
        if rn < 0:
            act += _(
                "L'exercice se solde par une perte, qui vient réduire les capitaux "
                "propres à due concurrence. ")
        if ebe < 0:
            act += _(
                "Le fait que l'excédent brut d'exploitation soit négatif est le point "
                "le plus préoccupant : l'activité courante détruit de la valeur, "
                "indépendamment de toute politique d'amortissement ou de financement. ")
        elif marge_ebe < 5:
            act += _(
                "Le niveau de marge brute d'exploitation laisse peu de ressources pour "
                "financer les amortissements et le service de la dette. ")
        paras.append(act + "</p>")

        # ---------- 3. Équilibre financier ----------
        frng = v.get('FRNG', 0.0)
        bfr = v.get('BFR', 0.0)
        tn = v.get('TN', 0.0)
        eq = _("<p><b>Équilibre financier.</b> ")
        eq += _(
            "Le fonds de roulement net global s'élève à %(fr)s et le besoin en fonds de "
            "roulement à %(bfr)s, dégageant une trésorerie nette de %(tn)s. ",
            fr=self._fmt_amount(frng, cur), bfr=self._fmt_amount(bfr, cur),
            tn=self._fmt_amount(tn, cur))
        if tn < 0 and frng > 0:
            eq += _(
                "Le fonds de roulement, bien que positif, ne couvre pas l'intégralité du "
                "besoin d'exploitation : le solde est financé par des concours bancaires "
                "courants, ressources coûteuses et révocables sans préavis. ")
        elif tn < 0 and frng <= 0:
            eq += _(
                "Le fonds de roulement est négatif : une partie des emplois durables est "
                "financée par des ressources à court terme, ce qui rompt la règle "
                "fondamentale de l'équilibre financier. ")
        else:
            eq += _("La structure de financement du cycle d'exploitation est équilibrée. ")
        if ca:
            eq += _(
                "Rapporté à l'activité, le besoin en fonds de roulement représente "
                "%(j).0f jours de chiffre d'affaires. ", j=bfr * 360 / ca)
        paras.append(eq + "</p>")

        # ---------- 4. Structure et solvabilité ----------
        cp = v.get('ST_CP', 0.0)
        ta = v.get('T_ACTIF', 0.0)
        auto = (cp / ta * 100) if ta else 0.0
        caf = v.get('CAF', 0.0)
        dfn = v.get('DETTE_FIN_NETTE', 0.0)
        st = _("<p><b>Structure financière et solvabilité.</b> ")
        st += _(
            "Les capitaux propres s'établissent à %(cp)s, soit %(a).1f %% du total du "
            "bilan. ", cp=self._fmt_amount(cp, cur), a=auto)
        if cp < 0:
            st += _(
                "La situation nette est négative : la reconstitution des capitaux propres "
                "constitue une obligation dont les modalités doivent être examinées sans "
                "délai avec les associés. ")
        elif auto < 20:
            st += _(
                "Ce niveau de fonds propres est insuffisant et limite fortement la "
                "capacité de négociation avec les partenaires financiers. ")
        if caf > 0 and dfn > 0:
            st += _(
                "La capacité d'autofinancement de %(caf)s permettrait de rembourser la "
                "dette financière nette en %(y).1f années. ",
                caf=self._fmt_amount(caf, cur), y=dfn / caf)
            if dfn / caf > 5:
                st += _(
                    "Cette durée dépasse largement le seuil de trois à quatre années "
                    "généralement retenu par les établissements de crédit. ")
        elif caf <= 0:
            st += _(
                "La capacité d'autofinancement est négative ou nulle : l'activité ne "
                "génère aucune ressource interne pour financer le développement ou "
                "rembourser les emprunts. ")
        paras.append(st + "</p>")

        # ---------- 5. Score de risque ----------
        scores = last.score_ids.filtered(lambda s: not s.is_na)
        if scores:
            sc = _("<p><b>Risque de défaillance.</b> ")
            parts = []
            for s in scores:
                if s.model == 'altman':
                    parts.append(_("le score Altman Z'' ressort à %(v).2f", v=s.value))
                elif s.model == 'conan':
                    parts.append(_("la fonction Conan et Holder à %(v).2f", v=s.value))
                else:
                    parts.append(_("la note de synthèse à %(v).0f sur 100", v=s.value))
            sc += _("Sur la dernière période, %(p)s. ", p=", ".join(parts))
            zones = set(scores.mapped('zone'))
            if zones == {'safe'}:
                sc += _(
                    "Les trois modèles convergent vers une situation saine. ")
            elif 'distress' in zones and 'safe' in zones:
                sc += _(
                    "Les modèles divergent, ce qui appelle à la prudence dans "
                    "l'interprétation : la situation est contrastée selon l'angle "
                    "d'analyse retenu. ")
            elif 'distress' in zones:
                sc += _(
                    "Ces résultats situent l'entreprise en zone de risque et justifient "
                    "la mise en place d'un suivi rapproché de la trésorerie. ")
            else:
                sc += _("Ces résultats situent l'entreprise en zone d'incertitude. ")
            sc += _(
                "Ces scores sont des signaux statistiques établis sur des populations "
                "d'entreprises étrangères ; ils ne valent pas diagnostic.")
            paras.append(sc + "</p>")

        # ---------- 6. Priorités d'action ----------
        syn = last.get_synthesis()
        recos = syn.get('recommendations')
        if recos:
            act_p = _("<p><b>Priorités d'action.</b> Au regard de l'ensemble des "
                      "indicateurs, trois chantiers ressortent :</p><ol>")
            for r in recos[:3]:
                act_p += _("<li><b>%(n)s</b> (%(v)s) : %(r)s</li>",
                           n=r.name, v=r.value_display, r=r.recommendation or '')
            act_p += "</ol>"
            paras.append(act_p)

        # ---------- 7. Réserve ----------
        paras.append(_(
            "<p><i>Projet de conclusion généré automatiquement à partir des indicateurs "
            "calculés. Il constitue une base de rédaction : il appartient au consultant "
            "de le compléter par les éléments qualitatifs du dossier — marché, "
            "gouvernance, projets en cours, événements postérieurs à la clôture — et "
            "d'en valider la formulation avant transmission au client.</i></p>"))

        return "\n".join(paras)


class FaConclusionConfirm(models.TransientModel):
    """Confirmation avant écrasement d'une conclusion déjà rédigée."""
    _name = 'fa.conclusion.confirm'
    _description = "Confirmation de génération de la conclusion"

    analysis_id = fields.Many2one('fa.analysis', string="Dossier", required=True)
    mode = fields.Selection([
        ('replace', "Remplacer la conclusion actuelle"),
        ('append', "Ajouter le projet à la suite du texte existant"),
    ], string="Mode", default='append', required=True)

    def action_confirm(self):
        self.ensure_one()
        draft = self.env['fa.conclusion.builder'].build(self.analysis_id)
        if self.mode == 'append':
            existing = self.analysis_id.conclusion or ''
            self.analysis_id.conclusion = "%s<hr/>%s" % (existing, draft)
        else:
            self.analysis_id.conclusion = draft
        return {'type': 'ir.actions.act_window_close'}
