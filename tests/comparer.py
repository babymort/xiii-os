#!/usr/bin/env python3
# OS XIII — tests visuels : compare chaque capture de la vérification ZZ à celle de la vérification précédente.
# Une page qui change sans raison (comme les colonnes du mode Mac qui s'empilaient) saute aux yeux :
# image « diff-*.png » où les zones changées sont en rouge, et liste dans regressions.txt.
#   comparer.py <captures précédentes> <nouvelles captures>
import sys, os
from PIL import Image, ImageChops, ImageFilter

SEUIL = 0.015      # au-delà de 1,5 % de pixels changés, la capture est signalée
IGNORER = ("clic-",)   # captures d'interaction (dépendent du temps)

def comparer(a, b):
    A = Image.open(a).convert("RGB"); B = Image.open(b).convert("RGB")
    if A.size != B.size: return 1.0, None
    d = ImageChops.difference(A, B).convert("L").point(lambda v: 255 if v > 24 else 0)
    d = d.filter(ImageFilter.MaxFilter(3))
    n = sum(d.histogram()[255:]) / (A.size[0] * A.size[1])
    if n < SEUIL: return n, None
    rouge = Image.new("RGB", B.size, (255, 40, 40))
    v = Image.blend(B, Image.new("RGB", B.size, (0, 0, 0)), 0.45); v.paste(rouge, mask=d)
    return n, v

def main(prec, neuf):
    lignes, nb = [], 0
    for f in sorted(os.listdir(neuf)):
        if not f.endswith(".png") or f.startswith("diff-") or f.startswith(IGNORER): continue
        p = os.path.join(prec, f)
        if not os.path.exists(p): lignes.append("NOUVELLE  %s" % f); continue
        try: n, img = comparer(p, os.path.join(neuf, f))
        except Exception as e: lignes.append("ERREUR    %s (%s)" % (f, e)); continue
        if img is not None or n >= SEUIL:
            nb += 1; lignes.append("CHANGÉE   %s : %.1f %% de l'image" % (f, n * 100))
            if img is not None: img.save(os.path.join(neuf, "diff-" + f))
    for f in sorted(os.listdir(prec)):
        if f.endswith(".png") and not f.startswith("diff-") and not os.path.exists(os.path.join(neuf, f)): lignes.append("DISPARUE  %s" % f)
    open(os.path.join(neuf, "regressions.txt"), "w").write(
        "Tests visuels — comparaison avec la vérification précédente\n%d capture(s) changée(s) au-delà de %.1f %%\n\n%s\n" % (nb, SEUIL * 100, "\n".join(lignes) or "Aucun changement."))
    print("%d capture(s) changée(s)" % nb)

if __name__ == "__main__":
    if os.path.isdir(sys.argv[1]): main(sys.argv[1], sys.argv[2])
    else: open(os.path.join(sys.argv[2], "regressions.txt"), "w").write("Pas de vérification précédente : référence créée.\n")
