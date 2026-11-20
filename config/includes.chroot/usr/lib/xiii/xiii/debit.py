# OS XIII — Test de débit XIII (iperf3) : mesurer le vrai débit entre deux PC du réseau (câble, Wi-Fi, liaison régie).
# Un PC « reçoit » (serveur), l'autre « mesure » ; envoi, réception ou les deux sens, graphe en direct, historique.
# Application développée par Matthieu Lamotte.
import os, sys, json, subprocess, threading, time, socket
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib
from . import systeme as S, netscan as N
from .ui import *
from .appli import preparer, Volet, page

HISTO = os.path.expanduser("~/.local/share/xiii/debit.json")

def mbps(b): return "%.0f Mbit/s" % (b / 1e6) if b >= 1e7 else "%.1f Mbit/s" % (b / 1e6)

class Courbe(Gtk.DrawingArea):
    def __init__(self):
        super().__init__(); self.v = []; self.set_size_request(-1, 180); self.set_draw_func(self.dessin)
    def dessin(self, a, cr, w, h):
        c = a.get_color(); acc = Gdk.RGBA(); acc.parse(ACC.get("c", "#f0b378"))
        cr.set_source_rgba(c.red, c.green, c.blue, .06); cr.rectangle(0, 0, w, h); cr.fill()
        if len(self.v) < 2: return
        m = max(self.v) * 1.15 or 1; pas = w / max(1, len(self.v) - 1)
        cr.move_to(0, h)
        for i, x in enumerate(self.v): cr.line_to(i * pas, h - h * x / m)
        cr.line_to((len(self.v) - 1) * pas, h); cr.close_path(); cr.set_source_rgba(acc.red, acc.green, acc.blue, .22); cr.fill()
        for i, x in enumerate(self.v): (cr.move_to if i == 0 else cr.line_to)(i * pas, h - h * x / m)
        cr.set_source_rgba(acc.red, acc.green, acc.blue, 1); cr.set_line_width(2.4); cr.stroke()

class Debit(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.debit"); self.serveur = None

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".gros-chiffre { font-family: 'IBM Plex Mono', monospace; font-size: 34px; font-weight: 700; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Test de débit XIII"); self.win.set_default_size(980, 680)
        self.volet = Volet("Test de débit", "Le vrai débit entre deux PC (iperf3)")
        self.volet.ajouter("mesurer", "gauge", "Mesurer", self.p_mesurer())
        self.volet.ajouter("recevoir", "radio-tower", "Être le PC de réception", self.p_recevoir())
        self.volet.ajouter("histo", "history", "Historique", rappel=self.p_histo)
        self.win.set_child(self.volet.racine); self.volet.aller("mesurer"); self.win.present()
        self.win.connect("close-request", lambda *_: (self.serveur and self.serveur.terminate(), False)[1])

    def p_mesurer(self):
        sc, v = page("Mesurer le débit", "Démarrez « Être le PC de réception » sur l'autre PC (ou un serveur iperf3), puis saisissez son adresse", "gauge")
        h = boite(False, 8); self.hote = Gtk.Entry(placeholder_text="Adresse de l'autre PC (ex. 192.168.1.20)", hexpand=True); h.append(self.hote)
        self.sens = Gtk.DropDown.new_from_strings(["Envoi (ce PC → l'autre)", "Réception (l'autre → ce PC)", "Les deux en même temps"]); h.append(self.sens)
        self.duree = Gtk.DropDown.new_from_strings(["10 s", "30 s", "60 s"]); h.append(self.duree)
        self.b_go = bouton("Mesurer", "play", "pilule", rappel=self.mesurer); h.append(self.b_go); v.append(h)
        self.chiffre = label("—", "gros-chiffre", "accent"); v.append(self.chiffre)
        self.courbe = Courbe(); v.append(self.courbe)
        self.resume = label("", "attenue", wrap=True); v.append(self.resume)
        return sc

    def mesurer(self):
        h = self.hote.get_text().strip()
        if not h: return
        d = [10, 30, 60][self.duree.get_selected()]; s = self.sens.get_selected()
        extra = ["-R"] if s == 1 else ["--bidir"] if s == 2 else []
        self.courbe.v = []; self.courbe.queue_draw(); self.chiffre.set_text("…"); self.b_go.set_sensitive(False); self.resume.set_text("Mesure en cours (%d s)…" % d)
        p = subprocess.Popen(["iperf3", "-c", h, "-t", str(d), "-i", "1", "--forceflush", "-f", "m"] + extra, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        def lire():
            import re
            for l in p.stdout:
                m = re.search(r"([\d.]+)\s+Mbits/sec", l)
                if m and "sender" not in l and "receiver" not in l:
                    x = float(m.group(1)) * 1e6
                    GLib.idle_add(lambda x=x: (self.courbe.v.append(x), self.courbe.queue_draw(), self.chiffre.set_text(mbps(x)), False)[3])
                if "receiver" in l and m:
                    fin = float(m.group(1)) * 1e6
                    GLib.idle_add(lambda fin=fin: (self.chiffre.set_text(mbps(fin)), False)[1])
                if "unable to connect" in l.lower() or "error" in l.lower():
                    GLib.idle_add(lambda l=l: (self.resume.set_text("Connexion impossible : l'autre PC est-il en réception ? (%s)" % l.strip()[-80:]), False)[1])
            p.wait()
            def fin():
                self.b_go.set_sensitive(True)
                if self.courbe.v:
                    moy = sum(self.courbe.v) / len(self.courbe.v)
                    self.resume.set_text("Moyenne %s · max %s · min %s" % (mbps(moy), mbps(max(self.courbe.v)), mbps(min(self.courbe.v))))
                    L = self.histo(); L.insert(0, {"date": time.strftime("%Y-%m-%d %H:%M"), "hote": h, "sens": ["envoi", "réception", "deux sens"][s], "moyenne": moy})
                    os.makedirs(os.path.dirname(HISTO), exist_ok=True); json.dump(L[:50], open(HISTO, "w"))
                return False
            GLib.idle_add(fin)
        threading.Thread(target=lire, daemon=True).start()

    def p_recevoir(self):
        sc, v = page("Être le PC de réception", "Ce PC attend la mesure lancée depuis l'autre PC", "radio-tower")
        self.l_srv = label("Arrêté", "gras"); v.append(self.l_srv)
        ips = ", ".join(c.split("/")[0] for _, c in N.interfaces_reseau()) or "?"
        v.append(label("Adresse(s) de ce PC à saisir sur l'autre : %s" % ips, "gros-chiffre" if len(ips) < 18 else "gras", wrap=True))
        def basculer():
            if self.serveur and self.serveur.poll() is None:
                self.serveur.terminate(); self.serveur = None; self.l_srv.set_text("Arrêté"); return
            self.serveur = subprocess.Popen(["iperf3", "-s"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); self.l_srv.set_text("● En réception (port 5201)")
        v.append(bouton("Démarrer / arrêter la réception", "power", "pilule", rappel=basculer))
        v.append(label("Si la mesure n'arrive pas : autorisez le port 5201 dans Paramètres › Pare-feu.", "petit", "attenue", wrap=True))
        return sc

    def histo(self):
        try: return json.load(open(HISTO))
        except Exception: return []

    def p_histo(self):
        sc, v = page("Historique", None, "history")
        L = self.histo()
        if not L: v.append(label("Aucune mesure pour l'instant.", "attenue"))
        for e in L:
            r = boite(False, 10, "reglage"); r.append(ico("gauge", 18, "c")); r.append(label("%s · %s · %s" % (e["date"], e["hote"], e["sens"]), hexpand=True))
            r.append(label(mbps(e["moyenne"]), "gras", "accent")); v.append(r)
        x = self.volet.pile.get_child_by_name("histo")
        if x: self.volet.pile.remove(x)
        self.volet.pile.add_named(sc, "histo"); self.volet.pile.set_visible_child_name("histo")

def main():
    sys.exit(Debit().run(sys.argv))
