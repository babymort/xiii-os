# OS XIII — Diffuser XIII : diffuser l'écran sur le réseau (navigateur d'une TV, d'un téléphone, d'un autre PC) ou vers
# une TV Chromecast / Miracast. Façon Google Home : un bouton, une adresse, un QR code.
# Application développée par Matthieu Lamotte.
import sys, os, shutil, subprocess
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf
from . import systeme as S
from .appli import preparer, page
from .diffusion import Diffusion, PORT
from .ui import *

QUALITES = [("720p · 15 images/s", 1280, 15), ("1080p · 15 images/s", 1920, 15), ("720p · 25 images/s (fluide)", 1280, 25), ("480p · 10 images/s (réseau lent)", 854, 10)]
CSS = ".qr-diff { background: #fff; border-radius: 12px; padding: 8px; } .url-diff { font-family: 'IBM Plex Mono', monospace; font-size: 15px; font-weight: 600; }"


class Diffuser(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.diffuser")
        self.diff = None

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(CSS)
        self.win = Gtk.ApplicationWindow(application=self, title="Diffuser XIII"); self.win.set_default_size(820, 700)
        self.win.connect("close-request", lambda *_: (self.arreter(), False)[1])
        sc, v = page("Diffuser l'écran", "Sur une TV, un téléphone ou un autre PC du même réseau, sans rien installer de leur côté", "cast")
        self.win.set_child(sc)
        # ---- navigateur
        c = boite(True, 10, "carte"); v.append(c)
        c.append(label("Dans un navigateur du réseau", "gras")); c.append(label("TV connectée, téléphone, tablette, autre ordinateur : ouvrez l'adresse ou scannez le QR code.", "petit", "attenue", wrap=True))
        r = boite(False, 10); c.append(r)
        self.ecrans = [e["nom"] for e in S.ecrans()]
        self.d_src = Gtk.DropDown.new_from_strings((["Écran " + n for n in self.ecrans] if len(self.ecrans) > 1 else ["Tout l'écran"]) + ["Une zone de l'écran…"]); r.append(self.d_src)
        self.d_q = Gtk.DropDown.new_from_strings([q[0] for q in QUALITES]); r.append(self.d_q)
        self.b = bouton("Diffuser", "cast", "pilule", rappel=self.basculer); r.append(self.b)
        self.etat = boite(False, 18); self.etat.set_visible(False); c.append(self.etat)
        self.qr = Gtk.Picture(); self.qr.set_size_request(180, 180); self.qr.set_can_shrink(True); q = boite(False, 0, "qr-diff"); q.append(self.qr); self.etat.append(q)
        col = boite(True, 6, valign=Gtk.Align.CENTER); self.etat.append(col)
        self.l_url = label("", "url-diff", selectable=True); col.append(self.l_url)
        self.l_info = label("", "petit", "attenue", wrap=True); col.append(self.l_info)
        rb = boite(False, 8); col.append(rb)
        rb.append(bouton("Copier l'adresse", "copy", "fantome", rappel=lambda: Gdk.Display.get_default().get_clipboard().set_text(self.l_url.get_text())))
        rb.append(bouton("Voir ici", "external-link", "fantome", rappel=lambda: S.detacher(["xdg-open", self.l_url.get_text()])))
        # ---- TV
        c2 = boite(True, 10, "carte"); v.append(c2)
        c2.append(label("Vers une TV Chromecast ou Miracast", "gras"))
        if shutil.which("gnome-network-displays"):
            c2.append(label("« Écrans réseau » trouve les TV et clés Chromecast du réseau et les écrans Miracast (Wi-Fi Direct), puis y envoie l'écran.", "petit", "attenue", wrap=True))
            c2.append(bouton("Chercher une TV", "tv", "pilule", rappel=lambda: S.detacher("gnome-network-displays")))
        else:
            c2.append(label("L'appli « Écrans réseau » (gnome-network-displays) n'est pas installée : faites une mise à jour d'OS XIII, ou installez-la depuis le Centre de logiciels. "
                            "En attendant, la plupart des TV connectées ouvrent l'adresse ci-dessus dans leur navigateur.", "petit", "attenue", wrap=True))
            c2.append(bouton("Ouvrir le Centre de logiciels", "download", "fantome", rappel=lambda: S.detacher("xiii-logiciels")))
        v.append(label("La diffusion reste sur le réseau local (port %d, ouvert aux appareils du réseau seulement par le pare-feu, réglable dans Paramètres › Pare-feu) : rien ne sort sur Internet. Elle s'arrête quand vous fermez cette fenêtre." % PORT, "petit", "attenue", wrap=True))
        self.win.present()

    def basculer(self):
        if self.diff: self.arreter(); return
        i = self.d_src.get_selected(); geo = None; sortie = None
        if i == len(self.ecrans) if len(self.ecrans) > 1 else i == 1:
            try: geo = subprocess.run(["slurp"], capture_output=True, text=True, timeout=60).stdout.strip() or None
            except Exception: geo = None
            if not geo: return
        elif len(self.ecrans) > 1:
            sortie = self.ecrans[i]
        nom, larg, ips = QUALITES[self.d_q.get_selected()]
        self.diff = Diffusion(PORT, sortie, larg, ips, geo, os.uname().nodename)
        try:
            url = self.diff.demarrer()
        except OSError as e:
            self.diff = None; self.l_info.set_text("Impossible de démarrer : %s" % e); self.etat.set_visible(True); return
        self.l_url.set_text(url)
        try:
            png = subprocess.run(["qrencode", "-o", "-", "-s", "8", "-m", "1", url], capture_output=True).stdout
            ld = GdkPixbuf.PixbufLoader(); ld.write(png); ld.close(); self.qr.set_paintable(Gdk.Texture.new_for_pixbuf(ld.get_pixbuf()))
        except Exception:
            pass
        self.etat.set_visible(True); self.b.set_child(None); self.b.set_label("Arrêter la diffusion")
        self._src = GLib.timeout_add_seconds(1, self.tic); self.tic()

    def tic(self):
        if not self.diff: return False
        n = self.diff.spectateurs
        self.l_info.set_text(("%d spectateur%s" % (n, "s" if n > 1 else "") if n else "En attente d'un spectateur…") + " · %d images envoyées · capture : %s" % (self.diff.n, self.diff.moteur or "…"))
        return True

    def arreter(self):
        if not self.diff: return
        self.diff.arreter(); self.diff = None
        self.etat.set_visible(False); self.b.set_label("Diffuser")


def main():
    sys.exit(Diffuser().run(sys.argv[:1]))
