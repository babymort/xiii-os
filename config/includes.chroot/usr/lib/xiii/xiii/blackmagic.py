# OS XIII — Blackmagic XIII : tous les outils Blackmagic Design et de régie dans une seule interface, volet de catégories
# à gauche (ATEM, grille Videohub, HyperDeck, cartes DeckLink, DaVinci Resolve, caméras, Web Presenter, Stream Deck,
# Companion, NDI).
# • Les outils web (Companion, HyperDeck, Web Presenter, caméras…) s'ouvrent DANS l'interface, restent actifs quand on
#   change d'onglet, et se détachent en fenêtre volante (puis se rattachent).
# • Les logiciels Blackmagic pour Linux (Desktop Video, DaVinci Resolve) sont détectés ; ceux qui n'existent que pour
#   Windows / Mac (ATEM Software Control, Videohub, HyperDeck Setup) s'installent avec Applications Windows.
# • Vérification quotidienne des mises à jour (Companion depuis GitHub, paquets Blackmagic installés).
# Application développée par Matthieu Lamotte.
import os, sys, json, re, shutil, subprocess, time, glob, urllib.request
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, Gdk, GLib, Gio, WebKit
from . import config, systeme as S
from .ui import *
from .appli import preparer, Volet, page

CONF = os.path.expanduser("~/.config/xiii/blackmagic.json")
COMPANION = os.path.expanduser("~/.local/opt/companion")
SUPPORT = "https://www.blackmagicdesign.com/support/family/"
# clé, nom, icône, description, page de support, type d'appareil web (adresse IP mémorisée) ou None
CATEGORIES = [
    ("atem", "ATEM", "tv", "Mélangeurs ATEM : réglages, multiview, macros, tally", SUPPORT + "atem-live-production-switchers", None),
    ("videohub", "Grille Videohub", "grid-3x3", "Routage des grilles Videohub et Smart Videohub", SUPPORT + "routing-and-distribution", None),
    ("hyperdeck", "HyperDeck", "disc", "Enregistreurs HyperDeck : contrôle, gestion des médias par le web", SUPPORT + "disk-recorders", "hyperdeck"),
    ("desktopvideo", "Cartes DeckLink", "video", "Desktop Video : DeckLink, UltraStudio, Intensity", SUPPORT + "capture-and-playback", None),
    ("resolve", "DaVinci Resolve", "film", "Montage, étalonnage, effets, son", SUPPORT + "davinci-resolve-and-fusion", None),
    ("cameras", "Caméras", "camera", "Caméras Blackmagic : contrôle à distance par le réseau (REST)", SUPPORT + "professional-cameras", "camera"),
    ("webpresenter", "Web Presenter", "radio", "Web Presenter et Streaming Encoder : diffusion en direct", SUPPORT + "atem-live-production-switchers", "webpresenter"),
    ("streamdeck", "Stream Deck", "keyboard", "Stream Deck Elgato pilotés par Companion", None, None),
    ("companion", "Companion", "layout-grid", "Bitfocus Companion : boutons de régie pour ATEM, vMix, OBS, HyperDeck…", None, None),
    ("ndi", "NDI", "radio-tower", "NDI XIII, Retour plateau et moteur NDI", None, None),
    ("autres", "Autres logiciels", "package", "Convertisseurs, Teranex, Cloud et autres logiciels Blackmagic installés", SUPPORT + "converters", None),
]
LOGICIELS_WINDOWS = {"atem": "ATEM Software Control", "videohub": "Blackmagic Videohub", "hyperdeck": "HyperDeck Setup", "cameras": "Blackmagic Camera Setup",
                     "webpresenter": "Blackmagic Streaming Setup"}
# logiciels qu'on propose d'installer quand ils manquent (catégorie → noms attendus)
ATTENDUS = {"atem": ["ATEM Software Control", "ATEM Setup"], "videohub": ["Blackmagic Videohub Control", "Blackmagic Videohub Setup"],
            "hyperdeck": ["HyperDeck Setup"], "cameras": ["Blackmagic Camera Setup"], "webpresenter": ["Blackmagic Streaming Setup"]}

def conf():
    try: return json.load(open(CONF))
    except Exception: return {}

def sauver(c):
    os.makedirs(os.path.dirname(CONF), exist_ok=True); json.dump(c, open(CONF, "w"))

def version_paquet(p):
    try: return subprocess.run(["dpkg-query", "-W", "-f=${Version}", p], capture_output=True, text=True).stdout.strip()
    except Exception: return ""

def resolve():
    for p in ("/opt/resolve/bin/resolve", "/opt/resolve/bin/Resolve"):
        if os.path.exists(p): return p
    return None

def installer_companion(progres=lambda f, t: None):
    """Companion 4 et plus : les versions Linux sont publiées par l'API de Bitfocus (plus sur GitHub)."""
    import json
    arm = os.uname().machine in ("aarch64", "arm64")
    cible, motif = ("linux-arm64-tgz", "arm64") if arm else ("linux-tgz", "x64")
    req = urllib.request.Request("https://api.bitfocus.io/v1/product/companion/packages?limit=20", headers={"User-Agent": "OS-XIII"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    L = d if isinstance(d, list) else d.get("packages", [])
    p = next((x for x in L if x.get("target") == cible and motif in (x.get("uri") or "")), None)
    if not p: raise RuntimeError("pas de version Linux publiée par Bitfocus")
    tmp = os.path.join(GLib.get_tmp_dir(), "companion.tar.gz")
    def avance(n, bs, tot):
        if tot > 0: progres(min(1, n * bs / tot) * .9, "Téléchargement de Companion %s : %d %%" % (p.get("version", ""), min(100, n * bs * 100 // tot)))
    urllib.request.urlretrieve(p["uri"], tmp, avance)
    progres(.95, "Installation…")
    shutil.rmtree(COMPANION, ignore_errors=True); os.makedirs(COMPANION)
    subprocess.run(["tar", "-xf", tmp, "-C", COMPANION], check=True); os.unlink(tmp)
    c = conf(); c["companion_version"] = p.get("version", ""); sauver(c)
    S.progres("xiii-blackmagic.desktop", None)
    return p.get("version", "")

def companion_bin():
    for p in glob.glob(COMPANION + "/**/companion-launcher", recursive=True) + glob.glob(COMPANION + "/**/companion_headless.sh", recursive=True):
        return p
    return None

# ------------------------------------------------------------------ logiciels Blackmagic installés (Linux, Windows via Wine, Flatpak)
# motif du nom → catégorie (le premier qui correspond)
FAMILLES = [
    (r"atem", "atem"), (r"videohub", "videohub"), (r"hyperdeck", "hyperdeck"), (r"camera (setup|control)|blackmagic camera", "cameras"),
    (r"streaming|web presenter", "webpresenter"), (r"desktop ?video|media express|disk ?speed|decklink|ultrastudio", "desktopvideo"),
    (r"resolve|fusion|fairlight|davinci", "resolve"), (r"raw (player|speed)|blackmagic raw|braw", "cameras"),
    (r"teranex|converter|mini ?converter|cloud|multiview|smartscope|audio monitor", "autres"),
]
IGNORER = re.compile(r"(?i)uninstall|désinstall|desinstall|readme|lisez|manual|manuel|release notes|notes de version|license|licence|website|site web")
DOSSIERS_APPS = [os.path.expanduser("~/.local/share/applications"), "/usr/share/applications", "/usr/local/share/applications",
                 os.path.expanduser("~/.local/share/flatpak/exports/share/applications"), "/var/lib/flatpak/exports/share/applications"]

def logiciels_installes():
    """Tous les logiciels Blackmagic Design installés : {catégorie: [{nom, fichier, origine}]}.
    Cherche dans tous les raccourcis (y compris les sous-dossiers créés par Wine : wine/Programs/Blackmagic Design/…)."""
    vus, out = set(), {}
    for d in DOSSIERS_APPS:
        for f in glob.glob(d + "/**/*.desktop", recursive=True):
            try: t = open(f, errors="replace").read()
            except OSError: continue
            m = re.search(r"(?m)^Name=(.*)$", t); nom = m.group(1).strip() if m else os.path.basename(f)[:-8]
            ex = (re.search(r"(?m)^Exec=(.*)$", t) or [None, ""])[1]
            if re.search(r"(?m)^NoDisplay=true", t) and "wine" not in f: continue
            texte = (nom + " " + ex + " " + f).lower()
            blackmagic = "blackmagic" in texte or any(re.search(p, nom.lower()) for p, _ in FAMILLES[:2])
            if not blackmagic or IGNORER.search(nom) or f.endswith("xiii-blackmagic.desktop"): continue
            cat = next((c for p, c in FAMILLES if re.search(p, nom.lower())), "autres")
            if cat == "resolve" and "blackmagic" not in texte and "davinci" not in texte: continue
            cle = nom.lower()
            if cle in vus: continue
            vus.add(cle)
            origine = "Windows (Wine)" if ("wine" in texte or "/xiii-win-" in f) else "Flatpak" if "flatpak" in f else "Linux"
            out.setdefault(cat, []).append({"nom": nom, "fichier": f, "origine": origine})
    for L in out.values(): L.sort(key=lambda x: x["nom"].lower())
    return out

def lancer(fichier):
    try:
        a = Gio.DesktopAppInfo.new_from_filename(fichier)
        if a: a.launch([], Gdk.Display.get_default().get_app_launch_context()); return True
    except Exception: pass
    S.detacher(["gtk-launch", os.path.basename(fichier)]); return True

def windows_installe(nom):
    return any(nom.lower() in x["nom"].lower() for L in logiciels_installes().values() for x in L)


class Blackmagic(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.blackmagic"); self.webs = {}; self.volantes = {}

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".barre-web { padding: 6px 10px; } .etat-ok { color: #6fdc8c; } "
                 ".atem-bouton { border-radius: 10px; background: alpha(currentColor, .06); border: 1px solid alpha(currentColor, .15); } "
                 ".atem-pgm { background: #d93b3b; border-color: #ff6b6b; } .atem-pgm label { color: white; } "
                 ".atem-pvw { background: #2f9e44; border-color: #51cf66; } .atem-pvw label { color: white; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Blackmagic XIII"); self.win.set_default_size(1240, 800)
        self.volet = Volet("Blackmagic XIII", "Les outils de régie dans une seule fenêtre")
        self.installes = logiciels_installes()
        self.volet.ajouter("installes", "app-window", "Mes logiciels", rappel=lambda: self.page("installes"), section="Installés sur ce PC")
        for i, (k, n, ic, d, sup, web) in enumerate(CATEGORIES):
            self.volet.ajouter(k, ic, n, rappel=lambda k=k: self.page(k), section="Blackmagic Design" if i == 0 else ("Régie" if k == "streamdeck" else None))
        self.win.set_child(self.volet.racine); self.volet.aller("installes" if self.installes else "atem"); self.win.present()
        # un logiciel installé pendant que la fenêtre est ouverte (ou au retour sur la fenêtre) apparaît tout seul
        self.win.connect("notify::is-active", lambda w, *_: self.rafraichir() if w.is_active() else None)
        self._mon = []
        for d in (os.path.expanduser("~/.local/share/applications"), os.path.expanduser("~/.local/share/applications/wine/Programs")):
            try:
                m = Gio.File.new_for_path(d).monitor_directory(Gio.FileMonitorFlags.NONE, None); m.set_rate_limit(2000)
                m.connect("changed", lambda *_: GLib.timeout_add(1500, lambda: (self.rafraichir(), False)[1])); self._mon.append(m)
            except GLib.Error: pass
        GLib.timeout_add_seconds(5, lambda: (self.verifier_mises_a_jour(), False)[1])

    def rafraichir(self):
        n = logiciels_installes()
        if n == self.installes: return
        nouveaux = [x["nom"] for L in n.values() for x in L if x["nom"] not in [y["nom"] for M in self.installes.values() for y in M]]
        self.installes = n
        vis = self.volet.pile.get_visible_child_name()
        for k in ["installes"] + [c[0] for c in CATEGORIES]:
            if k in self.webs: continue
            x = self.volet.pile.get_child_by_name(k)
            if x: self.volet.pile.remove(x)
        if vis and vis not in self.webs: self.page(vis)
        if nouveaux: S.detacher(["notify-send", "-a", "Blackmagic XIII", "-i", "xiii-blackmagic", "Ajouté à Blackmagic XIII", ", ".join(nouveaux)])

    def bloc_installes(self, v, k):
        L = self.installes.get(k, [])
        if not L: return
        v.append(label("Installés sur ce PC", "section"))
        for x in L:
            self.ligne(v, "app-window", x["nom"], x["origine"], bouton("Ouvrir", None, "pilule", rappel=lambda f=x["fichier"]: lancer(f)))

    def p_installes(self, v):
        if not self.installes:
            v.append(label("Aucun logiciel Blackmagic installé pour l'instant. Installez-en un (par exemple ATEM Software Control avec Applications Windows) : "
                           "il apparaîtra ici tout seul, et dans la bonne catégorie.", "attenue", wrap=True))
            v.append(bouton("Installer un logiciel Windows…", "app-window", "pilule", rappel=lambda: S.detacher("xiii-windows")))
            return
        v.append(label("Tout ce qui vient de Blackmagic Design sur cet ordinateur, détecté automatiquement.", "attenue", wrap=True))
        noms = {c[0]: (c[1], c[2]) for c in CATEGORIES}
        for k in [c[0] for c in CATEGORIES]:
            if k not in self.installes: continue
            n, ic = noms[k]
            t = boite(False, 8); t.append(label(n, "section", hexpand=True))
            t.append(bouton("Voir", None, "plat", taille=13, rappel=lambda k=k: self.volet.aller(k))); v.append(t)
            for x in self.installes[k]:
                self.ligne(v, ic, x["nom"], x["origine"], bouton("Ouvrir", None, "pilule", rappel=lambda f=x["fichier"]: lancer(f)))

    # ------------------------------------------------------------------ pages
    def page(self, k):
        if k in self.webs and self.volet.pile.get_child_by_name(k): self.volet.pile.set_visible_child_name(k); return   # outil web resté actif
        if k == "installes":
            sc, v = page("Mes logiciels Blackmagic", "Détectés automatiquement sur cet ordinateur", "app-window")
            self.p_installes(v); self.remplacer(k, sc); return
        _, n, ic, d, sup, web = next(c for c in CATEGORIES if c[0] == k)
        sc, v = page(n, d, ic)
        self.bloc_installes(v, k)
        getattr(self, "p_" + k, lambda v: None)(v)
        if k in self.webs: return                    # l'outil web s'est ouvert dans l'onglet
        if web: self.bloc_web(v, k, web)
        if k in LOGICIELS_WINDOWS: self.bloc_windows(v, k)
        if sup: v.append(bouton("Téléchargements et manuels Blackmagic", "external-link", "fantome", rappel=lambda: S.detacher(["xdg-open", sup])))
        self.remplacer(k, sc)

    def remplacer(self, k, w):
        x = self.volet.pile.get_child_by_name(k)
        if x: self.volet.pile.remove(x)
        self.volet.pile.add_named(w, k); self.volet.pile.set_visible_child_name(k)

    def ligne(self, v, ic, titre, sous, droite=None):
        r = boite(False, 12, "reglage"); r.append(ico(ic, 20, "c")); col = boite(True, 0, hexpand=True)
        col.append(label(titre, "gras")); col.append(label(sous, "petit", "attenue", wrap=True)); r.append(col)
        if droite: r.append(droite)
        v.append(r); return r

    def p_atem(self, v):
        # ---- pupitre : piloter l'ATEM directement (Programme / Preview / CUT / AUTO / noir)
        v.append(label("Pupitre ATEM", "section"))
        c = conf(); r = boite(False, 8)
        e = Gtk.Entry(text=c.get("atem_ip", ""), placeholder_text="Adresse IP de l'ATEM (ex. 192.168.10.240)", hexpand=True); r.append(e)
        r.append(bouton("Connecter", "plug", "pilule", rappel=lambda: self.atem_connecter(e.get_text().strip()))); v.append(r)
        self.atem_zone = boite(True, 10); v.append(self.atem_zone)
        if c.get("atem_ip"): GLib.idle_add(lambda: (self.atem_connecter(c["atem_ip"]), False)[1])
        else: self.atem_zone.append(label("Indiquez l'adresse de l'ATEM (affichée dans ATEM Setup, ou trouvée par le Scanner IP XIII).", "attenue", "petit", wrap=True))
        v.append(label("Autres outils", "section"))
        self.ligne(v, "siren", "Tally XIII", "Lampes de tally sur téléphones et boîtiers, branchées sur l'ATEM (natif OS XIII)", bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-tally")))
        self.ligne(v, "layout-grid", "Companion", "Boutons de régie pour l'ATEM (Stream Deck ou écran tactile)", bouton("Ouvrir", None, "fantome", rappel=lambda: self.volet.aller("companion")))

    def atem_connecter(self, ip):
        if not ip: return
        from .atem import ATEM
        c = conf(); c["atem_ip"] = ip; sauver(c)
        if getattr(self, "atem", None): self.atem.arreter()
        self.atem = ATEM(ip, lambda et: GLib.idle_add(self.atem_dessin, et)); self.atem.start()
        vider(self.atem_zone); self.atem_zone.append(label("Connexion à %s…" % ip, "attenue"))
        if not getattr(self, "_atem_touches", False):
            self._atem_touches = True
            k = Gtk.EventControllerKey()
            def touche(_c, kv, _code, st):
                if self.volet.pile.get_visible_child_name() != "atem" or not getattr(self, "atem", None) or isinstance(self.win.get_focus(), Gtk.Text): return False
                ent = self.atem.etat.get("entrees") or []
                if Gdk.KEY_1 <= kv <= Gdk.KEY_9 and kv - Gdk.KEY_1 < len(ent):
                    (self.atem.programme if st & Gdk.ModifierType.SHIFT_MASK else self.atem.preview)(ent[kv - Gdk.KEY_1]); return True
                if kv == Gdk.KEY_space: self.atem.cut(); return True
                if kv in (Gdk.KEY_Return, Gdk.KEY_KP_Enter): self.atem.auto(); return True
                return False
            k.connect("key-pressed", touche); self.win.add_controller(k)

    def atem_dessin(self, et):
        z = self.atem_zone
        if not z.get_root(): return False
        sig = repr((et["connecte"], et["programme"], et["preview"], et["noir"], et["transition"], sorted(et["noms"].items())))
        if sig == getattr(self, "_atem_sig", None): return False
        self._atem_sig = sig; vider(z)
        z.append(label(et["message"], "petit", "attenue" if not et["connecte"] else "accent"))
        if not et["connecte"]: return False
        ent = et.get("entrees") or sorted(et["noms"])
        for titre, cle, fn, css in (("Programme", "programme", self.atem.programme, "pgm"), ("Preview", "preview", self.atem.preview, "pvw")):
            z.append(label(titre, "petit", "gras"))
            g = Gtk.FlowBox(max_children_per_line=10, selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6)
            for i, src in enumerate(ent):
                b = Gtk.Button(); b.add_css_class("atem-bouton")
                if et[cle] == src: b.add_css_class("atem-" + css)
                b.set_child(label(et["courts"].get(src) or str(src), "gras", xalign=0.5)); b.set_tooltip_text("%s%s" % (et["noms"].get(src, src), (" — touche %d%s" % (i + 1, " + Maj" if cle == "programme" else "")) if i < 9 else ""))
                b.set_size_request(74, 54); b.connect("clicked", lambda _b, s_=src, f_=fn: f_(s_)); g.append(b)
            z.append(g)
        r = boite(False, 10, margin_top=6)
        for t_, ic, fn, css in (("CUT", "scissors", self.atem.cut, "atem-cut"), ("AUTO", "blend", self.atem.auto, "atem-auto"), ("NOIR", "moon", self.atem.noir, "atem-ftb")):
            b = bouton(t_, ic, "pilule" if t_ != "NOIR" else "fantome", rappel=fn); b.set_size_request(120, 48)
            if t_ == "NOIR" and et["noir"]: b.add_css_class("atem-pgm")
            if t_ == "AUTO" and et["transition"]: b.add_css_class("atem-pvw")
            r.append(b)
        z.append(r)
        z.append(label("Clavier : 1 à 9 = Preview · Maj + 1 à 9 = Programme · Espace = CUT · Entrée = AUTO", "petit", "attenue"))
        return False

    def p_desktopvideo(self, v):
        ver = version_paquet("desktopvideo")
        self.ligne(v, "check" if ver else "circle-alert", "Pilote Desktop Video", ("Installé · version %s" % ver) if ver else "Non installé",
                   bouton("Paramètres", None, "pilule", rappel=lambda: S.detacher(["xiii-parametres", "--page", "acquisition"])))
        if shutil.which("BlackmagicDesktopVideoSetup"):
            self.ligne(v, "settings", "Blackmagic Desktop Video Setup", "Formats, connecteurs, mise à jour du firmware des cartes", bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher("BlackmagicDesktopVideoSetup")))
        if shutil.which("MediaExpress") or os.path.exists("/usr/bin/MediaExpress"):
            self.ligne(v, "film", "Media Express", "Capture et lecture", bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher("MediaExpress")))

    def p_resolve(self, v):
        r = resolve()
        if r: self.ligne(v, "check", "DaVinci Resolve", "Installé", bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher([r])))
        else:
            self.ligne(v, "download", "DaVinci Resolve pour Linux", "L'assistant vérifie la carte graphique, installe les pilotes, repère le fichier téléchargé et installe Resolve",
                       bouton("Assistant d'installation", None, "pilule", rappel=lambda: S.detacher(["xiii-resolve"])))
            v.append(label("Resolve demande une carte graphique récente (NVIDIA conseillée, 4 Go de mémoire vidéo ou plus).", "petit", "attenue", wrap=True))

    def p_streamdeck(self, v):
        MODELES = {"0fd9": "Elgato Stream Deck", "05f3": "X-keys", "2ec2": "Loupedeck", "0b33": "Contour Shuttle"}
        trouves = []
        for d in glob.glob("/sys/bus/usb/devices/*/idVendor"):
            try:
                vid = open(d).read().strip()
                if vid in MODELES:
                    nom = open(os.path.join(os.path.dirname(d), "product")).read().strip() if os.path.exists(os.path.join(os.path.dirname(d), "product")) else ""
                    trouves.append("%s %s" % (MODELES[vid], nom.replace(MODELES[vid], "").strip()))
            except OSError: pass
        v.append(label("Pupitres branchés", "section"))
        if trouves:
            for t_ in trouves: self.ligne(v, "keyboard", t_.strip(), "Reconnu, utilisable sans mot de passe par Companion", None)
        else:
            v.append(label("Aucun Stream Deck, X-keys ou Loupedeck branché pour l'instant.", "attenue"))
        from . import config
        c = config.charger()
        v.append(label("Boutons XIII", "section"))
        v.append(label("Branchez un Stream Deck Elgato : il affiche tout seul deux pages — « Régie ATEM » (programme en rouge, preview en vert, CUT, AUTO, noir, "
                       "avec l'ATEM réglé dans la page ATEM) et « Apps XIII » (régie, prompteur, mesure audio, Multiview, captures, micro…). Le dernier bouton change de page. "
                       "Quand Companion est ouvert, il reprend la main.", "attenue", wrap=True))
        sw = Gtk.Switch(active=c.get("streamdeck_xiii", True), valign=Gtk.Align.CENTER); sw.connect("notify::active", lambda w, _p: config.modifier(streamdeck_xiii=w.get_active()))
        self.ligne(v, "keyboard", "Pages de boutons XIII", "Sans Companion, prêt à l'emploi", sw)
        self.ligne(v, "file-json" if os.path.exists("/usr/share/xiii/lucide/file-json.svg") else "file", "Modifier les pages", "Fichier ~/.config/xiii/streamdeck.json (créé à la première ouverture)",
                   bouton("Ouvrir", None, "fantome", rappel=self.editer_streamdeck))
        v.append(label("Pour des boutons plus poussés (vMix, OBS, caméras…), utilisez Bitfocus Companion.", "attenue", wrap=True))
        self.ligne(v, "layout-grid", "Companion", "Configurer les boutons", bouton("Ouvrir", None, "pilule", rappel=lambda: self.volet.aller("companion")))

    def editer_streamdeck(self):
        from . import streamdeck as SD
        if not os.path.exists(SD.CONF):
            os.makedirs(os.path.dirname(SD.CONF), exist_ok=True); json.dump(SD.PAGES_DEFAUT, open(SD.CONF, "w"), ensure_ascii=False, indent=1)
        S.detacher(["xdg-open", SD.CONF])

    def p_ndi(self, v):
        self.ligne(v, "radio-tower", "NDI XIII", "Sorties GRAPHICO / MELANGO en NDI, diffusion RTMP / SRT", bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-ndi")))
        self.ligne(v, "monitor-play", "Retour plateau", "Afficher une source NDI en plein écran", bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher("xiii-retour")))
        self.ligne(v, "layout-grid", "Multiview NDI", "Les sources du réseau en mosaïque 2 × 2, 3 × 3 ou 4 × 4", bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher("xiii-multiview")))
        self.ligne(v, "settings", "Moteur NDI", "Installation et version du runtime NDI", bouton("Paramètres", None, "fantome", rappel=lambda: S.detacher(["xiii-parametres", "--page", "ndi"])))

    def p_companion(self, v):
        b = companion_bin(); c = conf()
        if not b:
            self.ligne(v, "download", "Installer Companion", "Dernière version Linux publiée par Bitfocus", bouton("Installer", None, "pilule", rappel=lambda: self.installer_companion(v)))
            return
        auto = os.path.join(GLib.get_user_config_dir(), "autostart", "companion.desktop")
        def auto_(on):
            os.makedirs(os.path.dirname(auto), exist_ok=True)
            if on: open(auto, "w").write("[Desktop Entry]\nType=Application\nName=Companion\nExec=%s\nX-GNOME-Autostart-enabled=true\n" % b)
            elif os.path.exists(auto): os.unlink(auto)
        cb = Gtk.CheckButton(label="Lancer Companion à l'ouverture de session", active=os.path.exists(auto)); cb.connect("toggled", lambda w: auto_(w.get_active())); v.append(cb)
        import socket
        try: socket.create_connection(("127.0.0.1", 8000), timeout=.3).close(); actif = True
        except OSError: actif = False
        if not actif:
            S.detacher([b]); self.ligne(v, "loader", "Démarrage de Companion…", "L'interface s'affiche ici dans quelques secondes", None)
            GLib.timeout_add_seconds(6, lambda: (self.ouvrir_web(None, "companion", "http://127.0.0.1:8000/"), False)[1]); return
        self.ouvrir_web(v, "companion", "http://127.0.0.1:8000/")

    def installer_companion(self, v):
        pb = Gtk.ProgressBar(show_text=True); v.append(pb); pb.set_text("Recherche de la dernière version…")
        def progres(f, t): GLib.idle_add(lambda: (pb.set_fraction(f), pb.set_text(t), False)[2])
        S.en_fond(lambda: installer_companion(progres),
                  lambda r: (pb.set_text(("Erreur : %s" % r) if isinstance(r, Exception) else "Companion %s installé" % r), self.page("companion") if not isinstance(r, Exception) else None))

    # ------------------------------------------------------------------ outils web intégrés
    def bloc_web(self, v, k, typ):
        c = conf(); ips = c.get("ip_" + k, [])
        v.append(label("Appareils sur le réseau", "section"))
        r = boite(False, 8); e = Gtk.Entry(placeholder_text="Adresse IP de l'appareil (ex. 192.168.1.50)", hexpand=True)
        def ajouter(*_):
            ip = e.get_text().strip()
            if not ip: return
            c2 = conf(); L = [x for x in c2.get("ip_" + k, []) if x != ip] + [ip]; c2["ip_" + k] = L; sauver(c2); self.ouvrir_web(None, k, "http://%s/" % ip)
        e.connect("activate", ajouter); r.append(e); r.append(bouton("Ouvrir", "globe", "pilule", rappel=ajouter)); v.append(r)
        for ip in ips: self.ligne(v, "globe", ip, "Interface web de l'appareil", bouton("Ouvrir", None, "fantome", rappel=lambda ip=ip: self.ouvrir_web(None, k, "http://%s/" % ip)))
        v.append(label("Astuce : le Scanner IP XIII trouve l'adresse des appareils Blackmagic du réseau.", "petit", "attenue"))

    def ouvrir_web(self, v, k, url):
        """L'outil web s'affiche dans l'interface, reste actif d'un onglet à l'autre, et peut devenir une fenêtre volante."""
        if k in self.webs:
            wv = self.webs[k]["vue"]
            if wv.get_uri() != url: wv.load_uri(url)
            if k in self.volantes: self.volantes[k].present(); return
            self.volet.pile.set_visible_child_name(k); return
        wv = WebKit.WebView(); wv.load_uri(url)
        cont = boite(True, 0)
        barre = boite(False, 8, "barre-web"); lb = label(url, "petit", "attenue", hexpand=True, ellipsize=True); barre.append(ico("globe", 14, "c")); barre.append(lb)
        barre.append(bouton(None, "refresh-cw", "plat", taille=14, tip="Recharger", rappel=wv.reload))
        bvol = bouton("Fenêtre volante", "picture-in-picture-2", "fantome", taille=14, rappel=lambda: self.detacher(k)); barre.append(bvol)
        cont.append(barre); cont.append(Gtk.Separator()); wv.set_vexpand(True); cont.append(wv)
        wv.connect("notify::uri", lambda w, *_: lb.set_text(w.get_uri() or ""))
        self.webs[k] = {"vue": wv, "cont": cont, "barre": barre, "bvol": bvol}
        self.remplacer(k, cont)

    def detacher(self, k):
        w = self.webs[k]
        if k in self.volantes:                                  # rattacher à son onglet
            f = self.volantes.pop(k); f.set_child(None); self.remplacer(k, w["cont"]); f.destroy()
            w["bvol"].set_child(boite(False, 6)); w["bvol"].get_child().append(ico("picture-in-picture-2", 14)); w["bvol"].get_child().append(label("Fenêtre volante")); return
        self.volet.pile.remove(w["cont"])
        f = Gtk.Window(application=self, title="Blackmagic XIII — " + next(c[1] for c in CATEGORIES if c[0] == k)); f.set_default_size(980, 680)
        f.set_child(w["cont"]); f.connect("close-request", lambda *_: (self.detacher(k), True)[1]); self.volantes[k] = f; f.present()
        w["bvol"].set_child(boite(False, 6)); w["bvol"].get_child().append(ico("panel-left", 14)); w["bvol"].get_child().append(label("Rattacher"))
        sc, v = page(next(c[1] for c in CATEGORIES if c[0] == k), "L'outil est ouvert en fenêtre volante.", "picture-in-picture-2")
        v.append(bouton("Rattacher ici", "panel-left", "pilule", rappel=lambda: self.detacher(k)))
        self.volet.pile.add_named(sc, k); self.volet.pile.set_visible_child_name(k)

    # ------------------------------------------------------------------ logiciels Windows
    def bloc_windows(self, v, k):
        manque = [n for n in ATTENDUS.get(k, [LOGICIELS_WINDOWS[k]]) if not any(n.lower() in x["nom"].lower() or x["nom"].lower() in n.lower() for x in self.installes.get(k, []))]
        if not manque: return
        v.append(label("À installer (Windows / Mac seulement)", "section"))
        for nom in manque:
            self.ligne(v, "download", nom, "Blackmagic ne le publie pas pour Linux : téléchargez la version Windows, OS XIII l'installe avec Applications Windows. "
                       "Une fois installé, il apparaît ici tout seul.",
                       bouton("Installer…", None, "fantome", rappel=lambda: (S.detacher(["xdg-open", next(c[4] for c in CATEGORIES if c[0] == k)]), S.detacher("xiii-windows"))))

    # ------------------------------------------------------------------ mises à jour (une fois par jour)
    def verifier_mises_a_jour(self):
        c = conf()
        if time.time() - c.get("verif", 0) < 86400: return
        def tache():
            msg = []
            if companion_bin():
                d = json.load(urllib.request.urlopen(urllib.request.Request("https://api.bitfocus.io/v1/product/companion/packages?limit=20", headers={"User-Agent": "OS-XIII"}), timeout=30))
                L = d if isinstance(d, list) else d.get("packages", [])
                t = next((x.get("version") for x in L if (x.get("target") or "").startswith("linux")), None)
                if t and t != c.get("companion_version"): msg.append("Companion %s" % t)
            if version_paquet("desktopvideo"):
                o = subprocess.run(["apt-get", "-s", "upgrade"], capture_output=True, text=True).stdout
                if "desktopvideo" in o: msg.append("Desktop Video")
            return msg
        def fin(m):
            c2 = conf(); c2["verif"] = time.time(); sauver(c2)
            if isinstance(m, list) and m: S.detacher(["notify-send", "-a", "Blackmagic XIII", "-i", "software-update-available", "Mises à jour disponibles", ", ".join(m)])
        S.en_fond(tache, fin)

def main():
    sys.exit(Blackmagic().run(sys.argv))
