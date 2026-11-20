# OS XIII — réglages utilisateur (~/.config/xiii/reglages.json)
# Application développée par Matthieu Lamotte.
import json, os, copy
from gi.repository import Gio, GLib

DOSSIER = os.path.join(GLib.get_user_config_dir(), "xiii")
FICHIER = os.path.join(DOSSIER, "reglages.json")
FONDS = "/usr/share/xiii/wallpapers"

DEFAUTS = {
    "theme": "sombre",              # thèmes de la Suite XIII : sombre | clair | auto | sobre | sobrec | w2k | xp | mac9 | cyber | term | gb | regie | soleil | rainbow | sepia | perso
    "theme_perso": {"name": "Minuit bleu", "bg": "#0d1320", "panel": "#16203a", "text": "#e6ecf7", "accent": "#4fc3f7", "radius": "m", "shadow": "m", "glass": 0},
    "contraste": False,
    "densite": "normal",
    "accent": "#f0b378",
    "transparence": True,
    "animations": True,
    "fond": FONDS + "/xiii-sombre.png",
    "fond_mode": "fill",
    "verrou_fond": FONDS + "/xiii-connexion.png",
    "barre_alignement": "centre",   # centre | gauche
    "barre_style": "icones",        # icones | onglets
    "indic_style": "icone",
    "fichiers_vue": "windows",
    "ia": "claude", "ia_largeur": 480,      # windows | mac | arbre
    "mode_bureau": "classique",     # classique | production | fiction | multicam | backup | gaming
    "mode_epingles": {}, "backup_destination": "", "backup_nom": "", "backup_auto": False, "backup_algo": "xxh64",         # icone | rond | barre | pourcentage | minimal
    "timecode_source": "",          # entrée audio du timecode LTC
    "timecode_canal": 0,
    "decklink_entree": 0, "decklink_mode": "auto", "decklink_pont": False,
    "barre_recherche": True,
    "barre_meteo": True,
    "barre_badge": True,
    "epingles": ["xiii-parametres.desktop", "com.anthropic.Claude.desktop", "firefox-esr.desktop", "thunar.desktop",
                 "org.xfce.mousepad.desktop", "mpv.desktop", "xiii-bilan.desktop"],
    "menu_epingles": ["xiii-parametres.desktop", "com.anthropic.Claude.desktop", "xiii-claude-code.desktop", "xiii-suite-accueil.desktop", "xiii-tally.desktop", "firefox-esr.desktop", "thunar.desktop", "org.xfce.mousepad.desktop",
                      "mpv.desktop", "steam.desktop", "xiii-bilan.desktop", "xiii-pilotes.desktop", "xiii-demarrage.desktop",
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
    "profil": "normal",
    "timecode": False,
    "timecode_fps": 25,
    "projet_actif": "",
    "coins": {"hg": "rien", "hd": "rien", "bg": "rien", "bd": "bureau"},
    "icones_bureau": True,
    "reprise_session": False,
    "veille_mode": "horloge",
    "veille_delai": 300,
    "apercu_survol": True,
    "jeu_console": False,
    "mangohud": False,
    "jeu_30ips": False,
    "taille_texte": 1.0,
    "curseur_taille": 24,
    "police": "IBM Plex Sans",
    "montage_auto": True,
    "ecrans": {},
    "widgets": ["meteo", "systeme", "duo", "projet", "plan", "conducteur", "offload", "ndi", "media", "notes", "raccourcis"],
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

HISTO = os.path.join(DOSSIER, "historique.json")
SANS_HISTO = {"epingles", "menu_epingles", "ecrans", "visite_faite", "meteo_lat", "meteo_lon"}

def historique():
    try:
        return json.load(open(HISTO))
    except Exception:
        return []

def modifier(_histo=True, **kw):
    """Enregistre des réglages ; garde l'ancienne valeur pour pouvoir annuler (Paramètres › Historique)."""
    c = charger()
    avant = {k: c.get(k) for k in kw if c.get(k) != kw[k]}
    c.update(kw); enregistrer(c)
    if _histo and avant and not (set(avant) <= SANS_HISTO):
        import time
        h = historique()
        h.insert(0, {"t": time.time(), "avant": avant, "apres": {k: kw[k] for k in avant}})
        try:
            json.dump(h[:60], open(HISTO, "w"), ensure_ascii=False)
        except Exception:
            pass
    return c

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
