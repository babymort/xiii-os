#!/usr/bin/env python3
# OS XIII — génère le thème de curseurs « XIII-curseur » (format Xcursor) : formes sombres arrondies,
# contour blanc, ombre douce, anneau de chargement animé couleur cuivre XIII. Dessin original.
# Usage : python3 outils/curseur.py <dossier de sortie>
# Application développée par Matthieu Lamotte.
import os, sys, struct, math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

G = 8            # facteur de travail : grille nominale 32 px → 256 px
N = 32 * G
NOIR, BLANC, ACC = (24, 24, 24, 255), (255, 255, 255, 255), (240, 179, 120, 255)
TAILLES = (24, 32, 48, 64, 96)
POLICE = next((p for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",) if os.path.exists(p)), None)

def toile():
    m = Image.new("L", (N, N), 0); return m, ImageDraw.Draw(m)

def P(x, y): return (x * G, y * G)

def trait(d, pts, w, fill=255):
    pts = [P(*p) for p in pts]
    d.line(pts, fill=fill, width=int(w * G), joint="curve")
    r = w * G / 2
    for x, y in (pts[0], pts[-1]): d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

def poly_arrondi(d, pts, r=1.2):
    pp = [P(*p) for p in pts]
    d.polygon(pp, fill=255); d.line(pp + [pp[0]], fill=255, width=int(r * 2 * G), joint="curve")
    for x, y in pp: d.ellipse((x - r * G, y - r * G, x + r * G, y + r * G), fill=255)

def fleche(d, x0, y0, x1, y1, w=2.2, tete=4.2):
    a = math.atan2(y1 - y0, x1 - x0)
    bx, by = x1 - math.cos(a) * tete * 0.8, y1 - math.sin(a) * tete * 0.8
    trait(d, [(x0, y0), (bx, by)], w)
    pts = [(x1, y1), (bx + math.cos(a + 2.2) * -0 + math.cos(a + math.pi / 2) * tete * 0.75 - math.cos(a) * 0.6, by + math.sin(a + math.pi / 2) * tete * 0.75 - math.sin(a) * 0.6),
           (bx + math.cos(a - math.pi / 2) * tete * 0.75 - math.cos(a) * 0.6, by + math.sin(a - math.pi / 2) * tete * 0.75 - math.sin(a) * 0.6)]
    poly_arrondi(d, pts, 0.7)

def composer(masque, contour=1.5, couleur=NOIR, extra=None):
    """masque (L) → RGBA : ombre douce + contour blanc arrondi + remplissage."""
    k = int(contour * 2 * G) | 1
    bord = masque.filter(ImageFilter.MaxFilter(k))
    ombre = bord.filter(ImageFilter.GaussianBlur(2.2 * G)).point(lambda v: int(v * 0.45))
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    sh = Image.new("RGBA", (N, N), (0, 0, 0, 255)); sh.putalpha(ombre)
    im.alpha_composite(sh, (0, int(1.2 * G)))
    b = Image.new("RGBA", (N, N), BLANC); b.putalpha(bord); im.alpha_composite(b)
    f = Image.new("RGBA", (N, N), couleur); f.putalpha(masque); im.alpha_composite(f)
    if extra: extra(im)
    return im

# ------------------------------------------------------------------ formes
def pointeur(d, dx=0, dy=0):
    poly_arrondi(d, [(3.5 + dx, 2.5 + dy), (5 + dx, 22.5 + dy), (18.5 + dx, 13.5 + dy)], 1.7)

def f_pointeur():
    m, d = toile(); pointeur(d); return composer(m)

def f_main():
    m, d = toile()
    def rr(x0, y0, x1, y1, r): d.rounded_rectangle((x0 * G, y0 * G, x1 * G, y1 * G), radius=r * G, fill=255)
    rr(10, 2, 14.5, 17, 2.25)            # index
    rr(14, 9.5, 18, 18, 2)               # majeur
    rr(17.5, 10.5, 21.5, 19, 2)          # annulaire
    rr(10, 13, 24, 27.5, 4.5)            # paume
    rr(20.5, 12, 24, 20, 1.75)           # auriculaire
    d.polygon([P(10.5, 15.5), P(5, 15), P(4, 17.5), P(10.5, 25)], fill=255)   # pouce
    d.ellipse((3.6 * G, 14.4 * G, 7.6 * G, 18.4 * G), fill=255)
    return composer(m, 1.4)

def f_texte():
    m, d = toile()
    trait(d, [(16, 6), (16, 26)], 2.2); trait(d, [(12.5, 5), (15, 5.6), (17, 5.6), (19.5, 5)], 2); trait(d, [(12.5, 27), (15, 26.4), (17, 26.4), (19.5, 27)], 2)
    return composer(m, 1.3)

def f_viseur():
    m, d = toile()
    d.ellipse((9 * G, 9 * G, 23 * G, 23 * G), outline=255, width=int(2.4 * G))
    for a, b in (((16, 3), (16, 9)), ((16, 23), (16, 29)), ((3, 16), (9, 16)), ((23, 16), (29, 16))): trait(d, [a, b], 2.2)
    d.ellipse((14.5 * G, 14.5 * G, 17.5 * G, 17.5 * G), fill=255)
    return composer(m, 1.3)

def f_deplacer():
    m, d = toile()
    for x, y in ((16, 3), (16, 29), (3, 16), (29, 16)): fleche(d, 16, 16, x, y, 2.2, 4.6)
    return composer(m, 1.3)

def f_double(angle):
    def f():
        m, d = toile()
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        fleche(d, 16 + c * 2.5, 16 + s * 2.5, 16 + c * 11.5, 16 + s * 11.5, 2.2, 5)
        fleche(d, 16 - c * 2.5, 16 - s * 2.5, 16 - c * 11.5, 16 - s * 11.5, 2.2, 5)
        return composer(m, 1.3)
    return f

def f_interdit():
    m, d = toile(); d.ellipse((5 * G, 5 * G, 27 * G, 27 * G), fill=255)
    def extra(im):
        dd = ImageDraw.Draw(im)
        dd.ellipse((6.4 * G, 6.4 * G, 25.6 * G, 25.6 * G), fill=(232, 96, 96, 255))
        dd.line([P(10.5, 10.5), P(21.5, 21.5)], fill=NOIR, width=int(3 * G))
        dd.ellipse((8.6 * G, 8.6 * G, 23.4 * G, 23.4 * G), outline=NOIR, width=int(2.6 * G))
    return composer(m, 1.3, couleur=(0, 0, 0, 0), extra=extra)

def f_aide():
    m, d = toile(); pointeur(d, -1, 0)
    if POLICE:
        ft = ImageFont.truetype(POLICE, int(15 * G)); d.text(P(18.5, -2.5), "?", font=ft, fill=255)
    return composer(m, 1.4)

def f_haut():
    m, d = toile(); fleche(d, 16, 29, 16, 3, 2.4, 6); return composer(m, 1.3)

def f_crayon():
    m, d = toile()
    poly_arrondi(d, [(4, 28), (6, 21), (22, 5), (27, 10), (11, 26)], 1)
    def extra(im):
        ImageDraw.Draw(im).line([P(19.5, 7.5), P(24.5, 12.5)], fill=BLANC, width=int(1.4 * G))
    return composer(m, 1.3, extra=extra)

def anneau(img, cx, cy, r, ep, debut, couleur=ACC):
    """Arc cuivre avec traîne dégradée sur un rail discret."""
    d = ImageDraw.Draw(img)
    bb = (cx - r, cy - r, cx + r, cy + r)
    d.ellipse(bb, outline=(255, 255, 255, 70), width=ep)
    for i in range(24):
        a0 = debut + i * 6; al = int(255 * (0.25 + 0.75 * (i + 1) / 24))
        d.arc(bb, a0, a0 + 7, fill=couleur[:3] + (al,), width=ep)

def f_attente(phase):
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ombre = Image.new("L", (N, N), 0); ImageDraw.Draw(ombre).ellipse((4 * G, 5 * G, 28 * G, 29 * G), outline=255, width=int(5 * G))
    sh = Image.new("RGBA", (N, N), (0, 0, 0, 255)); sh.putalpha(ombre.filter(ImageFilter.GaussianBlur(2 * G)).point(lambda v: int(v * .35))); im.alpha_composite(sh)
    ImageDraw.Draw(im).ellipse((3 * G, 3 * G, 29 * G, 29 * G), outline=(24, 24, 24, 200), width=int(4.6 * G))
    anneau(im, 16 * G, 16 * G, 12 * G, int(3.2 * G), phase)
    return im

def f_occupe(phase):
    im = f_pointeur()
    anneau(im, 23 * G, 23 * G, int(6.5 * G), int(2.4 * G), phase)
    return im

# ------------------------------------------------------------------ Xcursor
def ecrire(chemin, images, hot, delai=0):
    """images : liste de RGBA 256×256 (plusieurs = animation)."""
    chunks = []
    for t in TAILLES:
        for im in images:
            r = im.resize((t, t), Image.LANCZOS)
            px = []
            for R, Gc, B, A in (r.get_flattened_data() if hasattr(r, "get_flattened_data") else r.getdata()):
                px.append((A << 24) | ((R * A // 255) << 16) | ((Gc * A // 255) << 8) | (B * A // 255))
            hx, hy = int(round(hot[0] * t / 32)), int(round(hot[1] * t / 32))
            chunks.append((t, struct.pack("<IIIIIIIII", 36, 0xfffd0002, t, 1, t, t, hx, hy, delai) + struct.pack("<%dI" % len(px), *px)))
    off = 16 + 12 * len(chunks); toc = b""; data = b""
    for t, c in chunks:
        toc += struct.pack("<III", 0xfffd0002, t, off + len(data)); data += c
    open(chemin, "wb").write(b"Xcur" + struct.pack("<III", 16, 0x10000, len(chunks)) + toc + data)

ALIAS = {
    "left_ptr": ["default", "arrow", "top_left_arrow", "left_arrow", "context-menu", "copy", "alias", "dnd-copy", "dnd-link", "dnd-move", "dnd-none", "x-cursor", "X_cursor"],
    "hand2": ["pointer", "hand1", "hand", "pointing_hand", "grab", "openhand", "grabbing", "closedhand", "fleur-grab", "e29285e634086352946a0e7090d73106", "9d800788f1b08800ae810202380a0822"],
    "xterm": ["text", "ibeam", "vertical-text"],
    "crosshair": ["cross", "tcross", "cell", "plus", "cross_reverse", "diamond_cross", "color-picker", "zoom-in", "zoom-out"],
    "fleur": ["move", "all-scroll", "size_all", "all-resize"],
    "sb_v_double_arrow": ["ns-resize", "n-resize", "s-resize", "row-resize", "size_ver", "v_double_arrow", "top_side", "bottom_side", "split_v", "double_arrow"],
    "sb_h_double_arrow": ["ew-resize", "e-resize", "w-resize", "col-resize", "size_hor", "h_double_arrow", "left_side", "right_side", "split_h"],
    "fd_double_arrow": ["nwse-resize", "nw-resize", "se-resize", "size_fdiag", "top_left_corner", "bottom_right_corner"],
    "bd_double_arrow": ["nesw-resize", "ne-resize", "sw-resize", "size_bdiag", "top_right_corner", "bottom_left_corner"],
    "not-allowed": ["no-drop", "forbidden", "crossed_circle", "circle", "dnd-no-drop", "pirate"],
    "question_arrow": ["help", "whats_this", "left_ptr_help", "dnd-ask"],
    "watch": ["wait"],
    "left_ptr_watch": ["progress", "half-busy", "08e8e1c95fe2fc01f976f1e063a24ccd", "3ecb610c1bf2410f44200f48c40d3599"],
    "up_arrow": ["center_ptr", "sb_up_arrow"],
    "pencil": ["draft"],
}

def main(sortie):
    c = os.path.join(sortie, "cursors"); os.makedirs(c, exist_ok=True)
    for f in os.listdir(c): os.remove(os.path.join(c, f))
    ecrire(c + "/left_ptr", [f_pointeur()], (3.5, 2.5))
    ecrire(c + "/hand2", [f_main()], (12.2, 2.5))
    ecrire(c + "/xterm", [f_texte()], (16, 16))
    ecrire(c + "/crosshair", [f_viseur()], (16, 16))
    ecrire(c + "/fleur", [f_deplacer()], (16, 16))
    ecrire(c + "/sb_v_double_arrow", [f_double(90)()], (16, 16))
    ecrire(c + "/sb_h_double_arrow", [f_double(0)()], (16, 16))
    ecrire(c + "/fd_double_arrow", [f_double(45)()], (16, 16))
    ecrire(c + "/bd_double_arrow", [f_double(-45)()], (16, 16))
    ecrire(c + "/not-allowed", [f_interdit()], (16, 16))
    ecrire(c + "/question_arrow", [f_aide()], (2.5, 2.5))
    ecrire(c + "/up_arrow", [f_haut()], (16, 3))
    ecrire(c + "/pencil", [f_crayon()], (4, 28))
    ecrire(c + "/watch", [f_attente(i * 15) for i in range(24)], (16, 16), 33)
    ecrire(c + "/left_ptr_watch", [f_occupe(i * 15) for i in range(24)], (3.5, 2.5), 33)
    for src, L in ALIAS.items():
        for a in L:
            p = os.path.join(c, a)
            if not os.path.lexists(p): os.symlink(src, p)
    open(os.path.join(sortie, "index.theme"), "w").write("[Icon Theme]\nName=XIII-curseur\nComment=Curseurs OS XIII\nInherits=Adwaita\n")
    # planche d'aperçu
    pl = Image.new("RGBA", (8 * 80, 2 * 80), (110, 110, 110, 255))
    for i, im in enumerate([f_pointeur(), f_main(), f_texte(), f_viseur(), f_deplacer(), f_double(90)(), f_double(0)(), f_double(45)(),
                            f_interdit(), f_aide(), f_haut(), f_crayon(), f_attente(0), f_occupe(90), f_attente(180), f_double(-45)()]):
        pl.alpha_composite(im.resize((64, 64), Image.LANCZOS), ((i % 8) * 80 + 8, (i // 8) * 80 + 8))
    pl.save("/tmp/curseurs-xiii.png")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "XIII-curseur")
