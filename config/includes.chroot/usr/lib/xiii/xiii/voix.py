# OS XIII — Commandes vocales XIII (Super + H) : on parle, OS XIII comprend, hors ligne (Vosk, sur ce PC, rien n'est envoyé).
# « Ouvre CONDUCO », « lance la régie », « cherche les vidéos de cette semaine », « trouve le devis Dupont »,
# « mode production », « projet Concert », « capture d'écran », « enregistre l'écran », « coupe le son », « monte le volume »,
# « ne pas déranger », « quelle heure est-il », « demande à l'IA … ».
# Application développée par Matthieu Lamotte.
import os, sys, re, json, time, glob, subprocess, unicodedata, threading
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import config, systeme as S

DUREE = 5.0


def plat(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def ecouter(duree=DUREE):
    """Enregistre le micro (16 kHz mono) et transcrit avec Vosk. → texte"""
    from .synthese import modele
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    m = modele()
    if not m: raise RuntimeError("modèle vocal absent : ouvrez une fois l'Assistant de synthèse pour le télécharger (40 Mo)")
    p = subprocess.Popen(["ffmpeg", "-loglevel", "quiet", "-f", "pulse", "-i", "default", "-t", str(duree), "-ar", "16000", "-ac", "1", "-f", "s16le", "-"], stdout=subprocess.PIPE)
    rec = KaldiRecognizer(Model(m), 16000); silence = 0; parle = False; t0 = time.time()
    while True:
        b = p.stdout.read(3200)
        if not b: break
        niv = max(abs(int.from_bytes(b[i:i + 2], "little", signed=True)) for i in range(0, len(b) - 1, 64))
        if niv > 1500: parle = True; silence = 0
        elif parle: silence += 1
        rec.AcceptWaveform(b)
        if parle and silence > 8: p.terminate(); break        # ~0,8 s de silence après avoir parlé : c'est fini
    return json.loads(rec.FinalResult()).get("text", "")


def comprendre(t):
    """Texte → (action, argument, phrase de réponse)."""
    t0 = plat(t).strip()
    if not t0: return None, None, "Je n'ai rien entendu."
    m = re.match(r"^(?:ouvre|ouvrir|lance|lancer|demarre|demarrer|affiche)\s+(?:le |la |les |l'|mon |ma )?(.+)$", t0)
    if m: return "ouvrir", m.group(1), None
    m = re.match(r"^(?:cherche|chercher|trouve|trouver|ou est|ou sont)\s+(.+)$", t0)
    if m: return "chercher", m.group(1), None
    m = re.match(r"^(?:mode|passe en mode|passer en mode)\s+(classique|production|fiction|multicam|multi cam|backup|gaming|jeu)", t0)
    if m: return "mode", m.group(1).replace("multi cam", "multicam").replace("jeu", "gaming"), "Mode %s" % m.group(1)
    m = re.match(r"^(?:projet|ouvre le projet|passe au projet|change de projet)\s+(.+)$", t0)
    if m: return "projet", m.group(1), None
    if re.search(r"capture d.?ecran|copie d.?ecran", t0): return "cmd", ["xiii-capture", "ecran"], "Capture d'écran"
    if re.search(r"enregistr\w* (l.?)?ecran|filme l.?ecran", t0): return "cmd", ["xiii-enregistreur"], "Enregistreur d'écran"
    if re.search(r"coupe le son|silence|muet", t0): return "cmd", ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"], "Son coupé"
    if re.search(r"remets? le son|reactive le son", t0): return "cmd", ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], "Son remis"
    if re.search(r"monte le (son|volume)|plus fort", t0): return "cmd", ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "15%+"], "Plus fort"
    if re.search(r"baisse le (son|volume)|moins fort", t0): return "cmd", ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "15%-"], "Moins fort"
    if re.search(r"ne pas deranger", t0): return "dnd", None, "Ne pas déranger activé"
    if re.search(r"quelle heure|l.?heure", t0): return "dire", None, time.strftime("Il est %H h %M")
    if re.search(r"quel jour|la date", t0):
        j = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][time.localtime().tm_wday]; return "dire", None, "Nous sommes %s %s" % (j, time.strftime("%d/%m/%Y"))
    if re.search(r"resume (ce|le) (fichier|document)", t0): return "resumer", None, None
    m = re.match(r"^(?:demande a l.?ia|demande a claude|question)\s+(.+)$", t0)
    if m: return "ia", t, None
    if re.search(r"verrouill", t0): return "cmd", ["swaylock", "-f"], "Verrouillage"
    return "ia", t, "Je transmets à l'IA : « %s »" % t


def chercher_filtres(q):
    """« les vidéos de cette semaine du projet concert » → (texte, type, jours)"""
    typ = None; jours = None
    for k, v in (("video", "video"), ("rush", "video"), ("photo", "image"), ("image", "image"), ("son", "audio"), ("audio", "audio"), ("musique", "audio"),
                 ("pdf", "pdf"), ("document", "doc"), ("devis", "doc"), ("contrat", "doc")):
        if re.search(r"\b%ss?\b" % k, q): typ = v; break
    for rx, n in ((r"aujourd.?hui", 1), (r"hier", 2), (r"(cette|de la) semaine", 7), (r"semaine derniere", 14), (r"(ce|du) mois", 31), (r"mois dernier", 62)):
        if re.search(rx, q): jours = n; break
    vides = r"\b(les|le|la|l|des|de|du|d|mes|mon|ma|tous|toutes|fichiers?|videos?|rushs?|photos?|images?|sons?|audios?|musiques?|pdf|documents?|aujourd.?hui|hier|cette|ce|semaine|derniere|dernier|mois|projet)\b"
    texte = re.sub(r"\s+", " ", re.sub(vides, " ", q)).strip()
    if typ == "doc" and re.search(r"\bdevis\b", q) and "devis" not in texte.split(): texte = ("devis " + texte).strip()
    return texte, typ, jours


def executer(action, arg, phrase):
    from . import apps
    if action == "ouvrir":
        a = plat(arg); meilleur = None
        for app in apps.toutes():
            n = plat(app.get_display_name())
            if a == n or a in n or (n.split(" ")[0] == a.split(" ")[0] and len(a) > 3):
                if not meilleur or len(n) < len(plat(meilleur.get_display_name())): meilleur = app
        if meilleur: apps.lancer(meilleur); return "J'ouvre %s" % meilleur.get_display_name()
        outils = {"conduco", "plano", "syno", "deviso", "callsheeto", "call sheeto", "backupo", "dossier", "decoup", "casto", "matos", "encodo", "scripto", "graphico", "melango"}
        if a.replace(" ", "") in {o.replace(" ", "") for o in outils}:
            S.detacher(["xiii-suite", a.replace(" ", "")]); return "J'ouvre %s" % arg.upper()
        return "Je ne trouve pas « %s »." % arg
    if action == "chercher":
        texte, typ, jours = chercher_filtres(plat(arg))
        S.detacher(["xiii-fichiers", "--chercher", texte] + (["--type", typ] if typ else []) + (["--jours", str(jours)] if jours else []))
        return "Je cherche %s" % arg
    if action == "mode": config.modifier(mode_bureau=arg); return phrase
    if action == "projet":
        from . import projets
        L = projets.liste(); a = plat(arg)
        p = next((x for x in L if plat(x) == a), None) or next((x for x in L if a in plat(x)), None)
        if p: projets.activer(p); return "Projet « %s »" % p
        return "Pas de projet « %s »." % arg
    if action == "cmd": S.detacher(arg); return phrase
    if action == "dnd": config.modifier(ne_pas_deranger=True); return phrase
    if action == "dire": return phrase
    if action == "resumer":
        return "Dans Fichiers : clic droit sur le document › « Résumer avec l'IA »."
    if action == "ia": S.detacher(["xiii-ia", "--demander", arg]); return phrase or "Je demande à l'IA"


def texte_de(f):
    """Texte d'un document pour le résumé : PDF, Word, LibreOffice, texte."""
    e = f.lower()
    try:
        if e.endswith(".pdf"): return subprocess.run(["pdftotext", "-layout", f, "-"], capture_output=True, text=True, timeout=60).stdout
        if e.endswith((".docx", ".odt", ".pptx", ".odp")):
            import zipfile
            z = zipfile.ZipFile(f); noms = [n for n in z.namelist() if re.search(r"(word/document|content|ppt/slides/slide\d+)\.xml$", n)]
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", " ".join(z.read(n).decode("utf-8", "ignore") for n in noms)))
        if e.endswith((".md", ".txt", ".csv", ".srt", ".json", ".html", ".fdx")): return open(f, encoding="utf-8", errors="ignore").read()
    except Exception:
        pass
    return ""


def resumer(f):
    """Résumé d'un document par l'IA choisie en haut de l'écran (le texte part vers cette IA, avec votre compte)."""
    t = texte_de(f).strip()
    if not t:
        S.detacher(["notify-send", "-a", "IA XIII", "Résumé impossible", "Ce type de fichier ne contient pas de texte lisible."]); return
    if len(t) > 24000: t = t[:24000] + "\n[…]"
    S.detacher(["xiii-ia", "--demander", "Résume ce document en français (points clés, chiffres, décisions, actions) :\n\n« %s »\n\n%s" % (os.path.basename(f), t)])


class Voix(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.voix")

    def do_activate(self):
        if getattr(self, "win", None): return
        from .ui import boite, label, ico
        from .appli import preparer
        preparer(".voix { background: alpha(#1d1b19, .94); border-radius: 22px; padding: 18px 26px; border: 1px solid alpha(#f0b378, .5); }"
                 " .voix-t { font-size: 18px; font-weight: 600; }")
        w = Gtk.Window(application=self, title="Commandes vocales XIII", decorated=False, resizable=False); self.win = w
        try:
            gi.require_version("Gtk4LayerShell", "1.0")
            from gi.repository import Gtk4LayerShell as LS
            LS.init_for_window(w); LS.set_layer(w, LS.Layer.OVERLAY); LS.set_anchor(w, LS.Edge.TOP, True); LS.set_margin(w, LS.Edge.TOP, 70)
        except Exception: pass
        b = boite(False, 14, "voix"); b.append(ico("mic", 28, "c")); v = boite(True, 2)
        self.t = label("Je vous écoute…", "voix-t"); self.s = label("Ex. « ouvre CONDUCO », « cherche les vidéos de cette semaine », « mode production »", "petit", "attenue")
        v.append(self.t); v.append(self.s); b.append(v); w.set_child(b); w.present()
        def fond():
            try:
                txt = ecouter()
                GLib.idle_add(lambda: (self.t.set_text("« %s »" % txt if txt else "Je n'ai rien entendu."), False)[1])
                a, arg, ph = comprendre(txt)
                rep = executer(a, arg, ph) if a else ph
            except Exception as e:
                rep = "Commandes vocales indisponibles : %s" % e
            GLib.idle_add(lambda: (self.s.set_text(rep or ""), False)[1]); time.sleep(2.2)
            GLib.idle_add(self.quit)
        threading.Thread(target=fond, daemon=True).start()


def main():
    a = sys.argv[1:]
    if a[:1] == ["--comprendre"]:          # tests : xiii-voix --comprendre "cherche les vidéos de cette semaine"
        act, arg, ph = comprendre(" ".join(a[1:])); print(json.dumps({"action": act, "arg": arg, "phrase": ph, "filtres": chercher_filtres(plat(arg)) if act == "chercher" else None}, ensure_ascii=False)); return
    if a[:1] == ["--resumer"] and len(a) > 1: resumer(a[1]); return
    sys.exit(Voix().run(sys.argv[:1]))
