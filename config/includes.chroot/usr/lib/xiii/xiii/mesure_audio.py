# OS XIII — Mesure audio broadcast : sonie (LUFS) momentanée, court terme et intégrée, crête vraie (dBTP), plage
# dynamique (LRA), d'après la norme EBU R128 / ITU-R BS.1770 (filtre ebur128 de FFmpeg).
# Source : ce que joue l'ordinateur (sortie), une entrée (micro, carte son) ou un fichier (analyse complète).
# Cibles : EBU R128 (-23), ATSC A/85 (-24), web / YouTube / Spotify (-14), Apple (-16), Netflix (-27 dialogue).
# Application développée par Matthieu Lamotte.
import os, sys, re, subprocess, threading, time, json
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S
from .ui import *
from .appli import preparer

CIBLES = [("ebu", "EBU R128 (télévision Europe)", -23, -1), ("atsc", "ATSC A/85 (États-Unis)", -24, -2), ("web", "Web, YouTube, Spotify", -14, -1),
          ("apple", "Apple Podcasts / Music", -16, -1), ("netflix", "Netflix (dialogue)", -27, -2), ("cinema", "Cinéma (référence)", -27, -1)]
RE = re.compile(r"M:\s*(-?[\d.]+|-inf)\s+S:\s*(-?[\d.]+|-inf)\s+I:\s*(-?[\d.]+|-inf)\s+LUFS\s+LRA:\s*(-?[\d.]+)\s+LU(?:.*?\bTPK:\s*(-?[\d.]+|-inf)(?:\s+(-?[\d.]+|-inf))?\s+dBFS)?")

def sources():
    """[(nom pour ffmpeg -f pulse, libellé)] : moniteur de la sortie par défaut + entrées."""
    L = [("@DEFAULT_MONITOR@", "Ce que joue l'ordinateur (sortie)")]
    try:
        for l in subprocess.run(["pactl", "list", "short", "sources"], capture_output=True, text=True, timeout=5).stdout.splitlines():
            p = l.split("\t")
            if len(p) > 1 and not p[1].endswith(".monitor"): L.append((p[1], "Entrée : " + p[1].split(".")[-1].replace("_", " ")))
    except Exception: pass
    return L

BANDES = [25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]
TAUX, N = 44100, 2048


def fft(x):
    """FFT radix 2 (numpy si présent, sinon Python pur)."""
    try:
        import numpy as np
        return list(np.abs(np.fft.rfft(np.array(x) * np.hanning(len(x)))))
    except ImportError:
        import cmath, math
        n = len(x); a = [complex(v * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)))) for i, v in enumerate(x)]
        j = 0
        for i in range(1, n):
            b = n >> 1
            while j & b: j ^= b; b >>= 1
            j |= b
            if i < j: a[i], a[j] = a[j], a[i]
        m = 2
        while m <= n:
            w = cmath.exp(-2j * math.pi / m)
            for k in range(0, n, m):
                wk = 1
                for t in range(m // 2):
                    u, v = a[k + t], a[k + t + m // 2] * wk; a[k + t], a[k + t + m // 2] = u + v, u - v; wk *= w
            m <<= 1
        return [abs(c) for c in a[:n // 2 + 1]]


def bandes(mag):
    """Spectre en tiers d'octave, dBFS approximatifs."""
    import math
    out = []
    for fc in BANDES:
        lo, hi = fc / 2 ** (1 / 6), fc * 2 ** (1 / 6)
        i0, i1 = max(1, int(lo * N / TAUX)), max(int(lo * N / TAUX) + 1, int(hi * N / TAUX))
        e = sum(m * m for m in mag[i0:i1 + 1]) if i0 < len(mag) else 0
        out.append(10 * math.log10(e / (N * N / 8)) if e > 0 else -100)
    return out


def f(x):
    try: return float(x)
    except (TypeError, ValueError): return -70.0

class Mesure(Gtk.Application):
    def __init__(self, fichier=None):
        super().__init__(application_id="fr.xiii.mesureaudio"); self.fichier = fichier; self.proc = None; self.hist = []

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        self.cfg = preparer(".lufs-grand { font-family: 'IBM Plex Mono'; font-size: 64px; font-weight: 700; } .lufs-moy { font-family: 'IBM Plex Mono'; font-size: 30px; font-weight: 700; }"
                            " .lufs-ok { color: #51cf66; } .lufs-haut { color: #ff6b6b; } .lufs-bas { color: #74c0fc; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Mesure audio XIII", default_width=900, default_height=640)
        v = boite(True, 12, margin_top=16, margin_bottom=16, margin_start=20, margin_end=20)
        h = boite(False, 10); h.append(ico("audio-waveform", 26, "c")); h.append(label("Mesure audio", "page-titre", hexpand=True))
        self.src = sources(); self.dd_src = Gtk.DropDown(model=Gtk.StringList.new([x[1] for x in self.src])); h.append(self.dd_src)
        self.dd_cible = Gtk.DropDown(model=Gtk.StringList.new([x[1] for x in CIBLES])); h.append(self.dd_cible)
        k = [x[0] for x in CIBLES]; self.dd_cible.set_selected(k.index(self.cfg.get("lufs_cible", "ebu")) if self.cfg.get("lufs_cible", "ebu") in k else 0)
        self.dd_cible.connect("notify::selected", lambda w, *_: config.modifier(_histo=False, lufs_cible=CIBLES[w.get_selected()][0]))
        v.append(h)
        r = boite(False, 10)
        self.b_go = bouton("Mesurer en direct", "play", "pilule", rappel=self.basculer); r.append(self.b_go)
        r.append(bouton("Remettre à zéro", "rotate-ccw", "fantome", rappel=lambda: (self.arreter(), self.demarrer())))
        r.append(bouton("Analyser un fichier…", "file-audio", "fantome", rappel=self.choisir_fichier)); v.append(r)
        g = boite(False, 14, homogeneous=True)
        def carte(titre, css="lufs-moy"):
            c = boite(True, 4, "carte"); c.append(label(titre, "petit", "attenue")); l = label("—", css); c.append(l); g.append(c); return l
        self.l_m = carte("Momentanée (400 ms)", "lufs-grand"); self.l_s = carte("Court terme (3 s)", "lufs-grand"); self.l_i = carte("Intégrée (programme)", "lufs-grand")
        v.append(g)
        g2 = boite(False, 14, homogeneous=True)
        def carte2(titre):
            c = boite(True, 4, "carte"); c.append(label(titre, "petit", "attenue")); l = label("—", "lufs-moy"); c.append(l); g2.append(c); return l
        self.l_tp = carte2("Crête vraie (dBTP)"); self.l_lra = carte2("Plage dynamique (LRA)"); self.l_ecart = carte2("Écart à la cible"); v.append(g2)
        gg = boite(False, 14, vexpand=True)
        self.graph = Gtk.DrawingArea(hexpand=True, vexpand=True); self.graph.set_draw_func(self.dessin); self.graph.set_size_request(-1, 200); gg.append(self.graph)
        self.spectre = []; self.g_spec = Gtk.DrawingArea(hexpand=True, vexpand=True); self.g_spec.set_draw_func(self.dessin_spectre); self.g_spec.set_size_request(320, 200); gg.append(self.g_spec)
        v.append(gg)
        self.etat = label("Choisissez la source puis « Mesurer en direct ».", "petit", "attenue"); v.append(self.etat)
        self.win.set_child(v); self.win.connect("close-request", lambda *_: (self.arreter(), False)[1]); self.win.present()
        if self.fichier: self.analyser(self.fichier)

    def cible(self): return CIBLES[self.dd_cible.get_selected()]

    def basculer(self):
        if self.proc: self.arreter()
        else: self.demarrer()

    def demarrer(self, fichier=None):
        self.hist = []; self.fin_i = None
        if fichier: cmd = ["ffmpeg", "-nostats", "-hide_banner", "-nostdin", "-i", fichier, "-af", "ebur128=peak=true:framelog=info", "-f", "null", "-"]
        else: cmd = ["ffmpeg", "-nostats", "-hide_banner", "-nostdin", "-f", "pulse", "-i", self.src[self.dd_src.get_selected()][0], "-filter_complex",
                     "[0:a]asplit[x][y];[x]ebur128=peak=true:framelog=info[e];[y]aresample=%d,aformat=sample_fmts=s16:channel_layouts=mono[m]" % TAUX,
                     "-map", "[e]", "-f", "null", "-", "-map", "[m]", "-f", "s16le", "pipe:1"]
        try: self.proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL if fichier else subprocess.PIPE, bufsize=0 if not fichier else 1, text=bool(fichier))
        except FileNotFoundError: self.etat.set_text("FFmpeg est absent."); return
        self.b_go.set_child(boite(False, 6)); self.b_go.get_child().append(ico("square", 16)); self.b_go.get_child().append(label("Arrêter"))
        self.etat.set_text("Analyse de « %s »…" % os.path.basename(fichier) if fichier else "Mesure en direct : %s" % self.src[self.dd_src.get_selected()][1])
        threading.Thread(target=self._lire, args=(self.proc, fichier), daemon=True).start()
        if not fichier: threading.Thread(target=self._spectre, args=(self.proc,), daemon=True).start()

    def _spectre(self, p):
        import array, time as _t
        dernier = 0
        while True:
            b = p.stdout.read(N * 2)
            if not b or len(b) < N * 2: break
            if _t.time() - dernier < .15: continue
            dernier = _t.time(); x = array.array("h", b); self.spectre = bandes(fft([v / 32768 for v in x])); GLib.idle_add(self.g_spec.queue_draw)

    def _lire(self, p, fichier):
        resume = {}
        import io
        flux = p.stderr if fichier else io.TextIOWrapper(p.stderr, errors="replace")
        for l in flux:
            m = RE.search(l)
            if m:
                d = {"M": f(m.group(1)), "S": f(m.group(2)), "I": f(m.group(3)), "LRA": f(m.group(4)), "TP": max(f(m.group(5)), f(m.group(6)) if m.group(6) else -70) if m.group(5) else None}
                self.hist.append(d)
                if len(self.hist) > 3000: self.hist = self.hist[-3000:]
                if not fichier or len(self.hist) % 50 == 0: GLib.idle_add(self.afficher, d)
            for k, rx in (("I", r"^\s+I:\s+(-?[\d.]+) LUFS"), ("LRA", r"^\s+LRA:\s+(-?[\d.]+) LU"), ("TP", r"^\s+Peak:\s+(-?[\d.]+) dBFS")):
                mm = re.match(rx, l)
                if mm: resume[k] = float(mm.group(1))
        if fichier and resume:
            GLib.idle_add(self.afficher, {"M": self.hist[-1]["M"] if self.hist else -70, "S": self.hist[-1]["S"] if self.hist else -70, **resume}, True)
        GLib.idle_add(self.fini, fichier)

    def fini(self, fichier):
        self.proc = None
        self.b_go.set_child(boite(False, 6)); self.b_go.get_child().append(ico("play", 16)); self.b_go.get_child().append(label("Mesurer en direct"))
        if fichier: self.etat.set_text("Analyse terminée : %s" % os.path.basename(fichier))

    def afficher(self, d, final=False):
        cib, tp_max = self.cible()[2], self.cible()[3]
        def met(l, x, ref=None):
            l.set_text("%.1f" % x if x > -69 else "—")
            for c in ("lufs-ok", "lufs-haut", "lufs-bas"): l.remove_css_class(c)
            if ref is not None and x > -69: l.add_css_class("lufs-ok" if abs(x - ref) <= 1 else ("lufs-haut" if x > ref else "lufs-bas"))
        met(self.l_m, d["M"], cib); met(self.l_s, d["S"], cib); met(self.l_i, d["I"], cib)
        if d.get("TP") is not None:
            self.l_tp.set_text("%.1f" % d["TP"]); [self.l_tp.remove_css_class(c) for c in ("lufs-ok", "lufs-haut")]; self.l_tp.add_css_class("lufs-haut" if d["TP"] > tp_max else "lufs-ok")
        self.l_lra.set_text("%.1f LU" % d["LRA"] if d.get("LRA") else "—")
        e = d["I"] - cib if d["I"] > -69 else None
        self.l_ecart.set_text(("%+.1f LU" % e) if e is not None else "—")
        if final: self.etat.set_text("Programme : %.1f LUFS, crête %.1f dBFS, LRA %.1f LU — %s" % (d["I"], d.get("TP", 0), d.get("LRA", 0),
                                     "dans la cible ✓" if e is not None and abs(e) <= 1 else "à corriger de %+.1f dB" % (-e if e is not None else 0)))
        self.graph.queue_draw(); return False

    def dessin(self, a, cr, W, H):
        cr.set_source_rgba(1, 1, 1, .04); cr.paint()
        bas, haut = -50.0, -5.0; y = lambda v: H - (max(bas, min(haut, v)) - bas) / (haut - bas) * H
        cib = self.cible()[2]
        cr.set_source_rgba(.32, .81, .40, .15); cr.rectangle(0, y(cib + 1), W, y(cib - 1) - y(cib + 1)); cr.fill()
        cr.set_source_rgba(1, 1, 1, .25); cr.select_font_face("IBM Plex Mono"); cr.set_font_size(10)
        for v in range(-50, 0, 5):
            cr.move_to(4, y(v) - 2); cr.show_text("%d" % v); cr.rectangle(34, y(v), W - 34, .5); cr.fill()
        H_ = self.hist[-int(W):]
        for cle, coul in (("S", (.94, .70, .47)), ("M", (1, 1, 1))):
            cr.set_source_rgba(*coul, .9 if cle == "S" else .35); cr.set_line_width(2 if cle == "S" else 1)
            for i, d in enumerate(H_):
                (cr.move_to if i == 0 else cr.line_to)(34 + i * (W - 34) / max(1, len(H_)), y(d[cle]))
            cr.stroke()

    def dessin_spectre(self, a, cr, W, H):
        """Spectre en tiers d'octave (25 Hz – 20 kHz), en direct."""
        cr.set_source_rgba(1, 1, 1, .04); cr.paint()
        cr.set_source_rgba(1, 1, 1, .3); cr.select_font_face("IBM Plex Mono"); cr.set_font_size(9)
        for k, fc in enumerate(BANDES):
            if fc in (31.5, 125, 500, 2000, 8000):
                cr.move_to(k * W / len(BANDES) + 1, H - 2); cr.show_text("%g" % fc if fc < 1000 else "%dk" % (fc // 1000))
        if not self.spectre:
            cr.move_to(10, 18); cr.show_text("Spectre : en mesure directe"); return
        bw = W / len(BANDES)
        for k, db in enumerate(self.spectre):
            h = max(0, min(1, (db + 80) / 80)) * (H - 14)
            cr.set_source_rgba(.94, .70, .47, .85) if db < -12 else cr.set_source_rgba(1, .42, .42, .9)
            cr.rectangle(k * bw + 1, H - 14 - h, bw - 2, h); cr.fill()

    def choisir_fichier(self):
        d = Gtk.FileDialog(title="Analyser la sonie d'un fichier")
        def fini(dl, r):
            try: self.analyser(dl.open_finish(r).get_path())
            except GLib.Error: pass
        d.open(self.win, None, fini)

    def analyser(self, fichier):
        self.arreter(); self.demarrer(fichier)

    def arreter(self):
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass
            self.proc = None

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("-")]
    sys.exit(Mesure(a[0] if a else None).run(sys.argv[:1]))
