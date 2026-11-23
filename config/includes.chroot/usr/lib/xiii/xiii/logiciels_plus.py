# OS XIII — Centre de logiciels, partie « données » : recherche partout (sélection XIII, Debian, Flathub, AppImage, GitHub),
# fiches détaillées (description, captures, taille réelle, popularité), packs métiers, mises à jour groupées.
# Application développée par Matthieu Lamotte.
import os, re, json, time, subprocess, shutil, urllib.request, urllib.parse, threading, concurrent.futures

CACHE = os.path.expanduser("~/.cache/xiii/logiciels")
UA = {"User-Agent": "OS-XIII", "Accept": "application/json"}

# Packs métiers : clés du catalogue (logiciels.CATALOGUE)
PACKS = [
    ("monteur", "Monteur", "film", "Montage, conversion, son et graphisme d'appoint", ["kdenlive", "shotcut", "handbrake", "audacity", "blender", "gimp"],
     "DaVinci Resolve s'installe à part, avec l'assistant (page « DaVinci Resolve »)."),
    ("regisseur", "Régisseur", "cctv", "Diffusion, boutons de régie, lumière, réseau", ["obs", "companion", "qlcplus", "iperf3", "scanip", "qrwifi", "remmina"], ""),
    ("photographe", "Photographe", "aperture", "RAW, retouche, dessin", ["darktable", "gimp", "krita", "inkscape"], ""),
    ("son", "Ingé son", "audio-lines", "Enregistrement multipiste, montage audio, DJ", ["ardour", "audacity", "mixxx"], ""),
    ("graphiste", "Graphiste", "pen-tool", "Vectoriel, peinture, 3D, retouche", ["inkscape", "krita", "blender", "gimp"], ""),
    ("bureau", "Bureau", "file-text", "Documents, courriel, notes, mots de passe", ["libreoffice", "thunderbird", "obsidian", "bitwarden"], ""),
]


def _json(url, corps=None, delai=20):
    req = urllib.request.Request(url, data=json.dumps(corps).encode() if corps is not None else None, headers=dict(UA, **({"Content-Type": "application/json"} if corps is not None else {})))
    with urllib.request.urlopen(req, timeout=delai) as r: return json.load(r)


def humain(o):
    o = float(o or 0)
    for u in ("o", "Ko", "Mo", "Go"):
        if o < 1000 or u == "Go": return ("%.0f %s" if u in ("o", "Ko") else "%.1f %s") % (o, u)
        o /= 1000


# ------------------------------------------------------------------ recherche partout
def _catalogue(q, CAT):
    qq = q.lower(); R = []
    for cat, L in CAT.items():
        for k, nom, desc, src, cmd, ic in L:
            if qq in (nom + " " + desc + " " + k).lower(): R.append(dict(cle=k, nom=nom, desc=desc, src=src, cmd=cmd, ic=ic, origine="Sélection XIII"))
    return R


def _apt(q):
    """Paquets Debian qui ont une application (fichier .desktop) — pas les bibliothèques."""
    try: o = subprocess.run(["apt-cache", "search", q], capture_output=True, text=True, timeout=20).stdout
    except Exception: return []
    R = []
    for l in o.splitlines():
        nom, _, desc = l.partition(" - ")
        if re.search(r"^(lib|python3-|golang-|node-|ruby-|r-cran|fonts-|texlive)|-(dev|doc|dbg|data|common|l10n|dbgsym)$", nom): continue
        R.append(dict(cle="apt-" + nom, nom=nom, desc=desc, src="apt:" + nom, cmd=nom, ic="package", origine="Debian"))
        if len(R) >= 12: break
    return R


def _flathub(q):
    for corps in ({"query": q}, {"query": q, "filters": []}):
        try:
            H = _json("https://flathub.org/api/v2/search", corps).get("hits", [])
            if H:
                return [dict(cle=h["app_id"], nom=h.get("name") or h["app_id"], desc=(h.get("summary") or "")[:160], src="flatpak:" + h["app_id"], cmd=None, ic="package",
                             origine="Flathub", icone_url=h.get("icon"), popularite=h.get("installs_last_month")) for h in H[:12]]
        except Exception:
            pass
    return []


def _appimages(q):
    """Catalogue AppImageHub (mis en cache une journée) ; installation par la page GitHub du projet."""
    f = os.path.join(CACHE, "appimagehub.json")
    try:
        if not os.path.exists(f) or time.time() - os.path.getmtime(f) > 86400:
            os.makedirs(CACHE, exist_ok=True)
            with urllib.request.urlopen(urllib.request.Request("https://appimage.github.io/feed.json", headers=UA), timeout=30) as r: open(f, "wb").write(r.read())
        items = json.load(open(f)).get("items", [])
    except Exception:
        return []
    qq = q.lower(); R = []
    for it in items:
        txt = ((it.get("name") or "") + " " + (it.get("description") or "")).lower()
        if qq not in txt: continue
        gh = next((l.get("url") for l in it.get("links") or [] if l.get("type") == "GitHub"), None)
        if not gh: continue
        R.append(dict(cle="appimage-" + it["name"], nom=it["name"], desc=re.sub(r"<[^>]+>", "", it.get("description") or "")[:160], src="github:" + gh, cmd=None, ic="package", origine="AppImage"))
        if len(R) >= 8: break
    return R


def _github(q):
    try:
        H = _json("https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": q + " linux in:name,description,topics", "sort": "stars", "per_page": 8})).get("items", [])
    except Exception:
        return []
    return [dict(cle="gh-" + h["full_name"], nom=h["name"], desc=(h.get("description") or "")[:160], src="github:" + h["full_name"], cmd=None, ic="package",
                 origine="GitHub", popularite=h.get("stargazers_count")) for h in H]


def chercher_partout(q, CAT):
    """→ [(origine, [résultats])] dans l'ordre : Sélection XIII, Flathub, Debian, AppImage, GitHub."""
    with concurrent.futures.ThreadPoolExecutor(5) as ex:
        F = {"Sélection XIII": ex.submit(_catalogue, q, CAT), "Flathub": ex.submit(_flathub, q), "Debian": ex.submit(_apt, q),
             "AppImage": ex.submit(_appimages, q), "GitHub": ex.submit(_github, q)}
        R = []
        for k in ("Sélection XIII", "Flathub", "Debian", "AppImage", "GitHub"):
            try: L = F[k].result(timeout=45)
            except Exception: L = []
            if L: R.append((k, L))
    vus = set(); out = []
    for k, L in R:      # un même logiciel n'apparaît qu'une fois (priorité à la sélection XIII, puis Flathub…)
        L2 = [x for x in L if x["nom"].lower() not in vus]
        vus.update(x["nom"].lower() for x in L2)
        if L2: out.append((k, L2))
    return out


# ------------------------------------------------------------------ fiche détaillée
def fiche(src):
    """{description, taille, telechargement, popularite, version, site, licence, captures: [url]}"""
    t, _, v = src.partition(":"); d = {"captures": []}
    try:
        if t == "flatpak":
            a = _json("https://flathub.org/api/v2/appstream/" + v)
            d["description"] = re.sub(r"\s+\n", "\n", re.sub(r"<li>", "• ", re.sub(r"</(p|li)>", "\n", a.get("description") or ""))).strip()
            d["description"] = re.sub(r"<[^>]+>", "", d["description"])
            for sc in (a.get("screenshots") or [])[:5]:
                sz = sc.get("sizes") or {}
                u = sz.get("624x351") or sz.get("752x423") or next(iter(sz.values()), None) if isinstance(sz, dict) else None
                if not u and isinstance(sz, list) and sz: u = sz[0].get("src")
                if u: d["captures"].append(u)
            d["site"] = (a.get("urls") or {}).get("homepage"); d["licence"] = a.get("project_license")
            rel = a.get("releases") or []
            if rel: d["version"] = rel[0].get("version")
            try:
                st = _json("https://flathub.org/api/v2/stats/" + v); d["popularite"] = "%s installations" % format(st.get("installs_total", 0), ",").replace(",", " ")
            except Exception: pass
            try:
                o = subprocess.run(["flatpak", "remote-info", "--user", "flathub", v], capture_output=True, text=True, timeout=30).stdout
                m = re.search(r"Installed size:\s*(.+)", o) or re.search(r"Taille installée\s*:\s*(.+)", o); m2 = re.search(r"Download size:\s*(.+)", o) or re.search(r"Taille du téléchargement\s*:\s*(.+)", o)
                if m: d["taille"] = m.group(1).strip()
                if m2: d["telechargement"] = m2.group(1).strip()
            except Exception: pass
        elif t in ("apt", "deb"):
            p = v.split("|")[-1].split(":")[0]
            o = subprocess.run(["apt-cache", "show", "--no-all-versions", p], capture_output=True, text=True, timeout=20).stdout
            m = re.search(r"^Installed-Size: (\d+)", o, re.M); d["taille"] = humain(int(m.group(1)) * 1024) + " (avec ce qui manque : voir à l'installation)" if m else None
            m = re.search(r"^Size: (\d+)", o, re.M); d["telechargement"] = humain(int(m.group(1))) if m else None
            m = re.search(r"^Version: (.+)", o, re.M); d["version"] = m.group(1) if m else None
            m = re.search(r"^Homepage: (.+)", o, re.M); d["site"] = m.group(1) if m else None
            m = re.search(r"^Description(?:-fr|-en)?: (.+)\n((?: .*\n?)*)", o, re.M)
            if m: d["description"] = m.group(1) + "\n" + "\n".join(l[1:] if l.strip() != "." else "" for l in m.group(2).splitlines())
        elif t == "github":
            r = _json("https://api.github.com/repos/" + v)
            d["description"] = r.get("description") or ""; d["popularite"] = "★ %s sur GitHub" % format(r.get("stargazers_count", 0), ",").replace(",", " ")
            d["site"] = r.get("homepage") or r.get("html_url"); d["licence"] = (r.get("license") or {}).get("spdx_id")
            try:
                rel = _json("https://api.github.com/repos/%s/releases/latest" % v); d["version"] = rel.get("tag_name")
                from .store_github import meilleur_fichier
                a, typ = meilleur_fichier(rel.get("assets", []))
                if a: d["telechargement"] = "%s (%s)" % (humain(a.get("size")), typ)
            except Exception: pass
            m = re.findall(r"!\[[^\]]*\]\((https://[^)\s]+\.(?:png|jpg|jpeg|gif|webp))", _readme(v) or "")
            d["captures"] = m[:4]
    except Exception as e:
        d["erreur"] = str(e)
    return d


def _readme(depot):
    try:
        with urllib.request.urlopen(urllib.request.Request("https://raw.githubusercontent.com/%s/HEAD/README.md" % depot, headers=UA), timeout=15) as r: return r.read(200000).decode("utf-8", "replace")
    except Exception:
        return ""


def image_locale(url):
    """Télécharge une capture dans le cache (une fois)."""
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, re.sub(r"[^\w.-]", "_", url)[-120:])
    if not os.path.exists(f):
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "OS-XIII"}), timeout=25) as r: open(f, "wb").write(r.read(8_000_000))
    return f


# ------------------------------------------------------------------ mises à jour groupées
def a_mettre_a_jour():
    """{systeme: [paquets], flatpak: [ids], github: [(dépôt, installée, nouvelle)]} — sans mot de passe (listes déjà connues)."""
    R = {"systeme": [], "flatpak": [], "github": []}
    try:
        o = subprocess.run(["apt", "list", "--upgradable"], capture_output=True, text=True, timeout=60).stdout
        R["systeme"] = [l.split("/")[0] for l in o.splitlines() if "/" in l and "[" in l]
    except Exception: pass
    if shutil.which("flatpak"):
        for sc in ("--user", "--system"):
            try:
                o = subprocess.run(["flatpak", "remote-ls", sc, "--updates", "--columns=application"], capture_output=True, text=True, timeout=90).stdout
                R["flatpak"] += [l.strip() for l in o.splitlines() if "." in l]
            except Exception: pass
    try:
        from .store_github import suivi, requete
        for depot, e in suivi().items():
            try:
                t = requete("/repos/%s/releases/latest" % depot).get("tag_name")
                if t and t != e.get("version"): R["github"].append((depot, e.get("version"), t))
            except Exception: pass
    except Exception: pass
    return R


def tout_mettre_a_jour(progres, systeme=True, nuit=False):
    """Système (mot de passe, sauf la nuit : fait par le service système), Flathub, GitHub. → liste des erreurs."""
    E = []
    if systeme and not nuit:
        progres("Système (mot de passe administrateur)…")
        if subprocess.run(["pkexec", "sh", "-c", "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confold upgrade"], capture_output=True).returncode:
            E.append("système")
    if shutil.which("flatpak"):
        progres("Applications Flathub…")
        if subprocess.run(["flatpak", "update", "--user", "-y", "--noninteractive"], capture_output=True).returncode: E.append("Flathub")
    try:
        from .store_github import suivi, installer, requete
        for depot, e in suivi().items():
            try:
                t = requete("/repos/%s/releases/latest" % depot).get("tag_name")
                if t and t != e.get("version"):
                    progres("GitHub : %s %s…" % (e.get("nom", depot), t)); installer(depot, lambda f, txt: None)
            except Exception:
                E.append(depot)
    except Exception: pass
    try:
        json.dump({"date": time.strftime("%Y-%m-%d %H:%M"), "erreurs": E}, open(os.path.join(os.path.expanduser("~/.local/share/xiii"), "maj-apps.json"), "w"))
    except Exception: pass
    return E
