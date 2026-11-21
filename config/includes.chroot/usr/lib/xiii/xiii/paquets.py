# OS XIII — Installer un logiciel Linux (.deb) d'un double-clic : nom, version, description, dépendances installées toutes seules.
# Application développée par Matthieu Lamotte.
import os, sys, re, subprocess, shutil
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib
from .appli import preparer
from .ui import *
from . import systeme as S

def infos(f):
    r = subprocess.run(["dpkg-deb", "-f", f, "Package", "Version", "Architecture", "Description", "Installed-Size", "Maintainer", "Depends"], capture_output=True, text=True)
    d, cle = {}, None
    for l in r.stdout.splitlines():
        m = re.match(r"^([A-Za-z-]+): ?(.*)$", l)
        if m: cle = m.group(1); d[cle] = m.group(2)
        elif cle: d[cle] += "\n" + l.strip(" .")
    return d

def installe(paquet):
    r = subprocess.run(["dpkg-query", "-W", "-f=${Status} ${Version}", paquet], capture_output=True, text=True)
    return r.stdout.split()[-1] if "install ok installed" in r.stdout else None

def lanceur(paquet):
    """Application du menu installée par ce paquet."""
    r = subprocess.run(["dpkg", "-L", paquet], capture_output=True, text=True)
    for l in r.stdout.splitlines():
        if l.startswith("/usr/share/applications/") and l.endswith(".desktop"): return os.path.basename(l)
    return None

class Paquets(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.paquets", flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self):
        preparer()
        w = Gtk.ApplicationWindow(application=self, title="Installer un logiciel", default_width=560, default_height=420)
        v = boite(True, 12, margin_start=22, margin_end=22, margin_top=18, margin_bottom=18); w.set_child(v)
        v.append(label("Installer un logiciel Linux", "page-titre"))
        v.append(label("Double-cliquez sur un fichier .deb dans Fichiers, ou choisissez-le ici. Pour chercher un logiciel : Centre de logiciels XIII.", "attenue", wrap=True))
        def choisir():
            d = Gtk.FileDialog(title="Choisir un fichier .deb")
            def fin(dl, res):
                try: g = dl.open_finish(res)
                except GLib.Error: return
                w.close(); self.fenetre(g.get_path())
            d.open(w, None, fin)
        r = boite(False, 8)
        r.append(bouton("Choisir un fichier .deb…", "folder-open", "pilule", rappel=choisir))
        r.append(bouton("Centre de logiciels", "layout-grid", "fantome", rappel=lambda: (S.detacher("xiii-logiciels"), w.close())))
        v.append(r); w.present()

    def do_open(self, fichiers, n, hint):
        for f in fichiers: self.fenetre(f.get_path())

    def fenetre(self, f):
        preparer()
        w = Gtk.ApplicationWindow(application=self, title="Installer un logiciel", default_width=600, default_height=480)
        v = boite(True, 12, margin_start=22, margin_end=22, margin_top=18, margin_bottom=18); w.set_child(v)
        d = infos(f)
        if not d.get("Package"):
            v.append(label("Ce fichier n'est pas un paquet .deb valide.", "page-titre")); w.present(); return
        nom = d["Package"]; desc = (d.get("Description") or "").split("\n", 1)
        h = boite(False, 14); h.append(ico("package", 48, "c"))
        t = boite(True, 2, hexpand=True); t.append(label(nom, "page-titre", ellipsize=True)); t.append(label(desc[0], "attenue", wrap=True)); h.append(t); v.append(h)
        arch = subprocess.run(["dpkg", "--print-architecture"], capture_output=True, text=True).stdout.strip()
        deja = installe(nom)
        lignes = [("Version", d.get("Version", "?")), ("Taille installée", S.humain(int(d.get("Installed-Size", "0") or 0) * 1024)),
                  ("Éditeur", (d.get("Maintainer") or "—").split("<")[0].strip()), ("Déjà installé", ("version " + deja) if deja else "non")]
        for k, val in lignes:
            r = boite(False, 8); r.append(label(k, "attenue", hexpand=True)); r.append(label(val, selectable=True)); v.append(r)
        if len(desc) > 1:
            sc = defilant(label(desc[1].strip(), "petit", wrap=True, xalign=0)); sc.set_vexpand(True); v.append(sc)
        else:
            v.append(Gtk.Box(vexpand=True))
        ok_arch = d.get("Architecture") in ("all", arch)
        if not ok_arch:
            v.append(label("Ce paquet est fait pour « %s » : il ne fonctionnera pas sur ce PC (%s)." % (d.get("Architecture"), arch), "attenue", wrap=True))
        v.append(label("Installez seulement des logiciels venant d'une source de confiance : un paquet .deb a accès à tout l'ordinateur.", "petit", "attenue", wrap=True))
        pb = Gtk.ProgressBar(); pb.set_visible(False); v.append(pb)
        etat = label("", "attenue", wrap=True); v.append(etat)
        bas = boite(False, 8, halign=Gtk.Align.END)
        def installer():
            b.set_sensitive(False); pb.set_visible(True); etat.set_text("Installation (mot de passe administrateur)… les dépendances sont téléchargées si besoin")
            src = GLib.timeout_add(120, lambda: (pb.pulse(), True)[1])
            def tache():
                tmp = "/tmp/xiii-paquet-%d.deb" % os.getpid(); shutil.copy(f, tmp); os.chmod(tmp, 0o644)   # lisible par apt (_apt)
                r = subprocess.run(["pkexec", "sh", "-c", "apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y '%s'" % tmp], capture_output=True, text=True)
                try: os.remove(tmp)
                except OSError: pass
                return r
            def fini(r):
                GLib.source_remove(src); pb.set_fraction(1 if r.returncode == 0 else 0)
                if r.returncode == 0:
                    etat.set_text("%s est installé." % nom)
                    l = lanceur(nom)
                    if l: bas.prepend(bouton("Ouvrir", "app-window", "pilule", rappel=lambda: (S.detacher(["gtk-launch", l]), w.close())))
                    b.set_visible(False)
                elif r.returncode in (126, 127):
                    etat.set_text("Installation annulée."); b.set_sensitive(True)
                else:
                    err = [x for x in (r.stdout + r.stderr).splitlines() if x.startswith("E:")]
                    etat.set_text("Échec : " + (err[-1][2:].strip() if err else "dépendances impossibles à installer (connexion Internet ?)")); b.set_sensitive(True)
            S.en_fond(tache, fini)
        b = bouton("Réinstaller" if deja else "Installer", "download", "pilule", rappel=installer); b.set_sensitive(ok_arch)
        bas.append(bouton("Fermer", None, "fantome", rappel=w.close)); bas.append(b); v.append(bas)
        w.present()

def main():
    sys.exit(Paquets().run(sys.argv))
