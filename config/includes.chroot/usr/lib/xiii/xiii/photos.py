# OS XIII — XIII Photos : visionneuse rapide. Navigation instantanée (images voisines préchargées), RAW (aperçu intégré
# au fichier : Canon, Nikon, Sony, Fujifilm, DNG…), notation 0 à 5 étoiles (fichier .xmp lu par darktable, Lightroom,
# Bridge, Capture One), comparaison côte à côte, infos de prise de vue, bande de miniatures.
# ← → : photo précédente / suivante · 0-5 : note · C : comparer (↑ ↓ : photo de droite) · Z : 100 % · I : infos · F : plein écran · Suppr : corbeille
# Application développée par Matthieu Lamotte.
import os, sys, json, subprocess, threading, hashlib, collections
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf
from .ui import *
from .appli import preparer

IMAGES = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif")
RAW = (".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".raf", ".dng", ".orf", ".rw2", ".pef", ".srw", ".x3f", ".3fr", ".iiq", ".rwl")
CACHE = os.path.expanduser("~/.cache/xiii/photos")


def est_image(p): return p.lower().endswith(IMAGES + RAW)


def source_affichable(p):
    """Fichier lisible par GdkPixbuf : la photo, ou l'aperçu JPEG intégré au RAW (extrait une fois, mis en cache)."""
    if not p.lower().endswith(RAW): return p
    os.makedirs(CACHE, exist_ok=True)
    c = os.path.join(CACHE, hashlib.md5(("%s:%s" % (p, os.path.getmtime(p))).encode()).hexdigest() + ".jpg")
    if not os.path.exists(c):
        for tag in ("-JpgFromRaw", "-PreviewImage", "-OtherImage", "-ThumbnailImage"):
            d = subprocess.run(["exiftool", "-b", tag, p], capture_output=True, timeout=30).stdout
            if len(d) > 20000: open(c, "wb").write(d); break
        else:
            return None
        # orientation de l'appareil appliquée à l'aperçu
        o = subprocess.run(["exiftool", "-n", "-s3", "-Orientation", p], capture_output=True, text=True).stdout.strip()
        if o: subprocess.run(["exiftool", "-overwrite_original", "-n", "-Orientation=" + o, c], capture_output=True)
    return c


def charger(p, l, h):
    s = source_affichable(p)
    if not s: raise OSError("aperçu RAW introuvable")
    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(s, l, h, True)
    pb = pb.apply_embedded_orientation() or pb
    return Gdk.Texture.new_for_pixbuf(pb)


def xmp(p): return os.path.splitext(p)[0] + ".xmp"


def lire_note(p):
    try: return int(os.getxattr(p, "user.xiii.note"))
    except (OSError, ValueError): pass
    try:
        for f in (xmp(p), p):
            if os.path.exists(f):
                o = subprocess.run(["exiftool", "-s3", "-XMP:Rating", f], capture_output=True, text=True, timeout=10).stdout.strip()
                if o: return int(float(o))
    except Exception: pass
    return 0


def ecrire_note(p, n):
    try: os.setxattr(p, "user.xiii.note", str(n).encode())
    except OSError: pass
    f = xmp(p)
    if os.path.exists(f): subprocess.run(["exiftool", "-overwrite_original", "-XMP:Rating=%d" % n, f], capture_output=True)
    else: subprocess.run(["exiftool", "-XMP:Rating=%d" % n, "-o", f, p], capture_output=True)


def infos(p):
    try:
        d = json.loads(subprocess.run(["exiftool", "-j", "-Model", "-LensModel", "-LensID", "-ISO", "-FNumber", "-ExposureTime", "-FocalLength", "-DateTimeOriginal",
                                       "-ImageSize", "-FileSize", "-Make", p], capture_output=True, text=True, timeout=15).stdout)[0]
    except Exception:
        return []
    mk, md = d.get("Make") or "", d.get("Model") or ""
    L = [("Appareil", md if md.lower().startswith(mk.split(" ")[0].lower()) else (mk + " " + md).strip()),
         ("Objectif", d.get("LensModel") or d.get("LensID")), ("Réglages", " · ".join(x for x in (("ISO %s" % d["ISO"]) if d.get("ISO") else "", ("f/%s" % d["FNumber"]) if d.get("FNumber") else "",
         ("%s s" % d["ExposureTime"]) if d.get("ExposureTime") else "", d.get("FocalLength") or "") if x)), ("Prise le", (d.get("DateTimeOriginal") or "").replace(":", "/", 2)),
         ("Taille", " · ".join(x for x in (d.get("ImageSize"), d.get("FileSize")) if x))]
    return [(k, str(v)) for k, v in L if v]


class Vue:
    """Une photo affichée (ajustée à la fenêtre, ou à 100 % avec défilement)."""
    def __init__(self):
        self.pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True, hexpand=True, vexpand=True)
        self.sc = Gtk.ScrolledWindow(hexpand=True, vexpand=True); self.sc.set_child(self.pic); self.sc.add_css_class("ph-fond")
        self.etoiles = label("", "ph-etoiles"); self.etoiles.set_halign(Gtk.Align.CENTER); self.etoiles.set_valign(Gtk.Align.END); self.etoiles.set_margin_bottom(14)
        self.nom = label("", "ph-nom"); self.nom.set_halign(Gtk.Align.START); self.nom.set_valign(Gtk.Align.START); self.nom.set_margin_start(12); self.nom.set_margin_top(10)
        self.w = Gtk.Overlay(); self.w.set_child(self.sc); self.w.add_overlay(self.etoiles); self.w.add_overlay(self.nom)
        self.reel = False

    def montrer(self, tex, p, note):
        self.pic.set_paintable(tex); self.nom.set_text(os.path.basename(p)); self.afficher_note(note)

    def afficher_note(self, n): self.etoiles.set_text("★" * n + "☆" * (5 - n) if n else "")

    def zoom(self, reel):
        self.reel = reel
        self.pic.set_can_shrink(not reel); self.pic.set_content_fit(Gtk.ContentFit.SCALE_DOWN if reel else Gtk.ContentFit.CONTAIN)


class Photos(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.photos", flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE)
        self.L = []; self.i = 0; self.cache = collections.OrderedDict(); self.comparer = False; self.j = None; self.notes = {}

    def do_open(self, files, n, hint):
        p = files[0].get_path(); self.depart(p)

    def do_activate(self):
        self.depart(None)

    def depart(self, p):
        if p and os.path.isdir(p): d, p = p, None
        elif p: d = os.path.dirname(p)
        else:
            d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or os.path.expanduser("~")
        try: self.L = sorted((os.path.join(d, x) for x in os.listdir(d) if est_image(x) and not x.startswith(".")), key=lambda x: x.lower())
        except OSError: self.L = []
        self.i = self.L.index(p) if p in self.L else 0
        self.fenetre(); self.afficher()

    def fenetre(self):
        preparer(".ph-fond { background: #0c0b0a; } .ph-etoiles { font-size: 26px; color: #f0b378; text-shadow: 0 1px 4px black; }"
                 " .ph-nom { background: alpha(black, .55); color: white; border-radius: 6px; padding: 3px 8px; font-weight: 600; }"
                 " .ph-bande { background: #141210; padding: 6px; } .ph-mini { padding: 2px; border-radius: 6px; border: 2px solid transparent; background: transparent; }"
                 " .ph-mini.actif { border-color: #f0b378; } .ph-infos { background: alpha(#1d1b19, .92); padding: 14px; border-radius: 12px; }")
        w = Gtk.ApplicationWindow(application=self, title="XIII Photos", default_width=1400, default_height=900); self.win = w
        v = boite(True, 0)
        barre = boite(False, 6, margin_start=10, margin_end=10, margin_top=6, margin_bottom=6)
        self.titre = label("", "gras", hexpand=True, ellipsize=True); barre.append(self.titre)
        for ic, tip, f in (("chevron-left", "Précédente (←)", lambda: self.aller(-1)), ("chevron-right", "Suivante (→)", lambda: self.aller(1)),
                           ("columns-2", "Comparer côte à côte (C)", self.basculer_comparer), ("scan", "100 % / ajuster (Z ou double-clic)", self.basculer_zoom),
                           ("info", "Infos de prise de vue (I)", self.basculer_infos), ("trash-2", "Mettre à la corbeille (Suppr)", self.supprimer),
                           ("external-link", "Ouvrir avec… (darktable, GIMP…)", self.ouvrir_avec), ("maximize", "Plein écran (F)", self.plein_ecran)):
            barre.append(bouton(None, ic, "plat", tip=tip, rappel=f))
        v.append(barre)
        self.a = Vue(); self.b = Vue()
        self.zone = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True, vexpand=True); self.zone.set_start_child(self.a.w); self.zone.set_resize_start_child(True)
        ov = Gtk.Overlay(); ov.set_child(self.zone)
        self.p_infos = boite(True, 4, "ph-infos", halign=Gtk.Align.END, valign=Gtk.Align.START, margin_top=12, margin_end=12); self.p_infos.set_visible(False); ov.add_overlay(self.p_infos)
        v.append(ov)
        self.bande = boite(False, 4, "ph-bande"); bs = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.NEVER); bs.set_child(self.bande); bs.set_size_request(-1, 96); self.bs = bs
        v.append(bs)
        w.set_child(v)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.touche); w.add_controller(k)
        g = Gtk.GestureClick(); g.connect("pressed", lambda g_, n, x, y: self.basculer_zoom() if n == 2 else None); self.a.w.add_controller(g)
        w.present()
        self.construire_bande()

    def texture(self, p):
        if p in self.cache: self.cache.move_to_end(p); return self.cache[p]
        return None

    def precharger(self, p):
        if p in self.cache or not p: return
        def fond():
            try: t = charger(p, 2560, 1600)
            except Exception: t = None
            GLib.idle_add(self.ranger, p, t)
        threading.Thread(target=fond, daemon=True).start()

    def ranger(self, p, t):
        if t is None: return False
        self.cache[p] = t
        while len(self.cache) > 12: self.cache.popitem(last=False)
        if self.L and self.L[self.i] == p: self.a.montrer(t, p, self.note(p))
        if self.comparer and self.j is not None and self.L[self.j] == p: self.b.montrer(t, p, self.note(p))
        return False

    def note(self, p):
        if p not in self.notes:
            self.notes[p] = 0
            threading.Thread(target=lambda: (self.notes.__setitem__(p, lire_note(p)), GLib.idle_add(self.maj_notes)), daemon=True).start()
        return self.notes[p]

    def maj_notes(self):
        if self.L: self.a.afficher_note(self.notes.get(self.L[self.i], 0))
        if self.comparer and self.j is not None: self.b.afficher_note(self.notes.get(self.L[self.j], 0))
        return False

    def afficher(self):
        if not self.L:
            self.titre.set_text("Aucune photo dans ce dossier"); return
        p = self.L[self.i]
        self.titre.set_text("%s   ·   %d / %d" % (os.path.basename(p), self.i + 1, len(self.L)))
        t = self.texture(p)
        if t: self.a.montrer(t, p, self.note(p))
        else: self.a.pic.set_paintable(None); self.a.nom.set_text(os.path.basename(p) + " — chargement…"); self.precharger(p)
        for d in (1, -1, 2):    # navigation instantanée : les voisines sont déjà prêtes
            k = self.i + d
            if 0 <= k < len(self.L): self.precharger(self.L[k])
        if self.comparer:
            if self.j is None or self.j == self.i: self.j = min(len(self.L) - 1, self.i + 1)
            q = self.L[self.j]; t2 = self.texture(q)
            if t2: self.b.montrer(t2, q, self.note(q))
            else: self.precharger(q)
        if self.p_infos.get_visible(): self.remplir_infos()
        self.marquer_bande()

    def aller(self, d):
        if not self.L: return
        self.i = max(0, min(len(self.L) - 1, self.i + d)); self.afficher()

    def touche(self, c, kv, code, st):
        ch = Gdk.keyval_to_unicode(kv)
        if kv in (Gdk.KEY_Right, Gdk.KEY_space, Gdk.KEY_Page_Down): self.aller(1)
        elif kv in (Gdk.KEY_Left, Gdk.KEY_BackSpace, Gdk.KEY_Page_Up): self.aller(-1)
        elif kv == Gdk.KEY_Home: self.i = 0; self.afficher()
        elif kv == Gdk.KEY_End: self.i = len(self.L) - 1; self.afficher()
        elif ch and chr(ch) in "012345" and not (st & Gdk.ModifierType.CONTROL_MASK): self.noter(int(chr(ch)))
        elif kv in (Gdk.KEY_c, Gdk.KEY_C): self.basculer_comparer()
        elif kv in (Gdk.KEY_i, Gdk.KEY_I): self.basculer_infos()
        elif kv in (Gdk.KEY_f, Gdk.KEY_F, Gdk.KEY_F11): self.plein_ecran()
        elif kv == Gdk.KEY_Delete: self.supprimer()
        elif kv in (Gdk.KEY_z, Gdk.KEY_Z): self.basculer_zoom()
        elif kv == Gdk.KEY_Escape:
            if self.win.is_fullscreen(): self.win.unfullscreen()
            else: self.win.close()
        elif kv in (Gdk.KEY_Up, Gdk.KEY_Down) and self.comparer:
            self.j = max(0, min(len(self.L) - 1, (self.j or 0) + (1 if kv == Gdk.KEY_Down else -1))); self.afficher()
        else: return False
        return True

    def noter(self, n):
        if not self.L: return
        p = self.L[self.i]; self.notes[p] = n; self.a.afficher_note(n)
        threading.Thread(target=ecrire_note, args=(p, n), daemon=True).start()
        self.marquer_bande()

    def basculer_comparer(self):
        self.comparer = not self.comparer
        if self.comparer:
            self.zone.set_end_child(self.b.w); self.j = min(len(self.L) - 1, self.i + 1)
            GLib.idle_add(lambda: (self.zone.set_position(self.zone.get_width() // 2), False)[1])
        else:
            self.zone.set_end_child(None)
        self.afficher()

    def basculer_zoom(self):
        for v_ in (self.a, self.b): v_.zoom(not v_.reel)
        if self.a.reel and self.L:     # 100 % : on recharge en pleine définition
            p = self.L[self.i]
            def fond():
                try: t = charger(p, 12000, 12000)
                except Exception: return
                GLib.idle_add(lambda: (self.a.pic.set_paintable(t), False)[1])
            threading.Thread(target=fond, daemon=True).start()

    def basculer_infos(self):
        self.p_infos.set_visible(not self.p_infos.get_visible())
        if self.p_infos.get_visible(): self.remplir_infos()

    def remplir_infos(self):
        vider(self.p_infos); p = self.L[self.i] if self.L else None
        if not p: return
        self.p_infos.append(label("Prise de vue", "gras"))
        S_ = self
        def fin(L):
            if S_.L[S_.i] != p: return
            for k, v_ in L or [("Infos", "aucune")]:
                r = boite(False, 10); r.append(label(k, "petit", "attenue")); r.append(label(v_, "petit", hexpand=True, xalign=1)); S_.p_infos.append(r)
        threading.Thread(target=lambda: (lambda L: GLib.idle_add(fin, L))(infos(p)), daemon=True).start()

    def supprimer(self):
        if not self.L: return
        p = self.L[self.i]
        try: Gio.File.new_for_path(p).trash(None)
        except GLib.Error: return
        x = xmp(p)
        if os.path.exists(x):
            try: Gio.File.new_for_path(x).trash(None)
            except GLib.Error: pass
        self.L.pop(self.i); self.cache.pop(p, None); self.i = min(self.i, len(self.L) - 1); self.construire_bande(); self.afficher()

    def ouvrir_avec(self):
        if not self.L: return
        l = Gtk.FileLauncher.new(Gio.File.new_for_path(self.L[self.i])); l.set_always_ask(True); l.launch(self.win, None, None)

    def plein_ecran(self):
        if self.win.is_fullscreen(): self.win.unfullscreen(); self.bs.set_visible(True)
        else: self.win.fullscreen(); self.bs.set_visible(False)

    # bande de miniatures (chargées petit à petit)
    def construire_bande(self):
        vider(self.bande); self.minis = []
        for k, p in enumerate(self.L[:600]):
            b = Gtk.Button(); b.add_css_class("ph-mini"); pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True); pic.set_size_request(110, 74); b.set_child(pic)
            b.connect("clicked", lambda _b, k=k: (setattr(self, "i", k), self.afficher())); self.bande.append(b); self.minis.append((b, pic))
        def fond():
            for k, p in enumerate(self.L[:600]):
                try: t = charger(p, 220, 148)
                except Exception: continue
                GLib.idle_add(lambda k=k, t=t: (k < len(self.minis) and self.minis[k][1].set_paintable(t), False)[1])
        threading.Thread(target=fond, daemon=True).start()

    def marquer_bande(self):
        for k, (b, _p) in enumerate(getattr(self, "minis", [])):
            (b.add_css_class if k == self.i else b.remove_css_class)("actif")


def main():
    sys.exit(Photos().run(sys.argv))
