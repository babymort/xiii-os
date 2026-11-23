# OS XIII — Coffre XIII : gestionnaire de mots de passe compatible KeePass (.kdbx, chiffré AES / ChaCha20 + Argon2).
# Le même fichier s'ouvre avec KeePassXC (PC, Mac), KeePassDX (Android), Strongbox (iPhone) : placé dans un dossier
# synchronisé (OneDrive, NAS…), il suit sur tous vos appareils. Import d'un export Bitwarden (.json) ou d'un CSV.
# Copie protégée : le presse-papiers est vidé après 30 s et le mot de passe n'entre pas dans l'historique.
# Verrouillage automatique après 5 minutes sans activité. Générateur de mots de passe.
# Application développée par Matthieu Lamotte.
import os, sys, json, csv, secrets, string, math, time, subprocess
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S
from .ui import *
from .appli import preparer

DEFAUT = os.path.expanduser("~/Documents/Coffre XIII.kdbx")
MOTS = ("arbre", "bateau", "camera", "drone", "etoile", "falaise", "girafe", "horloge", "image", "jardin", "kiwi", "lumiere", "montage", "nuage", "orage",
        "plateau", "quartz", "regie", "studio", "tournage", "volcan", "wagon", "xylophone", "yaourt", "zebre", "micro", "trepied", "objectif", "rushs", "pellicule")


def generer(longueur=20, symboles=True, phrase=False):
    if phrase:
        return "-".join(secrets.choice(MOTS).capitalize() if i == 0 else secrets.choice(MOTS) for i in range(5)) + str(secrets.randbelow(90) + 10)
    car = string.ascii_letters + string.digits + ("!@#$%&*-_=+?" if symboles else "")
    while True:
        m = "".join(secrets.choice(car) for _ in range(longueur))
        if any(c.islower() for c in m) and any(c.isupper() for c in m) and any(c.isdigit() for c in m): return m


def force(m):
    """(0-4, texte) : estimation simple de l'entropie."""
    if not m: return 0, ""
    n = (26 if any(c.islower() for c in m) else 0) + (26 if any(c.isupper() for c in m) else 0) + (10 if any(c.isdigit() for c in m) else 0) + (20 if any(not c.isalnum() for c in m) else 0)
    bits = len(m) * math.log2(max(n, 2))
    if "-" in m and len(m) > 25: bits = max(bits, 60)
    k = 0 if bits < 35 else 1 if bits < 50 else 2 if bits < 65 else 3 if bits < 85 else 4
    return k, ["Très faible", "Faible", "Correct", "Fort", "Très fort"][k]


def importer_bitwarden(kp, chemin):
    d = json.load(open(chemin, encoding="utf-8"))
    if d.get("encrypted"): raise RuntimeError("export chiffré : exportez au format .json non chiffré depuis Bitwarden")
    dossiers = {f["id"]: f["name"] for f in d.get("folders", [])}; n = 0
    for it in d.get("items", []):
        lg = it.get("login") or {}
        nom_g = dossiers.get(it.get("folderId"))
        g = kp.root_group
        if nom_g:
            g = kp.find_groups(name=nom_g, first=True) or kp.add_group(kp.root_group, nom_g)
        url = ((lg.get("uris") or [{}])[0] or {}).get("uri") or ""
        kp.add_entry(g, it.get("name") or "Sans nom", lg.get("username") or "", lg.get("password") or "", url=url, notes=it.get("notes") or "", force_creation=True); n += 1
    kp.save(); return n


def importer_csv(kp, chemin):
    """CSV de Chrome, Firefox, Bitwarden, 1Password, KeePassXC (colonnes name/title, url, username, password, notes)."""
    n = 0
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            r = {k.lower().strip(): (v or "") for k, v in r.items() if k}
            titre = r.get("name") or r.get("title") or r.get("titre") or r.get("url") or "Sans nom"
            mdp = r.get("password") or r.get("login_password") or r.get("mot de passe")
            if not mdp: continue
            kp.add_entry(kp.root_group, titre, r.get("username") or r.get("login_username") or r.get("identifiant") or "", mdp,
                         url=r.get("url") or r.get("login_uri") or "", notes=r.get("notes") or r.get("note") or "", force_creation=True); n += 1
    kp.save(); return n


class Coffre(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.coffre"); self.kp = None; self.derniere = time.time()

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".entree-coffre { padding: 8px 10px; border-radius: 10px; } .force-0,.force-1 { color: #ef6b6b; } .force-2 { color: #f0b84a; } .force-3,.force-4 { color: #5fd39a; }"
                 " .mdp { font-family: 'IBM Plex Mono', monospace; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Coffre XIII", default_width=1000, default_height=680)
        self.pile = Gtk.Stack(); self.win.set_child(self.pile)
        for ev in (Gtk.EventControllerKey(), Gtk.EventControllerMotion()):
            (ev.connect("key-pressed", lambda *_: (self.activite(), False)[1]) if isinstance(ev, Gtk.EventControllerKey) else ev.connect("motion", lambda *_: self.activite()))
            self.win.add_controller(ev)
        GLib.timeout_add_seconds(20, self.verrou_auto)
        self.ecran_ouverture(); self.win.present()

    def activite(self): self.derniere = time.time()

    def verrou_auto(self):
        if self.kp and time.time() - self.derniere > 300: self.verrouiller()
        return True

    def verrouiller(self):
        self.kp = None; self.ecran_ouverture()

    def fichier(self): return config.charger().get("coffre_fichier") or DEFAUT

    # ------------------------------------------------------------ ouverture / création
    def ecran_ouverture(self):
        v = boite(True, 14, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER); v.set_size_request(420, -1)
        v.append(ico("key-round", 56, "c")); v.append(label("Coffre XIII", "page-titre", xalign=0.5))
        f = self.fichier(); existe = os.path.exists(f)
        v.append(label(f if existe else "Nouveau coffre : %s" % f, "petit", "attenue", wrap=True, xalign=0.5))
        mdp = Gtk.PasswordEntry(show_peek_icon=True); mdp.set_property("placeholder-text", "Mot de passe principal"); v.append(mdp)
        mdp2 = None
        if not existe:
            mdp2 = Gtk.PasswordEntry(show_peek_icon=True); mdp2.set_property("placeholder-text", "Confirmer le mot de passe principal"); v.append(mdp2)
            v.append(label("Choisissez une phrase longue et facile à retenir : elle protège tous les autres. Si vous l'oubliez, personne ne pourra ouvrir le coffre.", "petit", "attenue", wrap=True))
        err = label("", "petit", "attenue", wrap=True, xalign=0.5)
        def ouvrir(*_):
            m = mdp.get_text()
            if not m: return
            try:
                from pykeepass import PyKeePass, create_database
            except ImportError:
                err.set_text("Module KeePass absent (paquet python3-pykeepass)."); return
            if not existe:
                if m != mdp2.get_text(): err.set_text("Les deux mots de passe sont différents."); return
                if force(m)[0] < 2: err.set_text("Mot de passe principal trop faible : allongez-le (une phrase de 4 ou 5 mots convient)."); return
                os.makedirs(os.path.dirname(f), exist_ok=True)
                self.kp = create_database(f, password=m)
            else:
                err.set_text("Ouverture…")
                try: self.kp = PyKeePass(f, password=m)
                except Exception: err.set_text("Mot de passe incorrect."); mdp.set_text(""); return
            self.activite(); self.ecran_coffre()
        mdp.connect("activate", ouvrir)
        if mdp2: mdp2.connect("activate", ouvrir)
        v.append(bouton("Créer le coffre" if not existe else "Déverrouiller", "unlock", "pilule", rappel=ouvrir)); v.append(err)
        b = boite(False, 8, halign=Gtk.Align.CENTER)
        b.append(bouton("Ouvrir un autre fichier .kdbx…", None, "plat", rappel=self.choisir_fichier)); v.append(b)
        self.remplacer("ouverture", v); GLib.idle_add(mdp.grab_focus)

    def choisir_fichier(self):
        d = Gtk.FileDialog(title="Coffre KeePass (.kdbx)")
        def fin(dd, r):
            try: g = dd.open_finish(r)
            except GLib.Error: return
            config.modifier(coffre_fichier=g.get_path()); self.ecran_ouverture()
        d.open(self.win, None, fin)

    def remplacer(self, nom, w):
        old = self.pile.get_child_by_name(nom)
        if old: self.pile.remove(old)
        self.pile.add_named(w, nom); self.pile.set_visible_child_name(nom)

    # ------------------------------------------------------------ coffre ouvert
    def ecran_coffre(self):
        r = boite(False, 0)
        g = boite(True, 8, margin_start=12, margin_end=8, margin_top=12, margin_bottom=12); g.set_size_request(340, -1); r.append(g)
        h = boite(False, 6); h.append(label("Coffre", "titre-astoria", hexpand=True))
        h.append(bouton(None, "lock", "plat", tip="Verrouiller", rappel=self.verrouiller)); g.append(h)
        self.q = Gtk.SearchEntry(placeholder_text="Rechercher (site, identifiant…)"); self.q.connect("search-changed", lambda *_: self.lister()); g.append(self.q)
        b = boite(False, 6); b.append(bouton("Ajouter", "plus", "pilule", rappel=lambda: self.editer(None)))
        b.append(bouton("Importer…", "download", "fantome", rappel=self.importer)); g.append(b)
        sc = Gtk.ScrolledWindow(vexpand=True); self.liste = Gtk.ListBox(); self.liste.add_css_class("navigation-sidebar"); sc.set_child(self.liste); g.append(sc)
        self.liste.connect("row-activated", lambda l, row: self.detail(row._e))
        self.l_n = label("", "petit", "attenue"); g.append(self.l_n)
        r.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.d = boite(True, 10, hexpand=True, margin_start=20, margin_end=20, margin_top=16, margin_bottom=16); r.append(self.d)
        self.remplacer("coffre", r); self.lister(); self.accueil_detail()

    def lister(self):
        c = self.liste.get_first_child()
        while c: n = c.get_next_sibling(); self.liste.remove(c); c = n
        q = self.q.get_text().lower().strip(); E = sorted(self.kp.entries, key=lambda e: (e.title or "").lower()); n = 0
        for e in E:
            if e.group and e.group.name in ("Recycle Bin", "Corbeille"): continue
            if q and q not in " ".join(x or "" for x in (e.title, e.username, e.url, e.notes)).lower(): continue
            row = Gtk.ListBoxRow(); row._e = e; bx = boite(False, 10, "entree-coffre")
            bx.append(ico("globe" if e.url else "key-round", 18, "c")); t = boite(True, 0, hexpand=True)
            t.append(label(e.title or "Sans nom", "gras", ellipsize=True)); t.append(label(e.username or "", "petit", "attenue", ellipsize=True)); bx.append(t)
            row.set_child(bx); self.liste.append(row); n += 1
        self.l_n.set_text("%d mot%s de passe" % (n, "s" if n > 1 else ""))

    def accueil_detail(self):
        vider(self.d)
        faibles = [e for e in self.kp.entries if e.password and force(e.password)[0] < 2]
        vus = {}
        for e in self.kp.entries:
            if e.password: vus.setdefault(e.password, []).append(e)
        doublons = sum(1 for L in vus.values() if len(L) > 1)
        self.d.append(label("Bilan de sécurité", "page-titre"))
        for ic, t, n in (("shield-alert", "Mots de passe faibles", len(faibles)), ("copy", "Mots de passe utilisés sur plusieurs sites", doublons)):
            self.d.append(reglage_coffre(ic, t, ("%d à changer" % n) if n else "Aucun ✓"))
        self.d.append(label("Le fichier %s s'ouvre aussi avec KeePassXC (PC, Mac), KeePassDX (Android) et Strongbox (iPhone). Rangez-le dans un dossier synchronisé "
                            "(OneDrive, NAS) pour l'avoir partout." % os.path.basename(self.fichier()), "petit", "attenue", wrap=True))

    def copier(self, texte, quoi):
        """Copie protégée : vidée après 30 s, retirée de l'historique du presse-papiers."""
        cb = Gdk.Display.get_default().get_clipboard()
        cb.set_content(Gdk.ContentProvider.new_union([Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", GLib.Bytes.new(texte.encode())),
                                                      Gdk.ContentProvider.new_for_bytes("x-kde-passwordManagerHint", GLib.Bytes.new(b"secret"))]))
        self.toast_d("%s copié — effacé dans 30 s" % quoi)
        def effacer():
            try: cb.set_text("")
            except Exception: pass
            try:
                o = subprocess.run(["cliphist", "list"], capture_output=True, text=True, timeout=3).stdout
                for l in o.splitlines()[:5]:
                    if texte[:20] in l: subprocess.run(["cliphist", "delete"], input=l, text=True, timeout=3)
            except Exception: pass
            return False
        GLib.timeout_add_seconds(30, effacer)
        GLib.timeout_add(1500, lambda: (self._purge_histo(texte), False)[1])

    def _purge_histo(self, texte):
        try:
            o = subprocess.run(["cliphist", "list"], capture_output=True, text=True, timeout=3).stdout
            for l in o.splitlines()[:5]:
                if texte[:20] in l: subprocess.run(["cliphist", "delete"], input=l, text=True, timeout=3)
        except Exception: pass

    def toast_d(self, t):
        if getattr(self, "l_toast", None) and self.l_toast.get_parent(): self.l_toast.set_text(t)

    def detail(self, e):
        vider(self.d); self.activite()
        h = boite(False, 10); h.append(ico("globe" if e.url else "key-round", 30, "c")); h.append(label(e.title or "Sans nom", "page-titre", hexpand=True))
        h.append(bouton("Modifier", "pencil", "fantome", rappel=lambda: self.editer(e))); self.d.append(h)
        def ligne(titre, val, secret=False, copie=True):
            r = boite(False, 10, "reglage"); t = boite(True, 0, hexpand=True); t.append(label(titre, "petit", "attenue"))
            l = label("•" * 12 if secret else (val or "—"), *(("mdp",) if secret else ()), selectable=not secret, ellipsize=True); t.append(l); r.append(t)
            if secret:
                r.append(bouton(None, "eye", "plat", tip="Afficher", rappel=lambda: l.set_text(val if l.get_text().startswith("•") else "•" * 12)))
            if copie and val: r.append(bouton(None, "copy", "plat", tip="Copier", rappel=lambda: self.copier(val, titre)))
            self.d.append(r)
        ligne("Identifiant", e.username); ligne("Mot de passe", e.password, secret=True)
        if e.url:
            ligne("Site", e.url)
            self.d.append(bouton("Ouvrir le site", "external-link", "fantome", rappel=lambda: S.detacher(["xdg-open", e.url if "://" in e.url else "https://" + e.url])))
        if e.notes: ligne("Notes", e.notes, copie=False)
        k, t = force(e.password or ""); self.d.append(label("Solidité : " + t, "petit", "force-%d" % k))
        self.l_toast = label("", "petit", "accent"); self.d.append(self.l_toast)

    def editer(self, e):
        d = Gtk.Window(transient_for=self.win, modal=True, title="Mot de passe", default_width=480); v = boite(True, 10, margin_top=18, margin_bottom=18, margin_start=18, margin_end=18); d.set_child(v)
        titre = Gtk.Entry(text=(e.title if e else "") or "", placeholder_text="Nom (ex. Netflix, BACKUPO, NAS du bureau)"); v.append(titre)
        url = Gtk.Entry(text=(e.url if e else "") or "", placeholder_text="Site (facultatif)"); v.append(url)
        user = Gtk.Entry(text=(e.username if e else "") or "", placeholder_text="Identifiant / adresse e-mail"); v.append(user)
        h = boite(False, 6); mdp = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True); mdp.set_text((e.password if e else "") or generer()); h.append(mdp)
        dd = Gtk.DropDown.new_from_strings(["20 caractères", "32 caractères", "Phrase de mots", "Sans symboles"]); h.append(dd)
        h.append(bouton(None, "refresh-cw", "plat", tip="Générer", rappel=lambda: mdp.set_text(generer(**[dict(longueur=20), dict(longueur=32), dict(phrase=True), dict(longueur=20, symboles=False)][dd.get_selected()]))))
        v.append(h); fl = label("", "petit"); v.append(fl)
        def maj_force(*_):
            k, t = force(mdp.get_text()); fl.set_text("Solidité : " + t)
            for i in range(5): fl.remove_css_class("force-%d" % i)
            fl.add_css_class("force-%d" % k)
        mdp.connect("changed", maj_force); maj_force()
        notes = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD); notes.set_size_request(-1, 80); notes.get_buffer().set_text((e.notes if e else "") or ""); v.append(notes)
        def ok():
            t = titre.get_text().strip() or url.get_text().strip() or "Sans nom"; nb = notes.get_buffer()
            n = nb.get_text(nb.get_start_iter(), nb.get_end_iter(), True)
            if e: e.title, e.url, e.username, e.password, e.notes = t, url.get_text().strip(), user.get_text().strip(), mdp.get_text(), n
            else: self.kp.add_entry(self.kp.root_group, t, user.get_text().strip(), mdp.get_text(), url=url.get_text().strip(), notes=n, force_creation=True)
            self.kp.save(); d.close(); self.lister()
            if e: self.detail(e)
        b = boite(False, 8, halign=Gtk.Align.END)
        if e: b.append(bouton("Supprimer", "trash-2", "plat", rappel=lambda: (self.kp.delete_entry(e), self.kp.save(), d.close(), self.lister(), self.accueil_detail())))
        b.append(bouton("Annuler", None, "fantome", rappel=d.close)); b.append(bouton("Enregistrer", None, "pilule", rappel=ok)); v.append(b); d.present()

    def importer(self):
        d = Gtk.FileDialog(title="Importer : export Bitwarden (.json) ou CSV (Chrome, Firefox, 1Password…)")
        def fin(dd, r):
            try: g = dd.open_finish(r).get_path()
            except GLib.Error: return
            try:
                n = importer_bitwarden(self.kp, g) if g.lower().endswith(".json") else importer_csv(self.kp, g)
                self.lister(); self.accueil_detail(); self.d.append(label("%d mot%s de passe importé%s ✓ — pensez à supprimer le fichier d'export, il n'est pas chiffré." % (n, "s" if n > 1 else "", "s" if n > 1 else ""), "accent", wrap=True))
            except Exception as ex:
                self.d.append(label("Import impossible : %s" % ex, "attenue", wrap=True))
        d.open(self.win, None, fin)


def reglage_coffre(ic, t, s_):
    r = boite(False, 10, "reglage"); r.append(ico(ic, 18, "c")); c = boite(True, 0, hexpand=True); c.append(label(t, "gras")); c.append(label(s_, "petit", "attenue")); r.append(c); return r


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":       # tests : création, ajout, import Bitwarden, relecture
        from pykeepass import PyKeePass, create_database
        f = "/tmp/coffre-test.kdbx"
        if os.path.exists(f): os.remove(f)
        kp = create_database(f, password="Plateau-Camera-Regie-42"); kp.add_entry(kp.root_group, "NAS", "admin", generer(), url="https://nas.local"); kp.save()
        json.dump({"encrypted": False, "folders": [{"id": "a", "name": "Prod"}], "items": [{"name": "BACKUPO", "folderId": "a", "login": {"username": "dit", "password": "x9!Kz", "uris": [{"uri": "https://xiii"}]}}]}, open("/tmp/bw.json", "w"))
        n = importer_bitwarden(kp, "/tmp/bw.json")
        kp2 = PyKeePass(f, password="Plateau-Camera-Regie-42")
        print("OK        Coffre XIII : %d entrées relues (dont %d importée de Bitwarden), générateur « %s », phrase « %s »" % (len(kp2.entries), n, generer(), generer(phrase=True))); return
    sys.exit(Coffre().run(sys.argv[:1]))
