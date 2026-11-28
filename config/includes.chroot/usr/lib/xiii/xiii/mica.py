# OS XIII — effet « Mica » (option, désactivée par défaut) : la barre des tâches, la barre du haut et les panneaux
# laissent voir le fond d'écran flouté qui se trouve derrière eux, teinté de la couleur du thème.
# Comme l'effet Mica de Windows 11, c'est le fond d'écran qui est flouté (pas les fenêtres) : aucun calcul en continu,
# une seule image floutée par fond d'écran, d'où un coût nul pour la carte graphique (marche sur un vieux PC).
# Le vrai flou en direct derrière les fenêtres demanderait un autre gestionnaire de fenêtres que labwc.
# Application développée par Matthieu Lamotte.
import os, hashlib
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0"); gi.require_version("Graphene", "1.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Graphene
from gi.repository import Gtk4LayerShell as LS

CACHE = os.path.join(GLib.get_user_cache_dir(), "xiii", "mica")


def image_floue(fond, W, H):
    """Fond d'écran recadré comme « Remplir » à W × H, très flouté ; chemin du PNG en cache (ou None)."""
    if not fond or not os.path.exists(fond) or W < 10 or H < 10: return None
    try: m = os.path.getmtime(fond)
    except OSError: return None
    cle = hashlib.sha1(("%s|%s|%dx%d" % (fond, m, W, H)).encode()).hexdigest()[:16]
    f = os.path.join(CACHE, cle + ".png")
    if os.path.exists(f): return f
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file(fond)
        k = max(W / pb.get_width(), H / pb.get_height())
        pw, ph = max(1, int(pb.get_width() * k + .5)), max(1, int(pb.get_height() * k + .5))
        pb = pb.scale_simple(pw, ph, GdkPixbuf.InterpType.BILINEAR)
        pb = pb.new_subpixbuf((pw - W) // 2, (ph - H) // 2, W, H)
        # flou : réduction forte puis agrandissements successifs (lisse, sans calcul lourd)
        p = pb.scale_simple(max(1, W // 40), max(1, H // 40), GdkPixbuf.InterpType.HYPER)
        for d in (10, 4, 1):
            p = p.scale_simple(max(1, W // d), max(1, H // d), GdkPixbuf.InterpType.BILINEAR)
        os.makedirs(CACHE, exist_ok=True)
        for x in os.listdir(CACHE):
            if x != os.path.basename(f):
                try: os.remove(os.path.join(CACHE, x))
                except OSError: pass
        p.savev(f, "png", [], [])
        return f
    except Exception:
        return None


def taille_ecran(fenetre=None):
    try:
        d = Gdk.Display.get_default(); mon = None
        if fenetre is not None and fenetre.get_surface() is not None: mon = d.get_monitor_at_surface(fenetre.get_surface())
        if mon is None: mon = d.get_monitors().get_item(0)
        g = mon.get_geometry(); return g.width, g.height
    except Exception:
        return 1920, 1080


def position(w, Wm, Hm):
    """Coin haut gauche d'une surface de couche sur l'écran, d'après ses bords d'ancrage, ses marges et sa taille."""
    E = LS.Edge; ww, wh = w.get_width(), w.get_height()
    def axe(a, b, ma, mb, total, taille):
        if a and b: return ma + (total - ma - mb - taille) / 2 if taille < total - ma - mb else ma
        if a: return ma
        if b: return total - mb - taille
        return (total - taille) / 2
    try:
        x = axe(LS.get_anchor(w, E.LEFT), LS.get_anchor(w, E.RIGHT), LS.get_margin(w, E.LEFT), LS.get_margin(w, E.RIGHT), Wm, ww)
        y = axe(LS.get_anchor(w, E.TOP), LS.get_anchor(w, E.BOTTOM), LS.get_margin(w, E.TOP), LS.get_margin(w, E.BOTTOM), Hm, wh)
    except Exception:
        return 0, 0
    return int(x), int(y)


class Mica:
    """Une feuille de style par surface (barre, haut, panneaux), recalculée quand la surface s'ouvre ou bouge."""
    def __init__(self, shell):
        self.sh = shell; self.parts = {}
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 20)

    def actif(self):
        return bool(self.sh.cfg.get("flou_panneaux", False)) and not self.sh.cfg.get("vieux_pc")

    def appliquer(self, nom, fenetre, widget, opacite=.74):
        """Fond flouté sous « widget » (enfant de « fenetre »), à la bonne place sur l'écran."""
        if not self.actif() or fenetre is None or widget is None:
            if nom in self.parts: self.parts.pop(nom); self.charger()
            return
        def go():
            Wm, Hm = taille_ecran(fenetre)
            img = image_floue(self.sh.cfg.get("fond"), Wm, Hm)
            if not img or fenetre.get_width() < 2: return False
            x, y = position(fenetre, Wm, Hm)
            ok, bx, by = False, 0, 0
            try:
                pt = widget.compute_point(fenetre, Graphene.Point().init(0, 0))
                ok, bx, by = pt[0], pt[1].x, pt[1].y
            except Exception:
                pass
            x += int(bx) if ok else 0; y += int(by) if ok else 0
            classe = "mica-" + nom
            widget.add_css_class(classe)
            p = self.sh.p; teinte = p["panneau_plein"] if p["panneau_plein"].startswith("#") else "#202020"
            self.parts[nom] = (".%s { background-color: transparent; background-image: linear-gradient(alpha(%s,%.2f), alpha(%s,%.2f)), url(\"file://%s\"); "
                               "background-size: auto, %dpx %dpx; background-position: 0 0, %dpx %dpx; background-repeat: no-repeat; }"
                               % (classe, teinte, opacite, teinte, opacite, img, Wm, Hm, -x, -y))
            self.charger(); return False
        GLib.timeout_add(60, go)

    def charger(self):
        self.css.load_from_string("\n".join(self.parts.values()))

    def tout(self):
        """Après un changement de fond, de thème ou de position : toutes les surfaces visibles."""
        sh = self.sh
        if not self.actif():
            self.parts.clear(); self.charger(); return
        if hasattr(sh, "barre") and hasattr(sh, "cb"): self.appliquer("barre", sh.barre, sh.cb, .70)
        if hasattr(sh, "haut") and sh.haut.get_child() is not None: self.appliquer("haut", sh.haut, sh.haut.get_child(), .70)
        if sh.ouvert and sh.ouvert in sh.panneaux:
            w, obj = sh.panneaux[sh.ouvert]; self.appliquer("panneau", w, obj.widget)
