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
    im = theme.image(nom, taille, ACC.get(role, role))
    im.set_halign(Gtk.Align.CENTER); im.set_valign(Gtk.Align.CENTER)
    return im

_vign = {}
def vignette(chemin, l, h, couvrir=True, echelle=2):
    """Gtk.Picture d'une image réduite (évite les tailles naturelles géantes)."""
    from gi.repository import GdkPixbuf
    cle = (chemin, l, h, echelle)
    tex = _vign.get(cle)
    if tex is None:
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(chemin, l * echelle, h * echelle, True)
            tex = Gdk.Texture.new_for_pixbuf(pb)
        except Exception:
            tex = None
        _vign[cle] = tex
    p = Gtk.Picture.new_for_paintable(tex) if tex else Gtk.Picture()
    p.set_content_fit(Gtk.ContentFit.COVER if couvrir else Gtk.ContentFit.CONTAIN)
    p.set_size_request(l, h); p.set_can_shrink(True)
    return p

# classes de titres (ex-Astoria, sans accents) : Space Grotesk a tous les accents, plus rien à retirer
ASTORIA = set()
_ANCIEN_ASTORIA = {"hero-grand", "page-titre", "panneau-titre", "nav-titre", "titre-astoria", "haut-logo", "filigrane", "fil-txt", "grand-titre", "v-titre", "surimp-titre-astoria"}

def sans_accents_astoria(s):
    s = (s or "").replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"))

def _astoria(l, _p=None):
    t = l.get_label(); s = sans_accents_astoria(t)
    if s != t: l.set_label(s)

def label(txt, *classes, xalign=0, wrap=False, ellipsize=False, markup=False, largeur=None, **kw):
    l = Gtk.Label(xalign=xalign, **kw)
    if ASTORIA & set(classes) and not markup: txt = sans_accents_astoria(txt)
    l.set_markup(txt) if markup else l.set_text(txt)
    for c in classes: l.add_css_class(c)
    if ASTORIA & set(classes) and not markup: l.connect("notify::label", _astoria)
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

def clic_droit_w(widget, rappel):
    """Clic droit dont le rappel reçoit le widget (rappel(w)) : à préférer à une fonction qui cite le widget lui-même,
    car un widget retenu par son propre gestionnaire n'est jamais libéré (fuite de mémoire à chaque reconstruction)."""
    g = Gtk.GestureClick(button=3)
    g.connect("pressed", lambda g, n, x, y: rappel(g.get_widget()))
    widget.add_controller(g)
    return g

def survol_revele(widget, rv):
    """Révèle rv au survol de widget, sans que le gestionnaire retienne le widget (pas de fuite)."""
    widget._rv = rv
    m = Gtk.EventControllerMotion()
    m.connect("enter", lambda c, *_: c.get_widget()._rv.set_reveal_child(True))
    m.connect("leave", lambda c, *_: c.get_widget()._rv.set_reveal_child(False))
    widget.add_controller(m)
    return m

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
    im.set_pixel_size(taille); im.set_halign(Gtk.Align.CENTER); im.set_valign(Gtk.Align.CENTER)
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


def glisser_deposer(b, cle, deposer):
    """Widget déplaçable (glisser) et cible de dépôt : deposer(cle_source) quand un autre élément est lâché dessus."""
    src = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
    src.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(cle))
    src.connect("drag-begin", lambda s_, d_: s_.set_icon(Gtk.WidgetPaintable.new(s_.get_widget()), s_.get_widget().get_width() // 2, s_.get_widget().get_height() // 2))
    b.add_controller(src)
    dt = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
    dt.connect("drop", lambda t, v, x, y: (GLib.idle_add(lambda: (deposer(v), False)[1]), True)[1] if v != cle else False)
    b.add_controller(dt)
