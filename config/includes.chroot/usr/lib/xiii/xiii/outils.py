# OS XIII — petits outils du quotidien (comme PowerToys et macOS) :
#   xiii-outil pipette      prendre une couleur à l'écran (Super + Maj + P) : code HEX copié, RGB et HSL en notification
#   xiii-outil lire         lire à voix haute le texte sélectionné (Super + Maj + L) ; un 2e appui arrête la lecture
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
def lire():
    if subprocess.run(["pkill", "-f", "espeak-ng -v fr"], capture_output=True).returncode == 0: return 0      # 2e appui : arrêt
    t = subprocess.run(["wl-paste", "--primary", "--no-newline"], capture_output=True, text=True).stdout.strip()
    if not t: t = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True).stdout.strip()
    if not t: notifier("Lecture à voix haute", "Sélectionnez d'abord un texte (ou copiez-le)"); return 1
    t = t[:20000]
    if shutil.which("piper") and os.path.isdir("/usr/share/piper-voices"):
        pass                                                         # voix naturelle si un jour installée : même usage
    if not shutil.which("espeak-ng"): notifier("Lecture à voix haute", "La synthèse vocale (espeak-ng) n'est pas installée", "dialog-error"); return 1
    subprocess.Popen(["espeak-ng", "-v", "fr", "-s", "165", t], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
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
