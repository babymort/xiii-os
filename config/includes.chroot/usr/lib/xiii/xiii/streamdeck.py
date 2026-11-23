# OS XIII — Boutons XIII : pages de boutons natives pour Stream Deck Elgato (sans Companion).
# Page « Régie ATEM » : programme / preview des entrées avec retour d'état (rouge = antenne, vert = preview), CUT, AUTO, noir ;
# page « Apps XIII » : régie, prompteur, mesure audio, Multiview, mires, tally, capture… ; dernier bouton = page suivante.
# Pages modifiables dans ~/.config/xiii/streamdeck.json. Désactivé automatiquement quand Companion tourne.
# • xiii-streamdeck                : service (lancé par le bureau quand un Stream Deck est branché)
# • xiii-streamdeck --apercu F.png : image des pages telles qu'affichées (tests)
# Application développée par Matthieu Lamotte.
import os, sys, json, time, threading, subprocess, glob

CONF = os.path.expanduser("~/.config/xiii/streamdeck.json")
ROUGE, VERT, FOND, ACCENT, TEXTE = (214, 48, 49), (46, 160, 67), (29, 27, 25), (240, 179, 120), (238, 233, 227)

PAGES_DEFAUT = [
    {"nom": "Régie ATEM", "boutons": [
        {"type": "atem", "action": "programme", "entree": 1}, {"type": "atem", "action": "programme", "entree": 2},
        {"type": "atem", "action": "programme", "entree": 3}, {"type": "atem", "action": "programme", "entree": 4},
        {"type": "atem", "action": "cut", "texte": "CUT"},
        {"type": "atem", "action": "preview", "entree": 1}, {"type": "atem", "action": "preview", "entree": 2},
        {"type": "atem", "action": "preview", "entree": 3}, {"type": "atem", "action": "preview", "entree": 4},
        {"type": "atem", "action": "auto", "texte": "AUTO"},
        {"type": "app", "commande": ["xiii-regie"], "texte": "Régie"}, {"type": "app", "commande": ["xiii-prompteur"], "texte": "Prompteur"},
        {"type": "app", "commande": ["xiii-tally"], "texte": "Tally"}, {"type": "atem", "action": "noir", "texte": "NOIR"}]},
    {"nom": "Apps XIII", "boutons": [
        {"type": "app", "commande": ["xiii-regie"], "texte": "Régie"}, {"type": "app", "commande": ["xiii-prompteur"], "texte": "Prompteur"},
        {"type": "app", "commande": ["xiii-mesure-audio"], "texte": "Mesure audio"}, {"type": "app", "commande": ["xiii-multiview"], "texte": "Multiview"},
        {"type": "app", "commande": ["xiii-mires"], "texte": "Mires"}, {"type": "app", "commande": ["xiii-tally"], "texte": "Tally"},
        {"type": "app", "commande": ["xiii-capture", "ecran"], "texte": "Capture"}, {"type": "app", "commande": ["xiii-capture", "video"], "texte": "Enregistrer"},
        {"type": "app", "commande": ["xiii-suite", "conduco"], "texte": "CONDUCO"}, {"type": "app", "commande": ["xiii-suite", "backupo"], "texte": "BACKUPO"},
        {"type": "app", "commande": ["xiii-envoi"], "texte": "Envoi"}, {"type": "app", "commande": ["xiii-fichiers"], "texte": "Fichiers"},
        {"type": "app", "commande": ["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"], "texte": "Micro on/off"},
        {"type": "app", "commande": ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], "texte": "Son on/off"}]},
]


def pages():
    try:
        P = json.load(open(CONF))
        if isinstance(P, list) and P: return P
    except Exception:
        pass
    return PAGES_DEFAUT


def atem_ip():
    try: return json.load(open(os.path.expanduser("~/.config/xiii/blackmagic.json"))).get("atem_ip") or ""
    except Exception: return ""


def police(taille):
    from PIL import ImageFont
    for f in ("/usr/share/fonts/truetype/ibm-plex/IBMPlexSans-Bold.ttf", "/usr/share/fonts/opentype/ibm-plex/IBMPlexSans-Bold.otf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            try: return ImageFont.truetype(f, taille)
            except Exception: pass
    return ImageFont.load_default()


def dessiner(b, etat, taille=72, page_suivante=None):
    """Image PIL d'un bouton (carré taille × taille)."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (taille, taille), (0, 0, 0)); d = ImageDraw.Draw(im)
    fond, coul, texte, sous = FOND, ACCENT, b.get("texte") or "", ""
    if page_suivante is not None:
        texte, sous, coul = "PAGE", page_suivante, TEXTE
    elif b.get("type") == "atem":
        a = b.get("action"); e = b.get("entree")
        nom = (etat.get("courts") or {}).get(e) or (etat.get("noms") or {}).get(e) or (str(e) if e else "")
        if a == "programme":
            texte, sous = nom or str(e), "PROG"
            if etat.get("programme") == e: fond, coul = ROUGE, (255, 255, 255)
        elif a == "preview":
            texte, sous = nom or str(e), "PREV"
            if etat.get("preview") == e: fond, coul = VERT, (255, 255, 255)
        elif a == "noir":
            if etat.get("noir"): fond, coul = ROUGE, (255, 255, 255)
        elif a == "auto" and etat.get("transition"):
            fond, coul = ROUGE, (255, 255, 255)
        if not etat.get("connecte"): coul = (120, 113, 104)
    r = max(6, taille // 9)
    d.rounded_rectangle((2, 2, taille - 3, taille - 3), r, fill=fond, outline=(60, 55, 50) if fond == FOND else fond, width=2)
    lignes = []
    for mot in texte.split():
        if lignes and len(lignes[-1] + " " + mot) <= 9: lignes[-1] += " " + mot
        else: lignes.append(mot)
    lignes = lignes[:3] or [""]
    lg = max(len(l) for l in lignes); f = police(int(taille * (.22 if lg <= 6 else .17 if lg <= 8 else .14)))
    hl = int(taille * .24); y0 = (taille - hl * len(lignes)) // 2 - (taille // 10 if sous else 0)
    for i, l in enumerate(lignes):
        w = d.textlength(l, font=f); d.text(((taille - w) / 2, y0 + i * hl), l, font=f, fill=coul)
    if sous:
        fs = police(int(taille * .13)); w = d.textlength(sous, font=fs)
        d.text(((taille - w) / 2, taille - taille * .27), sous, font=fs, fill=coul if fond != FOND else (155, 147, 138))
    return im


class Boutons:
    def __init__(self, deck):
        self.deck = deck; self.P = pages(); self.i = 0; self.etat = {"connecte": False}; self.atem = None; self.verrou = threading.Lock()
        ip = atem_ip()
        if ip:
            sys.path.insert(0, "/usr/lib/xiii")
            from xiii.atem import ATEM
            self.atem = ATEM(ip, self.maj_atem); self.atem.start()

    def maj_atem(self, e):
        self.etat = e; self.dessiner_tout()

    def boutons_page(self):
        n = self.deck.key_count(); L = list(self.P[self.i]["boutons"])
        if len(self.P) > 1: L = L[:n - 1] + [None] * max(0, n - 1 - len(L)) + ["page"]
        else: L = L[:n] + [None] * max(0, n - len(L))
        return L

    def dessiner_tout(self):
        from StreamDeck.ImageHelpers import PILHelper
        with self.verrou:
            L = self.boutons_page(); taille = self.deck.key_image_format()["size"][0]
            for k, b in enumerate(L):
                if b is None: im = dessiner({"texte": ""}, self.etat, taille)
                elif b == "page": im = dessiner({}, self.etat, taille, self.P[(self.i + 1) % len(self.P)]["nom"][:9])
                else: im = dessiner(b, self.etat, taille)
                im = im.resize(self.deck.key_image_format()["size"])
                self.deck.set_key_image(k, PILHelper.to_native_key_format(self.deck, im) if hasattr(PILHelper, "to_native_key_format") else PILHelper.to_native_format(self.deck, im))

    def appui(self, deck, k, enfonce):
        if not enfonce: return
        L = self.boutons_page(); b = L[k] if k < len(L) else None
        if b == "page":
            self.i = (self.i + 1) % len(self.P); self.dessiner_tout(); return
        if not b: return
        if b.get("type") == "app":
            subprocess.Popen(b["commande"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        elif b.get("type") == "atem" and self.atem:
            a = b.get("action")
            if a == "programme": self.atem.programme(b["entree"])
            elif a == "preview": self.atem.preview(b["entree"])
            elif a in ("cut", "auto", "noir"): getattr(self.atem, a)()


def companion_actif():
    return subprocess.run(["pgrep", "-f", "companion"], capture_output=True).returncode == 0


def present():
    for d in glob.glob("/sys/bus/usb/devices/*/idVendor"):
        try:
            if open(d).read().strip() == "0fd9": return True
        except OSError:
            pass
    return False


def service():
    try:
        from StreamDeck.DeviceManager import DeviceManager
    except ImportError:
        print("Boutons XIII : bibliothèque StreamDeck absente (paquet python3-elgato-streamdeck)"); return 1
    actifs = {}
    while True:
        if companion_actif():
            for b in actifs.values():
                try: b.deck.reset(); b.deck.close()
                except Exception: pass
            actifs.clear(); time.sleep(10); continue
        try: decks = DeviceManager().enumerate()
        except Exception: decks = []
        for d in decks:
            try:
                sid = d.id()
                if sid in actifs or not d.is_visual(): continue
                d.open(); d.reset(); d.set_brightness(70)
                b = Boutons(d); d.set_key_callback(b.appui); b.dessiner_tout(); actifs[sid] = b
                print("Boutons XIII :", d.deck_type(), d.key_count(), "touches", flush=True)
            except Exception as e:
                print("Boutons XIII :", e, flush=True)
        for sid, b in list(actifs.items()):
            try:
                if not b.deck.connected(): raise OSError
            except Exception:
                actifs.pop(sid, None)
        if not actifs and not present(): return 0      # plus rien de branché : le bureau relancera le service
        time.sleep(5)


def apercu(sortie, cles=15, colonnes=5):
    """Les pages comme sur un Stream Deck 15 touches, état ATEM d'exemple (entrée 2 à l'antenne, 3 en preview)."""
    from PIL import Image, ImageDraw
    etat = {"connecte": True, "programme": 2, "preview": 3, "courts": {1: "CAM1", 2: "CAM2", 3: "CAM3", 4: "PC"}}
    class Faux:
        def key_count(self): return cles
    P = pages(); t = 96; m = 12; lig = (cles + colonnes - 1) // colonnes
    out = Image.new("RGB", (len(P) * (colonnes * (t + m) + 40), lig * (t + m) + 50), (20, 18, 16)); dd = ImageDraw.Draw(out)
    for i, p in enumerate(P):
        b = Boutons.__new__(Boutons); b.deck = Faux(); b.P = P; b.i = i
        x0 = i * (colonnes * (t + m) + 40) + 20; dd.text((x0, 12), p["nom"], font=police(18), fill=ACCENT)
        for k, bt in enumerate(b.boutons_page()):
            im = dessiner({"texte": ""}, etat, t) if bt is None else dessiner({}, etat, t, P[(i + 1) % len(P)]["nom"][:9]) if bt == "page" else dessiner(bt, etat, t)
            out.paste(im, (x0 + (k % colonnes) * (t + m), 40 + (k // colonnes) * (t + m)))
    out.save(sortie); print("OK        aperçu Stream Deck :", sortie)


def main():
    a = sys.argv[1:]
    if a[:1] == ["--apercu"]: apercu(a[1] if len(a) > 1 else "/tmp/streamdeck.png"); return
    sys.exit(service() or 0)
