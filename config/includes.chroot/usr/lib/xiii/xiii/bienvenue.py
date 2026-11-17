# OS XIII — accueil de la session live : « Essayer OS XIII » ou « Installer OS XIII ».
# Application développée par Matthieu Lamotte.
import sys, os
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk
from . import config, theme, systeme as S
from .ui import *

class Bienvenue(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.Bienvenue")
    def do_activate(self):
        cfg = config.charger(); couleurs(cfg)
        css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(cfg) + """
button.choix { background: #2a2928; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 22px; box-shadow: none; }
button.choix:hover { border-color: #f0b378; background: alpha(#f0b378,0.08); }
button.choix.principal { border-color: alpha(#f0b378,0.6); }
.grand-titre { font-family: Astoria, sans-serif; font-size: 40px; color: #f0b378; }
""")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 900)
        w = Gtk.ApplicationWindow(application=self, title="Bienvenue dans OS XIII", default_width=820, default_height=520)
        w.add_css_class("parametres"); self.w = w
        v = boite(True, 18, margin_top=34, margin_bottom=24, margin_start=40, margin_end=40)
        v.append(vignette("/usr/share/xiii/logos/xiii-orange.png", 120, 98, couvrir=False))
        v.append(label("Bienvenue dans OS XIII", "grand-titre", xalign=0.5))
        v.append(label("Vous utilisez OS XIII depuis la clé ou le DVD, sans rien modifier sur cet ordinateur.", "attenue", xalign=0.5, wrap=True))
        r = boite(False, 18, homogeneous=True, margin_top=10)
        for ic, titre, sous, rap, princ in (("monitor-play" if os.path.exists(theme.LUCIDE + "/monitor-play.svg") else "monitor", "Essayer OS XIII", "Découvrir le bureau, les applications et vos périphériques. Rien n'est écrit sur le disque.", self.essayer, False),
                                            ("hard-drive-download" if os.path.exists(theme.LUCIDE + "/hard-drive-download.svg") else "download", "Installer OS XIII", "Installer sur le disque de cet ordinateur : guidé, en français, environ 10 minutes.", self.installer, True)):
            b = Gtk.Button(); b.add_css_class("choix")
            if princ: b.add_css_class("principal")
            bx = boite(True, 10); bx.append(ico(ic, 44, "c")); bx.append(label(titre, "hero-grand", xalign=0.5)); bx.append(label(sous, "attenue", wrap=True, xalign=0.5, justify=Gtk.Justification.CENTER))
            b.set_child(bx); b.connect("clicked", lambda _b, f=rap: f()); r.append(b)
        v.append(r)
        v.append(label("Vous pourrez lancer l'installation plus tard depuis l'icône « Installer OS XIII » de la barre des tâches.", "attenue", "petit", xalign=0.5, wrap=True))
        v.append(label("Application développée par Matthieu Lamotte", "credit", xalign=0.5))
        w.set_child(v); w.present()
    def essayer(self):
        self.w.close(); S.detacher(["xiii-ctl", "visite"])
    def installer(self):
        self.w.close(); S.detacher(["xiii-installer"])

def main():
    Bienvenue().run(sys.argv[:1])
