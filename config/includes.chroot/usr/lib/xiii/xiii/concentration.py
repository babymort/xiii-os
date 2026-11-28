# OS XIII — modes de concentration (façon macOS « Concentration » et Windows 11 « Sessions de concentration ») :
# Travail, Personnel, Sommeil, Lecture. Chaque mode laisse passer les notifications de quelques applis choisies,
# peut s'allumer tout seul à des horaires (ex. Sommeil de 23 h à 7 h), et une session minutée (25, 50, 90 min)
# coupe les notifications puis sonne à la fin. Les notifications urgentes passent toujours.
# Application développée par Matthieu Lamotte.
import time, datetime

MODES = [  # clé, nom, icône, description, réglages par défaut
    ("travail", "Travail", "briefcase", "Seules les applis de travail peuvent vous notifier",
     {"apps": ["Agenda", "Thunderbird", "Signal", "Slack", "Teams", "Horloge"], "horaires": {"on": False, "debut": "09:00", "fin": "18:00", "jours": [0, 1, 2, 3, 4]}}),
    ("personnel", "Personnel", "house", "Le travail se tait : messageries personnelles seulement",
     {"apps": ["Signal", "WhatsApp", "Telegram", "Horloge"], "horaires": {"on": False, "debut": "19:00", "fin": "23:00", "jours": [0, 1, 2, 3, 4, 5, 6]}}),
    ("sommeil", "Sommeil", "moon", "Tout se tait sauf les alarmes ; lumière nocturne",
     {"apps": ["Horloge"], "nuit": True, "horaires": {"on": False, "debut": "23:00", "fin": "07:00", "jours": [0, 1, 2, 3, 4, 5, 6]}}),
    ("lecture", "Lecture", "book-open", "Aucune notification, rien ne bouge",
     {"apps": ["Horloge"], "horaires": {"on": False, "debut": "21:00", "fin": "22:00", "jours": [5, 6]}}),
]
PAR_CLE = {m[0]: m for m in MODES}


def reglages(cfg, cle):
    d = dict(PAR_CLE[cle][4]); d.update((cfg.get("concentration_modes") or {}).get(cle, {}))
    return d


def _minutes(hhmm):
    try: h, m = hhmm.split(":"); return int(h) * 60 + int(m)
    except Exception: return 0


def dans_horaires(h, n):
    """h = {"on", "debut", "fin", "jours"} ; plage qui peut passer minuit (23:00 → 07:00 : le jour est celui du début)."""
    if not h.get("on"): return False
    d, f, x = _minutes(h["debut"]), _minutes(h["fin"]), n.hour * 60 + n.minute
    jours = h.get("jours") or list(range(7))
    if d <= f: return d <= x < f and n.weekday() in jours
    if x >= d: return n.weekday() in jours
    if x < f: return (n.weekday() - 1) % 7 in jours
    return False


def actif(cfg, n=None):
    """Mode de concentration en cours : (clé, raison) ou None. Manuel > session minutée > horaires."""
    n = n or datetime.datetime.now()
    c = cfg.get("concentration")
    fin = cfg.get("concentration_fin") or 0
    if c in PAR_CLE:
        if fin and time.time() >= fin: return None
        return c, ("session, encore %d min" % max(1, round((fin - time.time()) / 60))) if fin else "activé"
    for k, *_ in MODES:
        if dans_horaires(reglages(cfg, k).get("horaires", {}), n) and k not in (cfg.get("concentration_saute") or []): return k, "horaires"
    return None


def laisse_passer(cfg, app, urgence=1):
    a = actif(cfg)
    if not a or urgence >= 2: return True
    autorisees = [x.lower() for x in reglages(cfg, a[0]).get("apps", [])]
    return (app or "").lower() in autorisees


def nom(cle): return PAR_CLE[cle][1] if cle in PAR_CLE else ""
def icone(cle): return PAR_CLE[cle][2] if cle in PAR_CLE else "focus"
