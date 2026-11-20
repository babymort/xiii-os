# OS XIII — QR Wi-Fi XIII : choisir un réseau Wi-Fi enregistré (ou en saisir un), le QR code s'affiche ;
# les téléphones s'y connectent en le scannant. Imprimer (affichette A4 aux couleurs XIII) ou exporter en PNG / SVG.
# Hors ligne (qrencode). Application développée par Matthieu Lamotte.
import os, sys, subprocess, tempfile
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf
from . import systeme as S
from .ui import *
from .appli import preparer

def reseaux():
    """Réseaux Wi-Fi enregistrés : [(nom, ssid, sécurité, mot de passe)]."""
    L = []
    try:
        o = subprocess.run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], capture_output=True, text=True, timeout=5).stdout
        for l in o.splitlines():
            n, _, t = l.rpartition(":")
            if t != "802-11-wireless": continue
            n = n.replace("\\:", ":")
            d = subprocess.run(["nmcli", "-s", "-g", "802-11-wireless.ssid,802-11-wireless-security.key-mgmt,802-11-wireless-security.psk", "connection", "show", n],
                               capture_output=True, text=True, timeout=5).stdout.splitlines() + ["", "", ""]
            L.append((n, d[0] or n, d[1], d[2]))
    except Exception:
        pass
    return L

def echapper(s): return "".join("\\" + c if c in '\\;,":' else c for c in s)

def texte_qr(ssid, mdp, secu, cache=False):
    """Format standard des QR Wi-Fi (reconnu par Android et iPhone)."""
    t = "nopass" if not mdp else "WEP" if secu == "wep" else "WPA"
    return "WIFI:T:%s;S:%s;%s%s;" % (t, echapper(ssid), ("P:%s;" % echapper(mdp)) if t != "nopass" else "", "H:true;" if cache else "")

def png(texte, echelle=12):
    return subprocess.run(["qrencode", "-o", "-", "-s", str(echelle), "-m", "2", "-l", "M", texte], capture_output=True).stdout

class QRWifi(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.qrwifi")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".qr-cadre { background: white; border-radius: 18px; padding: 16px; }")
        self.win = Gtk.ApplicationWindow(application=self, title="QR Wi-Fi XIII"); self.win.set_default_size(820, 600)
        racine = boite(False, 24, margin_start=24, margin_end=24, margin_top=20, margin_bottom=20)
        g = boite(True, 10, hexpand=True)
        h = boite(False, 10); h.append(ico("qr-code", 30, "c")); h.append(label("QR Wi-Fi", "page-titre")); g.append(h)
        g.append(label("Les invités scannent le code avec l'appareil photo de leur téléphone : ils sont connectés, sans taper le mot de passe.", "attenue", wrap=True))
        self.R = reseaux()
        self.dd = Gtk.DropDown.new_from_strings([r[0] for r in self.R] + ["Autre réseau…"]); g.append(self.dd)
        self.ssid = Gtk.Entry(placeholder_text="Nom du réseau (SSID)"); self.mdp = Gtk.PasswordEntry(show_peek_icon=True, placeholder_text="Mot de passe")
        self.secu = Gtk.DropDown.new_from_strings(["WPA / WPA2 / WPA3", "Sans mot de passe", "WEP (ancien)"])
        self.cache = Gtk.CheckButton(label="Réseau masqué")
        for w in (self.ssid, self.mdp, self.secu, self.cache): g.append(w)
        self.titre = Gtk.Entry(placeholder_text="Titre de l'affichette (ex. Wi-Fi invités — Plateau B)"); g.append(self.titre)
        r = boite(False, 8)
        r.append(bouton("Imprimer l'affichette", "printer", "pilule", rappel=self.imprimer)); r.append(bouton("PNG", "download", "fantome", rappel=lambda: self.exporter("png")))
        r.append(bouton("SVG", "download", "fantome", rappel=lambda: self.exporter("svg"))); g.append(r)
        racine.append(g)
        cadre = boite(True, 0, "qr-cadre", valign=Gtk.Align.CENTER); self.pic = Gtk.Picture(); self.pic.set_size_request(300, 300); cadre.append(self.pic)
        self.l_ssid = label("", "gras", xalign=0.5); self.l_ssid.set_markup(""); d = boite(True, 8, valign=Gtk.Align.CENTER); d.append(cadre); d.append(self.l_ssid); racine.append(d)
        self.dd.connect("notify::selected", lambda *_: self.choisir())
        for w in (self.ssid, self.mdp): w.connect("changed", lambda *_: self.dessiner())
        self.secu.connect("notify::selected", lambda *_: self.dessiner()); self.cache.connect("toggled", lambda *_: self.dessiner())
        self.win.set_child(racine); self.choisir(); self.win.present()

    def choisir(self):
        i = self.dd.get_selected()
        if i < len(self.R):
            n, ssid, secu, mdp = self.R[i]; self.ssid.set_text(ssid); self.mdp.set_text(mdp)
            self.secu.set_selected(1 if secu in ("", "none") and not mdp else 2 if secu == "none" and mdp else 0)
        else:
            self.ssid.set_text(""); self.mdp.set_text("")
        self.dessiner()

    def texte(self):
        secu = ["wpa-psk", "none", "wep"][self.secu.get_selected()]
        return texte_qr(self.ssid.get_text(), "" if secu == "none" else self.mdp.get_text(), secu, self.cache.get_active())

    def dessiner(self):
        if not self.ssid.get_text(): self.pic.set_paintable(None); self.l_ssid.set_text(""); return
        data = png(self.texte())
        try:
            l = GdkPixbuf.PixbufLoader(); l.write(data); l.close(); self.pic.set_pixbuf(l.get_pixbuf())
        except Exception: pass
        self.l_ssid.set_text("Wi-Fi « %s »" % self.ssid.get_text())

    def exporter(self, fmt):
        if not self.ssid.get_text(): return
        d = Gtk.FileDialog(title="Exporter le QR code", initial_name="wifi-%s.%s" % (self.ssid.get_text().replace("/", "-"), fmt))
        def fin(dlg, res):
            try: f = dlg.save_finish(res).get_path()
            except Exception: return
            subprocess.run(["qrencode", "-t", fmt.upper(), "-o", f, "-s", "16", "-m", "2", self.texte()])
        d.save(self.win, None, fin)

    def imprimer(self):
        if not self.ssid.get_text(): return
        q = tempfile.NamedTemporaryFile(suffix=".png", delete=False); q.write(png(self.texte(), 20)); q.close()
        import html
        page = """<!doctype html><meta charset=utf-8><style>@page{size:A4;margin:18mm}body{font-family:'IBM Plex Sans',sans-serif;text-align:center;color:#1d1b19}
        h1{font-family:Astoria,serif;font-weight:400;font-size:40pt;color:#b8651f;margin:10mm 0 4mm}.s{font-size:20pt;margin:2mm}.p{font-family:'IBM Plex Mono',monospace;font-size:18pt}
        img{width:120mm;margin:10mm auto;display:block}.x{margin-top:12mm;color:#8a837b;font-size:10pt}</style>
        <h1>%s</h1><div class=s>Réseau : <b>%s</b></div>%s<img src="file://%s"><div>Scannez avec l'appareil photo de votre téléphone</div><div class=x>OS XIII</div>""" % (
            html.escape(self.titre.get_text() or "Wi-Fi"), html.escape(self.ssid.get_text()), ('<div class="s p">Mot de passe : %s</div>' % html.escape(self.mdp.get_text())) if self.mdp.get_text() else "", q.name)
        f = os.path.join(tempfile.gettempdir(), "qr-wifi-xiii.html"); open(f, "w").write(page)
        S.detacher(["xdg-open", f])
        S.detacher(["notify-send", "-a", "QR Wi-Fi", "-i", "printer", "Affichette prête", "Imprimez-la depuis le navigateur (Ctrl + P)."])

def main():
    sys.exit(QRWifi().run(sys.argv))
