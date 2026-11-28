# OS XIII — Assistance XIII (comme « Assistance rapide » de Windows et le partage d'écran de macOS) :
#   Recevoir de l'aide — sur le même réseau : partage de l'écran avec contrôle (wayvnc), code à 6 chiffres valable
#                         tant que la fenêtre reste ouverte ; par Internet : RustDesk (pack conseillé, téléchargé au 1er usage).
#   Aider quelqu'un     — adresse + code (visionneuse VNC), ou identifiant RustDesk.
# La session s'arrête dès qu'on ferme la fenêtre ou qu'on clique sur « Arrêter le partage ».
# Application développée par Matthieu Lamotte.
import os, sys, random, socket, shutil, subprocess, tempfile
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import systeme as S

PORT = 5900


def ip_locale():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("10.255.255.255", 1)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"


def config_wayvnc(dossier, code):
    """Fichiers de wayvnc : certificat TLS jetable (VeNCrypt) + identifiant « xiii » et le code à 6 chiffres."""
    cle, cert = os.path.join(dossier, "cle.pem"), os.path.join(dossier, "cert.pem")
    if not os.path.exists(cert):
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", cle, "-out", cert, "-days", "2", "-subj", "/CN=OS XIII"],
                       capture_output=True, timeout=60)
    c = os.path.join(dossier, "config")
    open(c, "w").write("address=0.0.0.0\nport=%d\nenable_auth=true\nusername=xiii\npassword=%s\nprivate_key_file=%s\ncertificate_file=%s\n" % (PORT, code, cle, cert))
    os.chmod(c, 0o600)
    return c


def visionneuse(adresse):
    """Commande pour se connecter à « ip » ou « ip:port »."""
    h, _, p = adresse.strip().partition(":"); p = int(p) if p.isdigit() else PORT
    if shutil.which("gvncviewer"): return ["gvncviewer", "%s:%d" % (h, p - 5900 if 5900 <= p < 6000 else p)]
    if shutil.which("remmina"): return ["remmina", "-c", "vnc://xiii@%s:%d" % (h, p)]
    return None


class Assistance(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.assistance")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        from .ui import boite, label, bouton, ico
        from .appli import preparer
        self.U = (boite, label, bouton, ico)
        preparer(""".carte-a { background: alpha(currentColor, .05); border-radius: 18px; padding: 18px; }
                    .code { font-family: "IBM Plex Mono", monospace; font-size: 40px; letter-spacing: 6px; }""")
        self.proc = None; self.tmp = tempfile.mkdtemp(prefix="xiii-assistance-")
        self.win = Gtk.ApplicationWindow(application=self, title="Assistance XIII"); self.win.set_default_size(820, 520)
        r = boite(False, 18, margin_start=22, margin_end=22, margin_top=20, margin_bottom=20, homogeneous=True)
        # ---- recevoir
        g = boite(True, 10, "carte-a"); h = boite(False, 10); h.append(ico("life-buoy", 28, "c")); h.append(label("Recevoir de l'aide", "page-titre")); g.append(h)
        g.append(label("Sur le même réseau (bureau, maison) : donnez l'adresse et le code à la personne qui vous aide. "
                       "Elle voit votre écran et peut prendre la souris tant que cette fenêtre reste ouverte.", "attenue", wrap=True))
        self.l_code = label("— — —", "code", xalign=.5); self.l_adr = label("", "attenue", xalign=.5, wrap=True)
        g.append(self.l_code); g.append(self.l_adr)
        self.b_partage = bouton("Partager mon écran", "screen-share", "pilule", rappel=self.basculer_partage); g.append(self.b_partage)
        g.append(label("Par Internet (n'importe où) : RustDesk affiche votre identifiant et un mot de passe à donner.", "attenue", wrap=True))
        g.append(bouton("Ouvrir RustDesk", "globe", "fantome", rappel=lambda: S.detacher(["xiii-pack", "rustdesk"])))
        r.append(g)
        # ---- aider
        a = boite(True, 10, "carte-a"); h = boite(False, 10); h.append(ico("hand-helping" if os.path.exists("/usr/share/xiii/lucide/hand-helping.svg") else "users", 28, "c"))
        h.append(label("Aider quelqu'un", "page-titre")); a.append(h)
        a.append(label("Tapez l'adresse affichée sur son écran (ex. 192.168.1.20), puis son code à 6 chiffres quand il est demandé "
                       "(identifiant : xiii).", "attenue", wrap=True))
        self.e_adr = Gtk.Entry(placeholder_text="Adresse (ex. 192.168.1.20)"); a.append(self.e_adr)
        self.e_adr.connect("activate", lambda *_: self.aider())
        a.append(bouton("Se connecter", "monitor-play" if os.path.exists("/usr/share/xiii/lucide/monitor-play.svg") else "monitor", "pilule", rappel=self.aider))
        self.l_aide = label("", "attenue", wrap=True); a.append(self.l_aide)
        a.append(label("Par Internet : demandez-lui son identifiant RustDesk et saisissez-le dans RustDesk.", "attenue", wrap=True))
        a.append(bouton("Ouvrir RustDesk", "globe", "fantome", rappel=lambda: S.detacher(["xiii-pack", "rustdesk"])))
        r.append(a)
        self.win.set_child(r); self.win.present()
        self.win.connect("close-request", lambda *_: (self.arreter(), False)[1])

    def basculer_partage(self):
        if self.proc: self.arreter(); return
        if not shutil.which("wayvnc"):
            self.l_adr.set_text("Le partage d'écran (wayvnc) n'est pas installé : faites une mise à jour d'OS XIII, ou utilisez RustDesk."); return
        code = "%06d" % random.SystemRandom().randrange(10 ** 6)
        try: c = config_wayvnc(self.tmp, code)
        except Exception as e: self.l_adr.set_text("Impossible de préparer le partage : %s" % e); return
        self.proc = subprocess.Popen(["wayvnc", "-C", c, "-r"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
        GLib.timeout_add(1200, self._verifier)
        self.l_code.set_text(code[:3] + " " + code[3:])
        self.l_adr.set_text("Adresse : %s   ·   identifiant : xiii\nVotre écran est partagé. Fermez cette fenêtre pour arrêter." % ip_locale())
        self.b_partage.get_child().get_last_child().set_text("Arrêter le partage")
        S.detacher(["notify-send", "-a", "Assistance XIII", "-i", "screen-share", "-u", "critical", "Votre écran est partagé",
                    "Code %s — fermez Assistance XIII pour arrêter." % code])

    def _verifier(self):
        if self.proc and self.proc.poll() is not None:
            err = (self.proc.stderr.read() or b"").decode(errors="replace").strip().splitlines()[-1:] if self.proc.stderr else []
            self.proc = None; self.l_code.set_text("— — —"); self.b_partage.get_child().get_last_child().set_text("Partager mon écran")
            self.l_adr.set_text("Le partage s'est arrêté%s." % ((" : " + err[0]) if err else ""))
        return False

    def arreter(self):
        if self.proc:
            try: os.killpg(self.proc.pid, 15)
            except Exception: pass
            self.proc = None
        if hasattr(self, "l_code"):
            self.l_code.set_text("— — —"); self.l_adr.set_text("Partage arrêté."); self.b_partage.get_child().get_last_child().set_text("Partager mon écran")

    def aider(self):
        adr = self.e_adr.get_text().strip()
        if not adr: self.e_adr.grab_focus(); return
        cmd = visionneuse(adr)
        if not cmd: self.l_aide.set_text("Aucune visionneuse VNC installée : faites une mise à jour d'OS XIII, ou utilisez RustDesk."); return
        S.detacher(cmd); self.l_aide.set_text("Connexion à %s… le code vous sera demandé." % adr)


def main():
    sys.exit(Assistance().run(sys.argv))
