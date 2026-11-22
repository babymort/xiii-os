# OS XIII — projets XIII (dossier ~/XIII/<nom> avec ses sous-dossiers), comme le sélecteur de projet de la suite.
# Application développée par Matthieu Lamotte.
import os, re, json, shutil, gzip, subprocess
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

def lire_xiii(f):
    """Contenu d'un fichier de la Suite : .xiii (projet complet, JSON compressé gzip) ou .xiii.json / .json (JSON simple)."""
    try:
        with open(f, "rb") as o: b = o.read()
        if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
        o = json.loads(b.decode("utf-8"))
        return o if isinstance(o, dict) else None
    except Exception:
        return None

def fiche_du_paquet(o):
    """Fiche du projet actif dans un projet complet (.xiii) : localStorage « xiii.projets » = {list:[…], active}."""
    try:
        p = json.loads((o.get("ls") or {}).get("xiii.projets") or "null")
        L = p.get("list") or []
        return next((x for x in L if x and x.get("id") == p.get("active")), L[0] if L else None)
    except Exception:
        return None

def nom_depuis_fichier(f):
    """Nom du projet contenu dans un fichier de la suite (.xiii projet complet, fiche projet, conducteur, plan…)."""
    o = lire_xiii(f)
    base = re.sub(r"[_ ]\d{4}-\d\d-\d\d$", "", os.path.basename(f).split(".")[0]).replace("_", " ").strip()
    if o is None: return base or None
    if o.get("format") == "xiii-bundle":
        fi = fiche_du_paquet(o)
        if fi and str(fi.get("title") or "").strip(): return str(fi["title"]).strip()
        n = str(o.get("name") or "").strip()
        return n if n and not n.lower().startswith(("projet xiii", "sauvegarde")) else (base or "Projet XIII")
    for chemin in (("fiche", "title"), ("project", "name"), ("data", "project"), ("data", "titre"), ("data", "title"), ("title",), ("name",), ("projet",)):
        v = o
        for k in chemin: v = v.get(k) if isinstance(v, dict) else None
        if isinstance(v, str) and v.strip(): return v.strip()
    return base

def importer(f):
    """Crée / active le projet décrit par le fichier, le range dans 03_Documents ; un projet complet (.xiii)
    est en plus restauré dans la Suite XIII (tous les outils retrouvent leurs données)."""
    o = lire_xiii(f)
    if o is None and not f.lower().endswith((".xiii", ".json")): raise ValueError("Ce fichier n'est pas un fichier XIII")
    if o is None: raise ValueError("Fichier XIII illisible (abîmé ou incomplet)")
    nom = nom_depuis_fichier(f)
    d = activer(nom)
    if not d: raise ValueError("Nom de projet invalide")
    cible = os.path.join(d, "03_Documents", os.path.basename(f))
    try:
        if os.path.abspath(f) != os.path.abspath(cible): shutil.copy(f, cible)
    except OSError: cible = f
    if o.get("format") == "xiii-bundle":
        fi = fiche_du_paquet(o)
        if fi: ecrire_fiche(nom, fi)
        subprocess.Popen(["xiii-suite", "--restaurer", cible], start_new_session=True)
    return nom


# ---------------------------------------------------------------- fiche projet venue de la Suite XIII
GENRES = {"tv": "Émission TV", "live": "Captation live", "fiction": "Fiction", "doc": "Documentaire", "corporate": "Institutionnel",
          "event": "Événementiel", "pub": "Publicité / clip", "autre": "Autre"}
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _f_fiche(nom):
    return os.path.join(BASE, nettoyer(nom), ".fiche-suite.json")


def ecrire_fiche(nom, fiche):
    """La fiche du projet (dates, lieu, client…) est rangée dans le dossier du projet : elle voyage avec lui."""
    if not nom or not isinstance(fiche, dict): return
    try:
        os.makedirs(os.path.dirname(_f_fiche(nom)), exist_ok=True)
        if fiche != fiche_de(nom):
            json.dump(fiche, open(_f_fiche(nom), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except OSError:
        pass


def fiche_de(nom):
    try:
        return json.load(open(_f_fiche(nom), encoding="utf-8"))
    except Exception:
        return {}


def _date(iso):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    return (int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def resume(nom):
    """« Fiction · tournage du 12 au 14 nov. · Lyon · Client » — vide si la Suite n'a pas encore de fiche."""
    f = fiche_de(nom)
    if not f: return ""
    P = []
    if f.get("genre") in GENRES: P.append(GENRES[f["genre"]])
    d, fi = _date(f.get("debut")), _date(f.get("fin"))
    if d and fi and fi != d:
        P.append("tournage du %d%s au %d %s" % (d[0], "" if d[1] == fi[1] else " " + MOIS[d[1] - 1], fi[0], MOIS[fi[1] - 1]))
    elif d:
        P.append("tournage le %d %s" % (d[0], MOIS[d[1] - 1]))
    for k in ("lieu", "client"):
        if (f.get(k) or "").strip(): P.append(f[k].strip())
    return " · ".join(P)
