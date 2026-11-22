# OS XIII — Mires et tests d'écran, en plein écran : barres SMPTE, PLUGE (noirs), dégradés de gamma, damier de netteté,
# grille de convergence et cadres de sécurité, couleurs pleines (pixels morts), synchronisation son / image (éclair + bip).
# ← → : mire suivante · Échap : quitter · I : afficher / masquer les infos.
# Application développée par Matthieu Lamotte.
import sys, os, math, time, subprocess, shutil
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib

MIRES = [("smpte", "Barres SMPTE"), ("pluge", "PLUGE — réglage des noirs"), ("gamma", "Dégradés et gamma"), ("damier", "Damier — netteté et mise au point"),
         ("grille", "Grille, cercle et cadres de sécurité"), ("rouge", "Rouge plein"), ("vert", "Vert plein"), ("bleu", "Bleu plein"), ("blanc", "Blanc plein"),
         ("noir", "Noir plein"), ("synchro", "Synchronisation son / image")]
BIP = "/usr/share/sounds/XIII/stereo/bell.wav"

class Mires(Gtk.Application):
    def __init__(self, depart=None):
        super().__init__(application_id="fr.xiii.mires"); self.i = next((k for k, (c, _) in enumerate(MIRES) if c == depart), 0); self.infos = True; self.t0 = time.time()

    def do_activate(self):
        w = Gtk.ApplicationWindow(application=self, title="Mires XIII"); self.w = w
        css = Gtk.CssProvider(); css.load_from_string("window { background: #000; }"); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 900)
        self.da = Gtk.DrawingArea(hexpand=True, vexpand=True); self.da.set_draw_func(self.dessin); w.set_child(self.da)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.touche); w.add_controller(k)
        g = Gtk.GestureClick(); g.connect("pressed", lambda *_: self.aller(1)); w.add_controller(g)
        w.fullscreen(); w.present()
        GLib.timeout_add(20, self.tic)

    def aller(self, d): self.i = (self.i + d) % len(MIRES); self.t0 = time.time(); self.da.queue_draw()

    def touche(self, c, kv, code, st):
        if kv in (Gdk.KEY_Escape, Gdk.KEY_q): self.quit()
        elif kv in (Gdk.KEY_Right, Gdk.KEY_space, Gdk.KEY_Page_Down): self.aller(1)
        elif kv in (Gdk.KEY_Left, Gdk.KEY_Page_Up): self.aller(-1)
        elif kv in (Gdk.KEY_i, Gdk.KEY_I): self.infos = not self.infos; self.da.queue_draw()
        else: return False
        return True

    def tic(self):
        if MIRES[self.i][0] == "synchro":
            self.da.queue_draw()
            p = (time.time() - self.t0) % 1.0
            if p < .025 and not getattr(self, "_bip", False):
                self._bip = True
                if shutil.which("pw-play") and os.path.exists(BIP): subprocess.Popen(["pw-play", BIP], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif p > .5: self._bip = False
        return True

    def dessin(self, a, cr, W, H):
        c = MIRES[self.i][0]
        def rect(x, y, w, h, r, g, b): cr.set_source_rgb(r, g, b); cr.rectangle(x, y, w, h); cr.fill()
        if c == "smpte":
            bar = [(.75, .75, .75), (.75, .75, 0), (0, .75, .75), (0, .75, 0), (.75, 0, .75), (.75, 0, 0), (0, 0, .75)]
            bw = W / 7
            for i, col in enumerate(bar): rect(i * bw, 0, bw + 1, H * .67, *col)
            for i, col in enumerate([(0, 0, .75), (.075, .075, .075), (.75, 0, .75), (.075, .075, .075), (0, .75, .75), (.075, .075, .075), (.75, .75, .75)]): rect(i * bw, H * .67, bw + 1, H * .08, *col)
            for x, w_, col in ((0, 1.25, (0, .13, .3)), (1.25, 1.25, (1, 1, 1)), (2.5, 1.25, (.2, 0, .42)), (3.75, 1.25, (.075,) * 3), (5, .33, (.03,) * 3), (5.33, .34, (.075,) * 3), (5.67, .33, (.115,) * 3), (6, 1, (.075,) * 3)):
                rect(x * bw, H * .75, w_ * bw + 1, H * .25, *col)
        elif c == "pluge":
            rect(0, 0, W, H, .0, .0, .0)
            for k, v in enumerate((-.02, 0, .02, .04)):
                rect(W * (.2 + k * .15), H * .2, W * .1, H * .6, *(max(0, v),) * 3)
            for k in range(11): rect(W * .82, H * (.1 + k * .075), W * .1, H * .07, *(k / 10,) * 3)
        elif c == "gamma":
            for k in range(4):
                for x in range(0, int(W), 2):
                    v = x / W; col = [(v, v, v), (v, 0, 0), (0, v, 0), (0, 0, v)][k]; rect(x, k * H / 4, 2, H / 4, *col)
            for k in range(21): rect(W * k / 21, H * .46, W / 21 + 1, H * .08, *(k / 20,) * 3)
        elif c == "damier":
            n = 16; s = max(W, H) / n
            for x in range(n + 1):
                for y in range(n + 1): rect(x * s, y * s, s, s, *((1, 1, 1) if (x + y) % 2 else (0, 0, 0)))
            cr.set_source_rgb(.5, .5, .5); cr.set_line_width(1)
            for k in range(1, 60): cr.move_to(W / 2, H / 2); cr.line_to(W / 2 + math.cos(k / 60 * 6.283) * H * .3, H / 2 + math.sin(k / 60 * 6.283) * H * .3)
            cr.stroke()
        elif c == "grille":
            rect(0, 0, W, H, .05, .05, .05); cr.set_source_rgb(.8, .8, .8); cr.set_line_width(1)
            for k in range(0, 17): cr.move_to(W * k / 16, 0); cr.line_to(W * k / 16, H)
            for k in range(0, 10): cr.move_to(0, H * k / 9); cr.line_to(W, H * k / 9)
            cr.stroke(); cr.set_line_width(3); cr.arc(W / 2, H / 2, H * .42, 0, 6.283); cr.stroke()
            for marge, col in ((.05, (.94, .7, .47)), (.1, (.3, .8, .4))):
                cr.set_source_rgb(*col); cr.rectangle(W * marge, H * marge, W * (1 - 2 * marge), H * (1 - 2 * marge)); cr.stroke()
            cr.set_source_rgb(1, 1, 1); cr.move_to(W / 2 - 20, H / 2); cr.line_to(W / 2 + 20, H / 2); cr.move_to(W / 2, H / 2 - 20); cr.line_to(W / 2, H / 2 + 20); cr.stroke()
        elif c in ("rouge", "vert", "bleu", "blanc", "noir"):
            rect(0, 0, W, H, *{"rouge": (1, 0, 0), "vert": (0, 1, 0), "bleu": (0, 0, 1), "blanc": (1, 1, 1), "noir": (0, 0, 0)}[c])
        elif c == "synchro":
            p = (time.time() - self.t0) % 1.0
            rect(0, 0, W, H, *((1, 1, 1) if p < .04 else (0, 0, 0)))
            cr.set_source_rgb(.94, .7, .47); cr.set_line_width(6); cr.arc(W / 2, H / 2, H * .3, -1.5708, -1.5708 + p * 6.283); cr.stroke()
        if self.infos:
            cr.set_source_rgba(0, 0, 0, .55); cr.rectangle(0, H - 34, W, 34); cr.fill()
            cr.select_font_face("IBM Plex Sans"); cr.set_font_size(14); cr.set_source_rgb(1, 1, 1)
            t = "%s   ·   %d × %d   ·   ← → mire suivante · I infos · Échap quitter" % (MIRES[self.i][1], W * self.da.get_scale_factor(), H * self.da.get_scale_factor())
            if c == "synchro": t += "   ·   un éclair blanc et un bip par seconde (décalage son/image approximatif selon la sortie audio)"
            cr.move_to(14, H - 12); cr.show_text(t)

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("-")]
    sys.exit(Mires(a[0] if a else None).run(sys.argv[:1]))
