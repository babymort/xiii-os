# OS XIII — Applications Windows : un double-clic sur un .exe ou un .msi l'installe ou le lance, comme sous Windows.
# Chaque logiciel reçoit son propre environnement Windows isolé (préfixe Wine), ses composants (Visual C++, .NET,
# DirectX, polices) et un raccourci avec sa vraie icône dans le menu Démarrer. Désinstallation depuis Paramètres.
# Application développée par Matthieu Lamotte.
import os, sys, re, json, glob, time, shutil, subprocess, threading, tempfile, fnmatch
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, theme, systeme as S
from .ui import *

RACINE = os.path.join(GLib.get_user_data_dir(), "xiii", "windows")
APPS_DIR = os.path.join(GLib.get_user_data_dir(), "applications")
ICONES = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor", "256x256", "apps")
PROFILS = "/usr/share/xiii/windows-profils.json"
COMPOSANTS = [  # clé winetricks, nom, motifs dans l'exécutable
    ("vcrun2022", "Visual C++ 2015-2022", [b"msvcp140", b"vcruntime140", b"vcruntime140_1"]),
    ("vcrun2010", "Visual C++ 2010", [b"msvcr100.dll", b"msvcp100.dll"]),
    ("dotnet48", ".NET Framework 4.8", [b"mscoree.dll", b"_CorExeMain", b"mscorlib"]),
    ("d3dx9", "DirectX 9 (d3dx9)", [b"d3dx9_"]),
    ("d3dcompiler_47", "Compilateur DirectX", [b"d3dcompiler_47"]),
    ("corefonts", "Polices Windows (Arial, Times…)", []),
]

def slug(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:40] or "application"

def nom_propre(fichier):
    n = os.path.splitext(os.path.basename(fichier))[0]
    n = re.sub(r"(?i)[-_ .](setup|install(er)?|win(32|64|dows)?|x64|x86|amd64|portable|full|offline)\b", " ", n)
    n = re.sub(r"[-_]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n[:1].upper() + n[1:] if n else "Application"

def est_installeur(fichier):
    b = os.path.basename(fichier).lower()
    if b.endswith(".msi"): return True
    if re.search(r"setup|install|installer|_inst|-inst", b): return True
    try:
        with open(fichier, "rb") as f: d = f.read(4 * 1024 * 1024)
        return any(m in d for m in (b"Inno Setup", b"Nullsoft", b"NSIS", b"InstallShield", b"WiX", b"7-Zip SFX"))
    except OSError:
        return False

def composants_detectes(fichier):
    try:
        with open(fichier, "rb") as f: d = f.read(40 * 1024 * 1024).lower()
    except OSError:
        return set()
    return {k for k, _, motifs in COMPOSANTS if any(m.lower() in d for m in motifs)}

def profil(nom):
    try:
        regles = json.load(open(PROFILS))
    except Exception:
        return None
    for r in regles:
        if any(fnmatch.fnmatch(nom.lower(), m) for m in r["motifs"]):
            return r
    return None

def extraire_icone(exe, dest_png):
    """Plus grande icône du .exe (wrestool + icotool) → PNG."""
    tmp = tempfile.mkdtemp()
    try:
        subprocess.run(["wrestool", "-x", "-t", "14", "-o", tmp, exe], capture_output=True, timeout=20)
        for ico in glob.glob(tmp + "/*.ico"):
            subprocess.run(["icotool", "-x", "-o", tmp, ico], capture_output=True, timeout=20)
        pngs = glob.glob(tmp + "/*.png")
        if not pngs: return None
        def taille(p):
            m = re.search(r"_(\d+)x(\d+)x(\d+)\.png$", p)
            return (int(m.group(1)), int(m.group(3))) if m else (0, 0)
        meilleur = max(pngs, key=taille)
        os.makedirs(os.path.dirname(dest_png), exist_ok=True); shutil.copy(meilleur, dest_png)
        return dest_png
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, True)

def applis_windows():
    """Liste des logiciels Windows installés par OS XIII."""
    L = []
    for f in sorted(glob.glob(RACINE + "/*/xiii-app.json")):
        try:
            d = json.load(open(f)); d["prefixe"] = os.path.dirname(f); L.append(d)
        except Exception:
            pass
    return L

def desinstaller(app):
    for r in app.get("raccourcis", []):
        try: os.remove(r)
        except OSError: pass
    pref = app["prefixe"]
    for d in glob.glob(APPS_DIR + "/**/*.desktop", recursive=True):
        try:
            if pref in open(d, errors="ignore").read(): os.remove(d)
        except OSError:
            pass
    if app.get("icone") and app["icone"].startswith(ICONES):
        try: os.remove(app["icone"])
        except OSError: pass
    if pref.startswith(RACINE + "/"):
        subprocess.run(["wineserver", "-k"], env=dict(os.environ, WINEPREFIX=pref), capture_output=True, timeout=10)
        shutil.rmtree(pref, True)

# ================================================================================================ fenêtre
class AppWindows(Gtk.Application):
    def __init__(self, fichier):
        super().__init__(application_id="fr.xiii.Windows", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.fichier = fichier

    def do_activate(self):
        self.cfg = config.charger(); couleurs(self.cfg)
        css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(self.cfg) + """
.etape-ok { color: #6fbf73; } .etape-ko { color: #e98080; }
""")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 900)
        Gtk.Settings.get_default().set_property("gtk-icon-theme-name", theme.nom_icones(self.cfg))
        self.w = Gtk.ApplicationWindow(application=self, title="Applications Windows", default_width=720, default_height=600)
        self.w.add_css_class("parametres")
        self.pile = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT); self.w.set_child(self.pile)
        if not self.fichier:
            self.page_accueil()
        else:
            self.page_preparer(self.fichier)
        self.w.present()

    def cadre(self, nom):
        v = boite(True, 12, margin_top=24, margin_bottom=20, margin_start=30, margin_end=30)
        self.pile.add_named(defilant(v), nom); return v

    # ---------------------------------------------------------------- sans fichier : liste + choisir
    def page_accueil(self):
        v = self.cadre("accueil")
        v.append(label("Applications Windows", "page-titre"))
        v.append(label("Installez un logiciel Windows (.exe, .msi) : double-cliquez simplement dessus, ou choisissez-le ici.", "attenue", wrap=True))
        v.append(bouton("Choisir un fichier .exe ou .msi…", "folder-open", "pilule", taille=16, rappel=self.choisir))
        v.append(label("Installées", "groupe-titre"))
        L = applis_windows()
        if not L: v.append(label("Aucun logiciel Windows pour l'instant.", "attenue"))
        for a in L:
            r = boite(False, 12, "reglage")
            r.append(vignette(a["icone"], 32, 32, couvrir=False) if a.get("icone") and os.path.exists(a["icone"]) else ico("app-window", 28, "c"))
            t = boite(True, 2, hexpand=True); t.append(label(a["nom"], "reglage-titre")); t.append(label(time.strftime("Installé le %d/%m/%Y", time.localtime(a.get("cree", 0))), "reglage-sous")); r.append(t)
            r.append(bouton(None, "folder", "plat", tip="Ouvrir le disque C: de ce logiciel", rappel=lambda a=a: S.detacher(["xdg-open", os.path.join(a["prefixe"], "drive_c")])))
            r.append(bouton(None, "settings-2", "plat", tip="Réglages Windows (winecfg)", rappel=lambda a=a: subprocess.Popen(["winecfg"], env=dict(os.environ, WINEPREFIX=a["prefixe"]))))
            v.append(r)
        v.append(label("Pour désinstaller : Paramètres › Applications › Applications installées.", "attenue", "petit"))

    def choisir(self):
        d = Gtk.FileDialog(title="Choisir un logiciel Windows")
        ff = Gtk.FileFilter(); ff.set_name("Logiciels Windows (.exe, .msi)")
        for x in ("exe", "msi", "EXE", "MSI"): ff.add_suffix(x)
        st = Gio.ListStore.new(Gtk.FileFilter); st.append(ff); d.set_filters(st)
        def fini(dlg, res):
            try: f = dlg.open_finish(res)
            except Exception: return
            self.page_preparer(f.get_path())
        d.open(self.w, None, fini)

    # ---------------------------------------------------------------- préparation
    def page_preparer(self, fichier):
        self.fichier = fichier
        v = self.cadre("preparer")
        self.nom = nom_propre(fichier); self.installeur = est_installeur(fichier)
        self.png_tmp = os.path.join(tempfile.gettempdir(), "xiii-ico-%d.png" % os.getpid())
        ic = extraire_icone(fichier, self.png_tmp)
        h = boite(False, 18, "hero")
        h.append(vignette(ic, 64, 64, couvrir=False) if ic else ico("app-window", 56, "c"))
        t = boite(True, 4, hexpand=True, valign=Gtk.Align.CENTER)
        self.e_nom = Gtk.Entry(text=self.nom); self.e_nom.add_css_class("hero-grand"); t.append(self.e_nom)
        try: taille = S.humain(os.path.getsize(fichier))
        except OSError: taille = "?"
        t.append(label("%s · %s" % (os.path.basename(fichier), taille), "attenue", "petit", ellipsize=True))
        h.append(t); v.append(h)
        v.append(label("Ce fichier est…", "groupe-titre"))
        self.dd = Gtk.DropDown(model=Gtk.StringList.new(["Un programme d'installation — installer le logiciel", "Un logiciel portable — le lancer directement"]))
        self.dd.set_selected(0 if self.installeur else 1)
        r = boite(False, 12, "reglage"); r.append(ico("package", 20, "c")); r.append(label("Type", "reglage-titre", hexpand=True)); r.append(self.dd); v.append(r)
        pr = profil(self.nom)
        if pr and pr.get("note"):
            n = boite(False, 10, "info-bulle"); n.append(ico("info", 16, "c")); n.append(label(pr["note"], wrap=True, hexpand=True)); v.append(n)
        det = composants_detectes(fichier) | set((pr or {}).get("composants", []))
        v.append(label("Composants Windows", "groupe-titre"))
        v.append(label("Cochés automatiquement d'après le logiciel. Téléchargés depuis Microsoft lors de l'installation.", "attenue", "petit", wrap=True))
        self.cases = {}
        for k, n, _ in COMPOSANTS:
            c = Gtk.CheckButton(label=n, active=k in det); self.cases[k] = c
            r = boite(False, 12, "reglage"); r.append(c); r.append(Gtk.Box(hexpand=True))
            if k in det: r.append(label("conseillé", "accent", "petit"))
            v.append(r)
        b = boite(False, 10, margin_top=10, halign=Gtk.Align.END)
        b.append(bouton("Annuler", None, "fantome", rappel=self.w.close))
        self.go = bouton("Installer" if self.installeur else "Lancer", None, "pilule", rappel=self.lancer)
        self.dd.connect("notify::selected", lambda *_: self.go.set_label("Installer" if self.dd.get_selected() == 0 else "Ajouter et lancer"))
        b.append(self.go); v.append(b)
        self.pile.set_visible_child_name("preparer")

    # ---------------------------------------------------------------- installation
    def lancer(self):
        self.nom = self.e_nom.get_text().strip() or self.nom
        self.installeur = self.dd.get_selected() == 0
        comps = [k for k, c in self.cases.items() if c.get_active()]
        v = self.cadre("progres")
        v.append(label("Installation de %s" % self.nom, "page-titre", wrap=True))
        self.etapes = {}
        for k, t in (("env", "Préparation de l'environnement Windows"), ("comp", "Composants : " + (", ".join(n for kk, n, _ in COMPOSANTS if kk in comps) or "aucun")),
                     ("inst", "Installation du logiciel (sa fenêtre va s'ouvrir)" if self.installeur else "Copie du logiciel"), ("racc", "Raccourcis dans le menu Démarrer")):
            r = boite(False, 12, "reglage"); sp = Gtk.Spinner(); st = Gtk.Box(); st.append(ico("circle", 18, "d"))
            r.append(st); r.append(label(t, "reglage-titre", wrap=True, hexpand=True)); v.append(r); self.etapes[k] = st
        self.journal = Gtk.TextView(editable=False, monospace=True); self.journal.add_css_class("journal")
        ex = Gtk.Expander(label="Détails techniques"); sc = Gtk.ScrolledWindow(); sc.set_size_request(-1, 160); sc.set_child(self.journal); ex.set_child(sc); v.append(ex)
        self.fin_zone = boite(True, 10); v.append(self.fin_zone)
        self.pile.set_visible_child_name("progres")
        threading.Thread(target=self.travail, args=(comps,), daemon=True).start()

    def etat(self, k, e):
        def f():
            b = self.etapes[k]; vider(b)
            if e == "cours": s = Gtk.Spinner(spinning=True); b.append(s)
            elif e == "ok": b.append(ico("circle-check", 18, "#6fbf73"))
            elif e == "ko": b.append(ico("circle-x" if os.path.exists(theme.LUCIDE + "/circle-x.svg") else "x", 18, "#e98080"))
            return False
        GLib.idle_add(f)

    def log(self, t):
        def f():
            buf = self.journal.get_buffer(); buf.insert(buf.get_end_iter(), t.rstrip() + "\n"); return False
        GLib.idle_add(f)

    def run(self, cmd, env, timeout=3600):
        self.log("$ " + " ".join(cmd))
        if S.DEMO:
            time.sleep(0.8); return 0
        p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        for l in p.stdout:
            if l.strip() and not l.startswith(("fixme:", "err:ole", "warn:")): self.log(l)
        return p.wait(timeout)

    def travail(self, comps):
        pref = os.path.join(RACINE, slug(self.nom)); n = 2
        while os.path.exists(os.path.join(pref, "xiii-app.json")): pref = os.path.join(RACINE, slug(self.nom) + "-%d" % n); n += 1
        os.makedirs(pref, exist_ok=True)
        env = dict(os.environ, WINEPREFIX=pref, WINEDEBUG="-all", WINEARCH="win64")
        avant = set(glob.glob(APPS_DIR + "/**/*.desktop", recursive=True))
        # 1. environnement
        self.etat("env", "cours")
        rc = self.run(["wineboot", "-u"], dict(env, WINEDLLOVERRIDES="mscoree,mshtml="), 600)
        self.run(["wineserver", "-w"], env, 300)
        self.etat("env", "ok" if rc == 0 else "ko")
        # 2. composants
        self.etat("comp", "cours")
        ok = True
        if comps:
            ok = self.run(["winetricks", "-q", "--unattended"] + comps, env, 3600) == 0
        self.etat("comp", "ok" if ok else "ko")
        # 3. installation / copie
        self.etat("inst", "cours")
        raccourcis = []; icone = None
        if self.installeur:
            cmd = ["wine", "msiexec", "/i", self.fichier] if self.fichier.lower().endswith(".msi") else ["wine", self.fichier]
            rc = self.run(cmd, env, 7200); self.run(["wineserver", "-w"], env, 7200)
            cible = None
        else:
            dest = os.path.join(pref, "drive_c", "Program Files", self.nom); os.makedirs(dest, exist_ok=True)
            cible = os.path.join(dest, os.path.basename(self.fichier))
            try: shutil.copy(self.fichier, cible); rc = 0
            except Exception as e: self.log(str(e)); rc = 1
        self.etat("inst", "ok" if rc == 0 else "ko")
        # 4. raccourcis
        self.etat("racc", "cours")
        os.makedirs(APPS_DIR, exist_ok=True)
        if os.path.exists(self.png_tmp):
            icone = os.path.join(ICONES, "xiii-win-%s.png" % os.path.basename(pref)); os.makedirs(ICONES, exist_ok=True); shutil.copy(self.png_tmp, icone)
        nouveaux = [d for d in set(glob.glob(APPS_DIR + "/**/*.desktop", recursive=True)) - avant if pref in open(d, errors="ignore").read()]
        for d in nouveaux:
            txt = open(d, errors="ignore").read()
            if re.search(r"(?mi)^Name=.*(uninstall|désinstall|readme|lisez|website|site web)", txt):
                txt = re.sub(r"(?m)^\[Desktop Entry\]", "[Desktop Entry]\nNoDisplay=true", txt, 1)
            if "Categories=" not in txt: txt = txt.rstrip("\n") + "\nCategories=Wine;X-XIII-Windows;\n"
            open(d, "w").write(txt); raccourcis.append(d)
        if cible or (not nouveaux and self.installeur):
            exe = cible
            if not exe:   # installeur sans raccourci : chercher le .exe principal
                cands = [p for p in glob.glob(pref + "/drive_c/Program Files*/**/*.exe", recursive=True) if not re.search(r"(?i)unins|setup|update|crash|helper", p)]
                exe = max(cands, key=os.path.getsize) if cands else None
            if exe:
                dsk = os.path.join(APPS_DIR, "xiii-win-%s.desktop" % os.path.basename(pref))
                open(dsk, "w").write("[Desktop Entry]\nType=Application\nName=%s\nComment=Application Windows\nExec=env WINEPREFIX=\"%s\" WINEDEBUG=-all wine \"%s\"\n"
                                     "Path=%s\nIcon=%s\nCategories=Wine;X-XIII-Windows;\nStartupNotify=true\n" % (self.nom, pref, exe, os.path.dirname(exe), icone or "application-x-ms-dos-executable"))
                raccourcis.append(dsk)
        json.dump({"nom": self.nom, "source": self.fichier, "type": "installeur" if self.installeur else "portable", "cree": time.time(),
                   "composants": comps, "raccourcis": raccourcis, "icone": icone}, open(os.path.join(pref, "xiii-app.json"), "w"), ensure_ascii=False, indent=2)
        subprocess.run(["update-desktop-database", APPS_DIR], capture_output=True)
        self.etat("racc", "ok" if raccourcis else "ko")
        GLib.idle_add(lambda: (self.fini(raccourcis, rc == 0), False)[1])

    def fini(self, raccourcis, ok):
        z = self.fin_zone
        z.append(label("C'est prêt !" if ok and raccourcis else "Terminé, avec des avertissements", "hero-grand"))
        if raccourcis:
            z.append(label("%s est dans le menu Démarrer, catégorie « Applications Windows »." % self.nom, "attenue", wrap=True))
        else:
            z.append(label("Aucun raccourci n'a été trouvé. Ouvrez « Applications Windows » pour retrouver le logiciel, ou consultez les détails.", "attenue", wrap=True))
        r = boite(False, 10, halign=Gtk.Align.END)
        if raccourcis:
            dsk = raccourcis[-1]
            def ouvrir():
                a = Gio.DesktopAppInfo.new_from_filename(dsk)
                if a: a.launch([], None)
                self.w.close()
            def epingler():
                c = config.charger(); i = os.path.basename(dsk) if os.path.dirname(dsk) == APPS_DIR else None
                if i and i not in c["epingles"]: config.modifier(epingles=c["epingles"] + [i])
            r.append(bouton("Épingler à la barre des tâches", "pin", "fantome", taille=14, rappel=epingler))
            r.append(bouton("Ouvrir %s" % self.nom, None, "pilule", rappel=ouvrir))
        else:
            r.append(bouton("Fermer", None, "pilule", rappel=self.w.close))
        z.append(r)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    f = args[0] if args else None
    if f and f.startswith("file://"):
        f = Gio.File.new_for_uri(f).get_path()
    AppWindows(f).run(sys.argv[:1])
