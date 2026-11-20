# OS XIII — gabarit commun des applications XIII : fenêtre, thème, volet d'onglets à gauche (comme la Suite XIII).
# Application développée par Matthieu Lamotte.
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib
from . import config, theme
from .ui import *

def preparer(css_en_plus=""):
    cfg = config.charger(); couleurs(cfg)
    css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(cfg) + """
        .volet { padding: 12px 8px; min-width: 210px; }
        .volet .onglet { border-radius: 10px; padding: 8px 12px; background: transparent; border: none; }
        .volet .onglet:hover { background: alpha(currentColor, .06); }
        .volet .onglet.actif { background: alpha(@accent_bg_color, .2); }
        .volet .onglet.actif label { font-weight: 700; }
        .chiffre { font-family: "IBM Plex Mono", monospace; }
        .ligne-tab { padding: 6px 10px; border-radius: 8px; }
        .ligne-tab:hover { background: alpha(currentColor, .05); }
        .ligne-tab.choisi { background: alpha(@accent_bg_color, .22); }
    """ + css_en_plus)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return cfg

class Volet:
    """Volet d'onglets à gauche + pile de pages à droite."""
    def __init__(self, titre, sous=None):
        self.racine = boite(False, 0)
        self.nav = boite(True, 2, "volet", "nav"); self.nav.set_hexpand(False); self.nav.set_size_request(230, -1)
        self.nav.append(label(titre, "titre-astoria", margin_bottom=2, margin_start=6))
        if sous: self.nav.append(label(sous, "petit", "attenue", margin_start=6, margin_bottom=10, wrap=True, largeur=26))
        self.liste = boite(True, 2); self.nav.append(self.liste)
        self.pied = boite(True, 2, vexpand=True, valign=Gtk.Align.END); self.nav.append(self.pied)
        self.pied.append(label("Application développée par Matthieu Lamotte", "petit", "attenue", margin_start=6, wrap=True, largeur=26))
        self.pile = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True, vexpand=True)
        self.racine.append(self.nav); self.racine.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)); self.racine.append(self.pile)
        self.boutons = {}; self.rappels = {}

    def ajouter(self, cle, icone, nom, widget=None, rappel=None, section=None):
        if section: self.liste.append(label(section, "section", margin_start=8, margin_top=8))
        b = Gtk.Button(); b.add_css_class("onglet")
        bx = boite(False, 10); bx.append(ico(icone, 16, "c")); bx.append(label(nom, ellipsize=True, hexpand=True)); b.set_child(bx)
        b.connect("clicked", lambda *_: self.aller(cle)); self.liste.append(b); self.boutons[cle] = b
        if widget is not None: self.pile.add_named(widget, cle)
        if rappel: self.rappels[cle] = rappel
        return b

    def aller(self, cle):
        for k, b in self.boutons.items(): (b.add_css_class if k == cle else b.remove_css_class)("actif")
        if cle in self.rappels: self.rappels[cle]()
        if self.pile.get_child_by_name(cle): self.pile.set_visible_child_name(cle)

def page(titre, sous=None, icone=None):
    """Page avec en-tête (titre en Astoria) ; renvoie (défilant, contenu)."""
    v = boite(True, 12, margin_start=22, margin_end=22, margin_top=18, margin_bottom=18)
    h = boite(False, 12)
    if icone: h.append(ico(icone, 30, "c"))
    t = boite(True, 0, hexpand=True); t.append(label(titre, "page-titre")); h.append(t)
    if sous: t.append(label(sous, "attenue", wrap=True))
    v.append(h); v._entete = h
    sc = Gtk.ScrolledWindow(vexpand=True, hexpand=True); sc.set_child(v)
    return sc, v
