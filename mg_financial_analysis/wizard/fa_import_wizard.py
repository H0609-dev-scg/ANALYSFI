# -*- coding: utf-8 -*-
"""Import de la saisie depuis un fichier CSV ou Excel.

Le cabinet reçoit souvent les états financiers dans un tableur. Saisir
76 lignes à la main est une source d'erreur. L'assistant lit un fichier
dont la première colonne porte le code de rubrique (AC_STOCK, PL_VENTE_MSE…),
propose un aperçu ligne par ligne, puis applique uniquement les lignes
retenues.

Le fichier généré par l'export Excel du module est accepté tel quel :
l'onglet « Saisie » porte déjà les codes en première colonne.
"""
import base64
import csv
import io
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import openpyxl
except ImportError:
    openpyxl = None


_CODE_RE = re.compile(r'^(AC_|PA_|PL_|IN_)[A-Z0-9_]+$')


def _to_float(raw):
    if raw is None or raw == '':
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace('\u202f', '').replace(' ', '').replace(',', '.')
    if not text or text in ('-', 'n/a', 'N/A'):
        return None
    try:
        return float(text)
    except ValueError:
        return None


class FaImportWizard(models.TransientModel):
    _name = 'fa.import.wizard'
    _description = "Import de la saisie financière"

    statement_id = fields.Many2one(
        'fa.statement', string="Période", required=True, ondelete='cascade')
    file_data = fields.Binary(string="Fichier", required=True)
    file_name = fields.Char(string="Nom du fichier")

    overwrite = fields.Boolean(
        string="Écraser les montants déjà saisis", default=False,
        help="Décoché : seules les lignes encore à zéro sont mises à jour.")
    import_previous = fields.Boolean(
        string="Importer aussi les montants N-1", default=True)
    import_gross = fields.Boolean(
        string="Importer brut et amortissements", default=True)

    state = fields.Selection([
        ('upload', "Fichier"),
        ('preview', "Aperçu"),
        ('done', "Terminé"),
    ], default='upload')

    line_ids = fields.One2many('fa.import.line', 'wizard_id', string="Lignes")
    nb_matched = fields.Integer(string="Reconnues", compute='_compute_stats')
    nb_unknown = fields.Integer(string="Inconnues", compute='_compute_stats')
    nb_apply = fields.Integer(string="À appliquer", compute='_compute_stats')
    summary = fields.Text(string="Résultat", readonly=True)

    @api.depends('line_ids.status', 'line_ids.apply')
    def _compute_stats(self):
        for rec in self:
            rec.nb_matched = len(rec.line_ids.filtered(lambda l: l.status == 'ok'))
            rec.nb_unknown = len(rec.line_ids.filtered(lambda l: l.status == 'unknown'))
            rec.nb_apply = len(rec.line_ids.filtered(lambda l: l.apply))

    def action_download_template(self):
        """Fichier CSV modèle : une ligne par rubrique de saisie."""
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Code', 'Rubrique', 'Brut', 'Amort.', 'Net', 'N-1'])
        rubrics = self.env['fa.rubric'].search(
            [('line_type', '=', 'input')], order='sequence')
        for r in rubrics:
            writer.writerow([r.code, r.name, '', '', '', ''])
        data = base64.b64encode(output.getvalue().encode('utf-8-sig'))
        name = "modele_saisie_pcg2005.csv"
        self.write({'file_data': data, 'file_name': name})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fa.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_preview(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Chargez un fichier CSV ou Excel."))
        rows = self._parse_file()
        if not rows:
            raise UserError(_(
                "Aucune ligne reconnue. La première colonne doit porter le "
                "code de rubrique (ex. AC_STOCK, PL_VENTE_MSE)."))

        stmt = self.statement_id
        lines_by_code = {ln.code: ln for ln in stmt.line_ids if ln.code}
        rubrics = {r.code: r for r in self.env['fa.rubric'].search([])}

        self.line_ids.unlink()
        vals = []
        seq = 0
        for code, amounts in rows:
            seq += 10
            existing = lines_by_code.get(code)
            rubric = rubrics.get(code)
            status = 'ok' if existing else ('unknown' if not rubric else 'unused')
            current = existing.amount_net if existing else 0.0
            apply = status == 'ok' and (
                self.overwrite or not current or abs(current) < 1e-9)
            vals.append({
                'wizard_id': self.id,
                'sequence': seq,
                'code': code,
                'name': (existing.rubric_id.name if existing
                         else (rubric.name if rubric else '')),
                'status': status,
                'apply': apply,
                'amount_gross': amounts.get('gross'),
                'amount_deprec': amounts.get('deprec'),
                'amount_net': amounts.get('net'),
                'amount_previous': amounts.get('previous'),
                'current_net': current,
            })
        if vals:
            self.env['fa.import.line'].create(vals)
        self.state = 'preview'
        return self._reopen()

    def action_apply(self):
        self.ensure_one()
        if self.state != 'preview':
            raise UserError(_("Générez d'abord l'aperçu."))
        to_apply = self.line_ids.filtered(lambda l: l.apply and l.status == 'ok')
        if not to_apply:
            raise UserError(_("Aucune ligne à importer."))

        stmt = self.statement_id
        if stmt.state == 'analyzed':
            stmt.action_draft()

        lines_by_code = {ln.code: ln for ln in stmt.line_ids if ln.code}
        updated = 0
        for iline in to_apply:
            line = lines_by_code.get(iline.code)
            if not line:
                continue
            vals = {}
            if iline.amount_net is not False and iline.amount_net is not None:
                vals['amount_net'] = iline.amount_net
            if self.import_gross:
                if iline.amount_gross is not False and iline.amount_gross is not None:
                    vals['amount_gross'] = iline.amount_gross
                if iline.amount_deprec is not False and iline.amount_deprec is not None:
                    vals['amount_deprec'] = iline.amount_deprec
            if self.import_previous:
                if (iline.amount_previous is not False
                        and iline.amount_previous is not None):
                    vals['amount_previous'] = iline.amount_previous
            if vals:
                line.write(vals)
                updated += 1

        skipped = len(self.line_ids) - updated
        unknown = self.nb_unknown
        self.write({
            'state': 'done',
            'summary': _(
                "%(n)s rubrique(s) importée(s). "
                "%(s)s ligne(s) ignorée(s)%(u)s. "
                "Vérifiez l'équilibre Actif − Passif puis lancez l'analyse.",
                n=updated, s=skipped,
                u=(_(" dont %s code(s) inconnu(s)") % unknown) if unknown else ''),
        })
        return self._reopen()

    def action_open_statement(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fa.statement',
            'res_id': self.statement_id.id,
            'view_mode': 'form',
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fa.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _parse_file(self):
        raw = base64.b64decode(self.file_data)
        name = (self.file_name or '').lower()
        if name.endswith('.xlsx') or name.endswith('.xlsm'):
            return self._parse_xlsx(raw)
        return self._parse_csv(raw)

    def _parse_csv(self, raw):
        text = raw.decode('utf-8-sig', errors='replace')
        sample = text[:2048]
        delimiter = ';' if sample.count(';') >= sample.count(',') else ','
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        return self._rows_from_table(list(reader))

    def _parse_xlsx(self, raw):
        if not openpyxl:
            raise UserError(_(
                "La bibliothèque openpyxl n'est pas disponible. "
                "Enregistrez le fichier en CSV, ou installez openpyxl."))
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        tables = []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append(list(row))
            tables.extend(self._rows_from_table(rows))
        wb.close()
        return tables

    def _rows_from_table(self, table):
        """Extrait {code: montants} depuis un tableau à en-têtes libres."""
        if not table:
            return []
        header_idx = self._find_header(table)
        col_map = {}
        start = 0
        if header_idx is not None:
            headers = [str(c or '').strip().lower() for c in table[header_idx]]
            col_map = self._map_columns(headers)
            start = header_idx + 1

        collected = []
        seen = set()
        for row in table[start:]:
            if not row:
                continue
            code = self._extract_code(row)
            if not code or code in seen:
                continue
            seen.add(code)
            collected.append((code, self._extract_amounts(row, col_map)))
        return collected

    def _find_header(self, table):
        for i, row in enumerate(table[:15]):
            cells = [str(c or '').strip().lower() for c in row]
            joined = ' '.join(cells)
            if 'code' in joined and ('net' in joined or 'montant' in joined
                                     or 'brut' in joined):
                return i
        return None

    def _map_columns(self, headers):
        mapping = {}
        for i, h in enumerate(headers):
            if h in ('code',):
                mapping['code'] = i
            elif any(k in h for k in ('brut', 'gross')):
                mapping['gross'] = i
            elif any(k in h for k in ('amort', 'deprec', 'prov')):
                mapping['deprec'] = i
            elif h in ('net', 'montant', 'valeur', 'n') or h.startswith('net'):
                mapping.setdefault('net', i)
            elif 'n-1' in h or 'n−1' in h or h in ('précédent', 'precedent',
                                                    'previous'):
                mapping['previous'] = i
        return mapping

    def _extract_code(self, row):
        for cell in row[:3]:
            if cell is None:
                continue
            text = str(cell).strip().upper().replace(' ', '_')
            if _CODE_RE.match(text):
                return text
        return False

    def _extract_amounts(self, row, col_map):
        def cell(key, default_idx):
            idx = col_map.get(key, default_idx)
            if idx is None or idx >= len(row):
                return None
            return _to_float(row[idx])

        # Sans en-tête : Code, Rubrique, Brut, Amort., Net, N-1 (export module)
        # ou Code, Net
        if not col_map:
            net = cell('net', 4 if len(row) > 4 else 1)
            if net is None and len(row) > 1:
                # Cherche le premier nombre après le code
                for cell_val in row[1:]:
                    parsed = _to_float(cell_val)
                    if parsed is not None:
                        net = parsed
                        break
            return {
                'gross': cell('gross', 2 if len(row) > 4 else None),
                'deprec': cell('deprec', 3 if len(row) > 4 else None),
                'net': net,
                'previous': cell('previous', 5 if len(row) > 5 else None),
            }
        return {
            'gross': cell('gross', None),
            'deprec': cell('deprec', None),
            'net': cell('net', None),
            'previous': cell('previous', None),
        }


class FaImportLine(models.TransientModel):
    _name = 'fa.import.line'
    _description = "Ligne d'aperçu d'import"
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'fa.import.wizard', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Rubrique")
    status = fields.Selection([
        ('ok', "Reconnue"),
        ('unknown', "Code inconnu"),
        ('unused', "Hors saisie"),
    ], default='ok')
    apply = fields.Boolean(string="Importer", default=True)
    amount_gross = fields.Float(string="Brut", digits=(16, 2))
    amount_deprec = fields.Float(string="Amort.", digits=(16, 2))
    amount_net = fields.Float(string="Net", digits=(16, 2))
    amount_previous = fields.Float(string="N-1", digits=(16, 2))
    current_net = fields.Float(string="Saisi actuellement", digits=(16, 2))
