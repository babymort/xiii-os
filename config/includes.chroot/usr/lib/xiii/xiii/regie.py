# OS XIII — Mode Régie : un écran de pilotage en plein écran pendant une émission ou une captation.
# Horloge et timecode géants, compte à rebours jusqu'à l'antenne puis temps écoulé, chrono, conducteur CONDUCO avec le
# sujet en cours et son temps restant, notes, et les outils de régie à un clic. Ne pas déranger activé pendant la régie.
# Touches : N / → sujet suivant · P / ← précédent · Espace : chrono · R : remise à zéro · F11 : plein écran · Échap : quitter.
# Application développée par Matthieu Lamotte.
import os, sys, re, time, datetime, json
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, systeme as S
from .ui import *
from .appli import preparer

NOTES = os.path.join(GLib.get_user_data_dir(), "xiii", "regie-notes.txt")

def secondes(v):
    if v is None: return 0
    if isinstance(v, (int, float)): return int(v if v < 36000 else v / 1000)
    m = re.match(r"^\s*(?:(\d+):)?(\d+):(\d+)\s*$", str(v))
    if m: return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    try: return int(float(v))
    except ValueError: return 0

def hms(s, signe=False):
    neg = s < 0; s = abs(int(s))
    t = ("%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)) if s >= 3600 else "%02d:%02d" % (s // 60, s % 60)
    return ("-" if neg else ("+" if signe else "")) + t

class Regie(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.regie")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        self.cfg = preparer("""
            .regie { background: #0b0b0c; } .r-heure { font-family: 'IBM Plex Mono'; font-size: 110px; font-weight: 700; color: #f2ede7; }
            .r-tc { font-family: 'IBM Plex Mono'; font-size: 44px; color: #f0b378; } .r-gros { font-family: 'IBM Plex Mono'; font-size: 64px; font-weight: 700; }
            .r-antenne { background: #c92a2a; border-radius: 12px; padding: 6px 18px; } .r-antenne label { color: white; }
            .r-attente { background: alpha(#f0b378, .18); border-radius: 12px; padding: 6px 18px; }
            .r-sujet { padding: 8px 12px; border-radius: 10px; } .r-sujet.actuel { background: alpha(#f0b378, .22); border: 1px solid #f0b378; }
            .r-sujet.passe label { opacity: .4; } .r-rouge { color: #ff6b6b; } .r-titre { font-size: 22px; font-weight: 700; }""")
        self.dnd_avant = config.charger().get("ne_pas_deranger", False); config.modifier(_histo=False, ne_pas_deranger=True)
        self.win = Gtk.ApplicationWindow(application=self, title="Régie XIII", default_width=1500, default_height=900); self.win.add_css_class("regie")
        self.chrono_t0 = None; self.chrono_acc = 0.0; self.i = 0; self.sujet_t0 = time.time()
        self.conducteur = self.charger_conducteur()
        g = boite(False, 18, margin_top=18, margin_bottom=18, margin_start=22, margin_end=22)
        # ---- colonne horloge
        a = boite(True, 10, hexpand=True); a.set_size_request(520, -1)
        self.l_heure = label("", "r-heure", xalign=0.5); a.append(self.l_heure)
        self.l_tc = label("", "r-tc", xalign=0.5); a.append(self.l_tc)
        self.b_antenne = boite(False, 10, halign=Gtk.Align.CENTER, margin_top=10); self.l_antenne = label("", "r-gros"); self.b_antenne.append(self.l_antenne); a.append(self.b_antenne)
        r = boite(False, 8, halign=Gtk.Align.CENTER); r.append(label("Antenne à", "attenue"))
        self.e_antenne = Gtk.Entry(text=self.cfg.get("regie_antenne", ""), placeholder_text="20:30:00", width_chars=9)
        self.e_antenne.connect("changed", lambda w: config.modifier(_histo=False, regie_antenne=w.get_text().strip())); r.append(self.e_antenne); a.append(r)
        a.append(label("Chrono", "section", xalign=0.5)); self.l_chrono = label("00:00", "r-gros", xalign=0.5); a.append(self.l_chrono)
        rc = boite(False, 8, halign=Gtk.Align.CENTER)
        rc.append(bouton("Départ / pause (Espace)", "timer", "pilule", rappel=self.chrono)); rc.append(bouton("Zéro (R)", "rotate-ccw", "fantome", rappel=self.zero)); a.append(rc)
        outils = Gtk.FlowBox(max_children_per_line=3, selection_mode=Gtk.SelectionMode.NONE, column_spacing=8, row_spacing=8, margin_top=16)
        for n, ic, cmd in (("Tally", "siren", ["xiii-tally"]), ("ATEM", "tv", ["xiii-blackmagic"]), ("Prompteur", "scroll-text", ["xiii-prompteur"]),
                           ("Mesure audio", "audio-waveform", ["xiii-mesure-audio"]), ("CONDUCO", "list-video", ["xiii-suite", "conduco"]), ("Multiview NDI", "layout-grid", ["xiii-multiview"])):
            outils.append(bouton(n, ic, "fantome", rappel=lambda c=cmd: S.detacher(c)))
        a.append(outils); g.append(a)
        # ---- conducteur
        b = boite(True, 8, hexpand=True); b.set_size_request(480, -1)
        h = boite(False, 8); h.append(label(self.conducteur["nom"], "r-titre", hexpand=True, ellipsize=True))
        h.append(bouton(None, "chevron-left", "fantome", tip="Sujet précédent (P)", rappel=lambda: self.sujet(-1))); h.append(bouton("Suivant (N)", "chevron-right", "pilule", rappel=lambda: self.sujet(1)))
        b.append(h)
        self.l_reste = label("", "r-gros", xalign=0.5); b.append(self.l_reste)
        self.liste = boite(True, 4); sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(self.liste); b.append(sc); self.sc = sc
        g.append(b)
        # ---- notes
        c = boite(True, 8); c.set_size_request(300, -1)
        c.append(label("Notes de régie", "section"))
        self.buf = Gtk.TextBuffer()
        try: self.buf.set_text(open(NOTES).read())
        except OSError: pass
        self.buf.connect("changed", lambda *_: self.sauver_notes())
        tv = Gtk.TextView(buffer=self.buf, wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=8, left_margin=8); tv.add_css_class("champ")
        s2 = Gtk.ScrolledWindow(vexpand=True); s2.set_child(tv); c.append(s2)
        c.append(bouton("Quitter la régie (Échap)", "log-out", "fantome", rappel=self.quitter)); g.append(c)
        self.win.set_child(g)
        k = Gtk.EventControllerKey(); k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE); k.connect("key-pressed", self.touche); self.win.add_controller(k)
        self.win.connect("close-request", lambda *_: (self.restaurer(), False)[1])
        self.remplir(); self.win.fullscreen(); self.win.present()
        GLib.timeout_add(40, self.tic)

    def charger_conducteur(self):
        from .widgets import dernier_lien
        o = dernier_lien("rundown") or {}
        c = o.get("conducteur") or {}
        items = []
        for it in o.get("items") or []:
            items.append({"titre": it.get("title") or it.get("name") or "Sujet", "duree": secondes(it.get("duration") or it.get("dur") or it.get("duree") or it.get("length")),
                          "qui": it.get("who") or it.get("presenter") or it.get("source") or ""})
        return {"nom": c.get("name") or (o.get("project") or {}).get("name") or ("Conducteur" if items else "Aucun conducteur CONDUCO"), "items": items}

    def remplir(self):
        vider(self.liste); t = 0
        if not self.conducteur["items"]:
            self.liste.append(label("Exportez le conducteur depuis CONDUCO (Suite XIII) : il apparaîtra ici.", "attenue", wrap=True)); return
        for k, it in enumerate(self.conducteur["items"]):
            r = boite(False, 10, "r-sujet")
            if k == self.i: r.add_css_class("actuel")
            elif k < self.i: r.add_css_class("passe")
            r.append(label("%2d" % (k + 1), "attenue")); col = boite(True, 0, hexpand=True); col.append(label(it["titre"], "gras", wrap=True))
            if it["qui"]: col.append(label(it["qui"], "petit", "attenue"))
            r.append(col); r.append(label(hms(it["duree"]) if it["duree"] else "", "chiffre")); r.append(label(hms(t), "petit", "attenue"))
            t += it["duree"]; self.liste.append(r)

    def sujet(self, d):
        n = len(self.conducteur["items"])
        if not n: return
        self.i = max(0, min(n - 1, self.i + d)); self.sujet_t0 = time.time(); self.remplir()

    def chrono(self):
        if self.chrono_t0: self.chrono_acc += time.time() - self.chrono_t0; self.chrono_t0 = None
        else: self.chrono_t0 = time.time()
    def zero(self): self.chrono_t0 = None; self.chrono_acc = 0.0

    def tic(self):
        n = datetime.datetime.now(); fps = int(self.cfg.get("timecode_fps", 25)) or 25
        self.l_heure.set_text(n.strftime("%H:%M:%S")); self.l_tc.set_text("%s:%02d" % (n.strftime("%H:%M:%S"), int(n.microsecond / 1e6 * fps)))
        ch = self.chrono_acc + (time.time() - self.chrono_t0 if self.chrono_t0 else 0); self.l_chrono.set_text(hms(ch))
        txt = self.e_antenne.get_text().strip()
        m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", txt)
        for c in ("r-antenne", "r-attente"): self.b_antenne.remove_css_class(c)
        if m:
            cible = n.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=int(m.group(3) or 0), microsecond=0)
            d = (cible - n).total_seconds()
            if d > 0: self.l_antenne.set_text("Antenne dans " + hms(d)); self.b_antenne.add_css_class("r-attente")
            else: self.l_antenne.set_text("À L'ANTENNE  " + hms(-d)); self.b_antenne.add_css_class("r-antenne")
        else: self.l_antenne.set_text("")
        it = self.conducteur["items"][self.i] if self.conducteur["items"] else None
        if it and it["duree"]:
            r = it["duree"] - (time.time() - self.sujet_t0)
            self.l_reste.set_text(("Reste " if r >= 0 else "Dépassement ") + hms(r)); (self.l_reste.add_css_class if r < 0 else self.l_reste.remove_css_class)("r-rouge")
        else: self.l_reste.set_text("")
        return True

    def sauver_notes(self):
        try:
            os.makedirs(os.path.dirname(NOTES), exist_ok=True); open(NOTES, "w").write(self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), False))
        except OSError: pass

    def touche(self, c, kv, code, st):
        if isinstance(self.win.get_focus(), (Gtk.Text, Gtk.TextView)) and kv != Gdk.KEY_Escape: return False
        if kv == Gdk.KEY_Escape: self.quitter()
        elif kv in (Gdk.KEY_n, Gdk.KEY_N, Gdk.KEY_Right, Gdk.KEY_Page_Down): self.sujet(1)
        elif kv in (Gdk.KEY_p, Gdk.KEY_P, Gdk.KEY_Left, Gdk.KEY_Page_Up): self.sujet(-1)
        elif kv == Gdk.KEY_space: self.chrono()
        elif kv in (Gdk.KEY_r, Gdk.KEY_R): self.zero()
        elif kv == Gdk.KEY_F11: self.win.unfullscreen() if self.win.is_fullscreen() else self.win.fullscreen()
        else: return False
        return True

    def restaurer(self):
        config.modifier(_histo=False, ne_pas_deranger=self.dnd_avant)

    def quitter(self):
        self.restaurer(); self.quit()

def main():
    sys.exit(Regie().run(sys.argv[:1]))
