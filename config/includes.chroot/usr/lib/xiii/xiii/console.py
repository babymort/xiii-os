# OS XIII — Console XIII : l'interface du mode Gaming, façon Batocera, aux couleurs de la Suite XIII.
# Carrousel des consoles (nom de la console, pas de l'émulateur), liste des jeux, lancement plein écran,
# manette / clavier / souris. Les émulateurs absents de Debian s'installent à la demande (Flathub, GitHub).
# Jeux, BIOS et clés ne sont pas fournis : ~/Jeux/<console>/ et ~/Jeux/bios/.
# Application développée par Matthieu Lamotte.
import os, sys, json, glob, shutil, subprocess, threading, re, urllib.request
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, Gdk, GLib, Gio, WebKit
from . import systeme as SY

JEUX = os.path.expanduser("~/Jeux")
BIOS = os.path.join(JEUX, "bios")
CORES = (glob.glob("/usr/lib/*-linux-gnu/libretro") or ["/usr/lib/x86_64-linux-gnu/libretro"])[0]
HTML = "/usr/share/xiii/console/index.html"

def ra(core):     # RetroArch + cœur libretro, plein écran
    return ["retroarch", "-f", "-L", os.path.join(CORES, core + "_libretro.so"), "{rom}"]
def med():        # Mednafen
    return ["mednafen", "-video.fs", "1", "{rom}"]
def fp(app, *args):
    return ["flatpak", "run", app] + list(args) + ["{rom}"]

# id, nom de la console, fabricant, année, support (cartouche/disque/portable/ordinateur/arcade), couleurs, extensions,
# commande, source (apt:<binaire|cœur> / flatpak:<id> / lichii), remarque (BIOS, clés…)
S = [
    ("switch", "Switch / Switch 2", "Nintendo", 2017, "portable", ("#e60012", "#00c3e3"), "nsp xci nca nro nsz xcz", ["{lichii}", "{rom}"], "lichii", "Clés (prod.keys, title.keys) et firmware de VOTRE console à ajouter au premier lancement"),
    ("wiiu", "Wii U", "Nintendo", 2012, "disque", ("#009ac7", "#1d1d1b"), "wud wux rpx wua", fp("info.cemu.Cemu", "-f", "-g"), "flatpak:info.cemu.Cemu", "Clés de VOTRE console (keys.txt) à ajouter dans Cemu"),
    ("wii", "Wii", "Nintendo", 2006, "disque", ("#8f9aa3", "#34bee7"), "iso wbfs rvz gcz ciso wad", ["dolphin-emu", "-b", "-e", "{rom}"], "apt:dolphin-emu", ""),
    ("gamecube", "GameCube", "Nintendo", 2001, "disque", ("#6a5acd", "#2b1e6b"), "iso gcm rvz gcz ciso", ["dolphin-emu", "-b", "-e", "{rom}"], "apt:dolphin-emu", ""),
    ("n64", "Nintendo 64", "Nintendo", 1996, "cartouche", ("#1e8c45", "#f2b800"), "z64 n64 v64", ["mupen64plus", "--fullscreen", "{rom}"], "apt:mupen64plus", ""),
    ("snes", "Super Nintendo", "Nintendo", 1990, "cartouche", ("#5b4b9a", "#b8b8c8"), "sfc smc zip 7z", ra("snes9x"), "apt:core:snes9x", ""),
    ("nes", "NES", "Nintendo", 1983, "cartouche", ("#c8102e", "#3a3a3a"), "nes zip 7z", ra("nestopia"), "apt:core:nestopia", ""),
    ("3ds", "Nintendo 3DS", "Nintendo", 2011, "portable", ("#d4001c", "#4a4a4a"), "3ds cci cxi app", fp("org.azahar_emu.Azahar"), "flatpak:org.azahar_emu.Azahar", "Jeux décryptés depuis VOTRE console"),
    ("nds", "Nintendo DS", "Nintendo", 2004, "portable", ("#2b2b2b", "#c9c9c9"), "nds zip", ["desmume", "{rom}"], "apt:desmume", ""),
    ("gba", "Game Boy Advance", "Nintendo", 2001, "portable", ("#4b2bb0", "#a597e8"), "gba zip", ra("mgba"), "apt:core:mgba", ""),
    ("gbc", "Game Boy Color", "Nintendo", 1998, "portable", ("#7b2fbe", "#f7c600"), "gbc zip", ra("gambatte"), "apt:core:gambatte", ""),
    ("gb", "Game Boy", "Nintendo", 1989, "portable", ("#8b956d", "#0f380f"), "gb zip", ra("gambatte"), "apt:core:gambatte", ""),
    ("virtualboy", "Virtual Boy", "Nintendo", 1995, "portable", ("#c4001a", "#1a0000"), "vb vboy zip", ra("mednafen_vb"), "apt:core:mednafen_vb", ""),
    ("ps3", "PlayStation 3", "Sony", 2006, "disque", ("#1b1b1b", "#6b6b6b"), "iso pkg", fp("net.rpcs3.RPCS3", "--no-gui"), "flatpak:net.rpcs3.RPCS3", "Firmware officiel PS3 (PS3UPDAT.PUP) à installer dans RPCS3"),
    ("ps2", "PlayStation 2", "Sony", 2000, "disque", ("#1f2a6b", "#0b0f2b"), "iso chd cso bin", fp("net.pcsx2.PCSX2", "-fullscreen", "-batch"), "flatpak:net.pcsx2.PCSX2", "BIOS de VOTRE PS2 dans ~/Jeux/bios"),
    ("psp", "PSP", "Sony", 2004, "portable", ("#2a2a2a", "#7d8a99"), "iso cso pbp chd", fp("org.ppsspp.PPSSPP", "--fullscreen"), "flatpak:org.ppsspp.PPSSPP", ""),
    ("psx", "PlayStation", "Sony", 1994, "disque", ("#5d6670", "#c7c9cc"), "cue chd pbp m3u bin iso", med(), "apt:mednafen", "BIOS (scph5501.bin…) de VOTRE console dans ~/.mednafen/firmware"),
    ("xbox", "Xbox", "Microsoft", 2001, "disque", ("#107c10", "#0b2b0b"), "iso xiso", fp("app.xemu.xemu", "-full-screen", "-dvd_path"), "flatpak:app.xemu.xemu", "BIOS, MCPX et disque dur de VOTRE Xbox à régler dans xemu"),
    ("dreamcast", "Dreamcast", "Sega", 1998, "disque", ("#e85d04", "#f2f2f2"), "cdi gdi chd cue", fp("org.flycast.Flycast"), "flatpak:org.flycast.Flycast", ""),
    ("saturn", "Saturn", "Sega", 1994, "disque", ("#2c2c54", "#9a9ad1"), "cue chd iso m3u", med(), "apt:mednafen", "BIOS de VOTRE Saturn dans ~/.mednafen/firmware"),
    ("segacd", "Mega-CD", "Sega", 1991, "disque", ("#1b1b1b", "#e5383b"), "cue chd iso", ra("genesis_plus_gx"), "apt:core:genesis_plus_gx", "BIOS Mega-CD dans ~/Jeux/bios"),
    ("megadrive", "Mega Drive", "Sega", 1988, "cartouche", ("#111111", "#d90429"), "md gen smd bin zip", ra("genesis_plus_gx"), "apt:core:genesis_plus_gx", ""),
    ("mastersystem", "Master System", "Sega", 1985, "cartouche", ("#b00020", "#202020"), "sms zip", ra("genesis_plus_gx"), "apt:core:genesis_plus_gx", ""),
    ("gamegear", "Game Gear", "Sega", 1990, "portable", ("#1c1c1c", "#3a86ff"), "gg zip", ra("genesis_plus_gx"), "apt:core:genesis_plus_gx", ""),
    ("pcengine", "PC Engine", "NEC", 1987, "cartouche", ("#f4f4f4", "#e63946"), "pce cue chd zip", med(), "apt:mednafen", ""),
    ("neogeo", "Neo Geo", "SNK", 1990, "arcade", ("#c9a227", "#1a1a1a"), "zip 7z", ["mame", "-rompath", "{dossier}", "{nom}"], "apt:mame", "BIOS neogeo.zip à placer avec les jeux"),
    ("ngp", "Neo Geo Pocket", "SNK", 1998, "portable", ("#3d405b", "#e07a5f"), "ngp ngc zip", med(), "apt:mednafen", ""),
    ("arcade", "Arcade", "MAME", 1980, "arcade", ("#7209b7", "#f72585"), "zip 7z chd", ["mame", "-rompath", "{dossier}", "{nom}"], "apt:mame", "Jeux au format MAME correspondant à la version installée"),
    ("lynx", "Lynx", "Atari", 1989, "portable", ("#ff8800", "#222222"), "lnx zip", med(), "apt:mednafen", "BIOS lynxboot.img dans ~/.mednafen/firmware"),
    ("atari2600", "Atari 2600", "Atari", 1977, "cartouche", ("#8b5a2b", "#1a1a1a"), "a26 bin zip", ["stella", "-fullscreen", "1", "{rom}"], "apt:stella", ""),
    ("atari800", "Atari 800", "Atari", 1979, "ordinateur", ("#5e503f", "#c6ac8f"), "atr xex xfd car", ["atari800", "-fullscreen", "{rom}"], "apt:atari800", ""),
    ("atarist", "Atari ST", "Atari", 1985, "ordinateur", ("#3a3a3a", "#9ad1d4"), "st msa stx dim", ["hatari", "--fullscreen", "{rom}"], "apt:hatari", "TOS de VOTRE Atari ST, ou EmuTOS (libre)"),
    ("wonderswan", "WonderSwan", "Bandai", 1999, "portable", ("#00a6a6", "#efca08"), "ws wsc zip", ra("mednafen_wswan"), "apt:core:mednafen_wswan", ""),
    ("amiga", "Amiga", "Commodore", 1985, "ordinateur", ("#1d3557", "#e63946"), "adf ipf hdf lha", ["fs-uae", "--fullscreen", "{rom}"], "apt:fs-uae", "Kickstart de VOTRE Amiga dans ~/Documents/FS-UAE/Kickstarts"),
    ("c64", "Commodore 64", "Commodore", 1982, "ordinateur", ("#6c5eb5", "#a5a5ff"), "d64 t64 prg crt tap", ["x64sc", "-fullscreen", "-autostart", "{rom}"], "apt:x64sc", "ROM Commodore (kernal, basic, chargen) à ajouter dans ~/.local/share/vice/C64"),
    ("msx", "MSX", "MSX", 1983, "ordinateur", ("#0f4c81", "#f2f2f2"), "rom mx1 mx2 dsk", ["openmsx", "{rom}"], "apt:openmsx", ""),
    ("zxspectrum", "ZX Spectrum", "Sinclair", 1982, "ordinateur", ("#1b1b1b", "#ff3b3b"), "tap tzx z80 sna", ["fuse-gtk", "--full-screen", "{rom}"], "apt:fuse-gtk", ""),
    ("dos", "DOS", "PC", 1981, "ordinateur", ("#000080", "#c0c0c0"), "exe com bat", ["dosbox", "-fullscreen", "-exit", "{rom}"], "apt:dosbox", ""),
    ("scummvm", "ScummVM", "Point & clic", 1987, "ordinateur", ("#4a7c59", "#f4d35e"), "scummvm", ["scummvm", "-f", "--path={dossier}", "--auto-detect"], "apt:scummvm", "Un dossier par jeu"),
]

PAQUETS = {"core:nestopia": "libretro-nestopia", "core:snes9x": "libretro-snes9x", "core:mgba": "libretro-mgba", "core:gambatte": "libretro-gambatte",
           "core:genesis_plus_gx": "libretro-genesisplusgx", "core:mednafen_vb": "libretro-beetle-vb", "core:mednafen_wswan": "libretro-beetle-wswan",
           "mupen64plus": "mupen64plus-ui-console", "x64sc": "vice", "fuse-gtk": "fuse-emulator-gtk", "steam": "steam-installer"}

def flatpak_installe(app):
    try: return subprocess.run(["flatpak", "info", app], capture_output=True, timeout=5).returncode == 0
    except Exception: return False

def lichii():
    return os.path.expanduser("~/.local/share/xiii/lichii/Lichii.AppImage")

def installe(src):
    if src == "lichii": return os.path.exists(lichii())
    t, _, x = src.partition(":")
    if t == "flatpak": return flatpak_installe(x)
    if x.startswith("core:"): return os.path.exists(os.path.join(CORES, x[5:] + "_libretro.so")) and bool(shutil.which("retroarch"))
    return bool(shutil.which(x))

def jeux_de(sid, exts):
    d = os.path.join(JEUX, sid); L = []
    if not os.path.isdir(d): return L
    ex = set("." + e for e in exts.split())
    for racine, dossiers, fichiers in os.walk(d):
        if racine.count(os.sep) - d.count(os.sep) > 2: continue
        if sid == "scummvm" and racine != d: continue
        if sid == "scummvm":
            L += [{"nom": x, "chemin": os.path.join(racine, x), "taille": 0} for x in sorted(dossiers) if not x.startswith(".")]
            break
        for f in fichiers:
            if os.path.splitext(f)[1].lower() in ex and not f.startswith("."):
                p = os.path.join(racine, f)
                if sid in ("psx", "saturn", "segacd", "pcengine") and f.lower().endswith(".bin") and os.path.exists(os.path.splitext(p)[0] + ".cue"): continue
                L.append({"nom": nettoyer(f), "chemin": p, "taille": os.path.getsize(p)})
    return sorted(L, key=lambda j: j["nom"].lower())

def nettoyer(f):
    n = os.path.splitext(f)[0]
    n = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", n).replace("_", " ").strip()
    return n or f

def jeux_steam():
    L = [{"nom": "Steam Big Picture", "chemin": "steam:bigpicture", "taille": 0, "special": True}]
    for base in (os.path.expanduser("~/.local/share/Steam"), os.path.expanduser("~/.steam/steam")):
        for f in glob.glob(os.path.join(base, "steamapps", "appmanifest_*.acf")):
            try:
                t = open(f, encoding="utf-8", errors="replace").read()
                aid = re.search(r'"appid"\s+"(\d+)"', t).group(1); nom = re.search(r'"name"\s+"([^"]+)"', t).group(1)
                if "Proton" in nom or "Steamworks" in nom or "Runtime" in nom: continue
                if not any(j["chemin"] == "steam:" + aid for j in L): L.append({"nom": nom, "chemin": "steam:" + aid, "taille": 0})
            except Exception:
                pass
        if len(L) > 1: break
    return L

def jeux_pc():
    L = []
    for a in Gio.AppInfo.get_all():
        if not isinstance(a, Gio.DesktopAppInfo) or not a.should_show(): continue
        cats = a.get_categories() or ""
        if "Game" in cats and a.get_id() not in ("steam.desktop", "retroarch.desktop", "org.libretro.RetroArch.desktop", "xiii-console.desktop") and "Emulator" not in cats:
            L.append({"nom": a.get_display_name(), "chemin": "app:" + a.get_id(), "taille": 0})
    return sorted(L, key=lambda j: j["nom"].lower())

def donnees():
    out = [{"id": "steam", "nom": "Steam", "fabricant": "Valve", "annee": 2003, "support": "pc", "c1": "#1b2838", "c2": "#66c0f4",
            "jeux": jeux_steam(), "installe": bool(shutil.which("steam")), "source": "apt:steam", "remarque": "", "exts": "", "dossier": ""},
           {"id": "pc", "nom": "Jeux PC", "fabricant": "OS XIII", "annee": 2026, "support": "pc", "c1": "#2a1f16", "c2": "#f0b378",
            "jeux": jeux_pc(), "installe": True, "source": "", "remarque": "Jeux Linux installés et jeux Windows installés avec Applications Windows", "exts": "", "dossier": ""}]
    for sid, nom, fab, an, sup, (c1, c2), exts, cmd, src, rem in S:
        out.append({"id": sid, "nom": nom, "fabricant": fab, "annee": an, "support": sup, "c1": c1, "c2": c2, "exts": exts,
                    "jeux": jeux_de(sid, exts), "installe": installe(src), "source": src, "remarque": rem, "dossier": os.path.join(JEUX, sid)})
    return out

def enrichir(d):
    """Ajoute jaquette, capture et fiche (ScreenScraper / libretro) à chaque jeu."""
    try:
        sys.path.insert(0, "/usr/lib/xiii"); from xiii import scraper
    except Exception:
        return d
    for s in d:
        if s["id"] in ("steam", "pc"): continue
        fi = scraper.infos(s["id"])
        for g in s["jeux"]:
            j, e = scraper.medias(s["id"], g["chemin"])
            if j: g["jaquette"] = "file://" + j
            if e: g["ecran"] = "file://" + e
            info = fi.get(scraper.base(g["chemin"]))
            if info: g["info"] = info
    return d

def preparer_dossiers():
    os.makedirs(BIOS, exist_ok=True)
    for sid, nom, fab, an, sup, cols, exts, cmd, src, rem in S:
        d = os.path.join(JEUX, sid); os.makedirs(d, exist_ok=True)
        lis = os.path.join(d, "_LISEZ-MOI.txt")
        if not os.path.exists(lis):
            open(lis, "w").write("%s (%s, %d)\nDéposez ici vos jeux : %s\n%s\nOS XIII ne fournit ni jeux, ni BIOS, ni clés : utilisez uniquement des copies de vos propres jeux.\n"
                                 % (nom, fab, an, ", ".join("." + e for e in exts.split()), rem))


class Console(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.console")
        self.proc = None; self.manettes = None; self.scrape_en_cours = False

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer_dossiers()
        self.win = Gtk.ApplicationWindow(application=self, title="Console XIII"); self.win.set_default_size(1280, 720)
        ucm = WebKit.UserContentManager(); ucm.register_script_message_handler("xiii", None)
        ucm.connect("script-message-received::xiii", self.message)
        self.vue = WebKit.WebView(user_content_manager=ucm)
        st = self.vue.get_settings(); st.set_property("enable-developer-extras", False)
        for k in ("allow-file-access-from-file-urls", "allow-universal-access-from-file-urls"):
            try: st.set_property(k, True)
            except Exception: pass
        # manettes natives (libmanette) : fonctionnent même si le moteur web ne gère pas les manettes
        try:
            sys.path.insert(0, "/usr/lib/xiii"); from xiii.manette import Manettes
            self.manettes = Manettes(self.pad, combo=self.quitter_jeu)
        except Exception:
            self.manettes = None
        try: st.set_property("enable-webgl", True)
        except Exception: pass
        self.vue.set_background_color(Gdk.RGBA(red=.05, green=.05, blue=.06, alpha=1))
        self.win.set_child(self.vue)
        self.charger()
        if "--fenetre" not in sys.argv: self.win.fullscreen()
        self.win.present()
        GLib.timeout_add_seconds(4, lambda: (self.scraper(silencieux=True), False)[1])   # jaquettes manquantes en arrière-plan

    def pad(self, n):
        if self.proc and self.proc.poll() is None: return          # en jeu : la manette appartient à l'émulateur
        n = {"select": "menu", "accueil": "menu", "l": "pg", "r": "pd", "x": "x"}.get(n, n)
        self.js("action(%s)" % json.dumps(n))

    def quitter_jeu(self):
        """Select + Start ou bouton Accueil : quitte le jeu en cours (tous les émulateurs) et revient à la console."""
        if self.proc and self.proc.poll() is None and not getattr(self, "proc_steam", False):   # Steam garde son propre bouton Accueil
            import signal
            try: os.killpg(self.proc.pid, signal.SIGTERM)
            except Exception: pass
            GLib.timeout_add(2500, self._forcer)

    def _forcer(self):
        import signal
        if self.proc and self.proc.poll() is None:
            try: os.killpg(self.proc.pid, signal.SIGKILL)
            except Exception: pass
        return False

    def scraper(self, sid=None, silencieux=False, refaire=False):
        if self.scrape_en_cours: return
        try:
            sys.path.insert(0, "/usr/lib/xiii"); from xiii import scraper as SC
        except Exception:
            return
        lot = []
        for s in donnees():
            if s["id"] in ("steam", "pc") or (sid and s["id"] != sid): continue
            for g in s["jeux"]:
                if refaire or not SC.medias(s["id"], g["chemin"])[0]: lot.append((s["id"], g["chemin"]))
        if not lot:
            if not silencieux: self.js("toast('Toutes les jaquettes sont déjà là')")
            return
        self.scrape_en_cours = True
        def progres(k, n, t):
            GLib.idle_add(lambda: (self.js("scrapage(%d,%d,%s)" % (k, n, json.dumps(t))), False)[1])
            if k > 0:
                sid2, ch = lot[k - 1]; j, e = SC.medias(sid2, ch); info = SC.infos(sid2).get(SC.base(ch))
                GLib.idle_add(lambda: (self.js("majMedias(%s,%s,%s,%s,%s)" % (json.dumps(sid2), json.dumps(ch), json.dumps("file://" + j if j else None),
                                                                              json.dumps("file://" + e if e else None), json.dumps(info))), False)[1])
        def tache():
            try: n = SC.scraper(lot, progres, refaire=refaire)
            except Exception: n = -1
            self.scrape_en_cours = False
            GLib.idle_add(lambda: (self.js("toast(%s)" % json.dumps("%d jaquette(s) récupérée(s)" % n if n >= 0 else "Récupération des jaquettes impossible")), False)[1])
        threading.Thread(target=tache, daemon=True).start()

    def charger(self):
        try: html = open(HTML, encoding="utf-8").read()
        except OSError: html = "<h1 style='color:#fff'>Console XIII introuvable</h1>"
        cfg = {}
        try:
            sys.path.insert(0, "/usr/lib/xiii"); from xiii import config, theme
            c = config.charger(); p = theme.palette(c); cfg = {"accent": p["accent"], "fond": p["fond"], "demo": bool(os.environ.get("XIII_DEMO"))}
        except Exception:
            cfg = {"accent": "#f0b378", "fond": "#141210"}
        d = enrichir(donnees())
        if cfg.get("demo"):
            for s in d:
                if s["id"] in ("megadrive", "snes", "gba", "psx", "n64", "gamegear", "arcade"):
                    s["jeux"] = [{"nom": n, "chemin": "/demo/" + n, "taille": 2_400_000} for n in ("Aventure du pixel", "Course de nuit", "Le donjon perdu", "Pong Royale", "Rétro Rally")]
                    s["installe"] = True
        cfg["manette_native"] = bool(self.manettes and self.manettes.ok)
        cfg["reprise"] = getattr(self, "reprise", None)
        html = html.replace("/*DONNEES*/", "window.SYSTEMES = %s; window.CFG = %s;" % (json.dumps(d, ensure_ascii=False), json.dumps(cfg)))
        self.vue.load_html(html, "file:///usr/share/xiii/console/")

    def js(self, code):
        self.vue.evaluate_javascript(code, -1, None, None, None, None, None)

    def message(self, ucm, val):
        try: m = json.loads(val.to_json(0))
        except Exception: return
        a = m.get("a")
        if a == "lancer": self.lancer(m["sys"], m["jeu"])
        elif a == "dossier": subprocess.Popen(["thunar", os.path.join(JEUX, m.get("sys") or "")])
        elif a == "bios": subprocess.Popen(["thunar", BIOS])
        elif a == "installer": self.installer(m["sys"])
        elif a == "rescanner": self.reprise = m.get("reprise"); self.charger()
        elif a == "scraper": self.scraper(m.get("sys"), refaire=bool(m.get("refaire")))
        elif a == "quitter": self.quit()
        elif a == "bureau":
            try:
                from xiii import config; config.modifier(mode_bureau="classique")
            except Exception: pass
            self.quit()
        elif a == "eteindre": subprocess.Popen(["systemctl", "poweroff"])
        elif a == "fenetre": self.win.unfullscreen() if self.win.is_fullscreen() else self.win.fullscreen()

    def lancer(self, sid, chemin):
        if self.proc and self.proc.poll() is None: return
        if chemin == "steam:bigpicture": cmd = ["steam", "-gamepadui"]
        elif chemin.startswith("steam:"): cmd = ["steam", "-gamepadui", "steam://rungameid/" + chemin[6:]]
        elif chemin.startswith("app:"):
            a = Gio.DesktopAppInfo.new(chemin[4:])
            if a: a.launch([], None)
            return
        else:
            e = next((x for x in S if x[0] == sid), None)
            if not e: return
            cmd = [c.replace("{rom}", chemin).replace("{dossier}", os.path.dirname(chemin) if sid != "scummvm" else chemin)
                    .replace("{nom}", os.path.splitext(os.path.basename(chemin))[0]).replace("{lichii}", lichii()) for c in e[7]]
        self.proc_steam = cmd[0] == "steam"
        try:
            self.proc = subprocess.Popen(cmd, start_new_session=True)
        except OSError as ex:
            self.js("toast(%s)" % json.dumps("Lancement impossible : %s" % ex)); return
        self.js("enJeu(true)")
        def attendre():
            self.proc.wait(); GLib.idle_add(lambda: (self.js("enJeu(false)"), self.win.present(), False)[2])
        threading.Thread(target=attendre, daemon=True).start()

    def installer(self, sid):
        e = next((x for x in S if x[0] == sid), None)
        if not e: return
        src = e[8]
        def etat(t, fini=False, ok=True):
            m = re.search(r"(\d+)\s*%", t or "")
            SY.progres("xiii-console.desktop", None if fini else (int(m.group(1)) / 100 if m else 0.05))
            GLib.idle_add(lambda: (self.js("installation(%s,%s,%s,%s)" % (json.dumps(sid), json.dumps(t), json.dumps(fini), json.dumps(ok))), False)[1])
        def tache():
            try:
                if src == "lichii":
                    etat("Recherche de la dernière version de Lichii…")
                    req = urllib.request.Request("https://api.github.com/repos/zortos293/Lichii/releases", headers={"User-Agent": "OS-XIII"})
                    for r in json.load(urllib.request.urlopen(req, timeout=30)):
                        im = [x for x in r.get("assets", []) if x["name"].lower().endswith(".appimage") and not re.search(r"arm|aarch64", x["name"], re.I)]
                        if im:
                            f = lichii(); os.makedirs(os.path.dirname(f), exist_ok=True)
                            etat("Téléchargement de Lichii %s…" % r.get("tag_name", ""))
                            urllib.request.urlretrieve(im[0]["browser_download_url"], f + ".part"); os.chmod(f + ".part", 0o755); os.replace(f + ".part", f)
                            etat("Lichii installé", True); return
                    etat("Pas de version Linux publiée pour l'instant", True, False); return
                t, _, app = src.partition(":")
                if t == "flatpak":
                    etat("Installation depuis Flathub…")
                    subprocess.run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo"], capture_output=True)
                    p = subprocess.Popen(["flatpak", "install", "--user", "-y", "--noninteractive", "flathub", app], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for l in p.stdout:
                        m = re.search(r"(\d+)%", l)
                        if m: etat("Installation : %s %%" % m.group(1))
                    ok = p.wait() == 0
                    etat("Émulateur installé" if ok else "Installation impossible (connexion Internet ?)", True, ok); return
                if app in ("steam", "steam-installer"):
                    etat("Installation de Steam (mot de passe administrateur)…")
                    r = subprocess.run(["pkexec", "/usr/local/bin/xiii-installer-steam"], capture_output=True, text=True)
                    etat("Steam installé" if r.returncode == 0 else "Installation annulée ou impossible", True, r.returncode == 0); return
                paq = [PAQUETS.get(app, app)] + (["retroarch"] if app.startswith("core:") else [])
                etat("Installation de %s (mot de passe administrateur)…" % paq[0])
                r = subprocess.run(["pkexec", "sh", "-c", "apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y " + " ".join(paq)], capture_output=True, text=True)
                etat("Émulateur installé" if r.returncode == 0 else "Installation annulée ou impossible", True, r.returncode == 0)
            except Exception as ex:
                etat("Erreur : %s" % ex, True, False)
        threading.Thread(target=tache, daemon=True).start()

def main():
    sys.exit(Console().run([sys.argv[0]]))
