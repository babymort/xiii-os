# OS XIII — sons système (thème « XIII », synthétisés) : ouverture de session, notification, erreur,
# clé branchée / retirée, capture, batterie faible. Réglage : Paramètres › Son › Sons système.
import os, shutil, subprocess, time
from . import config

DOSSIER = "/usr/share/sounds/XIII/stereo"
_dernier = {}

def jouer(nom, cfg=None, force=False):
    cfg = cfg or config.charger()
    if not force and (not cfg.get("sons_systeme", True) or cfg.get("ne_pas_deranger")): return
    if not force and time.time() - _dernier.get(nom, 0) < 0.8: return       # pas de rafale (plusieurs notifications d'un coup)
    _dernier[nom] = time.time()
    f = os.path.join(DOSSIER, nom + ".wav")
    if not os.path.exists(f): return
    vol = max(0.05, min(1.0, float(cfg.get("sons_volume", 70)) / 100))
    for cmd in (["pw-play", "--volume", "%.2f" % vol, f], ["paplay", "--volume", str(int(65536 * vol)), f], ["aplay", "-q", f]):
        if shutil.which(cmd[0]):
            try: subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError: continue
            return

def pour_notification(app, icone, titre, hints):
    """Son d'une notification reçue (respecte « suppress-sound » et « sound-name »)."""
    if hints.get("suppress-sound"): return
    s = hints.get("sound-name")
    if isinstance(s, str) and os.path.exists(os.path.join(DOSSIER, s + ".wav")): return jouer(s)
    a, i, t = (app or "").lower(), (icone or "").lower(), (titre or "").lower()
    if a == "disques": return                                  # le branchement a déjà son propre son
    if a == "capture": return jouer("screen-capture")
    if "batterie" in t and ("faible" in t or "critique" in t): return jouer("battery-low")
    if "error" in i or "erreur" in t or "impossible" in t or "échec" in t: return jouer("dialog-error")
    if hints.get("urgency") == 2 or "warning" in i: return jouer("dialog-warning")
    if "terminé" in t or "installé" in t or "fini" in t: return jouer("complete")
    jouer("message-new-instant")
