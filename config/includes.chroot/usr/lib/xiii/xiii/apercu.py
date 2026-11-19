# OS XIII — Aperçu rapide (comme « Coup d'œil » sur Mac / « Peek » sous Windows) : Espace sur un fichier dans
# Fichiers, ou bouton œil dans les résultats de recherche. Image, vidéo, son, PDF, texte, fichiers .xiii.json de la suite.
# Échap ou Espace pour fermer, Entrée pour ouvrir avec l'application par défaut, ← / → pour les fichiers voisins.
# Application développée par Matthieu Lamotte.
import os, sys, json, subprocess, tempfile, mimetypes
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, theme, systeme as S
from .ui import *

TEXTE = (".txt", ".md", ".csv", ".tsv", ".log", ".json", ".xml", ".srt", ".vtt", ".edl", ".fcpxml", ".ale", ".py", ".sh", ".ini", ".conf", ".yml", ".yaml", ".html", ".css", ".js", ".mhl")

def nature(f):
    m = mimetypes.guess_type(f)[0] or ""
    b = f.lower()
    if b.endswith(".xiii.json"): return "xiii"
    if m.startswith("image/"): return "image"
    if m.startswith("video/") or b.endswith((".mxf", ".mts", ".braw", ".r3d")): return "video"
    if m.startswith("audio/"): return "audio"
    if b.endswith(".pdf"): return "pdf"
    if b.endswith(TEXTE) or m.startswith("text/"): return "texte"
    return "autre"

class Apercu(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.apercu", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.win = None; self.fichiers = []; self.i = 0; self.media = None

    def do_command_line(self, cl):
        a = [x for x in cl.get_arguments()[1:] if x]
        if not a: return 1
        f = Gio.File.new_for_commandline_arg(a[0]).get_path()
        if self.win and self.win.is_visible() and self.fichiers and self.fichiers[self.i] == f:
            self.win.close(); return 0                       # Espace une 2ᵉ fois : on referme
        d = os.path.dirname(f)
        try: self.fichiers = sorted([os.path.join(d, x) for x in os.listdir(d) if not x.startswith(".") and os.path.isfile(os.path.join(d, x))], key=str.lower)
        except OSError: self.fichiers = [f]
        if f not in self.fichiers: self.fichiers.insert(0, f)
        self.i = self.fichiers.index(f)
        self.construire(); self.montrer(); self.win.present()
        return 0

    def construire(self):
        if self.win: return
        cfg = config.charger(); couleurs(cfg)
        css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(cfg) + """
            .apercu-fond { background: alpha(#000, .92); }
            .apercu-texte { font-family: "IBM Plex Mono", monospace; font-size: 10.5pt; }""")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.win = Gtk.ApplicationWindow(application=self, title="Aperçu"); self.win.set_default_size(1000, 700)
        v = boite(True, 0)
        h = boite(False, 10, "entete", margin_start=12, margin_end=12, margin_top=8, margin_bottom=8)
        self.ic = Gtk.Image(); self.ic.set_pixel_size(20); h.append(self.ic)
        col = boite(True, 0, hexpand=True); self.titre = label("", "gras", ellipsize=True); self.info = label("", "petit", "attenue", ellipsize=True)
        col.append(self.titre); col.append(self.info); h.append(col)
        h.append(bouton(None, "chevron-left", "plat", tip="Fichier précédent (←)", rappel=lambda: self.aller(-1)))
        h.append(bouton(None, "chevron-right", "plat", tip="Fichier suivant (→)", rappel=lambda: self.aller(1)))
        h.append(bouton("Ouvrir", "external-link", "plein", tip="Ouvrir avec l'application par défaut (Entrée)", rappel=self.ouvrir))
        h.append(bouton(None, "x", "plat", tip="Fermer (Échap)", rappel=lambda: self.win.close()))
        v.append(h)
        self.zone = Gtk.Box(vexpand=True, hexpand=True); self.zone.add_css_class("apercu-fond"); v.append(self.zone)
        self.win.set_child(v)
        k = Gtk.EventControllerKey(); k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        def touche(c, kv, code, st):
            if kv in (Gdk.KEY_Escape, Gdk.KEY_space): self.win.close(); return True
            if kv == Gdk.KEY_Return: self.ouvrir(); return True
            if kv in (Gdk.KEY_Left, Gdk.KEY_Up): self.aller(-1); return True
            if kv in (Gdk.KEY_Right, Gdk.KEY_Down): self.aller(1); return True
            return False
        k.connect("key-pressed", touche); self.win.add_controller(k)
        self.win.connect("close-request", lambda *_: (self.stop_media(), self.win.set_visible(False), self.quit(), True)[3])

    def stop_media(self):
        if self.media:
            try: self.media.set_playing(False)
            except Exception: pass
            self.media = None

    def aller(self, d):
        if not self.fichiers: return
        self.i = (self.i + d) % len(self.fichiers); self.montrer()

    def ouvrir(self):
        S.detacher(["xdg-open", self.fichiers[self.i]]); self.win.close()

    def montrer(self):
        self.stop_media(); vider(self.zone)
        f = self.fichiers[self.i]; n = nature(f)
        try: taille = S.humain(os.path.getsize(f))
        except OSError: taille = "?"
        self.titre.set_text(os.path.basename(f)); self.info.set_text("%s · %s · %d / %d" % (taille, os.path.dirname(f), self.i + 1, len(self.fichiers)))
        try: self.ic.set_from_gicon(Gio.content_type_get_icon(Gio.content_type_guess(f, None)[0]))
        except Exception: pass
        w = getattr(self, "v_" + n)(f)
        w.set_hexpand(True); w.set_vexpand(True); self.zone.append(w)

    def v_image(self, f):
        p = Gtk.Picture.new_for_filename(f); p.set_content_fit(Gtk.ContentFit.CONTAIN); return p

    def v_video(self, f):
        m = Gtk.MediaFile.new_for_filename(f); m.set_loop(True); self.media = m
        vid = Gtk.Video.new(); vid.set_media_stream(m); vid.set_autoplay(True); return vid

    def v_audio(self, f):
        v = boite(True, 16, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        v.append(ico("music", 96, "c")); m = Gtk.MediaFile.new_for_filename(f); self.media = m
        c = Gtk.MediaControls.new(m); c.set_size_request(480, -1); v.append(c); m.play(); return v

    def v_pdf(self, f):
        sw = Gtk.ScrolledWindow(); v = boite(True, 16, halign=Gtk.Align.CENTER, margin_top=16, margin_bottom=16); sw.set_child(v)
        d = tempfile.mkdtemp(prefix="xiii-apercu-")
        def rendre():
            subprocess.run(["pdftoppm", "-png", "-r", "70", "-l", "8", f, os.path.join(d, "p")], capture_output=True)
            GLib.idle_add(fin)
        def fin():
            pages = sorted(x for x in os.listdir(d) if x.endswith(".png"))
            if not pages: v.append(label("Impossible d'afficher ce PDF.", "attenue"))
            for x in pages:
                p = Gtk.Picture.new_for_filename(os.path.join(d, x)); p.set_can_shrink(False); v.append(p)
            if len(pages) == 8: v.append(label("Aperçu des 8 premières pages — Entrée pour ouvrir le document complet.", "attenue", "petit"))
            return False
        import threading; threading.Thread(target=rendre, daemon=True).start()
        return sw

    def v_texte(self, f):
        sw = Gtk.ScrolledWindow(); tv = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=16, top_margin=12, right_margin=16)
        tv.add_css_class("apercu-texte")
        try:
            with open(f, "rb") as fh: t = fh.read(400_000).decode("utf-8", "replace")
            if f.lower().endswith(".json"):
                try: t = json.dumps(json.loads(t), ensure_ascii=False, indent=2)
                except Exception: pass
        except OSError as e:
            t = str(e)
        tv.get_buffer().set_text(t); sw.set_child(tv); return sw

    def v_xiii(self, f):
        try: o = json.load(open(f))
        except Exception: return self.v_texte(f)
        v = boite(True, 12, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER, margin_start=40, margin_end=40)
        v.append(label("SUITE XIII", "titre-astoria", "accent", xalign=0.5))
        kind = o.get("kind") or o.get("format") or "fichier"
        v.append(label("Fichier « %s »%s" % (kind, " — exporté par " + o["source"] if o.get("source") else ""), "page-titre", xalign=0.5, wrap=True))
        data = o.get("data") if isinstance(o.get("data"), dict) else o
        for k, val in list(data.items())[:12]:
            if isinstance(val, (str, int, float)) and str(val).strip():
                r = boite(False, 10); r.append(label(str(k), "attenue", "petit")); r.append(label(str(val)[:120], "petit", wrap=True)); v.append(r)
            elif isinstance(val, list):
                r = boite(False, 10); r.append(label(str(k), "attenue", "petit")); r.append(label("%d élément(s)" % len(val), "petit")); v.append(r)
        v.append(label("Entrée : ouvrir dans l'outil de la suite", "attenue", "petit", xalign=0.5))
        return v

    def v_autre(self, f):
        v = boite(True, 12, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        im = Gtk.Image(); im.set_pixel_size(128)
        try: im.set_from_gicon(Gio.content_type_get_icon(Gio.content_type_guess(f, None)[0]))
        except Exception: im.set_from_icon_name("text-x-generic")
        v.append(im); v.append(label("Pas d'aperçu pour ce type de fichier.", "attenue")); v.append(label("Entrée pour l'ouvrir.", "attenue", "petit"))
        return v

def main():
    sys.exit(Apercu().run(sys.argv))
