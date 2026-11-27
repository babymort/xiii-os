# Reproduction : bande de déclenchement du dock (couche wlr-layer-shell) — cherche l'erreur de protocole.
import sys, os
sys.path.insert(0, "/usr/lib/xiii")
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, GLib, Gtk4LayerShell as LS
cas = sys.argv[1] if len(sys.argv) > 1 else "bande"
app = Gtk.Application(application_id="fr.xiii.repro" + cas)
def act(app):
    T, B, L, R = LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT
    w = Gtk.Window(application=app); LS.init_for_window(w); LS.set_namespace(w, "repro"); LS.set_layer(w, LS.Layer.TOP)
    if cas == "bande":
        LS.set_anchor(w, B, True); LS.set_exclusive_zone(w, 0)
        b = Gtk.Box(); w.set_child(b)
        for e in (T, B, L, R): LS.set_anchor(w, e, e in (B, L, R))
        w.set_default_size(-1, 3); b.set_size_request(-1, 3); w.present()
    elif cas == "cache-ancres":
        LS.set_anchor(w, B, True); LS.set_anchor(w, L, True); LS.set_anchor(w, R, True); LS.auto_exclusive_zone_enable(w)
        w.set_child(Gtk.Label(label="barre")); w.present()
        def suite():
            w.set_visible(False); LS.set_exclusive_zone(w, 0)
            for e in (T, B, L, R): LS.set_anchor(w, e, e == B)
            LS.set_margin(w, B, 8); return False
        GLib.timeout_add(500, suite)
        GLib.timeout_add(1000, lambda: (w.set_visible(True), False)[1])
    GLib.timeout_add(2500, lambda: (print("OK", cas, "vivant"), app.quit(), False)[2])
app.connect("activate", act); app.run([])
