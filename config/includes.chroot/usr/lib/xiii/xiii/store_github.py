# OS XIII — Store GitHub : chercher des logiciels et extensions sur GitHub comme dans un magasin, ou coller le nom
# d'un dépôt (« auteur/projet » ou son adresse) : OS XIII prend la dernière version publiée et l'installe tout seul.
# Formats : .deb (paquet), .AppImage, .flatpak / .flatpakref, archive .tar.gz / .zip avec un programme.
# Les logiciels installés ici sont suivis : mise à jour en un clic, désinstallation.
# Application développée par Matthieu Lamotte.
import os, sys, json, re, shutil, subprocess, threading, tarfile, zipfile, urllib.request, urllib.parse, time, platform, stat
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S
from .ui import *
from .appli import preparer, Volet, page

API = "https://api.github.com"
SUIVI = os.path.expanduser("~/.local/share/xiii/store-github.json")
APPS = os.path.expanduser("~/Applications"); OPT = os.path.expanduser("~/.local/opt")
ARCH = "arm64|aarch64" if platform.machine() in ("aarch64", "arm64") else "amd64|x86_64|x64|linux64|linux-64"
SELECTIONS = [  # idées de départ
    ("Production et régie", ["obsproject/obs-studio", "Palakis/obs-websocket", "mltframework/shotcut", "olive-editor/olive"]),
    ("Utilitaires", ["localsend/localsend", "schollz/croc", "rclone/rclone", "ventoy/Ventoy", "balena-io/etcher"]),
    ("Jeux et émulation", ["zortos293/Lichii", "Ryubing/Ryujinx", "PCSX2/pcsx2", "hrydgard/ppsspp", "flyinghead/flycast"]),
]

def requete(chemin):
    req = urllib.request.Request(API + chemin, headers={"User-Agent": "OS-XIII", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)

def suivi():
    try: return json.load(open(SUIVI))
    except Exception: return {}

def sauver_suivi(d):
    os.makedirs(os.path.dirname(SUIVI), exist_ok=True); json.dump(d, open(SUIVI, "w"), ensure_ascii=False, indent=1)

def depot_de(texte):
    t = texte.strip().rstrip("/")
    m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", t) or re.match(r"^([\w.-]+)/([\w.-]+)$", t)
    return ("%s/%s" % (m.group(1), m.group(2).removesuffix(".git"))) if m else None

def meilleur_fichier(assets):
    """Choisit le fichier à installer dans une version : .deb, puis AppImage, puis flatpak, puis archive Linux."""
    n = lambda a: a["name"].lower()
    linux = lambda a: not re.search(r"windows|win32|win64|\.exe$|\.msi$|darwin|macos|\.dmg$|osx|android|\.apk$|sha256|\.sig$|\.asc$|checksum", n(a))
    bonne_arch = lambda a: re.search(ARCH, n(a)) or not re.search(r"arm|aarch|i386|i686|x86_64|amd64|x64|riscv|ppc", n(a))
    L = [a for a in assets if linux(a)]
    for ext in (".deb", ".appimage", ".flatpakref", ".flatpak"):
        c = [a for a in L if n(a).endswith(ext) and bonne_arch(a)]
        if c: return c[0], ext.lstrip(".")
    c = [a for a in L if n(a).endswith((".tar.gz", ".tgz", ".tar.xz", ".zip", ".tar.bz2")) and ("linux" in n(a)) and bonne_arch(a)]
    if c: return c[0], "archive"
    return None, None

def lanceur(nom, exe, icone="application-x-executable", depot=""):
    d = os.path.expanduser("~/.local/share/applications"); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, "github-%s.desktop" % re.sub(r"[^a-z0-9]+", "-", nom.lower()))
    open(f, "w").write("[Desktop Entry]\nType=Application\nName=%s\nComment=Installé depuis GitHub (%s) par le Store GitHub XIII\nExec=\"%s\" %%U\nIcon=%s\nCategories=Utility;\nTerminal=false\n" % (nom, depot, exe, icone))
    return f

def installer(depot, progres):
    """Installe la dernière version publiée de « auteur/projet ». Renvoie un dict de suivi."""
    def p2(f, t):
        S.progres("xiii-store-github.desktop", f if f < 1 else None); progres(f, t)
    try:
        return _installer(depot, p2)
    finally:
        S.progres("xiii-store-github.desktop", None)

def _installer(depot, progres):
    progres(.05, "Lecture du dépôt %s…" % depot)
    info = requete("/repos/" + depot)
    try: rel = requete("/repos/%s/releases/latest" % depot)
    except Exception:
        L = requete("/repos/%s/releases" % depot); rel = L[0] if L else None
    if not rel: raise RuntimeError("ce dépôt ne publie aucune version téléchargeable (il faudrait compiler le code source)")
    a, typ = meilleur_fichier(rel.get("assets", []))
    if not a: raise RuntimeError("aucune version Linux dans « %s » (%s)" % (rel.get("tag_name"), ", ".join(x["name"] for x in rel.get("assets", [])[:6]) or "aucun fichier"))
    nom = info.get("name") or depot.split("/")[1]
    # dossier temporaire propre à ce téléchargement (un fichier du même nom laissé dans /tmp par un autre compte
    # ou par l'administrateur ne bloque plus : « Permission non accordée ») ; lisible par apt (utilisateur _apt)
    import tempfile; d_ = tempfile.mkdtemp(prefix="xiii-store-"); os.chmod(d_, 0o755)
    tmp = os.path.join(d_, a["name"])
    req = urllib.request.Request(a["browser_download_url"], headers={"User-Agent": "OS-XIII"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or a.get("size") or 1); lu = 0
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b); lu += len(b); progres(.1 + .75 * lu / total, "Téléchargement de %s (%s)…" % (a["name"], S.humain(total)))
    progres(.9, "Installation…")
    e = {"depot": depot, "nom": nom, "version": rel.get("tag_name", ""), "type": typ, "fichier": a["name"], "date": time.strftime("%Y-%m-%d")}
    if typ == "deb":
        r = subprocess.run(["pkexec", "sh", "-c", "DEBIAN_FRONTEND=noninteractive apt-get install -y '%s'" % tmp], capture_output=True, text=True)
        if r.returncode: raise RuntimeError("installation du paquet refusée ou impossible")
        e["paquet"] = subprocess.run(["dpkg-deb", "-f", tmp, "Package"], capture_output=True, text=True).stdout.strip()
    elif typ == "appimage":
        os.makedirs(APPS, exist_ok=True); dest = os.path.join(APPS, a["name"]); shutil.move(tmp, dest)
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        e["chemin"] = dest; e["lanceur"] = lanceur(nom, dest, depot=depot)
    elif typ in ("flatpakref", "flatpak"):
        liste = lambda: set(subprocess.run(["flatpak", "list", "--user", "--app", "--columns=application"], capture_output=True, text=True).stdout.split())
        avant = liste()
        r = subprocess.run(["flatpak", "install", "--user", "-y", "--noninteractive", tmp], capture_output=True, text=True)
        if r.returncode: raise RuntimeError(r.stderr.strip()[-200:])
        e["flatpak"] = True
        nv = sorted(liste() - avant)
        if nv: e["flatpak_id"] = nv[0]
    else:
        dest = os.path.join(OPT, depot.replace("/", "_")); shutil.rmtree(dest, ignore_errors=True); os.makedirs(dest)
        if a["name"].lower().endswith(".zip"): zipfile.ZipFile(tmp).extractall(dest)
        else: tarfile.open(tmp).extractall(dest, filter="data") if hasattr(tarfile, "data_filter") else tarfile.open(tmp).extractall(dest)
        cands = []
        for r_, ds, fs in os.walk(dest):
            for f in fs:
                p = os.path.join(r_, f)
                try:
                    with open(p, "rb") as h:
                        if h.read(4) == b"\x7fELF" and not f.endswith(".so") and ".so." not in f: cands.append(p)
                except OSError: pass
        base = depot.split("/")[1].lower()
        cands.sort(key=lambda p: (base not in os.path.basename(p).lower(), len(p)))
        if not cands: raise RuntimeError("archive installée dans %s, mais aucun programme trouvé à lancer" % dest)
        for p in cands: os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
        e["chemin"] = dest; e["lanceur"] = lanceur(nom, cands[0], depot=depot)
    try: os.chmod(tmp, 0o644)
    except OSError: pass
    try: os.unlink(tmp)
    except OSError: pass
    d = suivi(); d[depot] = e; sauver_suivi(d)
    progres(1, "%s %s installé ✓" % (nom, e["version"]))
    return e

def desinstaller(e):
    if e.get("paquet"): subprocess.run(["pkexec", "apt-get", "remove", "-y", e["paquet"]])
    if e.get("flatpak"):
        pass
    for k in ("lanceur",):
        if e.get(k) and os.path.exists(e[k]): os.unlink(e[k])
    if e.get("chemin"):
        if os.path.isdir(e["chemin"]): shutil.rmtree(e["chemin"], ignore_errors=True)
        elif os.path.exists(e["chemin"]): os.unlink(e["chemin"])
    d = suivi(); d.pop(e["depot"], None); sauver_suivi(d)


class Store(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.storegithub", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

    def do_command_line(self, cl):
        a = cl.get_arguments()[1:]
        self.activer()
        if a and depot_de(a[0]): self.fiche(depot_de(a[0]))
        return 0

    def activer(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".appli-carte { padding: 14px; } .appli-carte:hover { background: alpha(@accent_bg_color, .1); } .etoiles { color: @accent_bg_color; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Store GitHub"); self.win.set_default_size(1100, 740)
        self.volet = Volet("Store GitHub", "Des milliers de logiciels libres, installés en un clic")
        self.volet.ajouter("accueil", "store", "À la une", rappel=self.p_accueil)
        self.volet.ajouter("chercher", "search", "Rechercher", rappel=self.p_chercher)
        self.volet.ajouter("depot", "link", "Installer un dépôt", rappel=self.p_depot)
        self.volet.ajouter("installes", "package-check", "Installés", rappel=self.p_installes)
        self.win.set_child(self.volet.racine); self.volet.aller("accueil"); self.win.present()

    def remplacer(self, cle, w):
        v = self.volet.pile.get_child_by_name(cle)
        if v: self.volet.pile.remove(v)
        self.volet.pile.add_named(w, cle); self.volet.pile.set_visible_child_name(cle)

    def carte(self, r):
        b = Gtk.Button(); b.add_css_class("carte"); b.add_css_class("appli-carte")
        v = boite(True, 4); h = boite(False, 8); h.append(ico("package", 18, "c")); h.append(label(r.get("name") or r["full_name"], "gras", ellipsize=True, hexpand=True))
        h.append(label("★ %s" % format(r.get("stargazers_count", 0), ",").replace(",", " "), "petit", "etoiles")); v.append(h)
        v.append(label(r["full_name"], "petit", "attenue")); v.append(label((r.get("description") or "")[:140], "petit", wrap=True, xalign=0))
        if r.get("language"): v.append(label(r["language"], "petit", "attenue"))
        b.set_child(v); b.connect("clicked", lambda *_: self.fiche(r["full_name"])); return b

    def grille(self, L):
        g = Gtk.FlowBox(max_children_per_line=3, min_children_per_line=1, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, homogeneous=True)
        for r in L: g.append(self.carte(r))
        return g

    def p_accueil(self):
        sc, v = page("À la une", "Une sélection pour la production, le quotidien et les jeux — tout GitHub est dans « Rechercher »", "store")
        self.remplacer("accueil", sc)
        for titre, L in SELECTIONS:
            v.append(label(titre, "section")); zone = boite(True, 0); v.append(zone)
            def charger(L=L, zone=zone):
                R = []
                for d in L:
                    try: R.append(requete("/repos/" + d))
                    except Exception: R.append({"full_name": d, "name": d.split("/")[1]})
                return R
            S.en_fond(charger, lambda R, zone=zone: zone.append(self.grille(R)) if isinstance(R, list) else None)

    def p_chercher(self):
        sc, v = page("Rechercher", "Logiciels, extensions, thèmes, outils… triés par popularité", "search")
        e = Gtk.SearchEntry(placeholder_text="ex. stream deck, montage vidéo, NDI, émulateur, timecode…"); v.append(e)
        f = Gtk.CheckButton(label="Seulement ceux qui publient une version Linux prête à installer", active=True); v.append(f)
        zone = boite(True, 0); v.append(zone)
        def go(*_):
            q = e.get_text().strip()
            if not q: return
            vider(zone); zone.append(label("Recherche…", "attenue"))
            qq = q + (" linux in:name,description,topics" if f.get_active() else "")
            S.en_fond(lambda: requete("/search/repositories?" + urllib.parse.urlencode({"q": qq, "sort": "stars", "per_page": 30})).get("items", []),
                      lambda R: (vider(zone), zone.append(self.grille(R) if isinstance(R, list) and R else label("Aucun résultat (ou limite de recherches GitHub atteinte : réessayez dans une minute).", "attenue", wrap=True))))
        e.connect("activate", go); self.remplacer("chercher", sc); e.grab_focus()

    def p_depot(self):
        sc, v = page("Installer un dépôt", "Collez le nom ou l'adresse d'un dépôt GitHub : la dernière version Linux est téléchargée et installée", "link")
        e = Gtk.Entry(placeholder_text="auteur/projet  ou  https://github.com/auteur/projet"); v.append(e)
        v.append(bouton("Voir et installer", "download", "pilule", rappel=lambda: self.fiche(depot_de(e.get_text())) if depot_de(e.get_text()) else None))
        v.append(label("Formats pris en charge : paquet .deb, AppImage, Flatpak, archive Linux contenant un programme. "
                       "Un dépôt qui ne publie que du code source ne peut pas être installé automatiquement.", "petit", "attenue", wrap=True))
        e.connect("activate", lambda *_: self.fiche(depot_de(e.get_text())) if depot_de(e.get_text()) else None)
        self.remplacer("depot", sc)

    def fiche(self, depot):
        sc, v = page(depot.split("/")[1], depot, "package")
        zone = boite(True, 10); v.append(zone); zone.append(label("Lecture du dépôt…", "attenue"))
        self.remplacer("fiche", sc)
        for b in self.volet.boutons.values(): b.remove_css_class("actif")
        def lire():
            r = requete("/repos/" + depot)
            try: rel = requete("/repos/%s/releases/latest" % depot)
            except Exception: rel = None
            return r, rel
        def fin(x):
            vider(zone)
            if isinstance(x, Exception): zone.append(label("Dépôt introuvable : %s" % x, "attenue", wrap=True)); return
            r, rel = x
            zone.append(label(r.get("description") or "", wrap=True))
            zone.append(label("★ %d · %s · licence %s · mis à jour le %s" % (r.get("stargazers_count", 0), r.get("language") or "—", ((r.get("license") or {}).get("spdx_id") or "?"), (r.get("pushed_at") or "")[:10]), "petit", "attenue"))
            a, typ = meilleur_fichier((rel or {}).get("assets", []))
            deja = suivi().get(depot)
            if a:
                zone.append(label("Dernière version : %s · %s (%s)" % (rel.get("tag_name"), a["name"], S.humain(a.get("size", 0))), "gras"))
                pb = Gtk.ProgressBar(show_text=True); pb.set_visible(False); zone.append(pb)
                def inst():
                    pb.set_visible(True)
                    S.en_fond(lambda: installer(depot, lambda f, t: GLib.idle_add(lambda: (pb.set_fraction(f), pb.set_text(t), False)[2])),
                              lambda e_: pb.set_text(("Erreur : %s" % e_) if isinstance(e_, Exception) else "Installé ✓ — dans le menu Démarrer"))
                zone.append(bouton("Mettre à jour" if deja and deja.get("version") != rel.get("tag_name") else ("Réinstaller" if deja else "Installer"), "download", "pilule", rappel=inst))
            else:
                zone.append(label("Pas de version Linux prête à installer dans ce dépôt" + (" (dernière version : %s)." % rel.get("tag_name") if rel else "."), "attenue", wrap=True))
            zone.append(bouton("Voir sur GitHub", "external-link", "fantome", rappel=lambda: S.detacher(["xdg-open", r["html_url"]])))
        S.en_fond(lire, fin)

    def p_installes(self):
        sc, v = page("Installés", "Logiciels installés depuis le Store GitHub", "package-check")
        d = suivi()
        if not d: v.append(label("Rien pour l'instant.", "attenue"))
        for depot, e in d.items():
            r = boite(False, 10, "reglage"); r.append(ico("package", 20, "c"))
            col = boite(True, 0, hexpand=True); col.append(label(e["nom"], "gras")); col.append(label("%s · %s · %s · installé le %s" % (depot, e["version"], e["type"], e["date"]), "petit", "attenue")); r.append(col)
            etat = label("", "petit", "accent"); r.append(etat)
            S.en_fond(lambda d_=depot: requete("/repos/%s/releases/latest" % d_).get("tag_name"), lambda t, e=e, l=etat: l.set_text("Nouvelle version : " + t) if isinstance(t, str) and t != e["version"] else None)
            r.append(bouton("Mettre à jour", None, "fantome", rappel=lambda d_=depot: self.fiche(d_)))
            r.append(bouton(None, "trash-2", "plat", tip="Désinstaller", rappel=lambda e=e: S.en_fond(lambda: desinstaller(e), lambda _r: self.p_installes())))
            v.append(r)
        self.remplacer("installes", sc)

def main():
    sys.exit(Store().run(sys.argv))
