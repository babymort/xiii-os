# OS XIII — premiers pas, au premier démarrage d'un OS XIII installé : apparence, fichiers de l'ancien ordinateur,
# comptes en ligne et NAS, logiciels utiles. Chaque étape peut être passée ; tout reste modifiable dans Paramètres.
# Application développée par Matthieu Lamotte.
import os, sys
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import config, theme, systeme as S
from .ui import *
from .appli import preparer

ETAPES = ["apparence", "fichiers", "comptes", "logiciels", "fin"]

class PremiersPas(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.premierspas")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".grand-titre { font-family: Astoria, sans-serif; font-size: 34px; } .choix-carte { padding: 14px; border-radius: 14px; }")
        self.win = Gtk.ApplicationWindow(application=self, title="Premiers pas avec OS XIII", default_width=820, default_height=600)
        self.win.add_css_class("parametres")
        r = boite(True, 0)
        self.pile = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT); r.append(self.pile)
        bas = boite(False, 10, margin_start=24, margin_end=24, margin_bottom=18, margin_top=8)
        self.points = boite(False, 6, hexpand=True, valign=Gtk.Align.CENTER); bas.append(self.points)
        self.b_passer = bouton("Passer", None, "plat", rappel=self.suivant); bas.append(self.b_passer)
        self.b_suiv = bouton("Suivant", "arrow-right", "pilule", rappel=self.suivant); bas.append(self.b_suiv)
        r.append(bas)
        for k in ETAPES: self.pile.add_named(getattr(self, "e_" + k)(), k)
        self.win.set_child(r); self.i = 0; self.aller(0); self.win.present()

    def cadre(self, ic, titre, sous):
        v = boite(True, 14, margin_top=34, margin_start=48, margin_end=48)
        v.append(ico(ic, 46, "c")); v.append(label(titre, "grand-titre", xalign=0.5)); v.append(label(sous, "attenue", wrap=True, xalign=0.5, justify=Gtk.Justification.CENTER))
        return v

    def aller(self, i):
        self.i = i; self.pile.set_visible_child_name(ETAPES[i])
        vider(self.points)
        for j in range(len(ETAPES)): self.points.append(ico("circle-dot" if j == i else "circle", 12, "c" if j <= i else "d"))
        fin = ETAPES[i] == "fin"; self.b_passer.set_visible(not fin)
        self.b_suiv.set_child(boite(False, 6)); self.b_suiv.get_child().append(label("C'est parti" if fin else "Suivant"))

    def suivant(self):
        if ETAPES[self.i] == "fin":
            config.modifier(_histo=False, premiers_pas_fait=True); self.quit(); return
        self.aller(self.i + 1)

    # ---------------------------------------------------------------- étapes
    def e_apparence(self):
        v = self.cadre("palette", "Votre OS XIII", "Choisissez une ambiance. Tout se change ensuite dans Paramètres › Personnalisation.")
        g = boite(False, 12, homogeneous=True, halign=Gtk.Align.CENTER)
        for k, nom, ic in (("sombre", "Sombre", "moon"), ("clair", "Clair", "sun"), ("auto", "Auto (suit le soleil)", "sunrise"), ("sobre", "Sobre", "square")):
            b = Gtk.Button(); b.add_css_class("carte"); b.add_css_class("choix-carte")
            bx = boite(True, 6); bx.append(ico(ic, 28, "c")); bx.append(label(nom, xalign=0.5)); b.set_child(bx)
            b.connect("clicked", lambda _b, k=k: self.theme(k)); g.append(b)
        v.append(g)
        fl = boite(False, 8, halign=Gtk.Align.CENTER, margin_top=6)
        for n, hx in theme.ACCENTS[:10]:
            b = Gtk.Button(); b.add_css_class("pastille"); b.set_tooltip_text(n)
            pr = Gtk.CssProvider(); pr.load_from_string("button { background: %s; min-width: 28px; min-height: 28px; border-radius: 999px; }" % hx)
            b.get_style_context().add_provider(pr, 900); b.connect("clicked", lambda _b, hx=hx: self.theme(None, hx)); fl.append(b)
        v.append(label("Couleur d'accent", "attenue", xalign=0.5)); v.append(fl)
        return v

    def theme(self, t=None, accent=None):
        kw = {}
        if t: kw["theme"] = t
        if accent: kw["accent"] = accent; kw["accent_auto"] = False
        c = config.charger(); c2 = dict(c, **kw)
        if theme.fond_par_defaut(c.get("fond")): kw["fond"] = theme.fond_assorti(c2)
        c = config.modifier(**kw); S.en_fond(theme.appliquer_systeme, None, c)

    def e_fichiers(self):
        v = self.cadre("folder-input", "Vos fichiers", "Vous venez de Windows ou d'un Mac ? Récupérez Bureau, Documents, Images, Musique et Vidéos de l'ancien système "
                       "(sur ce PC ou sur un disque branché). Rien n'est modifié sur l'ancien disque.")
        b = bouton("Récupérer mes fichiers…", "folder-input", "pilule", rappel=lambda: S.detacher("xiii-recuperer")); b.set_halign(Gtk.Align.CENTER); v.append(b)
        return v

    def e_comptes(self):
        v = self.cadre("cloud", "Cloud et réseau", "Branchez vos espaces en ligne (OneDrive, Google Drive, Dropbox…) et les NAS du réseau : ils apparaissent dans Fichiers comme des disques.")
        r = boite(False, 10, halign=Gtk.Align.CENTER)
        r.append(bouton("Comptes en ligne et NAS…", "hard-drive", "pilule", rappel=lambda: S.detacher("xiii-lecteurs")))
        r.append(bouton("Suite XIII", "layout-grid", "fantome", rappel=lambda: S.detacher("xiii-suite")))
        v.append(r); return v

    def e_logiciels(self):
        v = self.cadre("package", "Vos logiciels", "Montage, régie, son, photo, bureautique, jeux : le Centre de logiciels installe tout en un clic, "
                       "et les logiciels Windows passent par Applications Windows.")
        r = boite(False, 10, halign=Gtk.Align.CENTER)
        r.append(bouton("Centre de logiciels", "package", "pilule", rappel=lambda: S.detacher("xiii-logiciels")))
        r.append(bouton("Applications Windows", "app-window", "fantome", rappel=lambda: S.detacher("xiii-windows")))
        r.append(bouton("Pilotes", "cpu", "fantome", rappel=lambda: S.detacher(["xiii-bilan", "--pilotes"])))
        v.append(r); return v

    def e_fin(self):
        v = self.cadre("party-popper", "C'est prêt !", "Une visite guidée vous montre maintenant le bureau. Retrouvez ces étapes à tout moment : "
                       "Paramètres › Système › À propos › Premiers pas.")
        v.append(label("Application développée par Matthieu Lamotte", "credit", xalign=0.5))
        return v

def main():
    sys.exit(PremiersPas().run(sys.argv[:1]))
