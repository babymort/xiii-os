# OS XIII — panneaux rapides de la barre du haut (son, Wi-Fi, Bluetooth, batterie, centre de contrôle,
# alimentation), météo, volet de notifications et bulles.
# Clic gauche = réglage rapide ; clic droit = page complète des Paramètres.
# Application développée par Matthieu Lamotte.
import time, datetime, json, urllib.request, urllib.parse, os, re
from gi.repository import Gtk, GLib, Gio, Gdk, Pango
from . import systeme as S, config, apps, profils, theme
from .ui import *

def entete(icone, titre, shell, page, droite=None):
    h = boite(False, 10)
    h.append(ico(icone, 22, "c"))
    h.append(label(titre, "panneau-titre", ellipsize=True))
    sp = Gtk.Box(hexpand=True); h.append(sp)
    if droite: h.append(droite)
    if page:
        b = bouton(None, "settings", "plat", taille=16, role="d", tip="Ouvrir les paramètres", rappel=lambda: shell.parametres(page))
        h.append(b)
    return h

def pied_lien(texte, rappel):
    b = bouton(texte, "chevron-right", "plat", "ligne", taille=14, role="d", rappel=rappel)
    b.set_halign(Gtk.Align.END)
    return b

class Panneau:
    largeur = 360
    def __init__(self, shell):
        self.shell = shell
        self.widget = boite(True, 12, "panneau")
        self.widget.set_size_request(self.largeur, -1)
        self.construire()
    def construire(self): pass
    def rafraichir(self): pass

# =================================================================================== SON
class Son(Panneau):
    def construire(self):
        w = self.widget
        w.append(entete("volume-2", "Son", self.shell, "son"))
        w.append(label("Sortie", "section"))
        r = boite(False, 8)
        self.b_muet = bouton(None, "volume-2", "plat", taille=18, rappel=self.muet, tip="Couper / rétablir le son")
        self.s_vol = curseur(50, lambda v: (S.en_fond(S.regler_volume, None, v), self.n_vol.set_text("%d %%" % v), self.shell.icones_bientot()))
        self.n_vol = label("50 %", "niveau", xalign=1)
        r.append(self.b_muet); r.append(self.s_vol); r.append(self.n_vol); w.append(r)
        self.l_sorties = boite(True, 2); w.append(self.l_sorties)
        w.append(label("Entrée", "section"))
        r2 = boite(False, 8)
        r2.append(ico("mic", 18, "t"))
        self.s_in = curseur(50, lambda v: (S.en_fond(S.regler_entree, None, v), self.n_in.set_text("%d %%" % v)))
        self.n_in = label("50 %", "niveau", xalign=1)
        r2.append(self.s_in); r2.append(self.n_in); w.append(r2)
        self.l_entrees = boite(True, 2); w.append(self.l_entrees)
        self.t_apps = label("Mélangeur des applications", "section"); w.append(self.t_apps)
        self.l_apps = boite(True, 6); w.append(self.l_apps)
        w.append(pied_lien("Plus de réglages du son", lambda: self.shell.parametres("son")))

    def muet(self):
        S.en_fond(S.basculer_muet, lambda _: self.rafraichir())

    def rafraichir(self):
        S.en_fond(lambda: (S.sorties(), S.entrees(), S.flux_apps()), self._rendu)

    def _rendu(self, r):
        if isinstance(r, Exception): return
        so, en, fl = r
        d = next((s for s in so if s["defaut"]), so[0] if so else None)
        if d:
            self.s_vol.poser(d["vol"]); self.n_vol.set_text("%d %%" % d["vol"])
            self.b_muet.set_child(ico(icone_volume(d["vol"], d["muet"]), 18, "c" if d["muet"] else "t"))
        de = next((s for s in en if s["defaut"]), en[0] if en else None)
        if de: self.s_in.poser(de["vol"]); self.n_in.set_text("%d %%" % de["vol"])
        multi = any(x.get("multi") and x["defaut"] for x in so)
        so = [x for x in so if not x.get("multi")]
        for liste, items, fn in ((self.l_sorties, so, S.sortie_defaut), (self.l_entrees, en, S.entree_defaut)):
            vider(liste)
            if liste is self.l_sorties and len(items) > 1:
                # plusieurs sorties en même temps : cases à cocher (sortie combinée)
                choisies = set(self.shell.cfg.get("sorties_multiples", [])) if multi else set()
                sw = Gtk.CheckButton(label="Plusieurs sorties en même temps", active=multi); sw.add_css_class("petit")
                def bascule(w, items=items):
                    if w.get_active():
                        noms = [x["nom"] for x in items][:2]
                        config.modifier(_histo=False, sorties_multiples=noms); S.en_fond(S.sorties_multiples, lambda _: self.rafraichir(), noms)
                    else:
                        config.modifier(_histo=False, sorties_multiples=[]); S.en_fond(S.sorties_multiples, lambda _: self.rafraichir(), [])
                sw.connect("toggled", bascule); liste.append(sw)
                if multi:
                    for it in items:
                        c = Gtk.CheckButton(label=it["desc"], active=it["nom"] in choisies)
                        def coche(w, n=it["nom"]):
                            noms = [x for x in self.shell.cfg.get("sorties_multiples", []) if x != n] + ([n] if w.get_active() else [])
                            config.modifier(_histo=False, sorties_multiples=noms); S.en_fond(S.sorties_multiples, lambda _: self.rafraichir(), noms)
                        c.connect("toggled", coche); liste.append(c)
                    continue
            if not items:
                liste.append(label("Aucun périphérique", "attenue", "petit")); continue
            for it in items:
                b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                if it["defaut"]: b.add_css_class("sel")
                bx = boite(False, 10)
                bx.append(ico("check" if it["defaut"] else "circle", 14, "c" if it["defaut"] else "d"))
                bx.append(label(it["desc"], ellipsize=True, largeur=36))
                b.set_child(bx)
                b.connect("clicked", lambda _b, n=it["nom"], f=fn: S.en_fond(f, lambda _: self.rafraichir(), n))
                liste.append(b)
        vider(self.l_apps)
        self.t_apps.set_visible(bool(fl))
        for f in fl:
            r = boite(False, 8)
            a = apps.par_id((f["icone"] or "") + ".desktop")
            r.append(gicon_image(a.get_icon() if a else Gio.ThemedIcon.new(f["icone"] or "application-x-executable"), 18))
            r.append(label(f["nom"], "petit", ellipsize=True, largeur=10))
            s = curseur(f["vol"], lambda v, i=f["idx"]: S.en_fond(S.regler_flux, None, i, v))
            r.append(s); self.l_apps.append(r)

# =================================================================================== WI-FI
class Wifi(Panneau):
    def construire(self):
        w = self.widget
        self.sw = interrupteur(True, self.basculer)
        w.append(entete("wifi", "Wi-Fi", self.shell, "wifi", self.sw))
        self.etat = boite(False, 10, "carte"); w.append(self.etat)
        self.titre_liste = label("Réseaux disponibles", "section"); w.append(self.titre_liste)
        self.liste = boite(True, 2)
        w.append(defilant(self.liste, 330))
        bas = boite(False, 6)
        self.b_scan = bouton("Actualiser", "refresh-cw", "fantome", taille=14, rappel=lambda: self.rafraichir(True))
        bas.append(self.b_scan); bas.append(Gtk.Box(hexpand=True))
        bas.append(pied_lien("Paramètres réseau", lambda: self.shell.parametres("wifi")))
        w.append(bas)
        self.ouvert = None

    def basculer(self, on):
        S.en_fond(S.wifi_activer, lambda _: (self.rafraichir(), self.shell.icones_bientot()), on)

    def rafraichir(self, rescan=False):
        self.b_scan.set_sensitive(False)
        S.en_fond(lambda: (S.wifi_actif(), S.reseaux_wifi(rescan), S.etat_reseau()), self._rendu)

    def _rendu(self, r):
        self.b_scan.set_sensitive(True)
        if isinstance(r, Exception): return
        on, res, et = r
        self.sw.poser(on)
        vider(self.etat)
        if et["type"]:
            self.etat.append(ico("ethernet-port" if et["type"] == "ethernet" else icone_wifi(et["signal"]), 22, "c"))
            v = boite(True, 0); v.append(label(et["nom"] or "Connecté", "gras", ellipsize=True))
            v.append(label(("Câble · " if et["type"] == "ethernet" else "Connecté · ") + (et["ip"] or ""), "attenue", "petit"))
            self.etat.append(v)
        else:
            self.etat.append(ico("wifi-off", 22, "d")); self.etat.append(label("Non connecté" if on else "Wi-Fi désactivé", "attenue"))
        vider(self.liste)
        self.titre_liste.set_visible(on)
        if not on:
            return
        if not res:
            self.liste.append(label("Recherche des réseaux…", "attenue", "petit")); return
        for n in res:
            self.liste.append(self._ligne(n))

    def _ligne(self, n):
        v = boite(True, 4)
        b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
        if n["actif"]: b.add_css_class("sel")
        bx = boite(False, 10)
        bx.append(ico(icone_wifi(n["signal"]), 18, "c" if n["actif"] else "t"))
        t = boite(True, 0)
        t.append(label(n["ssid"], ellipsize=True, largeur=24))
        t.append(label(("Connecté" if n["actif"] else "Enregistré" if n["connu"] else ("Sécurisé" if n["secu"] else "Ouvert")) +
                       (" · %s" % n["secu"] if n["secu"] else ""), "attenue", "petit"))
        bx.append(t); bx.append(Gtk.Box(hexpand=True))
        if n["secu"]: bx.append(ico("lock", 14, "d"))
        b.set_child(bx); v.append(b)
        zone = boite(False, 6, margin_start=36, margin_bottom=6); zone.set_visible(False); v.append(zone)
        def clic(*_):
            if n["actif"]:
                vider(zone)
                zone.append(bouton("Déconnecter", None, "fantome", rappel=lambda: S.en_fond(S.wifi_deconnecter, lambda _: self.rafraichir())))
                zone.append(bouton("Oublier", None, "plat", rappel=lambda: S.en_fond(S.wifi_oublier, lambda _: self.rafraichir(), n["ssid"])))
                zone.set_visible(not zone.get_visible()); return
            if n["secu"] and not n["connu"]:
                vider(zone)
                e = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True, placeholder_text="Mot de passe")
                go = bouton("Connecter", None, "pilule")
                msg = label("", "attenue", "petit")
                def connecter(*_):
                    go.set_sensitive(False); go.set_label("Connexion…")
                    S.en_fond(S.wifi_connecter, fini, n["ssid"], e.get_text())
                def fini(res):
                    ok, m = res if not isinstance(res, Exception) else (False, str(res))
                    if ok: self.rafraichir(); self.shell.icones_bientot()
                    else: go.set_sensitive(True); go.set_label("Connecter"); msg.set_text("Échec : mot de passe incorrect ?")
                e.connect("activate", connecter); go.connect("clicked", connecter)
                zone.append(e); zone.append(go)
                zone.set_visible(True); e.grab_focus()
                return
            b.set_sensitive(False)
            S.en_fond(S.wifi_connecter, lambda _: (self.rafraichir(), self.shell.icones_bientot()), n["ssid"])
        b.connect("clicked", clic)
        return v

# =================================================================================== BLUETOOTH
class Bluetooth(Panneau):
    def construire(self):
        w = self.widget
        self.sw = interrupteur(True, lambda on: S.en_fond(S.bt_activer, lambda _: (self.rafraichir(), self.shell.icones_bientot()), on))
        w.append(entete("bluetooth", "Bluetooth", self.shell, "bluetooth", self.sw))
        w.append(label("Mes appareils", "section"))
        self.liste = boite(True, 2); w.append(self.liste)
        self.t_nouveaux = label("Appareils à proximité", "section"); w.append(self.t_nouveaux)
        self.nouveaux = boite(True, 2); w.append(self.nouveaux)
        bas = boite(False, 6)
        self.b_scan = bouton("Ajouter un appareil", "plus", "fantome", taille=14, rappel=self.rechercher)
        bas.append(self.b_scan); bas.append(Gtk.Box(hexpand=True))
        bas.append(pied_lien("Paramètres", lambda: self.shell.parametres("bluetooth")))
        w.append(bas)
        self.t_nouveaux.set_visible(False)

    def rafraichir(self):
        S.en_fond(lambda: (S.bt_present(), S.bt_actif(), S.bt_appareils()), self._rendu)

    def _rendu(self, r):
        if isinstance(r, Exception): return
        pres, on, L = r
        self.sw.poser(on); self.sw.set_sensitive(pres); self.b_scan.set_sensitive(on)
        vider(self.liste)
        if not pres:
            self.liste.append(label("Aucun adaptateur Bluetooth détecté.", "attenue", "petit")); return
        if not on:
            self.liste.append(label("Bluetooth désactivé.", "attenue", "petit")); return
        if not L:
            self.liste.append(label("Aucun appareil appairé.", "attenue", "petit"))
        for d in L:
            b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
            if d["connecte"]: b.add_css_class("sel")
            bx = boite(False, 10)
            bx.append(gicon_image(Gio.ThemedIcon.new(d["icone"]), 20))
            t = boite(True, 0); t.append(label(d["nom"], ellipsize=True, largeur=24))
            sous = "Connecté" if d["connecte"] else "Appairé"
            if d["batterie"] is not None: sous += " · batterie %d %%" % d["batterie"]
            t.append(label(sous, "attenue", "petit")); bx.append(t)
            b.set_child(bx)
            b.connect("clicked", lambda _b, d=d: (_b.set_sensitive(False), S.en_fond(S.bt_connecter, lambda _: (self.rafraichir(), self.shell.icones_bientot()), d["mac"], not d["connecte"])))
            clic_droit_w(b, lambda b, d=d: popover_menu(b, [("link" if not d["connecte"] else "unlink", "Déconnecter" if d["connecte"] else "Connecter",
                                                              lambda: S.en_fond(S.bt_connecter, lambda _: self.rafraichir(), d["mac"], not d["connecte"])),
                                                             ("trash-2", "Oublier l'appareil", lambda: S.en_fond(S.bt_oublier, lambda _: self.rafraichir(), d["mac"]))]))
            self.liste.append(b)

    def rechercher(self):
        self.b_scan.set_sensitive(False); self.t_nouveaux.set_visible(True)
        vider(self.nouveaux); sp = Gtk.Spinner(spinning=True, halign=Gtk.Align.START); self.nouveaux.append(sp)
        S.en_fond(S.bt_rechercher, self._trouves)

    def _trouves(self, L):
        self.b_scan.set_sensitive(True); vider(self.nouveaux)
        if isinstance(L, Exception) or not L:
            self.nouveaux.append(label("Aucun appareil trouvé. Mettez-le en mode appairage.", "attenue", "petit", wrap=True)); return
        for d in L:
            r = boite(False, 10)
            r.append(gicon_image(Gio.ThemedIcon.new(d["icone"]), 20)); r.append(label(d["nom"], hexpand=True, ellipsize=True))
            b = bouton("Appairer", None, "fantome")
            def go(_b=None, d=d, b=b):
                b.set_sensitive(False); b.set_label("…")
                S.en_fond(S.bt_appairer, lambda res: (self.rafraichir(),
                                                     b.set_label("Appairé ✓" if (not isinstance(res, Exception) and res[0]) else "Échec")), d["mac"])
            b.connect("clicked", go); r.append(b); self.nouveaux.append(r)

# =================================================================================== BATTERIE
class Batterie(Panneau):
    def construire(self):
        w = self.widget
        w.append(entete("battery-full", "Énergie", self.shell, "alimentation"))
        self.hero = boite(False, 14, "carte"); w.append(self.hero)
        w.append(label("Mode d'alimentation", "section"))
        self.profils = boite(False, 6, homogeneous=True); w.append(self.profils)
        self.t_lum = label("Luminosité", "section"); w.append(self.t_lum)
        r = boite(False, 8); r.append(ico("sun-medium", 18)); self.s_lum = curseur(50, lambda v: S.en_fond(S.regler_luminosite, None, v))
        r.append(self.s_lum); self.r_lum = r; w.append(r)
        w.append(pied_lien("Paramètres d'alimentation", lambda: self.shell.parametres("alimentation")))

    def rafraichir(self):
        S.en_fond(lambda: (S.batterie(), S.profil(), S.profils_dispo(), S.luminosite()), self._rendu)

    def _rendu(self, r):
        if isinstance(r, Exception): return
        b, p, dispo, lum = r
        vider(self.hero)
        self.hero.append(ico(icone_batterie(b), 40, "c"))
        v = boite(True, 0)
        if b:
            v.append(label("%d %%" % b["pct"], "grand")); v.append(label(b["etat"].capitalize() + (" · " + b["temps"] if b["temps"] else ""), "attenue", "petit"))
        else:
            v.append(label("Sur secteur", "gras")); v.append(label("Pas de batterie détectée", "attenue", "petit"))
        self.hero.append(v)
        vider(self.profils)
        for cle, nom, ic in S.PROFILS:
            bt = Gtk.Button(); bt.add_css_class("tuile")
            if cle == p: bt.add_css_class("on")
            bx = boite(True, 4, halign=Gtk.Align.CENTER); bx.append(ico(ic, 18, self.shell.p["sur_accent"] if cle == p else "t")); bx.append(label(nom, "petit", xalign=0.5))
            bt.set_child(bx); bt.set_sensitive(cle in dispo)
            bt.connect("clicked", lambda _b, c=cle: S.en_fond(S.regler_profil, lambda _: self.rafraichir(), c))
            self.profils.append(bt)
        self.t_lum.set_visible(lum is not None); self.r_lum.set_visible(lum is not None)
        if lum is not None: self.s_lum.poser(lum)

# =================================================================================== CENTRE DE CONTRÔLE
class Centre(Panneau):
    largeur = 380
    def construire(self):
        w = self.widget
        if not theme.imitation(self.shell.cfg): w.append(entete("sliders-horizontal", "Centre de contrôle", self.shell, None))      # Windows 11 / macOS : sans titre
        self.grille = Gtk.FlowBox(max_children_per_line=3, min_children_per_line=3, selection_mode=Gtk.SelectionMode.NONE,
                                  column_spacing=8, row_spacing=8, homogeneous=True)
        w.append(self.grille)
        self.r_lum = boite(False, 10); self.r_lum.append(ico("sun-medium", 18))
        self.s_lum = curseur(50, lambda v: S.en_fond(S.regler_luminosite, None, v)); self.r_lum.append(self.s_lum); w.append(self.r_lum)
        r = boite(False, 10); self.i_vol = Gtk.Box(); r.append(self.i_vol)
        self.s_vol = curseur(50, lambda v: (S.en_fond(S.regler_volume, None, v), self.shell.icones_bientot())); r.append(self.s_vol); w.append(r)
        pied = boite(False, 8, "menu-pied")
        self.bat = boite(False, 6); pied.append(self.bat); pied.append(Gtk.Box(hexpand=True))
        pied.append(bouton("Tous les paramètres", "settings", "plat", taille=15, rappel=lambda: self.shell.parametres("accueil")))
        w.append(pied)

    def tuile(self, icone, nom, sous, on, rappel, page=None, dispo=True):
        b = Gtk.Button(); b.add_css_class("tuile")
        if on: b.add_css_class("on")
        bx = boite(True, 2)
        i = ico(icone, 18, self.shell.p["sur_accent"] if on else "t"); i.set_halign(Gtk.Align.START); bx.append(i)
        bx.append(label(nom, "petit", "gras", ellipsize=True))
        bx.append(label(sous or ("Activé" if on else "Désactivé"), "tuile-sous", ellipsize=True))
        b.set_child(bx); b.set_sensitive(dispo)
        b.connect("clicked", lambda *_: rappel())
        if page: clic_droit(b, lambda: self.shell.parametres(page))
        return b

    def rafraichir(self):
        S.en_fond(lambda: (S.etat_reseau(), S.wifi_actif(), S.bt_present(), S.bt_actif(), S.profil(), S.luminosite(), S.volume(), S.batterie()), self._rendu)

    def _rendu(self, r):
        if isinstance(r, Exception): return
        et, wifi, btp, bt, prof, lum, (vol, muet), bat = r
        c = self.shell.cfg; sh = self.shell
        vider(self.grille)
        maj = lambda *_: (self.rafraichir(), sh.icones_bientot())
        T = [
            self.tuile(icone_wifi(et["signal"]) if wifi else "wifi-off", "Wi-Fi", et["nom"] if et["type"] == "wifi" else None, wifi,
                       lambda: S.en_fond(S.wifi_activer, maj, not wifi), "wifi"),
            self.tuile("bluetooth" if bt else "bluetooth-off", "Bluetooth", None, bt, lambda: S.en_fond(S.bt_activer, maj, not bt), "bluetooth", btp),
            self.tuile("plane", "Mode avion", None, et.get("avion"), lambda: S.en_fond(S.mode_avion, maj, not et.get("avion")), "avion"),
            self.tuile("bell-off" if c["ne_pas_deranger"] else "bell", "Ne pas déranger", None, c["ne_pas_deranger"],
                       lambda: (config.modifier(ne_pas_deranger=not c["ne_pas_deranger"])), "notifications"),
            self.tuile("moon-star", "Lumière nocturne", None, c["lumiere_nocturne"],
                       lambda: config.modifier(lumiere_nocturne=not c["lumiere_nocturne"]), "ecran"),
            self.tuile("leaf", "Économie", None, prof == "power-saver",
                       lambda: S.en_fond(S.regler_profil, maj, "balanced" if prof == "power-saver" else "power-saver"), "alimentation"),
            (self.tuile("moon", "Mode sombre", None, not theme.palette(c)["clair"],       # Façon Windows 11 / macOS : clair ↔ sombre du même thème
                        lambda: config.modifier(imitation_apparence="clair" if not theme.palette(c)["clair"] else "sombre"), "theme") if theme.imitation(c) else
             self.tuile("sun-moon", "Thème clair" if not theme.palette(c)["clair"] else "Thème sombre", "Clic : basculer", theme.palette(c)["clair"],
                       lambda: config.modifier(theme={"sobre": "sobrec", "sobrec": "sobre"}.get(c["theme"], "sombre" if theme.palette(c)["clair"] else "clair")), "theme")),
            self.tuile(profils.courant(c)[2], "Profil", profils.courant(c)[1], profils.courant(c)[0] != "normal",
                       lambda: self.shell.menu_profils(self._t_profil), "profils"),
            self.tuile("scan-line", "Capture", "Zone, écran, vidéo", False, lambda: (sh.fermer(), S.detacher("sleep 0.4; xiii-outil-capture"))),
        ]
        self._t_profil = T[7]
        for t in T: self.grille.append(t)
        self.r_lum.set_visible(lum is not None)
        if lum is not None: self.s_lum.poser(lum)
        vider(self.i_vol); self.i_vol.append(ico(icone_volume(vol, muet), 18)); self.s_vol.poser(vol)
        vider(self.bat)
        self.bat.append(ico(icone_batterie(bat), 16, "d"))
        self.bat.append(label(("%d %%" % bat["pct"]) if bat else "Secteur", "attenue", "petit"))

# =================================================================================== ALIMENTATION
class Alimentation(Panneau):
    largeur = 260
    def construire(self):
        w = self.widget
        w.append(entete("power", "Session", self.shell, None))
        for ic, nom, cmd in (("lock", "Verrouiller", "swaylock -f"), ("moon", "Mettre en veille", "systemctl suspend"),
                             ("log-out", "Se déconnecter", "labwc --exit"), ("rotate-ccw", "Redémarrer", "systemctl reboot"),
                             ("power", "Éteindre", "systemctl poweroff")):
            b = bouton(nom, ic, "ligne", "plat", taille=17, rappel=lambda c=cmd: (self.shell.fermer(), S.detacher(c)))
            w.append(b)

# =================================================================================== MÉTÉO
METEO = {0: ("sun", "Ensoleillé"), 1: ("cloud-sun", "Éclaircies"), 2: ("cloud-sun", "Partiellement nuageux"), 3: ("cloud", "Couvert"),
         45: ("cloud-fog", "Brouillard"), 48: ("cloud-fog", "Brouillard givrant"), 51: ("cloud-drizzle", "Bruine"), 53: ("cloud-drizzle", "Bruine"),
         55: ("cloud-drizzle", "Bruine dense"), 61: ("cloud-rain", "Pluie faible"), 63: ("cloud-rain", "Pluie"), 65: ("cloud-rain", "Forte pluie"),
         66: ("cloud-rain", "Pluie verglaçante"), 67: ("cloud-rain", "Pluie verglaçante"), 71: ("cloud-snow", "Neige faible"), 73: ("cloud-snow", "Neige"),
         75: ("snowflake", "Forte neige"), 77: ("snowflake", "Grains de neige"), 80: ("cloud-rain-wind", "Averses"), 81: ("cloud-rain-wind", "Averses"),
         82: ("cloud-rain-wind", "Violentes averses"), 85: ("cloud-snow", "Averses de neige"), 86: ("cloud-snow", "Averses de neige"),
         95: ("cloud-lightning", "Orage"), 96: ("cloud-lightning", "Orage et grêle"), 99: ("cloud-lightning", "Orage et grêle")}
JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]

def meteo(lat, lon):
    if S.DEMO:
        return dict(t=14, code=2, vent=12, jours=[(JOURS[(i) % 7], [2, 61, 3, 0, 80][i], 15 - i, 8 + i % 3) for i in range(5)], lever="08:01", coucher="17:03")
    q = urllib.parse.urlencode(dict(latitude=lat, longitude=lon, current="temperature_2m,weather_code,wind_speed_10m",
                                    daily="weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset", timezone="auto", forecast_days=5))
    d = json.load(urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + q, timeout=10))
    c = d["current"]; dl = d["daily"]
    jours = []
    for i, iso in enumerate(dl["time"]):
        j = datetime.date.fromisoformat(iso)
        jours.append(("Aujourd'hui" if i == 0 else JOURS[j.weekday()], dl["weather_code"][i], round(dl["temperature_2m_max"][i]), round(dl["temperature_2m_min"][i])))
    return dict(t=round(c["temperature_2m"]), code=c["weather_code"], vent=round(c["wind_speed_10m"]), jours=jours,
                lever=(dl.get("sunrise") or [""])[0][11:16], coucher=(dl.get("sunset") or [""])[0][11:16])

class Meteo(Panneau):
    largeur = 340
    def construire(self):
        w = self.widget
        w.append(entete("cloud-sun", "Météo", self.shell, "meteo"))
        self.corps = boite(True, 12); w.append(self.corps)
    def rendu(self, m):
        vider(self.corps)
        if not m:
            self.corps.append(label("Météo indisponible (pas de connexion ?)", "attenue")); return
        ic, nom = METEO.get(m["code"], ("cloud", ""))
        h = boite(False, 14, "carte"); h.append(ico(ic, 48, "c"))
        v = boite(True, 0); v.append(label("%d°" % m["t"], "meteo-grand")); v.append(label(nom, "gras"))
        v.append(label("%s · vent %d km/h" % (self.shell.cfg["meteo_ville"], m["vent"]), "attenue", "petit")); h.append(v)
        self.corps.append(h)
        g = boite(False, 4, homogeneous=True)
        for j, code, mx, mn in m["jours"]:
            c = boite(True, 4, "carte", halign=Gtk.Align.FILL)
            c.append(label(j, "petit", "gras", xalign=0.5, ellipsize=True)); c.append(ico(METEO.get(code, ("cloud",))[0], 22, "c"))
            c.append(label("%d° / %d°" % (mx, mn), "petit", xalign=0.5)); g.append(c)
        self.corps.append(g)

# =================================================================================== VOLET DE NOTIFICATIONS
class Volet(Panneau):
    largeur = 380
    def construire(self):
        w = self.widget
        h = boite(False, 10)
        h.append(ico("bell", 22, "c")); h.append(label("Notifications", "panneau-titre", hexpand=True))
        h.append(bouton("Tout effacer", None, "fantome", rappel=lambda: self.shell.serveur.tout_effacer()))
        w.append(h)
        r = boite(False, 10, "carte")
        r.append(ico("bell-off", 18)); r.append(label("Ne pas déranger", hexpand=True))
        self.dnd = interrupteur(False, lambda on: config.modifier(ne_pas_deranger=on)); r.append(self.dnd); w.append(r)
        self.liste = boite(True, 8)
        self.vide = boite(True, 8, valign=Gtk.Align.CENTER, vexpand=True)
        self.vide.append(ico("bell", 44, "d")); self.vide.append(label("Aucune nouvelle notification", "attenue", xalign=0.5))
        self.zone = Gtk.Stack(vexpand=True)
        self.zone.add_named(self.vide, "vide"); self.zone.add_named(defilant(self.liste), "liste")
        self.histo = boite(True, 4); self.zone.add_named(defilant(self.histo), "historique")
        bas = boite(False, 6)
        self.b_histo = Gtk.ToggleButton(label="Historique (7 jours)"); self.b_histo.add_css_class("plat")
        self.b_histo.connect("toggled", lambda b: self.rafraichir()); bas.append(self.b_histo)
        w.append(self.zone); w.append(bas)
        cal = boite(True, 6, "carte")
        self.date = label("", "gras"); cal.append(self.date)
        self.cal = Gtk.Calendar(); cal.append(self.cal)
        w.append(cal)

    def rafraichir(self):
        self.dnd.poser(self.shell.cfg["ne_pas_deranger"])
        d = datetime.date.today()
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        self.date.set_text("%s %d %s" % (jours[d.weekday()].capitalize(), d.day, mois[d.month - 1]))
        vider(self.liste)
        if self.b_histo.get_active():                 # historique : même les notifications fermées, groupées par jour
            from .notifs import historique
            vider(self.histo); jour = None
            for x in sorted(historique(), key=lambda x: -x["t"])[:200]:
                lt = time.localtime(x["t"]); JR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
                MS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
                j = "%s %d %s" % (JR[lt.tm_wday], lt.tm_mday, MS[lt.tm_mon - 1])
                if j != jour: jour = j; self.histo.append(label(j.capitalize(), "notif-app", margin_top=6))
                r = boite(False, 8, "notif"); r.append(ico("bell", 14, "d"))
                v = boite(True, 0, hexpand=True); v.append(label("%s · %s" % (x.get("app") or "", time.strftime("%H:%M", time.localtime(x["t"]))), "attenue", "petit"))
                v.append(label(x.get("titre") or "", "gras", wrap=True, xalign=0))
                if x.get("corps"): v.append(label(re.sub(r"<[^>]+>", "", x["corps"])[:160], "petit", wrap=True, xalign=0))
                r.append(v); self.histo.append(r)
            if not historique(): self.histo.append(label("Aucune notification ces 7 derniers jours.", "attenue", wrap=True))
            self.zone.set_visible_child_name("historique"); return
        ns = self.shell.serveur.triees()
        self.zone.set_visible_child_name("liste" if ns else "vide")
        groupes = {}
        for n in ns: groupes.setdefault(n.app, []).append(n)
        for app, L in groupes.items():
            t = boite(False, 6, margin_top=4)
            t.append(label(app, "notif-app", hexpand=True))
            t.append(bouton(None, "x", "plat", taille=12, role="d", tip="Effacer",
                            rappel=lambda L=L: [self.shell.serveur.fermer(n.id) for n in L]))
            self.liste.append(t)
            for n in L:
                self.liste.append(carte_notif(n, self.shell, volet=True))

def depuis(t):
    s = int(time.time() - t)
    return "à l'instant" if s < 60 else "il y a %d min" % (s // 60) if s < 3600 else time.strftime("%H:%M", time.localtime(t))

def image_notif(n, taille=32):
    if n.pixbuf:
        im = Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(n.pixbuf))
    elif n.image and os.path.exists(n.image.replace("file://", "")):
        im = Gtk.Image.new_from_file(n.image.replace("file://", ""))
    elif n.icone and os.path.exists(n.icone.replace("file://", "")):
        im = Gtk.Image.new_from_file(n.icone.replace("file://", ""))
    elif n.icone:
        im = Gtk.Image.new_from_icon_name(n.icone)
    else:
        de = n.hints.get("desktop-entry")
        a = apps.par_id(de + ".desktop") if de else None
        im = gicon_image(a.get_icon(), taille) if a else ico("bell", taille, "c")
    im.set_pixel_size(taille); im.set_valign(Gtk.Align.START)
    return im

def carte_notif(n, shell, volet=False):
    c = boite(False, 12, "notif" if volet else "toast")
    c.set_size_request(340 if not volet else -1, -1)
    c.append(image_notif(n))
    v = boite(True, 2, hexpand=True)
    if not volet:
        h0 = boite(False, 6); h0.append(label(n.app, "notif-app", hexpand=True)); h0.append(label(depuis(n.heure), "attenue", "petit")); v.append(h0)
    h = boite(False, 6)
    h.append(label(n.titre or n.app, "notif-titre", wrap=True, hexpand=True))
    if volet: h.append(label(depuis(n.heure), "attenue", "petit"))
    h.append(bouton(None, "x", "plat", taille=12, role="d", tip="Fermer la notification", rappel=lambda: shell.serveur.fermer(n.id)))
    v.append(h)
    if n.corps:
        l = label("", "notif-corps", wrap=True)
        try:
            Pango.parse_markup(n.corps, -1, "\0"); l.set_markup(n.corps)
        except Exception:
            l.set_text(n.corps)
        l.set_lines(4); l.set_ellipsize(Pango.EllipsizeMode.END); v.append(l)
    acts = [a for a in n.actions if a[0] != "default"]
    if acts:
        r = boite(False, 6, margin_top=6)
        for cle, nom in acts:
            r.append(bouton(nom, None, "fantome", rappel=lambda k=cle: shell.serveur.action(n.id, k)))
        v.append(r)
    c.append(v)
    g = Gtk.GestureClick(button=1)
    def defaut(*_):
        if any(a[0] == "default" for a in n.actions): shell.serveur.action(n.id, "default")
    g.connect("released", defaut); c.add_controller(g)
    return c
