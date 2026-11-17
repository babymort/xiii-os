# OS XIII — la Suite XIII en applications natives, hors ligne.
# Un serveur local (127.0.0.1) sert la copie embarquée du site ; chaque outil s'ouvre dans sa propre fenêtre (WebKitGTK),
# avec son icône dans la barre des tâches. Toutes les fenêtres partagent les mêmes données (projets, annuaire, échanges entre outils).
# • .xiii.json : double-clic → le bon outil, fichier importé automatiquement
# • « Envoyer à DOSSIER XIII » (clic droit dans Fichiers) : n'importe quel document rejoint le dossier en cours
# • « Convertir avec ENCODO XIII » : fichiers chargés dans le convertisseur
# • exports et téléchargements rangés dans le projet XIII actif (03_Documents / 06_Exports), sinon dans Téléchargements
# Application développée par Matthieu Lamotte.
import os, sys, json, re, threading, secrets, mimetypes, socket, time, urllib.parse
import http.server, socketserver
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, Gdk, Gio, GLib, WebKit
try:
    gi.require_version("GdkWayland", "4.0")
    from gi.repository import GdkWayland
except (ValueError, ImportError):
    GdkWayland = None
from . import config

SYS = "/usr/share/xiii/suite"
UTIL = os.path.join(GLib.get_user_data_dir(), "xiii", "suite")
PORT0 = 8713
DONNEES = os.path.join(GLib.get_user_data_dir(), "xiii", "suite-donnees")
CACHE = os.path.join(GLib.get_user_cache_dir(), "xiii", "suite")
SOUS = ["01_Rushes", "02_Son", "03_Documents", "04_Graphismes", "05_Montage", "06_Exports", "07_Livraison"]
EXT_DOCS = (".json", ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".ics", ".txt", ".odt", ".ods", ".pptx", ".html", ".vcf", ".gpx", ".kml", ".mhl", ".fdx")

# kind xiii-link → [(outil, id du champ d'import, libellé)]
CIBLES = {
    "project": [("callsheeto", "xp-file", "CALL SHEETO — feuille de service"), ("conduco", "xp-file", "CONDUCO — conducteur"), ("deviso", "xp-file", "DEVISO — devis"), ("dossier", "xp-file", "DOSSIER — dossier de production")],
    "contacts": [("callsheeto", "xb-cfile", "Annuaire XIII (via CALL SHEETO)"), ("dossier", "xb-cfile", "Annuaire XIII (via DOSSIER)")],
    "crew": [("callsheeto", "project-upload", "CALL SHEETO — feuille de service"), ("deviso", "project-upload", "DEVISO — devis")],
    "rundown": [("callsheeto", "xcs-file", "CALL SHEETO — feuille de service depuis le conducteur")],
    "workplan": [("callsheeto", "project-upload", "CALL SHEETO — feuilles de service du plan de travail")],
    "equipment": [("plano", "project-upload", "PLANO — placer le matériel"), ("deviso", "project-upload", "DEVISO — chiffrer le matériel")],
    "sources": [("backupo", "xb-jfile", "BACKUPO — sources à sauvegarder")],
    "locations": [("repero", "project-upload", "REPERO — lieux sur la carte"), ("callsheeto", "xrp-file", "CALL SHEETO — lieux de la journée")],
    "places": [("repero", "project-upload", "REPERO — lieux sur la carte")],
    "decoupage": [("storyboardo", "project-upload", "STORYBOARDO"), ("scripto", "project-upload", "SCRIPTO")],
    "layout": [("plano", "project-upload", "PLANO")],
    "lengths": [("plano", "project-upload", "PLANO")],
    "prices": [("deviso", "project-upload", "DEVISO")],
    "devis": [("deviso", "project-upload", "DEVISO")],
}
# id d'outil dans le nom d'un projet exporté (ex. « Concert-conduco.json »)
NOMS = ["moodo", "storyboardo", "decoup", "repero", "cadro", "syno", "plano", "casto", "posto", "sono", "lumo", "runo", "transporto", "soustitro",
        "callsheeto", "calendrier", "controle", "matos", "packingo", "deviso", "ressourco", "scripto", "conduco", "graphico", "melango", "backupo", "encodo", "dossier"]


def racine():
    return UTIL if os.path.exists(os.path.join(UTIL, "index.html")) else SYS


def outils():
    try:
        return json.load(open(os.path.join(racine(), "outils-os.json"), encoding="utf-8"))
    except Exception:
        return []


def nom_outil(oid):
    return next((o["nom"] for o in outils() if o["id"] == oid), "Suite XIII" if oid == "index" else oid.upper() + " XIII")


# ===================================================================== serveur local
DEPOT = {}  # jeton → (chemin, nom, type)
SW_NEUTRE = b"self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.registration.unregister().then(()=>self.clients.claim())));"
VIDE = b"<!doctype html><meta charset=utf-8><title>Suite XIII</title><body style='background:#111'></body>"


class Gestion(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map, **{".mjs": "text/javascript", ".js": "text/javascript", ".wasm": "application/wasm",
                                                                               ".webmanifest": "application/manifest+json", ".json": "application/json", ".svg": "image/svg+xml"})

    def __init__(self, *a, **k):
        super().__init__(*a, directory=racine(), **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        chemin = urllib.parse.urlparse(self.path).path
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        if chemin.startswith("/encodo"):
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "credentialless")
        super().end_headers()

    def _brut(self, data, ctype):
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p == "/sw.js": return self._brut(SW_NEUTRE, "text/javascript")
        if p == "/__xiii/vide.html": return self._brut(VIDE, "text/html; charset=utf-8")
        if p.startswith("/__xiii/depot/"):
            d = DEPOT.get(p.rsplit("/", 1)[-1])
            if not d: self.send_error(404); return
            try: data = open(d[0], "rb").read()
            except OSError: self.send_error(404); return
            return self._brut(data, d[2])
        if p in ("/app", "/app/"): p = "/equipe.html"
        if p == "/compte": p = "/compte.html"
        if p != "/" and not os.path.exists(os.path.join(racine(), p.lstrip("/"))) and not p.endswith("/"):
            if os.path.exists(os.path.join(racine(), p.lstrip("/") + ".html")): self.path = p + ".html"
            else:
                self.send_response(404); data = open(os.path.join(racine(), "404.html"), "rb").read() if os.path.exists(os.path.join(racine(), "404.html")) else b"404"
                self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        return super().do_GET()


class Serveur(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def demarrer_serveur():
    for port in range(PORT0, PORT0 + 10):
        try:
            s = Serveur(("127.0.0.1", port), Gestion)
        except OSError:
            continue
        threading.Thread(target=s.serve_forever, daemon=True).start()
        return port
    raise RuntimeError("aucun port libre pour la Suite XIII")


def deposer(chemin):
    t = secrets.token_urlsafe(12)
    typ = Gio.content_type_guess(chemin, None)[0]
    DEPOT[t] = (chemin, os.path.basename(chemin), Gio.content_type_get_mime_type(typ) or "application/octet-stream")
    return t


# ===================================================================== scripts injectés
JS_INJECTER = r"""
(async () => {
  const L = %s, champ = %s, multiple = %s;
  let inp = null;
  for (let i = 0; i < 80 && !(inp = document.getElementById(champ)); i++) await new Promise(r => setTimeout(r, 150));
  if (!inp) { const c = [...document.querySelectorAll('input[type=file]')].filter(x => /json/.test(x.accept || '')); inp = c[0] || null; }
  if (!inp) return 'absent';
  await new Promise(r => setTimeout(r, 600));
  const dt = new DataTransfer();
  for (const d of (multiple ? L : L.slice(0, 1))) { const b = await (await fetch('/__xiii/depot/' + d.t)).blob(); dt.items.add(new File([b], d.n, { type: d.m })); }
  inp.files = dt.files;
  inp.dispatchEvent(new Event('change', { bubbles: true }));
  if (inp.onchange) try { inp.onchange({ target: inp }); } catch (e) {}
  return 'ok';
})()
"""

JS_DOSSIER = r"""
(async () => {
  const L = %s, projet = %s;
  const db = await new Promise((res, rej) => { const r = indexedDB.open('xiiiLink', 1); r.onupgradeneeded = () => { if (!r.result.objectStoreNames.contains('outbox')) r.result.createObjectStore('outbox'); }; r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
  for (const d of L) {
    const b = await (await fetch('/__xiii/depot/' + d.t)).blob();
    let p = null;
    if (/\.json$/i.test(d.n)) { try { const o = JSON.parse(await b.text()); if (o && o.format === 'xiii-link') p = o; } catch (e) {} }
    if (p && p.file && p.file.data && !p.file.blob) { const bin = atob(p.file.data), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); p.file = { name: p.file.name, type: p.file.type, blob: new Blob([u8], { type: p.file.type || '' }) }; }
    if (!p || p.kind !== 'document') {
      const titre = d.n.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ');
      p = { format: 'xiii-link', version: 1, kind: 'document', from: 'os', app: 'OS XIII', ts: Date.now(), created: new Date().toISOString(), project: { name: projet },
            title: titre, target: { title: titre, keywords: [] }, file: { name: d.n, type: d.m, blob: b }, html: null, auto: 1 };
    }
    p.id = 'x' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); p.to = 'dossier'; p.ts = Date.now();
    await new Promise((res, rej) => { const t = db.transaction('outbox', 'readwrite'); t.objectStore('outbox').put(p, p.id); t.oncomplete = res; t.onerror = () => rej(t.error); });
  }
  location.href = '/dossier.html';
  return 'ok';
})()
"""


# ===================================================================== application
class Suite(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.Suite", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.port = None; self.session = None; self.fenetres = []

    def do_startup(self):
        Gtk.Application.do_startup(self)
        try:
            Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", config.charger().get("theme") != "clair")
        except Exception:
            pass
        self.port = demarrer_serveur()
        os.makedirs(DONNEES, exist_ok=True); os.makedirs(CACHE, exist_ok=True)
        self.session = WebKit.NetworkSession.new(DONNEES, CACHE)
        self.session.connect("download-started", self.telechargement)

    def base(self):
        return "http://127.0.0.1:%d" % self.port

    # ------------------------------------------------------------- ligne de commande
    def do_command_line(self, cl):
        a = cl.get_arguments()[1:]
        cwd = cl.get_cwd() or os.path.expanduser("~")
        absolu = lambda f: f if os.path.isabs(f) else os.path.join(cwd, f)
        if f := self._opt(a, "--ouvrir"):
            for x in f: self.ouvrir_fichier(absolu(x))
        elif f := self._opt(a, "--dossier"):
            self.vers_dossier([absolu(x) for x in f])
        elif f := self._opt(a, "--encodo"):
            self.injecter("encodo", "files-in", [absolu(x) for x in f], multiple=True)
        elif a and a[0] == "--avec" and len(a) >= 3:
            self.injecter(a[1], "project-upload", [absolu(a[2])])
        else:
            oid = re.sub(r"[^a-z0-9_-]", "", (a[0] if a else "index").lower()) or "index"
            self.fenetre(oid)
        return 0

    @staticmethod
    def _opt(a, nom):
        if nom in a:
            i = a.index(nom); return [x for x in a[i + 1:] if not x.startswith("--")] or None
        return None

    # ------------------------------------------------------------- fenêtres
    def nouvelle_vue(self, liee=None):
        v = WebKit.WebView(network_session=self.session) if liee is None else WebKit.WebView(related_view=liee)
        s = v.get_settings()
        for k, val in (("enable-developer-extras", False), ("javascript-can-open-windows-automatically", True), ("enable-media-stream", True),
                       ("enable-webrtc", True), ("enable-fullscreen", True), ("enable-encrypted-media", True), ("enable-back-forward-navigation-gestures", True),
                       ("javascript-can-access-clipboard", True), ("enable-webgl", True), ("media-playback-requires-user-gesture", False)):
            try: s.set_property(k, val)
            except TypeError: pass
        s.set_user_agent_with_application_details("OS-XIII", "1")
        v.connect("permission-request", self.permission)
        v.connect("decide-policy", self.politique)
        v.connect("create", self.creer)
        return v

    def fenetre(self, oid, vue=None, apres=None):
        w = Gtk.ApplicationWindow(application=self, title=nom_outil(oid), default_width=1400, default_height=880)
        w.set_icon_name("xiii-suite-" + oid if oid != "index" else "xiii-suite")
        v = vue or self.nouvelle_vue()
        w.set_child(v); w._vue = v; w._oid = oid; w._apres = apres
        v.connect("notify::title", lambda vv, _p: w.set_title(vv.get_title() or nom_outil(oid)))
        v.connect("load-changed", self.charge, w)
        v.connect("close", lambda vv: w.close())
        w.connect("realize", lambda ww: self._app_id(ww, oid))
        self._raccourcis(w, v)
        if vue is None:
            v.load_uri(self.base() + ("/" if oid == "index" else "/%s.html" % oid))
        w.present(); self.fenetres.append(w)
        w.connect("close-request", lambda ww: (self.fenetres.remove(ww) if ww in self.fenetres else None, False)[1])
        return w

    def _app_id(self, w, oid):
        """Chaque outil a son identifiant Wayland : sa propre icône dans la barre des tâches."""
        try:
            s = w.get_surface()
            if GdkWayland and isinstance(s, GdkWayland.WaylandToplevel):
                s.set_application_id("fr.xiii.suite." + oid)
        except Exception:
            pass

    def _raccourcis(self, w, v):
        c = Gtk.ShortcutController(); c.set_scope(Gtk.ShortcutScope.MANAGED)
        def ajout(acc, fn):
            c.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(acc), Gtk.CallbackAction.new(lambda *_: (fn(), True)[1])))
        ajout("F11", lambda: w.unfullscreen() if w.is_fullscreen() else w.fullscreen())
        ajout("<Control>r", v.reload); ajout("F5", v.reload)
        ajout("<Control>plus", lambda: v.set_zoom_level(min(3, v.get_zoom_level() + .1)))
        ajout("<Control>equal", lambda: v.set_zoom_level(min(3, v.get_zoom_level() + .1)))
        ajout("<Control>minus", lambda: v.set_zoom_level(max(.4, v.get_zoom_level() - .1)))
        ajout("<Control>0", lambda: v.set_zoom_level(1))
        ajout("<Alt>Left", v.go_back); ajout("<Alt>Right", v.go_forward)
        w.add_controller(c)

    def charge(self, v, ev, w):
        if ev == WebKit.LoadEvent.FINISHED and getattr(w, "_apres", None):
            js = w._apres; w._apres = None
            v.evaluate_javascript(js, -1, None, None, None, lambda vv, res: self._resultat(vv, res), None)

    def _resultat(self, v, res):
        try:
            r = v.evaluate_javascript_finish(res)
            if r and r.to_string() == "absent":
                self.notifier("Import automatique impossible", "Utilisez le bouton « Ouvrir » de l'outil.")
        except GLib.Error:
            pass

    # ------------------------------------------------------------- navigation
    def interne(self, uri):
        return uri.startswith(self.base()) or uri.startswith(("blob:", "data:", "about:"))

    def politique(self, v, decision, typ):
        if typ in (WebKit.PolicyDecisionType.NAVIGATION_ACTION, WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            uri = decision.get_navigation_action().get_request().get_uri()
            if not self.interne(uri) and re.match(r"^(https?|mailto|tel|webcal|sms):", uri):
                Gio.AppInfo.launch_default_for_uri(uri, None); decision.ignore(); return True
        return False

    def creer(self, v, action):
        uri = action.get_request().get_uri()
        if uri and not self.interne(uri) and uri.startswith("http"):
            Gio.AppInfo.launch_default_for_uri(uri, None); return None
        nv = self.nouvelle_vue(liee=v)
        oid = re.sub(r"^.*/([a-z0-9_-]+)\.html.*$", r"\1", uri or "") if uri and ".html" in uri else "index"
        nv.connect("ready-to-show", lambda vv: self.fenetre(oid, vue=vv))
        return nv

    def permission(self, v, req):
        req.allow(); return True  # outils locaux de confiance : caméra, micro, notifications, position, presse-papiers

    # ------------------------------------------------------------- téléchargements → projet actif
    def dossier_rangement(self, nom):
        p = config.charger().get("projet_actif")
        if p:
            d = os.path.join(os.path.expanduser("~/XIII"), p, "03_Documents" if nom.lower().endswith(EXT_DOCS) else "06_Exports")
            os.makedirs(d, exist_ok=True); return d, p
        d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or os.path.expanduser("~/Téléchargements")
        os.makedirs(d, exist_ok=True); return d, None

    def telechargement(self, session, dl):
        info = []
        def destination(d, nom):
            nom = os.path.basename(nom or "export") or "export"
            dossier, projet = self.dossier_rangement(nom)
            base, ext = os.path.splitext(nom); f = os.path.join(dossier, nom); i = 2
            if nom.lower().endswith(".xiii.json"): base, ext = nom[:-10], ".xiii.json"
            while os.path.exists(f): f = os.path.join(dossier, "%s (%d)%s" % (base, i, ext)); i += 1
            d.set_destination(f); info[:] = [f, projet]; return True
        def fini(d):
            f, projet = info if info else (None, None)
            if f: self.notifier("Enregistré dans " + ("le projet « %s »" % projet if projet else "Téléchargements"), os.path.basename(f), os.path.dirname(f))
        dl.connect("decide-destination", destination)
        dl.connect("finished", fini)

    def notifier(self, titre, corps, dossier=None):
        n = Gio.Notification.new(titre); n.set_body(corps)
        n.set_icon(Gio.ThemedIcon.new("xiii-suite"))
        if dossier: n.set_default_action_and_target("app.ouvrir-dossier", GLib.Variant.new_string(dossier))
        self.send_notification(None, n)

    def do_activate(self):
        self.fenetre("index")

    # ------------------------------------------------------------- fichiers venant de l'OS
    @staticmethod
    def _dep(f):
        t = deposer(f); return {"t": t, "n": DEPOT[t][1], "m": DEPOT[t][2]}

    def injecter(self, oid, champ, fichiers, multiple=False):
        L = [self._dep(f) for f in fichiers if os.path.isfile(f)]
        if not L: return
        self.fenetre(oid, apres=JS_INJECTER % (json.dumps(L), json.dumps(champ), "true" if multiple else "false"))

    def vers_dossier(self, fichiers):
        L = [self._dep(f) for f in fichiers if os.path.isfile(f)]
        if not L: return
        w = self.fenetre("dossier", vue=self.nouvelle_vue())
        w._apres = JS_DOSSIER % (json.dumps(L), json.dumps(config.charger().get("projet_actif") or ""))
        w._vue.load_uri(self.base() + "/__xiii/vide.html")
        self.notifier("Envoyé à DOSSIER XIII", "%d document(s) ajouté(s) au dossier" % len(L))

    def ouvrir_fichier(self, f):
        try:
            o = json.load(open(f, encoding="utf-8"))
        except Exception:
            o = None
        if isinstance(o, dict) and o.get("format") == "os-xiii-reglages":
            Gio.Subprocess.new(["xiii-parametres", "--page", "xiii"], 0)
            return self.notifier("Réglages d'OS XIII", "Importez-les avec « Importer des réglages » dans Paramètres › Suite XIII.")
        if isinstance(o, dict) and o.get("format") == "xiii-link":
            kind = o.get("kind", "")
            if kind == "document": return self.vers_dossier([f])
            cibles = CIBLES.get(kind, [])
            extra = []
            if kind == "project":
                nom = (o.get("fiche") or {}).get("title") or (o.get("project") or {}).get("name")
                if nom: extra.append(("__projet", nom, "Activer « %s » comme projet XIII de l'ordinateur" % nom))
            if len(cibles) == 1 and not extra:
                return self.injecter(cibles[0][0], cibles[0][1], [f])
            return self.choisir(f, cibles, extra, "Fichier Suite XIII — %s" % (o.get("title") or (o.get("project") or {}).get("name") or os.path.basename(f)))
        # projet propre à un outil (.json) : l'outil d'après le nom, sinon au choix
        n = os.path.basename(f).lower()
        for oid in NOMS:
            if oid in n: return self.injecter(oid, "project-upload", [f])
        self.choisir(f, [(x["id"], "project-upload", x["nom"] + " — " + x["role"]) for x in outils() if x["id"] not in ("ludo",)], [], "Ouvrir « %s » avec…" % os.path.basename(f))

    def choisir(self, f, cibles, extra, titre):
        w = Gtk.Window(application=self, title=titre, default_width=520, modal=True)
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        lab = Gtk.Label(label=titre, xalign=0, wrap=True); lab.add_css_class("title-3"); b.append(lab)
        b.append(Gtk.Label(label="Ouvrir avec :", xalign=0))
        sc = Gtk.ScrolledWindow(vexpand=True, min_content_height=min(420, 56 * (len(cibles) + len(extra)) + 10), propagate_natural_height=True)
        lb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); sc.set_child(lb); b.append(sc)
        def bouton(texte, icone, fn):
            bt = Gtk.Button(); h = Gtk.Box(spacing=12)
            im = Gtk.Image.new_from_icon_name(icone); im.set_pixel_size(32); h.append(im); h.append(Gtk.Label(label=texte, xalign=0, wrap=True, hexpand=True))
            bt.set_child(h); bt.connect("clicked", lambda *_: (w.close(), fn())); lb.append(bt)
        for oid, champ, texte in cibles:
            bouton(texte, "xiii-suite-" + oid, lambda oid=oid, champ=champ: self.injecter(oid, champ, [f]))
        for _, nom, texte in extra:
            bouton(texte, "folder-kanban", lambda nom=nom: self.activer_projet(nom, f))
        bouton("Envoyer à DOSSIER XIII", "xiii-suite-dossier", lambda: self.vers_dossier([f]))
        an = Gtk.Button(label="Annuler"); an.connect("clicked", lambda *_: w.close()); b.append(an)
        w.set_child(b); w.present()

    def activer_projet(self, nom, f=None):
        nom = re.sub(r'[\\/:*?"<>|]', "-", nom).strip()
        d = os.path.join(os.path.expanduser("~/XIII"), nom)
        for x in SOUS: os.makedirs(os.path.join(d, x), exist_ok=True)
        if f and os.path.dirname(os.path.abspath(f)) != os.path.join(d, "03_Documents"):
            import shutil
            try: shutil.copy(f, os.path.join(d, "03_Documents", os.path.basename(f)))
            except OSError: pass
        config.modifier(projet_actif=nom)
        self.notifier("Projet XIII actif : " + nom, "Dossiers 01_Rushes → 07_Livraison prêts", d)


def main():
    app = Suite()
    act = Gio.SimpleAction.new("ouvrir-dossier", GLib.VariantType.new("s"))
    act.connect("activate", lambda a, p: Gio.AppInfo.launch_default_for_uri("file://" + urllib.parse.quote(p.get_string()), None))
    app.add_action(act)
    sys.exit(app.run(sys.argv))
