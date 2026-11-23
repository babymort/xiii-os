# OS XIII — Moniteur système / Gestionnaire des tâches (Ctrl + Maj + Échap), façon Windows : processus (processeur, mémoire,
# fin de tâche), performances en graphes (processeur, mémoire, carte graphique, disque, réseau), températures,
# « Fermer ce qui bloque » (programmes bloqués à 100 %, ou qui dévorent la mémoire), applications au démarrage.
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

def gpu():
    """(nom, % d'utilisation ou None, mémoire utilisée, mémoire totale) — NVIDIA (nvidia-smi), AMD et Intel récents (sysfs)."""
    if S.DEMO: return ("GeForce GTX 1660", 23.0, 1.1e9, 6e9)
    import shutil, subprocess
    if shutil.which("nvidia-smi"):
        try:
            o = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3).stdout.split(",")
            return (o[0].strip(), float(o[1]), float(o[2]) * 1048576, float(o[3]) * 1048576)
        except Exception: pass
    for c in sorted(glob.glob("/sys/class/drm/card[0-9]/device")):
        try:
            u = float(open(c + "/gpu_busy_percent").read())
            mu = float(open(c + "/mem_info_vram_used").read()) if os.path.exists(c + "/mem_info_vram_used") else 0
            mt = float(open(c + "/mem_info_vram_total").read()) if os.path.exists(c + "/mem_info_vram_total") else 0
            return ("Carte graphique AMD", u, mu, mt)
        except (OSError, ValueError): continue
    for c in sorted(glob.glob("/sys/class/drm/card[0-9]")):     # Intel : fréquence actuelle / maximale, faute de taux d'utilisation lisible
        try:
            act = float(open(c + "/gt_act_freq_mhz").read()); mx = float(open(c + "/gt_max_freq_mhz").read())
            return ("Graphique Intel (fréquence)", 100 * act / mx if mx else None, 0, 0)
        except (OSError, ValueError): continue
    return None

def temperatures():
    """[(nom, °C)] : processeur, carte graphique, disques NVMe, Wi-Fi… (capteurs hwmon)."""
    if S.DEMO: return [("Processeur", 52.0), ("Carte graphique", 47.0), ("Disque NVMe", 38.0)]
    NOMS = {"coretemp": "Processeur", "k10temp": "Processeur", "zenpower": "Processeur", "cpu_thermal": "Processeur", "amdgpu": "Carte graphique", "nouveau": "Carte graphique",
            "nvme": "Disque NVMe", "iwlwifi_1": "Wi-Fi", "acpitz": "Carte mère", "pch_cannonlake": "Chipset", "drivetemp": "Disque"}
    L = []
    for h in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try: n = open(h + "/name").read().strip()
        except OSError: continue
        t = []
        for f in glob.glob(h + "/temp*_input"):
            try: t.append(int(open(f).read()) / 1000)
            except (OSError, ValueError): pass
        if t: L.append((NOMS.get(n, n), max(t)))
    return L

def etat_proc(pid):
    try: return open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError): return "?"

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
        self.win = Gtk.ApplicationWindow(application=self, title="Moniteur système XIII"); self.win.set_default_size(980, 680); self.histo = {}
        racine = boite(False, 0)
        nav = boite(True, 4, "nav", margin_start=10, margin_end=10, margin_top=12); nav.set_size_request(200, -1)
        nav.append(label("Moniteur système", "titre-astoria", margin_bottom=10))
        self.pile = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True)
        for cle, ic, nom, fn in (("proc", "list", "Processus", self.page_proc), ("perf", "activity", "Performances", self.page_perf),
                                 ("bloque", "octagon-x" if os.path.exists("/usr/share/xiii/lucide/octagon-x.svg") else "x", "Ce qui bloque", self.page_bloque), ("demarrage", "rocket", "Démarrage", self.page_demarrage)):
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
        self.gpu_info = gpu()
        cartes = [("cpu", "cpu", "Processeur", 100.0), ("mem", "memory-stick", "Mémoire", 100.0)]
        if self.gpu_info: cartes.append(("gpu", "monitor", "Carte graphique · " + self.gpu_info[0], 100.0))
        cartes += [("disque", "hard-drive", "Disque (lecture + écriture)", None), ("net", "network", "Réseau (réception + envoi)", None)]
        for cle, ic, titre, maxi in cartes:
            c = boite(True, 6, "carte"); h = boite(False, 8); h.append(ico(ic, 16, "c")); h.append(label(titre, "gras", hexpand=True))
            val = label("—", "chiffre", "petit"); h.append(val); c.append(h)
            g = Graphe(maxi); c.append(g); v.append(c); self.g[cle] = (g, val)
        try: modele = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
        except Exception: modele = ""
        c = boite(True, 6, "carte"); h = boite(False, 8); h.append(ico("thermometer", 16, "c")); h.append(label("Températures", "gras", hexpand=True)); c.append(h)
        self.l_temp = boite(False, 18); c.append(self.l_temp); v.append(c)
        v.append(label("%s · %d cœurs logiques · démarré depuis %s" % (modele, NCPU, self.duree()), "petit", "attenue", wrap=True))
        return sc

    # ------------------------------------------------------------- ce qui bloque
    def page_bloque(self):
        sc = Gtk.ScrolledWindow(); v = boite(True, 10, margin_start=14, margin_end=14, margin_top=12, margin_bottom=12); sc.set_child(v)
        h = boite(False, 10); h.append(ico("octagon-x" if os.path.exists("/usr/share/xiii/lucide/octagon-x.svg") else "x", 28, "c"))
        t = boite(True, 0, hexpand=True); t.append(label("Fermer ce qui bloque", "gras")); t.append(label("Programmes bloqués à fond sur le processeur depuis plus de 10 secondes, figés, ou qui prennent plus du tiers de la mémoire.", "petit", "attenue", wrap=True)); h.append(t)
        self.b_tout = bouton("Tout fermer", "x", "pilule", rappel=self.fermer_bloquants); self.b_tout.set_sensitive(False); h.append(self.b_tout); v.append(h)
        self.l_bloque = boite(True, 4); v.append(self.l_bloque)
        return sc

    def bloquants(self):
        L = []; tot = self.mem[0]
        for p in self.procs:
            if p["uid"] != MOI or p["pid"] == os.getpid(): continue
            H = self.histo.get(p["pid"], [])
            raison = None
            if len(H) >= 7 and min(H[-7:]) > 85: raison = "à %d %% du processeur depuis plus de 10 s" % (sum(H[-7:]) / 7)
            elif p["rss"] > tot / 3: raison = "occupe %s de mémoire (%d %%)" % (S.humain(p["rss"]), 100 * p["rss"] / tot)
            elif etat_proc(p["pid"]) == "D" and len(H) >= 7: raison = "figé (en attente d'un disque ou d'un appareil)"
            if raison: L.append((p, raison))
        return L

    def fermer_bloquants(self):
        for p, _r in self.bloquants():
            try: os.kill(p["pid"], signal.SIGTERM); GLib.timeout_add(2500, lambda pid=p["pid"]: (self._forcer(pid), False)[1])
            except OSError: pass

    def maj_bloque(self):
        if not hasattr(self, "l_bloque"): return
        L = self.bloquants(); sig = [(p["pid"], r) for p, r in L]
        if sig == getattr(self, "_sig_bloque", None): return
        self._sig_bloque = sig; vider(self.l_bloque); self.b_tout.set_sensitive(bool(L))
        if not L: self.l_bloque.append(label("Rien ne bloque en ce moment ✓", "attenue")); return
        for p, r in L:
            ligne = boite(False, 10, "reglage"); ligne.append(ico("triangle-alert", 18, "c")); t = boite(True, 0, hexpand=True)
            t.append(label(p["nom"], "gras")); t.append(label(r, "petit", "attenue")); ligne.append(t)
            ligne.append(bouton("Fermer", None, "fantome", rappel=lambda pid=p["pid"]: (setattr(self, "choix", pid), self.fin())))
            ligne.append(bouton("Forcer", None, "plat", rappel=lambda pid=p["pid"]: self._forcer(pid))); self.l_bloque.append(ligne)

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
        vivants = set()
        for p in self.procs:
            vivants.add(p["pid"]); H = self.histo.setdefault(p["pid"], []); H.append(p.get("cpu", 0)); del H[:-10]
        for k in list(self.histo):
            if k not in vivants: del self.histo[k]
        if "gpu" in self.g:
            gi_ = gpu()
            if gi_ and gi_[1] is not None:
                self.g["gpu"][0].ajouter(gi_[1]); self.g["gpu"][1].set_text("%d %%" % gi_[1] + (" · %s / %s" % (S.humain(gi_[2]), S.humain(gi_[3])) if gi_[3] else ""))
        if getattr(self, "_n_temp", 0) % 3 == 0 and hasattr(self, "l_temp"):
            vider(self.l_temp)
            T = temperatures()
            for n, t in T or [("Aucun capteur lisible", None)]:
                c = boite(True, 0); c.append(label(n, "petit", "attenue"))
                if t is not None: c.append(label("%d °C" % t, *(("chiffre", "gras", "accent") if t >= 85 else ("chiffre", "gras"))))
                self.l_temp.append(c)
        self._n_temp = getattr(self, "_n_temp", 0) + 1
        self.maj_bloque()
        self.remplir()
        return True

def main():
    sys.exit(Taches().run(sys.argv))
