# OS XIII — applications installées, catégories du menu Démarrer, fichiers récents, lancement.
# Application développée par Matthieu Lamotte.
import os, re, urllib.parse
from gi.repository import Gio, GLib, Gdk

CATEGORIES = [  # (clé, nom affiché, icône Lucide, catégories freedesktop)
    ("suite", "Suite XIII", "clapperboard", ["X-XIII-Suite"]),
    ("xiii", "Outils XIII", "zap", ["XIII"]),
    ("ia", "Intelligence artificielle", "sparkles", ["X-XIII-IA"]),
    ("windows", "Applications Windows", "app-window", ["Wine", "X-XIII-Windows"]),
    ("internet", "Internet", "globe", ["Network", "WebBrowser", "Email", "Chat", "InstantMessaging", "FileTransfer"]),
    ("multimedia", "Multimédia", "clapperboard", ["AudioVideo", "Audio", "Video", "Player", "Recorder"]),
    ("graphisme", "Graphisme", "palette", ["Graphics", "Photography", "2DGraphics", "3DGraphics"]),
    ("bureautique", "Bureautique", "file-text", ["Office", "WordProcessor", "Spreadsheet", "Presentation", "Viewer"]),
    ("jeux", "Jeux", "gamepad-2", ["Game"]),
    ("dev", "Développement", "code-xml", ["Development", "IDE"]),
    ("accessoires", "Accessoires", "wrench", ["Utility", "Accessories", "TextEditor", "Archiving", "Calculator", "FileManager"]),
    ("systeme", "Système", "settings", ["Settings", "System", "Monitor", "HardwareSettings", "Security", "PackageManager"]),
    ("autres", "Autres", "shapes", []),
]
CACHES = {"lxpolkit.desktop", "blueman-adapters.desktop", "nm-applet.desktop", "org.freedesktop.IBus.Setup.desktop",
          "vim.desktop", "htop.desktop", "debian-uxterm.desktop", "debian-xterm.desktop", "mpv-dmenu.desktop",
          "display-im6.q16.desktop", "foot-server.desktop", "footclient.desktop", "thunar-bulk-rename.desktop",
          "thunar-settings.desktop", "thunar-volman-settings.desktop", "xdg-desktop-portal-wlr.desktop", "lightdm-gtk-greeter-settings.desktop",
          "calamares.desktop", "calamares-install-debian.desktop", "wine.desktop", "wine-notepad.desktop", "wine-winecfg.desktop", "wine-uninstaller.desktop", "winetricks.desktop",
          # ZZ — doublons d'une app ou d'une page XIII (restent utilisables par « Ouvrir avec » et les Paramètres)
          "thunar.desktop", "nm-connection-editor.desktop", "blueman-manager.desktop", "org.pulseaudio.pavucontrol.desktop", "pavucontrol.desktop",
          "system-config-printer.desktop", "org.gnome.DejaDup.desktop", "timeshift-gtk.desktop", "gnome-disk-image-mounter.desktop",
          "gnome-disk-image-writer.desktop", "imv-dir.desktop", "qv4l2.desktop", "qvidcap.desktop", "nano.desktop", "lstopo.desktop",
          "org.freedesktop.IBus.Panel.Emojier.desktop", "org.freedesktop.IBus.Panel.Extension.Gtk3.desktop", "yelp.desktop", "cups.desktop",
          "io.github.ilya_zlobintsev.LACT.desktop", "foot.desktop", "org.xfce.mousepad-settings.desktop"}

IA = {"com.anthropic.Claude.desktop", "xiii-claude-code.desktop"}

def toutes():
    L = []
    for a in Gio.AppInfo.get_all():
        try:
            if not a.should_show() or a.get_id() in CACHES: continue
        except Exception:
            continue
        L.append(a)
    return sorted(L, key=lambda a: a.get_display_name().lower())

def categorie(a):
    cats = (a.get_categories() or "").split(";") if hasattr(a, "get_categories") else []
    try:
        if "wine " in (a.get_commandline() or "") or "WINEPREFIX" in (a.get_commandline() or ""): return "windows"
    except Exception:
        pass
    if a.get_id() in IA: return "ia"
    for cle, _, _, fd in CATEGORIES:
        if any(c in cats for c in fd):
            return cle
    return "autres"

def par_categorie():
    d = {c[0]: [] for c in CATEGORIES}
    for a in toutes():
        d[categorie(a)].append(a)
    return [(c, n, i, d[c]) for c, n, i, _ in CATEGORIES if d[c]]

def par_id(i):
    try:
        return Gio.DesktopAppInfo.new(i)
    except TypeError:
        return None

_index_wm = None
def pour_fenetre(app_id):
    """Trouve l'appli .desktop d'une fenêtre (app_id Wayland / classe X11)."""
    global _index_wm
    if not app_id: return None
    alias = {"fr.xiii.parametres": "xiii-parametres.desktop", "fr.xiii.bilan": "xiii-bilan.desktop", "fr.xiii.demarrage": "xiii-demarrage.desktop", "fr.xiii.windows": "xiii-windows.desktop", "fr.xiii.somme": "xiii-somme.desktop", "steam": "steam.desktop", "fr.xiii.bienvenue": "xiii-installer.desktop", "fr.xiii.claudecode": "xiii-claude-code.desktop", "fr.xiii.retour": "xiii-retour.desktop", "fr.xiii.tally": "xiii-tally.desktop", "ndi-xiii": "xiii-ndi.desktop", "ndi xiii": "xiii-ndi.desktop",
             "org.xfce.mousepad": "org.xfce.mousepad.desktop", "thunar": "thunar.desktop", "firefox-esr": "firefox-esr.desktop", "mpv": "mpv.desktop"}
    if app_id.startswith("fr.xiii.suite."):
        a = par_id("xiii-suite-%s.desktop" % ("accueil" if app_id[14:] == "index" else app_id[14:]))
        if a: return a
    if app_id in ("fr.xiii.Suite", "fr.xiii.suite"):
        a = par_id("xiii-suite-accueil.desktop")
        if a: return a
    if app_id.lower() in alias:
        a = par_id(alias[app_id.lower()])
        if a: return a
    for cand in (app_id, app_id.lower(), app_id.split(".")[-1].lower()):
        a = par_id(cand + ".desktop")
        if a: return a
    if _index_wm is None:
        _index_wm = {}
        for a in Gio.AppInfo.get_all():
            try:
                wm = a.get_startup_wm_class() if hasattr(a, "get_startup_wm_class") else None
                # une même classe de fenêtre peut être déclarée par l'appli et par sa page de réglages : l'appli l'emporte
                rang = lambda x: (not x.should_show(), "setting" in (x.get_id() or "").lower())
                if wm and (wm.lower() not in _index_wm or rang(a) < rang(_index_wm[wm.lower()])): _index_wm[wm.lower()] = a
                exe = os.path.basename((a.get_executable() or "")).lower()
                if exe and (exe not in _index_wm or rang(a) < rang(_index_wm[exe])): _index_wm[exe] = a
            except Exception:
                pass
    return _index_wm.get(app_id.lower()) or _index_wm.get(app_id.split(".")[-1].lower())

def deux_cartes():
    """PC portable à deux cartes graphiques (Intel/AMD intégrée + carte dédiée)."""
    import glob
    return len(glob.glob("/sys/class/drm/card[0-9]")) > 1


USAGE = os.path.expanduser("~/.local/share/xiii/usage.json")

def noter_usage(a):
    """Compte les lancements (préchargement des applis fréquentes au démarrage)."""
    try:
        import json
        try: d = json.load(open(USAGE))
        except Exception: d = {}
        k = a.get_id() or ""; d[k] = d.get(k, 0) + 1
        os.makedirs(os.path.dirname(USAGE), exist_ok=True); json.dump(d, open(USAGE, "w"))
    except Exception: pass

def lancer(a, fichiers=None, dediee=False):
    noter_usage(a)
    try:
        ctx = Gdk.Display.get_default().get_app_launch_context()
        if dediee:      # carte dédiée : Mesa (AMD, nouveau) et pilote NVIDIA officiel
            for k, v in (("DRI_PRIME", "1"), ("__NV_PRIME_RENDER_OFFLOAD", "1"), ("__GLX_VENDOR_LIBRARY_NAME", "nvidia" if os.path.exists("/proc/driver/nvidia") else "mesa"),
                         ("__VK_LAYER_NV_optimus", "NVIDIA_only" if os.path.exists("/proc/driver/nvidia") else "")):
                if v: ctx.setenv(k, v)
        if fichiers:
            a.launch([Gio.File.new_for_path(f) for f in fichiers], ctx)
        else:
            a.launch([], ctx)
        return True
    except Exception:
        return False

def ouvrir_fichier(chemin):
    try:
        Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(chemin).get_uri(),
                                           Gdk.Display.get_default().get_app_launch_context())
    except Exception:
        pass

def recents(n=6):
    """Fichiers récents (recently-used.xbel), plus récents d'abord."""
    p = os.path.join(GLib.get_user_data_dir(), "recently-used.xbel")
    try:
        x = open(p, encoding="utf-8", errors="ignore").read()
    except OSError:
        return []
    L = []
    for m in re.finditer(r'<bookmark href="([^"]+)"[^>]*?modified="([^"]+)"', x):
        u = m.group(1)
        if not u.startswith("file://"): continue
        chemin = urllib.parse.unquote(u[7:])
        if os.path.exists(chemin):
            L.append((m.group(2), chemin))
    L.sort(reverse=True)
    vus, res = set(), []
    for _, c in L:
        if c not in vus:
            vus.add(c); res.append(c)
        if len(res) >= n: break
    return res

def icone_fichier(chemin):
    try:
        info = Gio.File.new_for_path(chemin).query_info("standard::icon", 0, None)
        return info.get_icon()
    except Exception:
        return Gio.ThemedIcon.new("text-x-generic")
