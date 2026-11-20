# OS XIII — mode Backup : déchargement des cartes et disques.
# Dès qu'un support est branché (mode Auto) ou sur un clic (mode Manuel) : copie vers <destination>/<nom du transfert>/<support>,
# empreinte calculée pendant la copie, relecture et vérification de chaque fichier copié, rapport texte + MHL,
# fichier BACKUPO (.xiii.json) pour la Suite XIII, progression lumineuse dans la barre des tâches.
# Application développée par Matthieu Lamotte.
import os, json, time, hashlib, threading, datetime, socket, getpass, shutil
from gi.repository import Gtk, Gio, GLib
from . import config, systeme as S
try:
    import xxhash
except ImportError:
    xxhash = None

BLOC = 8 * 1024 * 1024
TAG = {"xxh64": "xxhash64be", "md5": "md5", "sha256": "sha256"}

def hacheur(algo):
    if algo == "xxh64" and xxhash: return xxhash.xxh64()
    return hashlib.new("md5" if algo == "xxh64" else algo)

class Moteur:
    def __init__(self, shell):
        self.shell = shell; self.vue = None; self.transferts = []
        c = shell.cfg
        self.nom = c.get("backup_nom", ""); self.auto = bool(c.get("backup_auto", False)); self.algo = c.get("backup_algo", "xxh64")
        self.mon = Gio.VolumeMonitor.get()
        self.mon.connect("mount-added", self.branche)

    # ------------------------------------------------------------------ réglages
    def destination(self):
        d = self.shell.cfg.get("backup_destination") or ""
        if not d:
            pj = self.shell.cfg.get("projet_actif")
            d = os.path.join(os.path.expanduser("~/XIII"), pj, "01_Rushes") if pj else os.path.expanduser("~/Rushes")
        os.makedirs(d, exist_ok=True)
        return d

    def choisir_destination(self, apres=None):
        dlg = Gtk.FileDialog(title="Dossier de destination des rushes")
        def fini(d, res):
            try: f = d.select_folder_finish(res).get_path()
            except Exception: return
            config.modifier(backup_destination=f)
            if apres: GLib.timeout_add(300, lambda: (apres(), False)[1])
        dlg.select_folder(None, None, fini)

    def set_nom(self, n): self.nom = n; config.modifier(_histo=False, backup_nom=n)
    def set_auto(self, on): self.auto = on; config.modifier(_histo=False, backup_auto=on)
    def set_algo(self, a): self.algo = a; config.modifier(_histo=False, backup_algo=a)

    # ------------------------------------------------------------------ supports
    def supports(self):
        L = []
        for m in self.mon.get_mounts():
            r = m.get_root(); p = r.get_path() if r else None
            if not p or not p.startswith(("/media/", "/run/media/", "/mnt/")): continue
            try: st = os.statvfs(p); util = (st.f_blocks - st.f_bfree) * st.f_frsize
            except OSError: util = 0
            L.append({"nom": m.get_name(), "chemin": p, "utilise": util, "amovible": bool(m.can_eject() or m.can_unmount()), "mount": m})
        if S.DEMO and not L:
            L = [{"nom": "CARTE_A001", "chemin": "/media/demo/CARTE_A001", "utilise": 238e9, "amovible": True, "mount": None}]
        return L

    def branche(self, mon, m):
        r = m.get_root(); p = r.get_path() if r else None
        if not p or not p.startswith(("/media/", "/run/media/", "/mnt/")): return
        if self.shell.cfg.get("mode_bureau") != "backup": return
        if self.auto:
            GLib.timeout_add(1500, lambda: (self.demarrer({"nom": m.get_name(), "chemin": p, "mount": m}), False)[1])
        else:
            S.detacher(["notify-send", "-a", "Backup", "-i", "media-flash", "Support branché : " + m.get_name(), "Cliquez sur « Décharger » dans le mode Backup."])

    # ------------------------------------------------------------------ transfert
    def demarrer(self, s):
        if any(t["source"] == s["chemin"] and t["etat"] in ("copie", "verification") for t in self.transferts): return
        nom_tr = (self.nom or datetime.datetime.now().strftime("%Y-%m-%d")).strip().replace("/", "-")
        dossier = os.path.join(self.destination(), nom_tr, s["nom"].replace("/", "-"))
        i = 2; base = dossier
        while os.path.exists(dossier) and os.listdir(dossier): dossier = "%s_%d" % (base, i); i += 1
        t = {"source": s["chemin"], "nom_support": s["nom"], "dossier": dossier, "etat": "copie", "fraction": 0.0, "texte": "Préparation…",
             "algo": self.algo, "nom_transfert": nom_tr, "debut": time.time()}
        self.transferts.append(t)
        threading.Thread(target=self._copier, args=(t,), daemon=True).start()

    def _copier(self, t):
        src, dst, algo = t["source"], t["dossier"], t["algo"]
        fichiers = []
        for d, _, fs in os.walk(src):
            for f in fs:
                if f.startswith(".") or f in ("System Volume Information",): continue
                p = os.path.join(d, f)
                try: fichiers.append((p, os.path.getsize(p)))
                except OSError: pass
        total = sum(x for _, x in fichiers) * 2 or 1; fait = [0]; t0 = time.time(); lignes = []; erreurs = 0
        def avance(n, etape):
            fait[0] += n; dt = max(.1, time.time() - t0); v = fait[0] / dt; reste = (total - fait[0]) / max(1, v)
            t["fraction"] = fait[0] / total
            t["texte"] = "%s %d %% · %s/s · reste %s" % (etape, 100 * fait[0] / total, S.humain(v), "%d min %02d" % (reste // 60, reste % 60))
            if int(t["fraction"] * 100) != getattr(self, "_pc", -1):
                self._pc = int(t["fraction"] * 100); S.progres("xiii-modes.desktop", t["fraction"])
        try:
            os.makedirs(dst, exist_ok=True)
            for p, taille in fichiers:                          # 1. copie + empreinte de la source
                rel = os.path.relpath(p, src); q = os.path.join(dst, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
                h = hacheur(algo)
                with open(p, "rb") as a, open(q, "wb") as b:
                    while True:
                        x = a.read(BLOC)
                        if not x: break
                        h.update(x); b.write(x); avance(len(x), "Copie")
                    b.flush(); os.fsync(b.fileno())
                shutil.copystat(p, q, follow_symlinks=False)
                lignes.append([rel, taille, h.hexdigest(), ""])
            t["etat"] = "verification"
            for ligne in lignes:                                 # 2. relecture de la copie
                h = hacheur(algo)
                with open(os.path.join(dst, ligne[0]), "rb") as b:
                    while True:
                        x = b.read(BLOC)
                        if not x: break
                        h.update(x); avance(len(x), "Vérification")
                ligne[3] = "OK" if h.hexdigest() == ligne[2] else "DIFFÉRENT"
                if ligne[3] != "OK": erreurs += 1
            self._rapports(t, lignes)
            t["etat"] = "erreur" if erreurs else "fini"; t["fraction"] = 1
            t["texte"] = ("%d fichier(s) · %s · vérifiés ✓" % (len(lignes), S.humain(total / 2))) if not erreurs else ("%d fichier(s) différent(s) !" % erreurs)
        except Exception as e:
            t["etat"] = "erreur"; t["texte"] = "Erreur : %s" % e
        S.progres("xiii-modes.desktop", None)
        S.detacher(["notify-send", "-a", "Backup", "-i", "drive-harddisk", ("Déchargement vérifié : " if t["etat"] == "fini" else "Problème de déchargement : ") + t["nom_support"], t["texte"]])

    def _rapports(self, t, lignes):
        now = datetime.datetime.now().isoformat(timespec="seconds"); d = t["dossier"]; nom = "backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        with open(os.path.join(d, nom + ".mhl"), "w") as m:
            m.write('<?xml version="1.0" encoding="UTF-8"?>\n<hashlist version="1.1">\n  <creatorinfo><name>%s</name><hostname>%s</hostname><tool>OS XIII Backup</tool><startdate>%s</startdate></creatorinfo>\n'
                    % (getpass.getuser(), socket.gethostname(), now))
            for rel, taille, h, st in lignes:
                m.write('  <hash><file>%s</file><size>%d</size><%s>%s</%s><hashdate>%s</hashdate></hash>\n' % (rel.replace("&", "&amp;").replace("<", "&lt;"), taille, TAG[t["algo"]], h, TAG[t["algo"]], now))
            m.write("</hashlist>\n")
        with open(os.path.join(d, nom + ".txt"), "w") as r:
            r.write("OS XIII — déchargement\nTransfert : %s\nSupport : %s\nSource : %s\nCopie : %s\nAlgorithme : %s\nDate : %s\n\n" % (t["nom_transfert"], t["nom_support"], t["source"], d, t["algo"], now))
            for rel, taille, h, st in lignes: r.write("%s\t%d\t%s\t%s\n" % (h, taille, st, rel))
        # fichier pour BACKUPO XIII (Suite) : liste des rushes avec noms, tailles et empreintes
        lien = {"format": "xiii-link", "kind": "backupo", "source": "OS XIII", "version": 1,
                "data": {"titre": "%s — %s" % (t["nom_transfert"], t["nom_support"]), "transfert": t["nom_transfert"], "support": t["nom_support"],
                         "destination": d, "algo": t["algo"], "date": now, "projet": self.shell.cfg.get("projet_actif", ""),
                         "fichiers": [{"nom": rel, "taille": taille, "empreinte": h, "statut": st} for rel, taille, h, st in lignes]}}
        json.dump(lien, open(os.path.join(d, nom + ".xiii.json"), "w"), ensure_ascii=False, indent=1)
        pj = self.shell.cfg.get("projet_actif")
        if pj:
            doc = os.path.join(os.path.expanduser("~/XIII"), pj, "03_Documents"); os.makedirs(doc, exist_ok=True)
            shutil.copy(os.path.join(d, nom + ".xiii.json"), os.path.join(doc, "BACKUPO-%s-%s.xiii.json" % (t["nom_transfert"], t["nom_support"])))
        try:
            from .somme import historiser
            ko = sum(1 for l in lignes if l[3] != "OK")
            historiser({"date": now, "source": t["source"], "copie": d, "algo": t["algo"], "fichiers": len(lignes), "octets": sum(l[1] for l in lignes),
                        "ok": len(lignes) - ko, "differents": ko, "manquants": 0, "rapport": os.path.join(d, nom + ".mhl")})
        except Exception:
            pass
