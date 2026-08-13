# -*- coding: utf-8 -*-
"""Scoring du risque de défaillance.

Trois modèles complémentaires :

* **Altman Z''** version marchés émergents. C'est la variante appropriée à
  Madagascar : elle exclut la rotation d'actif (trop sensible au secteur),
  fonctionne pour les sociétés non cotées et ajoute la constante 3,25 qui
  cale le zéro sur une notation obligataire D.
* **Conan et Holder**, fonction discriminante française à cinq ratios, plus
  adaptée aux PME et sensible au poids des frais financiers et de la masse
  salariale — deux points de fragilité fréquents dans le tissu malgache.
* **Note de synthèse sur 100**, propre au module, qui agrège les
  appréciations des ratios par famille pondérée.

Aucun de ces modèles n'a été recalibré sur des données malgaches : ils sont
utilisés comme signaux d'alerte convergents, non comme verdicts.
"""
from odoo import models, fields, api, _


class FaScore(models.Model):
    _name = 'fa.score'
    _description = "Score de risque de défaillance"
    _order = 'statement_id, sequence'

    statement_id = fields.Many2one(
        'fa.statement', string="Période", required=True, ondelete='cascade', index=True)
    analysis_id = fields.Many2one(related='statement_id.analysis_id', store=True)
    partner_id = fields.Many2one(related='statement_id.partner_id', store=True)
    currency_id = fields.Many2one(related='statement_id.currency_id', store=True)
    sequence = fields.Integer(default=10)

    model = fields.Selection([
        ('altman', "Altman Z'' — marchés émergents"),
        ('conan', "Conan et Holder"),
        ('synthesis', "Note de synthèse du cabinet"),
    ], string="Modèle", required=True, index=True)

    value = fields.Float(string="Score", digits=(16, 4), group_operator=False)
    value_display = fields.Char(string="Score", compute='_compute_display')

    zone = fields.Selection([
        ('distress', "Zone de danger"),
        ('grey', "Zone d'incertitude"),
        ('safe', "Zone de sécurité"),
    ], string="Zone de risque", index=True)

    risk_level = fields.Selection([
        ('very_high', "Très élevé"),
        ('high', "Élevé"),
        ('moderate', "Modéré"),
        ('low', "Faible"),
        ('very_low', "Très faible"),
    ], string="Niveau de risque")

    default_probability = fields.Char(
        string="Probabilité de défaillance",
        help="Fourchette indicative à horizon de trois ans, issue des travaux "
             "d'origine du modèle.")

    detail = fields.Text(string="Détail du calcul", help="Contribution de chaque composante.")
    comment = fields.Text(string="Lecture du score")
    is_na = fields.Boolean(string="Non calculable")
    na_reason = fields.Char(string="Motif")

    previous_value = fields.Float(string="Score N-1", digits=(16, 4), group_operator=False)
    variation = fields.Float(
        string="Variation", digits=(16, 4), compute='_compute_variation', store=True,
        group_operator=False)

    @api.depends('value', 'previous_value')
    def _compute_variation(self):
        for rec in self:
            rec.variation = rec.value - rec.previous_value

    @api.depends('value', 'model', 'is_na')
    def _compute_display(self):
        for rec in self:
            if rec.is_na:
                rec.value_display = "N/A"
            elif rec.model == 'synthesis':
                rec.value_display = "%.0f / 100" % rec.value
            else:
                rec.value_display = "%.2f" % rec.value

    # ------------------------------------------------------------------
    # Modèles
    # ------------------------------------------------------------------
    @api.model
    def compute_altman(self, v):
        """Altman Z'' marchés émergents : 3,25 + 6,56 X1 + 3,26 X2 + 6,72 X3 + 1,05 X4."""
        ta = v.get('T_ACTIF', 0.0)
        if not ta:
            return None, _("Total actif nul.")
        dettes = v.get('DETTES_TOTALES', 0.0)
        if not dettes:
            return None, _("Aucune dette : le ratio X4 n'est pas calculable.")
        # X1 : fonds de roulement / total actif
        x1 = (v.get('ST_AC', 0.0) - v.get('ST_PC', 0.0)) / ta
        # X2 : réserves et report à nouveau / total actif
        reserves = v.get('PA_PRIMES', 0.0) + v.get('PA_AUTRES_CP', 0.0)
        x2 = reserves / ta
        # X3 : résultat opérationnel (proxy EBIT) / total actif
        x3 = v.get('REX', 0.0) / ta
        # X4 : capitaux propres / total dettes
        x4 = v.get('ST_CP', 0.0) / dettes
        score = 3.25 + 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
        detail = _(
            "X1 Fonds de roulement / Actif total  : %(x1).3f  × 6,56 = %(c1).2f\n"
            "X2 Réserves / Actif total            : %(x2).3f  × 3,26 = %(c2).2f\n"
            "X3 Résultat opérationnel / Actif     : %(x3).3f  × 6,72 = %(c3).2f\n"
            "X4 Capitaux propres / Dettes totales : %(x4).3f  × 1,05 = %(c4).2f\n"
            "Constante marchés émergents          : +3,25\n"
            "―――――――――――――――――――――――――――――――――\n"
            "Z'' = %(z).2f",
            x1=x1, c1=6.56 * x1, x2=x2, c2=3.26 * x2, x3=x3, c3=6.72 * x3,
            x4=x4, c4=1.05 * x4, z=score)
        return (score, detail)

    @api.model
    def compute_conan(self, v):
        """Conan et Holder : 24 R1 + 22 R2 + 16 R3 − 87 R4 − 10 R5."""
        ta = v.get('T_ACTIF', 0.0)
        ca = v.get('CA', 0.0)
        va = v.get('VA', 0.0)
        dettes = v.get('DETTES_TOTALES', 0.0)
        if not (ta and dettes):
            return None, _("Total actif ou dettes nuls.")
        if not ca:
            return None, _("Chiffre d'affaires nul.")
        if not va:
            return None, _("Valeur ajoutée nulle : le ratio R5 n'est pas calculable.")
        r1 = v.get('EBE', 0.0) / dettes
        r2 = v.get('CAPITAUX_PERMANENTS', 0.0) / ta
        r3 = (v.get('AC_TRESO', 0.0) + v.get('AC_PLACEMENT', 0.0)
              + v.get('AC_CLIENT', 0.0)) / ta
        r4 = v.get('PL_CH_FIN', 0.0) / ca
        r5 = v.get('PL_PERSONNEL', 0.0) / va
        score = 24 * r1 + 22 * r2 + 16 * r3 - 87 * r4 - 10 * r5
        detail = _(
            "R1 EBE / Endettement global          : %(r1).3f  × 24  = %(c1).2f\n"
            "R2 Capitaux permanents / Actif       : %(r2).3f  × 22  = %(c2).2f\n"
            "R3 Réalisable et disponible / Actif  : %(r3).3f  × 16  = %(c3).2f\n"
            "R4 Frais financiers / CA HT          : %(r4).3f  × -87 = %(c4).2f\n"
            "R5 Frais de personnel / Valeur ajoutée : %(r5).3f × -10 = %(c5).2f\n"
            "―――――――――――――――――――――――――――――――――\n"
            "N = %(n).2f",
            r1=r1, c1=24 * r1, r2=r2, c2=22 * r2, r3=r3, c3=16 * r3,
            r4=r4, c4=-87 * r4, r5=r5, c5=-10 * r5, n=score)
        return (score, detail)

    FAMILY_WEIGHTS = {
        'structure': 0.22,
        'liquidity': 0.24,
        'activity': 0.14,
        'profitability': 0.24,
        'value_added': 0.06,
        'coverage': 0.10,
    }
    APPRECIATION_POINTS = {'bad': 0.0, 'watch': 40.0, 'ok': 70.0, 'good': 100.0}

    def _compute_synthesis(self, statement):
        """Note sur 100 : moyenne des appréciations, pondérée par famille."""
        results = statement.ratio_result_ids.filtered(lambda r: not r.is_na and r.appreciation)
        if not results:
            return None, _("Aucun ratio calculable."), {}
        total_weight = 0.0
        total_points = 0.0
        by_family = {}
        for family, weight in self.FAMILY_WEIGHTS.items():
            lines = results.filtered(lambda r, f=family: r.family == f)
            if not lines:
                continue
            pts = sum(self.APPRECIATION_POINTS.get(r.appreciation, 0.0) for r in lines)
            avg = pts / len(lines)
            by_family[family] = (avg, len(lines))
            total_points += avg * weight
            total_weight += weight
        if not total_weight:
            return None, _("Aucune famille de ratios exploitable."), {}
        score = total_points / total_weight
        fam_labels = dict(self.env['fa.ratio']._fields['family'].selection)
        detail_lines = [
            _("%(fam)-46s %(avg)5.1f / 100  (%(n)s ratios, poids %(w).0f %%)",
              fam=fam_labels.get(f, f)[:46], avg=a, n=n,
              w=self.FAMILY_WEIGHTS[f] * 100)
            for f, (a, n) in sorted(by_family.items(),
                                    key=lambda kv: -self.FAMILY_WEIGHTS[kv[0]])
        ]
        detail_lines.append("―" * 33)
        detail_lines.append(_("Note pondérée : %.0f / 100") % score)
        return score, "\n".join(detail_lines), by_family

    # ------------------------------------------------------------------
    # Zones et lectures
    # ------------------------------------------------------------------
    @staticmethod
    def _altman_zone(score):
        if score < 1.1:
            return 'distress', 'very_high', "Supérieure à 50 %"
        if score < 2.6:
            return 'grey', 'moderate', "De 15 à 50 %"
        return 'safe', 'low', "Inférieure à 10 %"

    @staticmethod
    def _conan_zone(score):
        # Barème usuel de la fonction Conan-Holder
        if score < 4:
            return 'distress', 'very_high', "Supérieure à 65 %"
        if score < 9:
            return 'distress', 'high', "De 30 à 65 %"
        if score < 16:
            return 'grey', 'moderate', "De 10 à 30 %"
        return 'safe', 'low', "Inférieure à 10 %"

    @staticmethod
    def _synthesis_zone(score):
        if score < 35:
            return 'distress', 'very_high', "Situation très dégradée"
        if score < 50:
            return 'distress', 'high', "Situation dégradée"
        if score < 65:
            return 'grey', 'moderate', "Situation contrastée"
        if score < 80:
            return 'safe', 'low', "Situation saine"
        return 'safe', 'very_low', "Situation solide"

    def _build_comment(self, model, score, zone, statement, extra=None):
        """Rédige la lecture du score, avec la réserve méthodologique qui s'impose."""
        name = statement.partner_id.name or _("l'entreprise")
        if model == 'altman':
            base = _(
                "Le score Altman Z'' s'établit à %(s).2f. ", s=score)
            if zone == 'distress':
                base += _(
                    "Ce niveau situe %(n)s en zone de danger (seuil de 1,10). Le modèle "
                    "signale une probabilité élevée de difficultés financières graves "
                    "à horizon de deux ans si la trajectoire actuelle se poursuit.", n=name)
            elif zone == 'grey':
                base += _(
                    "Ce niveau place %(n)s en zone d'incertitude, entre 1,10 et 2,60. "
                    "Le modèle ne conclut pas : la situation peut évoluer dans les deux "
                    "sens selon les décisions prises dans les prochains mois.", n=name)
            else:
                base += _(
                    "Ce niveau situe %(n)s en zone de sécurité (au-dessus de 2,60). "
                    "Le risque de défaillance à court terme est faible.", n=name)
            base += _(
                " Le modèle retenu est la variante Z'' pour marchés émergents, adaptée "
                "aux sociétés non cotées et non exclusivement industrielles.")
        elif model == 'conan':
            base = _("La fonction Conan et Holder donne un score de %(s).2f. ", s=score)
            if zone == 'distress':
                base += _(
                    "Ce résultat traduit une vulnérabilité marquée. Cette fonction est "
                    "particulièrement sensible au poids des frais financiers et de la "
                    "masse salariale : leur allègement produit un effet direct sur le score.")
            elif zone == 'grey':
                base += _(
                    "Ce résultat situe l'entreprise en zone de prudence. La tendance sur "
                    "plusieurs exercices est plus significative que le niveau absolu.")
            else:
                base += _("Ce résultat traduit une situation financière saine.")
        else:
            base = _("La note de synthèse s'établit à %(s).0f sur 100. ", s=score)
            if extra:
                fam_labels = dict(self.env['fa.ratio']._fields['family'].selection)
                worst = min(extra.items(), key=lambda kv: kv[1][0])
                best = max(extra.items(), key=lambda kv: kv[1][0])
                base += _(
                    "La famille la plus fragile est « %(w)s » (%(wv).0f / 100), "
                    "la mieux orientée « %(b)s » (%(bv).0f / 100). ",
                    w=fam_labels.get(worst[0], '')[3:], wv=worst[1][0],
                    b=fam_labels.get(best[0], '')[3:], bv=best[1][0])
            base += _(
                "Cette note agrège les appréciations de l'ensemble des ratios, pondérées "
                "par famille : liquidité et rentabilité comptent chacune pour près d'un "
                "quart, la structure financière pour un cinquième.")

        base += _(
            "\n\nCe score est un signal d'alerte statistique, non un diagnostic. Les "
            "modèles employés ont été calibrés sur des populations d'entreprises "
            "européennes ou américaines ; aucun n'a été validé sur un échantillon "
            "malgache. Il doit être interprété avec la connaissance du dossier, du "
            "secteur et du contexte de marché.")
        return base

    # ------------------------------------------------------------------
    def generate_for_statement(self, statement):
        """Calcule et enregistre les trois scores d'une période."""
        self.search([('statement_id', '=', statement.id)]).unlink()
        v = statement._get_values_dict(annualized=True)

        prev_scores = {}
        if statement.previous_statement_id:
            prev_scores = {
                s.model: s.value
                for s in self.search([
                    ('statement_id', '=', statement.previous_statement_id.id)])
            }

        vals = []
        # --- Altman ---
        res, detail = self.compute_altman(v)
        if res is None:
            vals.append({'statement_id': statement.id, 'model': 'altman', 'sequence': 10,
                         'is_na': True, 'na_reason': detail})
        else:
            zone, risk, proba = self._altman_zone(res)
            vals.append({
                'statement_id': statement.id, 'model': 'altman', 'sequence': 10,
                'value': res, 'zone': zone, 'risk_level': risk,
                'default_probability': proba, 'detail': detail,
                'previous_value': prev_scores.get('altman', 0.0),
                'comment': self._build_comment('altman', res, zone, statement),
            })
        # --- Conan et Holder ---
        res, detail = self.compute_conan(v)
        if res is None:
            vals.append({'statement_id': statement.id, 'model': 'conan', 'sequence': 20,
                         'is_na': True, 'na_reason': detail})
        else:
            zone, risk, proba = self._conan_zone(res)
            vals.append({
                'statement_id': statement.id, 'model': 'conan', 'sequence': 20,
                'value': res, 'zone': zone, 'risk_level': risk,
                'default_probability': proba, 'detail': detail,
                'previous_value': prev_scores.get('conan', 0.0),
                'comment': self._build_comment('conan', res, zone, statement),
            })
        # --- Note de synthèse ---
        res, detail, by_fam = self._compute_synthesis(statement)
        if res is None:
            vals.append({'statement_id': statement.id, 'model': 'synthesis', 'sequence': 30,
                         'is_na': True, 'na_reason': detail})
        else:
            zone, risk, proba = self._synthesis_zone(res)
            vals.append({
                'statement_id': statement.id, 'model': 'synthesis', 'sequence': 30,
                'value': res, 'zone': zone, 'risk_level': risk,
                'default_probability': proba, 'detail': detail,
                'previous_value': prev_scores.get('synthesis', 0.0),
                'comment': self._build_comment('synthesis', res, zone, statement, by_fam),
            })
        return self.create(vals)
