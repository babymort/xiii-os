# OS XIII — Réseau XIII : chaque interface réglée séparément (Wi-Fi, câble, adaptateur USB, 4G), sortie Internet au choix,
# profils par lieu, test de la régie, recherche des appareils du réseau, XIII Duo (deux liens ensemble : répartition ou secours).
# Tout passe par NetworkManager (nmcli) ; XIII Duo par le service système xiii-duo.
# Application développée par Matthieu Lamotte.
import os, re, json, subprocess, ipaddress, socket, threading, time, glob

PROFILS = os.path.expanduser("~/.config/xiii/reseau-profils.json")
DUO = "/etc/xiii/duo.json"
DEMO = bool(os.environ.get("XIII_DEMO"))


def nm(*a, t=15):
    r = subprocess.run(["nmcli"] + list(a), capture_output=True, text=True, timeout=t)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def champs(l):
    return [x.replace("\\:", ":") for x in re.split(r"(?<!\\):", l)]


def lire(f, d=""):
    try: return open(f).read().strip()
    except OSError: return d


# ===================================================================== interfaces
def nature(dev, typ):
    """wifi | ethernet | usb | gsm | autre — un adaptateur Ethernet USB ou un téléphone en partage USB est « usb »."""
    if typ == "wifi": return "wifi"
    if typ in ("gsm", "cdma", "modem"): return "gsm"
    if typ == "ethernet":
        chemin = os.path.realpath("/sys/class/net/%s/device" % dev)
        return "usb" if "/usb" in chemin else "ethernet"
    return "autre"


NOMS = {"wifi": "Wi-Fi", "ethernet": "Câble (RJ45)", "usb": "Adaptateur USB / partage de téléphone", "gsm": "4G / 5G", "autre": "Autre"}
ICONES = {"wifi": "wifi", "ethernet": "ethernet-port", "usb": "usb", "gsm": "signal", "autre": "network"}


def interfaces():
    if DEMO:
        return [dict(dev="wlan0", type="wifi", nature="wifi", etat="connecté", connexion="Studio-XIII", uuid="d1", mode="auto", ip="192.168.1.42/24",
                     passerelle="192.168.1.1", dns="192.168.1.1", mac="3c:a9:f4:12:8b:7e", debit="433 Mb/s", internet=True, jamais_defaut=False, metrique=600),
                dict(dev="enp3s0", type="ethernet", nature="ethernet", etat="connecté", connexion="Régie ATEM", uuid="d2", mode="manual", ip="192.168.10.50/24",
                     passerelle="", dns="", mac="54:ee:75:08:aa:10", debit="1000 Mb/s", internet=False, jamais_defaut=True, metrique=100),
                dict(dev="enx00e04c", type="ethernet", nature="usb", etat="débranché", connexion="", uuid="", mode="", ip="", passerelle="", dns="",
                     mac="00:e0:4c:68:01:22", debit="", internet=False, jamais_defaut=False, metrique=0)]
    L = []
    _, o, _ = nm("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device")
    defaut = route_defaut()
    for l in o.splitlines():
        f = champs(l)
        if len(f) < 4 or f[1] not in ("wifi", "ethernet", "gsm", "cdma", "modem"): continue
        dev = f[0]; info = {}
        for li in nm("-t", "device", "show", dev)[1].splitlines():
            k, _, v = li.partition(":"); info.setdefault(k, v)
        uuid = info.get("GENERAL.CON-UUID", "")
        conf = connexion(uuid) if uuid else {}
        debit = ""
        if f[1] == "ethernet":
            s = lire("/sys/class/net/%s/speed" % dev)
            if s.isdigit() and int(s) > 0: debit = "%s Mb/s" % s
        elif f[1] == "wifi":
            for li in nm("-t", "-f", "ACTIVE,RATE", "dev", "wifi", "list", "ifname", dev)[1].splitlines():
                if li.startswith(("oui:", "yes:")): debit = li.split(":", 1)[1]
        L.append(dict(dev=dev, type=f[1], nature=nature(dev, f[1]),
                      etat={"connected": "connecté", "disconnected": "déconnecté", "unavailable": "débranché", "connecting": "connexion…"}.get(f[2].split(" ")[0], f[2]),
                      connexion=f[3] if f[3] != "--" else "", uuid=uuid, mode=conf.get("ipv4.method", ""), ip=info.get("IP4.ADDRESS[1]", ""),
                      passerelle=info.get("IP4.GATEWAY", "") if info.get("IP4.GATEWAY", "") != "--" else "", dns=info.get("IP4.DNS[1]", ""),
                      mac=info.get("GENERAL.HWADDR", ""), debit=debit, internet=defaut == dev,
                      jamais_defaut=conf.get("ipv4.never-default") == "yes", metrique=int(conf.get("ipv4.route-metric", "-1") or -1)))
    return L


def connexion(uuid):
    _, o, _ = nm("-t", "-f", "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns,ipv4.never-default,ipv4.route-metric,connection.id,connection.interface-name", "connection", "show", uuid)
    d = {}
    for l in o.splitlines():
        k, _, v = l.partition(":"); d[k] = v
    return d


def route_defaut():
    o = subprocess.run(["ip", "-4", "route", "show", "default"], capture_output=True, text=True).stdout
    best = None
    for l in o.splitlines():
        m = re.search(r"dev (\S+)", l); me = re.search(r"metric (\d+)", l)
        if m:
            v = int(me.group(1)) if me else 0
            if best is None or v < best[0]: best = (v, m.group(1))
        if "nexthop" in l: return "duo"
    return best[1] if best else None


def connexion_pour(dev, nat):
    """UUID du profil de l'interface (en crée un pour un câble ou un adaptateur qui n'en a pas)."""
    for i in interfaces():
        if i["dev"] == dev and i["uuid"]: return i["uuid"]
    _, o, _ = nm("-t", "-f", "UUID,DEVICE,TYPE,NAME", "connection", "show")
    for l in o.splitlines():
        f = champs(l)
        if len(f) >= 4 and connexion(f[0]).get("connection.interface-name") == dev: return f[0]
    if nat in ("ethernet", "usb"):
        nom = "XIII %s" % dev
        c, o, e = nm("connection", "add", "type", "ethernet", "ifname", dev, "con-name", nom)
        if c == 0:
            return nm("-t", "-f", "connection.uuid", "connection", "show", nom)[1].split(":")[-1]
    raise RuntimeError("aucun profil pour %s (connectez-vous d'abord au réseau)" % dev)


def appliquer_ip(dev, nat, mode, adresse="", passerelle="", dns="", internet=True):
    """mode « auto » (DHCP) ou « manual » (IP fixe) ; internet=False : jamais de route par défaut sur cette interface (réseau régie)."""
    if DEMO: return True, "démo"
    uuid = connexion_pour(dev, nat)
    a = ["connection", "modify", uuid]
    if mode == "manual":
        adr = adresse.strip()
        if "/" not in adr: adr += "/24"
        ipaddress.ip_interface(adr)  # contrôle
        a += ["ipv4.method", "manual", "ipv4.addresses", adr, "ipv4.gateway", passerelle.strip() if (passerelle.strip() and internet) else "",
              "ipv4.dns", ",".join(x.strip() for x in re.split(r"[ ,;]+", dns) if x.strip())]
        if passerelle.strip(): ipaddress.ip_address(passerelle.strip())
    else:
        a += ["ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""]
    a += ["ipv4.never-default", "no" if internet else "yes", "ipv4.ignore-auto-dns", "no" if internet else "yes"]
    c, o, e = nm(*a)
    if c != 0: return False, e or o
    c, o, e = nm("connection", "up", uuid, "ifname", dev, t=40)
    return c == 0, (e or o)


def sortie_internet(dev_choisi):
    """Donne la priorité Internet à une interface (métrique basse) ; les autres gardent leur rôle. None = automatique."""
    if DEMO: return True, ""
    for i in interfaces():
        if not i["uuid"]: continue
        m = "-1" if dev_choisi is None else ("50" if i["dev"] == dev_choisi else str(700 + {"ethernet": 0, "usb": 50, "wifi": 100, "gsm": 200}.get(i["nature"], 300)))
        nm("connection", "modify", i["uuid"], "ipv4.route-metric", m, "ipv6.route-metric", m)
        if i["etat"] == "connecté": nm("device", "reapply", i["dev"], t=20)
    return True, ""


# ===================================================================== diagnostics
def ping(cible, dev=None, n=3):
    a = ["ping", "-n", "-c", str(n), "-W", "1"] + (["-I", dev] if dev else []) + [cible]
    o = subprocess.run(a, capture_output=True, text=True, timeout=n * 2 + 4).stdout
    m = re.search(r"(\d+)% packet loss", o); r = re.search(r"= [\d.]+/([\d.]+)/", o)
    perte = int(m.group(1)) if m else 100
    return perte < 100, ("%s ms" % r.group(1) if r else "—"), perte


def appareils(dev):
    """Appareils répondant sur le sous-réseau de l'interface : [(ip, mac, nom)]."""
    i = next((x for x in interfaces() if x["dev"] == dev and x["ip"]), None)
    if not i: return []
    reseau = ipaddress.ip_interface(i["ip"]).network
    if reseau.num_addresses > 1024: reseau = ipaddress.ip_network(str(ipaddress.ip_interface(i["ip"]).ip) + "/24", strict=False)
    hotes = [str(h) for h in reseau.hosts()]
    def p(h):
        subprocess.run(["ping", "-n", "-c", "1", "-W", "1", "-I", dev, h], capture_output=True)
    th = []
    for h in hotes:
        t = threading.Thread(target=p, args=(h,), daemon=True); t.start(); th.append(t)
        if len(th) >= 64:
            for x in th: x.join()
            th = []
    for x in th: x.join()
    L = []
    for l in subprocess.run(["ip", "-4", "neigh", "show", "dev", dev], capture_output=True, text=True).stdout.splitlines():
        f = l.split()
        if len(f) >= 3 and "lladdr" in f and f[-1] in ("REACHABLE", "STALE", "DELAY", "PERMANENT"):
            ip = f[0]; mac = f[f.index("lladdr") + 1]
            try: nom = socket.gethostbyaddr(ip)[0]
            except OSError: nom = ""
            L.append((ip, mac, nom))
    mon = str(ipaddress.ip_interface(i["ip"]).ip)
    return sorted([x for x in L if x[0] != mon], key=lambda x: ipaddress.ip_address(x[0]))


def trafic():
    """{dev: (octets reçus, octets envoyés)}"""
    d = {}
    for l in open("/proc/net/dev").read().splitlines()[2:]:
        n, _, r = l.partition(":"); f = r.split()
        if len(f) >= 9: d[n.strip()] = (int(f[0]), int(f[8]))
    return d


# ===================================================================== profils par lieu
def profils():
    try: return json.load(open(PROFILS))
    except Exception: return []


def sauver_profils(L):
    os.makedirs(os.path.dirname(PROFILS), exist_ok=True); json.dump(L, open(PROFILS, "w"), ensure_ascii=False, indent=1)


def capturer(nom, wifi_associe=""):
    """Profil = réglages IP de chaque interface connectée + sortie Internet + Wi-Fi qui l'active automatiquement."""
    its = []
    for i in interfaces():
        if not i["uuid"]: continue
        c = connexion(i["uuid"])
        its.append({"dev": i["dev"], "nature": i["nature"], "mode": c.get("ipv4.method", "auto"), "adresse": c.get("ipv4.addresses", ""),
                    "passerelle": c.get("ipv4.gateway", "") if c.get("ipv4.gateway", "") != "--" else "", "dns": c.get("ipv4.dns", ""),
                    "internet": c.get("ipv4.never-default") != "yes", "connexion": i["connexion"]})
    sortie = route_defaut()
    return {"nom": nom, "wifi": wifi_associe, "interfaces": its, "sortie": sortie if sortie not in (None, "duo") else None, "cree": time.strftime("%Y-%m-%d %H:%M")}


def appliquer_profil(p):
    erreurs = []
    devs = {i["dev"]: i for i in interfaces()}
    for it in p.get("interfaces", []):
        dev = it["dev"] if it["dev"] in devs else next((d for d, i in devs.items() if i["nature"] == it["nature"]), None)
        if not dev: erreurs.append("%s absente" % it["dev"]); continue
        try:
            ok, m = appliquer_ip(dev, it["nature"], it["mode"] if it["mode"] in ("auto", "manual") else "auto", it.get("adresse", "").split(",")[0], it.get("passerelle", ""), it.get("dns", ""), it.get("internet", True))
            if not ok: erreurs.append("%s : %s" % (dev, m))
        except Exception as e:
            erreurs.append("%s : %s" % (dev, e))
    if p.get("sortie"): sortie_internet(p["sortie"])
    return not erreurs, "; ".join(erreurs)


def wifi_actuel():
    for l in nm("-t", "-f", "ACTIVE,SSID", "dev", "wifi")[1].splitlines():
        if l.startswith(("oui:", "yes:")): return l.split(":", 1)[1]
    return ""


# ===================================================================== XIII Duo
def duo():
    try: return json.load(open(DUO))
    except Exception: return {"mode": "arret", "prefere": "", "poids": {}}


def duo_etat():
    try: return json.load(open("/run/xiii-duo.json"))
    except Exception: return {}


def regler_duo(conf):
    if DEMO: return True
    r = subprocess.run(["pkexec", "/usr/local/bin/xiii-duo", "regler", json.dumps(conf)], capture_output=True, text=True)
    return r.returncode == 0


def surveiller():
    """Applique le profil dont le Wi-Fi associé vient d'être rejoint (lancé à l'ouverture de session)."""
    dernier = None
    p = subprocess.Popen(["nmcli", "monitor"], stdout=subprocess.PIPE, text=True)
    for _ in p.stdout:
        time.sleep(2)
        ssid = wifi_actuel()
        if not ssid or ssid == dernier: continue
        dernier = ssid
        for pr in profils():
            if pr.get("wifi") and pr["wifi"] == ssid and pr.get("auto", True):
                ok, m = appliquer_profil(pr)
                subprocess.run(["notify-send", "-a", "Réseau XIII", "-i", "network-wired", "Profil réseau « %s »" % pr["nom"],
                                "Appliqué automatiquement (Wi-Fi « %s »)" % ssid + ("" if ok else " — " + m)])
                break


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--surveiller": surveiller()
