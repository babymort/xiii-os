# OS XIII — vue des tâches (Super+Tab), dispositions d'ancrage (Super+Z), coins actifs,
# historique du presse-papiers (Super+V), sélecteur d'émojis (Super+.).
# Application développée par Matthieu Lamotte.
import os, subprocess, unicodedata, shutil
import gi
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from gi.repository import Gtk4LayerShell as LS
from . import apps, config, systeme as S
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

    def nb_bureaux(self):
        try:
            import re
            t = open(os.path.expanduser("~/.config/labwc/rc.xml")).read()
            return max(1, min(6, int(re.search(r'<desktops number="(\d+)"', t).group(1))))
        except Exception:
            return 1

    def envoyer(self, f, n):
        """Glisser une fenêtre sur un bureau : on l'active puis on déclenche le raccourci labwc SendToDesktop."""
        self.fermer(); self.shell.fenetres.activer(f)
        from . import raccourcis
        GLib.timeout_add(250, lambda: (raccourcis.declencher("SendToDesktop", {"to": str(n)}, "W-A-S-%d" % n), False)[1])

    def aller(self, n):
        self.fermer()
        from . import raccourcis
        GLib.timeout_add(150, lambda: (raccourcis.declencher("GoToDesktop", {"to": str(n)}, "W-A-%d" % n), False)[1])

    def ouvrir(self):
        vider(self.corps); self.shell.vue_ouverte = True
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
            mp = self.shell.miniatures.chemin(f) if getattr(self.shell, "miniatures", None) else None
            if mp:
                pic = Gtk.Picture.new_for_filename(mp); pic.set_content_fit(Gtk.ContentFit.COVER); pic.set_size_request(240, 120); pic.add_css_class("miniature"); mid.append(pic)
            else:
                mid.append(gicon_image(a.get_icon(), 56) if a else ico("app-window", 56, "c"))
            mid.append(label(f.titre or "", "attenue", "petit", xalign=0.5, ellipsize=True, largeur=30))
            if f.reduite: mid.append(label("réduite", "accent", "petit", xalign=0.5))
            c.append(mid)
            gc = Gtk.GestureClick(); gc.connect("released", lambda *_a, f=f: (self.fermer(), self.shell.fenetres.activer(f))); c.add_controller(gc)
            ds = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            ds.connect("prepare", lambda *_a, f=f: Gdk.ContentProvider.new_for_value(str(f.id)))
            c.add_controller(ds)
            g.append(c)
        self.corps.append(g)
        from . import bureaux as BX
        n, noms = BX.lire(); cour = getattr(self.shell, "bureau_courant", 1)
        rang = boite(False, 12, halign=Gtk.Align.CENTER)
        for i in range(1, n + 1):
            p = boite(True, 4, "panneau", "bureau-puce"); p.set_size_request(160, 84)
            if i == cour: p.add_css_class("vue-active")
            fb = (self.shell.cfg.get("fonds_bureaux") or {}).get(str(i))
            if fb and os.path.exists(fb): p.append(vignette(fb, 120, 40))
            else: p.append(ico("layout-dashboard", 20, "c"))
            p.append(label(noms[i - 1], "gras", "petit", xalign=0.5, ellipsize=True, largeur=18))
            p.set_tooltip_text("Clic : aller sur ce bureau · clic droit : renommer, fond d'écran · glisser une fenêtre ici pour l'y déplacer")
            dt = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
            def depose(cible, val, x, y, i=i):
                f = next((w for w in fen if str(w.id) == val), None)
                if f: self.envoyer(f, i)
                return bool(f)
            dt.connect("drop", depose)
            dt.connect("enter", lambda *_a, p=p: (p.add_css_class("survol-depot"), Gdk.DragAction.MOVE)[1])
            dt.connect("leave", lambda *_a, p=p: p.remove_css_class("survol-depot"))
            p.add_controller(dt)
            gp = Gtk.GestureClick(); gp.connect("released", lambda *_a, i=i: self.aller(i)); p.add_controller(gp)
            clic_droit_w(p, lambda w, i=i, n=n: self.menu_bureau(w, i, n))
            rang.append(p)
        if n < BX.MAXI:
            plus = Gtk.Button(); plus.add_css_class("panneau"); plus.add_css_class("bureau-puce"); plus.set_size_request(84, 84)
            plus.set_child(ico("plus", 24, "c")); plus.set_tooltip_text("Nouveau bureau (Ctrl + Super + D)")
            plus.connect("clicked", lambda *_: (BX.ajouter(), GLib.timeout_add(400, lambda: (self.ouvrir(), False)[1])))
            rang.append(plus)
        self.corps.append(rang)
        aide = label("Clic : aller à la fenêtre · glisser sur un bureau : l'y déplacer · clic droit sur un bureau : renommer, fond · ✕ : fermer · Échap : quitter", "attenue", "petit", xalign=0.5)
        self.corps.append(aide)
        self.w.present()

    def fermer(self):
        self.w.set_visible(False); self.shell.vue_ouverte = False

    def menu_bureau(self, w, i, n):
        from . import bureaux as BX
        def renommer():
            pop = Gtk.Popover(); pop.set_parent(w); e = Gtk.Entry(text=BX.lire()[1][i - 1], width_chars=18)
            e.connect("activate", lambda *_: (BX.renommer(i, e.get_text()), pop.popdown(), GLib.timeout_add(300, lambda: (self.ouvrir(), False)[1])))
            pop.set_child(e); pop.connect("closed", lambda p_: GLib.idle_add(lambda: (p_.unparent(), False)[1])); pop.popup(); e.grab_focus()
        def fond():
            self.fermer()                          # le sélecteur de fichiers s'ouvrirait sous la Vue des tâches
            d = Gtk.FileDialog(title="Fond d'écran du bureau %d" % i)
            f = Gtk.FileFilter(); f.set_name("Images"); f.add_mime_type("image/*"); fl = Gio.ListStore.new(Gtk.FileFilter); fl.append(f); d.set_filters(fl)
            try: d.set_initial_folder(Gio.File.new_for_path("/usr/share/xiii/wallpapers"))
            except Exception: pass
            def fini(dd, res):
                try: g = dd.open_finish(res)
                except Exception: return
                F = dict(self.shell.cfg.get("fonds_bureaux") or {}); F[str(i)] = g.get_path()
                self.shell.cfg = config.modifier(_histo=False, fonds_bureaux=F); self.shell.services()
                S.detacher(["notify-send", "-a", "OS XIII", "-i", "image", "-t", "2500", "Fond du bureau %d" % i, os.path.basename(g.get_path())])
            d.open(None, None, fini)
        def sans_fond():
            F = dict(self.shell.cfg.get("fonds_bureaux") or {}); F.pop(str(i), None)
            self.shell.cfg = config.modifier(_histo=False, fonds_bureaux=F); self.shell.services(); self.ouvrir()
        items = [("pencil", "Renommer", renommer), ("image", "Fond d'écran de ce bureau…", fond)]
        if str(i) in (self.shell.cfg.get("fonds_bureaux") or {}): items.append(("image-off" if os.path.exists("/usr/share/xiii/lucide/image-off.svg") else "image", "Même fond que les autres bureaux", sans_fond))
        if i == n and n > 1: items += [None, ("trash-2", "Retirer ce bureau (ses fenêtres passent sur le précédent)", lambda: (BX.retirer(), self.shell.bureau_change(BX.courant()), GLib.timeout_add(400, lambda: (self.ouvrir(), False)[1])))]
        popover_menu(w, items)

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
        h.append(bouton(None, "smartphone", "fantome", tip="Partager avec le téléphone (QR code)", rappel=lambda: (self.shell.fermer(), S.detacher("xiii-presse-telephone"))))
        h.append(bouton("Tout effacer", None, "fantome", rappel=lambda: (S.sh(["cliphist", "wipe"]), self.rafraichir())))
        self.widget.append(h)
        self.liste = boite(True, 4); sc = defilant(self.liste); sc.set_vexpand(True); self.widget.append(sc)
        self.widget.append(label("Super + V · clic : copier · le texte est prêt à coller (Ctrl + V)", "attenue", "petit"))

    def rafraichir(self):
        vider(self.liste)
        import hashlib
        DOS = os.path.join(GLib.get_user_data_dir(), "xiii", "presse"); os.makedirs(DOS, exist_ok=True)
        cache = os.path.join(GLib.get_user_cache_dir(), "xiii", "presse"); os.makedirs(cache, exist_ok=True)
        def copier_texte(t): Gdk.Display.get_default().get_clipboard().set_text(t)
        def copier_image(f): subprocess.Popen(["sh", "-c", "wl-copy --type image/png < " + _q(f)])
        def epingler(el):
            L = [x for x in self.shell.cfg.get("presse_epingles", []) if x != el] + [el]
            self.shell.cfg = config.modifier(_histo=False, presse_epingles=L[-30:]); self.rafraichir()
        def desepingler(el):
            self.shell.cfg = config.modifier(_histo=False, presse_epingles=[x for x in self.shell.cfg.get("presse_epingles", []) if x != el]); self.rafraichir()
        # ---- épinglés (gardés même après « Tout effacer » et redémarrage)
        ep = list(self.shell.cfg.get("presse_epingles", []))
        if ep:
            self.liste.append(label("Épinglés", "section"))
            for el in reversed(ep):
                img = el.get("img") if isinstance(el, dict) else None
                txt = el.get("t", "") if isinstance(el, dict) else str(el)
                r = boite(False, 6)
                b = Gtk.Button(hexpand=True); b.add_css_class("ligne"); b.add_css_class("plat")
                bx = boite(False, 10)
                if img and os.path.exists(img):
                    p = vignette(img, 120, 68); bx.append(p); bx.append(label("Image épinglée", "attenue", "petit"))
                else:
                    bx.append(ico("pin", 16, "c")); bx.append(label(txt.strip()[:160], ellipsize=True, largeur=40, hexpand=True))
                b.set_child(bx)
                b.connect("clicked", lambda _b, img=img, txt=txt: ((copier_image(img) if img else copier_texte(txt)), self.shell.fermer()))
                r.append(b); r.append(bouton(None, "pin-off", "plat", taille=14, role="d", tip="Désépingler", rappel=lambda el=el: desepingler(el)))
                self.liste.append(r)
            self.liste.append(label("Historique", "section"))
        if S.DEMO:
            lignes = ["1\tSTUDIO-XIII / 192.168.10.20", "2\tConducteur captation — 20:30", "3\t[[ binary data 230 KiB png 1600x900 ]]", "4\thttps://suite-xiii.netlify.app/"]
        else:
            lignes = S.out(["cliphist", "list"]).splitlines()[:60]
        if not lignes:
            self.liste.append(label("L'historique est vide. Copiez du texte ou une image.", "attenue", "petit", wrap=True)); return
        n_img = 0
        for l in lignes:
            ident, _, txt = l.partition("\t")
            image = txt.startswith("[[ binary data")
            r = boite(False, 6)
            b = Gtk.Button(hexpand=True); b.add_css_class("ligne"); b.add_css_class("plat")
            bx = boite(False, 10)
            fimg = None
            if image and n_img < 8 and not S.DEMO:          # miniatures des images copiées (8 plus récentes)
                fimg = os.path.join(cache, hashlib.md5(l.encode()).hexdigest() + ".png")
                if not os.path.exists(fimg): subprocess.run("printf '%s' " + _q(l) + " | cliphist decode > " + _q(fimg), shell=True, timeout=5)
                if os.path.getsize(fimg) > 0: bx.append(vignette(fimg, 120, 68)); n_img += 1
                else: fimg = None
            if not fimg: bx.append(ico("image" if image else "type", 16, "d"))
            bx.append(label("Image copiée" + txt.split("png")[-1].replace("]]", "") if image else txt.strip()[:160], ellipsize=True, largeur=40, hexpand=True))
            b.set_child(bx)
            b.connect("clicked", lambda _b, l=l: (subprocess.run("printf '%s' " + _q(l) + " | cliphist decode | wl-copy", shell=True), self.shell.fermer()))
            r.append(b)
            def ep_ligne(l=l, image=image, txt=txt, fimg=fimg):
                if image:
                    f = fimg or os.path.join(cache, hashlib.md5(l.encode()).hexdigest() + ".png")
                    if not fimg: subprocess.run("printf '%s' " + _q(l) + " | cliphist decode > " + _q(f), shell=True, timeout=5)
                    dest = os.path.join(DOS, os.path.basename(f)); shutil.copy(f, dest); epingler({"img": dest})
                else:
                    epingler({"t": S.out(["sh", "-c", "printf '%s' " + _q(l) + " | cliphist decode"], 3) or txt})
            r.append(bouton(None, "pin", "plat", taille=14, role="d", tip="Épingler (gardé même après effacement)", rappel=ep_ligne))
            self.liste.append(r)

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


# ================================================================================ ALT + TAB (vignettes, logo en haut)
class AltTab:
    """Alt + Tab : même fonctionnement (Alt maintenu, Tab pour avancer, relâcher Alt pour choisir), mais en grandes cartes :
    logo de l'appli en haut, nom, aperçu de la fenêtre. Maj + Tab ou ← pour reculer, Échap pour annuler, clic pour choisir."""
    def __init__(self, shell):
        self.shell = shell; self.w = None; self.fen = []; self.i = 0; self.cartes = []; self.mru = []

    def noter_active(self, fen):
        """Ordre « dernière utilisée d'abord » (comme Windows)."""
        a = next((f for f in fen if f.active), None)
        if a:
            self.mru = [a.id] + [x for x in self.mru if x != a.id]
        ids = {f.id for f in fen}; self.mru = [x for x in self.mru if x in ids]

    def ouvrir(self, sens=1):
        if self.w and self.w.get_visible():
            self.deplacer(sens); return
        fen = self.shell.fenetres.liste() if self.shell.fenetres and self.shell.fenetres.ok else []
        if not fen: return
        rang = {x: n for n, x in enumerate(self.mru)}
        self.fen = sorted(fen, key=lambda f: (0 if f.active else 1, rang.get(f.id, 999)))
        self.i = (1 if len(self.fen) > 1 else 0) if sens > 0 else len(self.fen) - 1
        if not self.w:
            self.w = surface(self.shell, "xiii-alttab", ancres="", exclusif=None)
            k = Gtk.EventControllerKey(); k.connect("key-pressed", self._touche); k.connect("key-released", self._relache); self.w.add_controller(k)
            self.w.connect("notify::is-active", self._focus)
        self.construire(); self.w.present()
        # sans le clavier au bout de 0,7 s (aucune touche reçue), la liste ne reste pas affichée
        GLib.timeout_add(700, lambda: (self.fermer() if self.w.get_visible() and not self.w.is_active() and not getattr(self, "_src", 0) else None, False)[1])

    def construire(self):
        bx = boite(False, 14, "panneau", "alttab"); self.cartes = []
        for n, f in enumerate(self.fen):
            a = apps.pour_fenetre(f.app_id)
            c = boite(True, 8, "alttab-carte"); c.set_size_request(240, -1)
            # en haut : petit logo + nom de l'appli (comme Windows) ; dessous : l'aperçu de la fenêtre prend la place
            h = boite(False, 8); h.append(gicon_image(a.get_icon(), 20) if a else ico("app-window", 20, "c"))
            h.append(label(a.get_display_name() if a else (f.app_id or "Application"), "gras", "petit", hexpand=True, ellipsize=True, largeur=22)); c.append(h)
            mp = self.shell.miniatures.chemin(f) if getattr(self.shell, "miniatures", None) else None
            if mp:
                pic = Gtk.Picture.new_for_filename(mp); pic.set_content_fit(Gtk.ContentFit.COVER); pic.set_size_request(224, 126); pic.add_css_class("miniature"); c.append(pic)
            else:       # pas encore d'aperçu : cadre de la même taille avec le titre de la fenêtre
                ph = boite(True, 6, "alttab-vide", valign=Gtk.Align.CENTER); ph.set_size_request(224, 126)
                ph.append(label(f.titre or "", "attenue", xalign=0.5, wrap=True, largeur=26)); c.append(ph)
            if mp: c.append(label(f.titre or "", "petit", "attenue", xalign=0, ellipsize=True, largeur=28))
            g = Gtk.GestureClick(); g.connect("released", lambda *_a, n=n: (setattr(self, "i", n), self.choisir())); c.add_controller(g)
            self.cartes.append(c); bx.append(c)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC, vscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_width=True, propagate_natural_height=True)
        sc.set_max_content_width(1500); sc.set_child(bx); self.w.set_child(sc); self.marquer()

    def marquer(self):
        for n, c in enumerate(self.cartes): (c.add_css_class if n == self.i else c.remove_css_class)("alttab-sel")

    def deplacer(self, sens):
        if self.fen: self.i = (self.i + sens) % len(self.fen); self.marquer()

    def choisir(self):
        f = self.fen[self.i] if 0 <= self.i < len(self.fen) else None
        self.fermer()
        if f: self.shell.fenetres.activer(f)

    def fermer(self):
        if getattr(self, "_src", 0): GLib.source_remove(self._src); self._src = 0
        if self.w: self.w.set_visible(False)

    def _alt_tenu(self):
        try:
            kb = self.w.get_display().get_default_seat().get_keyboard()
            return bool(kb.get_modifier_state() & Gdk.ModifierType.ALT_MASK)
        except Exception:
            return None

    def _focus(self, w, _p):
        # surveillance de la touche Alt tant que la liste est affichée : relâchée (même très vite, ou avant l'apparition) = on choisit
        if not w.is_active() or getattr(self, "_src", 0): return
        self._t0 = GLib.get_monotonic_time()
        def veille():
            if not self.w.get_visible(): self._src = 0; return False
            tenu = self._alt_tenu()
            if tenu is False: self._src = 0; self.choisir(); return False
            if tenu is None and GLib.get_monotonic_time() - self._t0 > 4_000_000: self._src = 0; self.fermer(); return False   # état du clavier inconnu : on ne reste pas bloqué
            return True
        self._src = GLib.timeout_add(80, veille)

    def _touche(self, c, kv, code, st):
        if kv == Gdk.KEY_Escape: self.fermer(); return True
        if kv in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space): self.choisir(); return True
        if kv in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Left) or (kv == Gdk.KEY_Tab and st & Gdk.ModifierType.SHIFT_MASK): self.deplacer(-1); return True
        if kv in (Gdk.KEY_Tab, Gdk.KEY_Right): self.deplacer(1); return True
        return False

    def _relache(self, c, kv, code, st):
        if kv in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Meta_L, Gdk.KEY_ISO_Level3_Shift): self.choisir()
