# OS XIII — mises à jour d'OS XIII depuis GitHub (babymort/xiii-os), sans perte de données.
# Canal « Stable » (branche main) ou « Beta » (branche beta). Vérification régulière, liste des nouveautés,
# instantané Timeshift avant d'appliquer, puis :
#   • fichiers d'OS XIII remplacés (applications XIII, thèmes, icônes, réglages système)
#   • nouveaux paquets installés, scripts d'installation modifiés relancés (ceux marqués « xiii-maj: relancer »)
#   • réglages des comptes complétés sans rien écraser (nouveaux raccourcis, nouvelles actions de Fichiers)
# Le dossier personnel, les projets, les jeux et les réglages de chacun ne sont jamais touchés.
# Application développée par Matthieu Lamotte.
import os, sys, json, re, shutil, subprocess, tarfile, hashlib, pwd, time, datetime, urllib.request, filecmp

DEPOT = "babymort/xiii-os"
VERSION = "/usr/share/xiii/VERSION.json"
ETAT = "/var/lib/xiii/maj.json"
JOURNAL = "/var/log/xiii-maj.log"
CACHE = "/var/cache/xiii-maj"
UA = {"User-Agent": "OS-XIII-maj", "Accept": "application/vnd.github+json"}
# fichiers de /etc qui appartiennent à l'utilisateur ou à la machine : jamais remplacés s'ils existent
GARDER = ("var/lib/xiii/maj.json", "usr/share/xiii/VERSION.json", "etc/fstab", "etc/hostname", "etc/hosts", "etc/xiii/duo.json", "etc/lightdm/lightdm.conf.d/60-autologin.conf",
          "etc/os-release", "etc/issue", "etc/xiii/edition")

def version():
    try: return json.load(open(VERSION))
    except Exception: return {"version": "inconnue", "branche": "beta", "commit": "", "date": ""}

def api(chemin):
    with urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/%s%s" % (DEPOT, chemin), headers=UA), timeout=25) as r:
        return json.load(r)

def verifier(canal=None):
    """{'dispo': bool, 'local', 'distant', 'nouveautes': [(date, message)], 'canal'}"""
    v = version(); canal = canal or v.get("branche") or "beta"
    br = "main" if canal in ("stable", "main") else "beta"
    tete = api("/commits/" + br)
    sha = tete["sha"]; L = []
    if v.get("commit") and not sha.startswith(v["commit"]):
        try:
            cmp_ = api("/compare/%s...%s" % (v["commit"], sha))
            for c in cmp_.get("commits", [])[-60:]:
                m = c["commit"]["message"].split("\n")[0]
                if not m.lower().startswith(("merge", "firmware")): L.append((c["commit"]["author"]["date"][:10], m))
        except Exception:
            L = [(tete["commit"]["author"]["date"][:10], tete["commit"]["message"].split("\n")[0])]
    elif not v.get("commit"):
        L = [(tete["commit"]["author"]["date"][:10], tete["commit"]["message"].split("\n")[0])]
    return {"dispo": not (v.get("commit") and sha.startswith(v["commit"])), "local": v, "distant": sha[:7], "date": tete["commit"]["author"]["date"][:10],
            "nouveautes": list(reversed(L)), "canal": br}

# ------------------------------------------------------------------------------ application (root)
def log(m):
    l = "%s  %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), m)
    print(l, flush=True)
    try: open(JOURNAL, "a").write(l + "\n")
    except OSError: pass

def evenement(typ, msg):
    try:
        os.makedirs("/var/log/xiii", exist_ok=True)
        with open("/var/log/xiii/evenements.log", "a") as o: o.write("%s|%s|%s\n" % (datetime.datetime.now().astimezone().isoformat(timespec="seconds"), typ, msg))
    except OSError: pass

def instantane():
    # Btrfs : instantané instantané et sans copie, avec « Revenir à… » dans le menu de démarrage
    if os.path.exists("/etc/snapper/configs/root") and os.path.exists("/usr/local/sbin/xiii-instantanes"):
        r = subprocess.run(["/usr/local/sbin/xiii-instantanes", "creer", "Avant mise à jour OS XIII"], capture_output=True, text=True, timeout=600)
        log("Instantané : " + ("n°" + r.stdout.strip() if r.returncode == 0 else "impossible"))
        if r.returncode == 0: return True
    if not shutil.which("timeshift"): log("Timeshift absent : pas d'instantané"); return False
    r = subprocess.run(["timeshift", "--create", "--comments", "Avant mise à jour OS XIII", "--tags", "O", "--scripted"], capture_output=True, text=True, timeout=3600)
    log("Instantané Timeshift : " + ("créé" if r.returncode == 0 else "impossible (%s)" % (r.stdout + r.stderr).strip()[-200:]))
    return r.returncode == 0

def telecharger(sha):
    os.makedirs(CACHE, exist_ok=True); f = os.path.join(CACHE, "xiii-os-%s.tar.gz" % sha[:7])
    urllib.request.urlretrieve("https://codeload.github.com/%s/tar.gz/%s" % (DEPOT, sha), f)
    d = os.path.join(CACHE, "src"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    with tarfile.open(f) as t:
        t.extractall(d, filter="data") if hasattr(tarfile, "data_filter") else t.extractall(d)
    os.unlink(f)
    return os.path.join(d, os.listdir(d)[0])

def copier_overlay(src):
    """Remplace les fichiers d'OS XIII ; ne touche pas aux fichiers listés dans GARDER s'ils existent."""
    racine = os.path.join(src, "config", "includes.chroot"); n = 0
    for r, ds, fs in os.walk(racine):
        rel_dir = os.path.relpath(r, racine)
        if "__pycache__" in rel_dir: continue
        for f in fs:
            rel = os.path.normpath(os.path.join(rel_dir, f)); s = os.path.join(r, f); d = "/" + rel
            if rel in GARDER and os.path.exists(d): continue
            if os.path.islink(s):
                if os.path.lexists(d) and not os.path.isdir(d): os.unlink(d)
                os.makedirs(os.path.dirname(d), exist_ok=True); os.symlink(os.readlink(s), d); continue
            if os.path.exists(d) and filecmp.cmp(s, d, shallow=False): continue
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d + ".xiii-nouveau"); os.replace(d + ".xiii-nouveau", d); n += 1
    log("Fichiers d'OS XIII mis à jour : %d" % n)
    # modules Python supprimés depuis : on retire ceux qui n'existent plus
    mod = os.path.join(racine, "usr/lib/xiii/xiii")
    if os.path.isdir(mod):
        for f in os.listdir("/usr/lib/xiii/xiii"):
            if f.endswith(".py") and not os.path.exists(os.path.join(mod, f)): os.unlink(os.path.join("/usr/lib/xiii/xiii", f)); log("Retiré : " + f)
    shutil.rmtree("/usr/lib/xiii/xiii/__pycache__", ignore_errors=True)

def paquets(src):
    L = []
    for f in sorted(os.listdir(os.path.join(src, "config", "package-lists"))):
        for l in open(os.path.join(src, "config", "package-lists", f)):
            l = l.split("#")[0].strip()
            if l and not l.startswith("!"): L += l.split()
    manquants = [p for p in dict.fromkeys(L) if not subprocess.run(["dpkg-query", "-W", "-f=${Status}", p], capture_output=True, text=True).stdout.endswith("installed")]
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    subprocess.run(["apt-get", "update", "-qq"], env=env)
    for p in manquants:
        r = subprocess.run(["apt-get", "install", "-y", "--no-install-recommends", p], capture_output=True, env=env)
        log("Paquet %s : %s" % (p, "installé" if r.returncode == 0 else "indisponible"))
    log("Paquets d'OS XIII : %d nouveau(x)" % len(manquants))

def scripts(src):
    """Relance les scripts d'installation marqués « xiii-maj: relancer » dont le contenu a changé."""
    try: etat = json.load(open(ETAT))
    except Exception: etat = {}
    vus = etat.setdefault("scripts", {})
    d = os.path.join(src, "config", "hooks", "normal")
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f); t = open(p, "rb").read()
        if b"xiii-maj: relancer" not in t: continue
        h = hashlib.sha256(t).hexdigest()
        if vus.get(f) == h: continue
        log("Script %s…" % f)
        r = subprocess.run(["sh", p], capture_output=True, text=True, env=dict(os.environ, DEBIAN_FRONTEND="noninteractive"), timeout=3600)
        log("Script %s : %s" % (f, "terminé" if r.returncode == 0 else "erreur %d" % r.returncode))
        if r.returncode == 0: vus[f] = h
    os.makedirs(os.path.dirname(ETAT), exist_ok=True); json.dump(etat, open(ETAT, "w"))

def completer_comptes(src):
    """Ajoute aux comptes existants ce qui est nouveau (raccourcis labwc, actions de Fichiers, fichiers absents), sans rien écraser."""
    skel = os.path.join(src, "config", "includes.chroot", "etc", "skel")
    if not os.path.isdir(skel): return
    import xml.etree.ElementTree as ET
    for u in pwd.getpwall():
        if not (1000 <= u.pw_uid < 60000) or not os.path.isdir(u.pw_dir): continue
        for r, ds, fs in os.walk(skel):
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), skel); d = os.path.join(u.pw_dir, rel)
                try:
                    if not os.path.exists(d):
                        os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(os.path.join(r, f), d); os.chown(d, u.pw_uid, u.pw_gid)
                    elif rel == ".config/labwc/rc.xml":
                        n = fusion_xml(os.path.join(r, f), d, "keybind", "key")
                        os.chown(d, u.pw_uid, u.pw_gid)
                        if n: log("%s : %d raccourci(s) ajouté(s)" % (u.pw_name, n))
                    elif rel == ".config/Thunar/uca.xml":
                        fusion_xml(os.path.join(r, f), d, "action", "unique-id", texte=True); os.chown(d, u.pw_uid, u.pw_gid)
                except Exception as e:
                    log("Compte %s, %s : %s" % (u.pw_name, rel, e))

def fusion_xml(nouveau, actuel, balise, cle, texte=False):
    """Ajoute à l'actuel les éléments <balise> du nouveau fichier qui n'y sont pas (comparés par attribut ou sous-élément « cle »)."""
    import xml.etree.ElementTree as ET
    loc = lambda t: t.split("}")[-1]
    val = (lambda e: e.findtext(cle) or "") if texte else (lambda e: e.get(cle))
    a, n = ET.parse(actuel), ET.parse(nouveau)
    deja = {val(e) for e in a.getroot().iter() if loc(e.tag) == balise}
    sig = lambda e: None
    if balise == "keybind":
        # raccourcis : ne pas remettre ce que l'utilisateur a supprimé ou déplacé sur une autre touche
        def sig(e):
            acts = []
            for x in e.findall("action"):
                at = dict(x.attrib); n = at.pop("name", ""); acts.append((n, at))
            return json.dumps(acts, sort_keys=True, ensure_ascii=False)
        try:
            for r in json.load(open(os.path.join(os.path.dirname(os.path.dirname(actuel)), "xiii", "raccourcis-retires.json"))): deja.add(r["cle"])
        except Exception: pass
        sigs = {sig(e) for e in a.getroot().iter() if loc(e.tag) == balise}
    parents_a = {}
    for p in a.getroot().iter():
        for e in p:
            if loc(e.tag) == balise: parents_a.setdefault(loc(p.tag), p)
    ajout = 0
    for p in n.getroot().iter():
        for e in list(p):
            if loc(e.tag) == balise and val(e) not in deja and not (balise == "keybind" and sig(e) in sigs):
                cible = parents_a.get(loc(p.tag), a.getroot()); cible.append(e); deja.add(val(e)); ajout += 1
    if ajout:
        shutil.copy2(actuel, actuel + ".avant-maj"); a.write(actuel, encoding="UTF-8", xml_declaration=True)
    return ajout

def finaliser(sha, canal):
    for c in (["update-desktop-database", "-q", "/usr/share/applications"], ["gtk-update-icon-cache", "-qf", "/usr/share/icons/hicolor"],
              ["gtk-update-icon-cache", "-qf", "/usr/share/icons/XIII"], ["update-mime-database", "/usr/share/mime"], ["fc-cache", "-f"], ["systemctl", "daemon-reload"]):
        try: subprocess.run(c, capture_output=True, timeout=300)
        except Exception: pass
    v = {"version": datetime.date.today().strftime("%Y%m%d") + "-" + canal + "-" + sha[:7], "branche": canal, "commit": sha[:7], "date": datetime.date.today().isoformat(), "mise_a_jour": True,
         "edition": version().get("edition", "complete")}
    try:      # numéro affiché par le système
        n = datetime.date.today().strftime("%Y.%m.%d")
        t = open("/etc/os-release").read()
        t = re.sub(r'(?m)^VERSION_ID=.*$', 'VERSION_ID="%s"' % n, t); t = re.sub(r'(?m)^VERSION=.*$', 'VERSION="%s (%s)"' % (n, canal), t)
        open("/etc/os-release", "w").write(t)
    except OSError:
        pass
    os.makedirs(os.path.dirname(VERSION), exist_ok=True); json.dump(v, open(VERSION, "w"))
    log("OS XIII est à jour : %s" % v["version"])
    evenement("maj", "OS XIII mis à jour (%s, %s)" % (canal, sha[:7]))

def appliquer(canal, sha, avec_instantane=True):
    if os.geteuid() != 0: raise SystemExit("à lancer en administrateur (pkexec)")
    log("=== Mise à jour vers %s (%s) ===" % (sha[:7], canal))
    if avec_instantane: instantane()
    log("Téléchargement…"); src = telecharger(sha)
    copier_overlay(src); paquets(src); scripts(src); completer_comptes(src); finaliser(sha, canal)
    shutil.rmtree(os.path.join(CACHE, "src"), ignore_errors=True)

def main():
    a = sys.argv[1:]
    if a and a[0] == "appliquer":       # xiii-maj-systeme appliquer <canal> <sha> [--sans-instantane]
        appliquer(a[1], a[2], "--sans-instantane" not in a)
    elif a and a[0] == "verifier":
        print(json.dumps(verifier(a[1] if len(a) > 1 else None), ensure_ascii=False, indent=1))
    else:
        print("usage : xiii-maj-systeme verifier [stable|beta] | appliquer <canal> <commit>")

if __name__ == "__main__":
    main()
