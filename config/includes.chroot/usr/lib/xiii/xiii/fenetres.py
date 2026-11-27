# OS XIII — liste des fenêtres ouvertes pour la barre des tâches.
# Petit client Wayland en Python pur (protocole zwlr_foreign_toplevel_manager_v1, géré par labwc) :
# aucune dépendance, branché sur la boucle GLib.
# Application développée par Matthieu Lamotte.
import os, socket, struct
from gi.repository import GLib

ETAT_MAX, ETAT_MIN, ETAT_ACTIF, ETAT_PLEIN = 0, 1, 2, 3

class Fenetre:
    def __init__(self, oid):
        self.id = oid; self.titre = ""; self.app_id = ""; self.etats = set(); self.sorties = set()      # ids des wl_output où elle est affichée
    @property
    def active(self): return ETAT_ACTIF in self.etats
    @property
    def reduite(self): return ETAT_MIN in self.etats

class Gestionnaire:
    """rappel() est appelé (boucle GTK) à chaque changement ; .fenetres = liste ordonnée."""
    def __init__(self, rappel):
        self.rappel = rappel; self.fenetres = {}; self.ordre = []
        self.ok = False; self._buf = b""; self._next = 2; self._types = {1: "display"}
        self._registry = self._manager = self._seat = None
        self.noms_sorties = {}          # id wl_output → nom de l'écran (HDMI-A-1, eDP-1…), comme Gdk.Monitor.get_connector()
        path = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        if not path.startswith("/"):
            path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), path)
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(path); self.sock.setblocking(False)
        except OSError:
            return
        self.ok = True
        self._registry = self._nouvel("registry")
        self._envoyer(1, 1, struct.pack("<I", self._registry))          # wl_display.get_registry
        GLib.io_add_watch(self.sock.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._lire)

    # ------------------------------------------------------------ fil
    def _nouvel(self, typ):
        i = self._next; self._next += 1; self._types[i] = typ; return i

    def _envoyer(self, obj, op, args=b""):
        try:
            self.sock.sendall(struct.pack("<II", obj, ((8 + len(args)) << 16) | op) + args)
        except OSError:
            pass

    @staticmethod
    def _chaine(s):
        b = s.encode() + b"\0"
        return struct.pack("<I", len(b)) + b + b"\0" * ((4 - len(b) % 4) % 4)

    @staticmethod
    def _lire_chaine(d, o):
        n = struct.unpack_from("<I", d, o)[0]; o += 4
        s = d[o:o + n - 1].decode("utf-8", "replace") if n else ""
        return s, o + ((n + 3) & ~3)

    def _lire(self, fd, cond):
        if cond & (GLib.IO_HUP | GLib.IO_ERR):
            self.ok = False; return False
        try:
            data = self.sock.recv(65536)
        except BlockingIOError:
            return True
        except OSError:
            self.ok = False; return False
        if not data:
            self.ok = False; return False
        self._buf += data
        change = False
        while len(self._buf) >= 8:
            obj, w = struct.unpack_from("<II", self._buf)
            taille, op = w >> 16, w & 0xffff
            if taille < 8 or len(self._buf) < taille: break
            corps = self._buf[8:taille]; self._buf = self._buf[taille:]
            change |= self._evenement(obj, op, corps)
        if change:
            self.rappel()
        return True

    def _evenement(self, obj, op, d):
        t = self._types.get(obj)
        if t == "registry" and op == 0:                                     # global
            nom = struct.unpack_from("<I", d, 0)[0]
            iface, o = self._lire_chaine(d, 4)
            ver = struct.unpack_from("<I", d, o)[0]
            if iface == "zwlr_foreign_toplevel_manager_v1" and not self._manager:
                self._manager = self._nouvel("manager")
                self._envoyer(self._registry, 0, struct.pack("<I", nom) + self._chaine(iface) + struct.pack("<II", min(ver, 3), self._manager))
            elif iface == "wl_output" and ver >= 4:                         # pour savoir sur quel écran est chaque fenêtre
                o_ = self._nouvel("output"); self.noms_sorties[o_] = ""
                self._envoyer(self._registry, 0, struct.pack("<I", nom) + self._chaine(iface) + struct.pack("<II", 4, o_))
            elif iface == "wl_seat" and not self._seat:
                self._seat = self._nouvel("seat")
                self._envoyer(self._registry, 0, struct.pack("<I", nom) + self._chaine(iface) + struct.pack("<II", 1, self._seat))
        elif t == "manager" and op == 0:                                    # toplevel(new_id)
            nid = struct.unpack_from("<I", d, 0)[0]
            self._types[nid] = "toplevel"; self.fenetres[nid] = Fenetre(nid); self.ordre.append(nid)
        elif t == "toplevel":
            f = self.fenetres.get(obj)
            if not f: return False
            if op == 0: f.titre = self._lire_chaine(d, 0)[0]
            elif op == 1: f.app_id = self._lire_chaine(d, 0)[0]
            elif op == 4:
                n = struct.unpack_from("<I", d, 0)[0]
                f.etats = set(struct.unpack_from("<%dI" % (n // 4), d, 4)) if n else set()
            elif op in (2, 3):                                              # output_enter / output_leave
                o_ = struct.unpack_from("<I", d, 0)[0]
                (f.sorties.add if op == 2 else f.sorties.discard)(o_)
            elif op == 5: return True                                       # done
            elif op == 6:                                                   # closed
                self.fenetres.pop(obj, None)
                if obj in self.ordre: self.ordre.remove(obj)
                self._envoyer(obj, 7)                                       # destroy
                return True
        elif t == "output" and op == 4:                                     # wl_output.name
            self.noms_sorties[obj] = self._lire_chaine(d, 0)[0]
        elif t == "display" and op == 1:                                    # delete_id
            self._types.pop(struct.unpack_from("<I", d, 0)[0], None)
        return False

    # ------------------------------------------------------------ actions
    def ecrans(self, f):
        """Noms des écrans où la fenêtre est affichée (vide si inconnu)."""
        return {self.noms_sorties.get(o) for o in f.sorties if self.noms_sorties.get(o)}

    def liste(self):
        return [self.fenetres[i] for i in self.ordre if i in self.fenetres]

    def activer(self, f):
        if f.reduite: self._envoyer(f.id, 3)                                # unset_minimized
        if self._seat: self._envoyer(f.id, 4, struct.pack("<I", self._seat))

    def reduire(self, f):
        self._envoyer(f.id, 2)

    def fermer(self, f):
        self._envoyer(f.id, 5)

    def agrandir(self, f):
        """Agrandit la fenêtre, ou la remet à sa taille si elle l'est déjà (set_maximized / unset_maximized)."""
        self._envoyer(f.id, 1 if ETAT_MAX in f.etats else 0)

    def plein_ecran(self, f):
        if ETAT_PLEIN in f.etats: self._envoyer(f.id, 9)
        else: self._envoyer(f.id, 8, struct.pack("<I", 0))

    def clic(self, f):
        """Comme Windows : active, ou réduit si déjà au premier plan."""
        if f.active and not f.reduite: self.reduire(f)
        else: self.activer(f)

    def active(self):
        return next((f for f in self.liste() if f.active), None)
