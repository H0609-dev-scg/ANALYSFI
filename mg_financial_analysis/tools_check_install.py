#!/usr/bin/env python3
"""Contrôle d'intégrité du module avant installation dans Odoo 16.

Usage :  python3 tools_check_install.py

Vérifie, sans démarrer Odoo :
  1. l'ordre de chargement du manifest (référence utilisée avant définition) ;
  2. la conformité de la syntaxe des vues à Odoo 16 (pas de syntaxe v17) ;
  3. l'existence de chaque champ cité dans une vue, y compris les sous-vues ;
  4. l'intégrité générale : fichiers, imports, droits d'accès, doublons.
"""
import ast
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
FAILURES = []


def report(section, problems, hint=None):
    if problems:
        FAILURES.append(section)
        print(f"\n[ECHEC] {section}")
        for p in problems:
            print(f"    {p}")
        if hint:
            print(f"    -> {hint}")
    else:
        print(f"[ OK ] {section}")


def load_manifest():
    src = open(os.path.join(BASE, '__manifest__.py'), encoding='utf-8').read()
    return ast.literal_eval(src[src.index('{'):src.rindex('}') + 1])


def parse_models():
    """Retourne (champs par modèle, relations, modèles concrets)."""
    fields_by_model, relations, concrete = {}, {}, set()
    for path in glob.glob(f'{BASE}/models/*.py') + glob.glob(f'{BASE}/wizard/*.py'):
        src = open(path, encoding='utf-8').read()
        for block in re.split(r'\nclass ', src):
            header = block.split('\n')[0]
            name = re.search(r"^\s{4}_name\s*=\s*'([\w.]+)'", block, re.M)
            inherit = re.search(r"^\s{4}_inherit\s*=\s*'([\w.]+)'", block, re.M)
            target = name.group(1) if name else (inherit.group(1) if inherit else None)
            if not target:
                continue
            if name and 'AbstractModel' not in header:
                concrete.add(target)
            bucket = fields_by_model.setdefault(target, set())
            for m in re.finditer(r"^\s{4}(\w+)\s*=\s*fields\.(\w+)\(([^\n]*)", block, re.M):
                fname, ftype, args = m.group(1), m.group(2), m.group(3)
                bucket.add(fname)
                if ftype in ('One2many', 'Many2many', 'Many2one'):
                    rel = re.match(r"\s*'([\w.]+)'", args)
                    if rel:
                        relations[(target, fname)] = rel.group(1)
    return fields_by_model, relations, concrete


def check_load_order(manifest, concrete):
    defined = {'model_' + m.replace('.', '_') for m in concrete}
    problems = []
    for rel in manifest['data'] + manifest.get('demo', []):
        if not rel.endswith('.xml'):
            continue
        root = ET.parse(os.path.join(BASE, rel)).getroot()
        for node in root.iter():
            if node.tag not in ('record', 'menuitem', 'template'):
                continue
            for el in node.iter():
                ref = el.get('ref')
                if ref and '.' not in ref and ref not in defined:
                    problems.append(f"{rel} : '{ref}' requis par <{node.get('id')}>")
            for attr in ('parent', 'action'):
                ref = node.get(attr)
                if ref and '.' not in ref and ref not in defined:
                    problems.append(f"{rel} : '{ref}' requis par <{node.get('id')}>")
            if node.get('id'):
                defined.add(node.get('id'))
    report("Ordre de chargement du manifest", sorted(set(problems)),
           "déplacer le fichier plus loin dans la clé 'data'")


def check_odoo16_syntax():
    problems = []
    for path in glob.glob(f'{BASE}/**/*.xml', recursive=True):
        rel = os.path.relpath(path, BASE)
        raw = open(path, encoding='utf-8').read()
        for m in re.finditer(r'column_invisible="(?!\[)', raw):
            problems.append(f"{rel}:{raw[:m.start()].count(chr(10)) + 1} "
                            f"column_invisible en attribut direct (Odoo 17)")
        for attr in ('invisible', 'readonly', 'required'):
            for m in re.finditer(rf'\b{attr}="([^"]+)"', raw):
                val = m.group(1).strip()
                if val in ('0', '1', 'True', 'False'):
                    continue
                if 'attrs=' in raw[max(0, m.start() - 40):m.start()]:
                    continue
                problems.append(f"{rel}:{raw[:m.start()].count(chr(10)) + 1} "
                                f"{attr}=\"{val[:30]}\" : expression non supportée")
        for m in re.finditer(r'<list[\s>]', raw):
            problems.append(f"{rel} : balise <list> (Odoo 17), utiliser <tree>")
    report("Syntaxe compatible Odoo 16", sorted(set(problems)),
           "remplacer par invisible=\"1\" ou attrs=\"{...}\"")


def check_view_fields(fields_by_model, relations):
    std = {'id', 'display_name', 'create_date', 'write_date', 'create_uid',
           'write_uid', '__last_update', 'message_ids', 'message_follower_ids',
           'activity_ids'}
    problems = []

    def walk(node, model, rel):
        for child in node:
            if child.tag == 'field':
                fname = child.get('name')
                if fname and fname not in fields_by_model.get(model, set()) \
                        and fname not in std:
                    problems.append(f"{rel} : modèle {model}, champ '{fname}' inexistant")
                sub = relations.get((model, fname))
                if sub and len(child):
                    for grand in child:
                        if grand.tag in ('tree', 'form', 'kanban'):
                            walk(grand, sub, rel)
            else:
                walk(child, model, rel)

    for path in glob.glob(f'{BASE}/views/*.xml') + glob.glob(f'{BASE}/wizard/*.xml'):
        rel = os.path.relpath(path, BASE)
        for rec in ET.parse(path).getroot().iter('record'):
            if rec.get('model') != 'ir.ui.view':
                continue
            mdl = rec.find("field[@name='model']")
            arch = rec.find("field[@name='arch']")
            if mdl is None or arch is None or mdl.text not in fields_by_model:
                continue
            walk(arch, mdl.text, rel)
    report("Champs des vues existants", sorted(set(problems)),
           "champ renommé ou supprimé du modèle")


def check_integrity(manifest, concrete):
    import csv
    problems = []
    for f in manifest['data'] + manifest.get('demo', []):
        if not os.path.exists(os.path.join(BASE, f)):
            problems.append(f"fichier déclaré absent : {f}")
    declared = set(manifest['data'] + manifest.get('demo', []))
    for f in glob.glob(f'{BASE}/**/*.xml', recursive=True):
        rel = os.path.relpath(f, BASE)
        if rel not in declared:
            problems.append(f"XML non déclaré au manifest : {rel}")
    for folder in ('models', 'wizard', 'report'):
        init = os.path.join(BASE, folder, '__init__.py')
        if not os.path.exists(init):
            continue
        content = open(init, encoding='utf-8').read()
        for py in glob.glob(f'{BASE}/{folder}/*.py'):
            mod = os.path.basename(py)[:-3]
            if mod == '__init__':
                continue
            if f'from . import {mod}' not in content:
                problems.append(f"module non importé : {folder}/{mod}.py")
    acl = os.path.join(BASE, 'security', 'ir.model.access.csv')
    if os.path.exists(acl):
        rows = list(csv.DictReader(open(acl)))
        for m in concrete:
            key = 'model_' + m.replace('.', '_')
            if not any(r['model_id:id'] == key for r in rows):
                problems.append(f"droits d'accès manquants : {m}")
    seen, dups = set(), set()
    for f in manifest['data'] + manifest.get('demo', []):
        if not f.endswith('.xml'):
            continue
        for node in ET.parse(os.path.join(BASE, f)).getroot().iter():
            if node.tag in ('record', 'menuitem', 'template') and node.get('id'):
                if node.get('id') in seen:
                    dups.add(node.get('id'))
                seen.add(node.get('id'))
    problems += [f"identifiant dupliqué : {d}" for d in sorted(dups)]
    report("Intégrité générale", problems)


def main():
    print(f"Contrôle du module : {BASE}\n")
    manifest = load_manifest()
    fields_by_model, relations, concrete = parse_models()
    check_load_order(manifest, concrete)
    check_odoo16_syntax()
    check_view_fields(fields_by_model, relations)
    check_integrity(manifest, concrete)
    print()
    if FAILURES:
        print(f"RESULTAT : {len(FAILURES)} contrôle(s) en échec — corriger avant installation")
        sys.exit(1)
    print("RESULTAT : module prêt pour installation")


if __name__ == '__main__':
    main()
