# OS XIII — jeux : Steam, Proton par défaut, GameMode, MangoHud, profil vieux PC.
# Application développée par Matthieu Lamotte.
import os, re, glob, shutil, subprocess
from gi.repository import GLib
from . import systeme as S

STEAM = os.path.expanduser("~/.local/share/Steam")
VDF = os.path.join(STEAM, "config", "config.vdf")
MANGO = os.path.join(GLib.get_user_config_dir(), "MangoHud", "MangoHud.conf")
ENV = os.path.join(GLib.get_user_config_dir(), "labwc", "environment")

def steam_installe():
    return shutil.which("steam") is not None

def steam_initialise():
    return os.path.exists(os.path.join(STEAM, "steam.sh"))

def steam_lance():
    return S.sh(["pgrep", "-x", "steam"])[0] == 0

def proton_actif():
    try:
        t = open(VDF, errors="ignore").read()
    except OSError:
        return False
    return bool(re.search(r'"CompatToolMapping"\s*\{\s*"0"\s*\{\s*"name"\s*"proton', t))

def activer_proton():
    """Proton Experimental pour tous les jeux Windows (Steam doit être fermé)."""
    if steam_lance(): return False, "Fermez Steam d'abord."
    if not os.path.exists(VDF): return False, "Lancez Steam une première fois (connexion), puis revenez ici."
    t = open(VDF, errors="ignore").read()
    entree = '\n\t\t\t\t\t"0"\n\t\t\t\t\t{\n\t\t\t\t\t\t"name"\t\t"proton_experimental"\n\t\t\t\t\t\t"config"\t\t""\n\t\t\t\t\t\t"priority"\t\t"75"\n\t\t\t\t\t}'
    m = re.search(r'"CompatToolMapping"\s*\{', t)
    if m:
        t = t[:m.end()] + entree + t[m.end():]
    else:
        m = re.search(r'"Steam"\s*\{', t)
        if not m: return False, "Fichier de configuration Steam inattendu."
        t = t[:m.end()] + '\n\t\t\t\t"CompatToolMapping"\n\t\t\t\t{' + entree + '\n\t\t\t\t}' + t[m.end():]
    shutil.copy(VDF, VDF + ".avant-xiii")
    open(VDF, "w").write(t)
    return True, "Proton activé pour tous les jeux."

def env_lire():
    try: return open(ENV).read().splitlines()
    except OSError: return []

def env_poser(cle, val):
    L = [l for l in env_lire() if not l.startswith(cle + "=")]
    if val is not None: L.append("%s=%s" % (cle, val))
    os.makedirs(os.path.dirname(ENV), exist_ok=True); open(ENV, "w").write("\n".join(L) + "\n")

def mangohud(on, ips30=False):
    env_poser("MANGOHUD", "1" if on else None)
    os.makedirs(os.path.dirname(MANGO), exist_ok=True)
    open(MANGO, "w").write("# OS XIII\nposition=top-left\nfont_size=18\nbackground_alpha=0.4\ncpu_temp\ngpu_temp\nram\nframetime=0\n"
                           + ("fps_limit=30\n" if ips30 else ""))

def vieux_pc():
    try:
        ram = int(re.search(r"MemTotal:\s+(\d+)", open("/proc/meminfo").read()).group(1)) / 1048576
    except Exception:
        ram = 8
    vk = S.out("vulkaninfo --summary 2>/dev/null | grep -c deviceName") not in ("", "0")
    return ram < 6 or not vk or (os.cpu_count() or 4) <= 2, ram, vk

def gamemode_ok():
    return shutil.which("gamemoded") is not None
