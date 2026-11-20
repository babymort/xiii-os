# OS XIII — IA XIII : Claude, ChatGPT, Gemini et OpenJarvis dans un volet à droite de l'écran, avec VOTRE compte
# (vraie connexion par le site, pas d'API). La session reste ouverte d'une fois sur l'autre.
# Bouton en haut de l'écran (pastille de l'IA en cours), Super + J pour afficher / masquer.
#   xiii-ia                    afficher / masquer le volet
#   xiii-ia --demander "texte" ouvrir l'IA en cours avec ce texte (assistant de synthèse, recherche…)
# Application développée par Matthieu Lamotte.
import os, sys, json, shutil, subprocess, urllib.parse
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("WebKit", "6.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio, WebKit
from gi.repository import Gtk4LayerShell as LS
from . import config, systeme as S
from .ui import *
from .appli import preparer

from .ia_base import IAS, PAR_CLE, pastille
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
DONNEES = os.path.join(GLib.get_user_data_dir(), "xiii", "ia")
CACHE = os.path.join(GLib.get_user_cache_dir(), "xiii", "ia")

def actuelle():
    k = config.charger().get("ia", "claude")
    return k if k in PAR_CLE else "claude"

class IA(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.xiii.ia", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.vues = {}

    def do_command_line(self, cl):
        a = cl.get_arguments()[1:]
        prem = not getattr(self, "win", None)
        if prem: self.construire()
        if "--demander" in a and a.index("--demander") + 1 < len(a):
            self.demander(a[a.index("--demander") + 1]); self.win.set_visible(True); self.win.present()
        elif "--montrer" in a or prem:
            self.win.set_visible(True); self.win.present()
        else:
            self.win.set_visible(not self.win.get_visible())
            if self.win.get_visible(): self.win.present()
        return 0

    def construire(self):
        preparer(".volet-ia { background: @window_bg_color; border-left: 1px solid alpha(@accent_bg_color, .4); box-shadow: -8px 0 30px alpha(black, .35); }"
                 ".choix-ia { border-radius: 999px; padding: 2px 10px; } .choix-ia.actif { background: alpha(@accent_bg_color, .2); }")
        self.session = WebKit.NetworkSession.new(DONNEES, CACHE)
        try: self.session.get_cookie_manager().set_persistent_storage(os.path.join(DONNEES, "cookies.sqlite"), WebKit.CookiePersistentStorage.SQLITE)
        except Exception: pass
        w = Gtk.Window(application=self, title="IA XIII"); self.win = w
        LS.init_for_window(w); LS.set_namespace(w, "xiii-ia"); LS.set_layer(w, LS.Layer.TOP)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.RIGHT): LS.set_anchor(w, e, True)
        LS.set_margin(w, LS.Edge.TOP, 6); LS.set_margin(w, LS.Edge.BOTTOM, 6)
        LS.set_keyboard_mode(w, LS.KeyboardMode.ON_DEMAND)
        largeur = int(config.charger().get("ia_largeur", 480)); w.set_default_size(largeur, -1)
        v = boite(True, 0, "volet-ia"); v.set_size_request(largeur, -1)
        h = boite(False, 6, margin_start=10, margin_end=8, margin_top=8, margin_bottom=8)
        self.sel = boite(False, 2); h.append(self.sel)
        h.append(Gtk.Box(hexpand=True))
        h.append(bouton(None, "refresh-cw", "plat", taille=14, tip="Recharger", rappel=lambda: self.vue().reload() if self.vue() else None))
        h.append(bouton(None, "external-link", "plat", taille=14, tip="Ouvrir dans le navigateur", rappel=lambda: S.detacher(["xdg-open", self.vue().get_uri()]) if self.vue() else None))
        h.append(bouton(None, "chevrons-left", "plat", taille=14, tip="Plus large / plus étroit", rappel=self.elargir))
        h.append(bouton(None, "x", "plat", taille=14, tip="Masquer (Super + J)", rappel=lambda: self.win.set_visible(False)))
        v.append(h); v.append(Gtk.Separator())
        self.pile = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE); v.append(self.pile)
        w.set_child(v); self.v = v
        k = Gtk.EventControllerKey(); k.connect("key-pressed", lambda c, kv, *_: (self.win.set_visible(False), True)[1] if kv == Gdk.KEY_Escape else False); w.add_controller(k)
        self.choisir(actuelle())

    def elargir(self):
        l = 760 if self.v.get_width() < 700 else 480
        self.v.set_size_request(l, -1); self.win.set_default_size(l, -1); config.modifier(_histo=False, ia_largeur=l)

    def remplir_sel(self):
        vider(self.sel); cur = getattr(self, "cur", "claude")
        for k, nom, mono, url, q in IAS:
            b = Gtk.Button(); b.add_css_class("plat"); b.add_css_class("choix-ia"); b.set_tooltip_text(nom)
            bx = boite(False, 6); bx.append(pastille(k, 20, k == cur))
            if k == cur: b.add_css_class("actif"); bx.append(label(nom, "gras", "petit"))
            b.set_child(bx); b.connect("clicked", lambda _b, k=k: self.choisir(k)); self.sel.append(b)

    def vue(self):
        return self.vues.get(getattr(self, "cur", None))

    def choisir(self, k):
        self.cur = k; config.modifier(_histo=False, ia=k); self.remplir_sel()
        if k not in self.vues:
            _, nom, mono, url, q = PAR_CLE[k]
            if url:
                wv = WebKit.WebView(network_session=self.session); st = wv.get_settings()
                st.set_user_agent(UA); st.set_property("enable-developer-extras", False)
                for p in ("enable-media-stream", "enable-webrtc", "enable-clipboard"):
                    try: st.set_property(p, True)
                    except Exception: pass
                wv.connect("permission-request", lambda v, r: (r.allow(), True)[1])
                wv.connect("create", lambda v, act: (S.detacher(["xdg-open", act.get_request().get_uri()]), None)[1])   # fenêtres de connexion → navigateur si besoin
                wv.load_uri(url); self.vues[k] = wv; self.pile.add_named(wv, k)
            else:
                self.vues[k] = None; self.pile.add_named(self.page_openjarvis(), k)
        self.pile.set_visible_child_name(k)

    def page_openjarvis(self):
        v = boite(True, 12, margin_start=20, margin_end=20, margin_top=24, valign=Gtk.Align.START)
        v.append(pastille("openjarvis", 48)); v.append(label("OpenJarvis", "page-titre"))
        v.append(label("Assistant IA local et libre : il tourne sur ce PC (modèles Ollama), sans compte ni envoi de données. "
                       "Il demande un PC récent avec au moins 8 Go de mémoire.", "attenue", wrap=True))
        ok = shutil.which("jarvis") or os.path.exists(os.path.expanduser("~/.local/bin/jarvis"))
        if ok:
            v.append(bouton("Ouvrir OpenJarvis", "terminal", "pilule", rappel=lambda: S.detacher(["foot", "--app-id=fr.xiii.terminal", "-e", "jarvis"])))
        else:
            v.append(bouton("Installer OpenJarvis", "download", "pilule",
                            rappel=lambda: S.detacher(["foot", "--app-id=fr.xiii.terminal", "-e", "sh", "-c", "curl -fsSL https://openjarvis.ai/install.sh | bash; echo; echo 'Terminé : appuyez sur Entrée'; read x"])))
            v.append(label("L'installation (environ 3 minutes) se fait dans une fenêtre : elle installe aussi Ollama et un petit modèle.", "petit", "attenue", wrap=True))
        return v

    def demander(self, texte):
        """Ouvre l'IA en cours avec le texte : dans l'adresse si le site le permet, sinon collé dans la zone de saisie."""
        k = actuelle(); self.choisir(k); _, nom, mono, url, q = PAR_CLE[k]
        Gdk.Display.get_default().get_clipboard().set_text(texte)
        wv = self.vue()
        if not wv: return
        if q and len(texte) < 6000:
            wv.load_uri(q % urllib.parse.quote(texte)); return
        js = """(function(t){var e=document.querySelector('rich-textarea .ql-editor, div[contenteditable="true"], textarea');
                 if(!e) return false; e.focus(); if(e.tagName==='TEXTAREA'){e.value=t;e.dispatchEvent(new Event('input',{bubbles:true}));}
                 else {document.execCommand('insertText', false, t);} return true;})(%s)""" % json.dumps(texte)
        def essai(n=0):
            wv.evaluate_javascript(js, -1, None, None, None, None, None)
            return False
        GLib.timeout_add(1500, essai)
        S.detacher(["notify-send", "-a", "IA XIII", "-i", "edit-paste", "Texte prêt pour " + nom, "Il est dans la zone de saisie (sinon : Ctrl + V)."])

def main():
    os.environ.pop("LD_PRELOAD", None)     # chargé ; ne pas le transmettre au navigateur et aux applis ouvertes
    sys.exit(IA().run(sys.argv))
