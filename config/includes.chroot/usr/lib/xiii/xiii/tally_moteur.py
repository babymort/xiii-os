# OS XIII — TALLY XIII, le moteur : lit le tally des mélangeurs par IP et le diffuse aux téléphones et boîtiers.
# Mélangeurs : Blackmagic ATEM (protocole UDP 9910), vMix (API TCP 8099, SUBSCRIBE TALLY), NewTek TriCaster (API HTTP /v1),
#              simulateur (essais sans régie), forçage manuel (tableau de bord, Companion).
# Diffusion  : page web pour téléphones (http://IP:8790, QR code), WebSocket /ws, API JSON pour ESP32 / M5Stack / Companion :
#              GET /api/etat · GET /api/cam/N (texte : programme | preview | repos) · GET /api/forcer?cam=N&etat=programme|preview|repos|auto
# Application développée par Matthieu Lamotte.
import os, json, socket, struct, threading, time, base64, hashlib, re, random, select, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
import http.server, socketserver

REGLAGES = os.path.join(os.path.expanduser("~/.config/xiii"), "tally.json")
DEFAUT = {"port": 8790, "cameras": 8, "noms": {}, "sources": [], "vibrer": True, "preview": True}
REPOS, PREVIEW, PROGRAMME = 0, 1, 2
NOM_ETAT = {REPOS: "repos", PREVIEW: "preview", PROGRAMME: "programme"}


def charger():
    try:
        r = dict(DEFAUT); r.update(json.load(open(REGLAGES))); return r
    except Exception:
        return json.loads(json.dumps(DEFAUT))


def sauver(r):
    os.makedirs(os.path.dirname(REGLAGES), exist_ok=True)
    tmp = REGLAGES + ".tmp"; json.dump(r, open(tmp, "w"), ensure_ascii=False, indent=1); os.replace(tmp, REGLAGES)


def ip_locale():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ===================================================================== sources (mélangeurs)
class Source(threading.Thread):
    """Base : chaque source tient à jour self.etats {numéro de caméra (1…): REPOS|PREVIEW|PROGRAMME} et self.noms."""
    TYPE = "?"

    def __init__(self, cfg, moteur):
        super().__init__(daemon=True)
        self.cfg = cfg; self.moteur = moteur; self.actif = True
        self.etats = {}; self.noms = {}; self.connecte = False; self.message = "Connexion…"; self.vu = 0

    def publier(self, etats, noms=None):
        if etats != self.etats or (noms and noms != self.noms):
            self.etats = dict(etats)
            if noms: self.noms.update(noms)
            self.moteur.changement()
        self.vu = time.time()

    def etat_connexion(self, ok, msg):
        if ok != self.connecte or msg != self.message:
            self.connecte, self.message = ok, msg
            if not ok: self.etats = {}
            self.moteur.changement()

    def arreter(self):
        self.actif = False

    def run(self):
        while self.actif:
            try:
                self.boucle()
            except Exception as e:
                self.etat_connexion(False, "Hors ligne : %s" % (e.__class__.__name__ if not str(e) else str(e)))
            for _ in range(20):
                if not self.actif: return
                time.sleep(0.1)


class ATEM(Source):
    """Blackmagic ATEM : protocole UDP (port 9910) — poignée de main, accusés de réception, commandes TlIn (tally par entrée) et InPr (noms)."""
    TYPE = "atem"
    SYN, ACK_DEMANDE, RENVOI, DEMANDE_RENVOI, ACK = 0x02, 0x01, 0x04, 0x08, 0x10
    BONJOUR = bytes([0x10, 0x14, 0x53, 0xAB, 0, 0, 0, 0, 0, 0x3A, 0, 0, 0x01, 0, 0, 0, 0, 0, 0, 0])

    def entete(self, drapeaux, longueur, session, ack=0, local=0):
        # octet 9 à 0x41 : valeur envoyée par les logiciels Blackmagic dans les accusés de réception
        return struct.pack(">HHHHBBH", (drapeaux << 11) | longueur, session, ack, 0, 0, 0x41 if drapeaux & self.ACK else 0, local)

    def boucle(self):
        ip, port = self.cfg["ip"], int(self.cfg.get("port") or 9910)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0.5)
        try:
            s.sendto(self.BONJOUR, (ip, port))
            session = 0x53AB; t0 = time.time(); dernier = time.time(); etats = {}; noms = {}; pret = False
            self.etat_connexion(False, "Connexion à l'ATEM…")
            while self.actif:
                try:
                    data, _ = s.recvfrom(4096)
                except socket.timeout:
                    if time.time() - dernier > 3:
                        raise ConnectionError("l'ATEM ne répond plus")
                    if not pret and time.time() - t0 > 1.5:
                        s.sendto(self.BONJOUR, (ip, port)); t0 = time.time()
                    continue
                if len(data) < 12: continue
                mot, sess, ack_id, _, _, distant = struct.unpack(">HHHHHH", data[:12])
                drap, lng = mot >> 11, mot & 0x07FF
                dernier = time.time()
                if drap & self.SYN:
                    # réponse au bonjour : 0x02 = accepté (on accuse réception, l'ATEM envoie tout son état), 0x03 = plus de place
                    if len(data) > 12 and data[12] == 0x03:
                        raise ConnectionError("l'ATEM refuse : trop de connexions ouvertes")
                    s.sendto(self.entete(self.ACK, 12, sess, distant), (ip, port)); continue
                session = sess
                if drap & self.ACK_DEMANDE:
                    s.sendto(self.entete(self.ACK, 12, session, distant), (ip, port))
                charge = data[12:lng] if lng <= len(data) else data[12:]
                i = 0
                while i + 8 <= len(charge):
                    l = struct.unpack(">H", charge[i:i + 2])[0]
                    if l < 8: break
                    nom = charge[i + 4:i + 8]; d = charge[i + 8:i + l]
                    if nom == b"TlIn" and len(d) >= 2:
                        n = struct.unpack(">H", d[:2])[0]
                        etats = {k + 1: (PROGRAMME if d[2 + k] & 1 else PREVIEW if d[2 + k] & 2 else REPOS) for k in range(min(n, len(d) - 2))}
                        if pret: self.publier(etats, noms)
                    elif nom == b"InPr" and len(d) >= 26:
                        src = struct.unpack(">H", d[:2])[0]
                        if 1 <= src <= 40:
                            long_ = d[2:22].split(b"\0")[0].decode("utf-8", "replace").strip()
                            if long_: noms[src] = long_
                    elif nom == b"_pin" and len(d) >= 1:
                        self.modele = d.split(b"\0")[0].decode("utf-8", "replace")
                    elif nom == b"InCm":
                        pret = True
                        self.etat_connexion(True, "Connecté — " + getattr(self, "modele", "ATEM"))
                        self.publier(etats, noms)
                    i += l
        finally:
            s.close()


class VMix(Source):
    """vMix : API TCP (port 8099), « SUBSCRIBE TALLY » → « TALLY OK 0120… » (un chiffre par entrée : 0 repos, 1 programme, 2 preview)."""
    TYPE = "vmix"

    def noms_vmix(self, ip):
        try:
            x = ET.fromstring(urllib.request.urlopen("http://%s:8088/api" % ip, timeout=2).read())
            return {int(i.get("number")): (i.get("title") or "").strip() for i in x.iter("input") if i.get("number", "").isdigit()}
        except Exception:
            return {}

    def boucle(self):
        ip, port = self.cfg["ip"], int(self.cfg.get("port") or 8099)
        s = socket.create_connection((ip, port), timeout=3)
        try:
            s.settimeout(1); s.sendall(b"SUBSCRIBE TALLY\r\n")
            noms = self.noms_vmix(ip); tn = time.time(); tampon = b""; dernier = time.time()
            self.etat_connexion(True, "Connecté — vMix")
            while self.actif:
                try:
                    d = s.recv(4096)
                    if not d: raise ConnectionError("vMix a fermé la connexion")
                    tampon += d; dernier = time.time()
                except socket.timeout:
                    if time.time() - dernier > 5:
                        s.sendall(b"VERSION\r\n"); dernier = time.time()
                    continue
                while b"\r\n" in tampon:
                    ligne, tampon = tampon.split(b"\r\n", 1)
                    m = re.match(rb"TALLY OK (\d+)", ligne)
                    if m:
                        if time.time() - tn > 30: noms = self.noms_vmix(ip) or noms; tn = time.time()
                        self.publier({k + 1: {b"1": PROGRAMME, b"2": PREVIEW}.get(m.group(1)[k:k + 1], REPOS) for k in range(len(m.group(1)))}, noms)
        finally:
            s.close()


class TriCaster(Source):
    """NewTek / Vizrt TriCaster : API HTTP /v1/dictionary?key=tally (colonnes on_pgm / on_prev), interrogée toutes les 150 ms."""
    TYPE = "tricaster"

    def boucle(self):
        ip = self.cfg["ip"]; port = int(self.cfg.get("port") or 80)
        url = "http://%s:%d/v1/dictionary?key=tally" % (ip, port)
        hdr = {}
        if self.cfg.get("utilisateur"):
            hdr["Authorization"] = "Basic " + base64.b64encode(("%s:%s" % (self.cfg["utilisateur"], self.cfg.get("mot_de_passe", ""))).encode()).decode()
        echecs = 0
        while self.actif:
            try:
                x = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=2).read())
                etats, noms = {}, {}
                for c in x.iter("column"):
                    idx = int(c.get("index", "-1"))
                    if idx < 0: continue
                    vrai = lambda k: (c.get(k) or "").lower() == "true"
                    etats[idx + 1] = PROGRAMME if vrai("on_pgm") else PREVIEW if vrai("on_prev") else REPOS
                    if c.get("name"): noms[idx + 1] = c.get("name")
                if not self.connecte: self.etat_connexion(True, "Connecté — TriCaster")
                self.publier(etats, noms); echecs = 0
            except Exception as e:
                echecs += 1
                if echecs >= 3: raise ConnectionError("TriCaster injoignable (%s)" % e.__class__.__name__)
            time.sleep(0.15)


class Simulateur(Source):
    """Essais sans régie : programme et preview changent toutes les quelques secondes."""
    TYPE = "simulateur"

    def boucle(self):
        n = int(self.cfg.get("cameras") or self.moteur.r.get("cameras", 8))
        self.etat_connexion(True, "Simulateur actif")
        pgm, pvw = 1, 2
        while self.actif:
            self.publier({k: PROGRAMME if k == pgm else PREVIEW if k == pvw else REPOS for k in range(1, n + 1)})
            for _ in range(int(float(self.cfg.get("rythme") or 4) * 10)):
                if not self.actif: return
                time.sleep(0.1)
            pgm, pvw = pvw, random.choice([k for k in range(1, n + 1) if k != pvw] or [1])


TYPES = {"atem": ATEM, "vmix": VMix, "tricaster": TriCaster, "simulateur": Simulateur}
NOMS_TYPES = {"atem": "Blackmagic ATEM", "vmix": "vMix", "tricaster": "TriCaster", "simulateur": "Simulateur"}
PORTS = {"atem": 9910, "vmix": 8099, "tricaster": 80}


# ===================================================================== moteur
class Moteur:
    def __init__(self, ecouteur=None):
        self.r = charger(); self.sources = []; self.forces = {}; self.clients = {}  # ws → caméra
        self.verrou = threading.Lock(); self.ecouteurs = [ecouteur] if ecouteur else []; self.version = 0
        self.serveur = None

    # --- sources
    def demarrer(self):
        self.recharger_sources()
        self.serveur = Serveur(("0.0.0.0", int(self.r.get("port", 8790))), Gestion); self.serveur.moteur = self
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        threading.Thread(target=self._battement, daemon=True).start()

    def recharger_sources(self):
        for s in self.sources: s.arreter()
        self.sources = []
        for c in self.r.get("sources", []):
            if c.get("actif", True) and c.get("type") in TYPES and (c.get("ip") or c["type"] == "simulateur"):
                s = TYPES[c["type"]](c, self); self.sources.append(s); s.start()
        self.changement()

    def arreter(self):
        for s in self.sources: s.arreter()
        if self.serveur: self.serveur.shutdown()

    # --- état fusionné
    def etats(self):
        """{caméra: état} : le programme l'emporte sur la preview, toutes sources confondues ; forçage manuel prioritaire."""
        n = int(self.r.get("cameras", 8)); e = {k: REPOS for k in range(1, n + 1)}
        for s in self.sources:
            for k, v in s.etats.items():
                if k <= n and v > e.get(k, REPOS): e[k] = v
        for k, v in self.forces.items():
            if k <= n: e[k] = v
        if not self.r.get("preview", True):
            e = {k: (REPOS if v == PREVIEW else v) for k, v in e.items()}
        return e

    def noms(self):
        n = int(self.r.get("cameras", 8)); L = {}
        for s in self.sources:
            for k, v in s.noms.items():
                if k <= n: L.setdefault(k, v)
        for k, v in self.r.get("noms", {}).items():
            if v: L[int(k)] = v
        return L

    def instantane(self):
        e = self.etats(); noms = self.noms()
        with self.verrou: cl = list(self.clients.values())
        return {"type": "etat", "v": self.version, "t": time.time(),
                "cameras": {str(k): {"etat": NOM_ETAT[v], "nom": noms.get(k, ""), "telephones": cl.count(k)} for k, v in e.items()},
                "sources": [{"type": s.TYPE, "nom": s.cfg.get("nom") or NOMS_TYPES.get(s.TYPE, s.TYPE), "ip": s.cfg.get("ip", ""), "connecte": s.connecte, "message": s.message} for s in self.sources],
                "vibrer": self.r.get("vibrer", True)}

    def changement(self):
        self.version += 1
        msg = json.dumps(self.instantane(), ensure_ascii=False).encode()
        with self.verrou: cl = list(self.clients)
        for ws in cl: ws.envoyer(msg)
        for f in self.ecouteurs:
            try: f()
            except Exception: pass

    def _battement(self):
        while True:
            time.sleep(2)
            msg = json.dumps({"type": "battement", "t": time.time()}).encode()
            with self.verrou: cl = list(self.clients)
            for ws in cl: ws.envoyer(msg)

    def forcer(self, cam, etat):
        if etat == "auto" or etat is None: self.forces.pop(cam, None)
        else: self.forces[cam] = {"programme": PROGRAMME, "preview": PREVIEW, "repos": REPOS}[etat]
        self.changement()

    def url(self):
        return "http://%s:%d/" % (ip_locale(), int(self.r.get("port", 8790)))


# ===================================================================== serveur HTTP + WebSocket
class WS:
    def __init__(self, sock):
        self.sock = sock; self.verrou = threading.Lock(); self.ouvert = True

    def envoyer(self, data, op=1):
        if not self.ouvert: return
        n = len(data)
        h = bytes([0x80 | op]) + (bytes([n]) if n < 126 else bytes([126]) + struct.pack(">H", n) if n < 65536 else bytes([127]) + struct.pack(">Q", n))
        try:
            with self.verrou: self.sock.sendall(h + data)
        except OSError:
            self.ouvert = False

    def lire(self):
        def exact(n):
            b = b""
            while len(b) < n:
                c = self.sock.recv(n - len(b))
                if not c: raise ConnectionError
                b += c
            return b
        a, b = exact(2)
        op, n = a & 0x0F, b & 0x7F
        if n == 126: n = struct.unpack(">H", exact(2))[0]
        elif n == 127: n = struct.unpack(">Q", exact(8))[0]
        masque = exact(4) if b & 0x80 else b"\0\0\0\0"
        d = bytes(x ^ masque[i % 4] for i, x in enumerate(exact(n)))
        return op, d


class Gestion(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    @property
    def moteur(self):
        return self.server.moteur

    def repondre(self, code, data, ctype):
        if isinstance(data, str): data = data.encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store"); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            return self.websocket(int((q.get("cam") or ["0"])[0] or 0))
        if u.path in ("/", "/index.html"):
            return self.repondre(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/api/etat":
            return self.repondre(200, json.dumps(self.moteur.instantane(), ensure_ascii=False), "application/json; charset=utf-8")
        m = re.match(r"^/api/cam/(\d+)$", u.path)
        if m:
            e = self.moteur.etats().get(int(m.group(1)))
            return self.repondre(200 if e is not None else 404, NOM_ETAT.get(e, "inconnu"), "text/plain; charset=utf-8")
        if u.path == "/api/forcer":
            try:
                cam = int(q["cam"][0]); etat = q.get("etat", ["auto"])[0]
                if etat not in ("programme", "preview", "repos", "auto"): raise ValueError
                self.moteur.forcer(cam, etat); return self.repondre(200, "ok", "text/plain")
            except (KeyError, ValueError):
                return self.repondre(400, "cam=N&etat=programme|preview|repos|auto", "text/plain")
        if u.path == "/api/aide":
            return self.repondre(200, AIDE, "text/plain; charset=utf-8")
        self.repondre(404, "introuvable", "text/plain")

    def websocket(self, cam):
        cle = self.headers.get("Sec-WebSocket-Key", "")
        acc = base64.b64encode(hashlib.sha1((cle + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101); self.send_header("Upgrade", "websocket"); self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", acc); self.end_headers(); self.wfile.flush()
        ws = WS(self.connection)
        with self.moteur.verrou: self.moteur.clients[ws] = cam
        self.moteur.changement()
        try:
            self.connection.settimeout(30)
            while ws.ouvert:
                op, d = ws.lire()
                if op == 8: break
                if op == 9: ws.envoyer(d, 10); continue
                if op == 1:
                    try:
                        m = json.loads(d)
                        if m.get("type") == "camera":
                            with self.moteur.verrou: self.moteur.clients[ws] = int(m.get("cam") or 0)
                            self.moteur.changement()
                    except Exception:
                        pass
        except (OSError, ConnectionError):
            pass
        finally:
            ws.ouvert = False
            with self.moteur.verrou: self.moteur.clients.pop(ws, None)
            self.moteur.changement()
            self.close_connection = True


class Serveur(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


AIDE = """TALLY XIII — protocole ouvert pour boîtiers (ESP32, M5Stack ATOM, Arduino Wi-Fi…) et logiciels (Bitfocus Companion…)

GET  /api/cam/N        → texte « programme », « preview » ou « repos » (caméra N, à interroger toutes les 100 à 250 ms)
GET  /api/etat         → JSON complet : caméras (état, nom, téléphones connectés), sources (mélangeurs, connexion)
GET  /api/forcer?cam=N&etat=programme|preview|repos|auto   → forçage manuel (auto = rendre la main au mélangeur)
WS   /ws?cam=N         → WebSocket : un message JSON {"type":"etat",…} à chaque changement + {"type":"battement"} toutes les 2 s
                         envoyer {"type":"camera","cam":N} pour changer de caméra
Couleurs conseillées : programme = rouge, preview = vert, repos = éteint.
"""

PAGE = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no">
<meta name="theme-color" content="#000"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<title>Tally XIII</title>
<style>
html,body{margin:0;height:100%;background:#141414;color:#fff;font-family:system-ui,-apple-system,"IBM Plex Sans",sans-serif;overflow:hidden;-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent}
body{display:flex;flex-direction:column;align-items:center;justify-content:center;transition:background .08s}
body.programme{background:#d50000}body.preview{background:#00a344}body.repos{background:#161616}body.perdu{background:#2a2a2a}
#cam{font-size:min(34vw,30vh);font-weight:900;line-height:1;letter-spacing:-.03em}
#nm{font-size:min(8vw,6vh);font-weight:700;margin-top:2vh;text-align:center;padding:0 4vw;opacity:.95}
#st{font-size:min(6.5vw,4.5vh);font-weight:800;margin-top:3vh;letter-spacing:.22em}
#info{position:fixed;top:calc(10px + env(safe-area-inset-top));left:0;right:0;text-align:center;font-size:13px;opacity:.75}
#bar{position:fixed;left:0;right:0;bottom:0;display:flex;gap:8px;justify-content:center;padding:10px 10px calc(12px + env(safe-area-inset-bottom));background:#0007;transition:opacity .4s}
#bar.cache{opacity:0;pointer-events:none}
#bar button{font:600 15px system-ui;background:#fff2;color:#fff;border:1px solid #fff4;border-radius:12px;padding:11px 15px}
#pick{position:fixed;inset:0;background:#111;display:none;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:20px;text-align:center}
#pick.on{display:flex}#pick .g{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;width:min(440px,92vw)}
#pick button{font:800 22px system-ui;padding:16px 0 12px;border-radius:14px;border:2px solid #333;background:#222;color:#fff;display:flex;flex-direction:column;align-items:center;gap:3px}
#pick button small{font:500 11px system-ui;opacity:.7;max-width:90%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#pick button.programme{border-color:#d50000}#pick button.preview{border-color:#00a344}
#logo{font:italic 700 15px system-ui;color:#f0b378;letter-spacing:.1em}
</style></head><body class="perdu">
<div id="info">Tally XIII · connexion…</div>
<div id="cam">–</div><div id="nm"></div><div id="st"></div>
<div id="bar"><button id="b-cam">Caméra</button><button id="b-fs">Plein écran</button></div>
<div id="pick"><div id="logo">TALLY XIII</div><b style="font-size:21px">Quelle caméra tenez-vous ?</b><div class="g"></div>
<small style="opacity:.7;max-width:420px">Touchez l'écran pour le plein écran. Désactivez la mise en veille du téléphone pendant le direct : l'écran vibre au passage à l'antenne.</small></div>
<script>
const $ = id => document.getElementById(id), q = new URLSearchParams(location.search);
let cam = +(q.get('cam') || localStorage.getItem('tally.xiii.cam') || 0), S = null, last = '', ws = null, vu = 0, wl = null, tBar = 0;
const ETIQ = { programme: '● ANTENNE', preview: 'PREVIEW', repos: '' };
function pick() {
  const g = document.querySelector('#pick .g'), C = (S && S.cameras) || {}; const n = Object.keys(C).length || 8;
  g.innerHTML = Array.from({ length: n }, (_, i) => { const c = C[i + 1] || {}; return '<button class="' + (c.etat || '') + '" data-c="' + (i + 1) + '">' + (i + 1) + '<small>' + (c.nom || '&nbsp;').replace(/</g, '&lt;') + '</small></button>'; }).join('');
  g.querySelectorAll('button').forEach(b => b.onclick = () => { cam = +b.dataset.c; localStorage.setItem('tally.xiii.cam', cam); $('pick').classList.remove('on'); envoyerCam(); dessiner(); plein(); });
  $('pick').classList.add('on');
}
function dessiner() {
  $('cam').textContent = cam || '–';
  if (!S || Date.now() - vu > 6000) { document.body.className = 'perdu'; $('st').textContent = 'PAS DE LIAISON'; $('info').textContent = 'Tally XIII · reconnexion…'; return; }
  const c = (S.cameras || {})[cam] || {}, e = c.etat || 'repos';
  document.body.className = e; $('nm').textContent = c.nom || ''; $('st').textContent = ETIQ[e] || '';
  const src = (S.sources || []); const ok = src.filter(s => s.connecte).length;
  $('info').textContent = 'Tally XIII · ' + (src.length ? (ok ? src.filter(s => s.connecte).map(s => s.nom).join(' + ') : 'mélangeur déconnecté') : 'aucun mélangeur');
  if (e === 'programme' && last !== 'programme' && S.vibrer !== false && navigator.vibrate) navigator.vibrate([150, 70, 150]);
  last = e;
  if ($('pick').classList.contains('on')) pick();
}
function envoyerCam() { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'camera', cam })); }
function connecter() {
  ws = new WebSocket('ws://' + location.host + '/ws?cam=' + cam);
  ws.onopen = envoyerCam;
  ws.onmessage = e => { try { const m = JSON.parse(e.data); vu = Date.now(); if (m.type === 'etat') { S = m; dessiner(); } } catch (x) {} };
  ws.onclose = () => { ws = null; setTimeout(connecter, 1000); };
}
async function veille() { try { if ('wakeLock' in navigator && !wl) { wl = await navigator.wakeLock.request('screen'); wl.addEventListener('release', () => wl = null); } } catch (e) {} }
function plein() { const d = document.documentElement; try { (d.requestFullscreen || d.webkitRequestFullscreen || (() => {})).call(d); } catch (e) {} veille(); }
function barre() { $('bar').classList.remove('cache'); clearTimeout(tBar); tBar = setTimeout(() => $('bar').classList.add('cache'), 4000); }
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { veille(); if (!ws) connecter(); } });
$('b-cam').onclick = e => { e.stopPropagation(); pick(); }; $('b-fs').onclick = e => { e.stopPropagation(); plein(); };
document.body.addEventListener('click', () => { barre(); veille(); });
setInterval(dessiner, 1000); barre(); if (!cam) setTimeout(pick, 300); dessiner(); connecter();
</script></body></html>"""


if __name__ == "__main__":
    # mode serveur sans interface : python3 -m xiii.tally_moteur
    m = Moteur(); m.demarrer(); print("Tally XIII :", m.url())
    while True: time.sleep(3600)
