# OS XIII — TALLY XIII, le tableau de bord : mélangeurs (ATEM, vMix, TriCaster), caméras en direct, QR codes pour les téléphones,
# forçage manuel, alerte quand un téléphone décroche. Continue de tourner en arrière-plan quand la fenêtre est fermée.
# Application développée par Matthieu Lamotte.
import os, sys, subprocess, shutil, time, tempfile, threading
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
from . import config, theme, systeme as S
from .ui import *
from . import tally_moteur as T

COUL = {T.PROGRAMME: "#d50000", T.PREVIEW: "#00a344", T.REPOS: None}
CSS = """
.tuile { border-radius: 16px; padding: 14px; min-width: 150px; min-height: 118px; border: 2px solid alpha(currentColor, .14); background: alpha(currentColor, .04); }
.tuile.programme { background: #d50000; border-color: #ff5252; color: #fff; }
.tuile.preview { background: #00a344; border-color: #3ddc84; color: #fff; }
.tuile-num { font-size: 34pt; font-weight: 900; }
.tuile-nom { font-weight: 700; }
.tuile-etat { font-size: 9pt; font-weight: 800; letter-spacing: .14em; }
.tuile-alerte { color: #ffd54f; font-weight: 700; }
.point-ok { color: #3ddc84; } .point-ko { color: #ff5252; }
.qr { background: #fff; border-radius: 12px; padding: 8px; }
"""


def qr_png(texte, chemin, taille=6):
    if not shutil.which("qrencode"): return None
    subprocess.run(["qrencode", "-o", chemin, "-s", str(taille), "-m", "2", "--foreground=111111", texte], capture_output=True)
    return chemin if os.path.exists(chemin) else None


class Tally(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.tally", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.moteur = None; self.win = None; self.maj_prevue = False; self.tels = {}

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.moteur = T.Moteur(self.signaler)
        if S.DEMO and not self.moteur.r.get("sources"):
            self.moteur.r["sources"] = [{"type": "simulateur", "nom": "Simulateur", "actif": True, "rythme": 3},
                                        {"type": "atem", "ip": "192.168.10.240", "actif": True, "nom": "ATEM régie"}]
            self.moteur.r["noms"] = {"1": "Large", "2": "Jardin", "3": "Steadicam", "4": "Cour"}
        try:
            self.moteur.demarrer()
        except OSError as e:
            self.erreur = "Port %s déjà utilisé : %s" % (self.moteur.r.get("port"), e)
        self.hold()  # continue en arrière-plan (les téléphones restent servis)
        q = Gio.SimpleAction.new("quitter", None); q.connect("activate", lambda *_: (self.moteur.arreter(), self.quit())); self.add_action(q)

    def do_activate(self):
        if not self.win: self.construire()
        self.win.present()
        if BOITIER: GLib.timeout_add(400, lambda: (self.boitier(), False)[1])

    def signaler(self):
        if not self.maj_prevue:
            self.maj_prevue = True; GLib.timeout_add(80, self.rafraichir)

    # ------------------------------------------------------------- fenêtre
    def construire(self):
        cfg = config.charger(); couleurs(cfg)
        css = Gtk.CssProvider(); css.load_from_string(theme.css_parametres(cfg) + CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 900)
        w = Gtk.ApplicationWindow(application=self, title="Tally XIII", default_width=1180, default_height=820); w.add_css_class("parametres"); self.win = w
        w.connect("close-request", self.fermeture)
        v = boite(True, 12, margin_top=20, margin_bottom=16, margin_start=24, margin_end=24)
        w.set_child(defilant(v))
        # en-tête : titre, adresse, QR code général
        h = boite(False, 18, "hero")
        g = boite(True, 4, hexpand=True, valign=Gtk.Align.CENTER)
        g.append(label("Tally XIII", "hero-grand"))
        g.append(label("Les cadreurs scannent le QR code avec leur téléphone, choisissent leur caméra : l'écran passe au rouge à l'antenne, au vert en preview.", "attenue", wrap=True))
        self.l_url = label("", "accent", "gras"); g.append(self.l_url)
        rb = boite(False, 8, margin_top=6)
        rb.append(bouton("Copier l'adresse", "copy", "fantome", taille=14, rappel=lambda: Gdk.Display.get_default().get_clipboard().set_text(self.moteur.url())))
        rb.append(bouton("Ouvrir ici", "external-link", "fantome", taille=14, rappel=lambda: Gio.AppInfo.launch_default_for_uri(self.moteur.url(), None)))
        rb.append(bouton("Quitter Tally", "power", "plat", taille=14, rappel=lambda: self.activate_action("quitter", None)))
        g.append(rb); h.append(g)
        self.qr = Gtk.Picture(can_shrink=False); self.qr.add_css_class("qr"); self.qr.set_valign(Gtk.Align.CENTER); h.append(self.qr)
        v.append(h)
        if getattr(self, "erreur", None): v.append(info(self.erreur))
        self.parefeu = boite(False, 0); v.append(self.parefeu); self.verifier_parefeu()
        # caméras
        t = boite(False, 10); t.append(label("Caméras", "groupe-titre", hexpand=True))
        t.append(label("Nombre :", "attenue"))
        sp = Gtk.SpinButton.new_with_range(1, 40, 1); sp.set_value(int(self.moteur.r.get("cameras", 8)))
        sp.connect("value-changed", lambda s: self.regler(cameras=int(s.get_value()))); t.append(sp); v.append(t)
        self.grille = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8, min_children_per_line=2, column_spacing=10, row_spacing=10, homogeneous=True)
        v.append(self.grille)
        v.append(label("Clic sur une caméra : la renommer, la forcer à l'antenne ou en preview, afficher son QR code.", "attenue", "petit"))
        # mélangeurs
        v.append(label("Mélangeurs", "groupe-titre"))
        self.l_sources = boite(True, 6); v.append(self.l_sources)
        aj = boite(False, 8, "reglage")
        self.d_type = Gtk.DropDown(model=Gtk.StringList.new([T.NOMS_TYPES[k] for k in T.TYPES])); aj.append(self.d_type)
        self.e_ip = Gtk.Entry(placeholder_text="Adresse IP (ex. 192.168.10.240)", hexpand=True); aj.append(self.e_ip)
        self.e_port = Gtk.Entry(placeholder_text="Port", width_chars=6); aj.append(self.e_port)
        aj.append(bouton("Ajouter", "plus", "pilule", taille=14, rappel=self.ajouter)); v.append(aj)
        self.ident = boite(False, 8, "reglage"); self.ident.append(label("Identifiants du TriCaster", "reglage-titre"))
        self.e_util = Gtk.Entry(placeholder_text="Utilisateur (ex. admin)", hexpand=True); self.ident.append(self.e_util)
        self.e_mdp = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True); self.e_mdp.set_property("placeholder-text", "Mot de passe"); self.ident.append(self.e_mdp)
        v.append(self.ident); self.ident.set_visible(False)
        def type_change(*_):
            ty = list(T.TYPES)[self.d_type.get_selected()]
            self.e_port.set_placeholder_text(str(T.PORTS.get(ty, "—"))); self.ident.set_visible(ty == "tricaster")
            self.e_ip.set_placeholder_text("127.0.0.1 si MELANGO tourne sur ce PC" if ty == "melango" else "Adresse IP (ex. 192.168.10.240)")
        self.d_type.connect("notify::selected", type_change)
        v.append(info("ATEM : adresse IP du mélangeur (réglée dans ATEM Setup). vMix : IP du PC vMix (API TCP active par défaut, port 8099). "
                      "TriCaster : IP du TriCaster (API web), avec ses identifiants s'il en demande. MELANGO XIII : NDI XIII doit tourner sur le PC de MELANGO "
                      "et « Tally sur téléphone » être activé dans MELANGO (Sorties). Plusieurs mélangeurs peuvent être suivis en même temps : le programme l'emporte."))
        # noms des caméras depuis la suite
        v.append(label("Noms des caméras", "groupe-titre"))
        f, o = T.dernier_export_cameras()
        nb = boite(False, 8, "reglage"); nb.append(ico("layout-grid", 20, "c"))
        nv = boite(True, 2, hexpand=True); nv.append(label("Reprendre les noms de SYNO ou PLANO", "reglage-titre"))
        nv.append(label(("Dernier export trouvé : " + os.path.basename(f)) if f else "Exportez la liste des sources (SYNO) ou le plan (PLANO) en .xiii.json", "reglage-sous", wrap=True)); nb.append(nv)
        if f: nb.append(bouton("Reprendre", None, "pilule", rappel=lambda f=f: self.importer_noms(f)))
        nb.append(bouton("Choisir un fichier…", None, "fantome", rappel=self.choisir_noms)); v.append(nb)
        # lampes USB
        v.append(label("Lampes USB (blink(1))", "groupe-titre"))
        self.l_lampes = boite(True, 6); v.append(self.l_lampes); self.lampes_vues = None
        GLib.timeout_add_seconds(3, self.maj_lampes); self.maj_lampes()
        # boîtiers Wi-Fi
        v.append(label("Boîtiers Wi-Fi (ESP32 / M5Stack ATOM)", "groupe-titre"))
        v.append(reglage_simple("cpu", "Programmer un boîtier", "Branchez-le en USB : programme Tally XIII installé, Wi-Fi et caméra réglés, sans terminal",
                                bouton("Programmer…", None, "pilule", rappel=self.boitier)))
        # téléphones et boîtiers
        v.append(label("Téléphones et boîtiers", "groupe-titre"))
        r = self.moteur.r
        v.append(self.ligne("smartphone", "Afficher la preview (vert)", "Sinon les téléphones ne passent qu'au rouge", r.get("preview", True), lambda on: self.regler(preview=on)))
        v.append(self.ligne("vibrate" if os.path.exists(theme.LUCIDE + "/vibrate.svg") else "bell", "Vibrer au passage à l'antenne", "Sur les téléphones qui le permettent", r.get("vibrer", True), lambda on: self.regler(vibrer=on)))
        ex = Gtk.Expander(label="Protocole pour boîtiers ESP32 / M5Stack et Bitfocus Companion")
        tv = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD); tv.get_buffer().set_text(T.AIDE.replace("/api", self.moteur.url().rstrip("/") + "/api", 3)); tv.add_css_class("journal")
        ex.set_child(tv); v.append(ex)
        v.append(label("Application développée par Matthieu Lamotte", "credit", xalign=1))
        self.rafraichir(); self.maj_qr()
        GLib.timeout_add_seconds(10, lambda: (self.maj_qr(), True)[1])

    def ligne(self, ic, titre, sous, actif, rappel):
        return reglage_simple(ic, titre, sous, interrupteur(actif, rappel))

    def fermeture(self, w):
        w.set_visible(False)
        n = Gio.Notification.new("Tally XIII continue en arrière-plan"); n.set_body("Les téléphones restent servis. Rouvrez Tally XIII depuis le menu Démarrer pour l'arrêter.")
        n.set_icon(Gio.ThemedIcon.new("xiii-tally")); self.send_notification("fond", n)
        return True

    def regler(self, **kw):
        self.moteur.r.update(kw); T.sauver(self.moteur.r); self.moteur.changement()

    def verifier_parefeu(self):
        vider(self.parefeu)
        try:
            st = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=3).stdout
        except Exception:
            return
        port = str(self.moteur.r.get("port", 8790))
        if ("active" in st or "actif" in st) and port not in st:
            r = reglage_simple("shield-alert" if os.path.exists(theme.LUCIDE + "/shield-alert.svg") else "shield", "Le pare-feu bloque les téléphones",
                               "Autoriser le port %s sur le réseau local" % port,
                               bouton("Autoriser", None, "pilule", rappel=lambda: S.en_fond(lambda: subprocess.run(["pkexec", "ufw", "allow", port + "/tcp"]).returncode, lambda _: self.verifier_parefeu())))
            self.parefeu.append(r)

    # ------------------------------------------------------------- mise à jour
    def maj_qr(self):
        url = self.moteur.url(); self.l_url.set_text(url)
        if url != getattr(self, "_url_qr", None):
            f = qr_png(url, os.path.join(tempfile.gettempdir(), "xiii-tally-qr.png"), 5)
            if f: self.qr.set_filename(f)
            self._url_qr = url

    def rafraichir(self):
        self.maj_prevue = False
        if not self.win: return False
        snap = self.moteur.instantane()
        # alerte : téléphone décroché
        for k, c in snap["cameras"].items():
            avant = self.tels.get(k, 0)
            if avant > 0 and c["telephones"] == 0:
                n = Gio.Notification.new("Caméra %s : téléphone décroché" % k)
                n.set_body((c["nom"] + " — " if c["nom"] else "") + "le tally de cette caméra n'est plus affiché.")
                n.set_priority(Gio.NotificationPriority.HIGH); n.set_icon(Gio.ThemedIcon.new("xiii-tally")); self.send_notification("tel-" + k, n)
            self.tels[k] = c["telephones"]
        vider(self.grille)
        for k, c in snap["cameras"].items():
            self.grille.append(self.tuile(int(k), c))
        vider(self.l_sources)
        if not snap["sources"]:
            self.l_sources.append(label("Aucun mélangeur : ajoutez-en un ci-dessous (ou le simulateur pour essayer).", "attenue"))
        for i, s in enumerate(self.moteur.r.get("sources", [])):
            vivant = next((x for x in snap["sources"] if x["type"] == s["type"] and x["ip"] == s.get("ip", "")), None)
            ok = vivant and vivant["connecte"]
            r = boite(False, 12, "reglage")
            r.append(label("●", "point-ok" if ok else "point-ko"))
            tt = boite(True, 2, hexpand=True)
            tt.append(label((s.get("nom") or T.NOMS_TYPES.get(s["type"], s["type"])) + ("  ·  " + s["ip"] if s.get("ip") else ""), "reglage-titre"))
            tt.append(label(vivant["message"] if vivant else ("Désactivé" if not s.get("actif", True) else "—"), "reglage-sous")); r.append(tt)
            r.append(bouton(None, "pencil", "plat", tip="Modifier", rappel=lambda i=i, r=r: self.editer_source(r, i)))
            r.append(interrupteur(s.get("actif", True), lambda on, i=i: self.modifier_source(i, actif=on)))
            r.append(bouton(None, "trash-2", "plat", tip="Retirer", rappel=lambda i=i: self.retirer(i)))
            self.l_sources.append(r)
        return False

    def tuile(self, k, c):
        etat = c["etat"]
        b = Gtk.Button(); b.add_css_class("tuile"); b.add_css_class(etat)
        v = boite(True, 2)
        hd = boite(False, 6); hd.append(label(str(k), "tuile-num", hexpand=True))
        tels = c["telephones"]
        if tels:
            t = boite(False, 3, valign=Gtk.Align.START); t.append(ico("smartphone", 13)); t.append(label(str(tels), "petit")); hd.append(t)
        v.append(hd)
        v.append(label(c["nom"] or "Caméra %d" % k, "tuile-nom", ellipsize=True))
        v.append(label({"programme": "● ANTENNE", "preview": "PREVIEW", "repos": " "}[etat], "tuile-etat"))
        if k in self.moteur.forces: v.append(label("forcé à la main", "petit"))
        elif etat == "programme" and not tels: v.append(label("aucun téléphone", "tuile-alerte", "petit"))
        b.set_child(v); b.connect("clicked", lambda *_: self.menu_camera(b, k, c))
        return b

    def menu_camera(self, parent, k, c):
        pop = Gtk.Popover(); pop.set_parent(parent)
        v = boite(True, 8, margin_top=10, margin_bottom=10, margin_start=10, margin_end=10)
        e = Gtk.Entry(text=self.moteur.r.get("noms", {}).get(str(k), "") or "", placeholder_text=c["nom"] or "Nom de la caméra %d" % k)
        def nommer(*_):
            n = dict(self.moteur.r.get("noms", {})); n[str(k)] = e.get_text().strip(); self.regler(noms=n); pop.popdown()
        e.connect("activate", nommer); v.append(e)
        r = boite(False, 6)
        for etat, txt in (("programme", "Antenne"), ("preview", "Preview"), ("repos", "Éteint"), ("auto", "Auto")):
            r.append(bouton(txt, None, "fantome", rappel=lambda etat=etat: (self.moteur.forcer(k, etat), pop.popdown())))
        v.append(r)
        url = self.moteur.url() + "?cam=%d" % k
        f = qr_png(url, os.path.join(tempfile.gettempdir(), "xiii-tally-qr-%d.png" % k), 4)
        if f:
            p = Gtk.Picture.new_for_filename(f); p.set_can_shrink(False); p.add_css_class("qr"); p.set_halign(Gtk.Align.CENTER); v.append(p)
        v.append(label("QR de la caméra %d : le téléphone l'ouvre directement" % k, "attenue", "petit", wrap=True))
        v.append(bouton("Enregistrer le nom", None, "pilule", rappel=nommer))
        pop.set_child(v); pop.connect("closed", lambda p: GLib.idle_add(p.unparent)); pop.popup()

    # ------------------------------------------------------------- mélangeurs
    def ajouter(self):
        typ = list(T.TYPES)[self.d_type.get_selected()]; ip = self.e_ip.get_text().strip()
        if typ not in ("simulateur", "melango") and not ip: self.e_ip.grab_focus(); return
        if typ == "melango" and not ip: ip = "127.0.0.1"
        s = {"type": typ, "ip": ip, "actif": True}
        if self.e_port.get_text().strip().isdigit(): s["port"] = int(self.e_port.get_text())
        if typ == "tricaster" and self.e_util.get_text().strip():
            s["utilisateur"] = self.e_util.get_text().strip(); s["mot_de_passe"] = self.e_mdp.get_text(); self.e_mdp.set_text("")
        self.moteur.r.setdefault("sources", []).append(s); T.sauver(self.moteur.r); self.moteur.recharger_sources()
        self.e_ip.set_text(""); self.e_port.set_text("")

    def modifier_source(self, i, **kw):
        self.moteur.r["sources"][i].update(kw); T.sauver(self.moteur.r); self.moteur.recharger_sources()

    def editer_source(self, parent, i):
        s = self.moteur.r["sources"][i]
        pop = Gtk.Popover(); pop.set_parent(parent)
        g = Gtk.Grid(row_spacing=6, column_spacing=8, margin_top=10, margin_bottom=10, margin_start=10, margin_end=10)
        champs = [("nom", "Nom affiché", False), ("ip", "Adresse IP", False), ("port", "Port", False)]
        if s["type"] == "tricaster": champs += [("utilisateur", "Utilisateur", False), ("mot_de_passe", "Mot de passe", True)]
        E = {}
        for n, (k, t_, secret) in enumerate(champs):
            g.attach(label(t_, "reglage-sous"), 0, n, 1, 1)
            e = Gtk.PasswordEntry(show_peek_icon=True) if secret else Gtk.Entry()
            e.set_text(str(s.get(k, "") or "")); e.set_size_request(240, -1); g.attach(e, 1, n, 1, 1); E[k] = e
        def ok():
            for k, e in E.items():
                val = e.get_text().strip() if k != "mot_de_passe" else e.get_text()
                if k == "port": val = int(val) if val.isdigit() else None
                if val in ("", None): s.pop(k, None)
                else: s[k] = val
            T.sauver(self.moteur.r); self.moteur.recharger_sources(); pop.popdown()
        g.attach(bouton("Enregistrer", None, "pilule", rappel=ok), 1, len(champs), 1, 1)
        pop.set_child(g); pop.connect("closed", lambda p: GLib.idle_add(p.unparent)); pop.popup()

    # ------------------------------------------------------------- noms, lampes, boîtiers
    def importer_noms(self, f):
        import json
        try:
            noms = T.noms_depuis_xiii(json.load(open(f, encoding="utf-8")))
        except Exception as e:
            self.notifier("Noms non repris", str(e)); return
        if not noms: self.notifier("Aucune caméra trouvée", os.path.basename(f)); return
        n = dict(self.moteur.r.get("noms", {})); n.update({str(k): v for k, v in noms.items()})
        self.regler(noms=n, cameras=max(int(self.moteur.r.get("cameras", 8)), max(noms)))
        self.notifier("%d nom(s) de caméra repris" % len(noms), ", ".join("%d : %s" % kv for kv in list(noms.items())[:6]))

    def choisir_noms(self):
        d = Gtk.FileDialog(title="Export SYNO (sources) ou PLANO (plan)")
        flt = Gtk.FileFilter(); flt.set_name("Fichiers Suite XIII"); flt.add_pattern("*.json"); fl = Gio.ListStore.new(Gtk.FileFilter); fl.append(flt); d.set_filters(fl)
        def fini(dlg, res):
            try: self.importer_noms(dlg.open_finish(res).get_path())
            except GLib.Error: pass
        d.open(self.win, None, fini)

    def notifier(self, titre, corps):
        n = Gio.Notification.new(titre); n.set_body(corps); n.set_icon(Gio.ThemedIcon.new("xiii-tally")); self.send_notification(None, n)

    def maj_lampes(self):
        if not self.win: return True
        L = T.Lampes.detecter()
        cle = [s for s, _ in L]
        if cle == self.lampes_vues: return True
        self.lampes_vues = cle; vider(self.l_lampes)
        if not L:
            self.l_lampes.append(label("Aucune lampe blink(1) branchée. Branchez-en une par caméra : elle s'allume en rouge à l'antenne, en vert en preview.", "attenue", wrap=True))
            return True
        aff = self.moteur.r.get("lampes", {}); n = int(self.moteur.r.get("cameras", 8))
        for serie, dev in L:
            r = boite(False, 12, "reglage"); r.append(ico("lightbulb", 20, "c"))
            r.append(label("blink(1) " + serie, "reglage-titre", hexpand=True))
            dd = Gtk.DropDown(model=Gtk.StringList.new(["Aucune caméra"] + ["Caméra %d" % k for k in range(1, n + 1)]))
            dd.set_selected(int(aff.get(serie, 0) or 0))
            def choix(d, _p, serie=serie):
                a = dict(self.moteur.r.get("lampes", {})); k = d.get_selected()
                if k: a[serie] = k
                else: a.pop(serie, None)
                self.regler(lampes=a)
            dd.connect("notify::selected", choix); r.append(dd)
            def tester(dev=dev):
                def f():
                    try:
                        for c in ((255, 0, 0), (0, 160, 0), (0, 0, 0)): T.Lampes.couleur(dev, *c); time.sleep(0.5)
                    except OSError as e:
                        GLib.idle_add(self.notifier, "Lampe inaccessible", "Débranchez puis rebranchez la lampe (%s)" % e)
                    self.moteur.lampes.couleurs.clear(); self.moteur.lampes.evt.set()
                threading.Thread(target=f, daemon=True).start()
            r.append(bouton("Tester", None, "fantome", rappel=tester)); self.l_lampes.append(r)
        return True

    def boitier(self):
        from .tally_boitier import Programmeur
        Programmeur(self.win, self.moteur.url().replace("http://", "").rstrip("/"))

    def retirer(self, i):
        del self.moteur.r["sources"][i]; T.sauver(self.moteur.r); self.moteur.recharger_sources()


def reglage_simple(ic, titre, sous, droite):
    r = boite(False, 16, "reglage"); r.append(ico(ic, 20, "c"))
    v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label(titre, "reglage-titre")); v.append(label(sous, "reglage-sous", wrap=True)); r.append(v)
    droite.set_valign(Gtk.Align.CENTER); r.append(droite); return r


def info(t):
    b = boite(False, 10, "info-bulle", margin_top=6); b.append(ico("info", 16, "c")); b.append(label(t, wrap=True, hexpand=True)); return b


BOITIER = False


def main():
    global BOITIER
    BOITIER = "--boitier" in sys.argv
    sys.exit(Tally().run([a for a in sys.argv if a != "--boitier"]))
