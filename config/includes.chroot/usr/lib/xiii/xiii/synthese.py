# OS XIII — Assistant de synthèse : enregistre le micro (réunion, brief, interview) ou prend un fichier audio / vidéo,
# le transcrit sur ce PC (Vosk, hors ligne, en français), range la transcription dans le projet actif,
# puis la confie à l'IA choisie en haut de l'écran pour un résumé (points clés, décisions, actions).
# Application développée par Matthieu Lamotte.
import os, sys, json, wave, subprocess, threading, time, datetime, shutil
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S
from .ui import *
from .appli import preparer

MODELES = ["/usr/share/vosk/fr", os.path.expanduser("~/.local/share/vosk/fr")]
CONSIGNES = {
    "reunion": "Résume cette réunion en français : contexte en 2 phrases, points clés, décisions prises, actions à mener (qui / quoi / quand), questions en suspens.",
    "brief": "Fais une synthèse de ce brief de production en français : objectifs, contraintes, livrables, planning, matériel et équipe mentionnés.",
    "interview": "Résume cette interview en français : thèmes abordés, meilleures citations (avec leur moment approximatif), idées de titres et de montage.",
    "libre": "Résume ce texte en français, de façon claire et structurée.",
}

def modele():
    return next((m for m in MODELES if os.path.isdir(m)), None)

def dossier_sortie():
    pj = config.charger().get("projet_actif")
    d = os.path.join(os.path.expanduser("~/XIII"), pj, "03_Documents", "Syntheses") if pj else os.path.join(os.path.expanduser("~/Documents"), "Synthèses")
    os.makedirs(d, exist_ok=True); return d

def transcrire(chemin, progres):
    """Transcription hors ligne (Vosk) ; le fichier est d'abord converti en audio 16 kHz mono par ffmpeg."""
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    duree = 0
    try: duree = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", chemin], capture_output=True, text=True).stdout.strip() or 0)
    except Exception: pass
    p = subprocess.Popen(["ffmpeg", "-loglevel", "quiet", "-i", chemin, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"], stdout=subprocess.PIPE)
    rec = KaldiRecognizer(Model(modele()), 16000); rec.SetWords(False)
    morceaux = []; lu = 0
    while True:
        b = p.stdout.read(16000 * 2 * 2)
        if not b: break
        lu += len(b)
        if rec.AcceptWaveform(b):
            t = json.loads(rec.Result()).get("text", "")
            if t: morceaux.append(("[%02d:%02d] " % divmod(int(lu / 32000), 60)) + t)
        if duree: progres(min(.99, lu / 32000 / duree))
    t = json.loads(rec.FinalResult()).get("text", "")
    if t: morceaux.append(t)
    return "\n".join(morceaux)


class Synthese(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.synthese"); self.enr = None; self.fichier = None

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".rond-rec { border-radius: 999px; min-width: 96px; min-height: 96px; } .rond-rec.actif { background: #d83a3a; color: white; }"
                 ".minuteur { font-family: 'IBM Plex Mono', monospace; font-size: 28px; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Assistant de synthèse"); self.win.set_default_size(560, 640)
        v = boite(True, 14, margin_start=24, margin_end=24, margin_top=20, margin_bottom=20)
        h = boite(False, 12); h.append(ico("audio-lines", 30, "c")); t = boite(True, 0); t.append(label("Assistant de synthèse", "page-titre"))
        from .ia_base import PAR_CLE
        from .config import charger as _ch
        actuelle = lambda: _ch().get("ia", "claude")
        t.append(label("Transcription sur ce PC, puis résumé par %s" % PAR_CLE[actuelle()][1], "attenue")); h.append(t); v.append(h)
        # type de synthèse
        self.type = "reunion"; seg = boite(False, 4)
        prem = None
        for k, n in (("reunion", "Réunion"), ("brief", "Brief"), ("interview", "Interview"), ("libre", "Libre")):
            b = Gtk.ToggleButton(label=n, group=prem); b.add_css_class("fantome")
            if not prem: prem = b; b.set_active(True)
            b.connect("toggled", lambda w, k=k: w.get_active() and setattr(self, "type", k)); seg.append(b)
        v.append(seg)
        # micro
        c = boite(True, 10, "carte", halign=Gtk.Align.FILL)
        r = boite(False, 16, halign=Gtk.Align.CENTER)
        self.b_rec = Gtk.Button(); self.b_rec.add_css_class("rond-rec"); self.b_rec.set_child(ico("mic", 36, "c")); self.b_rec.connect("clicked", lambda *_: self.basculer())
        r.append(self.b_rec); col = boite(True, 4, valign=Gtk.Align.CENTER)
        self.l_temps = label("00:00", "minuteur"); col.append(self.l_temps); col.append(label("Enregistrer le micro", "attenue")); r.append(col); c.append(r)
        self.micros = self.lister_micros()
        dd = Gtk.DropDown.new_from_strings([d for _, d in self.micros] or ["Micro par défaut"]); self.dd = dd; c.append(dd)
        v.append(c)
        v.append(label("ou", "attenue", xalign=0.5))
        v.append(bouton("Choisir un fichier audio ou vidéo…", "file-audio", "fantome", rappel=self.choisir_fichier))
        self.etat = label("", "attenue", wrap=True); v.append(self.etat)
        self.pb = Gtk.ProgressBar(); self.pb.set_visible(False); v.append(self.pb)
        self.texte = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, left_margin=8, right_margin=8, top_margin=8)
        sc = Gtk.ScrolledWindow(vexpand=True, min_content_height=140); sc.set_child(self.texte); sc.add_css_class("carte"); v.append(sc)
        bas = boite(False, 8, halign=Gtk.Align.END)
        bas.append(bouton("Ouvrir le dossier", "folder-open", "fantome", rappel=lambda: S.detacher(["xiii-fichiers", dossier_sortie()])))
        self.b_res = bouton("Résumer avec l'IA", "sparkles", "pilule", rappel=self.resumer); self.b_res.set_sensitive(False); bas.append(self.b_res)
        v.append(bas)
        if not modele():
            self.etat.set_text("Le modèle de reconnaissance vocale française n'est pas installé : la transcription est impossible, mais l'enregistrement fonctionne.")
        self.win.set_child(v); self.win.present()

    def lister_micros(self):
        try:
            o = subprocess.run(["pactl", "-f", "json", "list", "sources"], capture_output=True, text=True, timeout=3).stdout
            return [(s["name"], s.get("description") or s["name"]) for s in json.loads(o) if not s["name"].endswith(".monitor")]
        except Exception:
            return []

    def basculer(self):
        if self.enr:
            self.enr.terminate(); self.enr.wait(); self.enr = None; self.b_rec.remove_css_class("actif"); self.b_rec.set_child(ico("mic", 36, "c"))
            GLib.source_remove(self._t); self.traiter(self.fichier); return
        nom = datetime.datetime.now().strftime("enregistrement-%Y%m%d-%H%M%S.ogg")
        self.fichier = os.path.join(dossier_sortie(), nom)
        src = self.micros[self.dd.get_selected()][0] if self.micros else None
        cmd = ["ffmpeg", "-loglevel", "quiet", "-f", "pulse", "-i", src or "default", "-ac", "1", "-c:a", "libopus", "-b:a", "48k", self.fichier]
        self.enr = subprocess.Popen(cmd, stdin=subprocess.PIPE); self.debut = time.time()
        self.b_rec.add_css_class("actif"); self.b_rec.set_child(ico("square", 30, "#ffffff"))
        self.etat.set_text("Enregistrement… cliquez à nouveau pour arrêter.")
        self._t = GLib.timeout_add(500, lambda: (self.l_temps.set_text("%02d:%02d" % divmod(int(time.time() - self.debut), 60)), True)[1])

    def choisir_fichier(self):
        d = Gtk.FileDialog(title="Fichier audio ou vidéo")
        ff = Gtk.FileFilter(); ff.set_name("Audio et vidéo"); ff.add_mime_type("audio/*"); ff.add_mime_type("video/*")
        st = Gio.ListStore.new(Gtk.FileFilter); st.append(ff); d.set_filters(st)
        def fin(dlg, res):
            try: self.traiter(dlg.open_finish(res).get_path())
            except Exception: pass
        d.open(self.win, None, fin)

    def traiter(self, f):
        if not modele(): self.etat.set_text("Enregistré : %s. Transcription impossible sans le modèle vocal." % f); return
        self.etat.set_text("Transcription sur ce PC… (environ la moitié de la durée de l'audio sur un vieux PC)"); self.pb.set_visible(True); self.pb.set_fraction(0)
        def prog(x): GLib.idle_add(lambda: (self.pb.set_fraction(x), False)[1])
        def fin(t):
            self.pb.set_fraction(1)
            if isinstance(t, Exception): self.etat.set_text("Transcription impossible : %s" % t); return
            sortie = os.path.splitext(f)[0] + ".txt" if f.startswith(dossier_sortie()) else os.path.join(dossier_sortie(), os.path.splitext(os.path.basename(f))[0] + ".txt")
            open(sortie, "w").write(t)
            self.texte.get_buffer().set_text(t); self.b_res.set_sensitive(bool(t.strip()))
            self.etat.set_text("Transcription enregistrée : %s" % sortie.replace(os.path.expanduser("~"), "~"))
        S.en_fond(lambda: transcrire(f, prog), fin)

    def resumer(self):
        b = self.texte.get_buffer(); t = b.get_text(b.get_start_iter(), b.get_end_iter(), False).strip()
        if not t: return
        S.detacher(["xiii-ia", "--demander", CONSIGNES[self.type] + "\n\nTranscription :\n" + t[:60000]])

def main():
    sys.exit(Synthese().run(sys.argv))
