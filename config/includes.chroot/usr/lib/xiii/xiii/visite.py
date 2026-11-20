# OS XIII — visite guidée du bureau (premier démarrage) : écran assombri, zone mise en lumière,
# bulle d'explication, « Suivant » / « Passer la visite » / « Ne plus afficher » — comme les tutos de la Suite XIII.
# Application développée par Matthieu Lamotte.
import math
import gi
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib
from gi.repository import Gtk4LayerShell as LS
from . import config, claude
from .ui import *

def etapes(sh):
    B, H = "bas", "haut"
    return [
        (None, None, "Bienvenue dans OS XIII", "Faisons le tour du bureau en une minute. Vous pourrez revoir cette visite depuis Paramètres › Suite XIII."),
        (sh.b_start, B, "Menu Démarrer", "Vos applications épinglées, vos fichiers récents et toutes les applications par catégories. Touche Windows (Super) pour l'ouvrir."),
        (sh.b_cherche, B, "Rechercher", "Tapez pour trouver une application, un réglage, un fichier, faire un calcul ou chercher sur le Web — Super + Espace de n'importe où."),
        (sh.taches, B, "Barre des tâches", "Applications épinglées et ouvertes. Clic : ouvrir ou réduire. Clic droit : épingler, fermer. Clic molette : nouvelle fenêtre."),
        (sh.b_meteo, B, "Widgets", "Météo, état du système, lecture en cours, notes et vos projets Suite XIII (projet, conducteur, prochain tournage)."),
        (sh.droite, B, "Heure et notifications", "Le volet de notifications avec le calendrier et le mode Ne pas déranger."),
        (sh.zone_haut, H, "Réglages rapides", "Wi-Fi, Bluetooth, son, énergie. Clic gauche : réglage rapide. Clic droit : la page complète des Paramètres."),
        (sh.h_centre, H, "Centre de contrôle", "Mode avion, lumière nocturne, thème clair/sombre, mode tournage, capture d'écran… (Super + A)."),
        (sh.taches, B, "Claude intégré", "Claude Desktop (discussion, Cowork, Claude Code) est épinglé à la barre : Super + C pour l'ouvrir, Super + Maj + C pour Claude Code dans votre projet. "
         "Il est relié à OS XIII : il voit l'état du PC et vos fichiers de la Suite XIII. Connectez-vous avec votre compte Claude.",
         ("Se connecter à Claude", lambda: claude.ouvrir())),
        (None, None, "C'est parti !", "Raccourcis utiles : Super (menu), Super + Espace (rechercher), Super + I (Paramètres), Super + Maj + S (capture), Super + V (presse-papiers), Super + L (verrouiller)."),
    ]

class Visite:
    def __init__(self, shell):
        self.shell = shell; self.i = 0; self.trou = None
        w = Gtk.Window(application=shell); self.win = w
        LS.init_for_window(w); LS.set_namespace(w, "xiii-visite"); LS.set_layer(w, LS.Layer.OVERLAY)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(w, e, True)
        LS.set_exclusive_zone(w, -1); LS.set_keyboard_mode(w, LS.KeyboardMode.EXCLUSIVE)
        w.add_css_class("xiii-surface")
        ov = Gtk.Overlay(); w.set_child(ov)
        self.da = Gtk.DrawingArea(hexpand=True, vexpand=True); self.da.set_draw_func(self.dessiner); ov.set_child(self.da)
        self.fixe = Gtk.Fixed(); ov.add_overlay(self.fixe)
        self.bulle = boite(True, 10, "panneau"); self.bulle.set_size_request(380, -1)
        self.fixe.put(self.bulle, 0, 0)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.touche); w.add_controller(k)
        self.L = etapes(shell)

    def touche(self, c, kv, code, st):
        if kv == Gdk.KEY_Escape: self.fin(False)
        elif kv in (Gdk.KEY_Return, Gdk.KEY_Right, Gdk.KEY_space): self.suivant()
        elif kv == Gdk.KEY_Left: self.precedent()
        return True

    def lancer(self):
        self.i = 0; self.shell.bulles.set_visible(False); self.win.present(); GLib.timeout_add(250, lambda: (self.montrer(), False)[1])

    def rect(self, widget, ou):
        ok, r = widget.compute_bounds(widget.get_root())
        if not ok or not widget.get_mapped(): return None
        W, Hh = self.win.get_width(), self.win.get_height()
        x, y, w, h = r.get_x(), r.get_y(), r.get_width(), r.get_height()
        if ou == "bas":
            y += Hh - widget.get_root().get_height()
        m = 6
        return (x - m, y - m, w + 2 * m, h + 2 * m)

    def montrer(self):
        cible, ou, titre, texte = self.L[self.i][:4]
        action = self.L[self.i][4] if len(self.L[self.i]) > 4 else None
        self.trou = self.rect(cible, ou) if cible is not None else None
        vider(self.bulle)
        h = boite(False, 10); h.append(ico("sparkles", 20, "c")); h.append(label(titre, "panneau-titre", hexpand=True))
        h.append(label("%d / %d" % (self.i + 1, len(self.L)), "attenue", "petit")); self.bulle.append(h)
        self.bulle.append(label(texte, wrap=True, largeur=46))
        if action:
            ab = boite(False, 0); ab.append(bouton(action[0], "sparkles", "fantome", taille=14, rappel=action[1])); self.bulle.append(ab)
        bas = boite(False, 8, margin_top=6)
        self.case = Gtk.CheckButton(label="Ne plus afficher", active=True); bas.append(self.case); bas.append(Gtk.Box(hexpand=True))
        if self.i < len(self.L) - 1: bas.append(bouton("Passer la visite", None, "plat", rappel=lambda: self.fin(False)))
        if self.i > 0: bas.append(bouton(None, "chevron-left", "fantome", taille=14, tip="Étape précédente", rappel=self.precedent))
        dernier = self.i == len(self.L) - 1
        bas.append(bouton("Terminer" if dernier else "Suivant", None, "pilule", rappel=self.suivant))
        self.bulle.append(bas)
        W, Hh = self.win.get_width(), self.win.get_height()
        _, nat = self.bulle.get_preferred_size(); bw = max(380, nat.width); bh = max(nat.height, 150)
        if self.trou:
            x, y, w, h = self.trou
            bx = min(max(12, x + w / 2 - bw / 2), W - bw - 12)
            by = y - bh - 18 if ou == "bas" else y + h + 18
        else:
            bx, by = W / 2 - bw / 2, Hh / 2 - bh / 2
        self.fixe.move(self.bulle, bx, max(12, by))
        self.da.queue_draw()

    def dessiner(self, da, cr, w, h):
        cr.set_fill_rule(1)  # EVEN_ODD
        cr.rectangle(0, 0, w, h)
        if self.trou:
            x, y, tw, th = self.trou; r = 10
            cr.new_sub_path()
            cr.arc(x + tw - r, y + r, r, -math.pi / 2, 0); cr.arc(x + tw - r, y + th - r, r, 0, math.pi / 2)
            cr.arc(x + r, y + th - r, r, math.pi / 2, math.pi); cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2); cr.close_path()
        cr.set_source_rgba(0, 0, 0, 0.62); cr.fill()
        if self.trou:
            x, y, tw, th = self.trou; r = 10
            A = self.shell.p["accent"].lstrip("#"); c = tuple(int(A[i:i + 2], 16) / 255 for i in (0, 2, 4))
            cr.new_sub_path()
            cr.arc(x + tw - r, y + r, r, -math.pi / 2, 0); cr.arc(x + tw - r, y + th - r, r, 0, math.pi / 2)
            cr.arc(x + r, y + th - r, r, math.pi / 2, math.pi); cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2); cr.close_path()
            cr.set_source_rgba(*c, 1); cr.set_line_width(2); cr.stroke()

    def suivant(self):
        if self.i >= len(self.L) - 1: self.fin(True); return
        self.i += 1; self.montrer()

    def precedent(self):
        if self.i > 0: self.i -= 1; self.montrer()

    def fin(self, terminee):
        if self.case.get_active() or terminee:
            config.modifier(visite_faite=True)
        self.win.set_visible(False)
