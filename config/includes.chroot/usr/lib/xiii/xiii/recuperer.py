# OS XIII — Récupérer mes fichiers : retrouve les dossiers personnels d'un Windows ou d'un Mac (sur ce PC en double
# démarrage, ou sur un disque branché), et copie Bureau, Documents, Images, Musique, Vidéos, Téléchargements dans
# le dossier personnel, rangés dans « Récupéré de Windows (nom) » pour ne rien écraser. Rien n'est modifié sur l'ancien disque.
# Application développée par Matthieu Lamotte.
import os, sys, json, subprocess, shutil, threading, time
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import systeme as S
from .ui import *
from .appli import preparer, page

# dossier de l'ancien système → dossier XDG d'OS XIII
DOSSIERS = [("Desktop", "DESKTOP", "Bureau"), ("Documents", "DOCUMENTS", "Documents"), ("Pictures", "PICTURES", "Images"),
            ("Music", "MUSIC", "Musique"), ("Videos", "VIDEOS", "Vidéos"), ("Movies", "VIDEOS", "Vidéos"), ("Downloads", "DOWNLOAD", "Téléchargements")]
IGNORER_COMPTES = {"Public", "Default", "Default User", "All Users", "defaultuser0", "Shared", "Guest", ".localized", "WsiAccount"}

def partitions():
    """Partitions Windows (NTFS) et Mac (HFS+, APFS) de tous les disques."""
    try: j = json.loads(subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,FSTYPE,SIZE,LABEL,MOUNTPOINT,TYPE"], capture_output=True, text=True, timeout=10).stdout)
    except Exception: return []
    out = []
    def tour(L):
        for d in L:
            if d.get("fstype") in ("ntfs", "ntfs3", "hfsplus", "apfs", "exfat"): out.append(d)
            tour(d.get("children") or [])
    tour(j.get("blockdevices", []))
    return out

def monter(dev):
    """Monte en lecture seule (rien n'est écrit sur l'ancien système). Renvoie le point de montage."""
    m = subprocess.run(["findmnt", "-n", "-o", "TARGET", "-S", dev], capture_output=True, text=True).stdout.strip().splitlines()
    if m: return m[0]
    r = subprocess.run(["udisksctl", "mount", "-b", dev, "-o", "ro"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0: raise RuntimeError((r.stderr or r.stdout).strip()[:200] or "montage impossible")
    return r.stdout.split(" at ")[-1].strip().rstrip(".")

def comptes(racine):
    """[(systeme, nom du compte, chemin)] : C:\\Users\\<nom> (Windows) ou /Users/<nom> (Mac)."""
    out = []
    for base, sysn in (("Users", "Windows"), ("Documents and Settings", "Windows")):
        p = os.path.join(racine, base)
        if not os.path.isdir(p): continue
        for n in sorted(os.listdir(p)):
            q = os.path.join(p, n)
            if n in IGNORER_COMPTES or n.startswith(".") or not os.path.isdir(q): continue
            if any(os.path.isdir(os.path.join(q, d[0])) for d in DOSSIERS):
                mac = os.path.isdir(os.path.join(q, "Library")) and not os.path.isdir(os.path.join(q, "AppData"))
                out.append(("Mac" if mac else sysn, n, q))
    return out

def taille(p, limite=None):
    t = 0
    for r, ds, fs in os.walk(p):
        ds[:] = [d for d in ds if not d.startswith(".") and d not in ("AppData", "Library")]
        for f in fs:
            try: t += os.lstat(os.path.join(r, f)).st_size
            except OSError: pass
    return t

def destination(xdg, nom_compte, sysn):
    base = GLib.get_user_special_dir(getattr(GLib.UserDirectory, "DIRECTORY_" + xdg)) or os.path.expanduser("~")
    return os.path.join(base, "Récupéré de %s (%s)" % (sysn, nom_compte))


class Recuperer(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.recuperer"); self.stop = False

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer()
        self.win = Gtk.ApplicationWindow(application=self, title="Récupérer mes fichiers", default_width=760, default_height=620)
        sc, self.v = page("Récupérer mes fichiers", "Depuis un ancien Windows ou Mac : sur ce PC (double démarrage) ou sur un disque branché. Rien n'est modifié sur l'ancien disque.", "folder-input")
        self.win.set_child(sc); self.win.present()
        self.zone = boite(True, 10); self.v.append(self.zone)
        self.chercher()

    def chercher(self):
        vider(self.zone); self.zone.append(label("Recherche des anciens systèmes…", "attenue"))
        def tache():
            L = []
            for d in partitions():
                if d.get("fstype") == "apfs":
                    L.append((d, None, "Disque Mac récent (APFS) : Linux ne sait pas encore le lire. Copiez vos fichiers sur un disque externe depuis le Mac.")); continue
                try: m = monter(d["path"])
                except Exception as e: L.append((d, None, "Impossible d'ouvrir : %s" % e)); continue
                for c in comptes(m): L.append((d, c, None))
            return L
        S.en_fond(tache, self.afficher)

    def afficher(self, L):
        vider(self.zone)
        if isinstance(L, Exception) or not L:
            self.zone.append(label("Aucun ancien Windows ou Mac trouvé. Branchez le disque de l'ancien ordinateur (ou un disque de sauvegarde), puis :", "attenue", wrap=True))
            b = bouton("Chercher à nouveau", "refresh-cw", "pilule", rappel=self.chercher); b.set_halign(Gtk.Align.START); self.zone.append(b); return
        self.choix = []
        for d, c, err in L:
            nom = (d.get("label") or d.get("path")) + " · " + S.humain(int(d.get("size") or 0))
            if err:
                self.zone.append(label(nom, "section")); self.zone.append(label(err, "attenue", "petit", wrap=True)); continue
            sysn, compte, chemin = c
            self.zone.append(label("%s — compte « %s »  (%s)" % (sysn, compte, nom), "section"))
            for src, xdg, fr in DOSSIERS:
                p = os.path.join(chemin, src)
                if not os.path.isdir(p): continue
                r = boite(False, 10, "reglage")
                cb = Gtk.CheckButton(active=True); r.append(cb); r.append(ico("folder", 18, "c"))
                col = boite(True, 0, hexpand=True); col.append(label(fr, "gras")); t = label("calcul de la taille…", "petit", "attenue"); col.append(t); r.append(col)
                self.zone.append(r)
                self.choix.append((cb, p, destination(xdg, compte, sysn), fr))
                S.en_fond(taille, lambda n, t=t: t.set_text(S.humain(n) if isinstance(n, int) else "?"), p)
        self.pb = Gtk.ProgressBar(show_text=True, visible=False); self.zone.append(self.pb)
        self.b_go = bouton("Copier dans mon dossier personnel", "download", "pilule", rappel=self.copier); self.b_go.set_halign(Gtk.Align.END); self.zone.append(self.b_go)
        self.zone.append(label("Les fichiers arrivent dans des dossiers « Récupéré de Windows (nom) » : rien d'existant n'est écrasé. Les fichiers système et les logiciels ne sont pas copiés.", "attenue", "petit", wrap=True))

    def copier(self):
        L = [(p, d, fr) for cb, p, d, fr in self.choix if cb.get_active()]
        if not L: return
        self.b_go.set_sensitive(False); self.pb.set_visible(True)
        def tache():
            fichiers = []
            for p, d, fr in L:
                for r, ds, fs in os.walk(p):
                    ds[:] = [x for x in ds if not x.startswith(".") and x not in ("AppData", "Library")]
                    for f in fs:
                        if f.lower() in ("desktop.ini", "thumbs.db", ".ds_store"): continue
                        s = os.path.join(r, f)
                        try: fichiers.append((s, os.path.join(d, os.path.relpath(s, p)), os.lstat(s).st_size))
                        except OSError: pass
            tot = sum(x[2] for x in fichiers) or 1; fait = 0; err = 0; t0 = time.time()
            for i, (s, d, n) in enumerate(fichiers):
                if self.stop: break
                try:
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    if not os.path.exists(d): shutil.copy2(s, d)
                except OSError: err += 1
                fait += n
                if i % 20 == 0:
                    v = fait / max(1, time.time() - t0); reste = (tot - fait) / v if v else 0
                    GLib.idle_add(self.pb.set_fraction, fait / tot)
                    GLib.idle_add(self.pb.set_text, "%s sur %s · encore %d min" % (S.humain(fait), S.humain(tot), reste // 60 + 1))
            return len(fichiers), err, [d for _, d, _ in L]
        def fin(r):
            if isinstance(r, Exception): self.pb.set_text("Erreur : %s" % r); return
            n, err, dests = r
            self.pb.set_fraction(1); self.pb.set_text("%d fichiers récupérés%s" % (n, (" · %d illisibles" % err) if err else ""))
            S.detacher(["notify-send", "-a", "OS XIII", "-i", "folder", "-h", "string:sound-name:complete", "Fichiers récupérés", "%d fichiers copiés dans votre dossier personnel" % n])
            if dests: S.detacher(["xiii-fichiers", os.path.dirname(dests[0])])
        S.en_fond(tache, fin)

def main():
    sys.exit(Recuperer().run(sys.argv[:1]))
