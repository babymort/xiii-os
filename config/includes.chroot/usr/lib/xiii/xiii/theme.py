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
THEMES = [("sombre", "Sombre", "Verre sombre, lueur cuivre — le thème signature de la suite"),
          ("clair", "Clair", "Papier chaud, verre beige, lueur ambre"),
          ("sobre", "Sobre", "Plat, sans verre ni lueur, couleurs de la suite")]

def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def rgb_hex(r, g, b):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in (r, g, b))

def melange(a, b, t):
    A, B = hex_rgb(a), hex_rgb(b)
    return rgb_hex(*(A[i] + (B[i] - A[i]) * t for i in range(3)))

def sur_accent(a):
    r, g, b = hex_rgb(a)
    return "#1a1a1a" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#ffffff"

def palette(cfg):
    t = cfg.get("theme", "sombre"); A = cfg.get("accent", "#f0b378")
    verre = cfg.get("transparence", True) and t != "sobre"
    if t == "clair":
        p = dict(fond="#eef0f2", panneau="rgba(250,249,247,%s)" % (".95" if verre else "1"), panneau_plein="#faf9f7",
                 carte="#ffffff", carte2="#f3f1ee", texte="#1d1b19", attenue="#6d675f", bord="rgba(0,0,0,0.09)",
                 survol="rgba(0,0,0,0.05)", ombre="rgba(60,40,20,0.18)", accent_texte=melange(A, "#000000", 0.30), clair=True)
    else:
        p = dict(fond="#1e1e1e", panneau="rgba(28,27,26,%s)" % (".94" if verre else "1"), panneau_plein="#1c1b1a",
                 carte="#2a2928" if t != "sobre" else "#2d2d2d", carte2="#232221", texte="#eee9e3", attenue="#9b938a",
                 bord="rgba(255,255,255,0.08)", survol="rgba(255,255,255,0.07)", ombre="rgba(0,0,0,0.50)", accent_texte=A, clair=False)
    p.update(accent=A, accent_survol=melange(A, "#ffffff", 0.18), sur_accent=sur_accent(A), sobre=(t == "sobre"),
             rayon="4px" if t == "sobre" else "14px", rayon_petit="3px" if t == "sobre" else "8px",
             lueur="none" if (t == "sobre" or not verre) else "0 0 48px alpha(%s,0.10)" % A,
             police=cfg.get("police", "IBM Plex Sans"), anim="none" if not cfg.get("animations", True) else "all 160ms ease")
    return p

# --------------------------------------------------------------------------------------------- CSS commun
def css_commun(p):
    return f"""
* {{ font-family: "{p['police']}", "IBM Plex Sans", sans-serif; }}
label {{ color: {p['texte']}; }}
.attenue, .attenue label {{ color: {p['attenue']}; }}
.petit {{ font-size: 11.5px; }}
.titre-astoria {{ font-family: Astoria, "Archivo Black", sans-serif; color: {p['accent_texte']}; }}
.accent {{ color: {p['accent_texte']}; }}
.gras {{ font-weight: 600; }}
.section {{ font-weight: 600; font-size: 12.5px; color: {p['attenue']}; margin-top: 6px; }}
button {{ transition: {p['anim']}; }}
button.pilule {{ background: {p['accent']}; color: {p['sur_accent']}; border-radius: 999px; padding: 6px 18px; font-weight: 700; border: none; box-shadow: none; }}
button.pilule label {{ color: {p['sur_accent']}; }}
button.pilule:hover {{ background: {p['accent_survol']}; }}
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
.barre {{ background: {p['panneau']}; border-top: 1px solid {p['bord']}; }}
.haut {{ background: {p['panneau']}; border-bottom: 1px solid {p['bord']}; }}
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
.tb-ind {{ background: {p['attenue']}; min-height: 3px; min-width: 6px; border-radius: 2px; }}
.tb-ind.actif {{ background: {p['accent']}; min-width: 16px; }}
.tb-ind.vide {{ background: transparent; }}
.horloge-h {{ font-weight: 600; font-size: 12.5px; }}
.horloge-d {{ font-size: 11px; color: {p['attenue']}; }}
.badge {{ background: {p['accent']}; color: {p['sur_accent']}; border-radius: 999px; font-size: 10px; font-weight: 700; min-width: 16px; min-height: 16px; padding: 0 4px; }}
.meteo-t {{ font-weight: 600; font-size: 12.5px; }}
.panneau {{ background: {p['panneau']}; border: 1px solid alpha({p['accent']},0.28); border-radius: {p['rayon']}; box-shadow: 0 12px 40px {p['ombre']}{', ' + p['lueur'] if p['lueur'] != 'none' else ''}; padding: 16px; }}
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
.reglage {{ background: {p['carte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon_petit']}; padding: 12px 16px; min-height: 40px; }}
button.reglage {{ box-shadow: none; }}
button.reglage:hover {{ background: alpha({p['accent']},0.06); border-color: alpha({p['accent']},0.35); }}
.reglage-titre {{ font-weight: 500; }}
.reglage-sous {{ font-size: 12px; color: {p['attenue']}; }}
.groupe {{ margin-bottom: 2px; }}
.groupe-titre {{ font-weight: 600; font-size: 13.5px; margin: 14px 0 6px 2px; }}
.hero {{ background: {p['carte']}; border: 1px solid {p['bord']}; border-radius: {p['rayon']}; padding: 16px; }}
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

def fond_assorti(cfg):
    """Si le fond est un fond XIII par défaut, prend celui assorti au thème."""
    if cfg.get("fond") in FONDS_XIII.values():
        return FONDS_XIII.get(cfg.get("theme"), cfg["fond"])
    return cfg.get("fond")

def nom_icones(cfg):
    """Thème d'icônes : XIII (cuivre) ou copie teintée à la couleur d'accent."""
    A = cfg.get("accent", "#f0b378").lower()
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

def appliquer_systeme(cfg):
    """Propage thème / accent / tailles aux apps GTK, aux fenêtres (labwc) et au verrouillage."""
    p = palette(cfg); A = p["accent"]; conf = GLib.get_user_config_dir()
    clair = p["clair"]; dpi = int(96 * 1024 * float(cfg.get("taille_texte", 1.0)))
    anim = "true" if cfg.get("animations", True) else "false"
    curseur = int(cfg.get("curseur_taille", 24))
    police = "%s %d" % (cfg.get("police", "IBM Plex Sans"), 10)
    icones = nom_icones(cfg)
    for v in ("3.0", "4.0"):
        _ecrire(f"{conf}/gtk-{v}/settings.ini", f"""[Settings]
gtk-theme-name={'XIII-clair' if (clair and v == '3.0') else ('XIII' if v == '3.0' else 'Adwaita')}
gtk-application-prefer-dark-theme={'0' if clair else '1'}
gtk-icon-theme-name={icones}
gtk-font-name={police}
gtk-cursor-theme-name=XIII-curseur
gtk-cursor-theme-size={curseur}
gtk-xft-dpi={dpi}
gtk-enable-animations={anim}
""")
    _ecrire(f"{conf}/gtk-3.0/gtk.css", f"""/* OS XIII — accent (généré par Paramètres XIII) */
@define-color theme_selected_bg_color {A};
@define-color theme_selected_fg_color {p['sur_accent']};
@define-color accent_color {A};
*:selected, selection {{ background-color: {A}; color: {p['sur_accent']}; }}
button.suggested-action {{ background: {A}; color: {p['sur_accent']}; border-color: {A}; }}
check:checked, radio:checked, switch:checked, scale highlight, progressbar progress {{ background: {A}; border-color: {A}; }}
link, *:link {{ color: {p['accent_texte']}; }}
""")
    _ecrire(f"{conf}/gtk-4.0/gtk.css", f"""/* OS XIII — accent (généré par Paramètres XIII) */
@define-color accent_color {p['accent_texte']};
@define-color accent_bg_color {A};
@define-color accent_fg_color {p['sur_accent']};
@define-color window_bg_color {p['fond']};
@define-color view_bg_color {'#ffffff' if clair else '#252525'};
@define-color headerbar_bg_color {'#e8e6e3' if clair else '#1a1a1a'};
@define-color card_bg_color {p['carte']};
@define-color popover_bg_color {p['panneau_plein']};
@define-color dialog_bg_color {p['panneau_plein']};
""")
    titre_fond = "#e8e6e3" if clair else "#1a1a1a"
    _ecrire(f"{conf}/labwc/themerc-override", f"""window.active.border.color: {A}
window.inactive.border.color: {'#d5d8db' if clair else '#2d2d2d'}
window.active.title.bg.color: {titre_fond}
window.inactive.title.bg.color: {titre_fond}
window.active.label.text.color: {p['accent_texte']}
window.inactive.label.text.color: {p['attenue']}
window.active.button.unpressed.image.color: {p['accent_texte']}
window.inactive.button.unpressed.image.color: {p['attenue']}
menu.items.bg.color: {p['panneau_plein']}
menu.items.text.color: {p['texte']}
menu.items.active.bg.color: {A}
menu.items.active.text.color: {p['sur_accent']}
menu.border.color: {A}
osd.bg.color: {p['panneau_plein']}
osd.border.color: {A}
osd.label.text.color: {p['texte']}
window.switcher.width: 600
""")
    _ecrire(f"{conf}/swaylock/config", f"""image={cfg.get('verrou_fond', '/usr/share/xiii/wallpapers/xiii-connexion.png')}
scaling=fill
indicator-radius=90
indicator-thickness=6
inside-color=1a1a1acc
ring-color={A.lstrip('#')}ff
key-hl-color={p['accent_survol'].lstrip('#')}ff
line-color=00000000
text-color=eee9e3ff
inside-ver-color=1a1a1acc
ring-ver-color={A.lstrip('#')}ff
inside-wrong-color=1a1a1acc
ring-wrong-color=e98080ff
separator-color=00000000
font=IBM Plex Sans
show-failed-attempts
""")
    env = f"{conf}/labwc/environment"
    try:
        lignes = [l for l in open(env).read().splitlines() if not l.startswith(("XCURSOR_SIZE=", "XCURSOR_THEME="))]
    except OSError:
        lignes = ["XKB_DEFAULT_LAYOUT=fr"]
    lignes += ["XCURSOR_THEME=XIII-curseur", f"XCURSOR_SIZE={curseur}"]
    _ecrire(env, "\n".join(l for l in lignes if l) + "\n")
    reconfigurer_labwc()

def reconfigurer_labwc():
    if os.environ.get("LABWC_PID") or os.environ.get("WAYLAND_DISPLAY"):
        try:
            subprocess.Popen(["labwc", "--reconfigure"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
