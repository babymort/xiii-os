# OS XIII — bureaux virtuels (façon Windows 11 / macOS Spaces) : ajouter, renommer, retirer, un fond d'écran par bureau.
# labwc garde le nombre et les noms dans rc.xml (<desktops number="N"><names><name>…) ; le bureau affiché est suivi par
# la barre : chaque raccourci « aller au bureau » de labwc lance aussi « xiii-ctl bureau-est-… ».
#   Ctrl + Super + ← / →   bureau précédent / suivant      Ctrl + Super + D   nouveau bureau
#   Ctrl + Super + F4      retirer le dernier bureau       Super + Alt + 1…6  aller au bureau n
# Application développée par Matthieu Lamotte.
import os, subprocess
import xml.etree.ElementTree as ET
from gi.repository import GLib

RC = os.path.join(GLib.get_user_config_dir(), "labwc", "rc.xml")
COURANT = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "xiii-bureau")
MAXI = 6


def _loc(t): return t.split("}")[-1]


def lire(rc=RC):
    """(nombre de bureaux, [noms])."""
    try:
        r = ET.parse(rc).getroot(); d = next((e for e in r if _loc(e.tag) == "desktops"), None)
        n = int(d.get("number", "1")) if d is not None else 1
        noms = [x.text or "" for x in d.iter() if _loc(x.tag) == "name"] if d is not None else []
    except Exception:
        n, noms = 1, []
    n = max(1, min(MAXI, n))
    return n, [(noms[i] if i < len(noms) and noms[i] else "Bureau %d" % (i + 1)) for i in range(n)]


def ecrire(n, noms, rc=RC, recharger=True):
    n = max(1, min(MAXI, n)); t = ET.parse(rc); r = t.getroot()
    d = next((e for e in r if _loc(e.tag) == "desktops"), None)
    if d is None: d = ET.SubElement(r, "desktops")
    d.set("number", str(n))
    for x in [x for x in d if _loc(x.tag) == "names"]: d.remove(x)
    ns = ET.SubElement(d, "names")
    for i in range(n): ET.SubElement(ns, "name").text = (noms[i] if i < len(noms) and noms[i] else "Bureau %d" % (i + 1))
    if not any(_loc(x.tag) == "popupTime" for x in d): ET.SubElement(d, "popupTime").text = "700"
    t.write(rc, encoding="UTF-8", xml_declaration=True)
    if recharger:
        try: subprocess.Popen(["labwc", "--reconfigure"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError: pass
    return n


def courant():
    try: return max(1, int(open(COURANT).read()))
    except Exception: return 1


def noter(x, n=None):
    """x = « left », « right » ou un numéro (comme l'attribut « to » de labwc) → nouveau bureau courant (bouclage)."""
    n = n or lire()[0]; c = courant()
    if x == "left": c = c - 1 if c > 1 else n
    elif x == "right": c = c + 1 if c < n else 1
    elif str(x).isdigit(): c = min(n, max(1, int(x)))
    try: open(COURANT, "w").write(str(c))
    except Exception: pass
    return c


def ajouter():
    n, noms = lire()
    if n >= MAXI: return n
    return ecrire(n + 1, noms + ["Bureau %d" % (n + 1)])


def retirer():
    """Retire le dernier bureau (labwc ramène ses fenêtres sur le bureau précédent)."""
    n, noms = lire()
    if n <= 1: return n
    if courant() > n - 1: noter(str(n - 1), n - 1)
    return ecrire(n - 1, noms[:n - 1])


def renommer(i, nom):
    n, noms = lire(); noms[i - 1] = nom.strip() or "Bureau %d" % i
    return ecrire(n, noms)
