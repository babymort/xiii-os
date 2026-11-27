# OS XIII — plusieurs écrans : écran principal, barre des tâches sur chaque écran, un mode d'utilisation par écran.
# L'écran principal garde la barre du haut, la barre des tâches complète, les icônes du bureau et le mode choisi en haut.
# Les autres écrans ont leur barre des tâches (Démarrer, applis, heure) et leur propre mode (Classique, Production, Fiction,
# Multicam, Backup, Gaming) : par exemple Fiction sur l'écran principal et Multicam sur le second.
# Application développée par Matthieu Lamotte.
import datetime
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib
from gi.repository import Gtk4LayerShell as LS
from . import apps, config
from .ui import *

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def moniteurs():
    try:
        m = Gdk.Display.get_default().get_monitors()
        return [m.get_item(i) for i in range(m.get_n_items())]
    except Exception:
        return []


def nom(mon):
    try: return mon.get_connector() or ""
    except Exception: return ""


def description(mon):
    try: d = mon.get_description() or ""
    except Exception: d = ""
    if not d:
        d = " ".join(x for x in ((mon.get_manufacturer() or ""), (mon.get_model() or "")) if x).strip()
    return d or nom(mon)


class BarreEcran:
    """Barre des tâches d'un écran secondaire : Démarrer, applis, heure et date."""
    def __init__(self, ecrans, mon):
        self.ecrans = ecrans; self.sh = ecrans.sh; self.mon = mon; self.nom = nom(mon)
        w = Gtk.Window(application=self.sh); self.w = w
        LS.init_for_window(w); LS.set_namespace(w, "xiii-barre-ecran"); LS.set_layer(w, LS.Layer.TOP); LS.set_monitor(w, mon)
        LS.set_keyboard_mode(w, LS.KeyboardMode.NONE); w.add_css_class("xiii-surface")
        self.placer()
        cb = Gtk.CenterBox(); cb.add_css_class("barre")
        from .shell import HB
        cb.set_size_request(-1, HB)
        g = boite(False, 2)
        st = Gtk.Button(); st.add_css_class("tb"); st.set_tooltip_text("Démarrer")
        st.set_child(vignette("/usr/share/xiii/logos/xiii-orange.png", 27, 22, couvrir=False, echelle=1))
        st.connect("clicked", lambda *_: self.sh.basculer("demarrer")); g.append(st)
        self.taches = boite(False, 2); g.append(self.taches)
        cb.set_center_widget(g)
        d = boite(False, 2, margin_end=8)
        hb = Gtk.Button(); hb.add_css_class("tb"); v = boite(True, 0, valign=Gtk.Align.CENTER)
        self.l_h = label("", "horloge-h", xalign=1); self.l_d = label("", "horloge-d", xalign=1); v.append(self.l_h); v.append(self.l_d); hb.set_child(v)
        hb.connect("clicked", lambda *_: self.sh.basculer("volet")); d.append(hb)
        cb.set_end_widget(d); w.set_child(cb)
        self.tic(); self._src = GLib.timeout_add_seconds(5, self.tic)

    def placer(self):
        w = self.w
        haut = self.sh.position_barre() == "haut"
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
            LS.set_anchor(w, e, e in ((LS.Edge.TOP if haut else LS.Edge.BOTTOM), LS.Edge.LEFT, LS.Edge.RIGHT))
        LS.auto_exclusive_zone_enable(w)
        from .shell import HB
        w.set_default_size(1, HB)

    def tic(self):
        n = datetime.datetime.now(); c = self.sh.cfg
        self.l_h.set_text(n.strftime("%H:%M" if c.get("horloge_24h", True) else "%I:%M %p"))
        self.l_d.set_text("%d %s %d" % (n.day, MOIS[n.month - 1], n.year))
        return True

    def remplir(self, groupes):
        vider(self.taches)
        for cle, a, fs in groupes: self.taches.append(self.sh.bouton_tache(cle, a, fs))

    def detruire(self):
        if self._src: GLib.source_remove(self._src); self._src = 0
        self.w.destroy()


class Ecrans:
    def __init__(self, sh):
        self.sh = sh; self.barres = {}; self.vues = {}; self._principal = None; self._src = 0
        try: Gdk.Display.get_default().get_monitors().connect("items-changed", lambda *_: self.bientot())
        except Exception: pass

    def bientot(self, delai=900):
        if self._src: GLib.source_remove(self._src)
        def go():
            self._src = 0; self.maj(); return False
        self._src = GLib.timeout_add(delai, go)

    # ---------------------------------------------------------------- écrans
    def principal(self):
        L = moniteurs()
        if not L: return None
        voulu = self.sh.cfg.get("ecran_principal")
        m = next((m for m in L if nom(m) == voulu), None)
        if m is not None: return m
        # par défaut : l'écran intégré d'un portable, sinon celui le plus en haut à gauche
        integre = [m for m in L if nom(m).startswith(("eDP", "LVDS", "DSI"))]
        if integre: return integre[0]
        def pos(m):
            try: g = m.get_geometry(); return (g.x, g.y)
            except Exception: return (0, 0)
        return min(L, key=pos)

    def secondaires(self):
        p = self.principal()
        return [m for m in moniteurs() if m is not p and nom(m) != nom(p)]

    def nom_principal(self):
        p = self.principal(); return nom(p) if p else ""

    # ---------------------------------------------------------------- mise à jour
    def maj(self):
        sh = self.sh; L = moniteurs()
        p = self.principal()
        # les surfaces de l'écran principal (barre, barre du haut, mode, icônes du bureau) y restent épinglées
        if p is not None and len(L) > 1 and nom(p) != self._principal:
            self._principal = nom(p)
            for w in self.surfaces_principales():
                try: LS.set_monitor(w, p)
                except Exception: pass
        elif len(L) <= 1:
            self._principal = nom(p) if p else None
        sec = {nom(m): m for m in self.secondaires()}
        # barres des écrans secondaires
        veut_barre = sh.cfg.get("barre_tous_ecrans", True) and not sh.cfg.get("barre_masquee") and sh.imit() != "macos"
        for n in list(self.barres):
            if n not in sec or not veut_barre: self.barres.pop(n).detruire()
        if veut_barre:
            for n, m in sec.items():
                if n not in self.barres: self.barres[n] = BarreEcran(self, m)
        # modes des écrans secondaires
        modes = sh.cfg.get("modes_ecrans") or {}
        for n in list(self.vues):
            if n not in sec or modes.get(n, "classique") == "classique":
                v = self.vues.pop(n); v.arreter(); v.w.destroy()
        from .modes import VueMode, PAR_CLE
        for n, m in sec.items():
            k = modes.get(n, "classique")
            if k == "classique" or k not in PAR_CLE: continue
            if n not in self.vues:
                v = VueMode(sh); LS.set_monitor(v.w, m); self.vues[n] = v
            self.vues[n].appliquer(k)
        self.visibilite(); self.maj_taches()

    def surfaces_principales(self):
        sh = self.sh; L = []
        for a in ("barre", "haut", "bulles"):       # les bulles de notification aussi, sur l'écran principal
            if hasattr(sh, a): L.append(getattr(sh, a))
        if hasattr(sh, "vue_mode"): L.append(sh.vue_mode.w)
        if hasattr(sh, "bureau"): L.append(sh.bureau.w)
        if getattr(sh, "ile", None) is not None: L.append(sh.ile.w)
        return L

    def visibilite(self):
        """Barre d'un écran secondaire cachée dans les modes plein écran (Production, Fiction, Multicam), comme l'écran principal."""
        modes = self.sh.cfg.get("modes_ecrans") or {}
        for n, b in self.barres.items():
            cache = modes.get(n, "classique") in ("production", "fiction", "multicam") and self.sh.cfg.get("barre_modes_masquee", True)
            b.w.set_visible(not cache)

    def replacer(self):
        for b in self.barres.values():
            vis = b.w.get_visible()
            if not vis: b.w.set_visible(True)
            b.placer()
            if not vis: b.w.set_visible(False)

    # ---------------------------------------------------------------- applis de chaque barre
    def filtre_principal(self, fs_par_cle):
        """Barre principale : toutes les fenêtres, ou seulement celles de l'écran principal (réglage façon Windows)."""
        if not self.barres or self.sh.cfg.get("barre_applis_ecrans", "toutes") != "ecran": return fs_par_cle
        return {k: [f for f in fs if self.sur(f, self._principal or self.nom_principal(), True)] for k, fs in fs_par_cle.items()}

    def sur(self, f, n, principal=False):
        fe = self.sh.fenetres
        e = fe.ecrans(f) if fe and hasattr(fe, "ecrans") else set()
        if not e: return principal          # écran inconnu : sur l'écran principal
        return n in e

    def maj_taches(self):
        if not self.barres: return
        sh = self.sh
        fen = sh.fenetres.liste() if sh.fenetres and sh.fenetres.ok else []
        seul = sh.cfg.get("barre_applis_ecrans", "toutes") == "ecran"
        for n, b in self.barres.items():
            groupes, info = {}, {}
            for f in fen:
                if seul and not self.sur(f, n): continue
                a = apps.pour_fenetre(f.app_id); cle = a.get_id() if a else ("x:" + (f.app_id or f.titre))
                groupes.setdefault(cle, []).append(f); info[cle] = a
            ordre = [p for p in sh.cfg["epingles"] if apps.par_id(p)] + [k for k in groupes if k not in sh.cfg["epingles"]]
            L = []
            for cle in ordre:
                a = info.get(cle) or (apps.par_id(cle) if not cle.startswith("x:") else None)
                if a is None and not groupes.get(cle): continue
                L.append((cle, a, groupes.get(cle, [])))
            b.remplir(L)
        for v in self.vues.values(): v.maj_fenetres(fen)
