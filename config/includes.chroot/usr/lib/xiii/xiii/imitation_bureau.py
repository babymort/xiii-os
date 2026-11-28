# OS XIII — le bureau « Façon Windows 11 » et « Façon macOS » : barre des tâches, barre des menus, Dock, Launchpad, Spotlight.
# Appelé par shell.py quand le thème choisi est une imitation (theme.imitation(cfg) → « onze » ou « macos »).
# Application développée par Matthieu Lamotte.
import os, datetime, pwd
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
from gi.repository import Gtk4LayerShell as LS
from . import apps, theme, config, systeme as S, imitation as IMIT
from .ui import *

JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
FINDER = "xiii-fichiers.desktop"
IMAGES = os.path.join(GLib.get_user_cache_dir(), "xiii", "imitation")


def enfants(w):
    L = []; c = w.get_first_child()
    while c is not None: L.append(c); c = c.get_next_sibling()
    return L


def detacher_ou(cmd, *secours):
    for c in (cmd,) + secours:
        try: S.detacher(c); return
        except Exception: continue


def touches(*args):
    """Raccourci clavier envoyé à l'appli au premier plan (menus Fichier, Édition… de la barre des menus) : wtype."""
    GLib.timeout_add(140, lambda: (S.detacher(["wtype"] + list(args)), False)[1])


def ctrl(t, maj=False):
    a = ["-M", "ctrl"] + (["-M", "shift"] if maj else []) + (["-k", t] if len(t) > 1 else [t]) + (["-m", "shift"] if maj else []) + ["-m", "ctrl"]
    return lambda: touches(*a)


def rac(spec):
    """« ctrl+shift+t », « alt+Left », « F11 » → raccourci envoyé à l'appli au premier plan."""
    *mods, k = spec.split("+"); M = {"ctrl": "ctrl", "shift": "shift", "alt": "alt", "super": "logo"}
    a = sum((["-M", M[m]] for m in mods), []) + (["-k", k] if len(k) > 1 else [k]) + sum((["-m", M[m]] for m in reversed(mods)), [])
    return lambda: touches(*a)


# menus propres aux applis courantes (les applis GTK 4 n'exportent plus leurs menus : OS XIII les décrit ici)
# clé = morceau de l'identifiant de fenêtre ; menus = [(titre, [(texte, raccourci affiché, raccourci envoyé) | None])]
_ED = [("Annuler", "Ctrl Z", "ctrl+z"), ("Rétablir", "Ctrl Maj Z", "ctrl+shift+z"), None, ("Couper", "Ctrl X", "ctrl+x"), ("Copier", "Ctrl C", "ctrl+c"),
       ("Coller", "Ctrl V", "ctrl+v"), ("Tout sélectionner", "Ctrl A", "ctrl+a"), None, ("Rechercher…", "Ctrl F", "ctrl+f")]
_ZOOM = [("Zoom avant", "Ctrl +", "ctrl+plus"), ("Zoom arrière", "Ctrl −", "ctrl+minus"), ("Taille réelle", "Ctrl 0", "ctrl+0")]
MENUS_APPLIS = [
    (("firefox", "librewolf", "chromium", "chrome", "brave"), [
        ("Fichier", [("Nouvel onglet", "Ctrl T", "ctrl+t"), ("Nouvelle fenêtre", "Ctrl N", "ctrl+n"), ("Nouvelle fenêtre privée", "Ctrl Maj P", "ctrl+shift+p"),
                     ("Ouvrir un fichier…", "Ctrl O", "ctrl+o"), None, ("Enregistrer la page sous…", "Ctrl S", "ctrl+s"), ("Imprimer…", "Ctrl P", "ctrl+p"), None,
                     ("Fermer l'onglet", "Ctrl W", "ctrl+w")]),
        ("Édition", _ED + [("Rechercher à nouveau", "Ctrl G", "ctrl+g")]),
        ("Présentation", _ZOOM + [None, ("Mode lecture", "F9", "F9"), ("Recharger la page", "Ctrl R", "ctrl+r"), ("Code source de la page", "Ctrl U", "ctrl+u"),
                                  ("Plein écran", "F11", "F11")]),
        ("Historique", [("Précédent", "Alt ←", "alt+Left"), ("Suivant", "Alt →", "alt+Right"), ("Page d'accueil", "Alt Début", "alt+Home"), None,
                        ("Rouvrir l'onglet fermé", "Ctrl Maj T", "ctrl+shift+t"), ("Tout l'historique", "Ctrl H", "ctrl+h"), ("Effacer l'historique récent…", "Ctrl Maj Suppr", "ctrl+shift+Delete")]),
        ("Marque-pages", [("Marquer cette page", "Ctrl D", "ctrl+d"), ("Barre personnelle", "Ctrl Maj B", "ctrl+shift+b"), ("Gérer les marque-pages", "Ctrl Maj O", "ctrl+shift+o")]),
        ("Outils", [("Téléchargements", "Ctrl Maj Y", "ctrl+shift+y"), ("Extensions", "Ctrl Maj A", "ctrl+shift+a"), ("Outils de développement", "F12", "F12")]),
    ]),
    (("fr.xiii.fichiers", "thunar", "nautilus"), [
        ("Fichier", [("Nouvelle fenêtre", "Ctrl N", "ctrl+n"), ("Nouvel onglet", "Ctrl T", "ctrl+t"), ("Nouveau dossier", "Ctrl Maj N", "ctrl+shift+n"), None,
                     ("Renommer", "F2", "F2"), ("Mettre à la corbeille", "Suppr", "Delete"), ("Propriétés", "Alt Entrée", "alt+Return"), None, ("Fermer l'onglet", "Ctrl W", "ctrl+w")]),
        ("Édition", _ED),
        ("Présentation", [("Volet d'aperçu", "Alt P", "alt+p"), ("Fichiers cachés", "Ctrl H", "ctrl+h"), None] + _ZOOM + [None, ("Actualiser", "F5", "F5")]),
        ("Aller", [("Précédent", "Alt ←", "alt+Left"), ("Suivant", "Alt →", "alt+Right"), ("Dossier parent", "Alt ↑", "alt+Up"), ("Dossier personnel", "Alt Début", "alt+Home"),
                   None, ("Aller au dossier…", "Ctrl L", "ctrl+l")]),
    ]),
    (("mousepad", "gedit", "gnome-text-editor", "org.gnome.texteditor"), [
        ("Fichier", [("Nouveau", "Ctrl N", "ctrl+n"), ("Ouvrir…", "Ctrl O", "ctrl+o"), None, ("Enregistrer", "Ctrl S", "ctrl+s"), ("Enregistrer sous…", "Ctrl Maj S", "ctrl+shift+s"),
                     None, ("Imprimer…", "Ctrl P", "ctrl+p"), None, ("Fermer l'onglet", "Ctrl W", "ctrl+w")]),
        ("Édition", _ED + [("Remplacer…", "Ctrl R", "ctrl+r"), ("Aller à la ligne…", "Ctrl G", "ctrl+g")]),
        ("Présentation", _ZOOM + [None, ("Plein écran", "F11", "F11")]),
    ]),
    (("foot", "fr.xiii.terminal", "terminal"), [
        ("Shell", [("Nouvelle fenêtre", "Ctrl Maj N", "ctrl+shift+n"), None, ("Fermer la fenêtre", "Ctrl Maj W", "ctrl+shift+w")]),
        ("Édition", [("Copier", "Ctrl Maj C", "ctrl+shift+c"), ("Coller", "Ctrl Maj V", "ctrl+shift+v"), None, ("Rechercher…", "Ctrl Maj R", "ctrl+shift+r")]),
        ("Présentation", _ZOOM),
    ]),
    (("mpv", "vlc", "celluloid", "fr.xiii.vignette"), [
        ("Lecture", [("Lecture / pause", "Espace", "space"), ("Avancer de 10 s", "→", "Right"), ("Reculer de 10 s", "←", "Left"), None,
                     ("Plus fort", "0", "0"), ("Moins fort", "9", "9"), ("Couper le son", "M", "m")]),
        ("Présentation", [("Plein écran", "F", "f"), ("Sous-titres suivants", "J", "j"), ("Capture de l'image", "S", "s")]),
    ]),
]


def menus_de(app_id):
    a = (app_id or "").lower()
    for cles, menus in MENUS_APPLIS:
        if any(k in a for k in cles): return menus
    return None


# ============================================================================== barre des tâches Windows 11
def barre_onze(sh):
    """Retouche la barre construite par shell.construire_barre() : Démarrer à carreaux, champ Rechercher, chevron des icônes
    de fond, groupe Wi-Fi / son / batterie (le bureau n'a plus de barre du haut)."""
    A = sh.p["accent"]
    f = IMIT.icone_demarrer_onze(A, os.path.join(IMAGES, "demarrer-%s.svg" % A.lstrip("#")))
    im = Gtk.Image.new_from_file(f); im.set_pixel_size(22); sh.b_start.set_child(im)
    barre_onze_icones(sh); sh.b_cherche.add_css_class("b-recherche"); sh.b_vue.set_tooltip_text("Vue des tâches (Super + Tab)")
    # chevron « ^ » : les icônes des applis en arrière-plan, rangées dans une bulle
    ch = Gtk.Button(); ch.add_css_class("tb"); ch.set_child(ico("chevron-up", 16, "t")); ch.set_tooltip_text("Afficher les icônes cachées")
    def bulle(_b):
        pop = Gtk.Popover(has_arrow=False); pop.set_parent(ch); pop.set_position(Gtk.PositionType.TOP)
        g = Gtk.FlowBox(max_children_per_line=4, selection_mode=Gtk.SelectionMode.NONE, margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
        n = 0
        for cle, it in sh.icones_zone(True):
            g.append(sh.bouton_zone(cle, it, 16)); n += 1
        if not n: g.append(label("Aucune icône cachée", "attenue", "petit", margin_start=8, margin_end=8, margin_top=6, margin_bottom=6))
        # glisser une icône de la barre dans la bulle : elle se cache ; glisser dans la bulle pour réordonner
        dt = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        dt.connect("drop", lambda t, v, x, y: (GLib.idle_add(lambda: (sh.deposer_zone(v, None, False), pop.popdown(), False)[-1]), True)[1] if str(v).startswith("tray:") else False)
        g.add_controller(dt)
        g.set_tooltip_text("Glissez une icône vers la barre pour la garder visible")
        pop.set_child(g); pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1])); pop.popup()
    ch.connect("clicked", bulle)
    sh.droite.insert_child_after(ch, sh.zone_notif); sh.b_chevron = ch; sh.maj_zone()
    sh.l_heure.set_xalign(1); sh.l_date.set_xalign(1)


def barre_onze_icones(sh):
    r = boite(False, 8, "onze-recherche", valign=Gtk.Align.CENTER); r.append(ico("search", 16, "t")); r.append(label("Rechercher"))
    sh.b_cherche.set_child(r); sh.b_vue.set_child(ico("copy", 19, "t"))


def haut_onze(sh):
    """Windows n'a pas de barre en haut : on la cache et on descend Wi-Fi / son / batterie dans la barre des tâches."""
    sh.haut.set_visible(False)
    etat = sh.haut_etat
    par = etat.get_parent()
    if par is not None: par.remove(etat)
    etat.remove_css_class("haut-secteur"); etat.add_css_class("onze-etat")
    sh.h_centre.set_visible(False); sh.h_dnd.set_visible(False)
    old = getattr(sh, "_onze_etat", None)
    if old is not None and old.get_parent() is not None: old.get_parent().remove(old)
    sh._onze_etat = etat
    sh.droite.insert_child_after(etat, getattr(sh, "b_chevron", sh.zone_notif))


# ============================================================================== Dock (macOS)
def barre_mac(sh):
    """Le Dock : Fichiers et la tuile Applications en premier, applis épinglées et ouvertes, séparateur, Corbeille."""
    for w in (sh.b_meteo, sh.b_cherche, sh.b_vue, sh.b_start, sh.b_heure, sh.b_cloche):
        w.set_visible(False)
    sh.zone_notif.set_visible(False)
    c = sh.droite.get_last_child()
    while c is not None:
        if c.has_css_class("coin-bureau"): c.set_visible(False)
        c = c.get_prev_sibling()
    sep = Gtk.Box(); sep.add_css_class("dock-sep")
    sh.groupe.append(sep)
    sh.b_corbeille = Gtk.Button(); sh.b_corbeille.add_css_class("tb"); sh.b_corbeille.set_tooltip_text("Corbeille")
    sh.b_corbeille.connect("clicked", lambda *_: detacher_ou(["xiii-fichiers", "--corbeille"]))
    clic_droit(sh.b_corbeille, lambda: popover_menu(sh.b_corbeille, [("folder-open", "Ouvrir", lambda: S.detacher(["xiii-fichiers", "--corbeille"])),
                                                                      ("trash-2", "Vider la corbeille…", lambda: S.detacher(["xiii-fichiers", "--corbeille"]))]))
    sh.groupe.append(sh.b_corbeille); maj_corbeille(sh)
    sh.groupe.set_margin_start(0)


def maj_corbeille(sh):
    b = getattr(sh, "b_corbeille", None)
    if b is None: return
    d = os.path.expanduser("~/.local/share/Trash/files")
    try: plein = bool(os.listdir(d))
    except OSError: plein = False
    v = boite(True, 2, valign=Gtk.Align.CENTER)
    im = Gtk.Image.new_from_icon_name("user-trash-full" if plein else "user-trash"); im.set_pixel_size(sh.taille_icone()); v.append(im)
    ind = Gtk.Box(halign=Gtk.Align.CENTER); ind.add_css_class("tb-ind"); ind.add_css_class("vide"); v.append(ind)
    b.set_child(v)


def bouton_launchpad(sh):
    b = Gtk.Button(); b.add_css_class("tb"); b.set_tooltip_text("Applications (Launchpad)")
    f = IMIT.icone_launchpad(os.path.join(IMAGES, "launchpad.svg"))
    v = boite(True, 2, valign=Gtk.Align.CENTER)
    im = Gtk.Image.new_from_file(f); im.set_pixel_size(sh.taille_icone()); v.append(im)
    ind = Gtk.Box(halign=Gtk.Align.CENTER); ind.add_css_class("tb-ind"); ind.add_css_class("vide"); v.append(ind)
    b.set_child(v); b.connect("clicked", lambda *_: sh.basculer("launchpad"))
    clic_droit(b, lambda: popover_menu(b, [("layout-grid", "Menu des applications", lambda: sh.ouvrir("demarrer")), ("settings", "Réglages du Dock", lambda: sh.parametres("barre"))]))
    return b


def ordre_dock(ordre):
    """Fichiers toujours en tête du Dock, comme le Finder."""
    return [FINDER] + [k for k in ordre if k != FINDER]


# ============================================================================== barre des menus (macOS)
class MenusMac:
    def __init__(self, sh):
        self.sh = sh; self.pop = None

    def construire(self):
        sh = self.sh
        cb = Gtk.CenterBox(); cb.add_css_class("haut"); cb.set_size_request(-1, 28)
        g = boite(False, 0, margin_start=8)
        lg = Gtk.Button(); lg.add_css_class("hb"); lg.set_child(label("XIII", "mac-logo")); lg.set_tooltip_text("OS XIII")
        self.titre(lg, self.menu_systeme); g.append(lg)
        self.b_appli = Gtk.Button(); self.b_appli.add_css_class("hb"); self.b_appli.add_css_class("mac-appli")
        self.l_appli = label("Fichiers"); self.b_appli.set_child(self.l_appli); self.titre(self.b_appli, self.menu_appli); g.append(self.b_appli)
        self.g_menus = g; self._profil = "?"; self.poser_menus()
        cb.set_start_widget(g)
        d = boite(False, 0, margin_end=8, valign=Gtk.Align.CENTER)
        # icônes des applis en fond, puis état (monochrome), Spotlight, Centre de contrôle, date et heure
        z = sh.zone_notif; par = z.get_parent()
        if par is not None: par.remove(z)
        z.set_visible(True); d.append(z)
        for w in (sh.h_dnd, sh.h_conc, sh.h_bat, sh.h_wifi, sh.h_bt):
            p_ = w.get_parent()
            if p_ is not None: p_.remove(w)
            d.append(w)
        sp = Gtk.Button(); sp.add_css_class("hb"); sp.set_child(ico("search", 15, "t")); sp.set_tooltip_text("Spotlight (Super + Espace)")
        sp.connect("clicked", lambda *_: sh.basculer("spotlight")); d.append(sp)
        cc = sh.h_centre; p_ = cc.get_parent()
        if p_ is not None: p_.remove(cc)
        cc.set_child(ico("toggle-right", 16, "t")); cc.set_visible(True); cc.set_tooltip_text("Centre de contrôle"); d.append(cc)
        self.b_heure = Gtk.Button(); self.b_heure.add_css_class("hb"); self.l_heure = label("", "mac-horloge"); self.b_heure.set_child(self.l_heure)
        self.b_heure.set_tooltip_text("Centre de notifications"); self.b_heure.connect("clicked", lambda *_: sh.basculer("volet"))
        sh.boutons_panneaux.setdefault("volet", []).append(self.b_heure)
        clic_droit(self.b_heure, lambda: sh.parametres("heure")); d.append(self.b_heure)
        cb.set_end_widget(d)
        sh.haut.set_child(cb); sh.haut.set_visible(True)
        self.tic(); self.maj_appli()

    def poser_menus(self):
        """Titres de la barre des menus selon l'appli au premier plan (menus de l'appli si OS XIII les connaît)."""
        f = self.active(); m = menus_de(f.app_id if f else "")
        cle = repr([t for t, _ in m]) if m else "generique"
        if cle == self._profil: return
        self._profil = cle
        g = self.g_menus; c = self.b_appli.get_next_sibling()
        while c is not None:
            n = c.get_next_sibling(); g.remove(c); c = n
        self.titres = [t for t in getattr(self, "titres", []) if t[0] in (g.get_first_child(), self.b_appli)]
        if m:
            liste = [(t, (lambda it=it: [None if x is None else (x[0], x[1], rac(x[2])) for x in it])) for t, it in m] + [("Fenêtre", self.menu_fenetre), ("Aide", self.menu_aide)]
        else:
            liste = [("Fichier", self.menu_fichier), ("Édition", self.menu_edition), ("Présentation", self.menu_presentation), ("Fenêtre", self.menu_fenetre), ("Aide", self.menu_aide)]
        for nom, fn in liste:
            b = Gtk.Button(); b.add_css_class("hb"); b.set_child(label(nom)); self.titre(b, fn); g.append(b)

    # ---------------------------------------------------------------- titres de menus
    def titre(self, b, fn):
        self.titres = getattr(self, "titres", []) + [(b, fn)]
        b.connect("clicked", lambda *_: self.ouvrir(b, fn))
        m = Gtk.EventControllerMotion()
        m.connect("enter", lambda *_: self.ouvrir(b, fn) if self.pop is not None and getattr(self.pop, "_titre", None) is not b else None)
        b.add_controller(m)

    def ouvrir(self, b, fn):
        if self.pop is not None:
            p = self.pop; self.pop = None
            if getattr(p, "_titre", None) is b: p.popdown(); return
            p.popdown()
        items = fn()
        pop = Gtk.Popover(has_arrow=False); pop.add_css_class("mac-menu"); pop.set_parent(b); pop.set_position(Gtk.PositionType.BOTTOM)
        pop.set_halign(Gtk.Align.START); pop._titre = b
        v = boite(True, 0)
        for it in items:
            if it is None:
                v.append(Gtk.Separator()); continue
            texte, rac, rap = it[0], it[1], it[2]
            actif = it[3] if len(it) > 3 else True
            x = Gtk.Button(); x.add_css_class("mac-item"); x.set_sensitive(actif)
            r = boite(False, 24); r.append(label(texte, hexpand=True)); r.append(label(rac or "", "mac-raccourci")); x.set_child(r)
            x.connect("clicked", lambda _x, f=rap: (pop.popdown(), GLib.timeout_add(60, lambda: (f(), False)[1])))
            v.append(x)
        pop.set_child(v); b.add_css_class("ouvert")
        def ferme(p):
            b.remove_css_class("ouvert")
            if self.pop is p: self.pop = None
            GLib.idle_add(lambda: (p.unparent(), False)[1])
        pop.connect("closed", ferme); self.pop = pop; pop.popup()

    # ---------------------------------------------------------------- contenu des menus
    def active(self):
        sh = self.sh
        return sh.fenetres.active() if sh.fenetres and sh.fenetres.ok else None

    def nom_appli(self):
        f = self.active()
        if not f: return "Fichiers"
        a = apps.pour_fenetre(f.app_id)
        return a.get_display_name() if a else (f.app_id or f.titre or "Appli").split(".")[-1].capitalize()

    def menu_systeme(self):
        sh = self.sh; u = pwd.getpwuid(os.getuid()); nom = (u.pw_gecos.split(",")[0] or u.pw_name).strip()
        return [("À propos de cet ordinateur", "", lambda: sh.parametres("apropos")), None,
                ("Réglages Système…", "", lambda: sh.parametres("accueil")), ("Logithèque…", "", lambda: S.detacher("xiii-logiciels")), None,
                ("Forcer à quitter…", "Ctrl Maj Échap", lambda: S.detacher("xiii-taches")), None,
                ("Suspendre l'activité", "", lambda: S.detacher("systemctl suspend")), ("Redémarrer…", "", lambda: S.detacher("systemctl reboot")),
                ("Éteindre…", "", lambda: S.detacher("systemctl poweroff")), None,
                ("Verrouiller l'écran", "Super L", lambda: S.detacher("swaylock -f")), ("Fermer la session de %s…" % nom, "", lambda: S.detacher("labwc --exit"))]

    def menu_appli(self):
        sh = self.sh; f = self.active(); n = self.nom_appli()
        return [("À propos de %s" % n, "", lambda: sh.parametres("apps")), None,
                ("Réglages…", "Ctrl ,", ctrl("comma")), None,
                ("Masquer %s" % n, "", lambda: sh.fenetres.reduire(f) if f else None, bool(f)),
                ("Masquer les autres", "", self.masquer_autres, bool(f)), None,
                ("Quitter %s" % n, "Ctrl Q", lambda: sh.fenetres.fermer(f) if f else None, bool(f))]

    def masquer_autres(self):
        sh = self.sh; a = self.active()
        for f in sh.fenetres.liste():
            if f is not a and not f.reduite: sh.fenetres.reduire(f)

    def menu_fichier(self):
        sh = self.sh; f = self.active()
        return [("Nouvelle fenêtre", "Ctrl N", ctrl("n")), ("Nouvel onglet", "Ctrl T", ctrl("t")), ("Ouvrir…", "Ctrl O", ctrl("o")), None,
                ("Enregistrer", "Ctrl S", ctrl("s")), ("Enregistrer sous…", "Ctrl Maj S", ctrl("s", True)), None,
                ("Imprimer…", "Ctrl P", ctrl("p")), None,
                ("Fermer la fenêtre", "Ctrl W", lambda: sh.fenetres.fermer(f) if f else None, bool(f))]

    def menu_edition(self):
        return [("Annuler", "Ctrl Z", ctrl("z")), ("Rétablir", "Ctrl Maj Z", ctrl("z", True)), None,
                ("Couper", "Ctrl X", ctrl("x")), ("Copier", "Ctrl C", ctrl("c")), ("Coller", "Ctrl V", ctrl("v")),
                ("Tout sélectionner", "Ctrl A", ctrl("a")), None, ("Rechercher…", "Ctrl F", ctrl("f")), None,
                ("Émojis et symboles", "Super .", lambda: self.sh.basculer("emoji")), ("Historique du presse-papiers", "Super V", lambda: self.sh.basculer("presse"))]

    def menu_presentation(self):
        sh = self.sh; f = self.active()
        return [("Zoom avant", "Ctrl +", ctrl("plus")), ("Zoom arrière", "Ctrl −", ctrl("minus")), ("Taille réelle", "Ctrl 0", ctrl("0")), None,
                ("Passer en plein écran", "F11", lambda: sh.fenetres.plein_ecran(f) if f else None, bool(f))]

    def menu_fenetre(self):
        sh = self.sh; f = self.active()
        L = [("Placer dans le Dock", "", lambda: sh.fenetres.reduire(f) if f else None, bool(f)),
             ("Réduire / agrandir", "Super ↑", lambda: sh.fenetres.agrandir(f) if f else None, bool(f)),
             ("Toujours au premier plan", "Ctrl Super T", lambda: touches("-M", "ctrl", "-M", "logo", "t", "-m", "logo", "-m", "ctrl"), bool(f)), None,
             ("Disposer les fenêtres…", "", lambda: sh.basculer("dispositions")), ("Mission Control", "Super Tab", lambda: sh.basculer("vue")),
             ("Afficher le bureau", "Super D", sh.afficher_bureau), None]
        for x in (sh.fenetres.liste() if sh.fenetres and sh.fenetres.ok else [])[:12]:
            L.append((("✓ " if x.active else "   ") + (x.titre or x.app_id or "Fenêtre")[:48], "", lambda x=x: sh.fenetres.activer(x)))
        return L

    def menu_aide(self):
        sh = self.sh
        return [("Visite d'OS XIII", "", lambda: sh.basculer("visite")), ("Raccourcis clavier", "", lambda: sh.parametres("raccourcis")),
                ("Rechercher dans les réglages…", "", lambda: sh.basculer("spotlight"))]

    # ---------------------------------------------------------------- mises à jour
    def tic(self):
        n = datetime.datetime.now(); c = self.sh.cfg
        h = n.strftime("%H:%M" if c.get("horloge_24h", True) else "%I:%M %p")
        self.l_heure.set_text("%s %d %s  %s" % (JOURS[n.weekday()], n.day, MOIS[n.month - 1], h))

    def maj_appli(self):
        t = self.nom_appli()
        if t != self.l_appli.get_text(): self.l_appli.set_text(t)
        if self.pop is None: self.poser_menus()


# ============================================================================== Launchpad (macOS)
class Launchpad:
    PAR_PAGE = 35
    def __init__(self, shell):
        self.shell = shell; self.page = 0
        ov = Gtk.Overlay(); ov.add_css_class("launchpad"); self.widget = ov
        self.fond = Gtk.Picture(); self.fond.set_content_fit(Gtk.ContentFit.COVER); self.fond.set_can_shrink(True); ov.set_child(self.fond)
        voile = Gtk.Box(); voile.add_css_class("launchpad"); ov.add_overlay(voile)
        v = boite(True, 18, margin_top=46, margin_bottom=36)
        self.entree = Gtk.Entry(placeholder_text="Rechercher", halign=Gtk.Align.CENTER)
        self.entree.set_icon_from_paintable(Gtk.EntryIconPosition.PRIMARY, theme.icone("search", 14, "#ffffff"))
        self.entree.connect("changed", lambda *_: self.remplir()); self.entree.connect("activate", self.premier)
        v.append(self.entree)
        self.pile = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=260); v.append(self.pile)
        self.points = boite(False, 10, halign=Gtk.Align.CENTER); v.append(self.points)
        ov.add_overlay(v)
        # clic dans le vide : fermer ; molette : page suivante / précédente
        g = Gtk.GestureClick(); g.connect("released", self.clic_vide); ov.add_controller(g)
        sc = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES | Gtk.EventControllerScrollFlags.DISCRETE)
        sc.connect("scroll", lambda c, dx, dy: (self.aller(self.page + (1 if (dy or dx) > 0 else -1)), True)[1]); ov.add_controller(sc)

    def clic_vide(self, g, n, x, y):
        w = self.widget.pick(x, y, Gtk.PickFlags.DEFAULT)
        while w is not None and w is not self.widget:
            if isinstance(w, (Gtk.Button, Gtk.Entry, Gtk.Text)): return
            w = w.get_parent()
        self.shell.fermer()

    def flou_fond(self):
        """Fond d'écran flouté (réduit puis agrandi), comme derrière le Launchpad."""
        f = self.shell.cfg.get("fond")
        if getattr(self, "_fond", None) == f: return
        self._fond = f
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(f, 64, 36, False)
            pb = pb.scale_simple(640, 360, GdkPixbuf.InterpType.BILINEAR).scale_simple(1280, 720, GdkPixbuf.InterpType.BILINEAR)
            self.fond.set_paintable(Gdk.Texture.new_for_pixbuf(pb))
        except Exception:
            self.fond.set_paintable(None)

    def rafraichir(self):
        self.flou_fond(); self.entree.set_text(""); self.remplir()
        GLib.idle_add(lambda: (self.entree.grab_focus(), False)[1])

    # ---- dossiers (glisser une appli sur une autre crée un dossier, comme sur macOS)
    def dossiers(self):
        return [dict(d) for d in (self.shell.cfg.get("launchpad_dossiers") or []) if d.get("apps")]

    def ecrire_dossiers(self, D):
        D = [d for d in D if len(d.get("apps", [])) >= 1]
        self.shell.cfg["launchpad_dossiers"] = D; config.modifier(_histo=False, launchpad_dossiers=D)
        GLib.idle_add(lambda: (self.remplir(), False)[1])

    def deposer(self, src, cible):
        """src / cible : « app:ID » ou « dossier:N »."""
        D = self.dossiers()
        if not src.startswith("app:"): return
        sid = src[4:]
        for d in D:
            if sid in d["apps"]: d["apps"].remove(sid)
        if cible.startswith("dossier:"):
            i = int(cible[8:])
            if i < len(D) and sid not in D[i]["apps"]: D[i]["apps"].append(sid)
        else:
            cid = cible[4:]
            for d in D:
                if cid in d["apps"]: d["apps"].append(sid); break
            else:
                a, b = apps.par_id(sid), apps.par_id(cid)
                cats = lambda x: set((x.get_categories() or "").split(";")) - {"", "GTK", "GNOME", "XIII", "Qt", "KDE", "X-XIII"} if x else set()
                commun = cats(a) & cats(b)
                NOMS = {"Game": "Jeux", "AudioVideo": "Audio et vidéo", "Video": "Vidéo", "Audio": "Audio", "Graphics": "Graphisme", "Office": "Bureautique",
                        "Network": "Internet", "Development": "Développement", "System": "Système", "Utility": "Utilitaires", "Settings": "Réglages", "Education": "Éducation"}
                nom = next((NOMS[c] for c in NOMS if c in commun), "Dossier")
                D.append({"nom": nom, "apps": [cid, sid]})
        self.ecrire_dossiers(D)

    def bouton_dossier(self, i, d):
        b = Gtk.Button(); b.add_css_class("lp-app")
        bx = boite(True, 6); gr = Gtk.Grid(row_spacing=3, column_spacing=3, halign=Gtk.Align.CENTER); gr.add_css_class("lp-dossier")
        for k, aid in enumerate(d["apps"][:4]):
            a = apps.par_id(aid)
            if a: gr.attach(gicon_image(a.get_icon(), 32), k % 2, k // 2, 1, 1)
        bx.append(gr); bx.append(label(d.get("nom") or "Dossier", "lp-nom", xalign=0.5, ellipsize=True, largeur=14)); b.set_child(bx)
        b.set_tooltip_text("%s — %d applis" % (d.get("nom"), len(d["apps"])))
        b.connect("clicked", lambda bb, i=i: self.ouvrir_dossier(bb, i))
        glisser_deposer(b, "dossier:%d" % i, lambda src, i=i: self.deposer(src, "dossier:%d" % i))
        return b

    def ouvrir_dossier(self, b, i):
        D = self.dossiers()
        if i >= len(D): return
        d = D[i]; pop = Gtk.Popover(); pop.add_css_class("lp-dossier-ouvert"); pop.set_parent(b)
        v = boite(True, 12, margin_start=16, margin_end=16, margin_top=12, margin_bottom=12)
        e = Gtk.Entry(text=d.get("nom", ""), halign=Gtk.Align.CENTER); e.add_css_class("lp-nom-dossier")
        def renommer(*_):
            D2 = self.dossiers()
            if i < len(D2): D2[i]["nom"] = e.get_text().strip() or "Dossier"; self.ecrire_dossiers(D2)
        e.connect("activate", lambda *_: (renommer(), pop.popdown())); v.append(e)
        g = Gtk.FlowBox(max_children_per_line=4, selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, row_spacing=12, column_spacing=16)
        for aid in d["apps"]:
            a = apps.par_id(aid)
            if not a: continue
            x = Gtk.Button(); x.add_css_class("lp-app"); bx = boite(True, 4); bx.append(gicon_image(a.get_icon(), 56))
            bx.append(label(a.get_display_name(), "lp-nom", xalign=.5, ellipsize=True, largeur=12)); x.set_child(bx)
            x.connect("clicked", lambda _x, a=a: (pop.popdown(), self.shell.fermer(), apps.lancer(a)))
            def retirer(aid=aid):
                D2 = self.dossiers()
                if i < len(D2) and aid in D2[i]["apps"]: D2[i]["apps"].remove(aid)
                pop.popdown(); self.ecrire_dossiers(D2)
            clic_droit(x, retirer); x.set_tooltip_text("Clic droit : retirer du dossier")
            g.append(x)
        v.append(g); v.append(label("Glissez une appli sur ce dossier pour l'y ranger · clic droit sur une appli : la sortir", "lp-nom", xalign=.5))
        pop.set_child(v); pop.connect("closed", lambda p: (renommer() if e.get_text().strip() != d.get("nom") else None, GLib.idle_add(lambda: (p.unparent(), False)[1])))
        pop.popup()

    def remplir(self):
        q = sans_accents(self.entree.get_text().strip())
        D = self.dossiers() if not q else []
        ranges = {x for d in D for x in d["apps"]}
        L = [("d", i, d) for i, d in enumerate(D)] + [a for a in apps.toutes() if (not q or q in sans_accents(a.get_display_name())) and a.get_id() not in ranges]
        self._liste = [a for a in L if not isinstance(a, tuple)]
        for c in enfants(self.pile):
            self.pile.remove(c)
        vider(self.points)
        n = max(1, (len(L) + self.PAR_PAGE - 1) // self.PAR_PAGE)
        for i in range(n):
            g = Gtk.FlowBox(max_children_per_line=7, min_children_per_line=7, selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                            row_spacing=18, column_spacing=24, valign=Gtk.Align.START, halign=Gtk.Align.CENTER, margin_start=80, margin_end=80)
            for a in L[i * self.PAR_PAGE:(i + 1) * self.PAR_PAGE]:
                if isinstance(a, tuple): g.append(self.bouton_dossier(a[1], a[2])); continue
                b = Gtk.Button(); b.add_css_class("lp-app")
                bx = boite(True, 6); bx.append(gicon_image(a.get_icon(), 76)); bx.append(label(a.get_display_name(), "lp-nom", xalign=0.5, ellipsize=True, largeur=14))
                b.set_child(bx); b.set_tooltip_text(a.get_description() or a.get_display_name())
                b.connect("clicked", lambda _b, a=a: (self.shell.fermer(), apps.lancer(a)))
                if not q: glisser_deposer(b, "app:" + a.get_id(), lambda src, aid=a.get_id(): self.deposer(src, "app:" + aid))
                g.append(b)
            self.pile.add_named(g, str(i))
            if n > 1:
                p = Gtk.Button(); p.add_css_class("lp-point"); p.connect("clicked", lambda _p, i=i: self.aller(i)); self.points.append(p)
        self.page = 0; self.aller(0)

    def aller(self, i):
        n = len(enfants(self.pile))
        if not n: return
        self.page = max(0, min(n - 1, i)); self.pile.set_visible_child_name(str(self.page))
        for k, p in enumerate(enfants(self.points)): (p.add_css_class if k == self.page else p.remove_css_class)("actif")

    def premier(self, *_):
        if getattr(self, "_liste", None):
            a = self._liste[0]; self.shell.fermer(); apps.lancer(a)


# ============================================================================== Spotlight (macOS)
class Spotlight:
    """La recherche du menu Démarrer, seule, en grand champ au milieu de l'écran (Super + Espace)."""
    def __init__(self, shell):
        self.shell = shell
        self.m = type(shell.menu)(shell)
        w = self.m.widget; w.add_css_class("spotlight"); w.set_size_request(680, -1); self.widget = w
        self.m.filtres.set_visible(False)
        pied = w.get_last_child()
        if pied is not None and pied is not self.m.pile: pied.set_visible(False)
        self.m.recherche.set_placeholder_text("Recherche Spotlight")
        self.m.recherche.connect("changed", lambda e: self.m.pile.set_visible(bool(e.get_text().strip())))
        self.m.pile.set_size_request(-1, 380)

    def rafraichir(self):
        self.m.reinitialiser(); self.m.pile.set_visible(False)
        GLib.idle_add(lambda: (self.m.recherche.grab_focus(), False)[1])


# ============================================================================== placement des panneaux
def ancrer_panneaux(sh, ecart, HH):
    """Windows 11 : réglages rapides et notifications en bas à droite, au-dessus de la barre (pas de barre en haut).
    macOS : bulles de notification en haut à droite, sous la barre des menus. Les panneaux déjà construits sont refaits
    (une surface cachée ne doit pas changer de bords d'ancrage)."""
    T, B, L, R = LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT
    im = theme.imitation(sh.cfg)
    for nom in ("son", "wifi", "bluetooth", "batterie", "centre", "alim"):
        if nom not in sh._defs: continue
        cls = sh._defs[nom][0]
        anc, mg = ((B, R), {B: ecart, R: 12}) if im == "onze" else ((T, R), {T: HH + 8, R: 8})
        if (sh._defs[nom][1], sh._defs[nom][2]) != (mg, anc):
            sh._defs[nom] = (cls, mg, anc); refaire(sh, nom)
    if "volet" in sh._defs and im == "onze":
        cls = sh._defs["volet"][0]; sh._defs["volet"] = (cls, {T: 12, B: ecart, R: 12}, (T, B, R)); refaire(sh, "volet")
    if "widgets" in sh._defs and im == "onze":
        cls = sh._defs["widgets"][0]; sh._defs["widgets"] = (cls, {T: 12, B: ecart, L: 12}, (T, B, L)); refaire(sh, "widgets")
    # panneaux propres à macOS
    if im == "macos":
        sh._defs["launchpad"] = (Launchpad, {}, (T, B, L, R))
        sh._defs["spotlight"] = (Spotlight, {T: 170}, (T,))
    else:
        for nom in ("launchpad", "spotlight"):
            if nom in sh._defs: refaire(sh, nom); sh._defs.pop(nom, None)
    # bulles de notification
    bu = getattr(sh, "bulles", None)
    if bu is not None:
        voulu = "haut" if im == "macos" else "bas"
        if getattr(sh, "_bulles_pos", "bas") != voulu:
            sh._bulles_pos = voulu
            vis = bu.get_visible()
            if not vis: bu.set_visible(True)
            for e in (T, B, L, R): LS.set_anchor(bu, e, e in ((T, R) if voulu == "haut" else (B, R))); LS.set_margin(bu, e, 0)
            if voulu == "haut": LS.set_margin(bu, T, HH + 8)
            else: LS.set_margin(bu, B, ecart)
            LS.set_margin(bu, R, 10)
            if not vis: bu.set_visible(False)


def refaire(sh, nom):
    if nom in sh.panneaux and sh.ouvert != nom:
        w, obj = sh.panneaux.pop(nom)
        GLib.timeout_add_seconds(20, lambda o=obj: (o.__dict__.clear(), False)[1])
        w.destroy()
