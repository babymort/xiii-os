# OS XIII — timecode LTC : lecture du timecode audio (SMPTE LTC) sur une entrée son (carte son, micro, retour
# d'une caméra ou d'un enregistreur), grâce à libltc. Grand affichage plateau, widget, et fichier partagé
# /run/user/<uid>/xiii-timecode pour les autres outils (Tally XIII, MCP…).
# Application développée par Matthieu Lamotte.
import os, sys, ctypes, ctypes.util, subprocess, threading, time, json

TAUX = 48000

class SMPTE(ctypes.Structure):
    _fields_ = [("timezone", ctypes.c_char * 6), ("years", ctypes.c_ubyte), ("months", ctypes.c_ubyte), ("days", ctypes.c_ubyte),
                ("hours", ctypes.c_ubyte), ("mins", ctypes.c_ubyte), ("secs", ctypes.c_ubyte), ("frame", ctypes.c_ubyte)]

_lib = None
def lib():
    global _lib
    if _lib is None:
        n = ctypes.util.find_library("ltc") or "libltc.so.11"
        _lib = ctypes.CDLL(n)
        _lib.ltc_decoder_create.restype = ctypes.c_void_p; _lib.ltc_decoder_create.argtypes = [ctypes.c_int, ctypes.c_int]
        _lib.ltc_decoder_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_longlong]
        _lib.ltc_decoder_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; _lib.ltc_decoder_read.restype = ctypes.c_int
        _lib.ltc_decoder_free.argtypes = [ctypes.c_void_p]
        _lib.ltc_frame_to_time.argtypes = [ctypes.POINTER(SMPTE), ctypes.c_void_p, ctypes.c_int]
        _lib.ltc_encoder_create.restype = ctypes.c_void_p; _lib.ltc_encoder_create.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_int]
        _lib.ltc_encoder_set_timecode.argtypes = [ctypes.c_void_p, ctypes.POINTER(SMPTE)]
        _lib.ltc_encoder_encode_frame.argtypes = [ctypes.c_void_p]
        _lib.ltc_encoder_inc_timecode.argtypes = [ctypes.c_void_p]
        _lib.ltc_encoder_get_buffer.argtypes = [ctypes.c_void_p, ctypes.c_char_p]; _lib.ltc_encoder_get_buffer.restype = ctypes.c_int
        _lib.ltc_encoder_free.argtypes = [ctypes.c_void_p]
    return _lib

def disponible():
    try: lib(); return True
    except OSError: return False

def texte(tc, fps=25):
    return "%02d:%02d:%02d%s%02d" % (tc.hours, tc.mins, tc.secs, ":", tc.frame)

class Decodeur:
    """Nourri d'échantillons 8 bits non signés (centrés sur 128) ; rappel(texte_timecode) à chaque image décodée."""
    def __init__(self, rappel, taux=TAUX, fps=25):
        self.rappel = rappel; self.d = lib().ltc_decoder_create(int(taux / fps), 32); self.pos = 0
        self.ext = ctypes.create_string_buffer(2048); self.tc = SMPTE()

    def ecrire(self, octets):
        L = lib()
        for i in range(0, len(octets), 1920):         # par petits blocs : la file du décodeur est limitée
            b = octets[i:i + 1920]
            L.ltc_decoder_write(self.d, b, len(b), self.pos); self.pos += len(b)
            while L.ltc_decoder_read(self.d, self.ext):
                L.ltc_frame_to_time(ctypes.byref(self.tc), self.ext, 0)
                self.rappel(texte(self.tc))

    def fermer(self):
        if self.d: lib().ltc_decoder_free(self.d); self.d = None

def encoder(debut=(10, 0, 0, 0), images=50, fps=25, taux=TAUX):
    """Génère du LTC (u8) — sert au test et au bouton « signal de test »."""
    L = lib(); e = L.ltc_encoder_create(taux, fps, 1 if fps == 25 else 0, 0)
    tc = SMPTE(b"+0100", 26, 11, 20, *debut); L.ltc_encoder_set_timecode(e, ctypes.byref(tc))
    buf = ctypes.create_string_buffer(8192); out = bytearray()
    for _ in range(images):
        L.ltc_encoder_encode_frame(e); n = L.ltc_encoder_get_buffer(e, buf); out += buf.raw[:n]; L.ltc_encoder_inc_timecode(e)
    L.ltc_encoder_free(e)
    return bytes(out)

def entrees():
    """Entrées audio PipeWire/PulseAudio : [(nom, description)]."""
    try:
        o = subprocess.run(["pactl", "-f", "json", "list", "sources"], capture_output=True, text=True, timeout=3).stdout
        return [(s["name"], s.get("description") or s["name"]) for s in json.loads(o) if not s["name"].endswith(".monitor")]
    except Exception:
        try:
            o = subprocess.run(["pactl", "list", "short", "sources"], capture_output=True, text=True, timeout=3).stdout
            return [(l.split("\t")[1], l.split("\t")[1]) for l in o.splitlines() if "\t" in l and not l.split("\t")[1].endswith(".monitor")]
        except Exception:
            return []

PARTAGE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "xiii-timecode")

class Lecteur:
    """Écoute une entrée son en continu (parec) et décode le LTC."""
    def __init__(self, rappel, source=None, canal=0):
        self.rappel = rappel; self.source = source; self.canal = canal; self.proc = None; self.actif = False; self.dernier = 0

    def demarrer(self):
        self.actif = True
        threading.Thread(target=self._boucle, daemon=True).start()

    def _boucle(self):
        while self.actif:
            cmd = ["parec", "--format=u8", "--rate=%d" % TAUX, "--channels=2", "--latency-msec=20"] + (["--device=" + self.source] if self.source else [])
            try:
                self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except OSError:
                return
            dec = Decodeur(self._image)
            while self.actif:
                b = self.proc.stdout.read(1920)
                if not b: break
                dec.ecrire(b[self.canal::2])
            dec.fermer()
            if self.actif: time.sleep(1)

    def _image(self, t):
        self.dernier = time.time(); self.rappel(t)
        try:
            with open(PARTAGE, "w") as f: f.write(t + "\n")
        except OSError:
            pass

    def arreter(self):
        self.actif = False
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass

def lire_partage(max_age=1.0):
    try:
        if time.time() - os.path.getmtime(PARTAGE) <= max_age: return open(PARTAGE).read().strip()
    except OSError:
        pass
    return None

# ------------------------------------------------------------------------------- grand affichage
def main():
    if "--test" in sys.argv:              # auto-test : encode puis décode
        vus = []; d = Decodeur(vus.append); d.ecrire(encoder()); d.fermer()
        print("\n".join(vus[:3]), "…", vus[-1] if vus else "", "(%d images)" % len(vus)); sys.exit(0 if len(vus) >= 45 and vus[0] in ("10:00:00:00", "10:00:00:01") else 1)

    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gdk, GLib, Gio
    from . import config, theme
    from .ui import boite, label, bouton, couleurs

    def deroulant(options, courant, rappel):
        dd = Gtk.DropDown.new_from_strings([d for _, d in options])
        cles = [k for k, _ in options]
        if courant in cles: dd.set_selected(cles.index(courant))
        dd.connect("notify::selected", lambda d, *_: rappel(cles[d.get_selected()]))
        return dd

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="fr.xiii.timecode")
            self.lecteur = None; self.tc = "--:--:--:--"

        def do_activate(self):
            if getattr(self, "win", None): self.win.present(); return
            cfg = config.charger(); couleurs(cfg)
            css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(cfg) + """
                .tc-fond { background: #000; } .tc { font-family: "IBM Plex Mono", monospace; font-size: 96pt; font-weight: 700; color: #fff; }
                .tc.perdu { color: alpha(#fff, .35); }""")
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.win = Gtk.ApplicationWindow(application=self, title="Timecode LTC"); self.win.set_default_size(900, 420)
            v = boite(True, 12); v.add_css_class("tc-fond")
            h = boite(False, 10, margin_start=12, margin_end=12, margin_top=10)
            h.append(label("Entrée audio", "petit", "attenue"))
            ent = entrees(); src = cfg.get("timecode_source") or (ent[0][0] if ent else "")
            choix = [(n, d) for n, d in ent] or [("", "Entrée par défaut")]
            h.append(deroulant(choix, src if src in [c[0] for c in choix] else choix[0][0], self.changer))
            h.append(deroulant([("0", "Canal gauche"), ("1", "Canal droit")], str(cfg.get("timecode_canal", 0)), self.canal))
            h.append(Gtk.Box(hexpand=True))
            h.append(bouton(None, "maximize", "plat", tip="Plein écran", rappel=lambda: self.win.unfullscreen() if self.win.is_fullscreen() else self.win.fullscreen()))
            v.append(h)
            self.l = label(self.tc, "tc", "perdu", xalign=0.5, vexpand=True); v.append(self.l)
            self.etat = label("En attente d'un signal LTC…", "attenue", xalign=0.5); v.append(self.etat)
            self.win.set_child(v); self.win.present()
            if not disponible():
                self.etat.set_text("libltc introuvable : le décodage du timecode n'est pas possible."); return
            self.src, self.can = src, int(cfg.get("timecode_canal", 0)); self.relancer()
            GLib.timeout_add(40, self.tic)

        def relancer(self):
            if self.lecteur: self.lecteur.arreter()
            self.lecteur = Lecteur(lambda t: setattr(self, "tc", t), self.src or None, self.can); self.lecteur.demarrer()

        def changer(self, v):
            self.src = v; config.modifier(timecode_source=v); self.relancer()

        def canal(self, v):
            self.can = int(v); config.modifier(timecode_canal=self.can); self.relancer()

        def tic(self):
            vivant = self.lecteur and time.time() - self.lecteur.dernier < 0.5
            self.l.set_text(self.tc)
            (self.l.remove_css_class if vivant else self.l.add_css_class)("perdu")
            self.etat.set_text("Signal LTC reçu · 25 i/s" if vivant else "En attente d'un signal LTC…" if self.tc.startswith("-") else "Signal perdu — dernier timecode affiché")
            return True

    sys.exit(App().run([sys.argv[0]]))
