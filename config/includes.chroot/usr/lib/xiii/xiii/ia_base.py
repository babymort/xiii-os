# OS XIII — IA XIII : liste des IA et pastille (léger, utilisé par la barre du haut).
# Application développée par Matthieu Lamotte.
from gi.repository import Gtk, Gdk
from .ui import ACC

# clé, nom, monogramme, adresse, adresse avec question (ou None)
IAS = [
    ("claude", "Claude", "C", "https://claude.ai/new", "https://claude.ai/new?q=%s"),
    ("chatgpt", "ChatGPT", "G", "https://chatgpt.com/", "https://chatgpt.com/?q=%s"),
    ("gemini", "Gemini", "Ge", "https://gemini.google.com/app", None),
    ("openjarvis", "OpenJarvis", "OJ", None, None),
]
PAR_CLE = {x[0]: x for x in IAS}
def pastille(k, taille=22, actif=True):
    """Pastille de l'IA : monogramme dans un cercle au trait, comme les icônes de la Suite XIII."""
    nom = PAR_CLE.get(k, IAS[0])[2]
    da = Gtk.DrawingArea(); da.set_size_request(taille, taille)
    def dessin(a, cr, w, h):
        import math
        acc = Gdk.RGBA(); acc.parse(ACC.get("c", "#f0b378")); c = a.get_color()
        col = acc if actif else c
        cr.set_source_rgba(col.red, col.green, col.blue, 1); cr.set_line_width(1.6)
        cr.arc(w / 2, h / 2, min(w, h) / 2 - 1.2, 0, 2 * math.pi); cr.stroke()
        cr.select_font_face("IBM Plex Sans", 0, 1); cr.set_font_size(h * (0.5 if len(nom) == 1 else 0.38))
        e = cr.text_extents(nom); cr.move_to(w / 2 - e.width / 2 - e.x_bearing, h / 2 - e.height / 2 - e.y_bearing); cr.show_text(nom)
    da.set_draw_func(dessin); return da


