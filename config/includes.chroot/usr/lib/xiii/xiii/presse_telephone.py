# OS XIII — Presse-papiers partagé avec le téléphone (comme le presse-papiers universel d'Apple ou « Lien avec le téléphone »).
# Sans appli à installer : le téléphone scanne un QR code et ouvre une page web servie par ce PC (même Wi-Fi).
#   PC → téléphone : la page montre ce qui est copié sur le PC (texte, image), mis à jour toutes les 2 s.
#   Téléphone → PC : coller un texte ou envoyer une photo, c'est aussitôt dans le presse-papiers du PC (Ctrl + V).
# Une clé secrète est dans l'adresse ; le partage s'arrête quand on ferme la fenêtre.
#   xiii-presse-telephone            fenêtre avec le QR code
# Application développée par Matthieu Lamotte.
import os, sys, json, time, secrets, threading, subprocess, http.server, socketserver, urllib.parse, html
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

PORT = 8742
RECUS = os.path.join(os.path.expanduser("~"), "Images", "Du téléphone")
TYPES_IMG = ("image/png", "image/jpeg", "image/webp", "image/gif", "image/heic")


def ip_locale():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except OSError: return "127.0.0.1"
    finally: s.close()


def lire_pc():
    """(texte, type d'image ou None) du presse-papiers du PC."""
    try: types = subprocess.run(["wl-paste", "--list-types"], capture_output=True, text=True, timeout=2).stdout.split()
    except Exception: types = []
    img = next((t for t in TYPES_IMG if t in types), None)
    txt = ""
    if any(t.startswith("text/") or t in ("UTF8_STRING", "STRING", "TEXT") for t in types):
        try: txt = subprocess.run(["wl-paste", "--no-newline", "--type", "text"], capture_output=True, text=True, timeout=2).stdout[:20000]
        except Exception: pass
    return txt, img


def historique(n=8):
    try:
        L = subprocess.run(["cliphist", "list"], capture_output=True, text=True, timeout=2).stdout.splitlines()
        return [l.split("\t", 1)[1] for l in L if "\t" in l and not l.split("\t", 1)[1].startswith("[[ binary")][:n]
    except Exception:
        return []


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Presse-papiers · {NOM}</title><style>
:root{color-scheme:dark}body{margin:0;font:16px/1.4 system-ui,sans-serif;background:#161412;color:#eee9e3}
header{padding:18px 18px 6px;display:flex;gap:10px;align-items:center}header b{color:#f0b378;font-size:20px}header span{opacity:.6;font-size:13px}
section{margin:12px;padding:14px;border-radius:18px;background:#221f1c}h2{margin:0 0 8px;font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:#9b938a}
#pc{white-space:pre-wrap;word-break:break-word;min-height:2em;user-select:all}#img img{max-width:100%;border-radius:12px;margin-top:8px}
textarea{width:100%;box-sizing:border-box;min-height:90px;border-radius:12px;border:1px solid #3a352f;background:#161412;color:inherit;padding:10px;font:inherit}
button,label.b{display:inline-block;margin-top:10px;padding:11px 18px;border-radius:99px;border:0;background:#f0b378;color:#1c1a18;font-weight:700;font-size:15px}
button.f{background:#3a352f;color:#eee9e3}ul{list-style:none;padding:0;margin:0}li{padding:9px 0;border-top:1px solid #322d28;display:flex;gap:8px;align-items:center}
li span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}#ok{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#f0b378;color:#1c1a18;padding:9px 16px;border-radius:99px;display:none;font-weight:700}
input[type=file]{display:none}</style></head><body>
<header><b>XIII</b><span>Presse-papiers partagé avec {NOM}</span></header>
<section><h2>Copié sur le PC</h2><div id="pc">…</div><div id="img"></div><button onclick="copier(document.getElementById('pc').textContent)">Copier sur ce téléphone</button></section>
<section><h2>Envoyer au PC</h2><textarea id="t" placeholder="Collez ou tapez ici…"></textarea>
<button onclick="envoyer()">Envoyer au presse-papiers du PC</button> <label class="b f" for="f">Photo / image</label><input id="f" type="file" accept="image/*" onchange="photo(this)"></section>
<section><h2>Récemment copié sur le PC</h2><ul id="h"></ul></section><div id="ok"></div>
<script>
const K=new URLSearchParams(location.search).get("k");let dernier="";
function ok(m){const o=document.getElementById("ok");o.textContent=m;o.style.display="block";setTimeout(()=>o.style.display="none",1800)}
function copier(t){if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(()=>ok("Copié"));return}
 const a=document.createElement("textarea");a.value=t;document.body.appendChild(a);a.select();try{document.execCommand("copy");ok("Copié")}catch(e){ok("Sélectionnez le texte pour le copier")}a.remove()}
async function etat(){try{const r=await fetch("/etat?k="+K);if(!r.ok)return;const d=await r.json();
 if(d.texte!==dernier){dernier=d.texte;document.getElementById("pc").textContent=d.texte||"(rien de copié)"}
 document.getElementById("img").innerHTML=d.image?'<img src="/image-pc?k='+K+'&t='+d.n+'" alt="">':"";
 const h=document.getElementById("h");h.innerHTML="";for(const x of d.historique){const li=document.createElement("li");const s=document.createElement("span");s.textContent=x;
 const b=document.createElement("button");b.className="f";b.textContent="Copier";b.style.margin=0;b.onclick=()=>copier(x);li.append(s,b);h.append(li)}}catch(e){}}
async function envoyer(){const t=document.getElementById("t").value;if(!t)return;const r=await fetch("/envoyer?k="+K,{method:"POST",body:t});
 if(r.ok){ok("Dans le presse-papiers du PC");document.getElementById("t").value=""}}
async function photo(i){const f=i.files[0];if(!f)return;ok("Envoi…");const r=await fetch("/image?k="+K,{method:"POST",headers:{"Content-Type":f.type||"image/jpeg","X-Nom":encodeURIComponent(f.name)},body:f});
 if(r.ok)ok("Image copiée sur le PC");i.value=""}
etat();setInterval(etat,2000);
</script></body></html>"""


class Serveur:
    def __init__(self, port=PORT, nom="ce PC", rappel=lambda m: None):
        self.port, self.nom, self.rappel = port, nom, rappel
        self.cle = secrets.token_urlsafe(9); self.httpd = None; self.vu = 0; self.n = 0

    def url(self): return "http://%s:%d/?k=%s" % (ip_locale(), self.port, self.cle)

    def demarrer(self):
        sv = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def autorise(self):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if q.get("k", [""])[0] != sv.cle:
                    self.send_error(403, "Clé incorrecte"); return False
                sv.vu = time.time(); return True

            def repondre(self, corps, typ="application/json; charset=utf-8", code=200):
                self.send_response(code); self.send_header("Content-Type", typ); self.send_header("Content-Length", str(len(corps)))
                self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(corps)

            def do_GET(self):
                if not self.autorise(): return
                ch = urllib.parse.urlparse(self.path).path
                if ch == "/etat":
                    t, img = lire_pc()
                    if (t, img) != getattr(sv, "_der", None): sv._der = (t, img); sv.n += 1
                    return self.repondre(json.dumps({"texte": t, "image": bool(img), "n": sv.n, "historique": historique()}, ensure_ascii=False).encode())
                if ch == "/image-pc":
                    _t, img = lire_pc()
                    d = subprocess.run(["wl-paste", "--type", img], capture_output=True, timeout=5).stdout if img else b""
                    return self.repondre(d, img or "application/octet-stream", 200 if d else 404)
                self.repondre(PAGE.replace("{NOM}", html.escape(sv.nom)).encode(), "text/html; charset=utf-8")

            def do_POST(self):
                if not self.autorise(): return
                ch = urllib.parse.urlparse(self.path).path
                n = int(self.headers.get("Content-Length") or 0)
                if n > 40 * 1024 * 1024: return self.send_error(413)
                corps = self.rfile.read(n)
                if ch == "/envoyer":
                    t = corps.decode("utf-8", "replace")
                    subprocess.run(["wl-copy"], input=t.encode(), timeout=5)
                    sv.rappel("Texte reçu du téléphone : " + t[:80]); return self.repondre(b"{}")
                if ch == "/image":
                    typ = self.headers.get("Content-Type", "image/jpeg").split(";")[0]
                    if typ not in TYPES_IMG: typ = "image/jpeg"
                    os.makedirs(RECUS, exist_ok=True)
                    nom = os.path.basename(urllib.parse.unquote(self.headers.get("X-Nom", ""))) or "photo.jpg"
                    f = os.path.join(RECUS, time.strftime("%Y-%m-%d %H%M%S ") + nom)
                    open(f, "wb").write(corps)
                    subprocess.run(["wl-copy", "--type", typ], input=corps, timeout=10)
                    sv.rappel("Image reçue du téléphone (copiée, et rangée dans Images › Du téléphone)"); return self.repondre(b"{}")
                self.send_error(404)

        class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True; allow_reuse_address = True

        for p in range(self.port, self.port + 10):
            try: self.httpd = S(("0.0.0.0", p), H); self.port = p; break
            except OSError: continue
        if not self.httpd: raise OSError("aucun port libre")
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def arreter(self):
        if self.httpd: self.httpd.shutdown(); self.httpd.server_close(); self.httpd = None


class App(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.presse-telephone")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        from .ui import boite, label, bouton, ico
        from .appli import preparer
        preparer(".qr-cadre { background: white; border-radius: 18px; padding: 12px; }")
        import socket
        def notif(m): subprocess.Popen(["notify-send", "-a", "Presse-papiers", "-i", "smartphone", "-t", "3000", m], stderr=subprocess.DEVNULL)
        self.sv = Serveur(nom=socket.gethostname(), rappel=lambda m: GLib.idle_add(lambda: (self.etat.set_text(m), notif(m), False)[2]))
        w = Gtk.ApplicationWindow(application=self, title="Presse-papiers partagé"); w.set_default_size(460, -1); self.win = w
        v = boite(True, 12, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        h = boite(False, 10); h.append(ico("smartphone", 26, "c")); h.append(label("Presse-papiers avec le téléphone", "page-titre")); v.append(h)
        v.append(label("Scannez ce code avec l'appareil photo du téléphone (même Wi-Fi). Copier sur l'un, coller sur l'autre — sans appli à installer.", "attenue", wrap=True))
        try: self.sv.demarrer(); url = self.sv.url()
        except Exception as e: url = None; v.append(label("Impossible de démarrer le partage : %s" % e, wrap=True))
        if url:
            png = subprocess.run(["qrencode", "-o", "-", "-s", "8", "-m", "1", url], capture_output=True).stdout
            cadre = boite(True, 0, "qr-cadre", halign=Gtk.Align.CENTER)
            if png:
                l = GdkPixbuf.PixbufLoader(); l.write(png); l.close()
                pic = Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(l.get_pixbuf())); pic.set_size_request(240, 240); cadre.append(pic)
            v.append(cadre)
            e = Gtk.Entry(text=url, editable=False); v.append(e)
            v.append(label("Si le téléphone n'arrive pas à se connecter : Paramètres › Pare-feu › autoriser le port %d." % self.sv.port, "attenue", "petit", wrap=True))
        self.etat = label("En attente du téléphone…", "petit", wrap=True); v.append(self.etat)
        r = boite(False, 8, halign=Gtk.Align.END); r.append(bouton("Arrêter le partage", "x", "fantome", rappel=w.close)); v.append(r)
        w.set_child(v); w.present()
        w.connect("close-request", lambda *_: (self.sv.arreter(), False)[1])
        GLib.timeout_add_seconds(2, self.surveiller)

    def surveiller(self):
        if not self.sv.httpd: return False
        if self.sv.vu and time.time() - self.sv.vu < 5 and self.etat.get_text().startswith("En attente"): self.etat.set_text("Téléphone connecté ✓")
        return True


def main():
    sys.exit(App().run(sys.argv[:1]))
