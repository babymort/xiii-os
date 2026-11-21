# OS XIII — Archives XIII : ouvrir et extraire les .zip, .rar, .7z, .tar.gz… d'un double-clic, sans terminal.
# Extraction avec 7-Zip (7z) ou unar (RAR 5 compris), progression, mot de passe demandé si besoin.
# Application développée par Matthieu Lamotte.
import os, sys, re, subprocess, shutil, threading
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib
from .appli import preparer
from .ui import *
from . import systeme as S

EXT = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst", ".tgz", ".zip", ".rar", ".7z", ".tar", ".gz", ".xz", ".bz2", ".zst", ".cab", ".iso", ".lzh", ".arj")

def nom_sans_ext(f):
    b = os.path.basename(f)
    for e in EXT:
        if b.lower().endswith(e): return b[:-len(e)]
    b = re.sub(r"\.part0*1\.rar$", "", b, flags=re.I)
    return os.path.splitext(b)[0]

def contenu(f):
    """[(nom, taille)] ou None si illisible."""
    if shutil.which("7z"):
        r = subprocess.run(["7z", "l", "-slt", "-p", f], capture_output=True, text=True)
        L, cur = [], {}
        for l in r.stdout.splitlines():
            if l.startswith("Path = "): cur = {"n": l[7:]}
            elif l.startswith("Size = ") and cur: cur["t"] = int(l[7:] or 0)
            elif l.startswith("Folder = ") and cur:
                if l.endswith("-") and cur.get("n") != f: L.append((cur["n"], cur.get("t", 0)))
                cur = {}
        if L or r.returncode == 0: return L
    if shutil.which("lsar"):
        r = subprocess.run(["lsar", f], capture_output=True, text=True)
        return [(l.strip(), 0) for l in r.stdout.splitlines()[1:] if l.strip()]
    return None

class Archives(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.archives", flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self):
        self.fenetre(None)

    def do_open(self, fichiers, n, hint):
        for f in fichiers: self.fenetre(f.get_path())

    def fenetre(self, f):
        preparer()
        w = Gtk.ApplicationWindow(application=self, title="Archives XIII", default_width=640, default_height=520)
        v = boite(True, 12, margin_start=22, margin_end=22, margin_top=18, margin_bottom=18)
        w.set_child(v)
        if not f:
            v.append(label("Archives XIII", "page-titre"))
            v.append(label("Double-cliquez sur un .zip, .rar, .7z ou .tar.gz dans Fichiers, ou choisissez-le ici.", "attenue", wrap=True))
            def choisir():
                d = Gtk.FileDialog(title="Ouvrir une archive")
                d.open(w, None, lambda dl, res: (lambda g: (w.close(), self.fenetre(g.get_path())) if g else None)(self._fin(dl, res)))
            b = bouton("Choisir une archive…", "folder-open", "pilule", rappel=choisir); b.set_halign(Gtk.Align.START); v.append(b)
            w.present(); return
        h = boite(False, 12); h.append(ico("archive", 40, "c"))
        t = boite(True, 2, hexpand=True); t.append(label(os.path.basename(f), "page-titre", ellipsize=True)); t.append(label(S.humain(os.path.getsize(f)) + " · " + os.path.dirname(f).replace(os.path.expanduser("~"), "~"), "attenue")); h.append(t)
        v.append(h)
        liste = boite(True, 2); sc = defilant(liste); sc.set_vexpand(True); v.append(sc)
        liste.append(label("Lecture du contenu…", "attenue"))
        def rendu(L):
            vider(liste)
            if L is None: liste.append(label("Impossible de lire cette archive (format inconnu ou abîmée).", "attenue")); return
            liste.append(label("%d élément(s)" % len(L), "section"))
            for n, ta in L[:400]:
                r = boite(False, 8); r.append(ico("file", 14, "d")); r.append(label(n, hexpand=True, ellipsize=True)); r.append(label(S.humain(ta) if ta else "", "petit", "attenue")); liste.append(r)
            if len(L) > 400: liste.append(label("… et %d autres" % (len(L) - 400), "attenue"))
        S.en_fond(contenu, rendu, f)
        self.mdp = Gtk.PasswordEntry(placeholder_text="Mot de passe (si l'archive est protégée)", show_peek_icon=True); v.append(self.mdp)
        pb = Gtk.ProgressBar(show_text=True); pb.set_visible(False); v.append(pb)
        etat = label("", "attenue", wrap=True); v.append(etat)
        bas = boite(False, 8, halign=Gtk.Align.END)
        dest_ici = os.path.dirname(f); dest_dossier = os.path.join(dest_ici, nom_sans_ext(f))
        def extraire(dest):
            for b in (b1, b2): b.set_sensitive(False)
            pb.set_visible(True); pb.set_fraction(0); etat.set_text("Extraction vers " + dest.replace(os.path.expanduser("~"), "~"))
            mdp = self.mdp.get_text()
            def tache():
                os.makedirs(dest, exist_ok=True)
                if shutil.which("7z"):
                    cmd = ["7z", "x", "-y", "-bsp1", "-bso0", "-o" + dest, "-p" + mdp, f]
                else:
                    cmd = ["unar", "-f", "-o", dest] + (["-p", mdp] if mdp else []) + [f]
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                tout = ""
                for morceau in iter(lambda: p.stdout.read(64), ""):
                    tout += morceau
                    m = re.findall(r"(\d+)%", morceau)
                    if m: GLib.idle_add(pb.set_fraction, int(m[-1]) / 100)
                code = p.wait()
                # 7-Zip ne gère pas tous les RAR : nouvel essai avec unar
                if code and shutil.which("unar") and cmd[0] == "7z":
                    code = subprocess.run(["unar", "-f", "-o", dest] + (["-p", mdp] if mdp else []) + [f], capture_output=True).returncode
                return code, tout
            def fini(r):
                code, tout = r if isinstance(r, tuple) else (1, str(r))
                if code == 0:
                    pb.set_fraction(1); etat.set_text("Extrait dans " + dest.replace(os.path.expanduser("~"), "~"))
                    bas.prepend(bouton("Ouvrir le dossier", "folder-open", "fantome", rappel=lambda: (S.detacher(["xiii-fichiers", dest]), w.close())))
                else:
                    etat.set_text("Mot de passe incorrect ou manquant." if re.search(r"password|Wrong", tout, re.I) else "Échec de l'extraction (archive abîmée ou incomplète ?).")
                    for b in (b1, b2): b.set_sensitive(True)
            S.en_fond(tache, fini)
        b1 = bouton("Extraire ici", None, "fantome", rappel=lambda: extraire(dest_ici))
        b2 = bouton("Extraire dans « %s »" % nom_sans_ext(f)[:30], "folder-input", "pilule", rappel=lambda: extraire(dest_dossier))
        bas.append(bouton("Fermer", None, "fantome", rappel=w.close)); bas.append(b1); bas.append(b2); v.append(bas)
        w.present()

    @staticmethod
    def _fin(d, res):
        try: return d.open_finish(res)
        except GLib.Error: return None

def main():
    sys.exit(Archives().run(sys.argv))
