# OS XIII — XIII Notes : notes rapides en Markdown (titres, gras, listes, cases à cocher cliquables) et croquis à main levée,
# rangées avec le projet actif (~/XIII/<projet>/03_Documents/Notes), sinon dans Documents/Notes. Enregistrement automatique.
# Une note part dans DOSSIER XIII en un clic. Les fichiers restent de simples .md / .png, lisibles partout.
# Application développée par Matthieu Lamotte.
import os, sys, re, json, time, glob, math
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, Pango
from . import config, systeme as S
from .ui import *
from .appli import preparer

COULEURS = ["#eee9e3", "#f0b378", "#ef6b6b", "#5fd39a", "#6aa8ff"]


def dossier_notes(projet=None):
    pj = projet if projet is not None else (config.charger().get("projet_actif") or "")
    if pj: d = os.path.expanduser("~/XIII/%s/03_Documents/Notes" % pj)
    else: d = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or os.path.expanduser("~/Documents"), "Notes")
    os.makedirs(d, exist_ok=True); return d


def titre_de(p):
    if p.endswith(".png"): return os.path.basename(p)[:-4]
    try:
        for l in open(p, encoding="utf-8"):
            l = l.strip().lstrip("#").strip()
            if l: return l[:60]
    except OSError: pass
    return "Note vide"


class Croquis(Gtk.DrawingArea):
    def __init__(self, chemin, rappel):
        super().__init__(hexpand=True, vexpand=True); self.chemin = chemin; self.rappel = rappel
        self.traits = []; self.couleur = COULEURS[1]; self.epaisseur = 3; self.gomme = False
        try: self.traits = json.load(open(chemin[:-4] + ".json"))
        except Exception: pass
        self.set_draw_func(self.dessin)
        g = Gtk.GestureDrag(); g.connect("drag-begin", self.debut); g.connect("drag-update", self.suite); g.connect("drag-end", lambda *_: self.sauver()); self.add_controller(g)

    def debut(self, g, x, y):
        self.x0, self.y0 = x, y
        self.traits.append({"c": "#1d1b19" if self.gomme else self.couleur, "e": self.epaisseur * (5 if self.gomme else 1), "gomme": self.gomme, "p": [[round(x, 1), round(y, 1)]]})

    def suite(self, g, dx, dy):
        self.traits[-1]["p"].append([round(self.x0 + dx, 1), round(self.y0 + dy, 1)]); self.queue_draw()

    def dessin(self, a, cr, w, h, fond=True):
        if fond: cr.set_source_rgb(0.114, 0.106, 0.098); cr.paint()
        cr.set_line_cap(1); cr.set_line_join(1)
        for t in self.traits:
            rgba = Gdk.RGBA(); rgba.parse(t["c"]); cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1)
            cr.set_line_width(t["e"]); P = t["p"]
            cr.move_to(*P[0])
            if len(P) == 1: cr.line_to(P[0][0] + .1, P[0][1])
            for x, y in P[1:]: cr.line_to(x, y)
            cr.stroke()

    def sauver(self):
        import cairo
        w, h = max(self.get_width(), 1200), max(self.get_height(), 800)
        s = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h); cr = cairo.Context(s); self.dessin(None, cr, w, h); s.write_to_png(self.chemin)
        json.dump(self.traits, open(self.chemin[:-4] + ".json", "w")); self.rappel()

    def effacer(self): self.traits = []; self.queue_draw(); self.sauver()

    def annuler(self):
        if self.traits: self.traits.pop(); self.queue_draw(); self.sauver()


class Notes(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.notes"); self.courant = None; self._src = 0; self.charge = False

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer(".liste-notes row { padding: 8px 10px; border-radius: 10px; } .editeur-notes { font-size: 15px; padding: 18px 22px; background: transparent; }"
                 " .editeur-notes text { background: transparent; }")
        self.win = Gtk.ApplicationWindow(application=self, title="XIII Notes", default_width=1100, default_height=720)
        racine = boite(False, 0); self.win.set_child(racine)
        g = boite(True, 8, "volet", margin_start=10, margin_end=6, margin_top=10, margin_bottom=10); g.set_size_request(270, -1); racine.append(g)
        g.append(label("Notes", "titre-astoria"))
        self.l_pj = label("", "petit", "attenue", wrap=True); g.append(self.l_pj)
        b = boite(False, 6); b.append(bouton("Note", "plus", "pilule", rappel=self.nouvelle)); b.append(bouton("Croquis", "pencil", "fantome", rappel=self.nouveau_croquis)); g.append(b)
        self.q = Gtk.SearchEntry(placeholder_text="Rechercher dans les notes"); self.q.connect("search-changed", lambda *_: self.lister()); g.append(self.q)
        sc = Gtk.ScrolledWindow(vexpand=True); self.liste = Gtk.ListBox(); self.liste.add_css_class("liste-notes"); self.liste.add_css_class("navigation-sidebar"); sc.set_child(self.liste); g.append(sc)
        self.liste.connect("row-activated", lambda l, r: self.ouvrir(r._chemin))
        g.append(label("Application développée par Matthieu Lamotte", "petit", "attenue", wrap=True))
        racine.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        d = boite(True, 0, hexpand=True); racine.append(d)
        self.outils = boite(False, 4, margin_start=12, margin_end=12, margin_top=8, margin_bottom=4); d.append(self.outils)
        self.pile = Gtk.Stack(vexpand=True); d.append(self.pile)
        self.tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, vexpand=True); self.tv.add_css_class("editeur-notes")
        self.buf = self.tv.get_buffer(); self.tags()
        self.buf.connect("changed", self.change)
        clic = Gtk.GestureClick(); clic.connect("released", self.clic_texte); self.tv.add_controller(clic)
        sc2 = Gtk.ScrolledWindow(); sc2.set_child(self.tv); self.pile.add_named(sc2, "texte")
        self.pile.add_named(label("Choisissez une note ou créez-en une.", "attenue"), "vide")
        self.zone_croquis = boite(True, 0); self.pile.add_named(self.zone_croquis, "croquis")
        self.lister(); self.win.present()
        L = self.fichiers()
        if L: self.ouvrir(L[0])
        else: self.pile.set_visible_child_name("vide")
        self._cfg = config.surveiller(lambda c: GLib.idle_add(self.lister))

    def tags(self):
        b = self.buf
        b.create_tag("h1", scale=1.6, weight=800); b.create_tag("h2", scale=1.3, weight=700); b.create_tag("h3", scale=1.12, weight=700)
        b.create_tag("gras", weight=700); b.create_tag("ital", style=Pango.Style.ITALIC); b.create_tag("marque", foreground="#8a93a6")
        b.create_tag("fait", strikethrough=True, foreground="#8a93a6"); b.create_tag("case", foreground="#f0b378", weight=700)

    def fichiers(self):
        d = dossier_notes(); q = self.q.get_text().lower().strip() if getattr(self, "q", None) else ""
        L = sorted(glob.glob(os.path.join(d, "*.md")) + glob.glob(os.path.join(d, "*.png")), key=os.path.getmtime, reverse=True)
        if q: L = [p for p in L if q in titre_de(p).lower() or (p.endswith(".md") and q in open(p, encoding="utf-8", errors="ignore").read().lower())]
        return L

    def lister(self):
        pj = config.charger().get("projet_actif") or ""
        self.l_pj.set_text(("Projet « %s »" % pj) if pj else "Aucun projet actif : notes dans Documents › Notes")
        c = self.liste.get_first_child()
        while c: n = c.get_next_sibling(); self.liste.remove(c); c = n
        for p in self.fichiers():
            r = Gtk.ListBoxRow(); r._chemin = p
            bx = boite(False, 8); bx.append(ico("pencil" if p.endswith(".png") else "notebook-pen", 16, "c"))
            t = boite(True, 0, hexpand=True); t.append(label(titre_de(p), "gras", ellipsize=True))
            t.append(label(time.strftime("%d/%m %H:%M", time.localtime(os.path.getmtime(p))), "petit", "attenue")); bx.append(t); r.set_child(bx); self.liste.append(r)
        return False

    # ------------------------------------------------------------ texte
    def nouvelle(self):
        p = os.path.join(dossier_notes(), time.strftime("Note %Y-%m-%d %H%M%S.md")); open(p, "w").write("# Nouvelle note\n\n- [ ] \n")
        self.lister(); self.ouvrir(p)

    def ouvrir(self, p):
        self.enregistrer(); self.courant = p
        vider(self.outils)
        if p.endswith(".png"): return self.ouvrir_croquis(p)
        for ic, tip, f in (("heading", "Titre", lambda: self.prefixe("# ")), ("list-checks" if os.path.exists("/usr/share/xiii/lucide/list-checks.svg") else "check-square", "Case à cocher", lambda: self.prefixe("- [ ] ")),
                           ("list", "Liste", lambda: self.prefixe("- ")), ("bold", "Gras", lambda: self.entourer("**")), ("italic", "Italique", lambda: self.entourer("*"))):
            self.outils.append(bouton(None, ic, "plat", tip=tip, rappel=f))
        self.outils.append(boite(False, 0, hexpand=True))
        self.outils.append(bouton("Envoyer à DOSSIER", "folder-input", "fantome", rappel=lambda: S.detacher(["xiii-suite", "--dossier", self.courant])))
        self.outils.append(bouton(None, "trash-2", "plat", tip="Mettre à la corbeille", rappel=self.supprimer))
        self.charge = True; self.buf.set_text(open(p, encoding="utf-8", errors="ignore").read()); self.charge = False
        self.styler(); self.pile.set_visible_child_name("texte"); self.tv.grab_focus()

    def change(self, *_):
        if self.charge: return
        self.styler()
        if self._src: GLib.source_remove(self._src)
        self._src = GLib.timeout_add(700, self.enregistrer)

    def enregistrer(self):
        self._src = 0
        if self.courant and self.courant.endswith(".md"):
            t = self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), True)
            try:
                if open(self.courant, encoding="utf-8").read() != t:
                    open(self.courant, "w", encoding="utf-8").write(t); GLib.idle_add(self.lister)
            except OSError: pass
        return False

    def styler(self):
        b = self.buf; b.remove_all_tags(b.get_start_iter(), b.get_end_iter())
        for n in range(b.get_line_count()):
            ok, it = b.get_iter_at_line(n)
            if not ok: continue
            fin = it.copy()
            if not fin.ends_line(): fin.forward_to_line_end()
            l = b.get_text(it, fin, True)
            m = re.match(r"^(#{1,3}) ", l)
            if m: b.apply_tag_by_name("h%d" % len(m.group(1)), it, fin); continue
            m = re.match(r"^(\s*[-*] \[([ xX])\] )", l)
            if m:
                e = it.copy(); e.forward_chars(len(m.group(1))); b.apply_tag_by_name("case", it, e)
                if m.group(2) in "xX": b.apply_tag_by_name("fait", e, fin)
            for rx, tag in ((r"\*\*[^*]+\*\*", "gras"), (r"(?<!\*)\*[^*\s][^*]*\*(?!\*)", "ital")):
                for mm in re.finditer(rx, l):
                    a = it.copy(); a.forward_chars(mm.start()); z = it.copy(); z.forward_chars(mm.end()); b.apply_tag_by_name(tag, a, z)

    def clic_texte(self, g, n, x, y):
        """Un clic sur [ ] coche la case (et l'inverse)."""
        bx, by = self.tv.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        ok, it = self.tv.get_iter_at_location(bx, by)
        if not ok: return
        ligne = it.get_line(); _, deb = self.buf.get_iter_at_line(ligne); fin = deb.copy()
        if not fin.ends_line(): fin.forward_to_line_end()
        l = self.buf.get_text(deb, fin, True); m = re.match(r"^(\s*[-*] \[)([ xX])(\])", l)
        if m and it.get_line_offset() <= len(m.group(0)) + 1:
            a = deb.copy(); a.forward_chars(len(m.group(1))); z = a.copy(); z.forward_char()
            self.buf.delete(a, z); _, a = self.buf.get_iter_at_line_offset(ligne, len(m.group(1)))
            self.buf.insert(a, " " if m.group(2) in "xX" else "x")

    def prefixe(self, p):
        it = self.buf.get_iter_at_mark(self.buf.get_insert()); it.set_line_offset(0); self.buf.insert(it, p); self.tv.grab_focus()

    def entourer(self, m):
        if self.buf.get_has_selection():
            a, z = self.buf.get_selection_bounds(); t = self.buf.get_text(a, z, True); self.buf.delete(a, z); self.buf.insert(a, m + t + m)
        else:
            self.buf.insert_at_cursor(m + m); it = self.buf.get_iter_at_mark(self.buf.get_insert()); it.backward_chars(len(m)); self.buf.place_cursor(it)
        self.tv.grab_focus()

    def supprimer(self):
        if not self.courant: return
        p = self.courant; self.courant = None
        for f in (p, p[:-4] + ".json" if p.endswith(".png") else None):
            if f and os.path.exists(f):
                try: Gio.File.new_for_path(f).trash(None)
                except GLib.Error: pass
        self.lister(); L = self.fichiers()
        if L: self.ouvrir(L[0])
        else: self.pile.set_visible_child_name("vide"); vider(self.outils)

    # ------------------------------------------------------------ croquis
    def nouveau_croquis(self):
        p = os.path.join(dossier_notes(), time.strftime("Croquis %Y-%m-%d %H%M%S.png"))
        import cairo
        s = cairo.ImageSurface(cairo.FORMAT_RGB24, 1200, 800); cr = cairo.Context(s); cr.set_source_rgb(0.114, 0.106, 0.098); cr.paint(); s.write_to_png(p)
        self.lister(); self.ouvrir(p)

    def ouvrir_croquis(self, p):
        vider(self.zone_croquis)
        c = Croquis(p, lambda: GLib.idle_add(self.lister))
        for coul in COULEURS:
            b = Gtk.Button(); b.add_css_class("plat"); da = Gtk.DrawingArea(); da.set_size_request(20, 20)
            da.set_draw_func(lambda a, cr, w, h, coul=coul: (cr.set_source_rgba(*(lambda r: (r.red, r.green, r.blue, 1))(self._rgba(coul))), cr.arc(w / 2, h / 2, 9, 0, 6.3), cr.fill()))
            b.set_child(da); b.connect("clicked", lambda _b, coul=coul: (setattr(c, "couleur", coul), setattr(c, "gomme", False))); self.outils.append(b)
        dd = Gtk.DropDown(model=Gtk.StringList.new(["Fin", "Moyen", "Épais"])); dd.set_selected(1)
        dd.connect("notify::selected", lambda w, *_: setattr(c, "epaisseur", [1.5, 3, 7][w.get_selected()])); self.outils.append(dd)
        self.outils.append(bouton(None, "eraser", "plat", tip="Gomme", rappel=lambda: setattr(c, "gomme", True)))
        self.outils.append(bouton(None, "undo-2", "plat", tip="Annuler le dernier trait", rappel=c.annuler))
        self.outils.append(bouton(None, "x", "plat", tip="Tout effacer", rappel=c.effacer))
        self.outils.append(boite(False, 0, hexpand=True))
        self.outils.append(bouton("Envoyer à DOSSIER", "folder-input", "fantome", rappel=lambda: S.detacher(["xiii-suite", "--dossier", p])))
        self.outils.append(bouton(None, "trash-2", "plat", tip="Mettre à la corbeille", rappel=self.supprimer))
        self.zone_croquis.append(c); self.pile.set_visible_child_name("croquis")

    def _rgba(self, h):
        r = Gdk.RGBA(); r.parse(h); return r


def main():
    sys.exit(Notes().run(sys.argv[:1]))
