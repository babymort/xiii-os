# OS XIII — fond d'écran animé : l'image dérive lentement (zoom et glissement très doux) sous une lueur de l'accent
# qui se promène ; ou une vidéo en boucle (sans son) si le fond choisi est une vidéo.
# Pause automatique sur batterie, en mode Tournage et quand l'écran est verrouillé / en veille (rien n'est visible).
# Application développée par Matthieu Lamotte.
import os, sys, glob
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from gi.repository import Gtk4LayerShell as LS
from . import config, theme

VIDEOS = (".mp4", ".webm", ".mkv", ".mov", ".m4v")

def sur_batterie():
    secteur = [f for f in glob.glob("/sys/class/power_supply/*/online")]
    if not secteur: return False
    try: return not any(open(f).read().strip() == "1" for f in secteur)
    except OSError: return False

class FondAnime(Gtk.Application):
    def __init__(self, chemin):
        super().__init__(application_id="fr.xiii.FondAnime", flags=Gio.ApplicationFlags.NON_UNIQUE); self.chemin = chemin; self.fenetres = []

    def do_activate(self):
        cfg = config.charger(); p = theme.palette(cfg)
        css = Gtk.CssProvider()
        css.load_from_string("""
window.fond-anime { background: #000; }
@keyframes derive { 0% { transform: scale(1.0) translate(0px, 0px); } 50% { transform: scale(1.07) translate(-18px, -10px); } 100% { transform: scale(1.0) translate(0px, 0px); } }
@keyframes lueur { 0% { background-position: 10% 20%; opacity: .55; } 50% { background-position: 80% 70%; opacity: .9; } 100% { background-position: 10% 20%; opacity: .55; } }
.image-fond.anime { animation: derive 48s ease-in-out infinite; }
.lueur { background-image: radial-gradient(circle at center, alpha(ACCENT, .22) 0%, transparent 45%); background-size: 160% 160%; background-repeat: no-repeat; }
.lueur.anime { animation: lueur 30s ease-in-out infinite; }
""".replace("ACCENT", p["accent"]))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 800)
        moniteurs = Gdk.Display.get_default().get_monitors()
        for i in range(moniteurs.get_n_items()): self.fenetre(moniteurs.get_item(i))
        GLib.timeout_add_seconds(20, self.verifier); self.verifier()
        self.hold()

    def fenetre(self, mon):
        w = Gtk.Window(application=self); w.add_css_class("fond-anime")
        LS.init_for_window(w); LS.set_namespace(w, "xiii-fond"); LS.set_layer(w, LS.Layer.BACKGROUND); LS.set_monitor(w, mon)
        for b in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(w, b, True)
        LS.set_exclusive_zone(w, -1); LS.set_keyboard_mode(w, LS.KeyboardMode.NONE)
        ov = Gtk.Overlay()
        if self.chemin.lower().endswith(VIDEOS):
            med = Gtk.MediaFile.new_for_filename(self.chemin); med.set_loop(True); med.set_muted(True); med.play()
            pic = Gtk.Picture.new_for_paintable(med); pic.set_content_fit(Gtk.ContentFit.COVER); self.media = med
        else:
            pic = Gtk.Picture.new_for_filename(self.chemin); pic.set_content_fit(Gtk.ContentFit.COVER); self.media = None
        pic.add_css_class("image-fond"); pic.set_can_shrink(True); ov.set_child(pic)
        lu = Gtk.Box(hexpand=True, vexpand=True); lu.add_css_class("lueur"); lu.set_can_target(False); ov.add_overlay(lu)
        w.set_child(ov); w.present(); self.fenetres.append((w, pic, lu))

    def verifier(self):
        c = config.charger()
        pause = sur_batterie() or c.get("mode_tournage") or c.get("profil") == "tournage" or not c.get("fond_anime", False)
        for _w, pic, lu in self.fenetres:
            for x in (pic, lu): (x.remove_css_class if pause else x.add_css_class)("anime")
        if self.media: (self.media.pause if pause else self.media.play)()
        return True

def main():
    ch = sys.argv[1] if len(sys.argv) > 1 else config.charger().get("fond", "")
    if not os.path.exists(ch): sys.exit(1)
    sys.exit(FondAnime(ch).run([sys.argv[0]]))
