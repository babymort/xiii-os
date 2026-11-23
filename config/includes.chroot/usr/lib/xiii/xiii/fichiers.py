# OS XIII — Fichiers XIII : l'explorateur aux couleurs de la Suite XIII, onglets sur le côté gauche, trois façons de voir :
#   • Windows : liste détaillée (nom, date, type, taille), tri par colonne
#   • Mac : colonnes en cascade (comme le Finder), aperçu du fichier dans la dernière colonne
#   • Arbre : arbre généalogique des dossiers, qu'on déplie branche par branche
# Cloud (~/Cloud) et NAS (~/Réseau) montés par Lecteurs réseau, clés et disques, corbeille.
# Application développée par Matthieu Lamotte.
import os, sys, re, shutil, threading, time, datetime, subprocess, json
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GObject, Pango
from . import config, systeme as S, apps, medias, copie, etiquettes as ET, corbeille as CB
from .ui import *
from .appli import preparer

ATTR = "standard::*,time::modified,thumbnail::path"
VUES = [("windows", "Windows", "list"), ("galerie", "Galerie", "layout-grid"), ("mac", "Mac", "columns-3"), ("arbre", "Arbre", "network")]

def taille_txt(info):
    return "" if info.get_file_type() == Gio.FileType.DIRECTORY else S.humain(info.get_size())

def date_txt(info):
    t = info.get_modification_date_time()
    if not t: return ""
    d = datetime.datetime.fromtimestamp(t.to_unix()); n = datetime.datetime.now()
    return d.strftime("Aujourd'hui %H:%M") if d.date() == n.date() else d.strftime("%d/%m/%Y %H:%M")

def type_txt(info):
    if info.get_file_type() == Gio.FileType.DIRECTORY: return "Dossier"
    ct = info.get_content_type() or ""
    return Gio.content_type_get_description(ct) if ct else ""

def fichier_de(info): return info.get_attribute_object("standard::file")

def icone_info(info, taille=18):
    g = info.get_icon()
    im = Gtk.Image.new_from_gicon(g) if g else Gtk.Image.new_from_icon_name("text-x-generic")
    im.set_pixel_size(taille); return im


def deroulant_simple(options, courant, rappel):
    d = Gtk.DropDown(model=Gtk.StringList.new([n for _, n in options]))
    d.set_selected(next((i for i, (k, _) in enumerate(options) if k == courant), 0))
    d.connect("notify::selected", lambda w, _p: rappel(options[w.get_selected()][0])); return d

def confirmer_f(parent, titre, sous, action, rappel):
    d = Gtk.Window(transient_for=parent, modal=True, title=titre, default_width=420)
    v = boite(True, 10, margin_top=18, margin_bottom=18, margin_start=20, margin_end=20)
    v.append(label(titre, "page-titre", wrap=True)); v.append(label(sous, "attenue", wrap=True))
    r = boite(False, 8, halign=Gtk.Align.END); r.append(bouton("Annuler", None, "fantome", rappel=d.close)); r.append(bouton(action, None, "pilule", rappel=lambda: (d.close(), rappel()))); v.append(r)
    d.set_child(v); d.present()

def pastille_couleur(e, taille=10):
    b = Gtk.Box(valign=Gtk.Align.CENTER); b.add_css_class("etiquette"); b.set_size_request(taille, taille); b.set_tooltip_text("Étiquette " + ET.NOMS.get(e, e))
    pr = Gtk.CssProvider(); pr.load_from_string("box { background: %s; }" % ET.HEX.get(e, "#888")); b.get_style_context().add_provider(pr, 900)
    return b

class Fichiers(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.fichiers", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.histo = []; self.futur = []; self.presse = None; self.couper = False

    def do_command_line(self, cl):
        a = [x for x in cl.get_arguments()[1:] if not x.startswith("--")]
        depart = os.path.expanduser("~")
        pj = config.charger().get("projet_actif")
        if pj and config.charger().get("fichiers_depart_projet", True) and os.path.isdir(os.path.expanduser("~/XIII/" + pj)):
            depart = os.path.expanduser("~/XIII/" + pj)       # le projet choisi en haut à gauche est le point de départ
        A0 = cl.get_arguments()
        a = [x for i, x in enumerate(A0[1:], 1) if not x.startswith("--") and A0[i - 1] not in ("--chercher", "--type", "--jours")]
        d = Gio.File.new_for_commandline_arg_and_cwd(a[0], cl.get_cwd() or "/").get_path() if a else depart
        if d and os.path.isfile(d): d = os.path.dirname(d)
        self.activer(); self.aller(d or os.path.expanduser("~"))
        if "--test-colonnes" in cl.get_arguments(): GLib.timeout_add(1500, self.test_colonnes)
        if "--infos" in cl.get_arguments() and a: GLib.timeout_add(800, lambda: (self.infos_fichier(os.path.abspath(a[0])), False)[1])
        if "--corbeille" in cl.get_arguments(): GLib.timeout_add(500, lambda: (self.vue_corbeille(), False)[1])
        A = cl.get_arguments()
        if "--chercher" in A:       # commandes vocales : « cherche les vidéos de cette semaine »
            g = lambda k: A[A.index(k) + 1] if k in A and A.index(k) + 1 < len(A) else None
            GLib.timeout_add(500, lambda: (self.recherche_filtree(g("--chercher") or "", g("--type"), int(g("--jours") or 0)), False)[1])
        return 0

    def test_colonnes(self):
        """Test automatique (vérification ZZ) de la vue Mac : un clic remplace les colonnes à droite au lieu d'en ajouter."""
        base = os.path.expanduser("~/xiii-test-colonnes")
        for p in ("a/b/c", "z/y"): os.makedirs(os.path.join(base, p), exist_ok=True)
        open(os.path.join(base, "f.txt"), "w").write("test\n")
        self.changer_vue("mac"); self.aller(base)
        def cols(): 
            n, c = [], self.mac_boite.get_first_child()
            while c:
                if not c.has_css_class("poignee-colonne"): n.append(c)
                c = c.get_next_sibling()
            return n
        def liste(col): return col.get_child().get_child() if isinstance(col.get_child(), Gtk.Viewport) else col.get_child()
        def choisir(col, nom):
            lb = liste(col); r = lb.get_first_child()
            while r:
                if getattr(r, "_chemin", "").endswith("/" + nom): lb.select_row(r); return True
                r = r.get_next_sibling()
            return False
        res = []
        def etape(txt, attendu):
            n = len(cols()); res.append("%s %s : %d colonne(s), attendu %d" % ("OK      " if n == attendu else "ÉCHEC   ", txt, n, attendu)); return n
        n0 = etape("ouverture", len(cols()))
        c0 = cols()[-1]
        choisir(c0, "a"); etape("clic sur a", n0 + 1)
        choisir(cols()[-1], "b"); etape("clic sur a/b", n0 + 2)
        choisir(c0, "z"); etape("retour, clic sur z (remplace a et b)", n0 + 1)
        choisir(c0, "z"); choisir(c0, "f.txt"); etape("clic sur un fichier (aperçu)", n0 + 1)
        self.changer_vue("arbre"); res.append("OK       vue Arbre ouverte"); self.changer_vue("windows"); res.append("OK       vue Windows ouverte")
        print("\n".join("COLONNES " + r for r in res), flush=True)
        self.quit(); return False

    # =================================================================== fenêtre
    def activer(self):
        if getattr(self, "win", None): self.win.present(); return
        self.cfg = preparer("""
            progressbar.indic-barre > trough { min-height: 5px; border-radius: 3px; background-color: alpha(currentColor, .15); border: none; }
            progressbar.indic-barre > trough > progress { min-height: 5px; border-radius: 3px; background-color: @accent_bg_color; background-image: none; border: none; box-shadow: none; }
            progressbar.indic-barre.plein > trough > progress { background-color: #e98080; }
            .barre-chemin button { padding: 2px 8px; border-radius: 8px; } .barre-chemin button:last-child label { font-weight: 700; }
            .vue-choix button { padding: 4px 10px; border-radius: 999px; } .vue-choix button.actif { background: alpha(@accent_bg_color, .22); }
            columnview { background: transparent; } columnview row:selected { background: alpha(@accent_bg_color, .22); }
            .colonne-mac { border-right: 1px solid alpha(currentColor, .1); min-width: 230px; }
            .colonne-mac row:selected { background: alpha(@accent_bg_color, .25); }
            .noeud { background: alpha(currentColor, .05); border: 1px solid alpha(currentColor, .14); border-radius: 12px; padding: 8px 12px; min-width: 120px; }
            .noeud:hover { border-color: @accent_bg_color; } .noeud.ouvert { background: alpha(@accent_bg_color, .16); border-color: @accent_bg_color; }
            .noeud.racine { background: alpha(@accent_bg_color, .28); }
            .lien-v { min-width: 2px; min-height: 18px; background: alpha(@accent_bg_color, .55); }
            .enfants { border-top: 2px solid alpha(@accent_bg_color, .55); padding-top: 0; }
            .feuille { font-size: 11px; opacity: .8; padding: 2px 6px; }
            .onglet-fichiers { padding: 3px 8px; border-radius: 10px 10px 0 0; background: alpha(currentColor, .04); }
            .onglet-fichiers.actif { background: alpha(@accent_bg_color, .22); }
            .carte-galerie { padding: 6px; border-radius: 10px; }
            gridview > child:selected { background: alpha(@accent_bg_color, .22); border-radius: 10px; }
            .etiquette { min-width: 10px; min-height: 10px; border-radius: 999px; }
            .poignee-colonne { background: alpha(currentColor, .04); } .poignee-colonne:hover { background: alpha(@accent_bg_color, .5); }""")
        self.win = Gtk.ApplicationWindow(application=self, title="Fichiers"); self.win.set_default_size(1200, 760)
        racine = boite(False, 0)
        # ---- volet gauche (onglets, comme la Suite XIII)
        self.volet = boite(True, 2, "volet", "nav"); self.volet.set_size_request(220, -1)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); sc.set_child(self.volet); sc.set_hexpand(False)
        racine.append(sc); racine.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        # ---- droite
        d = boite(True, 0, hexpand=True)
        self.barre_onglets = boite(False, 4, "barre-onglets", margin_start=10, margin_end=10, margin_top=6); self.barre_onglets.set_visible(False); d.append(self.barre_onglets)
        self.onglets = [{"dossier": None, "histo": [], "futur": []}]; self.i_onglet = 0
        h = boite(False, 6, margin_start=10, margin_end=10, margin_top=8, margin_bottom=8)
        self.b_prec = bouton(None, "arrow-left", "plat", tip="Précédent (Alt+←)", rappel=self.precedent); h.append(self.b_prec)
        self.b_suiv = bouton(None, "arrow-right", "plat", tip="Suivant (Alt+→)", rappel=self.suivant); h.append(self.b_suiv)
        h.append(bouton(None, "arrow-up", "plat", tip="Dossier parent (Alt+↑)", rappel=self.parent))
        self.chemin = boite(False, 0, "barre-chemin", hexpand=True)
        self.saisie = Gtk.Entry(hexpand=True); self.saisie.set_visible(False)
        self.saisie.connect("activate", lambda e: (self.aller(os.path.expanduser(e.get_text())), self.fin_saisie()))
        h.append(self.chemin); h.append(self.saisie)
        self.recherche = Gtk.SearchEntry(placeholder_text="Rechercher dans ce dossier"); self.recherche.set_size_request(190, -1)
        self.recherche.connect("activate", lambda *_: self.chercher()); self.recherche.connect("stop-search", lambda *_: self.recharger()); h.append(self.recherche)
        self.b_contenu = Gtk.ToggleButton(); self.b_contenu.set_child(ico("file-search", 16)); self.b_contenu.add_css_class("plat")
        self.b_contenu.set_tooltip_text("Chercher aussi DANS les fichiers (textes, PDF, documents)"); h.append(self.b_contenu)
        vc = boite(False, 2, "vue-choix"); self.b_vues = {}
        for k, n, ic in VUES:
            b = Gtk.Button(); b.set_child(ico(ic, 15, "c")); b.set_tooltip_text("Vue " + n)
            b.connect("clicked", lambda _b, k=k: self.changer_vue(k)); vc.append(b); self.b_vues[k] = b
        h.append(vc)
        h.append(bouton(None, "folder-plus", "plat", tip="Nouveau dossier (Ctrl+Maj+N)", rappel=self.nouveau_dossier))
        h.append(bouton(None, "plus", "plat", tip="Nouvel onglet (Ctrl+T)", rappel=lambda: self.nouvel_onglet(self.dossier)))
        h.append(bouton(None, "columns-2", "plat", tip="Double volet (F3)", rappel=self.basculer_double))
        h.append(bouton(None, "ellipsis-vertical", "plat", tip="Plus", rappel=None)); h.get_last_child().connect("clicked", lambda b: popover_menu(b, self.menu_plus()))
        d.append(h); d.append(Gtk.Separator())
        self.pile = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE); d.append(self.pile)
        self.zone_copies = boite(True, 4, margin_start=10, margin_end=10); self.zone_copies.set_visible(False); d.append(self.zone_copies)
        self.file = copie.File(lambda t=None: GLib.idle_add(self.maj_copies, t)); self._src_copies = 0
        self.etat = label("", "petit", "attenue", margin_start=12, margin_bottom=6, margin_top=4); d.append(self.etat)
        racine.append(d)
        self.double = None; self.racine_droite = racine
        self.win.set_child(racine)
        self.construire_windows(); self.construire_galerie(); self.construire_mac(); self.construire_arbre()
        self.cachés = False; self.vue = config.charger().get("fichiers_vue", "windows")
        self.raccourcis(); self.remplir_volet()
        S.en_fond(CB.nettoyer, None, self.cfg.get("corbeille_jours", 30))
        Gio.VolumeMonitor.get().connect("mount-added", lambda *_: self.remplir_volet()); Gio.VolumeMonitor.get().connect("mount-removed", lambda *_: self.remplir_volet())
        self.win.present()

    # =================================================================== volet
    def remplir_volet(self):
        vider(self.volet)
        self.volet.append(label("Fichiers", "titre-astoria", margin_start=8, margin_bottom=8))
        def onglet(ic, nom, chemin, sec=None):
            if not chemin or not os.path.exists(chemin): return
            b = Gtk.Button(); b.add_css_class("onglet"); bx = boite(False, 10); bx.append(ico(ic, 16, "c")); bx.append(label(nom, ellipsize=True, hexpand=True)); b.set_child(bx)
            b.set_tooltip_text(chemin); b._chemin = chemin; b.connect("clicked", lambda *_: self.aller(chemin))
            dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            dt.connect("drop", lambda t, v, x, y, c=chemin: (self.coller_vers([f.get_path() for f in v.get_files()], c, deplacer=False), True)[1]); b.add_controller(dt)
            self.volet.append(b)
        sp = lambda k: GLib.get_user_special_dir(k)
        maison = os.path.expanduser("~")
        onglet("house", "Dossier personnel", maison)
        pj = self.cfg.get("projet_actif")
        if pj: onglet("folder-kanban", "Projet " + pj, os.path.join(maison, "XIII", pj))
        for k, ic, n in ((GLib.UserDirectory.DIRECTORY_DESKTOP, "monitor", "Bureau"), (GLib.UserDirectory.DIRECTORY_DOCUMENTS, "file-text", "Documents"),
                         (GLib.UserDirectory.DIRECTORY_DOWNLOAD, "download", "Téléchargements"), (GLib.UserDirectory.DIRECTORY_PICTURES, "image", "Images"),
                         (GLib.UserDirectory.DIRECTORY_VIDEOS, "film", "Vidéos"), (GLib.UserDirectory.DIRECTORY_MUSIC, "music", "Musique")):
            onglet(ic, n, sp(k))
        onglet("gamepad-2", "Jeux", os.path.join(maison, "Jeux"))
        self.volet.append(label("Dossiers intelligents", "section", margin_start=8, margin_top=10))
        for ic, n, k in self.INTELLIGENTS:
            b = Gtk.Button(); b.add_css_class("onglet"); bx = boite(False, 10); bx.append(ico(ic, 16, "c")); bx.append(label(n, ellipsize=True, hexpand=True)); b.set_child(bx)
            b.connect("clicked", lambda _b, k=k: self.intelligent(k)); self.volet.append(b)
        et = boite(False, 6, margin_start=12, margin_top=6)
        for k, n, hx in ET.COULEURS:
            b = Gtk.Button(); b.add_css_class("plat"); b.set_child(pastille_couleur(k, 14)); b.set_tooltip_text("Fichiers étiquetés « %s »" % n)
            b.connect("clicked", lambda _b, k=k: self.par_etiquette(k)); et.append(b)
        self.volet.append(et)
        nuage = [os.path.join(maison, "Cloud", x) for x in sorted(os.listdir(os.path.join(maison, "Cloud")))] if os.path.isdir(os.path.join(maison, "Cloud")) else []
        reseau = [os.path.join(maison, "Réseau", x) for x in sorted(os.listdir(os.path.join(maison, "Réseau")))] if os.path.isdir(os.path.join(maison, "Réseau")) else []
        self.volet.append(label("Cloud et réseau", "section", margin_start=8, margin_top=10))
        for p in nuage: onglet("cloud", os.path.basename(p), p)
        for p in reseau: onglet("hard-drive", os.path.basename(p), p)
        b = bouton("Connecter un NAS / cloud…", "plus", "plat", "petit", taille=14, rappel=lambda: S.detacher("xiii-lecteurs")); self.volet.append(b)
        mounts = [m for m in Gio.VolumeMonitor.get().get_mounts() if m.get_root() and m.get_root().get_path() and m.get_root().get_path().startswith(("/media", "/run/media", "/mnt"))]
        if mounts:
            self.volet.append(label("Appareils", "section", margin_start=8, margin_top=10))
            for m in mounts:
                p = m.get_root().get_path(); onglet("hard-drive" if not m.can_eject() else "usb", m.get_name(), p)
        self.volet.append(label("", margin_top=6))
        onglet("hard-drive", "Ordinateur", "/")
        b = Gtk.Button(); b.add_css_class("onglet"); bx = boite(False, 10); bx.append(ico("trash-2", 16, "c")); bx.append(label("Corbeille", hexpand=True)); b.set_child(bx)
        b.connect("clicked", lambda *_: self.vue_corbeille()); self.volet.append(b)
        # espace restant sur chaque disque, en bas du volet
        disques = [("Ordinateur", "/")] + [(m.get_name(), m.get_root().get_path()) for m in mounts]
        if os.path.ismount(os.path.expanduser("~")): disques.insert(1, ("Dossier personnel", os.path.expanduser("~")))
        bas = boite(True, 6, vexpand=True, valign=Gtk.Align.END, margin_top=14, margin_start=8, margin_end=8)
        bas.append(label("Espace disque", "section"))
        for nom, chemin in disques:
            try: u = shutil.disk_usage(chemin)
            except OSError: continue
            r = boite(True, 2)
            h = boite(False, 6); h.append(label(nom, "petit", "gras", hexpand=True, ellipsize=True)); h.append(label("%s libres" % S.humain(u.free), "petit", "attenue")); r.append(h)
            pb = Gtk.ProgressBar(fraction=u.used / u.total if u.total else 0); pb.add_css_class("indic-barre")
            if u.total and u.free / u.total < .1: pb.add_css_class("plein")
            pb.set_tooltip_text("%s utilisés sur %s" % (S.humain(u.used), S.humain(u.total))); r.append(pb); bas.append(r)
        self.volet.append(bas)
        self.marquer_volet()

    def marquer_volet(self):
        c = self.volet.get_first_child()
        while c:
            if hasattr(c, "_chemin"): (c.add_css_class if getattr(self, "dossier", None) == c._chemin else c.remove_css_class)("actif")
            c = c.get_next_sibling()

    # =================================================================== navigation
    def aller(self, d, histo=True):
        d = os.path.abspath(os.path.expanduser(d))
        if not os.path.isdir(d): return
        if histo and getattr(self, "dossier", None) and self.dossier != d: self.histo.append(self.dossier); self.futur.clear()
        self.dossier = d; self.win.set_title(os.path.basename(d) or "/")
        if hasattr(self, "onglets"): self.onglets[self.i_onglet]["dossier"] = d; self.maj_onglets()
        if getattr(self, "vue_avant", None): self.vue = self.vue_avant; self.vue_avant = None
        self.b_prec.set_sensitive(bool(self.histo)); self.b_suiv.set_sensitive(bool(self.futur))
        self.barre_chemin(); self.marquer_volet(); self.recharger()

    # =================================================================== onglets
    def maj_onglets(self):
        vider(self.barre_onglets); self.barre_onglets.set_visible(len(self.onglets) > 1)
        for i, o in enumerate(self.onglets):
            b = Gtk.Button(); b.add_css_class("onglet-fichiers")
            if i == self.i_onglet: b.add_css_class("actif")
            bx = boite(False, 6); bx.append(ico("folder", 14, "c")); bx.append(label(os.path.basename(o["dossier"] or "") or "/", "petit", ellipsize=True, largeur=18))
            x = bouton(None, "x", "plat", taille=12, role="d", tip="Fermer l'onglet (Ctrl+W)", rappel=lambda i=i: self.fermer_onglet(i)); bx.append(x)
            b.set_child(bx); b.connect("clicked", lambda _b, i=i: self.changer_onglet(i)); self.barre_onglets.append(b)
        self.barre_onglets.append(bouton(None, "plus", "plat", taille=14, tip="Nouvel onglet (Ctrl+T)", rappel=lambda: self.nouvel_onglet(self.dossier)))

    def nouvel_onglet(self, d):
        self.onglets[self.i_onglet].update(histo=list(self.histo), futur=list(self.futur))
        self.onglets.append({"dossier": d, "histo": [], "futur": []}); self.changer_onglet(len(self.onglets) - 1)

    def changer_onglet(self, i):
        if not 0 <= i < len(self.onglets): return
        self.onglets[self.i_onglet].update(histo=list(self.histo), futur=list(self.futur))
        self.i_onglet = i; o = self.onglets[i]; self.histo, self.futur = list(o["histo"]), list(o["futur"])
        self.aller(o["dossier"] or os.path.expanduser("~"), histo=False)

    def fermer_onglet(self, i):
        if len(self.onglets) <= 1: return
        self.onglets.pop(i)
        if self.i_onglet >= len(self.onglets) or i < self.i_onglet: self.i_onglet = max(0, self.i_onglet - 1)
        o = self.onglets[self.i_onglet]; self.histo, self.futur = list(o["histo"]), list(o["futur"]); self.aller(o["dossier"], histo=False)

    # =================================================================== double volet (copier / déplacer d'un dossier à l'autre)
    def basculer_double(self):
        if self.double:
            self.racine_droite.remove(self.double["sep"]); self.racine_droite.remove(self.double["w"]); self.double = None; return
        st = {"dossier": self.dossier}
        lst = Gtk.DirectoryList.new(ATTR, Gio.File.new_for_path(self.dossier)); lst.set_monitored(True)
        filt = Gtk.FilterListModel.new(lst, Gtk.CustomFilter.new(lambda i: self.cachés or not i.get_is_hidden()))
        tri = Gtk.SortListModel.new(filt, Gtk.CustomSorter.new(lambda a, b, _d=None: ((a.get_file_type() != Gio.FileType.DIRECTORY) - (b.get_file_type() != Gio.FileType.DIRECTORY)) or
                                                                 (a.get_display_name().lower() > b.get_display_name().lower()) - (a.get_display_name().lower() < b.get_display_name().lower())))
        sel = Gtk.MultiSelection.new(tri)
        fac = Gtk.SignalListItemFactory()
        fac.connect("setup", lambda _f, it: it.set_child(boite(False, 8, margin_start=6, margin_top=2, margin_bottom=2)))
        def bind(_f, it):
            bx = it.get_child(); vider(bx); i = it.get_item()
            bx.append(icone_info(i)); bx.append(label(i.get_display_name(), ellipsize=True, hexpand=True)); bx.append(label(taille_txt(i), "petit", "attenue"))
        fac.connect("bind", bind)
        lv = Gtk.ListView(model=sel, factory=fac)
        titre = label("", "gras", ellipsize=True, hexpand=True)
        def aller(d):
            st["dossier"] = d; lst.set_file(Gio.File.new_for_path(d)); titre.set_text(d.replace(os.path.expanduser("~"), "~"))
        lv.connect("activate", lambda _lv, pos: (lambda p: aller(p) if os.path.isdir(p) else self.ouvrir(p))(fichier_de(tri.get_item(pos)).get_path()))
        def choix():
            r = sel.get_selection(); return [fichier_de(tri.get_item(r.get_nth(k))).get_path() for k in range(r.get_size())]
        ds = Gtk.DragSource(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        ds.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([Gio.File.new_for_path(p) for p in choix()])) if choix() else None); lv.add_controller(ds)
        dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        dt.connect("drop", lambda t, v, x, y: (self.coller_vers([f.get_path() for f in v.get_files()], st["dossier"]), True)[1]); lv.add_controller(dt)
        w = boite(True, 6, margin_start=8, margin_end=8, margin_top=8, hexpand=True); w.set_size_request(380, -1)
        h = boite(False, 6)
        h.append(bouton(None, "arrow-up", "plat", tip="Dossier parent", rappel=lambda: aller(os.path.dirname(st["dossier"]) or "/"))); h.append(titre)
        h.append(bouton(None, "x", "plat", tip="Fermer le double volet (F3)", rappel=self.basculer_double)); w.append(h)
        a = boite(False, 6)
        a.append(bouton("Copier ici", "copy", "fantome", taille=13, tip="Copier la sélection de gauche dans ce dossier", rappel=lambda: self.coller_vers(self.selection(), st["dossier"])))
        a.append(bouton("Déplacer ici", "move", "fantome", taille=13, rappel=lambda: self.coller_vers(self.selection(), st["dossier"], deplacer=True)))
        a.append(bouton("Copier à gauche", "arrow-left", "fantome", taille=13, rappel=lambda: self.coller_vers(choix(), self.dossier)))
        w.append(a)
        sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(lv); w.append(sc)
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.racine_droite.append(sep); self.racine_droite.append(w); self.double = {"w": w, "sep": sep, "aller": aller}
        aller(self.dossier)

    def precedent(self):
        if self.histo: self.futur.append(self.dossier); self.aller(self.histo.pop(), histo=False)
    def suivant(self):
        if self.futur: self.histo.append(self.dossier); self.aller(self.futur.pop(), histo=False)
    def parent(self):
        if self.dossier != "/": self.aller(os.path.dirname(self.dossier))

    def barre_chemin(self):
        vider(self.chemin); maison = os.path.expanduser("~"); p = self.dossier
        parts = []
        if p.startswith(maison): parts.append(("Dossier personnel", maison)); reste = p[len(maison):]
        else: parts.append(("Ordinateur", "/")); reste = p
        acc = parts[0][1]
        for x in [y for y in reste.split("/") if y]:
            acc = os.path.join(acc, x); parts.append((x, acc))
        caches = []
        if len(parts) > 4: caches = parts[1:-3]; parts = parts[:1] + [("…", None)] + parts[-3:]     # chemin long : les dossiers du milieu dans « … »
        for k, (n, c) in enumerate(parts):
            if k: self.chemin.append(label("›", "attenue"))
            b = Gtk.Button(); b.add_css_class("plat"); b.set_child(label(n, ellipsize=True, largeur=22 if k == len(parts) - 1 else 14))
            if c is None: b.connect("clicked", lambda bb: popover_menu(bb, [("folder", nn, (lambda cc=cc: self.aller(cc))) for nn, cc in caches]))
            else: b.connect("clicked", lambda _b, c=c: self.aller(c))
            b.set_tooltip_text(c or " / ".join(nn for nn, _ in caches)); self.chemin.append(b)
        g = Gtk.GestureClick(button=1); g.connect("pressed", lambda g_, n, x, y: self.saisir_chemin() if n == 2 else None); self.chemin.add_controller(g)

    def saisir_chemin(self):
        self.chemin.set_visible(False); self.saisie.set_visible(True); self.saisie.set_text(self.dossier); self.saisie.grab_focus()
    def fin_saisie(self):
        self.saisie.set_visible(False); self.chemin.set_visible(True)

    def changer_vue(self, k):
        self.vue = k; config.modifier(_histo=False, fichiers_vue=k); self.recharger()

    def recharger(self):
        for k, b in self.b_vues.items(): (b.add_css_class if k == self.vue else b.remove_css_class)("actif")
        self.pile.set_visible_child_name(self.vue)
        if self.vue in ("windows", "galerie"):
            self.tri, self.mod_windows = self.tri_base, self.sel_base; self.cv.set_model(self.sel_base)
            self.liste_dir.set_file(Gio.File.new_for_path(self.dossier))
        elif self.vue == "mac": self.remplir_mac()
        else: self.remplir_arbre()
        try:
            n = len([x for x in os.listdir(self.dossier) if self.cachés or not x.startswith(".")])
            self.etat.set_text("%d élément(s) · %s libres" % (n, S.humain(shutil.disk_usage(self.dossier).free)))
        except OSError as e:
            self.etat.set_text(str(e))

    # =================================================================== vue Windows (détails)
    def construire_windows(self):
        self.liste_dir = Gtk.DirectoryList.new(ATTR, None); self.liste_dir.set_monitored(True)
        self.filtre = Gtk.CustomFilter.new(lambda info: self.cachés or not info.get_is_hidden())
        filtree = Gtk.FilterListModel.new(self.liste_dir, self.filtre)
        self.cv = Gtk.ColumnView(show_column_separators=False, reorderable=False); self.cv.add_css_class("data-table")
        def col(titre, rempl, cmp, expand=False, larg=None):
            f = Gtk.SignalListItemFactory()
            f.connect("setup", lambda _f, it: it.set_child(boite(False, 8)))
            def bind(_f, it):
                bx = it.get_child(); vider(bx); info = it.get_item(); rempl(bx, info)
            f.connect("bind", bind)
            c = Gtk.ColumnViewColumn(title=titre, factory=f, expand=expand, resizable=True)
            if larg: c.set_fixed_width(larg)
            c.set_sorter(Gtk.CustomSorter.new(lambda a, b, _d=None: cmp(a, b)))
            self.cv.append_column(c); return c
        def nom_et_etiquette(bx, i):
            bx.append(icone_info(i)); bx.append(label(i.get_display_name(), ellipsize=True, hexpand=True))
            e = ET.lire(fichier_de(i).get_path() or "")
            if e: bx.append(pastille_couleur(e))
        nom = col("Nom", nom_et_etiquette,
                  lambda a, b: (a.get_display_name().lower() > b.get_display_name().lower()) - (a.get_display_name().lower() < b.get_display_name().lower()), True)
        col("Modifié", lambda bx, i: bx.append(label(date_txt(i), "attenue", "petit")),
            lambda a, b: ((a.get_modification_date_time() or GLib.DateTime.new_now_utc()).to_unix() > (b.get_modification_date_time() or GLib.DateTime.new_now_utc()).to_unix()) - ((a.get_modification_date_time() or GLib.DateTime.new_now_utc()).to_unix() < (b.get_modification_date_time() or GLib.DateTime.new_now_utc()).to_unix()), larg=160)
        col("Type", lambda bx, i: bx.append(label(type_txt(i), "attenue", "petit", ellipsize=True)), lambda a, b: (type_txt(a) > type_txt(b)) - (type_txt(a) < type_txt(b)), larg=180)
        col("Taille", lambda bx, i: bx.append(label(taille_txt(i), "attenue", "petit", "chiffre", xalign=1, hexpand=True)), lambda a, b: (a.get_size() > b.get_size()) - (a.get_size() < b.get_size()), larg=100)
        dossiers_dabord = Gtk.CustomSorter.new(lambda a, b, _d=None: (a.get_file_type() != Gio.FileType.DIRECTORY) - (b.get_file_type() != Gio.FileType.DIRECTORY))
        ms = Gtk.MultiSorter(); ms.append(dossiers_dabord); ms.append(self.cv.get_sorter())
        self.tri = Gtk.SortListModel.new(filtree, ms)
        self.mod_windows = Gtk.MultiSelection.new(self.tri); self.cv.set_model(self.mod_windows)
        self.tri_base, self.sel_base = self.tri, self.mod_windows
        self.cv.sort_by_column(nom, Gtk.SortType.ASCENDING)
        self.cv.connect("activate", lambda cv, pos: self.ouvrir(fichier_de(self.tri.get_item(pos)).get_path()))
        g = Gtk.GestureClick(button=3); g.connect("pressed", self.clic_droit_windows); self.cv.add_controller(g)
        ds = Gtk.DragSource(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        ds.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([Gio.File.new_for_path(p) for p in self.selection()])) if self.selection() else None)
        self.cv.add_controller(ds)
        dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        dt.connect("drop", lambda t, v, x, y: (self.coller_vers([f.get_path() for f in v.get_files()], self.dossier, deplacer=False), True)[1]); self.cv.add_controller(dt)
        sc = Gtk.ScrolledWindow(); sc.set_child(self.cv); self.pile.add_named(sc, "windows")

    def selection(self):
        if self.vue in ("windows", "galerie"):
            sel = self.mod_windows.get_selection(); L = []
            for k in range(sel.get_size()):
                it = self.tri.get_item(sel.get_nth(k))
                if it: L.append(fichier_de(it).get_path())
            return L
        return [self.choix] if getattr(self, "choix", None) else []

    def clic_droit_windows(self, g, n, x, y):
        sel = self.selection()
        pop = popover_menu(self.cv, self.menu_fichiers(sel) if sel else self.menu_dossier())
        if pop:
            r = Gdk.Rectangle(); r.x, r.y, r.width, r.height = int(x), int(y), 1, 1; pop.set_pointing_to(r)

    # =================================================================== vue Galerie (miniatures : rushes, photos RAW…)
    def construire_galerie(self):
        self._lies = {}                  # chemin → Gtk.Picture affichée (mise à jour quand la miniature est prête)
        self._file_min = []; self._fil_min = None
        f = Gtk.SignalListItemFactory()
        def setup(_f, it):
            v = boite(True, 4, "carte-galerie"); v.set_size_request(176, 150)
            pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True); pic.set_size_request(168, 104); v.append(pic)
            lb = boite(False, 4, halign=Gtk.Align.CENTER); et = boite(False, 0); lb.append(et)
            l = label("", "petit", xalign=0.5, ellipsize=True); l.set_max_width_chars(22); lb.append(l); v.append(lb)
            it.set_child(v); it._pic, it._l, it._et = pic, l, et
        def bind(_f, it):
            info = it.get_item(); p = fichier_de(info).get_path(); it._l.set_text(info.get_display_name()); it._p = p
            vider(it._et); e = ET.lire(p or "")
            if e: it._et.append(pastille_couleur(e))
            self._lies[p] = it._pic
            mini = medias.chemin_miniature(p)[0] if p and medias.est_media(p) else None
            if mini and os.path.exists(mini):
                it._pic.set_filename(mini)
            else:
                ic = info.get_icon(); th = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
                pt = th.lookup_by_gicon(ic, 96, 1, Gtk.TextDirection.NONE, 0) if ic else None
                it._pic.set_paintable(pt)
                if mini: self.demander_miniature(p)
        def unbind(_f, it):
            if self._lies.get(getattr(it, "_p", None)) is it._pic: self._lies.pop(it._p, None)
        f.connect("setup", setup); f.connect("bind", bind); f.connect("unbind", unbind)
        self.grille = Gtk.GridView(model=self.sel_base, factory=f, max_columns=12, min_columns=2, enable_rubberband=True)
        self.grille.connect("activate", lambda gv, pos: self.ouvrir(fichier_de(self.tri.get_item(pos)).get_path()))
        g = Gtk.GestureClick(button=3); g.connect("pressed", lambda g_, n, x, y: popover_menu(self.grille, self.menu_fichiers(self.selection()) if self.selection() else self.menu_dossier())); self.grille.add_controller(g)
        sc = Gtk.ScrolledWindow(); sc.set_child(self.grille); self.pile.add_named(sc, "galerie")

    def demander_miniature(self, p):
        """Miniatures fabriquées une à une en arrière-plan (les plus visibles d'abord)."""
        if p in self._file_min: return
        self._file_min.append(p)
        if self._fil_min and self._fil_min.is_alive(): return
        def fil():
            while self._file_min:
                q = self._file_min.pop()
                if q not in self._lies: continue          # plus à l'écran
                m = medias.miniature(q)
                if m: GLib.idle_add(lambda q=q, m=m: (self._lies[q].set_filename(m) if q in self._lies else None, False)[1])
        self._fil_min = threading.Thread(target=fil, daemon=True); self._fil_min.start()

    def infos_fichier(self, p):
        """Fenêtre d'informations : miniature + codec, résolution, i/s, durée, timecode, caméra… (ffprobe / exiftool)."""
        d = Gtk.Window(transient_for=self.win, modal=False, title="Informations — " + os.path.basename(p), default_width=520)
        v = boite(True, 10, margin_top=18, margin_bottom=18, margin_start=20, margin_end=20)
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN); pic.set_size_request(480, 220); v.append(pic)
        v.append(label(os.path.basename(p), "page-titre", wrap=True))
        try: st = os.stat(p); v.append(label("%s · modifié le %s" % (S.humain(st.st_size), datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y à %H:%M")), "attenue"))
        except OSError: pass
        g = Gtk.Grid(column_spacing=16, row_spacing=6); v.append(g); g.attach(label("Lecture des informations…", "attenue"), 0, 0, 2, 1)
        r = boite(False, 8, halign=Gtk.Align.END)
        r.append(bouton("Copier", "copy", "fantome", rappel=lambda: Gdk.Display.get_default().get_clipboard().set_text(getattr(d, "_txt", ""))))
        r.append(bouton("Ouvrir", "external-link", "pilule", rappel=lambda: self.ouvrir(p))); v.append(r)
        d.set_child(v); d.present()
        def fin(res):
            m, L = res if isinstance(res, tuple) else (None, [])
            if m: pic.set_filename(m)
            else: pic.set_visible(False)
            c = g.get_first_child()
            while c: n = c.get_next_sibling(); g.remove(c); c = n
            for i, (k, val) in enumerate(L or [("Informations", "aucune information technique pour ce type de fichier")]):
                g.attach(label(k, "attenue", xalign=1), 0, i, 1, 1); g.attach(label(str(val), "gras", wrap=True, selectable=True, xalign=0), 1, i, 1, 1)
            d._txt = os.path.basename(p) + "\n" + "\n".join("%s : %s" % kv for kv in L)
        S.en_fond(lambda: (medias.miniature(p, 512) if medias.est_media(p) else None, medias.infos(p)), fin)

    # =================================================================== vue Mac (colonnes)
    def construire_mac(self):
        self.mac_boite = boite(False, 0)
        sc = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.NEVER); sc.set_child(self.mac_boite); self.mac_sc = sc
        self.pile.add_named(sc, "mac")

    def remplir_mac(self):
        vider(self.mac_boite)
        # colonnes depuis le dossier personnel (ou /) jusqu'au dossier courant
        maison = os.path.expanduser("~"); base = maison if self.dossier.startswith(maison) else "/"
        chaine = [base]; p = base
        for x in [y for y in self.dossier[len(base):].split("/") if y]: p = os.path.join(p, x); chaine.append(p)
        for k, d in enumerate(chaine): self.colonne_mac(d, chaine[k + 1] if k + 1 < len(chaine) else None)
        GLib.timeout_add(80, lambda: (self.mac_sc.get_hadjustment().set_value(self.mac_sc.get_hadjustment().get_upper()), False)[1])

    def colonne_mac(self, d, choisi=None):
        try: noms = sorted((x for x in os.listdir(d) if self.cachés or not x.startswith(".")), key=lambda x: (not os.path.isdir(os.path.join(d, x)), x.lower()))
        except OSError: noms = []
        lb = Gtk.ListBox(); lb.add_css_class("colonne-mac"); lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
        for x in noms[:2000]:
            p = os.path.join(d, x); r = Gtk.ListBoxRow(); r._chemin = p
            bx = boite(False, 8, margin_start=8, margin_end=8, margin_top=3, margin_bottom=3)
            bx.append(gicon_image(apps.icone_fichier(p), 16)); bx.append(label(x, ellipsize=True, hexpand=True))
            if os.path.isdir(p): bx.append(ico("chevron-right", 12, "d"))
            r.set_child(bx); lb.append(r)
            if p == choisi: lb.select_row(r)
            g = Gtk.GestureClick(button=3); g.connect("pressed", lambda *_a, p=p, r=r: (setattr(self, "choix", p), popover_menu(r, self.menu_fichiers([p])))); r.add_controller(g)
            g2 = Gtk.GestureClick(); g2.connect("pressed", lambda g_, n, *_a, p=p: self.ouvrir(p) if n == 2 and not os.path.isdir(p) else None); r.add_controller(g2)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); sc.set_child(lb); sc.set_size_request(int(self.cfg.get("fichiers_col_mac", 240)), -1)
        def choisir(_lb, row):
            if not row or sc.get_parent() is None: return
            self.choix = row._chemin
            # retire les colonnes à droite
            c = pg.get_next_sibling()          # garde la poignée de cette colonne
            while c: n = c.get_next_sibling(); self.mac_boite.remove(c); c = n
            if os.path.isdir(row._chemin):
                self.dossier = row._chemin; self.barre_chemin(); self.colonne_mac(row._chemin)
            else:
                self.apercu_mac(row._chemin)
            GLib.timeout_add(60, lambda: (self.mac_sc.get_hadjustment().set_value(self.mac_sc.get_hadjustment().get_upper()), False)[1])
        lb.connect("row-selected", choisir)
        self.mac_boite.append(sc)
        # poignée : glisser pour élargir les colonnes (mémorisé), double-clic pour revenir à la largeur normale
        pg = Gtk.Box(); pg.add_css_class("poignee-colonne"); pg.set_size_request(6, -1); pg.set_cursor(Gdk.Cursor.new_from_name("col-resize"))
        dr = Gtk.GestureDrag(); dep = {}
        dr.connect("drag-begin", lambda g, x, y: dep.update(l=sc.get_width()))
        def bouge(g, dx, dy):
            l = max(150, min(700, int(dep.get("l", 240) + dx)))
            c = self.mac_boite.get_first_child()
            while c:
                if isinstance(c, Gtk.ScrolledWindow): c.set_size_request(l, -1)
                c = c.get_next_sibling()
            dep["n"] = l
        dr.connect("drag-update", bouge)
        dr.connect("drag-end", lambda *_: (config.modifier(_histo=False, fichiers_col_mac=dep.get("n", 240)), self.cfg.__setitem__("fichiers_col_mac", dep.get("n", 240))))
        pg.add_controller(dr)
        dc = Gtk.GestureClick(); dc.connect("pressed", lambda g, n, x, y: (bouge(None, 240 - dep.get("l", 240), 0), dr.emit("drag-end", 0, 0)) if n == 2 else None); pg.add_controller(dc)
        self.mac_boite.append(pg)

    def apercu_mac(self, p):
        v = boite(True, 10, margin_start=16, margin_end=16, margin_top=16); v.set_size_request(300, -1)
        ct = Gio.content_type_guess(p, None)[0] or ""
        if medias.est_media(p):
            pic = Gtk.Picture(); pic.set_size_request(260, 200); pic.set_content_fit(Gtk.ContentFit.CONTAIN); v.append(pic)
            S.en_fond(medias.miniature, lambda m: pic.set_filename(m) if isinstance(m, str) else pic.set_paintable(None), p, 512)
        else:
            v.append(gicon_image(apps.icone_fichier(p), 96))
        v.append(label(os.path.basename(p), "gras", wrap=True, xalign=0.5))
        try: st = os.stat(p); v.append(label("%s · %s" % (S.humain(st.st_size), datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")), "petit", "attenue", xalign=0.5))
        except OSError: pass
        v.append(label(Gio.content_type_get_description(ct) if ct else "", "petit", "attenue", xalign=0.5))
        if medias.ext(p) in medias.VIDEO + medias.RAW + tuple(medias.FERMES) or ct.startswith("audio/"):
            g = Gtk.Grid(column_spacing=10, row_spacing=3, halign=Gtk.Align.CENTER); v.append(g)
            def rempl(L):
                for i, (k, val) in enumerate((L if isinstance(L, list) else [])[:8]):
                    g.attach(label(k, "petit", "attenue", xalign=1), 0, i, 1, 1); g.attach(label(str(val), "petit", xalign=0, ellipsize=True, largeur=26), 1, i, 1, 1)
            S.en_fond(medias.infos, rempl, p)
        r = boite(False, 6, halign=Gtk.Align.CENTER)
        r.append(bouton("Ouvrir", "external-link", "pilule", rappel=lambda: self.ouvrir(p))); r.append(bouton("Aperçu", "eye", "fantome", rappel=lambda: S.detacher(["xiii-apercu", p])))
        v.append(r); self.mac_boite.append(v)

    # =================================================================== vue Arbre (généalogique)
    def construire_arbre(self):
        self.arbre_sc = Gtk.ScrolledWindow(); self.arbre_boite = boite(True, 0, halign=Gtk.Align.CENTER, margin_top=20, margin_bottom=30, margin_start=20, margin_end=20)
        self.arbre_sc.set_child(self.arbre_boite); self.pile.add_named(self.arbre_sc, "arbre"); self.ouverts = set()

    def remplir_arbre(self):
        vider(self.arbre_boite); self.arbre_boite.append(self.noeud(self.dossier, racine=True))

    def noeud(self, p, racine=False, profondeur=0):
        v = boite(True, 0, halign=Gtk.Align.CENTER)
        est_dir = os.path.isdir(p); ouvert = racine or p in self.ouverts
        b = Gtk.Button(); b.add_css_class("noeud")
        if racine: b.add_css_class("racine")
        if ouvert and not racine: b.add_css_class("ouvert")
        bx = boite(True, 2); bx.append(gicon_image(apps.icone_fichier(p), 28)); bx.append(label(os.path.basename(p) or "/", "gras" if est_dir else "", ellipsize=True, largeur=18, xalign=0.5))
        if est_dir:
            try: n = len([x for x in os.listdir(p) if self.cachés or not x.startswith(".")])
            except OSError: n = 0
            bx.append(label("%d élément(s)" % n, "petit", "attenue", xalign=0.5))
        b.set_child(bx)
        def clic(*_):
            if not est_dir: self.ouvrir(p); return
            if racine: return
            (self.ouverts.discard if p in self.ouverts else self.ouverts.add)(p); self.remplir_arbre()
        b.connect("clicked", clic)
        g = Gtk.GestureClick(button=3); g.connect("pressed", lambda *_a: (setattr(self, "choix", p), popover_menu(b, self.menu_fichiers([p]) + ([None, ("folder-open", "Entrer dans ce dossier", lambda: self.aller(p))] if est_dir and not racine else [])))); b.add_controller(g)
        v.append(b)
        if est_dir and ouvert and profondeur < 6:
            try: enfants = sorted((x for x in os.listdir(p) if self.cachés or not x.startswith(".")), key=lambda x: (not os.path.isdir(os.path.join(p, x)), x.lower()))
            except OSError: enfants = []
            dossiers = [os.path.join(p, x) for x in enfants if os.path.isdir(os.path.join(p, x))]
            fichiers = [os.path.join(p, x) for x in enfants if not os.path.isdir(os.path.join(p, x))]
            if dossiers or fichiers:
                lien = Gtk.Box(halign=Gtk.Align.CENTER); lien.add_css_class("lien-v"); v.append(lien)
                rang = boite(False, 14, "enfants", halign=Gtk.Align.CENTER)
                for c in dossiers[:24]:
                    col = boite(True, 0, valign=Gtk.Align.START); l2 = Gtk.Box(halign=Gtk.Align.CENTER); l2.add_css_class("lien-v"); col.append(l2)
                    col.append(self.noeud(c, profondeur=profondeur + 1)); rang.append(col)
                if fichiers:
                    col = boite(True, 0, valign=Gtk.Align.START); l2 = Gtk.Box(halign=Gtk.Align.CENTER); l2.add_css_class("lien-v"); col.append(l2)
                    f = boite(True, 0, "noeud")
                    f.append(label("%d fichier(s)" % len(fichiers), "petit", "gras", xalign=0.5))
                    for x in fichiers[:8]:
                        fb = Gtk.Button(); fb.add_css_class("plat"); fb.add_css_class("feuille"); fb.set_child(label(os.path.basename(x), "petit", ellipsize=True, largeur=20))
                        fb.connect("clicked", lambda _b, x=x: self.ouvrir(x)); f.append(fb)
                    if len(fichiers) > 8: f.append(label("+ %d autres" % (len(fichiers) - 8), "petit", "attenue", xalign=0.5))
                    col.append(f); rang.append(col)
                if len(dossiers) > 24: rang.append(label("+ %d dossiers" % (len(dossiers) - 24), "attenue", valign=Gtk.Align.CENTER))
                v.append(rang)
        return v

    # =================================================================== actions
    def ouvrir(self, p):
        if not p: return
        if os.path.isdir(p): self.aller(p)
        elif p.lower().endswith((".exe", ".msi")): S.detacher(["xiii-windows", p])
        else: apps.ouvrir_fichier(p)

    def menu_fichiers(self, L):
        if not L: return self.menu_dossier()
        p = L[0]; uri = Gio.File.new_for_path(p).get_uri()
        items = [("folder-open", "Ouvrir", lambda: self.ouvrir(p))]
        if os.path.isdir(p): items.append(("plus", "Ouvrir dans un nouvel onglet", lambda: self.nouvel_onglet(p)))
        if os.path.isfile(p):
            items.append(("eye", "Aperçu rapide (Espace)", lambda: S.detacher(["xiii-apercu", p])))
            items.append(("info", "Informations (codec, durée, timecode…)" if medias.est_media(p) or medias.ext(p) in medias.FERMES else "Informations", lambda: self.infos_fichier(p)))
            try:
                for a in Gio.AppInfo.get_recommended_for_type(Gio.content_type_guess(p, None)[0])[:3]:
                    items.append(("app-window", "Ouvrir avec " + a.get_display_name(), lambda a=a: a.launch([Gio.File.new_for_path(p)], None)))
            except Exception: pass
        items += [None, ("scissors", "Couper (Ctrl+X)", lambda: self.memoriser(L, True)), ("copy", "Copier (Ctrl+C)", lambda: self.memoriser(L, False))]
        if self.presse and os.path.isdir(p): items.append(("clipboard-paste", "Coller dans ce dossier", lambda: self.coller(p)))
        if len(L) == 1 and re.search(r"\.(zip|rar|7z|tar|tgz|gz|xz|bz2|zst)$", p, re.I):
            items += [("folder-input", "Extraire…", lambda: S.detacher(["xiii-archives", p]))]
        if len(L) == 1 and p.lower().endswith(".deb"):
            items += [("package", "Installer ce logiciel", lambda: S.detacher(["xiii-paquets", p]))]
        items += [("tag", "Étiquette de couleur…", lambda: self.menu_etiquette(L))]
        items += [("text-cursor-input", "Renommer %d éléments… (F2)" % len(L) if len(L) > 1 else "Renommer (F2)", lambda: self.renommer_lot(L) if len(L) > 1 else self.renommer(p)), ("archive", "Compresser (.zip)", lambda: self.compresser(L)),
                  ("smartphone", "Envoyer à un appareil proche", lambda: S.detacher(["xiii-envoi"] + L)),
                  ("send", "Envoyer (Transferts XIII)", lambda: S.detacher(["xiii-transferts"] + L)), ("folder-input", "Envoyer à DOSSIER XIII", lambda: S.detacher(["xiii-suite", "--dossier"] + L)),
                  None, ("link", "Copier le chemin", lambda: Gdk.Display.get_default().get_clipboard().set_text("\n".join(L))),
                  ("trash-2", "Mettre à la corbeille (Suppr)", lambda: self.corbeille(L)), None,
                  ("square-terminal", "Ouvrir dans le terminal", lambda: S.detacher(["foot", "--app-id=fr.xiii.terminal", "-D", p if os.path.isdir(p) else os.path.dirname(p)])),
                  ("info", "Propriétés", lambda: S.detacher(["dbus-send", "--session", "--dest=org.xfce.FileManager", "--type=method_call", "/org/xfce/FileManager",
                                                            "org.xfce.FileManager.DisplayFileProperties", "string:" + uri, "string:", "string:"]))]
        if len(L) == 1 and L[0].lower().endswith((".pdf", ".docx", ".odt", ".pptx", ".odp", ".txt", ".md", ".srt")):
            items.append(("sparkles", "Résumer avec l'IA", lambda: S.detacher(["xiii-voix", "--resumer", L[0]])))
        return items

    def menu_etiquette(self, L):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Étiquette", default_width=300)
        v = boite(True, 4, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        def mettre(c):
            for p in L: ET.poser(p, c)
            d.close(); self.liste_dir.set_file(None); self.recharger(); self.remplir_volet()
        for k, n, hx in ET.COULEURS:
            b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat"); bx = boite(False, 10); bx.append(pastille_couleur(k, 14)); bx.append(label(n)); b.set_child(bx)
            b.connect("clicked", lambda _b, k=k: mettre(k)); v.append(b)
        v.append(bouton("Retirer l'étiquette", "x", "plat", rappel=lambda: mettre(None)))
        d.set_child(v); d.present()

    def montrer_liste(self, R, titre):
        """Affiche une liste de fichiers venus de n'importe où (recherche, étiquette, dossier intelligent)."""
        st = Gio.ListStore.new(Gio.FileInfo)
        for p in R:
            try: info = Gio.File.new_for_path(p).query_info(ATTR, Gio.FileQueryInfoFlags.NONE, None); info.set_attribute_object("standard::file", Gio.File.new_for_path(p)); st.append(info)
            except GLib.Error: pass
        self.pile.set_visible_child_name("windows")
        tri = Gtk.SortListModel.new(st, self.tri_base.get_sorter()); sel = Gtk.MultiSelection.new(tri)
        self.cv.set_model(sel); self.mod_windows = sel; self.tri = tri; self.vue_avant = self.vue; self.vue = "windows"
        for k, b in self.b_vues.items(): (b.add_css_class if k == "windows" else b.remove_css_class)("actif")
        self.etat.set_text("%d élément(s) · %s" % (len(R), titre))

    def par_etiquette(self, c):
        self.etat.set_text("Recherche des fichiers « %s »…" % ET.NOMS[c])
        S.en_fond(ET.chercher, lambda R: self.montrer_liste(R if isinstance(R, list) else [], "étiquette " + ET.NOMS[c]), c, [os.path.expanduser("~")] + [m.get_root().get_path() for m in Gio.VolumeMonitor.get().get_mounts() if m.get_root() and m.get_root().get_path()])

    def menu_dossier(self):
        L = [("folder-plus", "Nouveau dossier", self.nouveau_dossier), ("file-text", "Nouveau document texte", self.nouveau_texte)]
        if self.presse: L.append(("clipboard-paste", "Coller (Ctrl+V)", lambda: self.coller(self.dossier)))
        L += [None, ("refresh-cw", "Actualiser (F5)", self.recharger), ("square-terminal", "Ouvrir dans le terminal", lambda: S.detacher(["foot", "--app-id=fr.xiii.terminal", "-D", self.dossier])),
              ("share-2", "Partager ce dossier sur le réseau", lambda: S.detacher(["xiii-transferts", "--local", self.dossier]))]
        return L

    def menu_plus(self):
        v = self.cfg.get("fichiers_verifier", True)
        return [(("eye-off" if self.cachés else "eye"), "Masquer les fichiers cachés" if self.cachés else "Afficher les fichiers cachés (Ctrl+H)", self.basculer_caches),
                ("shield-check" if v else "shield", ("✓ " if v else "") + "Vérifier chaque copie (xxHash, plus sûr pour les rushes)",
                 lambda: (config.modifier(fichiers_verifier=not v), self.cfg.__setitem__("fichiers_verifier", not v))),
                ("columns-2", "Double volet (F3)", self.basculer_double),
                ("hard-drive", "Lecteurs réseau et cloud", lambda: S.detacher("xiii-lecteurs")), ("send", "Transferts XIII", lambda: S.detacher("xiii-transferts")),
                ("folder", "Ouvrir dans Thunar", lambda: S.detacher(["thunar", self.dossier]))]

    def basculer_caches(self):
        self.cachés = not self.cachés; self.filtre.changed(Gtk.FilterChange.DIFFERENT); self.recharger()

    def memoriser(self, L, couper):
        self.presse = list(L); self.couper = couper
        uris = [Gio.File.new_for_path(p).get_uri() for p in L]
        g = (("cut" if couper else "copy") + "\n" + "\n".join(uris)).encode()
        Gdk.Display.get_default().get_clipboard().set_content(Gdk.ContentProvider.new_union([
            Gdk.ContentProvider.new_for_bytes("x-special/gnome-copied-files", GLib.Bytes.new(g)),
            Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new(("\r\n".join(uris) + "\r\n").encode()))]))
        self.etat.set_text("%d élément(s) %s" % (len(L), "coupé(s)" if couper else "copié(s)"))

    def coller(self, dest):
        if self.presse: self.coller_vers(self.presse, dest, self.couper)
        if self.couper: self.presse = None

    def coller_vers(self, L, dest, deplacer=False):
        L = [p for p in L if p and os.path.exists(p) and not (deplacer and os.path.realpath(os.path.dirname(p.rstrip("/"))) == os.path.realpath(dest))]
        L = [p for p in L if not (os.path.isdir(p) and os.path.realpath(dest).startswith(os.path.realpath(p) + "/"))]   # pas un dossier dans lui-même
        if not L: return
        self.file.ajouter(copie.Tache(L, dest, deplacer, verifier=self.cfg.get("fichiers_verifier", True)))

    def maj_copies(self, fini=None):
        """Panneau des copies en cours : progression, vitesse, temps restant, pause / reprise / annulation."""
        vider(self.zone_copies)
        actives = [t for t in self.file.taches if t.etat not in ("terminée", "annulée") or t is fini or getattr(t, "_vu", 0) > time.time()]
        self.zone_copies.set_visible(bool(actives))
        for t in actives:
            if t is fini: t._vu = time.time() + 8
            r = boite(True, 3, "carte", margin_top=4)
            h = boite(False, 8); h.append(ico("copy" if not t.deplacer else "move", 16, "c")); h.append(label(t.titre, "gras", hexpand=True, ellipsize=True))
            if t.etat in ("copie", "vérification", "attente", "préparation"):
                h.append(bouton(None, "play" if t.pause else "pause", "plat", taille=14, tip="Reprendre" if t.pause else "Pause", rappel=lambda t=t: (setattr(t, "pause", not t.pause), self.maj_copies())))
                h.append(bouton(None, "x", "plat", taille=14, tip="Annuler", rappel=lambda t=t: (setattr(t, "annule", True), setattr(t, "pause", False))))
            elif t.erreurs:
                h.append(bouton("Détails", None, "fantome", taille=13, rappel=lambda t=t: self.erreurs_copie(t)))
            r.append(h)
            pb = Gtk.ProgressBar(fraction=min(1, t.fait / t.total) if t.total else 0); pb.add_css_class("indic-barre")
            if t.erreurs: pb.add_css_class("plein")
            r.append(pb); r.append(label(t.texte(S.humain), "petit", "attenue", ellipsize=True)); self.zone_copies.append(r)
        if fini is not None:
            self.recharger()
            if fini.etat in ("terminée", "erreurs"):
                corps = fini.texte(S.humain) + ((" · " + fini.erreurs[0][1]) if fini.erreurs else "")
                S.detacher(["notify-send", "-a", "Fichiers", "-i", "dialog-error" if fini.erreurs else "folder", "-h", "string:sound-name:" + ("dialog-error" if fini.erreurs else "complete"),
                            fini.titre + (" : erreurs" if fini.erreurs else " : terminé"), corps])
        if actives and not self._src_copies:
            self._src_copies = GLib.timeout_add(500, self._tic_copies)
        return False

    def _tic_copies(self):
        if not any(t.etat in ("copie", "vérification", "préparation", "attente") for t in self.file.taches) and not any(getattr(t, "_vu", 0) > time.time() for t in self.file.taches):
            self._src_copies = 0; self.maj_copies(); return False
        self.maj_copies(); return True

    def erreurs_copie(self, t):
        d = Gtk.Window(transient_for=self.win, title="Erreurs de copie", default_width=640, default_height=400)
        v = boite(True, 6, margin_top=14, margin_bottom=14, margin_start=16, margin_end=16)
        v.append(label("%d fichier(s) en erreur" % len(t.erreurs), "page-titre"))
        lst = boite(True, 4)
        for p, e in t.erreurs[:300]: lst.append(label("%s — %s" % (p, e), "petit", wrap=True, selectable=True))
        v.append(defilant(lst, 300)); d.set_child(v); d.present()

    def renommer(self, p):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Renommer", default_width=420)
        v = boite(True, 10, margin_top=18, margin_bottom=18, margin_start=20, margin_end=20)
        v.append(label("Renommer", "page-titre")); e = Gtk.Entry(text=os.path.basename(p)); v.append(e)
        def ok(*_):
            n = e.get_text().strip()
            if n and "/" not in n and n != os.path.basename(p):
                try: os.rename(p, os.path.join(os.path.dirname(p), n))
                except OSError as ex: self.etat.set_text(str(ex))
            d.close(); self.recharger()
        e.connect("activate", ok)
        r = boite(False, 8, halign=Gtk.Align.END); r.append(bouton("Annuler", None, "fantome", rappel=d.close)); r.append(bouton("Renommer", None, "pilule", rappel=ok)); v.append(r)
        d.set_child(v); d.present()
        n, ext = os.path.splitext(os.path.basename(p)); GLib.idle_add(lambda: (e.grab_focus(), e.select_region(0, len(n) if os.path.isfile(p) else -1), False)[2])

    def renommer_lot(self, L):
        """Renommer plusieurs fichiers d'un coup : modèle numéroté, remplacer, casse, date ; aperçu avant de valider."""
        L = sorted(L, key=lambda p: os.path.basename(p).lower())
        d = Gtk.Window(transient_for=self.win, modal=True, title="Renommer %d éléments" % len(L), default_width=720, default_height=560)
        v = boite(True, 10, margin_top=16, margin_bottom=16, margin_start=18, margin_end=18)
        v.append(label("Renommer %d éléments" % len(L), "page-titre"))
        g = Gtk.Grid(column_spacing=10, row_spacing=8); v.append(g)
        mode = Gtk.DropDown(model=Gtk.StringList.new(["Nouveau nom numéroté", "Remplacer du texte", "Ajouter au début / à la fin", "Majuscules / minuscules"]))
        g.attach(label("Méthode", xalign=1), 0, 0, 1, 1); g.attach(mode, 1, 0, 3, 1)
        e1 = Gtk.Entry(hexpand=True); e2 = Gtk.Entry(hexpand=True); l1 = label("", xalign=1); l2 = label("", xalign=1)
        num = Gtk.SpinButton.new_with_range(0, 99999, 1); num.set_value(1); chiffres = Gtk.SpinButton.new_with_range(1, 6, 1); chiffres.set_value(3)
        cas = Gtk.DropDown(model=Gtk.StringList.new(["minuscules", "MAJUSCULES", "Première Lettre En Majuscule"]))
        date = Gtk.CheckButton(label="Ajouter la date du fichier (AAAA-MM-JJ_)")
        g.attach(l1, 0, 1, 1, 1); g.attach(e1, 1, 1, 3, 1); g.attach(l2, 0, 2, 1, 1); g.attach(e2, 1, 2, 3, 1)
        ln = label("Commencer à", xalign=1); lc = label("Chiffres", xalign=1)
        g.attach(ln, 0, 3, 1, 1); g.attach(num, 1, 3, 1, 1); g.attach(lc, 2, 3, 1, 1); g.attach(chiffres, 3, 3, 1, 1)
        g.attach(cas, 1, 4, 3, 1); g.attach(date, 1, 5, 3, 1)
        ap = boite(True, 2); v.append(label("Aperçu", "section")); v.append(defilant(ap, 260))
        msg = label("", "attenue", "petit"); v.append(msg)
        def nouveaux():
            m = mode.get_selected(); out = []
            for i, p in enumerate(L):
                b = os.path.basename(p.rstrip("/")); n, x = os.path.splitext(b) if os.path.isfile(p) else (b, "")
                if m == 0: n = (e1.get_text() or "Fichier") + "_" + str(int(num.get_value()) + i).zfill(int(chiffres.get_value()))
                elif m == 1: n = n.replace(e1.get_text(), e2.get_text()) if e1.get_text() else n
                elif m == 2: n = e1.get_text() + n + e2.get_text()
                else: n = [n.lower(), n.upper(), n.title()][cas.get_selected()]
                if date.get_active():
                    try: n = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d_") + n
                    except OSError: pass
                out.append(n + (x.lower() if m == 3 and cas.get_selected() == 0 else x))
            return out
        def maj(*_):
            m = mode.get_selected()
            l1.set_text(["Nom", "Chercher", "Au début", ""][m]); l2.set_text(["", "Remplacer par", "À la fin", ""][m])
            for w, vis in ((l1, m != 3), (e1, m != 3), (l2, m in (1, 2)), (e2, m in (1, 2)), (ln, m == 0), (num, m == 0), (lc, m == 0), (chiffres, m == 0), (cas, m == 3)): w.set_visible(vis)
            vider(ap); N = nouveaux(); doublons = len(set(N)) != len(N)
            for p, n in list(zip(L, N))[:200]:
                r = boite(False, 8); r.append(label(os.path.basename(p), "attenue", ellipsize=True, hexpand=True)); r.append(ico("arrow-right", 12, "d")); r.append(label(n, "gras", ellipsize=True, hexpand=True)); ap.append(r)
            msg.set_text("Deux fichiers auraient le même nom : modifiez le modèle." if doublons else ""); ok_b.set_sensitive(not doublons)
        def appliquer():
            N = nouveaux(); fait = 0; tmp = []
            for p in L:                                  # deux temps : évite les collisions (a→b, b→a)
                t = os.path.join(os.path.dirname(p), ".xiii-ren-%d-%s" % (os.getpid(), os.path.basename(p))); os.rename(p, t); tmp.append(t)
            for t, n, p in zip(tmp, N, L):
                c = os.path.join(os.path.dirname(t), n)
                if os.path.exists(c): c = os.path.join(os.path.dirname(t), os.path.basename(p))
                try: os.rename(t, c); fait += 1
                except OSError as ex: self.etat.set_text(str(ex))
            d.close(); self.recharger(); self.etat.set_text("%d élément(s) renommé(s)" % fait)
        for w in (e1, e2): w.connect("changed", maj)
        for w in (num, chiffres): w.connect("value-changed", maj)
        for w in (mode, cas): w.connect("notify::selected", maj)
        date.connect("toggled", maj)
        r = boite(False, 8, halign=Gtk.Align.END); r.append(bouton("Annuler", None, "fantome", rappel=d.close)); ok_b = bouton("Renommer", None, "pilule", rappel=appliquer); r.append(ok_b); v.append(r)
        e1.set_text(os.path.splitext(os.path.basename(L[0]))[0].rstrip("0123456789_- ") or "Fichier")
        d.set_child(v); maj(); d.present()

    def corbeille(self, L):
        for p in L:
            try: Gio.File.new_for_path(p).trash(None)
            except GLib.Error as ex: self.etat.set_text(ex.message)
        self.recharger()

    def compresser(self, L):
        base = os.path.join(os.path.dirname(L[0]), os.path.basename(L[0].rstrip("/")) if len(L) == 1 else "Archive")
        S.en_fond(lambda: subprocess.run(["zip", "-qr", base + ".zip"] + [os.path.basename(x) for x in L], cwd=os.path.dirname(L[0])), lambda r: self.recharger())

    def nouveau_dossier(self):
        k = 1; d = os.path.join(self.dossier, "Nouveau dossier")
        while os.path.exists(d): k += 1; d = os.path.join(self.dossier, "Nouveau dossier %d" % k)
        try: os.makedirs(d); self.recharger(); GLib.timeout_add(300, lambda: (self.renommer(d), False)[1])
        except OSError as e: self.etat.set_text(str(e))

    def nouveau_texte(self):
        k = 1; f = os.path.join(self.dossier, "Nouveau document.txt")
        while os.path.exists(f): k += 1; f = os.path.join(self.dossier, "Nouveau document %d.txt" % k)
        open(f, "w").close(); self.recharger()

    def chercher(self):
        q = self.recherche.get_text().strip().lower()
        if not q: self.recharger(); return
        contenu = self.b_contenu.get_active()
        self.etat.set_text("Recherche de « %s »%s…" % (q, " dans le contenu des fichiers" if contenu else "")); base = self.dossier
        TEXTE = (".txt", ".md", ".csv", ".srt", ".vtt", ".edl", ".xml", ".fcpxml", ".json", ".html", ".log", ".ale", ".rtf", ".tex", ".ini", ".yml", ".yaml", ".py", ".sh")
        def dans(p):
            e = os.path.splitext(p)[1].lower()
            try:
                if e in TEXTE:
                    if os.path.getsize(p) > 20e6: return False
                    with open(p, errors="ignore") as f: return q in f.read().lower()
                if e == ".pdf":
                    return q in subprocess.run(["pdftotext", "-q", p, "-"], capture_output=True, text=True, timeout=20).stdout.lower()
                if e in (".docx", ".odt", ".xlsx", ".ods", ".pptx", ".odp"):
                    import zipfile
                    with zipfile.ZipFile(p) as z:
                        return any(q in re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore")).lower() for n in z.namelist()
                                   if n.endswith(".xml") and ("word/document" in n or n == "content.xml" or "sharedStrings" in n or "slides/slide" in n))
            except Exception: return False
            return False
        def tache():
            R = []; t0 = time.time()
            for r, ds, fs in os.walk(base):
                ds[:] = [d for d in ds if self.cachés or not d.startswith(".")]
                for x in ds + fs:
                    p = os.path.join(r, x)
                    if q in x.lower() or (contenu and x in fs and dans(p)): R.append(p)
                if len(R) > 500 or time.time() - t0 > 60: break
            return R
        S.en_fond(tache, lambda R: None if isinstance(R, Exception) else self.montrer_liste(R, "« %s »%s dans %s" % (q, " (noms et contenu)" if contenu else "", base)))

    # =================================================================== corbeille
    def vue_corbeille(self):
        x = self.pile.get_child_by_name("corbeille")
        if x: self.pile.remove(x)
        v = boite(True, 8, margin_start=14, margin_end=14, margin_top=10, margin_bottom=10)
        h = boite(False, 8); h.append(ico("trash-2", 24, "c")); h.append(label("Corbeille", "page-titre", hexpand=True))
        jours = int(self.cfg.get("corbeille_jours", 30))
        h.append(label("Vider automatiquement après", "petit", "attenue"))
        h.append(deroulant_simple([("0", "jamais"), ("7", "7 jours"), ("30", "30 jours"), ("90", "90 jours")], str(jours), lambda val: (config.modifier(corbeille_jours=int(val)), setattr(self, "cfg", config.charger()))))
        h.append(bouton("Vider la corbeille", "trash-2", "fantome", rappel=lambda: self.vider_corbeille())); v.append(h)
        lst = boite(True, 4); v.append(defilant(lst)); lst.get_parent().get_parent().set_vexpand(True)
        L = CB.elements()
        if not L: lst.append(label("La corbeille est vide.", "attenue"))
        for e in L[:500]:
            r = boite(False, 10, "reglage")
            r.append(gicon_image(apps.icone_fichier(e["fichier"]), 22))
            col = boite(True, 0, hexpand=True); col.append(label(e["nom"], "gras", ellipsize=True))
            col.append(label("Supprimé le %s · venait de %s%s" % (e["date"].strftime("%d/%m/%Y à %H:%M"), os.path.dirname(e["origine"]).replace(os.path.expanduser("~"), "~") or "?",
                                                                     "" if e["disque"] == "Ordinateur" else " · disque " + e["disque"]), "petit", "attenue", ellipsize=True)); r.append(col)
            def rest(e=e):
                try: d = CB.restaurer(e); self.etat.set_text("Restauré : " + d)
                except OSError as ex: self.etat.set_text(str(ex))
                self.vue_corbeille()
            def supp(e=e):
                confirmer_f(self.win, "Supprimer définitivement « %s » ?" % e["nom"], "Impossible à annuler.", "Supprimer", lambda: (CB.supprimer(e), self.vue_corbeille()))
            r.append(bouton("Restaurer", "rotate-ccw", "fantome", taille=13, rappel=rest)); r.append(bouton(None, "x", "plat", taille=14, tip="Supprimer définitivement", rappel=supp))
            lst.append(r)
        self.pile.add_named(v, "corbeille"); self.pile.set_visible_child_name("corbeille")
        S.en_fond(lambda: sum(CB.taille(e) for e in L), lambda t: self.etat.set_text("%d élément(s) à la corbeille · %s" % (len(L), S.humain(t) if isinstance(t, int) else "")))

    def vider_corbeille(self):
        L = CB.elements()
        if not L: return
        confirmer_f(self.win, "Vider la corbeille ?", "%d élément(s) seront supprimés définitivement (toutes les corbeilles, clés et disques compris)." % len(L), "Vider",
                    lambda: S.en_fond(lambda: [CB.supprimer(e) for e in L], lambda r: self.vue_corbeille()))

    # =================================================================== dossiers intelligents
    INTELLIGENTS = [("folder-kanban", "Récents du projet", "projet"), ("film", "Rushes de la semaine", "videos7"), ("hard-drive", "Gros fichiers (plus de 1 Go)", "gros"), ("clock", "Modifiés aujourd'hui", "jour")]
    def intelligent(self, k):
        racines = [os.path.expanduser("~")] + [m.get_root().get_path() for m in Gio.VolumeMonitor.get().get_mounts() if m.get_root() and m.get_root().get_path() and m.get_root().get_path().startswith(("/media", "/run/media", "/mnt"))]
        maintenant = time.time(); titre = dict((c, t) for _, t, c in self.INTELLIGENTS)[k]
        if k == "projet":
            pj = self.cfg.get("projet_actif")
            if not pj: self.etat.set_text("Aucun projet actif : choisissez-en un en haut à gauche de l'écran."); return
            racines = [os.path.expanduser("~/XIII/" + pj)]; titre = "Récents du projet " + pj
        self.etat.set_text(titre + " : recherche…")
        def tache():
            R = []
            for base in racines:
                for r, ds, fs in os.walk(base):
                    ds[:] = [d for d in ds if not d.startswith(".") and d not in ("node_modules", "__pycache__", "Trash")]
                    for x in fs:
                        p = os.path.join(r, x)
                        try: st = os.stat(p)
                        except OSError: continue
                        if k == "videos7" and medias.ext(p) in medias.VIDEO + tuple(medias.FERMES) and maintenant - st.st_mtime < 7 * 86400: R.append(p)
                        elif k == "gros" and st.st_size > 1e9: R.append(p)
                        elif k == "projet" and maintenant - st.st_mtime < 14 * 86400: R.append(p)
                        elif k == "jour" and maintenant - st.st_mtime < 86400 and not r.startswith(os.path.expanduser("~/.")): R.append(p)
                    if len(R) > 800: return R
            return R
        S.en_fond(tache, lambda R: self.montrer_liste(R if isinstance(R, list) else [], titre))

    def recherche_filtree(self, texte, typ=None, jours=0):
        """Recherche par nom, type et ancienneté (projet actif d'abord, puis dossier personnel et disques)."""
        racines = [os.path.expanduser("~")] + [m.get_root().get_path() for m in Gio.VolumeMonitor.get().get_mounts() if m.get_root() and m.get_root().get_path() and m.get_root().get_path().startswith(("/media", "/run/media", "/mnt"))]
        mots = [m for m in sans_accents(texte.lower()).split() if len(m) > 1]; lim = time.time() - jours * 86400 if jours else 0
        EXT = {"video": medias.VIDEO + tuple(medias.FERMES), "image": (".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".dng"),
               "audio": (".wav", ".mp3", ".flac", ".aac", ".m4a", ".ogg", ".bwf"), "pdf": (".pdf",), "doc": (".pdf", ".docx", ".doc", ".odt", ".xlsx", ".ods", ".txt", ".md", ".pptx")}.get(typ)
        titre = "Recherche : " + " ".join(x for x in (texte, {"video": "vidéos", "image": "photos", "audio": "sons", "pdf": "PDF", "doc": "documents"}.get(typ, ""), ("%d derniers jours" % jours) if jours else "") if x)
        self.etat.set_text(titre + "…")
        def tache():
            R = []
            for base in racines:
                for r, ds, fs in os.walk(base):
                    ds[:] = [d for d in ds if not d.startswith(".") and d not in ("node_modules", "__pycache__", "Trash")]
                    for x in fs:
                        if EXT and not x.lower().endswith(EXT): continue
                        nx = sans_accents(x.lower())
                        if mots and not all(m in nx or m in sans_accents(r.lower()) for m in mots): continue
                        p = os.path.join(r, x)
                        if lim:
                            try:
                                if os.stat(p).st_mtime < lim: continue
                            except OSError: continue
                        R.append(p)
                    if len(R) > 800: return R
            return R
        S.en_fond(tache, lambda R: self.montrer_liste(R if isinstance(R, list) else [], titre))

    def raccourcis(self):
        k = Gtk.EventControllerKey(); k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        def touche(c, kv, code, st):
            ctrl = st & Gdk.ModifierType.CONTROL_MASK; alt = st & Gdk.ModifierType.ALT_MASK
            focus_saisie = isinstance(self.win.get_focus(), Gtk.Text)
            if focus_saisie and not ctrl: return False
            sel = self.selection()
            if ctrl and kv in (Gdk.KEY_c, Gdk.KEY_C) and sel: self.memoriser(sel, False); return True
            if ctrl and kv in (Gdk.KEY_x, Gdk.KEY_X) and sel: self.memoriser(sel, True); return True
            if ctrl and kv in (Gdk.KEY_v, Gdk.KEY_V): self.coller(self.dossier); return True
            if ctrl and kv in (Gdk.KEY_h, Gdk.KEY_H): self.basculer_caches(); return True
            if ctrl and kv in (Gdk.KEY_l, Gdk.KEY_L): self.saisir_chemin(); return True
            if ctrl and kv in (Gdk.KEY_f, Gdk.KEY_F): self.recherche.grab_focus(); return True
            if ctrl and kv == Gdk.KEY_N: self.nouveau_dossier(); return True
            if ctrl and kv in (Gdk.KEY_t, Gdk.KEY_T): self.nouvel_onglet(sel[0] if sel and os.path.isdir(sel[0]) else self.dossier); return True
            if ctrl and kv in (Gdk.KEY_w, Gdk.KEY_W): self.fermer_onglet(self.i_onglet) if len(self.onglets) > 1 else self.win.close(); return True
            if ctrl and kv in (Gdk.KEY_Tab, Gdk.KEY_Page_Down): self.changer_onglet((self.i_onglet + 1) % len(self.onglets)); return True
            if ctrl and kv in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Page_Up): self.changer_onglet((self.i_onglet - 1) % len(self.onglets)); return True
            if kv == Gdk.KEY_F3: self.basculer_double(); return True
            if kv == Gdk.KEY_Delete and sel: self.corbeille(sel); return True
            if kv == Gdk.KEY_F2 and sel: (self.renommer_lot(sel) if len(sel) > 1 else self.renommer(sel[0])); return True
            if kv == Gdk.KEY_F5: self.recharger(); return True
            if kv == Gdk.KEY_space and sel and not focus_saisie: S.detacher(["xiii-apercu", sel[0]]); return True
            if alt and kv == Gdk.KEY_Left or kv == Gdk.KEY_BackSpace and not focus_saisie: self.precedent(); return True
            if alt and kv == Gdk.KEY_Right: self.suivant(); return True
            if alt and kv == Gdk.KEY_Up: self.parent(); return True
            if kv == Gdk.KEY_Escape and self.saisie.get_visible(): self.fin_saisie(); return True
            return False
        k.connect("key-pressed", touche); self.win.add_controller(k)

def main():
    sys.exit(Fichiers().run(sys.argv))
