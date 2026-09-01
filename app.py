#!/usr/bin/env python3
"""
Serveur NSA Développement - API REST
Déployé sur Render.com
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json, os, hashlib, secrets, time
from datetime import datetime

app = Flask(__name__)
CORS(app, origins="*")

# ============================================================
# BASE DE DONNÉES (fichiers JSON simples - pas de SQL requis)
# ============================================================
DATA_DIR = os.environ.get('DATA_DIR', './data')
SECRET   = os.environ.get('NSA_SECRET', 'changez-ce-mot-de-passe-2026')

os.makedirs(DATA_DIR, exist_ok=True)

STORES = ['articles', 'clients', 'commandes', 'livraisons',
          'factures', 'avoirs', 'commerciaux', 'familles', 'fournisseurs']

def load(store):
    path = os.path.join(DATA_DIR, f'{store}.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save(store, data):
    path = os.path.join(DATA_DIR, f'{store}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def next_id(items):
    if not items: return 1
    return max((i.get('id', 0) for i in items), default=0) + 1

# ============================================================
# AUTHENTIFICATION SIMPLE
# ============================================================
tokens = {}  # token -> expiry

def check_auth():
    token = request.headers.get('X-Token') or request.args.get('token')
    if not token or token not in tokens:
        return False
    if time.time() > tokens[token]:
        del tokens[token]
        return False
    return True

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            return jsonify({'error': 'Non autorisé'}), 401
        return f(*args, **kwargs)
    return decorated

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    return jsonify({
        'app': 'ERP NSA Développement',
        'version': '1.0',
        'status': 'ok',
        'time': datetime.now().isoformat()
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    pwd  = data.get('password', '')
    if hashlib.sha256(pwd.encode()).hexdigest() == hashlib.sha256(SECRET.encode()).hexdigest():
        token = secrets.token_hex(32)
        tokens[token] = time.time() + 86400 * 7  # 7 jours
        return jsonify({'token': token, 'ok': True})
    return jsonify({'error': 'Mot de passe incorrect'}), 401

@app.route('/api/ping')
@require_auth
def ping():
    stats = {}
    for s in STORES:
        items = load(s)
        stats[s] = len(items)
    return jsonify({'ok': True, 'stats': stats})

# --- CRUD générique ---
@app.route('/api/<store>', methods=['GET'])
@require_auth
def get_all(store):
    if store not in STORES:
        return jsonify({'error': 'Store inconnu'}), 404
    return jsonify(load(store))

@app.route('/api/<store>/<int:item_id>', methods=['GET'])
@require_auth
def get_one(store, item_id):
    if store not in STORES:
        return jsonify({'error': 'Store inconnu'}), 404
    items = load(store)
    item  = next((i for i in items if i.get('id') == item_id), None)
    if not item:
        return jsonify({'error': 'Non trouvé'}), 404
    return jsonify(item)

@app.route('/api/<store>', methods=['POST'])
@require_auth
def create(store):
    if store not in STORES:
        return jsonify({'error': 'Store inconnu'}), 404
    items    = load(store)
    new_item = request.get_json() or {}
    new_item['id']          = next_id(items)
    new_item['dateCreation'] = datetime.now().isoformat()
    items.append(new_item)
    save(store, items)
    return jsonify(new_item), 201

@app.route('/api/<store>/<int:item_id>', methods=['PUT'])
@require_auth
def update(store, item_id):
    if store not in STORES:
        return jsonify({'error': 'Store inconnu'}), 404
    items   = load(store)
    updated = request.get_json() or {}
    updated['id'] = item_id
    updated['dateModification'] = datetime.now().isoformat()
    idx = next((i for i, x in enumerate(items) if x.get('id') == item_id), None)
    if idx is None:
        items.append(updated)
    else:
        items[idx] = updated
    save(store, items)
    return jsonify(updated)

@app.route('/api/<store>/<int:item_id>', methods=['DELETE'])
@require_auth
def delete(store, item_id):
    if store not in STORES:
        return jsonify({'error': 'Store inconnu'}), 404
    items = load(store)
    items = [i for i in items if i.get('id') != item_id]
    save(store, items)
    return jsonify({'ok': True})

# --- Import groupé (depuis ERP PC) ---
@app.route('/api/import/<store>', methods=['POST'])
@require_auth
def import_store(store):
    if store not in STORES:
        return jsonify({'error': 'Store inconnu'}), 404
    data  = request.get_json() or {}
    items = data.get(store) or data.get('items') or []
    if not items:
        return jsonify({'error': 'Aucune donnée'}), 400
    existing = load(store)
    added = updated = 0
    for item in items:
        item_id = item.get('id')
        idx = next((i for i, x in enumerate(existing) if x.get('id') == item_id), None)
        if idx is not None:
            existing[idx] = item
            updated += 1
        else:
            if not item_id:
                item['id'] = next_id(existing)
            existing.append(item)
            added += 1
    save(store, existing)
    return jsonify({'ok': True, 'added': added, 'updated': updated, 'total': len(existing)})

# --- Export groupé (vers ERP mobile) ---
@app.route('/api/export/<store>', methods=['GET'])
@require_auth
def export_store(store):
    if store not in STORES:
        return jsonify({'error': 'Store inconnu'}), 404
    items = load(store)
    return jsonify({'type': 'erp-export', 'store': store, store: items, 'count': len(items)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
