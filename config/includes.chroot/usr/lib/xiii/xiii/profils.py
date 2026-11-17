# OS XIII — profils de travail : un clic règle silence, performances, mise en veille…
# Application développée par Matthieu Lamotte.
PROFILS = [  # clé, nom, icône, description, réglages
    ("normal", "Normal", "monitor", "Réglages habituels", dict(dnd=False, perf="balanced", eveil=False)),
    ("tournage", "Tournage", "clapperboard", "Performances max, silence, jamais de veille", dict(dnd=True, perf="performance", eveil=True)),
    ("montage", "Montage", "film", "Performances max, silence ; la veille reste active", dict(dnd=True, perf="performance", eveil=False)),
    ("voyage", "Voyage", "luggage", "Économie d'énergie, lumière nocturne", dict(dnd=False, perf="power-saver", eveil=False, nuit=True)),
    ("presentation", "Présentation", "presentation", "Silence et écran toujours allumé", dict(dnd=True, perf="balanced", eveil=True)),
    ("jeu", "Jeu", "gamepad-2", "Performances max, silence, éveil ; Steam en mode console si activé", dict(dnd=True, perf="performance", eveil=True, jeu=True)),
]
PAR_CLE = {p[0]: p for p in PROFILS}

def courant(cfg):
    p = cfg.get("profil", "normal")
    if cfg.get("mode_tournage") and p == "normal": p = "tournage"
    return PAR_CLE.get(p, PROFILS[0])

def eveil(cfg):
    return courant(cfg)[4].get("eveil", False)
