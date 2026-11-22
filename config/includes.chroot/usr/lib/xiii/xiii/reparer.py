# OS XIII — Réparer un OS XIII installé (depuis la clé live), sans terminal.
# Application développée par Matthieu Lamotte.
import sys, subprocess
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from .appli import preparer
from .ui import *

class Reparer(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.reparer")
    def do_activate(self):
        preparer()
        w = Gtk.ApplicationWindow(application=self, title="Réparer OS XIII", default_width=620, default_height=460)
        v = boite(True, 12, margin_start=24, margin_end=24, margin_top=20, margin_bottom=20); w.set_child(v)
        v.append(label("Réparer OS XIII", "page-titre"))
        v.append(label("Votre ordinateur affiche « Kernel panic » ou ne démarre plus après un arrêt forcé ? Cet outil refait l'image de démarrage et le menu de démarrage de l'OS XIII installé. Vos fichiers ne sont pas touchés.", "attenue", wrap=True))
        pb = Gtk.ProgressBar(); v.append(pb)
        journal = boite(True, 4); sc = defilant(journal); sc.set_vexpand(True); v.append(sc)
        bas = boite(False, 8, halign=Gtk.Align.END)
        def lancer():
            b.set_sensitive(False); src = GLib.timeout_add(150, lambda: (pb.pulse(), True)[1])
            p = subprocess.Popen(["pkexec", "/usr/local/sbin/xiii-reparer-systeme"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def lire(_s, _c):
                l = p.stdout.readline()
                if not l:
                    GLib.source_remove(src); pb.set_fraction(1); return False
                for k in ("ETAPE ", "INFO ", "FINI ", "ERREUR "):
                    if l.startswith(k):
                        journal.append(label(l[len(k):].strip(), "gras" if k in ("FINI ", "ERREUR ") else "", wrap=True, xalign=0))
                        if k == "FINI ": bas.prepend(bouton("Redémarrer", "power", "pilule", rappel=lambda: subprocess.Popen(["systemctl", "reboot"])))
                        if k == "ERREUR ": b.set_sensitive(True)
                return True
            GLib.io_add_watch(p.stdout, GLib.IO_IN | GLib.IO_HUP, lire)
        b = bouton("Réparer", "wrench", "pilule", rappel=lancer)
        bas.append(bouton("Fermer", None, "fantome", rappel=w.close)); bas.append(b); v.append(bas)
        w.present()

def main(): sys.exit(Reparer().run([sys.argv[0]]))
