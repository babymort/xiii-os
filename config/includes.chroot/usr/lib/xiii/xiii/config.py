# OS XIII — réglages utilisateur (~/.config/xiii/reglages.json)
# Application développée par Matthieu Lamotte.
import json, os, copy
from gi.repository import Gio, GLib

DOSSIER = os.path.join(GLib.get_user_config_dir(), "xiii")
FICHIER = os.path.join(DOSSIER, "reglages.json")
FONDS = "/usr/share/xiii/wallpapers"

DEFAUTS = {
    "theme": "sombre",              # sombre | clair | sobre
    "accent": "#f0b378",
    "transparence": True,
    "animations": True,
    "fond": FONDS + "/xiii-sombre.png",
    "fond_mode": "fill",
    "verrou_fond": FONDS + "/xiii-connexion.png",
    "barre_alignement": "centre",   # centre | gauche
    "barre_recherche": True,
    "barre_meteo": True,
    "barre_badge": True,
    "epingles": ["xiii-parametres.desktop", "firefox-esr.desktop", "thunar.desktop",
                 "org.xfce.mousepad.desktop", "mpv.desktop", "xiii-bilan.desktop"],
    "menu_epingles": ["xiii-parametres.desktop", "firefox-esr.desktop", "thunar.desktop", "org.xfce.mousepad.desktop",
                      "mpv.desktop", "imv.desktop", "xiii-bilan.desktop", "xiii-pilotes.desktop", "xiii-demarrage.desktop",
                      "org.gnome.DiskUtility.desktop", "pavucontrol.desktop", "xiii-webcam.desktop"],
    "menu_recommandes": True,
    "menu_vue": "epingles",          # epingles | categories
    "haut_titre": True,
    "haut_secondes": False,
    "haut_pourcentage": True,
    "horloge_24h": True,
    "ne_pas_deranger": False,
    "notif_apercu": True,
    "notif_bloquees": [],
    "meteo_ville": "Paris",
    "meteo_lat": 48.8566,
    "meteo_lon": 2.3522,
    "meteo_unite": "celsius",
    "lumiere_nocturne": False,
    "nocturne_temp": 4000,
    "veille_ecran": 600,
    "verrou_actif": True,
    "mode_tournage": False,
    "taille_texte": 1.0,
    "curseur_taille": 24,
    "police": "IBM Plex Sans",
    "montage_auto": True,
    "ecrans": {},
    "widgets": ["meteo", "systeme", "projet", "plan", "conducteur", "media", "notes", "raccourcis"],
    "visite_faite": False,
}

def charger():
    c = copy.deepcopy(DEFAUTS)
    try:
        with open(FICHIER) as f:
            d = json.load(f)
        if isinstance(d, dict):
            c.update({k: v for k, v in d.items() if k in DEFAUTS or k.startswith("x_")})
    except Exception:
        pass
    return c

def enregistrer(c):
    os.makedirs(DOSSIER, exist_ok=True)
    tmp = FICHIER + ".tmp"
    with open(tmp, "w") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FICHIER)

def modifier(**kw):
    c = charger(); c.update(kw); enregistrer(c); return c

def surveiller(rappel):
    """Appelle rappel(config) quand le fichier change. Garder la référence retournée."""
    os.makedirs(DOSSIER, exist_ok=True)
    mon = Gio.File.new_for_path(FICHIER).monitor_file(Gio.FileMonitorFlags.NONE, None)
    etat = {"id": 0}
    def changed(*_):
        if etat["id"]:
            GLib.source_remove(etat["id"])
        def fire():
            etat["id"] = 0; rappel(charger()); return False
        etat["id"] = GLib.timeout_add(150, fire)
    mon.connect("changed", changed)
    return mon
