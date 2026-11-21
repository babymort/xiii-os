# OS XIII — animations de démarrage : aperçu animé (thèmes installés et store) et store de thèmes (façon Bazzite).
# Store : les 80 thèmes libres d'adi1090x/plymouth-themes (GPL-3.0), aperçus GIF, installation en un clic.
# Application développée par Matthieu Lamotte.
import os, re, json, glob, subprocess, urllib.request
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

CATALOGUE = "/usr/share/xiii/demarrage/catalogue.json"
CACHE = os.path.join(GLib.get_user_cache_dir(), "xiii", "animations")
THEMES = "/usr/share/plymouth/themes"

def catalogue():
    try: return json.load(open(CATALOGUE, encoding="utf-8"))
    except Exception: return []

def installe(dossier):
    return os.path.isdir(os.path.join(THEMES, dossier))

def apercu_local(url):
    """GIF d'aperçu téléchargé une fois puis gardé en cache."""
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, os.path.basename(url))
    if not os.path.exists(f):
        req = urllib.request.Request(url, headers={"User-Agent": "OS-XIII"})
        data = urllib.request.urlopen(req, timeout=30).read()
        open(f + ".part", "wb").write(data); os.replace(f + ".part", f)
    return f

def images_theme(theme):
    """Images d'un thème installé, dans l'ordre de l'animation."""
    d = os.path.join(THEMES, theme)
    L = glob.glob(d + "/*.png")
    def cle(p):
        n = re.findall(r"\d+", os.path.basename(p)); return (os.path.basename(p).rstrip("0123456789.png"), int(n[-1]) if n else -1)
    L.sort(key=cle)
    # les « progress-N.png », « f-N.png », « throbber-N.png » forment l'animation ; à défaut toutes les images
    anim = [p for p in L if re.search(r"(progress|f|throbber|animation|frame)[-_]?\d+\.png$", os.path.basename(p))]
    return anim or L

class Lecteur(Gtk.Picture):
    """Joue un GIF ou une suite d'images (25 i/s) ; s'arrête quand il n'est plus affiché."""
    def __init__(self, largeur=320, hauteur=180):
        super().__init__(); self.set_content_fit(Gtk.ContentFit.CONTAIN); self.set_size_request(largeur, hauteur)
        self._src = 0; self._anim = None; self._images = []; self._i = 0
        self.connect("unmap", lambda *_: self.stop())

    def stop(self):
        if self._src: GLib.source_remove(self._src); self._src = 0

    def gif(self, f, jouer=True):
        self.stop()
        try: self._anim = GdkPixbuf.PixbufAnimation.new_from_file(f)
        except GLib.Error: return
        if self._anim.is_static_image() or not jouer:
            self.set_pixbuf(self._anim.get_static_image()); return
        it = self._anim.get_iter(None)
        def pas():
            it.advance(None); self.set_pixbuf(it.get_pixbuf())
            d = it.get_delay_time(); self._src = GLib.timeout_add(max(20, d if d > 0 else 40), pas); return False
        self.set_pixbuf(it.get_pixbuf()); self._src = GLib.timeout_add(40, pas)

    def suite(self, images, fps=25):
        self.stop(); self._images = images; self._i = 0
        if not images: return
        def pas():
            if not self._images: return False
            self.set_filename(self._images[self._i % len(self._images)]); self._i += 1; return True
        pas(); self._src = GLib.timeout_add(int(1000 / fps), pas)

def fenetre_apercu(parent, titre, gif=None, theme=None):
    """Fenêtre d'aperçu plein écran de l'animation (fond noir, comme au démarrage)."""
    w = Gtk.Window(transient_for=parent, modal=True, title="Aperçu — " + titre, default_width=960, default_height=600)
    css = Gtk.CssProvider(); css.load_from_string(".apercu-noir { background: #000; }")
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 900)
    v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); v.add_css_class("apercu-noir")
    l = Lecteur(900, 520); l.set_vexpand(True); v.append(l)
    b = Gtk.Button(label="Fermer", halign=Gtk.Align.CENTER, margin_bottom=12, margin_top=8); b.connect("clicked", lambda *_: w.close()); v.append(b)
    w.set_child(v)
    k = Gtk.EventControllerKey(); k.connect("key-pressed", lambda c, kv, *_: (w.close(), True)[1] if kv == Gdk.KEY_Escape else False); w.add_controller(k)
    w.present()
    if gif: l.gif(gif)
    elif theme: l.suite(images_theme(theme))
    w.connect("close-request", lambda *_: (l.stop(), False)[1])
    return w
