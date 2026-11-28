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


# ------------------------------------------------------------------ devises (taux du jour de la Banque centrale européenne)
import os, json, time, threading, urllib.request, urllib.parse, html as _html
CACHE = os.path.join(os.path.expanduser("~/.cache"), "xiii")
F_DEVISES = os.path.join(CACHE, "devises.json")
BCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ALIAS = {"€": "EUR", "euro": "EUR", "euros": "EUR", "eur": "EUR", "$": "USD", "dollar": "USD", "dollars": "USD", "usd": "USD", "£": "GBP", "livre sterling": "GBP",
         "gbp": "GBP", "chf": "CHF", "franc suisse": "CHF", "francs suisses": "CHF", "cad": "CAD", "jpy": "JPY", "yen": "JPY", "yens": "JPY", "¥": "JPY",
         "cny": "CNY", "yuan": "CNY", "yuans": "CNY", "aud": "AUD", "sek": "SEK", "nok": "NOK", "dkk": "DKK", "pln": "PLN", "czk": "CZK", "huf": "HUF",
         "brl": "BRL", "mxn": "MXN", "inr": "INR", "krw": "KRW", "try": "TRY", "zar": "ZAR", "nzd": "NZD", "sgd": "SGD", "hkd": "HKD", "ron": "RON"}
CIBLES_DEV = ["EUR", "USD", "GBP", "CHF"]
_charge = {"t": 0}


def taux():
    """{code: taux pour 1 €} ; mis à jour une fois par jour en arrière-plan (vide la toute première fois, hors ligne)."""
    try: d = json.load(open(F_DEVISES))
    except Exception: d = {}
    if time.time() - d.get("t", 0) > 6 * 3600 and time.time() - _charge["t"] > 60:
        _charge["t"] = time.time(); threading.Thread(target=maj_devises, daemon=True).start()
    return d.get("taux") or {}


def maj_devises(xml=None):
    try:
        xml = xml or urllib.request.urlopen(urllib.request.Request(BCE, headers={"User-Agent": "OS-XIII"}), timeout=10).read().decode()
        T = {c: float(r) for c, r in re.findall(r"currency=['\"](\w{3})['\"]\s+rate=['\"]([\d.]+)['\"]", xml)}
        if not T: return False
        T["EUR"] = 1.0; jour = (re.findall(r"time=['\"]([\d-]+)['\"]", xml) or [""])[0]
        os.makedirs(CACHE, exist_ok=True); json.dump({"t": time.time(), "jour": jour, "taux": T}, open(F_DEVISES + ".tmp", "w")); os.replace(F_DEVISES + ".tmp", F_DEVISES)
        return True
    except Exception:
        return False


def _devise(x):
    x = x.strip().lower()
    return ALIAS.get(x) or (x.upper() if len(x) == 3 and x.isalpha() and x.upper() in taux() else None)


def devises(q):
    """« 100 usd en eur », « 50 € », « 20 dollars en livres » → ["100 USD = 92,4 EUR (BCE, 28/11)"]."""
    t = q.strip().lower().replace(",", ".")
    t = re.sub(r"^([€$£¥])\s*([\d.]+)", r"\2 \1", t)
    m = re.match(r"^\s*([\d.]+)\s*([€$£¥]|[a-zéè ]+?)\s*(?:(?:en|in|to|=|→)\s*([€$£¥]|[a-zéè ]+?))?\s*$", t)
    if not m: return []
    try: v = float(m.group(1))
    except ValueError: return []
    a = _devise(m.group(2)); b = _devise(m.group(3) or "") if m.group(3) else None
    if not a: return []
    T = taux()
    if not T or a not in T: return []
    try: jour = json.load(open(F_DEVISES)).get("jour", "")
    except Exception: jour = ""
    j = "/".join(jour.split("-")[::-1][:2]) if jour else ""
    cib = [b] if b and b in T else [c for c in CIBLES_DEV if c != a]
    return ["%s %s = %s %s%s" % (nombre(v), a, "{:,.2f}".format(v / T[a] * T[c]).replace(",", " ").replace(".", ","), c, " (BCE, %s)" % j if j else "") for c in cib if c in T]


# ------------------------------------------------------------------ définitions (Wiktionnaire, en ligne, gardées en cache)
F_DEFS = os.path.join(CACHE, "definitions.json")
_defs_cours = set()


def mot_a_definir(q):
    m = re.match(r"^\s*(?:d[ée]f(?:inition)?|d[ée]finir|que veut dire|c'est quoi|sens de)\s*(?:de |d'|du |des |la |le |les |l')?\s*([^\s?]{2,40}(?: [^\s?]{2,40})?)\s*\??\s*$", q.strip(), re.I)
    return m.group(1).lower() if m else None


def extraire_definitions(texte, n=3):
    """Texte brut d'une page du Wiktionnaire → [(nature, définition)] (section Français)."""
    i = texte.find("== Français ==")
    if i < 0: i = texte.find("Français")
    t = texte[i:] if i >= 0 else texte
    j = re.search(r"\n== (?!Français)[^=\n]+ ==\n", t[5:])
    if j: t = t[:j.start() + 5]
    out = []; nature = ""
    NAT = ("Nom commun", "Verbe", "Adjectif", "Adverbe", "Pronom", "Préposition", "Interjection", "Conjonction", "Nom propre", "Locution")
    for l in t.splitlines():
        s = l.strip()
        if s.startswith("===") and any(x in s for x in NAT): nature = re.sub(r"\s*\d+$", "", s.strip("= ")); continue
        if nature and s and not s.startswith(("=", "(", "Note", "Synonymes", "Dérivés")) and len(s) > 15 and not re.match(r"^[\w'-]+ \\", s) and "\\" not in s[:40]:
            out.append((nature, s.rstrip()))
            if len(out) >= n: break
    return out


def definitions(mot, rappel=None):
    """Définitions en cache ; sinon recherche en ligne en arrière-plan puis rappel() (la recherche se relance)."""
    try: C = json.load(open(F_DEFS))
    except Exception: C = {}
    if mot in C: return C[mot]
    if mot in _defs_cours: return None
    _defs_cours.add(mot)
    def aller():
        try:
            u = "https://fr.wiktionary.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
                                                                                  "titles": mot, "format": "json"})
            d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "OS-XIII (Matthieu Lamotte)"}), timeout=10).read())
            p = next(iter(d["query"]["pages"].values()))
            r = extraire_definitions(p.get("extract", "")) if "missing" not in p else []
            try: C2 = json.load(open(F_DEFS))
            except Exception: C2 = {}
            C2[mot] = r; os.makedirs(CACHE, exist_ok=True); json.dump(C2, open(F_DEFS, "w"), ensure_ascii=False)
        except Exception:
            pass
        finally:
            _defs_cours.discard(mot)
            if rappel: rappel()
    threading.Thread(target=aller, daemon=True).start()
    return None
