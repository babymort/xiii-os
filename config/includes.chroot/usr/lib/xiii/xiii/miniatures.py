# OS XIII — miniatures des fenêtres (vue des tâches, aperçu au survol de la barre).
# labwc 0.8 n'offre pas encore la capture fenêtre par fenêtre : quand une fenêtre passe au premier plan,
# on photographie l'écran en petit (grim -s 0.25) et on range l'image sous l'identifiant de la fenêtre.
# Application développée par Matthieu Lamotte.
import os, subprocess, shutil, time
from gi.repository import GLib

DOSSIER = os.path.expanduser("~/.cache/xiii/miniatures")

class Miniatures:
    def __init__(self, shell):
        self.shell = shell; self.dernier = None; self.src = 0; self.vu = {}
        os.makedirs(DOSSIER, exist_ok=True)
        for f in os.listdir(DOSSIER):                     # les identifiants changent à chaque session
            try: os.remove(os.path.join(DOSSIER, f))
            except OSError: pass
        self.ok = bool(shutil.which("grim"))
        if self.ok: GLib.timeout_add_seconds(12, self._rafraichir)

    def chemin(self, f):
        p = os.path.join(DOSSIER, "%d.png" % f.id)
        return p if os.path.exists(p) else None

    def changement(self, fenetres):
        """Appelé à chaque mise à jour de la liste des fenêtres."""
        if not self.ok: return
        vivantes = {f.id for f in fenetres}
        for i in list(self.vu):
            if i not in vivantes:
                self.vu.pop(i, None)
                try: os.remove(os.path.join(DOSSIER, "%d.png" % i))
                except OSError: pass
        a = next((f for f in fenetres if f.active and not f.reduite), None)
        if a and a.id != self.dernier:
            self.dernier = a.id
            if self.src: GLib.source_remove(self.src)
            self.src = GLib.timeout_add(700, self._capturer, a.id)   # laisse le temps à la fenêtre de se dessiner

    def _rafraichir(self):
        if self.dernier and self.dernier in self.vu and time.time() - self.vu[self.dernier] > 10:
            self._capturer(self.dernier)
        return True

    def _capturer(self, fid):
        self.src = 0
        sh = self.shell
        if sh.ouvert or getattr(sh, "vue_ouverte", False): return False   # pas de menu XIII sur la photo
        fm = sh.fenetres
        a = fm.active() if fm and fm.ok else None
        if not a or a.id != fid or a.reduite: return False
        dest = os.path.join(DOSSIER, "%d.png" % fid)
        try:
            subprocess.Popen(["sh", "-c", 'grim -s 0.25 -l 1 "$1.tmp" && mv "$1.tmp" "$1"', "-", dest],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.vu[fid] = time.time()
        except OSError:
            pass
        return False
