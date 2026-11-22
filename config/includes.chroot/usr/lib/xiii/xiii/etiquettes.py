# OS XIII — étiquettes de couleur des fichiers (comme sur Mac).
# Rangées dans l'attribut étendu « user.xdg.tags » (norme freedesktop, suit le fichier quand on le renomme ou le déplace
# sur le même disque) ; sur les disques qui ne le permettent pas (clés FAT, certains NAS), dans une liste de secours.
import os, json
from gi.repository import GLib

COULEURS = [("rouge", "Rouge", "#e5534b"), ("orange", "Orange", "#f0883e"), ("jaune", "Jaune", "#e3b341"), ("vert", "Vert", "#57ab5a"),
            ("bleu", "Bleu", "#539bf5"), ("violet", "Violet", "#b083f0"), ("gris", "Gris", "#8b949e")]
HEX = {k: h for k, _, h in COULEURS}; NOMS = {k: n for k, n, _ in COULEURS}
SECOURS = os.path.join(GLib.get_user_data_dir(), "xiii", "etiquettes.json")
ATTR = "user.xdg.tags"

_cache = {"t": None, "d": {}}
def _secours():
    """Liste de secours, relue seulement si elle a changé (appelée pour chaque ligne affichée)."""
    try: t = os.path.getmtime(SECOURS)
    except OSError: return {}
    if t != _cache["t"]:
        try: _cache["d"] = json.load(open(SECOURS))
        except Exception: _cache["d"] = {}
        _cache["t"] = t
    return _cache["d"]

def lire(p):
    try:
        v = os.getxattr(p, ATTR).decode()
        t = [x for x in v.split(",") if x in HEX]
        if t: return t[0]
    except OSError: pass
    return _secours().get(os.path.abspath(p))

def poser(p, couleur):
    """couleur = clé de COULEURS, ou None pour retirer."""
    p = os.path.abspath(p); ok = False
    try:
        if couleur: os.setxattr(p, ATTR, couleur.encode())
        else:
            try: os.removexattr(p, ATTR)
            except OSError: pass
        ok = True
    except OSError: pass
    d = dict(_secours())
    if couleur and not ok: d[p] = couleur
    else: d.pop(p, None)
    try:
        os.makedirs(os.path.dirname(SECOURS), exist_ok=True); json.dump(d, open(SECOURS, "w"), ensure_ascii=False)
    except OSError: pass

def chercher(couleur, racines, limite=500):
    """Fichiers portant cette étiquette (attributs étendus sous les dossiers donnés + liste de secours)."""
    out = [p for p, c in _secours().items() if c == couleur and os.path.exists(p)]
    for r in racines:
        for d, ds, fs in os.walk(r):
            ds[:] = [x for x in ds if not x.startswith(".") and x not in ("node_modules", "__pycache__")]
            for x in ds + fs:
                p = os.path.join(d, x)
                try:
                    if couleur in os.getxattr(p, ATTR).decode().split(","): out.append(p)
                except OSError: pass
            if len(out) >= limite: return out
    return out
