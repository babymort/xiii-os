# OS XIII — Pack conseillé : 19 logiciels libres choisis par Matthieu Lamotte, présents dans le menu dès l'installation
# (nom, icône, description) mais téléchargés seulement au premier lancement : l'ISO reste légère, rien n'est installé
# pour rien. Au premier clic : téléchargement et installation (paquet Debian, Flathub ou GitHub), puis l'appli s'ouvre ;
# ensuite elle s'ouvre directement.
#   xiii-pack CLÉ            ouvrir (et installer au premier lancement)
#   xiii-pack --icones DIR   (construction de l'ISO) icônes du pack dans DIR/hicolor
# Application développée par Matthieu Lamotte.
import os, sys, glob, shutil, threading

# clé, nom, description, source (comme le Centre de logiciels), commande après installation, catégories du menu,
# noms d'icône à chercher dans les thèmes installés (Papirus…), couleur et pictogramme Lucide si aucune icône n'existe
PACK = [
    ("obs", "OBS Studio", "Enregistrement et diffusion en direct", "apt:obs-studio", "obs", "AudioVideo;Recorder;",
     ["com.obsproject.Studio", "obs", "obs-studio"], "#302e31", "radio"),
    ("shotcut", "Shotcut", "Montage vidéo simple et léger", "apt:shotcut", "shotcut", "AudioVideo;Video;",
     ["org.shotcut.Shotcut", "shotcut"], "#2e6db4", "film"),
    ("kdenlive", "Kdenlive", "Montage vidéo complet", "apt:kdenlive", "kdenlive", "AudioVideo;Video;",
     ["org.kde.kdenlive", "kdenlive"], "#1d99f3", "film"),
    ("audacity", "Audacity", "Montage et nettoyage audio", "apt:audacity", "audacity", "AudioVideo;Audio;",
     ["audacity", "org.audacityteam.Audacity"], "#0000cc", "audio-lines"),
    ("handbrake", "HandBrake", "Conversion et compression vidéo", "apt:handbrake", "ghb", "AudioVideo;Video;",
     ["fr.handbrake.ghb", "handbrake", "ghb"], "#d8553b", "file-video"),
    ("losslesscut", "LosslessCut", "Couper et assembler des vidéos sans perte ni réencodage", "flatpak:no.mifi.losslesscut", None, "AudioVideo;Video;",
     ["no.mifi.losslesscut", "losslesscut"], "#2b2b2b", "scissors"),
    ("subtitleedit", "Subtitle Edit", "Créer, synchroniser et traduire des sous-titres", "github:SubtitleEdit/subtitleedit", None, "AudioVideo;Video;",
     ["subtitleedit", "subtitle-edit", "subtitleeditor"], "#4a90d9", "captions"),
    ("companion", "Bitfocus Companion", "Stream Deck et boutons de régie (ATEM, vMix, OBS…)", "companion", "xiii-blackmagic", "AudioVideo;",
     ["companion", "bitfocus-companion"], "#d50215", "layout-grid"),
    ("distroav", "NDI pour OBS (DistroAV)", "Sources et sorties NDI dans OBS Studio", "github:DistroAV/DistroAV", "obs", "AudioVideo;",
     ["distroav", "ndi"], "#6b2bd9", "cast"),
    ("sunshine", "Sunshine", "Diffuser ce PC vers Moonlight (jeux, bureau à distance)", "github:LizardByte/Sunshine", "sunshine", "Network;RemoteAccess;",
     ["sunshine", "dev.lizardbyte.app.Sunshine"], "#f4a71d", "sun"),
    ("localsend", "LocalSend", "Envoyer des fichiers entre téléphones et PC du même réseau", "github:localsend/localsend", "localsend_app", "Network;FileTransfer;",
     ["localsend", "org.localsend.localsend_app", "localsend_app"], "#008080", "share-2"),
    ("ventoy", "Ventoy", "Clé USB qui démarre plusieurs ISO (Windows, Linux…)", "github:ventoy/Ventoy", None, "System;Utility;",
     ["ventoy"], "#2b8a3e", "usb"),
    ("etcher", "balenaEtcher", "Écrire une image ISO sur une clé USB ou une carte SD", "github:balena-io/etcher", "balena-etcher", "System;Utility;",
     ["balena-etcher", "balena-etcher-electron", "etcher"], "#4d5057", "hard-drive-download"),
    ("rclone", "rclone", "Clouds et NAS montés comme des dossiers (dans Lecteurs réseau)", "apt:rclone", "xiii-lecteurs", "Network;Utility;",
     ["rclone", "rclone-browser"], "#3f79ad", "cloud"),
    ("czkawka", "Czkawka", "Trouver les doublons, fichiers vides et photos semblables", "flatpak:com.github.qarmin.czkawka", None, "Utility;",
     ["com.github.qarmin.czkawka", "czkawka"], "#e26d1c", "copy"),
    ("upscayl", "Upscayl", "Agrandir et nettoyer des images par IA, hors ligne", "flatpak:org.upscayl.Upscayl", None, "Graphics;",
     ["org.upscayl.Upscayl", "upscayl"], "#6f3cff", "image-up"),
    ("heroic", "Heroic", "Jeux Epic Games, GOG et Amazon", "flatpak:com.heroicgameslauncher.hgl", None, "Game;",
     ["com.heroicgameslauncher.hgl", "heroic"], "#1f2933", "gamepad-2"),
    ("pcsx2", "PCSX2", "Émulateur PlayStation 2", "flatpak:net.pcsx2.PCSX2", None, "Game;Emulator;",
     ["net.pcsx2.PCSX2", "pcsx2", "PCSX2"], "#0051a8", "gamepad-2"),
    ("ppsspp", "PPSSPP", "Émulateur PSP", "flatpak:org.ppsspp.PPSSPP", None, "Game;Emulator;",
     ["org.ppsspp.PPSSPP", "ppsspp"], "#3b88c3", "gamepad"),
    ("ryujinx", "Ryujinx (Ryubing)", "Émulateur Nintendo Switch", "flatpak:io.github.ryubing.Ryujinx", None, "Game;Emulator;",
     ["io.github.ryubing.Ryujinx", "org.ryujinx.Ryujinx", "ryujinx"], "#c4252d", "gamepad-2"),
]
PAR_CLE = {p[0]: p for p in PACK}
CACHES = os.path.expanduser("~/.local/share/applications")


def nom_desktop(cle):
    return "xiii-pack-%s.desktop" % cle


# --------------------------------------------------------------------------------------------- construction de l'ISO
def icones(racine="/usr/share/icons", dest="/usr/share/icons/hicolor", apps="/usr/share/applications"):
    """Icône de chaque logiciel du pack (prise dans les thèmes installés, sinon dessinée) + son raccourci de menu."""
    from . import icones_perso as IP
    os.makedirs(os.path.join(dest, "scalable", "apps"), exist_ok=True)
    for cle, nom, desc, src, cmd, cats, noms, coul, glyphe in PACK:
        trouve = None
        for n in noms:
            for th in ["Papirus", "hicolor", "Adwaita"] + sorted(os.listdir(racine)):
                for sz in ("scalable", "512x512", "256x256", "128x128", "96x96", "64x64", "48x48"):
                    for ext in ("svg", "png"):
                        for sous in ("apps", ""):
                            p = os.path.join(racine, th, sz, sous, "%s.%s" % (n, ext)) if sous else None
                            if p and os.path.exists(p): trouve = p; break
                        if trouve: break
                    if trouve: break
                if trouve: break
            if trouve: break
        if trouve:
            ext = trouve.rsplit(".", 1)[1]
            d = os.path.join(dest, "scalable" if ext == "svg" else "256x256", "apps"); os.makedirs(d, exist_ok=True)
            shutil.copy(os.path.realpath(trouve), os.path.join(d, "xiii-pack-%s.%s" % (cle, ext)))
        else:
            svg = IP.dessiner("lucide", glyphe, "#ffffff", 2, "degrade", coul) or IP.dessiner("lucide", "package", "#ffffff", 2, "degrade", coul)
            open(os.path.join(dest, "scalable", "apps", "xiii-pack-%s.svg" % cle), "w").write(svg)
        open(os.path.join(apps, nom_desktop(cle)), "w").write(
            "[Desktop Entry]\nType=Application\nName=%s\nComment=%s — téléchargé au premier lancement (pack conseillé XIII)\n"
            "Exec=xiii-pack %s %%U\nIcon=xiii-pack-%s\nCategories=%s\nKeywords=%s;pack;xiii;\nX-XIII-Pack=%s\nTerminal=false\n"
            % (nom, desc, cle, cle, cats, nom.lower(), src))
        print(cle, "→", trouve or "icône dessinée")


# --------------------------------------------------------------------------------------------- premier lancement
def masquer_raccourci(cle):
    """Une fois installé, l'appli a son propre raccourci : celui du pack disparaît du menu (pas de doublon)."""
    os.makedirs(CACHES, exist_ok=True)
    src = os.path.join("/usr/share/applications", nom_desktop(cle))
    try: txt = open(src).read()
    except OSError: return
    open(os.path.join(CACHES, nom_desktop(cle)), "w").write(txt.rstrip("\n") + "\nNoDisplay=true\n")


def ouvrir(cle, fichiers=()):
    from . import logiciels as L
    x = PAR_CLE.get(cle)
    if not x: print("logiciel inconnu :", cle); return 2
    _, nom, desc, src, cmd, *_r = x
    if L.installe(src):
        masquer_raccourci(cle); lancer(src, cmd, fichiers); return 0
    return fenetre(x, fichiers)


def lancer(src, cmd, fichiers=()):
    from . import logiciels as L, systeme as S
    t, _, v = src.partition(":")
    if t == "github" and not cmd:
        from .store_github import suivi
        e = suivi().get(v) or {}
        if e.get("lanceur") and os.path.exists(e["lanceur"]):
            S.detacher(["gtk-launch", os.path.basename(e["lanceur"])] + list(fichiers)); return
        if e.get("flatpak_id"):
            S.detacher(["flatpak", "run", e["flatpak_id"]] + list(fichiers)); return
    if t == "flatpak": S.detacher(["flatpak", "run", v] + list(fichiers)); return
    L.lancer(src, cmd)


def fenetre(x, fichiers):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gio
    from .appli import preparer
    from .ui import boite, label, bouton
    from . import logiciels as L, systeme as S
    cle, nom, desc, src, cmd = x[:5]

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="fr.xiii.pack." + cle, flags=Gio.ApplicationFlags.NON_UNIQUE)

        def do_activate(self):
            preparer(".pack-ico { margin: 6px; }")
            w = Gtk.ApplicationWindow(application=self, title=nom); w.set_default_size(460, -1); self.w = w
            v = boite(True, 12, margin_top=22, margin_bottom=20, margin_start=24, margin_end=24); w.set_child(v)
            h = boite(False, 16); im = Gtk.Image.new_from_icon_name("xiii-pack-" + cle); im.set_pixel_size(64); im.add_css_class("pack-ico"); h.append(im)
            c = boite(True, 4, valign=Gtk.Align.CENTER); c.append(label(nom, "page-titre")); c.append(label(desc, "attenue", wrap=True)); h.append(c); v.append(h)
            v.append(label("Premier lancement : %s est téléchargé et installé une seule fois, puis il s'ouvre." % nom, wrap=True))
            self.pb = Gtk.ProgressBar(show_text=False); self.pb.pulse(); v.append(self.pb)
            self.l = label("Préparation…", "petit", "attenue", wrap=True); v.append(self.l)
            r = boite(False, 8, halign=Gtk.Align.END); self.b = bouton("Annuler", None, "fantome", rappel=w.close); r.append(self.b); v.append(r)
            w.present()
            self._src = GLib.timeout_add(120, lambda: (self.pb.pulse(), True)[1])
            threading.Thread(target=self.installer, daemon=True).start()

        def installer(self):
            try:
                L.installer(src, lambda t: GLib.idle_add(self.l.set_text, t))
                GLib.idle_add(self.fini, None)
            except Exception as e:
                GLib.idle_add(self.fini, str(e) or e.__class__.__name__)

        def fini(self, err):
            GLib.source_remove(self._src)
            if err:
                self.pb.set_fraction(0); self.l.set_text("Installation impossible : %s. Vérifiez la connexion Internet, puis relancez." % err)
                t, _, v = src.partition(":")
                if t == "github":
                    self.b.get_parent().prepend(bouton("Page du projet", "external-link", "fantome", rappel=lambda: S.detacher(["xdg-open", "https://github.com/" + v])))
                self.b.set_label("Fermer"); return
            self.pb.set_fraction(1); self.l.set_text("%s est installé ✓ — ouverture…" % nom)
            masquer_raccourci(cle); lancer(src, cmd, fichiers)
            GLib.timeout_add(1500, lambda: (self.w.close(), False)[1])

    return App().run(sys.argv[:1])


def main():
    a = sys.argv[1:]
    if a and a[0] == "--icones":
        icones(dest=a[1] if len(a) > 1 else "/usr/share/icons/hicolor"); return
    if a and a[0] == "--liste":
        for p in PACK: print(p[0], p[1], p[3]); return
    if not a: print("usage : xiii-pack CLÉ | --icones [dossier] | --liste"); sys.exit(2)
    sys.exit(ouvrir(a[0], a[1:]) or 0)
