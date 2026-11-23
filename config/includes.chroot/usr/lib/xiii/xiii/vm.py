# OS XIII — Windows XIII (machine virtuelle) : pour les logiciels qui ne passent pas sous Wine (vMix, logiciels avec pilotes,
# protections…), un Windows 11 complet dans une fenêtre, créé en un clic avec Quickemu : image officielle téléchargée chez
# Microsoft, pilotes virtio, TPM et démarrage sécurisé, dossier ~/XIII partagé avec Windows.
# Application développée par Matthieu Lamotte.
import os, sys, re, glob, subprocess, shutil, threading
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from . import systeme as S
from .ui import *
from .appli import preparer, page

DOSSIER = os.path.expanduser("~/Machines virtuelles")
PAQUETS = "qemu-system-x86 qemu-utils ovmf swtpm swtpm-tools spice-client-gtk socat"


def verifier():
    d = {"virt": False, "kvm": False, "ram_go": 0, "libre_go": 0, "quickemu": bool(shutil.which("quickemu") and shutil.which("quickget")), "conseils": []}
    if S.DEMO: return dict(d, virt=True, kvm=True, ram_go=15.6, libre_go=210, quickemu=False)
    try: d["virt"] = bool(re.search(r"\b(vmx|svm)\b", open("/proc/cpuinfo").read()))
    except Exception: pass
    d["kvm"] = os.access("/dev/kvm", os.R_OK | os.W_OK)
    try: d["ram_go"] = round(int(open("/proc/meminfo").read().split()[1]) / 1048576, 1)
    except Exception: pass
    os.makedirs(DOSSIER, exist_ok=True); st = os.statvfs(DOSSIER); d["libre_go"] = round(st.f_bavail * st.f_frsize / 1e9)
    if not d["virt"]: d["conseils"].append("Le processeur n'a pas la virtualisation (VT-x / AMD-V), ou elle est coupée dans le BIOS : activez-la (souvent « Intel Virtualization Technology » ou « SVM »).")
    elif not d["kvm"]: d["conseils"].append("La virtualisation est là mais pas accessible : installez les composants (étape 1), puis fermez la session et rouvrez-la.")
    if d["ram_go"] < 7.5: d["conseils"].append("Mémoire : %.0f Go. Windows 11 a besoin de 4 Go pour lui : il faut 8 Go au total, 16 pour être à l'aise." % d["ram_go"])
    if d["libre_go"] < 70: d["conseils"].append("Place libre : %d Go. Comptez 70 Go (Windows 11 + vos logiciels)." % d["libre_go"])
    return d


def machines():
    return sorted(glob.glob(os.path.join(DOSSIER, "*.conf")))


class VM(Gtk.Application):
    def __init__(self): super().__init__(application_id="fr.xiii.vm")

    def do_activate(self):
        if getattr(self, "win", None): self.win.present(); return
        preparer()
        self.win = Gtk.ApplicationWindow(application=self, title="Windows XIII (machine virtuelle)"); self.win.set_default_size(820, 700)
        sc, self.v = page("Windows XIII", "Un vrai Windows 11 dans une fenêtre, pour les logiciels qui ne fonctionnent pas sous Wine", "app-window")
        self.win.set_child(sc); self.win.present(); self.rendu()

    def vider_page(self):
        c = self.v.get_first_child().get_next_sibling()
        while c: n = c.get_next_sibling(); self.v.remove(c); c = n

    def rendu(self):
        self.vider_page()
        z = boite(True, 6, "carte"); self.v.append(z); z.append(Gtk.Spinner(spinning=True, halign=Gtk.Align.START))
        S.en_fond(verifier, lambda d: self.rendu_suite(z, d))

    def rendu_suite(self, z, d):
        vider(z)
        if isinstance(d, Exception): z.append(label(str(d))); return
        ok = d["virt"] and d["ram_go"] >= 3.5
        h = boite(False, 8); h.append(ico("circle-check" if ok else "circle-x", 22, "c")); h.append(label("Ordinateur compatible" if ok else "Ordinateur pas compatible", "gras")); z.append(h)
        z.append(label("Virtualisation : %s · mémoire : %.1f Go · place libre : %d Go" % ("oui" if d["virt"] else "non", d["ram_go"], d["libre_go"]), "petit"))
        for k in d["conseils"]: z.append(label("• " + k, "petit", "attenue", wrap=True))
        M = machines()
        if M:
            self.v.append(label("Vos machines", "section"))
            for f in M:
                nom = os.path.basename(f)[:-5]
                r = boite(False, 10, "reglage"); r.append(ico("app-window", 22, "c")); t = boite(True, 0, hexpand=True); t.append(label(nom.replace("-", " ").title(), "gras"))
                t.append(label("Dossier partagé avec Windows : ~/XIII (réseau › « spice-webdav » dans Windows)", "petit", "attenue")); r.append(t)
                r.append(bouton("Démarrer", "play", "pilule", rappel=lambda f=f: S.detacher(["sh", "-c", "cd %s && quickemu --vm %s --display sdl" % (shq(DOSSIER), shq(f))])))
                r.append(bouton(None, "trash-2", "plat", tip="Supprimer cette machine", rappel=lambda f=f: self.supprimer(f))); self.v.append(r)
        e = label("", "petit", "attenue", wrap=True); pb = Gtk.ProgressBar(visible=False, show_text=True)
        c1 = boite(True, 6, "carte", margin_top=8); self.v.append(c1)
        c1.append(label("1 · Composants (environ 250 Mo)", "gras"))
        c1.append(label("Quickemu, QEMU, TPM virtuel et démarrage sécurisé.", "petit", "attenue"))
        if d["quickemu"]: c1.append(label("Installés ✓", "petit", "accent"))
        else:
            def comp():
                e.set_text("Installation (mot de passe administrateur)…")
                def fond():
                    r = subprocess.run(["pkexec", "sh", "-c", "apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends %s; adduser %s kvm || true" % (PAQUETS, os.environ.get("USER", ""))], capture_output=True)
                    if r.returncode: raise RuntimeError("annulé")
                    from .store_github import installer
                    installer("quickemu-project/quickemu", lambda f, t: None)
                S.en_fond(fond, lambda r: (e.set_text(("Erreur : %s" % r) if isinstance(r, Exception) else "Installés ✓ — fermez la session et rouvrez-la si Windows refuse de démarrer."), self.rendu()))
            b1 = bouton("Installer les composants", "download", "pilule", rappel=comp); b1.set_halign(Gtk.Align.START); c1.append(b1)
        c2 = boite(True, 6, "carte", margin_top=8); self.v.append(c2)
        c2.append(label("2 · Créer Windows 11", "gras"))
        c2.append(label("Téléchargement de l'image officielle chez Microsoft (environ 6 Go), en français, puis préparation de la machine (4 Go de mémoire, 64 Go de disque). "
                        "Windows s'installe ensuite tout seul au premier démarrage. Une licence Windows est nécessaire pour l'activer.", "petit", "attenue", wrap=True))
        def creer():
            pb.set_visible(True); e.set_text("Téléchargement…")
            def fond():
                os.makedirs(DOSSIER, exist_ok=True)
                p = subprocess.Popen(["quickget", "windows", "11", "French"], cwd=DOSSIER, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for l in p.stdout:
                    m = re.search(r"(\d+(?:\.\d+)?)%", l)
                    GLib.idle_add(lambda l=l.strip(), m=m: (pb.set_fraction(float(m.group(1)) / 100) if m else pb.pulse(), pb.set_text(l[-70:]), False)[-1])
                if p.wait(): raise RuntimeError("téléchargement impossible (connexion, ou Microsoft a refusé : réessayez plus tard)")
                for f in glob.glob(os.path.join(DOSSIER, "windows-11*.conf")):
                    t = open(f).read()
                    if "public_dir" not in t: open(f, "a").write('public_dir="%s"\nram="4G"\n' % os.path.expanduser("~/XIII"))
            S.en_fond(fond, lambda r: (e.set_text(("Erreur : %s" % r) if isinstance(r, Exception) else "Windows 11 est prêt : cliquez sur « Démarrer »."), self.rendu()))
        b = bouton("Créer Windows 11", "plus", "pilule", rappel=creer); b.set_halign(Gtk.Align.START); b.set_sensitive(d["quickemu"] and d["virt"]); c2.append(b)
        self.v.append(pb); self.v.append(e)
        self.v.append(label("Conseil : essayez d'abord le double-clic sur le .exe (Wine, plus léger). La machine virtuelle sert pour ce qui refuse de fonctionner autrement. "
                            "Les cartes d'acquisition et les périphériques USB spéciaux peuvent être transmis à Windows depuis le menu de la fenêtre.", "petit", "attenue", wrap=True, margin_top=8))

    def supprimer(self, f):
        nom = os.path.basename(f)[:-5]
        def ok():
            shutil.rmtree(os.path.join(DOSSIER, nom), ignore_errors=True)
            try: os.remove(f)
            except OSError: pass
            self.rendu()
        d = Gtk.AlertDialog(message="Supprimer « %s » ?" % nom, detail="Le disque de la machine et tout ce qu'il contient seront effacés définitivement.", buttons=["Annuler", "Supprimer"], cancel_button=0, default_button=0)
        d.choose(self.win, None, lambda dd, res: ok() if dd.choose_finish(res) == 1 else None)


def shq(s): return "'" + s.replace("'", "'\\''") + "'"


def main():
    sys.exit(VM().run(sys.argv[:1]))
