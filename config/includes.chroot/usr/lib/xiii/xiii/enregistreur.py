# OS XIII — XIII Enregistreur : enregistrer l'écran (entier ou une zone) avec la webcam incrustée dans un coin,
# le micro et le son de l'ordinateur. À l'arrêt, tout est assemblé en un seul MP4 (H.264 + AAC), rangé dans le projet actif
# (06_Exports) ou dans Vidéos, puis : regarder, ouvrir le dossier, envoyer (Envoi XIII / Transferts XIII).
#   xiii-enregistreur            fenêtre de réglages
#   xiii-enregistreur --arreter  arrête l'enregistrement en cours (aussi : la notification « Arrêter »)
# Application développée par Matthieu Lamotte.
import os, sys, json, glob, time, signal, shutil, subprocess, threading, tempfile
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import config, systeme as S
from .ui import *
from .appli import preparer, page

ETAT = os.path.join(GLib.get_user_runtime_dir() or "/tmp", "xiii-enregistreur.json")
COINS = [("bd", "En bas à droite", "W-w-28:H-h-28"), ("bg", "En bas à gauche", "28:H-h-28"), ("hd", "En haut à droite", "W-w-28:28"), ("hg", "En haut à gauche", "28:28")]
TAILLES = [("petite", "Petite", 0.18), ("moyenne", "Moyenne", 0.25), ("grande", "Grande", 0.33)]


def webcams():
    L = []
    for d in sorted(glob.glob("/dev/video*")):
        n = os.path.basename(d)
        try: nom = open("/sys/class/video4linux/%s/name" % n).read().strip()
        except OSError: nom = n
        try: idx = int(open("/sys/class/video4linux/%s/index" % n).read().strip())
        except (OSError, ValueError): idx = 0
        if idx == 0 and "metadata" not in nom.lower(): L.append((d, nom))
    return L


def destination():
    pj = config.charger().get("projet_actif")
    d = os.path.expanduser("~/XIII/%s/06_Exports" % pj) if pj else os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS) or os.path.expanduser("~/Vidéos"), "Enregistrements")
    os.makedirs(d, exist_ok=True); return d


def demarrer(zone, cam, coin, taille, micro, systeme):
    tmp = tempfile.mkdtemp(prefix="xiii-enr-")
    P = {}
    geo = []
    if zone:
        g = subprocess.run(["slurp"], capture_output=True, text=True).stdout.strip()
        if not g: return None
        geo = ["-g", g]
    P["ecran"] = subprocess.Popen(["wf-recorder", "-y", "-c", "libx264", "-p", "preset=veryfast", "-p", "crf=20", "-r", "30"] + geo + ["-f", os.path.join(tmp, "ecran.mp4")],
                                  stdout=subprocess.DEVNULL, stderr=open(os.path.join(tmp, "ecran.log"), "w"), start_new_session=True)
    if cam:
        P["cam"] = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "v4l2", "-framerate", "30", "-video_size", "1280x720", "-i", cam, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                                     os.path.join(tmp, "cam.mkv")], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=open(os.path.join(tmp, "cam.log"), "w"), start_new_session=True)
    if micro or systeme:
        ent = (["-f", "pulse", "-i", "default"] if micro else []) + (["-f", "pulse", "-i", "@DEFAULT_MONITOR@"] if systeme else [])
        mix = ["-filter_complex", "amix=inputs=2:duration=longest:normalize=0"] if micro and systeme else []
        P["son"] = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error"] + ent + mix + ["-c:a", "flac", os.path.join(tmp, "son.flac")],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=open(os.path.join(tmp, "son.log"), "w"), start_new_session=True)
    json.dump({"tmp": tmp, "pids": {k: p.pid for k, p in P.items()}, "coin": coin, "taille": taille, "debut": time.time()}, open(ETAT, "w"))
    return tmp


def en_cours():
    try: e = json.load(open(ETAT))
    except Exception: return None
    return e if any(os.path.exists("/proc/%d" % p) for p in e["pids"].values()) else None


def arreter():
    """Arrête les enregistreurs, assemble le MP4 final. → chemin du fichier."""
    e = en_cours()
    if not e: return None
    for k, pid in e["pids"].items():
        try: os.kill(pid, signal.SIGINT)
        except ProcessLookupError: pass
    for _ in range(80):
        if not any(os.path.exists("/proc/%d" % p) for p in e["pids"].values()): break
        time.sleep(.1)
    try: os.remove(ETAT)
    except OSError: pass
    t = e["tmp"]; ecran, cam, son = (os.path.join(t, f) for f in ("ecran.mp4", "cam.mkv", "son.flac"))
    if not os.path.exists(ecran): raise RuntimeError("l'enregistrement de l'écran a échoué (voir %s)" % os.path.join(t, "ecran.log"))
    sortie = os.path.join(destination(), time.strftime("Enregistrement %Y-%m-%d %H%M%S.mp4"))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", ecran]; fc = []; vmap = "0:v"
    if os.path.exists(cam) and os.path.getsize(cam) > 1000:
        cmd += ["-i", cam]; k = dict((x[0], x[2]) for x in TAILLES).get(e["taille"], .25); pos = dict((x[0], x[2]) for x in COINS).get(e["coin"], COINS[0][2])
        fc.append("[1:v][0:v]scale2ref=w=trunc(iw*%s/2)*2:h=trunc(ow*main_h/main_w/2)*2[c][e];[e][c]overlay=%s:eof_action=pass,format=yuv420p[v]" % (k, pos)); vmap = "[v]"
    amap = []
    if os.path.exists(son) and os.path.getsize(son) > 1000:
        cmd += ["-i", son]; amap = ["-map", "%d:a" % (2 if vmap == "[v]" else 1), "-c:a", "aac", "-b:a", "192k"]
    cmd += (["-filter_complex", ";".join(fc)] if fc else []) + ["-map", vmap] + amap
    cmd += (["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"] if fc else ["-c:v", "copy"]) + ["-shortest", "-movflags", "+faststart", sortie]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr.strip()[-300:])
    shutil.rmtree(t, ignore_errors=True)
    return sortie


def fin_notif(f):
    r = subprocess.run(["notify-send", "-a", "XIII Enregistreur", "-i", "xiii-enregistreur", "--wait", "-A", "voir=Regarder", "-A", "dossier=Ouvrir le dossier", "-A", "envoyer=Envoyer",
                        "Enregistrement prêt", os.path.basename(f)], capture_output=True, text=True, timeout=600).stdout.strip()
    if r == "voir": S.detacher(["xiii-lecteur", f])
    elif r == "dossier": S.detacher(["xiii-fichiers", f])
    elif r == "envoyer": S.detacher(["xiii-envoi", f])


class Enregistreur(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.enregistreur")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".compte { font-size: 96px; font-weight: 800; color: #f0b378; }")
        self.win = Gtk.ApplicationWindow(application=self, title="XIII Enregistreur", default_width=580, default_height=780)
        sc, v = page("Enregistreur", "Écran, webcam incrustée, micro et son de l'ordinateur — un seul fichier MP4 à la fin", "circle-dot")
        self.win.set_child(sc); c = config.charger()
        if en_cours():
            v.append(label("Un enregistrement est en cours.", "gras"))
            v.append(bouton("Arrêter et enregistrer", "square", "pilule", rappel=self.stop)); self.etat = label("", "attenue", wrap=True); v.append(self.etat)
            self.win.present(); return
        def ligne(t, w):
            r = boite(False, 10, "reglage"); r.append(label(t, hexpand=True)); r.append(w); v.append(r); return w
        self.dd_zone = ligne("Ce qu'on enregistre", Gtk.DropDown.new_from_strings(["Tout l'écran", "Une zone (à tracer)"]))
        cams = webcams(); self.cams = cams
        self.dd_cam = ligne("Webcam incrustée", Gtk.DropDown.new_from_strings(["Aucune"] + [n for _, n in cams])); self.dd_cam.set_selected(1 if cams and c.get("enr_webcam", True) else 0)
        self.dd_coin = ligne("Position de la webcam", Gtk.DropDown.new_from_strings([x[1] for x in COINS]))
        self.dd_taille = ligne("Taille de la webcam", Gtk.DropDown.new_from_strings([x[1] for x in TAILLES])); self.dd_taille.set_selected(1)
        self.sw_mic = ligne("Micro", Gtk.Switch(active=c.get("enr_micro", True), valign=Gtk.Align.CENTER))
        self.sw_sys = ligne("Son de l'ordinateur", Gtk.Switch(active=c.get("enr_systeme", True), valign=Gtk.Align.CENTER))
        v.append(label("Enregistré dans : " + destination(), "petit", "attenue", wrap=True))
        v.append(label("Pour arrêter : bouton « Arrêter » de la notification, ou relancez l'Enregistreur. La fenêtre se réduit pendant l'enregistrement.", "petit", "attenue", wrap=True))
        b = bouton("Enregistrer", "circle-dot", "pilule", rappel=self.go); b.set_halign(Gtk.Align.START); v.append(b)
        self.etat = label("", "attenue", wrap=True); v.append(self.etat)
        self.win.present()

    def go(self):
        config.modifier(_histo=False, enr_micro=self.sw_mic.get_active(), enr_systeme=self.sw_sys.get_active(), enr_webcam=self.dd_cam.get_selected() > 0)
        cam = self.cams[self.dd_cam.get_selected() - 1][0] if self.dd_cam.get_selected() > 0 else None
        args = (self.dd_zone.get_selected() == 1, cam, COINS[self.dd_coin.get_selected()][0], TAILLES[self.dd_taille.get_selected()][0], self.sw_mic.get_active(), self.sw_sys.get_active())
        n = {"k": 3}; o = Gtk.Window(decorated=False, transient_for=self.win); o.set_child(label("3", "compte")); o.present()
        def tic():
            n["k"] -= 1
            if n["k"] > 0: o.get_child().set_text(str(n["k"])); return True
            o.close(); self.win.minimize()
            t = demarrer(*args)
            if not t: self.etat.set_text("Zone annulée."); self.win.present(); return False
            def attente():
                r = subprocess.run(["notify-send", "-a", "XIII Enregistreur", "-i", "xiii-enregistreur", "-u", "critical", "--wait", "-A", "stop=Arrêter", "● Enregistrement en cours",
                                    "Cliquez sur « Arrêter » pour terminer"], capture_output=True, text=True).stdout.strip()
                if r == "stop" and en_cours(): GLib.idle_add(self.stop)
            threading.Thread(target=attente, daemon=True).start()
            return False
        GLib.timeout_add(900, tic)

    def stop(self):
        self.win.present(); self.etat.set_text("Assemblage de la vidéo…")
        S.en_fond(arreter, lambda f: (self.etat.set_text(("Erreur : %s" % f) if isinstance(f, Exception) else "Enregistré : %s" % f),
                                      threading.Thread(target=fin_notif, args=(f,), daemon=True).start() if isinstance(f, str) else None))
        return False


def main():
    if "--arreter" in sys.argv:
        f = arreter()
        if f: fin_notif(f)
        return
    sys.exit(Enregistreur().run(sys.argv[:1]))
