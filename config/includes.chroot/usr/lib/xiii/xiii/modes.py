# OS XIII — modes d'utilisation (sélecteur en haut au centre) : Classique, Production, Fiction, Multicam, Backup, Gaming.
# Chaque mode (sauf Classique) remplace le bureau par une vue plein écran derrière les fenêtres, et peut appliquer
# un profil de travail (Tournage pour Fiction / Multicam, Jeu pour Gaming).
# Application développée par Matthieu Lamotte.
import os, json, glob, shutil, time, threading, datetime, urllib.request, re
import gi
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from gi.repository import Gtk4LayerShell as LS
from . import config, apps, systeme as S
from .ui import *

MODES = [  # clé, nom, icône, description, profil appliqué
    ("classique", "Classique", "monitor", "Bureau et usage habituel de l'ordinateur", None),
    ("production", "Production", "layout-dashboard", "Tableau de bord des outils de production, façon accueil de la Suite XIII", None),
    ("fiction", "Fiction", "clapperboard", "Tuiles pour le tournage fiction : timecode, SCRIPTO et outils du plateau", "tournage"),
    ("multicam", "Multicam", "cctv", "Tuiles pour le direct multicaméra : timecode, CONDUCO, MELANGO, GRAPHICO, tally", "tournage"),
    ("backup", "Backup", "hard-drive-download", "Déchargement des cartes : copie, vérification par checksum, rapport BACKUPO", None),
    ("gaming", "Gaming", "gamepad-2", "Façon console : Steam Big Picture, émulateurs, jeux", "jeu"),
]
PAR_CLE = {m[0]: m for m in MODES}

# outils proposés par mode : (type, id, nom, icône) — type suite = outil de la Suite XIII, app = .desktop, cmd = commande
OUTILS = {
    "production": [("suite", "index", "Suite XIII", None), ("suite", "documents", "Documents", None), ("suite", "plano", "PLANO", None), ("suite", "syno", "SYNO", None),
                   ("suite", "deviso", "DEVISO", None), ("suite", "callsheeto", "CALL SHEETO", None), ("suite", "decoup", "DECOUP", None), ("suite", "planno", "PLANNO", None),
                   ("suite", "casto", "CASTO", None), ("suite", "matos", "MATOS", None), ("suite", "dossier", "DOSSIER", None), ("suite", "encodo", "ENCODO", None),
                   ("app", "xiii-blackmagic.desktop", "Blackmagic", "video"), ("app", "xiii-tally.desktop", "Tally XIII", None)],
    "fiction": [("suite", "scripto", "SCRIPTO", None), ("suite", "callsheeto", "CALL SHEETO", None), ("suite", "decoup", "DECOUP", None), ("suite", "cadro", "CADRO", None),
                ("suite", "storyboardo", "STORYBOARDO", None), ("suite", "repero", "REPERO", None), ("suite", "sono", "SONO", None), ("suite", "lumo", "LUMO", None),
                ("suite", "backupo", "BACKUPO", None), ("app", "xiii-timecode.desktop", "Timecode LTC", None)],
    "multicam": [("suite", "conduco", "CONDUCO", None), ("suite", "melango", "MELANGO", None), ("suite", "graphico", "GRAPHICO", None), ("suite", "runo", "RUNO", None),
                 ("app", "xiii-tally.desktop", "Tally XIII", None), ("app", "xiii-retour.desktop", "Retour plateau", None), ("app", "xiii-ndi.desktop", "NDI XIII", None),
                 ("app", "xiii-blackmagic.desktop", "Blackmagic", "video"), ("app", "xiii-terminal.desktop", "Invite de commande", None), ("app", "xiii-timecode.desktop", "Timecode LTC", None)],
}
ONGLETS = {"fiction": ["scripto", "callsheeto", "decoup", "cadro"], "multicam": ["conduco", "melango", "graphico", "runo"]}
WIDGETS = {"production": ["projet", "plan", "meteo", "offload"], "fiction": ["timecode", "plan", "meteo", "projet"], "multicam": ["timecode", "conducteur", "ndi", "duo"]}

def lancer_outil(t, i):
    if t == "suite": S.detacher(["xiii-suite", i])
    elif t == "app":
        a = apps.par_id(i)
        if a: apps.lancer(a)
        elif i == "xiii-blackmagic.desktop": S.detacher(["xiii-parametres", "--page", "acquisition"])
    else: S.detacher(i)

def icone_outil(t, i, ic, taille=40):
    if t == "suite":
        return gicon_image(Gio.ThemedIcon.new("xiii-suite-" + i if i != "index" else "xiii-suite"), taille)
    a = apps.par_id(i) if t == "app" else None
    if a and a.get_icon(): return gicon_image(a.get_icon(), taille)
    return ico(ic or "app-window", taille, "c")


class VueMode:
    """Surface plein écran (couche du bureau) qui affiche le mode choisi."""
    def __init__(self, shell):
        self.shell = shell; self.mode = None; self._src = 0; self.tab = None
        w = Gtk.Window(application=shell); self.w = w
        LS.init_for_window(w); LS.set_namespace(w, "xiii-mode"); LS.set_layer(w, LS.Layer.BOTTOM)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(w, e, True)
        LS.set_exclusive_zone(w, 0); LS.set_keyboard_mode(w, LS.KeyboardMode.ON_DEMAND); w.add_css_class("xiii-surface")
        self.corps = boite(True, 16, "vue-mode"); w.set_child(self.corps)
        self.backup = None

    def appliquer(self, mode):
        mode = mode if mode in PAR_CLE else "classique"
        if mode == self.mode: return
        self.mode = mode; self.arreter()
        if mode == "classique":
            self.w.set_visible(False); return
        vider(self.corps)
        getattr(self, "v_" + ("tuiles" if mode in ("production", "fiction", "multicam") else mode))(mode)
        self.w.present()

    def arreter(self):
        if self._src: GLib.source_remove(self._src); self._src = 0

    # ----------------------------------------------------------------- en-tête commun
    def entete(self, mode, droite=None):
        _, nom, ic, desc, _p = PAR_CLE[mode]
        h = boite(False, 14, margin_start=28, margin_end=28, margin_top=18)
        h.append(ico(ic, 34, "c"))
        v = boite(True, 0, hexpand=True); v.append(label(nom, "grand-titre", "titre-astoria")); v.append(label(desc, "attenue")); h.append(v)
        pj = self.shell.cfg.get("projet_actif")
        if pj:
            from . import projets
            pv = boite(True, 2, valign=Gtk.Align.CENTER)
            pv.append(bouton(pj, "folder-kanban", "fantome", rappel=lambda: self.shell.menu_projets()))
            r = projets.resume(pj)     # fiche venue de la Suite : dates de tournage, lieu, client
            if r: pv.append(label(r, "petit", "attenue", xalign=1, ellipsize=True, largeur=48))
            h.append(pv)
        if droite: h.append(droite)
        self.corps.append(h)

    # ----------------------------------------------------------------- Production / Fiction / Multicam
    def v_tuiles(self, mode):
        tc = None
        if mode in ("fiction", "multicam"):
            tc = label("--:--:--:--", "timecode-geant"); self.entete(mode, tc)
        else:
            self.entete(mode)
        sc = Gtk.ScrolledWindow(vexpand=True); cont = boite(True, 18, margin_start=28, margin_end=28, margin_bottom=24); sc.set_child(cont); self.corps.append(sc)
        # onglets des outils principaux (un clic : l'outil passe au premier plan, ou s'ouvre)
        if mode in ONGLETS:
            ong = boite(False, 6, "onglets-mode")
            for i in ONGLETS[mode]:
                b = Gtk.Button(); b.add_css_class("onglet-mode")
                bx = boite(False, 8); bx.append(icone_outil("suite", i, None, 18)); bx.append(label(i.upper() if i != "callsheeto" else "CALL SHEETO", "gras")); b.set_child(bx)
                b.connect("clicked", lambda _b, i=i: (self.marquer(ong, _b), lancer_outil("suite", i))); ong.append(b)
            cont.append(ong)
        # tuiles d'outils
        cont.append(label("Outils", "section"))
        g = Gtk.FlowBox(max_children_per_line=8, min_children_per_line=3, selection_mode=Gtk.SelectionMode.NONE, column_spacing=12, row_spacing=12, homogeneous=True)
        epingles = self.shell.cfg.get("mode_epingles", {}).get(mode, [])
        for t, i, nom, ic in OUTILS.get(mode, []) + [("app", e, None, None) for e in epingles]:
            a = apps.par_id(i) if t == "app" else None
            if t == "app" and not a and i != "xiii-blackmagic.desktop": continue
            g.append(self.tuile(mode, t, i, nom or (a.get_display_name() if a else i), ic, i in epingles))
        plus = Gtk.Button(); plus.add_css_class("tuile-mode"); plus.add_css_class("tuile-plus")
        pv = boite(True, 8, valign=Gtk.Align.CENTER); pv.append(ico("plus", 34, "d")); pv.append(label("Épingler une app", "petit", "attenue", xalign=0.5)); plus.set_child(pv)
        plus.connect("clicked", lambda b: self.choisir_app(b, mode)); g.append(plus)
        cont.append(g)
        # widgets utiles
        from .widgets import Tableau
        tb = Tableau(self.shell); self.tb = tb
        cont.append(label("En direct", "section"))
        gw = Gtk.FlowBox(max_children_per_line=4, min_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE, column_spacing=12, row_spacing=12, homogeneous=True)
        for k in WIDGETS.get(mode, []):
            fn = getattr(tb, "w_" + k, None)
            if fn:
                try: gw.append(fn())
                except Exception as e: gw.append(tb.carte(k, k, "circle-alert", label(str(e), "attenue", "petit", wrap=True)))
        cont.append(gw)
        def tic():
            try: tb.tic()
            except Exception: pass
            if tc is not None:
                from . import ltc
                t = ltc.lire_partage(1.0)
                if not t:
                    n = time.time(); lt = time.localtime(n); fps = int(self.shell.cfg.get("timecode_fps", 25)) or 25
                    t = "%02d:%02d:%02d:%02d" % (lt.tm_hour, lt.tm_min, lt.tm_sec, int((n % 1) * fps))
                tc.set_text(t)
            return True
        self._src = GLib.timeout_add(80 if tc is not None else 2000, tic); tic()

    def marquer(self, ong, b):
        c = ong.get_first_child()
        while c: c.remove_css_class("actif"); c = c.get_next_sibling()
        b.add_css_class("actif")

    def tuile(self, mode, t, i, nom, ic, epinglee):
        b = Gtk.Button(); b.add_css_class("tuile-mode")
        v = boite(True, 8, valign=Gtk.Align.CENTER); v.append(icone_outil(t, i, ic, 40)); v.append(label(nom, "gras", xalign=0.5, ellipsize=True)); b.set_child(v)
        b.connect("clicked", lambda *_: lancer_outil(t, i))
        if epinglee:
            clic_droit(b, lambda: popover_menu(b, [("pin-off", "Désépingler de ce mode", lambda: self.epingler(mode, i, False))]))
        return b

    def epingler(self, mode, i, on):
        d = dict(self.shell.cfg.get("mode_epingles", {})); L = list(d.get(mode, []))
        if on and i not in L: L.append(i)
        if not on and i in L: L.remove(i)
        d[mode] = L; config.modifier(mode_epingles=d)
        GLib.timeout_add(300, lambda: (self.recharger(), False)[1])

    def recharger(self):
        m = self.mode; self.mode = None; self.appliquer(m)

    def choisir_app(self, ancre, mode):
        pop = Gtk.Popover(); pop.set_parent(ancre)
        v = boite(True, 6, margin_top=8, margin_bottom=8, margin_start=8, margin_end=8); v.set_size_request(320, 420)
        e = Gtk.SearchEntry(placeholder_text="Rechercher une application"); v.append(e)
        sc = Gtk.ScrolledWindow(vexpand=True); lst = boite(True, 2); sc.set_child(lst); v.append(sc)
        def remplir(*_):
            vider(lst); q = sans_accents(e.get_text().lower())
            for a in apps.toutes():
                if q and q not in sans_accents(a.get_display_name().lower()): continue
                b = Gtk.Button(); b.add_css_class("ligne"); b.add_css_class("plat")
                bx = boite(False, 8); bx.append(gicon_image(a.get_icon(), 22)); bx.append(label(a.get_display_name(), ellipsize=True)); b.set_child(bx)
                b.connect("clicked", lambda _b, a=a: (pop.popdown(), self.epingler(mode, a.get_id(), True))); lst.append(b)
        e.connect("search-changed", remplir); remplir()
        pop.set_child(v); pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1])); pop.popup()

    # ----------------------------------------------------------------- Backup
    def v_backup(self, mode):
        from . import backup as B
        if not self.backup: self.backup = B.Moteur(self.shell)
        self.entete(mode)
        corps = boite(False, 18, margin_start=28, margin_end=28, margin_bottom=24, vexpand=True)
        # arborescence de la destination
        gauche = boite(True, 8, "panneau"); gauche.set_size_request(340, -1)
        gauche.append(label("Destination", "section"))
        dest = self.backup.destination()
        ld = label(dest.replace(os.path.expanduser("~"), "~"), "petit", "attenue", ellipsize=True); gauche.append(ld)
        gauche.append(bouton("Changer de destination…", "folder-cog", "fantome", rappel=lambda: self.backup.choisir_destination(lambda: self.recharger())))
        gauche.append(arbre(dest))
        corps.append(gauche)
        # supports, transferts, historique
        droite = boite(True, 12, hexpand=True)
        reg = boite(False, 10, "panneau")
        reg.append(label("Nom du transfert", "gras"))
        en = Gtk.Entry(text=self.backup.nom, placeholder_text="ex. J03_CAM-A", hexpand=True); en.connect("changed", lambda w: self.backup.set_nom(w.get_text())); reg.append(en)
        reg.append(label("Auto", "petit"))
        sw = Gtk.Switch(active=self.backup.auto, valign=Gtk.Align.CENTER); sw.connect("notify::active", lambda w, *_: self.backup.set_auto(w.get_active())); reg.append(sw)
        algos = ["xxh64", "md5", "sha256"]; dd = Gtk.DropDown.new_from_strings(["xxHash64", "MD5", "SHA-256"])
        dd.set_selected(algos.index(self.backup.algo) if self.backup.algo in algos else 0)
        dd.connect("notify::selected", lambda d, *_: self.backup.set_algo(algos[d.get_selected()])); reg.append(dd)
        droite.append(reg)
        droite.append(label("Supports branchés", "section"))
        self.zone_supports = boite(True, 8); droite.append(self.zone_supports)
        droite.append(label("Transferts", "section"))
        self.zone_transferts = boite(True, 8); droite.append(self.zone_transferts)
        sc = Gtk.ScrolledWindow(vexpand=True, hexpand=True); sc.set_child(droite); corps.append(sc)
        self.corps.append(corps)
        self.backup.vue = self; self.maj_backup()
        self._src = GLib.timeout_add(500, lambda: (self.maj_backup(), True)[1])

    def maj_backup(self):
        if self.mode != "backup" or not self.backup: return
        B = self.backup
        sup = B.supports()
        # rien n'est redessiné tant que rien ne change (pas de clignotement, moins de processeur)
        sig = repr(([(x["chemin"], x["utilise"] // 10 ** 7) for x in sup], [(t["etat"], round(t.get("fraction", 0), 3), t.get("texte")) for t in B.transferts[-8:]], B.auto))
        if sig == getattr(self, "_sig_backup", None): return
        self._sig_backup = sig
        vider(self.zone_supports)
        if not sup: self.zone_supports.append(label("Branchez une carte, un disque ou un SSD : il apparaît ici" + (" et le déchargement démarre seul." if B.auto else "."), "attenue"))
        for s in sup:
            r = boite(False, 10, "reglage"); r.append(ico("memory-stick" if s["amovible"] else "hard-drive", 22, "c"))
            col = boite(True, 0, hexpand=True); col.append(label(s["nom"], "gras")); col.append(label("%s · %s utilisés" % (s["chemin"], S.humain(s["utilise"])), "petit", "attenue")); r.append(col)
            en_cours = any(t["source"] == s["chemin"] and t["etat"] in ("copie", "verification") for t in B.transferts)
            r.append(bouton("En cours…" if en_cours else "Décharger", "download", "pilule", rappel=lambda s=s: B.demarrer(s)))
            self.zone_supports.append(r)
        vider(self.zone_transferts)
        if not B.transferts: self.zone_transferts.append(label("Aucun transfert pour l'instant.", "attenue"))
        for t in reversed(B.transferts[-8:]):
            c = boite(True, 6, "carte")
            h = boite(False, 8); h.append(ico({"copie": "copy", "verification": "shield-check", "fini": "circle-check", "erreur": "triangle-alert"}[t["etat"]], 18, "c" if t["etat"] != "erreur" else "d"))
            h.append(label("%s → %s" % (t["nom_support"], t["dossier"].replace(os.path.expanduser("~"), "~")), "gras", hexpand=True, ellipsize=True))
            if t["etat"] == "fini": h.append(bouton(None, "folder-open", "plat", tip="Ouvrir le dossier", rappel=lambda d=t["dossier"]: S.detacher(["thunar", d])))
            c.append(h)
            pb = Gtk.ProgressBar(fraction=t["fraction"], show_text=True); pb.set_text(t["texte"]); c.append(pb)
            self.zone_transferts.append(c)

    # ----------------------------------------------------------------- Gaming
    def v_gaming(self, mode):
        """Derrière la Console XIII (plein écran) : de quoi la rouvrir si on l'a quittée."""
        self.entete(mode)
        v = boite(True, 18, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, vexpand=True)
        b = Gtk.Button(); b.add_css_class("carte-jeu"); b.set_size_request(420, 280)
        c = boite(True, 14, valign=Gtk.Align.CENTER); c.append(ico("gamepad-2", 96, "c")); c.append(label("Console XIII", "grand-titre", "titre-astoria", xalign=0.5))
        c.append(label("Toutes vos consoles à la manette — Entrée pour ouvrir", "attenue", xalign=0.5)); b.set_child(c)
        b.connect("clicked", lambda *_: S.detacher("xiii-console")); v.append(b)
        v.append(label("Vos jeux vont dans le dossier Jeux de votre dossier personnel, une console par sous-dossier.", "petit", "attenue", xalign=0.5))
        self.corps.append(v); GLib.idle_add(lambda: (b.grab_focus(), False)[1])
        # en mode Gaming, la manette rouvre la console : A (sur cet écran) ou le bouton Accueil (partout)
        if not getattr(self, "manettes", None):
            try:
                from .manette import Manettes
                self.manettes = Manettes(self.pad)
            except Exception:
                self.manettes = None

    def pad(self, n):
        if self.mode != "gaming" or n not in ("a", "menu", "accueil"): return
        import subprocess
        if subprocess.run(["pgrep", "-f", "xiii.console"], capture_output=True).returncode == 0: return   # la console gère elle-même la manette
        S.detacher("xiii-console")

    def lichii(self):
        f = os.path.expanduser("~/.local/share/xiii/lichii/Lichii.AppImage")
        if os.path.exists(f): S.detacher([f]); return
        S.detacher(["notify-send", "-a", "Gaming", "-i", "download", "Installation de Lichii…", "Téléchargement de la dernière version depuis GitHub (zortos293/Lichii)."])
        def tache():
            req = urllib.request.Request("https://api.github.com/repos/zortos293/Lichii/releases", headers={"User-Agent": "OS-XIII"})
            for r in json.load(urllib.request.urlopen(req, timeout=30)):
                im = [a for a in r.get("assets", []) if a["name"].lower().endswith(".appimage") and not re.search(r"arm|aarch64", a["name"], re.I)]
                if im:
                    os.makedirs(os.path.dirname(f), exist_ok=True)
                    urllib.request.urlretrieve(im[0]["browser_download_url"], f + ".part"); os.chmod(f + ".part", 0o755); os.replace(f + ".part", f)
                    return r.get("tag_name") or "ok"
            return None
        def fin(r):
            if isinstance(r, str): S.detacher(["notify-send", "-a", "Gaming", "-i", "gamepad-2", "Lichii installé (%s)" % r, "Ajoutez vos propres clés et firmware au premier lancement."]); S.detacher([f])
            else: S.detacher(["notify-send", "-a", "Gaming", "-i", "dialog-warning", "Lichii : installation impossible", "Pas de version Linux publiée, ou pas de connexion Internet."])
        S.en_fond(tache, fin)


def arbre(racine):
    """Arborescence dépliable de la destination (dossiers seulement, jusqu'à 4 niveaux)."""
    sc = Gtk.ScrolledWindow(vexpand=True)
    lst = boite(True, 0)
    def ajouter(d, niveau, parent_box):
        try: enfants = sorted(x for x in os.listdir(d) if not x.startswith(".") and os.path.isdir(os.path.join(d, x)))
        except OSError: return
        for x in enfants[:200]:
            p = os.path.join(d, x)
            ligne = boite(False, 6, margin_start=12 * niveau)
            sous = boite(True, 0); sous.set_visible(False)
            tg = Gtk.ToggleButton(); tg.add_css_class("plat"); tg.set_child(ico("chevron-right", 12, "d"))
            def bascule(b, p=p, sous=sous, niveau=niveau):
                if b.get_active() and sous.get_first_child() is None: ajouter(p, niveau + 1, sous)
                sous.set_visible(b.get_active()); b.set_child(ico("chevron-down" if b.get_active() else "chevron-right", 12, "d"))
            tg.connect("toggled", bascule)
            ligne.append(tg if niveau < 4 else Gtk.Box(width_request=26)); ligne.append(ico("folder", 14, "c"))
            bl = Gtk.Button(); bl.add_css_class("plat"); bl.set_child(label(x, "petit", ellipsize=True)); bl.connect("clicked", lambda _b, p=p: S.detacher(["thunar", p])); ligne.append(bl)
            parent_box.append(ligne); parent_box.append(sous)
    ajouter(racine, 0, lst)
    if lst.get_first_child() is None: lst.append(label("Dossier vide.", "attenue", "petit"))
    sc.set_child(lst); return sc
