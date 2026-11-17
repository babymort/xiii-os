# OS XIII — tableau de widgets (façon Windows 11, ouvert depuis la météo de la barre des tâches) :
# météo, système, lecture en cours, notes, raccourcis, et widgets Suite XIII (projet, conducteur, plan de travail)
# alimentés par les fichiers .xiii.json exportés depuis la suite.
# Application développée par Matthieu Lamotte.
import os, glob, json, time, datetime, re
from gi.repository import Gtk, GLib, Gio, Pango
from . import systeme as S, config, apps
from .ui import *

WIDGETS = [  # clé, nom, icône, description
    ("meteo", "Météo", "cloud-sun", "Temps actuel et prévisions sur 5 jours"),
    ("systeme", "Système", "activity", "Processeur, mémoire, disque, réseau, température"),
    ("media", "Lecture en cours", "music", "Titre joué et commandes (lecteurs compatibles MPRIS)"),
    ("projet", "Projet XIII", "clapperboard", "Fiche projet exportée depuis la Suite XIII"),
    ("conducteur", "Conducteur", "list-video", "Dernier conducteur CONDUCO"),
    ("plan", "Prochain tournage", "calendar-days", "Plan de travail DECOUP : prochaine journée"),
    ("notes", "Notes", "notebook-pen", "Bloc-notes rapide, enregistré automatiquement"),
    ("raccourcis", "Raccourcis", "folder", "Dossiers et liens utiles"),
]
NOTES = os.path.join(GLib.get_user_data_dir(), "xiii", "notes.txt")

def dossiers_xiii():
    L = [os.path.expanduser("~/XIII")]
    for d in (GLib.UserDirectory.DIRECTORY_DOWNLOAD, GLib.UserDirectory.DIRECTORY_DOCUMENTS, GLib.UserDirectory.DIRECTORY_DESKTOP):
        p = GLib.get_user_special_dir(d)
        if p: L.append(p)
    return [p for p in L if os.path.isdir(p)]

def dernier_lien(kind):
    """Dernier fichier .xiii.json (format xiii-link) du type demandé."""
    if S.DEMO:
        return DEMO.get(kind)
    meilleurs = []
    for d in dossiers_xiii():
        for f in glob.glob(os.path.join(d, "**", "*.xiii.json"), recursive=True)[:300] + glob.glob(os.path.join(d, "*.json"))[:100]:
            try:
                meilleurs.append((os.path.getmtime(f), f))
            except OSError:
                pass
    for _, f in sorted(meilleurs, reverse=True):
        try:
            o = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(o, dict) and o.get("format") == "xiii-link" and o.get("kind") == kind:
            o["_fichier"] = f
            return o
    return None

DEMO = {
    "project": {"project": {"name": "Concert Dôme de Paris"}, "fiche": {"title": "Concert Dôme de Paris", "client": "Live Nation", "lieu": "Dôme de Paris — Palais des sports",
                                                                       "date": "2026-11-28", "realisateur": "M. Lamotte"}, "contacts": [1, 2, 3, 4, 5, 6, 7]},
    "rundown": {"project": {"name": "Concert Dôme de Paris"}, "conducteur": {"name": "Conducteur captation", "date": "2026-11-28", "start": "20:30", "end": "23:10", "totalTxt": "2 h 40"},
                "items": [{"title": "Ouverture"}, {"title": "Titre 1 — Intro"}, {"title": "Interview loge"}, {"title": "Titre 2"}, {"title": "Rappel"}]},
    "workplan": {"project": {"name": "Court-métrage « Nuit blanche »"}, "days": [{"n": 1, "date": "2026-11-20", "scenes": [{"seq": "12", "ie": "INT.", "decor": "Appartement Léa", "effet": "NUIT"}, {"seq": "13", "ie": "EXT.", "decor": "Rue", "effet": "NUIT"}]},
                                                                             {"n": 2, "date": "2026-11-21", "scenes": [{"seq": "4", "ie": "INT.", "decor": "Café", "effet": "JOUR"}]}]},
}

# ------------------------------------------------------------------------------------------------ mesures système
class Mesures:
    def __init__(self):
        self.cpu_prev = None; self.net_prev = None
    def cpu(self):
        try:
            v = list(map(int, open("/proc/stat").readline().split()[1:]))
        except Exception:
            return 0
        idle, tot = v[3] + v[4], sum(v)
        r = 0
        if self.cpu_prev:
            di, dt = idle - self.cpu_prev[0], tot - self.cpu_prev[1]
            r = 100 * (1 - di / dt) if dt else 0
        self.cpu_prev = (idle, tot)
        return max(0, min(100, r))
    def ram(self):
        try:
            m = dict((l.split(":")[0], int(l.split()[1])) for l in open("/proc/meminfo"))
            return 100 * (1 - m["MemAvailable"] / m["MemTotal"]), m["MemTotal"] / 1048576
        except Exception:
            return 0, 0
    def net(self):
        rx = tx = 0
        try:
            for l in open("/proc/net/dev").readlines()[2:]:
                n, d = l.split(":", 1)
                if n.strip() == "lo": continue
                f = d.split(); rx += int(f[0]); tx += int(f[8])
        except Exception:
            pass
        t = time.time(); r = (0, 0)
        if self.net_prev:
            dt = t - self.net_prev[2] or 1
            r = ((rx - self.net_prev[0]) / dt, (tx - self.net_prev[1]) / dt)
        self.net_prev = (rx, tx, t)
        return r
    def temp(self):
        vals = []
        for z in glob.glob("/sys/class/thermal/thermal_zone*/temp") + glob.glob("/sys/class/hwmon/hwmon*/temp1_input"):
            try: vals.append(int(open(z).read()) / 1000)
            except Exception: pass
        vals = [v for v in vals if 5 < v < 120]
        return max(vals) if vals else None

def jauge(nom, ic):
    r = boite(True, 4)
    h = boite(False, 6); h.append(ico(ic, 14, "d")); h.append(label(nom, "petit", hexpand=True)); v = label("—", "niveau", xalign=1); h.append(v)
    r.append(h); lb = Gtk.LevelBar(min_value=0, max_value=100); r.append(lb)
    r._val = v; r._lb = lb
    return r

# ------------------------------------------------------------------------------------------------ tableau
class Tableau:
    largeur = 760
    def __init__(self, shell):
        self.shell = shell; self.mes = Mesures(); self._src = 0
        w = boite(True, 12, "panneau"); w.set_size_request(self.largeur, -1); self.widget = w
        h = boite(False, 10)
        self.l_heure = label("", "panneau-titre"); h.append(self.l_heure)
        self.l_date = label("", "attenue", hexpand=True); h.append(self.l_date)
        h.append(bouton("Personnaliser", "settings", "fantome", taille=14, rappel=lambda: shell.parametres("widgets")))
        w.append(h)
        self.grille = Gtk.FlowBox(max_children_per_line=2, min_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE,
                                  column_spacing=10, row_spacing=10, homogeneous=True, valign=Gtk.Align.START)
        w.append(defilant(self.grille))
        self.grille.get_parent().get_parent().set_vexpand(True)
        w.connect("unmap", lambda *_: self.stop())

    def carte(self, cle, titre, ic, corps, page=None):
        c = boite(True, 10, "carte")
        c.set_size_request(-1, 190)
        h = boite(False, 8); h.append(ico(ic, 16, "c")); h.append(label(titre, "gras", hexpand=True))
        if page: h.append(bouton(None, "chevron-right", "plat", taille=14, role="d", rappel=page))
        c.append(h); c.append(corps)
        return c

    def rafraichir(self):
        n = datetime.datetime.now()
        self.l_heure.set_text(n.strftime("%H:%M"))
        jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        self.l_date.set_text("%s %d %s" % (jours[n.weekday()].capitalize(), n.day, mois[n.month - 1]))
        vider(self.grille)
        for cle in self.shell.cfg.get("widgets", [w[0] for w in WIDGETS]):
            fn = getattr(self, "w_" + cle, None)
            if fn:
                try:
                    self.grille.append(fn())
                except Exception as e:
                    self.grille.append(self.carte(cle, cle, "circle-alert", label(str(e), "attenue", "petit", wrap=True)))
        self.stop(); self._src = GLib.timeout_add_seconds(2, self.tic); self.tic()

    def stop(self):
        if self._src: GLib.source_remove(self._src); self._src = 0

    def tic(self):
        if hasattr(self, "_sys"):
            c = self.mes.cpu(); r, tot = self.ram(); rx, tx = self.mes.net(); t = self.mes.temp()
            j = self._sys
            j["cpu"]._lb.set_value(c); j["cpu"]._val.set_text("%d %%" % c)
            j["ram"]._lb.set_value(r); j["ram"]._val.set_text("%d %% de %.1f Go" % (r, tot))
            self._net.set_text("↓ %s/s   ↑ %s/s" % (S.humain(rx), S.humain(tx)))
            self._temp.set_text(("%d °C" % t) if t else "—")
        if hasattr(self, "_media_maj"): self._media_maj()
        return True

    def ram(self):
        if S.DEMO: return 41, 7.7
        return self.mes.ram()

    # ---------------------------------------------------------------- widgets
    def w_meteo(self):
        m = self.shell._meteo; v = boite(True, 8)
        if not m:
            v.append(label("Météo indisponible (pas de connexion ?)", "attenue", "petit", wrap=True))
        else:
            from .panneaux import METEO
            ic, nom = METEO.get(m["code"], ("cloud", ""))
            h = boite(False, 12); h.append(ico(ic, 42, "c"))
            t = boite(True, 0); t.append(label("%d°" % m["t"], "meteo-grand")); t.append(label("%s · %s" % (nom, self.shell.cfg["meteo_ville"]), "attenue", "petit")); h.append(t)
            v.append(h)
            g = boite(False, 4, homogeneous=True)
            for j, code, mx, mn in m["jours"][:5]:
                c = boite(True, 2); c.append(label(j[:4], "petit", xalign=0.5)); c.append(ico(METEO.get(code, ("cloud",))[0], 18, "c")); c.append(label("%d°/%d°" % (mx, mn), "petit", xalign=0.5))
                g.append(c)
            v.append(g)
        return self.carte("meteo", "Météo", "cloud-sun", v, lambda: self.shell.parametres("meteo"))

    def w_systeme(self):
        v = boite(True, 8)
        self._sys = {"cpu": jauge("Processeur", "cpu"), "ram": jauge("Mémoire", "memory-stick")}
        for j in self._sys.values(): v.append(j)
        d = S.disques()
        if d:
            dj = jauge("Disque système", "hard-drive"); pc = 100 * d[0]["utilise"] / max(1, d[0]["total"])
            dj._lb.set_value(pc); dj._val.set_text("%s libres" % S.humain(d[0]["libre"])); v.append(dj)
        r = boite(False, 10); r.append(ico("network", 14, "d")); self._net = label("—", "petit", hexpand=True); r.append(self._net)
        r.append(ico("thermometer", 14, "d")); self._temp = label("—", "petit"); r.append(self._temp); v.append(r)
        return self.carte("systeme", "Système", "activity", v, lambda: S.detacher("xiii-bilan"))

    def w_media(self):
        v = boite(True, 8)
        titre = label("Rien en lecture", "gras", ellipsize=True); artiste = label("Lancez un lecteur (navigateur, mpv…)", "attenue", "petit", ellipsize=True)
        v.append(titre); v.append(artiste)
        r = boite(False, 8, halign=Gtk.Align.CENTER, margin_top=6)
        bp = bouton(None, "play", "fantome", taille=18)
        for ic, cmd in (("skip-back", "previous"), (None, "play-pause"), ("skip-forward", "next")):
            b = bp if ic is None else bouton(None, ic, "plat", taille=18)
            b.connect("clicked", lambda _b, c=cmd: (S.detacher(["playerctl", c]), GLib.timeout_add(400, lambda: (self._media_maj(), False)[1])))
            r.append(b)
        v.append(r)
        def maj():
            if S.DEMO:
                titre.set_text("Clair de lune"); artiste.set_text("Claude Debussy · Firefox"); return
            o = S.out(["playerctl", "metadata", "--format", "{{status}}\t{{artist}}\t{{title}}\t{{playerName}}"], 2)
            if not o:
                titre.set_text("Rien en lecture"); artiste.set_text("Lancez un lecteur (navigateur, mpv…)"); return
            st, ar, ti, pl = (o.split("\t") + ["", "", "", ""])[:4]
            titre.set_text(ti or "Sans titre"); artiste.set_text(" · ".join(x for x in (ar, pl) if x))
            bp.set_child(ico("pause" if st == "Playing" else "play", 18))
        self._media_maj = maj; maj()
        return self.carte("media", "Lecture en cours", "music", v)

    def w_notes(self):
        tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, vexpand=True, top_margin=6, left_margin=6, right_margin=6)
        tv.add_css_class("champ")
        try: tv.get_buffer().set_text(open(NOTES).read())
        except OSError: tv.get_buffer().set_text("")
        src = [0]
        def changed(buf):
            if src[0]: GLib.source_remove(src[0])
            def save():
                src[0] = 0; os.makedirs(os.path.dirname(NOTES), exist_ok=True)
                s, e = buf.get_bounds(); open(NOTES, "w").write(buf.get_text(s, e, False)); return False
            src[0] = GLib.timeout_add(600, save)
        tv.get_buffer().connect("changed", changed)
        sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(tv); sc.set_size_request(-1, 120)
        return self.carte("notes", "Notes", "notebook-pen", sc)

    def w_raccourcis(self):
        g = Gtk.FlowBox(max_children_per_line=3, min_children_per_line=3, selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, row_spacing=4, column_spacing=4)
        cap = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or os.path.expanduser("~/Images"), "Captures")
        for nom, ic, cible in (("Documents", "file-text", GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)),
                               ("Téléchargements", "download", GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)),
                               ("Images", "image", GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)),
                               ("Vidéos", "film", GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)), ("Captures", "scan-line", cap),
                               ("Suite XIII", "zap", "https://suite-xiii.netlify.app/")):
            b = Gtk.Button(); b.add_css_class("app")
            bx = boite(True, 4); bx.append(ico(ic, 22, "c")); bx.append(label(nom, "app-nom", xalign=0.5, ellipsize=True)); b.set_child(bx)
            b.connect("clicked", lambda _b, c=cible: (self.shell.fermer(), S.detacher(["xdg-open", c or os.path.expanduser("~")])))
            g.append(b)
        return self.carte("raccourcis", "Raccourcis", "folder", g)

    def vide_xiii(self, quoi):
        v = boite(True, 8)
        v.append(label("Aucun %s trouvé." % quoi, "gras"))
        v.append(label("Exportez-le depuis la Suite XIII (fichier .xiii.json) : il est lu automatiquement dans ~/XIII, Téléchargements ou Documents.", "attenue", "petit", wrap=True))
        v.append(bouton("Ouvrir la Suite XIII", "external-link", "fantome", taille=14, rappel=lambda: (self.shell.fermer(), S.detacher(["xdg-open", "https://suite-xiii.netlify.app/"]))))
        return v

    def w_projet(self):
        o = dernier_lien("project")
        if not o: return self.carte("projet", "Projet XIII", "clapperboard", self.vide_xiii("projet"))
        f = o.get("fiche") or {}; v = boite(True, 6)
        v.append(label(f.get("title") or (o.get("project") or {}).get("name") or "Projet", "hero-grand" if False else "gras", wrap=True))
        n = 0
        for k, val in f.items():
            if k in ("title", "id", "logo", "image") or not isinstance(val, (str, int, float)) or not str(val).strip() or len(str(val)) > 80: continue
            r = boite(False, 8); r.append(label(k.replace("_", " ").capitalize(), "attenue", "petit")); r.append(label(str(val), "petit", ellipsize=True, hexpand=True, xalign=1)); v.append(r)
            n += 1
            if n >= 4: break
        if o.get("contacts"): v.append(label("%d contact(s) d'équipe" % len(o["contacts"]), "attenue", "petit"))
        return self.carte("projet", "Projet XIII", "clapperboard", v, (lambda: apps.ouvrir_fichier(o["_fichier"])) if o.get("_fichier") else None)

    def w_conducteur(self):
        o = dernier_lien("rundown")
        if not o: return self.carte("conducteur", "Conducteur", "list-video", self.vide_xiii("conducteur"))
        c = o.get("conducteur") or {}; v = boite(True, 6)
        v.append(label(c.get("name") or "Conducteur", "gras", ellipsize=True))
        v.append(label(" · ".join(x for x in ((o.get("project") or {}).get("name"), c.get("date"), ("%s → %s" % (c.get("start"), c.get("end"))) if c.get("start") else "", c.get("totalTxt")) if x), "attenue", "petit", wrap=True))
        for it in (o.get("items") or [])[:4]:
            t = it.get("title") or it.get("name") or it.get("titre") or ""
            if t:
                r = boite(False, 8); r.append(ico("chevron-right", 12, "c")); r.append(label(t, "petit", ellipsize=True)); v.append(r)
        if len(o.get("items") or []) > 4: v.append(label("+ %d éléments" % (len(o["items"]) - 4), "attenue", "petit"))
        return self.carte("conducteur", "Conducteur", "list-video", v)

    def w_plan(self):
        o = dernier_lien("workplan")
        if not o: return self.carte("plan", "Prochain tournage", "calendar-days", self.vide_xiii("plan de travail"))
        auj = datetime.date.today().isoformat()
        jours = sorted(o.get("days") or [], key=lambda d: d.get("date") or "")
        j = next((d for d in jours if (d.get("date") or "") >= auj), jours[-1] if jours else None)
        v = boite(True, 6)
        v.append(label((o.get("project") or {}).get("name") or "Plan de travail", "attenue", "petit"))
        if j:
            dt = j.get("date") or ""
            try:
                d = datetime.date.fromisoformat(dt); delta = (d - datetime.date.today()).days
                quand = "Aujourd'hui" if delta == 0 else "Demain" if delta == 1 else ("Dans %d jours" % delta if delta > 1 else d.strftime("%d/%m"))
            except Exception:
                quand = dt
            v.append(label("Jour %s — %s" % (j.get("n", "?"), quand), "gras"))
            for s in (j.get("scenes") or [])[:4]:
                v.append(label("Séq. %s · %s %s · %s" % (s.get("seq", ""), s.get("ie", ""), s.get("decor", ""), s.get("effet", "")), "petit", ellipsize=True))
        return self.carte("plan", "Prochain tournage", "calendar-days", v)
