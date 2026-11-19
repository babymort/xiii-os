# OS XIII — accès au système : son (PipeWire/pactl), réseau (NetworkManager), Bluetooth (BlueZ),
# batterie, profils d'énergie, luminosité, écrans (wlr-randr), heure, mises à jour…
# Toutes les fonctions sont bloquantes : les appeler depuis un fil (voir en_fond).
# XIII_DEMO=1 fournit des données factices (captures d'écran, tests sans matériel).
# Application développée par Matthieu Lamotte.
import os, subprocess, json, re, glob, shutil, threading, time
from gi.repository import GLib

DEMO = os.environ.get("XIII_DEMO") == "1"
_demo = {"vol": 62, "mute": False, "sink": "hdmi", "src": "mic", "srcvol": 80, "wifi": True, "bt": True,
         "profil": "balanced", "lum": 70, "connecte": "Studio-XIII", "airplane": False}

def sh(cmd, timeout=12, entree=None):
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout, input=entree)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

def out(cmd, timeout=12):
    return sh(cmd, timeout)[1]

def a(cmd):
    return shutil.which(cmd) is not None

def en_fond(fn, rappel=None, *args):
    """Exécute fn(*args) dans un fil, puis rappel(resultat) dans la boucle GTK."""
    def run():
        try:
            r = fn(*args)
        except Exception as e:
            r = e
        if rappel:
            GLib.idle_add(lambda: (rappel(r), False)[1])
    threading.Thread(target=run, daemon=True).start()

def detacher(cmd):
    try:
        subprocess.Popen(cmd if isinstance(cmd, list) else ["sh", "-c", cmd], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass

# ================================================================ SON
def _pact(kind):
    rc, o, _ = sh(["pactl", "-f", "json", "list", kind])
    try:
        return json.loads(o) if rc == 0 else []
    except Exception:
        return []

def _vol(d):
    try:
        v = list(d.get("volume", {}).values())[0]["value_percent"]
        return int(v.rstrip("%"))
    except Exception:
        return 0

def sorties():
    if DEMO:
        return [dict(nom="hdmi", desc="Écran HDMI — Moniteur régie", vol=_demo["vol"], muet=_demo["mute"], defaut=_demo["sink"] == "hdmi"),
                dict(nom="jack", desc="Haut-parleurs / casque (jack)", vol=40, muet=False, defaut=_demo["sink"] == "jack"),
                dict(nom="scarlett", desc="Focusrite Scarlett 2i2", vol=75, muet=False, defaut=_demo["sink"] == "scarlett")]
    d = out(["pactl", "get-default-sink"])
    return [dict(nom=s["name"], desc=s.get("description", s["name"]), vol=_vol(s), muet=s.get("mute", False),
                 defaut=s["name"] == d) for s in _pact("sinks")]

def entrees():
    if DEMO:
        return [dict(nom="mic", desc="Micro intégré", vol=_demo["srcvol"], muet=False, defaut=_demo["src"] == "mic"),
                dict(nom="scarlett-in", desc="Focusrite Scarlett 2i2 — Entrée 1", vol=90, muet=False, defaut=_demo["src"] == "scarlett-in")]
    d = out(["pactl", "get-default-source"])
    return [dict(nom=s["name"], desc=s.get("description", s["name"]), vol=_vol(s), muet=s.get("mute", False),
                 defaut=s["name"] == d) for s in _pact("sources") if not s["name"].endswith(".monitor")]

def flux_apps():
    if DEMO:
        return [dict(idx=1, nom="Firefox", vol=80, icone="firefox-esr"), dict(idx=2, nom="mpv", vol=55, icone="mpv")]
    L = []
    for s in _pact("sink-inputs"):
        pr = s.get("properties", {})
        L.append(dict(idx=s["index"], nom=pr.get("application.name", "Application"), vol=_vol(s),
                      icone=pr.get("application.icon_name", "") or pr.get("application.process.binary", "")))
    return L

def volume():
    if DEMO: return _demo["vol"], _demo["mute"]
    for s in sorties():
        if s["defaut"]: return s["vol"], s["muet"]
    return 0, False

def regler_volume(pct, nom="@DEFAULT_SINK@"):
    if DEMO: _demo["vol"] = int(pct); return
    sh(["pactl", "set-sink-volume", nom, "%d%%" % int(pct)])

def basculer_muet(nom="@DEFAULT_SINK@"):
    if DEMO: _demo["mute"] = not _demo["mute"]; return
    sh(["pactl", "set-sink-mute", nom, "toggle"])

def sortie_defaut(nom):
    if DEMO: _demo["sink"] = nom; return
    sh(["pactl", "set-default-sink", nom])

def entree_defaut(nom):
    if DEMO: _demo["src"] = nom; return
    sh(["pactl", "set-default-source", nom])

def regler_entree(pct, nom="@DEFAULT_SOURCE@"):
    if DEMO: _demo["srcvol"] = int(pct); return
    sh(["pactl", "set-source-volume", nom, "%d%%" % int(pct)])

def regler_flux(idx, pct):
    if DEMO: return
    sh(["pactl", "set-sink-input-volume", str(idx), "%d%%" % int(pct)])

# ================================================================ RÉSEAU
def _champs(ligne):
    return [c.replace("\\:", ":") for c in re.split(r"(?<!\\):", ligne)]

def wifi_actif():
    if DEMO: return _demo["wifi"]
    return out(["nmcli", "radio", "wifi"]) == "enabled"

def wifi_activer(on):
    if DEMO: _demo["wifi"] = on; return
    sh(["nmcli", "radio", "wifi", "on" if on else "off"])

def reseaux_wifi(rescan=False):
    if DEMO:
        if not _demo["wifi"]: return []
        return [dict(ssid="Studio-XIII", signal=92, secu="WPA2", actif=_demo["connecte"] == "Studio-XIII", connu=True),
                dict(ssid="Plateau-B", signal=71, secu="WPA3", actif=_demo["connecte"] == "Plateau-B", connu=True),
                dict(ssid="Régie mobile 4G", signal=58, secu="WPA2", actif=False, connu=False),
                dict(ssid="Livebox-7A21", signal=40, secu="WPA2", actif=False, connu=False),
                dict(ssid="Invités", signal=25, secu="", actif=False, connu=False)]
    connus = set(l.split(":")[0] for l in out(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"]).splitlines()
                 if l.endswith("802-11-wireless"))
    o = out(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes" if rescan else "auto"], 25)
    vus = {}
    for l in o.splitlines():
        f = _champs(l)
        if len(f) < 4 or not f[1]: continue
        r = dict(ssid=f[1], signal=int(f[2] or 0), secu=f[3], actif=f[0].strip() == "*", connu=f[1] in connus)
        if f[1] not in vus or r["actif"] or r["signal"] > vus[f[1]]["signal"]:
            vus[f[1]] = r
    return sorted(vus.values(), key=lambda r: (not r["actif"], -r["signal"]))

def wifi_connecter(ssid, mdp=None):
    if DEMO: _demo["connecte"] = ssid; return True, ""
    connus = [l.split(":")[0] for l in out(["nmcli", "-t", "-f", "NAME", "connection", "show"]).splitlines()]
    if ssid in connus and not mdp:
        rc, o, e = sh(["nmcli", "connection", "up", "id", ssid], 40)
    else:
        cmd = ["nmcli", "device", "wifi", "connect", ssid] + (["password", mdp] if mdp else [])
        rc, o, e = sh(cmd, 40)
    return rc == 0, (e or o)

def wifi_oublier(ssid):
    if DEMO: return
    sh(["nmcli", "connection", "delete", "id", ssid])

def wifi_deconnecter():
    if DEMO: _demo["connecte"] = ""; return
    for l in out(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"]).splitlines():
        f = _champs(l)
        if len(f) >= 3 and f[1] == "wifi" and f[2] == "connected":
            sh(["nmcli", "device", "disconnect", f[0]])

def etat_reseau():
    """{'type': 'wifi'|'ethernet'|None, 'nom': str, 'signal': int, 'ip': str}"""
    if DEMO:
        return dict(type="wifi" if _demo["connecte"] else None, nom=_demo["connecte"], signal=92, ip="192.168.1.42",
                    ethernet=True, avion=_demo["airplane"])
    r = dict(type=None, nom="", signal=0, ip="", ethernet=False, avion=False)
    for l in out(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"]).splitlines():
        f = _champs(l)
        if len(f) < 4: continue
        if f[1] == "ethernet":
            r["ethernet"] = True
            if f[2] == "connected" and r["type"] != "ethernet":
                r.update(type="ethernet", nom=f[3])
        elif f[1] == "wifi" and f[2] == "connected" and r["type"] is None:
            r.update(type="wifi", nom=f[3])
    if r["type"] == "wifi":
        for l in out(["nmcli", "-t", "-f", "IN-USE,SIGNAL", "device", "wifi"]).splitlines():
            if l.startswith("*"):
                try: r["signal"] = int(l.split(":")[1])
                except Exception: pass
    m = re.search(r"src (\S+)", out("ip route get 1.1.1.1 2>/dev/null"))
    r["ip"] = m.group(1) if m else ""
    r["avion"] = out(["nmcli", "radio", "all"]).count("disabled") >= 1 and not wifi_actif() and not bt_actif()
    return r

def mode_avion(on):
    if DEMO: _demo["airplane"] = on; _demo["wifi"] = not on; _demo["bt"] = not on; return
    sh(["nmcli", "radio", "all", "off" if on else "on"])
    sh(["rfkill", "block" if on else "unblock", "bluetooth"])
    if not on: bt_activer(True)

def details_interfaces():
    if DEMO:
        return [dict(dev="wlan0", type="wifi", etat="connecté", conn="Studio-XIII", ip="192.168.1.42/24", mac="3c:a9:f4:12:8b:7e", passerelle="192.168.1.1", dns="192.168.1.1"),
                dict(dev="enp3s0", type="ethernet", etat="débranché", conn="", ip="", mac="54:ee:75:08:aa:10", passerelle="", dns="")]
    L = []
    for l in out(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"]).splitlines():
        f = _champs(l)
        if len(f) < 4 or f[1] not in ("wifi", "ethernet"): continue
        info = {}
        for li in out(["nmcli", "-t", "device", "show", f[0]]).splitlines():
            k, _, v = li.partition(":"); info.setdefault(k, v)
        L.append(dict(dev=f[0], type=f[1], etat={"connected": "connecté", "disconnected": "déconnecté", "unavailable": "débranché"}.get(f[2], f[2]),
                      conn=f[3], ip=info.get("IP4.ADDRESS[1]", ""), mac=info.get("GENERAL.HWADDR", ""),
                      passerelle=info.get("IP4.GATEWAY", ""), dns=info.get("IP4.DNS[1]", "")))
    return L

def vpns():
    if DEMO: return [dict(nom="Bureau (WireGuard)", actif=False)]
    L = []
    act = out(["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"]).splitlines()
    for l in out(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"]).splitlines():
        f = _champs(l)
        if len(f) >= 2 and f[1] in ("vpn", "wireguard"):
            L.append(dict(nom=f[0], actif=f[0] in act))
    return L

def vpn_basculer(nom, on):
    if DEMO: return True
    return sh(["nmcli", "connection", "up" if on else "down", "id", nom], 30)[0] == 0

def point_acces(ssid, mdp, on=True):
    if DEMO: return True, ""
    if not on:
        return sh(["nmcli", "connection", "down", "Hotspot"])[0] == 0, ""
    rc, o, e = sh(["nmcli", "device", "wifi", "hotspot", "ssid", ssid, "password", mdp], 30)
    return rc == 0, e or o

# ================================================================ BLUETOOTH
def bt_present():
    if DEMO: return True
    return a("bluetoothctl") and "Controller" in out(["bluetoothctl", "list"], 5)

def bt_actif():
    if DEMO: return _demo["bt"]
    return "Powered: yes" in out(["bluetoothctl", "show"], 5)

def bt_activer(on):
    if DEMO: _demo["bt"] = on; return
    if on: sh(["rfkill", "unblock", "bluetooth"])
    sh(["bluetoothctl", "power", "on" if on else "off"], 8)

def _bt_info(mac):
    i = out(["bluetoothctl", "info", mac], 5)
    bat = re.search(r"Battery Percentage: 0x[0-9a-f]+ \((\d+)\)", i)
    ic = re.search(r"Icon: (\S+)", i)
    return dict(connecte="Connected: yes" in i, appaire="Paired: yes" in i, batterie=int(bat.group(1)) if bat else None,
                icone=ic.group(1) if ic else "bluetooth")

def bt_appareils():
    if DEMO:
        if not _demo["bt"]: return []
        return [dict(mac="AA:01", nom="Casque WH-1000XM5", connecte=True, batterie=80, icone="audio-headset", appaire=True),
                dict(mac="AA:02", nom="Souris MX Master", connecte=False, batterie=None, icone="input-mouse", appaire=True),
                dict(mac="AA:03", nom="Clavier K380", connecte=False, batterie=None, icone="input-keyboard", appaire=True)]
    L = []
    o = out(["bluetoothctl", "devices", "Paired"], 6) or out(["bluetoothctl", "paired-devices"], 6)
    for l in o.splitlines():
        m = re.match(r"Device (\S+) (.+)", l)
        if m:
            d = dict(mac=m.group(1), nom=m.group(2)); d.update(_bt_info(m.group(1))); L.append(d)
    return sorted(L, key=lambda d: not d["connecte"])

def bt_rechercher(duree=8):
    if DEMO:
        time.sleep(1.5)
        return [dict(mac="BB:01", nom="Enceinte JBL Flip", icone="audio-speakers"), dict(mac="BB:02", nom="Manette Xbox", icone="input-gaming")]
    sh(["bluetoothctl", "--timeout", str(duree), "scan", "on"], duree + 5)
    appaires = {d["mac"] for d in bt_appareils()}
    L = []
    for l in out(["bluetoothctl", "devices"], 6).splitlines():
        m = re.match(r"Device (\S+) (.+)", l)
        if m and m.group(1) not in appaires and not re.match(r"^([0-9A-F]{2}-){5}", m.group(2)):
            L.append(dict(mac=m.group(1), nom=m.group(2), icone=_bt_info(m.group(1))["icone"]))
    return L

def bt_connecter(mac, on=True):
    if DEMO: return True
    return sh(["bluetoothctl", "connect" if on else "disconnect", mac], 25)[0] == 0

def bt_appairer(mac):
    if DEMO: return True, ""
    rc, o, e = sh(["bluetoothctl", "pair", mac], 40)
    sh(["bluetoothctl", "trust", mac], 8)
    if rc == 0: sh(["bluetoothctl", "connect", mac], 25)
    return rc == 0, (o + e)[-200:]

def bt_oublier(mac):
    if DEMO: return
    sh(["bluetoothctl", "remove", mac], 8)

# ================================================================ BATTERIE / ÉNERGIE / LUMINOSITÉ
def batterie():
    """None si pas de batterie, sinon {pct, etat, temps}"""
    if DEMO:
        return dict(pct=76, etat="sur batterie", charge=False, temps="3 h 12 min restantes")
    bats = glob.glob("/sys/class/power_supply/BAT*")
    if not bats: return None
    try:
        pct = int(open(bats[0] + "/capacity").read())
        st = open(bats[0] + "/status").read().strip()
    except Exception:
        return None
    etat = {"Charging": "en charge", "Discharging": "sur batterie", "Full": "chargée", "Not charging": "branchée"}.get(st, st.lower())
    temps = ""
    dev = [l for l in out(["upower", "-e"]).splitlines() if "BAT" in l]
    if dev:
        m = re.search(r"time to (empty|full):\s+([\d.,]+) (\w+)", out(["upower", "-i", dev[0]]))
        if m:
            v = float(m.group(2).replace(",", ".")); u = m.group(3)
            mins = int(v * 60) if u.startswith("hour") else int(v)
            temps = "%d h %02d min %s" % (mins // 60, mins % 60, "restantes" if m.group(1) == "empty" else "avant charge complète")
    return dict(pct=pct, etat=etat, charge=st in ("Charging", "Full"), temps=temps)

PROFILS = [("power-saver", "Économie", "leaf"), ("balanced", "Équilibré", "scale"), ("performance", "Performances", "zap")]
def profil():
    if DEMO: return _demo["profil"]
    return out(["powerprofilesctl", "get"], 4) or ""

def profils_dispo():
    if DEMO: return [p[0] for p in PROFILS]
    o = out(["powerprofilesctl", "list"], 4)
    return [p[0] for p in PROFILS if p[0] in o]

def regler_profil(p):
    if DEMO: _demo["profil"] = p; return
    sh(["powerprofilesctl", "set", p], 6)

def luminosite():
    """pct ou None si pas d'écran réglable"""
    if DEMO: return _demo["lum"]
    o = out(["brightnessctl", "-m", "-c", "backlight"], 3)
    try:
        return int(o.split(",")[3].rstrip("%")) if o else None
    except Exception:
        return None

def regler_luminosite(pct):
    if DEMO: _demo["lum"] = int(pct); return
    sh(["brightnessctl", "-q", "-c", "backlight", "set", "%d%%" % max(1, int(pct))], 3)

# ================================================================ ÉCRANS
def ecrans():
    if DEMO:
        return [dict(nom="HDMI-A-1", desc="Moniteur régie 27\"", actif=True, w=1920, h=1080, hz=60.0, echelle=1.0, rotation="normal",
                     modes=[(1920, 1080, 60.0), (1600, 900, 60.0), (1280, 720, 60.0)])]
    rc, o, _ = sh(["wlr-randr", "--json"])
    try:
        d = json.loads(o)
    except Exception:
        return []
    L = []
    for e in d:
        cur = next((m for m in e.get("modes", []) if m.get("current")), None)
        modes = []
        for m in e.get("modes", []):
            t = (m["width"], m["height"], round(m["refresh"], 2))
            if t not in modes: modes.append(t)
        L.append(dict(nom=e["name"], desc=(e.get("make", "") + " " + e.get("model", "")).strip() or e["name"], actif=e.get("enabled", True),
                      w=cur["width"] if cur else 0, h=cur["height"] if cur else 0, hz=round(cur["refresh"], 2) if cur else 0,
                      echelle=e.get("scale", 1.0), rotation=e.get("transform", "normal"), modes=modes))
    return L

def regler_ecran(nom, w=None, h=None, hz=None, echelle=None, rotation=None, actif=None):
    if DEMO: return True
    cmd = ["wlr-randr", "--output", nom]
    if actif is False: cmd += ["--off"]
    else:
        if actif: cmd += ["--on"]
        if w: cmd += ["--mode", "%dx%d@%.3fHz" % (w, h, hz) if hz else "%dx%d" % (w, h)]
        if echelle: cmd += ["--scale", str(echelle)]
        if rotation: cmd += ["--transform", rotation]
    return sh(cmd)[0] == 0

# ================================================================ SYSTÈME / INFOS
def infos_systeme():
    def osr(k):
        m = re.search(r'^%s="?([^"\n]*)' % k, open("/etc/os-release").read(), re.M) if os.path.exists("/etc/os-release") else None
        return m.group(1) if m else ""
    cpu = out("grep -m1 'model name' /proc/cpuinfo | cut -d: -f2").strip()
    ram = 0
    try:
        ram = int(re.search(r"MemTotal:\s+(\d+)", open("/proc/meminfo").read()).group(1)) / 1048576
    except Exception:
        pass
    gpu = ", ".join(l.split(": ", 1)[-1] for l in out("lspci 2>/dev/null | grep -iE 'vga|3d|display'").splitlines()) or "—"
    up = 0
    try: up = float(open("/proc/uptime").read().split()[0])
    except Exception: pass
    return dict(nom=osr("PRETTY_NAME") or "OS XIII", version=osr("VERSION") or "", hote=os.uname().nodename,
                cpu=cpu or "—", ram="%.1f Go" % ram, gpu=gpu, noyau=os.uname().release,
                base="Debian " + (open("/etc/debian_version").read().strip() if os.path.exists("/etc/debian_version") else ""),
                uptime="%d h %02d min" % (up // 3600, (up % 3600) // 60), arch=os.uname().machine)

def disques():
    L = []
    for p, nom in (("/", "Système"), (os.path.expanduser("~"), "Dossier personnel")):
        try:
            u = shutil.disk_usage(p)
            if any(d["total"] == u.total and d["libre"] == u.free for d in L): continue
            L.append(dict(nom=nom, chemin=p, total=u.total, libre=u.free, utilise=u.used))
        except Exception:
            pass
    return L

def taille_dossier(p):
    t = 0
    for racine, _, fichiers in os.walk(p):
        for f in fichiers:
            try: t += os.lstat(os.path.join(racine, f)).st_size
            except OSError: pass
    return t

def humain(n):
    for u in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or u == "To":
            return ("%.0f %s" if u in ("o", "Ko") else "%.1f %s") % (n, u)
        n /= 1024

def admin(cmd, entree=None, timeout=900):
    """Exécute une commande en administrateur (fenêtre de mot de passe polkit)."""
    if DEMO: time.sleep(0.6); return True, "démo"
    rc, o, e = sh(["pkexec"] + (cmd if isinstance(cmd, list) else ["sh", "-c", cmd]), timeout, entree)
    return rc == 0, (o + "\n" + e).strip()

# ================================================================ HEURE / LANGUE
def fuseau():
    if DEMO: return "Europe/Paris"
    return out(["timedatectl", "show", "-p", "Timezone", "--value"]) or "Europe/Paris"

def fuseaux():
    o = out(["timedatectl", "list-timezones"])
    return o.splitlines() if o else ["Europe/Paris", "Europe/London", "America/New_York", "Asia/Tokyo"]

def ntp():
    if DEMO: return True
    return out(["timedatectl", "show", "-p", "NTP", "--value"]) == "yes"

# ================================================================ MISES À JOUR
def maj_disponibles():
    if DEMO:
        return [("firefox-esr", "128.5.0esr-1"), ("linux-image-amd64", "6.12.119-1"), ("mesa-vulkan-drivers", "25.0.7-2")]
    ok, o = admin("apt-get update -qq >/dev/null 2>&1; apt list --upgradable 2>/dev/null", timeout=300)
    L = []
    for l in o.splitlines():
        m = re.match(r"([^/\s]+)/\S+\s+(\S+)", l)
        if m: L.append((m.group(1), m.group(2)))
    return L

# ================================================================ PARE-FEU
def pare_feu():
    if DEMO: return True
    try:
        return "ENABLED=yes" in open("/etc/ufw/ufw.conf").read()
    except OSError:
        return None


def progres(desktop_id, fraction):
    """Barre de progression sous l'icône de l'application dans la barre des tâches (None = masquer)."""
    try:
        from gi.repository import Gio, GLib as _G
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        props = {"progress-visible": _G.Variant("b", fraction is not None)}
        if fraction is not None: props["progress"] = _G.Variant("d", max(0.0, min(1.0, float(fraction))))
        bus.emit_signal(None, "/fr/xiii/progres", "com.canonical.Unity.LauncherEntry", "Update",
                        _G.Variant("(sa{sv})", ("application://" + desktop_id, props)))
    except Exception:
        pass
