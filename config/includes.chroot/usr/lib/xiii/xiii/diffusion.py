# OS XIII — Diffuser l'écran : l'écran (ou une zone) est diffusé sur le réseau local et s'ouvre dans n'importe quel
# navigateur (TV connectée, téléphone, tablette, autre PC) par une adresse ou un QR code ; vers une TV Chromecast ou Miracast,
# l'appli « Écrans réseau » (gnome-network-displays) prend le relais.
# Moteur : wf-recorder (capture Wayland) en MJPEG, sinon grim image par image ; serveur HTTP en flux « multipart » (aucune
# appli à installer côté spectateur, quelques dixièmes de seconde de retard).
# Application développée par Matthieu Lamotte.
import os, sys, time, socket, shutil, subprocess, threading, http.server, socketserver

PORT = 8791

PAGE = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OS XIII — écran diffusé</title><style>
html,body{margin:0;height:100%;background:#0b0a09;color:#eee9e3;font-family:system-ui,sans-serif}
#e{width:100vw;height:100vh;object-fit:contain;display:block}
#b{position:fixed;top:12px;right:12px;display:flex;gap:8px;opacity:.85}
button{background:#f0b378;color:#1a1a1a;border:0;border-radius:999px;padding:8px 16px;font-weight:700;cursor:pointer}
#t{position:fixed;top:14px;left:16px;font-weight:700;letter-spacing:1px;color:#f0b378;opacity:.8}
</style></head><body><div id="t">XIII · %s</div>
<img id="e" src="/flux.mjpg" alt="Écran diffusé">
<div id="b"><button onclick="document.documentElement.requestFullscreen()">Plein écran</button></div>
<script>var e=document.getElementById('e');e.onerror=function(){setTimeout(function(){e.src='/flux.mjpg?'+Date.now()},1500)};</script>
</body></html>"""


def ip_locale():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Diffusion:
    """Capture + serveur. .image = dernière image JPEG, .spectateurs = nombre de navigateurs connectés."""
    def __init__(self, port=PORT, sortie=None, largeur=1280, ips=15, geometrie=None, nom="Écran"):
        self.port, self.sortie, self.largeur, self.ips, self.geometrie, self.nom = port, sortie, largeur, ips, geometrie, nom
        self.image = None; self.n = 0; self.spectateurs = 0; self.actif = False; self.moteur = ""
        self.cond = threading.Condition(); self.proc = None; self.httpd = None

    # ------------------------------------------------------------ serveur
    def demarrer(self):
        d = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def do_GET(self):
                if self.path.startswith("/flux.mjpg"): return self.flux()
                if self.path.startswith("/image.jpg"):
                    img = d.image or b""
                    self.send_response(200 if img else 503); self.send_header("Content-Type", "image/jpeg"); self.send_header("Content-Length", str(len(img)))
                    self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(img); return
                b = (PAGE % d.nom).encode()
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b)))
                self.end_headers(); self.wfile.write(b)

            def flux(self):
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=xiii"); self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close"); self.end_headers()
                with d.cond: d.spectateurs += 1
                vu = -1
                try:
                    while d.actif:
                        with d.cond:
                            if d.n == vu: d.cond.wait(2)
                            img, vu = d.image, d.n
                        if not img: continue
                        self.wfile.write(b"--xiii\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(img) + img + b"\r\n")
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    with d.cond: d.spectateurs -= 1

        class Serveur(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True; allow_reuse_address = True

        self.httpd = Serveur(("0.0.0.0", self.port), H)
        self.actif = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self.capturer, daemon=True).start()
        return "http://%s:%d/" % (ip_locale(), self.port)

    def arreter(self):
        self.actif = False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(3)
            except Exception: self.proc.kill()
        if self.httpd:
            threading.Thread(target=self.httpd.shutdown, daemon=True).start()
            try: self.httpd.server_close()
            except Exception: pass
        with self.cond: self.cond.notify_all()

    def publier(self, img):
        with self.cond:
            self.image = img; self.n += 1; self.cond.notify_all()

    # ------------------------------------------------------------ capture
    def capturer(self):
        if shutil.which("wf-recorder") and self.wf_recorder(): return
        self.grim()

    def wf_recorder(self):
        """Flux MJPEG de wf-recorder (images découpées sur les marqueurs JPEG). Faux si rien n'arrive en 4 s."""
        cmd = ["wf-recorder", "-y", "-c", "mjpeg", "-m", "mpjpeg", "-r", str(self.ips), "-x", "yuvj420p",
               "-F", "scale=%d:-2" % self.largeur, "-f", "/dev/stdout"]
        if self.sortie: cmd += ["-o", self.sortie]
        if self.geometrie: cmd += ["-g", self.geometrie]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        except OSError:
            return False
        self.moteur = "wf-recorder"; t0 = time.time(); buf = b""; recu = False
        fd = self.proc.stdout
        while self.actif:
            ch = fd.read1(65536) if hasattr(fd, "read1") else fd.read(65536)
            if not ch:
                break
            buf += ch
            while True:
                s = buf.find(b"\xff\xd8")
                e = buf.find(b"\xff\xd9", s + 2) if s >= 0 else -1
                if s < 0 or e < 0:
                    buf = buf[s:] if s >= 0 else buf[-1:]
                    break
                self.publier(buf[s:e + 2]); buf = buf[e + 2:]; recu = True
            if len(buf) > 8 << 20: buf = b""
            if not recu and time.time() - t0 > 4: break
        if self.proc.poll() is None and not self.actif: self.proc.terminate()
        if not recu:
            try: self.proc.kill()
            except Exception: pass
        return recu

    def grim(self):
        """Repli : une capture grim toutes les 1/ips s (plus lent, mais marche partout où grim marche)."""
        self.moteur = "grim"
        pause = 1 / max(2, min(self.ips, 10))
        while self.actif:
            t = time.time()
            cmd = ["grim", "-t", "jpeg", "-q", "70", "-s", "0.66"]
            if self.sortie: cmd += ["-o", self.sortie]
            if self.geometrie: cmd += ["-g", self.geometrie]
            try:
                img = subprocess.run(cmd + ["-"], capture_output=True, timeout=5).stdout
                if img.startswith(b"\xff\xd8"): self.publier(img)
            except Exception:
                time.sleep(1)
            time.sleep(max(0, pause - (time.time() - t)))


def main():
    """xiii-diffuser [--serveur [--duree N] [--sortie NOM]] : sans option, l'appli ; --serveur : diffusion seule (vérifications)."""
    if "--serveur" in sys.argv:
        duree = float(sys.argv[sys.argv.index("--duree") + 1]) if "--duree" in sys.argv else 0
        sortie = sys.argv[sys.argv.index("--sortie") + 1] if "--sortie" in sys.argv else None
        d = Diffusion(sortie=sortie); print(d.demarrer(), flush=True)
        t0 = time.time()
        try:
            while not duree or time.time() - t0 < duree:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        print("moteur", d.moteur, "images", d.n, flush=True); d.arreter(); return
    from .diffuser import main as appli
    appli()
