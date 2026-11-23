# OS XIII — Transferts XIII : envoyer des fichiers, une seule interface.
# • Lien de téléchargement : Gofile (envoi direct, sans compte), WeTransfer et Smash (site ouvert, fichiers prêts à glisser)
# • Réseau local : partage d'un dossier par lien + QR code (téléchargement et dépôt depuis un téléphone ou un PC)
# • D'appareil à appareil (open source) : croc et Magic Wormhole (code à dicter), PairDrop / LocalSend
# Application développée par Matthieu Lamotte.
import os, sys, json, re, socket, secrets, shutil, subprocess, threading, mimetypes, http.client, urllib.parse, html, zipfile, io, time
# icône de dossier au trait (comme les icônes Lucide de l'OS) pour la page de partage ouverte sur les téléphones
DOSSIER_SVG = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f0b378" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
               'style="vertical-align:-3px;margin-right:8px"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>')
import http.server, socketserver
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf
from . import config, systeme as S, netscan as N
from .ui import *
from .appli import preparer, Volet, page

HISTO = os.path.expanduser("~/.local/share/xiii/transferts.json")

def histo():
    try: return json.load(open(HISTO))
    except Exception: return []

def noter(e):
    os.makedirs(os.path.dirname(HISTO), exist_ok=True); json.dump(([e] + histo())[:50], open(HISTO, "w"), ensure_ascii=False)

def qr(texte, taille=220):
    """QR code (qrencode) → Gtk.Picture."""
    try:
        png = subprocess.run(["qrencode", "-o", "-", "-s", "8", "-m", "2", texte], capture_output=True, timeout=5).stdout
        l = GdkPixbuf.PixbufLoader(); l.write(png); l.close()
        p = Gtk.Picture.new_for_pixbuf(l.get_pixbuf()); p.set_size_request(taille, taille); p.set_can_shrink(True); return p
    except Exception:
        return label(texte, "petit")

# ---------------------------------------------------------------------------- Gofile
def envoyer_gofile(fichiers, progres):
    total = sum(os.path.getsize(f) for f in fichiers) or 1; fait = [0]; dossier = jeton = None; page_ = None
    for f in fichiers:
        limite = "----XIII" + secrets.token_hex(12)
        tete = ""
        if dossier: tete += '--%s\r\nContent-Disposition: form-data; name="folderId"\r\n\r\n%s\r\n' % (limite, dossier)
        tete += '--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (
            limite, os.path.basename(f).replace('"', "'"), mimetypes.guess_type(f)[0] or "application/octet-stream")
        fin = "\r\n--%s--\r\n" % limite
        t = os.path.getsize(f)
        c = http.client.HTTPSConnection("upload.gofile.io", timeout=120)
        c.putrequest("POST", "/uploadfile")
        c.putheader("Content-Type", "multipart/form-data; boundary=" + limite)
        c.putheader("Content-Length", str(len(tete.encode()) + t + len(fin.encode())))
        c.putheader("User-Agent", "OS-XIII")
        if jeton: c.putheader("Authorization", "Bearer " + jeton)
        c.endheaders(); c.send(tete.encode())
        with open(f, "rb") as h:
            while True:
                b = h.read(1 << 20)
                if not b: break
                c.send(b); fait[0] += len(b); progres(fait[0] / total, os.path.basename(f))
        c.send(fin.encode())
        r = json.loads(c.getresponse().read().decode("utf-8", "replace"))
        if r.get("status") != "ok": raise RuntimeError(r.get("status") or "refusé")
        d = r["data"]; dossier = dossier or d.get("parentFolder"); jeton = jeton or d.get("guestToken"); page_ = page_ or d.get("downloadPage")
    return page_

# ---------------------------------------------------------------------------- partage local
class Partage:
    """Serveur HTTP de partage d'un dossier sur le réseau local (téléchargement + dépôt)."""
    def __init__(self, dossier, depot=True):
        self.dossier = dossier; self.cle = secrets.token_urlsafe(6); self.depot = depot
        moi = self
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def ok(self):
                return self.path.split("?")[0].split("/")[1:2] == [moi.cle]
            def do_GET(self):
                if not self.ok(): self.send_error(404); return
                rel = urllib.parse.unquote(self.path.split("?")[0][len(moi.cle) + 2:])
                p = os.path.realpath(os.path.join(moi.dossier, rel))
                if not p.startswith(os.path.realpath(moi.dossier)): self.send_error(403); return
                if "?zip" in self.path and os.path.isdir(p):
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
                        for r, _, fs in os.walk(p):
                            for f in fs: z.write(os.path.join(r, f), os.path.relpath(os.path.join(r, f), p))
                    d = buf.getvalue(); self.send_response(200); self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Disposition", 'attachment; filename="%s.zip"' % os.path.basename(p)); self.send_header("Content-Length", len(d)); self.end_headers(); self.wfile.write(d); return
                if os.path.isdir(p):
                    L = sorted(os.listdir(p), key=lambda x: (not os.path.isdir(os.path.join(p, x)), x.lower()))
                    lignes = "".join('<a class="f" href="%s%s">%s<span>%s</span></a>' % (urllib.parse.quote(x), "/" if os.path.isdir(os.path.join(p, x)) else "",
                                     (DOSSIER_SVG if os.path.isdir(os.path.join(p, x)) else "") + html.escape(x), "" if os.path.isdir(os.path.join(p, x)) else S.humain(os.path.getsize(os.path.join(p, x))))
                                     for x in L if not x.startswith("."))
                    depot = ('<form method="post" enctype="multipart/form-data"><input type="file" name="f" multiple required><button>Déposer</button></form>' if moi.depot else "")
                    page_ = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><title>Partage XIII</title>"
                             "<style>body{font:16px system-ui;background:#141210;color:#eee9e3;margin:0;padding:18px}h1{color:#f0b378;font-weight:400;letter-spacing:.1em}"
                             "a.f{display:flex;justify-content:space-between;padding:12px 14px;border-radius:10px;background:#201d1a;margin:6px 0;color:#eee9e3;text-decoration:none}"
                             "a.f span{opacity:.6}.z{display:inline-block;margin:6px 0 14px;color:#141210;background:#f0b378;padding:10px 16px;border-radius:999px;text-decoration:none}"
                             "form{margin-top:18px;padding:14px;border:1px dashed #f0b378;border-radius:12px}button{background:#f0b378;border:0;border-radius:999px;padding:8px 16px;margin-left:8px}</style>"
                             "<h1>XIII · %s</h1><a class=z href='?zip'>Tout télécharger (.zip)</a>%s%s<p style='opacity:.5;font-size:12px'>Partagé depuis OS XIII</p>") % (html.escape(os.path.basename(p) or "Partage"), lignes, depot)
                    d = page_.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", len(d)); self.end_headers(); self.wfile.write(d); return
                if not os.path.isfile(p): self.send_error(404); return
                self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(p)[0] or "application/octet-stream")
                self.send_header("Content-Length", os.path.getsize(p)); self.send_header("Content-Disposition", 'attachment; filename="%s"' % os.path.basename(p).replace('"', "'")); self.end_headers()
                with open(p, "rb") as f: shutil.copyfileobj(f, self.wfile, 1 << 20)
            def do_POST(self):
                if not self.ok() or not moi.depot: self.send_error(403); return
                import email.parser, email.policy
                n = int(self.headers.get("Content-Length", 0))
                if n > 2 * 1024 ** 3: self.send_error(413); return
                corps = self.rfile.read(n)
                msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + corps)
                dest = os.path.join(moi.dossier, "Reçus"); os.makedirs(dest, exist_ok=True); k = 0
                for part in msg.iter_parts():
                    fn = part.get_filename()
                    if fn:
                        fn = os.path.basename(fn); open(os.path.join(dest, fn), "wb").write(part.get_payload(decode=True)); k += 1
                S.detacher(["notify-send", "-a", "Transferts", "-i", "folder-download", "%d fichier(s) reçu(s)" % k, dest])
                self.send_response(303); self.send_header("Location", self.path); self.end_headers()
        class Srv(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True; allow_reuse_address = True
        self.srv = None
        for port in range(8800, 8820):
            try: self.srv = Srv(("0.0.0.0", port), H); self.port = port; break
            except OSError: continue
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def urls(self):
        L = []
        for dev, cidr in N.interfaces_reseau(): L.append("http://%s:%d/%s/" % (cidr.split("/")[0], self.port, self.cle))
        return L or ["http://%s:%d/%s/" % (socket.gethostname(), self.port, self.cle)]

    def arreter(self): self.srv.shutdown(); self.srv.server_close()


class Transferts(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.transferts", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.fichiers = []; self.partages = []; self.procs = []

    def do_command_line(self, cl):
        a = [x for x in cl.get_arguments()[1:] if not x.startswith("--")]
        cwd = cl.get_cwd() or os.path.expanduser("~")
        self.activer()
        if a:
            self.fichiers = [x if os.path.isabs(x) else os.path.join(cwd, x) for x in a]
            self.volet.aller("local" if "--local" in cl.get_arguments() else "lien")
        return 0

    def activer(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".zone-depot { border: 2px dashed alpha(@accent_bg_color, .6); border-radius: 16px; padding: 26px; } .zone-depot.survol { background: alpha(@accent_bg_color, .12); }"
                 ".service { padding: 12px; } .service.choisi { background: alpha(@accent_bg_color, .2); border-color: @accent_bg_color; }"
                 ".code-geant { font-family: 'IBM Plex Mono', monospace; font-size: 26px; font-weight: 700; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Transferts XIII"); self.win.set_default_size(1000, 700)
        self.volet = Volet("Transferts", "Envoyer des fichiers, par lien, sur le réseau local ou d'appareil à appareil")
        self.volet.ajouter("lien", "link", "Lien de téléchargement", rappel=self.p_lien)
        self.volet.ajouter("local", "wifi", "Réseau local", rappel=self.p_local)
        self.volet.ajouter("p2p", "arrow-left-right", "D'appareil à appareil", rappel=self.p_p2p)
        self.volet.ajouter("histo", "history", "Historique", rappel=self.p_histo)
        self.win.set_child(self.volet.racine); self.volet.aller("lien"); self.win.present()
        self.win.connect("close-request", lambda *_: ([p.arreter() for p in self.partages], [x.terminate() for x in self.procs if x.poll() is None], False)[2])

    def remplacer(self, cle, w):
        v = self.volet.pile.get_child_by_name(cle)
        if v: self.volet.pile.remove(v)
        self.volet.pile.add_named(w, cle); self.volet.pile.set_visible_child_name(cle)

    def zone_fichiers(self, rappel, dossier=False):
        z = boite(True, 8, "zone-depot", halign=Gtk.Align.FILL)
        z.append(ico("upload", 36, "c")); z.append(label("Glissez des fichiers ici", "gras", xalign=0.5))
        lb = label(self.resume_fichiers(), "petit", "attenue", xalign=0.5, wrap=True); z.append(lb)
        def choisir():
            d = Gtk.FileDialog(title="Choisir")
            def fin(dlg, res):
                try:
                    if dossier: self.fichiers = [dlg.select_folder_finish(res).get_path()]
                    else: self.fichiers = [f.get_path() for f in dlg.open_multiple_finish(res)]
                except Exception: return
                lb.set_text(self.resume_fichiers()); rappel()
            (d.select_folder if dossier else d.open_multiple)(self.win, None, fin)
        z.append(bouton("Choisir un dossier…" if dossier else "Choisir des fichiers…", "folder-open", "fantome", rappel=choisir))
        dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        dt.connect("drop", lambda t, v, x, y: (setattr(self, "fichiers", [f.get_path() for f in v.get_files() if f.get_path()]), lb.set_text(self.resume_fichiers()), rappel(), True)[3])
        dt.connect("enter", lambda *_: (z.add_css_class("survol"), Gdk.DragAction.COPY)[1]); dt.connect("leave", lambda *_: z.remove_css_class("survol"))
        z.add_controller(dt)
        return z

    def resume_fichiers(self):
        if not self.fichiers: return "Aucun fichier choisi"
        t = sum(os.path.getsize(f) if os.path.isfile(f) else 0 for f in self.fichiers)
        return "%d élément(s) · %s — %s" % (len(self.fichiers), S.humain(t), ", ".join(os.path.basename(f) for f in self.fichiers[:3]) + ("…" if len(self.fichiers) > 3 else ""))

    # --------------------------------------------------------------- lien
    def p_lien(self):
        sc, v = page("Lien de téléchargement", "Le destinataire reçoit un lien, sans rien installer", "link")
        v.append(self.zone_fichiers(lambda: None))
        etat = {"service": "gofile"}
        g = boite(False, 10, homogeneous=True)
        cartes = {}
        for k, n, d in (("gofile", "Gofile", "Envoi direct depuis OS XIII, gratuit, sans compte, taille illimitée"),
                        ("wetransfer", "WeTransfer", "Ouvre WeTransfer : les fichiers sont prêts à glisser dans la page (3 Go gratuits)"),
                        ("smash", "Smash", "Ouvre Smash (France) : fichiers prêts à glisser, sans limite de taille")):
            b = Gtk.Button(); b.add_css_class("carte"); b.add_css_class("service")
            bx = boite(True, 4); bx.append(label(n, "gras")); bx.append(label(d, "petit", "attenue", wrap=True)); b.set_child(bx); cartes[k] = b
            b.connect("clicked", lambda _b, k=k: (etat.__setitem__("service", k), [c.remove_css_class("choisi") for c in cartes.values()], cartes[k].add_css_class("choisi")))
            g.append(b)
        cartes["gofile"].add_css_class("choisi"); v.append(g)
        pb = Gtk.ProgressBar(show_text=True); pb.set_visible(False); v.append(pb)
        res = boite(False, 16); v.append(res)
        def envoyer():
            fs = [f for f in self.fichiers if os.path.isfile(f)]
            dossiers = [f for f in self.fichiers if os.path.isdir(f)]
            for d in dossiers:                       # un dossier part en .zip
                z = os.path.join(GLib.get_tmp_dir(), os.path.basename(d.rstrip("/")) + ".zip"); shutil.make_archive(z[:-4], "zip", d); fs.append(z)
            if not fs: self.toast("Choisissez d'abord des fichiers"); return
            if etat["service"] in ("wetransfer", "smash"):
                S.detacher(["xdg-open", "https://wetransfer.com/" if etat["service"] == "wetransfer" else "https://fromsmash.com/"])
                S.detacher(["thunar", os.path.dirname(fs[0])])
                self.toast("Glissez vos fichiers depuis Fichiers vers la page qui vient de s'ouvrir"); return
            pb.set_visible(True); pb.set_fraction(0); vider(res)
            def prog(fr, nom): GLib.idle_add(lambda: (pb.set_fraction(fr), pb.set_text("%d %% · %s" % (fr * 100, nom)), False)[2])
            def fin(r):
                if isinstance(r, Exception) or not r: pb.set_text("Échec de l'envoi : %s" % r); return
                pb.set_text("Envoyé ✓"); self.afficher_lien(res, r, "Gofile")
                noter({"date": time.strftime("%Y-%m-%d %H:%M"), "service": "Gofile", "lien": r, "fichiers": [os.path.basename(f) for f in fs]})
            S.en_fond(lambda: envoyer_gofile(fs, prog), fin)
        v.append(bouton("Envoyer", "send", "pilule", rappel=envoyer))
        self.remplacer("lien", sc)

    def afficher_lien(self, zone, url, service):
        vider(zone); zone.append(qr(url, 160))
        col = boite(True, 6, valign=Gtk.Align.CENTER, hexpand=True)
        col.append(label("Lien %s" % service, "gras")); e = Gtk.Entry(text=url, editable=False); col.append(e)
        r = boite(False, 6)
        r.append(bouton("Copier le lien", "copy", "pilule", rappel=lambda: (Gdk.Display.get_default().get_clipboard().set_text(url), self.toast("Lien copié"))))
        r.append(bouton("Ouvrir", "external-link", "fantome", rappel=lambda: S.detacher(["xdg-open", url])))
        r.append(bouton("Par e-mail", "mail", "fantome", rappel=lambda: S.detacher(["xdg-open", "mailto:?subject=Fichiers&body=" + urllib.parse.quote(url)])))
        col.append(r); zone.append(col)

    def toast(self, t): S.detacher(["notify-send", "-a", "Transferts XIII", "-i", "folder-remote", t])

    # --------------------------------------------------------------- local
    def p_local(self):
        sc, v = page("Réseau local", "Partagez un dossier : les appareils du même réseau l'ouvrent avec le lien ou le QR code, et peuvent y déposer des fichiers", "wifi")
        v.append(self.zone_fichiers(lambda: None, dossier=True))
        depot = Gtk.CheckButton(label="Autoriser le dépôt de fichiers (dans un sous-dossier « Reçus »)", active=True); v.append(depot)
        zone = boite(True, 12); v.append(zone)
        def partager():
            d = next((f for f in self.fichiers if os.path.isdir(f)), None)
            if not d: self.toast("Choisissez un dossier à partager"); return
            p = Partage(d, depot.get_active()); self.partages.append(p); self.p_local()
        v.append(bouton("Partager ce dossier", "share-2", "pilule", rappel=partager))
        for p in self.partages:
            c = boite(False, 16, "carte"); u = p.urls()[0]; c.append(qr(u, 150))
            col = boite(True, 4, hexpand=True, valign=Gtk.Align.CENTER)
            col.append(label(os.path.basename(p.dossier), "gras")); col.append(label(p.dossier.replace(os.path.expanduser("~"), "~"), "petit", "attenue"))
            for x in p.urls(): col.append(Gtk.Entry(text=x, editable=False))
            col.append(label("Le lien contient une clé secrète : seuls ceux qui l'ont peuvent ouvrir le partage.", "petit", "attenue", wrap=True))
            r = boite(False, 6); r.append(bouton("Copier", "copy", "fantome", rappel=lambda u=u: Gdk.Display.get_default().get_clipboard().set_text(u)))
            r.append(bouton("Arrêter le partage", "square", "plat", "danger", rappel=lambda p=p: (p.arreter(), self.partages.remove(p), self.p_local()))); col.append(r)
            c.append(col); zone.append(c)
        self.remplacer("local", sc)

    # --------------------------------------------------------------- appareil à appareil
    def p_p2p(self):
        sc, v = page("D'appareil à appareil", "Outils libres et chiffrés de bout en bout : un code suffit, n'importe où dans le monde", "arrow-left-right")
        v.append(self.zone_fichiers(lambda: None))
        out = boite(True, 8); v.append(out)
        def croc_envoyer(outil):
            fs = self.fichiers
            if not fs: self.toast("Choisissez d'abord des fichiers"); return
            cmd = ["croc", "--yes", "send"] + fs if outil == "croc" else ["wormhole", "send"] + fs[:1]
            if not shutil.which(cmd[0]): self.toast(cmd[0] + " n'est pas installé"); return
            vider(out); l = label("Préparation…", "attenue"); out.append(l)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=dict(os.environ, CROC_SECRET="")); self.procs.append(p)
            def lire():
                for ligne in p.stdout:
                    m = re.search(r"Code is: (\S+)|code is: (\S+)|Wormhole code is: (\S+)", ligne)
                    if m:
                        code = next(x for x in m.groups() if x)
                        GLib.idle_add(lambda code=code: (vider(out), out.append(label("Code à donner au destinataire", "gras")), out.append(label(code, "code-geant", "accent", selectable=True)),
                                                         out.append(label(("Il tape : croc %s" if outil == "croc" else "Il tape : wormhole receive %s") % code, "petit", "attenue")),
                                                         out.append(bouton("Copier le code", "copy", "fantome", rappel=lambda: Gdk.Display.get_default().get_clipboard().set_text(code))), False)[-1])
                    elif "100%" in ligne or "Sending" in ligne:
                        GLib.idle_add(lambda t=ligne.strip()[-80:]: (out.append(label(t, "petit", "attenue")) if out.get_last_child() is None or True else None, False)[1])
                p.wait(); GLib.idle_add(lambda: (out.append(label("Transfert terminé ✓" if p.returncode == 0 else "Transfert interrompu", "gras")), False)[1])
            threading.Thread(target=lire, daemon=True).start()
        r = boite(False, 8)
        r.append(bouton("Envoyer avec croc", "send", "pilule", rappel=lambda: croc_envoyer("croc")))
        r.append(bouton("Envoyer avec Magic Wormhole", "send", "fantome", rappel=lambda: croc_envoyer("wormhole")))
        v.append(r)
        v.append(groupe_titre_l("Recevoir"))
        e = Gtk.Entry(placeholder_text="Code reçu (ex. 1234-mot-mot-mot)", hexpand=True)
        def recevoir():
            code = e.get_text().strip()
            if not code: return
            dest = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or os.path.expanduser("~")
            outil = "wormhole" if re.match(r"^\d+-\w+-\w+$", code) and not shutil.which("croc") else "croc"
            cmd = ["croc", "--yes", "--overwrite", "--out", dest] if outil == "croc" else ["wormhole", "receive", "--accept-file", "-o", dest, code]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=dict(os.environ, CROC_SECRET=code) if outil == "croc" else None); self.procs.append(p)
            S.en_fond(p.wait, lambda r: self.toast(("Fichiers reçus dans " + dest) if r == 0 else "Réception impossible (code ?)"))
        rr = boite(False, 8); rr.append(e); rr.append(bouton("Recevoir", "download", "pilule", rappel=recevoir)); v.append(rr)
        v.append(groupe_titre_l("Dans le navigateur"))
        v.append(bouton("PairDrop (comme AirDrop, entre appareils du réseau)", "smartphone", "fantome", rappel=lambda: S.detacher(["xdg-open", "https://pairdrop.net/"])))
        v.append(bouton("Envoi XIII (appareils proches)", "send", "pilule", rappel=lambda: S.detacher(["xiii-envoi"])))
        if shutil.which("localsend") or shutil.which("localsend_app"):
            v.append(bouton("LocalSend", "smartphone", "fantome", rappel=lambda: S.detacher([shutil.which("localsend") or "localsend_app"])))
        self.remplacer("p2p", sc)

    def p_histo(self):
        sc, v = page("Historique", "Les liens que vous avez envoyés", "history")
        L = histo()
        if not L: v.append(label("Aucun envoi pour l'instant.", "attenue"))
        for e in L:
            r = boite(False, 10, "reglage"); r.append(ico("link", 18, "c"))
            col = boite(True, 0, hexpand=True); col.append(label(", ".join(e.get("fichiers", []))[:90], "gras", ellipsize=True))
            col.append(label("%s · %s · %s" % (e["date"], e["service"], e["lien"]), "petit", "attenue", ellipsize=True)); r.append(col)
            r.append(bouton(None, "copy", "plat", tip="Copier", rappel=lambda u=e["lien"]: Gdk.Display.get_default().get_clipboard().set_text(u)))
            v.append(r)
        self.remplacer("histo", sc)

def groupe_titre_l(t): return label(t, "section", margin_top=10)

def main():
    sys.exit(Transferts().run(sys.argv))
