# OS XIII — Centre de logiciels XIII : un catalogue choisi pour la production et le quotidien (paquets Debian, Flathub,
# GitHub), plus toute la logithèque Flathub en recherche. Installer / ouvrir / retirer en un clic, sans terminal.
# Application développée par Matthieu Lamotte.
import os, sys, json, re, shutil, subprocess, threading, urllib.request, urllib.parse, time
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S
from .ui import *
from .appli import preparer, Volet, page

# clé, nom, description, source (apt:paquet | flatpak:id | github:auteur/projet | web:url | deb:url|paquet), commande ou .desktop, icône
CATALOGUE = {
    "Partage de fichiers": [
        ("localsend", "LocalSend", "Envoyer des fichiers entre téléphones et PC du même réseau, comme AirDrop", "github:localsend/localsend", "localsend_app", "share-2"),
        ("pairdrop", "PairDrop", "AirDrop dans le navigateur (successeur de Snapdrop), rien à installer sur le téléphone", "web:https://pairdrop.net/", None, "globe"),
        ("croc", "croc", "Envoi chiffré par code, n'importe où (interface dans Transferts XIII)", "github:schollz/croc", "xiii-transferts", "send"),
        ("wormhole", "Magic Wormhole", "Envoi chiffré par code (interface dans Transferts XIII)", "apt:magic-wormhole", "xiii-transferts", "send"),
        ("transferts", "Transferts XIII", "Gofile, WeTransfer, Smash, partage local, croc, Wormhole", "inclus", "xiii-transferts", "send"),
    ],
    "Réseau et diagnostic": [
        ("tailscale", "Tailscale", "Réseau privé entre vos appareils, partout dans le monde (réglages : Paramètres › Tailscale)", "apt:tailscale", "xiii-parametres --page tailscale", "shield"),
        ("wireshark", "Wireshark", "Analyse du trafic réseau, paquet par paquet", "apt:wireshark", "wireshark", "activity"),
        ("iperf3", "Test de débit XIII", "Mesure du débit entre deux PC (iperf3), avec une vraie interface", "apt:iperf3", "xiii-debit", "gauge"),
        ("kismet", "Kismet", "Détection des réseaux et appareils Wi-Fi / Bluetooth", "apt:kismet", "kismet", "radar"),
        ("scanip", "Scanner IP XIII", "Tous les appareils du réseau (comme Advanced IP Scanner)", "inclus", "xiii-scanip", "radar"),
        ("qrwifi", "QR Wi-Fi XIII", "QR code d'un réseau Wi-Fi, à imprimer ou partager", "inclus", "xiii-qrwifi", "qr-code"),
        ("wifidb", "WiFiDB", "Base de données collaborative des réseaux Wi-Fi (site web)", "web:https://wifidb.net/", None, "globe"),
    ],
    "Production et régie": [
        ("companion", "Bitfocus Companion", "Stream Deck et boutons de régie (ATEM, vMix, OBS, HyperDeck…) — aussi dans Blackmagic XIII", "github:bitfocus/companion", "xiii-blackmagic", "layout-grid"),
        ("obs", "OBS Studio", "Enregistrement et diffusion en direct", "apt:obs-studio", "obs", "radio"),
        ("kdenlive", "Kdenlive", "Montage vidéo", "apt:kdenlive", "kdenlive", "film"),
        ("shotcut", "Shotcut", "Montage vidéo simple et léger", "apt:shotcut", "shotcut", "film"),
        ("handbrake", "HandBrake", "Conversion vidéo", "apt:handbrake", "ghb", "file-video"),
        ("audacity", "Audacity", "Montage et nettoyage audio", "apt:audacity", "audacity", "audio-lines"),
        ("ardour", "Ardour", "Studio d'enregistrement multipiste", "apt:ardour", "ardour8", "sliders-horizontal"),
        ("qlcplus", "QLC+", "Console lumière DMX", "apt:qlcplus", "qlcplus", "lightbulb"),
        ("mixxx", "Mixxx", "Logiciel de DJ", "apt:mixxx", "mixxx", "disc"),
        ("blender", "Blender", "3D, animation, montage", "apt:blender", "blender", "box"),
        ("gimp", "GIMP", "Retouche photo", "apt:gimp", "gimp", "image"),
        ("krita", "Krita", "Dessin et peinture", "apt:krita", "krita", "brush"),
        ("inkscape", "Inkscape", "Dessin vectoriel, logos", "apt:inkscape", "inkscape", "pen-tool"),
        ("darktable", "darktable", "Développement des photos RAW", "apt:darktable", "darktable", "aperture"),
    ],
    "Bureau à distance et streaming": [
        ("moonlight", "Moonlight", "Jouer à distance sur un PC avec Sunshine / GeForce", "flatpak:com.moonlight_stream.Moonlight", None, "monitor-play"),
        ("sunshine", "Sunshine", "Diffuser ce PC vers Moonlight (jeux, bureau)", "github:LizardByte/Sunshine", "sunshine", "sun"),
        ("parsec", "Parsec", "Bureau à distance très faible latence", "deb:https://builds.parsec.app/package/parsec-linux.deb|parsec", "parsecd", "monitor"),
        ("rustdesk", "RustDesk", "Bureau à distance libre (alternative à TeamViewer / AnyDesk)", "github:rustdesk/rustdesk", "rustdesk", "monitor"),
        ("remmina", "Remmina", "Connexions RDP, VNC, SSH", "apt:remmina", "remmina", "monitor"),
    ],
    "Clavier, souris et téléphone": [
        ("inputleap", "Input Leap", "Un clavier et une souris pour plusieurs PC (successeur de Barrier)", "flatpak:io.github.input_leap.input-leap", None, "mouse"),
        ("kdeconnect", "KDE Connect", "Téléphone ↔ PC : notifications, fichiers, presse-papiers, télécommande", "apt:kdeconnect", "kdeconnect-app", "smartphone"),
        ("phonebox", "PhoneBox", "Le téléphone en tableau de bord du PC", "inclus", "xiii-phonebox", "smartphone"),
    ],
    "Jeux": [
        ("retroarch", "RetroArch", "Émulateurs rétro (aussi dans la Console XIII)", "apt:retroarch", "retroarch", "gamepad-2"),
        ("lutris", "Lutris", "Jeux GOG, Epic, Battle.net… sous Linux", "apt:lutris", "lutris", "gamepad-2"),
        ("heroic", "Heroic", "Jeux Epic Games, GOG et Amazon", "flatpak:com.heroicgameslauncher.hgl", None, "gamepad-2"),
        ("prism", "Prism Launcher", "Minecraft Java, plusieurs versions et mods", "flatpak:org.prismlauncher.PrismLauncher", None, "box"),
    ],
    "Internet et quotidien": [
        ("steam", "Steam", "Boutique et bibliothèque de jeux PC (licence de Valve acceptée à l'installation)", "steam", "steam", "gamepad-2"),
        ("wine32", "Wine 32 bits", "Pour les anciens logiciels Windows en 32 bits", "apt:wine32:i386", None, "app-window"),
        ("chromium", "Chromium", "Navigateur web (base de Chrome)", "apt:chromium", "chromium", "globe"),
        ("plex", "Plex", "Vos films, séries et musiques, depuis votre serveur Plex", "inclus", "xiii-plex", "monitor-play"),
        ("plexdesktop", "Plex (application)", "Application Plex complète", "flatpak:tv.plex.PlexDesktop", None, "monitor-play"),
        ("plexserver", "Plex Media Server", "Faire de ce PC un serveur Plex pour la maison", "plexserver", None, "server"),
        ("libreoffice", "LibreOffice", "Traitement de texte, tableur, présentations", "apt:libreoffice", "libreoffice", "file-text"),
        ("thunderbird", "Thunderbird", "Courriel et agenda", "apt:thunderbird", "thunderbird", "mail"),
        ("spotify", "Spotify", "Musique en ligne", "flatpak:com.spotify.Client", None, "music"),
        ("discord", "Discord", "Discussions vocales et texte", "flatpak:com.discordapp.Discord", None, "message-circle"),
        ("signal", "Signal", "Messagerie chiffrée", "flatpak:org.signal.Signal", None, "message-circle"),
        ("obsidian", "Obsidian", "Notes reliées entre elles", "flatpak:md.obsidian.Obsidian", None, "notebook-pen"),
        ("bitwarden", "Bitwarden", "Gestionnaire de mots de passe", "flatpak:com.bitwarden.desktop", None, "key-round"),
    ],
}

def tous():
    return [x for L in CATALOGUE.values() for x in L]

def installe(src):
    t, _, v = src.partition(":")
    try:
        if src == "inclus": return True
        if t == "apt": return subprocess.run(["dpkg-query", "-W", "-f=${Status}", v], capture_output=True, text=True).stdout.endswith("installed")
        if t == "flatpak": return subprocess.run(["flatpak", "info", v], capture_output=True).returncode == 0
        if t == "deb": return subprocess.run(["dpkg-query", "-W", "-f=${Status}", v.split("|")[1]], capture_output=True, text=True).stdout.endswith("installed")
        if t == "github":
            from .store_github import suivi
            nom = v.split("/")[1].lower()
            return v in suivi() or any(nom in p.lower() for p in os.listdir("/usr/share/applications"))
        if src == "plexserver": return os.path.exists("/usr/lib/plexmediaserver")
        if src == "steam": return bool(shutil.which("steam"))
        if t == "web": return True
    except Exception:
        pass
    return False

def installer(src, progres):
    t, _, v = src.partition(":")
    if t == "apt":
        progres("Installation (mot de passe administrateur)…")
        r = subprocess.run(["pkexec", "sh", "-c", ("dpkg --add-architecture i386; " if ":i386" in v else "") + "apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y " + v], capture_output=True, text=True)
        if r.returncode: raise RuntimeError("installation annulée ou impossible")
    elif t == "flatpak":
        progres("Installation depuis Flathub…")
        subprocess.run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo"], capture_output=True)
        p = subprocess.Popen(["flatpak", "install", "--user", "-y", "--noninteractive", "flathub", v], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for l in p.stdout:
            m = re.search(r"(\d+)%", l)
            if m: progres("Installation : %s %%" % m.group(1))
        if p.wait(): raise RuntimeError("installation impossible (connexion Internet ?)")
    elif t == "github":
        from .store_github import installer as gh
        gh(v, lambda f, txt: progres(txt))
    elif t == "deb":
        url, paq = v.split("|"); progres("Téléchargement…")
        f = os.path.join(GLib.get_tmp_dir(), paq + ".deb"); urllib.request.urlretrieve(url, f)
        progres("Installation (mot de passe administrateur)…")
        if subprocess.run(["pkexec", "sh", "-c", "DEBIAN_FRONTEND=noninteractive apt-get install -y '%s'" % f]).returncode: raise RuntimeError("installation annulée")
    elif src == "steam":
        progres("Installation de Steam (mot de passe administrateur)…")
        if subprocess.run(["pkexec", "/usr/local/bin/xiii-installer-steam"]).returncode: raise RuntimeError("installation annulée ou impossible")
    elif src == "plexserver":
        progres("Recherche de la dernière version de Plex Media Server…")
        d = json.load(urllib.request.urlopen("https://plex.tv/api/downloads/5.json", timeout=30))
        rel = d["computer"]["Linux"]["releases"]
        u = next(x["url"] for x in rel if x["url"].endswith("_amd64.deb"))
        f = os.path.join(GLib.get_tmp_dir(), "plexmediaserver.deb"); urllib.request.urlretrieve(u, f)
        progres("Installation (mot de passe administrateur)…")
        if subprocess.run(["pkexec", "sh", "-c", "DEBIAN_FRONTEND=noninteractive apt-get install -y '%s'" % f]).returncode: raise RuntimeError("installation annulée")

def retirer(src):
    t, _, v = src.partition(":")
    if t == "apt": return subprocess.run(["pkexec", "apt-get", "remove", "-y", v]).returncode == 0
    if t == "flatpak": return subprocess.run(["flatpak", "uninstall", "--user", "-y", "--noninteractive", v]).returncode == 0 or subprocess.run(["pkexec", "flatpak", "uninstall", "-y", v]).returncode == 0
    if t == "deb": return subprocess.run(["pkexec", "apt-get", "remove", "-y", v.split("|")[1]]).returncode == 0
    if src == "plexserver": return subprocess.run(["pkexec", "apt-get", "remove", "-y", "plexmediaserver"]).returncode == 0
    if t == "github":
        from .store_github import suivi, desinstaller
        e = suivi().get(v)
        if e: desinstaller(e); return True
    return False

def lancer(src, cmd):
    t, _, v = src.partition(":")
    if t == "web": S.detacher(["xdg-open", v]); return
    if t == "flatpak": S.detacher(["flatpak", "run", v]); return
    if cmd: S.detacher(cmd.split())


class Centre(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.logiciels")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".logiciel { padding: 12px; } .etat-ok { color: #6fdc8c; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Centre de logiciels XIII"); self.win.set_default_size(1120, 760)
        self.volet = Volet("Logiciels", "Installer, ouvrir, retirer — sans terminal")
        for i, cat in enumerate(CATALOGUE):
            self.volet.ajouter("c%d" % i, ["share-2", "network", "clapperboard", "monitor", "mouse", "gamepad-2", "globe"][i], cat, rappel=lambda c=cat, i=i: self.p_cat(c, "c%d" % i), section="Sélection XIII" if i == 0 else None)
        self.volet.ajouter("flathub", "search", "Rechercher sur Flathub", rappel=self.p_flathub, section="Tous les logiciels")
        self.volet.ajouter("github", "package", "Store GitHub", rappel=lambda: S.detacher("xiii-store-github"))
        self.volet.ajouter("maj", "refresh-cw", "Mises à jour", rappel=self.p_maj)
        self.win.set_child(self.volet.racine); self.volet.aller("c0"); self.win.present()

    def remplacer(self, cle, w):
        v = self.volet.pile.get_child_by_name(cle)
        if v: self.volet.pile.remove(v)
        self.volet.pile.add_named(w, cle); self.volet.pile.set_visible_child_name(cle)

    def p_cat(self, cat, cle):
        sc, v = page(cat, None, None)
        g = Gtk.FlowBox(max_children_per_line=2, min_children_per_line=1, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, homogeneous=True)
        for x in CATALOGUE[cat]: g.append(self.carte(*x))
        v.append(g); self.remplacer(cle, sc)

    def carte(self, k, nom, desc, src, cmd, ic):
        c = boite(True, 6, "carte", "logiciel")
        h = boite(False, 10); h.append(ico(ic, 26, "c")); col = boite(True, 0, hexpand=True); col.append(label(nom, "gras"))
        orig = {"apt": "Debian", "flatpak": "Flathub", "github": "GitHub", "web": "Site web", "deb": "Éditeur", "inclus": "OS XIII", "plexserver": "Plex"}[src.split(":")[0]]
        col.append(label(orig, "petit", "attenue")); h.append(col)
        zone = boite(False, 6, valign=Gtk.Align.CENTER); h.append(zone); c.append(h)
        c.append(label(desc, "petit", wrap=True))
        etat = label("", "petit", "attenue", wrap=True); c.append(etat)
        def maj(ok):
            vider(zone)
            if src.startswith("web:") or src == "inclus":
                zone.append(bouton("Ouvrir", None, "pilule", rappel=lambda: lancer(src, cmd))); return
            if ok:
                zone.append(bouton("Ouvrir", None, "pilule", rappel=lambda: lancer(src, cmd)))
                zone.append(bouton(None, "trash-2", "plat", tip="Retirer", rappel=lambda: S.en_fond(lambda: retirer(src), lambda r: S.en_fond(lambda: installe(src), maj))))
            else:
                zone.append(bouton("Installer", "download", "pilule", rappel=go))
        def go():
            vider(zone); zone.append(Gtk.Spinner(spinning=True))
            S.en_fond(lambda: installer(src, lambda t: GLib.idle_add(lambda: (etat.set_text(t), False)[1])),
                      lambda r: (etat.set_text(("Erreur : %s" % r) if isinstance(r, Exception) else "Installé ✓"), S.en_fond(lambda: installe(src), maj)))
        S.en_fond(lambda: installe(src), maj)
        return c

    def p_flathub(self):
        sc, v = page("Rechercher sur Flathub", "Toute la logithèque Linux : plus de 3 000 applications", "search")
        e = Gtk.SearchEntry(placeholder_text="ex. montage vidéo, VLC, Steam, Teams…"); v.append(e)
        zone = boite(True, 8); v.append(zone)
        def go(*_):
            q = e.get_text().strip()
            if not q: return
            vider(zone); zone.append(label("Recherche…", "attenue"))
            def cherche():
                req = urllib.request.Request("https://flathub.org/api/v2/search", data=json.dumps({"query": q, "filters": []}).encode(),
                                             headers={"Content-Type": "application/json", "User-Agent": "OS-XIII"})
                return json.load(urllib.request.urlopen(req, timeout=20)).get("hits", [])[:30]
            def fin(H):
                vider(zone)
                if isinstance(H, Exception) or not H: zone.append(label("Aucun résultat (connexion Internet ?).", "attenue")); return
                g = Gtk.FlowBox(max_children_per_line=2, min_children_per_line=1, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, homogeneous=True)
                for h in H:
                    g.append(self.carte(h["app_id"], h.get("name", h["app_id"]), (h.get("summary") or "")[:160], "flatpak:" + h["app_id"], None, "package"))
                zone.append(g)
            S.en_fond(cherche, fin)
        e.connect("activate", go); self.remplacer("flathub", sc); e.grab_focus()

    def p_maj(self):
        sc, v = page("Mises à jour", "Système, applications Flathub et logiciels GitHub", "refresh-cw")
        etat = label("", "attenue", wrap=True); v.append(etat)
        def tout():
            etat.set_text("Mise à jour en cours (mot de passe administrateur)…")
            def t():
                a = subprocess.run(["pkexec", "sh", "-c", "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get -y upgrade"], capture_output=True).returncode
                f = subprocess.run(["flatpak", "update", "--user", "-y", "--noninteractive"], capture_output=True).returncode
                return a, f
            S.en_fond(t, lambda r: etat.set_text("Terminé ✓" if isinstance(r, tuple) and r == (0, 0) else "Terminé, avec des erreurs : relancez plus tard"))
        v.append(bouton("Tout mettre à jour", "refresh-cw", "pilule", rappel=tout))
        v.append(bouton("Logiciels installés depuis GitHub", "package", "fantome", rappel=lambda: S.detacher("xiii-store-github")))
        self.remplacer("maj", sc)

def main():
    sys.exit(Centre().run(sys.argv))
