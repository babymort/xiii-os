# OS XIII — le bureau : barre des tâches (bas, façon Windows 11), barre du haut (réglages rapides),
# menu Démarrer avec catégories, panneaux rapides, notifications, fond d'écran, veille, lumière nocturne.
# Application développée par Matthieu Lamotte.
import os, sys, time, datetime, subprocess, signal, pwd, unicodedata
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from gi.repository import Gtk4LayerShell as LS
from . import config, theme, systeme as S, apps, notifs, panneaux as P, widgets as W, profils, vues, tray, claude
from .bureau import Bureau
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
        Gtk.Settings.get_default().set_property("gtk-icon-theme-name", theme.nom_icones(self.cfg))
        for nom, typ in (("basculer", "s"), ("fermer", None), ("parametres", "s")):
            a = Gio.SimpleAction.new(nom, GLib.VariantType.new(typ) if typ else None)
            a.connect("activate", getattr(self, "_act_" + nom)); self.add_action(a)
        self.creer_fenetres()
        self.serveur = notifs.Serveur(self.notif_nouvelle, self.notif_fermee)
        from .miniatures import Miniatures
        self.miniatures = Miniatures(self); self.progres = {}
        self.fenetres = Gestionnaire(self.maj_taches)
        self.ecouter_progres()
        if not S.DEMO: S.detacher(["xiii-lecteurs", "--monter-tout"])      # NAS et clouds reconnectés
        if self.cfg.get("decklink_pont") and not S.DEMO:      # pont DeckLink → caméra virtuelle
            try:
                from . import acquisition as A
                if A.pilote_blackmagic() and A.camera_virtuelle() and not A.pont_actif():
                    A.pont_demarrer(int(self.cfg.get("decklink_entree", 0)), self.cfg.get("decklink_mode", "auto"))
            except Exception:
                pass
        self.zone = tray.Zone(self.maj_zone)
        self.mon = config.surveiller(self.cfg_change)
        self.services(premier=True)
        theme.appliquer_systeme(self.cfg) if not os.path.exists(os.path.join(config.DOSSIER, ".applique")) else None
        try: open(os.path.join(config.DOSSIER, ".applique"), "w").close()
        except OSError: pass
        GLib.timeout_add_seconds(1, self.tic)
        GLib.timeout_add_seconds(6, self.maj_icones)
        GLib.timeout_add_seconds(1800, self.maj_meteo)
        self.maj_icones(); self.maj_meteo(); self.maj_taches(); self.tic(); self.demarrer_timecode()
        if not self.cfg.get("visite_faite") and not os.path.isdir("/run/live/medium"):
            GLib.timeout_add_seconds(3, lambda: (self.visite(), False)[1])

    def visite(self):
        from .visite import Visite, etapes
        if not getattr(self, "_visite", None): self._visite = Visite(self)
        self._visite.L = etapes(self)
        self._visite.lancer()

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
            "volet": (P.Volet, {T: HH + 8, B: HB + 10, R: 8}, (T, B, R)), "widgets": (W.Tableau, {T: HH + 8, B: HB + 10, Lf: 8}, (T, B, Lf)),
            "presse": (vues.PressePapiers, {B: HB + 10}, (B,)), "emoji": (vues.Emojis, {B: HB + 10}, (B,)),
        }
        for nom, (cls, marges, ancres) in defs.items():
            w = Gtk.Window(application=self)
            couche(w, LS.Layer.OVERLAY, ancres, marges, LS.KeyboardMode.EXCLUSIVE if nom in ("demarrer", "wifi", "presse", "emoji") else LS.KeyboardMode.ON_DEMAND, ns="xiii-" + nom)
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
        self.vue_taches = vues.VueTaches(self); self.dispositions = vues.Dispositions(self); self.coins = vues.Coins(self)
        self.bureau = Bureau(self)
        from .modes import VueMode
        self.vue_mode = VueMode(self); self.appliquer_mode(self.cfg.get("mode_bureau", "classique"), premier=True)

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
        if nom == "meteo": nom = "widgets"
        if nom == "vue":
            self.fermer(); self.vue_taches.ouvrir(); return
        if nom == "dispositions":
            self.fermer(); self.dispositions.ouvrir(); return
        if nom == "bureau":
            self.fermer(); self.afficher_bureau(); return
        if nom == "visite":
            self.fermer(); self.visite(); return
        if nom == "visite-suivant":
            if getattr(self, "_visite", None): self._visite.suivant()
            return
        if nom == "demarrer-toutes":
            self.ouvrir("demarrer"); self.menu.vue("toutes"); return
        if self.ouvert == nom: self.fermer()
        else: self.ouvrir(nom)

    def ouvrir(self, nom):
        if nom not in self.panneaux: return
        self.fermer(garder_voile=True)
        self.bulles.set_visible(False)
        w, obj = self.panneaux[nom]
        self.ouvert = nom
        self.voile.present()
        obj.rafraichir()
        if self.cfg.get("animations", True):
            w.set_opacity(0); w.present(); self.fondu(w)
        else:
            w.set_opacity(1); w.present()
        for b in self.boutons_panneaux.get(nom, []): b.add_css_class("ouvert")

    def fondu(self, w, duree=140):
        """Ouverture des panneaux en fondu (comme les panneaux de la suite) ; désactivée par « Animations »."""
        t0 = GLib.get_monotonic_time()
        def pas(*_):
            k = min(1, (GLib.get_monotonic_time() - t0) / (duree * 1000))
            w.set_opacity(1 - (1 - k) ** 3)
            return k < 1
        GLib.timeout_add(16, pas)

    def fermer(self, garder_voile=False):
        for v in ("vue_taches", "dispositions"):
            if hasattr(self, v): getattr(self, v).fermer()
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
        self.b_meteo.connect("clicked", lambda *_: self.basculer("widgets"))
        self.b_meteo.set_tooltip_text("Widgets")
        clic_droit(self.b_meteo, lambda: self.parametres("widgets"))
        self.boutons_panneaux["widgets"] = [self.b_meteo]
        # centre : Démarrer, recherche, applications
        self.groupe = boite(False, 2)
        self.b_start = Gtk.Button(); self.b_start.add_css_class("tb"); self.b_start.set_tooltip_text("Démarrer")
        logo = vignette("/usr/share/xiii/logos/xiii-orange.png", 27, 22, couvrir=False, echelle=1)
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
        self.b_vue = Gtk.Button(); self.b_vue.add_css_class("tb"); self.b_vue.set_tooltip_text("Vue des tâches (Super + Tab)")
        self.b_vue.set_child(ico("layout-dashboard", 19)); self.b_vue.connect("clicked", lambda *_: self.basculer("vue"))
        clic_droit(self.b_vue, lambda: self.basculer("dispositions"))
        self.taches = boite(False, 2)
        for x in (self.b_start, self.b_cherche, self.b_vue, self.taches): self.groupe.append(x)
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
        self.zone_notif = boite(False, 0); droite.append(self.zone_notif)
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
        if hasattr(self, "miniatures"): self.miniatures.changement(fen)
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

    def ecouter_progres(self):
        """Progression sous les icônes de la barre (com.canonical.Unity.LauncherEntry, comme Ubuntu / KDE)."""
        try:
            from gi.repository import Gio
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception:
            return
        def signal(conn, exp, chemin, iface, nom, params):
            try:
                uri, props = params.unpack()
                did = uri.replace("application://", "")
                if props.get("progress-visible") is False or ("progress" not in props and "progress-visible" in props): self.progres.pop(did, None)
                elif "progress" in props: self.progres[did] = float(props["progress"])
                GLib.idle_add(lambda: (self.maj_taches(), False)[1])
            except Exception:
                pass
        bus.signal_subscribe(None, "com.canonical.Unity.LauncherEntry", "Update", None, None, 0, signal)

    def bouton_tache(self, cle, a, fs):
        b = Gtk.Button(); b.add_css_class("tb")
        actif = any(f.active for f in fs)
        if actif: b.add_css_class("actif")
        v = boite(True, 2, valign=Gtk.Align.CENTER)
        if a: im = gicon_image(a.get_icon(), 26)
        else: im = Gtk.Image.new_from_icon_name((fs[0].app_id if fs else "") or "application-x-executable"); im.set_pixel_size(26)
        nom = a.get_display_name() if a else (fs[0].titre if fs else "")
        if self.cfg.get("barre_style") == "onglets" and fs:     # style « onglets » : icône + titre
            b.add_css_class("tb-onglet")
            h = boite(False, 8); im.set_pixel_size(20); h.append(im)
            h.append(label((fs[0].titre if len(fs) == 1 and fs[0].titre else nom) + (" (%d)" % len(fs) if len(fs) > 1 else ""), "petit", ellipsize=True, largeur=18))
            v.append(h)
        else:
            v.append(im)
        pr = self.progres.get(a.get_id()) if a else None
        if pr is not None:                                       # progression (somme, téléchargements…)
            pb = Gtk.ProgressBar(fraction=max(0, min(1, pr)), halign=Gtk.Align.CENTER); pb.set_size_request(26, -1); pb.add_css_class("tb-progres"); v.append(pb)
        else:
            ind = Gtk.Box(halign=Gtk.Align.CENTER); ind.add_css_class("tb-ind")
            if actif: ind.add_css_class("actif")
            elif not fs: ind.add_css_class("vide")
            v.append(ind)
        b.set_child(v)
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
        if fs and self.cfg.get("apercu_survol", True):
            m = Gtk.EventControllerMotion(); etat = {"src": 0, "pop": None}
            def entre(*_):
                def montre():
                    etat["src"] = 0
                    if etat["pop"] or self.ouvert: return False
                    pop = Gtk.Popover(has_arrow=False, autohide=False); pop.set_parent(b); pop.set_position(Gtk.PositionType.TOP)
                    v = boite(True, 6, margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
                    for f in fs:
                        c = boite(True, 6, "carte"); c.set_size_request(220, -1)
                        h = boite(False, 8); h.append(gicon_image(a.get_icon(), 16) if a else ico("app-window", 16)); h.append(label(f.titre or nom, "petit", "gras", hexpand=True, ellipsize=True, largeur=28))
                        h.append(bouton(None, "x", "plat", taille=12, role="d", rappel=lambda f=f: (self.fenetres.fermer(f), pop.popdown()))); c.append(h)
                        mp = self.miniatures.chemin(f) if hasattr(self, "miniatures") else None
                        if mp:
                            pic = Gtk.Picture.new_for_filename(mp); pic.set_content_fit(Gtk.ContentFit.COVER); pic.set_size_request(220, 124); pic.add_css_class("miniature"); c.append(pic)
                        g = Gtk.GestureClick(); g.connect("released", lambda *_x, f=f: (pop.popdown(), self.fenetres.activer(f))); c.add_controller(g)
                        v.append(c)
                    pop.set_child(v); pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1])); etat["pop"] = pop; pop.popup()
                    return False
                etat["src"] = GLib.timeout_add(650, montre)
            def sort(*_):
                if etat["src"]: GLib.source_remove(etat["src"]); etat["src"] = 0
                if etat["pop"]:
                    p = etat["pop"]; etat["pop"] = None
                    GLib.timeout_add(350, lambda: (p.popdown(), False)[1])
            m.connect("enter", entre); m.connect("leave", sort); b.add_controller(m)
        return b

    def maj_zone(self):
        vider(self.zone_notif)
        for cle, it in list(self.zone.items.items()):
            if it.get("statut") != "Passive": self.zone_notif.append(self.zone.bouton(cle))

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
        g = boite(False, 4, margin_start=6)
        # secteur 1 : accueil · logo · projet (comme la barre du haut de la suite : 🏠 · logo · document)
        g.append(self.bouton_survol("house", "Démarrer", lambda: self.basculer("demarrer")))
        lg = Gtk.Button(); lg.add_css_class("hb"); lg.set_child(label("XIII", "haut-logo")); lg.set_tooltip_text("À propos d'OS XIII")
        lg.connect("clicked", lambda *_: self.parametres("apropos"))
        g.append(lg)
        self.b_projet = Gtk.Button(); self.b_projet.add_css_class("hb"); self.b_projet.set_tooltip_text("Projet XIII actif")
        pj = boite(False, 6); pj.append(ico("folder-kanban", 14, "c")); pj.append(label(self.cfg.get("projet_actif") or "Choisir un projet", "accent" if self.cfg.get("projet_actif") else "attenue", "petit", "gras")); self.b_projet.set_child(pj)
        self.b_projet.connect("clicked", lambda *_: self.menu_projets())
        g.append(self.b_projet)
        self.l_titre = label("", "haut-titre", ellipsize=True, largeur=60, margin_start=6); g.append(self.l_titre)
        cb.set_start_widget(g)
        centre = boite(False, 10)
        centre.append(self.selecteur_modes())
        pr = profils.courant(self.cfg)
        self.l_tournage = Gtk.Button(); self.l_tournage.add_css_class("hb"); self.l_tournage.set_tooltip_text("Profil de travail — clic : changer")
        lt = boite(False, 6); lt.append(ico(pr[2], 14, "c")); lt.append(label("Profil " + pr[1], "accent", "petit", "gras")); self.l_tournage.set_child(lt)
        self.l_tournage.connect("clicked", lambda *_: self.menu_profils(self.l_tournage))
        centre.append(self.l_tournage)
        self.l_tc = label("", "timecode"); centre.append(self.l_tc)
        cb.set_center_widget(centre)
        d = boite(False, 2, margin_end=6)
        # secteur 2 : rechercher · Suite XIII · fichiers · Claude (libellés au survol, comme dans la suite)
        outils = boite(False, 2)
        outils.append(self.bouton_survol("search", "Rechercher", lambda: self.basculer("demarrer-recherche")))
        outils.append(self.bouton_survol("layout-grid", "Suite XIII", lambda: S.detacher(["xiii-suite"])))
        outils.append(self.bouton_survol("folder-open", "Fichiers", lambda: S.detacher(["xiii-fichiers", os.path.join(os.path.expanduser("~/XIII"), self.cfg["projet_actif"]) if self.cfg.get("projet_actif") and os.path.isdir(os.path.join(os.path.expanduser("~/XIII"), self.cfg["projet_actif"])) else os.path.expanduser("~")])))
        outils.append(self.bouton_survol("sparkles", "Claude", lambda: S.detacher("claude-desktop")))
        d.append(outils)
        etat = boite(False, 2); etat.add_css_class("haut-secteur"); d.append(etat)
        def hb(nom, page, tip):
            b = Gtk.Button(); b.add_css_class("hb"); b.set_tooltip_text(tip + " — clic droit : paramètres")
            b.connect("clicked", lambda *_: self.basculer(nom)); clic_droit(b, lambda: self.parametres(page))
            self.boutons_panneaux.setdefault(nom, []).append(b); etat.append(b); return b
        self.h_dnd = ico("bell-off", 16, "d"); etat.append(self.h_dnd)
        self.h_wifi = hb("wifi", "reseau", "Réseau"); self.h_bt = hb("bluetooth", "bluetooth", "Bluetooth")
        self.h_son = hb("son", "son", "Son"); self.h_bat = hb("batterie", "alimentation", "Énergie")
        self.h_centre = hb("centre", "accueil", "Centre de contrôle"); self.h_centre.set_child(ico("sliders-horizontal", 16))
        # secteur 3 : pastille du nom (comme la suite) et session
        fin = boite(False, 4); fin.add_css_class("haut-secteur"); d.append(fin)
        u = pwd.getpwuid(os.getuid()); nomu = (u.pw_gecos.split(",")[0] or u.pw_name).strip()
        pn = Gtk.Button(); pn.add_css_class("hb"); pn.set_tooltip_text("Votre compte")
        pb = boite(False, 0); pb.add_css_class("pastille-nom"); pb.append(label(nomu.split()[0][:14] if nomu else "Moi")); pn.set_child(pb)
        pn.connect("clicked", lambda *_: popover_menu(pn, [("user", "Votre compte", lambda: self.parametres("compte")), ("palette", "Thème et couleurs", lambda: self.parametres("theme")),
                                                          ("clapperboard", "Profil de travail", lambda: self.menu_profils(pn)), None, ("lock", "Verrouiller", lambda: S.detacher("swaylock -f"))]))
        fin.append(pn)
        self.h_alim = Gtk.Button(); self.h_alim.add_css_class("hb"); self.h_alim.set_tooltip_text("Session — clic droit : paramètres")
        self.h_alim.connect("clicked", lambda *_: self.basculer("alim")); clic_droit(self.h_alim, lambda: self.parametres("alimentation"))
        self.boutons_panneaux.setdefault("alim", []).append(self.h_alim); self.h_alim.set_child(ico("power", 16, "c")); fin.append(self.h_alim)
        cb.set_end_widget(d); self.zone_haut = d
        self.haut.set_child(cb)

    def selecteur_modes(self):
        """Modes d'utilisation (en haut au centre) : icônes, libellé du mode actif."""
        from .modes import MODES
        self.sel_mode = boite(False, 2, "sel-mode"); self.remplir_selecteur()
        return self.sel_mode

    def remplir_selecteur(self):
        """Menu déroulant des modes, au style de la Suite XIII : pastille du mode actif + flèche, liste au clic."""
        from .modes import MODES, PAR_CLE
        sel = self.sel_mode; vider(sel)
        cur = self.cfg.get("mode_bureau", "classique"); _, nom, ic, desc, _p = PAR_CLE.get(cur, MODES[0])
        b = Gtk.Button(); b.add_css_class("plat"); b.add_css_class("actif"); b.set_tooltip_text("Mode d'utilisation — " + desc)
        bx = boite(False, 6); bx.append(ico(ic, 14, "c")); bx.append(label(nom, "petit", "gras", "accent")); bx.append(ico("chevron-down", 12, "d")); b.set_child(bx)
        def ouvrir(_b):
            pop = Gtk.Popover(has_arrow=False); pop.set_parent(b); pop.set_position(Gtk.PositionType.BOTTOM); pop.add_css_class("menu-modes")
            v = boite(True, 2, margin_top=8, margin_bottom=8, margin_start=8, margin_end=8); v.set_size_request(340, -1)
            v.append(label("Mode d'utilisation", "section", margin_start=8))
            for k, n, i2, d, _pp in MODES:
                it = Gtk.Button(); it.add_css_class("ligne"); it.add_css_class("plat")
                if k == cur: it.add_css_class("mode-actif")
                r = boite(False, 12); r.append(ico(i2, 20, "c" if k == cur else "t"))
                col = boite(True, 0, hexpand=True); col.append(label(n, "gras")); col.append(label(d, "petit", "attenue", wrap=True, largeur=36)); r.append(col)
                if k == cur: r.append(ico("check", 16, "c"))
                it.set_child(r); it.connect("clicked", lambda _x, k=k: (pop.popdown(), config.modifier(mode_bureau=k))); v.append(it)
            pop.set_child(v); pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1])); pop.popup()
        b.connect("clicked", ouvrir); sel.append(b)

    def appliquer_mode(self, k, premier=False):
        from .modes import PAR_CLE
        k = k if k in PAR_CLE else "classique"
        self.vue_mode.appliquer(k)
        self.bureau.w.set_visible(k == "classique" and bool(self.cfg.get("icones_bureau", True)))
        prof = PAR_CLE[k][4]
        avant = getattr(self, "_mode_prec", None); self._mode_prec = k
        if not premier and avant != k:
            # le profil suit le mode : Tournage (Fiction, Multicam), Jeu (Gaming), retour à Normal en quittant ces modes
            if prof: config.modifier(profil=prof)
            elif avant and PAR_CLE.get(avant, (0, 0, 0, 0, None))[4]: config.modifier(profil="normal", mode_tournage=False)
        if k in ("fiction", "multicam") and not self.cfg.get("timecode"): config.modifier(_histo=False, timecode=True)
        if k == "gaming" and (not premier or avant is None): S.detacher("xiii-console")      # l'interface console plein écran

    def menu_projets(self):
        """Sélecteur de projet (en haut à gauche, comme la suite) : changer, créer, ajouter depuis un fichier .xiii."""
        from . import projets
        pop = Gtk.Popover(has_arrow=False); pop.set_parent(self.b_projet); pop.set_position(Gtk.PositionType.BOTTOM)
        v = boite(True, 4, margin_top=8, margin_bottom=8, margin_start=8, margin_end=8); v.set_size_request(300, -1)
        cur = self.cfg.get("projet_actif", "")
        v.append(label("Projets", "section"))
        for p in projets.liste()[:12]:
            b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
            bx = boite(False, 8); bx.append(ico("check" if p == cur else "folder", 16, "c" if p == cur else "d")); bx.append(label(p, "gras" if p == cur else "", hexpand=True, ellipsize=True)); b.set_child(bx)
            b.connect("clicked", lambda _b, p=p: (pop.popdown(), projets.activer(p))); v.append(b)
        e = Gtk.Entry(placeholder_text="Nouveau projet…"); e.set_icon_from_paintable(Gtk.EntryIconPosition.PRIMARY, theme.icone("plus", 14, ACC["d"]))
        e.connect("activate", lambda w: (pop.popdown(), projets.activer(w.get_text())) if w.get_text().strip() else None); v.append(e)
        def depuis_fichier():
            pop.popdown()
            d = Gtk.FileDialog(title="Ajouter un projet depuis un fichier .xiii")
            ff = Gtk.FileFilter(); ff.set_name("Fichiers XIII"); [ff.add_pattern(x) for x in ("*.xiii", "*.xiii.json", "*.json")]
            st = Gio.ListStore.new(Gtk.FileFilter); st.append(ff); d.set_filters(st)
            def fini(dlg, res):
                try: f = dlg.open_finish(res).get_path()
                except Exception: return
                n = projets.importer(f)
                if n: S.detacher(["notify-send", "-a", "Projet XIII", "-i", "folder", "Projet « %s » activé" % n, "Le fichier a été rangé dans 03_Documents."])
            d.open(None, None, fini)
        v.append(bouton("Ajouter depuis un fichier .xiii…", "file-plus", "ligne", "plat", taille=16, rappel=depuis_fichier))
        if cur:
            v.append(Gtk.Separator())
            v.append(bouton("Ouvrir le dossier du projet", "folder-open", "ligne", "plat", taille=16, rappel=lambda: (pop.popdown(), S.detacher(["thunar", os.path.join(projets.BASE, cur)]))))
            v.append(bouton("Widgets du projet", "layout-dashboard", "ligne", "plat", taille=16, rappel=lambda: (pop.popdown(), self.basculer("widgets"))))
        v.append(bouton("Gérer les projets", "settings", "ligne", "plat", taille=16, rappel=lambda: (pop.popdown(), self.parametres("projet"))))
        pop.set_child(v); pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1])); pop.popup()

    def bouton_survol(self, icone, texte, rappel):
        """Bouton icône dont le libellé glisse au survol (barre du haut de la suite)."""
        b = Gtk.Button(); b.add_css_class("hb"); b.set_tooltip_text(texte)
        bx = boite(False, 0); bx.append(ico(icone, 16))
        rv = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_RIGHT, transition_duration=160 if self.cfg.get("animations", True) else 0)
        rv.set_child(label(texte, "haut-survol")); bx.append(rv); b.set_child(bx)
        mv = Gtk.EventControllerMotion(); mv.connect("enter", lambda *_: rv.set_reveal_child(True)); mv.connect("leave", lambda *_: rv.set_reveal_child(False)); b.add_controller(mv)
        b.connect("clicked", lambda *_: rappel())
        return b

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
        style = self.cfg.get("indic_style", "icone")
        def met(b, icone, texte=None, role="t", valeur=None):
            """valeur 0..1 (signal, volume, charge) : dessinée selon le style choisi (Paramètres › Barre du haut)."""
            bx = boite(False, 5, valign=Gtk.Align.CENTER)
            if valeur is not None and style == "rond":
                bx.append(jauge_ronde(valeur, ico(icone, 11, role)))
            elif valeur is not None and style == "minimal":
                bx.append(label("%d%%" % round(valeur * 100), "petit", "gras"))
            else:
                bx.append(ico(icone, 16, role))
                if valeur is not None and style == "barre":
                    pb = Gtk.ProgressBar(fraction=valeur, valign=Gtk.Align.CENTER); pb.add_css_class("indic-barre"); pb.set_size_request(24, -1); bx.append(pb)
                elif valeur is not None and style == "pourcentage" and not texte:
                    texte = "%d%%" % round(valeur * 100)
            if texte and not (valeur is not None and style in ("rond", "minimal", "barre")): bx.append(label(texte))
            b.set_child(bx)
        if et["avion"]: met(self.h_wifi, "plane", role="c")
        elif et["type"] == "ethernet": met(self.h_wifi, "ethernet-port")
        elif et["type"] == "wifi": met(self.h_wifi, icone_wifi(et["signal"]), valeur=et["signal"] / 100)
        else: met(self.h_wifi, "wifi-off" if not wifi else "wifi-zero", role="d")
        self.h_bt.set_visible(btp)
        met(self.h_bt, "bluetooth-connected" if any(d["connecte"] for d in btd) else ("bluetooth" if bt else "bluetooth-off"), role="t" if bt else "d")
        met(self.h_son, icone_volume(vol, muet), "%d%%" % vol if not muet else None, valeur=None if muet else vol / 100)
        self.h_bat.set_visible(True)
        met(self.h_bat, icone_batterie(bat), ("%d%%" % bat["pct"]) if (bat and self.cfg["haut_pourcentage"]) else None,
            role="c" if bat and bat["pct"] < 15 and not bat["charge"] else "t", valeur=bat["pct"] / 100 if bat else None)
        self.h_dnd.set_visible(self.cfg["ne_pas_deranger"])
        self.l_tournage.set_visible(profils.courant(self.cfg)[0] != "normal")

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
        bx.append(v); self.b_meteo.set_child(bx); self.b_meteo.set_tooltip_text("Widgets — %s, %s" % (self.cfg["meteo_ville"], nom))

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
        if getattr(self, "_visite", None) and self._visite.win.get_visible(): return
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
        ancien = self.cfg
        if ancien["theme"] != cfg["theme"] or ancien.get("theme_perso") != cfg.get("theme_perso") or (ancien["accent"] != cfg["accent"] and theme.fond_par_defaut(cfg["fond"])):
            f = theme.fond_assorti(cfg)
            if f != cfg["fond"]:
                config.modifier(fond=f); return
            theme.appliquer_systeme(cfg)
        if ancien["accent"] != cfg["accent"] and not os.environ.get("XIII_PARAM"):
            theme.appliquer_systeme(cfg)
        self.cfg = cfg; self.p = theme.palette(cfg); couleurs(cfg)
        Gtk.Settings.get_default().set_property("gtk-icon-theme-name", theme.nom_icones(cfg))
        self.css.load_from_string(theme.css_shell(cfg))
        theme._cache.clear()
        if ancien["barre_alignement"] != cfg["barre_alignement"] or ancien["barre_meteo"] != cfg["barre_meteo"] or ancien["barre_recherche"] != cfg["barre_recherche"]:
            self.placer_barre(); self.aligner_menu()
        if (ancien["meteo_lat"], ancien["meteo_lon"]) != (cfg["meteo_lat"], cfg["meteo_lon"]): self.maj_meteo()
        if profils.courant(ancien)[0] != profils.courant(cfg)[0]: self.appliquer_profil(profils.courant(cfg)[0])
        if hasattr(self, "coins"): self.coins.maj()
        if hasattr(self, "bureau"): self.bureau.maj()
        if ancien.get("barre_style") != cfg.get("barre_style"): self.maj_taches()
        if ancien.get("indic_style") != cfg.get("indic_style"): self.maj_icones()
        if ancien.get("mode_bureau") != cfg.get("mode_bureau") and hasattr(self, "vue_mode"):
            self.appliquer_mode(cfg.get("mode_bureau", "classique"))
            if hasattr(self, "sel_mode"): self.remplir_selecteur()
        if ancien.get("projet_actif") != cfg.get("projet_actif") and hasattr(self, "b_projet"):
            pj = boite(False, 6); pj.append(ico("folder-kanban", 14, "c"))
            pj.append(label(cfg.get("projet_actif") or "Choisir un projet", "accent" if cfg.get("projet_actif") else "attenue", "petit", "gras")); self.b_projet.set_child(pj)
        # icônes teintées : reconstruire
        self.construire_haut(); self.demarrer_timecode(); self.b_cherche.set_child(ico("search", 20)); self.b_vue.set_child(ico("layout-dashboard", 19))
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
        if profils.eveil(c):
            self.arreter("veille")
        else:
            cmd = ["swayidle", "-w"]
            if c.get("veille_mode", "aucun") != "aucun" and int(c.get("veille_delai", 0)) > 0:
                cmd += ["timeout", str(int(c["veille_delai"])), "xiii-veille", "resume", "pkill -f xiii.veille"]
            if c["verrou_actif"] and int(c["veille_ecran"]) > 0:
                cmd += ["timeout", str(int(c["veille_ecran"])), "pkill -f xiii.veille; swaylock -f"]
            cmd += ["before-sleep", "swaylock -f"]
            self.processus("veille", cmd)
        self.processus("disques", ["udiskie", "--no-tray", "--notify"] + ([] if c["montage_auto"] else ["--no-automount"]))
        if premier:
            for nom, e in (c.get("ecrans") or {}).items():
                S.en_fond(S.regler_ecran, None, nom, e.get("w"), e.get("h"), e.get("hz"), e.get("echelle"), e.get("rotation"))
            if profils.courant(c)[0] != "normal": self.appliquer_profil(profils.courant(c)[0], silencieux=True)
            if c.get("reprise_session"): GLib.timeout_add_seconds(4, lambda: (self.reprendre_session(), False)[1])
            if c.get("jeu_console") and profils.courant(c)[0] == "jeu": S.detacher(["steam", "-gamepadui"])
        GLib.timeout_add_seconds(60, self.memoriser_session) if premier else None
        if premier:
            self._auto = theme.theme_effectif(c); GLib.timeout_add_seconds(300, self.theme_auto)

    def theme_auto(self):
        """Thème Auto : passe au clair au lever du soleil, au sombre au coucher."""
        if self.cfg.get("theme") == "auto":
            e = theme.theme_effectif(self.cfg)
            if e != getattr(self, "_auto", e):
                self._auto = e; c = self.cfg
                f = theme.fond_assorti(c)
                if f != c["fond"]: config.modifier(fond=f)
                theme.appliquer_systeme(c); self.p = theme.palette(c); couleurs(c); self.css.load_from_string(theme.css_shell(c))
            self._auto = e
        return True

    # ============================================================== profils de travail
    def menu_profils(self, parent):
        items = [(ic, ("● " if self.cfg.get("profil", "normal") == k else "") + nom + " — " + desc, (lambda k=k: config.modifier(profil=k, mode_tournage=(k == "tournage"))))
                 for k, nom, ic, desc, _ in profils.PROFILS]
        popover_menu(parent, items + [None, ("settings", "Régler les profils", lambda: self.parametres("profils"))])

    def appliquer_profil(self, k, silencieux=False):
        _, nom, ic, desc, r = profils.PAR_CLE.get(k, profils.PROFILS[0])
        S.en_fond(S.regler_profil, None, r.get("perf", "balanced"))
        kw = dict(ne_pas_deranger=r.get("dnd", False))
        if r.get("nuit") is not None: kw["lumiere_nocturne"] = r["nuit"]
        if any(self.cfg.get(x) != v for x, v in kw.items()): config.modifier(_histo=False, **kw)
        if r.get("jeu") and self.cfg.get("jeu_console") and not silencieux: S.detacher(["steam", "-gamepadui"])
        if not silencieux:
            S.detacher(["notify-send", "-a", "OS XIII", "-i", "preferences-system", "Profil " + nom, desc])

    def mode_tournage(self, on):
        config.modifier(profil="tournage" if on else "normal", mode_tournage=on)

    # ============================================================== timecode
    def demarrer_timecode(self):
        if getattr(self, "_tc_src", 0): GLib.source_remove(self._tc_src); self._tc_src = 0
        on = bool(self.cfg.get("timecode")); self.l_tc.set_visible(on)
        if not on: return
        fps = int(self.cfg.get("timecode_fps", 25)) or 25
        def tic():
            t = time.time(); lt = time.localtime(t)
            self.l_tc.set_text("%02d:%02d:%02d:%02d" % (lt.tm_hour, lt.tm_min, lt.tm_sec, int((t % 1) * fps)))
            return True
        self._tc_src = GLib.timeout_add(int(1000 / fps), tic); tic()

    # ============================================================== reprise de session
    def memoriser_session(self):
        try:
            ids = []
            for f in (self.fenetres.liste() if self.fenetres and self.fenetres.ok else []):
                a = apps.pour_fenetre(f.app_id)
                if a and a.get_id() not in ids and not a.get_id().startswith(("xiii-", "fr.xiii")): ids.append(a.get_id())
            d = os.path.join(GLib.get_user_cache_dir(), "xiii"); os.makedirs(d, exist_ok=True)
            import json; json.dump(ids, open(os.path.join(d, "session.json"), "w"))
        except Exception:
            pass
        return True

    def reprendre_session(self):
        import json
        try: ids = json.load(open(os.path.join(GLib.get_user_cache_dir(), "xiii", "session.json")))
        except Exception: return
        ouverts = {apps.pour_fenetre(f.app_id).get_id() for f in (self.fenetres.liste() if self.fenetres and self.fenetres.ok else []) if apps.pour_fenetre(f.app_id)}
        for i in ids:
            a = apps.par_id(i)
            if a and i not in ouverts: apps.lancer(a)

    # ============================================================== bureau
    def afficher_bureau(self):
        fen = self.fenetres.liste() if self.fenetres and self.fenetres.ok else []
        if all(f.reduite for f in fen) and getattr(self, "_reduites", None):
            for f in self._reduites: self.fenetres.activer(f)
            self._reduites = None
        else:
            self._reduites = [f for f in fen if not f.reduite]
            for f in self._reduites: self.fenetres.reduire(f)

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
        # filtres de recherche (Super + Espace) : Tout · Fichiers · Applications · IA
        self.mode = "tout"; filt = boite(False, 6); prem = None
        for cle, nom, ic in (("tout", "Tout", "search"), ("fichiers", "Fichiers", "file"), ("apps", "Applications", "layout-grid"), ("ia", "IA", "sparkles")):
            t = Gtk.ToggleButton(group=prem); t.add_css_class("fantome"); t.add_css_class("filtre-recherche")
            bx = boite(False, 6); bx.append(ico(ic, 14, "c")); bx.append(label(nom, "petit")); t.set_child(bx)
            if not prem: prem = t; t.set_active(True)
            t.connect("toggled", lambda b, c=cle: b.get_active() and (setattr(self, "mode", c), self.chercher() if self.recherche.get_text().strip() else None))
            filt.append(t)
        self.filtres = filt; w.append(filt)
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

    def avec_apercu(self, b, f):
        """Ligne de résultat fichier + bouton œil (aperçu rapide sans ouvrir)."""
        r = boite(False, 4); b.set_hexpand(True); r.append(b)
        r.append(bouton(None, "eye", "plat", taille=16, role="d", tip="Aperçu rapide", rappel=lambda: (self.shell.fermer(), S.detacher(["xiii-apercu", f]))))
        return r

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
        mode = getattr(self, "mode", "tout")
        if mode == "ia":
            brut = self.recherche.get_text().strip()
            self.res.append(label("Demander à une IA", "section"))
            for nom, ic, fn in (("Claude", "sparkles", lambda: claude.demander(brut)),
                                ("ChatGPT", "message-circle", lambda: S.detacher(["xdg-open", "https://chatgpt.com/?q=" + GLib.uri_escape_string(brut, None, False)])),
                                ("Gemini", "gem", lambda: S.detacher(["xdg-open", "https://gemini.google.com/app?q=" + GLib.uri_escape_string(brut, None, False)]))):
                self.res.append(bouton("%s : « %s »" % (nom, brut), ic, "ligne", "plat", taille=18, rappel=lambda f=fn: (self.shell.fermer(), f())))
            self._premier = lambda: (self.shell.fermer(), claude.demander(brut)); self.vue("res"); return
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
        if mode == "fichiers": trouves = []
        if trouves:
            self.res.append(label("Applications", "section"))
            for a in trouves[:8]:
                b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                bx = boite(False, 12); bx.append(gicon_image(a.get_icon(), 28))
                v = boite(True, 0); v.append(label(a.get_display_name(), "gras")); v.append(label(a.get_description() or "Application", "attenue", "petit", ellipsize=True, largeur=60))
                bx.append(v); b.set_child(bx); b.connect("clicked", lambda _b, a=a: self.lancer(a)); self.res.append(b)
                if not self._premier: self._premier = lambda a=a: self.lancer(a)
        from .pages_index import INDEX
        pg = [(cle, t, ic, chemin) for cle, t, ic, chemin, mots in INDEX if q in sans_accents(t + " " + mots)] if mode in ("tout", "apps") else []
        if pg:
            self.res.append(label("Paramètres", "section"))
            for cle, t, ic, chemin in pg[:6]:
                b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                bx = boite(False, 12); bx.append(ico(ic, 22, "c"))
                v = boite(True, 0); v.append(label(t, "gras")); v.append(label(chemin, "attenue", "petit")); bx.append(v); b.set_child(bx)
                b.connect("clicked", lambda _b, c=cle: self.shell.parametres(c)); self.res.append(b)
                if not self._premier: self._premier = lambda c=cle: self.shell.parametres(c)
        fic = [f for f in apps.recents(30) if q in sans_accents(os.path.basename(f))] if mode in ("tout", "fichiers") else []
        if fic:
            self.res.append(label("Fichiers récents", "section"))
            for f in fic[:5]:
                b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                bx = boite(False, 12); bx.append(gicon_image(apps.icone_fichier(f), 24))
                v = boite(True, 0); v.append(label(os.path.basename(f))); v.append(label(os.path.dirname(f).replace(os.path.expanduser("~"), "~"), "attenue", "petit", ellipsize=True)); bx.append(v)
                b.set_child(bx); b.connect("clicked", lambda _b, f=f: (self.shell.fermer(), apps.ouvrir_fichier(f))); self.res.append(self.avec_apercu(b, f))
        if len(q) >= (2 if mode == "fichiers" else 3) and not S.DEMO and mode in ("tout", "fichiers"):
            maison = os.path.expanduser("~")
            tout_pc = mode == "fichiers"          # filtre Fichiers : tout le PC (disques et clés montés compris)
            trouves_f = [l for l in S.out(["plocate", "-i", "-l", "200" if tout_pc else "40", "--", self.recherche.get_text().strip()], 2).splitlines()
                         if (l.startswith(maison + "/") and "/." not in l[len(maison):] or tout_pc and l.startswith(("/media/", "/mnt/", "/run/media/", "/srv/")))
                         and l not in fic][:20 if tout_pc else 6]
            if trouves_f:
                self.res.append(label("Fichiers", "section"))
                for f in trouves_f:
                    b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                    bx = boite(False, 12); bx.append(gicon_image(apps.icone_fichier(f), 24))
                    v = boite(True, 0); v.append(label(os.path.basename(f))); v.append(label(os.path.dirname(f).replace(maison, "~"), "attenue", "petit", ellipsize=True)); bx.append(v)
                    b.set_child(bx); b.connect("clicked", lambda _b, f=f: (self.shell.fermer(), apps.ouvrir_fichier(f))); self.res.append(self.avec_apercu(b, f))
        if mode != "tout":
            if self.res.get_first_child() is None: self.res.append(label("Aucun résultat.", "attenue"))
            self.vue("res"); return
        self.res.append(label("Web et assistant", "section"))
        brut0 = self.recherche.get_text().strip()
        self.res.append(bouton("Demander à Claude : « %s »" % brut0, "sparkles", "ligne", "plat", taille=18,
                               rappel=lambda: (self.shell.fermer(), claude.demander(brut0))))
        brut = self.recherche.get_text().strip()
        self.res.append(bouton("Rechercher « %s » sur le Web" % brut, "globe", "ligne", "plat", taille=18,
                               rappel=lambda: (self.shell.fermer(), S.detacher(["xdg-open", "https://duckduckgo.com/?q=" + GLib.uri_escape_string(brut, None, False)]))))
        if not self._premier:
            self._premier = lambda: (self.shell.fermer(), S.detacher(["xdg-open", "https://duckduckgo.com/?q=" + GLib.uri_escape_string(brut, None, False)]))
        self.vue("res")

    def valider(self, *_):
        if self.recherche.get_text().strip() and getattr(self, "_premier", None):
            self._premier()

def jauge_ronde(valeur, centre=None, taille=20):
    """Petite jauge circulaire (style « rond » des indicateurs)."""
    o = Gtk.Overlay(); da = Gtk.DrawingArea(); da.set_size_request(taille, taille)
    def dessin(a, cr, w, h):
        import math
        c = a.get_color(); acc = Gdk.RGBA(); acc.parse(ACC.get("c", "#f0b378"))
        r = min(w, h) / 2 - 1.5; cr.set_line_width(2.2)
        cr.set_source_rgba(c.red, c.green, c.blue, .22); cr.arc(w / 2, h / 2, r, 0, 2 * math.pi); cr.stroke()
        cr.set_source_rgba(acc.red, acc.green, acc.blue, 1); cr.arc(w / 2, h / 2, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * max(0, min(1, valeur))); cr.stroke()
    da.set_draw_func(dessin); o.set_child(da)
    if centre: o.add_overlay(centre)
    return o

def main():
    os.environ.pop("LD_PRELOAD", None)   # la bibliothèque est chargée ; ne pas la transmettre aux applis lancées
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Shell().run(sys.argv[:1])
