# OS XIII — serveur MCP (Model Context Protocol) : relie Claude Desktop et Claude Code à l'OS.
# Claude peut lire l'état du PC, le projet XIII actif, les fichiers de la Suite XIII, voir l'écran,
# appliquer un profil de travail, changer le thème, envoyer une notification, ouvrir une app ou un dossier.
# Transport stdio (JSON-RPC 2.0, un message par ligne). Aucune dépendance hors Python + PyGObject.
# Application développée par Matthieu Lamotte.
import sys, os, json, glob, time, base64, shutil, subprocess, platform, re, tempfile

sys.path.insert(0, "/usr/lib/xiii")
from xiii import config, profils

VERSION = "1.0"
PROTOCOLES = ("2025-06-18", "2025-03-26", "2024-11-05")
SOUS = ["01_Rushes", "02_Son", "03_Documents", "04_Graphismes", "05_Montage", "06_Exports", "07_Livraison"]
REGLABLES = {  # clé : (type, description)
    "theme": (["sombre", "clair", "sobre"], "Thème du bureau"),
    "accent": ("couleur", "Couleur d'accent, ex. #f0b378"),
    "ne_pas_deranger": (bool, "Ne pas déranger"),
    "lumiere_nocturne": (bool, "Lumière nocturne"),
    "timecode": (bool, "Horloge timecode dans la barre du haut"),
    "timecode_fps": ([24, 25, 30, 50, 60], "Images par seconde du timecode"),
    "transparence": (bool, "Effets de transparence"),
    "animations": (bool, "Animations"),
    "veille_mode": (["horloge", "mire", "conducteur"], "Écran de veille"),
}


def sh(cmd, t=8):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout.strip()
    except Exception:
        return ""


def lire(f, d=""):
    try:
        return open(f).read().strip()
    except OSError:
        return d


# ------------------------------------------------------------------ outils
def etat_systeme(_):
    mem = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo") if l.split(":")[0] in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}
    la = os.getloadavg()
    cpu = re.search(r"model name\s*:\s*(.+)", lire("/proc/cpuinfo"))
    h = os.path.expanduser("~"); du = shutil.disk_usage(h if os.path.isdir(h) else "/")
    temps = []
    for z in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try: temps.append(int(lire(z, "0")) / 1000)
        except ValueError: pass
    bat = None
    for b in glob.glob("/sys/class/power_supply/BAT*"):
        bat = {"pourcentage": lire(b + "/capacity"), "etat": lire(b + "/status")}
    reseau = sh(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"]).splitlines()
    ips = sh(["ip", "-brief", "-4", "address"]).splitlines()
    gpu = [l.split(": ", 1)[-1] for l in sh(["lspci"]).splitlines() if re.search(r"VGA|3D|Display", l)]
    up = float(lire("/proc/uptime", "0").split()[0])
    os_rel = dict(l.split("=", 1) for l in lire("/etc/os-release").splitlines() if "=" in l)
    return {
        "systeme": os_rel.get("PRETTY_NAME", "OS XIII").strip('"'), "noyau": platform.release(),
        "processeur": cpu.group(1) if cpu else platform.processor(), "coeurs": os.cpu_count(),
        "charge_1_5_15min": [round(x, 2) for x in la],
        "memoire_go": {"totale": round(mem["MemTotal"] / 1048576, 1), "disponible": round(mem["MemAvailable"] / 1048576, 1),
                       "swap_libre": round(mem.get("SwapFree", 0) / 1048576, 1)},
        "disque_personnel_go": {"total": round(du.total / 1e9, 1), "libre": round(du.free / 1e9, 1)},
        "temperature_max_c": max(temps) if temps else None, "batterie": bat, "carte_graphique": gpu,
        "reseau": [r.replace(":", " · ") for r in reseau if r], "adresses_ip": ips,
        "allume_depuis": "%d h %02d min" % (up // 3600, up % 3600 // 60),
    }


def reglages(_):
    c = config.charger()
    p = profils.courant(c)
    return {"profil": {"cle": p[0], "nom": p[1], "description": p[3]},
            "profils_disponibles": [{"cle": k, "nom": n, "description": d} for k, n, _, d, _ in profils.PROFILS],
            "projet_actif": c.get("projet_actif") or None,
            "reglages": {k: c.get(k) for k in REGLABLES}}


def appliquer_profil(a):
    k = a.get("profil", "")
    if k not in profils.PAR_CLE:
        raise ValueError("Profil inconnu. Choix : " + ", ".join(profils.PAR_CLE))
    config.modifier(profil=k, mode_tournage=(k == "tournage"))
    return "Profil « %s » appliqué : %s." % (profils.PAR_CLE[k][1], profils.PAR_CLE[k][3])


def regler(a):
    k, v = a.get("cle"), a.get("valeur")
    if k not in REGLABLES:
        raise ValueError("Réglage non modifiable par Claude. Choix : " + ", ".join(REGLABLES))
    t = REGLABLES[k][0]
    if t is bool:
        if isinstance(v, str): v = v.lower() in ("1", "true", "oui", "on", "vrai")
        v = bool(v)
    elif t == "couleur":
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)): raise ValueError("Couleur attendue au format #rrggbb")
    elif isinstance(t, list):
        if isinstance(t[0], int): v = int(v)
        if v not in t: raise ValueError("Valeurs possibles : %s" % t)
    config.modifier(**{k: v})
    return "%s → %s (annulable dans Paramètres › Historique des réglages)." % (REGLABLES[k][1], v)


def projet(_):
    c = config.charger(); nom = c.get("projet_actif")
    if not nom:
        return {"projet_actif": None, "conseil": "Aucun projet actif : il se crée dans Paramètres › Projet XIII."}
    d = os.path.join(os.path.expanduser("~/XIII"), nom)
    dossiers = {}
    for s in SOUS:
        p = os.path.join(d, s); n = 0; taille = 0
        for r, _, fs in os.walk(p):
            for f in fs:
                n += 1
                try: taille += os.path.getsize(os.path.join(r, f))
                except OSError: pass
        dossiers[s] = {"fichiers": n, "taille_mo": round(taille / 1e6, 1)}
    recents = sorted(glob.glob(os.path.join(d, "**", "*"), recursive=True), key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0, reverse=True)
    return {"projet_actif": nom, "chemin": d, "dossiers": dossiers,
            "fichiers_recents": [os.path.relpath(f, d) for f in recents if os.path.isfile(f)][:15]}


def dossiers_xiii():
    L = [os.path.expanduser(x) for x in ("~/XIII", "~/Téléchargements", "~/Downloads", "~/Documents", "~/Bureau", "~/Desktop")]
    return [p for p in L if os.path.isdir(p)]


def suite_xiii(a):
    kind = a.get("type", "project")
    if kind not in ("project", "rundown", "workplan"):
        raise ValueError("type : project (fiche projet), rundown (conducteur) ou workplan (plan de travail)")
    fichiers = []
    for d in dossiers_xiii():
        fichiers += glob.glob(os.path.join(d, "**", "*.xiii.json"), recursive=True)[:300] + glob.glob(os.path.join(d, "*.json"))[:100]
    for f in sorted(set(fichiers), key=os.path.getmtime, reverse=True):
        try:
            o = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(o, dict) and o.get("format") == "xiii-link" and o.get("kind") == kind:
            o["_fichier"] = f
            texte = json.dumps(o, ensure_ascii=False)
            return texte if len(texte) < 60000 else texte[:60000] + "… (tronqué)"
    return "Aucun fichier %s.xiii.json trouvé (exportez-le depuis la Suite XIII dans ~/XIII, Téléchargements ou Documents)." % kind


def capture(a):
    if not shutil.which("grim"):
        raise RuntimeError("grim est absent")
    f = tempfile.mktemp(suffix=".png", prefix="xiii-claude-")
    echelle = "0.5" if a.get("reduite", True) else "1"
    subprocess.run(["grim", "-s", echelle, f], check=True, timeout=10)
    data = base64.b64encode(open(f, "rb").read()).decode()
    os.unlink(f)
    return [{"type": "image", "data": data, "mimeType": "image/png"},
            {"type": "text", "text": "Capture de l'écran prise à %s." % time.strftime("%H:%M:%S")}]


def notifier(a):
    titre = str(a.get("titre", "Claude"))[:120]; msg = str(a.get("message", ""))[:800]
    subprocess.Popen(["notify-send", "-a", "Claude", "-i", "claude-desktop", titre, msg])
    return "Notification affichée."


def ouvrir(a):
    cible = str(a.get("cible", "")).strip()
    if not cible:
        raise ValueError("cible vide")
    if not re.match(r"^(https?|mailto):", cible):
        cible = os.path.expanduser(cible)
        if not os.path.exists(cible):
            raise ValueError("Chemin introuvable : " + cible)
    subprocess.Popen(["xdg-open", cible], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return "Ouvert : " + cible


def applications(a):
    q = (a.get("recherche") or "").lower()
    res = []
    for d in ("/usr/share/applications", os.path.expanduser("~/.local/share/applications")):
        for f in glob.glob(d + "/*.desktop"):
            t = lire(f)
            if re.search(r"^NoDisplay=true", t, re.M): continue
            n = re.search(r"^Name\[fr\]=(.+)$", t, re.M) or re.search(r"^Name=(.+)$", t, re.M)
            if not n: continue
            if q and q not in n.group(1).lower() and q not in os.path.basename(f).lower(): continue
            res.append({"nom": n.group(1), "id": os.path.basename(f)})
    return sorted(res, key=lambda x: x["nom"].lower())[:60]


def lancer(a):
    i = str(a.get("id", ""))
    if not re.fullmatch(r"[\w.\-]+\.desktop", i):
        raise ValueError("id attendu : nom de fichier .desktop (voir l'outil applications)")
    subprocess.Popen(["gtk-launch", i], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return "Lancé : " + i


def ouvrir_panneau(a):
    p = a.get("panneau", "")
    ok = ["demarrer", "centre", "volet", "son", "wifi", "bluetooth", "batterie", "widgets", "vue", "bureau"]
    if p not in ok: raise ValueError("Panneaux : " + ", ".join(ok))
    subprocess.run(["xiii-ctl", p], timeout=5)
    return "Panneau ouvert : " + p


def ouvrir_parametres(a):
    page = re.sub(r"[^a-z0-9_]", "", str(a.get("page", "")).lower())
    subprocess.Popen(["xiii-parametres"] + ([page] if page else []), start_new_session=True)
    return "Paramètres ouverts" + (" sur la page " + page if page else "")


def outils_suite(_):
    try:
        L = json.load(open(next(p for p in (os.path.expanduser("~/.local/share/xiii/suite/outils-os.json"), "/usr/share/xiii/suite/outils-os.json") if os.path.exists(p)), encoding="utf-8"))
    except Exception:
        return []
    return [{"id": o["id"], "nom": o["nom"], "role": o["role"]} for o in L]


def ouvrir_outil(a):
    oid = re.sub(r"[^a-z0-9_-]", "", str(a.get("id", "")).lower())
    if not oid: raise ValueError("id d'outil attendu (voir outils_suite_xiii)")
    f = a.get("fichier")
    cmd = ["xiii-suite", "--ouvrir", os.path.expanduser(f)] if f else ["xiii-suite", oid]
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "Ouvert : " + (f or oid)


def tally_etat(_):
    import urllib.request
    try:
        return json.loads(urllib.request.urlopen("http://127.0.0.1:8790/api/etat", timeout=2).read())
    except Exception:
        return "Tally XIII n'est pas lancé (menu Démarrer › Suite XIII › Tally XIII)."


def tally_forcer(a):
    import urllib.request, urllib.parse
    q = urllib.parse.urlencode({"cam": int(a.get("camera")), "etat": a.get("etat", "auto")})
    return urllib.request.urlopen("http://127.0.0.1:8790/api/forcer?" + q, timeout=2).read().decode()


O = lambda **p: {"type": "object", "properties": p, "additionalProperties": False}
OUTILS = [
    ("etat_systeme", "État du PC sous OS XIII : processeur, charge, mémoire, disque, température, batterie, carte graphique, réseau et adresses IP.", O(), etat_systeme, True),
    ("reglages", "Profil de travail actif (Normal, Tournage, Montage, Voyage, Présentation, Jeu), projet XIII actif et principaux réglages du bureau.", O(), reglages, True),
    ("appliquer_profil", "Applique un profil de travail OS XIII (règle silence, performances, mise en veille…).",
     dict(O(profil={"type": "string", "enum": [p[0] for p in profils.PROFILS]}), required=["profil"]), appliquer_profil, False),
    ("regler", "Modifie un réglage du bureau OS XIII. Clés : " + "; ".join("%s (%s)" % (k, v[1]) for k, v in REGLABLES.items()),
     dict(O(cle={"type": "string", "enum": list(REGLABLES)}, valeur={"type": ["string", "boolean", "integer"]}), required=["cle", "valeur"]), regler, False),
    ("projet_actif", "Projet XIII actif : dossiers 01_Rushes → 07_Livraison, nombre de fichiers, tailles, fichiers récents.", O(), projet, True),
    ("suite_xiii", "Lit le dernier fichier exporté par la Suite XIII : fiche projet (project), conducteur CONDUCO (rundown) ou plan de travail DECOUP (workplan).",
     O(type={"type": "string", "enum": ["project", "rundown", "workplan"]}), suite_xiii, True),
    ("outils_suite_xiii", "Liste des outils de la Suite XIII installés hors ligne (CONDUCO, SYNO, PLANO, CALL SHEETO, DOSSIER, ENCODO, MELANGO…).", O(), outils_suite, True),
    ("ouvrir_outil_xiii", "Ouvre un outil de la Suite XIII dans sa fenêtre, ou un fichier .xiii.json dans le bon outil.",
     O(id={"type": "string"}, fichier={"type": "string"}), ouvrir_outil, False),
    ("tally_etat", "État de TALLY XIII : chaque caméra (antenne, preview, repos), son nom, les téléphones connectés et les mélangeurs suivis.", O(), tally_etat, True),
    ("tally_forcer", "Force le tally d'une caméra (programme, preview, repos) ou rend la main au mélangeur (auto).",
     dict(O(camera={"type": "integer"}, etat={"type": "string", "enum": ["programme", "preview", "repos", "auto"]}), required=["camera", "etat"]), tally_forcer, False),
    ("capture_ecran", "Prend une capture de l'écran pour voir ce qui est affiché (réduite de moitié par défaut).", O(reduite={"type": "boolean"}), capture, True),
    ("notifier", "Affiche une notification sur le bureau.", dict(O(titre={"type": "string"}, message={"type": "string"}), required=["message"]), notifier, False),
    ("ouvrir", "Ouvre un fichier, un dossier ou une adresse web avec l'application par défaut.", dict(O(cible={"type": "string"}), required=["cible"]), ouvrir, False),
    ("applications", "Liste les applications installées (filtrables par nom).", O(recherche={"type": "string"}), applications, True),
    ("lancer_application", "Lance une application à partir de son id .desktop (voir l'outil applications).", dict(O(id={"type": "string"}), required=["id"]), lancer, False),
    ("ouvrir_panneau", "Ouvre un panneau du bureau XIII (menu Démarrer, centre de contrôle, notifications, son, Wi-Fi, Bluetooth, widgets, vue des tâches, bureau).",
     dict(O(panneau={"type": "string"}), required=["panneau"]), ouvrir_panneau, False),
    ("ouvrir_parametres", "Ouvre l'application Paramètres, éventuellement sur une page (ex. wifi, son, ecran, profils, projet, jeux, claude).", O(page={"type": "string"}), ouvrir_parametres, False),
]
PAR_NOM = {o[0]: o for o in OUTILS}


# ------------------------------------------------------------------ protocole
def repondre(i, result=None, error=None):
    m = {"jsonrpc": "2.0", "id": i}
    if error: m["error"] = error
    else: m["result"] = result
    sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n"); sys.stdout.flush()


def traiter(msg):
    meth, i, p = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if i is None:  # notification
        return
    if meth == "initialize":
        v = p.get("protocolVersion")
        repondre(i, {"protocolVersion": v if v in PROTOCOLES else PROTOCOLES[0], "capabilities": {"tools": {"listChanged": False}},
                     "serverInfo": {"name": "os-xiii", "title": "OS XIII", "version": VERSION},
                     "instructions": "Outils du système OS XIII (Linux pour la production audiovisuelle, Suite XIII). Réponds en français."})
    elif meth == "ping":
        repondre(i, {})
    elif meth == "tools/list":
        repondre(i, {"tools": [{"name": n, "description": d, "inputSchema": s, "annotations": {"readOnlyHint": ro}} for n, d, s, _, ro in OUTILS]})
    elif meth == "tools/call":
        o = PAR_NOM.get(p.get("name"))
        if not o:
            return repondre(i, error={"code": -32602, "message": "Outil inconnu : %s" % p.get("name")})
        try:
            r = o[3](p.get("arguments") or {})
            contenu = r if isinstance(r, list) else [{"type": "text", "text": r if isinstance(r, str) else json.dumps(r, ensure_ascii=False, indent=1)}]
            repondre(i, {"content": contenu, "isError": False})
        except Exception as e:
            repondre(i, {"content": [{"type": "text", "text": "Erreur : %s" % e}], "isError": True})
    elif meth in ("resources/list", "prompts/list"):
        repondre(i, {meth.split("/")[0]: []})
    else:
        repondre(i, error={"code": -32601, "message": "Méthode non prise en charge : %s" % meth})


def main():
    for ligne in sys.stdin:
        ligne = ligne.strip()
        if not ligne: continue
        try:
            msg = json.loads(ligne)
        except ValueError:
            repondre(None, error={"code": -32700, "message": "JSON invalide"}); continue
        for m in (msg if isinstance(msg, list) else [msg]):
            try:
                traiter(m)
            except Exception as e:
                repondre(m.get("id"), error={"code": -32603, "message": str(e)})


if __name__ == "__main__":
    main()
