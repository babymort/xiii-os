# OS XIII — prépare la Suite XIII hors ligne : téléchargement du site public (GitHub babymort/suite-xiii, branche main),
# copie locale des bibliothèques chargées depuis les CDN (jsPDF, PDF.js, Leaflet, xlsx…), liste des outils, icônes, lanceurs.
# Utilisé à la construction de l'ISO (hook 0900) et par « Mettre à jour la Suite XIII » (dossier personnel).
# Application développée par Matthieu Lamotte.
import os, re, sys, io, json, shutil, zipfile, tempfile, base64, html, urllib.request, hashlib

DEPOT = "https://codeload.github.com/babymort/suite-xiii/zip/refs/heads/main"
CDN = re.compile(r"https://(?:cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|unpkg\.com)/[^\s\"'`)<>]+?\.(?:min\.js|js|mjs|css|wasm)(?=[\"'`)\s])")
EXCLUS = ("ndi-xiii.zip", "graphico-ndi.zip", "_selftest_pdf", ".git")


def telecharger(url, t=60):
    req = urllib.request.Request(url, headers={"User-Agent": "OS-XIII"})
    with urllib.request.urlopen(req, timeout=t) as r:
        return r.read()


def extraire(zip_octets, dest):
    """Extrait l'archive GitHub (dossier racine suite-xiii-main/) dans dest ; renvoie le chemin du module NDI s'il existe."""
    tmp = tempfile.mkdtemp(prefix="xiii-suite-")
    zipfile.ZipFile(io.BytesIO(zip_octets)).extractall(tmp)
    racine = os.path.join(tmp, os.listdir(tmp)[0])
    ndi = os.path.join(racine, "ndi-xiii.zip")
    ndi_copie = None
    if os.path.exists(ndi):
        ndi_copie = os.path.join(tempfile.gettempdir(), "ndi-xiii.zip"); shutil.copy(ndi, ndi_copie)
    for x in EXCLUS:
        p = os.path.join(racine, x)
        if os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
        elif os.path.exists(p): os.unlink(p)
    if os.path.exists(dest + ".nouveau"): shutil.rmtree(dest + ".nouveau")
    shutil.move(racine, dest + ".nouveau")
    if os.path.exists(dest): shutil.rmtree(dest)
    os.rename(dest + ".nouveau", dest)
    shutil.rmtree(tmp, ignore_errors=True)
    return ndi_copie


def miroir_cdn(dest, journal=print):
    """Copie locale des bibliothèques CDN et réécriture des adresses (/__cdn/hôte/chemin). Les autres restent en ligne."""
    fichiers = [os.path.join(r, f) for r, _, fs in os.walk(dest) for f in fs if f.endswith((".html", ".js")) and "/__cdn/" not in os.path.join(r, f)]
    urls = set()
    for f in fichiers:
        urls.update(CDN.findall(open(f, encoding="utf-8", errors="ignore").read()))
    ok = {}
    for u in sorted(urls):
        local = "/__cdn/" + u.split("://", 1)[1]
        cible = dest + local
        try:
            if not os.path.exists(cible):
                data = telecharger(u, 40)
                os.makedirs(os.path.dirname(cible), exist_ok=True); open(cible, "wb").write(data)
            ok[u] = local
        except Exception as e:
            journal("  CDN indisponible (reste en ligne) : %s (%s)" % (u, e))
    for f in fichiers:
        t = open(f, encoding="utf-8", errors="ignore").read(); t2 = t
        for u, l in ok.items():
            if u in t2: t2 = t2.replace(u, l)
        if t2 != t: open(f, "w", encoding="utf-8").write(t2)
    journal("  %d bibliothèque(s) copiée(s) en local sur %d" % (len(ok), len(urls)))
    return ok


def outils(dest):
    """Outils de la page d'accueil (cartes visibles) : id, nom, rôle, couleur, description."""
    t = open(os.path.join(dest, "index.html"), encoding="utf-8").read()
    L, vus = [], set()
    for m in re.finditer(r'<a class="(?:card|break)[^"]*" href="([a-z0-9_-]+)\.html"([^>]*)>(.*?)</a>', t, re.S):
        oid, attrs, corps = m.group(1), m.group(2), m.group(3)
        if "display:none" in attrs.replace(" ", "") or oid in vus or oid.endswith("-m"): continue
        if not os.path.exists(os.path.join(dest, oid + ".html")): continue
        nom = re.search(r'class="card-name">(.*?)</div>', corps, re.S)
        nom = re.sub(r"<[^>]+>", "", nom.group(1)).strip() if nom else oid.upper() + " XIII"
        nom = re.sub(r"\s+", " ", html.unescape(nom))
        role = re.search(r'class="card-role">(.*?)</div>', corps, re.S)
        desc = re.search(r'class="card-desc">(.*?)</p>', corps, re.S)
        coul = re.search(r"--dc:\s*(#[0-9a-fA-F]{3,6})", attrs)
        emoji = re.search(r'class="card-icon">(.*?)</div>', corps, re.S)
        if not nom or nom == oid.upper() + " XIII":
            b = re.search(r"<b>(.*?)</b>", corps); nom = b.group(1).strip() if b else nom
        titre = re.search(r'title="[^"—]*—\s*([^"]+)"', attrs)
        vus.add(oid)
        L.append({"id": oid, "nom": nom, "role": html.unescape(re.sub(r"<[^>]+>", "", role.group(1))).strip() if role else (html.unescape(titre.group(1)).strip().capitalize() if titre else ""),
                  "description": html.unescape(re.sub(r"<[^>]+>", "", desc.group(1))).strip() if desc else "",
                  "couleur": coul.group(1) if coul else "#f0b378", "emoji": html.unescape(emoji.group(1)).strip() if emoji else "",
                  "logo": os.path.exists(os.path.join(dest, "logos", oid + ".png"))})
    json.dump(L, open(os.path.join(dest, "outils-os.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return L


def icone_svg(dest, o):
    """Icône carrée : contour arrondi à la couleur de l'outil + logo de l'outil (ou ses initiales)."""
    c = o["couleur"]
    if o.get("logo"):
        b64 = base64.b64encode(open(os.path.join(dest, "logos", o["id"] + ".png"), "rb").read()).decode()
        inner = '<image href="data:image/png;base64,%s" x="20" y="60" width="216" height="136" preserveAspectRatio="xMidYMid meet"/>' % b64
    else:
        init = html.escape(o["nom"].split()[0][:2])
        inner = '<text x="128" y="152" font-family="IBM Plex Sans" font-weight="700" font-size="84" text-anchor="middle" fill="%s">%s</text>' % (c, init)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">'
            '<rect x="10" y="10" width="236" height="236" rx="52" fill="#16161a" stroke="%s" stroke-width="10"/>%s</svg>' % (c, inner))


def lanceurs(dest, L, dossier_apps, dossier_icones):
    os.makedirs(dossier_apps, exist_ok=True); os.makedirs(dossier_icones, exist_ok=True)
    for f in os.listdir(dossier_apps):
        if f.startswith("xiii-suite-") and f.endswith(".desktop"): os.unlink(os.path.join(dossier_apps, f))
    for o in L:
        open(os.path.join(dossier_icones, "xiii-suite-%s.svg" % o["id"]), "w").write(icone_svg(dest, o))
        mots = ";".join(sorted(set(re.findall(r"[a-zà-ÿ]{4,}", (o["nom"] + " " + o["role"]).lower()))))
        open(os.path.join(dossier_apps, "xiii-suite-%s.desktop" % o["id"]), "w").write(
            "[Desktop Entry]\nType=Application\nName=%s\nComment=%s\nKeywords=xiii;suite;%s;\nExec=xiii-suite %s\n"
            "Icon=xiii-suite-%s\nTerminal=false\nCategories=X-XIII-Suite;\nStartupWMClass=fr.xiii.suite.%s\n" % (o["nom"], o["role"] or o["description"][:120], mots, o["id"], o["id"], o["id"]))
    # accueil de la suite
    sv = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256"><rect x="10" y="10" width="236" height="236" rx="52" fill="#16161a" stroke="#f0b378" stroke-width="10"/>'
    lg = os.path.join(dest, "xiii-logo.png")
    if os.path.exists(lg):
        sv += '<image href="data:image/png;base64,%s" x="36" y="36" width="184" height="184" preserveAspectRatio="xMidYMid meet"/>' % base64.b64encode(open(lg, "rb").read()).decode()
    open(os.path.join(dossier_icones, "xiii-suite.svg"), "w").write(sv + "</svg>")
    open(os.path.join(dossier_apps, "xiii-suite-accueil.desktop"), "w").write(
        "[Desktop Entry]\nType=Application\nName=Suite XIII\nComment=Tous les outils de production audiovisuelle, hors ligne\n"
        "Keywords=xiii;suite;production;tournage;\nExec=xiii-suite index\nIcon=xiii-suite\nTerminal=false\nCategories=X-XIII-Suite;\nStartupWMClass=fr.xiii.suite.index\n")


def preparer(dest, apps=None, icones=None, source=None, journal=print):
    journal("Suite XIII : téléchargement…")
    ndi = extraire(open(source, "rb").read() if source else telecharger(DEPOT, 300), dest)
    journal("Suite XIII : bibliothèques en local…")
    miroir_cdn(dest, journal)
    L = outils(dest)
    journal("Suite XIII : %d outils" % len(L))
    if apps and icones: lanceurs(dest, L, apps, icones)
    v = hashlib.sha1(open(os.path.join(dest, "index.html"), "rb").read()).hexdigest()[:8]
    open(os.path.join(dest, "version-os.txt"), "w").write(v + "\n")
    return ndi, L


if __name__ == "__main__":
    # suite_prep.py DEST [DOSSIER_APPS DOSSIER_ICONES] [--source fichier.zip] [--ndi DEST_NDI]
    a = sys.argv[1:]
    src = a[a.index("--source") + 1] if "--source" in a else None
    ndi_dest = a[a.index("--ndi") + 1] if "--ndi" in a else None
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--source", "--ndi"))]
    ndi, L = preparer(pos[0], *(pos[1:3] if len(pos) >= 3 else (None, None)), source=src)
    if ndi_dest and ndi:
        os.makedirs(ndi_dest, exist_ok=True)
        zipfile.ZipFile(ndi).extractall(ndi_dest)
        print("Module NDI XIII extrait dans", ndi_dest)
