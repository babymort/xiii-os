# OS XIII — miniatures et informations des fichiers média pour Fichiers XIII (et les autres applis via le cache standard).
# Vidéo (MP4, MOV, MXF, MKV, AVI…) : image prise à 10 % du plan. Photo RAW (CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2…) :
# aperçu JPEG embarqué par l'appareil. Les miniatures vont dans ~/.cache/thumbnails (norme freedesktop) : Thunar,
# les boîtes de dialogue et les autres logiciels en profitent aussi.
# BRAW (Blackmagic RAW) et R3D (RED) : formats fermés, illisibles sans les SDK des fabricants → icône seulement.
import os, json, hashlib, subprocess, shutil, urllib.parse
from gi.repository import GLib

VIDEO = (".mp4", ".mov", ".mxf", ".mkv", ".avi", ".m4v", ".mts", ".m2ts", ".webm", ".wmv", ".mpg", ".mpeg", ".3gp", ".flv", ".insv", ".lrv")
RAW = (".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw", ".x3f", ".3fr", ".iiq", ".rwl")
IMAGE = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif", ".svg")
FERMES = {".braw": "Blackmagic RAW", ".r3d": "RED R3D", ".ari": "ARRIRAW", ".arx": "ARRIRAW"}
CACHE = os.path.join(GLib.get_user_cache_dir(), "thumbnails", "large")
ECHEC = os.path.join(GLib.get_user_cache_dir(), "thumbnails", "fail", "xiii")

def ext(p): return os.path.splitext(p)[1].lower()
def est_media(p): return ext(p) in VIDEO + RAW + IMAGE

def chemin_miniature(p):
    uri = "file://" + urllib.parse.quote(os.path.abspath(p))
    return os.path.join(CACHE, hashlib.md5(uri.encode()).hexdigest() + ".png"), uri

def miniature(p, taille=256):
    """Chemin d'une miniature PNG (créée si besoin), ou None. Peut prendre une seconde : à appeler hors de l'interface."""
    e = ext(p)
    if e not in VIDEO + RAW + IMAGE: return None
    f, uri = chemin_miniature(p)
    try: mt = int(os.path.getmtime(p))
    except OSError: return None
    if os.path.exists(f) and os.path.getmtime(f) >= mt: return f
    rate = os.path.join(ECHEC, os.path.basename(f))
    if os.path.exists(rate) and os.path.getmtime(rate) >= mt: return None
    os.makedirs(CACHE, exist_ok=True); tmp = f + ".tmp.png"
    ok = False
    try:
        if e in VIDEO:
            if shutil.which("ffmpegthumbnailer"):
                ok = subprocess.run(["ffmpegthumbnailer", "-i", p, "-o", tmp, "-s", str(taille), "-t", "10%", "-c", "png"], capture_output=True, timeout=25).returncode == 0
            if not ok and shutil.which("ffmpeg"):
                ok = subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-ss", "1", "-i", p, "-frames:v", "1", "-vf", "scale=%d:-2" % taille, tmp], capture_output=True, timeout=25).returncode == 0
        elif e in RAW:
            jpg = None
            if shutil.which("exiftool"):
                for tag in ("-JpgFromRaw", "-PreviewImage", "-ThumbnailImage"):
                    b = subprocess.run(["exiftool", "-b", tag, p], capture_output=True, timeout=20).stdout
                    if len(b) > 2000: jpg = b; break
            if jpg:
                from gi.repository import GdkPixbuf
                ld = GdkPixbuf.PixbufLoader(); ld.write(jpg); ld.close(); pb = ld.get_pixbuf()
                pb = GdkPixbuf.Pixbuf.apply_embedded_orientation(pb) or pb
                w, h = pb.get_width(), pb.get_height(); k = taille / max(w, h)
                pb.scale_simple(max(1, int(w * k)), max(1, int(h * k)), GdkPixbuf.InterpType.BILINEAR).savev(tmp, "png", [], []); ok = True
        else:
            from gi.repository import GdkPixbuf
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(p, taille, taille, True)
            pb = GdkPixbuf.Pixbuf.apply_embedded_orientation(pb) or pb
            pb.savev(tmp, "png", [], []); ok = True
    except Exception:
        ok = False
    if ok and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, f); return f
    try: os.remove(tmp)
    except OSError: pass
    os.makedirs(ECHEC, exist_ok=True); open(rate, "w").close()
    return None

def _fps(s):
    try:
        a, b = s.split("/"); v = float(a) / float(b)
        return ("%.3f" % v).rstrip("0").rstrip(".") if v else ""
    except Exception: return ""

def duree(s):
    try: s = float(s)
    except (TypeError, ValueError): return ""
    return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60) if s >= 3600 else "%d:%02d" % (s // 60, s % 60)

def infos(p):
    """Informations utiles d'un fichier vidéo / son / photo : liste de (libellé, valeur)."""
    e = ext(p); L = []
    if e in FERMES:
        return [("Format", FERMES[e]), ("Lecture", "Format fermé : ouvrez-le dans DaVinci Resolve (BRAW) ou REDCINE-X (R3D)")]
    if e in RAW or e in (".jpg", ".jpeg", ".heic", ".tif", ".tiff"):
        if shutil.which("exiftool"):
            try:
                d = json.loads(subprocess.run(["exiftool", "-j", "-Make", "-Model", "-LensModel", "-ISO", "-ExposureTime", "-FNumber", "-FocalLength", "-ImageSize", "-DateTimeOriginal", p],
                                              capture_output=True, text=True, timeout=15).stdout)[0]
                for k, n in (("Make", "Marque"), ("Model", "Appareil"), ("LensModel", "Objectif"), ("ImageSize", "Dimensions"), ("ISO", "ISO"), ("ExposureTime", "Vitesse"),
                             ("FNumber", "Ouverture"), ("FocalLength", "Focale"), ("DateTimeOriginal", "Prise de vue")):
                    if d.get(k): L.append((n, ("f/%s" % d[k]) if k == "FNumber" else str(d[k])))
            except Exception: pass
        return L
    if not shutil.which("ffprobe"): return L
    try:
        d = json.loads(subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", p], capture_output=True, text=True, timeout=20).stdout)
    except Exception:
        return L
    fmt = d.get("format", {}); tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)
    a = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
    tc = next((s.get("tags", {}).get("timecode") for s in d.get("streams", []) if (s.get("tags") or {}).get("timecode")), None) or tags.get("timecode")
    if v:
        codec = (v.get("codec_long_name") or v.get("codec_name") or "").split(" (")[0]
        prof = v.get("profile")
        L.append(("Codec vidéo", codec + (" · " + prof if prof and prof.lower() not in codec.lower() else "")))
        L.append(("Résolution", "%s × %s" % (v.get("width"), v.get("height"))))
        f = _fps(v.get("avg_frame_rate") or v.get("r_frame_rate") or "")
        if f: L.append(("Images / s", f + (" (entrelacé)" if v.get("field_order") not in (None, "progressive", "unknown") else "")))
        if v.get("pix_fmt"): L.append(("Échantillonnage", v["pix_fmt"].replace("yuv", "YUV ").replace("p10le", " 10 bits").replace("p12le", " 12 bits").replace("p", " 8 bits") if v["pix_fmt"].startswith("yuv") else v["pix_fmt"]))
        if v.get("color_transfer") and v["color_transfer"] not in ("unknown", "bt709"): L.append(("Courbe", {"arib-std-b67": "HLG", "smpte2084": "PQ (HDR10)"}.get(v["color_transfer"], v["color_transfer"])))
    if fmt.get("duration"): L.append(("Durée", duree(fmt["duration"])))
    if tc: L.append(("Timecode de départ", tc))
    if fmt.get("bit_rate"):
        br = int(fmt["bit_rate"]); L.append(("Débit", "%.1f Mb/s · %.0f Go/h" % (br / 1e6, br * 3600 / 8e9)))
    if a:
        s = a[0]; L.append(("Son", "%s · %s Hz · %d piste(s), %s canaux" % ((s.get("codec_name") or "").upper(), s.get("sample_rate", "?"), len(a), s.get("channels", "?"))))
    cam = " ".join(x for x in (tags.get("com.apple.quicktime.make") or tags.get("make"), tags.get("com.apple.quicktime.model") or tags.get("model")) if x)
    if cam: L.append(("Caméra", cam))
    elif tags.get("encoder") or tags.get("company_name"): L.append(("Créé par", tags.get("company_name") or tags.get("encoder")))
    if tags.get("reel_name") or tags.get("reel"): L.append(("Bobine", tags.get("reel_name") or tags.get("reel")))
    if tags.get("creation_time"): L.append(("Enregistré le", tags["creation_time"][:19].replace("T", " à ")))
    L.append(("Conteneur", (fmt.get("format_long_name") or "").split(" / ")[0]))
    return L
