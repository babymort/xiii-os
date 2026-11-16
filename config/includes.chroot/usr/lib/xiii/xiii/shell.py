# OS XIII — le bureau : barre des tâches (bas, façon Windows 11), barre du haut (réglages rapides),
# menu Démarrer avec catégories, panneaux rapides, notifications, fond d'écran, veille, lumière nocturne.
# Application développée par Matthieu Lamotte.
import os, sys, time, datetime, subprocess, signal, pwd, unicodedata
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from gi.repository import Gtk4LayerShell as LS
from . import config, theme, systeme as S, apps, notifs, panneaux as P
from .fenetres import Gestionnaire
from .ui import *

HB, HH = 48, 32   # hauteurs barre des tâches / barre du haut
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]

def couche(win, niveau, ancres, marges=None, clavier=LS.KeyboardMode.NONE, ns="xiii", exclusif=None):
    LS.init_for_window(win)
    LS.set_namespace(win, ns)
    LS.set_layer(win, niveau)
    for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
        LS.set_anchor(win, e, e in ancres)
    for e, v in (marges or {}).items():
        LS.set_margin(win, e, v)
    LS.set_keyboard_mode(win, clavier)
    if exclusif == "auto": LS.auto_exclusive_zone_enable(win)
    elif exclusif is not None: LS.set_exclusive_zone(win, exclusif)
    win.add_css_class("xiii-surface")


class Shell(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.Shell", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.cfg = config.charger(); self.p = theme.palette(self.cfg)
        self.ouvert = None; self.procs = {}; self.fenetres = None; self.serveur = None
        self._icones_src = 0; self._meteo = None; self._apps_notif = set()

    # ============================================================== démarrage
    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()
        couleurs(self.cfg)
        self.css = Gtk.CssProvider(); self.css.load_from_string(theme.css_shell(self.cfg))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 10)
        Gtk.Settings.get_default().set_property("gtk-icon-theme-name", "XIII")
        for nom, typ in (("basculer", "s"), ("fermer", None), ("parametres", "s")):
            a = Gio.SimpleAction.new(nom, GLib.VariantType.new(typ) if typ else None)
            a.connect("activate", getattr(self, "_act_" + nom)); self.add_action(a)
        self.creer_fenetres()
        self.serveur = notifs.Serveur(self.notif_nouvelle, self.notif_fermee)
        self.fenetres = Gestionnaire(self.maj_taches)
        self.mon = config.surveiller(self.cfg_change)
        self.services(premier=True)
        theme.appliquer_systeme(self.cfg) if not os.path.exists(os.path.join(config.DOSSIER, ".applique")) else None
        try: open(os.path.join(config.DOSSIER, ".applique"), "w").close()
        except OSError: pass
        GLib.timeout_add_seconds(1, self.tic)
        GLib.timeout_add_seconds(6, self.maj_icones)
        GLib.timeout_add_seconds(1800, self.maj_meteo)
        self.maj_icones(); self.maj_meteo(); self.maj_taches(); self.tic()

    def do_activate(self):
        pass

    def _act_basculer(self, a, v):
        self.basculer(v.get_string())

    def _act_fermer(self, *_):
        self.fermer()

    def _act_parametres(self, a, v):
        self.parametres(v.get_string())

    # ============================================================== fenêtres de couche
    def creer_fenetres(self):
        T, B, Lf, R = LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT
        # fond cliquable qui ferme les panneaux
        self.voile = Gtk.Window(application=self); couche(self.voile, LS.Layer.TOP, (T, B, Lf, R), ns="xiii-voile", exclusif=-1)
        g = Gtk.GestureClick(); g.connect("pressed", lambda *_: self.fermer()); self.voile.add_controller(g)
        self.voile.set_child(Gtk.Box())
        # barre des tâches
        self.barre = Gtk.Window(application=self); couche(self.barre, LS.Layer.TOP, (B, Lf, R), ns="xiii-barre", exclusif="auto")
        self.barre.set_default_size(-1, HB); self.construire_barre(); self.barre.present()
        # barre du haut
        self.haut = Gtk.Window(application=self); couche(self.haut, LS.Layer.TOP, (T, Lf, R), ns="xiii-haut", exclusif="auto")
        self.haut.set_default_size(-1, HH); self.construire_haut(); self.haut.present()
        # panneaux
        self.panneaux = {}
        defs = {
            "demarrer": (None, {B: HB + 10}, (B,)),
            "son": (P.Son, {T: HH + 8, R: 8}, (T, R)), "wifi": (P.Wifi, {T: HH + 8, R: 8}, (T, R)),
            "bluetooth": (P.Bluetooth, {T: HH + 8, R: 8}, (T, R)), "batterie": (P.Batterie, {T: HH + 8, R: 8}, (T, R)),
            "centre": (P.Centre, {T: HH + 8, R: 8}, (T, R)), "alim": (P.Alimentation, {T: HH + 8, R: 8}, (T, R)),
            "volet": (P.Volet, {T: HH + 8, B: HB + 10, R: 8}, (T, B, R)), "meteo": (P.Meteo, {B: HB + 10, Lf: 8}, (B, Lf)),
        }
        for nom, (cls, marges, ancres) in defs.items():
            w = Gtk.Window(application=self)
            couche(w, LS.Layer.OVERLAY, ancres, marges, LS.KeyboardMode.EXCLUSIVE if nom in ("demarrer", "wifi") else LS.KeyboardMode.ON_DEMAND, ns="xiii-" + nom)
            k = Gtk.EventControllerKey(); k.connect("key-pressed", self._touche); w.add_controller(k)
            if nom == "demarrer":
                self.menu = MenuDemarrer(self); w.set_child(self.menu.widget); obj = self.menu
            else:
                obj = cls(self); w.set_child(obj.widget)
            self.panneaux[nom] = (w, obj)
        # bulles de notification
        self.bulles = Gtk.Window(application=self)
        couche(self.bulles, LS.Layer.OVERLAY, (B, R), {B: HB + 10, R: 10}, ns="xiii-bulles")
        self.pile = boite(True, 8); self.bulles.set_child(self.pile)
        self.aligner_menu()

    def aligner_menu(self):
        w = self.panneaux["demarrer"][0]
        gauche = self.cfg["barre_alignement"] == "gauche"
        LS.set_anchor(w, LS.Edge.LEFT, gauche); LS.set_margin(w, LS.Edge.LEFT, 8 if gauche else 0)

    def _touche(self, ctrl, keyval, code, etat):
        if keyval == Gdk.KEY_Escape:
            self.fermer(); return True
        return False

    # ============================================================== ouverture / fermeture
    def basculer(self, nom):
        if nom == "demarrer-recherche":
            if self.ouvert != "demarrer": self.ouvrir("demarrer")
            self.menu.recherche.grab_focus(); return
        if nom == "demarrer-toutes":
            self.ouvrir("demarrer"); self.menu.vue("toutes"); return
        if self.ouvert == nom: self.fermer()
        else: self.ouvrir(nom)

    def ouvrir(self, nom):
        if nom not in self.panneaux: return
        self.fermer(garder_voile=True)
        w, obj = self.panneaux[nom]
        self.ouvert = nom
        self.voile.present()
        if nom == "meteo": obj.rendu(self._meteo)
        else: obj.rafraichir()
        w.present()
        for b in self.boutons_panneaux.get(nom, []): b.add_css_class("ouvert")

    def fermer(self, garder_voile=False):
        if self.ouvert:
            w, obj = self.panneaux[self.ouvert]; w.set_visible(False)
            for b in self.boutons_panneaux.get(self.ouvert, []): b.remove_css_class("ouvert")
            if self.ouvert == "demarrer": self.menu.reinitialiser()
        self.ouvert = None
        if not garder_voile: self.voile.set_visible(False)

    def parametres(self, page="accueil"):
        self.fermer()
        S.detacher(["xiii-parametres", "--page", page or "accueil"])

    # ============================================================== barre des tâches (bas)
    def construire_barre(self):
        cb = Gtk.CenterBox(); cb.add_css_class("barre"); cb.set_size_request(-1, HB)
        self.boutons_panneaux = {}
        # gauche : météo
        self.b_meteo = Gtk.Button(); self.b_meteo.add_css_class("tb"); self.b_meteo.set_margin_start(6)
        self.b_meteo.connect("clicked", lambda *_: self.basculer("meteo"))
        clic_droit(self.b_meteo, lambda: self.parametres("meteo"))
        self.boutons_panneaux["meteo"] = [self.b_meteo]
        # centre : Démarrer, recherche, applications
        self.groupe = boite(False, 2)
        self.b_start = Gtk.Button(); self.b_start.add_css_class("tb"); self.b_start.set_tooltip_text("Démarrer")
        logo = vignette("/usr/share/xiii/logos/xiii-orange.png", 28, 23, couvrir=False)
        logo.set_halign(Gtk.Align.CENTER); logo.set_valign(Gtk.Align.CENTER); self.b_start.set_child(logo)
        self.b_start.connect("clicked", lambda *_: self.basculer("demarrer"))
        clic_droit(self.b_start, lambda: popover_menu(self.b_start, [
            ("app-window", "Applications installées", lambda: self.parametres("apps")),
            ("gauge", "Bilan matériel", lambda: S.detacher("xiii-bilan")), ("cpu", "Pilotes", lambda: S.detacher("xiii-bilan --pilotes")),
            ("hard-drive", "Disques", lambda: S.detacher("gnome-disks")), ("wifi", "Réseau", lambda: self.parametres("reseau")),
            None, ("settings", "Paramètres", lambda: self.parametres("accueil")), ("folder", "Explorateur de fichiers", lambda: S.detacher("thunar")),
            None, ("log-out", "Se déconnecter", lambda: S.detacher("labwc --exit")), ("power", "Éteindre", lambda: S.detacher("systemctl poweroff"))]))
        self.boutons_panneaux["demarrer"] = [self.b_start]
        self.b_cherche = Gtk.Button(); self.b_cherche.add_css_class("tb"); self.b_cherche.set_tooltip_text("Rechercher")
        self.b_cherche.set_child(ico("search", 20)); self.b_cherche.connect("clicked", lambda *_: self.basculer("demarrer-recherche"))
        self.taches = boite(False, 2)
        for x in (self.b_start, self.b_cherche, self.taches): self.groupe.append(x)
        # droite : horloge + notifications
        droite = boite(False, 2, margin_end=6)
        self.b_heure = Gtk.Button(); self.b_heure.add_css_class("tb")
        hv = boite(True, 0, valign=Gtk.Align.CENTER)
        self.l_heure = label("", "horloge-h", xalign=1); self.l_date = label("", "horloge-d", xalign=1)
        hv.append(self.l_heure); hv.append(self.l_date); self.b_heure.set_child(hv)
        self.b_heure.connect("clicked", lambda *_: self.basculer("volet"))
        clic_droit(self.b_heure, lambda: self.parametres("heure"))
        self.b_cloche = Gtk.Button(); self.b_cloche.add_css_class("tb"); self.b_cloche.set_tooltip_text("Notifications")
        ov = Gtk.Overlay(); ov.set_child(ico("bell", 19))
        self.badge = label("", "badge", xalign=0.5); self.badge.set_halign(Gtk.Align.END); self.badge.set_valign(Gtk.Align.START)
        self.badge.set_visible(False); ov.add_overlay(self.badge); self.b_cloche.set_child(ov)
        self.b_cloche.connect("clicked", lambda *_: self.basculer("volet"))
        clic_droit(self.b_cloche, lambda: self.parametres("notifications"))
        self.boutons_panneaux["volet"] = [self.b_heure, self.b_cloche]
        droite.append(self.b_heure); droite.append(self.b_cloche)
        self.cb = cb; self.droite = droite
        self.placer_barre()
        self.barre.set_child(cb)

    def placer_barre(self):
        cb = self.cb
        cb.set_start_widget(None); cb.set_center_widget(None); cb.set_end_widget(None)
        for w in (self.groupe, self.b_meteo, self.droite):
            par = w.get_parent()
            if par is not None and hasattr(par, "remove"): par.remove(w)
        if self.cfg["barre_alignement"] == "gauche":
            self.groupe.set_margin_start(6); cb.set_start_widget(self.groupe)
            fin = boite(False, 4); fin.append(self.b_meteo); fin.append(self.droite); cb.set_end_widget(fin)
        else:
            self.groupe.set_margin_start(0); cb.set_start_widget(self.b_meteo); cb.set_center_widget(self.groupe); cb.set_end_widget(self.droite)
        self.b_meteo.set_visible(self.cfg["barre_meteo"]); self.b_cherche.set_visible(self.cfg["barre_recherche"])

    def maj_taches(self):
        if not hasattr(self, "taches"): return
        vider(self.taches)
        fen = self.fenetres.liste() if self.fenetres and self.fenetres.ok else []
        groupes = {}   # id d'appli -> [fenetres]
        info = {}
        for f in fen:
            a = apps.pour_fenetre(f.app_id)
            cle = a.get_id() if a else ("x:" + (f.app_id or f.titre))
            groupes.setdefault(cle, []).append(f); info[cle] = a
        ordre = [p for p in self.cfg["epingles"] if apps.par_id(p)] + [k for k in groupes if k not in self.cfg["epingles"]]
        for cle in ordre:
            a = info.get(cle) or (apps.par_id(cle) if not cle.startswith("x:") else None)
            fs = groupes.get(cle, [])
            self.taches.append(self.bouton_tache(cle, a, fs))
        self.maj_titre()

    def bouton_tache(self, cle, a, fs):
        b = Gtk.Button(); b.add_css_class("tb")
        actif = any(f.active for f in fs)
        if actif: b.add_css_class("actif")
        v = boite(True, 2, valign=Gtk.Align.CENTER)
        if a: im = gicon_image(a.get_icon(), 26)
        else: im = Gtk.Image.new_from_icon_name((fs[0].app_id if fs else "") or "application-x-executable"); im.set_pixel_size(26)
        v.append(im)
        ind = Gtk.Box(halign=Gtk.Align.CENTER); ind.add_css_class("tb-ind")
        if actif: ind.add_css_class("actif")
        elif not fs: ind.add_css_class("vide")
        v.append(ind); b.set_child(v)
        nom = a.get_display_name() if a else (fs[0].titre if fs else "")
        b.set_tooltip_text(fs[0].titre if len(fs) == 1 and fs[0].titre else nom + (" — %d fenêtres" % len(fs) if len(fs) > 1 else ""))
        def clic(*_):
            if not fs:
                if a: apps.lancer(a)
            elif len(fs) == 1:
                self.fenetres.clic(fs[0])
            else:
                popover_menu(b, [("app-window", (f.titre or nom)[:48], (lambda f=f: self.fenetres.activer(f))) for f in fs])
        b.connect("clicked", clic)
        if a: clic_milieu(b, lambda: apps.lancer(a))
        def menu():
            items = [("app-window", nom[:40], lambda: apps.lancer(a) if a else None)] if a else []
            if a:
                ep = cle in self.cfg["epingles"]
                items.append(("pin-off" if ep else "pin", "Désépingler de la barre" if ep else "Épingler à la barre", lambda: self.epingler(cle, not ep)))
            if fs:
                items.append(None)
                items.append(("x", "Fermer la fenêtre" if len(fs) == 1 else "Fermer toutes les fenêtres", lambda: [self.fenetres.fermer(f) for f in fs]))
            if items: popover_menu(b, items)
        clic_droit(b, menu)
        return b

    def epingler(self, cle, on, liste="epingles"):
        L = list(self.cfg[liste])
        if on and cle not in L: L.append(cle)
        if not on and cle in L: L.remove(cle)
        self.cfg = config.modifier(**{liste: L}); self.maj_taches()
        if liste == "menu_epingles": self.menu.remplir_epingles()

    # ============================================================== barre du haut
    def construire_haut(self):
        for k in ("wifi", "bluetooth", "son", "batterie", "centre", "alim"): self.boutons_panneaux.pop(k, None)
        cb = Gtk.CenterBox(); cb.add_css_class("haut"); cb.set_size_request(-1, HH)
        g = boite(False, 6, margin_start=8)
        lg = Gtk.Button(); lg.add_css_class("hb"); lg.set_child(label("XIII", "haut-logo")); lg.set_tooltip_text("À propos d'OS XIII")
        lg.connect("clicked", lambda *_: self.parametres("apropos"))
        g.append(lg)
        self.l_titre = label("", "haut-titre", ellipsize=True, largeur=60); g.append(self.l_titre)
        cb.set_start_widget(g)
        self.l_tournage = boite(False, 6, "carte", margin_top=3, margin_bottom=3)
        self.l_tournage.append(ico("clapperboard", 14, "c")); self.l_tournage.append(label("Mode tournage", "accent", "petit", "gras"))
        cb.set_center_widget(self.l_tournage)
        d = boite(False, 2, margin_end=6)
        def hb(nom, page, tip):
            b = Gtk.Button(); b.add_css_class("hb"); b.set_tooltip_text(tip + " — clic droit : paramètres")
            b.connect("clicked", lambda *_: self.basculer(nom)); clic_droit(b, lambda: self.parametres(page))
            self.boutons_panneaux.setdefault(nom, []).append(b); d.append(b); return b
        self.h_wifi = hb("wifi", "reseau", "Réseau"); self.h_bt = hb("bluetooth", "bluetooth", "Bluetooth")
        self.h_son = hb("son", "son", "Son"); self.h_bat = hb("batterie", "alimentation", "Énergie")
        self.h_dnd = ico("bell-off", 16, "d"); d.prepend(self.h_dnd)
        self.h_centre = hb("centre", "accueil", "Centre de contrôle"); self.h_centre.set_child(ico("sliders-horizontal", 16))
        self.h_alim = hb("alim", "alimentation", "Session"); self.h_alim.set_child(ico("power", 16, "c"))
        cb.set_end_widget(d)
        self.haut.set_child(cb)

    def maj_titre(self):
        f = self.fenetres.active() if self.fenetres and self.fenetres.ok else None
        self.l_titre.set_text(f.titre if (f and self.cfg["haut_titre"]) else "")

    def icones_bientot(self):
        if self._icones_src: GLib.source_remove(self._icones_src)
        def go():
            self._icones_src = 0; self.maj_icones(); return False
        self._icones_src = GLib.timeout_add(700, go)

    def maj_icones(self):
        S.en_fond(lambda: (S.etat_reseau(), S.wifi_actif(), S.bt_present(), S.bt_actif(), S.bt_appareils() if S.bt_actif() else [],
                           S.volume(), S.batterie()), self._rendu_icones)
        return True

    def _rendu_icones(self, r):
        if isinstance(r, Exception): return
        et, wifi, btp, bt, btd, (vol, muet), bat = r
        def met(b, icone, texte=None, role="t"):
            bx = boite(False, 5); bx.append(ico(icone, 16, role))
            if texte: bx.append(label(texte))
            b.set_child(bx)
        if et["avion"]: met(self.h_wifi, "plane", role="c")
        elif et["type"] == "ethernet": met(self.h_wifi, "ethernet-port")
        elif et["type"] == "wifi": met(self.h_wifi, icone_wifi(et["signal"]))
        else: met(self.h_wifi, "wifi-off" if not wifi else "wifi-zero", role="d")
        self.h_bt.set_visible(btp)
        met(self.h_bt, "bluetooth-connected" if any(d["connecte"] for d in btd) else ("bluetooth" if bt else "bluetooth-off"), role="t" if bt else "d")
        met(self.h_son, icone_volume(vol, muet), "%d%%" % vol if not muet else None)
        self.h_bat.set_visible(True)
        met(self.h_bat, icone_batterie(bat), ("%d%%" % bat["pct"]) if (bat and self.cfg["haut_pourcentage"]) else None,
            role="c" if bat and bat["pct"] < 15 and not bat["charge"] else "t")
        self.h_dnd.set_visible(self.cfg["ne_pas_deranger"])
        self.l_tournage.set_visible(self.cfg["mode_tournage"])

    # ============================================================== horloge & météo
    def tic(self):
        n = datetime.datetime.now()
        fmt = ("%H:%M" if self.cfg["horloge_24h"] else "%I:%M %p") + (":%S" if self.cfg["haut_secondes"] else "")
        self.l_heure.set_text(n.strftime(fmt)); self.l_date.set_text("%d %s %d" % (n.day, MOIS[n.month - 1], n.year))
        if self.fenetres: self.maj_titre()
        return True

    def maj_meteo(self):
        if not self.cfg["barre_meteo"]: return True
        S.en_fond(P.meteo, self._rendu_meteo, self.cfg["meteo_lat"], self.cfg["meteo_lon"])
        return True

    def _rendu_meteo(self, m):
        if isinstance(m, Exception) or not m:
            self.b_meteo.set_child(boite(False, 6)); self.b_meteo.get_child().append(ico("cloud-off" if os.path.exists(theme.LUCIDE + "/cloud-off.svg") else "cloud", 20, "d"))
            GLib.timeout_add_seconds(120, lambda: (self.maj_meteo(), False)[1]); return
        self._meteo = m
        ic, nom = P.METEO.get(m["code"], ("cloud", ""))
        bx = boite(False, 8, margin_start=4, margin_end=4); bx.append(ico(ic, 22, "c"))
        v = boite(True, 0, valign=Gtk.Align.CENTER); v.append(label("%d°C" % m["t"], "meteo-t")); v.append(label(nom, "horloge-d", ellipsize=True, largeur=16))
        bx.append(v); self.b_meteo.set_child(bx); self.b_meteo.set_tooltip_text("%s — %s" % (self.cfg["meteo_ville"], nom))

    # ============================================================== notifications
    def notif_nouvelle(self, n, remplacee):
        self.maj_badge()
        if n.app not in self._apps_notif:
            self._apps_notif.add(n.app)
            try:
                d = os.path.join(GLib.get_user_cache_dir(), "xiii"); os.makedirs(d, exist_ok=True)
                import json; json.dump(sorted(self._apps_notif), open(os.path.join(d, "notif-apps.json"), "w"))
            except Exception: pass
        if self.ouvert == "volet": self.panneaux["volet"][1].rafraichir()
        if (self.cfg["ne_pas_deranger"] and n.urgence < 2) or n.app in self.cfg["notif_bloquees"]: return
        if self.ouvert == "volet": return
        for c in list(self._enfants(self.pile)):
            if getattr(c, "nid", None) == n.id: self.pile.remove(c)
        c = P.carte_notif(n, self); c.nid = n.id
        self.pile.prepend(c)
        while len(self._enfants(self.pile)) > 3: self.pile.remove(self.pile.get_last_child())
        self.bulles.present()
        delai = n.delai if n.delai and n.delai > 0 else (12000 if n.urgence >= 2 else 6000)
        if n.urgence < 2 or n.delai > 0:
            GLib.timeout_add(delai, lambda: (self.retirer_bulle(n.id), False)[1])

    def _enfants(self, b):
        L = []; c = b.get_first_child()
        while c: L.append(c); c = c.get_next_sibling()
        return L

    def retirer_bulle(self, nid):
        for c in self._enfants(self.pile):
            if getattr(c, "nid", None) == nid: self.pile.remove(c)
        if not self._enfants(self.pile): self.bulles.set_visible(False)

    def notif_fermee(self, nid):
        self.retirer_bulle(nid); self.maj_badge()
        if self.ouvert == "volet": self.panneaux["volet"][1].rafraichir()

    def maj_badge(self):
        n = len(self.serveur.liste) if self.serveur else 0
        self.badge.set_text(str(n) if n < 100 else "99+"); self.badge.set_visible(n > 0 and self.cfg["barre_badge"])

    # ============================================================== réglages & services
    def cfg_change(self, cfg):
        ancien = self.cfg; self.cfg = cfg; self.p = theme.palette(cfg); couleurs(cfg)
        self.css.load_from_string(theme.css_shell(cfg))
        theme._cache.clear()
        if ancien["barre_alignement"] != cfg["barre_alignement"] or ancien["barre_meteo"] != cfg["barre_meteo"] or ancien["barre_recherche"] != cfg["barre_recherche"]:
            self.placer_barre(); self.aligner_menu()
        if (ancien["meteo_lat"], ancien["meteo_lon"]) != (cfg["meteo_lat"], cfg["meteo_lon"]): self.maj_meteo()
        if ancien["mode_tournage"] != cfg["mode_tournage"]: self.mode_tournage(cfg["mode_tournage"])
        # icônes teintées : reconstruire
        self.construire_haut(); self.b_cherche.set_child(ico("search", 20))
        ov = self.b_cloche.get_child(); ov.set_child(ico("bell", 19))
        self.maj_taches(); self.maj_icones(); self.maj_badge(); self.tic()
        if self._meteo: self._rendu_meteo(self._meteo)
        for nom, (w, obj) in self.panneaux.items():
            if nom == "demarrer":
                self.menu = MenuDemarrer(self); w.set_child(self.menu.widget); self.panneaux[nom] = (w, self.menu)
            else:
                o = type(obj)(self); w.set_child(o.widget); self.panneaux[nom] = (w, o)
                if self.ouvert == nom: o.rafraichir()
        self.services()

    def processus(self, nom, cmd):
        p = self.procs.get(nom)
        if p and p.poll() is None and getattr(p, "_cmd", None) == cmd: return
        self.arreter(nom)
        if cmd:
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); p._cmd = cmd; self.procs[nom] = p
            except OSError:
                pass

    def arreter(self, nom):
        p = self.procs.pop(nom, None)
        if p and p.poll() is None:
            p.terminate()
            try: p.wait(2)
            except Exception: p.kill()

    def services(self, premier=False):
        c = self.cfg
        if os.path.exists(c["fond"]):
            self.processus("fond", ["swaybg", "-m", c["fond_mode"], "-i", c["fond"]])
        if c["lumiere_nocturne"]:
            t = int(c["nocturne_temp"]); self.processus("nuit", ["wlsunset", "-t", str(t), "-T", str(t + 1), "-S", "00:00", "-s", "23:59", "-d", "60"])
        else:
            self.arreter("nuit")
        if c["mode_tournage"] or not c["verrou_actif"] or int(c["veille_ecran"]) <= 0:
            self.arreter("veille")
        else:
            self.processus("veille", ["swayidle", "-w", "timeout", str(int(c["veille_ecran"])), "swaylock -f", "before-sleep", "swaylock -f"])
        self.processus("disques", ["udiskie", "--no-tray", "--notify"] + ([] if c["montage_auto"] else ["--no-automount"]))
        if premier:
            for nom, e in (c.get("ecrans") or {}).items():
                S.en_fond(S.regler_ecran, None, nom, e.get("w"), e.get("h"), e.get("hz"), e.get("echelle"), e.get("rotation"))
            if c["mode_tournage"]: self.mode_tournage(True)

    def mode_tournage(self, on):
        if on:
            S.en_fond(S.regler_profil, None, "performance")
            config.modifier(ne_pas_deranger=True)
            S.detacher(["notify-send", "-a", "OS XIII", "-i", "camera-video", "Mode tournage activé",
                        "Performances maximales, notifications en silence, pas de mise en veille."])
        else:
            S.en_fond(S.regler_profil, None, "balanced")
            config.modifier(ne_pas_deranger=False)

    def do_shutdown(self):
        for n in list(self.procs): self.arreter(n)
        Gtk.Application.do_shutdown(self)

# ======================================================================================================== MENU DÉMARRER
class MenuDemarrer:
    COLS = 6
    def __init__(self, shell):
        self.shell = shell
        w = boite(True, 12, "panneau"); w.set_size_request(640, 680); self.widget = w
        self.recherche = Gtk.Entry(placeholder_text="Rechercher des applications, des paramètres, des fichiers…", hexpand=True)
        self.recherche.add_css_class("recherche")
        self.recherche.set_icon_from_paintable(Gtk.EntryIconPosition.PRIMARY, theme.icone("search", 16, ACC["d"]))
        self.recherche.connect("changed", self.chercher); self.recherche.connect("activate", self.valider)
        w.append(self.recherche)
        self.pile = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT if shell.cfg["animations"] else Gtk.StackTransitionType.NONE)
        w.append(self.pile)
        # --- accueil
        acc = boite(True, 10)
        h = boite(False, 6); h.append(label("Épinglées", "gras", hexpand=True))
        h.append(bouton("Toutes les applications", "chevron-right", "fantome", taille=14, rappel=lambda: self.vue("toutes"))); acc.append(h)
        self.grille_ep = self.flow(self.COLS); acc.append(self.grille_ep)
        self.bloc_rec = boite(True, 8)
        h2 = boite(False, 6); h2.append(label("Recommandés", "gras", hexpand=True)); self.bloc_rec.append(h2)
        self.grille_rec = Gtk.FlowBox(max_children_per_line=2, min_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=4, homogeneous=True)
        self.bloc_rec.append(self.grille_rec); acc.append(self.bloc_rec)
        self.pile.add_named(acc, "accueil")
        # --- toutes (catégories / A-Z)
        tt = boite(True, 10)
        h = boite(False, 6)
        h.append(bouton("Retour", "chevron-left", "fantome", taille=14, rappel=lambda: self.vue("accueil")))
        h.append(label("Toutes les applications", "gras", hexpand=True, xalign=0.5))
        self.seg_cat = Gtk.ToggleButton(label="Catégories"); self.seg_az = Gtk.ToggleButton(label="A – Z", group=self.seg_cat)
        for s in (self.seg_cat, self.seg_az): s.add_css_class("fantome")
        self.seg_cat.connect("toggled", lambda b: b.get_active() and self.sous.set_visible_child_name("cats"))
        self.seg_az.connect("toggled", lambda b: b.get_active() and self.sous.set_visible_child_name("az"))
        sg = boite(False, 4); sg.append(self.seg_cat); sg.append(self.seg_az); h.append(sg); tt.append(h)
        self.sous = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.grille_cat = Gtk.FlowBox(max_children_per_line=3, min_children_per_line=3, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, homogeneous=True, valign=Gtk.Align.START)
        self.sous.add_named(defilant(self.grille_cat), "cats")
        self.liste_az = boite(True, 2); self.sous.add_named(defilant(self.liste_az), "az")
        tt.append(self.sous); self.pile.add_named(tt, "toutes")
        # --- une catégorie
        cv = boite(True, 10)
        h = boite(False, 6); h.append(bouton("Catégories", "chevron-left", "fantome", taille=14, rappel=lambda: self.vue("toutes")))
        self.titre_cat = label("", "panneau-titre", hexpand=True, xalign=0.5); h.append(self.titre_cat); h.append(Gtk.Box(width_request=100)); cv.append(h)
        self.grille_une = self.flow(self.COLS); cv.append(defilant(self.grille_une)); self.pile.add_named(cv, "cat")
        # --- résultats
        self.res = boite(True, 4); self.pile.add_named(defilant(self.res), "res")
        # --- pied
        pied = boite(False, 8, "menu-pied")
        u = pwd.getpwuid(os.getuid()); nom = (u.pw_gecos.split(",")[0] or u.pw_name)
        ub = Gtk.Button(); ub.add_css_class("ligne"); ub.add_css_class("plat")
        ux = boite(False, 10); av = Gtk.Overlay(); av.add_css_class("avatar")
        face = os.path.expanduser("~/.face")
        if os.path.exists(face):
            av.set_child(vignette(face, 34, 34))
        else:
            av.set_child(label(nom[:1].upper(), xalign=0.5))
        av.set_size_request(34, 34); ux.append(av); ux.append(label(nom, "gras")); ub.set_child(ux)
        ub.connect("clicked", lambda *_: shell.parametres("compte")); pied.append(ub); pied.append(Gtk.Box(hexpand=True))
        for ic, tip, rap in (("folder", "Fichiers", lambda: (shell.fermer(), S.detacher("thunar"))),
                             ("settings", "Paramètres", lambda: shell.parametres("accueil"))):
            pied.append(bouton(None, ic, "plat", taille=18, tip=tip, rappel=rap))
        self.b_power = bouton(None, "power", "plat", taille=18, role="c", tip="Marche / arrêt")
        self.b_power.connect("clicked", lambda *_: popover_menu(self.b_power, [
            ("lock", "Verrouiller", lambda: (shell.fermer(), S.detacher("swaylock -f"))), ("moon", "Mettre en veille", lambda: (shell.fermer(), S.detacher("systemctl suspend"))),
            ("log-out", "Se déconnecter", lambda: S.detacher("labwc --exit")), None,
            ("rotate-ccw", "Redémarrer", lambda: S.detacher("systemctl reboot")), ("power", "Éteindre", lambda: S.detacher("systemctl poweroff"))]))
        pied.append(self.b_power); w.append(pied)
        self.remplir_epingles(); self.remplir_toutes()
        self.pile.set_visible_child_name("accueil")

    def flow(self, cols):
        return Gtk.FlowBox(max_children_per_line=cols, min_children_per_line=cols, selection_mode=Gtk.SelectionMode.NONE,
                           column_spacing=4, row_spacing=4, homogeneous=True, valign=Gtk.Align.START)

    def tuile_app(self, a, liste="menu_epingles"):
        b = Gtk.Button(); b.add_css_class("app")
        v = boite(True, 6); v.append(gicon_image(a.get_icon(), 34))
        n = label(a.get_display_name(), "app-nom", xalign=0.5, ellipsize=True); n.set_max_width_chars(11); v.append(n)
        b.set_child(v); b.set_tooltip_text(a.get_description() or a.get_display_name())
        b.connect("clicked", lambda *_: self.lancer(a))
        clic_droit(b, lambda: self.menu_app(b, a))
        return b

    def menu_app(self, b, a):
        cle = a.get_id(); c = self.shell.cfg
        em, eb = cle in c["menu_epingles"], cle in c["epingles"]
        popover_menu(b, [("app-window", "Ouvrir", lambda: self.lancer(a)),
                         ("pin-off" if em else "pin", "Désépingler du menu" if em else "Épingler au menu", lambda: self.shell.epingler(cle, not em, "menu_epingles")),
                         ("pin-off" if eb else "panel-bottom", "Désépingler de la barre" if eb else "Épingler à la barre des tâches", lambda: self.shell.epingler(cle, not eb, "epingles")),
                         None, ("trash-2", "Désinstaller…", lambda: self.shell.parametres("apps"))])

    def lancer(self, a):
        self.shell.fermer(); apps.lancer(a)

    def rafraichir(self):
        self.remplir_epingles()
        GLib.idle_add(lambda: (self.recherche.grab_focus(), False)[1])

    def remplir_epingles(self):
        vider(self.grille_ep)
        for i in self.shell.cfg["menu_epingles"]:
            a = apps.par_id(i)
            if a: self.grille_ep.append(self.tuile_app(a))
        vider(self.grille_rec)
        rec = apps.recents(6) if self.shell.cfg["menu_recommandes"] else []
        self.bloc_rec.set_visible(bool(rec) or self.shell.cfg["menu_recommandes"])
        if not rec:
            self.grille_rec.append(label("Vos fichiers récents apparaîtront ici.", "attenue", "petit"))
        for f in rec:
            b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
            bx = boite(False, 10); bx.append(gicon_image(apps.icone_fichier(f), 28))
            v = boite(True, 0); v.append(label(os.path.basename(f), ellipsize=True, largeur=26))
            try: t = os.path.getmtime(f)
            except OSError: t = time.time()
            v.append(label(P.depuis(t), "attenue", "petit")); bx.append(v); b.set_child(bx)
            b.connect("clicked", lambda _b, f=f: (self.shell.fermer(), apps.ouvrir_fichier(f)))
            self.grille_rec.append(b)

    def remplir_toutes(self):
        vider(self.grille_cat); vider(self.liste_az)
        for cle, nom, ic, L in apps.par_categorie():
            b = Gtk.Button(); b.add_css_class("cat")
            v = boite(True, 8)
            h = boite(False, 8); h.append(ico(ic, 18, "c")); h.append(label(nom, "cat-nom", hexpand=True, ellipsize=True))
            h.append(label(str(len(L)), "attenue", "petit")); v.append(h)
            g = Gtk.Grid(column_spacing=6, row_spacing=6, halign=Gtk.Align.CENTER)
            for i, a in enumerate(L[:4]): g.attach(gicon_image(a.get_icon(), 30), i % 2, i // 2, 1, 1)
            v.append(g); b.set_child(v)
            b.connect("clicked", lambda _b, n=nom, L=L: self.ouvrir_cat(n, L))
            self.grille_cat.append(b)
        lettre = None
        for a in apps.toutes():
            l = sans_accents(a.get_display_name()[:1]).upper()
            l = l if l.isalpha() else "#"
            if l != lettre:
                lettre = l; self.liste_az.append(label(l, "accent", "gras", margin_top=6, margin_start=10))
            b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
            bx = boite(False, 12); bx.append(gicon_image(a.get_icon(), 26)); bx.append(label(a.get_display_name(), ellipsize=True))
            b.set_child(bx); b.connect("clicked", lambda _b, a=a: self.lancer(a)); clic_droit(b, lambda b=b, a=a: self.menu_app(b, a))
            self.liste_az.append(b)
        (self.seg_cat if self.shell.cfg["menu_vue"] != "az" else self.seg_az).set_active(True)
        self.sous.set_visible_child_name("cats" if self.shell.cfg["menu_vue"] != "az" else "az")

    def ouvrir_cat(self, nom, L):
        self.titre_cat.set_text(nom); vider(self.grille_une)
        for a in L: self.grille_une.append(self.tuile_app(a))
        self.vue("cat")

    def vue(self, v):
        self.pile.set_visible_child_name(v)

    def reinitialiser(self):
        self.recherche.set_text(""); self.pile.set_visible_child_name("accueil")

    # ---------------------------------------------------- recherche
    def chercher(self, *_):
        q = sans_accents(self.recherche.get_text().strip())
        if not q:
            self.vue("accueil"); return
        vider(self.res); self._premier = None
        trouves = [a for a in apps.toutes() if q in sans_accents(a.get_display_name()) or q in sans_accents(a.get_description() or "")
                   or q in sans_accents(" ".join(a.get_keywords() or []) if hasattr(a, "get_keywords") else "")]
        trouves.sort(key=lambda a: (not sans_accents(a.get_display_name()).startswith(q), a.get_display_name()))
        # calcul
        expr = self.recherche.get_text().strip().lstrip("=").replace(",", ".").replace("x", "*").replace("÷", "/")
        if expr and all(c in "0123456789.+-*/() %" for c in expr) and any(c in expr for c in "+-*/%") and any(c.isdigit() for c in expr):
            try:
                r = eval(expr, {"__builtins__": {}}, {})
                r = ("%.10g" % r).replace(".", ",")
                self.res.append(label("Calculatrice", "section"))
                b = bouton("%s = %s" % (self.recherche.get_text().strip(), r), "calculator", "ligne", "plat", taille=18,
                           rappel=lambda r=r: (Gdk.Display.get_default().get_clipboard().set_text(r), self.shell.fermer()))
                b.set_tooltip_text("Copier le résultat"); self.res.append(b)
            except Exception:
                pass
        if trouves:
            self.res.append(label("Applications", "section"))
            for a in trouves[:8]:
                b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                bx = boite(False, 12); bx.append(gicon_image(a.get_icon(), 28))
                v = boite(True, 0); v.append(label(a.get_display_name(), "gras")); v.append(label(a.get_description() or "Application", "attenue", "petit", ellipsize=True, largeur=60))
                bx.append(v); b.set_child(bx); b.connect("clicked", lambda _b, a=a: self.lancer(a)); self.res.append(b)
                if not self._premier: self._premier = lambda a=a: self.lancer(a)
        from .pages_index import INDEX
        pg = [(cle, t, ic, chemin) for cle, t, ic, chemin, mots in INDEX if q in sans_accents(t + " " + mots)]
        if pg:
            self.res.append(label("Paramètres", "section"))
            for cle, t, ic, chemin in pg[:6]:
                b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                bx = boite(False, 12); bx.append(ico(ic, 22, "c"))
                v = boite(True, 0); v.append(label(t, "gras")); v.append(label(chemin, "attenue", "petit")); bx.append(v); b.set_child(bx)
                b.connect("clicked", lambda _b, c=cle: self.shell.parametres(c)); self.res.append(b)
                if not self._premier: self._premier = lambda c=cle: self.shell.parametres(c)
        fic = [f for f in apps.recents(30) if q in sans_accents(os.path.basename(f))]
        if fic:
            self.res.append(label("Fichiers récents", "section"))
            for f in fic[:5]:
                b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                bx = boite(False, 12); bx.append(gicon_image(apps.icone_fichier(f), 24))
                v = boite(True, 0); v.append(label(os.path.basename(f))); v.append(label(os.path.dirname(f).replace(os.path.expanduser("~"), "~"), "attenue", "petit", ellipsize=True)); bx.append(v)
                b.set_child(bx); b.connect("clicked", lambda _b, f=f: (self.shell.fermer(), apps.ouvrir_fichier(f))); self.res.append(b)
        self.res.append(label("Web", "section"))
        brut = self.recherche.get_text().strip()
        self.res.append(bouton("Rechercher « %s » sur le Web" % brut, "globe", "ligne", "plat", taille=18,
                               rappel=lambda: (self.shell.fermer(), S.detacher(["xdg-open", "https://duckduckgo.com/?q=" + GLib.uri_escape_string(brut, None, False)]))))
        if not self._premier:
            self._premier = lambda: (self.shell.fermer(), S.detacher(["xdg-open", "https://duckduckgo.com/?q=" + GLib.uri_escape_string(brut, None, False)]))
        self.vue("res")

    def valider(self, *_):
        if self.recherche.get_text().strip() and getattr(self, "_premier", None):
            self._premier()

def main():
    os.environ.pop("LD_PRELOAD", None)   # la bibliothèque est chargée ; ne pas la transmettre aux applis lancées
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Shell().run(sys.argv[:1])
