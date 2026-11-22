# OS XIII — tous les raccourcis clavier du système, modifiables
#   Source unique : ~/.config/labwc/rc.xml (<keyboard><keybind>).
#   Les raccourcis par défaut de labwc (<default/>) sont rendus explicites pour pouvoir être changés eux aussi.
#   ~/.config/xiii/raccourcis-retires.json garde les raccourcis d'origine que l'utilisateur a supprimés ou déplacés,
#   pour que les mises à jour ne les remettent pas.
import os, json, shutil, copy
import xml.etree.ElementTree as ET
import gi
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk

RC = os.path.join(GLib.get_user_config_dir(), "labwc", "rc.xml")
SKEL = "/etc/skel/.config/labwc/rc.xml"
RETIRES = os.path.join(GLib.get_user_config_dir(), "xiii", "raccourcis-retires.json")

# raccourcis intégrés de labwc quand <default/> est présent (ceux qu'XIII ne redéfinit pas)
DEFAUTS_LABWC = [
    ("A-Tab", [("NextWindow", {})]),
    ("A-S-Tab", [("PreviousWindow", {})]),
    ("A-space", [("ShowMenu", {"menu": "client-menu"})]),
    ("W-a", [("ToggleMaximize", {})]),
    ("A-F4", [("Close", {})]),
    ("W-Up", [("ToggleMaximize", {})]),
]

# ------------------------------------------------------------------ noms lisibles
CATEGORIES = ["Système et bureau", "Fenêtres", "Bureaux virtuels", "Ancrage et dispositions", "Applications", "Captures", "Son et luminosité", "Personnalisés"]

COMMANDES = {
    "xiii-ctl demarrer": ("Ouvrir le menu Démarrer", "Système et bureau"),
    "xiii-ctl demarrer-recherche": ("Rechercher", "Système et bureau"),
    "xiii-ctl centre": ("Centre de contrôle", "Système et bureau"),
    "xiii-ctl volet": ("Volet de notifications", "Système et bureau"),
    "xiii-ctl vue": ("Vue des tâches", "Fenêtres"),
    "xiii-ctl dispositions": ("Dispositions des fenêtres", "Ancrage et dispositions"),
    "xiii-ctl presse": ("Historique du presse-papiers", "Système et bureau"),
    "xiii-ctl emoji": ("Émojis", "Système et bureau"),
    "xiii-ctl bureau": ("Afficher le bureau", "Système et bureau"),
    "xiii-ctl widgets": ("Widgets", "Système et bureau"),
    "swaylock -f": ("Verrouiller la session", "Système et bureau"),
    "labwc --reconfigure": ("Recharger la configuration", "Système et bureau"),
    "xiii-parametres": ("Paramètres", "Applications"),
    "xiii-fichiers": ("Explorateur de fichiers", "Applications"),
    "xiii-taches": ("Gestionnaire des tâches", "Applications"),
    "xiii-ia": ("Assistant XIII", "Applications"),
    "claude-desktop": ("Claude", "Applications"),
    "xiii-claude-code": ("Claude Code dans le projet", "Applications"),
    "foot --app-id=fr.xiii.terminal": ("Terminal", "Applications"),
    "xiii-capture zone": ("Capture d'une zone", "Captures"),
    "xiii-capture ecran": ("Capture de l'écran entier", "Captures"),
    "xiii-capture menu": ("Menu des captures (zone, écran, vidéo…)", "Captures"),
    "xiii-capture video ecran": ("Enregistrer l'écran en vidéo (démarrer / arrêter)", "Captures"),
    "xiii-capture video zone": ("Enregistrer une zone en vidéo", "Captures"),
    "xiii-capture delai": ("Capture de l'écran dans 5 secondes", "Captures"),
    "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+": ("Monter le son", "Son et luminosité"),
    "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-": ("Baisser le son", "Son et luminosité"),
    "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle": ("Couper le son", "Son et luminosité"),
    "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle": ("Couper le micro", "Son et luminosité"),
    "brightnessctl set +5%": ("Augmenter la luminosité", "Son et luminosité"),
    "brightnessctl set 5%-": ("Baisser la luminosité", "Son et luminosité"),
    "playerctl play-pause": ("Lecture / pause", "Son et luminosité"),
    "playerctl next": ("Piste suivante", "Son et luminosité"),
    "playerctl previous": ("Piste précédente", "Son et luminosité"),
}
DIRS = {"left": "gauche", "right": "droite", "up": "haut", "down": "bas"}
REGIONS_FR = {"gauche": "moitié gauche", "droite": "moitié droite", "haut-gauche": "quart haut gauche", "haut-droite": "quart haut droit",
              "bas-gauche": "quart bas gauche", "bas-droite": "quart bas droit", "tiers-gauche": "tiers gauche", "tiers-centre": "tiers central",
              "tiers-droite": "tiers droit", "deux-tiers-gauche": "deux tiers gauche", "deux-tiers-droite": "deux tiers droits", "centre": "centre"}

# actions labwc proposées quand on crée un raccourci
ACTIONS = [
    ("Close", {}, "Fermer la fenêtre", "Fenêtres"),
    ("ToggleMaximize", {}, "Agrandir / restaurer", "Fenêtres"),
    ("Iconify", {}, "Réduire la fenêtre", "Fenêtres"),
    ("ToggleFullscreen", {}, "Plein écran", "Fenêtres"),
    ("ToggleAlwaysOnTop", {}, "Toujours au premier plan", "Fenêtres"),
    ("NextWindow", {}, "Fenêtre suivante", "Fenêtres"),
    ("PreviousWindow", {}, "Fenêtre précédente", "Fenêtres"),
    ("ShowMenu", {"menu": "client-menu"}, "Menu de la fenêtre", "Fenêtres"),
    ("Move", {}, "Déplacer la fenêtre", "Fenêtres"),
    ("Resize", {}, "Redimensionner la fenêtre", "Fenêtres"),
    ("MoveToEdge", {"direction": "left"}, "Pousser la fenêtre à gauche", "Fenêtres"),
    ("MoveToEdge", {"direction": "right"}, "Pousser la fenêtre à droite", "Fenêtres"),
    ("SnapToEdge", {"direction": "left"}, "Ancrer à gauche", "Ancrage et dispositions"),
    ("SnapToEdge", {"direction": "right"}, "Ancrer à droite", "Ancrage et dispositions"),
    ("SnapToEdge", {"direction": "up"}, "Ancrer en haut", "Ancrage et dispositions"),
    ("SnapToEdge", {"direction": "down"}, "Ancrer en bas", "Ancrage et dispositions"),
    ("GoToDesktop", {"to": "left", "wrap": "yes"}, "Bureau précédent", "Bureaux virtuels"),
    ("GoToDesktop", {"to": "right", "wrap": "yes"}, "Bureau suivant", "Bureaux virtuels"),
    ("SendToDesktop", {"to": "left", "wrap": "yes"}, "Envoyer au bureau précédent", "Bureaux virtuels"),
    ("SendToDesktop", {"to": "right", "wrap": "yes"}, "Envoyer au bureau suivant", "Bureaux virtuels"),
    ("ShowMenu", {"menu": "root-menu"}, "Menu du bureau", "Système et bureau"),
    ("Reconfigure", {}, "Recharger la configuration", "Système et bureau"),
] + [("Execute", {"command": k}, v[0], v[1]) for k, v in COMMANDES.items() if k not in ("labwc --reconfigure",)]

def decrire(actions):
    """[(nom, attrs)] → (texte, catégorie)"""
    if not actions: return "Aucune action", "Personnalisés"
    n, a = actions[0]
    if n == "Execute":
        cmd = a.get("command", "")
        if cmd in COMMANDES: return COMMANDES[cmd]
        if cmd.startswith("gio launch "):
            nom = os.path.basename(cmd[11:].strip("'\"")).replace(".desktop", "")
            try:
                from gi.repository import Gio
                ap = Gio.DesktopAppInfo.new_from_filename(cmd[11:].strip("'\""))
                if ap: nom = ap.get_display_name()
            except Exception: pass
            return "Ouvrir " + nom, "Personnalisés"
        return "Commande : " + cmd, "Personnalisés"
    if n == "GoToDesktop":
        t = a.get("to", ""); return ({"left": "Bureau précédent", "right": "Bureau suivant"}.get(t) or "Aller au bureau " + t), "Bureaux virtuels"
    if n == "SendToDesktop":
        t = a.get("to", ""); return ({"left": "Envoyer au bureau précédent", "right": "Envoyer au bureau suivant"}.get(t) or "Envoyer la fenêtre au bureau " + t), "Bureaux virtuels"
    if n == "SnapToEdge": return "Ancrer la fenêtre " + {"left": "à gauche", "right": "à droite", "up": "en haut", "down": "en bas"}.get(a.get("direction"), ""), "Ancrage et dispositions"
    if n == "SnapToRegion": return "Placer la fenêtre : " + REGIONS_FR.get(a.get("region"), a.get("region", "")), "Ancrage et dispositions"
    for an, aa, txt, cat in ACTIONS:
        if an == n and all(a.get(k) == v for k, v in aa.items()): return txt, cat
    return n, "Fenêtres"

# ------------------------------------------------------------------ touches
NOMS_MODS = {"W": "Super", "C": "Ctrl", "A": "Alt", "S": "Maj", "H": "Hyper", "M": "AltGr"}
NOMS_TOUCHES = {"space": "Espace", "Return": "Entrée", "Escape": "Échap", "Tab": "Tab", "BackSpace": "Retour arrière", "Delete": "Suppr", "Print": "Impr. écran",
                "Left": "←", "Right": "→", "Up": "↑", "Down": "↓", "period": ".", "semicolon": ";", "comma": ",", "Home": "Début", "End": "Fin",
                "Page_Up": "Page ↑", "Prior": "Page ↑", "Page_Down": "Page ↓", "Next": "Page ↓", "Insert": "Inser", "Super_L": "Super", "Super_R": "Super droite",
                "XF86AudioRaiseVolume": "Touche Volume +", "XF86AudioLowerVolume": "Touche Volume −", "XF86AudioMute": "Touche Muet", "XF86AudioMicMute": "Touche Micro muet",
                "XF86MonBrightnessUp": "Touche Luminosité +", "XF86MonBrightnessDown": "Touche Luminosité −", "XF86TouchpadToggle": "Touche Pavé tactile",
                "XF86AudioPlay": "Touche Lecture", "XF86AudioNext": "Touche Suivant", "XF86AudioPrev": "Touche Précédent", "minus": "-", "plus": "+", "equal": "=",
                "slash": "/", "backslash": "\\", "apostrophe": "'", "grave": "`", "bracketleft": "[", "bracketright": "]"}

def humain(cle):
    if not cle: return "—"
    p = cle.split("-")
    mods, t = p[:-1], p[-1]
    if t == "" and len(p) > 1: t = "-"
    t = NOMS_TOUCHES.get(t, t.upper() if len(t) == 1 else t)
    return " + ".join([NOMS_MODS.get(m, m) for m in mods] + [t])

ORDRE_MODS = ["W", "C", "A", "S"]

def depuis_gdk(keyval, etat):
    """Touche Gdk + modificateurs → notation labwc (ex : W-S-s). None si seulement un modificateur."""
    nom = Gdk.keyval_name(Gdk.keyval_to_lower(keyval)) or ""
    seuls = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R", "ISO_Level3_Shift", "Hyper_L", "Hyper_R"}
    if nom in seuls: return None
    mods = []
    if etat & Gdk.ModifierType.SUPER_MASK and nom not in ("Super_L", "Super_R"): mods.append("W")
    if etat & Gdk.ModifierType.CONTROL_MASK: mods.append("C")
    if etat & Gdk.ModifierType.ALT_MASK: mods.append("A")
    if etat & Gdk.ModifierType.SHIFT_MASK: mods.append("S")
    return "-".join(mods + [nom])

def normaliser(cle):
    p = cle.split("-"); t = p[-1]; mods = sorted(set(p[:-1]), key=lambda m: ORDRE_MODS.index(m) if m in ORDRE_MODS else 9)
    return "-".join(mods + [t.lower() if len(t) == 1 else t])

# ------------------------------------------------------------------ lecture / écriture
def _arbre():
    try: return ET.parse(RC)
    except Exception:
        try: return ET.parse(SKEL)
        except Exception: return ET.ElementTree(ET.fromstring("<labwc_config><keyboard/></labwc_config>"))

def _clavier(racine):
    k = racine.find("keyboard")
    if k is None: k = ET.SubElement(racine, "keyboard")
    return k

def _actions(kb):
    out = []
    for a in kb.findall("action"):
        attrs = dict(a.attrib); n = attrs.pop("name", "")
        if n == "Execute" and "command" not in attrs:
            c = a.findtext("command") or a.findtext("execute")
            if c: attrs["command"] = c
        out.append((n, attrs))
    return out

def signature(actions):
    return json.dumps(actions, sort_keys=True, ensure_ascii=False)

def lire():
    """Liste de raccourcis : dict(cle, actions, texte, categorie, onrelease)."""
    t = _arbre(); k = _clavier(t.getroot())
    L = []; vues = set()
    for kb in k.findall("keybind"):
        a = _actions(kb); txt, cat = decrire(a)
        L.append({"cle": kb.get("key", ""), "actions": a, "texte": txt, "categorie": cat, "onrelease": kb.get("onRelease") == "yes"}); vues.add(kb.get("key"))
    if k.find("default") is not None:
        for cle, a in DEFAUTS_LABWC:
            if cle not in vues:
                txt, cat = decrire(a); L.append({"cle": cle, "actions": a, "texte": txt, "categorie": cat, "onrelease": False})
    return L

def ecrire(liste):
    """Réécrit tous les <keybind> ; <default/> est retiré (les défauts sont maintenant explicites dans la liste)."""
    t = _arbre(); r = t.getroot(); k = _clavier(r)
    for e in list(k):
        if e.tag in ("keybind", "default"): k.remove(e)
    for s in liste:
        if not s.get("cle"): continue
        kb = ET.SubElement(k, "keybind", key=s["cle"])
        if s.get("onrelease"): kb.set("onRelease", "yes")
        for n, a in s["actions"]:
            ae = ET.SubElement(kb, "action", name=n)
            for kk, vv in a.items(): ae.set(kk, vv)
    ET.indent(t, "  ")
    os.makedirs(os.path.dirname(RC), exist_ok=True)
    if os.path.exists(RC): shutil.copy2(RC, RC + ".avant-raccourcis")
    t.write(RC, encoding="unicode", xml_declaration=True)
    _memoriser_retires(liste)
    try:
        import subprocess; subprocess.Popen(["labwc", "--reconfigure"], stderr=subprocess.DEVNULL)
    except Exception: pass

def origine():
    """Raccourcis livrés avec OS XIII."""
    try:
        t = ET.parse(SKEL); k = _clavier(t.getroot())
        L = [{"cle": kb.get("key"), "actions": _actions(kb), "onrelease": kb.get("onRelease") == "yes"} for kb in k.findall("keybind")]
        if k.find("default") is not None:
            vues = {s["cle"] for s in L}
            L += [{"cle": c, "actions": a, "onrelease": False} for c, a in DEFAUTS_LABWC if c not in vues]
        return L
    except Exception:
        return []

def _memoriser_retires(liste):
    """Raccourcis d'origine absents (supprimés ou déplacés) → la mise à jour ne les remettra pas."""
    actuels = {(s["cle"], signature(s["actions"])) for s in liste}
    sigs = {signature(s["actions"]) for s in liste}
    retires = []
    for o in origine():
        if (o["cle"], signature(o["actions"])) not in actuels:
            retires.append({"cle": o["cle"], "sig": signature(o["actions"]), "deplace": signature(o["actions"]) in sigs})
    os.makedirs(os.path.dirname(RETIRES), exist_ok=True)
    json.dump(retires, open(RETIRES, "w"), ensure_ascii=False, indent=1)

def reinitialiser():
    L = [dict(s) for s in origine()]
    ecrire(L)
    try: os.remove(RETIRES)
    except OSError: pass

def conflit(liste, cle, sauf=None):
    cle = normaliser(cle)
    for i, s in enumerate(liste):
        if i != sauf and s.get("cle") and normaliser(s["cle"]) == cle: return i
    return None

def exporter(chemin, liste):
    json.dump({"os-xiii-raccourcis": 1, "raccourcis": [{"cle": s["cle"], "actions": s["actions"], "onrelease": s.get("onrelease", False)} for s in liste]},
              open(chemin, "w"), ensure_ascii=False, indent=1)

def importer(chemin):
    d = json.load(open(chemin))
    L = [{"cle": s["cle"], "actions": [tuple(a) for a in s["actions"]], "onrelease": s.get("onrelease", False)} for s in d.get("raccourcis", [])]
    if not L: raise ValueError("Aucun raccourci dans ce fichier")
    ecrire(L); return len(L)


# ------------------------------------------------------------------ déclencher une action labwc (gestes, vue des tâches…)
WT = {"W": "logo", "C": "ctrl", "A": "alt", "S": "shift"}
def declencher(nom, attrs=None, defaut=None):
    """Simule le raccourci actuellement attribué à l'action labwc (suit les raccourcis personnalisés).
    defaut : touche à utiliser si aucun raccourci n'est attribué (ex. « C-W-Right »)."""
    import subprocess
    attrs = attrs or {}
    cle = next((x["cle"] for x in lire() if x["actions"] and x["actions"][0][0] == nom and all(x["actions"][0][1].get(k) == v for k, v in attrs.items())), defaut)
    if not cle: return False
    p = cle.split("-"); mods, t = [WT[m] for m in p[:-1] if m in WT], p[-1] or "-"
    cmd = ["wtype"]
    for m in mods: cmd += ["-M", m]
    cmd += ["-k", t]
    for m in reversed(mods): cmd += ["-m", m]
    try: subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); return True
    except OSError: return False

# gestes du pavé tactile (service xiii-gestes) → action du bureau
GESTES = {"balayage 3 gauche": ("bureau-suivant", "Bureau suivant"), "balayage 3 droite": ("bureau-precedent", "Bureau précédent"),
          "balayage 3 haut": ("vue", "Vue des tâches"), "balayage 3 bas": ("bureau", "Afficher le bureau"),
          "balayage 4 haut": ("demarrer", "Menu Démarrer"), "balayage 4 bas": ("volet", "Notifications"),
          "balayage 4 gauche": ("presse", "Presse-papiers"), "balayage 4 droite": ("widgets", "Widgets"),
          "pincement 3 resserrer": ("vue", "Vue des tâches")}

