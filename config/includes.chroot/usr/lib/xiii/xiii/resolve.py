# OS XIII — Assistant DaVinci Resolve : vérifie la carte graphique, la mémoire et le processeur, installe les bons pilotes
# et dépendances, repère le fichier téléchargé chez Blackmagic (zip ou .run), l'installe et applique les correctifs connus
# sous Debian (bibliothèques glib embarquées qui font planter Resolve au démarrage).
# Application développée par Matthieu Lamotte.
import os, sys, re, glob, subprocess, shutil, threading, zipfile
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import systeme as S
from .ui import *
from .appli import preparer, page

PAGE = "https://www.blackmagicdesign.com/products/davinciresolve"
DEPENDANCES = ["libapr1t64", "libaprutil1t64", "libasound2t64", "libglib2.0-0t64", "libxcb-composite0", "libxcb-cursor0", "libxcb-damage0",
               "libxcb-xinerama0", "libxcb-xinput0", "libxcb-xkb1", "libxkbcommon-x11-0", "ocl-icd-libopencl1", "libfuse2t64", "xwayland"]


def bin_resolve():
    for p in ("/opt/resolve/bin/resolve", "/opt/resolve/bin/Resolve"):
        if os.path.exists(p): return p
    return None


def diagnostic():
    """{gpu: [(fabricant, nom)], nvidia_pilote, ram_go, avx2, libre_go, verdict, conseils: []}"""
    d = {"gpu": [], "conseils": []}
    if S.DEMO:
        return {"gpu": [("NVIDIA", "GeForce GTX 1660")], "nvidia_pilote": None, "ram_go": 15.6, "avx2": True, "libre_go": 120, "verdict": "pilote",
                "conseils": ["Installez le pilote NVIDIA (bouton ci-dessous), puis redémarrez."]}
    for l in S.out(["lspci", "-nn"]).splitlines():
        if re.search(r"VGA|3D controller|Display controller", l):
            fab = "NVIDIA" if "NVIDIA" in l else "AMD" if re.search(r"AMD|ATI|Radeon", l) else "Intel" if "Intel" in l else "?"
            d["gpu"].append((fab, re.sub(r"^.*?: ", "", l).split(" [")[0][:80]))
    d["nvidia_pilote"] = S.out(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], 8).strip() or None if shutil.which("nvidia-smi") else None
    try: d["ram_go"] = round(int(open("/proc/meminfo").read().split()[1]) / 1048576, 1)
    except Exception: d["ram_go"] = 0
    try: d["avx2"] = "avx2" in open("/proc/cpuinfo").read()
    except Exception: d["avx2"] = False
    st = os.statvfs("/opt" if os.path.exists("/opt") else "/"); d["libre_go"] = round(st.f_bavail * st.f_frsize / 1e9)
    fabs = [g[0] for g in d["gpu"]]
    if "NVIDIA" in fabs:
        d["verdict"] = "ok" if d["nvidia_pilote"] else "pilote"
        if not d["nvidia_pilote"]: d["conseils"].append("Installez le pilote NVIDIA (bouton ci-dessous), puis redémarrez : sans lui, Resolve ne démarre pas.")
    elif "AMD" in fabs:
        d["verdict"] = "limite"
        d["conseils"].append("Carte AMD : Resolve passe par OpenCL (paquet installé ici). Ça marche sur les Radeon récentes, mais moins bien que sous Windows ; les anciennes Radeon ne sont pas prises en charge.")
    else:
        d["verdict"] = "non"
        d["conseils"].append("Pas de carte NVIDIA ni AMD : sous Linux, Resolve ne fonctionne pas avec le graphique intégré Intel. Kdenlive ou Shotcut sont de bonnes alternatives.")
    if d["ram_go"] < 7.5: d["conseils"].append("Mémoire : %.0f Go. Il en faut 16 pour être à l'aise (8 au strict minimum)." % d["ram_go"]); d["verdict"] = "non" if d["ram_go"] < 3.5 else d["verdict"]
    elif d["ram_go"] < 15: d["conseils"].append("Mémoire : %.0f Go. Ça passe pour du HD ; 16 Go ou plus pour la 4K." % d["ram_go"])
    if not d["avx2"]: d["conseils"].append("Processeur sans AVX2 : les versions récentes de Resolve refusent de démarrer sur ce processeur."); d["verdict"] = "non"
    if d["libre_go"] < 8: d["conseils"].append("Place libre : %d Go. Il faut au moins 8 Go pour installer Resolve." % d["libre_go"])
    return d


def telecharges():
    """Fichiers Resolve trouvés dans Téléchargements (zip ou .run), du plus récent au plus ancien."""
    dl = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or os.path.expanduser("~/Téléchargements")
    L = glob.glob(os.path.join(dl, "DaVinci_Resolve*Linux*.zip")) + glob.glob(os.path.join(dl, "**", "DaVinci_Resolve*Linux*.run"), recursive=True)
    return sorted(L, key=os.path.getmtime, reverse=True)


def installer(fichier, progres):
    if fichier.endswith(".zip"):
        progres("Décompression…")
        dest = os.path.join(os.path.dirname(fichier), os.path.basename(fichier)[:-4])
        with zipfile.ZipFile(fichier) as z: z.extractall(dest)
        runs = glob.glob(os.path.join(dest, "*.run"))
        if not runs: raise RuntimeError("pas de fichier .run dans l'archive")
        fichier = runs[0]
    os.chmod(fichier, 0o755)
    progres("Installation de Resolve (mot de passe administrateur, quelques minutes)…")
    script = ("cd %s && SKIP_PACKAGE_CHECK=1 %s -i -y && mkdir -p /opt/resolve/libs/desactivees-xiii && "
              "for f in /opt/resolve/libs/libglib-2.0.so* /opt/resolve/libs/libgio-2.0.so* /opt/resolve/libs/libgmodule-2.0.so*; do [ -e \"$f\" ] && mv \"$f\" /opt/resolve/libs/desactivees-xiii/; done; true"
              ) % (sh_q(os.path.dirname(fichier)), sh_q(fichier))
    r = subprocess.run(["pkexec", "sh", "-c", script], capture_output=True, text=True)
    if r.returncode or not bin_resolve(): raise RuntimeError((r.stderr or r.stdout or "installation annulée").strip()[-300:])


def sh_q(s): return "'" + s.replace("'", "'\\''") + "'"


class Assistant(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.resolve")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer()
        self.win = Gtk.ApplicationWindow(application=self, title="Assistant DaVinci Resolve"); self.win.set_default_size(820, 720)
        sc, self.v = page("DaVinci Resolve", "Montage, étalonnage, effets et son — l'assistant prépare l'ordinateur et installe Resolve", "film")
        self.win.set_child(sc); self.win.present(); self.rendu()

    def etape(self, n, titre, sous=None):
        c = boite(True, 8, "carte", margin_top=6)
        h = boite(False, 10); h.append(label(str(n), "titre-astoria")); t = boite(True, 0, hexpand=True); t.append(label(titre, "gras"))
        if sous: t.append(label(sous, "petit", "attenue", wrap=True))
        h.append(t); c.append(h); self.v.append(c); return c

    def rendu(self):
        c = self.v.get_first_child().get_next_sibling()
        while c: n = c.get_next_sibling(); self.v.remove(c); c = n
        r = bin_resolve()
        if r:
            c = self.etape("✓", "DaVinci Resolve est installé", r)
            b = boite(False, 8); b.append(bouton("Ouvrir Resolve", "play", "pilule", rappel=lambda: S.detacher([r]))); c.append(b)
        c1 = self.etape(1, "Vérification de l'ordinateur"); z1 = boite(True, 4); c1.append(z1); z1.append(Gtk.Spinner(spinning=True, halign=Gtk.Align.START))
        def fin(d):
            vider(z1)
            if isinstance(d, Exception): z1.append(label(str(d), "attenue")); return
            V = {"ok": ("circle-check", "Compatible"), "pilote": ("triangle-alert", "Compatible une fois le pilote installé"), "limite": ("triangle-alert", "Compatible avec des limites"), "non": ("circle-x", "Pas compatible")}[d["verdict"]]
            h = boite(False, 8); h.append(ico(V[0], 22, "c")); h.append(label(V[1], "gras")); z1.append(h)
            for fab, nom in d["gpu"] or [("?", "carte graphique non trouvée")]: z1.append(label("Carte graphique : %s%s" % (nom, " · pilote NVIDIA %s" % d["nvidia_pilote"] if fab == "NVIDIA" and d.get("nvidia_pilote") else ""), "petit"))
            z1.append(label("Mémoire : %.1f Go · processeur %s AVX2 · place libre : %d Go" % (d["ram_go"], "avec" if d["avx2"] else "sans", d["libre_go"]), "petit"))
            for k in d["conseils"]: z1.append(label("• " + k, "petit", "attenue", wrap=True))
            self.diag = d
        S.en_fond(diagnostic, fin)
        c2 = self.etape(2, "Pilotes et composants", "Pilote NVIDIA (si besoin), OpenCL et les bibliothèques que Resolve demande sous Debian")
        e2 = label("", "petit", "attenue", wrap=True)
        def pilotes():
            d = getattr(self, "diag", {}) or {}
            P = list(DEPENDANCES)
            if any(g[0] == "NVIDIA" for g in d.get("gpu", [])): P += ["nvidia-driver", "nvidia-opencl-icd", "libcuda1", "firmware-misc-nonfree"]
            elif any(g[0] == "AMD" for g in d.get("gpu", [])): P += ["mesa-opencl-icd", "clinfo"]
            e2.set_text("Installation (mot de passe administrateur)…")
            script = ("grep -q 'non-free' /etc/apt/sources.list /etc/apt/sources.list.d/* 2>/dev/null || sed -i 's/ main$/ main contrib non-free non-free-firmware/' /etc/apt/sources.list; "
                      "apt-get update -qq; for p in %s; do DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $p || echo \"absent : $p\"; done") % " ".join(P)
            S.en_fond(lambda: subprocess.run(["pkexec", "sh", "-c", script], capture_output=True, text=True),
                      lambda r: e2.set_text(("Terminé ✓" + (" — redémarrez l'ordinateur pour activer le pilote NVIDIA." if "nvidia-driver" in P else "")) if not isinstance(r, Exception) and r.returncode == 0 else "Annulé ou impossible"))
        b = boite(False, 8); b.append(bouton("Installer les pilotes et composants", "download", "pilule", rappel=pilotes)); c2.append(b); c2.append(e2)
        c3 = self.etape(3, "Télécharger Resolve chez Blackmagic", "Gratuit (ou Studio avec votre licence). Choisissez « Linux » ; Blackmagic demande un court formulaire. Laissez le fichier dans Téléchargements.")
        z3 = label("", "petit", wrap=True)
        b = boite(False, 8); b.append(bouton("Ouvrir la page de téléchargement", "external-link", "pilule", rappel=lambda: S.detacher(["xdg-open", PAGE]))); c3.append(b); c3.append(z3)
        c4 = self.etape(4, "Installer", "L'assistant repère le fichier téléchargé tout seul")
        e4 = label("", "petit", "attenue", wrap=True); b4 = boite(False, 8); c4.append(b4); c4.append(e4)
        def guetter():
            L = telecharges()
            vider(b4)
            if L:
                f = L[0]; z3.set_text("Trouvé : " + os.path.basename(f))
                def go():
                    e4.set_text("Préparation…")
                    S.en_fond(installer, lambda r: (e4.set_text(("Erreur : %s" % r) if isinstance(r, Exception) else "Resolve est installé ✓ (dans le menu Démarrer)"), self.rendu() if not isinstance(r, Exception) else None),
                              f, lambda t: GLib.idle_add(lambda: (e4.set_text(t), False)[1]))
                b4.append(bouton("Installer " + os.path.basename(f)[:48], "download", "pilule", rappel=go))
            else:
                z3.set_text("En attente du fichier dans Téléchargements…"); b4.append(label("Le bouton apparaîtra quand le téléchargement sera fini.", "petit", "attenue"))
            return not L and self.win.get_visible()
        guetter(); GLib.timeout_add_seconds(3, guetter)
        self.v.append(label("Resolve fonctionne dans une fenêtre compatible (XWayland). Les codecs H.264 / H.265 en lecture et en rendu demandent la version Studio sous Linux ; "
                            "ENCODO XIII convertit vos rushes en DNxHR ou ProRes que la version gratuite lit sans souci.", "petit", "attenue", wrap=True, margin_top=8))


def main():
    sys.exit(Assistant().run(sys.argv[:1]))
