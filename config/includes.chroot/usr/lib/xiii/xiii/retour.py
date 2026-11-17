# OS XIII — Retour plateau : une source NDI en plein écran, en un clic. Le vieux PC devient un écran de retour.
# • choix de la source (liste du réseau, adresse IP pour un autre sous-réseau), qualité pleine ou légère
# • plein écran (F11 / double-clic), nom de la source et horloge en surimpression, reconnexion automatique
# • se souvient de la dernière source : « xiii-retour --dernier » au démarrage
# NDI® est une marque déposée de Vizrt NDI AB.
# Application développée par Matthieu Lamotte.
import os, sys, json, threading, time
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import ndi, theme, config
from .ui import *

REGL = os.path.join(GLib.get_user_config_dir(), "xiii", "retour.json")


def charger():
    try: return json.load(open(REGL))
    except Exception: return {"source": "", "url": "", "leger": False, "infos": True, "ips": ""}


def sauver(r):
    os.makedirs(os.path.dirname(REGL), exist_ok=True); json.dump(r, open(REGL, "w"), ensure_ascii=False, indent=1)


class Retour(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.retour", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.r = charger(); self.rec = None; self.rech = None; self.fil = None; self.actif = False
        self.attente = False; self.derniere = 0; self.ips = 0; self.compte = 0

    def do_command_line(self, cl):
        a = cl.get_arguments()[1:]
        if not getattr(self, "win", None): self.construire()
        if a and a[0] != "--dernier": self.r["source"] = a[0]; self.r["url"] = ""
        if (a or self.r.get("source")) and ndi.disponible(): self.connecter(self.r["source"], self.r.get("url", ""))
        self.win.present()
        return 0

    def construire(self):
        cfg = config.charger()
        css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(cfg) + """
            .retour { background: #000; }
            .surimp { background: alpha(#000, .55); border-radius: 12px; padding: 8px 14px; color: #fff; }
            .surimp-titre { font-weight: 700; font-size: 15pt; }
            .barre-retour { background: alpha(#101014, .86); border-radius: 16px; padding: 10px; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        w = Gtk.ApplicationWindow(application=self, title="Retour plateau", default_width=1280, default_height=720)
        w.add_css_class("retour"); self.win = w
        ov = Gtk.Overlay(); w.set_child(ov)
        self.image = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, hexpand=True, vexpand=True); ov.set_child(self.image)
        self.vide = boite(True, 14, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.vide.append(ico("cast" if os.path.exists(theme.LUCIDE + "/cast.svg") else "monitor", 64, "c"))
        self.vide_titre = label("Retour plateau", "hero-grand"); self.vide.append(self.vide_titre)
        self.vide_texte = label("Choisissez une source NDI du réseau.", "attenue", wrap=True, largeur=60); self.vide.append(self.vide_texte)
        ov.add_overlay(self.vide)
        # surimpression : source + horloge
        self.info = boite(True, 2, "surimp", halign=Gtk.Align.START, valign=Gtk.Align.START, margin_start=20, margin_top=20)
        self.l_src = label("", "surimp-titre"); self.l_det = label("", "petit"); self.info.append(self.l_src); self.info.append(self.l_det)
        ov.add_overlay(self.info); self.info.set_visible(False)
        self.l_heure = label("", "surimp", "surimp-titre", halign=Gtk.Align.END, valign=Gtk.Align.START, margin_end=20, margin_top=20)
        ov.add_overlay(self.l_heure); self.l_heure.set_visible(False)
        # barre de commande (apparaît au mouvement de la souris)
        b = boite(False, 8, "barre-retour", halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=24); self.barre = b
        self.liste = Gtk.StringList(); self.dd = Gtk.DropDown(model=self.liste); self.dd.set_size_request(380, -1)
        self.dd.connect("notify::selected", self.choisi); b.append(self.dd)
        b.append(bouton(None, "refresh-cw", "fantome", tip="Actualiser les sources", rappel=lambda: self.chercher(True)))
        self.b_leger = Gtk.ToggleButton(label="Léger", active=self.r.get("leger", False), tooltip_text="Qualité légère : moins de réseau et de processeur (vieux PC, Wi-Fi)")
        self.b_leger.connect("toggled", lambda t: (self.r.update(leger=t.get_active()), sauver(self.r), self.connecter(self.r.get("source", ""), self.r.get("url", ""))) if self.r.get("source") else None); b.append(self.b_leger)
        self.b_infos = Gtk.ToggleButton(label="Infos", active=self.r.get("infos", True), tooltip_text="Nom de la source et horloge")
        self.b_infos.connect("toggled", lambda t: (self.r.update(infos=t.get_active()), sauver(self.r), self.maj_infos())); b.append(self.b_infos)
        self.e_ip = Gtk.Entry(placeholder_text="IP d'un autre réseau", text=self.r.get("ips", ""), width_chars=16)
        self.e_ip.connect("activate", lambda e: (self.r.update(ips=e.get_text().strip()), sauver(self.r), self.chercher(True, True))); b.append(self.e_ip)
        b.append(bouton(None, "maximize", "fantome", tip="Plein écran (F11)", rappel=self.plein_ecran))
        ov.add_overlay(b)
        mv = Gtk.EventControllerMotion(); mv.connect("motion", self.bouge); w.add_controller(mv)
        cl = Gtk.GestureClick(); cl.connect("pressed", lambda g, n, x, y: self.plein_ecran() if n == 2 else None); w.add_controller(cl)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.touche); w.add_controller(k)
        self.cache_barre = 0
        GLib.timeout_add(500, self.tic)
        if not ndi.disponible():
            self.vide_titre.set_text("Runtime NDI non installé")
            self.vide_texte.set_text("Le runtime NDI est gratuit mais sa licence interdit de le fournir dans OS XIII : il s'installe en un clic après acceptation de la licence.")
            bi = bouton("Installer le runtime NDI", None, "pilule", rappel=lambda: os.system("xiii-parametres --page ndi &")); bi.set_halign(Gtk.Align.CENTER); self.vide.append(bi)
            self.barre.set_visible(False)
        else:
            self.chercher()
        w.present()

    # ------------------------------------------------------------- sources
    def chercher(self, forcer=False, nouveau=False):
        def fond():
            try:
                if nouveau and self.rech: self.rech.fermer(); self.rech = None
                if not self.rech: self.rech = ndi.Recherche(self.r.get("ips") or None)
                L = self.rech.sources(2500 if forcer else 1500)
            except OSError as e:
                L = []; GLib.idle_add(self.vide_texte.set_text, str(e))
            GLib.idle_add(self.remplir, L)
        threading.Thread(target=fond, daemon=True).start()

    def remplir(self, L):
        self._remplissage = True
        self.sources = L
        noms = [n for n, _ in L]
        if self.r.get("source") and self.r["source"] not in noms: noms.insert(0, self.r["source"]); self.sources.insert(0, (self.r["source"], self.r.get("url", "")))
        self.liste.splice(0, self.liste.get_n_items(), ["— Choisir une source —"] + noms)
        self.dd.set_selected(noms.index(self.r["source"]) + 1 if self.r.get("source") in noms else 0)
        self._remplissage = False
        if not L and not self.actif: self.vide_texte.set_text("Aucune source NDI trouvée. Vérifiez que le PC est sur le même réseau que le mélangeur, ou saisissez son adresse IP.")
        GLib.timeout_add_seconds(8, lambda: (self.chercher(), False)[1])

    def choisi(self, dd, _p):
        if getattr(self, "_remplissage", False): return
        i = dd.get_selected()
        if i == 0 or i == Gtk.INVALID_LIST_POSITION: return
        n, u = self.sources[i - 1]
        if n == self.r.get("source") and self.actif: return
        self.r.update(source=n, url=u); sauver(self.r); self.connecter(n, u)

    # ------------------------------------------------------------- réception
    def connecter(self, nom, url=""):
        self.arreter()
        if not nom: return
        self.actif = True; self.vide_titre.set_text(nom); self.vide_texte.set_text("Connexion…")
        self.fil = threading.Thread(target=self.recevoir, args=(nom, url, self.r.get("leger", False)), daemon=True); self.fil.start()
        self.maj_infos()

    def arreter(self):
        self.actif = False
        if self.fil: self.fil.join(1.5); self.fil = None

    def recevoir(self, nom, url, leger):
        try:
            rec = ndi.Recepteur(nom, url, leger, "Retour plateau — " + os.uname().nodename)
        except OSError as e:
            GLib.idle_add(self.vide_texte.set_text, str(e)); self.actif = False; return
        try:
            while self.actif:
                im = rec.image(250)
                if im is None:
                    if time.time() - self.derniere > 3 and self.derniere:
                        GLib.idle_add(self.perdu)
                    continue
                self.compte += 1
                if not self.attente:
                    self.attente = True; GLib.idle_add(self.afficher, im)
        finally:
            rec.fermer()

    def afficher(self, im):
        self.attente = False
        w, h, pas, data = im
        tex = Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.B8G8R8A8, GLib.Bytes.new(data), pas)
        self.image.set_paintable(tex)
        if self.vide.get_visible(): self.vide.set_visible(False)
        self.derniere = time.time(); self.taille = (w, h)
        return False

    def perdu(self):
        self.vide.set_visible(True); self.vide_texte.set_text("Signal perdu — reconnexion automatique…"); self.derniere = 0
        return False

    # ------------------------------------------------------------- interface
    def maj_infos(self):
        on = self.r.get("infos", True) and self.actif
        self.info.set_visible(on); self.l_heure.set_visible(on)

    def tic(self):
        now = time.time()
        self.ips = self.compte * 2; self.compte = 0
        if self.info.get_visible():
            self.l_src.set_text(self.r.get("source", ""))
            t = getattr(self, "taille", None)
            self.l_det.set_text(("%d × %d · %d i/s" % (t[0], t[1], self.ips) if t else "") + (" · léger" if self.r.get("leger") else ""))
            self.l_heure.set_text(time.strftime("%H:%M:%S"))
        if self.cache_barre and now > self.cache_barre and self.actif:
            self.barre.set_visible(False); self.cache_barre = 0; self.win.set_cursor(Gdk.Cursor.new_from_name("none"))
        return True

    def bouge(self, *_):
        if not ndi.disponible(): return
        self.barre.set_visible(True); self.win.set_cursor(None); self.cache_barre = time.time() + 3

    def plein_ecran(self):
        self.win.unfullscreen() if self.win.is_fullscreen() else self.win.fullscreen()

    def touche(self, c, kv, code, st):
        if kv in (Gdk.KEY_F11, Gdk.KEY_f): self.plein_ecran(); return True
        if kv == Gdk.KEY_Escape and self.win.is_fullscreen(): self.win.unfullscreen(); return True
        if kv == Gdk.KEY_i: self.b_infos.set_active(not self.b_infos.get_active()); return True
        return False


def main():
    sys.exit(Retour().run(sys.argv))
