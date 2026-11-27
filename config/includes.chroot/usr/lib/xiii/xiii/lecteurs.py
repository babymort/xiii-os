# OS XIII — Lecteurs réseau XIII (façon RaiDrive) : NAS, serveurs et clouds montés comme des dossiers,
# visibles dans Fichiers. SMB (partages Windows / NAS), NFS, WebDAV, SFTP, FTP, OneDrive, Google Drive — en local
# comme à distance. Recherche des NAS du réseau (Synology, QNAP, Asustor, TerraMaster, WD, UGREEN, TrueNAS, Freebox…).
# Montage par rclone (FUSE) ; mots de passe chiffrés dans la configuration rclone.
# Application développée par Matthieu Lamotte.
import os, sys, json, re, shutil, subprocess, threading, time
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S, netscan as N
from .ui import *
from .appli import preparer, Volet, page

CONF = os.path.expanduser("~/.config/xiii/lecteurs.json")
RESEAU = os.path.expanduser("~/Réseau"); CLOUD = os.path.expanduser("~/Cloud")
TYPES = [  # clé, nom, icône, description, champs
    ("smb", "NAS / partage Windows (SMB)", "hard-drive", "Synology, QNAP, Asustor, TrueNAS, Freebox, PC Windows…", ["hote", "partage", "utilisateur", "mdp", "domaine"]),
    ("nfs", "NFS", "server", "Partages NFS des NAS et serveurs Linux", ["hote", "chemin"]),
    ("webdav", "WebDAV", "globe", "Nextcloud, ownCloud, NAS en WebDAV, accès à distance en https", ["url", "utilisateur", "mdp"]),
    ("sftp", "SFTP / SSH", "terminal", "Serveurs et NAS joignables en SSH", ["hote", "port", "chemin", "utilisateur", "mdp"]),
    ("ftp", "FTP", "folder", "Serveurs FTP et FTPS", ["hote", "port", "chemin", "utilisateur", "mdp"]),
    ("onedrive", "OneDrive", "cloud", "Compte Microsoft personnel ou professionnel", []),
    ("drive", "Google Drive", "cloud", "Compte Google", []),
]
PAR_TYPE = {t[0]: t for t in TYPES}
LIBELLES = {"hote": "Adresse du serveur (IP ou nom)", "partage": "Partage", "utilisateur": "Utilisateur", "mdp": "Mot de passe", "domaine": "Domaine (facultatif)",
            "chemin": "Dossier (facultatif)", "port": "Port (facultatif)", "url": "Adresse (https://…)"}

def lecteurs():
    try: return json.load(open(CONF))
    except Exception: return []

def sauver(L):
    os.makedirs(os.path.dirname(CONF), exist_ok=True); json.dump(L, open(CONF, "w"), ensure_ascii=False, indent=1)

def ident(nom): return "xiii-" + (re.sub(r"[^a-z0-9]+", "-", sans_accents(nom.lower())).strip("-") or "lecteur")

def point(l):
    return os.path.join(CLOUD if l["type"] in ("onedrive", "drive") else RESEAU, l["nom"].replace("/", "-"))

def monte(l): return os.path.ismount(point(l))

def signets():
    """Lecteurs dans le volet de Fichiers."""
    bm = os.path.join(GLib.get_user_config_dir(), "gtk-3.0", "bookmarks"); os.makedirs(os.path.dirname(bm), exist_ok=True)
    try: L = [x for x in open(bm).read().splitlines() if "/Réseau/" not in GLib.uri_unescape_string(x.split(" ")[0], None) and "/Cloud/" not in GLib.uri_unescape_string(x.split(" ")[0], None)]
    except OSError: L = []
    for l in lecteurs():
        L.append("file://%s %s" % (GLib.uri_escape_string(point(l), "/", False), l["nom"]))
    open(bm, "w").write("\n".join(L) + "\n")

def rclone_creer(l):
    t = l["type"]; rid = ident(l["nom"])
    args = {"smb": ["smb", "host=" + l.get("hote", ""), "user=" + (l.get("utilisateur") or "guest"), "pass=" + l.get("mdp", ""), "domain=" + (l.get("domaine") or "WORKGROUP")],
            "webdav": ["webdav", "url=" + l.get("url", ""), "vendor=other", "user=" + l.get("utilisateur", ""), "pass=" + l.get("mdp", "")],
            "sftp": ["sftp", "host=" + l.get("hote", ""), "user=" + l.get("utilisateur", ""), "pass=" + l.get("mdp", "")] + (["port=" + l["port"]] if l.get("port") else []),
            "ftp": ["ftp", "host=" + l.get("hote", ""), "user=" + (l.get("utilisateur") or "anonymous"), "pass=" + l.get("mdp", "")] + (["port=" + l["port"]] if l.get("port") else []),
            "onedrive": ["onedrive", "config_type=onedrive"], "drive": ["drive", "scope=drive"]}[t]
    env = dict(os.environ)
    if t in ("onedrive", "drive"):      # navigateur en fenêtre privée : chaque connexion peut choisir un compte différent
        env["PATH"] = "/usr/lib/xiii/prive:" + env.get("PATH", "")
    r = subprocess.run(["rclone", "config", "create", rid] + args + ["--obscure"], capture_output=True, text=True, timeout=600, env=env)
    return r.returncode == 0, (r.stderr or r.stdout).strip()[-300:]

def distant(l):
    rid = ident(l["nom"])
    if l["type"] == "smb": return "%s:%s" % (rid, l.get("partage", ""))
    return "%s:%s" % (rid, l.get("chemin", "").lstrip("/") if l["type"] in ("sftp", "ftp") else "")

def monter(l):
    p = point(l); os.makedirs(p, exist_ok=True)
    if monte(l): return True, ""
    if l["type"] == "nfs":
        r = subprocess.run(["pkexec", "mount", "-t", "nfs", "-o", "soft,timeo=50,uid=%d,gid=%d" % (os.getuid(), os.getgid()) if False else "soft,timeo=50",
                            "%s:%s" % (l["hote"], l.get("chemin") or "/"), p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr.strip()
    r = subprocess.run(["rclone", "mount", distant(l), p, "--vfs-cache-mode", "writes", "--dir-cache-time", "30s", "--daemon",
                        "--volname", l["nom"], "--daemon-timeout", "20s"], capture_output=True, text=True, timeout=40)
    time.sleep(.5)
    return monte(l), (r.stderr or "").strip()[-300:]

def demonter(l):
    p = point(l)
    if l["type"] == "nfs": subprocess.run(["pkexec", "umount", p], capture_output=True)
    else: subprocess.run(["fusermount3", "-uz", p], capture_output=True)
    return not monte(l)

def monter_tout(reseau=False):
    """reseau=True : appelé au retour sur un réseau — sans les montages NFS (ils demandent le mot de passe administrateur)."""
    for l in lecteurs():
        if reseau and l["type"] == "nfs": continue
        if l.get("auto", True) and not monte(l):
            try: monter(l)
            except Exception: pass
    signets()

# ------------------------------------------------------------------ hors ligne (copie locale synchronisée)
# Un dossier d'un cloud (ex. « XIII » sur OneDrive) est gardé sur l'ordinateur et synchronisé dans les deux sens
# (rclone bisync) : les applis voient de vrais fichiers locaux, même sans Internet. Ajouts, modifications et
# suppressions passent d'un côté à l'autre ; en cas de conflit, les deux versions sont gardées.
ETAT_SYNC = os.path.expanduser("~/.config/xiii/hors-ligne.json")

def hors_ligne():
    """[(lecteur, {distant, local})] pour tous les dossiers gardés hors ligne."""
    return [(l, d) for l in lecteurs() for d in l.get("hors_ligne", [])]

def lister_dossiers(l, chemin=""):
    r = subprocess.run(["rclone", "lsf", "--dirs-only", "%s:%s" % (ident(l["nom"]), chemin)], capture_output=True, text=True, timeout=120)
    return sorted(x.rstrip("/") for x in r.stdout.splitlines() if x.strip())

def ajouter_hors_ligne(l, distant_, local):
    local = os.path.expanduser(local); os.makedirs(local, exist_ok=True)
    L = lecteurs()
    for x in L:
        if x["nom"] == l["nom"]:
            x.setdefault("hors_ligne", [])
            if not any(d["distant"] == distant_ for d in x["hors_ligne"]): x["hors_ligne"].append({"distant": distant_, "local": local, "premiere": True})
    sauver(L)

def retirer_hors_ligne(l, distant_):
    """Arrête la synchronisation ; les fichiers locaux restent sur l'ordinateur."""
    L = lecteurs()
    for x in L:
        if x["nom"] == l["nom"]: x["hors_ligne"] = [d for d in x.get("hors_ligne", []) if d["distant"] != distant_]
    sauver(L)

def synchroniser_un(l, d, avis=lambda t: None):
    src = "%s:%s" % (ident(l["nom"]), d["distant"]); dst = d["local"]; os.makedirs(dst, exist_ok=True)
    base = ["rclone", "bisync", src, dst, "--create-empty-src-dirs", "--compare", "size,modtime", "--max-delete", "50",
            "--exclude", ".~lock.*", "--exclude", "*.tmp", "--exclude", ".Trash*/**"]
    premiere = d.get("premiere", True)
    avis("Synchronisation de « %s »%s…" % (d["distant"], " (premier téléchargement)" if premiere else ""))
    r = subprocess.run(base + (["--resync"] if premiere else []), capture_output=True, text=True, timeout=6 * 3600)
    if r.returncode != 0 and not premiere and "resync" in (r.stderr + r.stdout).lower():
        r = subprocess.run(base + ["--resync"], capture_output=True, text=True, timeout=6 * 3600)     # état perdu : on refait l'inventaire (rien n'est supprimé)
    if r.returncode != 0 and "unknown flag" in r.stderr:            # rclone plus ancien : options de base seulement
        r = subprocess.run(["rclone", "bisync", src, dst, "--create-empty-src-dirs"] + (["--resync"] if premiere else []), capture_output=True, text=True, timeout=6 * 3600)
    ok = r.returncode == 0
    if ok and premiere:
        L = lecteurs()
        for x in L:
            for y in x.get("hors_ligne", []):
                if x["nom"] == l["nom"] and y["distant"] == d["distant"]: y["premiere"] = False
        sauver(L)
    try: e = json.load(open(ETAT_SYNC))
    except Exception: e = {}
    e[d["local"]] = {"date": time.strftime("%Y-%m-%d %H:%M"), "ok": ok, "message": "" if ok else (r.stderr or r.stdout).strip()[-300:]}
    json.dump(e, open(ETAT_SYNC, "w"), ensure_ascii=False, indent=1)
    return ok, e[d["local"]]["message"]

def synchroniser_tout(avis=lambda t: None):
    verrou = os.path.join(GLib.get_user_runtime_dir(), "xiii-hors-ligne.lock")
    try: fd = os.open(verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if time.time() - os.path.getmtime(verrou) < 6 * 3600: return      # une synchronisation tourne déjà
        os.unlink(verrou); fd = os.open(verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        for l, d in hors_ligne():
            try: synchroniser_un(l, d, avis)
            except Exception as ex: avis("Erreur : %s" % ex)
    finally:
        os.close(fd); os.unlink(verrou)

def etat_sync(local):
    try: return json.load(open(ETAT_SYNC)).get(local)
    except Exception: return None



class Lecteurs(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.lecteurs", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

    def do_command_line(self, cl):
        a = cl.get_arguments()[1:]
        if "--monter-tout" in a:
            threading.Thread(target=monter_tout, args=("--reseau" in a,)).start(); return 0
        self.activer()
        if "--ajouter" in a and a.index("--ajouter") + 1 < len(a):
            self.formulaire("smb", {"hote": a[a.index("--ajouter") + 1]})
        return 0

    def activer(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".type-carte { padding: 14px; } .type-carte:hover { background: alpha(@accent_bg_color, .14); }")
        self.win = Gtk.ApplicationWindow(application=self, title="Lecteurs réseau XIII"); self.win.set_default_size(1060, 700)
        self.volet = Volet("Lecteurs réseau", "NAS, serveurs et clouds dans Fichiers, comme RaiDrive")
        self.volet.ajouter("mes", "hard-drive", "Mes lecteurs", rappel=self.p_mes)
        self.volet.ajouter("ajouter", "plus", "Ajouter un lecteur", rappel=self.p_ajouter)
        self.volet.ajouter("chercher", "radar", "Rechercher les NAS", rappel=self.p_chercher)
        self.win.set_child(self.volet.racine); self.volet.aller("mes"); self.win.present()

    def remplacer(self, cle, w):
        v = self.volet.pile.get_child_by_name(cle)
        if v: self.volet.pile.remove(v)
        self.volet.pile.add_named(w, cle); self.volet.pile.set_visible_child_name(cle)

    # ------------------------------------------------------------------ mes lecteurs
    def p_mes(self):
        sc, v = page("Mes lecteurs", "Montés dans ~/Réseau et ~/Cloud, visibles dans Fichiers ; reconnectés à l'ouverture de session", "hard-drive")
        L = lecteurs()
        if not L: v.append(info_boite("Aucun lecteur pour l'instant : « Ajouter un lecteur » ou « Rechercher les NAS »."))
        for l in L:
            t = PAR_TYPE[l["type"]]; m = monte(l)
            r = boite(False, 12, "reglage"); r.append(ico(t[2], 24, "c" if m else "d"))
            col = boite(True, 0, hexpand=True); col.append(label(l["nom"], "gras"))
            col.append(label("%s · %s · %s" % (t[1], l.get("hote") or l.get("url") or "compte en ligne", "● connecté" if m else "○ déconnecté"), "petit", "attenue", ellipsize=True)); r.append(col)
            if m: r.append(bouton("Ouvrir", "folder-open", "fantome", rappel=lambda l=l: S.detacher(["thunar", point(l)])))
            if l["type"] in ("onedrive", "drive", "webdav", "smb", "sftp"):
                r.append(bouton("Hors ligne…", "download", "fantome", tip="Garder un dossier sur cet ordinateur (copie synchronisée)", rappel=lambda l=l: self.hors_ligne(l)))
            r.append(bouton("Déconnecter" if m else "Connecter", None, "pilule" if not m else "plat", rappel=lambda l=l, m=m: self.basculer(l, m)))
            auto = Gtk.CheckButton(label="Auto", active=l.get("auto", True), valign=Gtk.Align.CENTER); auto.set_tooltip_text("Reconnecter à l'ouverture de session")
            auto.connect("toggled", lambda w, l=l: self.regler(l, auto=w.get_active())); r.append(auto)
            r.append(bouton(None, "trash-2", "plat", tip="Supprimer", rappel=lambda l=l: self.supprimer(l)))
            v.append(r)
        self.remplacer("mes", sc)

    def hors_ligne(self, l):
        """Choisir un dossier du cloud à garder sur l'ordinateur, voir ceux déjà gardés."""
        w = Gtk.Window(transient_for=self.win, modal=True, title="Hors ligne — " + l["nom"], default_width=620, default_height=560)
        v = boite(True, 10, margin_top=18, margin_bottom=18, margin_start=20, margin_end=20)
        v.append(label("Garder sur cet ordinateur", "titre-astoria", "grand-titre"))
        v.append(label("Le dossier est téléchargé puis synchronisé dans les deux sens toutes les 15 minutes : vos applis (projets XIII, montage…) "
                       "voient de vrais fichiers, même sans Internet. Rien n'est supprimé du cloud au premier téléchargement.", "attenue", wrap=True))
        deja = [d for x, d in hors_ligne() if x["nom"] == l["nom"]]
        if deja:
            v.append(label("Déjà gardés", "gras", margin_top=6))
            for d in deja:
                e = etat_sync(d["local"]) or {}
                rr = boite(False, 8, "reglage"); c = boite(True, 0, hexpand=True)
                c.append(label("%s  →  %s" % (d["distant"] or "(tout le compte)", d["local"].replace(os.path.expanduser("~"), "~")), "gras", ellipsize=True))
                c.append(label(("Synchronisé le %s" % e["date"] if e.get("ok") else "Erreur : %s" % e.get("message", "")[:120]) if e else "En attente du premier téléchargement", "petit", "attenue", ellipsize=True))
                rr.append(c)
                rr.append(bouton("Ouvrir", None, "fantome", rappel=lambda d=d: S.detacher(["xiii-fichiers", d["local"]])))
                rr.append(bouton("Arrêter", None, "plat", tip="Les fichiers restent sur l'ordinateur", rappel=lambda d=d: (retirer_hors_ligne(l, d["distant"]), w.close(), self.hors_ligne(l))))
                v.append(rr)
        v.append(label("Ajouter un dossier", "gras", margin_top=10))
        liste = boite(True, 4); v.append(defilant(liste, 220)); liste.append(label("Lecture des dossiers du cloud…", "attenue"))
        dest = Gtk.Entry(placeholder_text="Dossier sur cet ordinateur"); v.append(dest)
        choix = {"d": None}
        def remplir(L):
            vider(liste)
            if isinstance(L, Exception) or not L: liste.append(label("Aucun dossier trouvé (le lecteur est-il connecté ?)", "attenue")); return
            grp = None
            for n in L:
                b = Gtk.CheckButton(label=n, group=grp); grp = grp or b
                def sel(bb, n=n):
                    if not bb.get_active(): return
                    choix["d"] = n
                    # le dossier des projets XIII prend sa place habituelle : ~/XIII
                    dest.set_text("~/XIII" if n.upper() == "XIII" else "~/" + n)
                b.connect("toggled", sel); liste.append(b)
        S.en_fond(lambda: lister_dossiers(l), remplir)
        def go():
            if not choix["d"]: return
            ajouter_hors_ligne(l, choix["d"], dest.get_text().strip() or "~/" + choix["d"]); w.close()
            self.toast_txt("« %s » sera gardé sur l'ordinateur : premier téléchargement en cours…" % choix["d"])
            def fin(r):
                ok = isinstance(r, tuple) and r[0]
                S.detacher(["notify-send", "-a", "Lecteurs réseau", "-i", "folder-download", ("« %s » est sur l'ordinateur" % choix["d"]) if ok else "Téléchargement de « %s » interrompu" % choix["d"],
                            "" if ok else (r[1] if isinstance(r, tuple) else str(r))[:200]])
            d = next(x for y, x in hors_ligne() if y["nom"] == l["nom"] and x["distant"] == choix["d"])
            S.en_fond(lambda: synchroniser_un(l, d), fin)
        b = bouton("Garder sur cet ordinateur", "download", "pilule", rappel=go); b.set_halign(Gtk.Align.END); v.append(b)
        w.set_child(v); w.present()

    def basculer(self, l, m):
        if m: S.en_fond(lambda: demonter(l), lambda r: self.p_mes())
        else:
            self.toast_txt("Connexion à « %s »…" % l["nom"])
            S.en_fond(lambda: monter(l), lambda r: (self.p_mes(), signets(), None if isinstance(r, tuple) and r[0] else self.erreur(r)))

    def erreur(self, r):
        msg = r[1] if isinstance(r, tuple) else str(r)
        d = Gtk.AlertDialog(message="Connexion impossible", detail=(msg or "Vérifiez l'adresse, le partage et les identifiants.")[:400]); d.show(self.win)

    def toast_txt(self, t): S.detacher(["notify-send", "-a", "Lecteurs réseau", "-i", "network-server", t])

    def regler(self, l, **kw):
        L = lecteurs()
        for x in L:
            if x["nom"] == l["nom"]: x.update(kw)
        sauver(L)

    def supprimer(self, l):
        def go():
            demonter(l); subprocess.run(["rclone", "config", "delete", ident(l["nom"])], capture_output=True)
            sauver([x for x in lecteurs() if x["nom"] != l["nom"]]); signets()
        S.en_fond(go, lambda r: self.p_mes())

    # ------------------------------------------------------------------ ajouter
    def p_ajouter(self):
        sc, v = page("Ajouter un lecteur", "Choisissez le type de connexion", "plus")
        g = Gtk.FlowBox(max_children_per_line=3, min_children_per_line=2, selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=10, homogeneous=True)
        for k, n, ic, d, ch in TYPES:
            b = Gtk.Button(); b.add_css_class("carte"); b.add_css_class("type-carte")
            bx = boite(True, 6); bx.append(ico(ic, 28, "c")); bx.append(label(n, "gras")); bx.append(label(d, "petit", "attenue", wrap=True)); b.set_child(bx)
            b.connect("clicked", lambda _b, k=k: self.formulaire(k)); g.append(b)
        v.append(g); self.remplacer("ajouter", sc)

    def formulaire(self, t, valeurs=None):
        valeurs = valeurs or {}; k, n, ic, d, champs = PAR_TYPE[t]
        sc, v = page(n, d, ic)
        defaut = valeurs.get("nom") or (valeurs.get("hote") or n.split(" (")[0])
        if not valeurs.get("nom"):          # plusieurs comptes du même service : « OneDrive 2 », « OneDrive 3 »…
            pris = {x["nom"] for x in lecteurs()}; base, i = defaut, 2
            while defaut in pris: defaut = "%s %d" % (base, i); i += 1
        nom = Gtk.Entry(text=defaut); v.append(reglage_ligne("Nom du lecteur", nom))
        if t in ("onedrive", "drive") and any(x["type"] == t for x in lecteurs()):
            v.append(info_boite("Un autre compte est déjà connecté : la connexion s'ouvre dans une fenêtre privée, pour choisir un autre compte."))
        E = {}
        for c in champs:
            e = Gtk.PasswordEntry(show_peek_icon=True) if c == "mdp" else Gtk.Entry(text=valeurs.get(c, ""))
            if c == "partage":
                box = boite(False, 6); box.append(e); e.set_hexpand(True)
                box.append(bouton("Lister", "list", "fantome", taille=14, rappel=lambda: self.lister_partages(E, box))); v.append(reglage_ligne(LIBELLES[c], box))
            else:
                v.append(reglage_ligne(LIBELLES[c], e))
            E[c] = e
        auto = Gtk.CheckButton(label="Reconnecter automatiquement à l'ouverture de session", active=True); v.append(auto)
        if t in ("onedrive", "drive"):
            v.append(info_boite("Votre navigateur va s'ouvrir pour vous connecter à votre compte et autoriser OS XIII (via rclone). Revenez ensuite ici."))
        if t == "webdav":
            v.append(info_boite("Accès à distance : utilisez l'adresse https de votre NAS (QuickConnect Synology, myQNAPcloud, Nextcloud…)."))
        etat = label("", "attenue", "petit", wrap=True); v.append(etat)
        def ok():
            l = {"nom": nom.get_text().strip() or n, "type": t, "auto": auto.get_active()}
            for c, e in E.items(): l[c] = e.get_text().strip()
            if any(x["nom"] == l["nom"] for x in lecteurs()): etat.set_text("Un lecteur porte déjà ce nom."); return
            etat.set_text("Création de la connexion…" + (" Terminez la connexion dans le navigateur." if t in ("onedrive", "drive") else ""))
            def tache():
                if t != "nfs":
                    ok_, msg = rclone_creer(l)
                    if not ok_: return (False, msg)
                mdp = l.pop("mdp", None)
                sauver(lecteurs() + [l])
                r = monter(l); signets(); return r
            def fin(r):
                if isinstance(r, tuple) and r[0]: self.volet.aller("mes")
                else: etat.set_text("Échec : " + (r[1] if isinstance(r, tuple) else str(r)) or "vérifiez les informations"); self.p_mes()
            S.en_fond(tache, fin)
        v.append(bouton("Connecter", "plug", "pilule", rappel=ok))
        self.remplacer("ajouter", sc)
        for b in self.volet.boutons.values(): b.remove_css_class("actif")
        self.volet.boutons["ajouter"].add_css_class("actif")

    def lister_partages(self, E, box):
        h, u, m = E["hote"].get_text().strip(), E["utilisateur"].get_text().strip(), E["mdp"].get_text()
        def fin(L):
            if not L or isinstance(L, Exception): self.toast_txt("Aucun partage trouvé (identifiants ?)"); return
            popover_menu(box, [("folder", p, lambda p=p: E["partage"].set_text(p)) for p in L])
        S.en_fond(lambda: N.partages_smb(h, u, m), fin)

    # ------------------------------------------------------------------ rechercher
    def p_chercher(self):
        sc, v = page("Rechercher les NAS", "Analyse du réseau : NAS et serveurs de fichiers, reconnus par marque", "radar")
        pb = Gtk.ProgressBar(); v.append(pb); zone = boite(True, 8); v.append(zone)
        zone.append(label("Analyse en cours…", "attenue"))
        def prog(f, t): GLib.idle_add(lambda: (pb.set_fraction(min(1, f / max(1, t))), False)[1])
        def fin(r):
            vider(zone); pb.set_fraction(1)
            if isinstance(r, Exception): zone.append(label("Analyse impossible : %s" % r, "attenue")); return
            serv = [a for a in r if a.get("nas") or set(a.get("ports", [])) & {445, 2049, 22, 21}]
            if not serv: zone.append(label("Aucun NAS ni serveur de fichiers trouvé sur ce réseau. Vous pouvez l'ajouter à la main (accès à distance compris).", "attenue", wrap=True))
            for a in sorted(serv, key=lambda a: not a.get("nas")):
                r_ = boite(False, 12, "reglage"); r_.append(ico("hard-drive" if a.get("nas") else "server", 26, "c"))
                col = boite(True, 0, hexpand=True); col.append(label((a.get("marque") + " · " if a.get("marque") else "") + (a["nom"] or a["ip"]), "gras"))
                srv = [x for x, p in (("SMB", 445), ("NFS", 2049), ("SFTP", 22), ("FTP", 21), ("Web", 5000)) if p in a.get("ports", [])]
                col.append(label("%s · %s · %s" % (a["ip"], a.get("fabricant") or "fabricant inconnu", ", ".join(srv)), "petit", "attenue", ellipsize=True)); r_.append(col)
                t = "smb" if 445 in a["ports"] else "nfs" if 2049 in a["ports"] else "sftp" if 22 in a["ports"] else "ftp"
                r_.append(bouton("Ajouter", "plus", "pilule", rappel=lambda a=a, t=t: self.formulaire(t, {"hote": a["ip"], "nom": a.get("nom") or a.get("marque") or a["ip"]})))
                zone.append(r_)
        self.remplacer("chercher", sc)
        if S.DEMO:
            GLib.timeout_add(500, lambda: (fin([{"ip": "192.168.1.12", "nom": "DS920", "marque": "Synology", "fabricant": "Synology Incorporated", "ports": [445, 5000, 22], "nas": True},
                                                {"ip": "192.168.1.40", "nom": "TS-453D", "marque": "QNAP", "fabricant": "ICP Electronics Inc.", "ports": [445, 2049, 8080], "nas": True},
                                                {"ip": "192.168.1.1", "nom": "freebox", "marque": "Freebox", "fabricant": "Freebox SAS", "ports": [445, 80], "nas": True}]), False)[1]); return
        S.en_fond(lambda: N.analyser(N.plage_par_defaut(), prog, ports=[21, 22, 80, 139, 443, 445, 548, 2049, 5000, 5001, 8080]), fin)

def reglage_ligne(t, w):
    r = boite(False, 12, "reglage"); r.append(label(t, hexpand=True)); w.set_size_request(320, -1); r.append(w); return r

def info_boite(t):
    r = boite(False, 10, "info-bulle"); r.append(ico("info", 16, "c")); r.append(label(t, wrap=True, hexpand=True)); return r

def main():
    if "--synchroniser" in sys.argv:        # lancé par le bureau toutes les 15 min et au retour du réseau
        synchroniser_tout(print); return
    sys.exit(Lecteurs().run(sys.argv))
