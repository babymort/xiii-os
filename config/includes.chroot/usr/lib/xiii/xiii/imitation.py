# OS XIII — thèmes « Façon Windows 11 » et « Façon macOS » : couleurs, CSS du bureau et des Paramètres, fenêtres (labwc),
# fonds d'écran dessinés, polices et icônes libres équivalentes.
# Rien n'est repris d'Apple ni de Microsoft : pas de logo, pas de fond d'écran, pas de police propriétaire. Polices :
# Selawik (Microsoft, licence SIL OFL, remplaçant libre de Segoe UI) et Inter (SIL OFL, proche de San Francisco) ;
# icônes et curseurs Fluent et WhiteSur (vinceliuice, GPL 3) ; fonds d'écran dessinés ici.
# Application développée par Matthieu Lamotte.
import os, math

NOMS = {"onze": "Façon Windows 11", "macos": "Façon macOS"}

# fond, panneau, carte, carte2, texte, atténué, bord, accent (None = choisi, sinon l'accent par défaut du système imité), arrondi, police
SKINS = {
    "onze": dict(fond="#f3f3f3", panneau="#f9f9f9", carte="#ffffff", carte2="#f3f3f3", texte="#1b1b1b", attenue="#5c5c5c", bord="rgba(0,0,0,0.08)",
                 acc=None, r=8, verre=True, clair=True, police="Selawik", imitation="onze", acc_defaut="#005fb8"),
    "onze-sombre": dict(fond="#202020", panneau="#2c2c2c", carte="#2d2d2d", carte2="#272727", texte="#ffffff", attenue="#c5c5c5", bord="rgba(255,255,255,0.08)",
                        acc=None, r=8, verre=True, police="Selawik", imitation="onze", acc_defaut="#4cc2ff"),
    "macos": dict(fond="#ececec", panneau="#f2f2f2", carte="#ffffff", carte2="#e9e9e9", texte="#1d1d1f", attenue="#6e6e73", bord="rgba(0,0,0,0.10)",
                  acc=None, r=10, verre=True, clair=True, police="Inter", imitation="macos", acc_defaut="#007aff"),
    "macos-sombre": dict(fond="#1e1e1e", panneau="#2b2b2b", carte="#323232", carte2="#262626", texte="#f5f5f7", attenue="#a1a1a6", bord="rgba(255,255,255,0.10)",
                         acc=None, r=10, verre=True, police="Inter", imitation="macos", acc_defaut="#0a84ff"),
}

# disposition du bureau imposée par chaque imitation (l'ancienne est gardée et rendue en revenant à un thème XIII)
DISPOSITIONS = {
    "onze": dict(barre_position="bas", barre_forme="classique", barre_alignement="centre", barre_masquee=False, barre_meteo=True,
                 barre_recherche=True, coin_bureau=True, barre_taille="normale", haut_applis=False, barre_style="icones"),
    "macos": dict(barre_position="bas", barre_forme="dock", dock_masquage=False, dock_grossissement=True, dock_rebond=True,
                  barre_masquee=False, barre_taille="grande", haut_applis=False, barre_style="icones"),
}
CLES_DISPOSITION = sorted({k for d in DISPOSITIONS.values() for k in d})

POLICES = {"onze": '"Selawik", "Segoe UI", "Inter", "IBM Plex Sans", sans-serif', "macos": '"Inter", "IBM Plex Sans", sans-serif'}


def de(t):
    """« onze-sombre » → « onze » ; None si ce n'est pas une imitation."""
    if not t: return None
    b = t.split("-")[0]
    return b if b in DISPOSITIONS else None


def variante(t, cfg, jour):
    """Clair ou sombre selon Paramètres › Thème › Apparence (clair, sombre, auto au lever / coucher du soleil)."""
    a = cfg.get("imitation_apparence", "clair")
    sombre = a == "sombre" or (a == "auto" and not jour())
    return t + ("-sombre" if sombre else "")


def icones(t, sombre):
    """Thème d'icônes installé pour l'imitation (Fluent, WhiteSur), sinon Papirus, sinon None."""
    noms = {"onze": ["Fluent-dark" if sombre else "Fluent", "Fluent"], "macos": ["WhiteSur-dark" if sombre else "WhiteSur", "WhiteSur"]}[t]
    noms += ["Papirus-Dark" if sombre else "Papirus", "Papirus"]
    for n in noms:
        for d in ("/usr/share/icons", os.path.expanduser("~/.local/share/icons"), os.path.expanduser("~/.icons")):
            if os.path.exists(os.path.join(d, n, "index.theme")): return n
    return None


def curseur(t):
    n = {"onze": "Fluent-cursors", "macos": "WhiteSur-cursors"}[t]
    for d in ("/usr/share/icons", os.path.expanduser("~/.local/share/icons")):
        if os.path.isdir(os.path.join(d, n, "cursors")): return n
    return None


def retoucher(p, s, rgba):
    """Ajuste la palette calculée par theme.palette() : pas de lueur ni de dégradé cuivre, verre acrylique neutre."""
    imit = s["imitation"]; clair = p["clair"]; verre = p["verre"]
    p["imitation"] = imit; p["sombre"] = not clair
    a = .84 if verre else 1
    pan = s["panneau"]
    p["lueur"] = "none"; p["pilule"] = p["accent"]; p["pilule_lueur"] = "none"
    p["panneau"] = rgba(pan, .90 if verre else 1); p["panneau_verre"] = p["panneau"]
    p["rayon_petit"] = "4px" if imit == "onze" else "6px"
    p["police_css"] = POLICES[imit]
    if imit == "onze":
        p["barre_fond"] = rgba("#eeeeee" if clair else "#1c1c1c", a)
        p["barre_ligne"] = "rgba(0,0,0,0.07)" if clair else "rgba(255,255,255,0.06)"
        p["ombre"] = "rgba(0,0,0,0.16)" if clair else "rgba(0,0,0,0.45)"
        p["survol"] = "rgba(0,0,0,0.04)" if clair else "rgba(255,255,255,0.06)"
    else:
        p["barre_fond"] = rgba("#f6f6f6" if clair else "#1e1e1e", .72 if verre else 1)       # barre des menus
        p["dock_fond"] = rgba("#ffffff" if clair else "#363636", .42 if verre else .96)
        p["barre_ligne"] = "rgba(0,0,0,0.06)" if clair else "rgba(255,255,255,0.08)"
        p["ombre"] = "rgba(0,0,0,0.22)" if clair else "rgba(0,0,0,0.55)"
        p["survol"] = "rgba(0,0,0,0.05)" if clair else "rgba(255,255,255,0.08)"
    return p


# --------------------------------------------------------------------------------------------- CSS du bureau
def css_commun_imitation(p):
    """Partie commune au bureau, aux Paramètres et aux applis XIII : police, boutons, interrupteurs, menus."""
    tx, A, SA, att, bord = p["texte"], p["accent"], p["sur_accent"], p["attenue"], p["bord"]
    clair = p["clair"]; pol = p["police_css"]
    return f"""
/* ---- imitation : {NOMS[p['imitation']]} ---- */
* {{ font-family: {pol}; }}
.titre-astoria, .page-titre, .hero-grand, .panneau-titre, .nav-titre, .haut-logo {{ font-family: {pol}; letter-spacing: 0; color: {tx}; }}
.panneau-titre {{ font-size: 15px; font-weight: 600; }}
.accent {{ color: {p['accent_texte']}; }}
.filigrane {{ color: transparent; }}
button.pilule {{ background: {A}; color: {SA}; box-shadow: none; border-radius: {p['rayon_petit']}; font-weight: 600; padding: 6px 18px; }}
button.pilule:hover {{ background: {p['accent_survol']}; }}
button.fantome {{ border-radius: {p['rayon_petit']}; border: 1px solid {bord}; background: {'#ffffff' if clair else 'rgba(255,255,255,0.06)'}; }}
button.fantome label {{ color: {tx}; }}
button.fantome:hover {{ background: {'#f6f6f6' if clair else 'rgba(255,255,255,0.09)'}; }}
popover > contents {{ background: {p['panneau']}; border: 1px solid {'rgba(0,0,0,0.10)' if clair else 'rgba(255,255,255,0.10)'}; border-radius: {p['rayon']}; box-shadow: 0 8px 24px {p['ombre']}; padding: 4px; }}
popover button.ligne {{ border-radius: {p['rayon_petit']}; padding: 6px 12px; }}
popover button.ligne:hover {{ background: {p['survol'] if p['imitation'] == 'onze' else A}; }}
.recherche {{ border-radius: {'999px' if p['imitation'] == 'onze' else '8px'}; background: {'#ffffff' if clair else 'rgba(255,255,255,0.06)'}; border: 1px solid {bord}; box-shadow: {'inset 0 -1px 0 ' + A if p['imitation'] == 'onze' else 'none'}; }}
.panneau {{ border: 1px solid {'rgba(0,0,0,0.10)' if clair else 'rgba(255,255,255,0.10)'}; box-shadow: 0 16px 48px {p['ombre']}; }}
tooltip {{ border-radius: {p['rayon_petit']}; border: 1px solid {bord}; }}
switch {{ background: {'rgba(0,0,0,0.0)' if p['imitation'] == 'onze' else 'rgba(120,120,128,0.32)'}; border: 1px solid {att if p['imitation'] == 'onze' else 'transparent'}; }}
switch slider {{ background: {att if p['imitation'] == 'onze' else '#ffffff'}; min-width: {12 if p['imitation'] == 'onze' else 18}px; min-height: {12 if p['imitation'] == 'onze' else 18}px; margin: {4 if p['imitation'] == 'onze' else 2}px; box-shadow: {'none' if p['imitation'] == 'onze' else '0 1px 3px rgba(0,0,0,0.3)'}; }}
switch:checked {{ background: {A}; border-color: {A}; }}
switch:checked slider {{ background: {SA if p['imitation'] == 'onze' else '#ffffff'}; }}
scale slider {{ background: {A}; border: {'5px solid ' + ('#ffffff' if clair else '#454545') if p['imitation'] == 'onze' else '0.5px solid rgba(0,0,0,0.2)'}; min-width: 20px; min-height: 20px; margin: -9px; box-shadow: 0 1px 3px rgba(0,0,0,0.25); }}
{'scale slider { background: #ffffff; }' if p['imitation'] == 'macos' else ''}
.notif, .toast {{ border-radius: {p['rayon']}; }}
.badge {{ background: {'#c42b1c' if p['imitation'] == 'onze' else '#ff3b30'}; color: #ffffff; }}
"""


def css_shell(p, cfg):
    tx, A, SA, att, bord = p["texte"], p["accent"], p["sur_accent"], p["attenue"], p["bord"]
    clair = p["clair"]; pol = p["police_css"]
    commun = css_commun_imitation(p)
    if p["imitation"] == "onze":
        return commun + f"""
/* barre des tâches Windows 11 : acrylique, icônes centrées, pilule sous l'appli active */
.barre {{ background: {p['barre_fond']}; border-top: 1px solid {p['barre_ligne']}; box-shadow: none; border-radius: 0; }}
button.tb {{ border-radius: 4px; min-height: 40px; min-width: 44px; padding: 0 4px; margin: 0 1px; }}
button.tb:hover {{ background: {'rgba(255,255,255,0.65)' if clair else 'rgba(255,255,255,0.07)'}; }}
button.tb.actif {{ background: {'rgba(255,255,255,0.75)' if clair else 'rgba(255,255,255,0.09)'}; }}
button.tb.ouvert {{ background: {'rgba(255,255,255,0.75)' if clair else 'rgba(255,255,255,0.09)'}; }}
.tb-ind {{ background: {'#8a8a8a' if clair else '#9d9d9d'}; min-height: 3px; min-width: 6px; border-radius: 2px; }}
.tb-ind.actif {{ background: {A}; min-width: 16px; }}
.onze-recherche {{ background: {'#ffffff' if clair else 'rgba(255,255,255,0.06)'}; border: 1px solid {'rgba(0,0,0,0.06)' if clair else 'rgba(255,255,255,0.08)'}; border-radius: 999px; padding: 0 14px 0 10px; min-height: 32px; min-width: 190px; }}
.onze-recherche label {{ color: {att}; font-size: 13px; }}
button.tb.b-recherche:hover {{ background: transparent; }}
button.tb.b-recherche:hover .onze-recherche {{ background: {'#fbfbfb' if clair else 'rgba(255,255,255,0.09)'}; }}
.onze-etat {{ border-radius: 4px; padding: 0 6px; }}
.onze-etat:hover {{ background: {'rgba(255,255,255,0.65)' if clair else 'rgba(255,255,255,0.07)'}; }}
.onze-etat button.hb {{ padding: 0 3px; min-height: 40px; background: transparent; }}
.onze-etat button.hb:hover {{ background: transparent; }}
.horloge-h, .horloge-d {{ font-size: 12px; font-weight: 400; color: {tx}; }}
.meteo-t {{ font-size: 12px; font-weight: 600; }}
.coin-bureau {{ border-left: 1px solid {'rgba(0,0,0,0.12)' if clair else 'rgba(255,255,255,0.12)'}; min-width: 6px; margin: 0 0 0 6px; border-radius: 0; }}
.coin-bureau:hover {{ background: transparent; }}
/* menu Démarrer : grand panneau acrylique, recherche en haut, pied gris */
.panneau {{ border-radius: 8px; padding: 22px 26px 0 26px; }}
.menu-pied {{ background: {'rgba(0,0,0,0.035)' if clair else 'rgba(0,0,0,0.18)'}; border-top: 1px solid {bord}; margin: 6px -26px 0 -26px; padding: 12px 34px; border-radius: 0 0 8px 8px; }}
button.app {{ border-radius: 4px; padding: 10px 2px 6px 2px; }}
button.app:hover {{ background: {'rgba(255,255,255,0.7)' if clair else 'rgba(255,255,255,0.06)'}; }}
.app-nom {{ font-size: 12px; }}
button.ligne {{ border-radius: 4px; }}
button.tuile {{ border-radius: 4px; min-height: 48px; background: {'#fbfbfb' if clair else 'rgba(255,255,255,0.06)'}; }}
button.tuile.on {{ background: {A}; border-color: {A}; }}
.avatar {{ background: {'#d9d9d9' if clair else '#4a4a4a'}; }} .avatar label {{ color: {tx}; }}
"""
    # ---- macOS
    return commun + f"""
/* barre des menus en haut */
.haut {{ background: {p['barre_fond']}; border-bottom: none; box-shadow: none; }}
.haut button.hb {{ border-radius: 5px; padding: 0 9px; min-height: 22px; }}
.haut button.hb:hover, .haut button.hb.ouvert {{ background: {'rgba(0,0,0,0.10)' if clair else 'rgba(255,255,255,0.16)'}; }}
.haut button.hb label {{ font-size: 13px; font-weight: 500; color: {tx}; }}
.mac-appli label, .haut button.hb.mac-appli label {{ font-weight: 700; }}
.mac-logo {{ font-family: {pol}; font-weight: 800; font-size: 13.5px; color: {tx}; letter-spacing: -0.5px; }}
.mac-horloge {{ font-size: 13px; font-weight: 500; }}
.haut-secteur {{ border-left: none; margin-left: 0; padding-left: 0; }}
/* menus déroulants de la barre des menus */
popover.mac-menu > contents {{ padding: 5px; border-radius: 8px; min-width: 230px; background: {'rgba(246,246,246,0.92)' if clair else 'rgba(40,40,40,0.92)'}; }}
popover.mac-menu button.mac-item {{ background: transparent; border: none; box-shadow: none; border-radius: 4px; padding: 2px 10px; min-height: 22px; }}
popover.mac-menu button.mac-item:hover {{ background: {A}; }}
popover.mac-menu button.mac-item:hover label {{ color: #ffffff; }}
popover.mac-menu button.mac-item label {{ font-size: 13px; }}
popover.mac-menu .mac-raccourci {{ color: {att}; font-size: 12.5px; }}
popover.mac-menu separator {{ margin: 4px 10px; background: {bord}; min-height: 1px; }}
/* Dock */
window.barre-dock .barre {{ background: {p['dock_fond']}; border: 1px solid {'rgba(255,255,255,0.55)' if clair else 'rgba(255,255,255,0.14)'}; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.25); padding: 0 6px; }}
window.barre-dock button.tb {{ background: transparent; border-radius: 12px; min-width: 54px; padding: 2px 3px 0 3px; }}
window.barre-dock button.tb:hover, window.barre-dock button.tb.actif, window.barre-dock button.tb.ouvert {{ background: transparent; }}
.tb-ind {{ background: {'#1d1d1f' if clair else '#f5f5f7'}; min-width: 4px; min-height: 4px; border-radius: 2px; opacity: .75; }}
.tb-ind.actif {{ background: {'#1d1d1f' if clair else '#f5f5f7'}; min-width: 4px; }}
.tb-ind.vide {{ background: transparent; }}
.dock-sep {{ background: {'rgba(0,0,0,0.18)' if clair else 'rgba(255,255,255,0.22)'}; min-width: 1px; margin: 10px 6px; }}
/* Launchpad et Spotlight */
.launchpad {{ background: rgba(0,0,0,0.25); }}
.launchpad .lp-nom {{ color: #ffffff; font-size: 12.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.6); }}
.launchpad button.lp-app {{ background: transparent; border: none; box-shadow: none; padding: 8px; border-radius: 16px; }}
.launchpad button.lp-app:hover {{ background: rgba(255,255,255,0.10); }}
.launchpad entry {{ background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.25); border-radius: 8px; color: #ffffff; min-width: 240px; min-height: 28px; }}
.launchpad entry text {{ color: #ffffff; }}
.lp-point {{ background: rgba(255,255,255,0.35); border-radius: 4px; min-width: 7px; min-height: 7px; padding: 0; border: none; }}
.lp-point.actif {{ background: #ffffff; }}
.panneau.spotlight {{ border-radius: 14px; padding: 8px 12px; background: {'rgba(240,240,240,0.88)' if clair else 'rgba(36,36,36,0.88)'}; }}
.panneau.spotlight .recherche {{ background: transparent; border: none; box-shadow: none; min-height: 44px; font-size: 22px; }}
.panneau.spotlight .recherche text {{ font-size: 22px; }}
/* menu « Démarrer » quand on y accède quand même (clic droit sur le Launchpad) */
.panneau {{ border-radius: 12px; }}
button.app {{ border-radius: 10px; }}
.menu-pied {{ border-top: 1px solid {bord}; }}
button.tuile {{ border-radius: 12px; background: {'rgba(255,255,255,0.7)' if clair else 'rgba(255,255,255,0.08)'}; border: none; box-shadow: 0 1px 2px rgba(0,0,0,0.12); }}
button.tuile.on {{ background: {A}; }}
.notif, .toast {{ border-radius: 14px; background: {'rgba(246,246,246,0.88)' if clair else 'rgba(44,44,44,0.88)'}; }}
"""


# --------------------------------------------------------------------------------------------- CSS Paramètres et applis XIII
def css_parametres(p):
    tx, A, att, bord = p["texte"], p["accent"], p["attenue"], p["bord"]; clair = p["clair"]
    if p["imitation"] == "onze":
        return f"""
window.parametres {{ background: {'#f3f3f3' if clair else '#202020'}; }}
.nav {{ background: transparent; border-right: none; }}
.nav-titre {{ font-size: 14px; font-weight: 400; color: {tx}; }}
button.nav-item {{ border-radius: 4px; padding: 7px 10px; }}
button.nav-item:hover {{ background: {'rgba(0,0,0,0.04)' if clair else 'rgba(255,255,255,0.06)'}; }}
button.nav-item.sel {{ background: {'rgba(0,0,0,0.055)' if clair else 'rgba(255,255,255,0.08)'}; }}
button.nav-item.sel label {{ color: {tx}; font-weight: 400; }}
.nav-barre.sel {{ background: {A}; min-height: 16px; min-width: 3px; }}
.page-titre {{ font-size: 28px; font-weight: 600; color: {tx}; letter-spacing: -0.2px; }}
button.fil-lien label {{ font-size: 28px; font-weight: 600; color: {att}; }}
.reglage {{ background: {'#ffffff' if clair else '#2b2b2b'}; border: 1px solid {'rgba(0,0,0,0.06)' if clair else 'rgba(0,0,0,0.2)'}; border-radius: 4px; margin-bottom: 1px; padding: 14px 16px; min-height: 44px; }}
button.reglage:hover {{ background: {'#f9f9f9' if clair else '#323232'}; border-color: {'rgba(0,0,0,0.06)' if clair else 'rgba(0,0,0,0.2)'}; }}
.reglage-titre {{ font-weight: 400; font-size: 14px; }}
.reglage-sous {{ font-size: 12px; }}
.groupe-titre {{ font-weight: 600; font-size: 14px; }}
.hero {{ background: {'#ffffff' if clair else '#2b2b2b'}; border-radius: 8px; border: 1px solid {bord}; box-shadow: none; }}
.hero-grand {{ font-size: 20px; font-weight: 600; color: {tx}; }}
.info-bulle {{ background: {'#f6f6f6' if clair else '#2b2b2b'}; border-color: {bord}; border-radius: 4px; }}
button.vignette.sel {{ border-color: {A}; }}
"""
    return f"""
window.parametres {{ background: {'#ececec' if clair else '#1e1e1e'}; }}
.nav {{ background: {'rgba(232,232,232,0.92)' if clair else 'rgba(42,42,42,0.92)'}; border-right: 1px solid {bord}; }}
.nav-titre {{ font-size: 13px; font-weight: 700; color: {tx}; }}
button.nav-item {{ border-radius: 6px; padding: 4px 8px; }}
button.nav-item:hover {{ background: transparent; }}
button.nav-item.sel {{ background: {A}; }}
button.nav-item.sel label {{ color: #ffffff; font-weight: 500; }}
.nav-barre, .nav-barre.sel {{ background: transparent; min-width: 0; }}
.page-titre {{ font-size: 15px; font-weight: 700; color: {tx}; }}
button.fil-lien label {{ font-size: 15px; font-weight: 700; color: {att}; }}
.reglage {{ background: {'#ffffff' if clair else '#2c2c2c'}; border: none; border-radius: 0; border-bottom: 1px solid {'rgba(0,0,0,0.06)' if clair else 'rgba(255,255,255,0.06)'}; padding: 9px 12px; min-height: 30px; }}
.groupe > .reglage:first-child, .reglage:first-child {{ border-top-left-radius: 10px; border-top-right-radius: 10px; }}
.groupe > .reglage:last-child, .reglage:last-child {{ border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; border-bottom: none; }}
button.reglage:hover {{ background: {'#fafafa' if clair else '#323232'}; }}
.reglage-titre {{ font-weight: 400; font-size: 13px; }}
.reglage-sous {{ font-size: 11.5px; }}
.groupe-titre {{ font-weight: 700; font-size: 13px; margin-top: 18px; }}
.hero {{ background: {'#ffffff' if clair else '#2c2c2c'}; border-radius: 10px; border: none; box-shadow: none; }}
.hero-grand {{ font-size: 17px; font-weight: 700; color: {tx}; }}
.info-bulle {{ background: {'rgba(0,0,0,0.04)' if clair else 'rgba(255,255,255,0.05)'}; border: none; border-radius: 8px; }}
"""


def css_gtk3(p):
    """Retouches du thème GTK 3 généré (Fichiers, Mousepad, Firefox…) pour l'imitation."""
    clair = p["clair"]; A = p["accent"]
    if p["imitation"] == "onze":
        return f"""
* {{ font-family: {p['police_css']}; }}
headerbar, .titlebar {{ background: {'#f3f3f3' if clair else '#202020'}; border-bottom: none; min-height: 40px; }}
headerbar .title {{ font-weight: 400; color: {p['texte']}; }}
button {{ border-radius: 4px; }}
button.suggested-action, button.default {{ border-radius: 4px; }}
entry {{ border-radius: 4px; box-shadow: inset 0 -1px {A}; }}
.sidebar row:selected, placessidebar row:selected {{ background: {'rgba(0,0,0,0.06)' if clair else 'rgba(255,255,255,0.08)'}; color: {p['texte']}; box-shadow: inset 3px 0 {A}; }}
menu, .menu, popover, .context-menu {{ border-radius: 8px; border-color: {'rgba(0,0,0,0.12)' if clair else 'rgba(255,255,255,0.12)'}; }}
menuitem:hover, menu menuitem:hover {{ background: {'rgba(0,0,0,0.05)' if clair else 'rgba(255,255,255,0.07)'}; color: {p['texte']}; border-radius: 4px; }}
"""
    return f"""
* {{ font-family: {p['police_css']}; }}
headerbar, .titlebar {{ background: {'#e9e9e9' if clair else '#2b2b2b'}; border-bottom: 1px solid {'rgba(0,0,0,0.10)' if clair else 'rgba(0,0,0,0.5)'}; min-height: 38px; }}
headerbar .title {{ font-weight: 700; color: {p['texte']}; }}
button {{ border-radius: 6px; }}
button.suggested-action, button.default {{ border-radius: 6px; }}
.sidebar, placessidebar, stacksidebar {{ background: {'#e8e8e8' if clair else '#2a2a2a'}; }}
.sidebar row:selected, placessidebar row:selected {{ background: {'rgba(0,0,0,0.10)' if clair else 'rgba(255,255,255,0.12)'}; color: {p['texte']}; border-radius: 6px; }}
menu, .menu, popover, .context-menu {{ border-radius: 8px; }}
menuitem:hover, menu menuitem:hover {{ background: {A}; color: #ffffff; border-radius: 4px; }}
"""


# --------------------------------------------------------------------------------------------- fenêtres (labwc)
def _svg(corps, l=24, h=24):
    return '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">%s</svg>' % (l, h, l, h, corps)


def boutons_labwc(imit, clair):
    """Images des boutons de fenêtre : {nom de fichier: svg}."""
    f = {}
    if imit == "onze":
        c = "#1b1b1b" if clair else "#ffffff"; ci = "#9a9a9a" if clair else "#8a8a8a"
        glyphes = {"iconify": '<path d="M7 12.5h10" stroke="{c}" stroke-width="1"/>',
                   "max": '<rect x="7.5" y="7.5" width="9" height="9" rx="1.5" fill="none" stroke="{c}" stroke-width="1"/>',
                   "max_toggled": '<rect x="7.5" y="9.5" width="7" height="7" rx="1.2" fill="none" stroke="{c}" stroke-width="1"/><path d="M9.5 9.5V8.7c0-.7.5-1.2 1.2-1.2h4.6c.7 0 1.2.5 1.2 1.2v4.6c0 .7-.5 1.2-1.2 1.2h-.8" fill="none" stroke="{c}" stroke-width="1"/>',
                   "close": '<path d="M7.5 7.5l9 9M16.5 7.5l-9 9" stroke="{c}" stroke-width="1"/>'}
        fond_survol = "rgba(0,0,0,0.06)" if clair else "rgba(255,255,255,0.08)"
        for n, g in glyphes.items():
            f["%s-active.svg" % n] = _svg(g.format(c=c)); f["%s-inactive.svg" % n] = _svg(g.format(c=ci))
            fs = "#c42b1c" if n == "close" else fond_survol; cs = "#ffffff" if n == "close" else c
            f["%s_hover-active.svg" % n] = _svg('<rect width="24" height="24" fill="%s"/>' % fs + g.format(c=cs))
            f["%s_hover-inactive.svg" % n] = f["%s_hover-active.svg" % n]
    else:
        couleurs = {"close": ("#ff5f57", "#e0443e"), "iconify": ("#febc2e", "#dea123"), "max": ("#28c840", "#1aab29"), "max_toggled": ("#28c840", "#1aab29")}
        glyphes = {"close": '<path d="M9.4 9.4l5.2 5.2M14.6 9.4l-5.2 5.2" stroke="#4d0000" stroke-width="1.3" stroke-linecap="round"/>',
                   "iconify": '<path d="M8.8 12h6.4" stroke="#995700" stroke-width="1.4" stroke-linecap="round"/>',
                   "max": '<path d="M9.2 13.8v-4.6h4.6zM14.8 10.2v4.6h-4.6z" fill="#006500"/>',
                   "max_toggled": '<path d="M12 12V7.6H7.6zM12 12v4.4h4.4z" fill="#006500"/>'}
        gris = "#d1d1d1" if clair else "#5a5a5a"
        for n, (rempli, bord) in couleurs.items():
            pastille = '<circle cx="12" cy="12" r="6.2" fill="%s" stroke="%s" stroke-width="0.6"/>'
            f["%s-active.svg" % n] = _svg(pastille % (rempli, bord))
            f["%s-inactive.svg" % n] = _svg(pastille % (gris, gris))
            f["%s_hover-active.svg" % n] = _svg(pastille % (rempli, bord) + glyphes[n])
            f["%s_hover-inactive.svg" % n] = f["%s_hover-active.svg" % n]
    return f


def themerc(imit, p):
    """Thème labwc complet de l'imitation (écrit dans ~/.local/share/themes/XIII-Onze ou XIII-Mac)."""
    clair = p["clair"]; tx = p["texte"]
    if imit == "onze":
        t, ti = ("#f3f3f3", "#f3f3f3") if clair else ("#202020", "#202020")
        lt, lti = (tx, "#8a8a8a") if clair else (tx, "#9a9a9a")
        return f"""# OS XIII — fenêtres « Façon Windows 11 »
border.width: 1
padding.height: 7
window.titlebar.padding.width: 0
window.titlebar.padding.height: 0
window.button.width: 46
window.button.height: 32
window.button.spacing: 0
window.label.text.justify: left
window.active.title.bg.color: {t}
window.inactive.title.bg.color: {ti}
window.active.label.text.color: {lt}
window.inactive.label.text.color: {lti}
window.active.border.color: {'#cfcfcf' if clair else '#3c3c3c'}
window.inactive.border.color: {'#dcdcdc' if clair else '#333333'}
window.active.button.unpressed.image.color: {tx}
window.inactive.button.unpressed.image.color: {lti}
window.active.shadow.size: 22
window.inactive.shadow.size: 12
window.active.shadow.color: {'#00000038' if clair else '#00000090'}
window.inactive.shadow.color: {'#0000001c' if clair else '#00000060'}
menu.overlap.x: 0
menu.items.bg.color: {'#f9f9f9' if clair else '#2c2c2c'}
menu.items.text.color: {tx}
menu.items.active.bg.color: {'#ececec' if clair else '#383838'}
menu.items.active.text.color: {tx}
menu.border.width: 1
menu.border.color: {'#d6d6d6' if clair else '#3c3c3c'}
menu.separator.color: {'#e5e5e5' if clair else '#3a3a3a'}
menu.items.padding.x: 12
menu.items.padding.y: 6
osd.bg.color: {'#f9f9f9' if clair else '#2c2c2c'}
osd.border.color: {'#d6d6d6' if clair else '#3c3c3c'}
osd.label.text.color: {tx}
window.switcher.width: 600
"""
    t, ti = ("#e8e8e8", "#f6f6f6") if clair else ("#2b2b2b", "#262626")
    return f"""# OS XIII — fenêtres « Façon macOS »
border.width: 1
padding.height: 6
window.titlebar.padding.width: 6
window.titlebar.padding.height: 0
window.button.width: 20
window.button.height: 26
window.button.spacing: 0
window.label.text.justify: center
window.active.title.bg.color: {t}
window.inactive.title.bg.color: {ti}
window.active.label.text.color: {'#4d4d4d' if clair else '#dfdfdf'}
window.inactive.label.text.color: {'#aaaaaa' if clair else '#7a7a7a'}
window.active.border.color: {'#c8c8c8' if clair else '#111111'}
window.inactive.border.color: {'#d8d8d8' if clair else '#1a1a1a'}
window.active.button.unpressed.image.color: #ff5f57
window.inactive.button.unpressed.image.color: #d1d1d1
window.active.shadow.size: 28
window.inactive.shadow.size: 16
window.active.shadow.color: {'#00000045' if clair else '#000000a0'}
window.inactive.shadow.color: {'#00000022' if clair else '#00000070'}
menu.items.bg.color: {'#f2f2f2' if clair else '#2b2b2b'}
menu.items.text.color: {tx}
menu.items.active.bg.color: {p['accent']}
menu.items.active.text.color: #ffffff
menu.border.width: 1
menu.border.color: {'#cfcfcf' if clair else '#454545'}
menu.separator.color: {'#dcdcdc' if clair else '#454545'}
menu.items.padding.x: 10
menu.items.padding.y: 3
osd.bg.color: {'#f2f2f2' if clair else '#2b2b2b'}
osd.border.color: {'#cfcfcf' if clair else '#454545'}
osd.label.text.color: {tx}
window.switcher.width: 600
"""


def ecrire_theme_labwc(imit, p, ecrire):
    """~/.local/share/themes/XIII-Onze (ou XIII-Mac)/openbox-3 : themerc + boutons. Renvoie le nom du thème."""
    from gi.repository import GLib
    nom = {"onze": "XIII-Onze", "macos": "XIII-Mac"}[imit]
    d = os.path.join(GLib.get_user_data_dir(), "themes", nom, "openbox-3")
    ecrire(os.path.join(d, "themerc"), themerc(imit, p))
    for f, svg in boutons_labwc(imit, p["clair"]).items(): ecrire(os.path.join(d, f), svg)
    return nom


def rc_labwc(imit, p):
    """Réglages de rc.xml : nom du thème, disposition des boutons, police du titre, arrondis."""
    if imit == "onze":
        return dict(nom="XIII-Onze", layout="icon:iconify,max,close", police=("Selawik", "10", "normal"), rayon="8")
    if imit == "macos":
        return dict(nom="XIII-Mac", layout="close,iconify,max:", police=("Inter", "10", "bold"), rayon="10")
    return dict(nom="XIII", layout="icon:iconify,max,close", police=("IBM Plex Sans", "10", "bold"), rayon=None)


def disposition_gtk(imit):
    """Boutons des applis qui dessinent leur propre barre de titre (GTK, Firefox…)."""
    if imit == "macos": return "close,minimize,maximize:menu", "close,minimize,maximize:appmenu"
    return "menu:minimize,maximize,close", "appmenu:minimize,maximize,close"


# --------------------------------------------------------------------------------------------- fonds d'écran dessinés
def fond(imit, clair, chemin, W=2560, H=1440):
    """Fond d'écran original (rubans de lumière bleue pour Windows 11, collines au crépuscule pour macOS), en PNG."""
    import cairo
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H); cr = cairo.Context(s)
    def rgb(h, a=1): h = h.lstrip("#"); return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)
    if imit == "onze":
        g = cairo.LinearGradient(0, 0, W, H)
        for k, c in ((0, "#dbe7f4" if clair else "#06101f"), (.55, "#c4d7ee" if clair else "#0b1d3a"), (1, "#a9c4e6" if clair else "#03070f")): g.add_color_stop_rgba(k, *rgb(c))
        cr.set_source(g); cr.paint()
        # rubans : larges courbes translucides qui se croisent au centre
        rubans = [("#1a5fd0", "#7cc0ff", .55, -0.10), ("#0f4fb8", "#4aa8ff", .45, 0.05), ("#2b74e8", "#a6d6ff", .40, 0.18),
                  ("#0a3c9a", "#3d8bfd", .50, 0.30), ("#3d8bfd", "#c9e6ff", .30, -0.22)]
        for i, (c1, c2, a, d) in enumerate(rubans):
            cr.save(); cr.translate(W / 2, H / 2); cr.rotate(d * math.pi); cr.translate(-W / 2, -H / 2)
            lg = cairo.LinearGradient(0, H * .3, W, H * .7)
            lg.add_color_stop_rgba(0, *rgb(c1, 0)); lg.add_color_stop_rgba(.45, *rgb(c1, a)); lg.add_color_stop_rgba(.55, *rgb(c2, a * (1.1 if clair else .9)))
            lg.add_color_stop_rgba(1, *rgb(c2, 0))
            e = H * (.10 + .025 * i)
            cr.move_to(-W * .1, H * .62)
            cr.curve_to(W * .25, H * .18, W * .55, H * .95, W * 1.1, H * .35)
            cr.line_to(W * 1.1, H * .35 + e)
            cr.curve_to(W * .55, H * .95 + e, W * .25, H * .18 + e, -W * .1, H * .62 + e)
            cr.close_path(); cr.set_source(lg); cr.fill(); cr.restore()
        rg = cairo.RadialGradient(W * .5, H * .5, 0, W * .5, H * .5, W * .45)
        rg.add_color_stop_rgba(0, *rgb("#ffffff", .30 if clair else .10)); rg.add_color_stop_rgba(1, *rgb("#ffffff", 0))
        cr.set_source(rg); cr.paint()
    else:
        ciel = (("#f6c1a4", "#f3d9c9", "#ede4f0") if clair else ("#10142c", "#1d2350", "#3a2f63"))
        g = cairo.LinearGradient(0, 0, 0, H)
        for k, c in zip((0, .45, 1), ciel): g.add_color_stop_rgba(k, *rgb(c))
        cr.set_source(g); cr.paint()
        soleil = cairo.RadialGradient(W * .68, H * .42, 0, W * .68, H * .42, H * .55)
        soleil.add_color_stop_rgba(0, *rgb("#fff4e0" if clair else "#9a7bd6", .85 if clair else .35)); soleil.add_color_stop_rgba(1, *rgb("#fff4e0", 0))
        cr.set_source(soleil); cr.paint()
        couches = (("#e9a58f", "#d98c86", "#b97a95", "#8b6aa6", "#5a5a9c") if clair else ("#3c3a7a", "#2e2c66", "#231f52", "#191640", "#100d2c"))
        for i, c in enumerate(couches):
            base = H * (.52 + i * .1); amp = H * (.06 - i * .006); ph = i * 1.7
            cr.move_to(0, H)
            for x in range(0, W + 41, 40):
                y = base - amp * math.sin(x / W * math.pi * (1.4 + i * .35) + ph) - amp * .45 * math.sin(x / W * math.pi * 5.3 + ph * 2)
                cr.line_to(x, y)
            cr.line_to(W, H); cr.close_path()
            lg = cairo.LinearGradient(0, base - amp, 0, H)
            lg.add_color_stop_rgba(0, *rgb(c)); lg.add_color_stop_rgba(1, *rgb(c, .92))
            cr.set_source(lg); cr.fill()
    os.makedirs(os.path.dirname(chemin), exist_ok=True); s.write_to_png(chemin)
    return chemin


# --------------------------------------------------------------------------------------------- petites images du bureau
def icone_demarrer_onze(A, chemin):
    """Bouton Démarrer : quatre carreaux arrondis (icône générique « applications »), dégradé de la couleur d'accent."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0" stop-color="{a}" stop-opacity=".78"/><stop offset="1" stop-color="{a}"/></linearGradient></defs>'
           '<rect x="2" y="2" width="9.4" height="9.4" rx="1.6" fill="url(#g)"/><rect x="12.6" y="2" width="9.4" height="9.4" rx="1.6" fill="url(#g)"/>'
           '<rect x="2" y="12.6" width="9.4" height="9.4" rx="1.6" fill="url(#g)"/><rect x="12.6" y="12.6" width="9.4" height="9.4" rx="1.6" fill="url(#g)"/></svg>').format(a=A)
    os.makedirs(os.path.dirname(chemin), exist_ok=True); open(chemin, "w").write(svg); return chemin


def icone_launchpad(chemin):
    """Tuile « toutes les applications » du Dock : grille de pastilles colorées sur fond gris (dessin original)."""
    cols = ["#ff6b6b", "#ffa94d", "#ffd43b", "#69db7c", "#38d9a9", "#4dabf7", "#748ffc", "#da77f2", "#f783ac"]
    p = "".join('<rect x="%.1f" y="%.1f" width="11" height="11" rx="3" fill="%s"/>' % (12 + (i % 3) * 14.5, 12 + (i // 3) * 14.5, c) for i, c in enumerate(cols))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><defs><linearGradient id="f" x1="0" y1="0" x2="0" y2="1">'
           '<stop offset="0" stop-color="#f4f4f6"/><stop offset="1" stop-color="#c9c9ce"/></linearGradient></defs>'
           '<rect x="3" y="3" width="58" height="58" rx="13" fill="url(#f)"/>' + p + '</svg>')
    os.makedirs(os.path.dirname(chemin), exist_ok=True); open(chemin, "w").write(svg); return chemin
