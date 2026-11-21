# OS XIII — analyse du réseau local, partagée par le Scanner IP XIII et les Lecteurs réseau :
# appareils (ping + table ARP), noms (DNS inverse, mDNS/Avahi, NetBIOS), fabricant (préfixe MAC, base IEEE),
# services ouverts, NAS reconnus par marque, partages SMB.
# Application développée par Matthieu Lamotte.
import os, re, socket, subprocess, threading, ipaddress, urllib.request, ssl, json, concurrent.futures as cf

PORTS = {21: "FTP", 22: "SSH", 80: "Web", 139: "NetBIOS", 443: "Web sécurisé", 445: "Partage Windows (SMB)", 548: "AFP", 631: "Imprimante",
         2049: "NFS", 3389: "Bureau à distance (RDP)", 5000: "Web (Synology / UGREEN)", 5001: "Web sécurisé (Synology)", 5900: "VNC",
         8080: "Web (QNAP / Asustor)", 8181: "Web (TerraMaster TOS)", 5443: "Web sécurisé (TerraMaster)", 9999: "Web (Buffalo / Zyxel)", 8443: "Web sécurisé", 9000: "Portainer / web", 9910: "ATEM", 8099: "vMix", 1935: "RTMP", 5960: "NDI"}
MARQUES = ["Synology", "QNAP", "Asustor", "TerraMaster", "Western Digital", "WD My Cloud", "Netgear", "ReadyNAS", "Buffalo", "UGREEN", "TrueNAS", "FreeNAS",
           "iXsystems", "Seagate", "LaCie", "Drobo", "Zyxel", "Thecus", "D-Link", "Unraid", "OpenMediaVault", "Freebox", "Livebox", "Bbox", "Apple",
           "Time Capsule", "Lenovo Iomega", "Iomega", "Netgear ReadyNAS", "Lacie", "Infortrend", "Promise", "OWC", "Blackmagic", "Dell", "HP", "Raspberry"]
_oui = None

def oui():
    """Préfixes MAC → fabricant (paquet ieee-data)."""
    global _oui
    if _oui is None:
        _oui = {}
        for f in ("/usr/share/ieee-data/oui.txt", "/usr/share/misc/oui.txt"):
            try:
                for l in open(f, encoding="utf-8", errors="replace"):
                    m = re.match(r"^([0-9A-F]{2})-([0-9A-F]{2})-([0-9A-F]{2})\s+\(hex\)\s+(.+)$", l.strip())
                    if m: _oui[(m.group(1) + m.group(2) + m.group(3))] = m.group(4).strip()
                if _oui: break
            except OSError:
                pass
    return _oui

def fabricant(mac):
    if not mac: return ""
    p = mac.replace(":", "").replace("-", "").upper()[:6]
    if int(p[1], 16) & 2: return "Adresse privée (aléatoire)"
    return oui().get(p, "")

def interfaces_reseau():
    """[(dev, cidr)] des interfaces IPv4 actives."""
    L = []
    try: o = subprocess.run(["ip", "-4", "-o", "addr", "show", "scope", "global"], capture_output=True, text=True).stdout
    except OSError: o = ""
    for l in o.splitlines():
        f = l.split(); dev = f[1]; cidr = f[3]
        if dev.startswith(("docker", "veth", "br-", "virbr")): continue
        L.append((dev, cidr))
    return L

def plage_par_defaut():
    i = interfaces_reseau()
    if not i: return "192.168.1.1-254"
    n = ipaddress.ip_interface(i[0][1]).network
    if n.num_addresses > 1024: n = ipaddress.ip_network(str(ipaddress.ip_interface(i[0][1]).ip) + "/24", strict=False)
    h = list(n.hosts())
    return "%s-%s" % (h[0], str(h[-1]).split(".")[-1])

def hotes(plage):
    """« 192.168.1.1-254 », « 192.168.1.0/24 », « 10.0.0.5 » ou une liste séparée par des virgules."""
    L = []
    for part in re.split(r"[,\s]+", plage.strip()):
        if not part: continue
        if "/" in part: L += [str(h) for h in ipaddress.ip_network(part, strict=False).hosts()]
        elif "-" in part:
            a, b = part.split("-", 1); a = ipaddress.ip_address(a)
            fin = ipaddress.ip_address(b) if "." in b else ipaddress.ip_address(".".join(str(a).split(".")[:3] + [b]))
            L += [str(ipaddress.ip_address(x)) for x in range(int(a), int(fin) + 1)]
        else: L.append(part)
    return L[:4096]

def ping(ip):
    try: return subprocess.run(["ping", "-n", "-c", "1", "-W", "1", ip], capture_output=True).returncode == 0
    except OSError: return port_ouvert(ip, 80, .5) or port_ouvert(ip, 445, .5) or port_ouvert(ip, 22, .5)

def voisins():
    d = {}
    try: o = subprocess.run(["ip", "-4", "neigh"], capture_output=True, text=True).stdout
    except OSError: o = ""
    for l in o.splitlines():
        f = l.split()
        if "lladdr" in f and f[-1] != "FAILED": d[f[0]] = f[f.index("lladdr") + 1]
    return d

def port_ouvert(ip, p, t=.35):
    try:
        with socket.create_connection((ip, p), timeout=t): return True
    except OSError: return False

def mdns():
    """Noms et services annoncés (Avahi) : {ip: {"nom", "services": set, "modele"}}."""
    d = {}
    try:
        o = subprocess.run(["avahi-browse", "-aprt", "--no-db-lookup"], capture_output=True, text=True, timeout=6).stdout
    except Exception:
        return d
    for l in o.splitlines():
        f = l.split(";")
        if len(f) >= 10 and f[0] == "=" and f[2] == "IPv4":
            ip = f[7]; e = d.setdefault(ip, {"nom": f[6].replace(".local", ""), "services": set(), "txt": ""})
            e["services"].add(f[4]); e["txt"] += " " + f[9]
    return d

def titre_web(ip, port):
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        u = "%s://%s:%d/" % ("https" if port in (443, 5001, 8443, 5443) else "http", ip, port)
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "OS-XIII"}), timeout=1.5, context=ctx)
        t = r.read(30000).decode("utf-8", "replace")
        m = re.search(r"<title[^>]*>([^<]{1,80})</title>", t, re.I)
        return ((m.group(1).strip() if m else "") + " " + r.headers.get("Server", "")).strip()
    except Exception:
        return ""

def marque(app):
    txt = " ".join([app.get("fabricant", ""), app.get("web", ""), app.get("nom", ""), app.get("txt", "")]).lower()
    for m in MARQUES:
        if m.lower() in txt: return m
    if "diskstation" in txt or "dsm" in txt: return "Synology"
    if "qts" in txt or "quts" in txt: return "QNAP"
    if "tnas" in txt or re.search(r"\btos\b", txt) or "terra" in txt: return "TerraMaster"
    if 8181 in app.get("ports", []) or 5443 in app.get("ports", []): return "TerraMaster"
    if "adm" in txt and "asustor" in txt: return "Asustor"
    return ""

def est_nas(app):
    s = set(app.get("ports", []))
    return bool(marque(app) in MARQUES[:24] or (s & {445, 2049, 548}) and (s & {5000, 5001, 8080, 8181, 5443, 80, 443}) or (s & {8181, 5443}) and (s & {445, 139}) or "_smb._tcp" in app.get("services", ()))

def type_appareil(app):
    s = set(app.get("ports", [])); m = marque(app); f = app.get("fabricant", "").lower()
    if est_nas(app) and m not in ("Apple", "Dell", "HP", "Raspberry"): return "NAS"
    if 9910 in s or "blackmagic" in f: return "Mélangeur / Blackmagic"
    if 631 in s or "_ipp._tcp" in app.get("services", ()): return "Imprimante"
    if 3389 in s or 445 in s: return "Ordinateur"
    if 22 in s: return "Ordinateur / serveur"
    if 80 in s or 443 in s: return "Appareil web"
    if any(x in f for x in ("apple", "samsung", "xiaomi", "huawei", "oneplus", "google")): return "Téléphone / tablette"
    return "Appareil"

def analyser(plage, progres=None, ports=None, arreter=lambda: False):
    """Analyse complète ; progres(fait, total). Renvoie une liste d'appareils (dict)."""
    L = hotes(plage); vivants = set(); fait = [0]; lock = threading.Lock()
    def p(ip):
        if arreter(): return
        if ping(ip): vivants.add(ip)
        with lock:
            fait[0] += 1
            if progres: progres(fait[0], len(L) * 2)
    with cf.ThreadPoolExecutor(96) as ex: list(ex.map(p, L))
    vs = voisins(); md = mdns()
    vivants |= {ip for ip in vs if ip in set(L)}
    ports = ports or list(PORTS)
    apps = []
    def detail(ip):
        if arreter(): return None
        a = {"ip": ip, "mac": vs.get(ip, ""), "nom": "", "ports": [], "services": set(), "txt": "", "web": ""}
        try: a["nom"] = socket.gethostbyaddr(ip)[0].replace(".local", "").replace(".lan", "").replace(".home", "")
        except OSError: pass
        if ip in md:
            a["nom"] = a["nom"] or md[ip]["nom"]; a["services"] = md[ip]["services"]; a["txt"] = md[ip]["txt"]
        a["fabricant"] = fabricant(a["mac"])
        a["ports"] = [pt for pt in ports if port_ouvert(ip, pt)]
        for pt in (5000, 5001, 8181, 5443, 8080, 80, 443):
            if pt in a["ports"]:
                a["web"] = titre_web(ip, pt)
                if a["web"]: break
        a["marque"] = marque(a); a["type"] = type_appareil(a); a["nas"] = est_nas(a)
        a["services"] = sorted(a["services"])
        with lock:
            fait[0] += 1
            if progres: progres(len(L) + int(len(L) * (fait[0] - len(L)) / max(1, len(vivants))), len(L) * 2)
        return a
    with cf.ThreadPoolExecutor(32) as ex:
        for a in ex.map(detail, sorted(vivants, key=lambda x: ipaddress.ip_address(x))):
            if a: apps.append(a)
    moi = {ipaddress.ip_interface(c).ip.exploded for _, c in interfaces_reseau()}
    for a in apps:
        if a["ip"] in moi: a["nom"] = (a["nom"] or socket.gethostname()) + " (ce PC)"
    if progres: progres(1, 1)
    return apps

def partages_smb(hote, utilisateur="", mdp=""):
    """Partages SMB d'un serveur (smbclient)."""
    cmd = ["smbclient", "-L", hote, "-g"] + (["-U", "%s%%%s" % (utilisateur, mdp)] if utilisateur else ["-N"])
    try: o = subprocess.run(cmd, capture_output=True, text=True, timeout=12).stdout
    except Exception: return []
    return [l.split("|")[1] for l in o.splitlines() if l.startswith("Disk|") and not l.split("|")[1].endswith("$")]
