# OS XIII — thèmes (Sombre, Clair, Sobre), couleur d'accent, CSS du bureau et des Paramètres,
# application du thème au reste du système (GTK3/4, fenêtres labwc, verrouillage).
# Application développée par Matthieu Lamotte.
import os, subprocess, re
from gi.repository import GLib, Gdk, GdkPixbuf

LUCIDE = "/usr/share/xiii/lucide"
ACCENTS = [("Cuivre XIII", "#f0b378"), ("Ambre", "#f5a623"), ("Corail", "#ff7a59"), ("Rouge régie", "#e57373"),
           ("Framboise", "#e05a8a"), ("Prune", "#ba68c8"), ("Lavande", "#9fa8ff"), ("Bleu", "#4fc3f7"),
           ("Océan", "#3d8bfd"), ("Turquoise", "#26c6b5"), ("Vert", "#81c784"), ("Citron", "#d4e157"),
           ("Ardoise", "#b0bec5"), ("Blanc", "#f2f2f2")]
# Thèmes de la Suite XIII (mêmes noms et couleurs que ⚙️ › Affichage › Thème de la suite)
THEMES = [("sombre", "Sombre", "Verre sombre, lueur cuivre — le thème signature de la suite"),
          ("clair", "Clair", "Papier chaud, verre beige, lueur ambre"),
          ("auto", "Auto", "Clair le jour, sombre la nuit (lever et coucher du soleil)"),
          ("sobre", "Sobre", "Noir mat, lignes fines, sans verre ni lueur"),
          ("sobrec", "Sobre clair", "Le Sobre en blanc cassé"),
          ("w2k", "Win 2000", "Gris classique, bleu marine, angles droits"),
          ("xp", "Win XP", "Beige Luna, bleu XP"),
          ("mac9", "Mac OS 9", "Platinum gris et violet-bleu"),
          ("cyber", "Cyberpunk", "Nuit violette, néons cyan et rose"),
          ("term", "Terminal", "Phosphore vert sur noir"),
          ("gb", "Game Boy", "Quatre verts, pixels"),
          ("regie", "Régie nuit", "Rouge sur noir : ne fatigue pas les yeux en régie"),
          ("soleil", "Plein soleil", "Contraste maximal, lisible en extérieur"),
          ("rainbow", "Rainbow", "Nuit violette, barre arc-en-ciel"),
          ("sepia", "Pellicule", "Sépia, papier, machine à écrire"),
          ("perso", "Thème perso", "Vos couleurs, vos arrondis, vos ombres")]
NOMS_THEMES = {k: n for k, n, _ in THEMES}

# fond, panneau, carte, carte2, texte, atténué, bord, accent imposé (None = couleur d'accent choisie), arrondi, police, verre, effet
SKINS = {
    "sombre": dict(fond="#1e1e1e", panneau="#1c1b1a", carte="#2a2928", carte2="#232221", texte="#eee9e3", attenue="#9b938a", bord="rgba(255,255,255,0.08)", acc=None, r=14, verre=True),
    "clair": dict(fond="#eef0f2", panneau="#faf9f7", carte="#ffffff", carte2="#f3f1ee", texte="#1d1b19", attenue="#6d675f", bord="rgba(0,0,0,0.09)", acc=None, r=14, verre=True, clair=True),
    "sobre": dict(fond="#0e0f12", panneau="#121317", carte="#16171b", carte2="#121317", texte="#ececee", attenue="#a3a6ad", bord="#2a2c32", acc=None, r=8, plat=True),
    "sobrec": dict(fond="#f6f5f2", panneau="#ffffff", carte="#ffffff", carte2="#f1efeb", texte="#1b1c1f", attenue="#555960", bord="#d5d1c9", acc=None, r=8, plat=True, clair=True),
    "w2k": dict(fond="#3a6ea5", panneau="#d4d0c8", carte="#e4e1da", carte2="#d4d0c8", texte="#000000", attenue="#404040", bord="#808080", acc="#0a246a", r=0, plat=True, clair=True, police="Tahoma"),
    "xp": dict(fond="#ece9d8", panneau="#fffffe", carte="#ffffff", carte2="#f4f3ee", texte="#000000", attenue="#555555", bord="#7f9db9", acc="#0a5fd8", r=6, plat=True, clair=True, police="Tahoma"),
    "mac9": dict(fond="#dddddd", panneau="#eeeeee", carte="#f4f4f4", carte2="#e4e4e4", texte="#000000", attenue="#555555", bord="#888888", acc="#3333cc", r=2, plat=True, clair=True),
    "cyber": dict(fond="#0d0221", panneau="#140533", carte="#1d0a45", carte2="#150638", texte="#e0f7ff", attenue="#8b7fb8", bord="rgba(255,42,109,0.55)", acc="#05d9e8", acc2="#ff2a6d", r=4, verre=True, police="Rajdhani", neon=True),
    "term": dict(fond="#000000", panneau="#030a03", carte="#061206", carte2="#020802", texte="#33ff66", attenue="#1a9e3c", bord="#1f7a35", acc="#33ff66", r=0, plat=True, police="IBM Plex Mono", phosphore=True),
    "gb": dict(fond="#9bbc0f", panneau="#8bac0f", carte="#9bbc0f", carte2="#8bac0f", texte="#0f380f", attenue="#306230", bord="#0f380f", acc="#0f380f", r=0, plat=True, clair=True, police="Pixelify Sans", pixel=True),
    "regie": dict(fond="#000000", panneau="#0a0000", carte="#140000", carte2="#0a0000", texte="#ff3b30", attenue="#992018", bord="#5a0f0a", acc="#ff3b30", r=8, plat=True),
    "soleil": dict(fond="#ffffff", panneau="#ffffff", carte="#ffffff", carte2="#f2f2f2", texte="#000000", attenue="#222222", bord="#000000", acc="#0033cc", r=6, plat=True, clair=True, fort=True),
    "rainbow": dict(fond="#1a1033", panneau="#241747", carte="#2e1f5a", carte2="#261a4d", texte="#ffffff", attenue="#bfb2e6", bord="#7d5fd6", acc="#ffd166", r=14, verre=True, arcenciel=True),
    "sepia": dict(fond="#e9dcc2", panneau="#f4ead6", carte="#fbf5e8", carte2="#eadcbf", texte="#3b2a1a", attenue="#7a6248", bord="#b49a74", acc="#8a4b14", r=4, plat=True, clair=True, police="Courier Prime"),
}
# thème perso : départs identiques à la suite (⚙️ › Affichage › Thème perso)
DEPARTS = [
    dict(name="Minuit bleu", bg="#0d1320", panel="#16203a", text="#e6ecf7", accent="#4fc3f7", radius="m", shadow="m", glass=0),
    dict(name="Forêt", bg="#0e1612", panel="#17241d", text="#e4efe7", accent="#81c784", radius="l", shadow="m", glass=0),
    dict(name="Ardoise", bg="#16181c", panel="#202329", text="#e8e9ec", accent="#b0bec5", radius="s", shadow="s", glass=0),
    dict(name="Prune", bg="#150f18", panel="#221a27", text="#f0e8f3", accent="#ba68c8", radius="l", shadow="l", glass=.12),
    dict(name="Papier", bg="#f4f1ea", panel="#ffffff", text="#2a2620", accent="#c56f1e", radius="m", shadow="s", glass=0),
    dict(name="Studio", bg="#0a0a0a", panel="#141414", text="#f2f2f2", accent="#e57373", radius="s", shadow="l", glass=0)]


def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def rgb_hex(r, g, b):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in (r, g, b))

def melange(a, b, t):
    A, B = hex_rgb(a), hex_rgb(b)
    return rgb_hex(*(A[i] + (B[i] - A[i]) * t for i in range(3)))

def lum(h):
    r, g, b = hex_rgb(h); return (0.299 * r + 0.587 * g + 0.114 * b) / 255

def sur_accent(a):
    return "#1a1a1a" if lum(a) > .55 else "#ffffff"

def contraste(a, b):
    """Rapport de contraste WCAG entre deux couleurs #rrggbb."""
    def L(h):
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (x / 255 for x in hex_rgb(h)); return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    x, y = sorted((L(a), L(b)), reverse=True); return (x + 0.05) / (y + 0.05)

def lisible(c, fond, mini=4.5):
    """Assombrit (fond clair) ou éclaircit (fond sombre) la couleur jusqu'à un contraste lisible sur le fond."""
    if not (c.startswith("#") and fond.startswith("#")): return c
    vers = "#000000" if lum(fond) > .5 else "#ffffff"
    for i in range(21):
        x = melange(c, vers, i * .05)
        if contraste(x, fond) >= mini: return x
    return vers

def rgba(h, a):
    r, g, b = hex_rgb(h); return "rgba(%d,%d,%d,%s)" % (r, g, b, a)


def jour():
    """Vrai entre le lever et le coucher du soleil (thème Auto), d'après la position météo ; sinon 7 h – 19 h."""
    import datetime, math
    try:
        from . import config
        c = config.charger(); lat, lon = float(c.get("meteo_lat", 48.85)), float(c.get("meteo_lon", 2.35))
        n = datetime.datetime.now(datetime.timezone.utc); j = n.timetuple().tm_yday
        decl = 23.44 * math.sin(math.radians(360 / 365 * (j - 81)))
        h = math.degrees(math.acos(max(-1, min(1, -math.tan(math.radians(lat)) * math.tan(math.radians(decl))))))
        midi = 12 - lon / 15
        heure = n.hour + n.minute / 60
        return midi - h / 15 <= heure <= midi + h / 15
    except Exception:
        return 7 <= datetime.datetime.now().hour < 19


def theme_effectif(cfg):
    t = cfg.get("theme", "sombre")
    if t == "auto": return "clair" if jour() else "sombre"
    return t if (t in SKINS or t == "perso") else "sombre"


def skin_perso(cfg):
    c = cfg.get("theme_perso") or DEPARTS[0]
    bg, pan, tx = c.get("bg", "#0d1320"), c.get("panel", "#16203a"), c.get("text", "#e6ecf7")
    clair = lum(bg) > .55
    return dict(fond=bg, panneau=pan, carte=melange(pan, tx, .05), carte2=melange(pan, bg, .35), texte=tx, attenue=rgba(tx, .62),
                bord=rgba(tx, .16 if clair else .12), acc=c.get("accent"), r={"s": 3, "m": 8, "l": 16}.get(c.get("radius", "m"), 8),
                verre=float(c.get("glass", 0) or 0) > 0, plat=float(c.get("glass", 0) or 0) == 0, clair=clair, ombre_niv=c.get("shadow", "m"))


def palette(cfg):
    t = theme_effectif(cfg)
    s = skin_perso(cfg) if t == "perso" else SKINS[t]
    A = s.get("acc") or cfg.get("accent", "#f0b378")
    if t in ("sobre", "sobrec") and A.lower() == "#f0b378":
        A = "#ff8a3d" if t == "sobre" else "#c2570c"  # accents du thème Sobre de la suite
    clair = s.get("clair", False)
    verre = cfg.get("transparence", True) and s.get("verre", False)
    contraste = cfg.get("contraste", False)
    al = ".93" if verre else "1"
    p = dict(theme=t, fond=s["fond"], panneau=rgba(s["panneau"], al) if not s["panneau"].startswith("rgba") else s["panneau"], panneau_plein=s["panneau"],
             carte=s["carte"], carte2=s["carte2"], texte=s["texte"], attenue=s["attenue"] if not contraste else s["texte"], bord=s["bord"] if not contraste else rgba(s["texte"] if s["texte"].startswith("#") else "#888888", .55),
             survol=rgba("#000000" if clair else "#ffffff", .06), ombre="rgba(60,40,20,0.18)" if clair else "rgba(0,0,0,0.50)",
             accent_texte=lisible(A, s["carte"] if s["carte"].startswith("#") else s["fond"]), clair=clair)
    # textes atténués toujours lisibles (ZZ : Régie nuit, Game Boy, Pellicule étaient sous le seuil)
    if p["attenue"].startswith("#"):
        for f in (s["panneau"], s["carte2"], s["carte"]):
            if f.startswith("#"): p["attenue"] = lisible(p["attenue"], f)
    p.update(accent=A, accent_survol=melange(A, "#ffffff", 0.18), sur_accent=sur_accent(A), sobre=bool(s.get("plat")), verre=verre,
             rayon="%dpx" % s["r"], rayon_petit="%dpx" % max(0, s["r"] // 2 + (1 if s["r"] else 0)),
             lueur="none" if not verre else "0 0 48px alpha(%s,0.12)" % A,
             police=s.get("police") or cfg.get("police", "IBM Plex Sans"),
             anim="none" if not cfg.get("animations", True) else "all 160ms ease",
             densite={"compact": .7, "aere": 1.35}.get(cfg.get("densite", "normal"), 1.0),
             fort=s.get("fort", False) or contraste, phosphore=s.get("phosphore", False), neon=s.get("neon", False), pixel=s.get("pixel", False),
             arcenciel=s.get("arcenciel", False), acc2=s.get("acc2") or melange(A, "#ff7a30", .45))
    # glassglow (Sombre, Clair, Cyberpunk, Rainbow, perso vitré) : barres et panneaux en verre teinté de l'accent, lueur ambre
    g1, g2 = melange(A, "#f0b429", .45), melange(A, "#ff8a3d", .45)
    p["pilule"] = "linear-gradient(135deg, %s, %s)" % (g1, g2) if verre else A
    p["pilule_lueur"] = "0 0 18px %s" % rgba(g1, .38) if verre else "none"
    if p["arcenciel"]:
        p["barre_fond"] = "linear-gradient(90deg,#ff595e,#ff924c,#ffca3a,#8ac926,#1982c4,#6a4c93)"
    elif verre and clair:
        p["barre_fond"] = "linear-gradient(180deg, rgba(255,250,240,.92), rgba(246,236,218,.86))"
    elif verre:
        p["barre_fond"] = "linear-gradient(180deg, %s, %s 70%%), %s" % (rgba(g2, .11), rgba(g1, .025), rgba(s["panneau"] if s["panneau"].startswith("#") else "#121010", .86))
    else:
        p["barre_fond"] = s["panneau"]
    p["barre_ligne"] = rgba(g1, .22) if verre else s["bord"]
    p["panneau_verre"] = ("linear-gradient(180deg, %s, transparent 30%%), %s" % (rgba(g2, .06 if not clair else .10), p["panneau"])) if verre else p["panneau"]
    return p

# --------------------------------------------------------------------------------------------- effets propres à certains thèmes
def effets(p):
    e = ""
    if p["phosphore"]: e += "label, entry text {{ text-shadow: 0 0 3px alpha({0},0.45); }}\n".format(p["texte"]).replace("{{", "{").replace("}}", "}")
    if p["fort"]: e += "label { font-weight: 600; }\n"
    if p["neon"]: e += "button.pilule, .panneau, .hero {{ box-shadow: 0 0 14px alpha({0},0.35), 0 0 2px {1}; }}\n".format(p["accent"], p["acc2"]).replace("{{", "{").replace("}}", "}")
    if p["pixel"]: e += "* { -gtk-icon-shadow: none; } label { letter-spacing: 1px; }\n"
    if p["rayon"] == "0px": e += "button, entry, .reglage, .carte, .panneau, popover > contents { border-radius: 0; }\n"
    return e

# --------------------------------------------------------------------------------------------- CSS commun
def css_commun(p):
    return f"""
* {{ font-family: "{p['police']}", "IBM Plex Sans", sans-serif; }}
{effets(p)}{('.titre-astoria, .page-titre, .hero-grand, .panneau-titre, .nav-titre { font-family: Orbitron, Astoria, sans-serif; letter-spacing: 1px; }' if p['neon'] else '')}{('.page-titre, .hero-grand, .panneau-titre, .nav-titre { font-family: "Press Start 2P", Astoria, monospace; font-size: 16px; }' if p['pixel'] else '')}
label {{ color: {p['texte']}; }}
.attenue, .attenue label {{ color: {p['attenue']}; }}
.petit {{ font-size: 11.5px; }}
.titre-astoria {{ font-family: Astoria, "Archivo Black", sans-serif; color: {p['accent_texte']}; }}
.accent {{ color: {p['accent_texte']}; }}
.gras {{ font-weight: 600; }}
.vue-mode {{ background: alpha({p['fond']}, .72); }}
.grand-titre {{ font-size: 26px; font-weight: 700; }}
.tuile-mode {{ background: {p['panneau_verre'] if p['verre'] else p['carte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon']}; padding: 18px 10px; min-height: 110px; transition: background 150ms ease, border-color 150ms ease; }}
.tuile-mode:hover, .tuile-mode:focus-visible {{ background: alpha({p['accent']}, .16); border-color: {p['accent']}; }}
.tuile-plus {{ border-style: dashed; background: transparent; }}
.onglets-mode {{ background: alpha({p['texte']}, .05); border-radius: 999px; padding: 4px; }}
.onglet-mode {{ border-radius: 999px; padding: 6px 16px; background: transparent; border: none; }}
.onglet-mode.actif {{ background: {p['accent']}; }}
.onglet-mode.actif label {{ color: {p['sur_accent']}; }}
.timecode-geant {{ font-family: "IBM Plex Mono", monospace; font-size: 42px; font-weight: 700; color: {p['accent_texte']}; }}
.carte-jeu {{ background: {p['panneau_verre'] if p['verre'] else p['carte']}; border: 2px solid {p['bord']}; border-radius: 22px; padding: 24px; transition: all 160ms ease; }}
.carte-jeu:hover, .carte-jeu:focus-visible {{ border-color: {p['accent']}; box-shadow: 0 0 24px alpha({p['accent']}, .45); }}
.sel-mode {{ background: alpha({p['texte']}, .06); border-radius: 999px; padding: 2px; }}
.sel-mode button {{ border-radius: 999px; padding: 2px 8px; min-height: 22px; }}
.sel-mode button.actif {{ background: alpha({p['accent']}, .16); padding: 2px 12px; }}
.menu-modes .mode-actif {{ background: alpha({p['accent']}, .14); }}
.section {{ font-weight: 600; font-size: 12.5px; color: {p['attenue']}; margin-top: 6px; }}
button {{ transition: {p['anim']}; }}
button.pilule {{ background: {p['pilule']}; color: {p['sur_accent']}; border-radius: {'999px' if p['rayon'] != '0px' else '0'}; padding: 6px 18px; font-weight: 700; border: none; box-shadow: {p['pilule_lueur']}; }}
button.pilule label {{ color: {p['sur_accent']}; }}
button.pilule:hover {{ background: {p['accent_survol']}; }}
button.bascule-mode:checked {{ background: {p['accent']}; color: {p['sur_accent']}; font-weight: 700; }}
button.bascule-mode:checked label {{ color: {p['sur_accent']}; }}
button.pilule:disabled {{ opacity: .5; }}
button.fantome {{ background: transparent; border: 1px solid alpha({p['accent']},0.55); border-radius: 999px; padding: 4px 14px; box-shadow: none; }}
button.fantome label {{ color: {p['accent_texte']}; }}
button.fantome:hover {{ background: alpha({p['accent']},0.12); }}
button.plat {{ background: transparent; border: none; box-shadow: none; border-radius: {p['rayon_petit']}; padding: 6px 8px; }}
button.plat:hover {{ background: {p['survol']}; }}
button.danger label {{ color: #e57373; }}
entry, spinbutton, dropdown > button, .champ {{ background: {p['carte']}; color: {p['texte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon_petit']}; min-height: 32px; box-shadow: none; }}
entry:focus-within {{ border-color: {p['accent']}; box-shadow: 0 0 0 2px alpha({p['accent']},0.22); }}
entry text {{ color: {p['texte']}; }}
dropdown > button {{ padding: 2px 10px; }}
popover > contents {{ background: {p['panneau_plein']}; border: 1px solid alpha({p['accent']},0.30); border-radius: {p['rayon_petit']}; color: {p['texte']}; }}
popover modelbutton:hover, popover row:hover {{ background: alpha({p['accent']},0.16); }}
popover listview row:selected {{ background: alpha({p['accent']},0.22); }}
scale trough {{ background: alpha({p['texte']},0.16); min-height: 4px; border-radius: 3px; border: none; }}
scale highlight {{ background: {p['accent']}; border-radius: 3px; border: none; min-height: 4px; }}
scale slider {{ background: {p['accent']}; border: 3px solid {p['panneau_plein']}; min-width: 14px; min-height: 14px; border-radius: 50%; box-shadow: 0 0 0 1px alpha({p['accent']},0.55); margin: -7px; }}
scale highlight, scale trough {{ min-width: 4px; }}
switch {{ background: alpha({p['texte']},0.18); border-radius: 999px; border: none; min-height: 22px; }}
switch:checked {{ background: {p['accent']}; }}
switch slider {{ background: #ffffff; border-radius: 50%; min-width: 16px; min-height: 16px; margin: 3px; box-shadow: none; border: none; }}
checkbutton check:checked, radio:checked, checkbutton radio:checked {{ background: {p['accent']}; border-color: {p['accent']}; color: {p['sur_accent']}; }}
progressbar trough {{ background: alpha({p['texte']},0.14); border-radius: 3px; min-height: 6px; }}
progressbar progress {{ background: {p['accent']}; border-radius: 3px; min-height: 6px; }}
levelbar block.filled {{ background: {p['accent']}; }}
levelbar block.empty {{ background: alpha({p['texte']},0.14); }}
scrollbar slider {{ background: alpha({p['texte']},0.25); border-radius: 999px; min-width: 4px; }}
scrollbar {{ background: transparent; }}
calendar {{ background: transparent; border: none; color: {p['texte']}; }}
calendar > header {{ border: none; }}
calendar > grid > label.day-number:selected {{ background: {p['accent']}; color: {p['sur_accent']}; border-radius: 50%; }}
calendar > grid > label.today {{ box-shadow: inset 0 0 0 2px {p['accent']}; border-radius: 50%; }}
calendar > grid > label.other-month {{ color: alpha({p['texte']},0.3); }}
tooltip {{ background: {p['panneau_plein']}; border: 1px solid alpha({p['accent']},0.4); border-radius: 6px; color: {p['texte']}; }}
tooltip label {{ color: {p['texte']}; }}
"""

# --------------------------------------------------------------------------------------------- CSS du bureau
def css_shell(cfg):
    p = palette(cfg)
    return css_commun(p) + f"""
window.xiii-surface {{ background: transparent; }}
.barre {{ background: {p['barre_fond'] if not p['arcenciel'] else p['panneau']}; border-top: 1px solid {p['barre_ligne']}; box-shadow: 0 -1px 0 {p['barre_ligne']}; }}
.haut {{ background: {p['barre_fond']}; border-bottom: 1px solid {p['barre_ligne']}; }}
.haut-secteur {{ border-left: 1px solid {p['bord']}; margin-left: 4px; padding-left: 4px; }}
.haut-survol {{ font-size: 12px; font-weight: 600; margin-left: 4px; }}
.pastille-nom {{ background: alpha({p['accent']},0.18); border-radius: 999px; padding: 0 8px; }}
.pastille-nom label {{ color: {p['accent_texte']}; font-weight: 700; font-size: 11.5px; }}
.haut-titre {{ font-weight: 600; font-size: 12.5px; }}
.haut-logo {{ font-family: Astoria, sans-serif; font-size: 17px; color: {p['accent_texte']}; padding: 0 6px; }}
button.tb {{ background: transparent; border: none; box-shadow: none; border-radius: {p['rayon_petit']}; padding: 2px 6px; min-height: 40px; min-width: 40px; }}
button.tb:hover {{ background: {p['survol']}; }}
button.tb.actif {{ background: alpha({p['texte']},0.09); }}
button.tb.ouvert {{ background: alpha({p['accent']},0.14); }}
button.hb {{ background: transparent; border: none; box-shadow: none; border-radius: 6px; padding: 0 8px; min-height: 26px; }}
button.hb:hover {{ background: {p['survol']}; }}
button.hb.ouvert {{ background: alpha({p['accent']},0.16); }}
button.hb label {{ font-size: 12.5px; }}
.tb-ind {{ background: {p['attenue']}; min-height: 3px; min-width: 6px; border-radius: 2px; transition: min-width 220ms cubic-bezier(.2,.9,.3,1.2), background 200ms ease; }}
.tb-ind.actif {{ background: {p['accent']}; min-width: 16px; }}
.tb-ind.vide {{ background: transparent; }}
progressbar.tb-progres {{ min-width: 26px; }}
progressbar.indic-barre, progressbar.indic-barre > trough {{ padding: 0; margin: 0; border: none; outline: none; background-image: none; box-shadow: none; }}
progressbar.indic-barre > trough {{ min-height: 4px; min-width: 24px; border-radius: 2px; background-color: alpha({p['texte']}, .2); }}
progressbar.indic-barre > trough > progress {{ min-height: 4px; border: none; background-image: none; box-shadow: none; border-radius: 2px; background-color: {p['accent']}; }}
progressbar.tb-progres, progressbar.tb-progres > trough {{ padding: 0; margin: 0; border: none; outline: none; background-image: none; }}
progressbar.tb-progres > trough {{ min-height: 3px; min-width: 26px; background-color: alpha({p['texte']}, .15); border-radius: 2px; box-shadow: none; }}
progressbar.tb-progres > trough > progress {{ min-height: 3px; border: none; background-image: none; background-color: {p['accent']}; border-radius: 2px; box-shadow: 0 0 6px alpha({p['accent']}, .9); }}
.tb.tb-onglet {{ min-width: 150px; padding: 0 10px; }}
.tb.tb-onglet.actif {{ background: alpha({p['accent']}, .14); }}
picture.miniature {{ border-radius: {p['rayon_petit']}; border: 1px solid {p['bord']}; }}
.bureau-puce {{ padding: 10px; transition: background 150ms ease; }}
.bureau-puce.survol-depot, .bureau-puce:hover {{ background: alpha({p['accent']}, .22); border-color: {p['accent']}; }}
.horloge-h {{ font-weight: 600; font-size: 12.5px; }}
.horloge-d {{ font-size: 11px; color: {p['attenue']}; }}
.badge {{ background: {p['accent']}; color: {p['sur_accent']}; border-radius: 999px; font-size: 10px; font-weight: 700; min-width: 16px; min-height: 16px; padding: 0 4px; }}
.meteo-t {{ font-weight: 600; font-size: 12.5px; }}
.panneau {{ background: {p['panneau_verre']}; border: 1px solid alpha({p['accent']},0.28); border-radius: {p['rayon']}; box-shadow: 0 12px 40px {p['ombre']}{', ' + p['lueur'] if p['lueur'] != 'none' else ''}; padding: 16px; }}
.panneau-titre {{ font-family: Astoria, sans-serif; font-size: 22px; color: {p['accent_texte']}; }}
.filigrane {{ font-family: Astoria, sans-serif; font-size: 72px; color: alpha({p['accent']},0.06); }}
.recherche {{ background: {p['carte']}; border-radius: 999px; border: 1px solid {p['bord']}; padding: 4px 14px; min-height: 38px; }}
.recherche:focus-within {{ border-color: {p['accent']}; box-shadow: 0 0 0 2px alpha({p['accent']},0.22); }}
.recherche text {{ color: {p['texte']}; }}
button.app {{ background: transparent; border: none; box-shadow: none; border-radius: {p['rayon_petit']}; padding: 10px 2px 8px 2px; }}
button.app:hover {{ background: {p['survol']}; }}
button.app:focus-visible {{ box-shadow: inset 0 0 0 2px alpha({p['accent']},0.7); }}
.app-nom {{ font-size: 11.5px; }}
button.cat {{ background: {p['carte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon_petit']}; padding: 10px; box-shadow: none; }}
button.cat:hover {{ border-color: alpha({p['accent']},0.5); background: alpha({p['accent']},0.07); }}
.cat-nom {{ font-weight: 600; font-size: 12px; }}
button.ligne {{ background: transparent; border: none; box-shadow: none; border-radius: {p['rayon_petit']}; padding: 7px 10px; }}
button.ligne:hover {{ background: {p['survol']}; }}
button.ligne.sel {{ background: alpha({p['accent']},0.15); }}
button.ligne.sel label {{ color: {p['accent_texte']}; }}
.menu-pied {{ border-top: 1px solid {p['bord']}; padding-top: 10px; }}
.avatar {{ background: alpha({p['accent']},0.18); border-radius: 50%; min-width: 34px; min-height: 34px; }}
.avatar label {{ color: {p['accent_texte']}; font-weight: 700; }}
button.tuile {{ background: {p['carte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon_petit']}; padding: 8px 10px; min-height: 52px; box-shadow: none; }}
button.tuile:hover {{ border-color: alpha({p['accent']},0.5); }}
button.tuile.on {{ background: {p['accent']}; border-color: {p['accent']}; }}
button.tuile.on label {{ color: {p['sur_accent']}; }}
.tuile-sous {{ font-size: 10.5px; opacity: .75; }}
.carte {{ background: {p['carte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon_petit']}; padding: 10px 12px; }}
.toast {{ background: {p['panneau']}; border: 1px solid alpha({p['accent']},0.30); border-radius: {p['rayon']}; box-shadow: 0 10px 30px {p['ombre']}; padding: 12px 14px; }}
.notif {{ background: {p['carte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon_petit']}; padding: 10px 12px; }}
.notif-app {{ font-size: 11px; color: {p['attenue']}; font-weight: 600; }}
.notif-titre {{ font-weight: 600; }}
.notif-corps {{ color: {p['attenue']}; font-size: 12.5px; }}
.niveau {{ font-family: "IBM Plex Mono", monospace; font-size: 12px; color: {p['attenue']}; min-width: 38px; }}
.grand {{ font-size: 34px; font-weight: 700; }}
.meteo-grand {{ font-size: 40px; font-weight: 300; }}
.timecode {{ font-family: "IBM Plex Mono", monospace; font-size: 13px; font-weight: 600; color: {p['accent_texte']}; background: alpha({p['accent']},0.10); border-radius: 5px; padding: 1px 8px; }}
.voile-vue {{ background: rgba(0,0,0,0.55); }}
.vue-active {{ border-color: {p['accent']}; }}
.dispo-cadre {{ background: {p['carte2']}; border: 1px solid {p['bord']}; border-radius: 6px; }}
button.dispo-zone {{ background: alpha({p['accent']},0.22); border: 1px solid alpha({p['accent']},0.45); border-radius: 4px; padding: 0; min-height: 0; min-width: 0; box-shadow: none; }}
button.dispo-zone:hover {{ background: {p['accent']}; }}
.icone-bureau {{ border-radius: {p['rayon_petit']}; padding: 6px 2px; }}
.icone-bureau:hover {{ background: rgba(255,255,255,0.10); }}
.icone-bureau label {{ color: #ffffff; text-shadow: 0 1px 3px rgba(0,0,0,0.9); }}
button.emoji {{ font-size: 22px; padding: 2px; min-width: 36px; min-height: 36px; }}
"""

# --------------------------------------------------------------------------------------------- CSS Paramètres
def css_parametres(cfg):
    p = palette(cfg)
    return css_commun(p) + f"""
window.parametres {{ background: {p['fond']}; }}
.nav {{ background: {p['carte2']}; border-right: 1px solid {p['bord']}; }}
.nav-titre {{ font-family: Astoria, sans-serif; font-size: 24px; color: {p['accent_texte']}; }}
button.nav-item {{ background: transparent; border: none; box-shadow: none; border-radius: {p['rayon_petit']}; padding: 8px 10px; }}
button.nav-item:hover {{ background: {p['survol']}; }}
button.nav-item.sel {{ background: alpha({p['accent']},0.14); }}
button.nav-item.sel label {{ color: {p['accent_texte']}; font-weight: 600; }}
.nav-barre {{ background: transparent; min-width: 3px; min-height: 16px; border-radius: 2px; }}
.nav-barre.sel {{ background: {p['accent']}; }}
.page-titre {{ font-family: Astoria, sans-serif; font-size: 32px; color: {p['accent_texte']}; }}
.fil {{ font-size: 15px; color: {p['attenue']}; }}
button.fil-lien {{ background: transparent; border: none; box-shadow: none; padding: 0 2px; }}
button.fil-lien label {{ font-family: Astoria, sans-serif; font-size: 26px; color: {p['attenue']}; }}
button.fil-lien:hover label {{ color: {p['accent_texte']}; }}
.reglage {{ background: {p['carte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon_petit']}; padding: {int(12 * p['densite'])}px 16px; min-height: {int(40 * p['densite'])}px; }}
button.reglage {{ box-shadow: none; }}
button.reglage:hover {{ background: alpha({p['accent']},0.06); border-color: alpha({p['accent']},0.35); }}
.reglage-titre {{ font-weight: 500; }}
.reglage-sous {{ font-size: 12px; color: {p['attenue']}; }}
.groupe {{ margin-bottom: 2px; }}
.groupe-titre {{ font-weight: 600; font-size: 13.5px; margin: 14px 0 6px 2px; }}
.hero {{ background: {p['panneau_verre'] if p['verre'] else p['carte']}; border: 1px solid {('alpha(' + p['accent'] + ',0.25)') if p['verre'] else p['bord']}; border-radius: {p['rayon']}; padding: 16px; box-shadow: {p['lueur'] if p['verre'] else 'none'}; }}
.hero-grand {{ font-family: Astoria, sans-serif; font-size: 26px; color: {p['accent_texte']}; }}
button.pastille {{ border-radius: 50%; min-width: 30px; min-height: 30px; padding: 0; border: 2px solid transparent; box-shadow: none; }}
button.pastille.sel {{ border-color: {p['texte']}; }}
button.vignette {{ padding: 3px; border-radius: {p['rayon_petit']}; border: 2px solid transparent; background: transparent; box-shadow: none; }}
button.vignette.sel {{ border-color: {p['accent']}; }}
button.vignette:hover {{ border-color: alpha({p['accent']},0.5); }}
.apercu-theme {{ border-radius: {p['rayon_petit']}; border: 1px solid {p['bord']}; }}
.mono {{ font-family: "IBM Plex Mono", monospace; font-size: 12px; }}
.journal {{ font-family: "IBM Plex Mono", monospace; font-size: 11px; background: {p['carte2']}; color: {p['attenue']}; }}
.credit {{ font-size: 11px; color: {p['attenue']}; }}
.info-bulle {{ background: alpha({p['accent']},0.10); border: 1px solid alpha({p['accent']},0.35); border-radius: {p['rayon_petit']}; padding: 10px 14px; }}
"""

# --------------------------------------------------------------------------------------------- icônes Lucide teintées
_cache = {}
def icone(nom, taille=20, couleur=None):
    """Gdk.Texture d'une icône Lucide au trait, teintée (accent par défaut)."""
    couleur = couleur or "#f0b378"
    cle = (nom, taille, couleur)
    if cle in _cache: return _cache[cle]
    chemin = os.path.join(LUCIDE, nom + ".svg")
    try:
        svg = open(chemin).read()
    except OSError:
        svg = open(os.path.join(LUCIDE, "circle.svg")).read() if os.path.exists(os.path.join(LUCIDE, "circle.svg")) else \
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/></svg>'
    svg = svg.replace("currentColor", couleur).replace('stroke-width="2"', 'stroke-width="1.75"')
    try:
        ld = GdkPixbuf.PixbufLoader.new_with_type("svg")
        ld.set_size(taille * 2, taille * 2)
        ld.write(svg.encode()); ld.close()
        tex = Gdk.Texture.new_for_pixbuf(ld.get_pixbuf())
    except Exception:
        tex = None
    _cache[cle] = tex
    return tex

def image(nom, taille=20, couleur=None):
    from gi.repository import Gtk
    t = icone(nom, taille, couleur)
    im = Gtk.Image.new_from_paintable(t) if t else Gtk.Image.new_from_icon_name("image-missing")
    im.set_pixel_size(taille)
    return im

# --------------------------------------------------------------------------------------------- application système
def _ecrire(chemin, texte):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w") as f:
        f.write(texte)

FONDS_XIII = {"sombre": "/usr/share/xiii/wallpapers/xiii-sombre.png", "clair": "/usr/share/xiii/wallpapers/xiii-clair.png",
              "sobre": "/usr/share/xiii/wallpapers/xiii-sobre.png"}

FONDS_GENERES = os.path.join(GLib.get_user_data_dir(), "xiii", "fonds-themes")

def fond_theme(cfg):
    """Fond d'écran assorti au thème : fourni (Sombre, Clair, Sobre) ou dessiné (fond du thème, lueur de l'accent, logo XIII en filigrane)."""
    t = theme_effectif(cfg)
    if t in FONDS_XIII and cfg.get("accent", "#f0b378").lower() == "#f0b378":
        return FONDS_XIII[t]
    p = palette(cfg)
    cle = "%s-%s-%s" % (t, p["fond"].lstrip("#"), p["accent"].lstrip("#"))
    f = os.path.join(FONDS_GENERES, cle + ".png")
    if os.path.exists(f): return f
    try:
        import cairo
        W, H = 2560, 1440
        s = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H); cr = cairo.Context(s)
        fr, fg, fb = (v / 255 for v in hex_rgb(p["fond"])); ar, ag, ab = (v / 255 for v in hex_rgb(p["accent"]))
        cr.set_source_rgb(fr, fg, fb); cr.paint()
        if not p["sobre"] or p["verre"]:
            g = cairo.RadialGradient(W * .78, H * .8, 0, W * .78, H * .8, W * .55)
            g.add_color_stop_rgba(0, ar, ag, ab, .16 if not p["clair"] else .12); g.add_color_stop_rgba(1, ar, ag, ab, 0)
            cr.set_source(g); cr.paint()
        if p["arcenciel"]:
            for i, c in enumerate(("#ff595e", "#ff924c", "#ffca3a", "#8ac926", "#1982c4", "#6a4c93")):
                cr.set_source_rgba(*(v / 255 for v in hex_rgb(c)), .55); cr.rectangle(0, H - 36 + i * 6, W, 6); cr.fill()
        if p["phosphore"]:
            cr.set_source_rgba(ar, ag, ab, .045)
            for y in range(0, H, 4): cr.rectangle(0, y, W, 1)
            cr.fill()
        logo = cairo.ImageSurface.create_from_png("/usr/share/xiii/logos/xiii-orange.png")
        lw = W * .072; k = lw / logo.get_width()
        cr.save(); cr.translate(W * .778, H * .738); cr.scale(k, k)
        cr.set_source_rgba(ar, ag, ab, .9 if p["sobre"] and not p["verre"] else .85); cr.mask_surface(logo, 0, 0); cr.restore()
        os.makedirs(FONDS_GENERES, exist_ok=True); s.write_to_png(f)
        return f
    except Exception:
        return FONDS_XIII.get("clair" if p["clair"] else "sombre")

def fond_par_defaut(chemin):
    return chemin in FONDS_XIII.values() or (chemin or "").startswith(FONDS_GENERES)

def fond_assorti(cfg):
    """Si le fond est un fond XIII par défaut, prend celui assorti au thème."""
    if fond_par_defaut(cfg.get("fond")):
        return fond_theme(cfg)
    return cfg.get("fond")

def nom_icones(cfg):
    """Thème d'icônes : XIII (cuivre) ou copie teintée à la couleur d'accent du thème."""
    A = palette(cfg)["accent"].lower()
    if A == "#f0b378": return "XIII"
    dest = os.path.join(GLib.get_user_data_dir(), "icons", "XIII-accent")
    marque = os.path.join(dest, ".accent")
    try:
        if open(marque).read() == A: return "XIII-accent"
    except OSError:
        pass
    import shutil
    shutil.rmtree(dest, True)
    for racine, dossiers, fichiers in os.walk("/usr/share/icons/XIII"):
        rel = os.path.relpath(racine, "/usr/share/icons/XIII"); os.makedirs(os.path.join(dest, rel), exist_ok=True)
        for f in fichiers:
            src = os.path.join(racine, f)
            if f.endswith(".svg"):
                txt = open(src).read().replace("#f0b378", A)
                open(os.path.join(dest, rel, f), "w").write(txt)
            elif f == "index.theme":
                open(os.path.join(dest, rel, f), "w").write(open(src).read().replace("Name=XIII", "Name=XIII-accent"))
    open(marque, "w").write(A)
    return "XIII-accent"


def couleur_pleine(c, fond="#000000"):
    """rgba(…) → #rrggbb (mélangé au fond) pour les logiciels qui n'acceptent que l'hexadécimal."""
    if c.startswith("#"): return c
    m = re.match(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)", c)
    if not m: return fond
    r, g, b = (float(x) for x in m.groups()[:3]); a = float(m.group(4) or 1)
    F = hex_rgb(fond)
    return rgb_hex(r * a + F[0] * (1 - a), g * a + F[1] * (1 - a), b * a + F[2] * (1 - a))


def css_gtk3(p):
    """Thème GTK3 complet (apps GTK3, Firefox, Thunar, écran de connexion) aux couleurs du thème XIII."""
    fond, pan, carte, tx = p["fond"], p["panneau_plein"], p["carte"], p["texte"]
    att = couleur_pleine(p["attenue"], pan); bord = couleur_pleine(p["bord"], pan); A, SA = p["accent"], p["sur_accent"]
    base = carte if p["clair"] else melange(fond, "#000000", .1) if lum(fond) > .05 else melange(fond, "#ffffff", .04)
    r = p["rayon_petit"]
    return f"""/* OS XIII — thème « {NOMS_THEMES.get(p['theme'], p['theme'])} » (généré par Paramètres XIII) */
@import url("resource:///org/gtk/libgtk/theme/Adwaita/gtk-contained{'' if p['clair'] else '-dark'}.css");
@define-color theme_bg_color {pan};
@define-color theme_base_color {base};
@define-color theme_fg_color {tx};
@define-color theme_text_color {tx};
@define-color theme_selected_bg_color {A};
@define-color theme_selected_fg_color {SA};
@define-color insensitive_fg_color {att};
@define-color borders {bord};
@define-color accent_color {A};
* {{ font-family: "{p['police']}", "IBM Plex Sans", sans-serif; }}
window, .background {{ background-color: {pan}; color: {tx}; }}
.view, textview text, iconview, treeview.view, list, row {{ background-color: {base}; color: {tx}; }}
headerbar, .titlebar, toolbar, .toolbar {{ background: {melange(pan, fond, .5)}; color: {tx}; border-bottom: 1px solid alpha({A},0.30); box-shadow: none; }}
headerbar .title {{ font-weight: bold; color: {p['accent_texte']}; }}
label {{ color: {tx}; }}
.dim-label, label.dim-label {{ color: {att}; }}
*:selected, selection, *:selected:focus, row:selected {{ background-color: {A}; color: {SA}; }}
button {{ border-radius: {r}; background: {carte}; color: {tx}; border: 1px solid {bord}; background-image: none; box-shadow: none; text-shadow: none; }}
button:hover {{ background: alpha({A},0.14); border-color: alpha({A},0.5); }}
button.suggested-action, button.default {{ background: {A}; color: {SA}; border-color: {A}; border-radius: {'999px' if r != '0px' else '0'}; font-weight: bold; }}
entry, spinbutton, combobox button {{ background: {base}; color: {tx}; border: 1px solid {bord}; border-radius: {r}; box-shadow: none; }}
entry:focus, spinbutton:focus {{ border-color: {A}; box-shadow: inset 0 0 0 1px {A}; }}
check:checked, radio:checked, switch:checked {{ background: {A}; border-color: {A}; color: {SA}; }}
scale highlight, progressbar progress, levelbar block.filled {{ background: {A}; border-color: {A}; }}
notebook > header {{ background: {melange(pan, fond, .5)}; }}
notebook > header tab:checked {{ box-shadow: inset 0 -2px {A}; color: {p['accent_texte']}; }}
.sidebar, placessidebar, stacksidebar {{ background: {melange(pan, fond, .4)}; }}
.sidebar row:selected, placessidebar row:selected {{ background: alpha({A},0.18); color: {p['accent_texte']}; }}
menu, .menu, popover, .context-menu {{ background: {pan}; color: {tx}; border: 1px solid alpha({A},0.35); }}
menuitem:hover, menu menuitem:hover {{ background: {A}; color: {SA}; }}
tooltip, tooltip.background {{ background: {pan}; color: {tx}; border: 1px solid alpha({A},0.4); }}
link, *:link {{ color: {p['accent_texte']}; }}
scrollbar slider {{ background: alpha({tx},0.28); }}
/* Écran de connexion */
#login_window, #restart_dialog, #shutdown_dialog {{ background: alpha({pan},0.88); border: 1px solid alpha({A},0.45); border-radius: {p['rayon']}; box-shadow: 0 0 60px alpha({A},0.18); padding: 18px; }}
#panel_window {{ background: alpha({pan},0.88); border-bottom: 1px solid alpha({A},0.35); color: {tx}; }}
#login_window #login_button {{ background: {A}; color: {SA}; border-radius: 999px; font-weight: bold; }}
"""


def appliquer_systeme(cfg):
    """Un choix, partout : apps GTK3 / GTK4, Qt (via GTK), Firefox (suit GTK), terminal, fenêtres labwc, verrouillage, icônes."""
    p = palette(cfg); A = p["accent"]; conf = GLib.get_user_config_dir(); data = GLib.get_user_data_dir()
    clair = p["clair"]; dpi = int(96 * 1024 * float(cfg.get("taille_texte", 1.0)))
    anim = "true" if cfg.get("animations", True) else "false"
    curseur = int(cfg.get("curseur_taille", 24))
    police = "%s %d" % (p["police"], 10)
    icones = nom_icones(cfg)
    pan = p["panneau_plein"]; att = couleur_pleine(p["attenue"], pan); bord = couleur_pleine(p["bord"], pan)
    # GTK 3 : thème complet généré
    _ecrire(f"{data}/themes/XIII-perso/gtk-3.0/gtk.css", css_gtk3(p))
    _ecrire(f"{data}/themes/XIII-perso/index.theme", "[Desktop Entry]\nType=X-GNOME-Metatheme\nName=XIII-perso\nComment=Thème XIII généré\n\n[X-GNOME-Metatheme]\nGtkTheme=XIII-perso\n")
    for v in ("3.0", "4.0"):
        _ecrire(f"{conf}/gtk-{v}/settings.ini", f"""[Settings]
gtk-theme-name={'XIII-perso' if v == '3.0' else 'Adwaita'}
gtk-application-prefer-dark-theme={'0' if clair else '1'}
gtk-icon-theme-name={icones}
gtk-font-name={police}
gtk-cursor-theme-name=XIII-curseur
gtk-cursor-theme-size={curseur}
gtk-xft-dpi={dpi}
gtk-enable-animations={anim}
""")
    _ecrire(f"{conf}/gtk-3.0/gtk.css", "/* OS XIII : couleurs dans ~/.local/share/themes/XIII-perso */\n")
    # GTK 4 : couleurs nommées d'Adwaita + réglages de base
    _ecrire(f"{conf}/gtk-4.0/gtk.css", f"""/* OS XIII — thème « {NOMS_THEMES.get(p['theme'], p['theme'])} » (généré par Paramètres XIII) */
@define-color accent_color {p['accent_texte']};
@define-color accent_bg_color {A};
@define-color accent_fg_color {p['sur_accent']};
@define-color window_bg_color {pan};
@define-color window_fg_color {p['texte']};
@define-color view_bg_color {p['carte'] if clair else melange(p['fond'], '#000000', .1)};
@define-color view_fg_color {p['texte']};
@define-color headerbar_bg_color {melange(pan, p['fond'], .5)};
@define-color headerbar_fg_color {p['texte']};
@define-color sidebar_bg_color {melange(pan, p['fond'], .4)};
@define-color card_bg_color {p['carte']};
@define-color card_fg_color {p['texte']};
@define-color popover_bg_color {pan};
@define-color popover_fg_color {p['texte']};
@define-color dialog_bg_color {pan};
@define-color dialog_fg_color {p['texte']};
@define-color borders {bord};
""")
    # Qt 5 / 6 : suivent le thème GTK
    # terminal (foot)
    def h(c): return couleur_pleine(c, pan).lstrip("#")
    _ecrire(os.path.join(conf, "foot", "xiii-couleurs.ini"), f"""[colors]
background={h(p['fond'] if not p['clair'] else melange(p['fond'], '#000000', .82))}
foreground={h(p['texte'] if not p['clair'] else '#eeeeee')}
regular1={h('#e57373')}
regular2={h('#81c784')}
regular3={h(A)}
regular4={h('#4fc3f7')}
bright3={h(p['accent_survol'])}
selection-background={h(A)}
selection-foreground={h(p['sur_accent'])}
""")
    foot = os.path.join(conf, "foot", "foot.ini")
    try: ft = open(foot).read()
    except OSError: ft = "font=IBM Plex Mono:size=11\npad=10x8\n"
    if "xiii-couleurs.ini" not in ft:
        ft = re.sub(r"\[colors\][^\[]*", "", ft).rstrip() + "\ninclude=%s\n" % os.path.join(conf, "foot", "xiii-couleurs.ini")
        _ecrire(foot, ft)
    # fenêtres (labwc)
    titre_fond = melange(pan, p["fond"], .5)
    _ecrire(f"{conf}/labwc/themerc-override", f"""window.active.border.color: {A}
window.inactive.border.color: {bord}
window.active.title.bg.color: {titre_fond}
window.inactive.title.bg.color: {titre_fond}
window.active.label.text.color: {p['accent_texte']}
window.inactive.label.text.color: {att}
window.active.button.unpressed.image.color: {p['accent_texte']}
window.inactive.button.unpressed.image.color: {att}
menu.items.bg.color: {pan}
menu.items.text.color: {p['texte']}
menu.items.active.bg.color: {A}
menu.items.active.text.color: {p['sur_accent']}
menu.border.color: {A}
osd.bg.color: {pan}
osd.border.color: {A}
osd.label.text.color: {p['texte']}
window.switcher.width: 600
border.width: {1 if p['rayon'] != '0px' else 2}
""")
    _ecrire(f"{conf}/swaylock/config", f"""image={cfg.get('verrou_fond', '/usr/share/xiii/wallpapers/xiii-connexion.png')}
scaling=fill
indicator-radius=90
indicator-thickness=6
inside-color={h(pan)}cc
ring-color={A.lstrip('#')}ff
key-hl-color={p['accent_survol'].lstrip('#')}ff
line-color=00000000
text-color={h(p['texte'])}ff
inside-ver-color={h(pan)}cc
ring-ver-color={A.lstrip('#')}ff
inside-wrong-color={h(pan)}cc
ring-wrong-color=e98080ff
separator-color=00000000
font={p['police']}
show-failed-attempts
""")
    env = f"{conf}/labwc/environment"
    try:
        lignes = [l for l in open(env).read().splitlines() if not l.startswith(("XCURSOR_SIZE=", "XCURSOR_THEME=", "QT_QPA_PLATFORMTHEME=", "GTK_THEME="))]
    except OSError:
        lignes = ["XKB_DEFAULT_LAYOUT=fr"]
    lignes += ["XCURSOR_THEME=XIII-curseur", f"XCURSOR_SIZE={curseur}", "QT_QPA_PLATFORMTHEME=gtk3"]
    _ecrire(env, "\n".join(l for l in lignes if l) + "\n")
    try:
        subprocess.Popen(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-light" if clair else "prefer-dark"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "XIII-perso"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
    reconfigurer_labwc()


def appliquer_connexion(cfg):
    """Écran de connexion (LightDM) et animation de démarrage (Plymouth) aux couleurs du thème — droits administrateur."""
    p = palette(cfg)
    r, g, b = (v / 255 for v in hex_rgb(p["fond"]))
    data = {"css": css_gtk3(p), "fond": fond_assorti(cfg) if fond_par_defaut(cfg.get("fond")) else cfg.get("fond"), "rgb": [round(r, 3), round(g, 3), round(b, 3)], "police": p["police"]}
    import json, tempfile
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump(data, f); f.close()
    return subprocess.run(["pkexec", "/usr/local/bin/xiii-theme-systeme", f.name]).returncode == 0


def reconfigurer_labwc():
    if os.environ.get("LABWC_PID") or os.environ.get("WAYLAND_DISPLAY"):
        try:
            subprocess.Popen(["labwc", "--reconfigure"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
