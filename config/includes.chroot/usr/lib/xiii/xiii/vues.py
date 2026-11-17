# OS XIII — vue des tâches (Super+Tab), dispositions d'ancrage (Super+Z), coins actifs,
# historique du presse-papiers (Super+V), sélecteur d'émojis (Super+.).
# Application développée par Matthieu Lamotte.
import os, subprocess, unicodedata
import gi
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib
from gi.repository import Gtk4LayerShell as LS
from . import apps, systeme as S
from .ui import *

def surface(app, ns, couche=LS.Layer.OVERLAY, ancres="tblr", clavier=LS.KeyboardMode.EXCLUSIVE, exclusif=-1):
    w = Gtk.Window(application=app); LS.init_for_window(w); LS.set_namespace(w, ns); LS.set_layer(w, couche)
    for c, e in (("t", LS.Edge.TOP), ("b", LS.Edge.BOTTOM), ("l", LS.Edge.LEFT), ("r", LS.Edge.RIGHT)): LS.set_anchor(w, e, c in ancres)
    if exclusif is not None: LS.set_exclusive_zone(w, exclusif)
    LS.set_keyboard_mode(w, clavier); w.add_css_class("xiii-surface")
    return w

def touches(w, rappel_esc):
    k = Gtk.EventControllerKey()
    k.connect("key-pressed", lambda c, kv, code, st: (rappel_esc(), True)[1] if kv == Gdk.KEY_Escape else False)
    w.add_controller(k)

# ================================================================================ VUE DES TÂCHES
class VueTaches:
    def __init__(self, shell):
        self.shell = shell
        self.w = surface(shell, "xiii-vue"); touches(self.w, self.fermer)
        fond = Gtk.Box(); fond.add_css_class("voile-vue")
        g = Gtk.GestureClick(); g.connect("released", lambda *_: self.fermer()); fond.add_controller(g)
        ov = Gtk.Overlay(); ov.set_child(fond); self.w.set_child(ov)
        self.corps = boite(True, 18, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        ov.add_overlay(self.corps)

    def ouvrir(self):
        vider(self.corps)
        t = label("Fenêtres ouvertes", "panneau-titre", xalign=0.5); self.corps.append(t)
        fen = self.shell.fenetres.liste() if self.shell.fenetres and self.shell.fenetres.ok else []
        g = Gtk.FlowBox(max_children_per_line=4, min_children_per_line=min(4, max(1, len(fen))), selection_mode=Gtk.SelectionMode.NONE,
                        column_spacing=18, row_spacing=18, homogeneous=True, halign=Gtk.Align.CENTER)
        if not fen:
            self.corps.append(label("Aucune fenêtre ouverte", "attenue", xalign=0.5))
        for f in fen:
            a = apps.pour_fenetre(f.app_id)
            c = boite(True, 10, "panneau"); c.set_size_request(260, 170)
            if f.active: c.add_css_class("vue-active")
            h = boite(False, 8)
            h.append(gicon_image(a.get_icon(), 20) if a else ico("app-window", 20))
            h.append(label(a.get_display_name() if a else (f.app_id or "Application"), "gras", hexpand=True, ellipsize=True))
            h.append(bouton(None, "x", "plat", taille=14, tip="Fermer", rappel=lambda f=f: (self.shell.fenetres.fermer(f), GLib.timeout_add(250, lambda: (self.ouvrir(), False)[1]))))
            c.append(h)
            mid = boite(True, 6, valign=Gtk.Align.CENTER, vexpand=True)
            mid.append(gicon_image(a.get_icon(), 56) if a else ico("app-window", 56, "c"))
            mid.append(label(f.titre or "", "attenue", "petit", xalign=0.5, ellipsize=True, largeur=30))
            if f.reduite: mid.append(label("réduite", "accent", "petit", xalign=0.5))
            c.append(mid)
            gc = Gtk.GestureClick(); gc.connect("released", lambda *_a, f=f: (self.fermer(), self.shell.fenetres.activer(f))); c.add_controller(gc)
            g.append(c)
        self.corps.append(g)
        aide = label("Clic : aller à la fenêtre · ✕ : fermer · Super + Ctrl + ← / → : changer de bureau · Échap : quitter", "attenue", "petit", xalign=0.5)
        self.corps.append(aide)
        self.w.present()

    def fermer(self):
        self.w.set_visible(False)

# ================================================================================ DISPOSITIONS (snap layouts)
# régions définies dans rc.xml (labwc) et déclenchées par Super+Alt+F1…F12
REGIONS = [("gauche", (0, 0, 50, 100)), ("droite", (50, 0, 50, 100)), ("haut-gauche", (0, 0, 50, 50)), ("haut-droite", (50, 0, 50, 50)),
           ("bas-gauche", (0, 50, 50, 50)), ("bas-droite", (50, 50, 50, 50)), ("tiers-gauche", (0, 0, 33, 100)), ("tiers-centre", (33, 0, 34, 100)),
           ("tiers-droite", (67, 0, 33, 100)), ("deux-tiers-gauche", (0, 0, 67, 100)), ("deux-tiers-droite", (33, 0, 67, 100)), ("centre", (15, 10, 70, 80))]
DISPOSITIONS = [("Moitiés", ["gauche", "droite"]), ("Quarts", ["haut-gauche", "haut-droite", "bas-gauche", "bas-droite"]),
                ("Tiers", ["tiers-gauche", "tiers-centre", "tiers-droite"]), ("Deux tiers + un tiers", ["deux-tiers-gauche", "tiers-droite"]),
                ("Un tiers + deux tiers", ["tiers-gauche", "deux-tiers-droite"]), ("Centré", ["centre"])]

class Dispositions:
    def __init__(self, shell):
        self.shell = shell
        self.w = surface(shell, "xiii-dispositions", ancres="t", exclusif=None); LS.set_margin(self.w, LS.Edge.TOP, 48)
        touches(self.w, self.fermer)
        p = boite(True, 12, "panneau"); self.w.set_child(p)
        p.append(label("Disposer la fenêtre active", "panneau-titre"))
        g = Gtk.FlowBox(max_children_per_line=3, min_children_per_line=3, selection_mode=Gtk.SelectionMode.NONE, column_spacing=14, row_spacing=14)
        for nom, zones in DISPOSITIONS:
            v = boite(True, 6)
            cadre = Gtk.Fixed(); cadre.set_size_request(150, 90); cadre.add_css_class("dispo-cadre")
            for z in zones:
                x, y, w, h = dict(REGIONS)[z]
                b = Gtk.Button(); b.add_css_class("dispo-zone"); b.set_size_request(int(150 * w / 100) - 4, int(90 * h / 100) - 4)
                b.set_tooltip_text(z.replace("-", " ").capitalize())
                b.connect("clicked", lambda _b, z=z: self.appliquer(z))
                cadre.put(b, int(150 * x / 100) + 2, int(90 * y / 100) + 2)
            v.append(cadre); v.append(label(nom, "petit", xalign=0.5)); g.append(v)
        p.append(g)
        p.append(label("Astuce : Super + ← / → ancre à gauche / à droite, Super + ↑ agrandit.", "attenue", "petit"))

    def ouvrir(self): self.w.present()
    def fermer(self): self.w.set_visible(False)

    def appliquer(self, z):
        self.fermer()
        i = [r[0] for r in REGIONS].index(z) + 1
        GLib.timeout_add(180, lambda: (S.detacher(["wtype", "-M", "logo", "-M", "alt", "-k", "F%d" % i, "-m", "alt", "-m", "logo"]), False)[1])

def regions_rcxml():
    """Fragment rc.xml : régions + raccourcis Super+Alt+F1…F12."""
    r = "\n".join('    <region name="%s" x="%d%%" y="%d%%" width="%d%%" height="%d%%" />' % (n, x, y, w, h) for n, (x, y, w, h) in REGIONS)
    k = "\n".join('    <keybind key="W-A-F%d"><action name="SnapToRegion" region="%s" /></keybind>' % (i + 1, n) for i, (n, _) in enumerate(REGIONS))
    return r, k

# ================================================================================ COINS ACTIFS
ACTIONS_COINS = [("rien", "Rien"), ("bureau", "Afficher le bureau"), ("vue", "Vue des tâches"), ("demarrer", "Menu Démarrer"), ("centre", "Centre de contrôle"),
                 ("volet", "Notifications"), ("widgets", "Widgets"), ("verrouiller", "Verrouiller l'écran")]

class Coins:
    def __init__(self, shell):
        self.shell = shell; self.w = {}
        for c, anc in (("hg", "tl"), ("hd", "tr"), ("bg", "bl"), ("bd", "br")):
            w = surface(shell, "xiii-coin-" + c, ancres=anc, clavier=LS.KeyboardMode.NONE, exclusif=-1)
            b = Gtk.Box(); b.set_size_request(2, 2); w.set_child(b); w.set_default_size(2, 2)
            m = Gtk.EventControllerMotion(); m.connect("enter", lambda *_a, c=c: self.declencher(c)); w.add_controller(m)
            self.w[c] = w
        self.maj()

    def maj(self):
        for c, w in self.w.items():
            w.set_visible(self.shell.cfg.get("coins", {}).get(c, "rien") != "rien")

    def declencher(self, c):
        a = self.shell.cfg.get("coins", {}).get(c, "rien"); sh = self.shell
        if a == "bureau": sh.afficher_bureau()
        elif a == "vue": sh.basculer("vue")
        elif a == "verrouiller": S.detacher("swaylock -f")
        elif a != "rien": sh.basculer(a)

# ================================================================================ PRESSE-PAPIERS
class PressePapiers:
    largeur = 420
    def __init__(self, shell):
        self.shell = shell
        self.widget = boite(True, 10, "panneau"); self.widget.set_size_request(self.largeur, 520)
        h = boite(False, 10); h.append(ico("clipboard-list", 22, "c")); h.append(label("Presse-papiers", "panneau-titre", hexpand=True))
        h.append(bouton("Tout effacer", None, "fantome", rappel=lambda: (S.sh(["cliphist", "wipe"]), self.rafraichir())))
        self.widget.append(h)
        self.liste = boite(True, 4); sc = defilant(self.liste); sc.set_vexpand(True); self.widget.append(sc)
        self.widget.append(label("Super + V · clic : copier · le texte est prêt à coller (Ctrl + V)", "attenue", "petit"))

    def rafraichir(self):
        vider(self.liste)
        if S.DEMO:
            lignes = ["1\tSTUDIO-XIII / 192.168.10.20", "2\tConducteur captation — 20:30", "3\t[[ binary data 230 KiB png 1600x900 ]]", "4\thttps://suite-xiii.netlify.app/"]
        else:
            lignes = S.out(["cliphist", "list"]).splitlines()[:60]
        if not lignes:
            self.liste.append(label("L'historique est vide. Copiez du texte ou une image.", "attenue", "petit", wrap=True)); return
        for l in lignes:
            ident, _, txt = l.partition("\t")
            image = txt.startswith("[[ binary data")
            b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
            bx = boite(False, 10); bx.append(ico("image" if image else "type", 16, "d"))
            bx.append(label("Image copiée" + txt.split("png")[-1].replace("]]", "") if image else txt.strip()[:160], ellipsize=True, largeur=44, hexpand=True))
            b.set_child(bx)
            b.connect("clicked", lambda _b, l=l: (subprocess.run("printf '%s' " + _q(l) + " | cliphist decode | wl-copy", shell=True), self.shell.fermer()))
            self.liste.append(b)

def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"

# ================================================================================ ÉMOJIS
PLAGES = [("Visages", [(0x1F600, 0x1F64F), (0x1F910, 0x1F92F), (0x1F970, 0x1F97A)]), ("Gestes et personnes", [(0x1F44A, 0x1F450), (0x1F466, 0x1F487), (0x1F4AA, 0x1F4AA), (0x1F64B, 0x1F64F), (0x1F918, 0x1F91F)]),
          ("Animaux et nature", [(0x1F400, 0x1F43F), (0x1F330, 0x1F343)]), ("Nourriture", [(0x1F345, 0x1F37F)]), ("Activités", [(0x1F380, 0x1F3CA), (0x26BD, 0x26BE)]),
          ("Voyage", [(0x1F680, 0x1F6C5), (0x1F3E0, 0x1F3F0)]), ("Objets", [(0x1F4A1, 0x1F4FF), (0x1F50A, 0x1F53D), (0x1F3A5, 0x1F3BC)]),
          ("Symboles", [(0x2600, 0x26FF), (0x2700, 0x27BF), (0x1F493, 0x1F49F), (0x2705, 0x2705), (0x274C, 0x274C)])]

def emojis():
    L = []
    for cat, plages in PLAGES:
        for a, b in plages:
            for cp in range(a, b + 1):
                c = chr(cp)
                try: n = unicodedata.name(c).lower()
                except ValueError: continue
                L.append((cat, c, n))
    return L

class Emojis:
    largeur = 440
    def __init__(self, shell):
        self.shell = shell; self.tous = emojis()
        self.widget = boite(True, 10, "panneau"); self.widget.set_size_request(self.largeur, 480)
        h = boite(False, 10); h.append(ico("smile-plus", 22, "c")); h.append(label("Émojis", "panneau-titre", hexpand=True)); self.widget.append(h)
        self.e = Gtk.SearchEntry(placeholder_text="Rechercher (en anglais : heart, camera, fire…)"); self.e.connect("search-changed", lambda *_: self.remplir())
        self.widget.append(self.e)
        self.grille = Gtk.FlowBox(max_children_per_line=10, min_children_per_line=10, selection_mode=Gtk.SelectionMode.NONE, homogeneous=True)
        sc = defilant(self.grille); sc.set_vexpand(True); self.widget.append(sc)

    def rafraichir(self):
        self.e.set_text(""); self.remplir(); GLib.idle_add(lambda: (self.e.grab_focus(), False)[1])

    def remplir(self):
        vider(self.grille); q = self.e.get_text().strip().lower()
        n = 0
        for cat, c, nom in self.tous:
            if q and q not in nom: continue
            b = Gtk.Button(label=c); b.add_css_class("plat"); b.add_css_class("emoji"); b.set_tooltip_text(nom)
            b.connect("clicked", lambda _b, c=c: self.choisir(c)); self.grille.append(b); n += 1
            if n >= 400: break

    def choisir(self, c):
        Gdk.Display.get_default().get_clipboard().set_text(c)
        self.shell.fermer()
        GLib.timeout_add(200, lambda: (S.detacher(["wtype", c]), False)[1])
