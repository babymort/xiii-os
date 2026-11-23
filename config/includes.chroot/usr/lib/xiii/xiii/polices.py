# OS XIII — Polices XIII : toutes les polices de l'ordinateur avec aperçu, recherche, activation / désactivation,
# import d'un fichier (.ttf, .otf, glisser-déposer) et téléchargement depuis Google Fonts (libres, licence OFL).
# Les polices de la DA XIII (Space Grotesk, IBM Plex, Archivo, Orbitron…) sont préinstallées et signalées.
# Application développée par Matthieu Lamotte.
import os, sys, re, json, shutil, subprocess, threading, urllib.request, urllib.parse
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from . import systeme as S
from .ui import *
from .appli import preparer, Volet, page

PERSO = os.path.expanduser("~/.local/share/fonts")
ARRET = os.path.expanduser("~/.local/share/fonts-desactivees")
DA = ("space grotesk", "ibm plex", "archivo", "orbitron", "rajdhani", "share tech", "press start", "pixelify", "courier prime")
UA = {"User-Agent": "OS-XIII"}


def familles():
    """{famille: {"fichiers": [..], "styles": set, "perso": bool, "da": bool}}"""
    o = subprocess.run(["fc-list", "--format", "%{family[0]}|%{style[0]}|%{file}\n"], capture_output=True, text=True).stdout
    F = {}
    for l in o.splitlines():
        p = l.split("|")
        if len(p) < 3 or not p[0]: continue
        f = F.setdefault(p[0], {"fichiers": [], "styles": set(), "perso": False, "da": False})
        f["fichiers"].append(p[2]); f["styles"].add(p[1]); f["perso"] |= p[2].startswith(PERSO); f["da"] |= any(x in p[0].lower() for x in DA)
    for d in (ARRET,):
        for r, _, fs in os.walk(d):
            for x in fs:
                if x.lower().endswith((".ttf", ".otf")):
                    nom = re.sub(r"[-_](Regular|Bold|Italic|Light|Medium|SemiBold|Black|Thin|ExtraBold|ExtraLight|\[.*\]).*$", "", os.path.splitext(x)[0])
                    f = F.setdefault(nom + " (désactivée)", {"fichiers": [], "styles": set(), "perso": True, "da": False, "arret": True}); f["fichiers"].append(os.path.join(r, x))
    return F


def basculer(fichiers, activer):
    src, dst = (ARRET, PERSO) if activer else (PERSO, ARRET)
    for f in fichiers:
        if not f.startswith(src): continue
        cible = os.path.join(dst, os.path.relpath(f, src)); os.makedirs(os.path.dirname(cible), exist_ok=True); shutil.move(f, cible)
    subprocess.run(["fc-cache", "-f", PERSO], capture_output=True)


def importer(chemins):
    os.makedirs(os.path.join(PERSO, "importees"), exist_ok=True); n = 0
    for p in chemins:
        if p.lower().endswith((".ttf", ".otf", ".ttc", ".woff2")):
            shutil.copy2(p, os.path.join(PERSO, "importees", os.path.basename(p))); n += 1
    subprocess.run(["fc-cache", "-f", PERSO], capture_output=True); return n


def google(famille):
    """Télécharge une famille Google Fonts (dépôt officiel google/fonts, licences OFL / Apache / UFL)."""
    dossier = re.sub(r"[^a-z0-9]", "", famille.lower())
    for lic in ("ofl", "apache", "ufl"):
        try:
            with urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/google/fonts/contents/%s/%s" % (lic, dossier), headers=UA), timeout=20) as r: L = json.load(r)
            break
        except Exception:
            L = None
    if not L: raise RuntimeError("« %s » introuvable sur Google Fonts (vérifiez l'orthographe)" % famille)
    dest = os.path.join(PERSO, "google", dossier); os.makedirs(dest, exist_ok=True); n = 0
    for a in L:
        if a["name"].lower().endswith((".ttf", ".otf")) or a["name"].startswith(("OFL", "LICENSE")):
            urllib.request.urlretrieve(a["download_url"], os.path.join(dest, a["name"])); n += a["name"].lower().endswith((".ttf", ".otf"))
    subprocess.run(["fc-cache", "-f", PERSO], capture_output=True)
    if not n: raise RuntimeError("aucun fichier de police dans « %s »" % famille)
    return n


class Polices(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.polices")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".apercu-police { font-size: 26px; } .ligne-police { padding: 10px 14px; border-radius: 12px; } .ligne-police:hover { background: alpha(currentColor, .05); }")
        self.win = Gtk.ApplicationWindow(application=self, title="Polices XIII"); self.win.set_default_size(1100, 760)
        self.texte = "Portez ce vieux whisky au juge blond qui fume"
        self.volet = Volet("Polices", "Aperçu, activation, import")
        self.volet.ajouter("toutes", "type", "Toutes les polices", rappel=lambda: self.p_liste("toutes"))
        self.volet.ajouter("da", "sparkles", "Polices de la DA XIII", rappel=lambda: self.p_liste("da"))
        self.volet.ajouter("perso", "folder", "Mes polices", rappel=lambda: self.p_liste("perso"))
        self.volet.ajouter("google", "download", "Google Fonts", rappel=self.p_google)
        self.win.set_child(self.volet.racine); self.volet.aller("toutes"); self.win.present()

    def remplacer(self, cle, w):
        v = self.volet.pile.get_child_by_name(cle)
        if v: self.volet.pile.remove(v)
        self.volet.pile.add_named(w, cle); self.volet.pile.set_visible_child_name(cle)

    def p_liste(self, filtre):
        titres = {"toutes": ("Toutes les polices", "Glissez un fichier .ttf ou .otf dans cette fenêtre pour l'installer"),
                  "da": ("Polices de la DA XIII", "Celles de la Suite XIII et des thèmes d'OS XIII, préinstallées"), "perso": ("Mes polices", "Importées ou téléchargées — elles peuvent être désactivées")}
        sc, v = page(titres[filtre][0], titres[filtre][1], "type")
        h = boite(False, 8); q = Gtk.SearchEntry(placeholder_text="Rechercher une police", hexpand=True); h.append(q)
        t = Gtk.Entry(text=self.texte, hexpand=True, placeholder_text="Texte d'aperçu"); h.append(t)
        taille = Gtk.SpinButton.new_with_range(10, 96, 2); taille.set_value(26); h.append(taille)
        h.append(bouton("Importer…", "plus", "pilule", rappel=self.choisir)); v.append(h)
        n_l = label("", "petit", "attenue"); v.append(n_l)
        lst = boite(True, 2); v.append(lst)
        dt = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        dt.connect("drop", lambda _t, val, x, y: (self.fin_import(importer([f.get_path() for f in val.get_files() if f.get_path()])), True)[1]); sc.add_controller(dt)
        etat = {"F": {}}
        def rendu(*_):
            vider(lst); self.texte = t.get_text() or self.texte; qq = q.get_text().lower().strip(); k = 0
            for nom in sorted(etat["F"], key=str.lower):
                f = etat["F"][nom]
                if filtre == "da" and not f["da"]: continue
                if filtre == "perso" and not f["perso"]: continue
                if qq and qq not in nom.lower(): continue
                k += 1
                if k > 150: continue
                r = boite(True, 4, "ligne-police")
                hh = boite(False, 8); hh.append(label(nom, "gras", hexpand=True))
                tags = ("DA XIII · " if f["da"] else "") + ("%d style%s" % (len(f["styles"]), "s" if len(f["styles"]) > 1 else "") if f["styles"] else "")
                hh.append(label(tags, "petit", "attenue"))
                if f["perso"]:
                    arret = f.get("arret", False)
                    hh.append(bouton("Activer" if arret else "Désactiver", None, "fantome", taille=12, rappel=lambda f=f, a=arret: (basculer(f["fichiers"], a), charger())))
                r.append(hh)
                ap = Gtk.Label(label=self.texte, xalign=0, ellipsize=Pango.EllipsizeMode.END)
                at = Pango.AttrList(); at.insert(Pango.attr_family_new(nom.replace(" (désactivée)", ""))); at.insert(Pango.attr_size_new(int(taille.get_value() * Pango.SCALE))); ap.set_attributes(at)
                r.append(ap); lst.append(r)
            n_l.set_text("%d police%s%s" % (k, "s" if k > 1 else "", " (150 affichées : affinez la recherche)" if k > 150 else ""))
        def charger():
            S.en_fond(familles, lambda F: (etat.update(F=F if isinstance(F, dict) else {}), rendu()))
        q.connect("search-changed", rendu); t.connect("activate", rendu)
        taille.connect("value-changed", rendu)
        charger(); self.remplacer(filtre, sc)

    def choisir(self):
        d = Gtk.FileDialog(title="Polices à installer (.ttf, .otf)")
        def fin(dd, res):
            try: L = dd.open_multiple_finish(res)
            except GLib.Error: return
            self.fin_import(importer([L.get_item(i).get_path() for i in range(L.get_n_items())]))
        d.open_multiple(self.win, None, fin)

    def fin_import(self, n):
        d = Gtk.AlertDialog(message="%d police%s installée%s" % (n, "s" if n > 1 else "", "s" if n > 1 else "") if n else "Aucun fichier de police reconnu (.ttf, .otf)")
        d.show(self.win); self.p_liste("perso")

    def p_google(self):
        sc, v = page("Google Fonts", "Plus de 1 500 polices libres, utilisables pour vos projets commerciaux", "download")
        h = boite(False, 8); e = Gtk.Entry(placeholder_text="Nom exact de la famille (ex. Montserrat, Bebas Neue, Inter, Playfair Display)", hexpand=True); h.append(e)
        etat = label("", "attenue", wrap=True)
        def go(*_):
            n = e.get_text().strip()
            if not n: return
            etat.set_text("Téléchargement de « %s »…" % n)
            S.en_fond(google, lambda r: etat.set_text(("Erreur : %s" % r) if isinstance(r, Exception) else "« %s » installée ✓ (%d fichier%s) — disponible dans toutes les applications" % (n, r, "s" if r > 1 else "")), n)
        e.connect("activate", go); h.append(bouton("Installer", "download", "pilule", rappel=go)); v.append(h); v.append(etat)
        v.append(label("Parcourir le catalogue", "section"))
        v.append(bouton("Ouvrir fonts.google.com", "external-link", "fantome", rappel=lambda: S.detacher(["xdg-open", "https://fonts.google.com/"])))
        v.append(label("Repérez une police sur le site, puis tapez son nom ici : elle est installée pour vous, sans manipulation.", "petit", "attenue", wrap=True))
        self.remplacer("google", sc)


def main():
    sys.exit(Polices().run(sys.argv[:1]))
