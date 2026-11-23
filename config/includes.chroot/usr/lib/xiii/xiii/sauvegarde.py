# OS XIII — Sauvegarde XIII, règle du 3-2-1 guidée : 3 copies de vos fichiers, sur 2 supports différents, dont 1 hors des
# murs (NAS distant ou cloud). Moteur restic : sauvegardes chiffrées, incrémentielles (seul ce qui change est copié),
# historique (7 jours, 4 semaines, 12 mois), vérification mensuelle, restauration d'un fichier ou de tout.
# Destinations : disque USB ou interne, NAS (lecteur réseau monté), cloud (OneDrive, Google Drive… via les Lecteurs réseau).
#   xiii-sauvegarde            assistant et tableau de bord
#   xiii-sauvegarde --auto     sauvegarde planifiée (lancée par le bureau une fois par jour si une destination est là)
# Application développée par Matthieu Lamotte.
import os, sys, json, time, secrets, subprocess, threading, shutil, re
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gio

CONF = os.path.expanduser("~/.config/xiii/sauvegarde.json")
CLE = os.path.expanduser("~/.local/share/xiii/sauvegarde.cle")
EXCLURE = ["*/.cache", "*/Cache", "*/cache2", "*/.thumbnails", "*/node_modules", "*/.local/share/Trash", "*/Téléchargements/*.iso", "*/.var/app/*/cache", "*/Steam", "*/.steam"]


def conf():
    try: return json.load(open(CONF))
    except Exception:
        h = os.path.expanduser("~")
        d = lambda k: GLib.get_user_special_dir(k)
        src = [x for x in (os.path.join(h, "XIII"), d(GLib.UserDirectory.DIRECTORY_DOCUMENTS), d(GLib.UserDirectory.DIRECTORY_PICTURES), d(GLib.UserDirectory.DIRECTORY_DESKTOP),
                           os.path.join(h, ".config/xiii"), os.path.join(h, ".local/share/xiii")) if x and os.path.isdir(x)]
        return {"sources": src, "destinations": [], "etat": {}}


def sauver(c):
    os.makedirs(os.path.dirname(CONF), exist_ok=True); json.dump(c, open(CONF, "w"), ensure_ascii=False, indent=1)


def cle():
    """Mot de passe de chiffrement des sauvegardes (créé une fois, à noter : il est demandé pour restaurer sur un autre PC)."""
    if not os.path.exists(CLE):
        os.makedirs(os.path.dirname(CLE), exist_ok=True)
        fd = os.open(CLE, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, "w") as f: f.write("-".join(secrets.token_hex(3) for _ in range(5)))
    return open(CLE).read().strip()


def env():
    e = dict(os.environ); e["RESTIC_PASSWORD_FILE"] = CLE; e["RESTIC_CACHE_DIR"] = os.path.expanduser("~/.cache/restic"); cle(); return e


def disponible(d):
    if d["type"] == "cloud": return True
    racine = d["depot"].split("/Sauvegarde XIII")[0]
    return os.path.isdir(racine) and os.access(racine, os.W_OK)


def restic(d, *args, json_=False, progres=None, timeout=None):
    cmd = ["restic", "-r", d["depot"]] + list(args) + (["--json"] if json_ or progres else [])
    if not progres:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env(), timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env()); fin = {}
    for l in p.stdout:
        try: j = json.loads(l)
        except ValueError: continue
        if j.get("message_type") == "status": progres(j.get("percent_done", 0), j)
        elif j.get("message_type") == "summary": fin = j
    err = p.stderr.read(); return p.wait(), fin, err


def initialiser(d):
    rc, o, e = restic(d, "cat", "config")
    if rc == 0: return
    if d["type"] != "cloud": os.makedirs(d["depot"], exist_ok=True)
    rc, o, e = restic(d, "init")
    if rc: raise RuntimeError(e.strip()[-300:] or "création impossible")


def sauvegarder(d, sources, progres=lambda f, j: None):
    initialiser(d)
    ex = []
    for x in EXCLURE: ex += ["--exclude", x]
    rc, fin, err = restic(d, "backup", "--tag", "xiii", "--exclude-caches", "--one-file-system", *ex, *sources, progres=progres)
    if rc not in (0, 3): raise RuntimeError(err.strip()[-300:] or "sauvegarde impossible")      # 3 = quelques fichiers illisibles, le reste est sauvé
    restic(d, "forget", "--tag", "xiii", "--keep-daily", "7", "--keep-weekly", "4", "--keep-monthly", "12", "--prune")
    return {"date": time.strftime("%Y-%m-%d %H:%M"), "ok": True, "fichiers": fin.get("total_files_processed"), "ajoute": fin.get("data_added", 0), "partiel": rc == 3}


def verifier(d):
    rc, o, e = restic(d, "check", "--read-data-subset=5%")
    return rc == 0, (o + e).strip()[-300:]


def instantanes(d):
    rc, o, e = restic(d, "snapshots", "--tag", "xiii", json_=True)
    try: return sorted(json.loads(o), key=lambda s: s["time"], reverse=True) if rc == 0 else []
    except ValueError: return []


def chercher(d, motif):
    rc, o, e = restic(d, "find", "--json", "*%s*" % motif)
    out = []
    try:
        for bloc in json.loads(o):
            for m in bloc.get("matches", [])[:50]: out.append((bloc["snapshot"], m["path"], m.get("mtime", "")[:16].replace("T", " ")))
    except ValueError: pass
    return out[:200]


def restaurer(d, snap, chemin=None, cible=None):
    cible = cible or os.path.expanduser("~/Restauré %s" % time.strftime("%Y-%m-%d %H%M"))
    a = ["restore", snap, "--target", cible] + (["--include", chemin] if chemin else [])
    rc, o, e = restic(d, *a)
    if rc: raise RuntimeError(e.strip()[-300:])
    return cible


def regle_321(c):
    """→ (copies, supports, hors_site) : l'original compte pour 1 copie sur 1 support."""
    D = c.get("destinations", [])
    return 1 + len(D), 1 + len({d["type"] for d in D if d["type"] in ("local", "nas")}) + (1 if any(d["type"] == "cloud" for d in D) else 0), any(d["type"] in ("cloud", "nas") for d in D)


def automatique():
    """Une fois par jour pour chaque destination présente ; vérification tous les 30 jours."""
    c = conf(); R = []
    for d in c.get("destinations", []):
        e = c.setdefault("etat", {}).setdefault(d["id"], {})
        if not disponible(d): continue
        if time.time() - e.get("t", 0) > 20 * 3600:
            try: r = sauvegarder(d, c["sources"]); e.update(r, t=time.time()); R.append("%s ✓" % d["nom"])
            except Exception as ex: e.update(ok=False, erreur=str(ex)[:200], date=time.strftime("%Y-%m-%d %H:%M")); R.append("%s ✗ %s" % (d["nom"], ex))
        if time.time() - e.get("verif_t", 0) > 30 * 86400:
            ok, msg = verifier(d); e.update(verif_t=time.time(), verif_ok=ok, verif=time.strftime("%Y-%m-%d"))
            if not ok: R.append("%s : vérification en échec !" % d["nom"])
        sauver(c)
    if R: subprocess.run(["notify-send", "-a", "Sauvegarde XIII", "-i", "xiii-sauvegarde", "Sauvegarde", "\n".join(R)])


# ===================================================================== fenêtre
def fenetre():
    from .ui import boite, label, bouton, ico, vider
    from .appli import preparer, page

    class App(Gtk.Application):
        def __init__(self): super().__init__(application_id="fr.xiii.sauvegarde")

        def do_activate(self):
            if getattr(self, "win", None): self.win.present(); return
            preparer(".etape-ok { color: #5fd39a; } .etape-ko { color: #ef6b6b; }")
            self.win = Gtk.ApplicationWindow(application=self, title="Sauvegarde XIII", default_width=900, default_height=760)
            self.rendu(); self.win.present()

        def rendu(self):
            c = conf(); self.c = c
            sc, v = page("Sauvegarde", "La règle du 3-2-1 : 3 copies, 2 supports différents, 1 hors de chez vous", "hard-drive-download"); self.win.set_child(sc); self.v = v
            if not shutil.which("restic"): v.append(label("Le moteur de sauvegarde (restic) n'est pas installé.", "attenue")); return
            n, s, hs = regle_321(c)
            g = boite(False, 12, homogeneous=True)
            for ok, t, sous in ((n >= 3, "%d copie%s" % (n, "s" if n > 1 else ""), "3 conseillées"), (s >= 2, "%d support%s" % (s, "s" if s > 1 else ""), "2 différents"), (hs, "Hors site" if hs else "Rien hors site", "NAS ou cloud")):
                b = boite(True, 2, "carte"); b.append(label(("✓ " if ok else "✗ ") + t, "gras", "etape-ok" if ok else "etape-ko")); b.append(label(sous, "petit", "attenue")); g.append(b)
            v.append(g)
            v.append(label("Ce qui est sauvegardé", "section"))
            for p in c["sources"]:
                r = boite(False, 8, "reglage"); r.append(ico("folder", 16, "c")); r.append(label(p.replace(os.path.expanduser("~"), "~"), hexpand=True))
                r.append(bouton(None, "x", "plat", rappel=lambda p=p: (c["sources"].remove(p), sauver(c), self.rendu()))); v.append(r)
            v.append(bouton("Ajouter un dossier…", "plus", "fantome", rappel=self.ajouter_source))
            v.append(label("Où", "section"))
            for d in c.get("destinations", []):
                e = c.get("etat", {}).get(d["id"], {})
                r = boite(False, 10, "reglage"); r.append(ico({"local": "hard-drive", "nas": "server", "cloud": "cloud"}[d["type"]], 20, "c"))
                t = boite(True, 0, hexpand=True); t.append(label(d["nom"], "gras"))
                etat = ("Dernière : %s%s" % (e["date"], " ✓" if e.get("ok") else " ✗ " + e.get("erreur", ""))) if e.get("date") else "Jamais sauvegardé"
                if e.get("verif"): etat += " · vérifiée le %s %s" % (e["verif"], "✓" if e.get("verif_ok") else "✗")
                if not disponible(d): etat += " · absente (branchez le disque / connectez le NAS)"
                t.append(label(etat, "petit", "attenue", wrap=True)); r.append(t)
                r.append(bouton("Sauvegarder", "play", "pilule", rappel=lambda d=d: self.lancer(d)))
                r.append(bouton(None, "rotate-ccw", "plat", tip="Restaurer", rappel=lambda d=d: self.restaurer(d)))
                r.append(bouton(None, "shield-check", "plat", tip="Vérifier maintenant", rappel=lambda d=d: self.verifier(d)))
                r.append(bouton(None, "trash-2", "plat", tip="Retirer (les sauvegardes restent sur le support)", rappel=lambda d=d: (c["destinations"].remove(d), sauver(c), self.rendu())))
                v.append(r)
            h = boite(False, 8)
            h.append(bouton("Disque USB / interne", "hard-drive", "fantome", rappel=lambda: self.ajouter_dest("local")))
            h.append(bouton("NAS", "server", "fantome", rappel=lambda: self.ajouter_dest("nas")))
            h.append(bouton("Cloud (OneDrive, Drive…)", "cloud", "fantome", rappel=lambda: self.ajouter_dest("cloud"))); v.append(h)
            self.pb = Gtk.ProgressBar(visible=False, show_text=True); v.append(self.pb)
            self.etat = label("", "attenue", wrap=True); v.append(self.etat)
            v.append(label("Automatique", "section"))
            v.append(label("Chaque jour, OS XIII sauvegarde vers chaque destination présente (disque branché, NAS joignable, cloud), puis vérifie chaque mois que les sauvegardes se relisent. "
                           "Rien n'est fait en mode Tournage.", "petit", "attenue", wrap=True))
            v.append(label("Mot de passe de chiffrement", "section"))
            k = label("•" * 20, "gras", selectable=True); hk = boite(False, 8); hk.append(k)
            hk.append(bouton("Afficher", "eye", "plat", rappel=lambda: k.set_text(cle()))); v.append(hk)
            v.append(label("Notez-le hors de l'ordinateur (ou dans Coffre XIII) : il est indispensable pour restaurer sur un autre PC si celui-ci est perdu.", "petit", "attenue", wrap=True))

        def ajouter_source(self):
            d = Gtk.FileDialog(title="Dossier à sauvegarder")
            def fin(dd, r):
                try: p = dd.select_folder_finish(r).get_path()
                except GLib.Error: return
                if p not in self.c["sources"]: self.c["sources"].append(p); sauver(self.c); self.rendu()
            d.select_folder(self.win, None, fin)

        def ajouter_dest(self, typ):
            if typ == "cloud":
                o = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True).stdout.split() if shutil.which("rclone") else []
                if not o: self.etat.set_text("Ajoutez d'abord un compte OneDrive ou Google Drive dans Lecteurs réseau."); S_detacher(["xiii-lecteurs"]); return
                dd = Gtk.Window(transient_for=self.win, modal=True, title="Cloud", default_width=420); v = boite(True, 10, margin_top=16, margin_bottom=16, margin_start=16, margin_end=16); dd.set_child(v)
                dr = Gtk.DropDown.new_from_strings(o); v.append(label("Compte cloud", "gras")); v.append(dr)
                def ok():
                    r = o[dr.get_selected()]
                    self.c["destinations"].append({"id": secrets.token_hex(4), "type": "cloud", "nom": "Cloud · " + r.rstrip(":").replace("xiii-", ""), "depot": "rclone:%sSauvegarde XIII" % r})
                    sauver(self.c); dd.close(); self.rendu()
                v.append(bouton("Ajouter", None, "pilule", rappel=ok)); dd.present(); return
            d = Gtk.FileDialog(title="Disque ou dossier de destination" if typ == "local" else "Dossier du NAS (Lecteurs réseau › Réseau)")
            if typ == "nas":
                for base in (os.path.expanduser("~/Réseau"), "/media", "/run/media"):
                    if os.path.isdir(base): d.set_initial_folder(Gio.File.new_for_path(base)); break
            def fin(dd, r):
                try: p = dd.select_folder_finish(r).get_path()
                except GLib.Error: return
                nom = ("Disque · " if typ == "local" else "NAS · ") + os.path.basename(p.rstrip("/"))
                self.c["destinations"].append({"id": secrets.token_hex(4), "type": typ, "nom": nom, "depot": os.path.join(p, "Sauvegarde XIII")}); sauver(self.c); self.rendu()
            d.select_folder(self.win, None, fin)

        def lancer(self, d):
            if not disponible(d): self.etat.set_text("%s n'est pas branché / joignable." % d["nom"]); return
            self.pb.set_visible(True); self.pb.set_fraction(0); self.etat.set_text("Sauvegarde vers %s…" % d["nom"])
            def prog(f, j): GLib.idle_add(lambda: (self.pb.set_fraction(f), self.pb.set_text("%d %% · %d fichiers" % (f * 100, j.get("files_done", 0))), False)[-1])
            def fond():
                try: r = sauvegarder(d, self.c["sources"], prog); ok = True
                except Exception as e: r = {"date": time.strftime("%Y-%m-%d %H:%M"), "ok": False, "erreur": str(e)[:200]}; ok = False
                c = conf(); c.setdefault("etat", {}).setdefault(d["id"], {}).update(r, t=time.time() if ok else 0); sauver(c)
                return r
            def fin(r):
                self.pb.set_fraction(1)
                self.etat.set_text(("Sauvegardé ✓ — %s fichiers, %s ajoutés%s" % (r.get("fichiers"), humain(r.get("ajoute", 0)), " (quelques fichiers illisibles ignorés)" if r.get("partiel") else "")) if r.get("ok") else "Erreur : %s" % r.get("erreur"))
                GLib.timeout_add_seconds(3, lambda: (self.rendu(), False)[1])
            threading.Thread(target=lambda: (lambda r: GLib.idle_add(fin, r))(fond()), daemon=True).start()

        def verifier(self, d):
            self.etat.set_text("Vérification de %s (relecture de 5 %% des données)…" % d["nom"])
            def fond():
                ok, msg = verifier(d); c = conf(); c.setdefault("etat", {}).setdefault(d["id"], {}).update(verif_t=time.time(), verif_ok=ok, verif=time.strftime("%Y-%m-%d")); sauver(c)
                GLib.idle_add(lambda: (self.etat.set_text("Vérification réussie ✓" if ok else "Vérification en échec : " + msg), self.rendu() if ok else None, False)[-1])
            threading.Thread(target=fond, daemon=True).start()

        def restaurer(self, d):
            dd = Gtk.Window(transient_for=self.win, modal=True, title="Restaurer depuis %s" % d["nom"], default_width=720, default_height=560)
            v = boite(True, 10, margin_top=16, margin_bottom=16, margin_start=16, margin_end=16); dd.set_child(v)
            v.append(label("Sauvegardes disponibles", "gras")); dsnap = Gtk.DropDown.new_from_strings(["Chargement…"]); v.append(dsnap); S = []
            h = boite(False, 8); q = Gtk.SearchEntry(placeholder_text="Retrouver un fichier par son nom (ex. devis, A001_C003)", hexpand=True); h.append(q); v.append(h)
            sc = Gtk.ScrolledWindow(vexpand=True); res = boite(True, 4); sc.set_child(res); v.append(sc); et = label("", "petit", "attenue", wrap=True); v.append(et)
            def snaps(L):
                S[:] = L; dsnap.set_model(Gtk.StringList.new(["%s · %s" % (s["time"][:16].replace("T", " "), s.get("hostname", "")) for s in L] or ["Aucune sauvegarde"]))
            threading.Thread(target=lambda: (lambda L: GLib.idle_add(snaps, L))(instantanes(d)), daemon=True).start()
            def rest(snap, chemin=None):
                et.set_text("Restauration…")
                def fond():
                    try: r = restaurer(d, snap, chemin)
                    except Exception as e: r = e
                    GLib.idle_add(lambda: (et.set_text(("Restauré dans « %s » ✓ (vos fichiers actuels ne sont pas touchés)" % r) if isinstance(r, str) else "Erreur : %s" % r), False)[1])
                threading.Thread(target=fond, daemon=True).start()
            def go(*_):
                vider(res); et.set_text("Recherche…")
                def fond():
                    L = chercher(d, q.get_text().strip()); GLib.idle_add(montrer, L)
                threading.Thread(target=fond, daemon=True).start()
            def montrer(L):
                vider(res); et.set_text("%d résultat(s)" % len(L))
                for snap, p, m in L:
                    r = boite(False, 8, "reglage"); t = boite(True, 0, hexpand=True); t.append(label(os.path.basename(p), "gras")); t.append(label("%s · %s" % (os.path.dirname(p), m), "petit", "attenue", ellipsize=True)); r.append(t)
                    r.append(bouton("Restaurer", None, "fantome", rappel=lambda snap=snap, p=p: rest(snap, p))); res.append(r)
            q.connect("activate", go)
            v.append(bouton("Tout restaurer depuis cette sauvegarde", "rotate-ccw", "pilule", rappel=lambda: rest(S[dsnap.get_selected()]["short_id"]) if S else None))
            dd.present()

    return App().run(sys.argv[:1])


def S_detacher(cmd): subprocess.Popen(cmd, start_new_session=True)


def humain(o):
    o = float(o or 0)
    for u in ("o", "Ko", "Mo", "Go", "To"):
        if o < 1000: return ("%.0f %s" if u == "o" else "%.1f %s") % (o, u)
        o /= 1000
    return "%.1f Po" % o


def main():
    if "--auto" in sys.argv: automatique(); return
    if "--test" in sys.argv:          # tests : sauvegarde, recherche, restauration et vérification dans /tmp
        import tempfile
        src = tempfile.mkdtemp(); open(os.path.join(src, "devis-concert.pdf"), "wb").write(os.urandom(200000))
        d = {"id": "t", "type": "local", "nom": "Test", "depot": "/tmp/xiii-sauvegarde-test/Sauvegarde XIII"}
        r = sauvegarder(d, [src]); L = chercher(d, "devis"); cible = restaurer(d, L[0][0], L[0][1], "/tmp/xiii-restaure")
        ok_v, _ = verifier(d)
        same = open(os.path.join(src, "devis-concert.pdf"), "rb").read() == open(cible + L[0][1], "rb").read()
        print("%s Sauvegarde XIII : %s fichier(s) sauvegardé(s), retrouvé « %s », restauré identique %s, vérification %s" % ("OK       " if same and ok_v else "ÉCHEC    ", r["fichiers"], os.path.basename(L[0][1]), same, ok_v))
        return
    sys.exit(fenetre())
