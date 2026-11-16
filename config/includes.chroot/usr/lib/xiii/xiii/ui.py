# OS XIII — petits composants GTK4 partagés (bureau et Paramètres).
# Application développée par Matthieu Lamotte.
import unicodedata
from gi.repository import Gtk, Gdk, GLib, Pango
from . import theme

ACC = {"c": "#f0b378", "t": "#eee9e3", "d": "#9b938a"}

def couleurs(cfg):
    p = theme.palette(cfg)
    ACC.update(c=p["accent_texte"], t=p["texte"], d=p["attenue"])

def ico(nom, taille=18, role="t"):
    """Icône Lucide teintée : role c=accent, t=texte, d=atténué, ou couleur #hex."""
    return theme.image(nom, taille, ACC.get(role, role))

def label(txt, *classes, xalign=0, wrap=False, ellipsize=False, markup=False, largeur=None, **kw):
    l = Gtk.Label(xalign=xalign, **kw)
    l.set_markup(txt) if markup else l.set_text(txt)
    for c in classes: l.add_css_class(c)
    if wrap: l.set_wrap(True); l.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if ellipsize: l.set_ellipsize(Pango.EllipsizeMode.END)
    if largeur: l.set_max_width_chars(largeur)
    return l

def boite(vertical=False, esp=0, *classes, **kw):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=esp, **kw)
    for c in classes: b.add_css_class(c)
    return b

def bouton(texte=None, icone=None, *classes, rappel=None, taille=16, role="t", tip=None):
    b = Gtk.Button()
    for c in classes: b.add_css_class(c)
    if icone and texte:
        bx = boite(False, 8); bx.append(ico(icone, taille, role)); bx.append(label(texte)); b.set_child(bx)
    elif icone:
        b.set_child(ico(icone, taille, role))
    else:
        b.set_label(texte or "")
    if rappel: b.connect("clicked", lambda *_: rappel())
    if tip: b.set_tooltip_text(tip)
    return b

def clic_droit(widget, rappel):
    g = Gtk.GestureClick(button=3)
    g.connect("pressed", lambda g, n, x, y: rappel())
    widget.add_controller(g)
    return g

def clic_milieu(widget, rappel):
    g = Gtk.GestureClick(button=2)
    g.connect("pressed", lambda g, n, x, y: rappel())
    widget.add_controller(g)

def vider(b):
    c = b.get_first_child()
    while c:
        n = c.get_next_sibling(); b.remove(c); c = n

def interrupteur(actif, rappel):
    s = Gtk.Switch(active=bool(actif), valign=Gtk.Align.CENTER)
    s._bloque = False
    def chg(sw, _p):
        if not sw._bloque: rappel(sw.get_active())
    s.connect("notify::active", chg)
    def poser(v):
        s._bloque = True; s.set_active(bool(v)); s._bloque = False
    s.poser = poser
    return s

def curseur(val, rappel, mini=0, maxi=100, pas=1, delai=60):
    """Gtk.Scale avec rappel « anti-rebond » (n'inonde pas pactl)."""
    s = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, mini, maxi, pas)
    s.set_draw_value(False); s.set_hexpand(True); s.set_value(val)
    s._bloque = False; s._src = 0
    def chg(sc):
        if sc._bloque: return
        if sc._src: GLib.source_remove(sc._src)
        def go():
            sc._src = 0; rappel(sc.get_value()); return False
        sc._src = GLib.timeout_add(delai, go)
    s.connect("value-changed", chg)
    def poser(v):
        s._bloque = True; s.set_value(v); s._bloque = False
    s.poser = poser
    return s

def popover_menu(parent, items):
    """items = [(icone, texte, rappel) | None (séparateur)]"""
    pop = Gtk.Popover(has_arrow=False)
    pop.set_parent(parent)
    bx = boite(True, 2, margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
    for it in items:
        if it is None:
            bx.append(Gtk.Separator(margin_top=3, margin_bottom=3)); continue
        icone, texte, rap = it
        b = bouton(texte, icone, "ligne", "plat", taille=15)
        b.connect("clicked", lambda _b, r=rap: (pop.popdown(), r()))
        bx.append(b)
    pop.set_child(bx)
    pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1]))
    pop.popup()
    return pop

def defilant(enfant, hauteur_max=None, h=False):
    sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC if h else Gtk.PolicyType.NEVER)
    if hauteur_max:
        sc.set_max_content_height(hauteur_max); sc.set_propagate_natural_height(True)
    sc.set_child(enfant)
    return sc

def gicon_image(gicon, taille):
    im = Gtk.Image.new_from_gicon(gicon) if gicon else Gtk.Image.new_from_icon_name("application-x-executable")
    im.set_pixel_size(taille)
    return im

def icone_wifi(signal):
    return "wifi" if signal >= 70 else "wifi-high" if signal >= 50 else "wifi-low" if signal >= 25 else "wifi-zero"

def icone_volume(v, muet):
    return "volume-x" if muet or v == 0 else "volume-2" if v >= 60 else "volume-1" if v >= 25 else "volume"

def icone_batterie(b):
    if not b: return "plug"
    if b["charge"]: return "battery-charging"
    return "battery-full" if b["pct"] >= 70 else "battery-medium" if b["pct"] >= 35 else "battery-low" if b["pct"] >= 12 else "battery-warning"

def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
