# OS XIII — Accessibilité : lecteur d'écran (Orca), loupe, contraste, clavier visuel, sous-titres en direct,
# dictée partout, traduction de la sélection. Chaque aide a son raccourci et se coupe d'un second appui.
#   xiii-acces --lecteur | --contraste | --clavier | --soustitres [micro] | --dicter | --traduire | --etat | --test
# Application développée par Matthieu Lamotte.
import os, sys, re, json, time, shutil, subprocess, threading
from . import config, systeme as S

RACCOURCIS = [
    ("Super + Alt + S", "Lecteur d'écran (lit à voix haute ce qui est à l'écran)"),
    ("Super + =  /  Super + -", "Loupe : zoomer / dézoomer autour du pointeur"),
    ("Super + Alt + M", "Loupe : activer / couper"),
    ("Super + Alt + C", "Contraste renforcé"),
    ("Super + Alt + K", "Clavier visuel (à l'écran)"),
    ("Super + Ctrl + L", "Sous-titres en direct de ce qui joue sur le PC"),
    ("Super + Alt + H", "Dictée : parlez, le texte s'écrit là où se trouve le curseur"),
    ("Super + H", "Commandes vocales (« ouvre CONDUCO », « mode production »…)"),
    ("Super + Alt + T", "Traduire le texte sélectionné"),
]


def actif(nom):
    return subprocess.run(["pgrep", "-x", nom], stdout=subprocess.DEVNULL).returncode == 0


def dire(t):
    """Retour parlé (si le lecteur d'écran ou la synthèse vocale est là), sinon une notification."""
    if shutil.which("spd-say") and actif("orca"): S.detacher(["spd-say", "-l", "fr", t])
    else: S.detacher(["notify-send", "-a", "Accessibilité", "-t", "2500", t])


# ---------------------------------------------------------------- lecteur d'écran
def lecteur(on=None):
    on = (not actif("orca")) if on is None else on
    if on:
        if not shutil.which("orca"): dire("Le lecteur d'écran Orca n'est pas installé"); return False
        S.detacher(["orca", "--replace"]); config.modifier(lecteur_ecran=True)
        S.detacher(["spd-say", "-l", "fr", "Lecteur d'écran activé"])
    else:
        subprocess.run(["pkill", "-x", "orca"]); config.modifier(lecteur_ecran=False)
        S.detacher(["spd-say", "-l", "fr", "Lecteur d'écran coupé"])
    return on


def clavier(on=None):
    bin_ = shutil.which("wvkbd-mobintl") and "wvkbd-mobintl"
    on = (not actif("wvkbd-mobintl")) if on is None else on
    if on and bin_: S.detacher([bin_, "-L", "260", "--fn", "Sans 18"])
    elif not on: subprocess.run(["pkill", "-x", "wvkbd-mobintl"])
    config.modifier(clavier_visuel=bool(on and bin_))
    return on


def contraste():
    on = not config.charger().get("contraste", False); config.modifier(contraste=on)
    dire("Contraste renforcé " + ("activé" if on else "coupé")); return on


# ---------------------------------------------------------------- dictée (texte écrit là où est le curseur)
PONCTUATION = [
    (r"\s*point d.interrogation", "?"), (r"\s*point d.exclamation", "!"), (r"\s*points de suspension", "…"),
    (r"\s*deux points", " :"), (r"\s*point virgule", " ;"), (r"\s*virgule", ","), (r"\s*(?:a|à) la ligne", "\n"),
    (r"\s*nouveau paragraphe", "\n\n"), (r"\s*ouvrez? les guillemets\s*", " « "), (r"\s*fermez? les guillemets", " »"),
    (r"\s*point\b", "."),
]


def ponctuer(t):
    """« bonjour virgule on tourne demain point à la ligne merci » → « Bonjour, on tourne demain.\nMerci »"""
    t = " " + t.strip() + " "
    for motif, rep in PONCTUATION: t = re.sub(motif + r"(?=\s|$)", rep, t, flags=re.I)
    t = re.sub(r"[ \t]+", " ", t).strip(" ")
    t = re.sub(r"(^|[.!?…]\s+|\n\s*)([a-zàâéèêëîïôûùç])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t.replace(" \n", "\n").replace("\n ", "\n")


def dicter(duree=60):
    from .voix import ecouter
    S.detacher(["notify-send", "-a", "Dictée", "-t", "3000", "Je vous écoute…", "Dites « virgule », « point », « à la ligne ». Un silence termine la dictée."])
    try: t = ecouter(duree, avis=lambda m: S.detacher(["notify-send", "-a", "Dictée", m]))
    except Exception as e: S.detacher(["notify-send", "-a", "Dictée", "Dictée impossible", str(e)]); return ""
    t = ponctuer(t)
    if t:
        time.sleep(.3)
        if subprocess.run(["wtype", "--", t]).returncode != 0:          # application qui refuse la saisie simulée : presse-papiers
            subprocess.run(["wl-copy", t]); S.detacher(["notify-send", "-a", "Dictée", "Texte copié", "Collez-le avec Ctrl + V."])
    return t


# ---------------------------------------------------------------- traduction
def selection():
    for cmd in (["wl-paste", "--primary", "--no-newline"], ["wl-paste", "--no-newline"]):
        t = S.out(cmd) or ""
        if t.strip(): return t.strip()
    return ""


def consigne_traduction(t, cible=None):
    fr = sum(t.lower().count(m) for m in (" le ", " la ", " les ", " des ", " est ", " et ", " une ", " pour ")) >= 2
    cible = cible or ("anglais" if fr else "français")
    return "Traduis en %s ce texte, en gardant le ton et la mise en forme ; réponds uniquement par la traduction :\n\n%s" % (cible, t)


def traduire(cible=None):
    t = selection()
    if not t: dire("Sélectionnez d'abord un texte à traduire"); return
    S.detacher(["xiii-ia", "--demander", consigne_traduction(t, cible)])


# ---------------------------------------------------------------- sous-titres en direct
def flux_audio(source):
    entree = "@DEFAULT_MONITOR@" if source != "micro" else "default"
    return subprocess.Popen(["ffmpeg", "-loglevel", "quiet", "-f", "pulse", "-i", entree, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"], stdout=subprocess.PIPE)


def transcrire_flux(lire, rappel, arret=lambda: False):
    """Transcription continue : rappel(texte_validé, texte_en_cours) à chaque morceau de 0,2 s."""
    from .synthese import modele
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    rec = KaldiRecognizer(Model(modele()), 16000)
    while not arret():
        b = lire(6400)
        if not b: break
        if rec.AcceptWaveform(b): rappel(json.loads(rec.Result()).get("text", ""), "")
        else: rappel(None, json.loads(rec.PartialResult()).get("partial", ""))
    fin = json.loads(rec.FinalResult()).get("text", "")
    if fin: rappel(fin, "")


def sous_titres(source="pc"):
    import gi
    gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk, GLib, Gtk4LayerShell as LS
    from .synthese import modele, telecharger_modele
    from .ui import label, boite, bouton
    from . import theme
    cfg = config.charger(); taille = int(cfg.get("soustitres_taille", 28))
    app = Gtk.Application(application_id="fr.xiii.soustitres")
    etat = {"lignes": [], "fini": False, "journal": []}

    def activer(app):
        w = Gtk.ApplicationWindow(application=app, title="Sous-titres en direct")
        LS.init_for_window(w); LS.set_namespace(w, "xiii-soustitres"); LS.set_layer(w, LS.Layer.OVERLAY)
        LS.set_anchor(w, LS.Edge.BOTTOM, True); LS.set_margin(w, LS.Edge.BOTTOM, 90); LS.set_keyboard_mode(w, LS.KeyboardMode.NONE)
        css = Gtk.CssProvider(); css.load_from_string(".st{background:rgba(10,8,6,.86);border-radius:16px;padding:14px 22px;}"
                                                      ".st label.txt{color:#fff;font-size:%dpx;font-weight:600;} .st label.encours{color:#f0b378;}" % taille)
        Gtk.StyleContext.add_provider_for_display(w.get_display(), css, 800)
        b = boite(True, 4, "st"); b.set_size_request(900, -1)
        haut = boite(False, 8); haut.append(label("Sous-titres en direct · " + ("son du PC" if source != "micro" else "micro"), "petit", "attenue", xalign=0))
        sp = Gtk.Box(); sp.set_hexpand(True); haut.append(sp)
        haut.append(bouton(None, "copy", "fantome", tip="Copier la transcription", rappel=lambda: subprocess.run(["wl-copy", "\n".join(etat["journal"])])))
        haut.append(bouton(None, "x", "fantome", tip="Fermer", rappel=lambda: (etat.update(fini=True), app.quit())))
        b.append(haut)
        l1 = label("", "txt", wrap=True); l2 = label("Préparation de la reconnaissance vocale…", "txt", "encours", wrap=True)
        b.append(l1); b.append(l2); w.set_child(b); w.present()

        def maj(valide, encours):
            if valide:
                etat["lignes"] = (etat["lignes"] + [valide])[-2:]; etat["journal"].append(valide)
            GLib.idle_add(lambda: (l1.set_text(" ".join(etat["lignes"])), l2.set_text(encours), False)[2])

        def tache():
            if os.environ.get("XIII_DEMO"):          # captures de démonstration
                maj("Bienvenue sur le plateau, on tourne la première séquence à neuf heures.", "la régie est prête et les caméras"); return
            if not modele():
                maj(None, "Première utilisation : téléchargement de la voix française (40 Mo)…"); telecharger_modele()
            p = flux_audio(source); maj(None, "J'écoute…")
            try: transcrire_flux(p.stdout.read, maj, lambda: etat["fini"])
            finally: p.terminate()
        threading.Thread(target=tache, daemon=True).start()
    app.connect("activate", activer)
    return app.run([])


# ---------------------------------------------------------------- état (Paramètres, tests)
def etat():
    cfg = config.charger()
    return {"lecteur_ecran": actif("orca"), "orca_installe": bool(shutil.which("orca")), "clavier_visuel": actif("wvkbd-mobintl"),
            "clavier_installe": bool(shutil.which("wvkbd-mobintl")), "contraste": cfg.get("contraste", False),
            "dictee": bool(shutil.which("wtype")), "sous_titres": actif_st()}


def test():
    ok = True
    cas = {"bonjour virgule on tourne demain point à la ligne merci point d'exclamation": "Bonjour, on tourne demain.\nMerci!",
           "est-ce que tu viens point d'interrogation": "Est-ce que tu viens?",
           "la liste deux points caméras virgule micros": "La liste : caméras, micros"}
    for e, att in cas.items():
        r = ponctuer(e); bon = r == att; ok &= bon
        print(("OK        " if bon else "ÉCHEC     ") + "dictée « %s » → %r" % (e[:40], r))
    c = consigne_traduction("Le tournage est prévu demain et la régie est prête pour les caméras")
    print(("OK        " if "anglais" in c else "ÉCHEC     ") + "traduction : texte français → anglais")
    # sous-titres : flux audio synthétique (fichier) passé dans la reconnaissance, si le modèle vocal est présent
    try: from .synthese import modele
    except Exception: modele = lambda: None
    wav = os.environ.get("XIII_TEST_WAV")
    if modele() and wav and os.path.exists(wav):
        p = subprocess.Popen(["ffmpeg", "-loglevel", "quiet", "-i", wav, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"], stdout=subprocess.PIPE)
        out = []; transcrire_flux(p.stdout.read, lambda v, e: v and out.append(v))
        print(("OK        " if out else "ÉCHEC     ") + "sous-titres en direct : %r" % " ".join(out)[:80]); ok &= bool(out)
    else:
        print("INFO      sous-titres : pas de modèle vocal ou de fichier de test, reconnaissance non lancée")
    print("INFO      état :", json.dumps(etat(), ensure_ascii=False))
    return ok


def main():
    a = sys.argv[1:]; c = a[0] if a else "--etat"
    if c == "--lecteur": lecteur(None if len(a) < 2 else a[1] == "on")
    elif c == "--clavier": clavier(None if len(a) < 2 else a[1] == "on")
    elif c == "--contraste": contraste()
    elif c == "--dicter": dicter()
    elif c == "--traduire": traduire(a[1] if len(a) > 1 else None)
    elif c == "--soustitres":
        if actif_st():                       # second appui : on ferme les sous-titres
            for p in pids_st(): os.kill(p, 15)
            return
        sys.exit(sous_titres(a[1] if len(a) > 1 else config.charger().get("soustitres_source", "pc")))
    elif c == "--test": sys.exit(0 if test() else 1)
    else: print(json.dumps(etat(), ensure_ascii=False, indent=1))


def pids_st():
    r = subprocess.run(["pgrep", "-f", "--", "acces import main.*--soustitres"], capture_output=True, text=True).stdout.split()
    return [int(x) for x in r if int(x) not in (os.getpid(), os.getppid())]


def actif_st():
    return bool(pids_st())
