# OS XIII — XIII Calendrier : agenda local (avec rappels), agendas Google et Outlook affichés par leur adresse iCal
# (lecture seule, mis à jour toutes les 30 minutes), jours de tournage du plan de travail de la Suite (PLANO / DECOUP)
# et dates du projet actif. Vue mois + liste du jour, export .ics.
# Application développée par Matthieu Lamotte.
import os, sys, json, re, time, uuid, hashlib, datetime as dt, urllib.request, threading
from zoneinfo import ZoneInfo
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib
from . import config, systeme as S
from .ui import *
from .appli import preparer

LOCAL = os.path.expanduser("~/.local/share/xiii/agenda.json")
CACHE = os.path.expanduser("~/.cache/xiii/agenda")
def _fuseau():
    try: return ZoneInfo(os.path.realpath("/etc/localtime").split("zoneinfo/", 1)[1])
    except Exception: return dt.datetime.now().astimezone().tzinfo
ICI = _fuseau()
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
COUL = {"local": "#f0b378", "tournage": "#ef6b6b", "projet": "#a371f7"}


def locaux():
    try: return json.load(open(LOCAL))
    except Exception: return []


def sauver(L):
    os.makedirs(os.path.dirname(LOCAL), exist_ok=True); json.dump(L, open(LOCAL, "w"), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ iCal (Google, Outlook…)
def _dt(v, params):
    v = v.strip()
    if re.fullmatch(r"\d{8}", v): return dt.datetime.strptime(v, "%Y%m%d").replace(tzinfo=ICI), True
    t = dt.datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
    if v.endswith("Z"): t = t.replace(tzinfo=dt.timezone.utc)
    else:
        tz = re.search(r"TZID=([^;:]+)", params or "")
        try: t = t.replace(tzinfo=ZoneInfo(tz.group(1))) if tz else t.replace(tzinfo=ICI)
        except Exception: t = t.replace(tzinfo=ICI)
    return t.astimezone(ICI), False


def lire_ics(texte, debut, fin, source, couleur):
    """Événements entre debut et fin (répétitions comprises, via python3-dateutil)."""
    texte = re.sub(r"\r?\n[ \t]", "", texte); out = []
    for bloc in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", texte, re.S):
        P = {}; ex = []
        for l in bloc.strip().splitlines():
            if ":" not in l: continue
            k, v = l.split(":", 1); nom, _, params = k.partition(";")
            if nom == "EXDATE": ex += [(x, params) for x in v.split(",")]
            else: P[nom] = (v, params)
        if "DTSTART" not in P: continue
        try:
            d0, journee = _dt(*P["DTSTART"])
            d1 = _dt(*P["DTEND"])[0] if "DTEND" in P else d0 + (dt.timedelta(days=1) if journee else dt.timedelta(hours=1))
        except Exception:
            continue
        duree = d1 - d0
        dec = lambda s: s.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
        base = {"titre": dec(P.get("SUMMARY", ("(sans titre)",))[0]), "lieu": dec(P.get("LOCATION", ("",))[0]), "journee": journee, "source": source, "couleur": couleur}
        debuts = [d0]
        if "RRULE" in P:
            try:
                from dateutil.rrule import rrulestr
                r = rrulestr(P["RRULE"][0], dtstart=d0, ignoretz=False)
                exs = set()
                for x, pr in ex:
                    try: exs.add(_dt(x, pr)[0])
                    except Exception: pass
                debuts = [x for x in r.between(debut - duree, fin, inc=True) if x not in exs]
            except Exception:
                pass
        for x in debuts:
            if x < fin and x + duree > debut: out.append(dict(base, debut=x.isoformat(), fin=(x + duree).isoformat()))
    return out


def abonnements():
    return config.charger().get("agenda_abonnements") or []


def maj_abonnements(force=False):
    os.makedirs(CACHE, exist_ok=True); err = []
    for a in abonnements():
        f = os.path.join(CACHE, hashlib.md5(a["url"].encode()).hexdigest() + ".ics")
        if not force and os.path.exists(f) and time.time() - os.path.getmtime(f) < 1800: continue
        try:
            u = a["url"].replace("webcal://", "https://")
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "OS-XIII"}), timeout=30) as r: d = r.read()
            if b"BEGIN:VCALENDAR" in d: open(f, "wb").write(d)
            else: err.append(a["nom"])
        except Exception:
            err.append(a["nom"])
    return err


def evenements(debut, fin):
    L = []
    for e in locaux():
        try:
            d0, d1 = dt.datetime.fromisoformat(e["debut"]), dt.datetime.fromisoformat(e["fin"])
            if d0 < fin and d1 > debut: L.append(dict(e, source="local", couleur=COUL["local"]))
        except Exception: pass
    for a in abonnements():
        f = os.path.join(CACHE, hashlib.md5(a["url"].encode()).hexdigest() + ".ics")
        try: L += lire_ics(open(f, encoding="utf-8", errors="replace").read(), debut, fin, a["nom"], a.get("couleur") or "#6aa8ff")
        except OSError: pass
    # jours de tournage (plan de travail de la Suite) et dates du projet actif
    try:
        from .widgets import dernier_lien
        o = dernier_lien("workplan") or {}
        for j in o.get("days") or []:
            d = dt.datetime.fromisoformat(j["date"]).replace(tzinfo=ICI)
            if debut <= d < fin:
                sc = ", ".join("%s %s" % (s.get("seq", ""), s.get("decor", "")) for s in (j.get("scenes") or [])[:4])
                L.append({"titre": "Tournage J%s%s" % (j.get("n", "?"), (" — " + (o.get("project") or {}).get("name", "")) if o.get("project") else ""), "debut": d.isoformat(),
                          "fin": (d + dt.timedelta(days=1)).isoformat(), "journee": True, "lieu": j.get("lieu") or "", "notes": sc, "source": "Plan de travail", "couleur": COUL["tournage"]})
    except Exception: pass
    try:
        from . import projets
        pj = config.charger().get("projet_actif")
        f = projets.fiche_de(pj) if pj else None
        if f and f.get("debut"):
            d0 = dt.datetime.fromisoformat(f["debut"]).replace(tzinfo=ICI); d1 = dt.datetime.fromisoformat(f.get("fin") or f["debut"]).replace(tzinfo=ICI) + dt.timedelta(days=1)
            if d0 < fin and d1 > debut:
                L.append({"titre": "Projet « %s »" % (f.get("title") or pj), "debut": d0.isoformat(), "fin": d1.isoformat(), "journee": True, "lieu": f.get("lieu") or "", "source": "Projet XIII", "couleur": COUL["projet"]})
    except Exception: pass
    return sorted(L, key=lambda e: (not e.get("journee"), e["debut"]))


def exporter_ics(chemin):
    def f(x): return dt.datetime.fromisoformat(x).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OS XIII//Calendrier//FR"]
    for e in locaux():
        L += ["BEGIN:VEVENT", "UID:%s@os-xiii" % e["id"], "DTSTAMP:" + f(dt.datetime.now(ICI).isoformat()),
              ("DTSTART;VALUE=DATE:" + e["debut"][:10].replace("-", "")) if e.get("journee") else "DTSTART:" + f(e["debut"]),
              ("DTEND;VALUE=DATE:" + e["fin"][:10].replace("-", "")) if e.get("journee") else "DTEND:" + f(e["fin"]),
              "SUMMARY:" + e["titre"].replace(",", "\\,"), "LOCATION:" + (e.get("lieu") or "").replace(",", "\\,"), "END:VEVENT"]
    open(chemin, "w").write("\r\n".join(L + ["END:VCALENDAR"]) + "\r\n")


def rappels_a_venir(maintenant=None):
    """Événements locaux dont le rappel tombe dans la minute (utilisé par le bureau)."""
    n = maintenant or dt.datetime.now(ICI); R = []
    for e in locaux():
        if e.get("rappel") is None or e.get("journee"): continue
        try: t = dt.datetime.fromisoformat(e["debut"]) - dt.timedelta(minutes=int(e["rappel"]))
        except Exception: continue
        if n - dt.timedelta(seconds=60) < t <= n: R.append(e)
    return R


class Calendrier(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.calendrier"); a = dt.date.today(); self.mois = a.replace(day=1); self.jour = a

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".case-jour { border-radius: 10px; padding: 4px; min-height: 92px; background: alpha(currentColor, .035); }"
                 " .case-jour:hover { background: alpha(currentColor, .07); } .case-jour.choisi { background: alpha(@accent_bg_color, .2); }"
                 " .case-jour.hors { opacity: .45; } .num-jour { font-weight: 700; } .num-jour.auj { color: #f0b378; }"
                 " .pastille-ev { border-radius: 5px; padding: 0 5px; font-size: 11px; color: #111; }")
        self.win = Gtk.ApplicationWindow(application=self, title="XIII Calendrier", default_width=1240, default_height=780)
        r = boite(False, 0); self.win.set_child(r)
        g = boite(True, 8, hexpand=True, margin_start=16, margin_end=10, margin_top=12, margin_bottom=12); r.append(g)
        h = boite(False, 8); self.l_mois = label("", "page-titre", hexpand=True); h.append(self.l_mois)
        h.append(bouton(None, "chevron-left", "plat", rappel=lambda: self.decaler(-1))); h.append(bouton("Aujourd'hui", None, "fantome", rappel=self.aujourdhui))
        h.append(bouton(None, "chevron-right", "plat", rappel=lambda: self.decaler(1))); h.append(bouton("Événement", "plus", "pilule", rappel=lambda: self.editer(None)))
        h.append(bouton(None, "settings", "plat", tip="Agendas Google, Outlook… et export", rappel=self.reglages)); g.append(h)
        self.grille = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, column_spacing=6, row_spacing=6, vexpand=True); g.append(self.grille)
        r.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        d = boite(True, 8, margin_start=12, margin_end=16, margin_top=16, margin_bottom=12); d.set_size_request(330, -1); r.append(d)
        self.l_jour = label("", "gras"); d.append(self.l_jour)
        sc = Gtk.ScrolledWindow(vexpand=True); self.liste = boite(True, 6); sc.set_child(self.liste); d.append(sc)
        self.etat = label("", "petit", "attenue", wrap=True); d.append(self.etat)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.touche); self.win.add_controller(k)
        self.win.present(); self.rendu()
        S.en_fond(maj_abonnements, lambda e: (self.etat.set_text("Agenda injoignable : " + ", ".join(e)) if isinstance(e, list) and e else None, self.rendu()))
        GLib.timeout_add_seconds(1800, lambda: (S.en_fond(maj_abonnements, lambda e: self.rendu()), True)[1])

    def touche(self, c, kv, *a):
        if kv == Gdk.KEY_Page_Up: self.decaler(-1)
        elif kv == Gdk.KEY_Page_Down: self.decaler(1)
        elif kv in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down):
            self.jour += dt.timedelta(days={Gdk.KEY_Left: -1, Gdk.KEY_Right: 1, Gdk.KEY_Up: -7, Gdk.KEY_Down: 7}[kv])
            self.mois = self.jour.replace(day=1); self.rendu()
        elif kv in (Gdk.KEY_n, Gdk.KEY_N): self.editer(None)
        else: return False
        return True

    def decaler(self, n):
        m = self.mois.month - 1 + n; self.mois = dt.date(self.mois.year + m // 12, m % 12 + 1, 1); self.rendu()

    def aujourdhui(self):
        self.jour = dt.date.today(); self.mois = self.jour.replace(day=1); self.rendu()

    def rendu(self):
        self.l_mois.set_text("%s %d" % (MOIS[self.mois.month - 1].capitalize(), self.mois.year))
        c = self.grille.get_first_child()
        while c: n = c.get_next_sibling(); self.grille.remove(c); c = n
        for i, j in enumerate(JOURS): self.grille.attach(label(j, "petit", "attenue", xalign=0.5), i, 0, 1, 1)
        d0 = self.mois - dt.timedelta(days=self.mois.weekday())
        deb = dt.datetime.combine(d0, dt.time(), ICI); fin = deb + dt.timedelta(days=42)
        E = evenements(deb, fin); self.E = E
        auj = dt.date.today()
        for k in range(42):
            jour = d0 + dt.timedelta(days=k)
            b = Gtk.Button(); b.add_css_class("case-jour"); b.add_css_class("plat")
            if jour.month != self.mois.month: b.add_css_class("hors")
            if jour == self.jour: b.add_css_class("choisi")
            v = boite(True, 2, valign=Gtk.Align.START); v.append(label(str(jour.day), *(("num-jour", "auj") if jour == auj else ("num-jour",)), xalign=0))
            ev = self.du_jour(jour)
            for e in ev[:3]:
                p = label(("" if e.get("journee") else dt.datetime.fromisoformat(e["debut"]).strftime("%H:%M ")) + e["titre"], "pastille-ev", ellipsize=True, xalign=0)
                css = Gtk.CssProvider(); css.load_from_string("label { background: %s; }" % e["couleur"]); p.get_style_context().add_provider(css, 800); v.append(p)
            if len(ev) > 3: v.append(label("+ %d" % (len(ev) - 3), "petit", "attenue"))
            b.set_child(v); b.connect("clicked", lambda _b, jour=jour: (setattr(self, "jour", jour), self.rendu()))
            g = Gtk.GestureClick(); g.connect("pressed", lambda g_, n, x, y, jour=jour: (setattr(self, "jour", jour), self.editer(None)) if n == 2 else None); b.add_controller(g)
            self.grille.attach(b, k % 7, 1 + k // 7, 1, 1)
        self.rendu_jour()

    def du_jour(self, jour):
        a = dt.datetime.combine(jour, dt.time(), ICI); z = a + dt.timedelta(days=1)
        return [e for e in self.E if dt.datetime.fromisoformat(e["debut"]) < z and dt.datetime.fromisoformat(e["fin"]) > a]

    def rendu_jour(self):
        j = self.jour; self.l_jour.set_text("%s %d %s %d" % (["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"][j.weekday()], j.day, MOIS[j.month - 1], j.year))
        vider(self.liste); L = self.du_jour(j)
        if not L: self.liste.append(label("Rien de prévu. Double-clic sur un jour ou « Événement » pour en ajouter.", "attenue", "petit", wrap=True))
        for e in L:
            c = boite(True, 2, "carte")
            h = boite(False, 8); d = Gtk.DrawingArea(); d.set_size_request(10, 10); rg = Gdk.RGBA(); rg.parse(e["couleur"])
            d.set_draw_func(lambda a, cr, w, hh, rg=rg: (cr.set_source_rgba(rg.red, rg.green, rg.blue, 1), cr.arc(5, 5, 5, 0, 6.3), cr.fill())); h.append(d)
            h.append(label(e["titre"], "gras", hexpand=True, wrap=True))
            if e["source"] == "local": h.append(bouton(None, "pencil", "plat", taille=13, rappel=lambda e=e: self.editer(e)))
            c.append(h)
            quand = "Toute la journée" if e.get("journee") else "%s – %s" % (dt.datetime.fromisoformat(e["debut"]).strftime("%H:%M"), dt.datetime.fromisoformat(e["fin"]).strftime("%H:%M"))
            c.append(label(quand + " · " + ("Mon agenda" if e["source"] == "local" else e["source"]), "petit", "attenue"))
            if e.get("lieu"): c.append(label("📍 " + e["lieu"], "petit", wrap=True))
            if e.get("notes"): c.append(label(e["notes"], "petit", "attenue", wrap=True))
            self.liste.append(c)

    def editer(self, e):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Événement", default_width=440); v = boite(True, 10, margin_top=18, margin_bottom=18, margin_start=18, margin_end=18); d.set_child(v)
        jour = dt.datetime.fromisoformat(e["debut"]).date() if e else self.jour
        titre = Gtk.Entry(text=e["titre"] if e else "", placeholder_text="Titre (ex. Repérage, Réunion de prod…)"); v.append(titre)
        date = Gtk.Entry(text=jour.strftime("%d/%m/%Y"), placeholder_text="JJ/MM/AAAA"); v.append(date)
        journee = Gtk.CheckButton(label="Toute la journée", active=bool(e and e.get("journee"))); v.append(journee)
        h = boite(False, 8); h0 = Gtk.Entry(text=dt.datetime.fromisoformat(e["debut"]).strftime("%H:%M") if e and not e.get("journee") else "09:00", width_chars=6)
        h1 = Gtk.Entry(text=dt.datetime.fromisoformat(e["fin"]).strftime("%H:%M") if e and not e.get("journee") else "10:00", width_chars=6)
        h.append(label("De")); h.append(h0); h.append(label("à")); h.append(h1); v.append(h)
        journee.connect("toggled", lambda w: h.set_sensitive(not w.get_active())); h.set_sensitive(not journee.get_active())
        lieu = Gtk.Entry(text=(e or {}).get("lieu", ""), placeholder_text="Lieu"); v.append(lieu)
        rap = Gtk.DropDown.new_from_strings(["Pas de rappel", "5 min avant", "15 min avant", "1 h avant", "1 jour avant"]); R = [None, 5, 15, 60, 1440]
        rap.set_selected(R.index((e or {}).get("rappel", 15)) if (e or {}).get("rappel", 15) in R else 2); v.append(rap)
        err = label("", "petit", "attenue"); v.append(err)
        def ok():
            try:
                j = dt.datetime.strptime(date.get_text().strip(), "%d/%m/%Y").date()
                if journee.get_active(): a = dt.datetime.combine(j, dt.time(), ICI); z = a + dt.timedelta(days=1)
                else:
                    a = dt.datetime.combine(j, dt.datetime.strptime(h0.get_text().strip(), "%H:%M").time(), ICI); z = dt.datetime.combine(j, dt.datetime.strptime(h1.get_text().strip(), "%H:%M").time(), ICI)
                    if z <= a: z += dt.timedelta(days=1)
            except ValueError:
                err.set_text("Date (JJ/MM/AAAA) ou heure (HH:MM) à corriger."); return
            L = [x for x in locaux() if not e or x["id"] != e["id"]]
            L.append({"id": (e or {}).get("id") or uuid.uuid4().hex[:12], "titre": titre.get_text().strip() or "Sans titre", "debut": a.isoformat(), "fin": z.isoformat(),
                      "journee": journee.get_active(), "lieu": lieu.get_text().strip(), "rappel": R[rap.get_selected()]})
            sauver(L); self.jour = j; self.mois = j.replace(day=1); d.close(); self.rendu()
        b = boite(False, 8, halign=Gtk.Align.END)
        if e: b.append(bouton("Supprimer", "trash-2", "plat", rappel=lambda: (sauver([x for x in locaux() if x["id"] != e["id"]]), d.close(), self.rendu())))
        b.append(bouton("Annuler", None, "fantome", rappel=d.close)); b.append(bouton("Enregistrer", None, "pilule", rappel=ok)); v.append(b)
        d.present(); titre.grab_focus()

    def reglages(self):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Agendas", default_width=560); v = boite(True, 10, margin_top=18, margin_bottom=18, margin_start=18, margin_end=18); d.set_child(v)
        v.append(label("Agendas Google, Outlook, iCloud…", "gras"))
        v.append(label("Collez l'adresse iCal de l'agenda : Google Agenda › Paramètres de l'agenda › « Adresse secrète au format iCal » ; "
                       "Outlook › Paramètres › Calendriers partagés › « Publier un calendrier » › lien ICS. Affichés en lecture seule, mis à jour toutes les 30 minutes.", "petit", "attenue", wrap=True))
        zone = boite(True, 4); v.append(zone)
        def lister():
            vider(zone)
            for a in abonnements():
                r = boite(False, 8, "reglage"); r.append(label(a["nom"], "gras", hexpand=True))
                r.append(bouton(None, "trash-2", "plat", rappel=lambda a=a: (config.modifier(agenda_abonnements=[x for x in abonnements() if x["url"] != a["url"]]), lister(), self.rendu()))); zone.append(r)
        lister()
        nom = Gtk.Entry(placeholder_text="Nom (ex. Agenda Google pro)"); url = Gtk.Entry(placeholder_text="https://calendar.google.com/calendar/ical/…/basic.ics"); v.append(nom); v.append(url)
        etat = label("", "petit", "attenue", wrap=True)
        def ajouter():
            u = url.get_text().strip()
            if not u.startswith(("http", "webcal")): etat.set_text("Adresse iCal attendue (https://… ou webcal://…)."); return
            couleurs = ["#6aa8ff", "#5fd39a", "#ef6b6b", "#a371f7", "#ffca28"]
            config.modifier(agenda_abonnements=abonnements() + [{"nom": nom.get_text().strip() or "Agenda", "url": u, "couleur": couleurs[len(abonnements()) % 5]}])
            etat.set_text("Lecture de l'agenda…"); nom.set_text(""); url.set_text(""); lister()
            S.en_fond(maj_abonnements, lambda e: (etat.set_text("Ajouté ✓" if not e else "Agenda injoignable : vérifiez l'adresse"), self.rendu()), True)
        v.append(bouton("Ajouter cet agenda", "plus", "pilule", rappel=ajouter)); v.append(etat)
        v.append(label("Mon agenda", "gras"))
        def export():
            p = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or os.path.expanduser("~"), "Agenda XIII.ics"); exporter_ics(p)
            etat.set_text("Exporté : %s — à importer dans Google Agenda, Outlook ou la Suite XIII." % p)
        v.append(bouton("Exporter mon agenda (.ics)", "download", "fantome", rappel=export))
        d.present()


def main():
    sys.exit(Calendrier().run(sys.argv[:1]))
