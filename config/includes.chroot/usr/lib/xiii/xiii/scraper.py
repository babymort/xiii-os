# OS XIII — jaquettes et fiches des jeux pour la Console XIII.
# 1. ScreenScraper (screenscraper.fr), avec votre compte et des identifiants développeur ScreenScraper : jaquette,
#    capture, année, genre, éditeur, nombre de joueurs, résumé en français.
# 2. Sinon, sans compte : jaquettes et captures libres des « libretro-thumbnails » (thumbnails.libretro.com).
# Tout est rangé dans ~/Jeux/<console>/media/ (images + infos.json).
# Application développée par Matthieu Lamotte.
import os, re, json, time, zlib, urllib.request, urllib.parse, html

CONF = os.path.expanduser("~/.config/xiii/screenscraper.json")
UA = {"User-Agent": "OS-XIII/1.0 (Console XIII)"}

# console : (id ScreenScraper, dossier libretro-thumbnails)
SYSTEMES = {
    "nes": (3, "Nintendo - Nintendo Entertainment System"), "snes": (4, "Nintendo - Super Nintendo Entertainment System"),
    "n64": (14, "Nintendo - Nintendo 64"), "gb": (9, "Nintendo - Game Boy"), "gbc": (10, "Nintendo - Game Boy Color"),
    "gba": (12, "Nintendo - Game Boy Advance"), "nds": (15, "Nintendo - Nintendo DS"), "3ds": (17, "Nintendo - Nintendo 3DS"),
    "gamecube": (13, "Nintendo - GameCube"), "wii": (16, "Nintendo - Wii"), "wiiu": (18, "Nintendo - Wii U"), "switch": (225, None),
    "virtualboy": (11, "Nintendo - Virtual Boy"), "megadrive": (1, "Sega - Mega Drive - Genesis"), "mastersystem": (2, "Sega - Master System - Mark III"),
    "gamegear": (21, "Sega - Game Gear"), "segacd": (20, "Sega - Mega-CD - Sega CD"), "saturn": (22, "Sega - Saturn"), "dreamcast": (23, "Sega - Dreamcast"),
    "psx": (57, "Sony - PlayStation"), "ps2": (58, "Sony - PlayStation 2"), "ps3": (59, "Sony - PlayStation 3"), "psp": (61, "Sony - PlayStation Portable"),
    "xbox": (32, "Microsoft - Xbox"), "pcengine": (31, "NEC - PC Engine - TurboGrafx 16"), "neogeo": (142, "SNK - Neo Geo"),
    "ngp": (25, "SNK - Neo Geo Pocket"), "arcade": (75, "MAME"), "lynx": (28, "Atari - Lynx"), "atari2600": (26, "Atari - 2600"),
    "atari800": (43, "Atari - 8-bit"), "atarist": (42, "Atari - ST"), "wonderswan": (45, "Bandai - WonderSwan"),
    "amiga": (64, "Commodore - Amiga"), "c64": (66, "Commodore - 64"), "msx": (113, "Microsoft - MSX"),
    "zxspectrum": (76, "Sinclair - ZX Spectrum +3"), "dos": (135, "DOS"), "scummvm": (123, "ScummVM"),
}
REGIONS = ["fr", "eu", "wor", "us", "ss", "jp"]

def conf():
    try: return json.load(open(CONF))
    except Exception: return {}

def enregistrer_conf(c):
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    fd = os.open(CONF, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(c, f)

def dossier_media(sid):
    d = os.path.join(os.path.expanduser("~/Jeux"), sid, "media"); os.makedirs(d, exist_ok=True); return d

def base(chemin): return os.path.splitext(os.path.basename(chemin.rstrip("/")))[0]

def infos(sid):
    try: return json.load(open(os.path.join(dossier_media(sid), "infos.json")))
    except Exception: return {}

def medias(sid, chemin):
    """Chemins locaux (jaquette, capture) s'ils existent, et fiche."""
    d = os.path.join(os.path.expanduser("~/Jeux"), sid, "media"); b = base(chemin)
    j = os.path.join(d, b + ".png"); e = os.path.join(d, b + "-ecran.png")
    return (j if os.path.exists(j) else None, e if os.path.exists(e) else None)

def telecharger(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if len(data) < 200 or data[:4] not in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\xff\xd8\xff\xdb", b"GIF8", b"RIFF"): return False
    open(dest + ".part", "wb").write(data); os.replace(dest + ".part", dest); return True

def norm(n):
    n = html.unescape(n).lower()
    n = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", n)
    n = re.sub(r"^(the|le|la|les)\s+|,\s*(the|le|la|les)$", "", n)
    return re.sub(r"[^a-z0-9]+", "", n)

# ----------------------------------------------------------------------------- libretro-thumbnails
_index = {}
def index_libretro(dossier, genre):
    cle = (dossier, genre)
    if cle not in _index:
        url = "https://thumbnails.libretro.com/%s/%s/" % (urllib.parse.quote(dossier), genre)
        try:
            t = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
            noms = [urllib.parse.unquote(h)[:-4] for h in re.findall(r'href="([^"?/]+\.png)"', t)]
        except Exception:
            noms = []
        par_exact = {n.lower(): n for n in noms}; par_norm = {}
        for n in noms: par_norm.setdefault(norm(n), n)
        _index[cle] = (par_exact, par_norm)
    return _index[cle]

def libretro(sid, chemin, dest_j, dest_e):
    dossier = SYSTEMES.get(sid, (0, None))[1]
    if not dossier: return False
    b = base(chemin); ok = False
    for genre, dest in (("Named_Boxarts", dest_j), ("Named_Snaps", dest_e)):
        ex, nm = index_libretro(dossier, genre)
        n = ex.get(b.lower()) or nm.get(norm(b))
        if n:
            url = "https://thumbnails.libretro.com/%s/%s/%s.png" % (urllib.parse.quote(dossier), genre, urllib.parse.quote(n))
            try: ok = telecharger(url, dest) or ok
            except Exception: pass
    return ok

# ----------------------------------------------------------------------------- ScreenScraper
def crc32(f):
    if os.path.isdir(f) or os.path.getsize(f) > 64 * 1024 * 1024: return None
    c = 0
    with open(f, "rb") as h:
        for bloc in iter(lambda: h.read(1 << 20), b""): c = zlib.crc32(bloc, c)
    return "%08X" % (c & 0xffffffff)

def choisir(liste, champ="region"):
    for r in REGIONS:
        for x in liste:
            if x.get(champ) == r or x.get("langue") == r: return x
    return liste[0] if liste else None

def screenscraper(sid, chemin, c, dest_j, dest_e):
    ssid = SYSTEMES.get(sid, (None,))[0]
    if not ssid: return None
    p = {"devid": c["devid"], "devpassword": c["devpassword"], "softname": "OSXIII", "output": "json", "systemeid": ssid,
         "romtype": "rom", "romnom": os.path.basename(chemin)}
    if c.get("ssid"): p.update(ssid=c["ssid"], sspassword=c.get("sspassword", ""))
    if os.path.isfile(chemin):
        p["romtaille"] = os.path.getsize(chemin)
        k = crc32(chemin)
        if k: p["crc"] = k
    url = "https://api.screenscraper.fr/api2/jeuInfos.php?" + urllib.parse.urlencode(p)
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", "replace"))
    except Exception as e:
        if "429" in str(e) or "430" in str(e): time.sleep(5)
        return None
    jeu = (r.get("response") or {}).get("jeu")
    if not jeu: return None
    md = jeu.get("medias", [])
    for types, dest in ((("box-2D", "box-3D", "wheel"), dest_j), (("ss", "sstitle"), dest_e)):
        for t in types:
            m = choisir([x for x in md if x.get("type") == t])
            if m:
                try:
                    if telecharger(m["url"], dest): break
                except Exception: pass
    txt = lambda L: (choisir(L or []) or {}).get("text", "")
    genre = ""
    for g in jeu.get("genres", [])[:2]:
        n = next((x["text"] for x in g.get("noms", []) if x.get("langue") == "fr"), None) or next((x["text"] for x in g.get("noms", [])), "")
        genre += (", " if genre else "") + n
    return {"titre": txt(jeu.get("noms")), "annee": (txt(jeu.get("dates")) or "")[:4], "genre": genre,
            "editeur": (jeu.get("editeur") or {}).get("text", ""), "developpeur": (jeu.get("developpeur") or {}).get("text", ""),
            "joueurs": (jeu.get("joueurs") or {}).get("text", ""), "resume": txt(jeu.get("synopsis")), "note": (jeu.get("note") or {}).get("text", "")}

# ----------------------------------------------------------------------------- tout un lot
def scraper(lot, progres, arreter=lambda: False, refaire=False):
    """lot : [(console, chemin)] ; progres(fait, total, texte)."""
    c = conf(); ss = bool(c.get("devid") and c.get("devpassword"))
    fiches = {}; trouves = 0
    for k, (sid, chemin) in enumerate(lot):
        if arreter(): break
        d = dossier_media(sid); b = base(chemin)
        dj, de = os.path.join(d, b + ".png"), os.path.join(d, b + "-ecran.png")
        fi = fiches.setdefault(sid, infos(sid))
        progres(k, len(lot), "%s · %s" % (sid.upper(), b))
        if os.path.exists(dj) and b in fi and not refaire: continue
        info = screenscraper(sid, chemin, c, dj, de) if ss else None
        if not os.path.exists(dj): libretro(sid, chemin, dj, de)
        if info: fi[b] = info
        elif b not in fi: fi[b] = {}
        if os.path.exists(dj): trouves += 1
        json.dump(fi, open(os.path.join(d, "infos.json"), "w"), ensure_ascii=False, indent=1)
        time.sleep(1.1 if ss else .15)        # respect des limites de ScreenScraper
    progres(len(lot), len(lot), "")
    return trouves
