# OS XIII — Prompteur : le texte défile en grand, en miroir pour une vitre de prompteur.
# • texte tapé, collé, ouvert (.txt, .md, .docx, .odt) ou repris du dernier conducteur CONDUCO
# • vitesse réglable en direct (↑ ↓, molette, pédale USB qui envoie Page suivante / précédente), pause à la barre d'espace
# • miroir horizontal / vertical, taille du texte, marges, ligne de lecture, compte à rebours avant le départ
# Application développée par Matthieu Lamotte.
import os, sys, re, json, time, zipfile
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, Pango, PangoCairo
from . import config, systeme as S
from .ui import *
from .appli import preparer

TEXTE = os.path.join(GLib.get_user_data_dir(), "xiii", "prompteur.txt")

def lire(f):
    e = os.path.splitext(f)[1].lower()
    if e in (".docx", ".odt"):
        with zipfile.ZipFile(f) as z:
            x = z.read("word/document.xml" if e == ".docx" else "content.xml").decode("utf-8", "ignore")
        x = re.sub(r"</w:p>|</text:p>|<text:line-break/>|<w:br/>", "\n", x)
        return re.sub(r"<[^>]+>", "", x).replace("&apos;", "'").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return open(f, errors="replace").read()

def depuis_conducco():
    from .widgets import dernier_lien
    o = dernier_lien("rundown")
    if not o: return None
    out = []
    for it in o.get("items") or []:
        t = it.get("title") or it.get("name") or ""
        corps = it.get("script") or it.get("text") or it.get("notes") or it.get("description") or ""
        out.append(("■ " + t.upper() if t else "") + ("\n" + corps if corps else ""))
    return "\n\n".join(x for x in out if x.strip())

class Prompteur(Gtk.Application):
    def __init__(self, fichier=None):
        super().__init__(application_id="fr.xiii.prompteur", flags=Gio.ApplicationFlags.NON_UNIQUE); self.fichier = fichier

    def do_activate(self):
        self.cfg = preparer(".scene-prompteur { background: #000; } .compte { font-size: 160px; font-weight: 700; color: #f0b378; }")
        c = self.cfg
        self.vitesse = float(c.get("prompteur_vitesse", 60)); self.taille = int(c.get("prompteur_taille", 64)); self.marge = int(c.get("prompteur_marge", 12))
        self.miroir_h = bool(c.get("prompteur_miroir", False)); self.miroir_v = False; self.pos = 0.0; self.lecture = False; self._t = None; self.compte = 0
        self.win = Gtk.ApplicationWindow(application=self, title="Prompteur XIII", default_width=1100, default_height=720)
        self.pile = Gtk.Stack(); self.win.set_child(self.pile)
        # ---- édition
        ed = boite(True, 10, margin_top=14, margin_bottom=14, margin_start=18, margin_end=18)
        h = boite(False, 8); h.append(ico("scroll-text", 26, "c")); h.append(label("Prompteur", "page-titre", hexpand=True))
        h.append(bouton("Ouvrir…", "folder-open", "fantome", rappel=self.ouvrir)); h.append(bouton("Depuis CONDUCO", "list-video", "fantome", rappel=self.conducco))
        h.append(bouton("Lancer", "play", "pilule", rappel=self.lancer)); ed.append(h)
        self.buf = Gtk.TextBuffer()
        try: self.buf.set_text(lire(self.fichier) if self.fichier else open(TEXTE).read())
        except Exception: self.buf.set_text("Bonsoir et bienvenue.\n\nCollez ou tapez votre texte ici, puis cliquez sur « Lancer ».\n\nEspace : pause · ↑ ↓ ou molette : vitesse · + − : taille · M : miroir · Échap : retour au texte.")
        tv = Gtk.TextView(buffer=self.buf, wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=10, left_margin=12, right_margin=12); tv.add_css_class("champ")
        sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(tv); ed.append(sc)
        rg = boite(False, 14)
        def reglage(nom, mini, maxi, val, cle, pas=1):
            b = boite(False, 6); b.append(label(nom, "petit", "attenue")); sp = Gtk.SpinButton.new_with_range(mini, maxi, pas); sp.set_value(val)
            sp.connect("value-changed", lambda w: (setattr(self, cle, w.get_value()), config.modifier(_histo=False, **{"prompteur_" + cle: w.get_value()}))); b.append(sp); rg.append(b)
        reglage("Vitesse", 5, 400, self.vitesse, "vitesse", 5); reglage("Taille", 24, 200, self.taille, "taille", 2); reglage("Marges %", 0, 40, self.marge, "marge")
        cm = Gtk.CheckButton(label="Miroir (vitre de prompteur)", active=self.miroir_h); cm.connect("toggled", lambda w: setattr(self, "miroir_h", w.get_active())); rg.append(cm)
        self.cb_compte = Gtk.CheckButton(label="Compte à rebours 3 s", active=True); rg.append(self.cb_compte)
        ed.append(rg); ed.append(label("Pédale de prompteur USB : elle envoie Page suivante / Page précédente, reconnues sans réglage.", "petit", "attenue"))
        self.pile.add_named(ed, "edition")
        # ---- scène
        self.da = Gtk.DrawingArea(hexpand=True, vexpand=True); self.da.add_css_class("scene-prompteur"); self.da.set_draw_func(self.dessin)
        sc2 = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        sc2.connect("scroll", lambda c_, dx, dy: (self.regler_vitesse(-dy * 10), True)[1]); self.da.add_controller(sc2)
        g = Gtk.GestureClick(); g.connect("pressed", lambda *_: self.pause()); self.da.add_controller(g)
        self.pile.add_named(self.da, "scene")
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.touche); self.win.add_controller(k)
        self.buf.connect("changed", lambda *_: self.sauver())
        self.win.present()

    def sauver(self):
        try:
            os.makedirs(os.path.dirname(TEXTE), exist_ok=True)
            open(TEXTE, "w").write(self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), False))
        except OSError: pass

    def ouvrir(self):
        d = Gtk.FileDialog(title="Ouvrir un texte")
        def fini(dl, r):
            try: self.buf.set_text(lire(dl.open_finish(r).get_path()))
            except Exception as e: pass
        d.open(self.win, None, fini)

    def conducco(self):
        t = depuis_conducco()
        self.buf.set_text(t if t else "Aucun conducteur CONDUCO trouvé : exportez-le depuis la Suite XIII (.xiii.json).")

    # ---------------------------------------------------------------- lecture
    def lancer(self):
        self.texte = self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), False)
        self.pos = 0.0; self.pile.set_visible_child_name("scene"); self.win.fullscreen()
        self.compte = 3 if self.cb_compte.get_active() else 0; self.lecture = self.compte == 0; self._t = time.time()
        if self.compte: GLib.timeout_add(1000, self._decompte)
        if not getattr(self, "_src", 0): self._src = GLib.timeout_add(16, self._tic)

    def _decompte(self):
        self.compte -= 1
        if self.compte <= 0: self.lecture = True; self._t = time.time(); return False
        return True

    def _tic(self):
        n = time.time()
        if self.lecture: self.pos += self.vitesse * (n - (self._t or n))
        self._t = n; self.da.queue_draw(); return True

    def pause(self): self.lecture = not self.lecture; self._t = time.time()
    def regler_vitesse(self, d): self.vitesse = max(0, min(600, self.vitesse + d))

    def retour(self):
        self.win.unfullscreen(); self.pile.set_visible_child_name("edition")
        if getattr(self, "_src", 0): GLib.source_remove(self._src); self._src = 0

    def touche(self, c, kv, code, st):
        if self.pile.get_visible_child_name() != "scene": return False
        if kv == Gdk.KEY_Escape: self.retour()
        elif kv == Gdk.KEY_space: self.pause()
        elif kv in (Gdk.KEY_Up, Gdk.KEY_Page_Up): self.regler_vitesse(-10) if kv == Gdk.KEY_Up else setattr(self, "pos", max(0, self.pos - self.da.get_height() * .5))
        elif kv in (Gdk.KEY_Down, Gdk.KEY_Page_Down): self.regler_vitesse(10) if kv == Gdk.KEY_Down else setattr(self, "pos", self.pos + self.da.get_height() * .5)
        elif kv in (Gdk.KEY_plus, Gdk.KEY_KP_Add, Gdk.KEY_equal): self.taille = min(220, self.taille + 4)
        elif kv in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract): self.taille = max(20, self.taille - 4)
        elif kv in (Gdk.KEY_m, Gdk.KEY_M): self.miroir_h = not self.miroir_h
        elif kv in (Gdk.KEY_v, Gdk.KEY_V): self.miroir_v = not self.miroir_v
        elif kv == Gdk.KEY_Home: self.pos = 0
        else: return False
        return True

    def dessin(self, a, cr, W, H):
        cr.set_source_rgb(0, 0, 0); cr.paint()
        cr.save()
        if self.miroir_h: cr.translate(W, 0); cr.scale(-1, 1)
        if self.miroir_v: cr.translate(0, H); cr.scale(1, -1)
        lay = PangoCairo.create_layout(cr); mg = W * self.marge / 100
        lay.set_width(int((W - 2 * mg) * Pango.SCALE)); lay.set_wrap(Pango.WrapMode.WORD_CHAR)
        lay.set_font_description(Pango.FontDescription.from_string("IBM Plex Sans Bold %d" % self.taille))
        lay.set_spacing(int(self.taille * .25 * Pango.SCALE)); lay.set_text(getattr(self, "texte", ""), -1)
        _, h = lay.get_pixel_size()
        y = H * .35 - self.pos
        if y + h < 0: self.lecture = False
        cr.set_source_rgb(1, 1, 1); cr.move_to(mg, y); PangoCairo.show_layout(cr, lay)
        cr.restore()
        # ligne de lecture et repères (jamais en miroir : ils servent à l'opérateur)
        cr.set_source_rgba(0.94, 0.70, 0.47, .55); cr.rectangle(0, H * .35 - 2, 18, 4); cr.fill(); cr.rectangle(W - 18, H * .35 - 2, 18, 4); cr.fill()
        if self.compte > 0:
            cr.set_source_rgba(0, 0, 0, .6); cr.paint()
            cr.select_font_face("IBM Plex Sans", 0, 1); cr.set_font_size(H * .3); cr.set_source_rgb(0.94, 0.70, 0.47)
            t = str(self.compte); e = cr.text_extents(t); cr.move_to(W / 2 - e.width / 2 - e.x_bearing, H / 2 - e.height / 2 - e.y_bearing); cr.show_text(t)
        cr.select_font_face("IBM Plex Mono"); cr.set_font_size(13); cr.set_source_rgba(1, 1, 1, .35)
        cr.move_to(12, H - 12); cr.show_text("%s · vitesse %d · Échap : texte" % ("⏸ pause" if not self.lecture else "▶", self.vitesse))

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("-")]
    sys.exit(Prompteur(a[0] if a else None).run(sys.argv[:1]))
