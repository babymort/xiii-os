# OS XIII — TALLY XIII : programmer un boîtier Wi-Fi (ESP32, M5Stack ATOM Matrix / Lite) par le câble USB, sans terminal.
# 1. détecte le boîtier branché, 2. installe le programme Tally XIII (esptool), 3. envoie le Wi-Fi, l'adresse de Tally XIII,
# le numéro de caméra et la luminosité (une ligne JSON sur le port série, enregistrée dans le boîtier).
# Application développée par Matthieu Lamotte.
import os, re, json, glob, time, shutil, subprocess, threading
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from .ui import *

FIRMWARE = "/usr/share/xiii/tally/firmware"


def ports():
    """[(chemin, description)] des ports série USB."""
    L = []
    for p in sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")):
        nom = os.path.basename(p); desc = ""
        try:
            d = os.path.realpath("/sys/class/tty/%s/device/../" % nom)
            for f in ("product", "../product"):
                if os.path.exists(os.path.join(d, f)): desc = open(os.path.join(d, f)).read().strip(); break
        except OSError:
            pass
        L.append((p, desc or "Port série USB"))
    return L


def esptool():
    for c in ("esptool", "esptool.py"):
        if shutil.which(c): return c
    return None


def firmware(cible):
    try:
        m = json.load(open(os.path.join(FIRMWARE, "firmware.json")))
        f = os.path.join(FIRMWARE, m[cible])
        return f if os.path.exists(f) else None
    except Exception:
        return None


def wifi_actuel():
    """(ssid, mot de passe si lisible) du Wi-Fi en cours."""
    try:
        o = subprocess.run(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"], capture_output=True, text=True, timeout=4).stdout
        ssid = next((l.split(":", 1)[1] for l in o.splitlines() if l.startswith("oui:") or l.startswith("yes:")), "")
        if not ssid: return "", ""
        mdp = subprocess.run(["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", ssid], capture_output=True, text=True, timeout=4).stdout.strip()
        return ssid, mdp
    except Exception:
        return "", ""


def dialoguer(port, ligne, attente=3.0):
    """Envoie une ligne au boîtier et renvoie sa réponse JSON (identité)."""
    import serial
    with serial.Serial(port, 115200, timeout=0.2) as s:
        s.dtr = False; s.rts = False  # ne pas redémarrer l'ESP32 à l'ouverture
        time.sleep(0.3); s.reset_input_buffer()
        s.write((ligne + "\n").encode())
        fin = time.time() + attente; tampon = b""
        while time.time() < fin:
            tampon += s.read(256)
            for l in tampon.split(b"\n"):
                l = l.strip()
                if l.startswith(b"{") and b"XIII-TALLY" in l:
                    try: return json.loads(l)
                    except ValueError: pass
        return None


def redemarrer(port):
    import serial
    with serial.Serial(port, 115200) as s:
        s.dtr = False; s.rts = True; time.sleep(0.15); s.rts = False


class Programmeur(Gtk.Window):
    def __init__(self, parent, serveur):
        super().__init__(title="Programmer un boîtier Tally XIII", transient_for=parent, modal=True, default_width=640, default_height=700)
        self.add_css_class("parametres"); self.serveur = serveur
        v = boite(True, 10, margin_top=20, margin_bottom=18, margin_start=24, margin_end=24); self.set_child(defilant(v))
        v.append(label("Boîtier Tally XIII", "page-titre"))
        v.append(label("M5Stack ATOM Matrix / ATOM Lite ou boîtier ESP32 maison (LED WS2812 sur la broche 27, ou LED rouge 25 et verte 26). "
                       "Branchez-le en USB : il est programmé et configuré ici, puis il fonctionne seul sur le Wi-Fi de la régie.", "attenue", wrap=True))
        # port
        r = boite(False, 10, "reglage"); r.append(label("Boîtier", "reglage-titre"))
        self.l_ports = Gtk.StringList(); self.d_port = Gtk.DropDown(model=self.l_ports, hexpand=True); r.append(self.d_port)
        r.append(bouton(None, "refresh-cw", "plat", tip="Actualiser", rappel=self.lister)); v.append(r)
        self.l_etat = label("", "attenue", wrap=True); v.append(self.l_etat)
        # réglages
        ssid, mdp = wifi_actuel()
        self.e_ssid = self.champ(v, "Wi-Fi de la régie", ssid, "Nom du réseau")
        self.e_mdp = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True); self.e_mdp.set_text(mdp)
        r = boite(False, 10, "reglage"); r.append(label("Mot de passe", "reglage-titre")); r.append(self.e_mdp); v.append(r)
        self.e_srv = self.champ(v, "Adresse de Tally XIII", serveur, "IP:8790")
        r = boite(False, 10, "reglage"); r.append(label("Caméra", "reglage-titre", hexpand=True))
        self.s_cam = Gtk.SpinButton.new_with_range(1, 40, 1); r.append(self.s_cam)
        r.append(label("Luminosité", "reglage-titre")); self.s_lum = Gtk.SpinButton.new_with_range(5, 100, 5); self.s_lum.set_value(40); r.append(self.s_lum); v.append(r)
        # actions
        b = boite(False, 8, halign=Gtk.Align.END, margin_top=6)
        b.append(bouton("Configurer seulement", None, "fantome", rappel=lambda: self.lancer(False)))
        b.append(bouton("Installer le programme et configurer", None, "pilule", rappel=lambda: self.lancer(True))); v.append(b)
        self.barre = Gtk.ProgressBar(show_text=True); v.append(self.barre)
        self.journal = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR); self.journal.add_css_class("journal"); self.journal.set_size_request(-1, 160); v.append(self.journal)
        v.append(info_bulle("Sur le boîtier : appui court sur le bouton = caméra suivante, appui long = luminosité. "
                            "Couleurs : rouge antenne, vert preview, chiffre blanc au repos, orange = pas de Wi-Fi, bleu = Tally XIII injoignable, violet = à configurer."))
        self.lister(); self.present()

    def champ(self, v, titre, texte, aide):
        e = Gtk.Entry(text=texte or "", placeholder_text=aide, hexpand=True)
        r = boite(False, 10, "reglage"); r.append(label(titre, "reglage-titre")); r.append(e); v.append(r); return e

    def ecrire(self, t):
        GLib.idle_add(lambda: (self.journal.get_buffer().insert(self.journal.get_buffer().get_end_iter(), t + "\n"), False)[1])

    def lister(self):
        self.ports = ports()
        self.l_ports.splice(0, self.l_ports.get_n_items(), ["%s — %s" % (p, d) for p, d in self.ports] or ["Aucun boîtier branché"])
        if not self.ports:
            self.l_etat.set_text("Branchez le boîtier avec un câble USB de données (certains câbles ne font que charger).")
            GLib.timeout_add_seconds(2, lambda: (self.lister() if not self.ports and self.get_visible() else None, False)[1])
            return
        self.l_etat.set_text("Lecture du boîtier…")
        p = self.ports[0][0]
        def fond():
            try: return dialoguer(p, "?", 1.5)
            except Exception as e: return str(e)
        def fini(r):
            if isinstance(r, dict):
                self.l_etat.set_text("Programme Tally XIII %s déjà installé — caméra %s, Wi-Fi « %s »%s" % (r.get("version"), r.get("cam"), r.get("ssid"), " (connecté, IP %s)" % r["ip"] if r.get("wifi") else ""))
                self.s_cam.set_value(int(r.get("cam") or 1)); self.s_lum.set_value(int(r.get("lum") or 40))
            elif isinstance(r, str) and "Permission" in r:
                self.l_etat.set_text("Accès au port refusé : débranchez et rebranchez le boîtier (les droits sont donnés au branchement).")
            else:
                self.l_etat.set_text("Boîtier sans programme Tally XIII : utilisez « Installer le programme et configurer ».")
        threading.Thread(target=lambda: GLib.idle_add(fini, fond()), daemon=True).start()

    def lancer(self, flasher):
        if not self.ports: self.lister(); return
        port = self.ports[self.d_port.get_selected()][0] if self.d_port.get_selected() < len(self.ports) else self.ports[0][0]
        conf = {"ssid": self.e_ssid.get_text().strip(), "mdp": self.e_mdp.get_text(), "serveur": self.e_srv.get_text().strip().replace("http://", "").rstrip("/"),
                "cam": int(self.s_cam.get_value()), "lum": int(self.s_lum.get_value())}
        if not conf["ssid"] or not conf["serveur"]:
            self.l_etat.set_text("Indiquez le Wi-Fi et l'adresse de Tally XIII."); return
        self.journal.get_buffer().set_text(""); self.barre.set_fraction(0)
        threading.Thread(target=self.travail, args=(port, conf, flasher), daemon=True).start()

    def travail(self, port, conf, flasher):
        prog = lambda f, t: GLib.idle_add(lambda: (self.barre.set_fraction(f), self.barre.set_text(t), False)[2])
        try:
            if flasher:
                et = esptool()
                if not et: raise RuntimeError("esptool est absent")
                prog(0.02, "Identification du boîtier…")
                info = subprocess.run([et, "--port", port, "chip_id"], capture_output=True, text=True, timeout=40).stdout
                self.ecrire(info.strip()[-400:])
                cible = "atom" if "PICO" in info.upper() else "esp32"
                f = firmware(cible) or firmware("esp32")
                if not f: raise RuntimeError("programme du boîtier absent de l'OS")
                self.ecrire("Programme : %s (%s)" % (os.path.basename(f), "M5Stack ATOM" if cible == "atom" else "ESP32"))
                cmd = [et, "--chip", "esp32", "--port", port, "--baud", "460800", "write_flash", "0x0", f]
                pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for l in pr.stdout:
                    m = re.search(r"\((\d+) ?%\)", l)
                    if m: prog(0.05 + 0.8 * int(m.group(1)) / 100, "Installation… %s %%" % m.group(1))
                    elif l.strip(): self.ecrire(l.rstrip())
                if pr.wait() != 0: raise RuntimeError("l'installation a échoué (maintenez le bouton du boîtier en le branchant, puis réessayez)")
                time.sleep(2.5)
            prog(0.9, "Configuration…")
            r = None
            for _ in range(4):
                r = dialoguer(port, json.dumps(conf, ensure_ascii=False), 3)
                if r: break
                time.sleep(1)
            if not r: raise RuntimeError("le boîtier ne répond pas (programme non installé ?)")
            prog(1, "Terminé")
            self.ecrire("Boîtier configuré : caméra %s, Wi-Fi « %s », Tally XIII %s" % (r.get("cam"), r.get("ssid"), r.get("serveur")))
            GLib.idle_add(self.l_etat.set_text, "Prêt : le boîtier se connecte au Wi-Fi puis suit la caméra %s. Vous pouvez le débrancher." % r.get("cam"))
        except Exception as e:
            prog(0, "Échec"); self.ecrire("Erreur : %s" % e)
            GLib.idle_add(self.l_etat.set_text, "Échec : %s" % e)


def info_bulle(t):
    b = boite(False, 10, "info-bulle", margin_top=6); b.append(ico("info", 16, "c")); b.append(label(t, wrap=True, hexpand=True)); return b
