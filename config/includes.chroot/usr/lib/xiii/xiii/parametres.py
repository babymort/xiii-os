# OS XIII — Paramètres (aussi complets que ceux de Windows 11, aux couleurs de la Suite XIII).
# Lancement : xiii-parametres [--page clé]
# Application développée par Matthieu Lamotte.
import os, sys, re, glob, json, shutil, subprocess, pwd, time, datetime, threading, urllib.request, urllib.parse, grp, shlex
import xml.etree.ElementTree as ET
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, Pango
from . import config, theme, systeme as S, apps
from .ui import *
from . import animations as A
from .pages_index import PAGES, PAR_CLE, CATEGORIES, ALIAS, INDEX
from .panneaux import METEO

FONDS_PERSO = os.path.join(GLib.get_user_data_dir(), "xiii", "fonds")
RC = os.path.join(GLib.get_user_config_dir(), "labwc", "rc.xml")
CLES_THEME = {"theme", "accent", "icones_tierces", "transparence", "animations", "taille_texte", "curseur_taille", "police", "verrou_fond", "theme_perso", "contraste", "densite"}

# ------------------------------------------------------------------------------------------------ rc.xml de labwc
def rc_lire():
    try:
        return ET.parse(RC)
    except Exception:
        return ET.ElementTree(ET.fromstring("<labwc_config/>"))

def rc_noeud(racine, chemin, attrs=None):
    """Trouve/crée racine/a/b ; attrs pour le dernier (ex : device category=touchpad)."""
    n = racine
    parts = chemin.split("/")
    for i, p in enumerate(parts):
        a = attrs if i == len(parts) - 1 else None
        trouve = None
        for e in n.findall(p):
            if not a or all(e.get(k) == v for k, v in a.items()):
                trouve = e; break
        if trouve is None:
            trouve = ET.SubElement(n, p, a or {})
        n = trouve
    return n

def rc_ecrire(modif):
    t = rc_lire(); modif(t.getroot())
    os.makedirs(os.path.dirname(RC), exist_ok=True)
    t.write(RC, encoding="unicode", xml_declaration=True)
    theme.reconfigurer_labwc()

def rc_valeur(chemin, attrs=None, defaut=None):
    t = rc_lire().getroot()
    n = t
    for i, p in enumerate(chemin.split("/")):
        a = attrs if i == len(chemin.split("/")) - 1 else None
        n2 = None
        for e in n.findall(p):
            if not a or all(e.get(k) == v for k, v in a.items()):
                n2 = e; break
        if n2 is None: return defaut
        n = n2
    return (n.text or "").strip() or defaut

# ================================================================================================ application
NOMS_DOIGTS = {"right-index-finger": "Index droit", "left-index-finger": "Index gauche", "right-thumb": "Pouce droit", "left-thumb": "Pouce gauche",
               "right-middle-finger": "Majeur droit", "left-middle-finger": "Majeur gauche"}

class Parametres(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.Parametres", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.cfg = config.charger(); self.win = None; self.page = "accueil"; self.histo = []

    def do_command_line(self, cl):
        args = cl.get_arguments()[1:]
        page = "accueil"
        if "--page" in args:
            i = args.index("--page")
            if i + 1 < len(args): page = args[i + 1]
        self.activate(); self.aller(ALIAS.get(page, page))
        return 0

    def do_activate(self):
        if self.win:
            self.win.present(); return
        couleurs(self.cfg)
        self.css = Gtk.CssProvider(); self.css.load_from_string(theme.css_parametres(self.cfg))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 10)
        Gtk.Settings.get_default().set_property("gtk-icon-theme-name", theme.nom_icones(self.cfg))
        w = Gtk.ApplicationWindow(application=self, title="Paramètres", default_width=1180, default_height=780)
        w.add_css_class("parametres"); self.win = w
        corps = boite(False, 0); w.set_child(corps)
        # navigation
        nav = boite(True, 6, "nav"); nav.set_size_request(290, -1)
        nav.set_margin_top(0)
        tete = boite(False, 10, margin_top=18, margin_start=18, margin_end=18)
        tete.append(label("Paramètres", "nav-titre")); nav.append(tete)
        self.carte_compte = Gtk.Button(); self.carte_compte.add_css_class("nav-item"); self.carte_compte.set_margin_start(10); self.carte_compte.set_margin_end(10)
        self.carte_compte.connect("clicked", lambda *_: self.aller("compte")); nav.append(self.carte_compte)
        self.cherche = Gtk.SearchEntry(placeholder_text="Rechercher un paramètre", margin_start=14, margin_end=14, margin_bottom=6)
        self.cherche.connect("search-changed", self.rechercher); nav.append(self.cherche)
        self.nav_liste = boite(True, 2, margin_start=10, margin_end=10)
        nav.append(defilant(self.nav_liste)); self.nav_liste.set_vexpand(True)
        nav.append(label("Application développée par Matthieu Lamotte", "credit", xalign=0.5, margin_bottom=12, margin_top=6))
        corps.append(nav)
        # contenu
        droite = boite(True, 0, hexpand=True)
        self.fil = boite(False, 4, margin_top=22, margin_start=40, margin_end=40, margin_bottom=10); droite.append(self.fil)
        self.defil = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        droite.append(self.defil); corps.append(droite)
        self.remplir_nav(); self.maj_compte()
        self.mon = config.surveiller(self.cfg_change)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.touche); w.add_controller(k)
        w.present()
        if not self.page or self.page == "accueil": self.aller("accueil")

    def touche(self, c, kv, code, etat):
        if kv == Gdk.KEY_f and etat & Gdk.ModifierType.CONTROL_MASK:
            self.cherche.grab_focus(); return True
        if kv == Gdk.KEY_BackSpace and etat & Gdk.ModifierType.ALT_MASK or kv == Gdk.KEY_Escape and self.histo:
            self.retour(); return True
        return False

    def cfg_change(self, cfg):
        self.cfg = cfg; couleurs(cfg); theme._cache.clear()
        self.css.load_from_string(theme.css_parametres(cfg))

    def regler(self, **kw):
        """Enregistre des réglages ; propage le thème au système si besoin."""
        if {"theme", "accent", "theme_perso"} & set(kw) and "fond" not in kw and theme.fond_par_defaut(self.cfg.get("fond")):
            c2 = dict(self.cfg); c2.update(kw); kw["fond"] = theme.fond_assorti(c2)
        acc_avant = self.cfg.get("accent")
        self.cfg = config.modifier(**kw)
        if CLES_THEME & set(kw) or self.cfg.get("accent") != acc_avant:
            Gtk.Settings.get_default().set_property("gtk-icon-theme-name", theme.nom_icones(self.cfg))
            theme.appliquer_systeme(self.cfg)
            couleurs(self.cfg); theme._cache.clear(); self.css.load_from_string(theme.css_parametres(self.cfg))
            GLib.idle_add(lambda: (self.remplir_nav(), self.aller(self.page, histo=False), False)[-1])

    # ------------------------------------------------------------------ navigation
    def maj_compte(self):
        u = pwd.getpwuid(os.getuid()); nom = u.pw_gecos.split(",")[0] or u.pw_name
        bx = boite(False, 12, margin_top=6, margin_bottom=6)
        bx.append(avatar(64 if False else 48, nom))
        v = boite(True, 2, valign=Gtk.Align.CENTER); v.append(label(nom, "gras")); v.append(label("Compte local · " + u.pw_name, "attenue", "petit"))
        bx.append(v); self.carte_compte.set_child(bx)

    def remplir_nav(self):
        vider(self.nav_liste); self.boutons_nav = {}
        for cle, titre, ic, _, _, _ in CATEGORIES:
            b = Gtk.Button(); b.add_css_class("nav-item")
            bx = boite(False, 12); barre = Gtk.Box(); barre.add_css_class("nav-barre"); bx.append(barre)
            bx.append(ico(ic, 18, "c")); bx.append(label(titre)); b.set_child(bx); b._barre = barre
            b.connect("clicked", lambda _b, c=cle: self.aller(c))
            self.nav_liste.append(b); self.boutons_nav[cle] = b
        self.surligner()

    def surligner(self):
        p = PAR_CLE.get(self.page); cat = (p[3] or p[0]) if p else "accueil"
        if self.page == "recherche": cat = None
        for c, b in getattr(self, "boutons_nav", {}).items():
            on = c == cat
            (b.add_css_class if on else b.remove_css_class)("sel")
            (b._barre.add_css_class if on else b._barre.remove_css_class)("sel")

    def aller(self, cle, histo=True):
        cle = ALIAS.get(cle, cle)
        if cle not in PAR_CLE: cle = "accueil"
        if histo and self.page != cle and self.win: self.histo.append(self.page)
        self.page = cle
        if not self.win: return
        p = PAR_CLE[cle]
        vider(self.fil)
        if self.histo and p[3]:
            self.fil.append(bouton(None, "chevron-left", "plat", taille=18, tip="Retour", rappel=self.retour))
        if p[3]:
            pb = Gtk.Button(); pb.add_css_class("fil-lien"); pb.set_child(label(PAR_CLE[p[3]][1], "fil-txt"))
            pb.connect("clicked", lambda *_: self.aller(p[3])); self.fil.append(pb)
            self.fil.append(label("›", "page-titre", "attenue"))
        self.fil.append(label(p[1], "page-titre"))
        contenu = boite(True, 4, margin_start=40, margin_end=40, margin_bottom=40, hexpand=True)
        try:
            getattr(self, "p_" + cle, self.p_categorie)(contenu, cle)
        except Exception as e:
            import traceback; traceback.print_exc()
            contenu.append(label("Erreur dans cette page : %s" % e, "attenue", wrap=True))
        self.defil.set_child(contenu)
        self.defil.get_vadjustment().set_value(0)
        self.win.set_title("Paramètres — " + p[1])
        self.surligner()

    def retour(self):
        if self.histo: self.aller(self.histo.pop(), histo=False)

    def rechercher(self, e):
        q = e.get_text().strip().lower()
        if not q:
            self.aller("accueil"); return
        q = sans_accents(q)
        res = [x for x in INDEX if q in sans_accents(x[1] + " " + x[4])]
        vider(self.fil); self.fil.append(label("Résultats pour « %s »" % e.get_text().strip(), "page-titre"))
        c = boite(True, 4, margin_start=40, margin_end=40, margin_bottom=40)
        if not res: c.append(label("Aucun paramètre trouvé.", "attenue"))
        for cle, t, ic, ch, _ in res:
            c.append(reglage(ic, t, ch, clic=lambda c=cle: self.aller(c)))
        self.page = "recherche"; self.surligner(); self.defil.set_child(c)

    # ------------------------------------------------------------------ page catégorie générique
    def p_categorie(self, c, cle):
        for p in PAGES:
            if p[3] == cle:
                c.append(reglage(p[2], p[1], p[4], clic=lambda k=p[0]: self.aller(k)))

    # ================================================================== ACCUEIL
    def p_accueil(self, c, cle):
        i = S.infos_systeme(); cfg = self.cfg
        hero = boite(False, 20, "hero")
        pic = vignette(cfg["fond"], 220, 124)
        f = Gtk.Frame(); f.set_child(pic); f.add_css_class("apercu-theme"); hero.append(f)
        v = boite(True, 4, valign=Gtk.Align.CENTER, hexpand=True)
        v.append(label(i["hote"], "hero-grand")); v.append(label(i["nom"] + (" · " + i["version"] if i["version"] else ""), "attenue"))
        v.append(label(i["cpu"] + " · " + i["ram"], "attenue", "petit", ellipsize=True))
        r = boite(False, 8, margin_top=8); r.append(bouton("Renommer", None, "fantome", rappel=lambda: self.aller("apropos")))
        r.append(bouton("Personnaliser", "palette", "fantome", taille=14, rappel=lambda: self.aller("perso"))); v.append(r)
        hero.append(v); c.append(hero)
        g = Gtk.FlowBox(max_children_per_line=2, min_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, homogeneous=True, margin_top=10)
        c.append(g)
        def carte(ic, titre, sous_fn, page):
            b = Gtk.Button(); b.add_css_class("reglage")
            bx = boite(False, 14); bx.append(ico(ic, 26, "c"))
            vv = boite(True, 2); vv.append(label(titre, "reglage-titre")); sl = label("…", "reglage-sous", ellipsize=True); vv.append(sl); bx.append(vv)
            b.set_child(bx); b.connect("clicked", lambda *_: self.aller(page)); g.append(b)
            S.en_fond(sous_fn, lambda t: sl.set_text(t if isinstance(t, str) else "—"))
        def reseau():
            e = S.etat_reseau()
            return ("Connecté à " + e["nom"]) if e["type"] else "Non connecté"
        carte("globe", "Réseau et Internet", reseau, "reseau")
        carte("bluetooth", "Bluetooth", lambda: ("Activé · %d appareil(s)" % len([d for d in S.bt_appareils() if d["connecte"]])) if S.bt_actif() else "Désactivé", "bluetooth")
        carte("palette", "Personnalisation", lambda: "Thème %s · accent %s" % (theme.NOMS_THEMES.get(cfg["theme"], cfg["theme"]), theme.palette(cfg)["accent"]), "theme")
        carte("battery-full", "Alimentation", lambda: (lambda b: ("%d %% · %s" % (b["pct"], b["etat"])) if b else "Sur secteur")(S.batterie()), "alimentation")
        carte("hard-drive", "Stockage", lambda: (lambda d: "%s libres sur %s" % (S.humain(d[0]["libre"]), S.humain(d[0]["total"])) if d else "—")(S.disques()), "stockage")
        carte("refresh-cw", "Mises à jour", lambda: "Rechercher des mises à jour", "maj")
        c.append(groupe_titre("Recommandés pour vous"))
        for ic, t, s, pg in (("wifi", "Partager le Wi-Fi par QR code", "Affichez le QR code du réseau actuel", "wifi"),
                             ("clapperboard", "Mode tournage", "Performances, silence et éveil en un clic", "xiii"),
                             ("image", "Changer de fond d'écran", "Fonds XIII ou vos images", "fond"),
                             ("sparkles", "Relier OS XIII à Claude", "Claude voit votre PC, votre projet et vos fichiers XIII", "claude"),
                             ("cpu", "Vérifier les pilotes", "Scan des pilotes et firmwares manquants", None)):
            c.append(reglage(ic, t, s, clic=(lambda pg=pg: self.aller(pg)) if pg else (lambda: S.detacher("xiii-bilan --pilotes"))))

    # ================================================================== SYSTÈME
    def p_ecran(self, c, cle):
        cfg = self.cfg
        c.append(groupe_titre("Luminosité et couleur"))
        lum = S.luminosite()
        if lum is not None:
            c.append(reglage("sun-medium", "Luminosité", "Réglez la luminosité de l'écran intégré",
                             droite=dim(curseur(lum, lambda v: S.en_fond(S.regler_luminosite, None, v)), 260)))
        c.append(reglage("moon-star", "Lumière nocturne", "Réduit la lumière bleue pour reposer les yeux",
                         droite=interrupteur(cfg["lumiere_nocturne"], lambda on: self.regler(lumiere_nocturne=on))))
        c.append(reglage("thermometer", "Intensité de la lumière nocturne", "Plus chaud = plus orangé",
                         droite=dim(curseur(cfg["nocturne_temp"], lambda v: self.regler(nocturne_temp=int(v)), 2500, 6000, 100, 400), 260)))
        for e in S.ecrans():
            c.append(groupe_titre("Écran " + e["nom"] + (" — " + e["desc"] if e["desc"] != e["nom"] else "")))
            modes = sorted({(w, h) for w, h, _ in e["modes"]}, key=lambda m: -m[0] * m[1])
            res = deroulant([("%dx%d" % m, "%d × %d%s" % (m[0], m[1], " (recommandé)" if i == 0 else "")) for i, m in enumerate(modes)],
                            "%dx%d" % (e["w"], e["h"]), lambda v, e=e: self.ecran(e, mode=v))
            c.append(reglage("monitor", "Résolution de l'écran", "", droite=res))
            pr = boite(False, 6)
            ew = Gtk.SpinButton.new_with_range(320, 7680, 2); ew.set_value(e["w"]); eh = Gtk.SpinButton.new_with_range(200, 4320, 2); eh.set_value(e["h"])
            ez = Gtk.SpinButton.new_with_range(20, 360, 1); ez.set_value(round(e["hz"] or 60))
            for x, l in ((ew, None), (eh, "×"), (ez, "Hz")):
                if l == "×": pr.append(label("×"))
                pr.append(x)
                if l == "Hz": pr.append(label("Hz"))
            pr.append(bouton("Essayer", None, "fantome", rappel=lambda e=e, ew=ew, eh=eh, ez=ez: self.ecran_perso(e, int(ew.get_value()), int(eh.get_value()), float(ez.get_value()))))
            c.append(reglage("ruler", "Résolution personnalisée", "Pour un écran ou un vidéoprojecteur mal reconnu", droite=pr))
            hz = sorted({r for w, h, r in e["modes"] if (w, h) == (e["w"], e["h"])}, reverse=True)
            if len(hz) > 1:
                c.append(reglage("gauge", "Fréquence de rafraîchissement", "", droite=deroulant([(str(h), "%.0f Hz" % h) for h in hz], str(e["hz"]),
                                                                                                  lambda v, e=e: self.ecran(e, hz=float(v)))))
            c.append(reglage("move-horizontal", "Mise à l'échelle", "Taille du texte, des applications et des éléments",
                             droite=deroulant([(str(x), "%d %%" % int(x * 100)) for x in (1.0, 1.25, 1.5, 1.75, 2.0)], str(float(e["echelle"])),
                                              lambda v, e=e: self.ecran(e, echelle=float(v)))))
            c.append(reglage("rotate-ccw", "Orientation", "", droite=deroulant([("normal", "Paysage"), ("90", "Portrait"), ("180", "Paysage (retourné)"), ("270", "Portrait (retourné)")],
                                                                                e["rotation"], lambda v, e=e: self.ecran(e, rotation=v))))
        c.append(info("Les réglages d'écran sont mémorisés et réappliqués à chaque ouverture de session."))

    def ecran_perso(self, e, w, h, hz):
        """Essaie une résolution personnalisée : retour automatique à l'ancienne au bout de 15 s si on ne confirme pas (écran noir)."""
        ancien = (e["w"], e["h"], e["hz"])
        S.en_fond(S.regler_ecran, None, e["nom"], w, h, hz, None, None, None, True)
        d = Gtk.Window(transient_for=self.win, modal=True, title="Résolution personnalisée", default_width=420); d.add_css_class("parametres")
        v = boite(True, 12, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label("Garder %d × %d à %.0f Hz ?" % (w, h, hz), "page-titre")); msg = label("", "attenue", wrap=True); v.append(msg)
        n = [15]; fini = [False]
        def retour():
            if fini[0]: return
            fini[0] = True; S.en_fond(S.regler_ecran, None, e["nom"], ancien[0], ancien[1], ancien[2]); d.close()
        def garder():
            fini[0] = True
            ec = dict(self.cfg.get("ecrans", {})); dd = dict(ec.get(e["nom"], {})); dd.update(w=w, h=h, hz=hz, perso=True); ec[e["nom"]] = dd; self.regler(ecrans=ec); d.close()
        def tic():
            if fini[0]: return False
            n[0] -= 1; msg.set_text("Retour à l'ancienne résolution dans %d s." % n[0])
            if n[0] <= 0: retour(); return False
            return True
        tic(); GLib.timeout_add_seconds(1, tic)
        r = boite(False, 8, halign=Gtk.Align.END); r.append(bouton("Revenir", None, "fantome", rappel=retour)); r.append(bouton("Garder", None, "pilule", rappel=garder)); v.append(r)
        d.set_child(v); d.connect("close-request", lambda *_: (retour() if not fini[0] else None, False)[1]); d.present()

    def ecran(self, e, mode=None, hz=None, echelle=None, rotation=None):
        w = h = None
        if mode: w, h = map(int, mode.split("x"))
        S.en_fond(S.regler_ecran, None, e["nom"], w, h, hz, echelle, rotation)
        ec = dict(self.cfg.get("ecrans", {})); d = dict(ec.get(e["nom"], {}))
        if mode: d.update(w=w, h=h); d.pop("perso", None)
        if hz: d["hz"] = hz
        if echelle: d["echelle"] = echelle
        if rotation: d["rotation"] = rotation
        ec[e["nom"]] = d; self.regler(ecrans=ec)

    def p_son(self, c, cle):
        so, en, fl = S.sorties(), S.entrees(), S.flux_apps()
        c.append(groupe_titre("Sortie"))
        if so:
            d = next((s for s in so if s["defaut"]), so[0])
            c.append(reglage("speaker", "Choisir où lire le son", "", droite=deroulant([(s["nom"], s["desc"]) for s in so], d["nom"],
                                                                                    lambda v: S.en_fond(S.sortie_defaut, lambda _: self.aller("son", False), v), 320)))
            c.append(reglage("volume-2", "Volume", d["desc"], droite=dim(curseur(d["vol"], lambda v: S.en_fond(S.regler_volume, None, v)), 280)))
            c.append(reglage("volume-x", "Couper le son", "", droite=interrupteur(d["muet"], lambda on: S.en_fond(S.basculer_muet))))
            c.append(reglage("audio-lines" if os.path.exists(theme.LUCIDE + "/audio-lines.svg") else "volume-2", "Tester le son", "Joue un son court sur la sortie choisie",
                             droite=bouton("Tester", None, "fantome", rappel=lambda: S.detacher("timeout 2 speaker-test -t sine -f 523 -c 2 -l 1"))))
        else:
            c.append(info("Aucune sortie audio détectée."))
        c.append(groupe_titre("Entrée"))
        if en:
            d = next((s for s in en if s["defaut"]), en[0])
            c.append(reglage("mic", "Choisir un périphérique pour parler ou enregistrer", "", droite=deroulant([(s["nom"], s["desc"]) for s in en], d["nom"],
                                                                                                          lambda v: S.en_fond(S.entree_defaut, None, v), 320)))
            c.append(reglage("mic", "Volume d'entrée", d["desc"], droite=dim(curseur(d["vol"], lambda v: S.en_fond(S.regler_entree, None, v), 0, 150), 280)))
        else:
            c.append(info("Aucun micro détecté."))
        c.append(groupe_titre("Mélangeur de volume"))
        if not fl: c.append(info("Aucune application ne joue de son actuellement."))
        for f in fl:
            c.append(reglage("app-window", f["nom"], "", droite=dim(curseur(f["vol"], lambda v, i=f["idx"]: S.en_fond(S.regler_flux, None, i, v)), 280)))
        c.append(reglage("sliders-horizontal", "Réglages audio avancés", "Profils de carte son, ports, niveaux (pavucontrol)", clic=lambda: S.detacher("pavucontrol")))
        c.append(groupe_titre("Dépannage"))
        c.append(reglage("wrench", "Réparer le son", "Pas de son ? Relance le serveur de son, réactive les sorties muettes, essaie un autre pilote si besoin",
                         droite=bouton("Réparer", None, "pilule", rappel=lambda: (self.toast("Réparation du son…"), S.detacher("xiii-reparer-son")))))
        c.append(reglage("cpu", "Pilotes et firmwares", "Recherche approfondie du matériel son, graphique, Wi-Fi", clic=lambda: S.detacher("xiii-bilan --pilotes")))

        # ---- sons système (thème XIII)
        from . import sons
        c.append(groupe_titre("Sons système"))
        c.append(reglage("bell-ring", "Sons d'OS XIII", "Ouverture de session, notifications, clé USB branchée ou retirée, capture, erreurs. Silencieux en Ne pas déranger",
                         droite=interrupteur(self.cfg.get("sons_systeme", True), lambda on: self.regler(sons_systeme=on))))
        c.append(reglage("volume-1", "Volume des sons système", "", droite=dim(curseur(int(self.cfg.get("sons_volume", 70)), lambda v: self.regler(_histo=False, sons_volume=int(v)), 5, 100, 5), 260)))
        fl = Gtk.FlowBox(max_children_per_line=4, selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6)
        for k, n in (("desktop-login", "Ouverture"), ("message-new-instant", "Notification"), ("device-added", "Clé branchée"), ("device-removed", "Clé retirée"),
                     ("screen-capture", "Capture"), ("complete", "Terminé"), ("dialog-warning", "Attention"), ("dialog-error", "Erreur"), ("battery-low", "Batterie faible"), ("desktop-logout", "Fermeture")):
            fl.append(bouton(n, "play", "fantome", taille=13, rappel=lambda k=k: sons.jouer(k, self.cfg, force=True)))
        c.append(fl)
    def p_notifications(self, c, cle):
        cfg = self.cfg
        c.append(reglage("bell-off", "Ne pas déranger", "Les notifications arrivent en silence dans le volet",
                         droite=interrupteur(cfg["ne_pas_deranger"], lambda on: self.regler(ne_pas_deranger=on))))
        c.append(reglage("bell-dot", "Pastille sur l'icône de notifications", "Nombre de notifications non lues dans la barre des tâches",
                         droite=interrupteur(cfg["barre_badge"], lambda on: self.regler(barre_badge=on))))
        c.append(groupe_titre("Applications bloquées"))
        vues = []
        try: vues = json.load(open(os.path.join(GLib.get_user_cache_dir(), "xiii", "notif-apps.json")))
        except Exception: pass
        for a in sorted(set(vues + cfg["notif_bloquees"])):
            c.append(reglage("app-window", a, "Afficher les notifications de cette application",
                             droite=interrupteur(a not in cfg["notif_bloquees"], lambda on, a=a: self.bloquer(a, not on))))
        if not vues and not cfg["notif_bloquees"]:
            c.append(info("Les applications qui envoient des notifications apparaîtront ici."))
        c.append(reglage("bell", "Envoyer une notification de test", "", droite=bouton("Tester", None, "fantome",
                         rappel=lambda: S.detacher(["notify-send", "-a", "Paramètres", "-i", "preferences-system", "Notification de test", "Tout fonctionne. — OS XIII"]))))

    def bloquer(self, a, on):
        L = list(self.cfg["notif_bloquees"])
        if on and a not in L: L.append(a)
        if not on and a in L: L.remove(a)
        self.regler(notif_bloquees=L)

    def p_alimentation(self, c, cle):
        cfg = self.cfg; b = S.batterie()
        if b:
            h = boite(False, 16, "hero"); h.append(ico(icone_batterie(b), 44, "c"))
            v = boite(True, 2, valign=Gtk.Align.CENTER); v.append(label("%d %%" % b["pct"], "hero-grand")); v.append(label(b["etat"].capitalize() + (" · " + b["temps"] if b["temps"] else ""), "attenue"))
            h.append(v); c.append(h)
        c.append(groupe_titre("Mode d'alimentation"))
        dispo = S.profils_dispo()
        if dispo:
            c.append(reglage("gauge", "Mode d'alimentation", "Équilibre entre autonomie et performances",
                             droite=deroulant([(k, n) for k, n, _ in S.PROFILS if k in dispo], S.profil(), lambda v: S.en_fond(S.regler_profil, None, v))))
        else:
            c.append(info("Les profils d'alimentation ne sont pas disponibles sur cet ordinateur."))
        c.append(groupe_titre("Écran et mise en veille"))
        c.append(reglage("lock", "Verrouiller l'écran après inactivité", "", droite=interrupteur(cfg["verrou_actif"], lambda on: self.regler(verrou_actif=on))))
        c.append(reglage("timer", "Délai avant verrouillage", "", droite=deroulant([(str(s), t) for s, t in ((60, "1 minute"), (120, "2 minutes"), (300, "5 minutes"),
                         (600, "10 minutes"), (900, "15 minutes"), (1800, "30 minutes"), (3600, "1 heure"))], str(cfg["veille_ecran"]), lambda v: self.regler(veille_ecran=int(v)))))
        if b:
            capot = "suspend"
            try:
                capot = re.search(r"HandleLidSwitch=(\w+)", open("/etc/systemd/logind.conf.d/xiii.conf").read()).group(1)
            except Exception: pass
            c.append(reglage("laptop" if os.path.exists(theme.LUCIDE + "/laptop.svg") else "monitor", "Quand je ferme le capot", "",
                             droite=deroulant([("suspend", "Mettre en veille"), ("ignore", "Ne rien faire"), ("poweroff", "Éteindre"), ("lock", "Verrouiller")], capot,
                                              lambda v: S.en_fond(S.admin, None, "mkdir -p /etc/systemd/logind.conf.d && printf '[Login]\\nHandleLidSwitch=%s\\nHandleLidSwitchExternalPower=%s\\n' > /etc/systemd/logind.conf.d/xiii.conf && systemctl kill -s HUP systemd-logind" % (v, v)))))

    def p_stockage(self, c, cle):
        for d in S.disques():
            r = boite(True, 6, "reglage")
            h = boite(False, 10); h.append(ico("hard-drive", 22, "c")); h.append(label(d["nom"], "reglage-titre", hexpand=True))
            h.append(label("%s utilisés sur %s" % (S.humain(d["utilise"]), S.humain(d["total"])), "attenue")); r.append(h)
            lb = Gtk.LevelBar(min_value=0, max_value=1, value=d["utilise"] / max(1, d["total"])); r.append(lb)
            r.append(label("%s libres" % S.humain(d["libre"]), "reglage-sous")); c.append(r)
        c.append(groupe_titre("Dossiers personnels"))
        dossiers = [(GLib.get_user_special_dir(x) or "", n, ic) for x, n, ic in ((GLib.UserDirectory.DIRECTORY_DOCUMENTS, "Documents", "file-text"),
                    (GLib.UserDirectory.DIRECTORY_DOWNLOAD, "Téléchargements", "download"), (GLib.UserDirectory.DIRECTORY_PICTURES, "Images", "image"),
                    (GLib.UserDirectory.DIRECTORY_VIDEOS, "Vidéos", "film"), (GLib.UserDirectory.DIRECTORY_MUSIC, "Musique", "headphones"))]
        dossiers.append((os.path.join(GLib.get_user_data_dir(), "Trash"), "Corbeille", "trash-2"))
        for p, n, ic in dossiers:
            if not p: continue
            l = label("…", "attenue")
            c.append(reglage(ic, n, p.replace(os.path.expanduser("~"), "~"), droite=l, clic=lambda p=p: S.detacher(["thunar", p]) if os.path.isdir(p) else None))
            S.en_fond(S.taille_dossier, lambda t, l=l: l.set_text(S.humain(t) if not isinstance(t, Exception) else "—"), p)
        c.append(groupe_titre("Libérer de l'espace"))
        c.append(reglage("trash-2", "Vider la corbeille", "", droite=bouton("Vider", None, "fantome", rappel=lambda: (S.detacher("gio trash --empty"), self.plus_tard("stockage")))))
        c.append(reglage("image", "Miniatures en cache", "Recréées automatiquement au besoin",
                         droite=bouton("Nettoyer", None, "fantome", rappel=lambda: (shutil.rmtree(os.path.join(GLib.get_user_cache_dir(), "thumbnails"), True), self.plus_tard("stockage")))))
        c.append(reglage("package", "Paquets téléchargés et inutiles", "Nettoyage des fichiers d'installation (mot de passe demandé)",
                         droite=bouton("Nettoyer", None, "fantome", rappel=lambda: S.en_fond(S.admin, lambda r: self.toast("Nettoyage terminé"), "apt-get clean && apt-get -y autoremove"))))
        c.append(reglage("hard-drive", "Disques et partitions", "Formater, vérifier, monter (application Disques)", clic=lambda: S.detacher("gnome-disks")))

    def p_multitache(self, c, cle):
        snap = rc_valeur("snapping/range", defaut="10") != "0"
        c.append(reglage("app-window", "Ancrer les fenêtres", "Glisser une fenêtre contre un bord de l'écran pour la redimensionner (Super + flèches)",
                         droite=interrupteur(snap, lambda on: rc_ecrire(lambda r: setattr(rc_noeud(r, "snapping/range"), "text", "10" if on else "0")))))
        n = rc_valeur("desktops/number", defaut=None)
        if n is None:
            t = rc_lire().getroot().find("desktops"); n = t.get("number") if t is not None else "1"
        def bureaux(v):
            def m(r):
                d = rc_noeud(r, "desktops"); d.set("number", v)
            rc_ecrire(m)
        c.append(reglage("layout-dashboard", "Bureaux virtuels", "Nombre de bureaux (Super + Ctrl + ←/→ pour changer)",
                         droite=deroulant([(str(i), str(i)) for i in range(1, 7)], str(n or "1"), bureaux)))
        c.append(reglage("layout-panel-left", "Dispositions des fenêtres", "Moitiés, tiers, quarts… (Super + Z ou clic droit sur la vue des tâches)",
                         droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher(["xiii-ctl", "dispositions"]))))
        c.append(reglage("layout-dashboard", "Vue des tâches", "Toutes les fenêtres en un coup d'œil (Super + Tab)", droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher(["xiii-ctl", "vue"]))))
        c.append(reglage("history", "Rouvrir mes applications au démarrage", "Reprend les applications ouvertes lors de la dernière session",
                         droite=interrupteur(self.cfg.get("reprise_session", False), lambda on: self.regler(reprise_session=on))))
        c.append(reglage("layout-template", "Aperçu Alt + Tab", "Afficher la liste des fenêtres en changeant avec Alt + Tab",
                         droite=interrupteur(rc_lire().getroot().find("windowSwitcher") is None or rc_lire().getroot().find("windowSwitcher").get("show", "yes") == "yes",
                                             lambda on: rc_ecrire(lambda r: rc_noeud(r, "windowSwitcher").set("show", "yes" if on else "no")))))

    def p_profils(self, c, cle):
        from . import profils
        cur = profils.courant(self.cfg)[0]
        c.append(info("Un profil règle en un clic le silence des notifications, les performances et la mise en veille. Aussi dans le centre de contrôle et en haut de l'écran."))
        for k, nom, ic, desc, r in profils.PROFILS:
            det = ", ".join(x for x in (("silence" if r.get("dnd") else ""), {"performance": "performances max", "power-saver": "économie", "balanced": ""}.get(r.get("perf"), ""),
                                         ("jamais de veille" if r.get("eveil") else ""), ("lumière nocturne" if r.get("nuit") else "")) if x)
            b = bouton("Actif" if k == cur else "Activer", None, "pilule" if k == cur else "fantome",
                       rappel=lambda k=k: (self.regler(profil=k, mode_tournage=(k == "tournage")), self.aller("profils", False)))
            c.append(reglage(ic, nom, desc, droite=b))
        c.append(reglage("gamepad-2", "Profil Jeu : lancer Steam en mode console", "Big Picture plein écran, à la manette", droite=interrupteur(self.cfg.get("jeu_console", False), lambda on: self.regler(jeu_console=on))))

    def p_historique(self, c, cle):
        h = config.historique()
        if not h: c.append(info("Aucun changement enregistré pour l'instant.")); return
        c.append(info("Chaque changement de réglage peut être annulé ici, même plusieurs jours après."))
        noms = {"theme": "Thème", "accent": "Couleur d'accent", "fond": "Fond d'écran", "barre_alignement": "Alignement de la barre", "transparence": "Transparence",
                "animations": "Animations", "profil": "Profil", "ne_pas_deranger": "Ne pas déranger", "lumiere_nocturne": "Lumière nocturne", "taille_texte": "Taille du texte",
                "police": "Police", "widgets": "Widgets", "coins": "Coins actifs", "timecode": "Timecode", "projet_actif": "Projet actif"}
        def fmt(v):
            if isinstance(v, bool): return "activé" if v else "désactivé"
            if isinstance(v, str) and v.startswith("/"): return os.path.basename(v)
            if isinstance(v, (list, dict)): return "…"
            return str(v)
        for i, e in enumerate(h[:40]):
            t = ", ".join("%s : %s → %s" % (noms.get(k, k.replace("_", " ")), fmt(v), fmt(e["apres"].get(k))) for k, v in e["avant"].items())
            quand = datetime.datetime.fromtimestamp(e["t"]).strftime("%d/%m %H:%M")
            c.append(reglage("undo-2", t, quand, droite=bouton("Annuler", None, "fantome", rappel=lambda e=e: (self.regler(**e["avant"]), self.toast("Réglage rétabli"), self.aller("historique", False)))))

    def p_apropos(self, c, cle):
        i = S.infos_systeme()
        h = boite(False, 18, "hero")
        h.append(vignette("/usr/share/xiii/logos/xiii-orange.png", 90, 74, couvrir=False))
        v = boite(True, 4, hexpand=True, valign=Gtk.Align.CENTER); v.append(label(i["hote"], "hero-grand")); v.append(label(i["nom"], "attenue")); h.append(v)
        h.append(bouton("Renommer ce PC", None, "fantome", rappel=self.renommer)); c.append(h)
        c.append(groupe_titre("Caractéristiques de l'appareil"))
        txt = []
        for k, n in (("cpu", "Processeur"), ("ram", "Mémoire vive"), ("gpu", "Carte graphique"), ("arch", "Architecture")):
            c.append(reglage(None, n, None, droite=label(i[k], "attenue", xalign=1, selectable=True, ellipsize=True, largeur=60))); txt.append("%s : %s" % (n, i[k]))
        tot, util, zu, zc = S.memoire()
        if tot:
            pb = Gtk.ProgressBar(fraction=min(1, util / tot), valign=Gtk.Align.CENTER, hexpand=True); pb.set_size_request(160, -1)
            c.append(reglage(None, "Mémoire utilisée", "%s sur %s" % (S.humain(util), S.humain(tot)), droite=pb))
            c.append(reglage(None, "Mémoire compressée (zram)",
                             ("Active · %s rangés dans %s" % (S.humain(zu), S.humain(zc))) if zu else ("Active · inutilisée pour l'instant" if S.zram_actif() else "Inactive"),
                             droite=None))
        c.append(groupe_titre("Caractéristiques du système"))
        for k, n in (("nom", "Système"), ("base", "Base"), ("noyau", "Noyau Linux"), ("uptime", "Allumé depuis")):
            c.append(reglage(None, n, None, droite=label(i[k], "attenue", xalign=1, selectable=True))); txt.append("%s : %s" % (n, i[k]))
        r = boite(False, 8, margin_top=10)
        r.append(bouton("Copier", "copy", "fantome", taille=14, rappel=lambda: (Gdk.Display.get_default().get_clipboard().set_text("\n".join(txt)), self.toast("Copié"))))
        r.append(bouton("Bilan matériel", "gauge", "fantome", taille=14, rappel=lambda: S.detacher("xiii-bilan")))
        r.append(bouton("Pilotes", "cpu", "fantome", taille=14, rappel=lambda: S.detacher("xiii-bilan --pilotes"))); c.append(r)
        c.append(info("OS XIII — basé sur Debian. Icônes Lucide (licence ISC). Application développée par Matthieu Lamotte."))

    def renommer(self):
        def ok(nom):
            nom = re.sub(r"[^a-zA-Z0-9-]", "-", nom).strip("-")[:63]
            if nom: S.en_fond(S.admin, lambda r: self.aller("apropos", False), ["hostnamectl", "set-hostname", nom])
        demander(self.win, "Renommer ce PC", "Nouveau nom (lettres, chiffres, tirets)", os.uname().nodename, ok)

    # ================================================================== APPAREILS
    def p_bluetooth(self, c, cle):
        if not S.bt_present():
            c.append(info("Aucun adaptateur Bluetooth détecté sur cet ordinateur.")); return
        on = S.bt_actif()
        c.append(reglage("bluetooth", "Bluetooth", "Visible sous le nom « %s »" % os.uname().nodename if on else "Désactivé",
                         droite=interrupteur(on, lambda v: S.en_fond(S.bt_activer, lambda _: self.aller("bluetooth", False), v))))
        if not on: return
        c.append(groupe_titre("Appareils"))
        L = S.bt_appareils()
        if not L: c.append(info("Aucun appareil appairé."))
        for d in L:
            dr = boite(False, 6)
            dr.append(bouton("Déconnecter" if d["connecte"] else "Connecter", None, "fantome",
                             rappel=lambda d=d: S.en_fond(S.bt_connecter, lambda _: self.aller("bluetooth", False), d["mac"], not d["connecte"])))
            dr.append(bouton(None, "trash-2", "plat", taille=16, tip="Supprimer l'appareil", rappel=lambda d=d: S.en_fond(S.bt_oublier, lambda _: self.aller("bluetooth", False), d["mac"])))
            sous = ("Connecté" if d["connecte"] else "Appairé") + (" · batterie %d %%" % d["batterie"] if d["batterie"] is not None else "")
            c.append(reglage(None, d["nom"], sous, droite=dr, gicon=Gio.ThemedIcon.new(d["icone"])))
        c.append(groupe_titre("Ajouter un appareil"))
        zone = boite(True, 4)
        sp = Gtk.Spinner()
        def scan():
            vider(zone); zone.append(sp); sp.start()
            S.en_fond(S.bt_rechercher, trouves)
        def trouves(L):
            vider(zone)
            if isinstance(L, Exception) or not L: zone.append(info("Aucun appareil trouvé. Mettez l'appareil en mode appairage puis relancez.")); return
            for d in L:
                b = bouton("Appairer", None, "pilule")
                b.connect("clicked", lambda _b, d=d: (_b.set_sensitive(False), S.en_fond(S.bt_appairer, lambda r: self.aller("bluetooth", False), d["mac"])))
                zone.append(reglage(None, d["nom"], d["mac"], droite=b, gicon=Gio.ThemedIcon.new(d["icone"])))
        c.append(reglage("plus", "Rechercher des appareils à proximité", "Casques, enceintes, souris, claviers, manettes…", droite=bouton("Rechercher", None, "pilule", rappel=scan)))
        c.append(zone)
        c.append(reglage("settings-2", "Gestionnaire Bluetooth avancé", "Code PIN, transfert de fichiers, profils", clic=lambda: S.detacher("blueman-manager")))

    def p_imprimantes(self, c, cle):
        o = S.out("lpstat -p 2>/dev/null"); d = S.out("lpstat -d 2>/dev/null")
        defaut = d.split(":")[-1].strip() if ":" in d else ""
        L = re.findall(r"^printer (\S+)", o, re.M) if not S.DEMO else ["Brother_HL-L2350DW"]
        c.append(reglage("plus", "Ajouter une imprimante ou un scanner", "Détection automatique des imprimantes réseau et USB", droite=bouton("Ajouter", None, "pilule", rappel=lambda: S.detacher("system-config-printer"))))
        c.append(groupe_titre("Imprimantes"))
        if not L: c.append(info("Aucune imprimante installée."))
        for p in L:
            dr = boite(False, 6)
            if p != defaut:
                dr.append(bouton("Définir par défaut", None, "fantome", rappel=lambda p=p: (S.sh(["lpoptions", "-d", p]), self.aller("imprimantes", False))))
            c.append(reglage("printer", p.replace("_", " "), "Par défaut" if p == defaut else "Prête", droite=dr))
        c.append(reglage("settings-2", "Gérer les imprimantes", "Files d'attente, options, page de test", clic=lambda: S.detacher("system-config-printer")))

    def p_souris(self, c, cle):
        def _li(cat, k, d):
            r = rc_lire().getroot().find("libinput")
            if r is None: return d
            for dev in r.findall("device"):
                if dev.get("category") == cat:
                    e = dev.find(k)
                    if e is not None and e.text: return e.text.strip()
            return d
        def ecrire(cat, k, v):
            def m(r):
                dev = rc_noeud(r, "libinput/device", {"category": cat})
                e = dev.find(k)
                if e is None: e = ET.SubElement(dev, k)
                e.text = v
            rc_ecrire(m)
        c.append(groupe_titre("Souris"))
        c.append(reglage("mouse", "Vitesse du pointeur", "", droite=dim(curseur(float(_li("default", "pointerSpeed", "0")) * 50 + 50,
                         lambda v: ecrire("default", "pointerSpeed", "%.2f" % ((v - 50) / 50)), 0, 100, 1, 400), 260)))
        c.append(reglage("move-horizontal", "Bouton principal", "", droite=deroulant([("no", "Gauche"), ("yes", "Droit (gaucher)")], _li("default", "leftHanded", "no"),
                                                                                       lambda v: ecrire("default", "leftHanded", v))))
        c.append(reglage("chevron-down", "Défilement naturel (souris)", "Le contenu suit le mouvement de la molette",
                         droite=interrupteur(_li("default", "naturalScroll", "no") == "yes", lambda on: ecrire("default", "naturalScroll", "yes" if on else "no"))))
        c.append(groupe_titre("Pavé tactile"))
        c.append(reglage("hand", "Toucher pour cliquer", "", droite=interrupteur(_li("touchpad", "tap", "yes") == "yes", lambda on: ecrire("touchpad", "tap", "yes" if on else "no"))))
        c.append(reglage("chevron-down", "Défilement naturel", "", droite=interrupteur(_li("touchpad", "naturalScroll", "yes") == "yes",
                                                                                      lambda on: ecrire("touchpad", "naturalScroll", "yes" if on else "no"))))
        c.append(reglage("keyboard", "Désactiver pendant la frappe", "", droite=interrupteur(_li("touchpad", "disableWhileTyping", "yes") == "yes",
                                                                                            lambda on: ecrire("touchpad", "disableWhileTyping", "yes" if on else "no"))))
        c.append(reglage("mouse-pointer-2", "Vitesse du pavé tactile", "", droite=dim(curseur(float(_li("touchpad", "pointerSpeed", "0")) * 50 + 50,
                         lambda v: ecrire("touchpad", "pointerSpeed", "%.2f" % ((v - 50) / 50)), 0, 100, 1, 400), 260)))
        c.append(reglage("mouse-pointer-2", "Taille du pointeur", "", clic=lambda: self.aller("curseur")))

    def p_clavier(self, c, cle):
        env = os.path.join(GLib.get_user_config_dir(), "labwc", "environment")
        try: lay = re.search(r"XKB_DEFAULT_LAYOUT=(\S+)", open(env).read()).group(1)
        except Exception: lay = "fr"
        def disp(v):
            try: lignes = [l for l in open(env).read().splitlines() if not l.startswith("XKB_DEFAULT_LAYOUT=")]
            except OSError: lignes = []
            lignes.append("XKB_DEFAULT_LAYOUT=" + v)
            open(env, "w").write("\n".join(lignes) + "\n")
            S.en_fond(S.admin, None, ["localectl", "set-x11-keymap", v.split(",")[0]])
            self.toast("Disposition enregistrée — effective à la prochaine connexion")
        c.append(reglage("keyboard", "Disposition du clavier", "Appliquée à la prochaine ouverture de session",
                         droite=deroulant([("fr", "Français (AZERTY)"), ("fr(mac)", "Français (Mac)"), ("be", "Belge"), ("ch(fr)", "Suisse romand"), ("ca", "Canadien français"),
                                           ("us", "Anglais (US, QWERTY)"), ("gb", "Anglais (UK)"), ("de", "Allemand"), ("es", "Espagnol"), ("it", "Italien")], lay, disp, 260)))
        rate = rc_valeur("keyboard/repeatRate", defaut="25"); delay = rc_valeur("keyboard/repeatDelay", defaut="600")
        c.append(reglage("timer", "Délai avant répétition", "", droite=dim(curseur(int(delay), lambda v: rc_ecrire(lambda r: setattr(rc_noeud(r, "keyboard/repeatDelay"), "text", str(int(v)))), 150, 1000, 10, 500), 260)))
        c.append(reglage("gauge", "Vitesse de répétition", "", droite=dim(curseur(int(rate), lambda v: rc_ecrire(lambda r: setattr(rc_noeud(r, "keyboard/repeatRate"), "text", str(int(v)))), 5, 60, 1, 500), 260)))
        c.append(groupe_titre("Raccourcis clavier"))
        c.append(reglage("command", "Tous les raccourcis clavier", "Changer, ajouter ou supprimer n'importe quel raccourci du système", clic=lambda: self.aller("raccourcis")))

    def p_raccourcis(self, c, cle):
        from . import raccourcis as R
        L = R.lire(); lignes = []
        def enregistrer(msg="Raccourcis enregistrés"):
            R.ecrire(L); self.toast(msg); self.aller("raccourcis", False)
        haut = boite(False, 8)
        rech = Gtk.SearchEntry(placeholder_text="Rechercher un raccourci ou une touche…", hexpand=True); haut.append(rech)
        haut.append(bouton("Ajouter", "plus", "pilule", rappel=lambda: self.raccourci_nouveau(L, enregistrer)))
        haut.append(bouton(None, "more-vertical", "fantome", tip="Plus d'options", rappel=lambda: popover_menu(haut, [
            ("download", "Exporter mes raccourcis…", lambda: self.raccourcis_fichier(L, True)),
            ("upload", "Importer des raccourcis…", lambda: self.raccourcis_fichier(L, False)),
            None,
            ("rotate-ccw", "Revenir aux raccourcis d'origine", lambda: confirmer(self.win, "Revenir aux raccourcis d'origine ?", "Tous vos changements de raccourcis seront perdus.", "Réinitialiser",
                                                                            lambda _: (R.reinitialiser(), self.toast("Raccourcis d'origine rétablis"), self.aller("raccourcis", False))))])))
        c.append(haut)
        c.append(info("Cliquez sur une combinaison pour la changer, puis appuyez sur les nouvelles touches. Les changements s'appliquent tout de suite. "
                      "Les raccourcis internes aux applications (Ctrl+C, Ctrl+S…) se règlent dans chaque application."))
        for cat in R.CATEGORIES:
            idx = [i for i, s in enumerate(L) if s["categorie"] == cat]
            if not idx: continue
            t = groupe_titre(cat); c.append(t); grp = []
            for i in sorted(idx, key=lambda i: L[i]["texte"].lower()):
                s = L[i]
                droite = boite(False, 6)
                bk = bouton(R.humain(s["cle"]), None, "fantome", "mono", tip="Changer la combinaison"); bk.connect("clicked", lambda _b, i=i: self.raccourci_capturer(L, i, enregistrer)); droite.append(bk)
                droite.append(bouton(None, "more-vertical", "fantome", tip="Options", rappel=lambda i=i, w=droite: popover_menu(w, [
                    ("keyboard", "Changer la combinaison", lambda: self.raccourci_capturer(L, i, enregistrer)),
                    ("copy-plus", "Ajouter une autre combinaison", lambda: self.raccourci_capturer(L, i, enregistrer, doubler=True)),
                    ("pencil", "Changer l'action", lambda: self.raccourci_nouveau(L, enregistrer, remplacer=i)),
                    None,
                    ("trash-2", "Supprimer ce raccourci", lambda: (L.pop(i), enregistrer("Raccourci supprimé")))])))
                r = reglage(None, s["texte"], None, droite=droite); c.append(r)
                lignes.append((r, (s["texte"] + " " + R.humain(s["cle"]) + " " + s["cle"]).lower(), t)); grp.append(r)
        def filtrer(*_):
            q = rech.get_text().lower().strip(); vis_titres = {}
            for r, txt, t in lignes:
                v = not q or all(m in txt for m in q.split()); r.set_visible(v); vis_titres[t] = vis_titres.get(t, False) or v
            for t, v in vis_titres.items(): t.set_visible(v)
        rech.connect("search-changed", filtrer)

    def raccourci_capturer(self, L, i, enregistrer, doubler=False, nouveau=None):
        """Fenêtre qui attend la nouvelle combinaison. i = index dans L (None si nouveau raccourci → nouveau = dict)."""
        from . import raccourcis as R
        cible = nouveau if nouveau is not None else L[i]
        d = Gtk.Window(transient_for=self.win, modal=True, title="Nouveau raccourci", default_width=460); d.add_css_class("parametres")
        v = boite(True, 12, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label(cible.get("texte") or R.decrire(cible["actions"])[0], "page-titre", wrap=True))
        v.append(label("Appuyez sur la nouvelle combinaison de touches. Échap pour annuler, Retour arrière pour retirer la touche.", "attenue", wrap=True))
        aff = label("…", "hero-grand", xalign=0.5); v.append(aff)
        msg = label("", "attenue", wrap=True, xalign=0.5); v.append(msg)
        res = {"cle": None, "onrelease": False, "super_seul": False}
        # saisie manuelle (si une touche est déjà prise par le système et n'arrive pas ici)
        man = boite(False, 6, halign=Gtk.Align.CENTER)
        cases = {}
        for m, n in (("W", "Super"), ("C", "Ctrl"), ("A", "Alt"), ("S", "Maj")):
            cb = Gtk.CheckButton(label=n); cases[m] = cb; man.append(cb)
        ent = Gtk.Entry(placeholder_text="touche (ex : e, F5, Print)", width_chars=14); man.append(ent)
        def manuel(*_):
            t = ent.get_text().strip()
            if not t: return
            choisir("-".join([m for m in R.ORDRE_MODS if cases[m].get_active()] + [t]), False)
        ent.connect("activate", manuel)
        exp = Gtk.Expander(label="Saisir à la main"); bx = boite(True, 6); bx.append(man); bx.append(bouton("Utiliser", None, "fantome", rappel=manuel)); exp.set_child(bx); v.append(exp)
        r = boite(False, 8, halign=Gtk.Align.END)
        b_ok = bouton("Enregistrer", None, "pilule"); b_ok.set_sensitive(False)
        r.append(bouton("Annuler", None, "fantome", rappel=d.close)); r.append(b_ok); v.append(r)
        conf = [None]
        def choisir(cle, onrel):
            res["cle"], res["onrelease"] = cle, onrel
            aff.set_text(R.humain(cle))
            conf[0] = R.conflit(L, cle, sauf=None if doubler or i is None else i)
            if conf[0] is not None:
                msg.set_text("Déjà utilisé par « %s ». Enregistrer le retirera de cette action." % L[conf[0]]["texte"])
            else: msg.set_text("")
            b_ok.set_sensitive(True)
        def valider(*_):
            if not res["cle"]: return
            j = conf[0]
            if j is not None: L[j] = dict(L[j], cle="")
            if nouveau is not None: L.append(dict(nouveau, cle=res["cle"], onrelease=res["onrelease"]))
            elif doubler: L.append(dict(L[i], cle=res["cle"], onrelease=res["onrelease"]))
            else: L[i] = dict(L[i], cle=res["cle"], onrelease=res["onrelease"])
            L[:] = [s for s in L if s.get("cle")]
            d.close(); enregistrer()
        b_ok.connect("clicked", valider)
        k = Gtk.EventControllerKey(); k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        def appui(_c, kv, _code, etat):
            if ent.has_focus(): return False
            nom = Gdk.keyval_name(kv) or ""
            if kv == Gdk.KEY_Escape and not (etat & Gtk.accelerator_get_default_mod_mask()): d.close(); return True
            if kv == Gdk.KEY_BackSpace and not (etat & Gtk.accelerator_get_default_mod_mask()):
                if nouveau is None and not doubler:
                    L.pop(i); d.close(); enregistrer("Raccourci retiré")
                return True
            if nom in ("Super_L", "Super_R"): res["super_seul"] = nom; return True
            res["super_seul"] = False
            c2 = R.depuis_gdk(kv, etat)
            if c2: choisir(c2, False)
            return True
        def relache(_c, kv, _code, etat):
            nom = Gdk.keyval_name(kv) or ""
            if res["super_seul"] == nom: choisir(nom, True); res["super_seul"] = False
        k.connect("key-pressed", appui); k.connect("key-released", relache); d.add_controller(k)
        d.set_child(v); d.present()
        # demande au compositeur de laisser passer ses propres raccourcis pendant la saisie
        def inhiber():
            try: d.get_surface().inhibit_system_shortcuts(None)
            except Exception: pass
            return False
        GLib.timeout_add(150, inhiber)
        def liberer(*_):
            try: d.get_surface().restore_system_shortcuts()
            except Exception: pass
            return False
        d.connect("close-request", liberer)

    def raccourci_nouveau(self, L, enregistrer, remplacer=None):
        """Choisir l'action d'un raccourci : application, action du système ou commande libre."""
        from . import raccourcis as R
        d = Gtk.Window(transient_for=self.win, modal=True, title="Action du raccourci", default_width=480); d.add_css_class("parametres")
        v = boite(True, 12, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label("Que doit faire ce raccourci ?", "page-titre"))
        pile = Gtk.Stack(); choix = Gtk.StackSwitcher(stack=pile, halign=Gtk.Align.CENTER); v.append(choix); v.append(pile)
        aps = apps.toutes()
        dd_app = Gtk.DropDown(model=Gtk.StringList.new([a.get_display_name() for a in aps])); dd_app.set_enable_search(True)
        dd_app.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        p1 = boite(True, 8); p1.append(label("Ouvrir une application", "attenue")); p1.append(dd_app); pile.add_titled(p1, "app", "Application")
        dd_act = Gtk.DropDown(model=Gtk.StringList.new(["%s — %s" % (x[3], x[2]) for x in R.ACTIONS])); dd_act.set_enable_search(True)
        dd_act.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        p2 = boite(True, 8); p2.append(label("Fenêtres, bureaux, système, son…", "attenue")); p2.append(dd_act); pile.add_titled(p2, "act", "Action du système")
        e_cmd = Gtk.Entry(placeholder_text="ex : firefox --private-window"); e_nom = Gtk.Entry(placeholder_text="Nom affiché (facultatif)")
        p3 = boite(True, 8); p3.append(label("N'importe quelle commande", "attenue")); p3.append(e_cmd); p3.append(e_nom); pile.add_titled(p3, "cmd", "Commande")
        def suite(*_):
            page = pile.get_visible_child_name()
            if page == "app":
                if not aps: return
                a = aps[dd_app.get_selected()]; acts = [("Execute", {"command": "gio launch " + (a.get_filename() or "")})]; txt = "Ouvrir " + a.get_display_name()
            elif page == "act":
                x = R.ACTIONS[dd_act.get_selected()]; acts = [(x[0], dict(x[1]))]; txt = x[2]
            else:
                cmd = e_cmd.get_text().strip()
                if not cmd: return
                acts = [("Execute", {"command": cmd})]; txt = e_nom.get_text().strip() or "Commande : " + cmd
            d.close()
            if remplacer is not None:
                L[remplacer] = dict(L[remplacer], actions=acts, texte=txt); enregistrer("Action changée")
            else:
                self.raccourci_capturer(L, None, enregistrer, nouveau={"actions": acts, "texte": txt, "categorie": "Personnalisés"})
        r = boite(False, 8, halign=Gtk.Align.END)
        r.append(bouton("Annuler", None, "fantome", rappel=d.close)); r.append(bouton("Valider" if remplacer is not None else "Choisir la touche…", None, "pilule", rappel=suite)); v.append(r)
        d.set_child(v); d.present()

    def raccourcis_fichier(self, L, export):
        from . import raccourcis as R
        fd = Gtk.FileDialog(title="Exporter les raccourcis" if export else "Importer des raccourcis")
        f = Gtk.FileFilter(); f.set_name("Raccourcis OS XIII (.json)"); f.add_pattern("*.json"); st = Gio.ListStore.new(Gtk.FileFilter); st.append(f); fd.set_filters(st)
        def fini(dlg, res):
            try: g = dlg.save_finish(res) if export else dlg.open_finish(res)
            except GLib.Error: return
            try:
                if export: R.exporter(g.get_path(), L); self.toast("Raccourcis exportés")
                else: n = R.importer(g.get_path()); self.toast("%d raccourcis importés" % n); self.aller("raccourcis", False)
            except Exception as e: self.toast("Échec : %s" % e)
        if export: fd.set_initial_name("raccourcis-xiii.json"); fd.save(self.win, None, fini)
        else: fd.open(self.win, None, fini)

    def p_webcam(self, c, cle):
        cams = sorted(glob.glob("/dev/video*")) if not S.DEMO else ["/dev/video0"]
        if not cams: c.append(info("Aucune caméra détectée.")); return
        for v in cams:
            nom = S.out("cat /sys/class/video4linux/%s/name 2>/dev/null" % os.path.basename(v)) or v
            c.append(reglage("webcam", nom, v, droite=bouton("Tester", None, "fantome", rappel=lambda v=v: S.detacher(["mpv", "--title=Test caméra XIII", "--profile=low-latency", "--untimed", "av://v4l2:" + v]))))

    def p_autoplay(self, c, cle):
        c.append(reglage("usb", "Monter automatiquement les clés et disques", "Ils apparaissent dans les fichiers dès leur branchement, avec une notification",
                         droite=interrupteur(self.cfg["montage_auto"], lambda on: self.regler(montage_auto=on))))
        c.append(reglage("hard-drive", "Gérer les disques", "Formater, vérifier, créer des partitions", clic=lambda: S.detacher("gnome-disks")))

    # ================================================================== RÉSEAU
    def p_reseau(self, c, cle):
        e = S.etat_reseau()
        h = boite(False, 16, "hero")
        h.append(ico("ethernet-port" if e["type"] == "ethernet" else icone_wifi(e["signal"]) if e["type"] else "wifi-off", 40, "c"))
        v = boite(True, 2, valign=Gtk.Align.CENTER, hexpand=True)
        v.append(label(e["nom"] or "Non connecté", "hero-grand")); v.append(label(("Connecté · " + e["ip"]) if e["type"] else "Aucune connexion Internet", "attenue"))
        h.append(v); c.append(h)
        for p in PAGES:
            if p[3] == "reseau": c.append(reglage(p[2], p[1], p[4], clic=lambda k=p[0]: self.aller(k)))
        c.append(reglage("plane", "Mode avion", "Coupe le Wi-Fi et le Bluetooth", droite=interrupteur(e["avion"], lambda on: S.en_fond(S.mode_avion, lambda _: self.aller("reseau", False), on))))
        c.append(reglage("settings-2", "Paramètres réseau avancés", "IP fixe, DNS, proxy, 802.1X…", clic=lambda: S.detacher("nm-connection-editor")))

    def p_wifi(self, c, cle):
        on = S.wifi_actif()
        c.append(reglage("wifi", "Wi-Fi", "", droite=interrupteur(on, lambda v: S.en_fond(S.wifi_activer, lambda _: self.aller("wifi", False), v))))
        if not on: return
        e = S.etat_reseau()
        if e["type"] == "wifi":
            c.append(groupe_titre("Réseau actuel"))
            dr = boite(False, 6)
            dr.append(bouton("QR code / mot de passe", "qr-code", "fantome", taille=14, rappel=lambda: self.qr_wifi(e["nom"])))
            dr.append(bouton("Déconnecter", None, "plat", rappel=lambda: S.en_fond(S.wifi_deconnecter, lambda _: self.aller("wifi", False))))
            c.append(reglage(icone_wifi(e["signal"]), e["nom"], "Connecté · %s · signal %d %%" % (e["ip"], e["signal"]), droite=dr))
        c.append(groupe_titre("Réseaux disponibles"))
        zone = boite(True, 3); c.append(zone); zone.append(Gtk.Spinner(spinning=True, halign=Gtk.Align.START))
        def rendu(L):
            vider(zone)
            if isinstance(L, Exception) or not L: zone.append(info("Aucun réseau trouvé.")); return
            for n in L:
                if n["actif"]: continue
                b = bouton("Se connecter", None, "fantome")
                b.connect("clicked", lambda _b, n=n: self.connecter(n))
                c2 = reglage(icone_wifi(n["signal"]), n["ssid"], ("Enregistré · " if n["connu"] else "") + (n["secu"] or "Ouvert") + " · %d %%" % n["signal"], droite=b)
                zone.append(c2)
        S.en_fond(S.reseaux_wifi, rendu, True)
        c.append(groupe_titre("Réseaux connus"))
        connus = [l.split(":")[0] for l in S.out(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"]).splitlines() if l.endswith("802-11-wireless")] if not S.DEMO else ["Studio-XIII", "Plateau-B"]
        for n in connus:
            c.append(reglage("wifi", n, "Enregistré", droite=bouton("Oublier", None, "plat", rappel=lambda n=n: S.en_fond(S.wifi_oublier, lambda _: self.aller("wifi", False), n))))
        c.append(reglage("plus", "Ajouter un réseau masqué ou avancé", "", clic=lambda: S.detacher("nm-connection-editor")))

    def connecter(self, n):
        if n["secu"] and not n["connu"]:
            demander(self.win, "Se connecter à « %s »" % n["ssid"], "Mot de passe du réseau", "",
                     lambda mdp: S.en_fond(S.wifi_connecter, lambda r: (self.toast("Connecté" if not isinstance(r, Exception) and r[0] else "Échec de la connexion"), self.aller("wifi", False)), n["ssid"], mdp), secret=True)
        else:
            S.en_fond(S.wifi_connecter, lambda r: self.aller("wifi", False), n["ssid"])

    def qr_wifi(self, ssid):
        mdp = "motdepasse-demo" if S.DEMO else S.out(["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", ssid])
        chemin = os.path.join(GLib.get_user_cache_dir(), "xiii", "wifi-qr.png"); os.makedirs(os.path.dirname(chemin), exist_ok=True)
        esc = lambda s: re.sub(r'([\\;,:"])', r"\\\1", s)
        S.sh(["qrencode", "-o", chemin, "-s", "10", "-m", "2", "WIFI:T:%s;S:%s;P:%s;;" % ("WPA" if mdp else "nopass", esc(ssid), esc(mdp))])
        d = Gtk.Window(transient_for=self.win, modal=True, title="Partager « %s »" % ssid, default_width=420); d.add_css_class("parametres")
        v = boite(True, 12, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label("Partager le Wi-Fi", "page-titre"))
        v.append(label("Scannez ce code avec un téléphone pour rejoindre « %s »." % ssid, "attenue", wrap=True))
        if os.path.exists(chemin):
            v.append(vignette(chemin, 300, 300, couvrir=False))
        else:
            v.append(info("Générateur de QR code indisponible."))
        r = boite(False, 8); r.append(label("Mot de passe :", "attenue")); r.append(label(mdp or "(réseau ouvert)", "mono", "accent", selectable=True)); v.append(r)
        v.append(bouton("Fermer", None, "pilule", rappel=d.close)); d.set_child(v); d.present()

    def p_ethernet(self, c, cle):
        L = [i for i in S.details_interfaces() if i["type"] == "ethernet"]
        if not L: c.append(info("Aucun port Ethernet sur cet ordinateur.")); return
        for i in L:
            c.append(groupe_titre(i["dev"]))
            c.append(reglage("ethernet-port", "État", None, droite=label(i["etat"] + (" · " + i["conn"] if i["conn"] else ""), "attenue")))
            for k, n in (("ip", "Adresse IPv4"), ("passerelle", "Passerelle"), ("dns", "Serveur DNS"), ("mac", "Adresse physique (MAC)")):
                c.append(reglage(None, n, None, droite=label(i[k] or "—", "mono", selectable=True)))
        for i in L:
            c.append(reglage("settings-2", "Régler %s (IP fixe, rôle Internet…)" % i["dev"], "", clic=lambda d=i["dev"]: (setattr(self, "iface_sel", d), self.aller("iface"))))

    def p_vpn(self, c, cle):
        L = S.vpns()
        c.append(reglage("plus", "Ajouter une connexion VPN", "WireGuard, OpenVPN… ou importer un fichier", droite=bouton("Ajouter", None, "pilule", rappel=lambda: S.detacher("nm-connection-editor"))))
        if not L: c.append(info("Aucun VPN configuré."))
        for v in L:
            c.append(reglage("shield", v["nom"], "Connecté" if v["actif"] else "Déconnecté",
                             droite=interrupteur(v["actif"], lambda on, n=v["nom"]: S.en_fond(S.vpn_basculer, lambda _: self.aller("vpn", False), n, on))))

    def p_partage(self, c, cle):
        nom = Gtk.Entry(text="XIII-" + os.uname().nodename[:12]); mdp = Gtk.PasswordEntry(show_peek_icon=True); mdp.set_text("xiii" + str(abs(hash(os.uname().nodename)) % 100000).zfill(5))
        c.append(info("Partagez la connexion de cet ordinateur (câble, 4G USB…) en créant un point d'accès Wi-Fi."))
        c.append(reglage("radio-tower", "Nom du réseau", None, droite=dim(nom, 260)))
        c.append(reglage("lock", "Mot de passe (8 caractères minimum)", None, droite=dim(mdp, 260)))
        c.append(reglage("wifi", "Point d'accès", "Le Wi-Fi de cet ordinateur sera utilisé pour le partage",
                         droite=interrupteur(False, lambda on: S.en_fond(S.point_acces, lambda r: self.toast(("Point d'accès actif" if on else "Point d'accès arrêté") if not isinstance(r, Exception) and r[0] else "Impossible : " + (r[1] if not isinstance(r, Exception) else str(r))),
                                                                       nom.get_text(), mdp.get_text(), on))))

    # ------------------------------------------------------------------ Réseau XIII (phase 10)
    def p_interfaces(self, c, cle):
        from . import reseau as R
        L = R.interfaces() if not S.DEMO else R.interfaces()
        sortie = R.route_defaut() if not S.DEMO else "wlan0"
        d = R.duo_etat()
        h = boite(False, 16, "hero"); h.append(ico("network", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label("Interfaces réseau", "hero-grand"))
        v.append(label("Sortie Internet : " + ("XIII Duo (%s)" % " + ".join(d.get("actifs", [])) if sortie == "duo" else (sortie or "aucune")), "attenue")); h.append(v); c.append(h)
        c.append(info("Chaque connexion se règle séparément : par exemple le câble en IP fixe pour piloter la régie, et le Wi-Fi en automatique pour garder Internet, en même temps."))
        c.append(groupe_titre("Interfaces"))
        self._trafic = {}; self._lab_trafic = {}
        for i in L:
            mode = {"auto": "automatique (DHCP)", "manual": "IP fixe"}.get(i["mode"], "—")
            sous = " · ".join(x for x in (i["etat"], i["connexion"], i["ip"], mode if i["uuid"] else "", ("Internet" if i["internet"] else ("réseau local seulement" if i["jamais_defaut"] else "")), i["debit"]) if x)
            r = reglage(R.ICONES.get(i["nature"], "network"), "%s · %s" % (R.NOMS.get(i["nature"], i["nature"]), i["dev"]), sous,
                        droite=self._etiquette_trafic(i["dev"]), clic=lambda dev=i["dev"]: (setattr(self, "iface_sel", dev), self.aller("iface")))
            c.append(r)
        GLib.timeout_add(1000, self._maj_trafic)
        c.append(groupe_titre("Sortie Internet"))
        choix = [("auto", "Automatique (NetworkManager choisit)")] + [(i["dev"], "%s · %s" % (R.NOMS.get(i["nature"]), i["dev"])) for i in L if i["etat"] == "connecté"]
        cur = sortie if any(k == sortie for k, _ in choix) else "auto"
        c.append(reglage("globe", "Interface utilisée pour Internet", "Les autres restent actives pour leur réseau local",
                         droite=deroulant(choix, cur, lambda k: S.en_fond(R.sortie_internet, lambda r: (self.toast("Sortie Internet réglée"), self.aller("interfaces", False)), None if k == "auto" else k), 300)))
        c.append(reglage("git-merge" if os.path.exists(theme.LUCIDE + "/git-merge.svg") else "network", "XIII Duo", "Plusieurs liens ensemble : secours automatique ou répartition", clic=lambda: self.aller("duo")))
        c.append(reglage("bookmark", "Profils réseau", "Réglages enregistrés par lieu, appliqués en un clic", clic=lambda: self.aller("profilsreseau")))
        # test de la régie
        c.append(groupe_titre("Tester un appareil"))
        r = boite(False, 8, "reglage")
        e = Gtk.Entry(placeholder_text="Adresse de la régie (ex. 192.168.10.240)", hexpand=True, text=getattr(self, "_ping_ip", ""))
        devs = [("", "Toutes interfaces")] + [(i["dev"], i["dev"]) for i in L if i["etat"] == "connecté"]
        sel = {"dev": ""}
        r.append(e); r.append(deroulant(devs, "", lambda k: sel.update(dev=k), 180))
        res = label("", "attenue")
        def tester():
            self._ping_ip = e.get_text().strip()
            if not self._ping_ip: return
            res.set_text("Test en cours…")
            S.en_fond(lambda: R.ping(self._ping_ip, sel["dev"] or None) if not S.DEMO else (True, "0.4 ms", 0),
                      lambda x: res.set_text(("✓ Répond — %s de latence%s" % (x[1], "" if not x[2] else ", %d %% de pertes" % x[2])) if x[0] else "✗ Ne répond pas (câble, adresse ou masque ?)"))
        e.connect("activate", lambda *_: tester()); r.append(bouton("Tester", None, "pilule", rappel=tester)); c.append(r); c.append(res)
        r2 = boite(False, 8, "reglage"); r2.append(label("Trouver les appareils du réseau local", "reglage-titre", hexpand=True))
        dd = {"dev": next((i["dev"] for i in L if i["etat"] == "connecté" and not i["internet"]), next((i["dev"] for i in L if i["etat"] == "connecté"), ""))}
        r2.append(deroulant([(i["dev"], i["dev"]) for i in L if i["etat"] == "connecté"] or [("", "—")], dd["dev"], lambda k: dd.update(dev=k), 180))
        zone = boite(True, 4)
        def chercher():
            vider(zone); zone.append(label("Recherche sur %s…" % dd["dev"], "attenue"))
            def fini(L2):
                vider(zone)
                if isinstance(L2, Exception) or not L2: zone.append(label("Aucun appareil trouvé.", "attenue")); return
                for ip, mac, nom in L2:
                    zone.append(reglage(None, ip + ("  ·  " + nom if nom else ""), mac, droite=bouton("Copier", "copy", "plat", taille=14, rappel=lambda ip=ip: (Gdk.Display.get_default().get_clipboard().set_text(ip), self.toast("Copié")))))
            S.en_fond(lambda: R.appareils(dd["dev"]) if not S.DEMO else [("192.168.10.240", "7c:2e:0d:11:22:33", "ATEM Mini Pro"), ("192.168.10.60", "00:1b:21:aa:bb:cc", "")], fini)
        r2.append(bouton("Chercher", None, "fantome", rappel=chercher)); c.append(r2); c.append(zone)

    def _etiquette_trafic(self, dev):
        l = label("", "petit", "attenue"); self._lab_trafic[dev] = l; return l

    def _maj_trafic(self):
        from . import reseau as R
        if self.page != "interfaces" or not self.win: return False
        t = R.trafic(); now = time.time()
        for dev, l in self._lab_trafic.items():
            if dev in t and dev in self._trafic:
                (r0, s0), t0 = self._trafic[dev]; dt = max(.1, now - t0)
                l.set_text("↓ %s/s  ↑ %s/s" % (S.humain((t[dev][0] - r0) / dt), S.humain((t[dev][1] - s0) / dt)))
            if dev in t: self._trafic[dev] = (t[dev], now)
        return True

    def p_iface(self, c, cle):
        from . import reseau as R
        dev = getattr(self, "iface_sel", None) or ("enp3s0" if S.DEMO else None)
        i = next((x for x in R.interfaces() if x["dev"] == dev), None)
        if not i: c.append(info("Interface introuvable.")); return
        h = boite(False, 16, "hero"); h.append(ico(R.ICONES.get(i["nature"], "network"), 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label("%s · %s" % (R.NOMS.get(i["nature"]), dev), "hero-grand"))
        v.append(label(" · ".join(x for x in (i["etat"], i["connexion"], i["ip"], i["debit"]) if x), "attenue")); h.append(v); c.append(h)
        conf = R.connexion(i["uuid"]) if i["uuid"] and not S.DEMO else {}
        adr0 = (conf.get("ipv4.addresses", "") or (i["ip"] if i["mode"] == "manual" else "")).split(",")[0].strip()
        etat = {"mode": i["mode"] if i["mode"] in ("auto", "manual") else "auto", "internet": not i["jamais_defaut"]}
        c.append(groupe_titre("Adresse IP"))
        rb = boite(False, 8, "reglage")
        b_auto = Gtk.ToggleButton(label="Automatique (DHCP)"); b_fixe = Gtk.ToggleButton(label="Adresse IP fixe", group=b_auto)
        for b_ in (b_auto, b_fixe): b_.add_css_class("bascule-mode")
        (b_fixe if etat["mode"] == "manual" else b_auto).set_active(True)
        rb.append(b_auto); rb.append(b_fixe); c.append(rb)
        fixe = boite(True, 4); c.append(fixe)
        e_adr = Gtk.Entry(text=adr0.split("/")[0], placeholder_text="ex. 192.168.10.50", hexpand=True)
        e_masque = Gtk.Entry(text=str(ipaddress_masque(adr0)), placeholder_text="255.255.255.0", hexpand=True)
        e_gw = Gtk.Entry(text=(conf.get("ipv4.gateway", "") if conf.get("ipv4.gateway", "") not in ("--",) else "") or ("" if i["jamais_defaut"] else i["passerelle"]), placeholder_text="vide pour un réseau régie", hexpand=True)
        e_dns = Gtk.Entry(text=conf.get("ipv4.dns", "") or "", placeholder_text="ex. 1.1.1.1, 9.9.9.9", hexpand=True)
        for t_, e in (("Adresse", e_adr), ("Masque", e_masque), ("Passerelle", e_gw), ("DNS", e_dns)):
            r = boite(False, 10, "reglage"); r.append(dim(label(t_, "reglage-titre"), 120)); r.append(e); fixe.append(r)
        fixe.set_visible(etat["mode"] == "manual")
        b_fixe.connect("toggled", lambda b: (etat.update(mode="manual" if b.get_active() else "auto"), fixe.set_visible(b.get_active())))
        c.append(groupe_titre("Rôle"))
        sw = interrupteur(etat["internet"], lambda on: etat.update(internet=on))
        c.append(reglage("globe", "Utiliser cette connexion pour Internet", "Désactivé : réseau local seulement (régie, caméras, NDI) — Internet continue de passer par les autres connexions", droite=sw))
        c.append(groupe_titre("Préréglages"))
        pr = boite(False, 8, "reglage")
        def preset(adr, gw, internet):
            b_fixe.set_active(True); e_adr.set_text(adr); e_masque.set_text("255.255.255.0"); e_gw.set_text(gw); sw.set_active(internet)
        pr.append(bouton("Régie Blackmagic (192.168.10.x)", None, "fantome", rappel=lambda: preset("192.168.10.50", "", False)))
        pr.append(bouton("Régie 192.168.0.x", None, "fantome", rappel=lambda: preset("192.168.0.50", "", False)))
        pr.append(bouton("Liaison directe PC ↔ PC", None, "fantome", rappel=lambda: preset("10.13.13.1", "", False)))
        pr.append(bouton("Box / routeur (DHCP)", None, "fantome", rappel=lambda: (b_auto.set_active(True), sw.set_active(True))))
        c.append(pr)
        def appliquer():
            try:
                adr = e_adr.get_text().strip()
                if etat["mode"] == "manual":
                    adr = "%s/%d" % (adr, prefixe(e_masque.get_text().strip() or "255.255.255.0"))
                args = (dev, i["nature"], etat["mode"], adr, e_gw.get_text(), e_dns.get_text(), etat["internet"])
            except Exception as e:
                self.toast("Adresse invalide : %s" % e); return
            self.toast("Application…")
            def fini(r):
                if isinstance(r, Exception): self.toast("Impossible : %s" % r)
                else: self.toast("Réglage appliqué" if r[0] else "Refusé : %s" % r[1][:120])
                self.aller("iface", False)
            S.en_fond(R.appliquer_ip, fini, *args)
        ap = bouton("Appliquer", None, "pilule", rappel=appliquer); ap.set_halign(Gtk.Align.END); c.append(ap)
        c.append(groupe_titre("Détails"))
        for k, n in (("mac", "Adresse physique (MAC)"), ("passerelle", "Passerelle actuelle"), ("dns", "DNS actuel")):
            c.append(reglage(None, n, None, droite=label(i[k] or "—", "mono", selectable=True)))
        c.append(reglage("settings-2", "Réglages avancés (802.1X, VLAN, IPv6…)", "", clic=lambda: S.detacher("nm-connection-editor")))

    def p_profilsreseau(self, c, cle):
        from . import reseau as R
        L = R.profils()
        if S.DEMO and not L:
            L = [{"nom": "Régie plateau A", "wifi": "Studio-XIII", "auto": True, "interfaces": [{"dev": "enp3s0", "mode": "manual", "adresse": "192.168.10.50/24", "internet": False}, {"dev": "wlan0", "mode": "auto", "internet": True}], "sortie": "wlan0"},
                 {"nom": "Bureau", "wifi": "Box-Maison", "auto": True, "interfaces": [{"dev": "enp3s0", "mode": "auto", "internet": True}], "sortie": None}]
        c.append(info("Un profil retient le réglage de chaque connexion (IP fixe ou automatique, rôle Internet) et la sortie Internet. "
                      "S'il est associé à un Wi-Fi, il s'applique tout seul quand vous rejoignez ce Wi-Fi."))
        if not L: c.append(label("Aucun profil enregistré.", "attenue"))
        for n, p in enumerate(L):
            resume = " · ".join("%s %s" % (x["dev"], "IP fixe " + x.get("adresse", "").split("/")[0] if x.get("mode") == "manual" else "auto") + ("" if x.get("internet", True) else " (local)") for x in p.get("interfaces", []))
            r = reglage("bookmark", p["nom"], (("Wi-Fi « %s » · " % p["wifi"]) if p.get("wifi") else "") + resume,
                        droite=bouton("Appliquer", None, "pilule", rappel=lambda p=p: S.en_fond(R.appliquer_profil, lambda r: self.toast(("Profil « %s » appliqué" % p["nom"]) if not isinstance(r, Exception) and r[0] else "Partiellement appliqué : %s" % (r[1] if not isinstance(r, Exception) else r)), p)))
            c.append(r)
            ar = boite(False, 8, halign=Gtk.Align.END)
            def basc(on, n=n):
                L2 = R.profils(); L2[n]["auto"] = on; R.sauver_profils(L2)
            ar.append(label("Automatique", "petit", "attenue")); ar.append(interrupteur(p.get("auto", True), basc))
            ar.append(bouton(None, "trash-2", "plat", tip="Supprimer", rappel=lambda n=n: (R.sauver_profils([x for k, x in enumerate(R.profils()) if k != n]), self.aller("profilsreseau", False))))
            c.append(ar)
        c.append(groupe_titre("Enregistrer la configuration actuelle"))
        e = Gtk.Entry(placeholder_text="Nom du lieu (ex. Régie plateau A)", hexpand=True)
        w = Gtk.Entry(placeholder_text="Wi-Fi associé (facultatif)", hexpand=True, text=R.wifi_actuel() if not S.DEMO else "Studio-XIII")
        r = boite(False, 8, "reglage"); r.append(e); r.append(w)
        def enregistrer():
            if not e.get_text().strip(): e.grab_focus(); return
            def fond():
                p = R.capturer(e.get_text().strip(), w.get_text().strip()); L2 = [x for x in R.profils() if x["nom"] != p["nom"]] + [p]; R.sauver_profils(L2)
            S.en_fond(fond, lambda _: (self.toast("Profil enregistré"), self.aller("profilsreseau", False)))
        r.append(bouton("Enregistrer", None, "pilule", rappel=enregistrer)); c.append(r)

    def p_duo(self, c, cle):
        from . import reseau as R
        conf = R.duo() if not S.DEMO else {"mode": "repartition", "prefere": "enp3s0", "poids": {}}
        et = R.duo_etat() if not S.DEMO else {"liens": [{"dev": "wlan0", "gw": "192.168.1.1", "ok": True, "latence": 14.2, "type": "wifi"}, {"dev": "usb0", "gw": "172.20.10.1", "ok": True, "latence": 38.5, "type": "ethernet"}], "actifs": ["wlan0", "usb0"]}
        h = boite(False, 16, "hero"); h.append(ico("git-merge" if os.path.exists(theme.LUCIDE + "/git-merge.svg") else "network", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label("XIII Duo", "hero-grand"))
        v.append(label({"arret": "Arrêté", "secours": "Secours automatique", "repartition": "Répartition"}[conf["mode"]] + (" · actif sur " + " + ".join(et.get("actifs", [])) if et.get("actifs") else ""), "attenue")); h.append(v); c.append(h)
        c.append(groupe_titre("Mode"))
        for k, t_, s in (("arret", "Arrêt", "Une seule connexion sert Internet, choisie par le système"),
                         ("secours", "Secours automatique", "Une connexion préférée ; si elle tombe, tout bascule sur l'autre en 3 secondes"),
                         ("repartition", "Répartition", "Les connexions sont utilisées ensemble : chaque nouvelle connexion part sur un lien, débits cumulés quand plusieurs transferts tournent")):
            c.append(reglage("circle-check" if conf["mode"] == k else "circle", t_, s, clic=lambda k=k: self._duo(dict(conf, mode=k))))
        liens = et.get("liens", [])
        if conf["mode"] == "secours":
            c.append(reglage("star", "Connexion préférée", "", droite=deroulant([("", "Câble d'abord")] + [(l["dev"], l["dev"]) for l in liens], conf.get("prefere", ""), lambda k: self._duo(dict(conf, prefere=k)), 200)))
        c.append(groupe_titre("Liens Internet"))
        if not liens: c.append(info("Un seul lien (ou aucun) avec Internet. Branchez un câble, un téléphone en partage USB ou une clé 4G en plus du Wi-Fi. Les connexions réglées « réseau local seulement » ne sont jamais utilisées."))
        for l in liens:
            r = reglage("wifi" if l.get("type") == "wifi" else "ethernet-port", l["dev"], "Passerelle %s · %s" % (l["gw"], ("%.0f ms" % l["latence"]) if l.get("ok") and l.get("latence") else "pas d'Internet"),
                        droite=label("● utilisé" if l["dev"] in et.get("actifs", []) else ("● prêt" if l.get("ok") else "● hors service"), "accent" if l.get("ok") else "attenue"))
            c.append(r)
            if conf["mode"] == "repartition":
                sp = Gtk.SpinButton.new_with_range(1, 10, 1); sp.set_value(int(conf.get("poids", {}).get(l["dev"], 1)))
                sp.connect("value-changed", lambda s, d=l["dev"]: self._duo(dict(conf, poids=dict(conf.get("poids", {}), **{d: int(s.get_value())})), recharger=False))
                c.append(reglage(None, "Part du trafic sur " + l["dev"], "Plus le chiffre est grand, plus ce lien reçoit de connexions", droite=sp))
        c.append(groupe_titre("Téléchargements accélérés"))
        plexo = shutil.which("plexo") or os.path.exists("/opt/plexo/Plexo.AppImage") or os.path.exists("/usr/share/applications/plexo.desktop")
        c.append(reglage("download", "Plexo", "Découpe chaque téléchargement en morceaux récupérés sur toutes les connexions à la fois (Wi-Fi + câble + téléphone) : un seul gros fichier va plus vite",
                         droite=bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("plexo")) if plexo else bouton("Site", None, "fantome", rappel=lambda: S.detacher(["xdg-open", "https://getplexo.app/"]))))
        c.append(info("La répartition cumule les débits quand plusieurs connexions tournent (plusieurs téléchargements, envois, flux). Un seul téléchargement reste sur un lien : utilisez Plexo pour le découper. "
                      "L'extension Firefox « Download with Plexo » est installée : les téléchargements du navigateur passent par Plexo."))

    def _duo(self, conf, recharger=True):
        from . import reseau as R
        S.en_fond(R.regler_duo, lambda ok: (self.toast("XIII Duo réglé" if ok else "Réglage annulé"), self.aller("duo", False) if recharger else None), conf)

    # ================================================================== PERSONNALISATION
    def p_perso(self, c, cle):
        h = boite(False, 18, "hero")
        pic = vignette(self.cfg["fond"], 320, 180)
        f = Gtk.Frame(); f.set_child(pic); h.append(f)
        v = boite(True, 6, valign=Gtk.Align.CENTER)
        v.append(label("Choisissez un thème", "gras"))
        r = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=3, column_spacing=6, row_spacing=6)
        for k, n, _ in theme.THEMES:
            b = bouton(n, None, "pilule" if self.cfg["theme"] == k else "fantome", rappel=lambda k=k: self.regler(theme=k)); r.append(b)
        v.append(r); h.append(v); c.append(h)
        self.p_categorie(c, "perso")

    def p_theme(self, c, cle):
        cfg = self.cfg; p = theme.palette(cfg)
        c.append(groupe_titre("Thème"))
        c.append(label("Les mêmes thèmes que la Suite XIII : un choix s'applique aux applications, aux fenêtres, au terminal, au fond d'écran et au verrouillage.", "attenue", wrap=True))
        g = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4, min_children_per_line=2, column_spacing=10, row_spacing=10, homogeneous=True)
        for k, n, d in theme.THEMES:
            b = Gtk.Button(); b.add_css_class("vignette"); b.set_tooltip_text(d)
            if cfg["theme"] == k: b.add_css_class("sel")
            v = boite(True, 4)
            v.append(apercu_theme(k, cfg["accent"], cfg))
            v.append(label(n, "gras", xalign=0.5))
            b.set_child(v); b.connect("clicked", lambda _b, k=k: self.regler(theme=k)); g.append(b)
        c.append(g)
        c.append(info(dict((k, d) for k, _, d in theme.THEMES).get(cfg["theme"], "") + ("" if not theme.SKINS.get(cfg["theme"], {}).get("acc") else " — ce thème impose sa couleur d'accent.")))
        # ---- thème perso
        c.append(groupe_titre("Thème perso"))
        tp = dict(cfg.get("theme_perso") or theme.DEPARTS[0])
        def maj(**kw):
            n = dict(tp); n.update(kw); self.regler(theme_perso=n, theme="perso")
        dep = boite(False, 6, "reglage"); dep.append(label("Départs", "reglage-titre", hexpand=True))
        for d_ in theme.DEPARTS:
            dep.append(bouton(d_["name"], None, "fantome", taille=12, rappel=lambda d_=d_: self.regler(theme_perso=dict(d_), theme="perso")))
        c.append(dep)
        def btn_couleur(cle_, titre, sous):
            dlg = Gtk.ColorDialog(with_alpha=False); cb = Gtk.ColorDialogButton(dialog=dlg)
            rg = Gdk.RGBA(); rg.parse(tp.get(cle_, "#888888")); cb.set_rgba(rg)
            def chg(btn, _p):
                x = btn.get_rgba(); hx = "#%02x%02x%02x" % (int(x.red * 255), int(x.green * 255), int(x.blue * 255))
                if hx != tp.get(cle_): maj(**{cle_: hx})
            cb.connect("notify::rgba", chg)
            c.append(reglage("palette", titre, sous, droite=cb))
        btn_couleur("bg", "Fond", "Fond des fenêtres et du bureau")
        btn_couleur("panel", "Panneaux", "Barres, menus, cartes (les teintes secondaires se déduisent)")
        btn_couleur("text", "Texte", "Le texte atténué et les bordures se déduisent")
        btn_couleur("accent", "Accent", "Actions principales, sélection, repères")
        c.append(reglage("square", "Arrondis", "", droite=deroulant([("s", "Petits"), ("m", "Moyens"), ("l", "Grands")], tp.get("radius", "m"), lambda v: maj(radius=v), 160)))
        c.append(reglage("layers", "Ombres", "", droite=deroulant([("s", "Discrètes"), ("m", "Normales"), ("l", "Profondes")], tp.get("shadow", "m"), lambda v: maj(shadow=v), 160)))
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 0.6, 0.02); sc.set_value(float(tp.get("glass", 0) or 0)); sc.set_size_request(220, -1)
        sc.connect("value-changed", lambda s: GLib.timeout_add(350, lambda v=s.get_value(): (maj(glass=round(v, 2)) if abs(v - sc.get_value()) < 1e-6 else None, False)[1]))
        c.append(reglage("droplet", "Transparence", "0 = opaque ; au-delà : verre (glassglow)", droite=sc))
        ie = boite(False, 8, "reglage"); ie.append(label("Fichier .xiii-theme.json (compatible avec la Suite XIII)", "reglage-titre", hexpand=True))
        ie.append(bouton("Importer…", None, "fantome", rappel=self.importer_theme)); ie.append(bouton("Exporter…", None, "fantome", rappel=lambda: self.exporter_theme(tp)))
        c.append(ie)
        # ---- accent
        c.append(groupe_titre("Couleur d'accent"))
        r = boite(False, 8, "reglage")
        fl = Gtk.FlowBox(max_children_per_line=14, selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6, hexpand=True)
        for n, hx in theme.ACCENTS:
            b = Gtk.Button(); b.add_css_class("pastille")
            if hx.lower() == cfg["accent"].lower(): b.add_css_class("sel")
            pr = Gtk.CssProvider(); pr.load_from_string("button { background: %s; }" % hx)
            b.get_style_context().add_provider(pr, 900); b.set_tooltip_text(n)
            b.connect("clicked", lambda _b, hx=hx: self.regler(accent=hx, accent_auto=False)); fl.append(b)
        r.append(fl); c.append(r)
        dlg = Gtk.ColorDialog(with_alpha=False); cb = Gtk.ColorDialogButton(dialog=dlg)
        rg = Gdk.RGBA(); rg.parse(cfg["accent"]); cb.set_rgba(rg)
        def couleur(btn, _p):
            x = btn.get_rgba(); hx = "#%02x%02x%02x" % (int(x.red * 255), int(x.green * 255), int(x.blue * 255))
            if hx != self.cfg["accent"]: self.regler(accent=hx, accent_auto=False)
        cb.connect("notify::rgba", couleur)
        c.append(reglage("palette", "Couleur personnalisée", "Choisissez n'importe quelle couleur", droite=cb))
        c.append(reglage("shapes", "Icônes XIII pour les logiciels tiers", "Firefox, VLC, OBS, Resolve, LibreOffice, Steam… dessinés au trait XIII (130 icônes). Désactivez pour garder leurs logos d'origine",
                         droite=interrupteur(cfg.get("icones_tierces", True), lambda on: self.regler(icones_tierces=on))))
        c.append(reglage("pipette", "Assortir l'accent au fond d'écran", "La couleur vive dominante de votre image devient l'accent, ajustée pour rester lisible ; elle suit chaque changement de fond",
                         droite=interrupteur(cfg.get("accent_auto", False), lambda on: self.regler(accent_auto=on))))
        # ---- effets, typographie
        c.append(groupe_titre("Effets et typographie"))
        c.append(reglage("sparkles", "Effets de transparence (glassglow)", "Verre teinté, lueur ambre, action principale en pilule lumineuse",
                         droite=interrupteur(cfg["transparence"], lambda on: self.regler(transparence=on))))
        c.append(reglage("wand-sparkles", "Animations", "Ouverture des menus et panneaux, indicateur glissant de la barre des tâches", droite=interrupteur(cfg["animations"], lambda on: self.regler(animations=on))))
        c.append(reglage("rows-3" if os.path.exists(theme.LUCIDE + "/rows-3.svg") else "list", "Densité", "Espacement des listes et réglages",
                         droite=deroulant([("compact", "Compacte"), ("normal", "Normale"), ("aere", "Aérée")], cfg.get("densite", "normal"), lambda v: self.regler(densite=v), 160)))
        c.append(reglage("type", "Taille et police du texte", "Astoria pour les titres, IBM Plex pour le texte", clic=lambda: self.aller("texte")))
        c.append(groupe_titre("Partout"))
        c.append(reglage("log-in", "Écran de connexion et démarrage", "Appliquer aussi ce thème à l'écran de connexion et à l'animation de démarrage (mot de passe administrateur)",
                         droite=bouton("Appliquer", None, "pilule", rappel=lambda: S.en_fond(theme.appliquer_connexion, lambda ok: self.toast("Écran de connexion et démarrage mis à jour" if ok is True else "Annulé"), dict(self.cfg)))))

    def importer_theme(self):
        d = Gtk.FileDialog(title="Importer un thème (.xiii-theme.json)")
        def fini(dlg, res):
            try:
                o = json.load(open(dlg.open_finish(res).get_path(), encoding="utf-8"))
                th = o.get("theme") if isinstance(o, dict) and o.get("format") == "xiii-theme" else o
                if not all(k in th for k in ("bg", "panel", "text", "accent")): raise ValueError
                self.regler(theme_perso={k: th[k] for k in ("name", "bg", "panel", "text", "accent", "radius", "shadow", "glass") if k in th}, theme="perso")
                self.toast("Thème « %s » importé" % th.get("name", "perso"))
            except GLib.Error:
                pass
            except Exception:
                self.toast("Ce fichier n'est pas un thème XIII")
        d.open(self.win, None, fini)

    def exporter_theme(self, tp):
        nom = re.sub(r"[^\w\- ]+", "", tp.get("name") or "theme") or "theme"
        d = Gtk.FileDialog(title="Exporter le thème", initial_name=nom + ".xiii-theme.json")
        def fini(dlg, res):
            try: f = dlg.save_finish(res)
            except GLib.Error: return
            json.dump({"format": "xiii-theme", "version": 1, "theme": tp}, open(f.get_path(), "w"), ensure_ascii=False, indent=2)
            self.toast("Thème exporté — importable dans la Suite XIII (Réglages › Affichage › Thème perso)")
        d.save(self.win, None, fini)

    def p_fond(self, c, cle):
        cfg = self.cfg
        video = cfg["fond"].lower().endswith((".mp4", ".webm", ".mkv", ".mov", ".m4v"))
        if video:
            m = Gtk.MediaFile.new_for_filename(cfg["fond"]); m.set_loop(True); m.set_muted(True); m.play()
            pic = Gtk.Picture.new_for_paintable(m); pic.set_size_request(640, 260); pic.set_content_fit(Gtk.ContentFit.COVER)
        else:
            pic = vignette(cfg["fond"], 640, 260)
        f = Gtk.Frame(); f.set_child(pic); c.append(f)
        c.append(groupe_titre("Images récentes et fonds XIII"))
        fl = Gtk.FlowBox(max_children_per_line=5, min_children_per_line=3, selection_mode=Gtk.SelectionMode.NONE, column_spacing=8, row_spacing=8, homogeneous=True)
        for p in sorted(glob.glob(config.FONDS + "/*.png") + glob.glob(config.FONDS + "/*.jpg")) + sorted(glob.glob(FONDS_PERSO + "/*")):
            if "connexion" in p: continue
            b = Gtk.Button(); b.add_css_class("vignette")
            if p == cfg["fond"]: b.add_css_class("sel")
            im = vignette(p, 160, 90)
            b.set_child(im); b.set_tooltip_text(os.path.basename(p)); b.connect("clicked", lambda _b, p=p: self.regler(fond=p)); fl.append(b)
        c.append(fl)
        c.append(reglage("image", "Choisir une photo", "JPG, PNG, WebP…", droite=bouton("Parcourir les photos", None, "pilule", rappel=lambda: self.choisir_image("fond"))))
        c.append(groupe_titre("Animation"))
        leger = theme._leger()
        c.append(reglage("wind", "Fond animé", ("L'image dérive très lentement sous une lueur de l'accent. " +
                         ("Déconseillé sur ce PC (rendu sans carte 3D) : " if leger else "") + "En pause sur batterie et en mode Tournage."),
                         droite=interrupteur(cfg.get("fond_anime", False), lambda on: self.regler(fond_anime=on))))
        c.append(reglage("clapperboard", "Vidéo en fond d'écran", "Une boucle vidéo (MP4, WebM…) sans le son ; en pause sur batterie",
                         droite=bouton("Choisir une vidéo", None, "fantome", rappel=lambda: self.choisir_image("fond", video=True))))
        c.append(reglage("sparkles", "Fond assorti au thème", "Fond du thème « %s », lueur de l'accent, logo XIII en filigrane — suit les changements de thème" % theme.NOMS_THEMES.get(cfg["theme"], cfg["theme"]),
                         droite=bouton("Utiliser", None, "fantome", rappel=lambda: S.en_fond(theme.fond_theme, lambda f: self.regler(fond=f) if isinstance(f, str) else None, dict(self.cfg)))))
        if not video: c.append(reglage("move-horizontal", "Ajustement", "", droite=deroulant([("fill", "Remplir"), ("fit", "Ajuster"), ("stretch", "Étirer"), ("center", "Centrer"), ("tile", "Mosaïque")],
                                                                                cfg["fond_mode"], lambda v: self.regler(fond_mode=v))))

    def choisir_image(self, cle, video=False):
        d = Gtk.FileDialog(title="Choisir une vidéo" if video else "Choisir une image")
        ff = Gtk.FileFilter(); ff.set_name("Vidéos" if video else "Images"); ff.add_mime_type("video/*" if video else "image/*")
        st = Gio.ListStore.new(Gtk.FileFilter); st.append(ff); d.set_filters(st)
        def fini(dlg, res):
            try: f = dlg.open_finish(res)
            except Exception: return
            os.makedirs(FONDS_PERSO, exist_ok=True)
            dest = os.path.join(FONDS_PERSO, os.path.basename(f.get_path()))
            try: shutil.copy(f.get_path(), dest)
            except Exception: dest = f.get_path()
            self.regler(**{cle: dest})
        d.open(self.win, None, fini)

    def p_verrou(self, c, cle):
        cfg = self.cfg
        pic = vignette(cfg["verrou_fond"], 640, 220)
        f = Gtk.Frame(); f.set_child(pic); c.append(f)
        c.append(reglage("image", "Image de l'écran de verrouillage", "", droite=bouton("Parcourir", None, "pilule", rappel=lambda: self.choisir_image("verrou_fond"))))
        c.append(reglage("image", "Utiliser le fond d'écran actuel", "", droite=bouton("Utiliser", None, "fantome", rappel=lambda: self.regler(verrou_fond=cfg["fond"]))))
        c.append(reglage("timer", "Verrouillage automatique", "Délai et options", clic=lambda: self.aller("alimentation")))
        c.append(reglage("lock", "Verrouiller maintenant", "Super + L", droite=bouton("Verrouiller", None, "fantome", rappel=lambda: S.detacher("swaylock -f"))))
        # ---- écran de connexion (au démarrage, avant d'ouvrir la session)
        c.append(groupe_titre("Écran de connexion"))
        av = cfg.get("connexion_avatar")
        r = reglage("circle-user-round", "Photo de profil", "Affichée en rond au-dessus du mot de passe",
                    droite=bouton("Choisir…", None, "fantome", rappel=lambda: self.choisir_image("connexion_avatar")))
        if av and os.path.exists(av):
            im = vignette(av, 44, 44); im.add_css_class("avatar-rond"); im.set_overflow(Gtk.Overflow.HIDDEN); r.prepend(im)
        c.append(r)
        c.append(reglage("image", "Image de fond", os.path.basename(cfg.get("connexion_fond") or "") or "Fond d'écran du bureau (ou fond XIII du thème)",
                         droite=bouton("Choisir…", None, "fantome", rappel=lambda: self.choisir_image("connexion_fond"))))
        c.append(reglage("droplets", "Fond flouté", "Image adoucie pour mettre le formulaire en valeur",
                         droite=interrupteur(cfg.get("connexion_flou", False), lambda on: self.regler(connexion_flou=on))))
        c.append(reglage("align-horizontal-justify-center", "Position du formulaire", "",
                         droite=deroulant([("gauche", "À gauche"), ("centre", "Au centre"), ("droite", "À droite")], cfg.get("connexion_position", "centre"), lambda v: self.regler(connexion_position=v))))
        c.append(reglage("clock", "Horloge", "",
                         droite=deroulant([("%H:%M  ·  %a %d %b", "14:30 · dim. 22 nov."), ("%H:%M", "14:30"), ("%H:%M:%S", "14:30:05"), ("%A %d %B  ·  %H:%M", "dimanche 22 novembre · 14:30")],
                                          cfg.get("connexion_horloge", "%H:%M  ·  %a %d %b"), lambda v: self.regler(connexion_horloge=v), 260)))
        c.append(reglage("log-in", "Appliquer à l'écran de connexion", "Demande le mot de passe administrateur ; visible au prochain démarrage ou à la prochaine déconnexion",
                         droite=bouton("Appliquer", None, "pilule", rappel=lambda: S.en_fond(theme.appliquer_connexion, lambda ok: self.toast("Écran de connexion mis à jour" if ok is True else "Annulé"), dict(self.cfg)))))

    def p_barre(self, c, cle):
        cfg = self.cfg
        c.append(groupe_titre("Éléments de la barre des tâches"))
        c.append(reglage("search", "Recherche", "Bouton de recherche à côté de Démarrer", droite=interrupteur(cfg["barre_recherche"], lambda on: self.regler(barre_recherche=on))))
        c.append(reglage("cloud-sun", "Météo", "Température et ciel à gauche de la barre", droite=interrupteur(cfg["barre_meteo"], lambda on: self.regler(barre_meteo=on))))
        c.append(reglage("bell-dot", "Pastille de notifications", "", droite=interrupteur(cfg["barre_badge"], lambda on: self.regler(barre_badge=on))))
        c.append(reglage("app-window", "Aperçu des fenêtres au survol", "Liste des fenêtres d'une application en passant la souris", droite=interrupteur(cfg.get("apercu_survol", True), lambda on: self.regler(apercu_survol=on))))
        c.append(groupe_titre("Comportement"))
        c.append(reglage("panel-bottom", "Alignement", "Position du bouton Démarrer et des applications",
                         droite=deroulant([("centre", "Centré"), ("gauche", "À gauche")], cfg["barre_alignement"], lambda v: self.regler(barre_alignement=v))))
        c.append(reglage("app-window", "Style de la barre des tâches", "Icônes seules (Windows 11) ou onglets avec le titre de la fenêtre",
                         droite=deroulant([("icones", "Icônes"), ("onglets", "Onglets")], cfg.get("barre_style", "icones"), lambda v: self.regler(barre_style=v))))
        c.append(groupe_titre("Applications épinglées"))
        self.liste_epingles(c, "epingles")

    def liste_epingles(self, c, cle):
        L = list(self.cfg[cle])
        for i, idd in enumerate(L):
            a = apps.par_id(idd)
            if not a: continue
            dr = boite(False, 4)
            def bouger(i=i, d=0):
                L2 = list(self.cfg[cle]); j = i + d
                if 0 <= j < len(L2): L2[i], L2[j] = L2[j], L2[i]; self.regler(**{cle: L2}); self.aller(self.page, False)
            def retirer(idd=idd):
                L2 = [x for x in self.cfg[cle] if x != idd]; self.regler(**{cle: L2}); self.aller(self.page, False)
            dr.append(bouton(None, "chevron-up", "plat", taille=14, tip="Monter", rappel=lambda i=i: bouger(i, -1)))
            dr.append(bouton(None, "chevron-down", "plat", taille=14, tip="Descendre", rappel=lambda i=i: bouger(i, 1)))
            dr.append(bouton(None, "pin-off", "plat", taille=14, tip="Désépingler", rappel=retirer))
            c.append(reglage(None, a.get_display_name(), None, droite=dr, gicon=a.get_icon()))
        c.append(info("Pour épingler : clic droit sur une application dans le menu Démarrer."))

    def p_demarrer(self, c, cle):
        cfg = self.cfg
        c.append(reglage("history", "Afficher les fichiers récents (Recommandés)", "", droite=interrupteur(cfg["menu_recommandes"], lambda on: self.regler(menu_recommandes=on))))
        c.append(reglage("layout-grid", "Affichage de « Toutes les applications »", "",
                         droite=deroulant([("categories", "Par catégories"), ("az", "Liste A – Z")], cfg["menu_vue"], lambda v: self.regler(menu_vue=v))))
        c.append(groupe_titre("Épinglées dans le menu"))
        self.liste_epingles(c, "menu_epingles")

    def p_widgets(self, c, cle):
        from .widgets import WIDGETS
        actifs = list(self.cfg["widgets"]); noms = {w[0]: w for w in WIDGETS}
        c.append(info("Les widgets s'ouvrent d'un clic sur la météo, à gauche de la barre des tâches. Les widgets Suite XIII lisent les fichiers .xiii.json exportés depuis la suite (dossiers ~/XIII, Téléchargements, Documents)."))
        c.append(groupe_titre("Widgets affichés"))
        for i, k in enumerate(actifs):
            if k not in noms: continue
            _, nom, ic, desc = noms[k]
            dr = boite(False, 4)
            def bouger(i=i, d=0):
                L = list(self.cfg["widgets"]); j = i + d
                if 0 <= j < len(L): L[i], L[j] = L[j], L[i]; self.regler(widgets=L); self.aller("widgets", False)
            dr.append(bouton(None, "chevron-up", "plat", taille=14, tip="Monter", rappel=lambda i=i: bouger(i, -1)))
            dr.append(bouton(None, "chevron-down", "plat", taille=14, tip="Descendre", rappel=lambda i=i: bouger(i, 1)))
            dr.append(interrupteur(True, lambda on, k=k: (self.regler(widgets=[x for x in self.cfg["widgets"] if x != k]), self.aller("widgets", False))))
            c.append(reglage(ic, nom, desc, droite=dr))
        autres = [w for w in WIDGETS if w[0] not in actifs]
        if autres:
            c.append(groupe_titre("Autres widgets"))
            for k, nom, ic, desc in autres:
                c.append(reglage(ic, nom, desc, droite=interrupteur(False, lambda on, k=k: (self.regler(widgets=self.cfg["widgets"] + [k]), self.aller("widgets", False)))))
        c.append(reglage("cloud-sun", "Ville de la météo", self.cfg["meteo_ville"], clic=lambda: self.aller("meteo")))
        # ---- widgets posés sur le bureau
        c.append(groupe_titre("Sur le bureau"))
        c.append(info("Épinglez des widgets en colonne, en haut à droite du bureau : toujours visibles, sous les fenêtres."))
        sb = list(self.cfg.get("widgets_bureau", []))
        for k, nom, ic, desc in WIDGETS:
            c.append(reglage(ic, nom, None, droite=interrupteur(k in sb, lambda on, k=k: (self.regler(widgets_bureau=[x for x in self.cfg.get("widgets_bureau", []) if x != k] + ([k] if on else []))))))
        c.append(groupe_titre("Compte à rebours"))
        e_nom = Gtk.Entry(text=self.cfg.get("compte_nom") or "", placeholder_text="Nom (ex. Tournage Concert Dôme)", hexpand=True)
        e_date = Gtk.Entry(text=self.cfg.get("compte_date") or "", placeholder_text="AAAA-MM-JJ", width_chars=12)
        def ok(*_):
            d = e_date.get_text().strip()
            try:
                if d: datetime.date.fromisoformat(d)
            except ValueError:
                self.toast("Date à écrire sous la forme 2026-12-31"); return
            self.regler(compte_nom=e_nom.get_text().strip(), compte_date=d); self.toast("Compte à rebours enregistré")
        r = boite(False, 8, "reglage"); r.append(e_nom); r.append(e_date); r.append(bouton("Enregistrer", None, "pilule", rappel=ok)); c.append(r)
        c.append(info("Laissez la date vide pour compter jusqu'au premier jour du projet actif (fiche projet de la Suite XIII)."))

    def p_bureau(self, c, cle):
        from .vues import ACTIONS_COINS
        cfg = self.cfg
        c.append(groupe_titre("Bureau"))
        c.append(reglage("monitor", "Icônes sur le bureau", "Contenu du dossier Bureau, glisser-déposer, clic droit", droite=interrupteur(cfg.get("icones_bureau", True), lambda on: self.regler(icones_bureau=on))))
        c.append(groupe_titre("Coins actifs"))
        coins = dict(cfg.get("coins", {}))
        for k, n in (("hg", "Coin supérieur gauche"), ("hd", "Coin supérieur droit"), ("bg", "Coin inférieur gauche"), ("bd", "Coin inférieur droit")):
            c.append(reglage("mouse-pointer-click", n, None, droite=deroulant(ACTIONS_COINS, coins.get(k, "rien"),
                                                                                lambda v, k=k: self.regler(coins=dict(self.cfg.get("coins", {}), **{k: v})), 220)))
        c.append(groupe_titre("Écran de veille"))
        c.append(reglage("timer", "Écran de veille", "Affiché après inactivité, avant le verrouillage",
                         droite=deroulant([("aucun", "Aucun"), ("horloge", "Horloge plateau"), ("mire", "Mire de barres"), ("conducteur", "Conducteur CONDUCO")],
                                          cfg.get("veille_mode", "horloge"), lambda v: self.regler(veille_mode=v), 220)))
        c.append(reglage("timer", "Délai", None, droite=deroulant([(str(s), t) for s, t in ((60, "1 minute"), (180, "3 minutes"), (300, "5 minutes"), (600, "10 minutes"))],
                                                                  str(cfg.get("veille_delai", 300)), lambda v: self.regler(veille_delai=int(v)))))
        c.append(reglage("eye", "Aperçu", None, droite=bouton("Voir", None, "fantome", rappel=lambda: S.detacher(["xiii-veille", self.cfg.get("veille_mode", "horloge")]))))

    def p_jeux(self, c, cle):
        from . import jeux
        self.bloc_console(c)
        vp, ram, vk = jeux.vieux_pc()
        h = boite(False, 16, "hero"); h.append(ico("gamepad-2", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER)
        v.append(label("Steam + Proton", "hero-grand"))
        v.append(label(("Steam installé" + (" · Proton activé pour tous les jeux" if jeux.proton_actif() else " · Proton pas encore activé")) if jeux.steam_installe() else "Steam non installé", "attenue"))
        h.append(v)
        h.append(bouton("Lancer Steam", None, "pilule", rappel=lambda: S.detacher("steam"))); c.append(h)
        c.append(groupe_titre("Proton (jeux Windows)"))
        def proton():
            ok, m = jeux.activer_proton(); self.toast(m); self.aller("jeux", False)
        c.append(reglage("zap", "Proton pour tous les jeux Windows", "Proton Experimental par défaut (Steam doit être fermé ; à faire après la première connexion)",
                         droite=label("Activé ✓", "accent") if jeux.proton_actif() else bouton("Activer", None, "pilule", rappel=proton)))
        c.append(groupe_titre("Mode console"))
        c.append(reglage("monitor-play" if os.path.exists(theme.LUCIDE + "/monitor-play.svg") else "monitor", "Steam en plein écran (Big Picture)", "Pour jouer à la manette sur la télé",
                         droite=bouton("Lancer", None, "fantome", rappel=lambda: S.detacher(["steam", "-gamepadui"]))))
        c.append(reglage("gamepad-2", "Lancer le mode console avec le profil Jeu", "", droite=interrupteur(self.cfg.get("jeu_console", False), lambda on: self.regler(jeu_console=on))))
        c.append(reglage("clapperboard", "Profil Jeu", "Performances max, silence, pas de veille", clic=lambda: self.aller("profils")))
        c.append(groupe_titre("Performances"))
        c.append(reglage("gauge", "GameMode", "Optimise le processeur pendant le jeu (automatique avec Steam : gamemoderun %command%)",
                         droite=label("Installé ✓" if jeux.gamemode_ok() else "Absent", "accent" if jeux.gamemode_ok() else "attenue")))
        c.append(reglage("activity", "Compteur d'images (MangoHud)", "IPS, températures, mémoire — appliqué à la prochaine connexion",
                         droite=interrupteur(self.cfg.get("mangohud", False), lambda on: (self.regler(mangohud=on), jeux.mangohud(on, self.cfg.get("jeu_30ips"))))))
        c.append(reglage("timer", "Limiter à 30 images/s", "Plus stable et plus frais sur un vieux PC",
                         droite=interrupteur(self.cfg.get("jeu_30ips", False), lambda on: (self.regler(jeu_30ips=on, mangohud=True if on else self.cfg.get("mangohud")), jeux.mangohud(True if on else self.cfg.get("mangohud"), on)))))
        if vp:
            c.append(info("Profil vieux PC : %.1f Go de mémoire%s. Conseils : limiter à 30 i/s, jouer en 720p, préférer Proton 8 si un jeu plante au lancement (Propriétés du jeu › Compatibilité)."
                          % (ram, "" if vk else ", pas de Vulkan (jeux Windows en mode compatibilité, plus lent)")))
        c.append(info("Les jeux protégés par certains anti-triche (Valorant, Fortnite…) ne fonctionnent pas sous Linux. Vérifiez la compatibilité d'un jeu sur protondb.com."))

    def p_claude(self, c, cle):
        from . import claude as CL
        demo = S.DEMO
        vd = "5.11492.5" if demo else CL.version_paquet("claude-desktop")
        vc = "2.1.311" if demo else (CL.version_code() if CL.code_installe() else None)
        h = boite(False, 16, "hero"); h.append(gicon_image(Gio.ThemedIcon.new("claude-desktop"), 48) if (vd or demo) else ico("sparkles", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER)
        v.append(label("Claude", "hero-grand"))
        v.append(label(" · ".join(x for x in (("Claude Desktop " + vd) if vd else "Claude Desktop non installé", ("Claude Code " + vc) if vc else "Claude Code non installé") if x), "attenue"))
        h.append(v)
        if vd: h.append(bouton("Ouvrir Claude", None, "pilule", rappel=lambda: CL.ouvrir()))
        else:
            def installer():
                S.en_fond(lambda: subprocess.run(["pkexec", "sh", "-c", "apt-get update && apt-get install -y --no-install-recommends claude-desktop claude-code " + ("qemu-system-x86 ovmf virtiofsd" if os.uname().machine == "x86_64" else "")]).returncode,
                          lambda r: (self.toast("Claude installé" if r == 0 else "Installation impossible (connexion Internet ?)"), self.aller("claude", False)))
                self.toast("Installation de Claude…")
            h.append(bouton("Installer", None, "pilule", rappel=installer))
        c.append(h)

        c.append(groupe_titre("Claude Desktop"))
        c.append(reglage("message-square", "Nouvelle conversation", "Discuter, joindre des fichiers, créer des documents — raccourci Super+C",
                         clic=lambda: CL.ouvrir("claude://claude.ai/new?surface=chat&source=desktop_action")))
        c.append(reglage("code-xml", "Nouvelle session Claude Code dans l'app", "Sessions en parallèle, revue des modifications, terminal et aperçu intégrés",
                         clic=lambda: CL.ouvrir("claude://code/new?source=desktop_action")))
        c.append(reglage("bot", "Cowork", "Confiez une tâche longue : Claude travaille dans une machine virtuelle sécurisée", clic=lambda: CL.ouvrir()))

        c.append(groupe_titre("Claude Code"))
        pj = self.cfg.get("projet_actif")
        c.append(reglage("square-terminal", "Ouvrir Claude Code" + (" dans « %s »" % pj if pj else ""),
                         ("Dans le dossier du projet XIII actif" if pj else "Dans votre dossier personnel") + " — raccourci Super+Maj+C", clic=lambda: CL.code_dans()))
        def dossier():
            d = Gtk.FileDialog(title="Ouvrir Claude Code dans…")
            d.select_folder(self.win, None, lambda dlg, res: (lambda f: f and CL.code_dans(f.get_path()))(self._fichier_ou_rien(dlg.select_folder_finish, res)))
        c.append(reglage("folder-open", "Ouvrir Claude Code dans un dossier…", "Aussi en clic droit sur un dossier dans Fichiers", clic=dossier))
        c.append(reglage("user-round-key", "Compte", "Connecté" if (demo or CL.connecte_code()) else "La connexion est proposée au premier lancement (abonnement Pro ou Max, ou clé API)",
                         droite=label("✓", "accent") if (demo or CL.connecte_code()) else None))

        c.append(groupe_titre("Relier OS XIII à Claude"))
        c.append(info("Claude peut alors voir l'état de l'ordinateur et votre écran, lire le projet XIII actif et les fichiers de la Suite XIII (fiche projet, conducteur, plan de travail), "
                      "appliquer un profil de travail, changer le thème, ouvrir une application, un dossier ou une page des Paramètres, et vous envoyer une notification. "
                      "Claude demande votre accord avant chaque action."))
        c.append(reglage("plug-zap", "Dans Claude Desktop", "Pris en compte au prochain lancement de Claude",
                         droite=interrupteur(demo or CL.mcp_desktop(), lambda on: (CL.regler_mcp_desktop(on), self.toast("Relancez Claude pour appliquer")))))
        def code_mcp(on):
            S.en_fond(CL.regler_mcp_code, lambda ok: self.toast(("OS XIII relié à Claude Code" if on else "Lien retiré") if ok else "Claude Code est absent"), on)
        c.append(reglage("plug", "Dans Claude Code", "Outils « os-xiii » disponibles dans toutes vos sessions",
                         droite=interrupteur(demo or CL.mcp_code(), code_mcp)))

        c.append(groupe_titre("Cowork sur ce PC"))
        conds = [(t, True, a) for t, _, a in CL.cowork()] if demo else CL.cowork()
        for t, ok, conseil in conds:
            c.append(reglage("circle-check" if ok else "circle-x", t, None if ok else conseil, droite=label("OK" if ok else "À régler", "accent" if ok else "attenue")))
        if not all(ok for _, ok, _ in conds[2:]):
            c.append(reglage("wrench", "Réparer Cowork", "Charge les modules, donne l'accès à la virtualisation et installe QEMU (mot de passe administrateur)",
                             droite=bouton("Réparer", None, "pilule", rappel=lambda: S.en_fond(CL.reparer_cowork, lambda ok: (self.toast("Fermez puis rouvrez la session" if ok else "Réparation annulée"), self.aller("claude", False))))))

        c.append(groupe_titre("Mises à jour"))
        c.append(reglage("refresh-cw", "Claude se met à jour avec OS XIII", "Dépôts officiels d'Anthropic (canal stable), comme le reste du système", clic=lambda: self.aller("maj")))
        c.append(info("Pas encore dans la version Linux de Claude : le contrôle de l'écran (Computer Use) et la dictée vocale. "
                      "La capture d'écran d'OS XIII permet déjà à Claude de voir ce qui est affiché."))

    def _fichier_ou_rien(self, fin, res):
        try: return fin(res)
        except GLib.Error: return None

    def p_suite(self, c, cle):
        from . import suite as SU
        rac = SU.racine(); L = SU.outils()
        try: ver = open(os.path.join(rac, "version-os.txt")).read().strip()
        except OSError: ver = "—"
        maj = rac == SU.UTIL
        h = boite(False, 16, "hero"); h.append(gicon_image(Gio.ThemedIcon.new("xiii-suite"), 56))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label("Suite XIII", "hero-grand"))
        v.append(label("%d outils hors ligne · version %s%s" % (len(L), ver, " (mise à jour)" if maj else " (livrée avec OS XIII)"), "attenue")); h.append(v)
        h.append(bouton("Ouvrir la Suite", None, "pilule", rappel=lambda: S.detacher(["xiii-suite"]))); c.append(h)
        c.append(info("Chaque outil s'ouvre dans sa propre fenêtre, sans navigateur ni connexion. Les outils partagent leurs données entre eux (projets, annuaire, échanges) "
                      "mais pas avec le site en ligne : utilisez les fichiers .xiii.json pour passer de l'un à l'autre."))
        c.append(groupe_titre("Fichiers"))
        c.append(reglage("file-json" if os.path.exists(theme.LUCIDE + "/file-json.svg") else "file", "Double-clic sur un fichier .xiii.json", "Ouvre le bon outil et importe le fichier ; une fiche projet peut aussi devenir le projet XIII de l'ordinateur"))
        c.append(reglage("folder-kanban", "Exports rangés dans le projet actif", ("Projet « %s » : 03_Documents et 06_Exports" % self.cfg["projet_actif"]) if self.cfg.get("projet_actif") else "Sans projet actif : dossier Téléchargements", clic=lambda: self.aller("projet")))
        c.append(reglage("send", "Envoyer à DOSSIER XIII", "Clic droit sur un document dans Fichiers : il rejoint le dossier en cours"))
        c.append(reglage("refresh-cw", "Convertir avec ENCODO XIII", "Clic droit sur une vidéo, un son, une image ou un PDF"))
        c.append(groupe_titre("Mise à jour"))
        def mettre_a_jour():
            self.toast("Téléchargement de la Suite XIII…")
            def fond():
                from . import suite_prep
                try:
                    tmp = SU.UTIL + ".prep"
                    suite_prep.preparer(tmp, journal=lambda *_: None)
                    import shutil
                    if os.path.exists(SU.UTIL): shutil.rmtree(SU.UTIL)
                    os.rename(tmp, SU.UTIL); return True
                except Exception as e:
                    return str(e)
            S.en_fond(fond, lambda r: (self.toast("Suite XIII à jour — rouvrez les outils" if r is True else "Mise à jour impossible : %s" % r), self.aller("suite", False)))
        c.append(reglage("download", "Mettre à jour la Suite XIII", "Dernière version publiée sur suite-xiii.netlify.app (environ 30 Mo)", droite=bouton("Mettre à jour", None, "pilule", rappel=mettre_a_jour)))
        if maj:
            c.append(reglage("rotate-ccw", "Revenir à la version livrée avec OS XIII", "", droite=bouton("Revenir", None, "plat", rappel=lambda: (__import__("shutil").rmtree(SU.UTIL, ignore_errors=True), self.aller("suite", False)))))
        c.append(groupe_titre("Outils"))
        for o in L:
            c.append(reglage(None, o["nom"], o["role"], gicon=Gio.ThemedIcon.new("xiii-suite-" + o["id"]), clic=lambda o=o: S.detacher(["xiii-suite", o["id"]])))

    def p_ndi(self, c, cle):
        from . import ndi
        ok = ndi.disponible() or S.DEMO
        v_ndi = (ndi.version() if ndi.disponible() else ("NDI SDK 6.2 (démo)" if S.DEMO else None))
        h = boite(False, 16, "hero"); h.append(ico("radio-tower", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label("NDI", "hero-grand"))
        v.append(label(("Runtime installé · " + (v_ndi or "")) if ok else "Runtime NDI non installé", "attenue")); h.append(v); c.append(h)
        c.append(groupe_titre("Runtime NDI"))
        if not ok:
            c.append(info("Le runtime NDI est gratuit, mais sa licence ne permet pas de le livrer dans OS XIII. Il se télécharge depuis le site officiel de NDI, "
                          "puis s'installe après acceptation de son contrat de licence."))
            etat = {"dossier": None}
            zone = boite(True, 8); c.append(zone)
            def etape1():
                self.toast("Téléchargement du kit NDI…")
                S.en_fond(lambda: subprocess.run(["xiii-ndi-runtime", "telecharger"], capture_output=True, text=True),
                          lambda r: afficher_licence(r.stdout.strip()) if r.returncode == 0 else self.toast("Téléchargement impossible (connexion Internet ?)"))
            def afficher_licence(d):
                etat["dossier"] = d; vider(zone)
                txt = subprocess.run(["xiii-ndi-runtime", "licence"], capture_output=True, text=True).stdout.strip() or "Contrat de licence du NDI SDK : voir ndi.video."
                tv = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD, monospace=False); tv.get_buffer().set_text(txt)
                sc = Gtk.ScrolledWindow(min_content_height=260, max_content_height=360, propagate_natural_height=True); sc.set_child(tv); sc.add_css_class("reglage"); zone.append(sc)
                cb = Gtk.CheckButton(label="J'ai lu et j'accepte le contrat de licence NDI"); zone.append(cb)
                bi = bouton("Installer le runtime NDI", None, "pilule", rappel=lambda: installer() if cb.get_active() else self.toast("Acceptez d'abord la licence")); zone.append(bi)
            def installer():
                S.en_fond(lambda: subprocess.run(["pkexec", "xiii-ndi-runtime", "installer", etat["dossier"]], capture_output=True, text=True).returncode,
                          lambda r: (self.toast("Runtime NDI installé" if r == 0 else "Installation annulée ou impossible"), self.aller("ndi", False)))
            zone.append(reglage("download", "Installer le runtime NDI", "Téléchargement depuis downloads.ndi.tv, puis lecture du contrat de licence", droite=bouton("Commencer", None, "pilule", rappel=etape1)))
        else:
            c.append(reglage("check", "Runtime NDI", v_ndi or "", droite=label("Installé ✓", "accent")))
            c.append(reglage("trash-2", "Désinstaller le runtime NDI", "", droite=bouton("Désinstaller", None, "plat", "danger",
                             rappel=lambda: S.en_fond(lambda: subprocess.run(["pkexec", "xiii-ndi-runtime", "retirer"]).returncode, lambda r: self.aller("ndi", False)))))
        c.append(groupe_titre("Module NDI XIII"))
        mod = os.path.exists("/opt/ndi-xiii/node_modules/electron/dist/electron") or S.DEMO
        c.append(reglage("radio-tower", "NDI XIII", "Sorties GRAPHICO (avec transparence), programme MELANGO, entrées son, diffusion RTMP / SRT — trouvé automatiquement par les outils",
                         droite=bouton("Lancer", None, "pilule", rappel=lambda: S.detacher("xiii-ndi")) if mod else label("Absent", "attenue")))
        auto = os.path.join(GLib.get_user_config_dir(), "autostart", "xiii-ndi.desktop")
        def auto_ndi(on):
            os.makedirs(os.path.dirname(auto), exist_ok=True)
            if on: open(auto, "w").write("[Desktop Entry]\nType=Application\nName=NDI XIII\nExec=xiii-ndi\nIcon=xiii-ndi\n")
            elif os.path.exists(auto): os.unlink(auto)
        c.append(reglage("rocket", "Lancer NDI XIII à l'ouverture de session", "", droite=interrupteur(os.path.exists(auto), auto_ndi)))
        c.append(groupe_titre("Retour plateau"))
        c.append(reglage("monitor-play", "Retour plateau", "Une source NDI en plein écran : ce PC devient un écran de retour", droite=bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-retour"))))
        rr = os.path.join(GLib.get_user_config_dir(), "autostart", "xiii-retour.desktop")
        def auto_retour(on):
            os.makedirs(os.path.dirname(rr), exist_ok=True)
            if on: open(rr, "w").write("[Desktop Entry]\nType=Application\nName=Retour plateau\nExec=sh -c 'sleep 6; xiii-retour --dernier'\nIcon=xiii-retour\n")
            elif os.path.exists(rr): os.unlink(rr)
        c.append(reglage("tv", "Retour plateau au démarrage", "Dernière source en plein écran dès l'ouverture de session (PC dédié)", droite=interrupteur(os.path.exists(rr), auto_retour)))
        c.append(info("NDI passe par le réseau local : le PC et le mélangeur doivent être sur le même réseau (ou indiquez l'IP du mélangeur dans le retour plateau). "
                      "NDI® est une marque déposée de Vizrt NDI AB."))

    def p_sauvegarde(self, c, cle):
        c.append(info("Deux protections complémentaires : vos dossiers (photos, documents, projets) sur un disque externe ou en ligne, et des instantanés du système pour revenir en arrière après une mauvaise mise à jour."))
        c.append(reglage("archive", "Sauvegarde de mes dossiers", "Automatique, chiffrée, sur disque externe ou en ligne (Déjà Dup)", droite=bouton("Configurer", None, "pilule", rappel=lambda: S.detacher("deja-dup"))))
        c.append(reglage("rotate-ccw", "Restaurer un fichier", "Retrouver une version précédente d'un fichier ou d'un dossier", droite=bouton("Restaurer", None, "fantome", rappel=lambda: S.detacher(["deja-dup", "--restore"]))))
        c.append(groupe_titre("Instantanés du système"))
        etat = (S.out("/usr/local/sbin/xiii-instantanes etat 2>/dev/null") or "? 0").split()
        fs = etat[0] if etat else "?"
        if fs == "btrfs" and os.path.exists("/etc/snapper/configs/root"):
            c.append(info("Un instantané est pris avant chaque installation ou mise à jour, et chaque jour. Ils ne copient rien : ils ne prennent presque pas de place. "
                          "Si l'ordinateur ne démarre plus, choisissez « Revenir à un état précédent » dans le menu de démarrage ; après trois démarrages ratés, OS XIII revient tout seul en arrière. "
                          "Vos fichiers personnels ne sont jamais touchés."))
            c.append(reglage("camera", "Créer un point de retour maintenant", "Avant une manipulation risquée", droite=bouton("Créer", "plus", "pilule", rappel=lambda: demander(self.win, "Nouveau point de retour", "Description (facultative)", "",
                     lambda t: S.en_fond(lambda: subprocess.run(["pkexec", "/usr/local/sbin/xiii-instantanes", "creer", t or "Point de retour manuel"]).returncode,
                                         lambda r: (self.toast("Point de retour créé" if r == 0 else "Création annulée"), self.aller("sauvegarde", False)))))))
            L = [l.split("|", 3) for l in (S.out("/usr/local/sbin/xiii-instantanes liste 2>/dev/null") or "").splitlines() if l.count("|") >= 3]
            TY = {"pre": "Avant installation", "post": "Après installation", "single": "Point de retour"}
            for n, d, t, de in reversed(L[-15:]):
                try: dd = datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).astimezone().strftime("%d/%m/%Y à %H:%M")
                except ValueError: dd = d
                if "timeline" in de: de = "Instantané quotidien"
                c.append(reglage("history", dd, "%s — %s" % (TY.get(t, t), de), droite=bouton("Revenir", None, "fantome", rappel=lambda n=n, dd=dd: confirmer(self.win, "Revenir à l'état du %s ?" % dd,
                         "Le système (logiciels et réglages) redeviendra tel qu'il était. Vos fichiers personnels ne changent pas. Le système actuel est gardé 7 jours. L'ordinateur redémarrera.", "Revenir et redémarrer",
                         lambda _: S.en_fond(lambda: subprocess.run(["pkexec", "/usr/local/sbin/xiii-instantanes", "restaurer", n, "manuel"]).returncode,
                                             lambda r: S.detacher(["systemctl", "reboot"]) if r == 0 else self.toast("Retour annulé ou impossible"))))))
            if not L: c.append(info("Aucun instantané pour le moment : le premier sera créé au prochain démarrage."))
        elif fs == "btrfs":
            c.append(info("Les instantanés seront activés automatiquement une minute après le prochain démarrage."))
        else:
            if fs in ("overlay", "squashfs", "tmpfs"):
                c.append(info("Vous utilisez OS XIII depuis la clé : rien n'est modifié sur l'ordinateur. Les instantanés seront actifs une fois OS XIII installé (en Btrfs, le choix par défaut)."))
            else:
                c.append(info("Le disque système de cet ordinateur est formaté en %s. Les instantanés rapides demandent Btrfs, le choix par défaut des nouvelles installations d'OS XIII "
                              "(il faudrait réinstaller pour en profiter). En attendant, Timeshift peut faire des copies du système (plus lentes, elles prennent de la place) "
                              "et le menu de démarrage propose toujours un démarrage de secours." % fs))
            c.append(reglage("history", "Copies du système (Timeshift)", "Restaurer le système à une date précédente", droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher("pkexec timeshift-launcher"))))
        c.append(groupe_titre("Si l'ordinateur ne démarre plus"))
        c.append(info("Au démarrage, le menu OS XIII propose : démarrage de secours (dernier noyau qui a fonctionné), mode sans échec graphique, Réparer OS XIII (menu de réparation sans bureau) "
                      "et Revenir à un état précédent. Depuis la clé OS XIII, l'outil « Réparer OS XIII » refait aussi le démarrage."))

    def p_evenements(self, c, cle):
        from . import fiabilite as F
        c.append(info("Tout ce qui est arrivé au système ces 30 derniers jours, en clair."))
        haut = boite(False, 8)
        filtre = [None]; liste = boite(True, 0)
        TY = F.TYPES
        def remplir():
            vider(liste); n = 0
            for d, t, msg in EV:
                if filtre[0] and t != filtre[0]: continue
                ic, nom = TY.get(t, ("info", t))
                sous = d.strftime("%d/%m/%Y à %H:%M") + " · " + nom
                droite = None
                if t == "plantage":
                    f = os.path.join(os.path.expanduser("~/Rapports XIII"), msg.split("rapport : ")[-1])
                    droite = bouton("Voir", None, "fantome", rappel=lambda f=f: S.detacher(["xdg-open", f]))
                liste.append(reglage(ic, msg, sous, droite=droite)); n += 1
                if n >= 200: break
            if not n: liste.append(info("Rien à signaler."))
        EV = []
        types = [(None, "Tout"), ("echec", "Démarrages ratés"), ("arret", "Arrêts brutaux"), ("restauration", "Retours arrière"), ("plantage", "Plantages"),
                 ("logiciel", "Logiciels"), ("maj", "Mises à jour"), ("disque", "Disque"), ("demarrage", "Démarrages")]
        haut.append(dim(deroulant(types, None, lambda v: (filtre.__setitem__(0, v or None), remplir())), 220))
        haut.append(boite(False, 0, hexpand=True))
        haut.append(bouton("Dossier des rapports", "folder-open", "fantome", rappel=lambda: (os.makedirs(os.path.expanduser("~/Rapports XIII"), exist_ok=True), S.detacher(["xdg-open", os.path.expanduser("~/Rapports XIII")]))))
        c.append(haut)
        c.append(groupe_titre("Santé des disques"))
        sd = boite(True, 0); c.append(sd); sd.append(info("Vérification…"))
        def sante(L):
            vider(sd)
            if not L: sd.append(info("L'état de santé des disques n'est pas disponible sur cet ordinateur.")); return
            IC = {"bon": ("circle-check", "Bon état"), "attention": ("triangle-alert", "À surveiller"), "critique": ("octagon-alert", "En danger"), "inconnu": ("circle-help", "Inconnu")}
            for d in L:
                ic, et = IC.get(d["etat"], IC["inconnu"])
                plus = []
                if d.get("temperature"): plus.append("%d °C" % d["temperature"])
                if d.get("heures"): plus.append("%d h d'utilisation" % d["heures"])
                sd.append(reglage(ic, "%s (%s) — %s" % (d["nom"], d["taille"], et), d["detail"] + ((" · " + " · ".join(plus)) if plus else "")))
        S.en_fond(F.sante_disques, sante)
        c.append(groupe_titre("Événements"))
        c.append(liste); liste.append(info("Chargement…"))
        def charge(L): EV[:] = L; remplir()
        S.en_fond(F.evenements, charge)

    def p_projet(self, c, cle):
        base = os.path.expanduser("~/XIII"); cur = self.cfg.get("projet_actif", "")
        SOUS = ["01_Rushes", "02_Son", "03_Documents", "04_Graphismes", "05_Montage", "06_Exports", "07_Livraison"]
        def activer(nom):
            nom = re.sub(r'[\\/:*?"<>|]', "-", nom).strip()
            if not nom: return
            d = os.path.join(base, nom)
            for x in SOUS: os.makedirs(os.path.join(d, x), exist_ok=True)
            bm = os.path.join(GLib.get_user_config_dir(), "gtk-3.0", "bookmarks"); os.makedirs(os.path.dirname(bm), exist_ok=True)
            try: L = [l for l in open(bm).read().splitlines() if "/XIII/" not in l]
            except OSError: L = []
            L.insert(0, "file://%s Projet %s" % (GLib.uri_escape_string(d, "/", False), nom)); open(bm, "w").write("\n".join(L) + "\n")
            self.regler(projet_actif=nom); self.aller("projet", False)
        h = boite(False, 16, "hero"); h.append(ico("folder-kanban", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label(cur or "Aucun projet actif", "hero-grand"))
        v.append(label(os.path.join(base, cur).replace(os.path.expanduser("~"), "~") if cur else "Le projet actif s'affiche en haut de l'écran, avec ses dossiers prêts.", "attenue")); h.append(v)
        if cur:
            h.append(bouton("Ouvrir", "folder-open", "pilule", taille=14, rappel=lambda: S.detacher(["thunar", os.path.join(base, cur)])))
            h.append(bouton("Désactiver", None, "plat", rappel=lambda: (self.regler(projet_actif=""), self.aller("projet", False))))
        c.append(h)
        c.append(groupe_titre("Nouveau projet"))
        e = Gtk.Entry(placeholder_text="Nom du projet (ex. Concert Dôme de Paris)", hexpand=True)
        r = boite(False, 8, "reglage"); r.append(e); r.append(bouton("Créer et activer", None, "pilule", rappel=lambda: activer(e.get_text()))); c.append(r)
        e.connect("activate", lambda *_: activer(e.get_text()))
        c.append(label("Dossiers créés : " + ", ".join(SOUS), "attenue", "petit", wrap=True))
        try:
            from .widgets import dernier_lien
            o = dernier_lien("project")
            if o:
                n = (o.get("fiche") or {}).get("title") or (o.get("project") or {}).get("name")
                if n: c.append(reglage("download", "Depuis la Suite XIII : « %s »" % n, "Dernière fiche projet exportée (.xiii.json)", droite=bouton("Activer", None, "fantome", rappel=lambda n=n: activer(n))))
        except Exception:
            pass
        exist = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))) if os.path.isdir(base) else []
        if exist:
            c.append(groupe_titre("Projets existants"))
            for d in exist:
                c.append(reglage("folder", d, None, droite=bouton("Actif" if d == cur else "Activer", None, "pilule" if d == cur else "fantome", rappel=lambda d=d: activer(d))))

    def p_tailscale(self, c, cle):
        """Tailscale à la souris : connexion, appareils, sortie Internet."""
        if not shutil.which("tailscale"):
            c.append(info("Tailscale n'est pas installé.")); c.append(reglage("download", "Installer Tailscale", "Centre de logiciels XIII", droite=bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-logiciels")))); return
        try: st = json.loads(S.out(["tailscale", "status", "--json"], 6) or "{}")
        except Exception: st = {}
        etat = st.get("BackendState", "Stopped"); moi = st.get("Self") or {}
        h = boite(False, 16, "hero"); h.append(ico("shield", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label("Tailscale", "hero-grand"))
        v.append(label({"Running": "Connecté · " + ", ".join(moi.get("TailscaleIPs", [])[:1]), "NeedsLogin": "Connexion au compte nécessaire", "Stopped": "Arrêté"}.get(etat, etat), "attenue")); h.append(v); c.append(h)
        u = pwd.getpwuid(os.getuid()).pw_name
        def connecter():
            self.toast("Connexion à Tailscale…")
            def t():
                # le service ne tourne pas tant qu'on ne s'en sert pas (vieux PC) : il est allumé et gardé au démarrage ici
                S.admin(["sh", "-c", "systemctl enable --now tailscaled && sleep 2 && tailscale set --operator=" + shlex.quote(u)])
                p = subprocess.run(["tailscale", "up", "--timeout=8s"], capture_output=True, text=True, timeout=20)
                m = re.search(r"https://login\.tailscale\.com/\S+", p.stdout + p.stderr)
                return m.group(0) if m else None
            S.en_fond(t, lambda url: (S.detacher(["xdg-open", url]) if isinstance(url, str) else None, GLib.timeout_add_seconds(8, lambda: (self.aller("tailscale", False), False)[1])))
        if etat == "Running":
            c.append(reglage("power", "Tailscale actif", "Ce PC est joignable par vos autres appareils", droite=interrupteur(True, lambda on: S.en_fond(lambda: subprocess.run(["tailscale", "down"]), lambda r: self.aller("tailscale", False)) if not on else None)))
            pairs = list((st.get("Peer") or {}).values())
            c.append(groupe_titre("Vos appareils (%d)" % len(pairs)))
            for p_ in sorted(pairs, key=lambda x: not x.get("Online")):
                c.append(reglage("monitor" if p_.get("OS") in ("linux", "windows", "macOS") else "smartphone", p_.get("HostName", "?"),
                                 "%s · %s · %s" % (", ".join(p_.get("TailscaleIPs", [])[:1]), p_.get("OS", ""), "en ligne" if p_.get("Online") else "hors ligne"),
                                 droite=bouton("Copier l'IP", None, "fantome", rappel=lambda ip=(p_.get("TailscaleIPs") or [""])[0]: Gdk.Display.get_default().get_clipboard().set_text(ip))))
            sorties = [p_ for p_ in pairs if p_.get("ExitNodeOption")]
            if sorties:
                c.append(reglage("globe", "Sortie Internet par un autre appareil", "Comme un VPN : votre trafic passe par cet appareil",
                                 droite=deroulant([("", "Aucune")] + [((p_.get("TailscaleIPs") or [""])[0], p_.get("HostName")) for p_ in sorties], "",
                                                  lambda ip: S.en_fond(lambda: subprocess.run(["tailscale", "set", "--exit-node=" + ip]), lambda r: self.toast("Sortie Internet modifiée")))))
            c.append(reglage("share-2", "Proposer ce PC comme sortie Internet", "Vos appareils peuvent passer par la connexion de ce PC",
                             droite=interrupteur(False, lambda on: S.en_fond(lambda: subprocess.run(["tailscale", "set", "--advertise-exit-node=" + ("true" if on else "false")]), None))))
        else:
            c.append(reglage("log-in", "Se connecter à Tailscale", "Le navigateur s'ouvre pour vous connecter (Google, Microsoft, GitHub, Apple…)", droite=bouton("Connecter", None, "pilule", rappel=connecter)))
        c.append(reglage("external-link", "Console Tailscale", "Gérer les appareils et les accès", droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher(["xdg-open", "https://login.tailscale.com/admin/machines"]))))

    def p_acquisition(self, c, cle):
        from . import acquisition as A
        bm = A.cartes_blackmagic() if not S.DEMO else ["Blackmagic Design DeckLink Mini Recorder 4K"]
        pil = A.pilote_blackmagic() or S.DEMO
        h = boite(False, 16, "hero"); h.append(ico("video", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label("Cartes d'acquisition", "hero-grand"))
        v.append(label(" · ".join(bm) if bm else "Aucune carte Blackmagic détectée", "attenue", wrap=True)); h.append(v); c.append(h)
        c.append(groupe_titre("Entrées vidéo reconnues"))
        per = A.peripheriques_video() if not S.DEMO else [("/dev/video0", "USB Video: HDMI Capture"), ("/dev/video42", "Carte d acquisition (OS XIII)")]
        if not per: c.append(info("Aucune entrée vidéo. Les boîtiers HDMI → USB (UVC) et les webcams fonctionnent sans pilote : branchez-les, ils apparaissent ici."))
        for d, n in per:
            c.append(reglage("webcam" if d != A.VIRTUELLE else "cast", n, d + ("  · caméra virtuelle d'OS XIII" if d == A.VIRTUELLE else "  · prête à l'emploi"), droite=label("✓", "accent")))
        c.append(groupe_titre("Blackmagic DeckLink / UltraStudio / Intensity"))
        if not pil:
            c.append(info("Le pilote Blackmagic « Desktop Video » est gratuit mais ne peut pas être livré avec OS XIII. "
                          "1. Téléchargez « Desktop Video pour Linux » sur le site de Blackmagic Design (archive .tar). "
                          "2. Choisissez l'archive ci-dessous : OS XIII installe le pilote et ses dépendances, puis demande un redémarrage."))
            c.append(reglage("external-link", "Page de téléchargement Blackmagic", "blackmagicdesign.com › Support › Desktop Video",
                             droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher(["xdg-open", "https://www.blackmagicdesign.com/support/family/capture-and-playback"]))))
            def choisir():
                d = Gtk.FileDialog(title="Archive Desktop Video (Linux)")
                ff = Gtk.FileFilter(); ff.set_name("Archive Desktop Video"); [ff.add_pattern(p) for p in ("*.tar", "*.tar.gz", "*.tgz", "*.tar.xz")]
                st = Gio.ListStore.new(Gtk.FileFilter); st.append(ff); d.set_filters(st)
                def fini(dlg, res):
                    try: f = dlg.open_finish(res).get_path()
                    except Exception: return
                    self.toast("Installation du pilote Blackmagic… (quelques minutes)")
                    S.en_fond(lambda: subprocess.run(["pkexec", "xiii-acquisition", "desktop-video", f], capture_output=True, text=True),
                              lambda r: (self.toast("Pilote installé : redémarrez le PC" if r.returncode == 0 else (r.stdout.strip().splitlines() or ["Installation annulée ou impossible"])[-1]), self.aller("acquisition", False)))
                d.open(self.win, None, fini)
            c.append(reglage("download", "Installer le pilote Desktop Video", "Depuis l'archive téléchargée chez Blackmagic", droite=bouton("Choisir l'archive…", None, "pilule", rappel=choisir)))
        else:
            c.append(reglage("check", "Pilote Desktop Video", "Installé", droite=bouton("Désinstaller", None, "plat", "danger",
                             rappel=lambda: S.en_fond(lambda: subprocess.run(["pkexec", "xiii-acquisition", "retirer-desktop-video"]).returncode, lambda r: self.aller("acquisition", False)))))
            if os.path.exists("/usr/bin/BlackmagicDesktopVideoSetup"):
                c.append(reglage("settings", "Réglages Blackmagic", "Format vidéo, connecteur d'entrée, mise à jour du firmware", droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher("BlackmagicDesktopVideoSetup"))))
        c.append(groupe_titre("Pont vers la caméra virtuelle"))
        c.append(info("MELANGO XIII, OBS, les visioconférences et les navigateurs ne savent lire que des webcams. Le pont recopie l'entrée DeckLink "
                      "dans une caméra virtuelle « Carte d'acquisition (OS XIII) »."))
        if not A.camera_virtuelle() and not S.DEMO:
            c.append(reglage("cast", "Caméra virtuelle", "Module v4l2loopback (installé à la demande)",
                             droite=bouton("Installer", None, "pilule", rappel=lambda: (self.toast("Installation de la caméra virtuelle…"),
                                           S.en_fond(lambda: subprocess.run(["pkexec", "xiii-acquisition", "camera-virtuelle"], capture_output=True).returncode,
                                                     lambda r: (self.toast("Caméra virtuelle prête" if r == 0 else "Installation annulée ou impossible"), self.aller("acquisition", False)))))))
        elif not pil:
            c.append(info("Installez d'abord le pilote Desktop Video pour activer le pont."))
        else:
            n = max(1, A.nb_entrees_decklink()) if not S.DEMO else 2
            etat = {"entree": str(self.cfg.get("decklink_entree", 0)), "mode": self.cfg.get("decklink_mode", "auto")}
            c.append(reglage("plug", "Entrée de la carte", None, droite=deroulant([(str(i), "Entrée %d" % (i + 1)) for i in range(n)], etat["entree"],
                             lambda v: (etat.__setitem__("entree", v), self.regler(decklink_entree=int(v))))))
            c.append(reglage("film", "Format du signal", None, droite=deroulant(A.MODES, etat["mode"], lambda v: (etat.__setitem__("mode", v), self.regler(decklink_mode=v)))))
            actif = A.pont_actif() or (S.DEMO and False)
            def basculer(on):
                if on:
                    if not A.gst_decklink(): self.toast("Module GStreamer DeckLink absent"); return
                    A.pont_demarrer(int(etat["entree"]), etat["mode"]); self.toast("Pont actif : choisissez « Carte d'acquisition (OS XIII) » comme caméra")
                else:
                    A.pont_arreter()
                self.regler(decklink_pont=on)
            c.append(reglage("cast", "Envoyer la carte vers la caméra virtuelle", "Relancé automatiquement à l'ouverture de session",
                             droite=interrupteur(bool(actif), basculer)))

    def p_outilsprod(self, c, cle):
        cfg = self.cfg
        c.append(groupe_titre("Horloge timecode"))
        c.append(reglage("clock", "Afficher le timecode en haut de l'écran", "HH:MM:SS:II calé sur l'heure système (synchronisée par Internet)",
                         droite=interrupteur(cfg.get("timecode", False), lambda on: self.regler(timecode=on))))
        c.append(reglage("film", "Images par seconde", None, droite=deroulant([(str(f), "%s i/s" % f) for f in (24, 25, 30, 50, 60)], str(cfg.get("timecode_fps", 25)),
                                                                              lambda v: self.regler(timecode_fps=int(v)))))
        c.append(info("Pour caler plusieurs PC d'un plateau : activez « Régler l'heure automatiquement » (Heure et langue) sur chacun."))
        c.append(groupe_titre("Timecode LTC (entrée audio)"))
        c.append(reglage("audio-waveform", "Lire le timecode d'une entrée son", "SMPTE LTC venant d'une caméra, d'un enregistreur ou d'un générateur (Tentacle, Deity…) : grand affichage plateau et widget",
                         droite=bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-timecode"))))
        c.append(groupe_titre("Vérification d'offload"))
        c.append(reglage("hash", "Vérifier une copie de cartes", "xxHash64 / MD5 / SHA-256, rapport texte + MHL, comme BACKUPO XIII. Aussi au clic droit sur un dossier dans Fichiers.",
                         droite=bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-somme"))))
        c.append(groupe_titre("Santé du PC"))
        c.append(reglage("heart-pulse", "Note de forme et conseils", "Mémoire, disque, température, batterie…", droite=bouton("Voir", None, "fantome", rappel=lambda: S.detacher(["xiii-bilan", "--sante"]))))

    def p_haut(self, c, cle):
        cfg = self.cfg
        c.append(reglage("app-window", "Titre de la fenêtre active", "Affiché à gauche de la barre du haut", droite=interrupteur(cfg["haut_titre"], lambda on: self.regler(haut_titre=on))))
        c.append(reglage("clock", "Afficher les secondes", "", droite=interrupteur(cfg["haut_secondes"], lambda on: self.regler(haut_secondes=on))))
        c.append(reglage("clock", "Format 24 heures", "", droite=interrupteur(cfg["horloge_24h"], lambda on: self.regler(horloge_24h=on))))
        c.append(reglage("battery-full", "Pourcentage de batterie", "", droite=interrupteur(cfg["haut_pourcentage"], lambda on: self.regler(haut_pourcentage=on))))
        c.append(reglage("wifi", "Style des indicateurs", "Wi-Fi, son et batterie : icône, rond (jauge), barre, pourcentage ou minimal",
                         droite=deroulant([("icone", "Icône"), ("rond", "Rond"), ("barre", "Barre"), ("pourcentage", "Pourcentage"), ("minimal", "Minimal")],
                                          cfg.get("indic_style", "icone"), lambda v: self.regler(indic_style=v))))
        c.append(reglage("film", "Horloge timecode", "HH:MM:SS:II au centre de la barre", droite=interrupteur(cfg.get("timecode", False), lambda on: self.regler(timecode=on))))
        c.append(info("Clic gauche sur une icône de la barre du haut : réglage rapide. Clic droit : la page complète des paramètres."))

    def p_polices(self, c, cle):
        cfg = self.cfg
        fams = sorted({f.get_name() for f in Gtk.Label().get_pango_context().list_families()})
        choix = [f for f in ("IBM Plex Sans", "Noto Sans", "DejaVu Sans", "Cantarell", "Liberation Sans", "Ubuntu") if f in fams] or fams[:10]
        if cfg["police"] not in choix: choix.insert(0, cfg["police"])
        c.append(reglage("type", "Police de l'interface", "", droite=deroulant([(f, f) for f in choix], cfg["police"], lambda v: self.regler(police=v), 240)))
        self.p_texte(c, cle)

    def p_texte(self, c, cle):
        cfg = self.cfg
        ex = label("Aperçu : Portez ce vieux whisky au juge blond qui fume.", wrap=True); c.append(boite(False, 0, "reglage")); c.get_last_child().append(ex)
        c.append(reglage("type", "Taille du texte", "Agrandit le texte des applications", droite=dim(curseur(cfg["taille_texte"] * 100, lambda v: self.regler(taille_texte=round(v / 100, 2)), 80, 160, 5, 600), 280)))

    def p_curseur(self, c, cle):
        c.append(reglage("mouse-pointer-2", "Taille du pointeur", "Appliquée à la prochaine connexion pour toutes les applications",
                         droite=deroulant([(str(s), n) for s, n in ((24, "Normale"), (32, "Grande"), (48, "Très grande"), (64, "Énorme"))], str(self.cfg["curseur_taille"]),
                                          lambda v: self.regler(curseur_taille=int(v)))))

    def p_demarrage(self, c, cle):
        cur = S.out(["plymouth-set-default-theme"]) or "xiii"
        c.append(reglage("clapperboard", "Animation actuelle", cur, droite=bouton("Changer / importer", None, "pilule", rappel=lambda: S.detacher("xiii-demarrage"))))
        c.append(info("Importez une vidéo ou un GIF : il devient votre animation de démarrage."))
        from .ascii_boot import VARIANTES
        c.append(groupe_titre("Logo XIII en ASCII"))
        g = Gtk.FlowBox(max_children_per_line=3, min_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, homogeneous=True)
        for nom, titre, desc in VARIANTES:
            th = "xiii-ascii-" + nom; d = "/usr/share/plymouth/themes/" + th
            imgs = sorted(glob.glob(d + "/f-*.png"))
            carte = boite(True, 6, "carte")
            if imgs:
                pic = Gtk.Picture.new_for_filename(imgs[len(imgs) * 2 // 3]); pic.set_content_fit(Gtk.ContentFit.COVER); pic.set_size_request(220, 124); pic.add_css_class("miniature"); carte.append(pic)
            carte.append(label(titre + ("  ✓" if cur == th else ""), "gras")); carte.append(label(desc, "petit", "attenue", wrap=True))
            rb = boite(False, 6)
            rb.append(bouton("Aperçu", "play", "fantome", rappel=lambda th=th, t=titre: A.fenetre_apercu(self.win, t, theme=th)))
            rb.append(bouton("Actuelle" if cur == th else "Utiliser", None, "pilule" if cur == th else "fantome", rappel=lambda th=th: self.appliquer_animation(th)))
            carte.append(rb); g.append(carte)
        c.append(g)
        # ---- store d'animations (façon Bazzite)
        cat = A.catalogue()
        c.append(groupe_titre("Store d'animations (%d)" % len(cat)))
        if not cat:
            c.append(info("Le catalogue d'animations n'est pas disponible sur cette version : faites une mise à jour d'OS XIII."))
            return
        c.append(info("Animations libres de la collection adi1090x (licence GPL). Survolez une vignette pour la voir bouger, « Aperçu » pour la voir en grand."))
        g2 = Gtk.FlowBox(max_children_per_line=3, min_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, homogeneous=True)
        for t in cat:
            carte = boite(True, 6, "carte")
            lec = A.Lecteur(220, 124); lec.add_css_class("miniature"); carte.append(lec)
            def charger(lec=lec, url=t["apercu"]):
                S.en_fond(A.apercu_local, lambda f, lec=lec: lec.gif(f, jouer=False) if isinstance(f, str) else None, url)
            charger()
            mv = Gtk.EventControllerMotion()
            mv.connect("enter", lambda *_ , lec=lec, url=t["apercu"]: lec.gif(os.path.join(A.CACHE, os.path.basename(url))) if os.path.exists(os.path.join(A.CACHE, os.path.basename(url))) else None)
            mv.connect("leave", lambda *_ , lec=lec, url=t["apercu"]: (lec.stop(), lec.gif(os.path.join(A.CACHE, os.path.basename(url)), jouer=False)) if os.path.exists(os.path.join(A.CACHE, os.path.basename(url))) else None)
            lec.add_controller(mv)
            ok = A.installe(t["dossier"])
            carte.append(label(t["nom"] + ("  ✓" if cur == t["dossier"] else ""), "gras"))
            rb = boite(False, 6)
            rb.append(bouton("Aperçu", "play", "fantome", rappel=lambda t=t: S.en_fond(A.apercu_local, lambda f, t=t: A.fenetre_apercu(self.win, t["nom"], gif=f) if isinstance(f, str) else self.toast("Aperçu indisponible (connexion Internet ?)"), t["apercu"])))
            if ok: rb.append(bouton("Actuelle" if cur == t["dossier"] else "Utiliser", None, "pilule" if cur == t["dossier"] else "fantome", rappel=lambda d=t["dossier"]: self.appliquer_animation(d)))
            else: rb.append(bouton("Installer", "download", "pilule", rappel=lambda d=t["dossier"], n=t["nom"]: self.installer_animation(d, n)))
            carte.append(rb); g2.append(carte)
        c.append(g2)

    def appliquer_animation(self, th):
        self.toast("Application de l'animation… (une minute)")
        S.en_fond(S.admin, lambda r: (self.toast("Animation appliquée au prochain démarrage" if r[0] else "Annulé"), self.aller("demarrage", False)), ["xiii-demarrage-appliquer", th])

    def installer_animation(self, d, nom):
        self.toast("Téléchargement de « %s »… (mot de passe administrateur)" % nom)
        S.progres("xiii-parametres.desktop", 0.05)
        def t():
            p = subprocess.Popen(["pkexec", "/usr/local/sbin/xiii-animation-installer", d], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for l in p.stdout:
                m = re.match(r"PROGRES (\d+) (\d+)", l)
                if m: S.progres("xiii-parametres.desktop", int(m.group(1)) / int(m.group(2)))
            return p.wait()
        S.en_fond(t, lambda r: (S.progres("xiii-parametres.desktop", None), self.toast(("« %s » installée et appliquée" % nom) if r == 0 else "Installation annulée ou impossible"), self.aller("demarrage", False)))

    # ================================================================== APPLICATIONS
    def p_apps(self, c, cle):
        from .windows import applis_windows, desinstaller as des_win
        L = applis_windows()
        c.append(groupe_titre("Applications Windows"))
        c.append(reglage("app-window", "Installer un logiciel Windows", "Double-cliquez sur un .exe ou un .msi, ou choisissez-le ici", droite=bouton("Choisir…", None, "pilule", rappel=lambda: S.detacher("xiii-windows"))))
        for a in L:
            def suppr(a=a):
                confirmer(self.win, "Désinstaller « %s » ?" % a["nom"], "Le logiciel, ses réglages et ses fichiers dans son disque C: seront supprimés.", "Désinstaller",
                          lambda _: S.en_fond(des_win, lambda r: (self.toast("%s désinstallé" % a["nom"]), self.aller("apps", False)), a))
            dr = boite(False, 6)
            dr.append(bouton(None, "folder", "plat", taille=15, tip="Ouvrir son disque C:", rappel=lambda a=a: S.detacher(["xdg-open", os.path.join(a["prefixe"], "drive_c")])))
            dr.append(bouton("Désinstaller", None, "fantome", rappel=suppr))
            gi_ = Gio.FileIcon.new(Gio.File.new_for_path(a["icone"])) if a.get("icone") and os.path.exists(a["icone"]) else None
            c.append(reglage("app-window" if not gi_ else None, a["nom"], "Application Windows · " + ("installée" if a.get("type") == "installeur" else "portable"), droite=dr, gicon=gi_))
        c.append(groupe_titre("Applications Linux"))
        e = Gtk.SearchEntry(placeholder_text="Rechercher une application"); c.append(e)
        zone = boite(True, 3); c.append(zone)
        tous = apps.toutes()
        def rendu(*_):
            vider(zone); q = e.get_text().lower()
            for a in tous:
                if q and q not in a.get_display_name().lower(): continue
                dr = boite(False, 6)
                dr.append(bouton(None, "app-window", "plat", taille=15, tip="Ouvrir", rappel=lambda a=a: apps.lancer(a)))
                if not (a.get_id() or "").startswith("xiii-"):
                    dr.append(bouton("Désinstaller", None, "fantome", rappel=lambda a=a: self.desinstaller(a)))
                else:
                    dr.append(label("Intégrée à OS XIII", "attenue", "petit"))
                zone.append(reglage(None, a.get_display_name(), a.get_description() or a.get_id(), droite=dr, gicon=a.get_icon()))
        e.connect("search-changed", rendu); rendu()

    def desinstaller(self, a):
        f = a.get_filename() or ""
        pq = S.out(["dpkg", "-S", f]).split(":")[0] if f else ""
        if not pq:
            self.toast("Impossible de trouver le paquet de cette application"); return
        def ok(_):
            self.toast("Désinstallation de %s…" % a.get_display_name())
            S.en_fond(S.admin, lambda r: (self.toast("Désinstallée" if not isinstance(r, Exception) and r[0] else "Échec"), self.aller("apps", False)),
                      ["apt-get", "remove", "-y", pq])
        confirmer(self.win, "Désinstaller « %s » ?" % a.get_display_name(), "Le paquet %s sera supprimé." % pq, "Désinstaller", ok)

    def p_defaut(self, c, cle):
        for ic, nom, mime in (("globe", "Navigateur web", "x-scheme-handler/https"), ("folder", "Fichiers", "inode/directory"),
                              ("file-text", "Éditeur de texte", "text/plain"), ("image", "Visionneuse d'images", "image/png"),
                              ("film", "Lecteur vidéo", "video/mp4"), ("headphones", "Lecteur audio", "audio/mpeg"), ("file-text", "Lecteur PDF", "application/pdf")):
            L = Gio.AppInfo.get_all_for_type(mime); d = Gio.AppInfo.get_default_for_type(mime, False)
            if not L: continue
            def poser(v, mime=mime, L=L):
                for x in L:
                    if x.get_id() == v:
                        x.set_as_default_for_type(mime)
                        if mime.startswith("x-scheme-handler/https"): x.set_as_default_for_type("x-scheme-handler/http"); x.set_as_default_for_type("text/html")
                        if mime == "image/png":
                            for m in ("image/jpeg", "image/webp", "image/gif"): x.set_as_default_for_type(m)
                        if mime == "video/mp4":
                            for m in ("video/x-matroska", "video/quicktime", "video/webm"): x.set_as_default_for_type(m)
            c.append(reglage(ic, nom, mime, droite=deroulant([(x.get_id(), x.get_display_name()) for x in L], d.get_id() if d else L[0].get_id(), poser, 260)))

    def p_autostart(self, c, cle):
        perso = os.path.join(GLib.get_user_config_dir(), "autostart"); os.makedirs(perso, exist_ok=True)
        vus = {}
        for p in sorted(glob.glob("/etc/xdg/autostart/*.desktop")) + sorted(glob.glob(perso + "/*.desktop")):
            vus[os.path.basename(p)] = p
        if not vus: c.append(info("Aucune application au démarrage."))
        for b, p in sorted(vus.items()):
            try: a = Gio.DesktopAppInfo.new_from_filename(p)
            except Exception: a = None
            if not a: continue
            kf = GLib.KeyFile()
            try: kf.load_from_file(p, GLib.KeyFileFlags.NONE); cache = kf.get_boolean("Desktop Entry", "Hidden")
            except Exception: cache = False
            def bascule(on, b=b, p=p):
                dest = os.path.join(perso, b)
                txt = open(p).read()
                txt = re.sub(r"(?m)^Hidden=.*\n?", "", txt).rstrip("\n") + ("\n" if on else "\nHidden=true\n")
                open(dest, "w").write(txt)
            c.append(reglage(None, a.get_display_name(), a.get_description() or b, droite=interrupteur(not cache, bascule), gicon=a.get_icon()))

    # ================================================================== COMPTES
    def p_compte(self, c, cle):
        u = pwd.getpwuid(os.getuid()); nom = u.pw_gecos.split(",")[0] or u.pw_name
        h = boite(False, 20, "hero"); h.append(avatar(96, nom))
        v = boite(True, 4, valign=Gtk.Align.CENTER); v.append(label(nom, "hero-grand")); v.append(label("Compte local · administrateur", "attenue")); h.append(v); c.append(h)
        c.append(reglage("image", "Votre photo", "Utilisée dans le menu Démarrer et à la connexion",
                         droite=bouton("Choisir une photo", None, "pilule", rappel=self.photo)))
        c.append(reglage("user", "Nom affiché", nom, droite=bouton("Modifier", None, "fantome", rappel=lambda: demander(self.win, "Nom affiché", "Votre nom", nom,
                         lambda n: S.en_fond(S.admin, lambda r: (self.maj_compte(), self.aller("compte", False)), ["usermod", "-c", n, u.pw_name])))))
        c.append(reglage("lock", "Options de connexion", "Mot de passe, connexion automatique", clic=lambda: self.aller("connexion")))

    def photo(self):
        d = Gtk.FileDialog(title="Choisir une photo")
        ff = Gtk.FileFilter(); ff.set_name("Images"); ff.add_mime_type("image/*")
        st = Gio.ListStore.new(Gtk.FileFilter); st.append(ff); d.set_filters(st)
        def fini(dlg, res):
            try: f = dlg.open_finish(res)
            except Exception: return
            try:
                from gi.repository import GdkPixbuf
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(f.get_path(), 256, 256, True); pb.savev(os.path.expanduser("~/.face"), "png", [], [])
            except Exception:
                shutil.copy(f.get_path(), os.path.expanduser("~/.face"))
            self.maj_compte(); self.aller("compte", False); self.toast("Photo mise à jour")
        d.open(self.win, None, fini)

    def p_connexion(self, c, cle):
        u = pwd.getpwuid(os.getuid()).pw_name
        c.append(reglage("lock", "Mot de passe", "Changer le mot de passe de votre compte", droite=bouton("Modifier", None, "pilule", rappel=lambda: self.mdp(u))))
        auto = False
        for f in glob.glob("/etc/lightdm/lightdm.conf.d/*.conf"):
            try:
                if re.search(r"^autologin-user=%s" % u, open(f).read(), re.M): auto = True
            except OSError: pass
        c.append(reglage("log-out", "Connexion automatique", "Ouvrir la session sans mot de passe au démarrage",
                         droite=interrupteur(auto, lambda on: S.en_fond(S.admin, lambda r: self.toast("Enregistré"),
                                                                       ("printf '[Seat:*]\\nautologin-user=%s\\nautologin-session=xiii\\n' > /etc/lightdm/lightdm.conf.d/60-autologin.conf" % u) if on
                                                                       else "rm -f /etc/lightdm/lightdm.conf.d/60-autologin.conf"))))
        sans = False
        try: sans = S.out(["passwd", "-S", u]).split()[1] == "NP"
        except Exception: pass
        c.append(reglage("lock-open", "Sans mot de passe", "Ouvrir la session et déverrouiller sans mot de passe (déconseillé sur un portable)",
                         droite=interrupteur(sans, lambda on: S.en_fond(S.admin, lambda r: self.toast("Compte sans mot de passe" if on else "Choisissez un mot de passe"),
                                                                      ["passwd", "-d", u]) if on else self.mdp(u))))
        c.append(reglage("timer", "Verrouillage automatique", "", clic=lambda: self.aller("alimentation")))
        # empreinte digitale
        c.append(groupe_titre("Empreinte digitale"))
        lecteur = S.DEMO or (shutil.which("fprintd-list") and "no devices" not in S.out(["fprintd-list", u], 4).lower() and S.out(["fprintd-list", u], 4).strip() != "")
        if not shutil.which("fprintd-enroll"):
            c.append(info("Le service d'empreinte (fprintd) n'est pas installé."))
        elif not lecteur:
            c.append(info("Aucun lecteur d'empreinte détecté sur ce PC."))
        else:
            doigts = [l.split("-", 1)[1].strip() if "-" in l else l.strip() for l in S.out(["fprintd-list", u], 4).splitlines() if l.strip().startswith("-")]
            c.append(reglage("fingerprint", "Empreintes enregistrées", ", ".join(NOMS_DOIGTS.get(d, d) for d in doigts) or "Aucune",
                             droite=bouton("Ajouter un doigt", None, "pilule", rappel=lambda: self.empreinte(u))))
            if doigts:
                c.append(reglage("trash-2", "Effacer mes empreintes", "", droite=bouton("Effacer", None, "plat", "danger",
                                 rappel=lambda: S.en_fond(lambda: S.sh(["fprintd-delete", u]), lambda r: self.aller("connexion", False)))))
            c.append(info("L'empreinte sert à la connexion, au déverrouillage et aux demandes administrateur."))
        # visage (webcam)
        c.append(groupe_titre("Reconnaissance du visage"))
        try:
            import importlib.util; cv = importlib.util.find_spec("cv2") is not None
        except Exception: cv = False
        modeles = all(os.path.exists("/usr/share/xiii/visage/" + m) for m in ("face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx"))
        cam = bool(glob.glob("/dev/video[0-9]*")) or S.DEMO
        if not (cv or S.DEMO):
            def inst():
                self.toast("Installation de la reconnaissance du visage…")
                S.en_fond(lambda: subprocess.run(["pkexec", "sh", "-c", "apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-opencv python3-numpy"]).returncode,
                          lambda r: (self.toast("Installé" if r == 0 else "Installation annulée ou impossible"), self.aller("connexion", False)))
            c.append(reglage("scan-face" if os.path.exists(theme.LUCIDE + "/scan-face.svg") else "user", "Installer la reconnaissance du visage", "OpenCV, environ 100 Mo",
                             droite=bouton("Installer", None, "pilule", rappel=inst)))
        elif not modeles and not S.DEMO:
            c.append(info("Les modèles de reconnaissance sont absents : relancez une mise à jour d'OS XIII (Paramètres › Mises à jour)."))
        elif not cam:
            c.append(info("Aucune webcam détectée sur ce PC."))
        else:
            fait = os.path.exists(os.path.expanduser("~/.local/share/xiii/visage.npy"))
            c.append(reglage("scan-face" if os.path.exists(theme.LUCIDE + "/scan-face.svg") else "user", "Mon visage", "Enregistré" if fait else "Pas encore enregistré",
                             droite=bouton("Recommencer" if fait else "Enregistrer mon visage", None, "pilule", rappel=self.visage)))
            if fait:
                c.append(reglage("trash-2", "Effacer mon visage", "", droite=bouton("Effacer", None, "plat", "danger",
                                 rappel=lambda: S.en_fond(lambda: S.sh(["xiii-visage", "effacer"]), lambda r: self.aller("connexion", False)))))
            c.append(info("Avec une webcam ordinaire, une photo de vous pourrait suffire à tromper la reconnaissance : gardez un mot de passe sur un PC qui sort du bureau."))
        c.append(groupe_titre("Au verrouillage"))
        c.append(info("Tapez votre mot de passe, ou appuyez simplement sur Entrée : OS XIII regarde alors la caméra (visage), puis attend votre doigt sur le lecteur (empreinte)."))
        c.append(reglage("shield-check", "Tester le déverrouillage", "Essai à blanc, exactement comme sur l'écran verrouillé : visage (6 s au plus), puis empreinte (10 s au plus)",
                         droite=bouton("Tester", None, "fantome", rappel=self.tester_verrou)))
        c.append(info("Quoi qu'il arrive, le mot de passe reste accepté immédiatement : la caméra ou le lecteur ne peuvent plus bloquer l'écran verrouillé."))

    def tester_verrou(self):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Test du déverrouillage", default_width=420); d.add_css_class("parametres")
        v = boite(True, 12, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label("Test du déverrouillage", "page-titre"))
        msg = label("Regardez la caméra, puis posez un doigt enregistré sur le lecteur si on vous le demande…", "attenue", wrap=True); v.append(msg)
        sp = Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER); sp.set_size_request(32, 32); v.append(sp)
        r = boite(False, 8, halign=Gtk.Align.END); r.append(bouton("Fermer", None, "fantome", rappel=d.close)); v.append(r)
        d.set_child(v); d.present()
        def essai():
            t = time.time()
            env = dict(os.environ, PAM_USER=pwd.getpwuid(os.getuid()).pw_name)
            try: rc = subprocess.run(["/usr/local/lib/xiii/verrou-biometrie"], env=env, timeout=25, capture_output=True).returncode
            except subprocess.TimeoutExpired: rc = 99
            return rc, time.time() - t
        def fin(res):
            sp.set_spinning(False); sp.set_visible(False)
            if isinstance(res, Exception): msg.set_text("Le test n'a pas pu se lancer : %s" % res); return
            rc, dt = res
            if rc == 0: msg.set_text("Reconnu en %.1f s : le déverrouillage par visage ou empreinte fonctionne." % dt)
            elif rc == 99: msg.set_text("Pas de réponse au bout de 25 s : la caméra ou le lecteur ne répond pas. Le mot de passe, lui, marche toujours.")
            else: msg.set_text("Non reconnu (%.1f s). Vérifiez l'éclairage ou réenregistrez votre visage / votre empreinte. Le mot de passe marche toujours." % dt)
        S.en_fond(essai, fin)

    def empreinte(self, u):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Empreinte digitale", default_width=420); d.add_css_class("parametres")
        v = boite(True, 12, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label("Ajouter une empreinte", "page-titre"))
        choix = list(NOMS_DOIGTS.items()); etat = {"doigt": "right-index-finger"}
        v.append(deroulant([(k, n) for k, n in choix], etat["doigt"], lambda x: etat.__setitem__("doigt", x)))
        im = ico("fingerprint", 72, "d"); v.append(im)
        msg = label("Choisissez le doigt, puis « Commencer ».", "attenue", wrap=True, xalign=0.5); v.append(msg)
        pb = Gtk.ProgressBar(); v.append(pb)
        r = boite(False, 8, halign=Gtk.Align.END)
        def lancer():
            import subprocess
            p = subprocess.Popen(["fprintd-enroll", "-f", etat["doigt"], u], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            n = [0]
            def lire(src, cond):
                l = p.stdout.readline()
                if not l: return False
                if "enroll-stage-passed" in l: n[0] += 1; pb.set_fraction(min(1, n[0] / 8)); msg.set_text("Encore… levez puis reposez le doigt.")
                elif "enroll-retry" in l or "enroll-swipe-too-short" in l or "finger-not-centered" in l: msg.set_text("Recommencez : doigt bien à plat, au centre.")
                elif "enroll-completed" in l: pb.set_fraction(1); msg.set_text("Empreinte enregistrée ✓"); GLib.timeout_add(1200, lambda: (d.close(), self.aller("connexion", False), False)[2])
                elif "enroll-failed" in l or "error" in l.lower(): msg.set_text("Échec de l'enregistrement. Réessayez.")
                return True
            GLib.io_add_watch(p.stdout, GLib.IO_IN | GLib.IO_HUP, lire)
            msg.set_text("Posez le doigt sur le lecteur.")
        r.append(bouton("Fermer", None, "fantome", rappel=d.close)); r.append(bouton("Commencer", None, "pilule", rappel=lancer)); v.append(r)
        d.set_child(v); d.present()

    def visage(self):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Reconnaissance du visage", default_width=420); d.add_css_class("parametres")
        v = boite(True, 12, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label("Enregistrer mon visage", "page-titre"))
        v.append(ico("scan-face" if os.path.exists(theme.LUCIDE + "/scan-face.svg") else "user", 72, "d"))
        msg = label("Placez-vous face à la caméra, bien éclairé, puis « Commencer ».", "attenue", wrap=True, xalign=0.5); v.append(msg)
        pb = Gtk.ProgressBar(); v.append(pb)
        r = boite(False, 8, halign=Gtk.Align.END)
        def lancer():
            p = subprocess.Popen(["xiii-visage", "enregistrer"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            def lire(src, cond):
                l = p.stdout.readline()
                if not l: return False
                if l.startswith("ETAPE "): msg.set_text(l[6:].strip())
                elif l.startswith("PROGRES "): a, b = l.split()[1:3]; pb.set_fraction(int(a) / int(b))
                elif l.startswith("ERREUR "): msg.set_text("Échec : " + l[7:].strip())
                elif l.startswith("FINI"): pb.set_fraction(1); msg.set_text("Visage enregistré"); GLib.timeout_add(1200, lambda: (d.close(), self.aller("connexion", False), False)[2])
                return True
            GLib.io_add_watch(p.stdout, GLib.IO_IN | GLib.IO_HUP, lire)
        r.append(bouton("Fermer", None, "fantome", rappel=d.close)); r.append(bouton("Commencer", None, "pilule", rappel=lancer)); v.append(r)
        d.set_child(v); d.present()

    def p_utilisateurs(self, c, cle):
        moi = pwd.getpwuid(os.getuid()).pw_name
        admins = set(grp.getgrnam("sudo").gr_mem) if "sudo" in [g.gr_name for g in grp.getgrall()] else set()
        L = [u for u in pwd.getpwall() if 1000 <= u.pw_uid < 60000 and u.pw_shell not in ("/usr/sbin/nologin", "/bin/false")] if not S.DEMO else []
        c.append(info("Chaque personne a son compte : ses fichiers, ses réglages, son thème, son mot de passe. Les comptes apparaissent sur l'écran de connexion."))
        for u in L:
            nom = u.pw_gecos.split(",")[0] or u.pw_name
            r = reglage("user", nom, "%s · %s" % (u.pw_name, "administrateur" if u.pw_name in admins else "standard") + (" · vous" if u.pw_name == moi else ""),
                        droite=None if u.pw_name == moi else bouton("Supprimer", None, "plat", "danger", rappel=lambda n=u.pw_name: self.supprimer_compte(n)))
            c.append(r)
        c.append(reglage("user-plus", "Ajouter un compte", "Pour un membre de la famille, de l'équipe, ou un compte invité", droite=bouton("Ajouter", None, "pilule", rappel=self.nouveau_compte)))

    def nouveau_compte(self):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Nouveau compte", default_width=440); d.add_css_class("parametres")
        v = boite(True, 10, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label("Nouveau compte", "page-titre"))
        nom = Gtk.Entry(placeholder_text="Nom complet"); ident = Gtk.Entry(placeholder_text="Identifiant (minuscules, sans espace)")
        a = Gtk.PasswordEntry(show_peek_icon=True, placeholder_text="Mot de passe (vide = sans mot de passe)")
        adm = Gtk.CheckButton(label="Administrateur (peut installer des logiciels et changer les réglages du système)")
        def auto(*_):
            if not ident.get_text() or getattr(ident, "_auto", False):
                ident.set_text(re.sub(r"[^a-z0-9]", "", sans_accents(nom.get_text().lower().split(" ")[0]))[:24]); ident._auto = True
        nom.connect("changed", auto)
        msg = label("", "attenue", "petit")
        for w in (nom, ident, a, adm, msg): v.append(w)
        def ok(*_):
            i = ident.get_text().strip()
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", i): msg.set_text("Identifiant invalide."); return
            cmd = "useradd -m -s /bin/bash -c %s -G audio,video,plugdev,netdev,bluetooth,kvm,dialout%s %s" % (shlex.quote(nom.get_text().strip() or i), ",sudo" if adm.get_active() else "", i)
            cmd += " && " + ("printf '%%s:%%s\\n' %s %s | chpasswd" % (i, shlex.quote(a.get_text())) if a.get_text() else "passwd -d " + i)
            S.en_fond(S.admin, lambda r: (d.close(), self.toast("Compte créé" if r[0] else "Échec : " + r[1][-80:]), self.aller("utilisateurs", False)), cmd)
        r = boite(False, 8, halign=Gtk.Align.END); r.append(bouton("Annuler", None, "fantome", rappel=d.close)); r.append(bouton("Créer", None, "pilule", rappel=ok)); v.append(r)
        d.set_child(v); d.present()

    def supprimer_compte(self, n):
        confirmer(self.win, "Supprimer le compte « %s » ?" % n, "Ses fichiers personnels seront supprimés. Cette action est définitive.", "Supprimer",
                  lambda: S.en_fond(S.admin, lambda r: (self.toast("Compte supprimé" if r[0] else "Échec"), self.aller("utilisateurs", False)), ["userdel", "-r", n]))

    def bloc_console(self, c):
        """Console XIII : ouverture, jaquettes ScreenScraper."""
        from . import scraper
        c.append(groupe_titre("Console XIII"))
        c.append(reglage("gamepad-2", "Console XIII", "Toutes vos consoles en plein écran, à la manette (mode Gaming)", droite=bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-console"))))
        c.append(reglage("folder", "Dossier des jeux", "~/Jeux — un sous-dossier par console, BIOS dans ~/Jeux/bios", droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher(["thunar", os.path.expanduser("~/Jeux")]))))
        cf = scraper.conf()
        c.append(groupe_titre("Jaquettes et fiches des jeux"))
        c.append(info("Sans compte : jaquettes et captures libres (libretro-thumbnails), pour les jeux dont le fichier porte son nom officiel. "
                      "Avec ScreenScraper : jaquettes, captures, année, genre, éditeur, joueurs et résumé en français, même pour les fichiers mal nommés. "
                      "ScreenScraper demande un compte gratuit (screenscraper.fr) et des identifiants développeur, à demander sur leur forum."))
        champs = {}
        for k, t, secret in (("ssid", "Identifiant ScreenScraper", False), ("sspassword", "Mot de passe ScreenScraper", True),
                             ("devid", "Identifiant développeur", False), ("devpassword", "Mot de passe développeur", True)):
            e = Gtk.PasswordEntry(show_peek_icon=True) if secret else Gtk.Entry()
            e.set_text(cf.get(k, "")); e.set_size_request(260, -1); champs[k] = e
            c.append(reglage("key-round" if secret else "user", t, None, droite=e))
        def sauver():
            scraper.enregistrer_conf({k: e.get_text().strip() for k, e in champs.items()}); self.toast("Identifiants ScreenScraper enregistrés")
        c.append(reglage("save", "Enregistrer", "Les jaquettes se récupèrent depuis le menu de la Console XIII", droite=bouton("Enregistrer", None, "pilule", rappel=sauver)))
        c.append(reglage("external-link", "Créer un compte ScreenScraper", "screenscraper.fr", droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher(["xdg-open", "https://www.screenscraper.fr/membreinscription.php"]))))
        c.append(groupe_titre("Steam"))

    def mdp(self, u):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Mot de passe", default_width=420); d.add_css_class("parametres")
        v = boite(True, 10, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
        v.append(label("Nouveau mot de passe", "page-titre"))
        a = Gtk.PasswordEntry(show_peek_icon=True, placeholder_text="Nouveau mot de passe"); b = Gtk.PasswordEntry(show_peek_icon=True, placeholder_text="Confirmer")
        msg = label("", "attenue", "petit"); v.append(a); v.append(b); v.append(msg)
        r = boite(False, 8, halign=Gtk.Align.END)
        def ok(*_):
            if len(a.get_text()) < 4: msg.set_text("4 caractères minimum."); return
            if a.get_text() != b.get_text(): msg.set_text("Les mots de passe ne correspondent pas."); return
            S.en_fond(lambda: S.admin(["chpasswd"], entree="%s:%s\n" % (u, a.get_text())), lambda r: (d.close(), self.toast("Mot de passe modifié" if not isinstance(r, Exception) and r[0] else "Échec")))
        r.append(bouton("Annuler", None, "fantome", rappel=d.close)); r.append(bouton("Enregistrer", None, "pilule", rappel=ok)); v.append(r)
        d.set_child(v); d.present()

    # ================================================================== HEURE ET LANGUE
    def p_heure(self, c, cle):
        n = label("", "hero-grand")
        h = boite(False, 16, "hero"); h.append(ico("clock", 40, "c")); h.append(n); c.append(h)
        def tic():
            if n.get_root() is None: return False
            d = datetime.datetime.now(); n.set_text(d.strftime("%H:%M:%S") + "  ·  " + d.strftime("%d/%m/%Y")); return True
        tic(); GLib.timeout_add_seconds(1, tic)
        c.append(reglage("refresh-cw", "Régler l'heure automatiquement", "Synchronisation par Internet (NTP)",
                         droite=interrupteur(S.ntp(), lambda on: S.en_fond(S.admin, None, ["timedatectl", "set-ntp", "true" if on else "false"]))))
        fz = S.fuseaux()
        dd = deroulant([(z, z.replace("_", " ")) for z in fz], S.fuseau(), lambda v: S.en_fond(S.admin, lambda r: self.toast("Fuseau horaire : " + v), ["timedatectl", "set-timezone", v]), 300, recherche=True)
        c.append(reglage("globe", "Fuseau horaire", "", droite=dd))
        c.append(reglage("clock", "Format 24 heures", "", droite=interrupteur(self.cfg["horloge_24h"], lambda on: self.regler(horloge_24h=on))))

    def p_langue(self, c, cle):
        cur = os.environ.get("LANG", "fr_FR.UTF-8")
        c.append(reglage("languages", "Langue d'affichage", "Appliquée à la prochaine connexion",
                         droite=deroulant([("fr_FR.UTF-8", "Français (France)"), ("fr_BE.UTF-8", "Français (Belgique)"), ("fr_CA.UTF-8", "Français (Canada)"),
                                           ("fr_CH.UTF-8", "Français (Suisse)"), ("en_US.UTF-8", "English (US)"), ("en_GB.UTF-8", "English (UK)"),
                                           ("es_ES.UTF-8", "Español"), ("de_DE.UTF-8", "Deutsch"), ("it_IT.UTF-8", "Italiano")], cur,
                                          lambda v: S.en_fond(S.admin, lambda r: self.toast("Langue enregistrée — reconnectez-vous"),
                                                              "sed -i 's/^# *%s/%s/' /etc/locale.gen && locale-gen && localectl set-locale LANG=%s" % (v.replace(".", "\\."), v.replace(".", "\\."), v)), 260)))
        c.append(reglage("keyboard", "Clavier", "Disposition et raccourcis", clic=lambda: self.aller("clavier")))

    # ================================================================== ACCESSIBILITÉ
    def p_effets(self, c, cle):
        cfg = self.cfg
        def leger(on):
            self.regler(vieux_pc=on, animations=not on, transparence=not on)
        c.append(reglage("feather" if os.path.exists(theme.LUCIDE + "/feather.svg") else "gauge", "Mode léger (vieux PC)",
                         "Sans transparence ni animation, état du réseau et de la batterie relu moins souvent. Activé tout seul sur les PC de 3 Go ou moins.",
                         droite=interrupteur(cfg.get("vieux_pc", False), leger)))
        c.append(reglage("sparkles", "Effets de transparence", "", droite=interrupteur(cfg["transparence"], lambda on: self.regler(transparence=on))))
        c.append(reglage("wand-sparkles", "Effets d'animation", "", droite=interrupteur(cfg["animations"], lambda on: self.regler(animations=on))))
        c.append(reglage("contrast", "Contraste renforcé", "Texte atténué et bordures plus marqués, texte en demi-gras — avec n'importe quel thème",
                         droite=interrupteur(cfg.get("contraste", False), lambda on: self.regler(contraste=on))))
        c.append(reglage("sun", "Thème Plein soleil", "Contraste maximal pour l'extérieur ou une vue fatiguée", clic=lambda: self.regler(theme="soleil")))
        c.append(reglage("rows-3" if os.path.exists(theme.LUCIDE + "/rows-3.svg") else "list", "Densité", "Aérée : cibles plus grandes, plus faciles à toucher",
                         droite=deroulant([("compact", "Compacte"), ("normal", "Normale"), ("aere", "Aérée")], cfg.get("densite", "normal"), lambda v: self.regler(densite=v), 160)))
        c.append(reglage("mouse-pointer-2", "Taille du pointeur", "", clic=lambda: self.aller("curseur")))

    # ================================================================== SÉCURITÉ
    def p_parefeu(self, c, cle):
        on = S.pare_feu()
        if on is None: c.append(info("Le pare-feu n'est pas installé.")); return
        c.append(reglage("flame", "Pare-feu", "Bloque les connexions entrantes non sollicitées (recommandé)",
                         droite=interrupteur(on, lambda v: S.en_fond(S.admin, lambda r: self.aller("parefeu", False), "ufw default deny incoming && ufw default allow outgoing && ufw --force enable" if v else "ufw disable"))))
        c.append(info("LocalSend, KDE Connect, NDI et Sunshine ajouteront leurs exceptions automatiquement lors de leur installation."))

    def p_confidentialite(self, c, cle):
        xbel = os.path.join(GLib.get_user_data_dir(), "recently-used.xbel")
        c.append(reglage("history", "Fichiers récents", "Affichés dans « Recommandés » du menu Démarrer", droite=interrupteur(self.cfg["menu_recommandes"], lambda on: self.regler(menu_recommandes=on))))
        c.append(reglage("trash-2", "Effacer l'historique des fichiers récents", "", droite=bouton("Effacer", None, "fantome", rappel=lambda: (os.path.exists(xbel) and os.remove(xbel), self.toast("Historique effacé")))))
        c.append(reglage("cloud-sun", "Localisation pour la météo", "Seule la ville choisie est utilisée — aucune géolocalisation", clic=lambda: self.aller("meteo")))

    # ================================================================== MISES À JOUR
    def p_maj(self, c, cle):
        i = S.infos_systeme()
        h = boite(False, 16, "hero"); h.append(ico("refresh-cw", 40, "c"))
        v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); self.maj_titre = label("Vérifiez les mises à jour", "hero-grand"); v.append(self.maj_titre)
        v.append(label(i["nom"] + " · " + i["base"], "attenue")); h.append(v)
        self.b_maj = bouton("Rechercher des mises à jour", None, "pilule", rappel=lambda: self.verifier_maj(zone)); h.append(self.b_maj); c.append(h)
        zone = boite(True, 3); c.append(zone)
        c.append(info("Paquets Debian (système, pilotes, applications). Un mot de passe administrateur est demandé."))
        self.bloc_maj_xiii(c)

    def bloc_maj_xiii(self, c):
        """Mise à jour d'OS XIII lui-même, depuis GitHub, sans perte de données."""
        from . import maj
        v = maj.version()
        c.append(groupe_titre("OS XIII"))
        c.append(reglage("tag", "Version installée", "%s · canal %s" % (v.get("version", "?"), "Stable" if v.get("branche") == "main" else "Beta")))
        canal = {"v": "stable" if v.get("branche") == "main" else "beta"}
        c.append(reglage("git-branch", "Canal de mise à jour", "Stable : versions publiées · Beta : nouveautés en avant-première",
                         droite=deroulant([("stable", "Stable"), ("beta", "Beta")], canal["v"], lambda x: canal.__setitem__("v", x))))
        c.append(reglage("bell", "Vérifier automatiquement", "Une fois par jour, notification quand une nouvelle version est disponible",
                         droite=interrupteur(self.cfg.get("maj_auto", True), lambda on: self.regler(maj_auto=on))))
        zone = boite(True, 6); c.append(zone)
        def verifier():
            vider(zone); zone.append(label("Recherche sur GitHub…", "attenue"))
            def fin(r):
                vider(zone)
                if isinstance(r, Exception): zone.append(label("Vérification impossible : %s" % r, "attenue", wrap=True)); return
                if not r["dispo"]: zone.append(reglage("check", "OS XIII est à jour", "Dernière version du canal : %s (%s)" % (r["distant"], r["date"]))); return
                zone.append(reglage("sparkles", "Nouvelle version disponible : %s" % r["distant"], "%d nouveauté(s) depuis votre version" % len(r["nouveautes"]),
                                    droite=bouton("Mettre à jour OS XIII", None, "pilule", rappel=lambda: appliquer(r))))
                for d, m in r["nouveautes"][:25]: zone.append(label("• %s — %s" % (d, m), "petit", wrap=True))
            S.en_fond(lambda: maj.verifier(canal["v"]), fin)
        def appliquer(r):
            vider(zone)
            zone.append(info("Un instantané du système est créé d'abord (Timeshift) : en cas de souci, revenez en arrière depuis Paramètres › Sauvegardes. "
                             "Vos fichiers, projets, jeux et réglages ne sont pas touchés."))
            pb = Gtk.ProgressBar(pulse_step=.04); zone.append(pb); journal = label("", "petit", "attenue", wrap=True); zone.append(journal)
            src = GLib.timeout_add(120, lambda: (pb.pulse(), True)[1])
            p_ = subprocess.Popen(["pkexec", "xiii-maj-systeme", "appliquer", r["canal"], r["distant"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def lire(src_, cond):
                l = p_.stdout.readline()
                if l: journal.set_text(l.strip()[20:] or l.strip()); return True
                GLib.source_remove(src); pb.set_fraction(1)
                ok = p_.wait() == 0
                journal.set_text("OS XIII est à jour ✓ — redémarrez la session pour tout profiter" if ok else "Mise à jour interrompue (voir /var/log/xiii-maj.log)")
                if ok: zone.append(bouton("Redémarrer la session", None, "pilule", rappel=lambda: S.detacher(["labwc", "--exit"])))
                return False
            GLib.io_add_watch(p_.stdout, GLib.IO_IN | GLib.IO_HUP, lire)
        c.append(bouton("Rechercher une nouvelle version d'OS XIII", "refresh-cw", "fantome", rappel=verifier))

    def verifier_maj(self, zone):
        self.b_maj.set_sensitive(False); self.b_maj.set_label("Recherche…"); vider(zone)
        def rendu(L):
            self.b_maj.set_sensitive(True)
            if isinstance(L, Exception): self.maj_titre.set_text("Échec de la vérification"); return
            if not L:
                self.maj_titre.set_text("Vous êtes à jour"); self.b_maj.set_label("Rechercher à nouveau"); return
            self.maj_titre.set_text("%d mise(s) à jour disponible(s)" % len(L)); self.b_maj.set_label("Tout installer")
            for p, ver in L: zone.append(reglage("package", p, ver))
            def installer(*_):
                self.b_maj.set_sensitive(False); self.b_maj.set_label("Installation…")
                pb = Gtk.ProgressBar(pulse_step=0.05); zone.prepend(pb)
                src = GLib.timeout_add(120, lambda: (pb.pulse(), True)[1])
                S.en_fond(S.admin, lambda r: (GLib.source_remove(src), pb.set_fraction(1), self.maj_titre.set_text("Mises à jour installées" if not isinstance(r, Exception) and r[0] else "Échec de l'installation"),
                                              self.b_maj.set_label("Terminé")), "DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade")
            nb = bouton("Tout installer", None, "pilule", rappel=installer); self.b_maj.get_parent().append(nb); self.b_maj.set_visible(False); self.b_maj = nb
        S.en_fond(S.maj_disponibles, rendu)

    # ================================================================== SUITE XIII
    def p_xiii(self, c, cle):
        cfg = self.cfg
        h = boite(False, 16, "hero")
        h.append(vignette("/usr/share/xiii/logos/suite-xiii-a.png", 150, 94, couvrir=False))
        v = boite(True, 4, valign=Gtk.Align.CENTER); v.append(label("OS XIII × Suite XIII", "hero-grand")); v.append(label("Outils de production audiovisuelle intégrés au système", "attenue")); h.append(v); c.append(h)
        c.append(groupe_titre("Suite XIII sur ce PC"))
        c.append(reglage("layout-grid", "Outils de la Suite XIII", "Hors ligne, chacun dans sa fenêtre — fichiers .xiii.json, envoi à DOSSIER, mises à jour", clic=lambda: self.aller("suite")))
        c.append(reglage("radio-tower", "NDI", "Runtime NDI, module NDI XIII, retour plateau", clic=lambda: self.aller("ndi")))
        c.append(reglage("siren", "Tally XIII", "Tally des mélangeurs ATEM, vMix, TriCaster sur les téléphones et boîtiers des cadreurs",
                         droite=bouton("Ouvrir", None, "pilule", rappel=lambda: S.detacher("xiii-tally"))))
        c.append(groupe_titre("Mode tournage"))
        c.append(reglage("clapperboard", "Mode tournage", "Performances maximales, notifications en silence, jamais de mise en veille — pour le plateau",
                         droite=interrupteur(cfg["mode_tournage"], lambda on: self.regler(mode_tournage=on))))
        c.append(reglage("cloud-sun", "Météo de la barre des tâches", cfg["meteo_ville"], clic=lambda: self.aller("meteo")))
        c.append(reglage("sparkles", "Revoir la visite guidée", "Le tour du bureau en une minute", droite=bouton("Lancer", None, "pilule",
                         rappel=lambda: S.detacher(["xiii-ctl", "visite"]))))
        c.append(groupe_titre("Réglages d'OS XIII"))
        c.append(reglage("download", "Exporter mes réglages", "Fichier .xiii.json réutilisable sur un autre PC", droite=bouton("Exporter", None, "fantome", rappel=self.exporter)))
        c.append(reglage("plus", "Importer des réglages", "", droite=bouton("Importer", None, "fantome", rappel=self.importer)))
        c.append(reglage("rotate-ccw", "Réinitialiser l'apparence", "Thème Sombre, accent cuivre, fond XIII",
                         droite=bouton("Réinitialiser", None, "plat", "danger", rappel=lambda: self.regler(theme="sombre", accent="#f0b378", fond=config.DEFAUTS["fond"], transparence=True, animations=True))))
        c.append(reglage("globe", "Suite XIII en ligne", "suite-xiii.netlify.app", clic=lambda: S.detacher(["xdg-open", "https://suite-xiii.netlify.app/"])))

    def exporter(self):
        d = Gtk.FileDialog(title="Exporter les réglages", initial_name="reglages-os-xiii.xiii.json")
        def fini(dlg, res):
            try: f = dlg.save_finish(res)
            except Exception: return
            json.dump({"format": "os-xiii-reglages", "version": 1, "reglages": self.cfg}, open(f.get_path(), "w"), ensure_ascii=False, indent=2)
            self.toast("Réglages exportés")
        d.save(self.win, None, fini)

    def importer(self):
        d = Gtk.FileDialog(title="Importer des réglages")
        def fini(dlg, res):
            try: f = dlg.open_finish(res); data = json.load(open(f.get_path()))
            except Exception: self.toast("Fichier illisible"); return
            r = data.get("reglages", data)
            self.regler(**{k: v for k, v in r.items() if k in config.DEFAUTS and k != "ecrans"}); self.toast("Réglages importés")
        d.open(self.win, None, fini)

    def p_meteo(self, c, cle):
        e = Gtk.Entry(text=self.cfg["meteo_ville"], placeholder_text="Ville")
        zone = boite(True, 3)
        def chercher(*_):
            vider(zone); zone.append(Gtk.Spinner(spinning=True, halign=Gtk.Align.START))
            S.en_fond(geocoder, rendu, e.get_text())
        def rendu(L):
            vider(zone)
            if isinstance(L, Exception) or not L: zone.append(info("Aucune ville trouvée (connexion Internet ?).")); return
            for v in L:
                zone.append(reglage("map-pin" if os.path.exists(theme.LUCIDE + "/map-pin.svg") else "globe", v["name"], ", ".join(x for x in (v.get("admin1"), v.get("country")) if x),
                                    droite=bouton("Choisir", None, "pilule", rappel=lambda v=v: (self.regler(meteo_ville=v["name"], meteo_lat=v["latitude"], meteo_lon=v["longitude"]), self.aller("meteo", False)))))
        e.connect("activate", chercher)
        c.append(reglage("cloud-sun", "Ville actuelle", "%s (%.2f, %.2f)" % (self.cfg["meteo_ville"], self.cfg["meteo_lat"], self.cfg["meteo_lon"])))
        r = boite(False, 8, "reglage"); e.set_hexpand(True); r.append(e); r.append(bouton("Rechercher", None, "pilule", rappel=chercher)); c.append(r)
        c.append(zone)
        c.append(reglage("cloud-sun", "Afficher la météo dans la barre des tâches", "", droite=interrupteur(self.cfg["barre_meteo"], lambda on: self.regler(barre_meteo=on))))
        c.append(info("Données Open-Meteo, sans compte ni clé. Seule la ville choisie est envoyée."))

    # ------------------------------------------------------------------ utilitaires
    def plus_tard(self, page):
        GLib.timeout_add(800, lambda: (self.aller(page, False), False)[1])

    def toast(self, msg):
        S.detacher(["notify-send", "-a", "Paramètres", "-i", "preferences-system", "-t", "3000", "Paramètres", msg])

def geocoder(ville):
    if S.DEMO: return [dict(name="Paris", admin1="Île-de-France", country="France", latitude=48.85, longitude=2.35)]
    q = urllib.parse.urlencode(dict(name=ville, count=6, language="fr", format="json"))
    return json.load(urllib.request.urlopen("https://geocoding-api.open-meteo.com/v1/search?" + q, timeout=10)).get("results", [])

# ================================================================================================ composants de page
def prefixe(masque):
    import ipaddress
    masque = masque.strip().lstrip("/")
    if masque.isdigit(): return int(masque)
    return ipaddress.ip_network("0.0.0.0/" + masque).prefixlen


def ipaddress_masque(adr):
    import ipaddress
    try: return ipaddress.ip_interface(adr if "/" in adr else adr + "/24").network.netmask if adr else "255.255.255.0"
    except ValueError: return "255.255.255.0"


def groupe_titre(t):
    return label(t, "groupe-titre")

def reglage(icone, titre, sous=None, droite=None, clic=None, gicon=None):
    bx = boite(False, 16)
    if gicon is not None: bx.append(gicon_image(gicon, 26))
    elif icone: bx.append(ico(icone, 20, "c"))
    v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER)
    v.append(label(titre, "reglage-titre", wrap=True))
    if sous: v.append(label(sous, "reglage-sous", wrap=True))
    bx.append(v)
    if droite is not None:
        droite.set_valign(Gtk.Align.CENTER); bx.append(droite)
    if clic:
        bx.append(ico("chevron-right", 16, "d"))
        b = Gtk.Button(); b.add_css_class("reglage"); b.set_child(bx); b.connect("clicked", lambda *_: clic()); return b
    bx.add_css_class("reglage")
    return bx

def info(t):
    b = boite(False, 10, "info-bulle", margin_top=6); b.append(ico("info", 16, "c")); b.append(label(t, wrap=True, hexpand=True)); return b

def dim(w, largeur):
    w.set_size_request(largeur, -1); return w

def deroulant(options, courant, rappel, largeur=200, recherche=False):
    sl = Gtk.StringList.new([o[1] for o in options])
    d = Gtk.DropDown(model=sl)
    if recherche:
        d.set_enable_search(True)
        d.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
    idx = next((i for i, o in enumerate(options) if str(o[0]) == str(courant)), 0)
    d.set_selected(idx); d.set_size_request(largeur, -1)
    dernier = [str(courant)]
    def chg(dd, _p):
        i = dd.get_selected()
        if 0 <= i < len(options) and str(options[i][0]) != dernier[0]:
            dernier[0] = str(options[i][0]); rappel(options[i][0])
    d.connect("notify::selected", chg)
    return d

def avatar(taille, nom):
    face = os.path.expanduser("~/.face")
    ov = Gtk.Overlay(); ov.add_css_class("avatar"); ov.set_size_request(taille, taille)
    if os.path.exists(face):
        p = vignette(face, taille, taille)
        fr = Gtk.Frame(); fr.set_child(p); fr.set_overflow(Gtk.Overflow.HIDDEN)
        pr = Gtk.CssProvider(); pr.load_from_string("frame { border-radius: 50%%; border: none; min-width: %dpx; min-height: %dpx; }" % (taille, taille))
        fr.get_style_context().add_provider(pr, 900); ov.set_child(fr)
    else:
        l = label(nom[:1].upper(), xalign=0.5)
        pr = Gtk.CssProvider(); pr.load_from_string("label { font-size: %dpx; }" % int(taille * 0.42)); l.get_style_context().add_provider(pr, 900)
        ov.set_child(l)
    ov.set_halign(Gtk.Align.START); ov.set_valign(Gtk.Align.CENTER)
    return ov

def apercu_theme(cle, accent, cfg=None):
    c = dict(cfg or {}); c.update(theme=cle, accent=accent, transparence=True)
    if cle == "auto": c["theme"] = "clair" if theme.jour() else "sombre"
    p = theme.palette(c); accent = p["accent"]
    da = Gtk.DrawingArea(); da.set_size_request(168, 94); da.add_css_class("apercu-theme")
    def dessin(area, cr, w, h):
        def rgb(hx): hx = theme.couleur_pleine(hx, p["panneau_plein"]); return tuple(int(hx.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
        cr.set_source_rgb(*rgb(p["fond"])); cr.rectangle(0, 0, w, h); cr.fill()
        cr.set_source_rgb(*rgb(p["panneau_plein"])); cr.rectangle(0, h - 16, w, 16); cr.fill()
        cr.rectangle(0, 0, w, 9); cr.fill()
        cr.set_source_rgb(*rgb(p["carte"])); cr.rectangle(w * 0.28, h * 0.22, w * 0.44, h * 0.52); cr.fill()
        cr.set_source_rgb(*rgb(accent)); cr.rectangle(w * 0.33, h * 0.30, w * 0.16, 6); cr.fill()
        cr.rectangle(w / 2 - 6, h - 12, 12, 8); cr.fill()
        cr.set_source_rgb(*rgb(p["attenue"]))
        for i in range(3): cr.rectangle(w * 0.33, h * 0.42 + i * 9, w * 0.32, 4); cr.fill()
    da.set_draw_func(dessin)
    return da

def demander(parent, titre, sous, valeur, rappel, secret=False):
    d = Gtk.Window(transient_for=parent, modal=True, title=titre, default_width=420); d.add_css_class("parametres")
    v = boite(True, 10, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
    v.append(label(titre, "page-titre", wrap=True)); v.append(label(sous, "attenue"))
    e = Gtk.PasswordEntry(show_peek_icon=True) if secret else Gtk.Entry(text=valeur)
    v.append(e)
    r = boite(False, 8, halign=Gtk.Align.END)
    def ok(*_): d.close(); rappel(e.get_text())
    e.connect("activate", ok)
    r.append(bouton("Annuler", None, "fantome", rappel=d.close)); r.append(bouton("Valider", None, "pilule", rappel=ok)); v.append(r)
    d.set_child(v); d.present(); e.grab_focus()

def confirmer(parent, titre, sous, action, rappel):
    d = Gtk.Window(transient_for=parent, modal=True, title=titre, default_width=420); d.add_css_class("parametres")
    v = boite(True, 10, margin_top=20, margin_bottom=20, margin_start=24, margin_end=24)
    v.append(label(titre, "page-titre", wrap=True)); v.append(label(sous, "attenue", wrap=True))
    r = boite(False, 8, halign=Gtk.Align.END)
    r.append(bouton("Annuler", None, "fantome", rappel=d.close)); r.append(bouton(action, None, "pilule", rappel=lambda: (d.close(), rappel(True)))); v.append(r)
    d.set_child(v); d.present()

def main():
    Parametres().run(sys.argv)
