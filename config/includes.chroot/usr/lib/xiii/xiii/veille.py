# OS XIII — écran de veille utile : horloge plateau, mire de barres, ou conducteur CONDUCO en grand.
# Se ferme au moindre mouvement de souris ou à la moindre touche.
# Application développée par Matthieu Lamotte.
import sys, time, datetime, math
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib
from gi.repository import Gtk4LayerShell as LS
from . import config, theme
from .ui import *

MIRE = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]

class Veille(Gtk.Application):
    def __init__(self, mode):
        super().__init__(application_id="fr.xiii.Veille"); self.mode = mode
    def do_activate(self):
        cfg = config.charger(); couleurs(cfg); self.cfg = cfg; self.p = theme.palette(cfg)
        css = Gtk.CssProvider(); css.load_from_string(theme.css_shell(cfg) + """
window.veille { background: #050505; }
.v-heure { font-family: "IBM Plex Mono", monospace; font-size: 150px; font-weight: 300; color: #eee9e3; }
.v-sec { font-family: "IBM Plex Mono", monospace; font-size: 60px; color: %s; }
.v-date { font-size: 30px; color: #9b938a; }
.v-titre { font-family: Astoria, sans-serif; font-size: 44px; color: %s; }
.v-item { font-size: 26px; color: #eee9e3; }
""" % (self.p["accent"], self.p["accent"]))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 900)
        w = Gtk.Window(application=self); self.w = w; w.add_css_class("veille")
        LS.init_for_window(w); LS.set_namespace(w, "xiii-veille"); LS.set_layer(w, LS.Layer.OVERLAY)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(w, e, True)
        LS.set_exclusive_zone(w, -1); LS.set_keyboard_mode(w, LS.KeyboardMode.EXCLUSIVE)
        self.t0 = time.time(); self.pos = None
        m = Gtk.EventControllerMotion(); m.connect("motion", self.bouge); w.add_controller(m)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", lambda *_: (self.quit(), True)[1]); w.add_controller(k)
        g = Gtk.GestureClick(); g.connect("pressed", lambda *_: self.quit()); w.add_controller(g)
        if self.mode == "mire": w.set_child(self.mire())
        elif self.mode == "conducteur": w.set_child(self.conducteur())
        else: w.set_child(self.horloge())
        w.present()

    def bouge(self, c, x, y):
        if time.time() - self.t0 < 1.5: return
        if self.pos and (abs(self.pos[0] - x) + abs(self.pos[1] - y)) > 6: self.quit()
        self.pos = (x, y)

    def horloge(self):
        v = boite(True, 6, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        v.append(vignette("/usr/share/xiii/logos/xiii-orange.png", 90, 74, couvrir=False))
        r = boite(False, 10, halign=Gtk.Align.CENTER); self.h = label("", "v-heure"); self.s = label("", "v-sec", valign=Gtk.Align.END, margin_bottom=28)
        r.append(self.h); r.append(self.s); v.append(r)
        self.d = label("", "v-date", xalign=0.5); v.append(self.d)
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        def tic():
            n = datetime.datetime.now(); self.h.set_text(n.strftime("%H:%M")); self.s.set_text(n.strftime("%S"))
            self.d.set_text("%s %d %s" % (jours[n.weekday()], n.day, mois[n.month - 1])); return True
        tic(); GLib.timeout_add(250, tic)
        return v

    def mire(self):
        da = Gtk.DrawingArea(hexpand=True, vexpand=True)
        def dessin(a, cr, W, H):
            bw = W / 7
            for i, (r, g, b) in enumerate(MIRE):
                cr.set_source_rgb(r / 255, g / 255, b / 255); cr.rectangle(i * bw, 0, bw + 1, H * 0.67); cr.fill()
            bas = [(0, 0, 192), (19, 19, 19), (192, 0, 192), (19, 19, 19), (0, 192, 192), (19, 19, 19), (192, 192, 192)]
            for i, (r, g, b) in enumerate(bas):
                cr.set_source_rgb(r / 255, g / 255, b / 255); cr.rectangle(i * bw, H * 0.67, bw + 1, H * 0.08); cr.fill()
            for i, c in enumerate([(0, 33, 76), (255, 255, 255), (50, 0, 106), (19, 19, 19), (9, 9, 9), (19, 19, 19), (29, 29, 29)]):
                cr.set_source_rgb(*(x / 255 for x in c)); cr.rectangle(i * bw, H * 0.75, bw + 1, H * 0.25); cr.fill()
            n = datetime.datetime.now(); cr.set_source_rgba(0, 0, 0, 0.75); cr.rectangle(W / 2 - 170, H * 0.80, 340, 70); cr.fill()
            cr.select_font_face("IBM Plex Mono"); cr.set_font_size(46); cr.set_source_rgb(1, 1, 1)
            t = n.strftime("%H:%M:%S"); e = cr.text_extents(t); cr.move_to(W / 2 - e.width / 2, H * 0.80 + 52); cr.show_text(t)
        da.set_draw_func(dessin); GLib.timeout_add(500, lambda: (da.queue_draw(), True)[1])
        return da

    def conducteur(self):
        from .widgets import dernier_lien
        o = dernier_lien("rundown")
        v = boite(True, 14, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        if not o:
            v.append(label("Aucun conducteur (.xiii.json) trouvé", "v-date", xalign=0.5)); v.append(self.horloge()); return v
        c = o.get("conducteur") or {}
        v.append(label(c.get("name") or "Conducteur", "v-titre", xalign=0.5))
        v.append(label(" · ".join(x for x in ((o.get("project") or {}).get("name"), ("%s → %s" % (c.get("start"), c.get("end"))) if c.get("start") else "") if x), "v-date", xalign=0.5))
        for i, it in enumerate((o.get("items") or [])[:12], 1):
            v.append(label("%2d.  %s" % (i, it.get("title") or it.get("name") or ""), "v-item"))
        self.h = label("", "v-sec", xalign=0.5); v.append(self.h)
        GLib.timeout_add(500, lambda: (self.h.set_text(datetime.datetime.now().strftime("%H:%M:%S")), True)[1])
        return v

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else config.charger().get("veille_mode", "horloge")
    Veille(mode).run(sys.argv[:1])
