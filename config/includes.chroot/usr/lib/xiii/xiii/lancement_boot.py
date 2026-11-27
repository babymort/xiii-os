# OS XIII — animations de lancement XIII (Plymouth) : éclat lumineux, grille bleue, mosaïque, présentation « produit ».
# Les images sont calculées à la construction de l'ISO (comme les animations ASCII) :
#   python3 lancement_boot.py <dossier_themes> [variante…]
# Application développée par Matthieu Lamotte.
import os, sys, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

W, H = 960, 540
N = 66                      # images par animation (≈ 2,6 s à 25 images/s), la dernière reste affichée
LOGO = "/usr/share/xiii/logos/xiii-orange.png"
CUIVRE = (240, 179, 120)

VARIANTES = [
    ("eclat", "Éclat de lumière", "Un point de lumière grandit, des rayons éclatent et révèlent le logo"),
    ("grille", "Grille bleue", "Grille en perspective et formes géométriques qui assemblent le logo"),
    ("mosaique", "Mosaïque", "Une mosaïque de tuiles colorées se resserre et laisse place au logo"),
    ("produit", "Présentation", "Le logo glisse dans la lumière, reflet au sol et balayage brillant, façon présentation de produit"),
]

SCRIPT = """Window.SetBackgroundTopColor(0,0,0); Window.SetBackgroundBottomColor(0,0,0);
n = %d; for (i = 0; i < n; i++) { s = "" + i; while (s.Length() < 3) s = "0" + s; img[i] = Image("f-" + s + ".png"); }
sp = Sprite(img[0]); t = 0;
fun r () { t++; k = Math.Int(t / 2); if (k >= n) k = n - 1;
  ech = Window.GetWidth() / 960; if (Window.GetHeight() / 540 < ech) ech = Window.GetHeight() / 540;
  im = img[k].Scale(960 * ech, 540 * ech);
  sp.SetImage(im); sp.SetX(Window.GetWidth()/2 - im.GetWidth()/2); sp.SetY(Window.GetHeight()/2 - im.GetHeight()/2); }
Plymouth.SetRefreshFunction(r);
fun msg (texte) { m = Image.Text(texte, 0.9, 0.7, 0.5); ms = Sprite(m); ms.SetX(Window.GetWidth()/2 - m.GetWidth()/2); ms.SetY(Window.GetHeight() - 60); }
Plymouth.SetMessageFunction(msg);
"""


def ease(t): return 1 - (1 - max(0, min(1, t))) ** 3


def logo(hauteur, couleur=CUIVRE):
    """Le logo XIII (masque du PNG) teint d'une couleur, en RGBA, à la hauteur voulue."""
    src = Image.open(LOGO).convert("RGBA")
    k = hauteur / src.height
    m = src.split()[3].resize((max(1, int(src.width * k)), max(1, int(hauteur))), Image.LANCZOS)
    im = Image.new("RGBA", m.size, couleur + (255,)); im.putalpha(m)
    return im


def lueur(im, rayon, force=1.0):
    g = im.filter(ImageFilter.GaussianBlur(rayon))
    if force != 1:
        a = g.split()[3].point(lambda v: min(255, int(v * force))); g.putalpha(a)
    return g


def coller(fond, im, cx, cy, opacite=1.0):
    if opacite < 1:
        a = im.split()[3].point(lambda v: int(v * opacite)); im = im.copy(); im.putalpha(a)
    fond.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# ----------------------------------------------------------------------------------------------- variantes
def eclat(i):
    t = i / (N - 1)
    f = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(f, "RGBA")
    cx, cy = W / 2, H / 2
    # point de lumière qui grandit
    r = 4 + 320 * ease(t / .45)
    for k in range(14, 0, -1):
        rr = r * k / 14; a = int(18 * (1 - k / 15) * min(1, t / .1))
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(255, 214, 160, a))
    # rayons qui tournent et s'allongent
    if t > .12:
        long = (W * .8) * ease((t - .12) / .4); a = int(150 * (1 - ease((t - .62) / .38)) if t > .62 else 150)
        for k in range(18):
            ang = k * math.pi / 9 + t * .9
            x2, y2 = cx + math.cos(ang) * long, cy + math.sin(ang) * long
            d.line([cx, cy, x2, y2], fill=(255, 225, 180, max(0, a)), width=3 if k % 2 else 6)
        f = f.filter(ImageFilter.GaussianBlur(2))
    f = f.convert("RGBA")
    # éclair blanc puis logo
    if .42 < t < .62:
        b = 1 - abs(t - .5) / .12
        f = Image.alpha_composite(f, Image.new("RGBA", (W, H), (255, 244, 230, int(200 * max(0, b)))))
    if t > .48:
        l = logo(210); k = ease((t - .48) / .3)
        coller(f, lueur(l, 26), cx, cy, k * .45); coller(f, l, cx, cy, k)
    return f


def grille(i):
    t = i / (N - 1)
    f = Image.new("RGB", (W, H), (2, 6, 20)); d = ImageDraw.Draw(f, "RGBA")
    hz = H * .55; bleu = (40, 140, 255)
    # sol quadrillé qui défile vers nous
    off = (t * 6) % 1
    for k in range(18):
        z = (k + off) / 18; y = hz + (H - hz) * z ** 2
        d.line([0, y, W, y], fill=bleu + (int(40 + 150 * z),), width=1 + int(z * 2))
    for k in range(-20, 21):
        d.line([W / 2 + k * 14, hz, W / 2 + k * 120, H], fill=bleu + (110,), width=1)
    # horizon lumineux
    for k in range(10):
        d.rectangle([0, hz - k, W, hz + k], fill=bleu + (int(14 - k),))
    # formes géométriques qui arrivent et convergent
    rnd = random.Random(13)
    for k in range(16):
        x0, y0 = rnd.uniform(0, W), rnd.uniform(0, hz); s = rnd.uniform(14, 46); typ = k % 3
        p = ease(t / .7); x = x0 + (W / 2 - x0) * p; y = y0 + (H / 2 - 30 - y0) * p; s *= (1 - .7 * p)
        a = int(220 * (1 - ease((t - .6) / .25))) if t > .6 else 220
        col = (90, 190, 255, max(0, a))
        if typ == 0: d.polygon([(x, y - s), (x - s, y + s * .8), (x + s, y + s * .8)], outline=col, width=2)
        elif typ == 1: d.ellipse([x - s, y - s, x + s, y + s], outline=col, width=2)
        else: d.rectangle([x - s, y - s, x + s, y + s], outline=col, width=2)
    f = f.filter(ImageFilter.GaussianBlur(.6)).convert("RGBA")
    if t > .55:
        k = ease((t - .55) / .3)
        l = logo(190, (150, 215, 255)); coller(f, lueur(l, 22), W / 2, H / 2 - 40, k * .6); coller(f, logo(190, (235, 245, 255)), W / 2, H / 2 - 40, k)
    return f


def mosaique(i):
    t = i / (N - 1)
    f = Image.new("RGB", (W, H), (12, 10, 9)); d = ImageDraw.Draw(f, "RGBA")
    cols = [(255, 107, 107), (255, 169, 77), (255, 212, 59), (105, 219, 124), (56, 217, 169), (77, 171, 247), (116, 143, 252), (218, 119, 242), (247, 131, 172), CUIVRE]
    rnd = random.Random(7); T = 46; nx, ny = W // T + 1, H // T + 1
    for gx in range(nx):
        for gy in range(ny):
            x, y = gx * T + 4, gy * T + 4; c = rnd.choice(cols); dl = rnd.uniform(0, .25)
            app = ease((t - dl) / .2)
            # les tuiles se resserrent vers le centre, rapetissent et s'effacent
            p = ease((t - .45 - dl * .5) / .35)
            xx = x + (W / 2 - x) * p; yy = y + (H / 2 - y) * p; s = (T - 10) * (1 - p) * app
            if s < 1: continue
            a = int(235 * app * (1 - p))
            d.rounded_rectangle([xx, yy, xx + s, yy + s], radius=max(1, s / 4), fill=c + (a,))
            if s > 14:
                d.rounded_rectangle([xx + s * .3, yy + s * .3, xx + s * .7, yy + s * .7], radius=max(1, s / 10), fill=(255, 255, 255, int(a * .55)))
    f = f.convert("RGBA")
    if t > .62:
        k = ease((t - .62) / .28)
        l = logo(200); coller(f, lueur(l, 24), W / 2, H / 2, k * .4); coller(f, l, W / 2, H / 2, k)
    return f


def produit(i):
    t = i / (N - 1)
    f = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(f, "RGBA")
    # halo de scène
    for k in range(16, 0, -1):
        r = 40 * k; d.ellipse([W / 2 - r * 1.6, H * .42 - r, W / 2 + r * 1.6, H * .42 + r], fill=(60, 44, 30, 8))
    f = f.convert("RGBA")
    cy = H * .42; l = logo(170)
    p = ease(t / .55); cx = W / 2 + (1 - p) * 260
    # reflet au sol
    ref = l.transpose(Image.FLIP_TOP_BOTTOM); g = Image.linear_gradient("L").resize(ref.size)
    ref.putalpha(ImageChops.multiply(ref.split()[3], g.point(lambda v: int(v * .35))))
    coller(f, ref, cx, cy + l.height + 6, p)
    coller(f, lueur(l, 22), cx, cy, p * .35); coller(f, l, cx, cy, p)
    # balayage brillant sur le logo
    if .55 < t < .9:
        x = (t - .55) / .35 * (l.width + 160) - 80
        bande = Image.new("RGBA", l.size, (0, 0, 0, 0)); bd = ImageDraw.Draw(bande)
        bd.polygon([(x, 0), (x + 50, 0), (x - 20, l.height), (x - 70, l.height)], fill=(255, 255, 255, 170))
        bande.putalpha(ImageChops.multiply(bande.split()[3], l.split()[3]))
        coller(f, bande.filter(ImageFilter.GaussianBlur(4)), cx, cy)
    # sous-titre
    if t > .6:
        k = ease((t - .6) / .3); txt = "O S   X I I I"
        d2 = ImageDraw.Draw(f, "RGBA")
        try:
            from PIL import ImageFont
            fo = None
            for pth in ("/usr/share/fonts/truetype/xiii/SpaceGrotesk.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
                if os.path.exists(pth): fo = ImageFont.truetype(pth, 22); break
            w = d2.textlength(txt, font=fo) if fo else 120
            d2.text((W / 2 - w / 2, H * .82), txt, font=fo, fill=(235, 225, 214, int(220 * k)))
        except Exception:
            pass
    return f


FONCTIONS = {"eclat": eclat, "grille": grille, "mosaique": mosaique, "produit": produit}


def generer(racine, seules=None):
    for nom, titre, desc in VARIANTES:
        if seules and nom not in seules: continue
        d = os.path.join(racine, "xiii-lancement-" + nom); os.makedirs(d, exist_ok=True)
        for i in range(N):
            im = FONCTIONS[nom](i).convert("RGB").quantize(160, method=Image.Quantize.MEDIANCUT)
            im.save(os.path.join(d, "f-%03d.png" % i), optimize=True)
        open(os.path.join(d, "anim.script"), "w").write(SCRIPT % N)
        open(os.path.join(d, "xiii-lancement-%s.plymouth" % nom), "w").write(
            "[Plymouth Theme]\nName=XIII Lancement — %s\nDescription=%s\nModuleName=script\n[script]\nImageDir=%s\nScriptFile=%s/anim.script\n" % (titre, desc, d, d))
        print(nom, N, "images")


if __name__ == "__main__":
    generer(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/plymouth/themes", sys.argv[2:] or None)
