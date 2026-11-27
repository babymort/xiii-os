# OS XIII — Île XIII : la barre des tâches en forme d'« île dynamique » (façon Dynamic Island).
# Repliée : une pilule au centre de l'écran avec l'appli active, ce qui se passe (lecture en cours, enregistrement de l'écran,
# timecode en tournage, téléchargements) et les notifications. Au survol ou au clic, elle s'ouvre en grand : applis épinglées
# et ouvertes, lecture en cours avec ses boutons, météo, heure, raccourcis (Démarrer, Rechercher, Paramètres, Afficher le bureau).
# Application développée par Matthieu Lamotte.
import os, subprocess, time, json, urllib.request
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, GLib
from gi.repository import Gtk4LayerShell as LS
from . import apps, systeme as S
from .ui import *


class Ile:
    def __init__(self, shell):
        self.shell = shell; self.ouverte = False; self._src = 0; self._media = ""; self._etat_media = ""
        self.fin_minuteur = None; self.reste_pause = 0; self._seconde = 0; self._fini_jusqua = 0; self._tally = None
        w = Gtk.Window(application=shell); self.w = w
        LS.init_for_window(w); LS.set_namespace(w, "xiii-ile"); LS.set_layer(w, LS.Layer.TOP); LS.set_exclusive_zone(w, 0)
        LS.set_keyboard_mode(w, LS.KeyboardMode.NONE); w.add_css_class("xiii-surface")
        self.pilule = boite(True, 0, "ile"); w.set_child(self.pilule)
        # ligne repliée
        self.compacte = boite(False, 10, "ile-compacte", halign=Gtk.Align.CENTER)
        self.i_app = Gtk.Box(); self.compacte.append(self.i_app)
        self.l_act = label("", "ile-texte", ellipsize=True, largeur=36); self.compacte.append(self.l_act)
        self.l_heure = label("", "ile-heure"); self.compacte.append(self.l_heure)
        self.badge = label("", "badge", xalign=0.5); self.badge.set_visible(False); self.compacte.append(self.badge)
        self.pilule.append(self.compacte)
        # partie dépliée
        self.rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN, transition_duration=220)
        self.grand = boite(True, 10, "ile-grande"); self.rev.set_child(self.grand); self.pilule.append(self.rev)
        m = Gtk.EventControllerMotion(); m.connect("enter", lambda *_: self.ouvrir_bientot() if self.shell.cfg.get("ile_survol", True) else None); m.connect("leave", lambda *_: self.fermer_bientot()); w.add_controller(m)
        g = Gtk.GestureClick(); g.connect("released", lambda gg, n, x, y: self.ouvrir() if not self.ouverte else None); self.compacte.add_controller(g)
        GLib.timeout_add_seconds(2, self.tic); self.tic()

    # ---------------------------------------------------------------- placement / affichage
    def placer(self):
        T, B = LS.Edge.TOP, LS.Edge.BOTTOM
        haut = self.shell.position_barre() == "haut"
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(self.w, e, e == (T if haut else B))
        LS.set_margin(self.w, T, 32 + 6 if haut else 0); LS.set_margin(self.w, B, 0 if haut else 10)
        self.rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN if haut else Gtk.RevealerTransitionType.SLIDE_UP)
        # dépliée vers le haut quand l'île est en bas : la partie dépliée passe au-dessus de la pilule
        enf = self.pilule.get_first_child()
        if not haut and enf is self.compacte: self.pilule.reorder_child_after(self.compacte, self.rev)
        if haut and enf is self.rev: self.pilule.reorder_child_after(self.rev, self.compacte)

    def montrer(self, on):
        if on: self.w.present(); self.placer()     # ré-ancrer une surface visible (jamais une surface cachée)
        else: self.w.set_visible(False)

    def ouvrir_bientot(self):
        self._annuler(); self._src = GLib.timeout_add(220, lambda: (self.ouvrir(), False)[1])

    def fermer_bientot(self):
        self._annuler(); self._src = GLib.timeout_add(650, lambda: (self.fermer() if not self.shell.ouvert else None, False)[1])

    def _annuler(self):
        if self._src: GLib.source_remove(self._src); self._src = 0

    def ouvrir(self):
        self._src = 0
        if self.ouverte: return
        self.ouverte = True; self.remplir(); self.pilule.add_css_class("ile-ouverte"); self.rev.set_reveal_child(True)
        LS.set_keyboard_mode(self.w, LS.KeyboardMode.ON_DEMAND)

    def fermer(self):
        self._src = 0; self.ouverte = False; self.rev.set_reveal_child(False); self.pilule.remove_css_class("ile-ouverte")
        LS.set_keyboard_mode(self.w, LS.KeyboardMode.NONE)

    # ---------------------------------------------------------------- contenu
    def maj(self, groupes=None):
        """Appelé à chaque changement de fenêtres : appli active dans la pilule, applis dans la partie dépliée."""
        fen = self.shell.fenetres.liste() if self.shell.fenetres and self.shell.fenetres.ok else []
        act = next((f for f in fen if f.active and not f.reduite), None)
        vider(self.i_app)
        if act:
            a = apps.pour_fenetre(act.app_id); self.i_app.append(gicon_image(a.get_icon(), 18) if a else ico("app-window", 18, "c"))
        else:
            self.i_app.append(label("XIII", "titre-astoria", "ile-logo"))
        self._actif = (a.get_display_name() if act and a else (act.titre if act else "")) if act else ""
        if self.ouverte: self.remplir()
        self.tic()

    def remplir(self):
        vider(self.grand); sh = self.shell
        # 1. applis (épinglées + ouvertes), mêmes boutons que la barre des tâches : clic, clic droit, aperçus
        rang = boite(False, 4, halign=Gtk.Align.CENTER)
        st = Gtk.Button(); st.add_css_class("tb"); st.set_child(label("XIII", "titre-astoria", "ile-logo")); st.set_tooltip_text("Démarrer")
        st.connect("clicked", lambda *_: (self.fermer(), sh.basculer("demarrer"))); rang.append(st)
        fen = sh.fenetres.liste() if sh.fenetres and sh.fenetres.ok else []
        groupes, info = {}, {}
        for f in fen:
            a = apps.pour_fenetre(f.app_id); cle = a.get_id() if a else ("x:" + (f.app_id or f.titre))
            groupes.setdefault(cle, []).append(f); info[cle] = a
        ordre = [p for p in sh.cfg["epingles"] if apps.par_id(p)] + [k for k in groupes if k not in sh.cfg["epingles"]]
        for cle in ordre:
            a = info.get(cle) or (apps.par_id(cle) if not cle.startswith("x:") else None)
            rang.append(sh.bouton_tache(cle, a, groupes.get(cle, [])))
        self.grand.append(rang)
        # 2. widgets : lecture en cours, météo, raccourcis
        bas = boite(False, 12, halign=Gtk.Align.CENTER)
        cfg = sh.cfg
        if cfg.get("ile_minuteur", True): bas.append(self.carte_minuteur())
        if self._media and cfg.get("ile_media", True):
            mb = boite(False, 6, "ile-carte"); mb.append(ico("music", 16, "c")); mb.append(label(self._media, "petit", ellipsize=True, largeur=30))
            for ic, cmd in (("skip-back", "previous"), ("pause" if self._etat_media == "Playing" else "play", "play-pause"), ("skip-forward", "next")):
                mb.append(bouton(None, ic, "plat", taille=14, rappel=lambda c=cmd: (S.detacher(["playerctl", c]), GLib.timeout_add(400, lambda: (self.tic(), False)[1]))))
            bas.append(mb)
        m = getattr(sh, "_meteo", None) if cfg.get("ile_meteo", True) else None
        if m:
            from . import panneaux as P
            ic, nom = P.METEO.get(m["code"], ("cloud", ""))
            wb = Gtk.Button(); wb.add_css_class("ile-carte"); wb.add_css_class("plat"); x = boite(False, 6); x.append(ico(ic, 16, "c")); x.append(label("%d°C · %s" % (m["t"], nom), "petit")); wb.set_child(x)
            wb.connect("clicked", lambda *_: (self.fermer(), sh.basculer("widgets"))); bas.append(wb)
        rac = boite(False, 2, "ile-carte")
        for ic, tip, fn in (("search", "Rechercher", lambda: sh.basculer("demarrer-recherche")), ("bell", "Notifications", lambda: sh.basculer("volet")),
                            ("layout-dashboard", "Vue des tâches", lambda: sh.basculer("vue")), ("monitor", "Afficher le bureau", sh.afficher_bureau),
                            ("settings", "Paramètres", lambda: sh.parametres("accueil"))):
            rac.append(bouton(None, ic, "plat", taille=16, tip=tip, rappel=lambda f=fn: (self.fermer(), f())))
        bas.append(rac); self.grand.append(bas)
        if self._tally and cfg.get("ile_tally", True):
            tl = boite(False, 6, "ile-carte", halign=Gtk.Align.CENTER); tl.append(ico("radio-tower", 14, "c"))
            for num, nom, et in self._tally:
                p_ = Gtk.Box(valign=Gtk.Align.CENTER); p_.add_css_class("ile-pastille")
                if et == "preview": p_.add_css_class("preview")
                tl.append(p_); tl.append(label(("PGM " if et == "programme" else "PVW ") + (nom or "Cam %s" % num), "petit"))
            b_ = Gtk.Button(); b_.add_css_class("plat"); b_.set_child(tl); b_.set_tooltip_text("Ouvrir Tally XIII")
            b_.connect("clicked", lambda *_: (self.fermer(), S.detacher(["xiii-tally"]))); self.grand.append(b_)

    # ---------------------------------------------------------------- minuteur
    def reste(self):
        if self.fin_minuteur: return max(0, self.fin_minuteur - time.time())
        return self.reste_pause

    @staticmethod
    def hms(t):
        t = int(round(t)); return ("%d:%02d:%02d" % (t // 3600, t // 60 % 60, t % 60)) if t >= 3600 else "%02d:%02d" % (t // 60, t % 60)

    def carte_minuteur(self):
        mb = boite(False, 4, "ile-carte"); mb.append(ico("timer", 16, "c"))
        self.l_chrono = label(self.hms(self.reste()) if (self.fin_minuteur or self.reste_pause) else "Minuteur", "ile-chrono"); mb.append(self.l_chrono)
        for txt, n in (("+1", 60), ("+5", 300), ("+15", 900)):
            b = Gtk.Button(label=txt); b.add_css_class("plat"); b.add_css_class("petit"); b.set_tooltip_text("Ajouter %d min" % (n // 60))
            b.connect("clicked", lambda *_, n=n: self.minuteur_ajouter(n)); mb.append(b)
        if self.fin_minuteur or self.reste_pause:
            mb.append(bouton(None, "pause" if self.fin_minuteur else "play", "plat", taille=14, tip="Pause" if self.fin_minuteur else "Reprendre", rappel=self.minuteur_pause))
            mb.append(bouton(None, "rotate-ccw", "plat", taille=14, tip="Remettre à zéro", rappel=self.minuteur_zero))
        return mb

    def minuteur_ajouter(self, n):
        if self.fin_minuteur: self.fin_minuteur += n
        else: self.fin_minuteur = time.time() + self.reste_pause + n; self.reste_pause = 0
        self._demarrer_seconde(); self.apres_minuteur()

    def minuteur_pause(self):
        if self.fin_minuteur: self.reste_pause = self.reste(); self.fin_minuteur = None
        elif self.reste_pause: self.fin_minuteur = time.time() + self.reste_pause; self.reste_pause = 0; self._demarrer_seconde()
        self.apres_minuteur()

    def minuteur_zero(self):
        self.fin_minuteur = None; self.reste_pause = 0; self.apres_minuteur()

    def apres_minuteur(self):
        if self.ouverte: self.remplir()
        self.tic()

    def _demarrer_seconde(self):
        if not self._seconde: self._seconde = GLib.timeout_add(1000, self._chaque_seconde)

    def _chaque_seconde(self):
        if not self.fin_minuteur:
            self._seconde = 0; return False
        if self.reste() <= 0:
            self.fin_minuteur = None; self._seconde = 0; self._fini_jusqua = time.time() + 12
            from . import sons
            sons.jouer("complete", self.shell.cfg, force=True)
            S.detacher(["notify-send", "-a", "OS XIII", "-i", "alarm-clock", "-u", "critical", "Minuteur terminé", "Le temps est écoulé."])
            self.apres_minuteur(); return False
        self.tic(rapide=True)
        if self.ouverte and getattr(self, "l_chrono", None): self.l_chrono.set_text(self.hms(self.reste()))
        return True

    @staticmethod
    def lire_tally():
        """Caméras au programme / en preview si Tally XIII tourne sur ce PC : [(numéro, nom, état)]."""
        if S.DEMO and os.environ.get("XIII_ILE_TALLY"): return [("2", "Cam 2", "programme"), ("3", "Cam 3", "preview")]
        try:
            from . import tally_moteur
            port = int(tally_moteur.charger().get("port", 8790))
            with urllib.request.urlopen("http://127.0.0.1:%d/api/etat" % port, timeout=0.5) as r: d = json.load(r)
        except Exception:
            return None
        cams = [(k, v.get("nom", ""), v.get("etat")) for k, v in (d.get("cameras") or {}).items() if v.get("etat") in ("programme", "preview")]
        cams.sort(key=lambda x: (x[2] != "programme", int(x[0]) if str(x[0]).isdigit() else 0))
        return cams or None

    def tic(self, rapide=False):
        """Ce que montre la pilule repliée, par ordre d'importance : enregistrement, fin du minuteur, caméra au programme (Tally XIII),
        minuteur, tournage (timecode), lecture en cours, téléchargement, appli active."""
        sh = self.shell
        self.l_heure.set_text(time.strftime("%H:%M"))
        n = len(sh.serveur.liste) if getattr(sh, "serveur", None) else 0
        self.badge.set_text(str(n) if n < 100 else "99+"); self.badge.set_visible(n > 0)
        if rapide: return self._afficher(getattr(self, "_dernier", (False, "")))
        tally_ok = sh.cfg.get("ile_tally", True)
        def fond():
            tl = self.lire_tally() if tally_ok else None
            enr = subprocess.run(["pgrep", "-x", "wf-recorder"], stdout=subprocess.DEVNULL).returncode == 0
            o = S.out(["playerctl", "metadata", "--format", "{{status}}\t{{artist}}\t{{title}}"], 2) if not S.DEMO else "Playing\tXIII\tGénérique"
            return enr, o, tl
        def rendu(r):
            if isinstance(r, Exception): return
            enr, o, self._tally = r; self._dernier = (enr, o); self._afficher(self._dernier)
        S.en_fond(fond, rendu)
        return True

    def _afficher(self, r):
            sh = self.shell; enr, o = r
            p = (o or "").split("\t")
            self._etat_media = p[0] if len(p) > 2 else ""
            self._media = " — ".join(x for x in p[1:3] if x) if len(p) > 2 and p[0] in ("Playing", "Paused") else ""
            if not sh.cfg.get("ile_media", True): self._media = ""
            for c in ("ile-rec", "ile-media", "ile-minuteur", "ile-fini", "ile-programme", "ile-preview"): self.pilule.remove_css_class(c)
            pgm = [t for t in (self._tally or []) if t[2] == "programme"]
            if enr: self.l_act.set_text("● Enregistrement de l'écran"); self.pilule.add_css_class("ile-rec")
            elif time.time() < self._fini_jusqua: self.l_act.set_text("⏱ Minuteur terminé"); self.pilule.add_css_class("ile-fini")
            elif pgm: self.l_act.set_text("● PGM " + " · ".join(n or "Cam %s" % k for k, n, _ in pgm)); self.pilule.add_css_class("ile-programme")
            elif self.fin_minuteur: self.l_act.set_text("⏱ " + self.hms(self.reste())); self.pilule.add_css_class("ile-minuteur")
            elif sh.cfg.get("mode_tournage") or sh.cfg.get("profil") == "tournage": self.l_act.set_text("Tournage · " + (sh.l_tc.get_text() if hasattr(sh, "l_tc") else ""))
            elif self._media and self._etat_media == "Playing": self.l_act.set_text("♪ " + self._media); self.pilule.add_css_class("ile-media")
            elif sh.progres: self.l_act.set_text("Téléchargement %d %%" % round(100 * sum(sh.progres.values()) / len(sh.progres)))
            else: self.l_act.set_text(getattr(self, "_actif", "") or "")
            self.l_act.set_visible(bool(self.l_act.get_text()))
