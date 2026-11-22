# OS XIII — Multiview NDI : les sources NDI du réseau en mosaïque (2 × 2, 3 × 3, 4 × 4), nom et horloge en surimpression,
# reconnexion automatique. Chaque case reçoit la version « légère » du flux (peu de réseau, peu de processeur).
# Double-clic sur une case : la source en plein écran dans Retour plateau.
# NDI® est une marque déposée de Vizrt NDI AB.
# Application développée par Matthieu Lamotte.
import os, sys, time, threading, datetime
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib
from . import ndi, config, systeme as S
from .ui import *
from .appli import preparer

class Case:
    def __init__(self, app, i):
        self.app, self.i = app, i; self.nom = None; self.url = ""; self.actif = False; self.attente = False; self.derniere = 0
        self.pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, hexpand=True, vexpand=True, can_shrink=True)
        self.l = label("", "mv-nom"); self.l.set_halign(Gtk.Align.START); self.l.set_valign(Gtk.Align.END)
        self.vide = label("—", "attenue"); self.vide.set_halign(Gtk.Align.CENTER); self.vide.set_valign(Gtk.Align.CENTER)
        ov = Gtk.Overlay(); ov.set_child(self.pic); ov.add_overlay(self.vide); ov.add_overlay(self.l); ov.add_css_class("mv-case")
        g = Gtk.GestureClick(); g.connect("pressed", lambda g_, n, x, y: S.detacher(["xiii-retour", self.nom]) if n == 2 and self.nom else self.app.choisir_case(self)); ov.add_controller(g)
        self.widget = ov

    def regler(self, nom, url=""):
        self.arreter(); self.nom, self.url = nom, url
        self.l.set_text("  %d · %s  " % (self.i + 1, nom) if nom else ""); self.vide.set_text("Connexion…" if nom else "Case libre (clic pour choisir)"); self.vide.set_visible(True)
        self.pic.set_paintable(None)
        if nom: self.actif = True; threading.Thread(target=self.recevoir, daemon=True).start()

    def arreter(self): self.actif = False

    def recevoir(self):
        try: rec = ndi.Recepteur(self.nom, self.url, True, "Multiview — " + os.uname().nodename)
        except OSError as e:
            GLib.idle_add(self.vide.set_text, str(e)); return
        try:
            while self.actif:
                im = rec.image(250)
                if im is None:
                    if self.derniere and time.time() - self.derniere > 3: GLib.idle_add(lambda: (self.vide.set_text("Signal perdu…"), self.vide.set_visible(True), False)[2])
                    continue
                if not self.attente: self.attente = True; GLib.idle_add(self.afficher, im)
        finally:
            rec.fermer()

    def afficher(self, im):
        self.attente = False; w, h, pas, data = im
        self.pic.set_paintable(Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.B8G8R8A8, GLib.Bytes.new(data), pas))
        if self.vide.get_visible(): self.vide.set_visible(False)
        self.derniere = time.time(); return False

class Multiview(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.multiview")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        self.cfg = preparer(".mv { background: #000; } .mv-case { border: 1px solid #333; background: #050505; } .mv-nom { background: alpha(black, .65); color: white; font-weight: 700; margin: 6px; border-radius: 4px; }"
                            " .mv-heure { font-family: 'IBM Plex Mono'; font-size: 22px; color: #f0b378; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Multiview NDI XIII", default_width=1400, default_height=860); self.win.add_css_class("mv")
        v = boite(True, 0)
        h = boite(False, 8, margin_start=10, margin_end=10, margin_top=6, margin_bottom=6)
        h.append(ico("layout-grid", 20, "c")); h.append(label("Multiview NDI", "gras"))
        self.dd = Gtk.DropDown(model=Gtk.StringList.new(["2 × 2", "3 × 3", "4 × 4"])); self.dd.set_selected({4: 0, 9: 1, 16: 2}.get(int(self.cfg.get("multiview_cases", 4)), 0))
        self.dd.connect("notify::selected", lambda w, *_: self.grille([4, 9, 16][w.get_selected()])); h.append(self.dd)
        h.append(bouton("Remplir avec les sources du réseau", "refresh-cw", "fantome", rappel=self.auto)); h.append(boite(False, 0, hexpand=True))
        self.l_h = label("", "mv-heure"); h.append(self.l_h)
        h.append(bouton(None, "maximize", "plat", tip="Plein écran (F11)", rappel=lambda: self.win.unfullscreen() if self.win.is_fullscreen() else self.win.fullscreen()))
        v.append(h); self.g = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, vexpand=True); v.append(self.g)
        self.win.set_child(v); self.cases = []
        k = Gtk.EventControllerKey(); k.connect("key-pressed", lambda c, kv, *_: (self.win.unfullscreen() if self.win.is_fullscreen() else self.win.fullscreen(), True)[1] if kv == Gdk.KEY_F11 else False); self.win.add_controller(k)
        self.win.connect("close-request", lambda *_: ([c.arreter() for c in self.cases], False)[1])
        self.win.present()
        if not ndi.disponible():
            l = label("Le moteur NDI n'est pas installé.\nInstallez-le dans Paramètres › NDI, puis rouvrez Multiview.", "attenue")
            l.set_hexpand(True); l.set_vexpand(True); l.set_halign(Gtk.Align.CENTER); l.set_justify(Gtk.Justification.CENTER)
            self.g.attach(l, 0, 0, 1, 1); return
        self.grille(int(self.cfg.get("multiview_cases", 4)))
        GLib.timeout_add(500, lambda: (self.l_h.set_text(datetime.datetime.now().strftime("%H:%M:%S")), True)[1])
        noms = self.cfg.get("multiview_sources") or []
        if any(noms):
            for c, n in zip(self.cases, noms): c.regler(n)
        else: self.auto()

    def grille(self, n):
        for c in self.cases: c.arreter()
        c_ = self.g.get_first_child()
        while c_: s = c_.get_next_sibling(); self.g.remove(c_); c_ = s
        cote = int(n ** .5); anciens = [c.nom for c in self.cases]; self.cases = []
        for i in range(n):
            c = Case(self, i); self.cases.append(c); self.g.attach(c.widget, i % cote, i // cote, 1, 1)
            if i < len(anciens) and anciens[i]: c.regler(anciens[i])
            else: c.regler(None)
        config.modifier(_histo=False, multiview_cases=n)

    def sauver(self): config.modifier(_histo=False, multiview_sources=[c.nom for c in self.cases])

    def auto(self):
        def fond():
            r = ndi.Recherche(); L = r.sources(3000); r.fermer(); return L
        def fin(L):
            if isinstance(L, Exception) or not L: return
            for c, src in zip(self.cases, L): c.regler(src[0] if isinstance(src, tuple) else src)
            self.sauver()
        S.en_fond(fond, fin)

    def choisir_case(self, case):
        def fond():
            r = ndi.Recherche(); L = r.sources(2000); r.fermer(); return L
        def fin(L):
            items = [("cast", (s[0] if isinstance(s, tuple) else s), (lambda s=s: (case.regler(s[0] if isinstance(s, tuple) else s), self.sauver()))) for s in (L if isinstance(L, list) else [])]
            items.append(("x", "Vider cette case", lambda: (case.regler(None), self.sauver())))
            popover_menu(case.widget, items)
        S.en_fond(fond, fin)

def main():
    sys.exit(Multiview().run(sys.argv[:1]))
