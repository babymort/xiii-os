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
]
LOGICIELS_WINDOWS = {"atem": "ATEM Software Control", "videohub": "Blackmagic Videohub", "hyperdeck": "HyperDeck Setup", "cameras": "Blackmagic Camera Setup",
                     "webpresenter": "Blackmagic Streaming Setup"}

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

def companion_bin():
    for p in glob.glob(COMPANION + "/**/companion-launcher", recursive=True) + glob.glob(COMPANION + "/**/companion_headless.sh", recursive=True):
        return p
    return None

def windows_installe(nom):
    return any(nom.lower() in f.lower() for f in glob.glob(os.path.expanduser("~/.local/share/applications/wine-*.desktop")) + glob.glob(os.path.expanduser("~/.local/share/applications/xiii-win-*.desktop")))


class Blackmagic(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.blackmagic"); self.webs = {}; self.volantes = {}

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".barre-web { padding: 6px 10px; } .etat-ok { color: #6fdc8c; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Blackmagic XIII"); self.win.set_default_size(1240, 800)
        self.volet = Volet("Blackmagic XIII", "Les outils de régie dans une seule fenêtre")
        for i, (k, n, ic, d, sup, web) in enumerate(CATEGORIES):
            self.volet.ajouter(k, ic, n, rappel=lambda k=k: self.page(k), section="Blackmagic Design" if i == 0 else ("Régie" if k == "streamdeck" else None))
        self.win.set_child(self.volet.racine); self.volet.aller("atem"); self.win.present()
        GLib.timeout_add_seconds(5, lambda: (self.verifier_mises_a_jour(), False)[1])

    # ------------------------------------------------------------------ pages
    def page(self, k):
        if k in self.webs and self.volet.pile.get_child_by_name(k): self.volet.pile.set_visible_child_name(k); return   # outil web resté actif
        _, n, ic, d, sup, web = next(c for c in CATEGORIES if c[0] == k)
        sc, v = page(n, d, ic)
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
        self.ligne(v, "siren", "Tally XIII", "Lampes de tally sur téléphones et boîtiers, branchées sur l'ATEM (natif OS XIII)", bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-tally")))
        self.ligne(v, "layout-grid", "Companion", "Boutons de régie pour l'ATEM (Stream Deck ou écran tactile)", bouton("Ouvrir", None, "fantome", rappel=lambda: self.volet.aller("companion")))

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
            self.ligne(v, "download", "DaVinci Resolve pour Linux", "Gratuit, à télécharger chez Blackmagic (formulaire), puis double-clic sur le fichier .run téléchargé",
                       bouton("Télécharger", None, "pilule", rappel=lambda: S.detacher(["xdg-open", "https://www.blackmagicdesign.com/products/davinciresolve"])))
            v.append(label("Resolve demande une carte graphique récente (NVIDIA conseillée, 4 Go de mémoire vidéo ou plus).", "petit", "attenue", wrap=True))

    def p_streamdeck(self, v):
        v.append(label("Sous OS XIII, les Stream Deck Elgato sont pilotés par Bitfocus Companion : branchez le Stream Deck, ouvrez Companion, il est reconnu tout seul.", "attenue", wrap=True))
        self.ligne(v, "layout-grid", "Companion", "Configurer les boutons", bouton("Ouvrir", None, "pilule", rappel=lambda: self.volet.aller("companion")))

    def p_ndi(self, v):
        self.ligne(v, "radio-tower", "NDI XIII", "Sorties GRAPHICO / MELANGO en NDI, diffusion RTMP / SRT", bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-ndi")))
        self.ligne(v, "monitor-play", "Retour plateau", "Afficher une source NDI en plein écran", bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher("xiii-retour")))
        self.ligne(v, "settings", "Moteur NDI", "Installation et version du runtime NDI", bouton("Paramètres", None, "fantome", rappel=lambda: S.detacher(["xiii-parametres", "--page", "ndi"])))

    def p_companion(self, v):
        b = companion_bin(); c = conf()
        if not b:
            self.ligne(v, "download", "Installer Companion", "Dernière version Linux depuis GitHub (bitfocus/companion)", bouton("Installer", None, "pilule", rappel=lambda: self.installer_companion(v)))
            return
        import socket
        try: socket.create_connection(("127.0.0.1", 8000), timeout=.3).close(); actif = True
        except OSError: actif = False
        if not actif:
            S.detacher([b]); self.ligne(v, "loader", "Démarrage de Companion…", "L'interface s'affiche ici dans quelques secondes", None)
            GLib.timeout_add_seconds(6, lambda: (self.ouvrir_web(None, "companion", "http://127.0.0.1:8000/"), False)[1]); return
        self.ouvrir_web(v, "companion", "http://127.0.0.1:8000/")

    def installer_companion(self, v):
        pb = Gtk.ProgressBar(show_text=True); v.append(pb); pb.set_text("Recherche de la dernière version…")
        def tache():
            sys.path.insert(0, "/usr/lib/xiii")
            from xiii.store_github import requete, meilleur_fichier
            rel = requete("/repos/bitfocus/companion/releases/latest"); a, typ = meilleur_fichier(rel["assets"])
            if not a: raise RuntimeError("pas de version Linux")
            tmp = os.path.join(GLib.get_tmp_dir(), a["name"])
            urllib.request.urlretrieve(a["browser_download_url"], tmp)
            shutil.rmtree(COMPANION, ignore_errors=True); os.makedirs(COMPANION)
            subprocess.run(["tar", "-xf", tmp, "-C", COMPANION], check=True); os.unlink(tmp)
            c = conf(); c["companion_version"] = rel["tag_name"]; sauver(c); return rel["tag_name"]
        S.en_fond(tache, lambda r: (pb.set_text(("Erreur : %s" % r) if isinstance(r, Exception) else "Companion %s installé ✓" % r), self.page("companion") if not isinstance(r, Exception) else None))

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
        nom = LOGICIELS_WINDOWS[k]
        v.append(label("Logiciel Blackmagic (Windows / Mac seulement)", "section"))
        if windows_installe(nom):
            self.ligne(v, "app-window", nom, "Installé avec Applications Windows", bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher(["gtk-launch", next(os.path.basename(f) for f in glob.glob(os.path.expanduser("~/.local/share/applications/*.desktop")) if nom.lower() in open(f, errors="replace").read().lower())])))
        else:
            self.ligne(v, "app-window", nom, "Blackmagic ne le publie pas pour Linux : téléchargez la version Windows, OS XIII l'installe avec Applications Windows (fonctionnement à vérifier selon le logiciel)",
                       bouton("Installer…", None, "fantome", rappel=lambda: (S.detacher(["xdg-open", next(c[4] for c in CATEGORIES if c[0] == k)]), S.detacher("xiii-windows"))))

    # ------------------------------------------------------------------ mises à jour (une fois par jour)
    def verifier_mises_a_jour(self):
        c = conf()
        if time.time() - c.get("verif", 0) < 86400: return
        def tache():
            msg = []
            if companion_bin():
                sys.path.insert(0, "/usr/lib/xiii"); from xiii.store_github import requete
                t = requete("/repos/bitfocus/companion/releases/latest").get("tag_name")
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
