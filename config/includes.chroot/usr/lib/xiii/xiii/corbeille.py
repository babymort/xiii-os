# OS XIII — corbeille : éléments de toutes les corbeilles (dossier personnel + une par clé / disque), restauration à
# l'emplacement d'origine, suppression définitive, nettoyage automatique des éléments plus vieux que N jours.
import os, glob, shutil, datetime, urllib.parse
from gi.repository import GLib

def dossiers():
    L = [os.path.join(GLib.get_user_data_dir(), "Trash")]
    uid = os.getuid()
    for m in glob.glob("/media/*/*") + glob.glob("/run/media/*/*") + glob.glob("/mnt/*"):
        for t in (os.path.join(m, ".Trash-%d" % uid), os.path.join(m, ".Trash", str(uid))):
            if os.path.isdir(os.path.join(t, "files")): L.append(t)
    return L

def elements():
    """[{nom, origine, date (datetime), fichier, info, corbeille, disque}] du plus récent au plus ancien."""
    out = []
    for t in dossiers():
        disque = "Ordinateur" if t.startswith(GLib.get_user_data_dir()) else os.path.basename(os.path.dirname(t) if t.endswith(".Trash-%d" % os.getuid()) else os.path.dirname(os.path.dirname(t)))
        racine = os.path.dirname(t) if not t.startswith(GLib.get_user_data_dir()) else "/"
        for info in glob.glob(os.path.join(t, "info", "*.trashinfo")):
            nom = os.path.basename(info)[:-10]; f = os.path.join(t, "files", nom)
            if not os.path.lexists(f): continue
            orig, date = "", None
            try:
                for l in open(info, errors="replace"):
                    if l.startswith("Path="): orig = urllib.parse.unquote(l[5:].strip())
                    elif l.startswith("DeletionDate="): date = datetime.datetime.fromisoformat(l[13:].strip())
            except Exception: pass
            if orig and not orig.startswith("/"): orig = os.path.join(racine if racine != "/" else os.path.dirname(t), orig)
            out.append({"nom": nom, "origine": orig, "date": date or datetime.datetime.fromtimestamp(os.path.getmtime(info)), "fichier": f, "info": info, "corbeille": t, "disque": disque})
    return sorted(out, key=lambda e: e["date"], reverse=True)

def restaurer(e):
    dest = e["origine"] or os.path.join(os.path.expanduser("~"), e["nom"])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    b, k = dest, 2
    while os.path.lexists(dest):
        n, x = os.path.splitext(b); dest = "%s (%d)%s" % (n, k, x); k += 1
    shutil.move(e["fichier"], dest); os.remove(e["info"])
    return dest

def supprimer(e):
    f = e["fichier"]
    if os.path.isdir(f) and not os.path.islink(f): shutil.rmtree(f, ignore_errors=True)
    else: os.remove(f)
    try: os.remove(e["info"])
    except OSError: pass

def taille(e):
    f = e["fichier"]
    if not os.path.isdir(f) or os.path.islink(f):
        try: return os.lstat(f).st_size
        except OSError: return 0
    t = 0
    for r, _, fs in os.walk(f):
        for x in fs:
            try: t += os.lstat(os.path.join(r, x)).st_size
            except OSError: pass
    return t

def nettoyer(jours):
    """Supprime définitivement ce qui est à la corbeille depuis plus de « jours » jours (0 = jamais)."""
    if not jours: return 0
    limite = datetime.datetime.now() - datetime.timedelta(days=int(jours)); n = 0
    for e in elements():
        if e["date"].replace(tzinfo=None) < limite:
            try: supprimer(e); n += 1
            except OSError: pass
    return n
