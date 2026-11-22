# OS XIII — fiabilité : santé des disques (SMART via UDisks, sans droits administrateur),
# annonces après un retour arrière ou en mode sans échec, et journal « Ce qui s'est passé ».
import os, re, json, time, datetime, subprocess, glob
from gi.repository import Gio, GLib

ETAT = os.path.join(GLib.get_user_state_dir(), "xiii"); os.makedirs(ETAT, exist_ok=True)
EV = "/var/log/xiii/evenements.log"

def _notif(titre, corps, icone="dialog-information", actions=(), rappel=None):
    cmd = ["notify-send", "-a", "OS XIII", "-i", icone] + ["--action=%s=%s" % a for a in actions] + [titre, corps]
    if not actions: subprocess.Popen(cmd); return
    def t():
        try: r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600).stdout.strip()
        except Exception: return
        if r and rappel: GLib.idle_add(lambda: (rappel(r), False)[1])
    import threading; threading.Thread(target=t, daemon=True).start()

# ------------------------------------------------------------------ santé des disques
def sante_disques():
    """[{nom, modele, etat: bon|attention|critique|inconnu, detail, temperature}] pour chaque disque interne."""
    out = []
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
        r = bus.call_sync("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
                          None, GLib.VariantType("(a{oa{sa{sv}}})"), 0, 8000, None).unpack()[0]
    except Exception:
        return out
    for chemin, ifs in r.items():
        dr = ifs.get("org.freedesktop.UDisks2.Drive")
        if not dr or dr.get("Removable") or dr.get("Ejectable") or dr.get("Size", 0) == 0: continue
        nom = (dr.get("Vendor", "") + " " + dr.get("Model", "")).strip() or "Disque"
        taille = dr.get("Size", 0) / 1e9
        d = {"nom": nom, "taille": "%.0f Go" % taille, "etat": "inconnu", "detail": "Ce disque ne donne pas son état de santé", "temperature": None, "heures": None}
        ata = ifs.get("org.freedesktop.UDisks2.Drive.Ata")
        nvme = ifs.get("org.freedesktop.UDisks2.NVMe.Controller")
        if ata and ata.get("SmartSupported") and ata.get("SmartEnabled"):
            mauvais = ata.get("SmartNumBadSectors", 0) or 0; t = ata.get("SmartTemperature", 0) or 0
            d["temperature"] = round(t - 273.15) if t > 200 else None
            d["heures"] = int((ata.get("SmartPowerOnSeconds", 0) or 0) / 3600)
            if ata.get("SmartFailing"):
                d.update(etat="critique", detail="Le disque annonce une panne prochaine : sauvegardez vos fichiers dès maintenant")
            elif mauvais > 0 or (ata.get("SmartNumAttributesFailing", 0) or 0) > 0:
                d.update(etat="attention", detail="%d secteur(s) abîmé(s) : le disque commence à fatiguer, pensez à sauvegarder" % mauvais if mauvais else "Certains indicateurs sont dans le rouge")
            else:
                d.update(etat="bon", detail="Aucun problème détecté")
        elif nvme:
            warn = nvme.get("SmartCriticalWarning", []) or []
            t = nvme.get("SmartTemperature", 0) or 0
            d["temperature"] = round(t - 273.15) if t > 200 else None
            d["heures"] = nvme.get("SmartPowerOnHours")
            if warn:
                fr = {"spare": "réserve épuisée", "temperature": "trop chaud", "degraded": "usure avancée", "readonly": "passé en lecture seule", "volatile_mem": "mémoire de secours défaillante"}
                d.update(etat="critique" if {"degraded", "readonly"} & set(warn) else "attention", detail="Alerte : " + ", ".join(fr.get(w, w) for w in warn))
            else:
                d.update(etat="bon", detail="Aucun problème détecté")
        out.append(d)
    return out

def verifier_sante(force=False):
    """Vérification hebdomadaire ; notification seulement si un disque fatigue (et pas plus d'une fois par semaine)."""
    f = os.path.join(ETAT, "sante-disques.json")
    try: prec = json.load(open(f))
    except Exception: prec = {}
    if not force and time.time() - prec.get("t", 0) < 6 * 86400: return
    L = sante_disques()
    json.dump({"t": time.time(), "disques": L}, open(f, "w"), ensure_ascii=False)
    mal = [d for d in L if d["etat"] in ("attention", "critique")]
    if mal:
        d = mal[0]
        _journal_local("disque", "%s : %s" % (d["nom"], d["detail"]))
        _notif("Le disque « %s » fatigue" % d["nom"] if d["etat"] == "attention" else "Disque « %s » en danger" % d["nom"], d["detail"],
               "drive-harddisk", (("sauver", "Sauvegarder maintenant"), ("voir", "Voir les détails")),
               lambda r: subprocess.Popen(["xiii-transferts"] if r == "sauver" else ["xiii-parametres", "--page", "evenements"]))

def _journal_local(typ, msg):
    with open(os.path.join(ETAT, "evenements.log"), "a") as o: o.write("%s|%s|%s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), typ, msg))

# ------------------------------------------------------------------ annonces de démarrage
def au_demarrage():
    # retour arrière effectué (automatique ou depuis le menu de démarrage)
    f = "/var/lib/xiii/restauration-a-annoncer.txt"
    try:
        txt = open(f).read().strip(); vu = os.path.join(ETAT, "restauration-vue")
        if txt and (not os.path.exists(vu) or open(vu).read() != txt):
            open(vu, "w").write(txt)
            n, mode, _ = (txt.split("|") + ["", "", ""])[:3]
            if mode == "auto":
                _notif("OS XIII est revenu en arrière", "Le système ne démarrait plus après une installation : il a été ramené automatiquement au dernier état qui marchait (instantané n°%s). Vos fichiers n'ont pas changé." % n,
                       "edit-undo", (("voir", "Voir ce qui s'est passé"),), lambda r: subprocess.Popen(["xiii-parametres", "--page", "evenements"]))
            else:
                _notif("Retour arrière terminé", "Le système a été ramené à l'instantané n°%s. Vos fichiers n'ont pas changé." % n, "edit-undo")
    except OSError: pass
    if os.environ.get("XIII_SANS_ECHEC"):
        _notif("Mode sans échec graphique", "Affichage de base sans accélération. Si le mode normal ne démarre pas, essayez « Réparer OS XIII » ou mettez à jour les pilotes graphiques dans Paramètres.",
               "dialog-warning", (("pilotes", "Vérifier les pilotes"),), lambda r: subprocess.Popen(["xiii-bilan"]))
    GLib.timeout_add_seconds(600, lambda: (verifier_sante(), False)[1])
    return False

# ------------------------------------------------------------------ journal « Ce qui s'est passé »
TYPES = {
    "demarrage": ("power", "Démarrage"), "echec": ("circle-alert", "Démarrage raté"), "arret": ("zap-off", "Arrêt brutal"),
    "restauration": ("history", "Retour arrière"), "instantane": ("camera", "Instantané"), "nettoyage": ("trash-2", "Nettoyage"),
    "reparation": ("wrench", "Réparation"), "maj": ("download", "Mise à jour d'OS XIII"), "logiciel": ("package", "Logiciels"),
    "plantage": ("bug", "Plantage d'application"), "disque": ("hard-drive", "Santé du disque"),
}

def _apt(depuis):
    out = []
    try: txt = open("/var/log/apt/history.log", errors="replace").read()
    except OSError: return out
    for bloc in txt.split("\n\n"):
        m = re.search(r"Start-Date: (\S+ \S+)", bloc)
        if not m: continue
        try: d = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError: continue
        if d < depuis: continue
        parts = []
        for cle, mot in (("Install", "installé"), ("Upgrade", "mis à jour"), ("Remove", "retiré"), ("Purge", "retiré")):
            mm = re.search(r"^%s: (.*)$" % cle, bloc, re.M)
            if mm:
                noms = [x.split(":")[0] for x in re.findall(r"([^\s,(]+) \(", mm.group(1))]
                if noms: parts.append("%d %s%s (%s%s)" % (len(noms), mot, "s" if len(noms) > 1 else "", ", ".join(noms[:4]), "…" if len(noms) > 4 else ""))
        if parts: out.append((d, "logiciel", " ; ".join(parts)))
    return out

def _log(chemin, depuis):
    out = []
    try:
        for l in open(chemin, errors="replace"):
            p = l.rstrip("\n").split("|", 2)
            if len(p) < 3: continue
            try: d = datetime.datetime.fromisoformat(p[0]).replace(tzinfo=None)
            except ValueError: continue
            if d >= depuis: out.append((d, p[1], p[2]))
    except OSError: pass
    return out

def _demarrages(depuis):
    out = []
    try:
        r = subprocess.run(["journalctl", "--list-boots", "-q", "--no-pager"], capture_output=True, text=True, timeout=6).stdout
        for l in r.splitlines()[-40:]:
            m = re.search(r"\w{3} (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", l)
            if m:
                d = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                if d >= depuis: out.append((d, "demarrage", "Ordinateur démarré"))
    except Exception: pass
    return out

def evenements(jours=30):
    from . import rapport
    depuis = datetime.datetime.now() - datetime.timedelta(days=jours)
    L = _log(EV, depuis) + _log(os.path.join(ETAT, "evenements.log"), depuis) + _apt(depuis) + _demarrages(depuis)
    L += [(d, "plantage", "%s s'est arrêtée sur une erreur — rapport : %s" % (app.replace("xiii-", "").capitalize(), os.path.basename(f))) for d, app, f in rapport.liste() if d >= depuis]
    return sorted(L, key=lambda e: e[0], reverse=True)
