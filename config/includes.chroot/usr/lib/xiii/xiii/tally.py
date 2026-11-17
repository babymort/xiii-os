# OS XIII — TALLY XIII, le tableau de bord : mélangeurs (ATEM, vMix, TriCaster), caméras en direct, QR codes pour les téléphones,
# forçage manuel, alerte quand un téléphone décroche. Continue de tourner en arrière-plan quand la fenêtre est fermée.
# Application développée par Matthieu Lamotte.
import os, sys, subprocess, shutil, time, tempfile
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
        self.d_type.connect("notify::selected", lambda *_: self.e_port.set_placeholder_text(str(T.PORTS.get(list(T.TYPES)[self.d_type.get_selected()], "—"))))
        aj.append(bouton("Ajouter", "plus", "pilule", taille=14, rappel=self.ajouter)); v.append(aj)
        v.append(info("ATEM : adresse IP du mélangeur (réglée dans ATEM Setup). vMix : IP du PC vMix (API TCP active par défaut, port 8099). "
                      "TriCaster : IP du TriCaster (API web). Plusieurs mélangeurs peuvent être suivis en même temps : le programme l'emporte."))
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
        hd.append(label(("📱 %d" % tels) if tels else "", "petit", valign=Gtk.Align.START)); v.append(hd)
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
        if typ != "simulateur" and not ip: self.e_ip.grab_focus(); return
        s = {"type": typ, "ip": ip, "actif": True}
        if self.e_port.get_text().strip().isdigit(): s["port"] = int(self.e_port.get_text())
        self.moteur.r.setdefault("sources", []).append(s); T.sauver(self.moteur.r); self.moteur.recharger_sources()
        self.e_ip.set_text(""); self.e_port.set_text("")

    def modifier_source(self, i, **kw):
        self.moteur.r["sources"][i].update(kw); T.sauver(self.moteur.r); self.moteur.recharger_sources()

    def retirer(self, i):
        del self.moteur.r["sources"][i]; T.sauver(self.moteur.r); self.moteur.recharger_sources()


def reglage_simple(ic, titre, sous, droite):
    r = boite(False, 16, "reglage"); r.append(ico(ic, 20, "c"))
    v = boite(True, 2, hexpand=True, valign=Gtk.Align.CENTER); v.append(label(titre, "reglage-titre")); v.append(label(sous, "reglage-sous", wrap=True)); r.append(v)
    droite.set_valign(Gtk.Align.CENTER); r.append(droite); return r


def info(t):
    b = boite(False, 10, "info-bulle", margin_top=6); b.append(ico("info", 16, "c")); b.append(label(t, wrap=True, hexpand=True)); return b


def main():
    sys.exit(Tally().run(sys.argv))
