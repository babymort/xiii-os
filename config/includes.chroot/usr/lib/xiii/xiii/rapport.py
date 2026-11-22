# OS XIII — rapport de plantage en un clic.
# Toute erreur Python non rattrapée dans une application XIII écrit un rapport lisible dans ~/Rapports XIII/
# (erreur, version d'OS XIII, mémoire, dernières lignes des journaux) et affiche une notification
# « Voir le rapport / Ouvrir le dossier ». Une notification par application et par minute au plus.
import os, sys, time, datetime, traceback, subprocess, threading

DOSSIER = os.path.join(os.path.expanduser("~"), "Rapports XIII")
_dernier = [0.0]

def _app():
    a = os.path.basename(sys.argv[0] or "xiii") if sys.argv else "xiii"
    return a if a not in ("-c", "python3", "") else "xiii"

def _lire(chemin, n=40):
    try:
        with open(chemin, errors="replace") as f: return "".join(f.readlines()[-n:])
    except OSError: return "(absent)\n"

def _cmd(c, t=4):
    try: return subprocess.run(c, capture_output=True, text=True, timeout=t).stdout
    except Exception: return "(indisponible)\n"

def ecrire(typ, val, tb, contexte=""):
    os.makedirs(DOSSIER, exist_ok=True)
    app = _app(); h = datetime.datetime.now()
    f = os.path.join(DOSSIER, "%s_%s.txt" % (h.strftime("%Y-%m-%d_%H%M%S"), app))
    erreur = "".join(traceback.format_exception(typ, val, tb))
    vers = _lire("/etc/xiii/version.json", 20) if os.path.exists("/etc/xiii/version.json") else _lire("/etc/os-release", 10)
    with open(f, "w") as o:
        o.write("RAPPORT DE PLANTAGE — OS XIII\n%s\n\n" % ("=" * 40))
        o.write("Application : %s\nDate : %s\nCommande : %s\n%s\n" % (app, h.strftime("%d/%m/%Y %H:%M:%S"), " ".join(sys.argv), contexte))
        o.write("\n— Ce qui s'est passé —\n%s: %s\n" % (typ.__name__, val))
        o.write("\n— Détail technique —\n%s\n" % erreur)
        o.write("— Version —\n%s\nÉdition : %s\n" % (vers.strip(), _lire("/etc/xiii/edition", 1).strip()))
        o.write("\n— Mémoire —\n%s" % _cmd(["free", "-h"]))
        o.write("\n— Carte graphique —\nGSK_RENDERER=%s WLR_RENDERER=%s\n" % (os.environ.get("GSK_RENDERER", ""), os.environ.get("WLR_RENDERER", "")))
        o.write("\n— Journal du bureau (fin) —\n%s" % _lire(os.path.expanduser("~/.cache/xiii/bureau.log"), 30))
        o.write("\n— Journal de session (fin) —\n%s" % _cmd(["journalctl", "--user", "-n", "30", "--no-pager", "-o", "short"]))
    return f

def _notifier(f):
    if time.time() - _dernier[0] < 60: return
    _dernier[0] = time.time()
    app = _app().replace("xiii-", "").capitalize()
    try: subprocess.Popen(["/usr/local/lib/xiii/rapport-notif", f, app], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

def _crochet(typ, val, tb):
    sys.__excepthook__(typ, val, tb)       # toujours affiché dans le terminal / les journaux
    if issubclass(typ, KeyboardInterrupt): return
    try: _notifier(ecrire(typ, val, tb))
    except Exception: pass

def installer():
    if getattr(sys, "_xiii_rapport", False) or os.environ.get("XIII_SANS_RAPPORT"): return
    sys._xiii_rapport = True
    sys.excepthook = _crochet
    threading.excepthook = lambda a: _crochet(a.exc_type, a.exc_value, a.exc_traceback)

def liste(n=50):
    try: L = sorted((x for x in os.listdir(DOSSIER) if x.endswith(".txt")), reverse=True)[:n]
    except OSError: return []
    out = []
    for x in L:
        try: d = datetime.datetime.strptime(x[:17], "%Y-%m-%d_%H%M%S")
        except ValueError: continue
        out.append((d, x[18:-4], os.path.join(DOSSIER, x)))
    return out
