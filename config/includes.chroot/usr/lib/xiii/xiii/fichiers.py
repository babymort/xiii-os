# OS XIII — Fichiers XIII : l'explorateur aux couleurs de la Suite XIII, onglets sur le côté gauche, trois façons de voir :
#   • Windows : liste détaillée (nom, date, type, taille), tri par colonne
#   • Mac : colonnes en cascade (comme le Finder), aperçu du fichier dans la dernière colonne
#   • Arbre : arbre généalogique des dossiers, qu'on déplie branche par branche
# Cloud (~/Cloud) et NAS (~/Réseau) montés par Lecteurs réseau, clés et disques, corbeille.
# Application développée par Matthieu Lamotte.
import os, sys, shutil, threading, time, datetime, subprocess, json
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GObject, Pango
from . import config, systeme as S, apps
from .ui import *
from .appli import preparer

ATTR = "standard::*,time::modified,thumbnail::path"
VUES = [("windows", "Windows", "list"), ("mac", "Mac", "columns-3"), ("arbre", "Arbre", "network")]

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


class Fichiers(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.fichiers", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.histo = []; self.futur = []; self.presse = None; self.couper = False

    def do_command_line(self, cl):
        a = [x for x in cl.get_arguments()[1:] if not x.startswith("--")]
        d = Gio.File.new_for_commandline_arg_and_cwd(a[0], cl.get_cwd() or "/").get_path() if a else os.path.expanduser("~")
        if d and os.path.isfile(d): d = os.path.dirname(d)
        self.activer(); self.aller(d or os.path.expanduser("~"))
        return 0

    # =================================================================== fenêtre
    def activer(self):
        if getattr(self, "win", None): self.win.present(); return
        self.cfg = preparer("""
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
            .feuille { font-size: 11px; opacity: .8; padding: 2px 6px; }""")
        self.win = Gtk.ApplicationWindow(application=self, title="Fichiers"); self.win.set_default_size(1200, 760)
        racine = boite(False, 0)
        # ---- volet gauche (onglets, comme la Suite XIII)
        self.volet = boite(True, 2, "volet", "nav"); self.volet.set_size_request(220, -1)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); sc.set_child(self.volet); sc.set_hexpand(False)
        racine.append(sc); racine.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        # ---- droite
        d = boite(True, 0, hexpand=True)
        h = boite(False, 6, margin_start=10, margin_end=10, margin_top=8, margin_bottom=8)
        self.b_prec = bouton(None, "arrow-left", "plat", tip="Précédent (Alt+←)", rappel=self.precedent); h.append(self.b_prec)
        self.b_suiv = bouton(None, "arrow-right", "plat", tip="Suivant (Alt+→)", rappel=self.suivant); h.append(self.b_suiv)
        h.append(bouton(None, "arrow-up", "plat", tip="Dossier parent (Alt+↑)", rappel=self.parent))
        self.chemin = boite(False, 0, "barre-chemin", hexpand=True)
        self.saisie = Gtk.Entry(hexpand=True); self.saisie.set_visible(False)
        self.saisie.connect("activate", lambda e: (self.aller(os.path.expanduser(e.get_text())), self.fin_saisie()))
        h.append(self.chemin); h.append(self.saisie)
        self.recherche = Gtk.SearchEntry(placeholder_text="Rechercher dans ce dossier"); self.recherche.set_size_request(220, -1)
        self.recherche.connect("activate", lambda *_: self.chercher()); self.recherche.connect("stop-search", lambda *_: self.recharger()); h.append(self.recherche)
        vc = boite(False, 2, "vue-choix"); self.b_vues = {}
        for k, n, ic in VUES:
            b = Gtk.Button(); bx = boite(False, 5); bx.append(ico(ic, 14, "c")); bx.append(label(n, "petit")); b.set_child(bx); b.set_tooltip_text("Vue " + n)
            b.connect("clicked", lambda _b, k=k: self.changer_vue(k)); vc.append(b); self.b_vues[k] = b
        h.append(vc)
        h.append(bouton(None, "folder-plus", "plat", tip="Nouveau dossier (Ctrl+Maj+N)", rappel=self.nouveau_dossier))
        h.append(bouton(None, "ellipsis-vertical", "plat", tip="Plus", rappel=None)); h.get_last_child().connect("clicked", lambda b: popover_menu(b, self.menu_plus()))
        d.append(h); d.append(Gtk.Separator())
        self.pile = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE); d.append(self.pile)
        self.etat = label("", "petit", "attenue", margin_start=12, margin_bottom=6, margin_top=4); d.append(self.etat)
        racine.append(d); self.win.set_child(racine)
        self.construire_windows(); self.construire_mac(); self.construire_arbre()
        self.cachés = False; self.vue = config.charger().get("fichiers_vue", "windows")
        self.raccourcis(); self.remplir_volet()
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
        b.connect("clicked", lambda *_: S.detacher(["thunar", "trash:///"])); self.volet.append(b)
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
        self.b_prec.set_sensitive(bool(self.histo)); self.b_suiv.set_sensitive(bool(self.futur))
        self.barre_chemin(); self.marquer_volet(); self.recharger()

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
        for k, (n, c) in enumerate(parts):
            if k: self.chemin.append(label("›", "attenue"))
            b = Gtk.Button(); b.add_css_class("plat"); b.set_child(label(n, ellipsize=True, largeur=24)); b.connect("clicked", lambda _b, c=c: self.aller(c)); self.chemin.append(b)
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
        if self.vue == "windows":
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
        nom = col("Nom", lambda bx, i: (bx.append(icone_info(i)), bx.append(label(i.get_display_name(), ellipsize=True, hexpand=True))),
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
        if self.vue == "windows":
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
        def choisir(_lb, row):
            if not row: return
            self.choix = row._chemin
            # retire les colonnes à droite
            c = lb.get_parent().get_next_sibling() if isinstance(lb.get_parent(), Gtk.ScrolledWindow) else None
            while c: n = c.get_next_sibling(); self.mac_boite.remove(c); c = n
            if os.path.isdir(row._chemin):
                self.dossier = row._chemin; self.barre_chemin(); self.colonne_mac(row._chemin)
            else:
                self.apercu_mac(row._chemin)
            GLib.timeout_add(60, lambda: (self.mac_sc.get_hadjustment().set_value(self.mac_sc.get_hadjustment().get_upper()), False)[1])
        lb.connect("row-selected", choisir)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER); sc.set_child(lb); sc.set_size_request(240, -1)
        self.mac_boite.append(sc)

    def apercu_mac(self, p):
        v = boite(True, 10, margin_start=16, margin_end=16, margin_top=16); v.set_size_request(300, -1)
        ct = Gio.content_type_guess(p, None)[0] or ""
        if ct.startswith("image/"):
            pic = Gtk.Picture.new_for_filename(p); pic.set_size_request(260, 200); pic.set_content_fit(Gtk.ContentFit.CONTAIN); v.append(pic)
        else:
            v.append(gicon_image(apps.icone_fichier(p), 96))
        v.append(label(os.path.basename(p), "gras", wrap=True, xalign=0.5))
        try: st = os.stat(p); v.append(label("%s · %s" % (S.humain(st.st_size), datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")), "petit", "attenue", xalign=0.5))
        except OSError: pass
        v.append(label(Gio.content_type_get_description(ct) if ct else "", "petit", "attenue", xalign=0.5))
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
        if os.path.isfile(p):
            items.append(("eye", "Aperçu rapide (Espace)", lambda: S.detacher(["xiii-apercu", p])))
            try:
                for a in Gio.AppInfo.get_recommended_for_type(Gio.content_type_guess(p, None)[0])[:3]:
                    items.append(("app-window", "Ouvrir avec " + a.get_display_name(), lambda a=a: a.launch([Gio.File.new_for_path(p)], None)))
            except Exception: pass
        items += [None, ("scissors", "Couper (Ctrl+X)", lambda: self.memoriser(L, True)), ("copy", "Copier (Ctrl+C)", lambda: self.memoriser(L, False))]
        if self.presse and os.path.isdir(p): items.append(("clipboard-paste", "Coller dans ce dossier", lambda: self.coller(p)))
        items += [("text-cursor-input", "Renommer (F2)", lambda: self.renommer(p)), ("archive", "Compresser (.zip)", lambda: self.compresser(L)),
                  ("send", "Envoyer (Transferts XIII)", lambda: S.detacher(["xiii-transferts"] + L)), ("folder-input", "Envoyer à DOSSIER XIII", lambda: S.detacher(["xiii-suite", "--dossier"] + L)),
                  None, ("link", "Copier le chemin", lambda: Gdk.Display.get_default().get_clipboard().set_text("\n".join(L))),
                  ("trash-2", "Mettre à la corbeille (Suppr)", lambda: self.corbeille(L)), None,
                  ("square-terminal", "Ouvrir dans le terminal", lambda: S.detacher(["foot", "--app-id=fr.xiii.terminal", "-D", p if os.path.isdir(p) else os.path.dirname(p)])),
                  ("info", "Propriétés", lambda: S.detacher(["dbus-send", "--session", "--dest=org.xfce.FileManager", "--type=method_call", "/org/xfce/FileManager",
                                                            "org.xfce.FileManager.DisplayFileProperties", "string:" + uri, "string:", "string:"]))]
        return items

    def menu_dossier(self):
        L = [("folder-plus", "Nouveau dossier", self.nouveau_dossier), ("file-text", "Nouveau document texte", self.nouveau_texte)]
        if self.presse: L.append(("clipboard-paste", "Coller (Ctrl+V)", lambda: self.coller(self.dossier)))
        L += [None, ("refresh-cw", "Actualiser (F5)", self.recharger), ("square-terminal", "Ouvrir dans le terminal", lambda: S.detacher(["foot", "--app-id=fr.xiii.terminal", "-D", self.dossier])),
              ("share-2", "Partager ce dossier sur le réseau", lambda: S.detacher(["xiii-transferts", "--local", self.dossier]))]
        return L

    def menu_plus(self):
        return [(("eye-off" if self.cachés else "eye"), "Masquer les fichiers cachés" if self.cachés else "Afficher les fichiers cachés (Ctrl+H)", self.basculer_caches),
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
        if not L: return
        self.etat.set_text("%s de %d élément(s)…" % ("Déplacement" if deplacer else "Copie", len(L)))
        def tache():
            for p in L:
                b = os.path.basename(p.rstrip("/")); cible = os.path.join(dest, b); k = 2
                while os.path.exists(cible):
                    n, e = os.path.splitext(b); cible = os.path.join(dest, "%s (%d)%s" % (n, k, e) if os.path.isfile(p) else "%s (%d)" % (b, k)); k += 1
                if deplacer: shutil.move(p, cible)
                elif os.path.isdir(p): shutil.copytree(p, cible, symlinks=True)
                else: shutil.copy2(p, cible)
        S.en_fond(tache, lambda r: (self.etat.set_text("Erreur : %s" % r) if isinstance(r, Exception) else self.recharger()))

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
        self.etat.set_text("Recherche de « %s »…" % q); base = self.dossier
        def tache():
            R = []
            for r, ds, fs in os.walk(base):
                ds[:] = [d for d in ds if self.cachés or not d.startswith(".")]
                for x in ds + fs:
                    if q in x.lower(): R.append(os.path.join(r, x))
                if len(R) > 500: break
            return R
        def fin(R):
            if isinstance(R, Exception): return
            st = Gio.ListStore.new(Gio.FileInfo)
            for p in R:
                try: info = Gio.File.new_for_path(p).query_info(ATTR, Gio.FileQueryInfoFlags.NONE, None); info.set_attribute_object("standard::file", Gio.File.new_for_path(p)); st.append(info)
                except GLib.Error: pass
            self.pile.set_visible_child_name("windows")
            tri = Gtk.SortListModel.new(st, self.tri.get_sorter()); self.tri_recherche = tri
            sel = Gtk.MultiSelection.new(tri); self.cv.set_model(sel); self.mod_windows = sel; self.tri = tri
            self.etat.set_text("%d résultat(s) pour « %s » dans %s" % (len(R), q, base))
        S.en_fond(tache, fin)

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
            if kv == Gdk.KEY_Delete and sel: self.corbeille(sel); return True
            if kv == Gdk.KEY_F2 and sel: self.renommer(sel[0]); return True
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
