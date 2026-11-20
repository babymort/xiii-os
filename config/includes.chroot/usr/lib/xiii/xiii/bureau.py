# OS XIII — icônes sur le bureau : contenu du dossier Bureau, double-clic pour ouvrir, glisser-déposer pour copier,
# clic droit sur le bureau pour les actions courantes.
# Application développée par Matthieu Lamotte.
import os, shutil, subprocess
import gi
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from gi.repository import Gtk4LayerShell as LS
from . import apps, systeme as S
from .ui import *

def dossier_bureau():
    p = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP) or os.path.expanduser("~/Bureau")
    if p == os.path.expanduser("~"): p = os.path.expanduser("~/Bureau")
    os.makedirs(p, exist_ok=True)
    return p

class Bureau:
    def __init__(self, shell):
        self.shell = shell; self.dossier = dossier_bureau()
        w = Gtk.Window(application=shell); self.w = w
        LS.init_for_window(w); LS.set_namespace(w, "xiii-bureau"); LS.set_layer(w, LS.Layer.BOTTOM)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(w, e, True)
        LS.set_exclusive_zone(w, 0); LS.set_keyboard_mode(w, LS.KeyboardMode.ON_DEMAND); w.add_css_class("xiii-surface")
        self.grille = Gtk.FlowBox(orientation=Gtk.Orientation.VERTICAL, max_children_per_line=7, min_children_per_line=1,
                                  selection_mode=Gtk.SelectionMode.NONE, column_spacing=4, row_spacing=4, halign=Gtk.Align.START, valign=Gtk.Align.START,
                                  margin_top=14, margin_start=14)
        fond = Gtk.Box(hexpand=True, vexpand=True); ov = Gtk.Overlay(); ov.set_child(fond); ov.add_overlay(self.grille)
        ov.set_measure_overlay(self.grille, False)
        w.set_child(ov)
        g = Gtk.GestureClick(button=3); g.connect("pressed", self.menu_bureau); fond.add_controller(g)
        dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY); dt.connect("drop", self.depot); ov.add_controller(dt)
        self.mon = Gio.File.new_for_path(self.dossier).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.mon.connect("changed", lambda *_: GLib.timeout_add(300, lambda: (self.remplir(), False)[1]))
        self.remplir(); self.maj()

    def maj(self):
        self.w.set_visible(bool(self.shell.cfg.get("icones_bureau", True)) and self.shell.cfg.get("mode_bureau", "classique") == "classique")

    def remplir(self):
        vider(self.grille)
        try:
            noms = sorted((n for n in os.listdir(self.dossier) if not n.startswith(".")), key=lambda n: (not os.path.isdir(os.path.join(self.dossier, n)), n.lower()))
        except OSError:
            noms = []
        for n in noms:
            self.grille.append(self.icone(os.path.join(self.dossier, n)))

    def icone(self, p):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4); b.add_css_class("icone-bureau"); b.set_size_request(92, 84)
        nom = os.path.basename(p); gicon = None
        if p.endswith(".desktop"):
            try:
                a = Gio.DesktopAppInfo.new_from_filename(p); gicon = a.get_icon(); nom = a.get_display_name()
            except Exception:
                a = None
        b.append(gicon_image(gicon or apps.icone_fichier(p), 44))
        l = label(nom, "app-nom", xalign=0.5, wrap=True, ellipsize=True, largeur=12); l.set_lines(2); b.append(l)
        b.set_tooltip_text(nom)
        g = Gtk.GestureClick(); g.connect("pressed", lambda gg, n, x, y: self.ouvrir(p) if n == 2 else None); b.add_controller(g)
        g3 = Gtk.GestureClick(button=3); g3.connect("pressed", lambda *_: self.menu_icone(b, p)); b.add_controller(g3)
        ds = Gtk.DragSource(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        ds.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([Gio.File.new_for_path(p)])))
        b.add_controller(ds)
        return b

    def ouvrir(self, p):
        if p.endswith(".desktop"):
            try:
                a = Gio.DesktopAppInfo.new_from_filename(p)
                if a: apps.lancer(a); return
            except Exception:
                pass
        if p.lower().endswith((".exe", ".msi")):
            S.detacher(["xiii-windows", p]); return
        apps.ouvrir_fichier(p)

    def menu_icone(self, w, p):
        """Menu clic droit d'un fichier, comme sur Windows / Mac."""
        uri = Gio.File.new_for_path(p).get_uri()
        items = [("folder-open", "Ouvrir", lambda: self.ouvrir(p))]
        if os.path.isfile(p):
            items.append(("eye", "Aperçu rapide", lambda: S.detacher(["xiii-apercu", p])))
            try:
                ct = Gio.content_type_guess(p, None)[0]
                for a in Gio.AppInfo.get_recommended_for_type(ct)[:4]:
                    items.append(("app-window", "Ouvrir avec " + a.get_display_name(), lambda a=a: a.launch([Gio.File.new_for_path(p)], None)))
            except Exception:
                pass
        items += [None,
                  ("scissors", "Couper", lambda: self.presse_papiers(p, couper=True)),
                  ("copy", "Copier", lambda: self.presse_papiers(p)),
                  ("text-cursor-input", "Renommer", lambda: self.renommer(p)),
                  ("archive", "Compresser (.zip)", lambda: S.detacher(["sh", "-c", 'cd "$1" && zip -qr "$2.zip" "$2"', "-", os.path.dirname(p), os.path.basename(p)])),
                  ("send", "Envoyer à DOSSIER XIII", lambda: S.detacher(["xiii-suite", "--dossier", p])), None,
                  ("folder", "Afficher dans le dossier", lambda: S.detacher(["thunar", self.dossier])),
                  ("link", "Copier le chemin", lambda: Gdk.Display.get_default().get_clipboard().set_text(p)),
                  ("trash-2", "Mettre à la corbeille", lambda: Gio.File.new_for_path(p).trash(None)), None,
                  ("info", "Propriétés", lambda: S.detacher(["dbus-send", "--session", "--dest=org.xfce.FileManager", "--type=method_call", "/org/xfce/FileManager",
                                                            "org.xfce.FileManager.DisplayFileProperties", "string:" + uri, "string:", "string:"]))]
        popover_menu(w, items)

    def presse_papiers(self, p, couper=False):
        """Copier / couper au format des gestionnaires de fichiers (collable dans Fichiers)."""
        uri = Gio.File.new_for_path(p).get_uri()
        gnome = ("cut" if couper else "copy") + "\n" + uri
        prov = Gdk.ContentProvider.new_union([
            Gdk.ContentProvider.new_for_bytes("x-special/gnome-copied-files", GLib.Bytes.new(gnome.encode())),
            Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new((uri + "\r\n").encode())),
            Gdk.ContentProvider.new_for_value(p)])
        Gdk.Display.get_default().get_clipboard().set_content(prov)

    def renommer(self, p):
        from .parametres import demander
        demander(None, "Renommer", "Nouveau nom", os.path.basename(p),
                 lambda n: os.rename(p, os.path.join(os.path.dirname(p), n)) if n and "/" not in n and not os.path.exists(os.path.join(os.path.dirname(p), n)) else None)

    def menu_bureau(self, g, n, x, y):
        self.shell.fermer()
        def nouveau_dossier():
            i = 1; d = os.path.join(self.dossier, "Nouveau dossier")
            while os.path.exists(d): i += 1; d = os.path.join(self.dossier, "Nouveau dossier %d" % i)
            os.makedirs(d)
        ancre = Gtk.Box(); ancre.set_size_request(1, 1)
        self.grille.get_parent().add_overlay(ancre); ancre.set_halign(Gtk.Align.START); ancre.set_valign(Gtk.Align.START)
        ancre.set_margin_start(int(x)); ancre.set_margin_top(int(y))
        def nouveau_texte():
            i = 1; f = os.path.join(self.dossier, "Nouveau document.txt")
            while os.path.exists(f): i += 1; f = os.path.join(self.dossier, "Nouveau document %d.txt" % i)
            open(f, "w").close()
        pop = popover_menu(ancre, [("folder", "Nouveau dossier", nouveau_dossier), ("file-text", "Nouveau document texte", nouveau_texte),
                                   ("refresh-cw", "Actualiser", self.remplir), None,
                                   ("layout-dashboard", "Vue des tâches", lambda: self.shell.basculer("vue")),
                                   ("layout-panel-left", "Disposer les fenêtres", lambda: self.shell.basculer("dispositions")), None,
                                   ("image", "Changer de fond d'écran", lambda: self.shell.parametres("fond")),
                                   ("monitor", "Paramètres d'affichage", lambda: self.shell.parametres("ecran")),
                                   ("palette", "Personnaliser", lambda: self.shell.parametres("perso")), None,
                                   ("folder-open", "Ouvrir le dossier Bureau", lambda: S.detacher(["thunar", self.dossier])),
                                   ("square-terminal", "Ouvrir dans le terminal", lambda: S.detacher(["foot", "--app-id=fr.xiii.terminal", "-D", self.dossier]))])
        pop.connect("closed", lambda *_: GLib.idle_add(lambda: (ancre.get_parent() and ancre.get_parent().remove_overlay(ancre), False)[1]))

    def depot(self, cible, valeur, x, y):
        for f in valeur.get_files():
            src = f.get_path()
            if not src or os.path.dirname(src) == self.dossier: continue
            dest = os.path.join(self.dossier, os.path.basename(src))
            try:
                (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dest)
            except Exception:
                pass
        return True
