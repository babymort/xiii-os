# OS XIII — petits outils du quotidien (comme PowerToys et macOS) :
#   xiii-outil pipette      prendre une couleur à l'écran (Super + Maj + P) : code HEX copié, RGB et HSL en notification
#   xiii-outil lire         lire à voix haute le texte sélectionné (Super + Maj + L) ; un 2e appui arrête la lecture
#   xiii-outil pip [FICHIER|URL] vidéo en vignette flottante, toujours au premier plan (Super + Maj + V)
#   xiii-outil redimensionner [--largeur N] [--format jpg|png|garder] FICHIERS…   redimensionner des images en lot
# Application développée par Matthieu Lamotte.
import os, sys, subprocess, shutil, colorsys


def notifier(titre, corps="", icone="dialog-information"):
    subprocess.run(["notify-send", "-a", "OS XIII", "-i", icone, titre, corps], capture_output=True)


# --------------------------------------------------------------------------------------------- pipette
def lire_ppm(d):
    """Premier pixel d'une image PPM (P6) renvoyée par grim."""
    parts, i = [], 0
    while len(parts) < 4:
        while d[i:i + 1].isspace(): i += 1
        if d[i:i + 1] == b"#":
            while d[i:i + 1] not in (b"\n", b""): i += 1
            continue
        j = i
        while not d[j:j + 1].isspace(): j += 1
        parts.append(d[i:j]); i = j
    i += 1
    return d[i], d[i + 1], d[i + 2]


def pipette():
    try:
        pt = subprocess.run(["slurp", "-p"], capture_output=True, text=True, timeout=120).stdout.strip()
    except Exception:
        return 1
    if not pt: return 1
    xy = pt.split()[0]
    img = subprocess.run(["grim", "-g", "%s 1x1" % xy, "-t", "ppm", "-"], capture_output=True).stdout
    if not img.startswith(b"P6"): notifier("Pipette", "Impossible de lire la couleur à l'écran", "dialog-error"); return 1
    r, g, b = lire_ppm(img)
    hx = "#%02x%02x%02x" % (r, g, b)
    h, l, s_ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    subprocess.run(["wl-copy", hx], capture_output=True)
    hist = os.path.expanduser("~/.local/share/xiii/pipette.txt")
    try:
        os.makedirs(os.path.dirname(hist), exist_ok=True)
        L = [x for x in open(hist).read().split() if x != hx][:19] if os.path.exists(hist) else []
        open(hist, "w").write("\n".join([hx] + L) + "\n")
    except OSError:
        pass
    notifier("Couleur copiée : %s" % hx.upper(), "rgb(%d, %d, %d) · hsl(%d, %d %%, %d %%)\nCollez avec Ctrl + V (20 dernières dans ~/.local/share/xiii/pipette.txt)"
             % (r, g, b, round(h * 360), round(s_ * 100), round(l * 100)), "color-select")
    print(hx); return 0


# --------------------------------------------------------------------------------------------- lire à voix haute
PIPER_SYS = "/usr/share/xiii/piper"
PIPER_PERSO = os.path.expanduser("~/.local/share/xiii/piper")
PIPER_BIN = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
VOIX = "fr_FR-siwis-medium"
VOIX_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/" + VOIX + ".onnx"
PID = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "xiii-lire.pid")


def piper():
    """(binaire, modèle) de la voix naturelle Piper (hors ligne), installée par l'image ou téléchargée une fois (≈ 90 Mo)."""
    for d in (PIPER_SYS, PIPER_PERSO):
        b, m = os.path.join(d, "piper", "piper"), os.path.join(d, VOIX + ".onnx")
        if os.access(b, os.X_OK) and os.path.exists(m) and os.path.exists(m + ".json"): return b, m
    return None


def installer_piper(avis=lambda t: None):
    import urllib.request, tarfile, io
    os.makedirs(PIPER_PERSO, exist_ok=True)
    avis("Première lecture : téléchargement de la voix naturelle française (≈ 90 Mo)…")
    def get(u):
        return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "OS-XIII"}), timeout=120).read()
    if not os.path.exists(os.path.join(PIPER_PERSO, "piper", "piper")):
        tarfile.open(fileobj=io.BytesIO(get(PIPER_BIN))).extractall(PIPER_PERSO)
    for ext in (".onnx.json", ".onnx"):
        f = os.path.join(PIPER_PERSO, VOIX + ext)
        if not os.path.exists(f): open(f + ".part", "wb").write(get(VOIX_URL.replace(".onnx", ext))); os.replace(f + ".part", f)
    return piper()


def arreter_lecture():
    try:
        pid = int(open(PID).read()); os.killpg(pid, 15); os.remove(PID); return True
    except Exception:
        return subprocess.run(["pkill", "-f", "espeak-ng -v fr"], capture_output=True).returncode == 0


def parler(t, naturelle=True):
    """Lit un texte à voix haute : voix naturelle Piper si possible, sinon espeak-ng. Renvoie le processus."""
    import json
    v = piper() if naturelle else None
    if v is None and naturelle and os.environ.get("XIII_DEMO") != "1":
        try: v = installer_piper(lambda m: notifier("Lecture à voix haute", m, "audio-speakers"))
        except Exception: v = None
    if v:
        b, m = v
        try: taux = json.load(open(m + ".json"))["audio"]["sample_rate"]
        except Exception: taux = 22050
        lecteur = "aplay -q -r %d -f S16_LE -t raw -c 1 -" % taux if shutil.which("aplay") else "pw-play --rate %d --channels 1 --format s16 -" % taux
        cmd = ["sh", "-c", '"$0" --model "$1" --output-raw 2>/dev/null | ' + lecteur, b, m]
    elif shutil.which("espeak-ng"):
        cmd = ["espeak-ng", "-v", "fr", "-s", "165", "--stdin"]
    else:
        return None
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, text=True)
    try: open(PID, "w").write(str(p.pid))
    except Exception: pass
    p.stdin.write(t); p.stdin.close()
    return p


def lire():
    if arreter_lecture(): return 0                                     # 2e appui : arrêt
    t = subprocess.run(["wl-paste", "--primary", "--no-newline"], capture_output=True, text=True).stdout.strip()
    if not t: t = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True).stdout.strip()
    if not t: notifier("Lecture à voix haute", "Sélectionnez d'abord un texte (ou copiez-le)"); return 1
    import json
    try: nat = json.load(open(os.path.expanduser("~/.config/xiii/reglages.json"))).get("voix_naturelle", True)
    except Exception: nat = True
    p = parler(t[:20000], nat)
    if p is None: notifier("Lecture à voix haute", "Aucune synthèse vocale disponible", "dialog-error"); return 1
    p.wait()
    try: os.remove(PID)
    except Exception: pass
    return 0


def pip(cible=None):
    """Vignette vidéo flottante (image dans l'image) : un fichier, ou l'adresse copiée (YouTube… si yt-dlp est là)."""
    cible = cible or subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True).stdout.strip()
    if not cible or not (os.path.exists(cible) or cible.startswith(("http://", "https://"))):
        notifier("Vignette vidéo", "Copiez l'adresse d'une vidéo, ou faites clic droit › Lire en vignette dans Fichiers", "picture-in-picture"); return 1
    if not shutil.which("mpv"): notifier("Vignette vidéo", "Le lecteur mpv n'est pas installé", "dialog-error"); return 1
    nom = os.path.basename(cible) if os.path.exists(cible) else cible.split("//", 1)[-1][:50]
    subprocess.Popen(["mpv", "--force-window=immediate", "--autofit=480x270", "--keep-open=no", "--no-border",
                      "--title=Vignette XIII — " + nom, "--wayland-app-id=fr.xiii.vignette", cible],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


# --------------------------------------------------------------------------------------------- redimensionner des images
def redimensionner(fichiers, largeur=1920, fmt="garder", qualite=88):
    """Chaque image réduite à « largeur » pixels de large (jamais agrandie), à côté de l'original : « nom (1920).jpg »."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    faits, erreurs = [], []
    for f in fichiers:
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file(f)
            try: pb = pb.apply_embedded_orientation() or pb
            except Exception: pass
            w, h = pb.get_width(), pb.get_height()
            if w > largeur: pb = pb.scale_simple(largeur, max(1, round(h * largeur / w)), GdkPixbuf.InterpType.HYPER)
            base, ext = os.path.splitext(f); ext = ext.lower()
            if fmt == "jpg" or (fmt == "garder" and ext in (".jpg", ".jpeg", ".heic", ".webp", ".tif", ".tiff", ".bmp")): typ, ext2 = "jpeg", ".jpg"
            elif fmt == "png" or ext == ".png": typ, ext2 = "png", ".png"
            else: typ, ext2 = "jpeg", ".jpg"
            dest = "%s (%d)%s" % (base, pb.get_width(), ext2); k = 2
            while os.path.exists(dest): dest = "%s (%d) %d%s" % (base, pb.get_width(), k, ext2); k += 1
            if typ == "jpeg":
                if pb.get_has_alpha(): pb = pb.composite_color_simple(pb.get_width(), pb.get_height(), GdkPixbuf.InterpType.NEAREST, 255, 8, 0xffffff, 0xffffff)
                pb.savev(dest, "jpeg", ["quality"], [str(qualite)])
            else:
                pb.savev(dest, "png", [], [])
            faits.append(dest)
        except Exception as e:
            erreurs.append("%s : %s" % (os.path.basename(f), e))
    return faits, erreurs


def main():
    a = sys.argv[1:]
    if not a: print(__doc__ if __doc__ else "xiii-outil pipette | lire | redimensionner"); sys.exit(2)
    if a[0] == "pipette": sys.exit(pipette())
    if a[0] == "lire": sys.exit(lire())
    if a[0] == "pip": sys.exit(pip(a[1] if len(a) > 1 else None))
    if a[0] == "redimensionner":
        larg, fmt, L = 1920, "garder", []
        i = 1
        while i < len(a):
            if a[i] == "--largeur": larg = int(a[i + 1]); i += 2; continue
            if a[i] == "--format": fmt = a[i + 1]; i += 2; continue
            L.append(a[i]); i += 1
        faits, err = redimensionner(L, larg, fmt)
        print("\n".join(faits)); [print("ERREUR", e) for e in err]
        notifier("%d image(s) redimensionnée(s)" % len(faits), ("Erreurs : " + "; ".join(err)) if err else "À côté des originales, largeur %d px" % larg, "image-x-generic")
        sys.exit(0 if not err else 1)
    print("commande inconnue :", a[0]); sys.exit(2)
