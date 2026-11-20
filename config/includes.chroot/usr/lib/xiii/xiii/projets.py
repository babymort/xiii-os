# OS XIII — projets XIII (dossier ~/XIII/<nom> avec ses sous-dossiers), comme le sélecteur de projet de la suite.
# Application développée par Matthieu Lamotte.
import os, re, json, shutil
from gi.repository import GLib
from . import config

BASE = os.path.expanduser("~/XIII")
SOUS = ["01_Rushes", "02_Son", "03_Documents", "04_Graphismes", "05_Montage", "06_Exports", "07_Livraison"]

def nettoyer(nom):
    return re.sub(r'[\\/:*?"<>|]', "-", nom or "").strip()

def liste():
    return sorted(d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE, d))) if os.path.isdir(BASE) else []

def activer(nom):
    nom = nettoyer(nom)
    if not nom: return None
    d = os.path.join(BASE, nom)
    for x in SOUS: os.makedirs(os.path.join(d, x), exist_ok=True)
    bm = os.path.join(GLib.get_user_config_dir(), "gtk-3.0", "bookmarks"); os.makedirs(os.path.dirname(bm), exist_ok=True)
    try: L = [l for l in open(bm).read().splitlines() if "/XIII/" not in l]
    except OSError: L = []
    L.insert(0, "file://%s Projet %s" % (GLib.uri_escape_string(d, "/", False), nom)); open(bm, "w").write("\n".join(L) + "\n")
    config.modifier(projet_actif=nom)
    return d

def nom_depuis_fichier(f):
    """Nom du projet contenu dans un fichier .xiii / .xiii.json de la suite (fiche projet, conducteur, plan…)."""
    try: o = json.load(open(f))
    except Exception: return None
    for chemin in (("fiche", "title"), ("project", "name"), ("data", "project"), ("data", "titre"), ("data", "title"), ("title",), ("name",), ("projet",)):
        v = o
        for k in chemin: v = v.get(k) if isinstance(v, dict) else None
        if isinstance(v, str) and v.strip(): return v.strip()
    return os.path.basename(f).split(".")[0]

def importer(f):
    """Crée / active le projet décrit par le fichier et y range le fichier (03_Documents)."""
    nom = nom_depuis_fichier(f)
    d = activer(nom)
    if d:
        try: shutil.copy(f, os.path.join(d, "03_Documents", os.path.basename(f)))
        except OSError: pass
    return nom
