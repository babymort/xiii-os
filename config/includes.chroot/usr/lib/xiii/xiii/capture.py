# OS XIII — Outil Capture (façon Outil Capture d'écran de Windows 11) : une petite barre en haut de l'écran pour
# choisir Zone, Écran, Un écran (plusieurs moniteurs), Vidéo d'une zone ou de l'écran, avec ou sans délai.
# Touche Impr. écran ou Super + Maj + S. Échap ferme la barre. Le travail est fait par xiii-capture (grim, slurp, wf-recorder).
# Application développée par Matthieu Lamotte.
import sys, subprocess
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell as LS
from . import config
from .ui import boite, label, ico

MODES = [("zone", "scan", "Zone"), ("moniteur", "monitor", "Un écran"), ("ecran", "maximize", "Écran entier")]
VIDEO = [("video zone", "square-dashed", "Vidéo d'une zone"), ("video ecran", "video", "Vidéo de l'écran")]


def main():
    app = Gtk.Application(application_id="fr.xiii.capture")
    etat = {"delai": 0, "son": False}

    def lancer(w, cmd):
        w.close()
        args = cmd.split() + (["son"] if etat["son"] and cmd.startswith("video") else [])
        d = etat["delai"]
        GLib.timeout_add(250, lambda: (subprocess.Popen(["sh", "-c", ("sleep %d; " % d if d else "") + "exec xiii-capture " + " ".join(args)]), app.quit(), False)[2])

    def activer(app):
        from .appli import preparer
        preparer(".barre-capture { background: alpha(@window_bg_color, .96); border-radius: 16px; padding: 8px 10px; border: 1px solid alpha(currentColor,.12); }"
                 " .barre-capture button { padding: 8px 12px; border-radius: 10px; } .barre-capture button:checked { background: alpha(@accent_bg_color,.28); }")
        w = Gtk.ApplicationWindow(application=app, title="Capture")
        LS.init_for_window(w); LS.set_namespace(w, "xiii-capture"); LS.set_layer(w, LS.Layer.OVERLAY)
        LS.set_anchor(w, LS.Edge.TOP, True); LS.set_margin(w, LS.Edge.TOP, 48); LS.set_keyboard_mode(w, LS.KeyboardMode.EXCLUSIVE)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", lambda c, kv, *_: (app.quit(), True)[1] if kv == Gdk.KEY_Escape else False); w.add_controller(k)
        b = boite(False, 4, "barre-capture")
        def btn(ic, txt, cmd):
            x = Gtk.Button(); bx = boite(False, 6); bx.append(ico(ic, 18)); bx.append(label(txt)); x.set_child(bx)
            x.connect("clicked", lambda *_: lancer(w, cmd)); x.set_tooltip_text(txt); return x
        for cmd, ic, txt in MODES: b.append(btn(ic, txt, cmd))
        b.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        for cmd, ic, txt in VIDEO: b.append(btn(ic, txt, cmd))
        son = Gtk.ToggleButton(); son.set_child(ico("mic", 18)); son.set_tooltip_text("Avec le son (vidéo)")
        son.connect("toggled", lambda t: etat.__setitem__("son", t.get_active())); b.append(son)
        b.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        dl = Gtk.DropDown.new_from_strings(["Sans délai", "3 s", "5 s", "10 s"]); dl.set_tooltip_text("Délai avant la capture")
        dl.connect("notify::selected", lambda d, _p: etat.__setitem__("delai", [0, 3, 5, 10][d.get_selected()])); b.append(dl)
        fermer = Gtk.Button(); fermer.set_child(ico("x", 18)); fermer.set_tooltip_text("Fermer (Échap)"); fermer.connect("clicked", lambda *_: app.quit()); b.append(fermer)
        w.set_child(b); w.present()
    app.connect("activate", activer)
    sys.exit(app.run([]))
