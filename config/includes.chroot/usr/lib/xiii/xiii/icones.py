# OS XIII — Icônes XIII : changer le logo de n'importe quelle application.
# Bibliothèque de plusieurs milliers d'icônes libres (Lucide, Tabler, Phosphor) avec recherche, couleur, épaisseur du trait
# et fond (rond, carré, dégradé, goutte), aperçu en grand et dans la barre des tâches ; ou une image de votre choix.
# Le nouveau logo apparaît partout : menu Démarrer, barre des tâches, Dock, Alt+Tab, Launchpad, bureau.
# Application développée par Matthieu Lamotte.
import sys, os
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import apps, theme, config, icones_perso as IP
from .appli import preparer
from .ui import *

NUANCIER = ["#f0b378", "#f5a623", "#ff7a59", "#e57373", "#e05a8a", "#ba68c8", "#9fa8ff", "#4fc3f7", "#3d8bfd", "#26c6b5", "#81c784", "#d4e157", "#ffffff", "#b0bec5", "#1d1b19"]
CSS = """
.ic-grille gridview > child { padding: 6px 2px; border-radius: 10px; }
.ic-grille gridview > child:selected { background: alpha(@accent_bg_color, .25); }
.ic-nom { font-size: 10.5px; }
.ic-apercu { border-radius: 22px; padding: 18px; background: alpha(currentColor, .05); }
.ic-barre-sombre { background: #1c1b1a; border-radius: 12px; padding: 6px 10px; }
.ic-barre-claire { background: #f3f1ee; border-radius: 12px; padding: 6px 10px; }
.ic-perso { font-size: 10px; font-weight: 700; color: @accent_bg_color; }
button.nuance { min-width: 20px; min-height: 20px; padding: 0; border-radius: 50%; border: 2px solid alpha(currentColor, .15); }
"""


class Icones(Gtk.Application):
    def __init__(self, app_id=None):
        super().__init__(application_id="fr.xiii.icones", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.cible = app_id

    def do_activate(self):
        cfg = preparer(CSS); self.cfg = cfg; p = theme.palette(cfg)
        self.couleur = p["accent"]; self.epaisseur = 1.75; self.fond = "aucun"; self.couleur_fond = "#2a2928"
        self.choix = None; self.image = None; self.app = None
        self.win = Gtk.ApplicationWindow(application=self, title="Icônes XIII"); self.win.set_default_size(1220, 800)
        racine = boite(False, 0); self.win.set_child(racine)
        # ---- volet des applis
        nav = boite(True, 8, "volet", "nav", margin_top=4); nav.set_size_request(290, -1)
        nav.append(label("Icônes", "titre-astoria", margin_start=6))
        nav.append(label("Choisissez une appli, puis son nouveau logo", "petit", "attenue", margin_start=6, wrap=True, largeur=30))
        self.q_app = Gtk.SearchEntry(placeholder_text="Rechercher une appli"); self.q_app.connect("search-changed", lambda *_: self.remplir_applis()); nav.append(self.q_app)
        self.l_applis = Gtk.ListBox(); self.l_applis.add_css_class("navigation-sidebar")
        self.l_applis.connect("row-selected", self.appli_choisie)
        sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(self.l_applis); nav.append(sc)
        nav.append(label("Application développée par Matthieu Lamotte", "petit", "attenue", margin_start=6, wrap=True, largeur=30))
        racine.append(nav); racine.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        # ---- partie droite
        d = boite(True, 14, margin_start=22, margin_end=22, margin_top=18, margin_bottom=14, hexpand=True); racine.append(d)
        haut = boite(False, 22); d.append(haut)
        self.grand = Gtk.Image(); self.grand.set_pixel_size(112); ap = boite(False, 0, "ic-apercu"); ap.append(self.grand); haut.append(ap)
        col = boite(True, 8, hexpand=True, valign=Gtk.Align.CENTER); haut.append(col)
        self.l_titre = label("Choisissez une appli", "page-titre"); col.append(self.l_titre)
        self.l_etat = label("", "attenue", wrap=True); col.append(self.l_etat)
        barres = boite(False, 10)
        self.mini = []
        for cls in ("ic-barre-sombre", "ic-barre-claire"):
            b = boite(False, 10, cls)
            for t in (24, 32, 44):
                im = Gtk.Image(); im.set_pixel_size(t); b.append(im); self.mini.append(im)
            barres.append(b)
        col.append(barres)
        act = boite(False, 8); col.append(act)
        self.b_appliquer = bouton("Appliquer", "check", "pilule", rappel=self.appliquer); act.append(self.b_appliquer)
        act.append(bouton("Une image…", "image", "fantome", rappel=self.choisir_image))
        self.b_retablir = bouton("Rétablir le logo d'origine", "rotate-ccw", "fantome", rappel=self.retablir); act.append(self.b_retablir)
        # ---- réglages du dessin
        r = boite(False, 14); d.append(r)
        r.append(label("Couleur", "gras"))
        nu = boite(False, 4)
        for c in NUANCIER:
            b = Gtk.Button(); b.add_css_class("nuance"); b.set_tooltip_text(c)
            pr = Gtk.CssProvider(); pr.load_from_string("button { background: %s; }" % c); b.get_style_context().add_provider(pr, 900)
            b.connect("clicked", lambda _b, c=c: self.regler(couleur=c)); nu.append(b)
        r.append(nu)
        self.b_couleur = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False)); self.b_couleur.connect("notify::rgba", lambda b, _p: self.regler(couleur=hexa(b.get_rgba()))); r.append(self.b_couleur)
        r.append(label("Trait", "gras", margin_start=10))
        self.s_trait = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.75, 3, 0.25); self.s_trait.set_value(self.epaisseur); self.s_trait.set_size_request(130, -1)
        self.s_trait.connect("value-changed", lambda s: self.regler(epaisseur=s.get_value())); r.append(self.s_trait)
        r2 = boite(False, 14); d.append(r2)
        r2.append(label("Fond", "gras"))
        self.d_fond = Gtk.DropDown.new_from_strings([n for _, n in IP.FONDS]); self.d_fond.connect("notify::selected", lambda dd, _p: self.regler(fond=IP.FONDS[dd.get_selected()][0])); r2.append(self.d_fond)
        r2.append(label("Couleur du fond", "gras", margin_start=10))
        self.b_fond = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False)); self.b_fond.connect("notify::rgba", lambda b, _p: self.regler(couleur_fond=hexa(b.get_rgba()))); r2.append(self.b_fond)
        rg = Gdk.RGBA(); rg.parse(self.couleur_fond); self.b_fond.set_rgba(rg)
        rg = Gdk.RGBA(); rg.parse(self.couleur); self.b_couleur.set_rgba(rg)
        # ---- bibliothèque
        b = boite(False, 10); d.append(b)
        self.libs = IP.disponibles()
        noms = ["Toutes les bibliothèques (%d)" % sum(len(IP.liste(x[0])) for x in self.libs)] + ["%s (%d) — licence %s" % (x[1], len(IP.liste(x[0])), x[3]) for x in self.libs]
        self.d_lib = Gtk.DropDown.new_from_strings(noms); self.d_lib.connect("notify::selected", lambda *_: self.filtrer()); b.append(self.d_lib)
        self.q = Gtk.SearchEntry(placeholder_text="Rechercher une icône, en anglais : camera, film, music, folder…", hexpand=True)
        self.q.connect("search-changed", lambda *_: self.filtrer()); b.append(self.q)
        self.l_n = label("", "petit", "attenue"); b.append(self.l_n)
        self.modele = Gtk.StringList()
        self.sel = Gtk.SingleSelection(model=self.modele, autoselect=False, can_unselect=True)
        self.sel.connect("notify::selected-item", self.icone_choisie)
        fab = Gtk.SignalListItemFactory(); fab.connect("setup", self._setup); fab.connect("bind", self._bind)
        self.grille = Gtk.GridView(model=self.sel, factory=fab, max_columns=12, min_columns=5, single_click_activate=False)
        sc2 = Gtk.ScrolledWindow(vexpand=True); sc2.set_child(self.grille); sc2.add_css_class("ic-grille"); d.append(sc2)
        self.remplir_applis(); self.filtrer()
        self.win.present()

    # ------------------------------------------------------------ applis
    def remplir_applis(self):
        vider(self.l_applis)
        q = sans_accents(self.q_app.get_text().strip())
        self._lignes = []
        for a in apps.toutes():
            if q and q not in sans_accents(a.get_display_name()): continue
            row = Gtk.ListBoxRow(); row._app = a
            bx = boite(False, 10, margin_top=4, margin_bottom=4, margin_start=6, margin_end=6)
            bx.append(gicon_image(a.get_icon(), 24)); bx.append(label(a.get_display_name(), ellipsize=True, hexpand=True, largeur=22))
            if IP.personnalisee(a): bx.append(label("PERSO", "ic-perso"))
            row.set_child(bx); self.l_applis.append(row); self._lignes.append(row)
            if self.cible and a.get_id() == self.cible:
                GLib.idle_add(lambda r=row: (self.l_applis.select_row(r), False)[1])

    def appli_choisie(self, lb, row):
        if row is None: return
        self.app = Gio.DesktopAppInfo.new(row._app.get_id()) or row._app
        self.l_titre.set_text(self.app.get_display_name())
        self.b_retablir.set_sensitive(IP.personnalisee(self.app))
        self.l_etat.set_text("Logo personnalisé" if IP.personnalisee(self.app) else "Logo d'origine")
        self.maj_apercu()

    # ------------------------------------------------------------ bibliothèque
    def filtrer(self):
        i = self.d_lib.get_selected()
        L = IP.toutes() if i == 0 else [(self.libs[i - 1][0], n) for n in IP.liste(self.libs[i - 1][0])]
        q = self.q.get_text().strip().lower().replace(" ", "-")
        if q: L = [x for x in L if q in x[1]]
        self.modele.splice(0, self.modele.get_n_items(), ["%s/%s" % x for x in L])
        self.l_n.set_text("%d icônes" % len(L))

    def _setup(self, fab, item):
        v = boite(True, 4); im = Gtk.Image(); im.set_pixel_size(30); v.append(im)
        l = label("", "ic-nom", xalign=0.5, ellipsize=True, largeur=11); v.append(l); item.set_child(v); item._im = im; item._l = l

    def _bind(self, fab, item):
        cle, nom = item.get_item().get_string().split("/", 1)
        item._im.set_from_paintable(IP.apercu(cle, nom, theme.palette(self.cfg)["texte"], 30)); item._l.set_text(nom.replace("-", " "))
        item.get_child().set_tooltip_text("%s · %s" % (nom, IP.PAR_CLE[cle][1]))

    def icone_choisie(self, *_):
        it = self.sel.get_selected_item()
        if it is None: return
        self.choix = tuple(it.get_string().split("/", 1)); self.image = None
        self.maj_apercu()

    # ------------------------------------------------------------ dessin et aperçu
    def regler(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)
        self.maj_apercu()

    def svg(self):
        return IP.dessiner(self.choix[0], self.choix[1], self.couleur, self.epaisseur, self.fond, self.couleur_fond) if self.choix else None

    def maj_apercu(self):
        s = self.svg() if not self.image else None
        for im, t in [(self.grand, 112)] + [(m, m.get_pixel_size()) for m in self.mini]:
            if s: im.set_from_paintable(IP.texture(s, t))
            elif self.image: im.set_from_file(self.image)
            elif self.app: im.set_from_gicon(self.app.get_icon())
            else: im.set_from_icon_name("application-x-executable")
            im.set_pixel_size(t)
        self.b_appliquer.set_sensitive(bool(self.app and (s or self.image)))
        self.s_trait.set_sensitive(bool(self.choix and IP.PAR_CLE[self.choix[0]][4] == "trait"))

    def choisir_image(self):
        dlg = Gtk.FileDialog(title="Choisir une image pour le logo")
        f = Gtk.FileFilter(); f.set_name("Images"); [f.add_mime_type(m) for m in ("image/png", "image/svg+xml", "image/jpeg", "image/webp")]
        ls = Gio.ListStore.new(Gtk.FileFilter); ls.append(f); dlg.set_filters(ls)
        def fini(d, res):
            try: g = d.open_finish(res)
            except GLib.Error: return
            if g: self.image = g.get_path(); self.choix = None; self.maj_apercu()
        dlg.open(self.win, None, fini)

    def appliquer(self):
        if not self.app: return
        self.app = Gio.DesktopAppInfo.new(self.app.get_id()) or self.app; self.cible = self.app.get_id()
        try:
            IP.appliquer(self.app, svg=self.svg() if not self.image else None, image=self.image)
        except Exception as e:
            self.l_etat.set_text("Impossible : %s" % e); return
        self.l_etat.set_text("Nouveau logo appliqué : menu Démarrer, barre des tâches, Alt+Tab et bureau suivent tout de suite.")
        self.b_retablir.set_sensitive(True)
        GLib.timeout_add(700, lambda: (self.remplir_applis(), False)[1])

    def retablir(self):
        if self.app: self.app = Gio.DesktopAppInfo.new(self.app.get_id()) or self.app; self.cible = self.app.get_id()
        if self.app and IP.retablir(self.app):
            self.l_etat.set_text("Logo d'origine rétabli."); self.b_retablir.set_sensitive(False); self.choix = None; self.image = None
            GLib.timeout_add(700, lambda: (self.remplir_applis(), False)[1])


def hexa(rg):
    return "#%02x%02x%02x" % (int(rg.red * 255), int(rg.green * 255), int(rg.blue * 255))


def main():
    a = None
    if "--app" in sys.argv:
        i = sys.argv.index("--app")
        if i + 1 < len(sys.argv): a = sys.argv[i + 1]
    if "--test" in sys.argv:           # vérifications : nombre d'icônes par bibliothèque
        print(" · ".join("%s %d" % (b[1], len(IP.liste(b[0]))) for b in IP.disponibles()), "=", len(IP.toutes()), "icônes")
        return
    sys.exit(Icones(a).run(sys.argv[:1]))
