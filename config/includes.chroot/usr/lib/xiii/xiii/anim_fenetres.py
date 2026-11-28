# OS XIII — animations des fenêtres (ouverture, fermeture, réduction), façon Windows 11 / macOS.
# labwc ne sait pas animer les fenêtres elles-mêmes : une surface transparente, au-dessus de tout et qui laisse passer
# les clics, dessine pendant 0,2 s un cadre qui s'envole de l'icône de la barre vers l'écran (ouverture) ou y retourne
# (réduction, fermeture). Coupées avec Paramètres › Accessibilité › Animations, ou Paramètres › Barre › Animer les fenêtres.
# Application développée par Matthieu Lamotte.
import time, math
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib
from gi.repository import Gtk4LayerShell as LS

DUREE = {"ouvrir": .22, "fermer": .18, "reduire": .24, "restaurer": .22}


def _ease(t): return 1 - (1 - t) ** 3


def _rgba(h, a):
    h = h.lstrip("#")[:6]
    try: return tuple(int(h[k:k + 2], 16) / 255 for k in (0, 2, 4)) + (a,)
    except Exception: return (.94, .70, .47, a)


class AnimFenetres:
    def __init__(self, shell):
        self.shell = shell; self.en_cours = []; self.w = None

    def actif(self):
        c = self.shell.cfg
        return c.get("animations", True) and c.get("animations_fenetres", True)

    def _surface(self):
        if self.w: return self.w
        w = Gtk.Window(application=self.shell); LS.init_for_window(w); LS.set_namespace(w, "xiii-anim"); LS.set_layer(w, LS.Layer.OVERLAY)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(w, e, True)
        LS.set_exclusive_zone(w, -1); LS.set_keyboard_mode(w, LS.KeyboardMode.NONE)
        w.add_css_class("xiii-surface"); w.add_css_class("xiii-anim")
        self.da = Gtk.DrawingArea(); self.da.set_draw_func(self._dessiner); w.set_child(self.da)
        w.connect("realize", self._sans_clic); self.w = w
        return w

    @staticmethod
    def _sans_clic(w):
        try:
            import cairo
            w.get_surface().set_input_region(cairo.Region())       # les clics traversent
        except Exception: pass

    def position_bouton(self, b):
        """Rectangle du bouton de la barre, en coordonnées de l'écran."""
        try:
            root = b.get_root(); ok, r = b.compute_bounds(root)
            if not ok: return None
            mon = Gdk.Display.get_default().get_monitor_at_surface(root.get_surface()) if root.get_surface() else None
            g = mon.get_geometry() if mon else Gdk.Rectangle()
            W, H = (g.width or 1920), (g.height or 1080); rw, rh = root.get_width(), root.get_height()
            pos = self.shell.cfg.get("barre_position", "bas")
            ox = (W - rw) / 2 if pos in ("bas", "haut") else (0 if pos == "gauche" else W - rw)
            oy = (H - rh) / 2 if pos in ("gauche", "droite") else (0 if pos == "haut" else H - rh)
            return (ox + r.get_x(), oy + r.get_y(), r.get_width(), r.get_height())
        except Exception:
            return None

    def jouer(self, sorte, bouton):
        if not self.actif(): return
        src = self.position_bouton(bouton) if bouton is not None else None
        if not src and sorte != "fermer": return
        src = src or (0, 0, 1, 1)
        self.en_cours.append((sorte, src, time.monotonic()))
        w = self._surface()
        if not w.get_visible(): w.present()
        if not getattr(self, "_tic", None): self._tic = self.da.add_tick_callback(self._frame)

    def _frame(self, *_):
        now = time.monotonic()
        self.en_cours = [a for a in self.en_cours if now - a[2] < DUREE.get(a[0], .2)]
        self.da.queue_draw()
        if not self.en_cours:
            self._tic = None; self.w.set_visible(False); return False
        return True

    def _dessiner(self, _a, cr, W, H):
        p = getattr(self.shell, "p", {}) or {}; acc = p.get("accent", "#f0b378")
        now = time.monotonic()
        for sorte, (x, y, w, h), t0 in self.en_cours:
            t = min(1, (now - t0) / DUREE.get(sorte, .2)); e = _ease(t)
            gw, gh = W * .56, H * .56; gx, gy = (W - gw) / 2, (H - gh) / 2 - H * .03
            k = e if sorte in ("ouvrir", "restaurer") else 1 - e          # 0 = bouton, 1 = grand cadre
            if sorte == "fermer":                                         # fermeture : le cadre rétrécit sur place et s'efface
                k = 1 - .25 * e; gx2, gy2 = gx + gw * (1 - k) / 2, gy + gh * (1 - k) / 2; rx, ry, rw, rh = gx2, gy2, gw * k, gh * k
                al = 1 - e
            else:
                rx, ry = x + (gx - x) * k, y + (gy - y) * k; rw, rh = w + (gw - w) * k, h + (gh - h) * k
                al = (1 - e) if sorte in ("ouvrir", "restaurer") else (.4 + .6 * (1 - abs(.5 - e) * 2)) * (1 - e * .6)
            rad = min(18, rw / 4, rh / 4)
            cr.new_sub_path()
            cr.arc(rx + rw - rad, ry + rad, rad, -math.pi / 2, 0); cr.arc(rx + rw - rad, ry + rh - rad, rad, 0, math.pi / 2)
            cr.arc(rx + rad, ry + rh - rad, rad, math.pi / 2, math.pi); cr.arc(rx + rad, ry + rad, rad, math.pi, 3 * math.pi / 2); cr.close_path()
            cr.set_source_rgba(*_rgba(p.get("panneau_plein", "#2a2623"), .55 * al)); cr.fill_preserve()
            cr.set_source_rgba(*_rgba(acc, .75 * al)); cr.set_line_width(2); cr.stroke()

    # ------------------------------------------------------------ détection (appelé par la barre à chaque changement de fenêtres)
    def changement(self, fen, boutons, cle_de):
        """fen : fenêtres actuelles ; boutons() : clé d'appli → bouton actuel de la barre ; cle_de(f) → clé d'appli."""
        avant = getattr(self, "_etat", None)
        etat = {f.id: (cle_de(f), f.reduite) for f in fen}
        self._etat = etat
        if avant is None or not self.actif(): return
        evts = []
        for i, (cle, red) in etat.items():
            if i not in avant: evts.append(("ouvrir", cle))
            elif red and not avant[i][1]: evts.append(("reduire", cle))
            elif not red and avant[i][1]: evts.append(("restaurer", cle))
        for i, (cle, _r) in avant.items():
            if i not in etat: evts.append(("fermer", cle))
        if not evts or len(evts) > 4: return               # changement de bureau, session qui démarre… : pas de feu d'artifice
        GLib.timeout_add(40, lambda: ([self.jouer(s, boutons().get(c)) for s, c in evts], False)[1])
