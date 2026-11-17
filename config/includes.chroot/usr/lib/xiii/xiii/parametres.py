# OS XIII — Paramètres (aussi complets que ceux de Windows 11, aux couleurs de la Suite XIII).
# Lancement : xiii-parametres [--page clé]
# Application développée par Matthieu Lamotte.
import os, sys, re, glob, json, shutil, subprocess, pwd, time, datetime, threading, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, Pango
from . import config, theme, systeme as S, apps
from .ui import *
from .pages_index import PAGES, PAR_CLE, CATEGORIES, ALIAS, INDEX
from .panneaux import METEO

FONDS_PERSO = os.path.join(GLib.get_user_data_dir(), "xiii", "fonds")
RC = os.path.join(GLib.get_user_config_dir(), "labwc", "rc.xml")
CLES_THEME = {"theme", "accent", "transparence", "animations", "taille_texte", "curseur_taille", "police", "verrou_fond"}

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
        if "theme" in kw and "fond" not in kw:
            c2 = dict(self.cfg); c2.update(kw); kw["fond"] = theme.fond_assorti(c2)
        self.cfg = config.modifier(**kw)
        if CLES_THEME & set(kw):
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
            pb = Gtk.Button(); pb.add_css_class("fil-lien"); pb.set_child(label(PAR_CLE[p[3]][1]))
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
        carte("palette", "Personnalisation", lambda: "Thème %s · accent %s" % (cfg["theme"], cfg["accent"]), "theme")
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

    def ecran(self, e, mode=None, hz=None, echelle=None, rotation=None):
        w = h = None
        if mode: w, h = map(int, mode.split("x"))
        S.en_fond(S.regler_ecran, None, e["nom"], w, h, hz, echelle, rotation)
        ec = dict(self.cfg.get("ecrans", {})); d = dict(ec.get(e["nom"], {}))
        if mode: d.update(w=w, h=h)
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
        c.append(groupe_titre("Raccourcis clavier d'OS XIII"))
        for k, d in (("Super", "Menu Démarrer"), ("Super + A", "Centre de contrôle"), ("Super + N", "Volet de notifications"), ("Super + I", "Paramètres"),
                     ("Super + E", "Explorateur de fichiers"), ("Super + L", "Verrouiller"), ("Super + Maj + S", "Capture d'une zone"), ("Impr. écran", "Capture de l'écran entier"),
                     ("Super + V", "Historique du presse-papiers"), ("Super + .", "Émojis"), ("Super + Tab", "Vue des tâches"), ("Super + Z", "Dispositions des fenêtres"),
                     ("Super + D", "Afficher le bureau"), ("Super + W", "Widgets"), ("Super + ← / →", "Ancrer la fenêtre à gauche / droite"), ("Super + ↑", "Agrandir"),
                     ("Alt + Tab", "Changer de fenêtre"), ("Alt + F4", "Fermer la fenêtre"), ("Super + Entrée", "Terminal")):
            c.append(reglage(None, d, None, droite=label(k, "mono", "accent")))

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
        c.append(reglage("settings-2", "Modifier (IP fixe, DNS…)", "", clic=lambda: S.detacher("nm-connection-editor")))

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

    def p_duo(self, c, cle):
        c.append(info("XIII Duo utilisera le Wi-Fi et le câble en même temps : Plexo pour les téléchargements, répartition et secours automatique pour le reste. Arrive dans une prochaine version."))
        e = S.details_interfaces()
        for i in e: c.append(reglage("wifi" if i["type"] == "wifi" else "ethernet-port", i["dev"], i["etat"]))

    # ================================================================== PERSONNALISATION
    def p_perso(self, c, cle):
        h = boite(False, 18, "hero")
        pic = vignette(self.cfg["fond"], 320, 180)
        f = Gtk.Frame(); f.set_child(pic); h.append(f)
        v = boite(True, 6, valign=Gtk.Align.CENTER)
        v.append(label("Choisissez un thème", "gras"))
        r = boite(False, 8)
        for k, n, _ in theme.THEMES:
            b = bouton(n, None, "pilule" if self.cfg["theme"] == k else "fantome", rappel=lambda k=k: self.regler(theme=k)); r.append(b)
        v.append(r); h.append(v); c.append(h)
        self.p_categorie(c, "perso")

    def p_theme(self, c, cle):
        cfg = self.cfg
        c.append(groupe_titre("Thème"))
        g = boite(False, 12, homogeneous=True)
        for k, n, d in theme.THEMES:
            b = Gtk.Button(); b.add_css_class("vignette")
            if cfg["theme"] == k: b.add_css_class("sel")
            v = boite(True, 6)
            v.append(apercu_theme(k, cfg["accent"]))
            v.append(label(n, "gras", xalign=0.5)); v.append(label(d, "attenue", "petit", wrap=True, xalign=0.5, justify=Gtk.Justification.CENTER))
            b.set_child(v); b.connect("clicked", lambda _b, k=k: self.regler(theme=k)); g.append(b)
        c.append(g)
        c.append(groupe_titre("Couleur d'accent"))
        r = boite(False, 8, "reglage")
        fl = Gtk.FlowBox(max_children_per_line=14, selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6, hexpand=True)
        for n, hx in theme.ACCENTS:
            b = Gtk.Button(); b.add_css_class("pastille")
            if hx.lower() == cfg["accent"].lower(): b.add_css_class("sel")
            pr = Gtk.CssProvider(); pr.load_from_string("button { background: %s; }" % hx)
            b.get_style_context().add_provider(pr, 900); b.set_tooltip_text(n)
            b.connect("clicked", lambda _b, hx=hx: self.regler(accent=hx)); fl.append(b)
        r.append(fl); c.append(r)
        dlg = Gtk.ColorDialog(with_alpha=False); cb = Gtk.ColorDialogButton(dialog=dlg)
        rg = Gdk.RGBA(); rg.parse(cfg["accent"]); cb.set_rgba(rg)
        def couleur(btn, _p):
            x = btn.get_rgba(); hx = "#%02x%02x%02x" % (int(x.red * 255), int(x.green * 255), int(x.blue * 255))
            if hx != self.cfg["accent"]: self.regler(accent=hx)
        cb.connect("notify::rgba", couleur)
        c.append(reglage("palette", "Couleur personnalisée", "Choisissez n'importe quelle couleur", droite=cb))
        c.append(groupe_titre("Effets"))
        c.append(reglage("sparkles", "Effets de transparence (glassglow)", "Verre et lueur autour des panneaux",
                         droite=interrupteur(cfg["transparence"], lambda on: self.regler(transparence=on))))
        c.append(reglage("wand-sparkles", "Animations", "Transitions des menus et fenêtres", droite=interrupteur(cfg["animations"], lambda on: self.regler(animations=on))))
        c.append(info("D'autres thèmes de la Suite XIII (Cyberpunk, Terminal, Mac OS 9, Game Boy…) arrivent avec la phase Design XIII."))

    def p_fond(self, c, cle):
        cfg = self.cfg
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
        c.append(reglage("move-horizontal", "Ajustement", "", droite=deroulant([("fill", "Remplir"), ("fit", "Ajuster"), ("stretch", "Étirer"), ("center", "Centrer"), ("tile", "Mosaïque")],
                                                                                cfg["fond_mode"], lambda v: self.regler(fond_mode=v))))

    def choisir_image(self, cle):
        d = Gtk.FileDialog(title="Choisir une image")
        ff = Gtk.FileFilter(); ff.set_name("Images"); ff.add_mime_type("image/*")
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
                S.en_fond(lambda: subprocess.run(["pkexec", "sh", "-c", "apt-get update && apt-get install -y claude-desktop claude-code"]).returncode,
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
        c.append(reglage("history", "Instantanés du système", "Façon Time Machine : restaurer le système à une date précédente (Timeshift)", droite=bouton("Ouvrir", None, "fantome", rappel=lambda: S.detacher("pkexec timeshift-launcher"))))
        c.append(reglage("rotate-ccw", "Restaurer un fichier", "Retrouver une version précédente d'un fichier ou d'un dossier", droite=bouton("Restaurer", None, "fantome", rappel=lambda: S.detacher(["deja-dup", "--restore"]))))

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

    def p_outilsprod(self, c, cle):
        cfg = self.cfg
        c.append(groupe_titre("Horloge timecode"))
        c.append(reglage("clock", "Afficher le timecode en haut de l'écran", "HH:MM:SS:II calé sur l'heure système (synchronisée par Internet)",
                         droite=interrupteur(cfg.get("timecode", False), lambda on: self.regler(timecode=on))))
        c.append(reglage("film", "Images par seconde", None, droite=deroulant([(str(f), "%s i/s" % f) for f in (24, 25, 30, 50, 60)], str(cfg.get("timecode_fps", 25)),
                                                                              lambda v: self.regler(timecode_fps=int(v)))))
        c.append(info("Pour caler plusieurs PC d'un plateau : activez « Régler l'heure automatiquement » (Heure et langue) sur chacun. Entrée LTC : à venir."))
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
        c.append(reglage("timer", "Verrouillage automatique", "", clic=lambda: self.aller("alimentation")))

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
        c.append(reglage("sparkles", "Effets de transparence", "", droite=interrupteur(cfg["transparence"], lambda on: self.regler(transparence=on))))
        c.append(reglage("wand-sparkles", "Effets d'animation", "", droite=interrupteur(cfg["animations"], lambda on: self.regler(animations=on))))
        hc = cfg["theme"] == "sobre" and cfg["accent"].lower() == "#ffd54f"
        c.append(reglage("contrast", "Contraste élevé", "Thème Sobre, accent jaune vif, texte agrandi",
                         droite=interrupteur(hc, lambda on: self.regler(theme="sobre", accent="#ffd54f", taille_texte=1.15, transparence=False) if on
                                             else self.regler(theme="sombre", accent="#f0b378", taille_texte=1.0, transparence=True))))
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
        c.append(info("Les mises à jour d'OS XIII et de ses applications passent par les dépôts Debian et le dépôt XIII. Un mot de passe administrateur est demandé."))

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

def apercu_theme(cle, accent):
    p = theme.palette({"theme": cle, "accent": accent, "transparence": True})
    da = Gtk.DrawingArea(); da.set_size_request(200, 112); da.add_css_class("apercu-theme")
    def dessin(area, cr, w, h):
        def rgb(hx): return tuple(int(hx.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
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
