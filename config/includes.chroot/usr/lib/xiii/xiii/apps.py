# OS XIII — applications installées, catégories du menu Démarrer, fichiers récents, lancement.
# Application développée par Matthieu Lamotte.
import os, re, urllib.parse
from gi.repository import Gio, GLib, Gdk

CATEGORIES = [  # (clé, nom affiché, icône Lucide, catégories freedesktop)
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
          "calamares.desktop", "calamares-install-debian.desktop", "wine.desktop", "wine-notepad.desktop", "wine-winecfg.desktop", "wine-uninstaller.desktop", "winetricks.desktop"}

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
    alias = {"fr.xiii.parametres": "xiii-parametres.desktop", "fr.xiii.bilan": "xiii-bilan.desktop", "fr.xiii.demarrage": "xiii-demarrage.desktop", "fr.xiii.windows": "xiii-windows.desktop", "fr.xiii.somme": "xiii-somme.desktop", "steam": "steam.desktop", "fr.xiii.bienvenue": "xiii-installer.desktop", "fr.xiii.claudecode": "xiii-claude-code.desktop",
             "org.xfce.mousepad": "org.xfce.mousepad.desktop", "thunar": "thunar.desktop", "firefox-esr": "firefox-esr.desktop", "mpv": "mpv.desktop"}
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
                if wm: _index_wm[wm.lower()] = a
                exe = os.path.basename((a.get_executable() or "")).lower()
                if exe: _index_wm.setdefault(exe, a)
            except Exception:
                pass
    return _index_wm.get(app_id.lower()) or _index_wm.get(app_id.split(".")[-1].lower())

def lancer(a, fichiers=None):
    try:
        ctx = Gdk.Display.get_default().get_app_launch_context()
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
