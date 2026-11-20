# OS XIII — Scanner IP XIII : la version maison d'Advanced IP Scanner.
# Plage d'adresses → appareils (nom, IP, fabricant, MAC, type, services) ; actions en un clic : page web, partages,
# SSH, bureau à distance, VNC, réveil à distance (Wake-on-LAN), copier ; export CSV ; favoris.
# Application développée par Matthieu Lamotte.
import os, sys, json, csv, socket, threading, shutil, subprocess
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S, netscan as N
from .ui import *
from .appli import preparer, Volet, page

FAVORIS = os.path.expanduser("~/.config/xiii/scanip-favoris.json")
ICONES = {"NAS": "hard-drive", "Ordinateur": "monitor", "Ordinateur / serveur": "server", "Imprimante": "printer", "Mélangeur / Blackmagic": "video",
          "Téléphone / tablette": "smartphone", "Appareil web": "globe", "Appareil": "cpu"}

def wol(mac):
    m = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.sendto(b"\xff" * 6 + m * 16, ("255.255.255.255", 9)); s.close()

def favoris():
    try: return json.load(open(FAVORIS))
    except Exception: return []

class Scanner(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.scanip"); self.apps = []; self.choix = None; self.stop = False

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer()
        self.win = Gtk.ApplicationWindow(application=self, title="Scanner IP XIII"); self.win.set_default_size(1180, 720)
        self.volet = Volet("Scanner IP", "Les appareils de votre réseau, comme Advanced IP Scanner")
        self.volet.ajouter("analyse", "radar", "Analyse", self.p_analyse())
        self.volet.ajouter("favoris", "star", "Favoris", self.p_favoris(), rappel=self.remplir_favoris)
        self.win.set_child(self.volet.racine); self.volet.aller("analyse"); self.win.present()

    # -------------------------------------------------------------- analyse
    def p_analyse(self):
        v = boite(True, 10, margin_start=18, margin_end=18, margin_top=16, margin_bottom=14)
        h = boite(False, 8)
        self.plage = Gtk.Entry(text=N.plage_par_defaut(), hexpand=True, placeholder_text="ex. 192.168.1.1-254, 10.0.0.0/24")
        self.plage.connect("activate", lambda *_: self.analyser()); h.append(self.plage)
        self.b_go = bouton("Analyser", "radar", "pilule", rappel=self.analyser); h.append(self.b_go)
        h.append(bouton(None, "download", "plat", tip="Exporter en CSV", rappel=self.exporter))
        v.append(h)
        self.barre = Gtk.ProgressBar(); v.append(self.barre)
        self.filtre = Gtk.SearchEntry(placeholder_text="Filtrer (nom, IP, fabricant, service…)"); self.filtre.connect("search-changed", lambda *_: self.remplir()); v.append(self.filtre)
        en = boite(False, 8, margin_start=10, margin_end=10)
        for t, l in (("", 26), ("Nom", 0), ("IP", 120), ("Fabricant", 200), ("MAC", 140), ("Services", 220)):
            x = label(t, "petit", "attenue")
            if l: x.set_size_request(l, -1)
            else: x.set_hexpand(True)
            en.append(x)
        v.append(en)
        sc = Gtk.ScrolledWindow(vexpand=True); self.liste = boite(True, 0); sc.set_child(self.liste); v.append(sc)
        self.detail = boite(False, 8, "carte"); self.detail.set_visible(False); v.append(self.detail)
        self.resume = label("Appuyez sur « Analyser ». Les appareils qui ne répondent pas au ping mais sont connus du réseau apparaissent aussi.", "petit", "attenue", wrap=True); v.append(self.resume)
        return v

    def analyser(self):
        if self.b_go.get_sensitive() is False: return
        self.b_go.set_sensitive(False); self.stop = False; self.barre.set_fraction(0); self.resume.set_text("Analyse en cours…")
        plage = self.plage.get_text()
        def prog(f, t): GLib.idle_add(lambda: (self.barre.set_fraction(min(1, f / max(1, t))), False)[1])
        def fini(r):
            self.b_go.set_sensitive(True); self.barre.set_fraction(1)
            if isinstance(r, Exception): self.resume.set_text("Analyse impossible : %s" % r); return
            self.apps = r; self.remplir()
        if S.DEMO:
            demo = [{"ip": "192.168.1.%d" % k, "mac": m, "nom": n, "fabricant": f, "ports": p, "services": [], "marque": mq, "type": t, "nas": t == "NAS", "web": ""}
                    for k, m, n, f, p, mq, t in ((1, "34:27:92:aa:01:02", "freebox", "Freebox SAS", [80, 443], "Freebox", "Appareil web"),
                                                 (12, "00:11:32:bb:02:03", "DS920", "Synology Incorporated", [445, 5000, 5001, 22], "Synology", "NAS"),
                                                 (20, "7c:2e:0d:cc:04:05", "ATEM-Mini-Pro", "Blackmagic Design", [9910], "Blackmagic", "Mélangeur / Blackmagic"),
                                                 (31, "24:4b:fe:dd:05:06", "regie-pc", "ASUSTek COMPUTER INC.", [22, 445, 3389], "", "Ordinateur"),
                                                 (40, "00:08:9b:ee:06:07", "TS-453D", "ICP Electronics Inc.", [445, 8080, 2049], "QNAP", "NAS"),
                                                 (55, "3c:2a:f4:ff:07:08", "imprimante-bureau", "Brother Industries, LTD.", [80, 631], "", "Imprimante"))]
            GLib.timeout_add(600, lambda: (fini(demo), False)[1]); return
        S.en_fond(lambda: N.analyser(plage, prog, arreter=lambda: self.stop), fini)

    def remplir(self):
        vider(self.liste); q = self.filtre.get_text().lower()
        L = [a for a in self.apps if not q or q in json.dumps(a, default=list).lower()]
        for a in L:
            r = boite(False, 8, "ligne-tab")
            if self.choix is a: r.add_css_class("choisi")
            r.append(ico(ICONES.get(a["type"], "cpu"), 18, "c" if a.get("nas") else "t"))
            col = boite(True, 0, hexpand=True); col.append(label(a["nom"] or a["ip"], "gras", ellipsize=True))
            col.append(label(a["type"] + (" · " + a["marque"] if a.get("marque") else ""), "petit", "attenue", ellipsize=True)); r.append(col)
            for t, l in ((a["ip"], 120), (a.get("fabricant", ""), 200), (a.get("mac", "").upper(), 140),
                         (", ".join(N.PORTS.get(p, str(p)).split(" (")[0] for p in a.get("ports", [])[:4]), 220)):
                x = label(t, "petit", "chiffre" if t == a["ip"] or ":" in t else "", ellipsize=True); x.set_size_request(l, -1); r.append(x)
            g = Gtk.GestureClick(); g.connect("released", lambda *_x, a=a: self.choisir(a)); r.add_controller(g)
            g2 = Gtk.GestureClick(button=3); g2.connect("released", lambda *_x, a=a, r=r: (self.choisir(a), popover_menu(r, self.actions(a)))); r.add_controller(g2)
            self.liste.append(r)
        nas = sum(1 for a in self.apps if a.get("nas"))
        self.resume.set_text("%d appareil(s) trouvé(s)%s." % (len(self.apps), (" dont %d NAS" % nas) if nas else ""))

    def actions(self, a):
        ip, p = a["ip"], set(a.get("ports", []))
        L = []
        for pt, sch in ((443, "https"), (5001, "https"), (80, "http"), (5000, "http"), (8080, "http"), (8443, "https")):
            if pt in p: L.append(("globe", "Ouvrir la page web (%d)" % pt, lambda sch=sch, pt=pt: S.detacher(["xdg-open", "%s://%s:%d/" % (sch, ip, pt)])))
        if 445 in p or 139 in p: L.append(("folder-open", "Ouvrir les partages", lambda: S.detacher(["thunar", "smb://%s/" % ip])))
        if a.get("nas"): L.append(("hard-drive", "Connecter comme lecteur réseau", lambda: S.detacher(["xiii-lecteurs", "--ajouter", ip])))
        if 22 in p: L.append(("terminal", "SSH (terminal)", lambda: S.detacher(["foot", "--app-id=fr.xiii.terminal", "ssh", ip])))
        if 3389 in p: L.append(("monitor", "Bureau à distance (RDP)", lambda: S.detacher(["remmina", "-c", "rdp://" + ip] if shutil.which("remmina") else ["xdg-open", "rdp://" + ip])))
        if 5900 in p: L.append(("monitor", "VNC", lambda: S.detacher(["remmina", "-c", "vnc://" + ip] if shutil.which("remmina") else ["xdg-open", "vnc://" + ip])))
        if 21 in p: L.append(("folder", "FTP", lambda: S.detacher(["thunar", "ftp://" + ip])))
        if L: L.append(None)
        if a.get("mac") and not N.fabricant(a["mac"]).startswith("Adresse"): L.append(("power", "Réveiller (Wake-on-LAN)", lambda: (wol(a["mac"]), S.detacher(["notify-send", "-a", "Scanner IP", "Réveil envoyé à " + (a["nom"] or ip)]))))
        L.append(("copy", "Copier l'adresse IP", lambda: Gdk.Display.get_default().get_clipboard().set_text(ip)))
        if a.get("mac"): L.append(("copy", "Copier l'adresse MAC", lambda: Gdk.Display.get_default().get_clipboard().set_text(a["mac"].upper())))
        L.append(("star", "Ajouter aux favoris", lambda: self.favori(a)))
        return L

    def choisir(self, a):
        self.choix = a; self.remplir(); vider(self.detail); self.detail.set_visible(True)
        self.detail.append(ico(ICONES.get(a["type"], "cpu"), 32, "c"))
        col = boite(True, 2, hexpand=True); col.append(label(a["nom"] or a["ip"], "gras"))
        col.append(label("%s · %s · %s" % (a["ip"], a.get("mac", "").upper() or "MAC inconnue", a.get("fabricant") or "fabricant inconnu"), "petit", "attenue", wrap=True))
        if a.get("web"): col.append(label("Page web : " + a["web"][:80], "petit", "attenue", ellipsize=True))
        col.append(label("Services : " + (", ".join(N.PORTS.get(p, str(p)) for p in a.get("ports", [])) or "aucun service ouvert détecté"), "petit", wrap=True))
        self.detail.append(col)
        bx = boite(False, 6, valign=Gtk.Align.CENTER)
        for ic, t, fn in [x for x in self.actions(a) if x][:4]: bx.append(bouton(t, ic, "fantome", taille=14, rappel=fn))
        self.detail.append(bx)

    def exporter(self):
        d = Gtk.FileDialog(title="Exporter l'analyse", initial_name="analyse-reseau.csv")
        def fini(dlg, res):
            try: f = dlg.save_finish(res).get_path()
            except Exception: return
            with open(f, "w", newline="") as h:
                w = csv.writer(h, delimiter=";"); w.writerow(["Nom", "IP", "MAC", "Fabricant", "Type", "Marque", "Services"])
                for a in self.apps: w.writerow([a["nom"], a["ip"], a.get("mac", ""), a.get("fabricant", ""), a["type"], a.get("marque", ""), " ".join(map(str, a.get("ports", [])))])
        d.save(self.win, None, fini)

    # -------------------------------------------------------------- favoris
    def p_favoris(self):
        sc, self.v_fav = page("Favoris", "Vos appareils importants, réveillables et joignables en un clic", "star"); return sc

    def favori(self, a):
        L = [f for f in favoris() if f["ip"] != a["ip"]] + [a]
        os.makedirs(os.path.dirname(FAVORIS), exist_ok=True); json.dump(L, open(FAVORIS, "w"), default=list, ensure_ascii=False)

    def remplir_favoris(self):
        c = self.v_fav.get_first_child().get_next_sibling()
        while c: n = c.get_next_sibling(); self.v_fav.remove(c); c = n
        L = favoris()
        if not L: self.v_fav.append(label("Clic droit sur un appareil › « Ajouter aux favoris ».", "attenue"))
        for a in L:
            r = boite(False, 10, "reglage"); r.append(ico(ICONES.get(a.get("type"), "cpu"), 20, "c"))
            col = boite(True, 0, hexpand=True); col.append(label(a.get("nom") or a["ip"], "gras")); col.append(label("%s · %s" % (a["ip"], a.get("mac", "").upper()), "petit", "attenue")); r.append(col)
            etat = label("…", "petit", "attenue"); r.append(etat)
            S.en_fond(lambda ip=a["ip"]: N.ping(ip), lambda ok, e=etat: e.set_text("● en ligne" if ok is True else "○ hors ligne"))
            m = bouton(None, "ellipsis", "plat", rappel=None); m.connect("clicked", lambda b, a=a: popover_menu(b, self.actions(a) + [("trash-2", "Retirer des favoris", lambda a=a: self.retirer(a))])); r.append(m)
            self.v_fav.append(r)

    def retirer(self, a):
        json.dump([f for f in favoris() if f["ip"] != a["ip"]], open(FAVORIS, "w"), default=list); self.remplir_favoris()

def main():
    sys.exit(Scanner().run(sys.argv))
