# OS XIII — conversions d'unités pour la recherche (« 12 pouces en cm », « 100 °F », « 50 Mb/s », « 3 Go en Mo »…)
import re

U = {   # unité → (grandeur, facteur vers l'unité de base)
    "mm": ("l", .001), "cm": ("l", .01), "m": ("l", 1), "km": ("l", 1000), "in": ("l", .0254), "pouce": ("l", .0254), "pouces": ("l", .0254), "\"": ("l", .0254),
    "ft": ("l", .3048), "pied": ("l", .3048), "pieds": ("l", .3048), "yd": ("l", .9144), "mi": ("l", 1609.344), "mile": ("l", 1609.344), "miles": ("l", 1609.344),
    "mg": ("p", .001), "g": ("p", 1), "kg": ("p", 1000), "t": ("p", 1e6), "lb": ("p", 453.592), "lbs": ("p", 453.592), "livre": ("p", 453.592), "livres": ("p", 453.592), "oz": ("p", 28.3495),
    "ml": ("v", .001), "cl": ("v", .01), "l": ("v", 1), "gal": ("v", 3.78541),
    "o": ("d", 1), "ko": ("d", 1e3), "mo": ("d", 1e6), "go": ("d", 1e9), "to": ("d", 1e12), "b": ("d", 1), "kb": ("d", 1e3), "mb": ("d", 1e6), "gb": ("d", 1e9), "tb": ("d", 1e12),
    "kio": ("d", 1024), "mio": ("d", 1024 ** 2), "gio": ("d", 1024 ** 3), "tio": ("d", 1024 ** 4),
    "kb/s": ("r", 1e3 / 8), "kbps": ("r", 1e3 / 8), "mb/s": ("r", 1e6 / 8), "mbps": ("r", 1e6 / 8), "mbit/s": ("r", 1e6 / 8), "gb/s": ("r", 1e9 / 8), "gbps": ("r", 1e9 / 8),
    "ko/s": ("r", 1e3), "mo/s": ("r", 1e6), "go/s": ("r", 1e9), "go/h": ("r", 1e9 / 3600), "to/h": ("r", 1e12 / 3600),
    "ms": ("s", .001), "s": ("s", 1), "sec": ("s", 1), "min": ("s", 60), "h": ("s", 3600), "j": ("s", 86400), "jour": ("s", 86400), "jours": ("s", 86400),
    "km/h": ("vit", 1 / 3.6), "m/s": ("vit", 1), "mph": ("vit", .44704), "noeud": ("vit", .514444), "noeuds": ("vit", .514444),
    "w": ("e", 1), "kw": ("e", 1000), "ch": ("e", 735.5), "hp": ("e", 745.7),
}
TEMP = {"c": "C", "°c": "C", "celsius": "C", "f": "F", "°f": "F", "fahrenheit": "F", "k": "K", "kelvin": "K"}
NOMS = {"l": "longueur", "p": "masse", "v": "volume", "d": "données", "r": "débit", "s": "durée", "vit": "vitesse", "e": "puissance"}
CIBLES = {"l": ["cm", "m", "in", "ft"], "p": ["g", "kg", "lb", "oz"], "v": ["ml", "l", "gal"], "d": ["Mo", "Go", "Mio", "Gio"], "r": ["Mo/s", "To/h"],
          "s": ["s", "min", "h"], "vit": ["km/h", "m/s", "mph"], "e": ["W", "kW", "ch"]}

JOLI = {"mb/s": "Mb/s", "mbps": "Mbps", "gb/s": "Gb/s", "gbps": "Gbps", "kb/s": "kb/s", "go": "Go", "mo": "Mo", "ko": "Ko", "to": "To", "gb": "GB", "mb": "MB",
        "kb": "kB", "tb": "TB", "gio": "Gio", "mio": "Mio", "kio": "Kio", "tio": "Tio", "go/h": "Go/h", "to/h": "To/h", "mo/s": "Mo/s", "go/s": "Go/s", "ko/s": "Ko/s",
        "w": "W", "kw": "kW", "l": "L", "ml": "mL", "cl": "cL"}
def joli(u): return JOLI.get(u.lower(), u)

def nombre(x):
    if 1e6 <= abs(x) < 1e15: return "{:,.0f}".format(x).replace(",", " ")
    s = ("%.6g" % x) if abs(x) < 1e15 else "%.4e" % x
    if "e" not in s and "." in s: s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")

def convertir(q):
    """Liste de chaînes « 12 in = 30,48 cm » ; vide si la requête n'est pas une conversion."""
    t = q.strip().lower().replace(",", ".").replace("→", " en ").replace(" to ", " en ").replace(" in ", " en ") if not re.match(r"^\s*[\d.]+\s*in\s*$", q.lower()) else q.lower().replace(",", ".")
    m = re.match(r"^\s*(-?[\d.]+)\s*([^\d\s][^\s]*?)\s*(?:(?:en|=)\s*([^\s]+))?\s*$", t)
    if not m: return []
    try: v = float(m.group(1))
    except ValueError: return []
    a, b = m.group(2).strip(), (m.group(3) or "").strip()
    if a in TEMP:
        k = {"C": lambda x: x + 273.15, "F": lambda x: (x - 32) * 5 / 9 + 273.15, "K": lambda x: x}[TEMP[a]](v)
        vers = {"C": k - 273.15, "F": (k - 273.15) * 9 / 5 + 32, "K": k}
        cib = [TEMP[b]] if b in TEMP else [u for u in ("C", "F", "K") if u != TEMP[a]]
        return ["%s %s = %s %s" % (nombre(v), "°" + TEMP[a] if TEMP[a] != "K" else "K", nombre(vers[c]), "°" + c if c != "K" else "K") for c in cib]
    if a not in U: return []
    g, f = U[a]; base = v * f
    cib = [b] if b in U and U[b][0] == g else [c for c in CIBLES[g] if c.lower() != a]
    out = ["%s %s = %s %s" % (nombre(v), joli(a), nombre(base / U[c.lower()][1]), joli(c)) for c in cib if c.lower() in U]
    if g == "r" and not b:      # débit vidéo : place prise par heure d'enregistrement
        out.append("%s %s ≈ %s Go par heure d'enregistrement" % (nombre(v), joli(a), nombre(base * 3600 / 1e9)))
    return out
