# OS XIII — barre Tournage : quand le profil Tournage est actif, la barre des tâches montre ce qui compte sur un plateau :
# timecode, caméra au programme (Tally XIII), niveau du micro, place restante sur les cartes et batterie.
# Application développée par Matthieu Lamotte.
import os, time, glob, threading, subprocess, struct, math, pwd
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import systeme as S, profils
from .ui import *


def actif(cfg):
    return profils.courant(cfg)[0] == "tournage" and cfg.get("barre_tournage", True)


def cartes():
    """[(nom, octets libres)] des cartes, clés et disques externes montés."""
    u = pwd.getpwuid(os.getuid()).pw_name; L = []
    for m in glob.glob("/media/%s/*" % u) + glob.glob("/run/media/%s/*" % u) + glob.glob("/media/*/"):
        m = m.rstrip("/")
        if not os.path.ismount(m): continue
        try:
            st = os.statvfs(m); L.append((os.path.basename(m), st.f_bavail * st.f_frsize))
        except OSError:
            pass
    if S.DEMO and not L: L = [("A001_CARTE", 37 * 1024 ** 3)]
    vus = set(); R = []
    for n, l in L:
        if n not in vus: vus.add(n); R.append((n, l))
    return R


def taille(o):
    for u, k in (("To", 1024 ** 4), ("Go", 1024 ** 3), ("Mo", 1024 ** 2)):
        if o >= k: return ("%.1f %s" % (o / k, u)).replace(".0 ", " ").replace(".", ",")
    return "%d o" % o


class BarreTournage:
    def __init__(self, sh):
        self.sh = sh; self.niveau = -90.0; self._proc = None; self._fil = None; self._src = 0
        b = boite(False, 10, "barre-tournage", valign=Gtk.Align.CENTER); self.widget = b
        self.l_tc = label("00:00:00:00", "bt-tc"); b.append(self.l_tc)
        self.tally = label("", "bt-tally"); self.tally.set_visible(False); b.append(self.tally)
        v = boite(False, 4, valign=Gtk.Align.CENTER); v.append(ico("mic", 14, "t"))
        self.vu = Gtk.LevelBar(min_value=0, max_value=1, valign=Gtk.Align.CENTER); self.vu.set_size_request(70, 6); self.vu.add_css_class("bt-vu")
        for o in ("low", "high", "full"): self.vu.remove_offset_value(o)
        self.vu.add_offset_value("vert", .7); self.vu.add_offset_value("jaune", .85); self.vu.add_offset_value("rouge", 1.0)
        v.append(self.vu); b.append(v); v.set_tooltip_text("Niveau du micro")
        self.l_cartes = label("", "bt-info"); b.append(self.l_cartes)
        self.l_bat = label("", "bt-info"); b.append(self.l_bat)
        b.set_tooltip_text("Barre Tournage (profil Tournage) — Paramètres › Barre des tâches")

    def demarrer(self):
        if self._src: return
        self._src = GLib.timeout_add(100, self.tic); self._n = 0
        self.ecouter()

    def arreter(self):
        if self._src: GLib.source_remove(self._src); self._src = 0
        if self._proc and self._proc.poll() is None:
            try: self._proc.terminate()
            except Exception: pass
        self._proc = None

    def ecouter(self):
        """Niveau du micro : pw-record en mono 8 kHz, crête toutes les 50 ms (dans un fil, sans bloquer le bureau)."""
        if S.DEMO or not any(os.access(os.path.join(p, "pw-record"), os.X_OK) for p in os.environ.get("PATH", "/usr/bin").split(":")): return
        try:
            self._proc = subprocess.Popen(["pw-record", "--rate", "8000", "--channels", "1", "--format", "s16", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            return
        def fil(p=self._proc):
            while p.poll() is None:
                d = p.stdout.read(800)
                if not d: break
                n = len(d) // 2
                if not n: continue
                crete = max(abs(x) for x in struct.unpack("<%dh" % n, d[:n * 2])) / 32768
                self.niveau = 20 * math.log10(max(crete, 1e-5))
        self._fil = threading.Thread(target=fil, daemon=True); self._fil.start()

    def tic(self):
        t = time.time(); lt = time.localtime(t); fps = int(self.sh.cfg.get("timecode_fps", 25) or 25)
        self.l_tc.set_text("%02d:%02d:%02d:%02d" % (lt.tm_hour, lt.tm_min, lt.tm_sec, int((t % 1) * fps)))
        n = self.niveau if not S.DEMO else -18 + 6 * math.sin(t * 3)
        self.vu.set_value(max(0, min(1, (n + 60) / 60)))
        self._n += 1
        if self._n % 20 == 1: self.lent()
        return True

    def lent(self):
        """Toutes les 2 s : tally, cartes, batterie (dans un fil)."""
        def fond():
            from .ile import Ile
            return Ile.lire_tally(), cartes(), S.batterie()
        def rendu(r):
            if isinstance(r, Exception) or not self._src: return
            tl, cs, bat = r
            pgm = [x for x in (tl or []) if x[2] == "programme"]
            self.tally.set_visible(bool(pgm)); self.tally.set_text("● PGM " + " · ".join(n or "Cam %s" % k for k, n, _ in pgm) if pgm else "")
            if cs:
                n, libre = min(cs, key=lambda x: x[1]); self.l_cartes.set_text("💾 %s libres" % taille(libre)); self.l_cartes.set_tooltip_text("\n".join("%s : %s libres" % (a, taille(b)) for a, b in cs))
                (self.l_cartes.add_css_class if libre < 8 * 1024 ** 3 else self.l_cartes.remove_css_class)("bt-alerte")
            self.l_cartes.set_visible(bool(cs))
            if bat:
                self.l_bat.set_text("🔋 %d %%" % bat["pct"]); (self.l_bat.add_css_class if bat["pct"] <= 20 and not bat.get("charge") else self.l_bat.remove_css_class)("bt-alerte")
            self.l_bat.set_visible(bool(bat))
        S.en_fond(fond, rendu)


CSS = """
.barre-tournage {{ background: alpha({rouge},0.10); border: 1px solid alpha({rouge},0.35); border-radius: 10px; padding: 2px 10px; margin: 0 6px; }}
.bt-tc {{ font-family: "IBM Plex Mono", monospace; font-size: 15px; font-weight: 700; color: {acc}; }}
.bt-tally {{ background: #e5534b; color: #fff; border-radius: 6px; padding: 1px 8px; font-weight: 700; font-size: 12px; }}
.bt-info {{ font-size: 12px; font-weight: 600; }}
.bt-alerte {{ color: #ff6b6b; }}
levelbar.bt-vu block.vert {{ background: #69db7c; }} levelbar.bt-vu block.jaune {{ background: #ffd43b; }} levelbar.bt-vu block.rouge {{ background: #ff6b6b; }}
levelbar.bt-vu trough {{ min-height: 6px; }} levelbar.bt-vu block {{ min-height: 6px; border-radius: 3px; }}
"""
