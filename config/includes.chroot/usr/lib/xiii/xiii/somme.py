# OS XIII — vérification d'offload : sommes de contrôle (xxHash64, MD5, SHA-256) d'un dossier de rushes,
# comparaison source ↔ copie, rapport texte + MHL, comme BACKUPO XIII. Clic droit sur un dossier dans Fichiers.
# Application développée par Matthieu Lamotte.
import os, sys, time, hashlib, threading, datetime, socket, getpass, json
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, theme, systeme as S
from .ui import *
try:
    import xxhash
except ImportError:
    xxhash = None

TAG = {"xxh64": "xxhash64be", "md5": "md5", "sha256": "sha256"}
ALGOS = [("xxh64", "xxHash64 (rapide, standard tournage)"), ("md5", "MD5"), ("sha256", "SHA-256")]

def hacher(chemin, algo, avance):
    h = xxhash.xxh64() if algo == "xxh64" and xxhash else hashlib.new("md5" if algo == "xxh64" else algo)
    with open(chemin, "rb") as f:
        while True:
            b = f.read(8 * 1024 * 1024)
            if not b: break
            h.update(b); avance(len(b))
    return h.hexdigest()

HISTO = os.path.expanduser("~/.local/share/xiii/offload.json")

def historique():
    try: return json.load(open(HISTO))
    except Exception: return []

def historiser(e):
    """Mémorise les dernières vérifications (widget « Offload » du tableau de widgets)."""
    try:
        h = [e] + historique()
        os.makedirs(os.path.dirname(HISTO), exist_ok=True); json.dump(h[:30], open(HISTO, "w"), ensure_ascii=False, indent=1)
    except OSError:
        pass

def lister(racine):
    if os.path.isfile(racine): return [racine]
    L = []
    for d, _, fs in os.walk(racine):
        for f in fs:
            if f.startswith(".") or f.endswith((".mhl", ".xiii-somme.txt")): continue
            L.append(os.path.join(d, f))
    return sorted(L)

class Somme(Gtk.Application):
    def __init__(self, cibles):
        super().__init__(application_id="fr.xiii.Somme", flags=Gio.ApplicationFlags.NON_UNIQUE); self.cibles = cibles
    def do_activate(self):
        cfg = config.charger(); couleurs(cfg)
        css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(cfg)); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 900)
        self.w = Gtk.ApplicationWindow(application=self, title="Vérification d'offload", default_width=760, default_height=620); self.w.add_css_class("parametres")
        v = boite(True, 12, margin_top=22, margin_bottom=18, margin_start=26, margin_end=26); self.w.set_child(v)
        v.append(label("Vérification d'offload", "page-titre"))
        v.append(label("Calcule l'empreinte de chaque fichier et compare la copie à la source, comme BACKUPO XIII.", "attenue", wrap=True))
        self.src = Gtk.Entry(text=self.cibles[0] if self.cibles else "", hexpand=True, placeholder_text="Dossier source (carte, disque…)")
        self.cop = Gtk.Entry(text=self.cibles[1] if len(self.cibles) > 1 else "", hexpand=True, placeholder_text="Copie à comparer (optionnel)")
        for e, t in ((self.src, "Source"), (self.cop, "Copie")):
            r = boite(False, 10, "reglage"); r.append(label(t, "reglage-titre")); r.append(e)
            r.append(bouton(None, "folder-open", "plat", rappel=lambda e=e: self.choisir(e))); v.append(r)
        self.algo = Gtk.DropDown(model=Gtk.StringList.new([a[1] for a in ALGOS]))
        r = boite(False, 10, "reglage"); r.append(label("Algorithme", "reglage-titre", hexpand=True)); r.append(self.algo); v.append(r)
        self.go = bouton("Lancer la vérification", None, "pilule", rappel=self.lancer); self.go.set_halign(Gtk.Align.END); v.append(self.go)
        self.barre = Gtk.ProgressBar(show_text=True); v.append(self.barre)
        self.etat = label("", "attenue"); v.append(self.etat)
        self.res = Gtk.TextView(editable=False, monospace=True, vexpand=True); self.res.add_css_class("journal")
        sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(self.res); v.append(sc)
        v.append(label("Application développée par Matthieu Lamotte", "credit", xalign=1))
        self.w.present()

    def choisir(self, e):
        d = Gtk.FileDialog(title="Choisir un dossier")
        def fini(dlg, res):
            try: e.set_text(dlg.select_folder_finish(res).get_path())
            except Exception: pass
        d.select_folder(self.w, None, fini)

    def ecrire(self, t):
        GLib.idle_add(lambda: (self.res.get_buffer().insert(self.res.get_buffer().get_end_iter(), t + "\n"), False)[1])

    def lancer(self):
        src, cop = self.src.get_text().strip(), self.cop.get_text().strip()
        if not os.path.exists(src): self.etat.set_text("Dossier source introuvable."); return
        self.go.set_sensitive(False); self.res.get_buffer().set_text("")
        algo = ALGOS[self.algo.get_selected()][0]
        threading.Thread(target=self.travail, args=(src, cop, algo), daemon=True).start()

    def travail(self, src, cop, algo):
        fichiers = lister(src); total = sum(os.path.getsize(f) for f in fichiers) * (2 if cop else 1) or 1
        fait = [0]; t0 = time.time()
        def avance(n):
            fait[0] += n
            if int(fait[0] / total * 200) != int((fait[0] - n) / total * 200):
                d = time.time() - t0 or 1
                GLib.idle_add(lambda f=fait[0], d=d: (self.barre.set_fraction(f / total), self.barre.set_text("%d %% · %s/s" % (100 * f / total, S.humain(f / d))), S.progres("xiii-somme.desktop", f / total), False)[3])
        ok = ko = manq = 0; lignes = []
        for f in fichiers:
            rel = os.path.relpath(f, src) if os.path.isdir(src) else os.path.basename(f)
            hs = hacher(f, algo, avance); statut = ""
            if cop:
                fc = os.path.join(cop, rel) if os.path.isdir(cop) else cop
                if not os.path.exists(fc): statut = "MANQUANT"; manq += 1
                else:
                    hc = hacher(fc, algo, avance)
                    statut = "OK" if hc == hs else "DIFFÉRENT"
                    if hc == hs: ok += 1
                    else: ko += 1
            else:
                ok += 1
            lignes.append((rel, os.path.getsize(f), hs, statut))
            self.ecrire("%-10s %s  %s" % (statut or "—", hs, rel))
        # rapport
        d = src if os.path.isdir(src) else os.path.dirname(src)
        nom = "verification-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            with open(os.path.join(d, nom + ".xiii-somme.txt"), "w") as r:
                r.write("OS XIII — vérification d'offload\nSource : %s\nCopie : %s\nAlgorithme : %s\nDate : %s\n\n" % (src, cop or "—", algo, datetime.datetime.now().isoformat(timespec="seconds")))
                for rel, t, h, st in lignes: r.write("%s\t%d\t%s\t%s\n" % (h, t, st or "—", rel))
            with open(os.path.join(d, nom + ".mhl"), "w") as m:
                m.write('<?xml version="1.0" encoding="UTF-8"?>\n<hashlist version="1.1">\n  <creatorinfo><name>%s</name><hostname>%s</hostname><tool>OS XIII</tool><startdate>%s</startdate></creatorinfo>\n'
                        % (getpass.getuser(), socket.gethostname(), datetime.datetime.now().isoformat(timespec="seconds")))
                for rel, t, h, st in lignes:
                    m.write('  <hash><file>%s</file><size>%d</size><%s>%s</%s><hashdate>%s</hashdate></hash>\n' % (rel.replace("&", "&amp;").replace("<", "&lt;"), t, TAG[algo], h, TAG[algo], datetime.datetime.now().isoformat(timespec="seconds")))
                m.write("</hashlist>\n")
            rapport = "Rapport enregistré dans le dossier source (%s.mhl, .txt)." % nom
        except OSError as e:
            rapport = "Rapport non enregistré (%s)." % e
        bilan = ("%d fichier(s) vérifié(s)" % len(lignes)) if not cop else ("%d identique(s) · %d différent(s) · %d manquant(s)" % (ok, ko, manq))
        historiser({"date": datetime.datetime.now().isoformat(timespec="seconds"), "source": src, "copie": cop, "algo": algo,
                    "fichiers": len(lignes), "octets": sum(t for _, t, _, _ in lignes), "ok": ok, "differents": ko, "manquants": manq, "rapport": os.path.join(d, nom + ".mhl")})
        def fin():
            self.go.set_sensitive(True); self.barre.set_fraction(1); S.progres("xiii-somme.desktop", None)
            self.etat.set_text(("✓ " if not ko and not manq else "⚠ ") + bilan + " — " + rapport)
            S.detacher(["notify-send", "-a", "Vérification d'offload", "-i", "drive-harddisk", "Vérification terminée", bilan])
            return False
        GLib.idle_add(fin)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    args = [Gio.File.new_for_uri(a).get_path() if a.startswith("file://") else a for a in args]
    Somme(args).run(sys.argv[:1])
