# OS XIII — icônes personnalisées des applications : bibliothèques libres (Lucide, Tabler, Phosphor), dessin d'une icône
# (couleur, épaisseur, fond) et remplacement du logo d'une appli partout (menu Démarrer, barre des tâches, Dock, Alt+Tab, bureau).
# Le logo d'origine n'est jamais modifié : une copie du .desktop dans ~/.local/share/applications pointe vers la nouvelle icône ;
# « Rétablir » la retire.
# Application développée par Matthieu Lamotte.
import os, re, hashlib, shutil, glob

BIBLIOTHEQUES = [  # clé, nom, dossier, licence, type (trait ou plein), taille du dessin
    ("lucide", "Lucide", "/usr/share/xiii/lucide", "ISC", "trait", 24),
    ("tabler", "Tabler", "/usr/share/xiii/icones/tabler", "MIT", "trait", 24),
    ("phosphor", "Phosphor", "/usr/share/xiii/icones/phosphor", "MIT", "plein", 256),
]
PAR_CLE = {b[0]: b for b in BIBLIOTHEQUES}
DOSSIER = os.path.expanduser("~/.local/share/xiii/icones-perso")
APPLIS = os.path.expanduser("~/.local/share/applications")
FONDS = [("aucun", "Sans fond"), ("rond", "Rond"), ("carre", "Carré arrondi"), ("degrade", "Carré dégradé"), ("goutte", "Goutte")]
_listes = {}


def disponibles():
    return [b for b in BIBLIOTHEQUES if os.path.isdir(b[2]) and glob.glob(os.path.join(b[2], "*.svg"))]


def liste(cle):
    """Noms des icônes d'une bibliothèque (sans .svg), triés."""
    if cle not in _listes:
        d = PAR_CLE[cle][2]
        try: _listes[cle] = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".svg"))
        except OSError: _listes[cle] = []
    return _listes[cle]


def toutes():
    """[(bibliothèque, nom)] de toutes les bibliothèques installées."""
    return [(b[0], n) for b in disponibles() for n in liste(b[0])]


def _source(cle, nom):
    try: return open(os.path.join(PAR_CLE[cle][2], nom + ".svg"), encoding="utf-8").read()
    except OSError: return None


def _decouper(svg):
    """(viewBox, attributs de présentation de la racine, contenu intérieur)."""
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    m = re.search(r"<svg\b([^>]*)>(.*)</svg>", svg, flags=re.S)
    if not m: return "0 0 24 24", {}, ""
    attrs, corps = m.group(1), m.group(2)
    vb = re.search(r'viewBox="([^"]+)"', attrs)
    pres = {}
    for k in ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin"):
        x = re.search(r'\s%s="([^"]*)"' % k, attrs)
        if x: pres[k] = x.group(1)
    return (vb.group(1) if vb else "0 0 24 24"), pres, corps


def melange(a, b, t):
    a, b = a.lstrip("#"), b.lstrip("#")
    c = [round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(c)


def dessiner(cle, nom, couleur="#f0b378", epaisseur=1.75, fond="aucun", couleur_fond="#2a2928"):
    """SVG 128 × 128 de l'icône choisie, prête à servir de logo d'appli."""
    src = _source(cle, nom)
    if src is None: return None
    vb, pres, corps = _decouper(src)
    corps = corps.replace("currentColor", couleur)
    trait = PAR_CLE[cle][4] == "trait"
    if trait:
        pres["stroke"] = couleur; pres["stroke-width"] = "%.2f" % float(epaisseur); pres.setdefault("fill", "none")
        pres.setdefault("stroke-linecap", "round"); pres.setdefault("stroke-linejoin", "round")
    else:
        pres["fill"] = couleur if pres.get("fill", "currentColor") in ("currentColor", "") else pres["fill"].replace("currentColor", couleur)
    g = " ".join('%s="%s"' % (k, v.replace("currentColor", couleur)) for k, v in pres.items())
    defs, forme = "", ""
    if fond == "aucun":
        x, t = 8, 112
    else:
        x, t = 30, 68
        if fond == "rond": forme = '<circle cx="64" cy="64" r="60" fill="%s"/>' % couleur_fond
        elif fond == "carre": forme = '<rect x="6" y="6" width="116" height="116" rx="28" fill="%s"/>' % couleur_fond
        elif fond == "goutte": forme = '<path d="M64 6h40a18 18 0 0 1 18 18v40a58 58 0 0 1-58 58A58 58 0 0 1 6 64 58 58 0 0 1 64 6z" fill="%s"/>' % couleur_fond
        else:
            defs = ('<defs><linearGradient id="d" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient></defs>'
                    % (melange(couleur_fond, "#ffffff", .18), melange(couleur_fond, "#000000", .22)))
            forme = '<rect x="6" y="6" width="116" height="116" rx="28" fill="url(#d)"/><rect x="6.5" y="6.5" width="115" height="115" rx="27.5" fill="none" stroke="#ffffff" stroke-opacity=".18"/>'
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">%s%s'
            '<svg x="%d" y="%d" width="%d" height="%d" viewBox="%s"><g %s>%s</g></svg></svg>') % (defs, forme, x, x, t, t, vb, g, corps)


def apercu(cle, nom, couleur, taille=28):
    """Texture GTK d'une icône de la bibliothèque (grille du sélecteur)."""
    svg = dessiner(cle, nom, couleur, 1.75, "aucun")
    return texture(svg, taille) if svg else None


def texture(svg, taille):
    from gi.repository import GdkPixbuf, Gdk
    try:
        ld = GdkPixbuf.PixbufLoader.new_with_type("svg"); ld.set_size(taille * 2, taille * 2)
        ld.write(svg.encode()); ld.close()
        return Gdk.Texture.new_for_pixbuf(ld.get_pixbuf())
    except Exception:
        return None


# --------------------------------------------------------------------------------------------- appliquer à une appli
def _keyfile(chemin):
    from gi.repository import GLib
    k = GLib.KeyFile()
    k.load_from_file(chemin, GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    return k


def _lire(k, cle):
    try: return k.get_string("Desktop Entry", cle)
    except Exception: return None


def appliquer(app, svg=None, image=None):
    """Remplace le logo de l'appli (Gio.DesktopAppInfo) par le SVG dessiné ou par une image. Renvoie le chemin de l'icône."""
    aid = app.get_id(); src = app.get_filename()
    os.makedirs(DOSSIER, exist_ok=True); os.makedirs(APPLIS, exist_ok=True)
    base = re.sub(r"[^A-Za-z0-9._-]", "_", aid[:-8] if aid.endswith(".desktop") else aid)
    for f in glob.glob(os.path.join(DOSSIER, base + "-*")):
        try: os.remove(f)
        except OSError: pass
    if svg is not None:
        h = hashlib.sha1(svg.encode()).hexdigest()[:8]; ic = os.path.join(DOSSIER, "%s-%s.svg" % (base, h))
        open(ic, "w").write(svg)
    else:
        ext = os.path.splitext(image)[1].lower() or ".png"
        h = hashlib.sha1(open(image, "rb").read()).hexdigest()[:8]; ic = os.path.join(DOSSIER, "%s-%s%s" % (base, h, ext))
        shutil.copy(image, ic)
    dest = os.path.join(APPLIS, aid)
    k = _keyfile(src)
    if _lire(k, "X-XIII-Icone-Origine") is None:
        k.set_string("Desktop Entry", "X-XIII-Icone-Origine", _lire(k, "Icon") or "")
        k.set_string("Desktop Entry", "X-XIII-Icone-Copie", "false" if os.path.abspath(src) == os.path.abspath(dest) else "true")
    k.set_string("Desktop Entry", "Icon", ic)
    k.save_to_file(dest)
    return ic


def personnalisee(app):
    try: return _lire(_keyfile(app.get_filename()), "X-XIII-Icone-Origine") is not None
    except Exception: return False


def retablir(app):
    """Rend le logo d'origine : retire la copie du .desktop (ou remet l'ancienne icône dans un .desktop personnel)."""
    src = app.get_filename()
    try: k = _keyfile(src)
    except Exception: return False
    orig = _lire(k, "X-XIII-Icone-Origine")
    if orig is None: return False
    if _lire(k, "X-XIII-Icone-Copie") == "true":
        os.remove(src)
    else:
        k.set_string("Desktop Entry", "Icon", orig)
        for c in ("X-XIII-Icone-Origine", "X-XIII-Icone-Copie"):
            try: k.remove_key("Desktop Entry", c)
            except Exception: pass
        k.save_to_file(src)
    aid = app.get_id(); base = re.sub(r"[^A-Za-z0-9._-]", "_", aid[:-8] if aid.endswith(".desktop") else aid)
    for f in glob.glob(os.path.join(DOSSIER, base + "-*")):
        try: os.remove(f)
        except OSError: pass
    return True
