# OS XIII — mode Backup : déchargement des cartes et disques.
# Dès qu'un support est branché (mode Auto) ou sur un clic (mode Manuel) : copie vers <destination>/<nom du transfert>/<support>,
# empreinte calculée pendant la copie, relecture et vérification de chaque fichier copié, rapport texte + MHL,
# fichier BACKUPO (.xiii.json) pour la Suite XIII, progression lumineuse dans la barre des tâches.
# Application développée par Matthieu Lamotte.
import os, json, time, subprocess, hashlib, threading, datetime, socket, getpass, shutil
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

    def destination2(self):
        """Deuxième copie (disque navette, NAS…) : facultative."""
        d = self.shell.cfg.get("backup_destination2") or ""
        return d if d and os.path.isdir(d) else None

    def choisir_destination2(self, apres=None):
        dlg = Gtk.FileDialog(title="Deuxième copie des rushes (disque navette, NAS…)")
        def fini(d, res):
            try: f = d.select_folder_finish(res).get_path()
            except Exception: return
            config.modifier(backup_destination2=f)
            if apres: GLib.timeout_add(300, lambda: (apres(), False)[1])
        dlg.select_folder(None, None, fini)

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
        d2 = self.destination2(); dossier2 = None
        if d2:
            dossier2 = os.path.join(d2, nom_tr, s["nom"].replace("/", "-")); i = 2; b2 = dossier2
            while os.path.exists(dossier2) and os.listdir(dossier2): dossier2 = "%s_%d" % (b2, i); i += 1
        t = {"source": s["chemin"], "nom_support": s["nom"], "dossier": dossier, "dossier2": dossier2, "etat": "copie", "fraction": 0.0, "texte": "Préparation…",
             "algo": self.algo, "nom_transfert": nom_tr, "debut": time.time(), "mount": s.get("mount")}
        self.transferts.append(t)
        threading.Thread(target=self._copier, args=(t,), daemon=True).start()

    def _copier(self, t):
        src, dst, dst2, algo = t["source"], t["dossier"], t.get("dossier2"), t["algo"]
        fichiers = []
        for d, _, fs in os.walk(src):
            for f in fs:
                if f.startswith(".") or f in ("System Volume Information",): continue
                p = os.path.join(d, f)
                try: fichiers.append((p, os.path.getsize(p)))
                except OSError: pass
        n_copies = 2 if dst2 else 1
        total = sum(x for _, x in fichiers) * (1 + n_copies) or 1; fait = [0]; t0 = time.time(); lignes = []; erreurs = 0
        def avance(n, etape):
            fait[0] += n; dt = max(.1, time.time() - t0); v = fait[0] / dt; reste = (total - fait[0]) / max(1, v)
            t["fraction"] = fait[0] / total
            t["texte"] = "%s %d %% · %s/s · reste %s" % (etape, 100 * fait[0] / total, S.humain(v), "%d min %02d" % (reste // 60, reste % 60))
            if int(t["fraction"] * 100) != getattr(self, "_pc", -1):
                self._pc = int(t["fraction"] * 100); S.progres("xiii-modes.desktop", t["fraction"])
        try:
            cibles = [x for x in (dst, dst2) if x]
            for c in cibles: os.makedirs(c, exist_ok=True)
            for p, taille in fichiers:                          # 1. copie (une ou deux destinations, source lue une seule fois) + empreinte
                rel = os.path.relpath(p, src); qs = [os.path.join(c, rel) for c in cibles]
                for q in qs: os.makedirs(os.path.dirname(q), exist_ok=True)
                h = hacheur(algo); sorties = [open(q, "wb") for q in qs]
                try:
                    with open(p, "rb") as a:
                        while True:
                            x = a.read(BLOC)
                            if not x: break
                            h.update(x)
                            for b in sorties: b.write(x)
                            avance(len(x) * len(sorties), "Copie" + (" ×2" if dst2 else ""))
                    for b in sorties: b.flush(); os.fsync(b.fileno())
                finally:
                    for b in sorties: b.close()
                for q in qs: shutil.copystat(p, q, follow_symlinks=False)
                lignes.append([rel, taille, h.hexdigest(), "", "" if not dst2 else "?"])
            t["etat"] = "verification"
            for ligne in lignes:                                 # 2. relecture de chaque copie
                for k, c in enumerate(cibles):
                    h = hacheur(algo)
                    with open(os.path.join(c, ligne[0]), "rb") as b:
                        while True:
                            x = b.read(BLOC)
                            if not x: break
                            h.update(x); avance(len(x), "Vérification" + (" copie %d" % (k + 1) if dst2 else ""))
                    ligne[3 + k] = "OK" if h.hexdigest() == ligne[2] else "DIFFÉRENT"
                if any(x not in ("OK", "") for x in ligne[3:]): erreurs += 1
            t["fin"] = time.time()
            self._rapports(t, lignes)
            t["etat"] = "erreur" if erreurs else "fini"; t["fraction"] = 1
            t["texte"] = ("%d fichier(s) · %s · %s ✓" % (len(lignes), S.humain(sum(l[1] for l in lignes)), "2 copies vérifiées" if dst2 else "copie vérifiée")) if not erreurs else ("%d fichier(s) différent(s) !" % erreurs)
        except Exception as e:
            t["etat"] = "erreur"; t["texte"] = "Erreur : %s" % e
        S.progres("xiii-modes.desktop", None)
        self._apres(t)

    def _apres(self, t):
        """Fin du déchargement : tout le rapport part dans BACKUPO (entrée du journal) et dans DOSSIER (PDF + MHL),
        puis éjection de la carte et proxies si demandés."""
        c = self.shell.cfg
        titre = ("Déchargement vérifié : " if t["etat"] == "fini" else "Problème de déchargement : ") + t["nom_support"]
        envoye = []
        if t.get("lien") and c.get("backup_vers_suite", True):
            S.detacher(["xiii-suite", "--backupo", t["lien"]]); envoye.append("envoyé à BACKUPO")
            docs = [x for x in (t.get("pdf"), t.get("mhl")) if x and os.path.exists(x)]
            if docs: S.detacher(["xiii-suite", "--dossier"] + docs); envoye.append("à DOSSIER")
        if t["etat"] == "fini" and c.get("projet_actif"):        # carte dans l'Organiser du Studio XIII (colonne « Sauvegardé » si elle existe)
            try:
                from .studio import ajouter_carte
                ajouter_carte("Carte %s — %s" % (t["nom_support"], t["nom_transfert"]), "plan", {"carte_memoire": t["nom_support"], "fichier": t.get("rapport", "")},
                              colonne="Sauvegardé", etiquettes=["vert"]); envoye.append("carte dans le Studio")
            except Exception as e:
                print("[xiii] carte Studio impossible :", e)
        if t["etat"] == "fini" and c.get("backup_ejecter", False) and t.get("mount"):
            m = t["mount"]
            GLib.idle_add(lambda: (m.eject_with_operation(Gio.MountUnmountFlags.NONE, None, None, None, None) if m.can_eject() else
                                   m.unmount_with_operation(Gio.MountUnmountFlags.NONE, None, None, None, None), False)[1])
            envoye.append("carte éjectée")
        if t["etat"] == "fini" and c.get("backup_proxies", "non") != "non":
            threading.Thread(target=self._proxies, args=(t, c.get("backup_proxies")), daemon=True).start(); envoye.append("proxies en cours")
        corps = t["texte"] + ((" · " + ", ".join(envoye)) if envoye else "")
        def attendre():
            return subprocess.run(["notify-send", "-a", "Backup", "-i", "drive-harddisk", "-h", "string:sound-name:" + ("complete" if t["etat"] == "fini" else "dialog-error"),
                                   "--action=pdf=Voir le rapport", "--action=dossier=Ouvrir les rushes", titre, corps], capture_output=True, text=True, timeout=3600).stdout.strip()
        S.en_fond(attendre, lambda r: S.detacher(["xdg-open", t["pdf"]]) if r == "pdf" and t.get("pdf") else (S.detacher(["xiii-fichiers", t["dossier"]]) if r == "dossier" else None))

    def rapport_journee(self, jour=None, envoyer=True):
        """Rapport de la journée de tournage : tous les déchargements du jour (supports, fichiers, taille, copies vérifiées),
        en PDF rangé dans 03_Documents du projet et envoyé dans DOSSIER XIII."""
        jour = jour or datetime.date.today().isoformat()
        try: L = [e for e in json.load(open(os.path.join(GLib.get_user_data_dir(), "xiii", "dechargements.json"))) if e["date"].startswith(jour)]
        except Exception: L = []
        if not L: return None
        pj = self.shell.cfg.get("projet_actif", "")
        dest = os.path.join(os.path.expanduser("~/XIII"), pj, "03_Documents") if pj else self.destination()
        os.makedirs(dest, exist_ok=True)
        from . import rapport_pdf
        f = rapport_pdf.creer_journee(os.path.join(dest, "Rapport de tournage %s.pdf" % jour), jour, L, {"projet": pj, "dit": getpass.getuser(), "machine": socket.gethostname()})
        if envoyer and self.shell.cfg.get("backup_vers_suite", True): S.detacher(["xiii-suite", "--dossier", f])
        return f

    def _proxies(self, t, kind):
        """Proxies de montage à côté des rushes (dossier Proxies), en tâche de fond peu prioritaire."""
        VID = (".mov", ".mxf", ".mp4", ".m4v", ".mts", ".m2ts", ".avi", ".mkv")
        L = [os.path.join(r, f) for r, _, fs in os.walk(t["dossier"]) for f in fs if f.lower().endswith(VID) and "/Proxies" not in r]
        dossier = os.path.join(t["dossier"], "Proxies"); fait = 0
        for p in sorted(L):
            rel = os.path.relpath(p, t["dossier"]); base = os.path.splitext(os.path.join(dossier, rel))[0]
            os.makedirs(os.path.dirname(base), exist_ok=True)
            if kind == "prores":
                opts = ["-vf", "scale=-2:720", "-c:v", "prores_ks", "-profile:v", "0", "-c:a", "pcm_s16le"]; out = base + "_proxy.mov"
            else:
                opts = ["-vf", "scale=-2:540", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k"]; out = base + "_proxy.mp4"
            if os.path.exists(out): fait += 1; continue
            S.progres("xiii-modes.desktop", fait / max(1, len(L)))
            # même timecode que l'original (le montage retrouve les plans), toutes les pistes son
            subprocess.run(["nice", "-n", "15", "ionice", "-c3", "ffmpeg", "-v", "error", "-y", "-i", p, "-map", "0:v:0", "-map", "0:a?", "-map_metadata", "0"] + opts + [out], capture_output=True)
            fait += 1
        S.progres("xiii-modes.desktop", None)
        S.detacher(["notify-send", "-a", "Backup", "-i", "video-x-generic", "-h", "string:sound-name:complete", "Proxies prêts : " + t["nom_support"], "%d proxy(s) dans %s" % (fait, dossier)])

    def _rapports(self, t, lignes):
        now = datetime.datetime.now().isoformat(timespec="seconds"); d = t["dossier"]; nom = "backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        with open(os.path.join(d, nom + ".mhl"), "w") as m:
            m.write('<?xml version="1.0" encoding="UTF-8"?>\n<hashlist version="1.1">\n  <creatorinfo><name>%s</name><hostname>%s</hostname><tool>OS XIII Backup</tool><startdate>%s</startdate></creatorinfo>\n'
                    % (getpass.getuser(), socket.gethostname(), now))
            for rel, taille, h, st, *_ in lignes:
                m.write('  <hash><file>%s</file><size>%d</size><%s>%s</%s><hashdate>%s</hashdate></hash>\n' % (rel.replace("&", "&amp;").replace("<", "&lt;"), taille, TAG[t["algo"]], h, TAG[t["algo"]], now))
            m.write("</hashlist>\n")
        with open(os.path.join(d, nom + ".txt"), "w") as r:
            r.write("OS XIII — déchargement\nTransfert : %s\nSupport : %s\nSource : %s\nCopie : %s\nAlgorithme : %s\nDate : %s\n\n" % (t["nom_transfert"], t["nom_support"], t["source"], d, t["algo"], now))
            for rel, taille, h, st, *st2 in lignes: r.write("%s\t%d\t%s%s\t%s\n" % (h, taille, st, ("/" + st2[0]) if st2 and st2[0] else "", rel))
        # fichier pour BACKUPO XIII (Suite) : tout le rapport → une entrée complète du journal de déchargement
        MEDIA = (".mov", ".mxf", ".mp4", ".m4v", ".ari", ".arx", ".r3d", ".braw", ".crm", ".dng", ".mts", ".m2ts", ".avi", ".wav", ".bwf", ".mp3", ".aif", ".aiff", ".insv", ".lrv")
        medias = sorted(os.path.splitext(os.path.basename(l[0]))[0] for l in lignes if os.path.splitext(l[0])[1].lower() in MEDIA)
        dests = [{"chemin": d, "statut": "OK" if all(l[3] == "OK" for l in lignes) else "%d erreur(s)" % sum(1 for l in lignes if l[3] != "OK")}]
        if t.get("dossier2"):
            dests.append({"chemin": t["dossier2"], "statut": "OK" if all(l[4] == "OK" for l in lignes) else "%d erreur(s)" % sum(1 for l in lignes if l[4] != "OK")})
        lien = {"format": "xiii-link", "kind": "backupo", "source": "OS XIII", "version": 2,
                "data": {"titre": "%s — %s" % (t["nom_transfert"], t["nom_support"]), "transfert": t["nom_transfert"], "support": t["nom_support"], "source": t["source"],
                         "destination": d, "destinations": dests, "algo": t["algo"], "date": now, "debut": datetime.datetime.fromtimestamp(t["debut"]).isoformat(timespec="seconds"),
                         "duree_s": round(t.get("fin", time.time()) - t["debut"]), "projet": self.shell.cfg.get("projet_actif", ""), "dit": getpass.getuser(), "machine": socket.gethostname(),
                         "octets": sum(l[1] for l in lignes), "premier": medias[0] if medias else "", "dernier": medias[-1] if medias else "",
                         "ok": sum(1 for l in lignes if all(x in ("OK", "") for x in l[3:])),
                         "fichiers": [{"nom": l[0], "taille": l[1], "empreinte": l[2], "statut": l[3], "statut2": l[4] if len(l) > 4 else ""} for l in lignes]}}
        json.dump(lien, open(os.path.join(d, nom + ".xiii.json"), "w"), ensure_ascii=False, indent=1)
        t["lien"], t["rapport"], t["mhl"] = os.path.join(d, nom + ".xiii.json"), os.path.join(d, nom + ".txt"), os.path.join(d, nom + ".mhl")
        try:
            from . import rapport_pdf
            t["pdf"] = rapport_pdf.creer(os.path.join(d, "Rapport de déchargement %s %s.pdf" % (t["nom_transfert"], t["nom_support"])), t, lignes,
                                         {"projet": self.shell.cfg.get("projet_actif", ""), "dit": getpass.getuser(), "machine": socket.gethostname(), "destinations": dests})
        except Exception as e:
            print("[xiii] rapport PDF impossible :", e)
        try:                                       # journal des déchargements (rapport de la journée de tournage)
            J = os.path.join(GLib.get_user_data_dir(), "xiii", "dechargements.json")
            try: L = json.load(open(J))
            except Exception: L = []
            L.append({"date": now, "debut": t["debut"], "fin": t.get("fin"), "support": t["nom_support"], "transfert": t["nom_transfert"], "projet": self.shell.cfg.get("projet_actif", ""),
                      "fichiers": len(lignes), "octets": sum(l[1] for l in lignes), "ok": lien["data"]["ok"], "premier": lien["data"]["premier"], "dernier": lien["data"]["dernier"],
                      "destinations": dests, "pdf": t.get("pdf"), "dossier": d})
            os.makedirs(os.path.dirname(J), exist_ok=True); json.dump(L[-500:], open(J, "w"), ensure_ascii=False, indent=1)
        except Exception: pass
        if t.get("dossier2"):                     # la deuxième copie garde aussi ses rapports
            for x in (t.get("pdf"), t["mhl"], t["rapport"], t["lien"]):
                if x and os.path.exists(x): shutil.copy(x, t["dossier2"])
        pj = self.shell.cfg.get("projet_actif")
        if pj:
            doc = os.path.join(os.path.expanduser("~/XIII"), pj, "03_Documents"); os.makedirs(doc, exist_ok=True)
            shutil.copy(os.path.join(d, nom + ".xiii.json"), os.path.join(doc, "BACKUPO-%s-%s.xiii.json" % (t["nom_transfert"], t["nom_support"])))
            if t.get("pdf"): shutil.copy(t["pdf"], doc)
        try:
            from .somme import historiser
            ko = sum(1 for l in lignes if any(x not in ("OK", "") for x in l[3:]))
            historiser({"date": now, "source": t["source"], "copie": d, "algo": t["algo"], "fichiers": len(lignes), "octets": sum(l[1] for l in lignes),
                        "ok": len(lignes) - ko, "differents": ko, "manquants": 0, "rapport": os.path.join(d, nom + ".mhl")})
        except Exception:
            pass
