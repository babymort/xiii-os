# OS XIII — Envoi XIII : envoyer des fichiers aux appareils proches, façon AirDrop, sans Internet ni compte.
# Compatible LocalSend (protocole ouvert v2) : les téléphones Android / iPhone, Mac et PC qui ont LocalSend,
# et les autres ordinateurs OS XIII, se voient et s'envoient des fichiers sur le même réseau.
# • xiii-envoi              : fenêtre d'envoi (appareils proches, fichiers, progression)
# • xiii-envoi FICHIERS…    : la même, fichiers déjà choisis (clic droit « Envoyer à un appareil proche » dans Fichiers)
# • xiii-envoi --recevoir   : service de réception (lancé avec la session) ; fichiers reçus dans Téléchargements/Reçus
# • xiii-envoi --envoyer IP FICHIERS… : envoi en ligne de commande (tests)
# Application développée par Matthieu Lamotte.
import os, sys, json, socket, struct, threading, time, uuid, secrets, mimetypes, subprocess, ssl, http.client, urllib.parse, re
import http.server, socketserver

PORT = 53317
GROUPE = "224.0.0.167"
API = "/api/localsend/v2"
ID = os.path.expanduser("~/.local/share/xiii/envoi-id")


def cfg():
    try:
        sys.path.insert(0, "/usr/lib/xiii")
        from xiii import config
        return config.charger()
    except Exception:
        return {}


def empreinte():
    try:
        return open(ID).read().strip()
    except OSError:
        os.makedirs(os.path.dirname(ID), exist_ok=True)
        e = secrets.token_hex(32); open(ID, "w").write(e); return e


def identite(annonce=None):
    c = cfg()
    d = {"alias": (c.get("envoi_nom") or "").strip() or "OS XIII · " + socket.gethostname()[:20], "version": "2.1",
         "deviceModel": "OS XIII", "deviceType": "desktop", "fingerprint": empreinte(), "port": PORT, "protocol": "http", "download": False}
    if annonce is not None: d["announce"] = annonce
    return d


def dossier_reception():
    try:
        import gi
        from gi.repository import GLib
        base = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or os.path.expanduser("~/Téléchargements")
    except Exception:
        base = os.path.expanduser("~/Téléchargements")
    d = os.path.join(base, "Reçus"); os.makedirs(d, exist_ok=True); return d


def nom_sur(dossier, nom):
    """Nom de fichier sans chemin dangereux ; les sous-dossiers envoyés (dossier/fichier) sont gardés ; jamais d'écrasement."""
    parts = [p for p in re.split(r"[\\/]+", nom) if p not in ("", ".", "..")] or ["fichier"]
    p = os.path.join(dossier, *parts); os.makedirs(os.path.dirname(p), exist_ok=True)
    base, ext = os.path.splitext(p); k = 2
    while os.path.exists(p): p = "%s (%d)%s" % (base, k, ext); k += 1
    return p


def notifier(titre, corps, actions=None, attendre=0):
    """notify-send ; avec actions, attend la réponse (clé de l'action ou None)."""
    cmd = ["notify-send", "-a", "Envoi XIII", "-i", "xiii-envoi", titre, corps]
    for k, n in (actions or []): cmd += ["-A", "%s=%s" % (k, n)]
    try:
        if actions:
            r = subprocess.run(cmd + ["--wait"], capture_output=True, text=True, timeout=attendre or 60)
            return r.stdout.strip() or None
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return None


# ===================================================================== réception (service)
class Recepteur:
    def __init__(self):
        self.appareils = {}       # empreinte → {alias, ip, port, protocol, deviceType, deviceModel, vu}
        self.sessions = {}        # sessionId → {fichiers: {id: {token, nom, taille}}, de: alias, recus: [], debut}
        self.moi = empreinte()

    # ---- découverte
    def noter(self, d, ip):
        if not isinstance(d, dict) or d.get("fingerprint") in (None, self.moi): return
        self.appareils[d["fingerprint"]] = {"alias": d.get("alias") or ip, "ip": ip, "port": int(d.get("port") or PORT), "protocol": d.get("protocol") or "https",
                                           "deviceType": d.get("deviceType") or "desktop", "deviceModel": d.get("deviceModel") or "", "fingerprint": d["fingerprint"], "vu": time.time()}

    def annoncer(self, annonce=True):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            s.sendto(json.dumps(identite(annonce)).encode(), (GROUPE, PORT)); s.close()
        except OSError as e:
            print("annonce impossible :", e, flush=True)

    def ecouter_multicast(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError): pass
        s.bind(("", PORT))
        try: s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, struct.pack("4sl", socket.inet_aton(GROUPE), socket.INADDR_ANY))
        except OSError as e: print("multicast indisponible :", e, flush=True)
        while True:
            try:
                data, (ip, _p) = s.recvfrom(65535); d = json.loads(data.decode("utf-8", "replace"))
            except Exception:
                continue
            if d.get("fingerprint") == self.moi: continue
            self.noter(d, ip)
            if d.get("announce"):     # un appareil vient d'arriver : on se présente à lui
                threading.Thread(target=self.repondre, args=(d, ip), daemon=True).start()

    def repondre(self, d, ip):
        try:
            r = requete(d.get("protocol") or "https", ip, int(d.get("port") or PORT), "POST", API + "/register", identite(), 3)
            if r[0] != 200: raise OSError
        except Exception:
            self.annoncer(False)

    # ---- HTTP
    def serveur(self):
        R = self
        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *a): pass
            def json(self, code, o=None):
                b = json.dumps(o).encode() if o is not None else b""
                self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            def corps(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"{}") if n else {}
            def do_GET(self):
                u = urllib.parse.urlparse(self.path)
                if u.path in (API + "/info", "/api/localsend/v1/info"): return self.json(200, identite())
                if u.path == "/api/xiii/appareils" and self.client_address[0] == "127.0.0.1":
                    lim = time.time() - 600
                    return self.json(200, sorted([a for a in R.appareils.values() if a["vu"] > lim], key=lambda a: -a["vu"]))
                self.json(404, {"message": "introuvable"})
            def do_POST(self):
                u = urllib.parse.urlparse(self.path); q = dict(urllib.parse.parse_qsl(u.query))
                if u.path == API + "/register":
                    R.noter(self.corps(), self.client_address[0]); return self.json(200, identite())
                if u.path == "/api/xiii/annoncer" and self.client_address[0] == "127.0.0.1":
                    R.annoncer(True); return self.json(200, {"ok": True})
                if u.path == API + "/prepare-upload": return R.preparer(self)
                if u.path == API + "/upload": return R.recevoir(self, q)
                if u.path == API + "/cancel":
                    R.sessions.pop(q.get("sessionId"), None); return self.json(200)
                self.json(404, {"message": "introuvable"})
        class Srv(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True; allow_reuse_address = True
            def handle_error(self, *a): pass       # sondes https sur ce serveur http, connexions coupées : rien à signaler
        return Srv(("0.0.0.0", PORT), H)

    def preparer(self, h):
        try: o = h.corps()
        except Exception: return h.json(400, {"message": "requête invalide"})
        info = o.get("info") or {}; F = o.get("files") or {}
        if not F: return h.json(204)
        self.noter(info, h.client_address[0])
        de = info.get("alias") or h.client_address[0]
        total = sum(int(f.get("size") or 0) for f in F.values())
        resume = "%d fichier%s · %s" % (len(F), "s" if len(F) > 1 else "", taille(total)) + ("" if len(F) > 3 else " — " + ", ".join(os.path.basename(f.get("fileName", "")) for f in F.values()))
        c = cfg()
        if not c.get("envoi_actif", True): return h.json(403, {"message": "réception désactivée"})
        if not c.get("envoi_auto", False):
            r = notifier("%s veut vous envoyer des fichiers" % de, resume, [("oui", "Accepter"), ("non", "Refuser")], 90)
            if r != "oui": return h.json(403, {"message": "refusé"})
        sid = uuid.uuid4().hex
        self.sessions[sid] = {"fichiers": {k: {"token": secrets.token_hex(12), "nom": f.get("fileName") or k, "taille": int(f.get("size") or 0)} for k, f in F.items()},
                              "de": de, "recus": [], "debut": time.time(), "dossier": dossier_reception()}
        h.json(200, {"sessionId": sid, "files": {k: v["token"] for k, v in self.sessions[sid]["fichiers"].items()}})

    def recevoir(self, h, q):
        s = self.sessions.get(q.get("sessionId")); f = s and s["fichiers"].get(q.get("fileId"))
        if not f or f["token"] != q.get("token"): return h.json(403, {"message": "jeton invalide"})
        n = int(h.headers.get("Content-Length") or 0)
        p = nom_sur(s["dossier"], f["nom"]); tmp = p + ".part"
        try:
            with open(tmp, "wb") as out:
                reste = n
                while reste > 0:
                    b = h.rfile.read(min(1 << 20, reste))
                    if not b: break
                    out.write(b); reste -= len(b)
            if reste: raise OSError("transfert interrompu")
            os.replace(tmp, p)
        except Exception as e:
            try: os.remove(tmp)
            except OSError: pass
            return h.json(500, {"message": str(e)})
        s["recus"].append(p); h.json(200)
        print("[envoi] reçu", p, flush=True)
        if len(s["recus"]) == len(s["fichiers"]):
            sid = q.get("sessionId"); self.sessions.pop(sid, None)
            def fin():
                r = notifier("Reçu de %s" % s["de"], "%d fichier%s dans Téléchargements › Reçus" % (len(s["recus"]), "s" if len(s["recus"]) > 1 else ""), [("ouvrir", "Ouvrir le dossier")], 300)
                if r == "ouvrir": subprocess.Popen(["xiii-fichiers", s["dossier"]])
            threading.Thread(target=fin, daemon=True).start()

    def lancer(self):
        try:
            srv = self.serveur()
        except OSError as e:
            print("Envoi XIII : port %d déjà utilisé (%s) — réception déjà active ?" % (PORT, e), flush=True); return 1
        threading.Thread(target=self.ecouter_multicast, daemon=True).start()
        def annonces():
            for _ in range(3): self.annoncer(True); time.sleep(2)
            while True: time.sleep(300); self.annoncer(True)
        threading.Thread(target=annonces, daemon=True).start()
        print("Envoi XIII : réception active (port %d), visible sous « %s »" % (PORT, identite()["alias"]), flush=True)
        srv.serve_forever()


# ===================================================================== envoi
def taille(n):
    for u in ("o", "Ko", "Mo", "Go"):
        if n < 1000 or u == "Go": return ("%.0f %s" if u == "o" else "%.1f %s") % (n, u)
        n /= 1000


def connexion(protocole, ip, port, delai):
    if protocole == "https":
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE   # LocalSend : certificats auto-signés
        return http.client.HTTPSConnection(ip, port, timeout=delai, context=ctx)
    return http.client.HTTPConnection(ip, port, timeout=delai)


def requete(protocole, ip, port, methode, chemin, corps=None, delai=10):
    c = connexion(protocole, ip, port, delai)
    b = json.dumps(corps).encode() if corps is not None else None
    c.request(methode, chemin, body=b, headers={"Content-Type": "application/json"} if b else {})
    r = c.getresponse(); d = r.read(); c.close()
    try: return r.status, json.loads(d) if d else None
    except ValueError: return r.status, None


def sonder(ip):
    """Appareil à une adresse donnée (saisie manuelle) : https puis http."""
    for proto in ("https", "http"):
        try:
            st, d = requete(proto, ip, PORT, "GET", API + "/info", None, 3)
            if st == 200 and d: return {"alias": d.get("alias") or ip, "ip": ip, "port": PORT, "protocol": proto, "deviceType": d.get("deviceType") or "desktop",
                                        "deviceModel": d.get("deviceModel") or "", "fingerprint": d.get("fingerprint") or ip, "vu": time.time()}
        except Exception:
            continue
    return None


def appareils_proches(annoncer=True):
    """Liste tenue par le service de réception (lancé avec la session)."""
    try:
        if annoncer: requete("http", "127.0.0.1", PORT, "POST", "/api/xiii/annoncer", {}, 2)
        st, d = requete("http", "127.0.0.1", PORT, "GET", "/api/xiii/appareils", None, 2)
        return d or []
    except Exception:
        return None     # service arrêté


def envoyer(app, fichiers, prog=None):
    """→ (ok, message). prog(fait, total, nom)."""
    F = {}; P = {}
    for p in fichiers:
        if not os.path.isfile(p): continue
        k = uuid.uuid4().hex[:16]
        F[k] = {"id": k, "fileName": os.path.basename(p), "size": os.path.getsize(p), "fileType": mimetypes.guess_type(p)[0] or "application/octet-stream"}; P[k] = p
    if not F: return False, "Aucun fichier"
    try:
        st, d = requete(app["protocol"], app["ip"], app["port"], "POST", API + "/prepare-upload", {"info": identite(), "files": F}, 120)
    except Exception as e:
        return False, "Appareil injoignable (%s)" % e
    if st == 204: return True, "L'appareil n'avait besoin d'aucun fichier"
    if st == 403: return False, "Refusé par %s" % app["alias"]
    if st == 409: return False, "%s reçoit déjà un autre envoi" % app["alias"]
    if st == 401: return False, "%s demande un code PIN (désactivez-le dans LocalSend)" % app["alias"]
    if st != 200 or not d: return False, "Réponse inattendue (%s)" % st
    sid = d.get("sessionId"); jetons = d.get("files") or {}
    total = sum(F[k]["size"] for k in jetons if k in F); fait = 0
    for k, jeton in jetons.items():
        if k not in P: continue
        p = P[k]; n = F[k]["size"]
        q = urllib.parse.urlencode({"sessionId": sid, "fileId": k, "token": jeton})
        c = connexion(app["protocol"], app["ip"], app["port"], 60)
        try:
            c.putrequest("POST", API + "/upload?" + q); c.putheader("Content-Length", str(n)); c.putheader("Content-Type", F[k]["fileType"]); c.endheaders()
            with open(p, "rb") as f:
                while True:
                    b = f.read(1 << 20)
                    if not b: break
                    c.send(b); fait += len(b)
                    if prog: prog(fait, total, F[k]["fileName"])
            r = c.getresponse(); r.read()
            if r.status != 200: return False, "Échec sur %s (%s)" % (F[k]["fileName"], r.status)
        except Exception as e:
            try: requete(app["protocol"], app["ip"], app["port"], "POST", API + "/cancel?sessionId=" + sid, None, 3)
            except Exception: pass
            return False, "Transfert interrompu : %s" % e
        finally:
            c.close()
    return True, "%d fichier%s envoyé%s à %s" % (len(jetons), "s" if len(jetons) > 1 else "", "s" if len(jetons) > 1 else "", app["alias"])


# ===================================================================== fenêtre
def fenetre(fichiers):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gdk, GLib, Gio
    from .ui import boite, label, bouton, ico, vider, interrupteur
    from .appli import preparer
    from . import config

    ICONES = {"mobile": "smartphone", "desktop": "monitor", "laptop": "laptop", "web": "globe", "headless": "server", "server": "server"}

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="fr.xiii.envoi", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE); self.fichiers = list(fichiers); self.manuels = []

        def do_command_line(self, cl):
            a = [x for x in cl.get_arguments()[1:] if not x.startswith("--")]
            for x in a:
                p = Gio.File.new_for_commandline_arg_and_cwd(x, cl.get_cwd() or "/").get_path()
                if p and os.path.isfile(p) and p not in self.fichiers: self.fichiers.append(p)
            self.activer(); return 0

        def activer(self):
            if getattr(self, "win", None): self.maj_fichiers(); self.win.present(); return
            preparer(""".appareil { border-radius: 16px; padding: 14px 8px; min-width: 120px; }
                        .appareil:hover { background: alpha(@accent_bg_color, .18); }
                        .zone-depot { border: 2px dashed alpha(currentColor, .25); border-radius: 14px; padding: 14px; }""")
            if appareils_proches(False) is None and cfg().get("envoi_actif", True):
                subprocess.Popen(["xiii-envoi", "--recevoir"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            w = Gtk.ApplicationWindow(application=self, title="Envoi XIII"); w.set_default_size(720, 640); self.win = w
            v = boite(True, 14, margin_start=24, margin_end=24, margin_top=20, margin_bottom=20)
            h = boite(False, 12); h.append(ico("send", 30, "c"))
            t = boite(True, 0, hexpand=True); t.append(label("Envoi XIII", "page-titre"))
            t.append(label("Vers les téléphones et ordinateurs proches — LocalSend ou OS XIII, même réseau, sans Internet", "attenue", wrap=True)); h.append(t); v.append(h)
            # fichiers
            self.z = boite(True, 6, "zone-depot"); v.append(self.z)
            dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
            dt.connect("drop", lambda t_, val, x, y: (self.fichiers.extend(f.get_path() for f in val.get_files() if f.get_path() and os.path.isfile(f.get_path())), self.maj_fichiers(), True)[2])
            self.z.add_controller(dt)
            # appareils
            hh = boite(False, 8); hh.append(label("Appareils à proximité", "section", hexpand=True))
            hh.append(bouton("Actualiser", "refresh-cw", "fantome", rappel=lambda: self.chercher(True))); v.append(hh)
            self.g = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=2, column_spacing=8, row_spacing=8, homogeneous=True); v.append(self.g)
            self.vide = label("Recherche… Les appareils doivent être sur le même réseau, avec LocalSend ouvert (ou OS XIII).", "attenue", wrap=True); v.append(self.vide)
            m = boite(False, 8); self.ip = Gtk.Entry(placeholder_text="Pas dans la liste ? Adresse IP de l'appareil (ex. 192.168.1.23)", hexpand=True)
            m.append(self.ip); m.append(bouton("Ajouter", None, "fantome", rappel=self.ajouter_ip)); self.ip.connect("activate", lambda *_: self.ajouter_ip()); v.append(m)
            self.etat = label("", "attenue", wrap=True); v.append(self.etat)
            self.pb = Gtk.ProgressBar(visible=False); v.append(self.pb)
            # réception
            v.append(label("Recevoir", "section"))
            c = config.charger()
            r = boite(False, 10); r.append(label("Visible sous le nom", hexpand=True)); self.nom = Gtk.Entry(text=identite()["alias"], width_chars=26)
            self.nom.connect("changed", lambda e: config.modifier(envoi_nom=e.get_text().strip())); r.append(self.nom); v.append(r)
            r = boite(False, 10); r.append(label("Recevoir des fichiers des appareils proches", hexpand=True))
            r.append(interrupteur(c.get("envoi_actif", True), lambda on: (config.modifier(envoi_actif=on), on and subprocess.Popen(["xiii-envoi", "--recevoir"], start_new_session=True)))); v.append(r)
            r = boite(False, 10); r.append(label("Accepter sans demander (réseau de confiance)", hexpand=True))
            r.append(interrupteur(c.get("envoi_auto", False), lambda on: config.modifier(envoi_auto=on))); v.append(r)
            v.append(label("Fichiers reçus : Téléchargements › Reçus. Sur un téléphone, installez l'application gratuite LocalSend.", "petit", "attenue", wrap=True))
            from . import systeme as S
            if S.pare_feu() and not S.DEMO:
                r = boite(False, 10); r.append(label("Le pare-feu est actif : autorisez Envoi XIII pour être visible des autres appareils.", "petit", wrap=True, hexpand=True))
                r.append(bouton("Autoriser", None, "pilule", rappel=lambda: subprocess.Popen(["pkexec", "sh", "-c", "ufw allow 53317/tcp && ufw allow 53317/udp"]))); v.append(r)
            sc = Gtk.ScrolledWindow(); sc.set_child(v); w.set_child(sc)
            self.maj_fichiers(); self.chercher(True); GLib.timeout_add_seconds(3, lambda: (self.chercher(False), True)[1]); w.present()

        def maj_fichiers(self):
            vider(self.z)
            if not self.fichiers:
                self.z.append(label("Glissez des fichiers ici", "gras", xalign=0.5))
            else:
                tot = sum(os.path.getsize(p) for p in self.fichiers if os.path.isfile(p))
                self.z.append(label("%d fichier%s · %s" % (len(self.fichiers), "s" if len(self.fichiers) > 1 else "", taille(tot)), "gras"))
                for p in self.fichiers[:6]:
                    r = boite(False, 8); r.append(ico("file", 14, "d")); r.append(label(os.path.basename(p), "petit", ellipsize=True, hexpand=True))
                    r.append(bouton(None, "x", "plat", taille=12, rappel=lambda p=p: (self.fichiers.remove(p), self.maj_fichiers()))); self.z.append(r)
                if len(self.fichiers) > 6: self.z.append(label("+ %d autres" % (len(self.fichiers) - 6), "petit", "attenue"))
            b = boite(False, 8, halign=Gtk.Align.CENTER); b.append(bouton("Choisir des fichiers…", "plus", "fantome", rappel=self.choisir)); self.z.append(b)

        def choisir(self):
            d = Gtk.FileDialog(title="Fichiers à envoyer")
            def fin(dd, res):
                try: L = dd.open_multiple_finish(res)
                except GLib.Error: return
                for i in range(L.get_n_items()):
                    p = L.get_item(i).get_path()
                    if p and p not in self.fichiers: self.fichiers.append(p)
                self.maj_fichiers()
            d.open_multiple(self.win, None, fin)

        def ajouter_ip(self):
            ip = self.ip.get_text().strip()
            if not ip: return
            self.etat.set_text("Recherche de %s…" % ip)
            def fond():
                a = sonder(ip); GLib.idle_add(lambda: (self.manuels.append(a) if a else None, self.etat.set_text(("Ajouté : " + a["alias"]) if a else "Aucun appareil LocalSend ou OS XIII à cette adresse"), self.chercher(False), False)[-1])
            threading.Thread(target=fond, daemon=True).start()

        def chercher(self, annoncer):
            def fond():
                L = appareils_proches(annoncer); GLib.idle_add(lambda: (self.rendu(L), False)[1])
            threading.Thread(target=fond, daemon=True).start()

        def rendu(self, L):
            vus = {a["fingerprint"] for a in (L or [])}
            L = (L or []) + [a for a in self.manuels if a["fingerprint"] not in vus]
            sig = [(a["fingerprint"], a["alias"]) for a in L]
            if sig == getattr(self, "_sig", None): return
            self._sig = sig; vider(self.g); self.vide.set_visible(not L)
            if not L: return
            for a in L:
                b = Gtk.Button(); b.add_css_class("appareil"); b.add_css_class("plat")
                c = boite(True, 6); c.append(ico(ICONES.get(a.get("deviceType"), "monitor"), 34, "c")); c.append(label(a["alias"], "gras", xalign=0.5, ellipsize=True))
                c.append(label(a.get("deviceModel") or a["ip"], "petit", "attenue", xalign=0.5, ellipsize=True)); b.set_child(c)
                b.connect("clicked", lambda _b, a=a: self.envoyer(a)); self.g.append(b)

        def envoyer(self, a):
            if not self.fichiers: self.etat.set_text("Choisissez d'abord des fichiers."); return
            self.etat.set_text("En attente de l'accord de %s…" % a["alias"]); self.pb.set_visible(True); self.pb.set_fraction(0)
            def prog(f, t, n): GLib.idle_add(lambda: (self.pb.set_fraction(f / max(1, t)), self.etat.set_text("Envoi de %s… %s / %s" % (n, taille(f), taille(t))), False)[-1])
            def fond():
                ok, msg = envoyer(a, list(self.fichiers), prog)
                GLib.idle_add(lambda: (self.etat.set_text(("✓ " if ok else "✗ ") + msg), self.pb.set_visible(ok), self.pb.set_fraction(1 if ok else 0), False)[-1])
            threading.Thread(target=fond, daemon=True).start()

    return App().run([sys.argv[0]] + fichiers)


def main():
    a = sys.argv[1:]
    if "--recevoir" in a:
        sys.exit(Recepteur().lancer() or 0)
    if a[:1] == ["--envoyer"] and len(a) >= 3:
        app = sonder(a[1])
        if not app: print("ÉCHEC aucun appareil à", a[1]); sys.exit(1)
        ok, msg = envoyer(app, a[2:]); print(("OK " if ok else "ÉCHEC ") + msg); sys.exit(0 if ok else 1)
    if "--lister" in a:
        L = appareils_proches(True); time.sleep(3); L = appareils_proches(False)
        print(json.dumps(L, ensure_ascii=False, indent=1)); sys.exit(0)
    sys.exit(fenetre([x for x in a if not x.startswith("--")]))
