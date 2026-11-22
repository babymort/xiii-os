# OS XIII — rapport de déchargement (dérush) en PDF : en-tête du projet, support, destinations et leur vérification,
# chiffres clés (fichiers, taille, durée des rushes, débit), puis la liste complète des fichiers (durée, taille,
# empreinte, état). Rangé avec les rushes et envoyé dans DOSSIER XIII. Dessiné avec Cairo (aucune dépendance en plus).
import os, datetime, subprocess, json
import cairo

A4 = (595.28, 841.89); M = 42
ACC = (0.94, 0.70, 0.47); TXT = (0.12, 0.11, 0.10); ATT = (0.45, 0.42, 0.39); OK = (0.25, 0.62, 0.35); KO = (0.85, 0.27, 0.25)
MEDIA = (".mov", ".mxf", ".mp4", ".m4v", ".mts", ".m2ts", ".avi", ".mkv", ".braw", ".r3d", ".ari", ".wav", ".bwf", ".mp3", ".aif", ".aiff", ".crm", ".insv")

def humain(n):
    for u in ("o", "Ko", "Mo", "Go", "To"):
        if abs(n) < 1000 or u == "To": return ("%.0f %s" if u == "o" else "%.1f %s") % (n, u)
        n /= 1000.0

def duree_s(p):
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", p], capture_output=True, text=True, timeout=15)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return None

def hms(s):
    s = int(s or 0); return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)

class Page:
    def __init__(self, f):
        self.s = cairo.PDFSurface(f, *A4); self.c = cairo.Context(self.s); self.n = 1; self.y = M
    def police(self, taille, gras=False, mono=False):
        self.c.select_font_face("IBM Plex Mono" if mono else "IBM Plex Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if gras else cairo.FONT_WEIGHT_NORMAL)
        self.c.set_font_size(taille)
    def texte(self, x, y, t, taille=9, gras=False, coul=TXT, mono=False, droite=None, maxl=None):
        self.police(taille, gras, mono); self.c.set_source_rgb(*coul); t = str(t)
        if maxl:
            while t and self.c.text_extents(t).x_advance > maxl: t = t[:-2] + "…" if len(t) > 2 else ""
        if droite is not None: x = droite - self.c.text_extents(t).x_advance
        self.c.move_to(x, y); self.c.show_text(t)
    def pied(self, total=None):
        self.c.set_source_rgb(*ATT); self.police(7)
        self.c.move_to(M, A4[1] - 22); self.c.show_text("OS XIII — rapport de déchargement · Application développée par Matthieu Lamotte")
        t = "page %d" % self.n; self.c.move_to(A4[0] - M - self.c.text_extents(t).x_advance, A4[1] - 22); self.c.show_text(t)
    def suite(self):
        self.pied(); self.c.show_page(); self.n += 1; self.y = M
    def place(self, h):
        if self.y + h > A4[1] - 40: self.suite(); return True
        return False
    def fin(self):
        self.pied(); self.s.finish()

def creer(f, t, lignes, extra):
    """t : transfert (backup.Moteur) ; lignes : [rel, taille, empreinte, statut, statut2] ; extra : projet, dit, destinations…"""
    P = Page(f); c = P.c
    ok = sum(1 for l in lignes if l[3] == "OK" and (len(l) < 5 or l[4] in ("OK", "")))
    ko = len(lignes) - ok
    octets = sum(l[1] for l in lignes)
    medias = [l for l in lignes if os.path.splitext(l[0])[1].lower() in MEDIA]
    durees = {}
    for l in medias[:400]:                     # durée de chaque rush (400 premiers)
        d = duree_s(os.path.join(t["dossier"], l[0]))
        if d: durees[l[0]] = d
    # ---- bandeau
    c.set_source_rgb(*ACC); c.rectangle(0, 0, A4[0], 6); c.fill()
    P.texte(M, 58, "Rapport de déchargement", 22, True)
    P.texte(M, 76, "%s — %s" % (extra.get("projet") or "Sans projet", t["nom_support"]), 11, False, ATT)
    etat = "Copies vérifiées" if not ko else "%d fichier(s) en erreur" % ko
    c.set_source_rgb(*(OK if not ko else KO)); c.rectangle(A4[0] - M - 150, 40, 150, 26); c.fill()
    P.texte(A4[0] - M - 140, 57, ("✓ " if not ko else "⚠ ") + etat, 10, True, (1, 1, 1))
    # ---- informations
    y = 104
    debut = datetime.datetime.fromtimestamp(t.get("debut", 0)); fin = datetime.datetime.fromtimestamp(t.get("fin", t.get("debut", 0)))
    infos = [("Transfert", t["nom_transfert"]), ("Support", t["nom_support"]), ("Source", t["source"]),
             ("Début", debut.strftime("%d/%m/%Y à %H:%M:%S")), ("Fin", fin.strftime("%d/%m/%Y à %H:%M:%S")), ("Durée", hms((fin - debut).total_seconds())),
             ("Algorithme", {"xxh64": "xxHash64", "md5": "MD5", "sha256": "SHA-256"}.get(t["algo"], t["algo"])), ("Opérateur (DIT)", extra.get("dit", "")),
             ("Ordinateur", extra.get("machine", ""))]
    for i, (k, v) in enumerate(infos):
        x = M + (i % 2) * 260; yy = y + (i // 2) * 16
        P.texte(x, yy, k, 8, False, ATT); P.texte(x + 80, yy, v, 8.5, True, maxl=175)
    y += (len(infos) + 1) // 2 * 16 + 14
    # ---- destinations
    P.texte(M, y, "Copies", 11, True); y += 14
    for i, d in enumerate(extra.get("destinations", [])):
        st = d.get("statut", "OK")
        c.new_sub_path(); c.set_source_rgb(*(OK if st == "OK" else KO)); c.arc(M + 4, y - 3, 3.5, 0, 6.29); c.fill()
        P.texte(M + 14, y, "Copie %d : %s" % (i + 1, d["chemin"]), 8.5, maxl=380); P.texte(0, y, st, 8.5, True, OK if st == "OK" else KO, droite=A4[0] - M); y += 14
    y += 8
    # ---- chiffres clés
    cles = [("Fichiers", str(len(lignes))), ("Rushes", str(len(medias))), ("Taille", humain(octets)),
            ("Durée des rushes", hms(sum(durees.values())) if durees else "—"), ("Débit moyen", humain(octets / max(1, (fin - debut).total_seconds())) + "/s"), ("Vérifiés", "%d / %d" % (ok, len(lignes)))]
    w = (A4[0] - 2 * M - 5 * 8) / 6
    for i, (k, v) in enumerate(cles):
        x = M + i * (w + 8)
        c.set_source_rgb(0.96, 0.94, 0.92); c.rectangle(x, y, w, 44); c.fill()
        P.texte(x + 7, y + 15, k, 7, False, ATT); P.texte(x + 7, y + 34, v, 11, True, maxl=w - 12)
    y += 58
    if medias:
        noms = sorted(os.path.basename(l[0]) for l in medias)
        P.texte(M, y, "Premier rush : %s   ·   dernier rush : %s" % (noms[0], noms[-1]), 8.5, False, ATT); y += 18
    # ---- liste des fichiers
    P.y = y
    def entete_tab():
        c.set_source_rgb(*ACC); c.rectangle(M, P.y, A4[0] - 2 * M, 16); c.fill()
        for x, tt in ((M + 4, "Fichier"), (M + 268, "Durée"), (M + 318, "Taille"), (M + 372, "Empreinte"), (A4[0] - M - 34, "État")): P.texte(x, P.y + 11, tt, 7.5, True)
        P.y += 18
    entete_tab()
    for i, l in enumerate(sorted(lignes, key=lambda l: l[0])):
        if P.place(12): entete_tab()
        if i % 2: c.set_source_rgb(0.975, 0.97, 0.96); c.rectangle(M, P.y - 3, A4[0] - 2 * M, 12); c.fill()
        st = l[3] if len(l) < 5 or not l[4] else ("OK" if l[3] == l[4] == "OK" else "ERREUR")
        P.texte(M + 4, P.y + 6, l[0], 7, maxl=258); P.texte(M + 268, P.y + 6, hms(durees[l[0]]) if l[0] in durees else "", 7, mono=True)
        P.texte(M + 318, P.y + 6, humain(l[1]), 7); P.texte(M + 372, P.y + 6, l[2][:24], 6.5, mono=True, coul=ATT)
        P.texte(A4[0] - M - 34, P.y + 6, st, 7, True, OK if st == "OK" else KO)
        P.y += 12
    P.fin()
    return f

def creer_journee(f, jour, L, extra):
    """Rapport de la journée de tournage : un bloc par support déchargé, totaux en tête."""
    P = Page(f); c = P.c
    tot = sum(e["octets"] for e in L); nf = sum(e["fichiers"] for e in L); ko = sum(e["fichiers"] - e["ok"] for e in L)
    c.set_source_rgb(*ACC); c.rectangle(0, 0, A4[0], 6); c.fill()
    d = datetime.date.fromisoformat(jour)
    JR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]; MS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    P.texte(M, 58, "Rapport de tournage", 22, True)
    P.texte(M, 76, "%s — %s %d %s %d" % (extra.get("projet") or "Sans projet", JR[d.weekday()].capitalize(), d.day, MS[d.month - 1], d.year), 11, False, ATT)
    y = 100
    cles = [("Supports déchargés", str(len(L))), ("Fichiers", str(nf)), ("Volume du jour", humain(tot)), ("Erreurs", str(ko)), ("Opérateur", extra.get("dit", ""))]
    w = (A4[0] - 2 * M - 4 * 8) / 5
    for i, (k, v) in enumerate(cles):
        x = M + i * (w + 8); c.set_source_rgb(0.96, 0.94, 0.92); c.rectangle(x, y, w, 44); c.fill()
        P.texte(x + 7, y + 15, k, 7, False, ATT); P.texte(x + 7, y + 34, v, 11, True, KO if (k == "Erreurs" and ko) else TXT, maxl=w - 12)
    P.y = y + 64
    for e in sorted(L, key=lambda e: e["date"]):
        if P.place(70): pass
        y = P.y; okk = e["ok"] == e["fichiers"]
        c.set_source_rgb(*(OK if okk else KO)); c.rectangle(M, y - 10, 4, 52); c.fill()
        P.texte(M + 12, y, "%s  ·  %s" % (e["support"], e["transfert"]), 11, True, maxl=330)
        P.texte(0, y, e["date"][11:16], 10, True, ATT, droite=A4[0] - M)
        P.texte(M + 12, y + 15, "%d fichiers · %s · %s" % (e["fichiers"], humain(e["octets"]), ("rushes %s → %s" % (e["premier"], e["dernier"])) if e.get("premier") else ""), 8.5, maxl=470)
        dd = " · ".join("copie %d : %s (%s)" % (i + 1, os.path.basename(os.path.dirname(x["chemin"])) + "/" + os.path.basename(x["chemin"]), x["statut"]) for i, x in enumerate(e.get("destinations") or []))
        P.texte(M + 12, y + 29, dd, 8, False, ATT, maxl=470)
        P.texte(M + 12, y + 41, "Rapport détaillé : " + os.path.basename(e.get("pdf") or "—"), 7.5, False, ATT, maxl=470)
        P.y = y + 62
    P.fin()
    return f
