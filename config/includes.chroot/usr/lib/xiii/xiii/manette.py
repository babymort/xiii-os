# OS XIII — manettes (libmanette) : toutes les manettes reconnues (Xbox, PlayStation, Switch Pro, 8BitDo, génériques)
# traduites en actions simples : g d h bas a b x y menu select accueil. Répétition quand on maintient une direction.
# Sert à la Console XIII et au mode Gaming ; Select + Start (ou le bouton Accueil) quitte le jeu en cours.
# Application développée par Matthieu Lamotte.
import gi
from gi.repository import GLib
try:
    gi.require_version("Manette", "0.2")
    from gi.repository import Manette
except (ValueError, ImportError):
    Manette = None

# codes Linux (input-event-codes.h) normalisés par libmanette
BOUTONS = {304: "a", 305: "b", 307: "y", 308: "x", 310: "l", 311: "r", 314: "select", 315: "menu", 316: "accueil",
           544: "h", 545: "bas", 546: "g", 547: "d"}
DIRS = ("g", "d", "h", "bas")

class Manettes:
    def __init__(self, action, combo=None):
        """action(nom) pour chaque appui ; combo() appelé sur Select + Start ou Accueil (quitter le jeu)."""
        self.action = action; self.combo = combo; self.tenus = set(); self.rep = {}; self.axes = {}; self.appareils = []
        self.ok = Manette is not None
        if not self.ok: return
        self.mon = Manette.Monitor.new()
        it = self.mon.iterate()
        while True:
            r = it.next()
            ok, dev = r if isinstance(r, tuple) else (r is not None, r)
            if not ok or dev is None: break
            self.brancher(dev)
        self.mon.connect("device-connected", lambda m, d: self.brancher(d))

    def nombre(self): return len(self.appareils)

    def brancher(self, dev):
        self.appareils.append(dev)
        dev.connect("button-press-event", self.appui); dev.connect("button-release-event", self.relache)
        dev.connect("absolute-axis-event", self.axe); dev.connect("hat-axis-event", self.chapeau)
        dev.connect("disconnected", lambda d: self.appareils.remove(d) if d in self.appareils else None)

    def _bouton(self, ev):
        r = ev.get_button()
        b = r[1] if isinstance(r, tuple) else r
        return BOUTONS.get(b)

    def appui(self, dev, ev):
        n = self._bouton(ev)
        if not n: return
        self.tenus.add(n)
        if self.combo and (n == "accueil" or {"select", "menu"} <= self.tenus): self.combo()
        self.declencher(n)

    def relache(self, dev, ev):
        n = self._bouton(ev)
        if n: self.tenus.discard(n); self.stop(n)

    def declencher(self, n):
        self.action(n)
        if n in DIRS:
            self.stop(n)
            self.rep[n] = GLib.timeout_add(380, self._repeter, n, True)

    def _repeter(self, n, premier):
        self.action(n)
        if premier:
            self.rep[n] = GLib.timeout_add(110, self._repeter, n, False); return False
        return True

    def stop(self, n):
        s = self.rep.pop(n, None)
        if s: GLib.source_remove(s)

    def _dir(self, cle, neg, pos, v):
        """Stick ou croix analogique : seuil avec hystérésis."""
        avant = self.axes.get(cle)
        etat = neg if v < -.55 else pos if v > .55 else (avant if avant and abs(v) > .35 else None)
        if etat != avant:
            if avant: self.stop(avant); self.tenus.discard(avant)
            if etat: self.tenus.add(etat); self.declencher(etat)
            self.axes[cle] = etat

    def axe(self, dev, ev):
        r = ev.get_absolute()
        if not r or not r[0]: return
        _, a, v = r
        if a == 0: self._dir("x", "g", "d", v)
        elif a == 1: self._dir("y", "h", "bas", v)

    def chapeau(self, dev, ev):
        r = ev.get_hat()
        if not r or not r[0]: return
        _, a, v = r
        if a in (16, 0): self._dir("hx", "g", "d", v)
        elif a in (17, 1): self._dir("hy", "h", "bas", v)
