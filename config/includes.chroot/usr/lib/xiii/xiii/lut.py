# OS XIII — LUT XIII : bibliothèque de LUT (.cube, .3dl), aperçu avant / après sur une image ou une image de vos rushes,
# installation dans DaVinci Resolve, chemin prêt pour OBS, et « cuisson » d'une LUT dans une vidéo (FFmpeg).
# Application développée par Matthieu Lamotte.
import os, sys, shutil, subprocess, hashlib, glob
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S, medias
from .ui import *
from .appli import preparer

BIB = os.path.join(GLib.get_user_data_dir(), "xiii", "LUT")
CACHE = os.path.join(GLib.get_user_cache_dir(), "xiii", "lut")
RESOLVE = [os.path.expanduser("~/.local/share/DaVinciResolve/LUT/XIII"), "/opt/resolve/LUT/XIII"]

def luts():
    os.makedirs(BIB, exist_ok=True)
    return sorted(glob.glob(BIB + "/**/*.cube", recursive=True) + glob.glob(BIB + "/**/*.3dl", recursive=True), key=lambda p: os.path.basename(p).lower())

def apercu(ref, lut, largeur=480):
    """Image de référence passée dans la LUT (mise en cache)."""
    os.makedirs(CACHE, exist_ok=True)
    k = hashlib.md5(("%s|%s|%s|%d" % (ref, os.path.getmtime(ref), lut, largeur)).encode()).hexdigest()
    f = os.path.join(CACHE, k + ".png")
    if os.path.exists(f): return f
    src = ["-ss", "2", "-i", ref] if medias.ext(ref) in medias.VIDEO else ["-i", ref]
    vf = "scale=%d:-2" % largeur + ((",lut3d=file='%s'" % lut.replace("'", "\\'")) if lut else "")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y"] + src + ["-frames:v", "1", "-vf", vf, f], capture_output=True, timeout=40)
    return f if r.returncode == 0 and os.path.exists(f) else None

class LUT(Gtk.Application):
    def __init__(self, fichiers=None):
        super().__init__(application_id="fr.xiii.lut", flags=Gio.ApplicationFlags.HANDLES_OPEN); self.fichiers = fichiers or []

    def do_open(self, files, n, hint):
        self.importer([f.get_path() for f in files]); self.activate()

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        self.cfg = preparer(".carte-lut { padding: 6px; border-radius: 10px; } .carte-lut.choisie { background: alpha(@accent_bg_color, .25); }")
        self.ref = self.cfg.get("lut_reference") or self.reference_defaut(); self.choisie = None
        self.win = Gtk.ApplicationWindow(application=self, title="LUT XIII", default_width=1240, default_height=780)
        v = boite(True, 10, margin_top=14, margin_bottom=14, margin_start=18, margin_end=18)
        h = boite(False, 8); h.append(ico("swatch-book", 26, "c")); h.append(label("LUT XIII", "page-titre", hexpand=True))
        h.append(bouton("Importer des LUT…", "file-plus", "pilule", rappel=self.choisir_luts))
        h.append(bouton("Image de référence…", "image", "fantome", rappel=self.choisir_ref))
        h.append(bouton(None, "folder-open", "plat", tip="Ouvrir le dossier des LUT", rappel=lambda: S.detacher(["xiii-fichiers", BIB]))); v.append(h)
        corps = boite(False, 14, vexpand=True)
        self.grille = Gtk.FlowBox(max_children_per_line=4, min_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, valign=Gtk.Align.START)
        sc = Gtk.ScrolledWindow(hexpand=True); sc.set_child(self.grille); corps.append(sc)
        d = boite(True, 8); d.set_size_request(460, -1)
        d.append(label("Avant", "petit", "attenue")); self.p_avant = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN); self.p_avant.set_size_request(440, 248); d.append(self.p_avant)
        d.append(label("Après", "petit", "attenue")); self.p_apres = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN); self.p_apres.set_size_request(440, 248); d.append(self.p_apres)
        self.l_nom = label("Choisissez une LUT", "gras", wrap=True); d.append(self.l_nom)
        self.actions = boite(True, 6); d.append(self.actions); corps.append(d)
        v.append(corps)
        v.append(label("Glissez des fichiers .cube ici, ou ouvrez-les depuis Fichiers. L'image de référence peut être une photo ou un rush (une image est prise à 2 s).", "petit", "attenue", wrap=True))
        dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY); dt.connect("drop", lambda t, val, x, y: (self.importer([f.get_path() for f in val.get_files()]), True)[1]); v.add_controller(dt)
        self.win.set_child(v); self.win.present()
        if self.fichiers: self.importer(self.fichiers)
        self.remplir()

    def reference_defaut(self):
        for p in ("/usr/share/xiii/wallpapers/xiii-clair.png", "/usr/share/xiii/wallpapers/xiii-sombre.png"):
            if os.path.exists(p): return p
        return None

    def importer(self, L):
        os.makedirs(BIB, exist_ok=True); n = 0
        for p in L:
            if p and p.lower().endswith((".cube", ".3dl")): shutil.copy(p, BIB); n += 1
        if n and getattr(self, "win", None): self.remplir()

    def choisir_luts(self):
        d = Gtk.FileDialog(title="Importer des LUT (.cube, .3dl)")
        ff = Gtk.FileFilter(); ff.set_name("LUT"); ff.add_suffix("cube"); ff.add_suffix("3dl"); st = Gio.ListStore.new(Gtk.FileFilter); st.append(ff); d.set_filters(st)
        def fini(dl, r):
            try: self.importer([f.get_path() for f in dl.open_multiple_finish(r)])
            except GLib.Error: pass
        d.open_multiple(self.win, None, fini)

    def choisir_ref(self):
        d = Gtk.FileDialog(title="Image ou rush de référence")
        def fini(dl, r):
            try: self.ref = dl.open_finish(r).get_path()
            except GLib.Error: return
            config.modifier(_histo=False, lut_reference=self.ref); self.remplir()
        d.open(self.win, None, fini)

    def remplir(self):
        vider(self.grille); L = luts()
        if not L:
            self.grille.append(label("Aucune LUT pour l'instant. Importez vos fichiers .cube (LUT de caméra Log → Rec.709, looks…).", "attenue", wrap=True)); return
        if self.ref: S.en_fond(apercu, lambda f: self.p_avant.set_filename(f) if isinstance(f, str) else None, self.ref, None, 440)
        for p in L:
            b = Gtk.Button(); b.add_css_class("carte-lut"); b.add_css_class("plat")
            c = boite(True, 4); pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER); pic.set_size_request(220, 124); c.append(pic)
            c.append(label(os.path.splitext(os.path.basename(p))[0], "petit", ellipsize=True, xalign=0.5)); b.set_child(c)
            b.connect("clicked", lambda _b, p=p: self.choisir(p)); self.grille.append(b)
            if self.ref: S.en_fond(apercu, lambda f, pic=pic: pic.set_filename(f) if isinstance(f, str) else None, self.ref, p, 240)

    def choisir(self, p):
        self.choisie = p; self.l_nom.set_text(os.path.basename(p))
        if self.ref: S.en_fond(apercu, lambda f: self.p_apres.set_filename(f) if isinstance(f, str) else None, self.ref, p, 440)
        vider(self.actions)
        self.actions.append(bouton("Installer dans DaVinci Resolve", "film", "pilule", rappel=lambda: self.vers_resolve(p)))
        self.actions.append(bouton("Copier le chemin (OBS : filtre « Appliquer une LUT »)", "copy", "fantome", rappel=lambda: Gdk.Display.get_default().get_clipboard().set_text(p)))
        self.actions.append(bouton("Appliquer à une vidéo…", "clapperboard", "fantome", rappel=lambda: self.cuire(p)))
        self.actions.append(bouton("Retirer de la bibliothèque", "trash-2", "plat", rappel=lambda: (os.remove(p), self.remplir(), vider(self.actions))))

    def vers_resolve(self, p):
        for d in RESOLVE:
            try:
                os.makedirs(d, exist_ok=True); shutil.copy(p, d)
                S.detacher(["notify-send", "-a", "LUT XIII", "-i", "xiii-lut", "LUT installée dans DaVinci Resolve", "%s → %s (Resolve : Project Settings › Color Management › Update Lists)" % (os.path.basename(p), d)])
                return
            except OSError: continue

    def cuire(self, lut):
        d = Gtk.FileDialog(title="Vidéo à étalonner avec « %s »" % os.path.basename(lut))
        def fini(dl, r):
            try: v = dl.open_finish(r).get_path()
            except GLib.Error: return
            out = os.path.splitext(v)[0] + "_" + os.path.splitext(os.path.basename(lut))[0] + ".mov"
            self.l_nom.set_text("Application de la LUT… (%s)" % os.path.basename(out))
            S.en_fond(lambda: subprocess.run(["nice", "-n", "10", "ffmpeg", "-v", "error", "-y", "-i", v, "-vf", "lut3d=file='%s'" % lut.replace("'", "\\'"),
                                              "-c:v", "prores_ks", "-profile:v", "2", "-c:a", "copy", out]).returncode,
                      lambda rc: (self.l_nom.set_text(("Terminé : " if rc == 0 else "Échec : ") + os.path.basename(out)),
                                  S.detacher(["notify-send", "-a", "LUT XIII", "-i", "xiii-lut", "Vidéo étalonnée", out]) if rc == 0 else None))
        d.open(self.win, None, fini)

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("-")]
    sys.exit(LUT().run(sys.argv[:1] + a))
