# OS XIII — animations de démarrage ASCII : le logo XIII dessiné en caractères, 10 variantes.
# Les images sont calculées à la construction de l'ISO (Plymouth, thème « script ») :
#   python3 ascii_boot.py <dossier_themes>
# Application développée par Matthieu Lamotte.
import os, sys, random, math
from PIL import Image, ImageDraw, ImageFont

LOGO = [
    "###     ###   ###   ###   ###",
    " ###   ###    ###   ###   ###",
    "  ### ###     ###   ###   ###",
    "   #####      ###   ###   ###",
    "   #####      ###   ###   ###",
    "  ### ###     ###   ###   ###",
    " ###   ###    ###   ###   ###",
    "###     ###   ###   ###   ###",
]
COLS, ROWS = 64, 22
L0, C0 = (ROWS - len(LOGO)) // 2, (COLS - len(LOGO[0])) // 2
CUIVRE, CLAIR, GRIS, VERT, FOND = (240, 179, 120), (255, 226, 196), (90, 84, 78), (90, 255, 140), (17, 17, 17)
W, H = 960, 540

VARIANTES = [
    ("machine", "Machine à écrire", "Le logo se tape caractère par caractère, curseur clignotant"),
    ("matrix", "Pluie Matrix", "Une pluie de caractères qui laisse apparaître le logo"),
    ("crt", "Balayage CRT", "Le logo apparaît ligne par ligne sous un balayage d'écran cathodique"),
    ("glitch", "Glitch", "Le logo se brouille puis se stabilise"),
    ("phosphore", "Phosphore vert", "Écran vert d'ancien terminal, rémanence du phosphore"),
    ("blocs", "Bloc par bloc", "Le logo se construit morceau par morceau"),
    ("clap", "Clap timecode", "Compte à rebours 3-2-1 façon clap, puis le logo"),
    ("mire", "Mire de barres", "Mire de barres qui se transforme en logo"),
    ("vague", "Respiration", "Le logo ondule et respire en cuivre"),
    ("journal", "Journal Unix", "Journal de démarrage qui défile, puis le logo"),
]

def police():
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if os.path.exists(f): return ImageFont.truetype(f, 18)
    return ImageFont.load_default()

F = None
def rendre(cellules, fond=FOND, chemin=None, lignes_balayage=False):
    im = Image.new("RGB", (W, H), fond); d = ImageDraw.Draw(im)
    cw, ch = 13, 22; ox, oy = (W - COLS * cw) // 2, (H - ROWS * ch) // 2
    for (r, c), (car, col) in cellules.items():
        if 0 <= r < ROWS and 0 <= c < COLS and car != " ":
            d.text((ox + c * cw, oy + r * ch), car, font=F, fill=col)
    if lignes_balayage:
        for y in range(0, H, 3): d.line([(0, y), (W, y)], fill=tuple(max(0, v - 8) for v in fond))
    im.save(chemin, optimize=True)

def logo_cases():
    return [(L0 + r, C0 + c) for r, l in enumerate(LOGO) for c, ch in enumerate(l) if ch != " "]

def logo(cel, car="#", col=CUIVRE, cases=None):
    for p in (cases if cases is not None else logo_cases()): cel[p] = (car, col)

def melange(a, b, t): return tuple(int(x + (y - x) * t) for x, y in zip(a, b))

def frames(nom):
    rnd = random.Random(13); L = logo_cases(); out = []
    signature = lambda cel: [cel.__setitem__((L0 + len(LOGO) + 2, C0 + 8 + i), (ch, GRIS)) for i, ch in enumerate("O S   X I I I")]
    if nom == "machine":
        ordre = sorted(L)
        for i in range(0, len(ordre) + 1, 3):
            cel = {}; logo(cel, cases=ordre[:i])
            if i < len(ordre): cel[ordre[min(i, len(ordre) - 1)]] = ("_", CLAIR)
            out.append(cel)
    elif nom == "matrix":
        gouttes = [[rnd.randint(-ROWS, 0), rnd.randint(1, 2)] for _ in range(COLS)]
        for f in range(60):
            cel = {}
            for c, g in enumerate(gouttes):
                g[0] += g[1]
                for k in range(6):
                    r = g[0] - k
                    if 0 <= r < ROWS: cel[(r, c)] = (rnd.choice("01XIII#=+"), melange(VERT, FOND, k / 6))
                if g[0] - 6 > ROWS: g[0] = rnd.randint(-8, 0)
            vis = [p for p in L if rnd.random() < f / 45]
            logo(cel, cases=vis); out.append(cel)
    elif nom == "crt":
        for f in range(ROWS + 10):
            cel = {}; logo(cel, cases=[p for p in L if p[0] <= f])
            if f < ROWS:
                for c in range(COLS): cel[(f, c)] = ("-", melange(CLAIR, FOND, .4))
            out.append(cel)
    elif nom == "glitch":
        for f in range(40):
            cel = {}; force = max(0, 1 - f / 30)
            for (r, c) in L:
                dc = rnd.randint(-3, 3) if rnd.random() < force else 0
                cel[(r, c + dc)] = (rnd.choice("#%@&$") if rnd.random() < force else "#", rnd.choice([CUIVRE, (255, 60, 90), (60, 220, 255)]) if rnd.random() < force else CUIVRE)
            out.append(cel)
    elif nom == "phosphore":
        for f in range(36):
            cel = {}; t = min(1, f / 18)
            logo(cel, col=melange(FOND, VERT, t)); signature(cel)
            out.append(cel)
    elif nom == "blocs":
        ordre = L[:]; rnd.shuffle(ordre)
        for i in range(0, len(ordre) + 1, 4):
            cel = {}; logo(cel, car="#", cases=ordre[:i])
            for p in ordre[i:i + 4]: cel[p] = ("+", CLAIR)
            out.append(cel)
    elif nom == "clap":
        for n in (3, 2, 1):
            for k in range(8):
                cel = {}
                for c in range(C0 - 2, C0 + 31): cel[(L0 - 3, c)] = ("/" if (c // 2) % 2 else "\\", CLAIR if k < 2 else GRIS)
                for i, ch in enumerate("00:00:0%d:%02d" % (n, 24 - k * 3)): cel[(L0 + 2, C0 + 9 + i)] = (ch, CUIVRE)
                for i, ch in enumerate(str(n)): cel[(L0 + 5, C0 + 14 + i)] = (ch, CLAIR)
                out.append(cel)
        for k in range(10): cel = {}; logo(cel); out.append(cel)
    elif nom == "mire":
        barres = [(230, 230, 230), (230, 230, 40), (40, 230, 230), (40, 230, 40), (230, 40, 230), (230, 40, 40), (40, 40, 230)]
        for f in range(36):
            cel = {}; t = f / 30
            for r in range(3, ROWS - 3):
                for c in range(4, COLS - 4):
                    if rnd.random() > t: cel[(r, c)] = ("|", barres[(c - 4) * 7 // (COLS - 8)])
            logo(cel, cases=[p for p in L if rnd.random() < t]); out.append(cel)
    elif nom == "vague":
        for f in range(40):
            cel = {}
            for (r, c) in L:
                k = (math.sin(f / 4 + c / 3) + 1) / 2
                cel[(r + (1 if math.sin(f / 4 + c / 3) > .8 else 0), c)] = ("#", melange(GRIS, CUIVRE, .3 + .7 * k))
            out.append(cel)
    elif nom == "journal":
        msgs = ["[  OK  ] Montage des systèmes de fichiers", "[  OK  ] Réseau : NetworkManager", "[  OK  ] Son : PipeWire", "[  OK  ] Bluetooth",
                "[  OK  ] Tally XIII prêt", "[  OK  ] NDI : recherche des sources", "[  OK  ] XIII Duo", "[  OK  ] Suite XIII hors ligne",
                "[  OK  ] Session graphique", "[  OK  ] Bienvenue sur OS XIII"]
        for f in range(len(msgs) * 3):
            cel = {}; vis = msgs[:f // 3 + 1]
            for i, m in enumerate(vis[-ROWS + 2:]):
                for j, ch in enumerate(m): cel[(1 + i, 2 + j)] = (ch, VERT if 2 <= j <= 5 else CLAIR)
            out.append(cel)
        for k in range(12):
            cel = {}; logo(cel, col=melange(FOND, CUIVRE, min(1, k / 6))); out.append(cel)
    # fin : le logo tient, avec la signature
    fin = {}; logo(fin, col=VERT if nom == "phosphore" else CUIVRE); signature(fin)
    out += [fin] * 4
    return out

SCRIPT = """Window.SetBackgroundTopColor(0.067,0.067,0.067); Window.SetBackgroundBottomColor(0.067,0.067,0.067);
n = %d; for (i = 0; i < n; i++) { s = "" + i; while (s.Length() < 3) s = "0" + s; img[i] = Image("f-" + s + ".png"); }
sp = Sprite(img[0]); t = 0;
fun r () { t++; k = Math.Int(t / 2); if (k >= n) k = n - 1;
  ech = Window.GetWidth() / 960; if (Window.GetHeight() / 540 < ech) ech = Window.GetHeight() / 540;
  im = img[k]; if (ech < 1) im = img[k].Scale(960 * ech, 540 * ech);
  sp.SetImage(im); sp.SetX(Window.GetWidth()/2 - im.GetWidth()/2); sp.SetY(Window.GetHeight()/2 - im.GetHeight()/2); }
Plymouth.SetRefreshFunction(r);
fun msg (texte) { m = Image.Text(texte, 0.9, 0.7, 0.5); ms = Sprite(m); ms.SetX(Window.GetWidth()/2 - m.GetWidth()/2); ms.SetY(Window.GetHeight() - 60); }
Plymouth.SetMessageFunction(msg);
"""

def generer(racine, seules=None):
    global F
    F = police()
    for nom, titre, desc in VARIANTES:
        if seules and nom not in seules: continue
        d = os.path.join(racine, "xiii-ascii-" + nom); os.makedirs(d, exist_ok=True)
        fr = frames(nom)
        for i, cel in enumerate(fr):
            rendre(cel, (8, 18, 10) if nom == "phosphore" else FOND, os.path.join(d, "f-%03d.png" % i), lignes_balayage=nom in ("crt", "phosphore"))
        open(os.path.join(d, "anim.script"), "w").write(SCRIPT % len(fr))
        open(os.path.join(d, "xiii-ascii-%s.plymouth" % nom), "w").write(
            "[Plymouth Theme]\nName=XIII ASCII — %s\nDescription=%s\nModuleName=script\n[script]\nImageDir=%s\nScriptFile=%s/anim.script\n" % (titre, desc, d, d))
        print(nom, len(fr), "images")

if __name__ == "__main__":
    generer(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/plymouth/themes", sys.argv[2:] or None)
