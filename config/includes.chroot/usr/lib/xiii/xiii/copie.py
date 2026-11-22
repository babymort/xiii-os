# OS XIII — file de copie de Fichiers XIII : copies et déplacements l'un après l'autre, pause / reprise / annulation,
# vitesse et temps restant, et vérification de chaque fichier copié (xxHash64 de la source calculé pendant la lecture,
# puis relecture de la copie) : indispensable pour décharger des rushes en toute confiance.
import os, shutil, time, threading
try:
    import xxhash
    def _h(): return xxhash.xxh64()
    ALGO = "xxHash64"
except ImportError:
    import hashlib
    def _h(): return hashlib.md5()
    ALGO = "MD5"

BLOC = 8 * 1024 * 1024

class Tache:
    def __init__(self, sources, dest, deplacer=False, verifier=True):
        self.sources, self.dest, self.deplacer, self.verifier = list(sources), dest, deplacer, verifier
        self.total = self.fait = 0; self.nb = self.nb_fait = 0; self.erreurs = []; self.etat = "attente"
        self.pause = False; self.annule = False; self.vitesse = 0.0; self.courant = ""; self.verifies = 0; self.cibles = []

    @property
    def titre(self):
        n = len(self.sources)
        return ("Déplacement" if self.deplacer else "Copie") + " de " + (os.path.basename(self.sources[0].rstrip("/")) if n == 1 else "%d éléments" % n) + " vers " + (os.path.basename(self.dest) or self.dest)

    def _cible(self, p):
        b = os.path.basename(p.rstrip("/")); c = os.path.join(self.dest, b); k = 2
        while os.path.lexists(c):
            n, e = os.path.splitext(b); c = os.path.join(self.dest, "%s (%d)%s" % (n, k, e) if os.path.isfile(p) else "%s (%d)" % (b, k)); k += 1
        return c

    def _attendre(self):
        while self.pause and not self.annule: time.sleep(.2)
        return not self.annule

    def _copier_fichier(self, s, d):
        h = _h() if self.verifier else None
        os.makedirs(os.path.dirname(d), exist_ok=True)
        t0, f0 = time.time(), self.fait
        with open(s, "rb") as fs, open(d + ".xiii-partiel", "wb") as fd:
            while True:
                if not self._attendre(): break
                b = fs.read(BLOC)
                if not b: break
                fd.write(b); self.fait += len(b)
                if h: h.update(b)
                dt = time.time() - t0
                if dt > .5: self.vitesse = .7 * self.vitesse + .3 * (self.fait - f0) / dt if self.vitesse else (self.fait - f0) / dt; t0, f0 = time.time(), self.fait
            fd.flush(); os.fsync(fd.fileno())
        if self.annule:
            os.remove(d + ".xiii-partiel"); return False
        os.replace(d + ".xiii-partiel", d); shutil.copystat(s, d, follow_symlinks=False)
        if h:                                  # relecture de la copie (pas depuis le cache : fichier juste écrit, fsync fait)
            self.etat = "vérification"
            h2 = _h()
            try:
                fd = os.open(d, os.O_RDONLY)
                try: os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
                except (AttributeError, OSError): pass
                with os.fdopen(fd, "rb") as f:
                    while True:
                        b = f.read(BLOC)
                        if not b: break
                        h2.update(b)
            except OSError as e:
                self.erreurs.append((s, "relecture impossible : %s" % e)); return True
            if h.hexdigest() != h2.hexdigest(): self.erreurs.append((s, "la copie est différente de l'original (somme %s)" % ALGO))
            else: self.verifies += 1
            self.etat = "copie"
        return True

    def lancer(self):
        self.etat = "préparation"; plan = []
        for p in self.sources:
            if not os.path.lexists(p): continue
            c = self._cible(p); self.cibles.append(c)
            if self.deplacer:
                try:
                    if os.stat(p).st_dev == os.stat(self.dest).st_dev:      # même disque : déplacement instantané
                        os.rename(p, c); continue
                except OSError: pass
            if os.path.isdir(p) and not os.path.islink(p):
                for r, ds, fs in os.walk(p):
                    rel = os.path.relpath(r, p); os.makedirs(os.path.join(c, rel), exist_ok=True)
                    for x in fs:
                        s = os.path.join(r, x)
                        try: plan.append((s, os.path.join(c, rel, x), os.lstat(s).st_size))
                        except OSError: pass
            else:
                plan.append((p, c, os.lstat(p).st_size))
        self.total = sum(x[2] for x in plan) or 1; self.nb = len(plan); self.etat = "copie"
        for s, d, n in plan:
            if self.annule: break
            self.courant = os.path.basename(s)
            try:
                if os.path.islink(s): os.symlink(os.readlink(s), d); self.fait += n
                elif not self._copier_fichier(s, d): break
                self.nb_fait += 1
            except OSError as e:
                self.erreurs.append((s, str(e)))
        if self.deplacer and not self.annule and not self.erreurs:    # déplacement entre disques : source effacée seulement si tout est bien copié
            for p in self.sources:
                if os.path.lexists(p):
                    try: shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
                    except OSError as e: self.erreurs.append((p, "source non effacée : %s" % e))
        self.etat = "annulée" if self.annule else ("erreurs" if self.erreurs else "terminée")

    def texte(self, humain):
        if self.etat in ("attente", "préparation"): return "En attente…" if self.etat == "attente" else "Préparation…"
        if self.etat in ("terminée", "erreurs", "annulée"):
            v = (" · %d fichier(s) vérifié(s) (%s)" % (self.verifies, ALGO)) if self.verifier and self.verifies else ""
            return {"terminée": "Terminé", "annulée": "Annulé", "erreurs": "%d erreur(s)" % len(self.erreurs)}[self.etat] + " · %d fichier(s)%s" % (self.nb_fait, v)
        reste = (self.total - self.fait) / self.vitesse if self.vitesse > 0 else 0
        r = ("encore %d min" % (reste // 60 + 1)) if reste > 60 else ("encore %d s" % reste if reste else "")
        return "%s%s sur %s · %s/s · %s · %d/%d fichiers" % ("⏸ En pause · " if self.pause else ("Vérification · " if self.etat == "vérification" else ""),
                                                          humain(self.fait), humain(self.total), humain(self.vitesse), r, self.nb_fait, self.nb)

class File:
    """Les tâches s'exécutent l'une après l'autre (un disque n'aime pas deux copies en même temps)."""
    def __init__(self, change):
        self.taches = []; self.change = change; self._fil = None
    def ajouter(self, t):
        self.taches.append(t); self.change()
        if not (self._fil and self._fil.is_alive()):
            self._fil = threading.Thread(target=self._boucle, daemon=True); self._fil.start()
    def _boucle(self):
        while True:
            t = next((x for x in self.taches if x.etat == "attente"), None)
            if not t: return
            t.lancer(); self.change(t)
