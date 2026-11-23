# OS XIII — XIII Scanner : numériser des documents avec la webcam, un scanner (SANE) ou une photo du téléphone,
# recadrer en tirant les 4 coins (la perspective est redressée), rendre lisible (couleur, gris, noir et blanc),
# puis créer un PDF de plusieurs pages, avec le texte reconnu (OCR Tesseract, hors ligne) : le PDF devient cherchable.
# Rangé dans le projet actif (03_Documents) ou dans Documents › Scans ; envoi à DOSSIER XIII en un clic.
# Application développée par Matthieu Lamotte.
import os, sys, glob, time, shutil, subprocess, threading, tempfile
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
from . import config, systeme as S
from .ui import *
from .appli import preparer

TMP = tempfile.mkdtemp(prefix="xiii-scan-")
MODES = [("couleur", "Couleur"), ("gris", "Gris"), ("nb", "Noir et blanc (texte)")]


def destination():
    pj = config.charger().get("projet_actif")
    d = os.path.expanduser("~/XIII/%s/03_Documents" % pj) if pj else os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or os.path.expanduser("~/Documents"), "Scans")
    os.makedirs(d, exist_ok=True); return d


def webcams():
    L = []
    for d in sorted(glob.glob("/dev/video*")):
        n = os.path.basename(d)
        try:
            if int(open("/sys/class/video4linux/%s/index" % n).read()) != 0: continue
            L.append((d, open("/sys/class/video4linux/%s/name" % n).read().strip()))
        except (OSError, ValueError): pass
    return L


def scanners():
    if not shutil.which("scanimage"): return []
    o = subprocess.run(["scanimage", "-f", "%d|%v %m%n"], capture_output=True, text=True, timeout=40).stdout
    return [tuple(l.split("|", 1)) for l in o.splitlines() if "|" in l]


def coefficients(src, dst):
    """Coefficients de la transformation perspective (PIL) qui envoie le quadrilatère dst sur src (élimination de Gauss)."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    n = 8; M = [A[i] + [B[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c])); M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c and M[c][c]:
                f = M[r][c] / M[c][c]; M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def traiter(chemin, coins, mode, sortie):
    """Redresse le quadrilatère (coins en fractions 0..1, ordre HG, HD, BD, BG) et applique le mode."""
    from PIL import Image, ImageOps, ImageFilter
    im = ImageOps.exif_transpose(Image.open(chemin)).convert("RGB"); W, H = im.size
    P = [(x * W, y * H) for x, y in coins]
    largeur = int(max(((P[1][0] - P[0][0]) ** 2 + (P[1][1] - P[0][1]) ** 2) ** .5, ((P[2][0] - P[3][0]) ** 2 + (P[2][1] - P[3][1]) ** 2) ** .5))
    hauteur = int(max(((P[3][0] - P[0][0]) ** 2 + (P[3][1] - P[0][1]) ** 2) ** .5, ((P[2][0] - P[1][0]) ** 2 + (P[2][1] - P[1][1]) ** 2) ** .5))
    if coins != [(0, 0), (1, 0), (1, 1), (0, 1)]:
        im = im.transform((largeur, hauteur), Image.PERSPECTIVE, coefficients(P, [(0, 0), (largeur, 0), (largeur, hauteur), (0, hauteur)]), Image.BICUBIC)
    if mode == "gris": im = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    elif mode == "nb":
        g = im.convert("L"); fond = g.filter(ImageFilter.GaussianBlur(25))      # éclairage inégal de la webcam corrigé
        from PIL import ImageChops
        g = ImageChops.invert(ImageChops.subtract(fond, g)); g = ImageOps.autocontrast(g, cutoff=2)
        im = g.point(lambda v: 255 if v > 170 else (0 if v < 110 else int((v - 110) * 255 / 60)))
    else: im = ImageOps.autocontrast(im, cutoff=0.5)
    im.save(sortie, quality=92); return sortie


def creer_pdf(pages, nom, ocr=True, progres=lambda t: None):
    sortie = os.path.join(destination(), nom if nom.lower().endswith(".pdf") else nom + ".pdf")
    if ocr and shutil.which("tesseract"):
        parts = []
        for i, p in enumerate(pages):
            progres("Reconnaissance du texte, page %d / %d…" % (i + 1, len(pages)))
            base = os.path.join(TMP, "ocr-%03d" % i)
            r = subprocess.run(["tesseract", p, base, "-l", "fra+eng" if os.path.exists("/usr/share/tesseract-ocr/5/tessdata/eng.traineddata") else "fra", "pdf"], capture_output=True, text=True)
            if r.returncode or not os.path.exists(base + ".pdf"): break
            parts.append(base + ".pdf")
        else:
            if len(parts) == 1: shutil.copy(parts[0], sortie)
            else: subprocess.run(["pdfunite"] + parts + [sortie], check=True)
            return sortie, True
    from PIL import Image
    I = [Image.open(p).convert("RGB") for p in pages]
    I[0].save(sortie, save_all=True, append_images=I[1:], resolution=200.0)
    return sortie, False


class Recadrage(Gtk.DrawingArea):
    """Image + quadrilatère à 4 poignées."""
    def __init__(self, chemin):
        super().__init__(hexpand=True, vexpand=True); self.chemin = chemin
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(chemin, 1400, 1400, True); pb = pb.apply_embedded_orientation() or pb
        self.pb = pb; self.coins = [(0.04, 0.04), (0.96, 0.04), (0.96, 0.96), (0.04, 0.96)]; self.actif = None
        self.set_draw_func(self.dessin)
        g = Gtk.GestureDrag(); g.connect("drag-begin", self.debut); g.connect("drag-update", self.suite); g.connect("drag-end", lambda *_: setattr(self, "actif", None)); self.add_controller(g)

    def cadre(self):
        w, h = self.get_width(), self.get_height(); s = min(w / self.pb.get_width(), h / self.pb.get_height())
        iw, ih = self.pb.get_width() * s, self.pb.get_height() * s
        return (w - iw) / 2, (h - ih) / 2, iw, ih, s

    def dessin(self, a, cr, w, h):
        x0, y0, iw, ih, s = self.cadre()
        cr.save(); cr.translate(x0, y0); cr.scale(s, s); Gdk.cairo_set_source_pixbuf(cr, self.pb, 0, 0); cr.paint(); cr.restore()
        P = [(x0 + x * iw, y0 + y * ih) for x, y in self.coins]
        cr.set_source_rgba(0.94, 0.70, 0.47, 0.25); cr.move_to(*P[0]); [cr.line_to(*p) for p in P[1:]]; cr.close_path(); cr.fill_preserve()
        cr.set_source_rgb(0.94, 0.70, 0.47); cr.set_line_width(2.5); cr.stroke()
        for p in P: cr.arc(p[0], p[1], 11, 0, 6.3); cr.fill()

    def debut(self, g, x, y):
        x0, y0, iw, ih, s = self.cadre()
        d = [((x0 + cx * iw - x) ** 2 + (y0 + cy * ih - y) ** 2, i) for i, (cx, cy) in enumerate(self.coins)]
        m = min(d); self.actif = m[1] if m[0] < 40 ** 2 else None; self.dep = (x, y)

    def suite(self, g, dx, dy):
        if self.actif is None: return
        x0, y0, iw, ih, s = self.cadre()
        x, y = self.dep[0] + dx, self.dep[1] + dy
        self.coins[self.actif] = (min(1, max(0, (x - x0) / iw)), min(1, max(0, (y - y0) / ih))); self.queue_draw()

    def tout(self): self.coins = [(0, 0), (1, 0), (1, 1), (0, 1)]; self.queue_draw()


class Scanner(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.scanner"); self.pages = []; self.proc = None

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".mini-page { border: 2px solid transparent; border-radius: 8px; padding: 2px; background: transparent; } .mini-page.actif { border-color: #f0b378; }")
        self.win = Gtk.ApplicationWindow(application=self, title="XIII Scanner", default_width=1280, default_height=820)
        r = boite(False, 0); self.win.set_child(r)
        g = boite(True, 10, margin_start=14, margin_end=10, margin_top=12, margin_bottom=12); g.set_size_request(300, -1); r.append(g)
        g.append(label("Scanner", "titre-astoria")); g.append(label("Webcam, scanner ou photo → PDF cherchable", "petit", "attenue"))
        self.cams = webcams()
        if self.cams:
            g.append(label("Webcam", "section"))
            self.dd_cam = Gtk.DropDown.new_from_strings([n for _, n in self.cams]); g.append(self.dd_cam)
            self.dd_cam.connect("notify::selected", lambda *_: self.apercu_webcam())
            b = bouton("Prendre la page", "camera", "pilule", rappel=self.capturer_webcam); g.append(b)
        g.append(label("Scanner", "section"))
        self.zone_sc = boite(True, 6); g.append(self.zone_sc); self.zone_sc.append(label("Recherche des scanners…", "petit", "attenue"))
        S.en_fond(scanners, self.rendu_scanners)
        g.append(label("Fichier", "section"))
        g.append(bouton("Ajouter des photos…", "image", "fantome", rappel=self.importer))
        g.append(label("Pages", "section"))
        sc = Gtk.ScrolledWindow(vexpand=True); self.l_pages = boite(True, 6); sc.set_child(self.l_pages); g.append(sc)
        r.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        d = boite(True, 8, hexpand=True, margin_start=10, margin_end=14, margin_top=12, margin_bottom=12); r.append(d)
        self.outils = boite(False, 8); d.append(self.outils)
        self.pile = Gtk.Stack(vexpand=True); d.append(self.pile)
        self.pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, hexpand=True, vexpand=True); self.pile.add_named(self.pic, "apercu")
        self.pile.add_named(label("Prenez une page avec la webcam ou le scanner, ou ajoutez une photo.", "attenue"), "vide")
        self.zone_rec = boite(True, 0); self.pile.add_named(self.zone_rec, "recadrer")
        f = boite(False, 8); self.nom = Gtk.Entry(text=time.strftime("Scan %Y-%m-%d %H%M"), hexpand=True); f.append(self.nom)
        self.ocr = Gtk.CheckButton(label="Texte cherchable (OCR)", active=bool(shutil.which("tesseract"))); f.append(self.ocr)
        self.b_pdf = bouton("Créer le PDF", "file-text", "pilule", rappel=self.pdf); f.append(self.b_pdf); d.append(f)
        self.etat = label("", "petit", "attenue", wrap=True); d.append(self.etat)
        self.win.connect("close-request", lambda *_: (self.stop_apercu(), shutil.rmtree(TMP, ignore_errors=True), False)[2])
        self.win.present()
        if self.cams: self.apercu_webcam()
        else: self.pile.set_visible_child_name("vide")

    # ------------------------------------------------------------ sources
    def stop_apercu(self):
        if self.proc and self.proc.poll() is None: self.proc.terminate()
        self.proc = None

    def apercu_webcam(self):
        self.stop_apercu(); dev = self.cams[self.dd_cam.get_selected()][0]; self.cur = os.path.join(TMP, "webcam.jpg")
        self.proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-video_size", "1920x1080", "-i", dev, "-vf", "fps=3", "-q:v", "3", "-update", "1", "-y", self.cur],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        vider(self.outils); self.outils.append(label("Aperçu de la webcam — tenez la feuille bien à plat, sur un fond foncé", "petit", "attenue"))
        self.pile.set_visible_child_name("apercu")
        def tic():
            if not self.proc or self.pile.get_visible_child_name() != "apercu": return False
            try:
                if os.path.exists(self.cur): self.pic.set_paintable(Gdk.Texture.new_from_filename(self.cur))
            except GLib.Error: pass
            return True
        GLib.timeout_add(350, tic)

    def capturer_webcam(self):
        if not self.proc or not os.path.exists(getattr(self, "cur", "")): self.apercu_webcam(); return
        p = os.path.join(TMP, "brut-%03d.jpg" % len(self.pages)); shutil.copy(self.cur, p); self.stop_apercu(); self.ajouter(p)

    def rendu_scanners(self, L):
        vider(self.zone_sc)
        if isinstance(L, Exception) or not L: self.zone_sc.append(label("Aucun scanner trouvé (branché et allumé ?).", "petit", "attenue", wrap=True)); return
        self.dd_sc = Gtk.DropDown.new_from_strings([n for _, n in L]); self.zone_sc.append(self.dd_sc); self.sc_L = L
        self.zone_sc.append(bouton("Numériser", "scan", "pilule", rappel=self.numeriser))

    def numeriser(self):
        dev = self.sc_L[self.dd_sc.get_selected()][0]; p = os.path.join(TMP, "brut-%03d.png" % len(self.pages)); self.etat.set_text("Numérisation…")
        S.en_fond(lambda: subprocess.run(["scanimage", "-d", dev, "--format=png", "--resolution", "300", "-o", p], capture_output=True, timeout=180).returncode,
                  lambda rc: (self.etat.set_text(""), self.ajouter(p)) if rc == 0 and os.path.exists(p) else self.etat.set_text("Numérisation impossible."))

    def importer(self):
        d = Gtk.FileDialog(title="Photos de documents")
        def fin(dd, res):
            try: L = dd.open_multiple_finish(res)
            except GLib.Error: return
            for i in range(L.get_n_items()): self.ajouter(L.get_item(i).get_path())
        d.open_multiple(self.win, None, fin)

    # ------------------------------------------------------------ pages
    def ajouter(self, p):
        self.pages.append({"brut": p, "coins": None, "mode": "nb", "fini": None}); self.editer(len(self.pages) - 1)

    def editer(self, i):
        self.i = i; pg = self.pages[i]; vider(self.zone_rec); vider(self.outils)
        self.rec = Recadrage(pg["brut"])
        if pg["coins"]: self.rec.coins = list(pg["coins"])
        self.zone_rec.append(self.rec)
        self.outils.append(label("Tirez les 4 coins sur les bords de la feuille", "petit", "attenue", hexpand=True))
        self.outils.append(bouton("Image entière", None, "plat", rappel=self.rec.tout))
        dd = Gtk.DropDown.new_from_strings([n for _, n in MODES]); dd.set_selected([k for k, _ in MODES].index(pg["mode"])); self.outils.append(dd); self.dd_mode = dd
        self.outils.append(bouton("Valider la page", "check", "pilule", rappel=self.valider))
        self.outils.append(bouton(None, "trash-2", "plat", tip="Retirer la page", rappel=self.retirer))
        self.pile.set_visible_child_name("recadrer"); self.liste()

    def valider(self):
        pg = self.pages[self.i]; pg["coins"] = list(self.rec.coins); pg["mode"] = MODES[self.dd_mode.get_selected()][0]
        sortie = os.path.join(TMP, "page-%03d-%d.jpg" % (self.i, int(time.time() * 1000) % 100000))
        self.etat.set_text("Redressement…")
        S.en_fond(traiter, lambda r: self.fin_page(r), pg["brut"], pg["coins"], pg["mode"], sortie)

    def fin_page(self, r):
        if isinstance(r, Exception): self.etat.set_text("Erreur : %s" % r); return
        self.pages[self.i]["fini"] = r; self.etat.set_text("Page %d prête. Ajoutez la suivante ou créez le PDF." % (self.i + 1))
        self.pic.set_paintable(Gdk.Texture.new_from_filename(r)); self.pile.set_visible_child_name("apercu"); vider(self.outils)
        self.outils.append(bouton("Retoucher cette page", "pencil", "fantome", rappel=lambda i=self.i: self.editer(i)))
        if self.cams: self.outils.append(bouton("Page suivante (webcam)", "camera", "pilule", rappel=self.apercu_webcam))
        self.liste()

    def retirer(self):
        self.pages.pop(self.i); self.liste()
        if self.pages: self.editer(len(self.pages) - 1)
        elif self.cams: self.apercu_webcam()
        else: self.pile.set_visible_child_name("vide")

    def liste(self):
        vider(self.l_pages)
        for k, pg in enumerate(self.pages):
            b = Gtk.Button(); b.add_css_class("mini-page")
            if k == getattr(self, "i", -1): b.add_css_class("actif")
            h = boite(False, 8); pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER); pic.set_size_request(60, 80)
            try: pic.set_paintable(Gdk.Texture.new_for_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(pg["fini"] or pg["brut"], 120, 160, True)))
            except GLib.Error: pass
            h.append(pic); h.append(label("Page %d%s" % (k + 1, " ✓" if pg["fini"] else " (à valider)"), "petit")); b.set_child(h)
            b.connect("clicked", lambda _b, k=k: self.editer(k)); self.l_pages.append(b)

    def pdf(self):
        P = [pg["fini"] for pg in self.pages if pg["fini"]]
        if not P: self.etat.set_text("Validez au moins une page."); return
        self.b_pdf.set_sensitive(False)
        def fin(r):
            self.b_pdf.set_sensitive(True)
            if isinstance(r, Exception): self.etat.set_text("Erreur : %s" % r); return
            f, ocr = r; self.etat.set_text("PDF créé%s : %s" % (" avec texte cherchable" if ocr else "", f))
            vider(self.outils)
            self.outils.append(bouton("Ouvrir", "file-text", "pilule", rappel=lambda: S.detacher(["xdg-open", f])))
            self.outils.append(bouton("Envoyer à DOSSIER", "folder-input", "fantome", rappel=lambda: S.detacher(["xiii-suite", "--dossier", f])))
            self.outils.append(bouton("Nouveau document", "plus", "fantome", rappel=self.nouveau))
        S.en_fond(creer_pdf, fin, P, self.nom.get_text().strip() or "Scan", self.ocr.get_active(), lambda t: GLib.idle_add(lambda: (self.etat.set_text(t), False)[1]))

    def nouveau(self):
        self.pages = []; self.liste(); self.nom.set_text(time.strftime("Scan %Y-%m-%d %H%M"))
        if self.cams: self.apercu_webcam()
        else: self.pile.set_visible_child_name("vide")


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--test":       # tests : xiii-scanner --test photo.jpg sortie.pdf
        p = traiter(sys.argv[2], [(0.1, 0.08), (0.9, 0.12), (0.88, 0.92), (0.12, 0.9)], "nb", os.path.join(TMP, "t.jpg"))
        global destination
        destination = lambda: os.path.dirname(os.path.abspath(sys.argv[3]))
        f, ocr = creer_pdf([p], os.path.basename(sys.argv[3])); print("OK", f, "OCR" if ocr else "sans OCR"); return
    sys.exit(Scanner().run(sys.argv[:1]))
