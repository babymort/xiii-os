# OS XIII — cartes d'acquisition : détection (Blackmagic DeckLink / UltraStudio / Intensity, cartes USB UVC),
# pilote Desktop Video à la demande, et pont GStreamer DeckLink → caméra virtuelle (/dev/video42) pour que
# MELANGO XIII, OBS ou un navigateur voient la carte comme une webcam.
# Application développée par Matthieu Lamotte.
import os, glob, subprocess, signal, json
from . import systeme as S

VIRTUELLE = "/dev/video42"
PID = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "xiii-pont-decklink.pid")
MODES = [("auto", "Détection automatique"), ("1080p25", "1080p 25"), ("1080i50", "1080i 50"), ("1080p50", "1080p 50"), ("1080p2997", "1080p 29,97"),
         ("1080p30", "1080p 30"), ("720p50", "720p 50"), ("720p5994", "720p 59,94"), ("2160p25", "2160p 25"), ("pal", "PAL")]

def cartes_blackmagic():
    """Cartes Blackmagic vues sur le bus PCI (vendeur bdbd) ou en Thunderbolt/USB."""
    L = []
    try:
        o = subprocess.run(["lspci", "-nn", "-d", "bdbd:"], capture_output=True, text=True, timeout=3).stdout
        L += [l.split(": ", 1)[-1].strip() for l in o.splitlines() if l.strip()]
    except Exception:
        pass
    try:
        o = subprocess.run(["lsusb", "-d", "1edb:"], capture_output=True, text=True, timeout=3).stdout
        L += [l.split("ID ", 1)[-1][10:].strip() or "Blackmagic USB" for l in o.splitlines() if l.strip()]
    except Exception:
        pass
    return L

def pilote_blackmagic():
    return bool(glob.glob("/dev/blackmagic/*")) or os.path.exists("/usr/lib/libDeckLinkAPI.so") or os.path.exists("/usr/lib/blackmagic")

def nb_entrees_decklink():
    return len(glob.glob("/dev/blackmagic/io*")) or len(glob.glob("/dev/blackmagic/dv*")) or (1 if pilote_blackmagic() else 0)

def peripheriques_video():
    """Entrées vidéo V4L2 (cartes USB, webcams, caméra virtuelle)."""
    L = []
    for d in sorted(glob.glob("/sys/class/video4linux/video*")):
        try: nom = open(os.path.join(d, "name")).read().strip()
        except OSError: nom = "?"
        L.append(("/dev/" + os.path.basename(d), nom))
    return L

def camera_virtuelle():
    return os.path.exists(VIRTUELLE)

def gst_decklink():
    return bool(subprocess.run(["gst-inspect-1.0", "decklinkvideosrc"], capture_output=True).returncode == 0)

def pont_actif():
    try:
        pid = int(open(PID).read()); os.kill(pid, 0); return pid
    except Exception:
        return None

def pont_demarrer(entree=0, mode="auto", son=False):
    pont_arreter()
    cmd = ["gst-launch-1.0", "-q", "decklinkvideosrc", "device-number=%d" % entree, "mode=%s" % mode, "connection=auto", "!",
           "videoconvert", "!", "video/x-raw,format=YUY2", "!", "v4l2sink", "device=" + VIRTUELLE, "sync=false"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    open(PID, "w").write(str(p.pid))
    return p.pid

def pont_arreter():
    pid = pont_actif()
    if pid:
        try: os.killpg(pid, signal.SIGTERM)
        except Exception:
            try: os.kill(pid, signal.SIGTERM)
            except Exception: pass
    try: os.remove(PID)
    except OSError: pass
