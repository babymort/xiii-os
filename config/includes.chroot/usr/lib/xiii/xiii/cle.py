# OS XIII — Clé OS XIII : crée une clé USB à emporter en tournage, qui démarre OS XIII sur n'importe quel PC
# et garde vos fichiers, réglages et logiciels d'une fois sur l'autre (persistance).
# Application développée par Matthieu Lamotte.
import os, sys, json, glob, subprocess, threading
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gio
from . import config, systeme as S
from .ui import *
from .appli import preparer


def cles():
    """Clés USB / disques amovibles branchés : [{dev, nom, taille}]"""
    if S.DEMO: return [{"dev": "/dev/sdb", "nom": "SanDisk Ultra", "taille": 64 * 10**9}]
    try: d = json.loads(S.out(["lsblk", "-J", "-b", "-d", "-o", "NAME,SIZE,MODEL,VENDOR,TRAN,RM,TYPE"]) or "{}")
    except ValueError: return []
    r = []
    for b in d.get("blockdevices", []):
        if b.get("type") == "disk" and (b.get("tran") == "usb" or b.get("rm") in (True, 1, "1")) and int(b.get("size") or 0) > 0:
            r.append({"dev": "/dev/" + b["name"], "nom": " ".join(x.strip() for x in (b.get("vendor") or "", b.get("model") or "") if x and x.strip()) or b["name"], "taille": int(b["size"])})
    return r


def images():
    """Images OS XIII trouvées (Téléchargements, Bureau, dossier perso), la plus récente d'abord."""
    L = []
    for d in ("~/Téléchargements", "~/Downloads", "~/Bureau", "~"):
        L += glob.glob(os.path.expanduser(d + "/OS-XIII*.iso"))
    return sorted(set(L), key=os.path.getmtime, reverse=True)


def main():
    if sys.argv[1:2] == ["--lister"]:
        print(json.dumps({"cles": cles(), "images": images()}, ensure_ascii=False, indent=1)); return
    app = Gtk.Application(application_id="fr.xiii.cle", flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.connect("activate", Fenetre)
    sys.exit(app.run([]))


class Fenetre:
    def __init__(self, app):
        preparer()
        self.win = Gtk.ApplicationWindow(application=app, title="Clé OS XIII", default_width=620, default_height=560)
        self.iso = (images() or [None])[0]
        v = boite(True, 14, margin_top=26, margin_bottom=22, margin_start=30, margin_end=30)
        h = boite(False, 12); h.append(ico("usb", 34, "c")); t = boite(True, 2)
        t.append(label("Clé OS XIII", "titre-astoria", "grand-titre")); t.append(label("Démarre OS XIII sur n'importe quel PC, et garde vos fichiers et réglages", "attenue", wrap=True))
        h.append(t); v.append(h)
        v.append(label("1. Image OS XIII", "gras", margin_top=8))
        self.l_iso = label(os.path.basename(self.iso) if self.iso else "Aucune image trouvée dans Téléchargements", "attenue", ellipsize=True, hexpand=True)
        r = boite(False, 8); r.append(self.l_iso); r.append(bouton("Choisir…", "folder-open", "fantome", rappel=self.choisir)); v.append(r)
        v.append(label("2. Clé USB", "gras", margin_top=8))
        self.liste = boite(True, 6); v.append(self.liste)
        v.append(bouton("Actualiser", "refresh-cw", "fantome", rappel=self.remplir))
        v.append(label("3. Options", "gras", margin_top=8))
        r = boite(False, 10); self.sw = Gtk.Switch(active=True, valign=Gtk.Align.CENTER); r.append(self.sw)
        r.append(label("Garder mes fichiers, réglages et logiciels sur la clé (persistance)", wrap=True, hexpand=True)); v.append(r)
        self.etat = label("", "attenue", wrap=True); self.barre = Gtk.ProgressBar(visible=False)
        v.append(self.barre); v.append(self.etat)
        self.go = bouton("Créer la clé", "usb", "pilule", rappel=self.creer); self.go.set_halign(Gtk.Align.END); v.append(self.go)
        self.choix = None
        self.win.set_child(defilant(v)); self.remplir(); self.win.present()

    def remplir(self):
        vider(self.liste); L = cles(); grp = None
        if not L: self.liste.append(label("Branchez une clé USB (8 Go ou plus conseillés).", "attenue")); self.choix = None
        for k in L:
            b = Gtk.CheckButton(label="%s — %s  (%s)" % (k["nom"], S.humain(k["taille"]), k["dev"]), group=grp); grp = grp or b
            b.connect("toggled", lambda w, k=k: w.get_active() and setattr(self, "choix", k)); self.liste.append(b)
            if len(L) == 1: b.set_active(True)

    def choisir(self):
        d = Gtk.FileDialog(title="Image OS XIII (.iso)")
        f = Gtk.FileFilter(); f.set_name("Images ISO"); f.add_pattern("*.iso"); st = Gio.ListStore.new(Gtk.FileFilter); st.append(f); d.set_filters(st)
        def fini(d, r):
            try: self.iso = d.open_finish(r).get_path(); self.l_iso.set_text(os.path.basename(self.iso))
            except GLib.Error: pass
        d.open(self.win, None, fini)

    def creer(self):
        if not self.iso: self.etat.set_text("Choisissez d'abord une image OS XIII (.iso)."); return
        if not self.choix: self.etat.set_text("Choisissez la clé USB."); return
        k = self.choix
        dl = Gtk.AlertDialog(message="Effacer « %s » ?" % k["nom"], detail="Tout ce qui est sur cette clé (%s) sera remplacé par OS XIII. Cette opération ne peut pas être annulée." % S.humain(k["taille"]),
                             buttons=["Annuler", "Effacer et créer la clé"], cancel_button=0, default_button=0)
        dl.choose(self.win, None, lambda d, r: d.choose_finish(r) == 1 and self.lancer(k))

    def lancer(self, k):
        self.go.set_sensitive(False); self.barre.set_visible(True); self.barre.set_fraction(0)
        cmd = ["pkexec", "xiii-cle-ecrire", self.iso, k["dev"]] + ([] if self.sw.get_active() else ["--sans-persistance"])
        def tache():
            if S.DEMO:
                for i in range(0, 101, 20): GLib.idle_add(self.barre.set_fraction, i / 100)
                GLib.idle_add(self.fin, True, "démo"); return
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); dernier = ""
            for l in p.stdout:
                l = l.strip()
                if l.startswith("% "): GLib.idle_add(self.barre.set_fraction, int(l[2:]) / 100)
                elif l.startswith(("ETAPE ", "INFO ", "ERREUR ")): dernier = l.split(" ", 1)[1]; GLib.idle_add(self.etat.set_text, dernier)
            GLib.idle_add(self.fin, p.wait() == 0, dernier)
        threading.Thread(target=tache, daemon=True).start()

    def fin(self, ok, msg):
        self.go.set_sensitive(True)
        self.etat.set_text("Clé prête. Branchez-la sur un PC et démarrez dessus (touche F12, F11 ou Échap au démarrage selon les PC)." if ok else "Échec : " + msg)
        if ok: S.detacher(["notify-send", "-a", "Clé OS XIII", "Clé prête", "Vous pouvez la retirer."])
