# OS XIII — Fonds XIII : choisir son fond d'écran dans un anneau de vignettes qui tourne autour d'un grand aperçu.
# Flèches, molette ou clic pour tourner l'anneau ; Entrée pour appliquer ; Échap pour fermer.
# Images : fonds XIII, fonds des thèmes, fonds importés et photos du dossier Images.
# Application développée par Matthieu Lamotte.
import sys, os, glob, math
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf
from . import config, theme
from .appli import preparer
from .ui import *

FONDS_PERSO = os.path.expanduser("~/.local/share/xiii/fonds")
EXT = (".png", ".jpg", ".jpeg", ".webp")
CSS = """
window.fonds-anneau { background: #000; }
.fa-voile { background: alpha(#000, .55); }
.fa-apercu { border-radius: 18px; box-shadow: 0 30px 80px alpha(#000, .65); border: 1px solid alpha(#fff, .18); }
.fa-vignette { border-radius: 10px; border: 2px solid alpha(#fff, .20); box-shadow: 0 8px 22px alpha(#000, .5); }
.fa-vignette.fa-choisie { border: 3px solid @accent_bg_color; }
.fa-titre { color: #fff; font-size: 22px; font-weight: 700; }
.fa-nom { color: alpha(#fff, .85); font-size: 13px; }
.fa-aide { color: alpha(#fff, .6); font-size: 12px; }
.fa-bas button.fantome label { color: #fff; }
"""


def images():
    L = []
    for d in (config.FONDS, FONDS_PERSO, os.path.join(GLib.get_user_data_dir(), "xiii", "fonds-themes")):
        L += sorted(f for f in glob.glob(os.path.join(d, "*")) if f.lower().endswith(EXT) and "connexion" not in os.path.basename(f))
    photos = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or os.path.expanduser("~/Images")
    try:
        ph = sorted((f for f in glob.glob(os.path.join(photos, "*")) if f.lower().endswith(EXT)), key=os.path.getmtime, reverse=True)[:24]
    except OSError:
        ph = []
    vus, R = set(), []
    for f in L + ph:
        if f not in vus: vus.add(f); R.append(f)
    return R


def texture(chemin, l, h):
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(chemin, l, h, True)
        return Gdk.Texture.new_for_pixbuf(pb)
    except Exception:
        return None


def flou(chemin):
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(chemin, 48, 27, False)
        pb = pb.scale_simple(480, 270, GdkPixbuf.InterpType.BILINEAR).scale_simple(1280, 720, GdkPixbuf.InterpType.BILINEAR)
        return Gdk.Texture.new_for_pixbuf(pb)
    except Exception:
        return None


class Anneau(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.fonds", flags=Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self):
        self.cfg = preparer(CSS)
        self.L = images() or [self.cfg.get("fond")]
        cur = self.cfg.get("fond")
        self.i = self.L.index(cur) if cur in self.L else 0
        self.angle = self.cible = -self.i * self.pas()
        w = Gtk.Window(application=self, title="Fonds d'écran"); w.add_css_class("fonds-anneau"); self.win = w
        ov = Gtk.Overlay(); w.set_child(ov)
        self.fond = Gtk.Picture(); self.fond.set_content_fit(Gtk.ContentFit.COVER); self.fond.set_can_shrink(True); ov.set_child(self.fond)
        v = Gtk.Box(); v.add_css_class("fa-voile"); ov.add_overlay(v)
        self.fixe = Gtk.Fixed(); ov.add_overlay(self.fixe)
        self.vignettes = []
        for k, f in enumerate(self.L):
            p = Gtk.Picture.new_for_paintable(texture(f, 320, 180)); p.set_content_fit(Gtk.ContentFit.COVER); p.set_can_shrink(True)
            p.add_css_class("fa-vignette"); p.set_overflow(Gtk.Overflow.HIDDEN); p.set_tooltip_text(os.path.basename(f))
            g = Gtk.GestureClick(); g.connect("released", lambda *_a, k=k: self.aller(k) if k != self.i else self.appliquer()); p.add_controller(g)
            self.fixe.put(p, 0, 0); self.vignettes.append(p)
        self.apercu = Gtk.Picture(); self.apercu.set_content_fit(Gtk.ContentFit.COVER); self.apercu.set_can_shrink(True)
        self.apercu.add_css_class("fa-apercu"); self.apercu.set_overflow(Gtk.Overflow.HIDDEN); self.fixe.put(self.apercu, 0, 0)
        # en haut : titre ; en bas : nom, boutons, aide
        h = boite(True, 2, halign=Gtk.Align.CENTER, valign=Gtk.Align.START, margin_top=26)
        h.append(label("Fonds d'écran", "fa-titre", xalign=0.5)); self.l_nom = label("", "fa-nom", xalign=0.5); h.append(self.l_nom); ov.add_overlay(h)
        b = boite(False, 10, "fa-bas", halign=Gtk.Align.END, valign=Gtk.Align.END, margin_bottom=22, margin_end=26)
        b.append(bouton("Parcourir…", "folder-open", "fantome", rappel=self.parcourir)); b.append(bouton("Fermer", None, "fantome", rappel=w.close))
        b.append(bouton("Appliquer", "check", "pilule", rappel=self.appliquer)); ov.add_overlay(b)
        aide = label("← → ou molette : tourner · clic : choisir · Entrée : appliquer · Échap : fermer", "fa-aide", halign=Gtk.Align.START, valign=Gtk.Align.END, margin_bottom=30, margin_start=26)
        ov.add_overlay(aide)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.touche); w.add_controller(k)
        sc = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES | Gtk.EventControllerScrollFlags.DISCRETE)
        sc.connect("scroll", lambda c, dx, dy: (self.aller(self.i + (1 if (dy or dx) > 0 else -1)), True)[1]); w.add_controller(sc)
        self.fixe.add_tick_callback(self.tic)
        w.fullscreen(); w.present(); self.choisir(self.i)

    def pas(self):
        return 2 * math.pi / max(1, len(self.L))

    # ------------------------------------------------------------ anneau
    def aller(self, k):
        n = len(self.L); k %= n
        # chemin le plus court autour de l'anneau
        d = (k - self.i) % n
        if d > n / 2: d -= n
        self.i = k; self.cible -= d * self.pas(); self.choisir(k)

    def choisir(self, k):
        f = self.L[k]
        self.apercu.set_paintable(texture(f, 1280, 720)); self.fond.set_paintable(flou(f))
        self.l_nom.set_text(os.path.basename(f) + ("  ·  fond actuel" if f == self.cfg.get("fond") else ""))
        for j, p in enumerate(self.vignettes): (p.add_css_class if j == k else p.remove_css_class)("fa-choisie")

    def tic(self, w, horloge):
        W, H = self.fixe.get_width(), self.fixe.get_height()
        if W < 10: return True
        self.angle += (self.cible - self.angle) * 0.16
        if abs(self.cible - self.angle) < 1e-4: self.angle = self.cible
        etat = (W, H, round(self.angle, 5))
        if etat == getattr(self, "_etat", None): return True            # rien ne bouge : rien à recalculer
        self._etat = etat
        cx, cy = W / 2, H / 2 + 10
        aw = int(W * .44); ah = int(aw * 9 / 16)
        self.apercu.set_size_request(aw, ah); self.fixe.move(self.apercu, cx - aw / 2, cy - ah / 2)
        rx, ry = W / 2 - 120, H / 2 - 95
        for j, p in enumerate(self.vignettes):
            a = math.pi / 2 + self.angle + j * self.pas()          # la vignette choisie passe en bas, devant
            prof = (math.sin(a) + 1) / 2                            # 0 = au fond (en haut), 1 = devant (en bas)
            k = .55 + .45 * prof
            tw, th = int(190 * k), int(107 * k)
            x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
            p.set_size_request(tw, th); p.set_opacity(.35 + .65 * prof); self.fixe.move(p, x - tw / 2, y - th / 2)
        return True

    # ------------------------------------------------------------ actions
    def touche(self, c, kv, code, etat):
        if kv in (Gdk.KEY_Left, Gdk.KEY_Up): self.aller(self.i - 1); return True
        if kv in (Gdk.KEY_Right, Gdk.KEY_Down, Gdk.KEY_space): self.aller(self.i + 1); return True
        if kv in (Gdk.KEY_Return, Gdk.KEY_KP_Enter): self.appliquer(); return True
        if kv == Gdk.KEY_Escape: self.win.close(); return True
        return False

    def appliquer(self):
        f = self.L[self.i]
        self.cfg = config.modifier(fond=f)
        self.l_nom.set_text(os.path.basename(f) + "  ·  appliqué ✓")

    def parcourir(self):
        d = Gtk.FileDialog(title="Choisir une image")
        ff = Gtk.FileFilter(); ff.set_name("Images"); ff.add_mime_type("image/*")
        st = Gio.ListStore.new(Gtk.FileFilter); st.append(ff); d.set_filters(st)
        def fini(dlg, res):
            try: g = dlg.open_finish(res)
            except Exception: return
            import shutil
            os.makedirs(FONDS_PERSO, exist_ok=True); dest = os.path.join(FONDS_PERSO, os.path.basename(g.get_path()))
            try: shutil.copy(g.get_path(), dest)
            except Exception: dest = g.get_path()
            self.cfg = config.modifier(fond=dest); self.win.close()
        d.open(self.win, None, fini)


def main():
    sys.exit(Anneau().run(sys.argv[:1]))
