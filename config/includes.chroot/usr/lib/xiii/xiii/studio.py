# OS XIII — Studio XIII : l'espace de travail du mode Production, façon « Academic OS » / Notion, pensé pour l'audiovisuel.
#   • Tableau de bord : bannière, horloge, actions rapides, tâches de la semaine, tableaux actifs, habitudes, mémos épinglés
#   • Organiser : tableaux façon Trello (colonnes libres, cartes glissables, personnes, échéances, listes à cocher,
#     étiquettes, commentaires, archives) + modèles pré-prod / tournage / post-prod / livraison et cartes audiovisuelles
#     (plan / rush, livrable, validation client)
#   • Tâches : priorité, statut, échéance ; vues Aujourd'hui / Semaine / Mois / Terminées et semaine en calendrier
#   • Mémos : notes en cartes colorées façon pense-bêtes (texte ou liste, épingles, étiquettes, recherche)
#   • Objectifs : semaine, mois, année
# Tout est rangé avec le projet actif (~/XIII/<projet>/.studio/, donc synchronisé avec OneDrive si le dossier XIII l'est),
# sinon dans ~/XIII/.studio. Fichiers JSON simples. Utilisé dans le mode Production et en application (xiii-studio, xiii-memos).
# Application développée par Matthieu Lamotte.
import os, sys, json, time, uuid, datetime, math
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio, Pango
from . import config
from .ui import *

JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
ETIQUETTES = [("rouge", "#e5534b"), ("orange", "#f0883e"), ("jaune", "#d4a72c"), ("vert", "#57ab5a"), ("bleu", "#539bf5"), ("violet", "#b083f0")]
COUL_MEMOS = [("defaut", None), ("ambre", "#5a4325"), ("rouge", "#5c2b29"), ("vert", "#2d4a33"), ("bleu", "#25405c"), ("violet", "#43315c"), ("gris", "#3a3a3a"), ("sable", "#4d4637")]
PRIOS = [("haute", "Haute", "#e5534b"), ("moyenne", "Moyenne", "#d4a72c"), ("basse", "Basse", "#57ab5a")]
STATUTS = [("a_faire", "À faire", "#8b949e"), ("en_cours", "En cours", "#539bf5"), ("fait", "Fait", "#57ab5a")]
TYPES_CARTE = [("simple", "Carte", "square"), ("plan", "Plan / rush", "clapperboard"), ("livrable", "Livrable", "package"), ("validation", "Validation client", "badge-check")]
CHAMPS_TYPE = {"plan": [("sequence", "Séquence"), ("plan", "Plan"), ("prise", "Prise"), ("timecode", "Timecode"), ("camera", "Caméra"), ("carte_memoire", "Carte mémoire")],
               "livrable": [("format", "Format (ex. 1920×1080 25p)"), ("duree", "Durée"), ("codec", "Codec / conteneur"), ("diffusion", "Date de diffusion")],
               "validation": [("version", "Version (V1, V2…)"), ("client", "Client"), ("lien", "Lien de visionnage")]}
STATUT_VALID = ["En attente", "Retours", "Validé"]
MODELES = {
    "vide": ("Tableau vide", [("À faire", "#8b949e"), ("En cours", "#539bf5"), ("Terminé", "#57ab5a")]),
    "prepro": ("Pré-production", [("Idées", "#b083f0"), ("Écriture", "#539bf5"), ("Repérages", "#d4a72c"), ("Casting / équipe", "#f0883e"), ("Prêt", "#57ab5a")]),
    "tournage": ("Tournage", [("À tourner", "#8b949e"), ("Aujourd'hui", "#f0883e"), ("Tourné", "#539bf5"), ("Sauvegardé", "#57ab5a")]),
    "postprod": ("Post-production", [("Dérushage", "#8b949e"), ("Montage", "#539bf5"), ("Étalonnage", "#b083f0"), ("Son / mixage", "#d4a72c"), ("Fini", "#57ab5a")]),
    "livraison": ("Livraison", [("À exporter", "#8b949e"), ("En validation", "#d4a72c"), ("Retours client", "#e5534b"), ("Livré", "#57ab5a")]),
}

CSS = """
.studio-banniere { border-radius: 16px; }
.studio-bloc { border-radius: 14px; padding: 14px; background: alpha(currentColor, .045); border: 1px solid alpha(currentColor, .08); }
.studio-titre-bloc { padding: 6px 12px; border-radius: 10px; background: alpha(#8a5a2b, .55); font-weight: 700; }
.studio-colonne { border-radius: 14px; padding: 10px; background: alpha(currentColor, .05); min-width: 272px; }
.studio-carte { border-radius: 10px; padding: 10px; background: alpha(currentColor, .07); border: 1px solid alpha(currentColor, .10); }
.studio-carte:hover { border-color: alpha(#f0b378, .6); }
.studio-etiq { min-height: 6px; min-width: 34px; border-radius: 3px; }
.studio-pastille { border-radius: 6px; padding: 1px 7px; font-size: 11px; font-weight: 600; }
.studio-memo { border-radius: 12px; padding: 12px; border: 1px solid alpha(currentColor, .12); min-width: 220px; }
.studio-fait { opacity: .55; }
.studio-jour { border-radius: 10px; padding: 8px; background: alpha(currentColor, .04); min-height: 160px; }
.studio-jour.aujourdhui { border: 1px solid #f0b378; }
.studio-depot { background: alpha(#f0b378, .12); }
.studio-progres trough { min-height: 6px; border-radius: 3px; } .studio-progres progress { min-height: 6px; border-radius: 3px; }
"""
_css_ok = False
def css():
    global _css_ok
    if _css_ok: return
    p = Gtk.CssProvider(); p.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 5); _css_ok = True


def nid(): return uuid.uuid4().hex[:10]
def aujourdhui(): return datetime.date.today()
def lire_date(s):
    try: return datetime.date.fromisoformat(s)
    except Exception: return None
def date_courte(d):
    if not d: return ""
    j = (d - aujourdhui()).days
    return "aujourd'hui" if j == 0 else "demain" if j == 1 else "hier" if j == -1 else "%d %s" % (d.day, MOIS[d.month - 1][:4] + ".")
def saisie_date(t):
    """« 27/11 », « 27/11/2026 », « 2026-11-27 », « demain » → date ISO."""
    t = (t or "").strip().lower()
    if not t: return ""
    if t in ("aujourd'hui", "auj"): return aujourdhui().isoformat()
    if t == "demain": return (aujourdhui() + datetime.timedelta(days=1)).isoformat()
    for f in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d/%m"):
        try:
            d = datetime.datetime.strptime(t, f).date()
            if f == "%d/%m": d = d.replace(year=aujourdhui().year)
            return d.isoformat()
        except ValueError: pass
    return ""


# ====================================================================================== données
class Donnees:
    """Fichiers JSON du projet actif. Écriture atomique, relus à chaque changement de projet."""
    def __init__(self, projet=None):
        self.projet = projet if projet is not None else (config.charger().get("projet_actif") or "")
        base = os.path.expanduser("~/XIII")
        self.dossier = os.path.join(base, self.projet, ".studio") if self.projet else os.path.join(base, ".studio")
        os.makedirs(self.dossier, exist_ok=True)
        self.c = {}

    def lire(self, nom, defaut):
        if nom not in self.c:
            try: self.c[nom] = json.load(open(os.path.join(self.dossier, nom + ".json")))
            except Exception: self.c[nom] = defaut
        return self.c[nom]

    def ecrire(self, nom):
        f = os.path.join(self.dossier, nom + ".json"); t = f + ".tmp"
        with open(t, "w") as o: json.dump(self.c[nom], o, ensure_ascii=False, indent=1)
        os.replace(t, f)

    # --- organiser
    def tableaux(self):
        d = self.lire("organiser", {"tableaux": [], "actif": None})
        if not d["tableaux"]:
            self.nouveau_tableau("tournage" if self.projet else "vide", ecrire=False)
        return d

    def nouveau_tableau(self, modele="vide", nom=None, ecrire=True):
        d = self.lire("organiser", {"tableaux": [], "actif": None})
        titre, cols = MODELES.get(modele, MODELES["vide"])
        t = {"id": nid(), "nom": nom or titre, "modele": modele, "colonnes": [{"id": nid(), "nom": n, "couleur": c, "cartes": []} for n, c in cols]}
        d["tableaux"].append(t); d["actif"] = t["id"]
        if ecrire: self.ecrire("organiser")
        return t

    def tableau_actif(self):
        d = self.tableaux()
        return next((t for t in d["tableaux"] if t["id"] == d.get("actif")), d["tableaux"][0])

    def trouver_carte(self, cid):
        for t in self.tableaux()["tableaux"]:
            for c in t["colonnes"]:
                for i, k in enumerate(c["cartes"]):
                    if k["id"] == cid: return t, c, i, k
        return None, None, None, None

    def deplacer_carte(self, cid, col_id, index):
        t, c, i, k = self.trouver_carte(cid)
        if not k: return
        c["cartes"].pop(i)
        dest = next(x for x in t["colonnes"] if x["id"] == col_id)
        if dest is c and index > i: index -= 1
        dest["cartes"].insert(max(0, min(index, len(dest["cartes"]))), k)
        self.ecrire("organiser")

    # --- autres bases
    def taches(self): return self.lire("taches", [])
    def memos(self): return self.lire("memos", [])
    def objectifs(self): return self.lire("objectifs", {"semaine": [], "mois": [], "annee": []})
    def habitudes(self): return self.lire("habitudes", [{"nom": "Sauvegarder les rushes", "jours": {}}, {"nom": "Vérifier le planning du lendemain", "jours": {}}])


# ====================================================================================== petits composants
def pastille(txt, couleur):
    l = label(txt, "studio-pastille"); p = Gtk.CssProvider()
    p.load_from_string("label { background: alpha(%s, .22); color: %s; }" % (couleur, couleur)); l.get_style_context().add_provider(p, 900)
    return l

def colorer(w, couleur, alpha=1.0):
    if not couleur: return
    p = Gtk.CssProvider(); p.load_from_string("* { background: alpha(%s, %s); }" % (couleur, alpha)); w.get_style_context().add_provider(p, 900)

def titre_bloc(ic, txt, droite=None):
    h = boite(False, 8, "studio-titre-bloc"); h.append(ico(ic, 16)); h.append(label(txt, "gras", hexpand=True))
    if droite: h.append(droite)
    return h

def entree(texte="", ph="", largeur=None):
    e = Gtk.Entry(text=texte or "", placeholder_text=ph)
    if largeur: e.set_width_chars(largeur)
    return e

def initiales(nom):
    p = [x for x in nom.replace("-", " ").split() if x]
    return "".join(x[0] for x in p[:2]).upper() or "?"

def fenetre(parent, titre, l=560, h=640):
    w = Gtk.Window(title=titre, modal=True, default_width=l, default_height=h)
    if parent and isinstance(parent.get_root(), Gtk.Window): w.set_transient_for(parent.get_root())
    return w


class Horloge(Gtk.DrawingArea):
    """Horloge à aiguilles + date (comme le tableau de bord d'Academic OS)."""
    def __init__(self, taille=150):
        super().__init__(); self.set_content_width(taille); self.set_content_height(taille + 34); self.set_draw_func(self.dessin)
        GLib.timeout_add_seconds(1, lambda: (self.queue_draw(), self.get_root() is not None)[1])     # s'arrête quand la page est reconstruite

    def dessin(self, _a, cr, w, h):
        r = min(w, h - 34) / 2 - 4; cx, cy = w / 2, r + 4
        cr.set_source_rgba(1, 1, 1, .06); cr.arc(cx, cy, r, 0, 2 * math.pi); cr.fill()
        cr.set_source_rgba(1, 1, 1, .35)
        for i in range(12):
            a = i * math.pi / 6; cr.set_line_width(2 if i % 3 == 0 else 1)
            cr.move_to(cx + math.sin(a) * r * .84, cy - math.cos(a) * r * .84); cr.line_to(cx + math.sin(a) * r * .95, cy - math.cos(a) * r * .95); cr.stroke()
        n = datetime.datetime.now()
        for val, lon, ep, col in ((n.hour % 12 + n.minute / 60, .5, 3.5, (.93, .91, .89)), (n.minute + n.second / 60, .75, 2.5, (.93, .91, .89)), (n.second, .85, 1.2, (.94, .70, .47))):
            a = val * math.pi / (6 if lon == .5 else 30)
            cr.set_source_rgb(*col); cr.set_line_width(ep); cr.move_to(cx, cy); cr.line_to(cx + math.sin(a) * r * lon, cy - math.cos(a) * r * lon); cr.stroke()
        cr.set_source_rgba(.93, .91, .89, .9); cr.select_font_face("IBM Plex Sans"); cr.set_font_size(13)
        t = n.strftime("%H:%M:%S"); e = cr.text_extents(t); cr.move_to(cx - e.width / 2, h - 18); cr.show_text(t)
        cr.set_source_rgba(.6, .58, .55, 1); cr.set_font_size(11)
        t = "%s %d %s" % (JOURS[n.weekday()], n.day, MOIS[n.month - 1]); e = cr.text_extents(t); cr.move_to(cx - e.width / 2, h - 3); cr.show_text(t)


# ====================================================================================== Studio
class Studio:
    """Studio XIII en un seul objet : self.page(cle) donne la page à afficher (tableau de bord, organiser, tâches, mémos, objectifs)."""
    PAGES = [("bord", "layout-dashboard", "Tableau de bord"), ("organiser", "square-kanban", "Organiser"), ("taches", "list-checks", "Tâches"),
             ("memos", "sticky-note", "Mémos"), ("objectifs", "trophy", "Objectifs")]

    def __init__(self, ouvrir_page=None, projet=None, haut_bord=None):
        css(); self.d = Donnees(projet); self.ouvrir_page = ouvrir_page or (lambda k: None); self.haut_bord = haut_bord
        self.conteneurs = {}; self.vue_taches = "semaine"; self.recherche_memos = ""

    def page(self, cle):
        """Conteneur (ScrolledWindow) de la page, rempli maintenant et à chaque changement."""
        if cle not in self.conteneurs:
            sc = Gtk.ScrolledWindow(vexpand=True, hexpand=True); self.conteneurs[cle] = sc
        self.remplir(cle)
        return self.conteneurs[cle]

    def remplir(self, cle):
        sc = self.conteneurs.get(cle)
        if not sc: return
        v = boite(True, 14, margin_start=26, margin_end=26, margin_top=20, margin_bottom=26)
        getattr(self, "p_" + cle)(v); sc.set_child(v)

    def rafraichir(self, *cles):
        for k in (cles or list(self.conteneurs)): self.remplir(k)

    def entete(self, v, titre, sous, droite=None):
        h = boite(False, 12); c = boite(True, 0, hexpand=True); c.append(label(titre, "grand-titre"))
        c.append(label(sous, "attenue", wrap=True)); h.append(c)
        if droite: h.append(droite)
        v.append(h)

    # ---------------------------------------------------------------- tableau de bord
    def p_bord(self, v):
        from .modes import couverture
        if self.haut_bord: self.haut_bord(v)            # mode Production : projet en cours + outils récents en tête
        else:
            ov = Gtk.Overlay(); ban = couverture(self.d.projet or "studio", 600, 150); ban.set_hexpand(True); ban.add_css_class("studio-banniere")
            ov.set_child(ban)
            t = boite(True, 2, valign=Gtk.Align.END, halign=Gtk.Align.START, margin_start=22, margin_bottom=16)
            t.append(label(self.d.projet or "Studio XIII", "grand-titre")); t.append(label("Votre espace de production", "attenue"))
            ov.add_overlay(t); v.append(ov)
        # raccourcis vers les pages
        nav = boite(False, 8)
        for k, ic, n in self.PAGES[1:]:
            nav.append(bouton(n, ic, "fantome", rappel=lambda k=k: self.ouvrir_page(k)))
        v.append(nav)
        grille = boite(False, 16, homogeneous=False)
        g1 = boite(True, 14); g1.set_size_request(240, -1); g2 = boite(True, 14, hexpand=True); g3 = boite(True, 14); g3.set_size_request(300, -1)
        grille.append(g1); grille.append(g2); grille.append(g3); v.append(grille)
        # col. 1 : horloge + actions rapides
        b = boite(True, 8, "studio-bloc"); b.append(Horloge(170)); g1.append(b)
        a = boite(True, 4, "studio-bloc"); a.append(titre_bloc("zap", "Actions rapides"))
        for ic, n, fn in (("square-plus", "Nouvelle carte", self.nouvelle_carte_rapide), ("list-plus", "Nouvelle tâche", lambda: self.ouvrir_page("taches")),
                          ("sticky-note", "Nouveau mémo", lambda: self.editer_memo(None, a)), ("trophy", "Nouvel objectif", lambda: self.ouvrir_page("objectifs")),
                          ("layout-template", "Nouveau tableau", lambda: self.choisir_modele(a))):
            a.append(bouton(n, ic, "ligne", "plat", rappel=fn))
        g1.append(a)
        # col. 2 : tâches de la semaine + tableaux actifs
        tb = boite(True, 6, "studio-bloc"); tb.append(titre_bloc("list-checks", "Tâches de la semaine", bouton(None, "plus", "plat", taille=14, rappel=lambda: self.ouvrir_page("taches"))))
        fin = aujourdhui() + datetime.timedelta(days=7)
        T = [t for t in self.d.taches() if t.get("statut") != "fait" and (not t.get("echeance") or lire_date(t["echeance"]) and lire_date(t["echeance"]) <= fin)]
        T.sort(key=lambda t: (t.get("echeance") or "9999", ["haute", "moyenne", "basse"].index(t.get("priorite", "moyenne"))))
        if not T: tb.append(label("Rien d'urgent cette semaine.", "attenue", "petit"))
        for t in T[:8]: tb.append(self.ligne_tache(t, compacte=True))
        g2.append(tb)
        pr = boite(True, 8, "studio-bloc"); pr.append(titre_bloc("square-kanban", "Tableaux", bouton(None, "plus", "plat", taille=14, rappel=lambda: self.choisir_modele(pr))))
        fl = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3, column_spacing=10, row_spacing=10, homogeneous=True)
        for t in self.d.tableaux()["tableaux"]:
            n = sum(len(c["cartes"]) for c in t["colonnes"]); f = len(t["colonnes"][-1]["cartes"]) if t["colonnes"] else 0
            c = Gtk.Button(); c.add_css_class("studio-carte"); bx = boite(True, 6)
            from .modes import couverture
            bx.append(couverture(t["id"], 200, 56, collines=False)); bx.append(label(t["nom"], "gras", ellipsize=True))
            bx.append(label("%d carte%s · %d terminée%s" % (n, "s" if n > 1 else "", f, "s" if f > 1 else ""), "petit", "attenue"))
            pb = Gtk.ProgressBar(fraction=(f / n) if n else 0); pb.add_css_class("studio-progres"); bx.append(pb); c.set_child(bx)
            c.connect("clicked", lambda _b, t=t: (self.d.tableaux().__setitem__("actif", t["id"]), self.d.ecrire("organiser"), self.ouvrir_page("organiser"))); fl.append(c)
        pr.append(fl); g2.append(pr)
        # col. 3 : habitudes du jour + objectifs + mémos épinglés
        hb = boite(True, 6, "studio-bloc"); hb.append(titre_bloc("repeat", "Habitudes du jour", bouton(None, "plus", "plat", taille=14, rappel=lambda: self.ajouter_habitude(hb))))
        j = aujourdhui().isoformat(); H = self.d.habitudes()
        for h in H:
            cb = Gtk.CheckButton(label=h["nom"], active=bool(h["jours"].get(j)))
            def coche(w, h=h):
                h["jours"][j] = w.get_active(); self.d.ecrire("habitudes"); GLib.idle_add(lambda: (self.remplir("bord"), False)[1])
            cb.connect("toggled", coche); hb.append(cb)
        if H:
            faits = sum(1 for h in H if h["jours"].get(j)); pb = Gtk.ProgressBar(fraction=faits / len(H)); pb.add_css_class("studio-progres")
            hb.append(pb); hb.append(label("%d / %d aujourd'hui" % (faits, len(H)), "petit", "attenue"))
            sem = [(aujourdhui() - datetime.timedelta(days=k)).isoformat() for k in range(7)]
            hb.append(label("Cette semaine : %d %%" % round(100 * sum(1 for h in H for s in sem if h["jours"].get(s)) / (7 * len(H))), "petit", "attenue"))
        g3.append(hb)
        ob = boite(True, 6, "studio-bloc"); ob.append(titre_bloc("trophy", "Objectifs"))
        O = self.d.objectifs()
        for k, n in (("semaine", "Cette semaine"), ("mois", "Ce mois-ci"), ("annee", "Cette année")):
            L = O.get(k, [])
            if not L: continue
            f = sum(1 for x in L if x["ok"]); pb = Gtk.ProgressBar(fraction=f / len(L)); pb.add_css_class("studio-progres")
            ob.append(label("%s — %d / %d" % (n, f, len(L)), "petit")); ob.append(pb)
        if not any(O.values()): ob.append(bouton("Fixer des objectifs", "plus", "fantome", rappel=lambda: self.ouvrir_page("objectifs")))
        g3.append(ob)
        ep = [m for m in self.d.memos() if m.get("epingle")]
        if ep:
            mb = boite(True, 6, "studio-bloc"); mb.append(titre_bloc("pin", "Mémos épinglés"))
            for m in ep[:4]: mb.append(self.carte_memo(m, petite=True))
            g3.append(mb)

    def ajouter_habitude(self, ancre):
        pop = Gtk.Popover(); pop.set_parent(ancre); e = entree(ph="Nouvelle habitude (ex. sauvegarder les cartes)", largeur=30)
        def ok(*_):
            if e.get_text().strip(): self.d.habitudes().append({"nom": e.get_text().strip(), "jours": {}}); self.d.ecrire("habitudes")
            pop.popdown(); self.remplir("bord")
        e.connect("activate", ok); pop.set_child(e); pop.popup(); e.grab_focus()

    def nouvelle_carte_rapide(self):
        t = self.d.tableau_actif()
        if t["colonnes"]:
            k = {"id": nid(), "titre": "Nouvelle carte", "type": "simple", "checklist": [], "etiquettes": [], "personnes": [], "commentaires": [], "cree": time.time()}
            t["colonnes"][0]["cartes"].insert(0, k); self.d.ecrire("organiser"); self.ouvrir_page("organiser"); self.editer_carte(k["id"], None)

    def choisir_modele(self, ancre):
        items = [("layout-template", n, (lambda m=m: (self.d.nouveau_tableau(m), self.rafraichir(), self.ouvrir_page("organiser")))) for m, (n, _c) in MODELES.items()]
        popover_menu(ancre, items)

    # ---------------------------------------------------------------- organiser (Trello)
    def p_organiser(self, v):
        d = self.d.tableaux(); t = self.d.tableau_actif()
        droite = boite(False, 6)
        dd = Gtk.DropDown.new_from_strings([x["nom"] for x in d["tableaux"]]); dd.set_selected(d["tableaux"].index(t))
        dd.connect("notify::selected", lambda w, _p: (d.__setitem__("actif", d["tableaux"][w.get_selected()]["id"]), self.d.ecrire("organiser"), GLib.idle_add(lambda: (self.remplir("organiser"), False)[1])))
        droite.append(dd)
        nb = bouton("Nouveau tableau", "plus", "fantome"); nb.connect("clicked", lambda b: self.choisir_modele(b)); droite.append(nb)
        mb = bouton(None, "ellipsis", "plat"); mb.connect("clicked", lambda b: popover_menu(b, [
            ("pencil", "Renommer le tableau", lambda: self.renommer(b, t["nom"], lambda n: (t.__setitem__("nom", n), self.d.ecrire("organiser"), self.remplir("organiser")))),
            ("archive", "Cartes archivées", lambda: self.archives(b, t)),
            ("trash-2", "Supprimer le tableau", lambda: self.supprimer_tableau(t))])); droite.append(mb)
        self.entete(v, "Organiser", "Colonnes libres, cartes glissables d'une colonne à l'autre. Clic sur une carte pour la détailler.", droite)
        # filtre rapide
        f = Gtk.SearchEntry(placeholder_text="Filtrer les cartes (titre, personne, étiquette)…"); f.set_text(getattr(self, "_filtre", "")); v.append(f)
        hs = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.NEVER, hexpand=True, min_content_height=560)
        rang = boite(False, 12, valign=Gtk.Align.START, margin_bottom=8); hs.set_child(rang)
        def remplir_cols():
            vider(rang); q = f.get_text().strip().lower(); self._filtre = f.get_text()
            for c in t["colonnes"]: rang.append(self.colonne(t, c, q))
            add = boite(True, 6, "studio-colonne", valign=Gtk.Align.START)
            e = entree(ph="+ Ajouter une colonne")
            def ajout(*_):
                if e.get_text().strip():
                    t["colonnes"].append({"id": nid(), "nom": e.get_text().strip(), "couleur": "#8b949e", "cartes": []}); self.d.ecrire("organiser"); remplir_cols()
            e.connect("activate", ajout); add.append(e); rang.append(add)
        f.connect("search-changed", lambda *_: remplir_cols())
        remplir_cols(); v.append(hs)

    def colonne(self, t, c, filtre=""):
        col = boite(True, 8, "studio-colonne", valign=Gtk.Align.START); col.set_size_request(272, -1)
        h = boite(False, 8); h.append(ico("circle", 12, c.get("couleur") or "#8b949e")); h.append(label(c["nom"], "gras", hexpand=True, ellipsize=True))
        vis = [k for k in c["cartes"] if not k.get("archive")]
        h.append(label(str(len(vis)), "badge-nb"))
        m = bouton(None, "ellipsis", "plat", taille=14)
        def menu(b, c=c):
            popover_menu(b, [("pencil", "Renommer", lambda: self.renommer(b, c["nom"], lambda n: (c.__setitem__("nom", n), self.d.ecrire("organiser"), self.remplir("organiser")))),
                             ("palette", "Changer la couleur", lambda: popover_menu(b, [("circle", n, (lambda x=x: (c.__setitem__("couleur", x), self.d.ecrire("organiser"), self.remplir("organiser")))) for n, x in ETIQUETTES])),
                             ("arrow-left", "Déplacer à gauche", lambda: self.bouger_colonne(t, c, -1)), ("arrow-right", "Déplacer à droite", lambda: self.bouger_colonne(t, c, 1)),
                             None, ("trash-2", "Supprimer la colonne", lambda: self.supprimer_colonne(t, c))])
        m.connect("clicked", menu); h.append(m); col.append(h)
        liste = boite(True, 8); col.append(liste)
        for k in vis:
            if filtre and filtre not in (k["titre"] + " " + " ".join(k.get("personnes", [])) + " " + " ".join(k.get("etiquettes", []))).lower(): continue
            liste.append(self.carte(k))
        # dépôt d'une carte glissée : à la position du pointeur
        dt = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        def depot(cible, val, x, y, c=c):
            if not str(val).startswith("carte:"): return False
            idx = 0; enf = liste.get_first_child()
            while enf:
                ok, r = enf.compute_bounds(liste)
                if ok and y > r.get_y() + r.get_height() / 2: idx += 1
                enf = enf.get_next_sibling()
            # index parmi les cartes non archivées → index réel
            reel = [i for i, k in enumerate(c["cartes"]) if not k.get("archive")]
            pos = reel[idx] if idx < len(reel) else len(c["cartes"])
            self.d.deplacer_carte(val[6:], c["id"], pos); GLib.idle_add(lambda: (self.rafraichir("organiser", "bord"), False)[1]); return True
        dt.connect("drop", depot)
        dt.connect("enter", lambda *_a: (col.add_css_class("studio-depot"), Gdk.DragAction.MOVE)[1]); dt.connect("leave", lambda *_a: col.remove_css_class("studio-depot"))
        col.add_controller(dt)
        e = entree(ph="+ Ajouter une carte")
        def ajout(*_):
            if e.get_text().strip():
                c["cartes"].append({"id": nid(), "titre": e.get_text().strip(), "type": "simple", "checklist": [], "etiquettes": [], "personnes": [], "commentaires": [], "cree": time.time()})
                self.d.ecrire("organiser"); self.rafraichir("organiser", "bord")
        e.connect("activate", ajout); col.append(e)
        return col

    def carte(self, k):
        b = boite(True, 6, "studio-carte")
        if k.get("etiquettes"):
            et = boite(False, 4)
            for n in k["etiquettes"]:
                x = Gtk.Box(); x.add_css_class("studio-etiq"); colorer(x, dict(ETIQUETTES).get(n, "#888")); et.append(x)
            b.append(et)
        if k.get("type", "simple") != "simple":
            tn = dict((a, (n, i)) for a, n, i in TYPES_CARTE)[k["type"]]
            r = boite(False, 6); r.append(ico(tn[1], 13, "c")); r.append(label(tn[0], "petit", "accent")); b.append(r)
        b.append(label(k["titre"], "gras", wrap=True, xalign=0))
        extra = " · ".join(x for x in (k.get("champs", {}).get("sequence") and "Séq. %s" % k["champs"]["sequence"], k.get("champs", {}).get("plan") and "Plan %s" % k["champs"]["plan"],
                                        k.get("champs", {}).get("version"), k.get("champs", {}).get("format")) if x)
        if extra: b.append(label(extra, "petit", "attenue"))
        bas = boite(False, 8)
        d = lire_date(k.get("echeance", ""))
        if d:
            col = "#e5534b" if d < aujourdhui() and not k.get("fait") else "#d4a72c" if (d - aujourdhui()).days <= 2 else "#8b949e"
            bas.append(pastille("⏱ " + date_courte(d), col))
        if k.get("checklist"):
            f = sum(1 for x in k["checklist"] if x["ok"]); bas.append(pastille("☑ %d/%d" % (f, len(k["checklist"])), "#57ab5a" if f == len(k["checklist"]) else "#8b949e"))
        if k.get("commentaires"): bas.append(pastille("💬 %d" % len(k["commentaires"]), "#8b949e"))
        if k.get("statut_valid"): bas.append(pastille(k["statut_valid"], {"Validé": "#57ab5a", "Retours": "#e5534b"}.get(k["statut_valid"], "#d4a72c")))
        sp = Gtk.Box(hexpand=True); bas.append(sp)
        for p in k.get("personnes", [])[:3]:
            l = label(initiales(p), "studio-pastille"); l.set_tooltip_text(p); colorer(l, "#f0b378", .3); bas.append(l)
        if bas.get_first_child(): b.append(bas)
        g = Gtk.GestureClick(); g.connect("released", lambda gg, n, x, y, cid=k["id"]: self.editer_carte(cid, gg.get_widget())); b.add_controller(g)
        ds = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        ds.connect("prepare", lambda *_a, cid=k["id"]: Gdk.ContentProvider.new_for_value("carte:" + cid)); b.add_controller(ds)
        return b

    def bouger_colonne(self, t, c, sens):
        i = t["colonnes"].index(c); j = i + sens
        if 0 <= j < len(t["colonnes"]): t["colonnes"][i], t["colonnes"][j] = t["colonnes"][j], t["colonnes"][i]; self.d.ecrire("organiser"); self.remplir("organiser")

    def supprimer_colonne(self, t, c):
        if c["cartes"]:      # les cartes ne sont pas perdues : elles passent dans la première colonne restante
            reste = [x for x in t["colonnes"] if x is not c]
            if not reste: return
            reste[0]["cartes"].extend(c["cartes"])
        t["colonnes"].remove(c); self.d.ecrire("organiser"); self.rafraichir("organiser", "bord")

    def supprimer_tableau(self, t):
        d = self.d.tableaux()
        if len(d["tableaux"]) <= 1: return
        d["tableaux"].remove(t); d["actif"] = d["tableaux"][0]["id"]; self.d.ecrire("organiser"); self.rafraichir("organiser", "bord")

    def renommer(self, ancre, actuel, rappel):
        pop = Gtk.Popover(); pop.set_parent(ancre); e = entree(actuel, largeur=26)
        e.connect("activate", lambda *_: (pop.popdown(), rappel(e.get_text().strip()) if e.get_text().strip() else None)); pop.set_child(e); pop.popup(); e.grab_focus()

    def archives(self, ancre, t):
        A = [(c, k) for c in t["colonnes"] for k in c["cartes"] if k.get("archive")]
        if not A: popover_menu(ancre, [("archive", "Aucune carte archivée", lambda: None)]); return
        popover_menu(ancre, [("archive-restore" if True else "archive", "Restaurer « %s »" % k["titre"][:30], (lambda k=k: (k.pop("archive", None), self.d.ecrire("organiser"), self.remplir("organiser")))) for c, k in A])

    def editer_carte(self, cid, ancre):
        t, c, i, k = self.d.trouver_carte(cid)
        if not k: return
        w = fenetre(ancre or self.conteneurs.get("organiser"), "Carte — " + k["titre"], 620, 760)
        v = boite(True, 10, margin_top=18, margin_bottom=18, margin_start=20, margin_end=20)
        sc = Gtk.ScrolledWindow(vexpand=True); sc.set_child(v); w.set_child(sc)
        e_t = entree(k["titre"]); e_t.add_css_class("titre-carte"); v.append(e_t)
        v.append(label("dans « %s » · %s" % (c["nom"], t["nom"]), "petit", "attenue"))
        # type de carte (audiovisuel)
        r = boite(False, 6)
        for a, n, ic in TYPES_CARTE:
            tb = Gtk.ToggleButton(active=k.get("type", "simple") == a); bx = boite(False, 6); bx.append(ico(ic, 14)); bx.append(label(n, "petit")); tb.set_child(bx)
            tb.connect("toggled", lambda b, a=a: b.get_active() and (k.__setitem__("type", a), sauver(), w.close(), self.editer_carte(cid, ancre))); r.append(tb)
        v.append(r)
        champs = {}
        if k.get("type") in CHAMPS_TYPE:
            g = Gtk.Grid(column_spacing=8, row_spacing=6)
            for n, (cle, lib) in enumerate(CHAMPS_TYPE[k["type"]]):
                g.attach(label(lib, "petit", "attenue"), (n % 2) * 2, n // 2, 1, 1)
                e = entree(k.get("champs", {}).get(cle, ""), largeur=16); champs[cle] = e; g.attach(e, (n % 2) * 2 + 1, n // 2, 1, 1)
            v.append(g)
            if k["type"] == "validation":
                dd = Gtk.DropDown.new_from_strings(STATUT_VALID); dd.set_selected(STATUT_VALID.index(k.get("statut_valid", "En attente")) if k.get("statut_valid") in STATUT_VALID else 0)
                dd.connect("notify::selected", lambda d_, _p: k.__setitem__("statut_valid", STATUT_VALID[d_.get_selected()])); v.append(dd)
        # étiquettes
        v.append(label("Étiquettes", "gras"))
        et = boite(False, 6)
        for n, col in ETIQUETTES:
            tb = Gtk.ToggleButton(active=n in k.get("etiquettes", [])); x = Gtk.Box(); x.set_size_request(36, 14); colorer(x, col); tb.set_child(x); tb.set_tooltip_text(n)
            tb.connect("toggled", lambda b, n=n: k.__setitem__("etiquettes", [y for y in k.get("etiquettes", []) if y != n] + ([n] if b.get_active() else []))); et.append(tb)
        v.append(et)
        g = Gtk.Grid(column_spacing=10, row_spacing=6)
        g.attach(label("Échéance", "gras"), 0, 0, 1, 1); e_d = entree(lire_date(k.get("echeance", "")).strftime("%d/%m/%Y") if lire_date(k.get("echeance", "")) else "", "jj/mm/aaaa ou « demain »", 14); g.attach(e_d, 1, 0, 1, 1)
        g.attach(label("Personnes", "gras"), 0, 1, 1, 1); e_p = entree(", ".join(k.get("personnes", [])), "Prénom Nom, Prénom Nom…", 30); g.attach(e_p, 1, 1, 1, 1)
        v.append(g)
        v.append(label("Description", "gras"))
        tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=8, bottom_margin=8, left_margin=8, right_margin=8); tv.get_buffer().set_text(k.get("desc", ""))
        fr = Gtk.Frame(); fr.set_child(tv); fr.set_size_request(-1, 110); v.append(fr)
        # liste à cocher
        v.append(label("Liste à cocher", "gras")); lc = boite(True, 4); v.append(lc)
        def remplir_lc():
            vider(lc)
            for x in k.setdefault("checklist", []):
                rr = boite(False, 6); cb = Gtk.CheckButton(label=x["t"], active=x["ok"], hexpand=True)
                cb.connect("toggled", lambda b, x=x: x.__setitem__("ok", b.get_active())); rr.append(cb)
                rr.append(bouton(None, "x", "plat", taille=12, role="d", rappel=lambda x=x: (k["checklist"].remove(x), remplir_lc()))); lc.append(rr)
            e = entree(ph="+ Ajouter un élément"); e.connect("activate", lambda e: (k["checklist"].append({"t": e.get_text().strip(), "ok": False}), remplir_lc()) if e.get_text().strip() else None); lc.append(e)
        remplir_lc()
        # commentaires
        v.append(label("Commentaires", "gras")); cm = boite(True, 4); v.append(cm)
        for x in k.get("commentaires", []): cm.append(label("%s — %s" % (x["date"], x["texte"]), "petit", wrap=True))
        e_c = entree(ph="Écrire un commentaire et Entrée"); e_c.connect("activate", lambda e: (k.setdefault("commentaires", []).append({"date": time.strftime("%d/%m %H:%M"), "texte": e.get_text().strip()}), cm.append(label("%s — %s" % (time.strftime("%d/%m %H:%M"), e.get_text().strip()), "petit", wrap=True)), e.set_text("")) if e.get_text().strip() else None)
        v.append(e_c)
        def sauver():
            k["titre"] = e_t.get_text().strip() or k["titre"]; k["echeance"] = saisie_date(e_d.get_text())
            k["personnes"] = [p.strip() for p in e_p.get_text().split(",") if p.strip()]
            b_ = tv.get_buffer(); k["desc"] = b_.get_text(b_.get_start_iter(), b_.get_end_iter(), False)
            if champs: k["champs"] = {c_: e.get_text().strip() for c_, e in champs.items()}
            self.d.ecrire("organiser")
        bas = boite(False, 8, margin_top=8)
        bas.append(bouton("Archiver", "archive", "fantome", rappel=lambda: (sauver(), k.__setitem__("archive", True), self.d.ecrire("organiser"), w.close())))
        bas.append(bouton("Supprimer", "trash-2", "plat", rappel=lambda: (c["cartes"].remove(k), self.d.ecrire("organiser"), w.close())))
        bas.append(Gtk.Box(hexpand=True))
        bas.append(bouton("Enregistrer", "check", "pilule", rappel=lambda: (sauver(), w.close())))
        v.append(bas)
        w.connect("close-request", lambda *_: (sauver() if k in c["cartes"] or k.get("archive") else None, GLib.idle_add(lambda: (self.rafraichir("organiser", "bord"), False)[1]), False)[2])
        w.present()

    # ---------------------------------------------------------------- tâches
    def p_taches(self, v):
        self.entete(v, "Tâches", "Priorité, statut, échéance. Clic sur le statut pour le faire avancer.")
        aj = boite(False, 8)
        e = entree(ph="Nouvelle tâche…"); e.set_hexpand(True)
        pr = Gtk.DropDown.new_from_strings([n for _k, n, _c in PRIOS]); pr.set_selected(1)
        dt = entree(ph="échéance (jj/mm, demain…)", largeur=18)
        def ajout(*_):
            if not e.get_text().strip(): return
            self.d.taches().append({"id": nid(), "titre": e.get_text().strip(), "priorite": PRIOS[pr.get_selected()][0], "statut": "a_faire", "echeance": saisie_date(dt.get_text()), "cree": time.time()})
            self.d.ecrire("taches"); self.rafraichir("taches", "bord")
        e.connect("activate", ajout); dt.connect("activate", ajout)
        aj.append(e); aj.append(pr); aj.append(dt); aj.append(bouton("Ajouter", "plus", "pilule", rappel=ajout)); v.append(aj)
        onglets = boite(False, 6)
        for k, n in (("aujourdhui", "Aujourd'hui"), ("semaine", "Cette semaine"), ("mois", "Ce mois"), ("calendrier", "Semaine en calendrier"), ("terminees", "Terminées"), ("toutes", "Toutes")):
            b = Gtk.ToggleButton(label=n, active=self.vue_taches == k); b.connect("toggled", lambda b, k=k: b.get_active() and (setattr(self, "vue_taches", k), GLib.idle_add(lambda: (self.remplir("taches"), False)[1])))
            onglets.append(b)
        v.append(onglets)
        T = self.d.taches(); a = aujourdhui()
        if self.vue_taches == "calendrier":
            lundi = a - datetime.timedelta(days=a.weekday())
            g = boite(False, 8, homogeneous=True)
            for j in range(7):
                dj = lundi + datetime.timedelta(days=j); col = boite(True, 6, "studio-jour")
                if dj == a: col.add_css_class("aujourdhui")
                col.append(label("%s %d" % (JOURS[j], dj.day), "gras" if dj == a else "attenue"))
                for t in [t for t in T if t.get("echeance") == dj.isoformat()]: col.append(self.ligne_tache(t, compacte=True))
                g.append(col)
            v.append(g); return
        def garde(t):
            d = lire_date(t.get("echeance", ""))
            if self.vue_taches == "terminees": return t.get("statut") == "fait"
            if self.vue_taches == "toutes": return True
            if t.get("statut") == "fait": return False
            if self.vue_taches == "aujourdhui": return d is not None and d <= a
            if self.vue_taches == "semaine": return d is None or d <= a + datetime.timedelta(days=7)
            if self.vue_taches == "mois": return d is None or (d.year, d.month) <= (a.year, a.month)
            return True
        L = sorted([t for t in T if garde(t)], key=lambda t: (t.get("statut") == "fait", t.get("echeance") or "9999", ["haute", "moyenne", "basse"].index(t.get("priorite", "moyenne"))))
        if not L: v.append(label("Aucune tâche ici.", "attenue"))
        for t in L: v.append(self.ligne_tache(t))

    def ligne_tache(self, t, compacte=False):
        r = boite(False, 8, "studio-carte" if not compacte else "")
        if t.get("statut") == "fait": r.add_css_class("studio-fait")
        cb = Gtk.CheckButton(active=t.get("statut") == "fait")
        cb.connect("toggled", lambda b, t=t: (t.__setitem__("statut", "fait" if b.get_active() else "a_faire"), self.d.ecrire("taches"), GLib.idle_add(lambda: (self.rafraichir("taches", "bord"), False)[1])))
        r.append(cb); r.append(label(t["titre"], hexpand=True, ellipsize=True, xalign=0))
        if not compacte:
            p = dict((k, (n, c)) for k, n, c in PRIOS)[t.get("priorite", "moyenne")]; r.append(pastille(p[0], p[1]))
            s = dict((k, (n, c)) for k, n, c in STATUTS)[t.get("statut", "a_faire")]
            sb = Gtk.Button(); sb.add_css_class("plat"); sb.set_child(pastille(s[0], s[1])); sb.set_tooltip_text("Faire avancer le statut")
            def avance(*_a, t=t):
                ordre = [k for k, _n, _c in STATUTS]; t["statut"] = ordre[(ordre.index(t.get("statut", "a_faire")) + 1) % len(ordre)]; self.d.ecrire("taches"); self.rafraichir("taches", "bord")
            sb.connect("clicked", avance); r.append(sb)
        d = lire_date(t.get("echeance", ""))
        if d: r.append(pastille(date_courte(d), "#e5534b" if d < aujourdhui() and t.get("statut") != "fait" else "#8b949e"))
        if not compacte:
            r.append(bouton(None, "trash-2", "plat", taille=14, role="d", tip="Supprimer", rappel=lambda t=t: (self.d.taches().remove(t), self.d.ecrire("taches"), self.rafraichir("taches", "bord"))))
        return r

    # ---------------------------------------------------------------- mémos (pense-bêtes)
    def p_memos(self, v):
        self.entete(v, "Mémos", "Notes rapides en cartes de couleur. Épinglez les plus importantes : elles restent en haut et sur le tableau de bord.")
        h = boite(False, 8)
        s = Gtk.SearchEntry(placeholder_text="Rechercher dans les mémos…", hexpand=True); s.set_text(self.recherche_memos)
        h.append(s); h.append(bouton("Nouveau mémo", "plus", "pilule", rappel=lambda: self.editer_memo(None, h)))
        h.append(bouton("Nouvelle liste", "list-checks", "fantome", rappel=lambda: self.editer_memo(None, h, liste=True))); v.append(h)
        zone = boite(True, 10); v.append(zone)
        def remplir_z():
            vider(zone); q = s.get_text().strip().lower(); self.recherche_memos = s.get_text()
            M = [m for m in self.d.memos() if not q or q in (m.get("titre", "") + " " + m.get("texte", "") + " " + " ".join(x["t"] for x in m.get("liste", [])) + " " + " ".join(m.get("etiquettes", []))).lower()]
            for titre, L in (("Épinglés", [m for m in M if m.get("epingle")]), ("Autres", [m for m in M if not m.get("epingle")])):
                if not L: continue
                if any(m.get("epingle") for m in M): zone.append(label(titre, "section"))
                fl = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=5, min_children_per_line=2, column_spacing=12, row_spacing=12, valign=Gtk.Align.START)
                for m in sorted(L, key=lambda m: -m.get("modif", 0)): fl.append(self.carte_memo(m))
                zone.append(fl)
            if not M: zone.append(label("Aucun mémo. « Nouveau mémo » pour commencer.", "attenue"))
        s.connect("search-changed", lambda *_: remplir_z()); remplir_z()

    def carte_memo(self, m, petite=False):
        b = boite(True, 6, "studio-memo"); colorer(b, dict(COUL_MEMOS).get(m.get("couleur", "defaut")), .95)
        if not petite: b.set_size_request(220, -1)
        h = boite(False, 6)
        if m.get("titre"): h.append(label(m["titre"], "gras", hexpand=True, wrap=True, xalign=0))
        else: h.append(Gtk.Box(hexpand=True))
        if not petite:
            pb = bouton(None, "pin-off" if m.get("epingle") else "pin", "plat", taille=14, role="c" if m.get("epingle") else "d", tip="Épingler")
            pb.connect("clicked", lambda *_a, m=m: (m.__setitem__("epingle", not m.get("epingle")), self.d.ecrire("memos"), self.rafraichir("memos", "bord"))); h.append(pb)
        b.append(h)
        if m.get("texte"): b.append(label(m["texte"][:400 if not petite else 120], wrap=True, xalign=0))
        for x in m.get("liste", [])[:12 if not petite else 4]:
            cb = Gtk.CheckButton(label=x["t"], active=x["ok"]); cb.connect("toggled", lambda w, x=x: (x.__setitem__("ok", w.get_active()), self.d.ecrire("memos"))); b.append(cb)
        if m.get("etiquettes") and not petite:
            r = boite(False, 4)
            for n in m["etiquettes"]: r.append(pastille("#" + n, "#f0b378"))
            b.append(r)
        def clic(gg, n, x, y, m=m):
            pk = gg.get_widget().pick(x, y, Gtk.PickFlags.DEFAULT)
            if pk and (isinstance(pk, Gtk.CheckButton) or pk.get_ancestor(Gtk.CheckButton) or isinstance(pk, Gtk.Button) or pk.get_ancestor(Gtk.Button)): return
            self.editer_memo(m, gg.get_widget())
        g = Gtk.GestureClick(); g.connect("released", clic)
        b.add_controller(g)
        return b

    def editer_memo(self, m, ancre, liste=False):
        nouveau = m is None
        if nouveau: m = {"id": nid(), "titre": "", "texte": "", "liste": [{"t": "", "ok": False}] if liste else [], "couleur": "defaut", "epingle": False, "etiquettes": []}
        w = fenetre(ancre, "Mémo", 460, 520)
        v = boite(True, 8, margin_top=16, margin_bottom=16, margin_start=16, margin_end=16); colorer(v, dict(COUL_MEMOS).get(m.get("couleur", "defaut")), .5)
        e_t = entree(m.get("titre", ""), "Titre"); v.append(e_t)
        tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=6, left_margin=6, right_margin=6); tv.get_buffer().set_text(m.get("texte", ""))
        sc = Gtk.ScrolledWindow(vexpand=True, min_content_height=120); sc.set_child(tv); v.append(sc)
        lc = boite(True, 4); v.append(lc)
        def remplir_lc():
            vider(lc)
            for x in m["liste"]:
                rr = boite(False, 6); cb = Gtk.CheckButton(active=x["ok"]); cb.connect("toggled", lambda b, x=x: x.__setitem__("ok", b.get_active())); rr.append(cb)
                e = entree(x["t"]); e.set_hexpand(True); e.connect("changed", lambda e, x=x: x.__setitem__("t", e.get_text())); rr.append(e)
                rr.append(bouton(None, "x", "plat", taille=12, role="d", rappel=lambda x=x: (m["liste"].remove(x), remplir_lc()))); lc.append(rr)
            lc.append(bouton("Ajouter une case", "list-plus", "plat", rappel=lambda: (m["liste"].append({"t": "", "ok": False}), remplir_lc())))
        remplir_lc()
        e_e = entree(" ".join("#" + x for x in m.get("etiquettes", [])), "#étiquettes (ex. #devis #tournage)"); v.append(e_e)
        cr = boite(False, 6)
        for n, col in COUL_MEMOS:
            tb = Gtk.ToggleButton(active=m.get("couleur", "defaut") == n); x = Gtk.Box(); x.set_size_request(22, 22); colorer(x, col or "#2a2622"); tb.set_child(x); tb.set_tooltip_text(n)
            tb.connect("toggled", lambda b, n=n: b.get_active() and (m.__setitem__("couleur", n), colorer(v, dict(COUL_MEMOS).get(n), .5))); cr.append(tb)
        v.append(cr)
        bas = boite(False, 8)
        if not nouveau: bas.append(bouton("Supprimer", "trash-2", "plat", rappel=lambda: (self.d.memos().remove(m), self.d.ecrire("memos"), setattr(w, "_suppr", True), w.close())))
        bas.append(Gtk.Box(hexpand=True)); bas.append(bouton("Fermer", "check", "pilule", rappel=lambda: w.close())); v.append(bas)
        def fin(*_):
            if getattr(w, "_suppr", False): self.rafraichir("memos", "bord"); return False
            b_ = tv.get_buffer(); m["titre"] = e_t.get_text().strip(); m["texte"] = b_.get_text(b_.get_start_iter(), b_.get_end_iter(), False).strip()
            m["liste"] = [x for x in m["liste"] if x["t"].strip()]; m["etiquettes"] = [x.lstrip("#") for x in e_e.get_text().split() if x.strip("#")]
            m["modif"] = time.time()
            if m["titre"] or m["texte"] or m["liste"]:
                if nouveau: self.d.memos().append(m)
                self.d.ecrire("memos")
            elif not nouveau: self.d.memos().remove(m); self.d.ecrire("memos")
            GLib.idle_add(lambda: (self.rafraichir("memos", "bord"), False)[1]); return False
        w.connect("close-request", fin); w.set_child(v); w.present(); (e_t if not liste else lc).grab_focus()

    # ---------------------------------------------------------------- objectifs
    def p_objectifs(self, v):
        self.entete(v, "Objectifs", "Ce que vous visez cette semaine, ce mois-ci et cette année. Cochez au fil de l'eau.")
        O = self.d.objectifs(); g = boite(False, 14, homogeneous=True)
        for k, n in (("semaine", "Cette semaine"), ("mois", "Ce mois-ci"), ("annee", "Cette année")):
            col = boite(True, 6, "studio-bloc", valign=Gtk.Align.START); col.append(titre_bloc("trophy", n))
            L = O.setdefault(k, [])
            for x in L:
                r = boite(False, 6); cb = Gtk.CheckButton(label=x["t"], active=x["ok"], hexpand=True)
                if x["ok"]: cb.add_css_class("studio-fait")
                cb.connect("toggled", lambda b, x=x: (x.__setitem__("ok", b.get_active()), self.d.ecrire("objectifs"), GLib.idle_add(lambda: (self.rafraichir("objectifs", "bord"), False)[1])))
                r.append(cb); r.append(bouton(None, "x", "plat", taille=12, role="d", rappel=lambda L=L, x=x: (L.remove(x), self.d.ecrire("objectifs"), self.rafraichir("objectifs", "bord")))); col.append(r)
            e = entree(ph="+ Ajouter")
            e.connect("activate", lambda e, L=L: (L.append({"t": e.get_text().strip(), "ok": False}), self.d.ecrire("objectifs"), self.rafraichir("objectifs", "bord")) if e.get_text().strip() else None)
            col.append(e)
            if L:
                f = sum(1 for x in L if x["ok"]); pb = Gtk.ProgressBar(fraction=f / len(L)); pb.add_css_class("studio-progres"); col.append(pb)
            g.append(col)
        v.append(g)


# ====================================================================================== application (mode Classique)
def main():
    page = "memos" if sys.argv[0].endswith("memos") or "--memos" in sys.argv else (sys.argv[sys.argv.index("--page") + 1] if "--page" in sys.argv else "bord")
    if "--test" in sys.argv: sys.exit(0 if test() else 1)
    app = Gtk.Application(application_id="fr.xiii.studio" + (".memos" if page == "memos" else ""), flags=Gio.ApplicationFlags.NON_UNIQUE)
    def activer(app):
        from .appli import preparer, Volet
        preparer()
        w = Gtk.ApplicationWindow(application=app, title="Mémos XIII" if page == "memos" else "Studio XIII", default_width=1280, default_height=820)
        vol = Volet("Mémos" if page == "memos" else "Studio", "Projet : %s" % (config.charger().get("projet_actif") or "général"))
        st = Studio(ouvrir_page=lambda k: vol.aller(k))
        for k, ic, n in Studio.PAGES: vol.ajouter(k, ic, n, rappel=lambda k=k: vol.pile.get_child_by_name(k) or vol.pile.add_named(st.page(k), k))
        vol.aller(page); w.set_child(vol.racine); w.present()
    app.connect("activate", activer)
    sys.exit(app.run([]))


def test():
    """Vérification sans écran : tableaux, cartes, déplacement, tâches, mémos, objectifs, relecture du disque."""
    import tempfile
    os.environ["HOME"] = tempfile.mkdtemp()
    d = Donnees("Concert"); t = d.nouveau_tableau("postprod")
    a, b = t["colonnes"][0], t["colonnes"][1]
    a["cartes"] += [{"id": "k1", "titre": "Dérusher la cam A", "checklist": [{"t": "copie", "ok": True}], "type": "plan", "champs": {"sequence": "3"}},
                    {"id": "k2", "titre": "Synchro son", "checklist": []}]
    d.ecrire("organiser"); d.deplacer_carte("k1", b["id"], 0)
    d.taches().append({"id": "t1", "titre": "Appeler la régie", "priorite": "haute", "statut": "a_faire", "echeance": saisie_date("demain")}); d.ecrire("taches")
    d.memos().append({"id": "m1", "titre": "Codes Wi-Fi", "texte": "plateau : xiii", "liste": [], "epingle": True}); d.ecrire("memos")
    d.objectifs()["semaine"].append({"t": "Livrer la V1", "ok": False}); d.ecrire("objectifs")
    d2 = Donnees("Concert"); t2 = d2.tableau_actif()
    ok = (t2["colonnes"][1]["cartes"][0]["id"] == "k1" and len(t2["colonnes"][0]["cartes"]) == 1 and d2.taches()[0]["echeance"] == (aujourdhui() + datetime.timedelta(days=1)).isoformat()
          and d2.memos()[0]["epingle"] and d2.objectifs()["semaine"][0]["t"] == "Livrer la V1" and os.path.isdir(os.path.expanduser("~/XIII/Concert/.studio")))
    print(("OK        " if ok else "ÉCHEC     ") + "Studio XIII : %d tableau(x), carte déplacée de « %s » vers « %s », tâche pour demain, mémo épinglé, objectif — relus du disque"
          % (len(d2.tableaux()["tableaux"]), a["nom"], b["nom"]))
    return ok
