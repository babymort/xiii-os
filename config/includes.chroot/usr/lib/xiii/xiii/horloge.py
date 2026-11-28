# OS XIII — Horloge XIII : horloges du monde, alarmes (sonnent même appli fermée : c'est la barre qui veille),
# minuteurs (plusieurs à la fois) et chronomètre avec tours. Façon Horloge de Windows 11 / macOS.
# Application développée par Matthieu Lamotte.
import os, sys, json, time, datetime, shutil, subprocess
from zoneinfo import ZoneInfo
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import config

FICHIER = os.path.join(config.DOSSIER, "horloge.json")
SON = "/usr/share/sounds/XIII/stereo/alarm-clock-elapsed.wav"
JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
VILLES = [("Paris", "Europe/Paris"), ("Londres", "Europe/London"), ("New York", "America/New_York"), ("Los Angeles", "America/Los_Angeles"),
          ("Montréal", "America/Toronto"), ("Tokyo", "Asia/Tokyo"), ("Pékin", "Asia/Shanghai"), ("Dubaï", "Asia/Dubai"), ("Sydney", "Australia/Sydney"),
          ("Berlin", "Europe/Berlin"), ("Madrid", "Europe/Madrid"), ("Rome", "Europe/Rome"), ("Moscou", "Europe/Moscow"), ("Mumbai", "Asia/Kolkata"),
          ("São Paulo", "America/Sao_Paulo"), ("Mexico", "America/Mexico_City"), ("Le Caire", "Africa/Cairo"), ("Dakar", "Africa/Dakar"),
          ("Casablanca", "Africa/Casablanca"), ("Pointe-à-Pitre", "America/Guadeloupe"), ("Saint-Denis (Réunion)", "Indian/Reunion"),
          ("Nouméa", "Pacific/Noumea"), ("Papeete", "Pacific/Tahiti"), ("Singapour", "Asia/Singapore"), ("Séoul", "Asia/Seoul"), ("Bangkok", "Asia/Bangkok")]


def charger():
    d = {"villes": ["New York", "Tokyo"], "alarmes": []}
    try: d.update(json.load(open(FICHIER, encoding="utf-8")))
    except Exception: pass
    return d


def enregistrer(d):
    os.makedirs(config.DOSSIER, exist_ok=True)
    json.dump(d, open(FICHIER + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(FICHIER + ".tmp", FICHIER)


def alarmes_dues(maintenant=None):
    """Alarmes à faire sonner à cette minute (appelé chaque minute par la barre). Une alarme sans jour ne sonne qu'une fois."""
    n = maintenant or datetime.datetime.now(); d = charger(); dues = []; change = False
    for a in d["alarmes"]:
        if not a.get("on", True) or a.get("h") != n.hour or a.get("m") != n.minute: continue
        if a.get("jours") and n.weekday() not in a["jours"]: continue
        cle = n.strftime("%Y%m%d%H%M")
        if a.get("derniere") == cle: continue
        a["derniere"] = cle; dues.append(a); change = True
        if not a.get("jours"): a["on"] = False
    d["alarmes"] = [a for a in d["alarmes"] if not (a.get("unique") and not a.get("on", True))]
    if change: enregistrer(d)
    return dues


def prochaine(a, n=None):
    n = n or datetime.datetime.now()
    for k in range(8):
        j = (n + datetime.timedelta(days=k)).replace(hour=a["h"], minute=a["m"], second=0, microsecond=0)
        if j <= n: continue
        if not a.get("jours") or j.weekday() in a["jours"]: return j
    return None


def dans(a):
    j = prochaine(a)
    if not j: return ""
    s = int((j - datetime.datetime.now()).total_seconds()) // 60
    return "dans %s" % ("%d h %02d" % (s // 60, s % 60) if s >= 60 else "%d min" % max(1, s))


def hms(t, centiemes=False):
    t = max(0, t); h, r = divmod(int(t), 3600); m, s = divmod(r, 60)
    base = ("%d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))
    return base + (",%02d" % int((t % 1) * 100) if centiemes else "")


def jouer_son(boucle=False):
    if not os.path.exists(SON): return None
    for cmd in (["pw-play", SON], ["paplay", SON], ["aplay", "-q", SON]):
        if shutil.which(cmd[0]):
            if boucle: cmd = ["sh", "-c", "while :; do %s; sleep .4; done" % " ".join(cmd)]
            try: return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError: continue
    return None


def arreter_son(p):
    if p is None: return
    try: os.killpg(p.pid, 15)
    except Exception: pass


class Horloge(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.horloge")

    def do_command_line(self, cl):
        a = cl.get_arguments()[1:]
        if a[:1] == ["--sonner"]: self.sonnerie(" ".join(a[1:]) or "Alarme")
        else:
            self.do_activate()
            if a[:1] in (["--minuteur"], ["--chrono"], ["--alarmes"]): self.pile.set_visible_child_name(a[0][2:])
        return 0

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        from .ui import boite, label, bouton, ico, vider, interrupteur
        from .appli import preparer
        self.ui = dict(boite=boite, label=label, bouton=bouton, ico=ico, vider=vider, interrupteur=interrupteur)
        preparer(""".gros { font-family: "IBM Plex Mono", monospace; font-size: 64px; font-weight: 300; }
            .moyen { font-family: "IBM Plex Mono", monospace; font-size: 30px; }
            .carte-h { background: alpha(currentColor, .05); border-radius: 16px; padding: 14px 18px; }
            .anneau { min-width: 220px; min-height: 220px; }""")
        self.d = charger(); self.minuteurs = []; self.chrono = [0.0, None, []]     # cumul, départ, tours
        self.win = Gtk.ApplicationWindow(application=self, title="Horloge XIII"); self.win.set_default_size(760, 560)
        v = boite(True, 0); self.pile = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True)
        for nom, titre, f in (("monde", "Horloges", self.p_monde), ("alarmes", "Alarmes", self.p_alarmes),
                              ("minuteur", "Minuteurs", self.p_minuteur), ("chrono", "Chronomètre", self.p_chrono)):
            self.pile.add_titled(f(), nom, titre)
        sw = Gtk.StackSwitcher(stack=self.pile, halign=Gtk.Align.CENTER, margin_top=10, margin_bottom=6)
        v.append(sw); v.append(self.pile); self.win.set_child(v); self.win.present()
        GLib.timeout_add(50, self.tic)
        self.win.connect("close-request", self.fermer)

    def fermer(self, *_):
        if any(m["fin"] for m in self.minuteurs):      # des minuteurs tournent : on garde l'appli en fond
            self.win.set_visible(False); self.hold(); self._tenu = True; return True
        return False

    # ------------------------------------------------------------ horloges du monde
    def p_monde(self):
        U = self.ui; v = U["boite"](True, 14, margin_start=24, margin_end=24, margin_top=16, margin_bottom=16)
        self.l_heure = U["label"]("", "gros", xalign=.5); self.l_jour = U["label"]("", "attenue", xalign=.5)
        v.append(self.l_heure); v.append(self.l_jour)
        self.b_villes = U["boite"](True, 8); sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(self.b_villes); v.append(sc)
        dd = Gtk.DropDown.new_from_strings(["Ajouter une ville…"] + [n for n, _ in VILLES])
        def ajout(d, _p):
            i = d.get_selected()
            if i > 0 and VILLES[i - 1][0] not in self.d["villes"]:
                self.d["villes"].append(VILLES[i - 1][0]); enregistrer(self.d); self.remplir_villes()
            if i: d.set_selected(0)
        dd.connect("notify::selected", ajout); v.append(dd)
        self.remplir_villes(); return v

    def remplir_villes(self):
        U = self.ui; U["vider"](self.b_villes); self.l_villes = []
        tz = dict(VILLES)
        for n in self.d["villes"]:
            if n not in tz: continue
            r = U["boite"](False, 12, "carte-h"); g = U["boite"](True, 2, hexpand=True)
            g.append(U["label"](n, "titre")); ec = U["label"]("", "attenue"); g.append(ec); r.append(g)
            h = U["label"]("", "moyen"); r.append(h)
            r.append(U["bouton"](None, "x", "fantome", rappel=lambda n=n: (self.d["villes"].remove(n), enregistrer(self.d), self.remplir_villes()), tip="Retirer"))
            self.b_villes.append(r); self.l_villes.append((ZoneInfo(tz[n]), h, ec))
        self.maj_villes()

    def maj_villes(self):
        n = datetime.datetime.now().astimezone()
        self.l_heure.set_text(n.strftime("%H:%M:%S"))
        self.l_jour.set_text(n.strftime("%A %d %B %Y").capitalize())
        for z, h, ec in self.l_villes:
            t = n.astimezone(z); dh = (t.utcoffset() - n.utcoffset()).total_seconds() / 3600
            jour = "aujourd'hui" if t.date() == n.date() else ("demain" if t.date() > n.date() else "hier")
            h.set_text(t.strftime("%H:%M"))
            ec.set_text("%s, %s%s h" % (jour, "+" if dh >= 0 else "−", ("%g" % abs(dh)).replace(".", ",")))

    # ------------------------------------------------------------ alarmes
    def p_alarmes(self):
        U = self.ui; v = U["boite"](True, 10, margin_start=24, margin_end=24, margin_top=16, margin_bottom=16)
        h = U["boite"](False, 8); h.append(U["label"]("Les alarmes sonnent même quand Horloge est fermée.", "attenue", hexpand=True, wrap=True))
        h.append(U["bouton"]("Nouvelle alarme", "plus", "pilule", rappel=lambda: self.editer_alarme(None))); v.append(h)
        self.b_alarmes = U["boite"](True, 8); sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(self.b_alarmes); v.append(sc)
        self.remplir_alarmes(); return v

    def remplir_alarmes(self):
        U = self.ui; U["vider"](self.b_alarmes)
        if not self.d["alarmes"]: self.b_alarmes.append(U["label"]("Aucune alarme.", "attenue", xalign=.5))
        for a in sorted(self.d["alarmes"], key=lambda a: (a["h"], a["m"])):
            r = U["boite"](False, 12, "carte-h"); g = U["boite"](True, 2, hexpand=True)
            g.append(U["label"]("%02d:%02d" % (a["h"], a["m"]), "moyen"))
            j = "Tous les jours" if len(a.get("jours") or []) == 7 else ", ".join(JOURS[k] for k in a.get("jours") or []) or "Une fois"
            g.append(U["label"]("%s · %s %s" % (a.get("nom") or "Alarme", j, dans(a) if a.get("on", True) else ""), "attenue"))
            ev = Gtk.GestureClick(); ev.connect("released", lambda *_, a=a: self.editer_alarme(a)); g.add_controller(ev)
            r.append(g)
            def bascule(on, a=a):
                a["on"] = on; enregistrer(self.d); GLib.idle_add(lambda: (self.remplir_alarmes(), False)[1])
            r.append(U["interrupteur"](a.get("on", True), bascule))
            self.b_alarmes.append(r)

    def editer_alarme(self, a):
        U = self.ui; neuf = a is None
        a = a or {"id": str(int(time.time() * 1000)), "h": 7, "m": 0, "jours": [0, 1, 2, 3, 4], "nom": "Réveil", "on": True}
        dlg = Gtk.Window(transient_for=self.win, modal=True, title="Alarme"); v = U["boite"](True, 12, margin_start=20, margin_end=20, margin_top=18, margin_bottom=18)
        r = U["boite"](False, 6, halign=Gtk.Align.CENTER)
        hh = Gtk.SpinButton.new_with_range(0, 23, 1); hh.set_value(a["h"]); mm = Gtk.SpinButton.new_with_range(0, 59, 1); mm.set_value(a["m"])
        for s in (hh, mm): s.set_orientation(Gtk.Orientation.VERTICAL); s.connect("output", lambda s: (s.set_text("%02d" % s.get_value_as_int()), True)[1]); s.add_css_class("moyen")
        r.append(hh); r.append(U["label"](":", "moyen")); r.append(mm); v.append(r)
        nom = Gtk.Entry(text=a.get("nom", "")); v.append(nom)
        jr = U["boite"](False, 4, halign=Gtk.Align.CENTER); cases = []
        for k, j in enumerate(JOURS):
            t = Gtk.ToggleButton(label=j, active=k in (a.get("jours") or [])); jr.append(t); cases.append(t)
        v.append(jr)
        b = U["boite"](False, 8, halign=Gtk.Align.END)
        if not neuf: b.append(U["bouton"]("Supprimer", "trash-2", "fantome", rappel=lambda: (self.d["alarmes"].remove(a), enregistrer(self.d), self.remplir_alarmes(), dlg.close())))
        def ok():
            a.update(h=hh.get_value_as_int(), m=mm.get_value_as_int(), nom=nom.get_text().strip() or "Alarme", on=True,
                     jours=[k for k, t in enumerate(cases) if t.get_active()], derniere=None)
            if neuf: self.d["alarmes"].append(a)
            enregistrer(self.d); self.remplir_alarmes(); dlg.close()
        b.append(U["bouton"]("Enregistrer", "check", "pilule", rappel=ok)); v.append(b)
        dlg.set_child(v); dlg.present()

    def sonnerie(self, nom):
        """Fenêtre de sonnerie (lancée par la barre à l'heure dite) : Arrêter ou Répéter dans 10 min."""
        from .ui import boite, label, bouton, ico
        from .appli import preparer
        preparer(".gros { font-family: 'IBM Plex Mono', monospace; font-size: 64px; font-weight: 300; }")
        w = Gtk.Window(application=self, title="Alarme"); w.set_default_size(420, 300)
        v = boite(True, 14, margin_start=24, margin_end=24, margin_top=24, margin_bottom=24, valign=Gtk.Align.CENTER)
        v.append(ico("alarm-clock", 48, "c")); v.append(label(datetime.datetime.now().strftime("%H:%M"), "gros", xalign=.5)); v.append(label(nom, "titre", xalign=.5))
        p = jouer_son(True)
        def fin(rep):
            arreter_son(p)
            if rep:
                t = datetime.datetime.now() + datetime.timedelta(minutes=10); d = charger()
                d["alarmes"].append({"id": "r" + str(int(time.time())), "h": t.hour, "m": t.minute, "jours": [], "nom": nom, "on": True, "unique": True}); enregistrer(d)
            w.destroy()
        r = boite(False, 10, halign=Gtk.Align.CENTER)
        r.append(bouton("Répéter (10 min)", "alarm-clock-plus", "fantome", rappel=lambda: fin(True)))
        r.append(bouton("Arrêter", "square", "pilule", rappel=lambda: fin(False))); v.append(r)
        w.connect("close-request", lambda *_: (arreter_son(p), False)[1])
        GLib.timeout_add_seconds(300, lambda: (fin(False) if w.get_visible() else None, False)[1])   # 5 min sans réponse : on se tait
        w.set_child(v); w.present()

    # ------------------------------------------------------------ minuteurs
    def p_minuteur(self):
        U = self.ui; v = U["boite"](True, 12, margin_start=24, margin_end=24, margin_top=16, margin_bottom=16)
        r = U["boite"](False, 8, halign=Gtk.Align.CENTER)
        for n in (1, 3, 5, 10, 15, 25, 45, 60):
            r.append(U["bouton"]("%d min" % n if n < 60 else "1 h", None, "fantome", rappel=lambda n=n: self.ajouter_minuteur(60 * n, "%d min" % n if n < 60 else "1 h")))
        v.append(r)
        p = U["boite"](False, 6, halign=Gtk.Align.CENTER)
        self.s_h = Gtk.SpinButton.new_with_range(0, 23, 1); self.s_m = Gtk.SpinButton.new_with_range(0, 59, 1); self.s_s = Gtk.SpinButton.new_with_range(0, 59, 1)
        self.s_m.set_value(5)
        for s, u in ((self.s_h, "h"), (self.s_m, "min"), (self.s_s, "s")): p.append(s); p.append(U["label"](u, "attenue"))
        p.append(U["bouton"]("Démarrer", "play", "pilule", rappel=lambda: self.ajouter_minuteur(
            self.s_h.get_value_as_int() * 3600 + self.s_m.get_value_as_int() * 60 + self.s_s.get_value_as_int())))
        v.append(p)
        self.b_min = U["boite"](True, 8); sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(self.b_min); v.append(sc)
        return v

    def ajouter_minuteur(self, s, nom=None):
        if s <= 0: return
        U = self.ui; m = {"total": s, "fin": time.time() + s, "reste": s, "nom": nom or hms(s), "son": None}
        r = U["boite"](False, 12, "carte-h"); m["l"] = U["label"](hms(s), "moyen", hexpand=True)
        g = U["boite"](True, 4, hexpand=True); g.append(U["label"](m["nom"], "attenue")); g.append(m["l"])
        m["barre"] = Gtk.ProgressBar(fraction=1); g.append(m["barre"]); r.append(g)
        m["bp"] = U["bouton"](None, "pause", "fantome", rappel=lambda: self.pause_minuteur(m), tip="Pause / reprendre"); r.append(m["bp"])
        r.append(U["bouton"](None, "rotate-ccw", "fantome", rappel=lambda: m.update(fin=time.time() + m["total"], reste=m["total"]), tip="Recommencer"))
        r.append(U["bouton"](None, "x", "fantome", rappel=lambda: (arreter_son(m["son"]), self.minuteurs.remove(m), self.b_min.remove(r)), tip="Supprimer"))
        m["w"] = r; self.minuteurs.append(m); self.b_min.prepend(r)

    def pause_minuteur(self, m):
        if m["son"]: arreter_son(m["son"]); m["son"] = None; m["fin"] = None; m["reste"] = m["total"]; return
        if m["fin"]: m["reste"] = m["fin"] - time.time(); m["fin"] = None
        else: m["fin"] = time.time() + m["reste"]

    # ------------------------------------------------------------ chronomètre
    def p_chrono(self):
        U = self.ui; v = U["boite"](True, 14, margin_start=24, margin_end=24, margin_top=16, margin_bottom=16)
        self.l_chrono = U["label"]("00:00,00", "gros", xalign=.5); v.append(self.l_chrono)
        r = U["boite"](False, 10, halign=Gtk.Align.CENTER)
        self.b_go = U["bouton"]("Démarrer", "play", "pilule", rappel=self.chrono_go); r.append(self.b_go)
        r.append(U["bouton"]("Tour", "flag", "fantome", rappel=self.chrono_tour)); r.append(U["bouton"]("Remettre à zéro", "rotate-ccw", "fantome", rappel=self.chrono_zero))
        v.append(r)
        self.b_tours = U["boite"](True, 4); sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(self.b_tours); v.append(sc)
        return v

    def chrono_t(self):
        c = self.chrono; return c[0] + (time.time() - c[1] if c[1] else 0)

    def chrono_go(self):
        c = self.chrono
        if c[1]: c[0] += time.time() - c[1]; c[1] = None
        else: c[1] = time.time()
        self.b_go.get_child().get_last_child().set_text("Pause" if c[1] else "Reprendre")

    def chrono_tour(self):
        t = self.chrono_t(); c = self.chrono
        if not t: return
        prec = c[2][-1] if c[2] else 0; c[2].append(t)
        r = self.ui["boite"](False, 10); r.append(self.ui["label"]("Tour %d" % len(c[2]), hexpand=True))
        r.append(self.ui["label"]("+" + hms(t - prec, True), "chiffre")); r.append(self.ui["label"](hms(t, True), "chiffre"))
        self.b_tours.prepend(r)

    def chrono_zero(self):
        self.chrono[:] = [0.0, None, []]; self.ui["vider"](self.b_tours); self.b_go.get_child().get_last_child().set_text("Démarrer")

    # ------------------------------------------------------------ boucle
    def tic(self):
        if self.pile.get_visible_child_name() == "monde": self.maj_villes()
        self.l_chrono.set_text(hms(self.chrono_t(), True))
        for m in self.minuteurs:
            reste = (m["fin"] - time.time()) if m["fin"] else m["reste"]
            m["l"].set_text(hms(reste + .999) if reste > 0 else "Terminé"); m["barre"].set_fraction(max(0, reste) / m["total"])
            if m["fin"] and reste <= 0 and not m["son"]:
                m["son"] = jouer_son(True); m["fin"] = None; m["reste"] = 0
                subprocess.Popen(["notify-send", "-a", "Horloge", "-i", "xiii-horloge", "-u", "critical", "Minuteur terminé", m["nom"]], stderr=subprocess.DEVNULL)
                self.win.present()
                GLib.timeout_add_seconds(60, lambda m=m: (arreter_son(m["son"]), m.update(son=None), False)[2])
        if getattr(self, "_tenu", False) and not any(m["fin"] for m in self.minuteurs) and not self.win.get_visible():
            self._tenu = False; self.release()
        return True


def main():
    from gi.repository import Gio
    app = Horloge(); app.set_flags(app.get_flags() | Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
    sys.exit(app.run(sys.argv))
