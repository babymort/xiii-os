# OS XIII — Gestionnaire des tâches (Ctrl + Maj + Échap), façon Windows :
# processus (processeur, mémoire, fin de tâche), performances en graphes, applications au démarrage.
# Application développée par Matthieu Lamotte.
import os, sys, time, signal, pwd, glob, configparser
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, theme, systeme as S
from .ui import *

HZ = os.sysconf("SC_CLK_TCK"); PAGE = os.sysconf("SC_PAGE_SIZE"); NCPU = os.cpu_count() or 1
MOI = os.getuid()

def processus():
    L = []
    for d in os.listdir("/proc"):
        if not d.isdigit(): continue
        try:
            st = open("/proc/%s/stat" % d).read()
            nom = st[st.find("(") + 1:st.rfind(")")]; f = st[st.rfind(")") + 2:].split()
            temps = int(f[11]) + int(f[12]); rss = int(f[21]) * PAGE
            uid = os.stat("/proc/" + d).st_uid
            try: cmd = open("/proc/%s/cmdline" % d, "rb").read().split(b"\0")[0].decode(errors="replace")
            except OSError: cmd = ""
            if cmd and os.path.basename(cmd) not in ("python3", "sh", "bash"): nom = os.path.basename(cmd)[:40] or nom
            elif cmd:
                a = open("/proc/%s/cmdline" % d, "rb").read().split(b"\0")
                m = next((x.decode(errors="replace") for x in a[1:] if b"xiii." in x), None)
                if m and "import" in m: nom = "XIII · " + m.split("xiii.")[1].split(" ")[0].split(".")[0]
            L.append({"pid": int(d), "nom": nom, "temps": temps, "rss": rss, "uid": uid})
        except (OSError, ValueError, IndexError):
            pass
    return L

def cpu_total():
    v = [int(x) for x in open("/proc/stat").readline().split()[1:]]
    return sum(v), v[3] + v[4]

def memoire():
    m = {}
    for l in open("/proc/meminfo"):
        k, v = l.split(":"); m[k] = int(v.split()[0]) * 1024
    return m["MemTotal"], m["MemTotal"] - m["MemAvailable"]

def disque_io():
    lu = ec = 0
    for l in open("/proc/diskstats"):
        f = l.split()
        if f[2].startswith(("loop", "ram", "zram")) or f[2][-1].isdigit() and not f[2].startswith("nvme"): continue
        lu += int(f[5]) * 512; ec += int(f[9]) * 512
    return lu, ec

def reseau_io():
    rx = tx = 0
    for l in open("/proc/net/dev").readlines()[2:]:
        n, v = l.split(":", 1)
        if n.strip() == "lo": continue
        v = v.split(); rx += int(v[0]); tx += int(v[8])
    return rx, tx

class Graphe(Gtk.DrawingArea):
    def __init__(self, maxi=100.0):
        super().__init__(); self.v = [0.0] * 60; self.maxi = maxi; self.auto = maxi is None
        self.set_size_request(-1, 110); self.set_draw_func(self.dessin)
    def ajouter(self, x):
        self.v = self.v[1:] + [x]; self.queue_draw()
    def dessin(self, a, cr, w, h):
        rgba = self.get_color(); acc = Gdk.RGBA(); acc.parse(ACC.get("c", "#f0b378"))
        m = (max(self.v) * 1.2 or 1) if self.auto else self.maxi
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, .08); cr.rectangle(0, 0, w, h); cr.fill()
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, .12)
        for i in range(1, 4): cr.move_to(0, h * i / 4); cr.line_to(w, h * i / 4)
        cr.set_line_width(1); cr.stroke()
        pas = w / (len(self.v) - 1)
        cr.move_to(0, h)
        for i, x in enumerate(self.v): cr.line_to(i * pas, h - h * min(1, x / m))
        cr.line_to(w, h); cr.close_path(); cr.set_source_rgba(acc.red, acc.green, acc.blue, .25); cr.fill_preserve()
        cr.new_path()
        for i, x in enumerate(self.v): (cr.move_to if i == 0 else cr.line_to)(i * pas, h - h * min(1, x / m))
        cr.set_source_rgba(acc.red, acc.green, acc.blue, 1); cr.set_line_width(2); cr.stroke()

class Taches(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.taches")
        self.avant = {}; self.t_avant = None; self.tri = "cpu"; self.filtre = ""; self.tous = False; self.choix = None

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        cfg = config.charger(); couleurs(cfg)
        css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(cfg) + """
            .ligne-proc { padding: 4px 10px; border-radius: 8px; } .ligne-proc:hover { background: alpha(currentColor, .06); }
            .ligne-proc.choisi { background: alpha(@accent_bg_color, .22); } .chiffre { font-family: "IBM Plex Mono", monospace; }""")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.win = Gtk.ApplicationWindow(application=self, title="Gestionnaire des tâches"); self.win.set_default_size(900, 620)
        racine = boite(False, 0)
        nav = boite(True, 4, "nav", margin_start=10, margin_end=10, margin_top=12); nav.set_size_request(200, -1)
        nav.append(label("Gestionnaire des tâches", "titre-astoria", margin_bottom=10))
        self.pile = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True)
        for cle, ic, nom, fn in (("proc", "list", "Processus", self.page_proc), ("perf", "activity", "Performances", self.page_perf), ("demarrage", "rocket", "Démarrage", self.page_demarrage)):
            self.pile.add_named(fn(), cle)
            b = bouton(nom, ic, "plat", "nav-item", rappel=lambda c=cle: self.pile.set_visible_child_name(c)); b.set_halign(Gtk.Align.FILL); nav.append(b)
        racine.append(nav); racine.append(self.pile); self.win.set_child(racine)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", lambda c, kv, *_: (self.fin(), True)[1] if kv == Gdk.KEY_Delete else False); self.win.add_controller(k)
        self.tic(); GLib.timeout_add(1500, self.tic); self.win.present()

    # ------------------------------------------------------------- processus
    def page_proc(self):
        v = boite(True, 8, margin_start=14, margin_end=14, margin_top=12, margin_bottom=12)
        h = boite(False, 8)
        e = Gtk.SearchEntry(placeholder_text="Rechercher un processus", hexpand=True); e.connect("search-changed", lambda w: (setattr(self, "filtre", w.get_text().lower()), self.remplir())); h.append(e)
        t = Gtk.CheckButton(label="Tous les utilisateurs"); t.connect("toggled", lambda w: (setattr(self, "tous", w.get_active()), self.remplir())); h.append(t)
        self.b_fin = bouton("Fin de tâche", "x", "pilule", rappel=self.fin); self.b_fin.set_sensitive(False); h.append(self.b_fin)
        v.append(h)
        en = boite(False, 8, margin_start=10, margin_end=10)
        for txt, cle, larg in (("Nom", "nom", None), ("PID", "pid", 70), ("Processeur", "cpu", 100), ("Mémoire", "rss", 100)):
            b = bouton(txt, None, "plat", "petit", rappel=lambda c=cle: (setattr(self, "tri", c), self.remplir()))
            if larg: b.set_size_request(larg, -1)
            else: b.set_hexpand(True); b.set_halign(Gtk.Align.START)
            en.append(b)
        v.append(en)
        sc = Gtk.ScrolledWindow(vexpand=True); self.liste = boite(True, 0); sc.set_child(self.liste); v.append(sc)
        self.resume = label("", "petit", "attenue"); v.append(self.resume)
        return v

    def fin(self):
        if not self.choix: return
        try:
            os.kill(self.choix, signal.SIGTERM)
            GLib.timeout_add(2500, lambda p=self.choix: (self._forcer(p), False)[1])
        except PermissionError:
            S.detacher(["pkexec", "kill", str(self.choix)])
        except ProcessLookupError:
            pass
        self.choix = None; self.b_fin.set_sensitive(False)

    def _forcer(self, p):
        try: os.kill(p, 0); os.kill(p, signal.SIGKILL)
        except OSError: pass

    def remplir(self):
        L = [p for p in self.procs if (self.tous or p["uid"] == MOI) and (not self.filtre or self.filtre in p["nom"].lower())]
        cle = {"nom": lambda p: p["nom"].lower(), "pid": lambda p: p["pid"], "cpu": lambda p: -p.get("cpu", 0), "rss": lambda p: -p["rss"]}[self.tri]
        L.sort(key=cle)
        vider(self.liste)
        for p in L[:200]:
            r = boite(False, 8, "ligne-proc")
            if p["pid"] == self.choix: r.add_css_class("choisi")
            r.append(label(p["nom"], hexpand=True, ellipsize=True))
            for txt, larg in ((str(p["pid"]), 70), ("%.1f %%" % p.get("cpu", 0), 100), (S.humain(p["rss"]), 100)):
                l = label(txt, "chiffre", "petit", xalign=1); l.set_size_request(larg, -1); r.append(l)
            g = Gtk.GestureClick(); g.connect("released", lambda *_a, pid=p["pid"]: (setattr(self, "choix", pid), self.b_fin.set_sensitive(True), self.remplir())); r.add_controller(g)
            g2 = Gtk.GestureClick(button=3)
            g2.connect("released", lambda *_a, pid=p["pid"], w=r: (setattr(self, "choix", pid), self.b_fin.set_sensitive(True),
                       popover_menu(w, [("x", "Fin de tâche", self.fin), ("skull", "Forcer l'arrêt", lambda: self._forcer(pid)),
                                        ("folder-open", "Ouvrir l'emplacement", lambda: S.detacher(["thunar", os.path.dirname(os.path.realpath("/proc/%d/exe" % pid))]) if os.access("/proc/%d/exe" % pid, os.R_OK) else None)])))
            r.add_controller(g2)
            self.liste.append(r)
        self.resume.set_text("%d processus · processeur %d %% · mémoire %s / %s" % (len(self.procs), self.cpu_pc, S.humain(self.mem[1]), S.humain(self.mem[0])))

    # ------------------------------------------------------------- performances
    def page_perf(self):
        sc = Gtk.ScrolledWindow(); v = boite(True, 14, margin_start=14, margin_end=14, margin_top=12, margin_bottom=12); sc.set_child(v)
        self.g = {}
        for cle, ic, titre, maxi in (("cpu", "cpu", "Processeur", 100.0), ("mem", "memory-stick", "Mémoire", 100.0), ("disque", "hard-drive", "Disque (lecture + écriture)", None), ("net", "network", "Réseau (réception + envoi)", None)):
            c = boite(True, 6, "carte"); h = boite(False, 8); h.append(ico(ic, 16, "c")); h.append(label(titre, "gras", hexpand=True))
            val = label("—", "chiffre", "petit"); h.append(val); c.append(h)
            g = Graphe(maxi); c.append(g); v.append(c); self.g[cle] = (g, val)
        try: modele = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
        except Exception: modele = ""
        v.append(label("%s · %d cœurs logiques · démarré depuis %s" % (modele, NCPU, self.duree()), "petit", "attenue", wrap=True))
        return sc

    def duree(self):
        s = int(float(open("/proc/uptime").read().split()[0])); return "%d h %02d" % (s // 3600, s % 3600 // 60)

    # ------------------------------------------------------------- démarrage
    def page_demarrage(self):
        sc = Gtk.ScrolledWindow(); v = boite(True, 8, margin_start=14, margin_end=14, margin_top=12, margin_bottom=12); sc.set_child(v)
        v.append(label("Applications lancées à l'ouverture de session", "gras"))
        perso = os.path.join(GLib.get_user_config_dir(), "autostart")
        vus = {}
        for d in ("/etc/xdg/autostart", perso):
            for f in sorted(glob.glob(os.path.join(d, "*.desktop"))): vus[os.path.basename(f)] = f
        for nom, f in sorted(vus.items()):
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            try: cp.read(f, encoding="utf-8"); e = cp["Desktop Entry"]
            except Exception: continue
            if e.get("NoDisplay", "false") == "true" and not f.startswith(perso): continue
            actif = e.get("Hidden", "false") != "true" and e.get("X-GNOME-Autostart-enabled", "true") != "false"
            def basculer(on, nom=nom, f=f):
                os.makedirs(perso, exist_ok=True); dst = os.path.join(perso, nom)
                t = open(f).read() if os.path.exists(f) else "[Desktop Entry]\n"
                import re
                t = re.sub(r"(?m)^Hidden=.*\n?", "", t).replace("[Desktop Entry]\n", "[Desktop Entry]\nHidden=%s\n" % ("false" if on else "true"), 1)
                open(dst, "w").write(t)
            r = boite(False, 10, "reglage")
            r.append(ico("rocket", 16, "d")); col = boite(True, 0, hexpand=True)
            col.append(label(e.get("Name[fr]", e.get("Name", nom)), "gras")); col.append(label(e.get("Comment[fr]", e.get("Comment", "")), "petit", "attenue", ellipsize=True))
            r.append(col); sw = Gtk.Switch(active=actif, valign=Gtk.Align.CENTER); sw.connect("notify::active", lambda w, *_x, b=basculer: b(w.get_active())); r.append(sw)
            v.append(r)
        return sc

    # ------------------------------------------------------------- mesure
    def tic(self):
        t, idle = cpu_total(); now = time.time()
        self.procs = processus(); self.mem = memoire()
        if self.t_avant:
            dt_tot = max(1, t - self.t_avant[0]); self.cpu_pc = 100 * (1 - (idle - self.t_avant[1]) / dt_tot)
            for p in self.procs:
                a = self.avant.get(p["pid"]); p["cpu"] = 100 * NCPU * (p["temps"] - a) / dt_tot if a is not None else 0
        else:
            self.cpu_pc = 0
        self.avant = {p["pid"]: p["temps"] for p in self.procs}; self.t_avant = (t, idle)
        io, net = disque_io(), reseau_io(); dt = now - getattr(self, "now", now) or 1
        if hasattr(self, "io0"):
            d = (io[0] - self.io0[0] + io[1] - self.io0[1]) / dt; n = (net[0] - self.net0[0] + net[1] - self.net0[1]) / dt
            self.g["disque"][0].ajouter(d); self.g["disque"][1].set_text(S.humain(d) + "/s")
            self.g["net"][0].ajouter(n); self.g["net"][1].set_text(S.humain(n) + "/s")
        self.io0, self.net0, self.now = io, net, now
        self.g["cpu"][0].ajouter(self.cpu_pc); self.g["cpu"][1].set_text("%d %%" % self.cpu_pc)
        pm = 100 * self.mem[1] / self.mem[0]; self.g["mem"][0].ajouter(pm); self.g["mem"][1].set_text("%s / %s" % (S.humain(self.mem[1]), S.humain(self.mem[0])))
        self.remplir()
        return True

def main():
    sys.exit(Taches().run(sys.argv))
