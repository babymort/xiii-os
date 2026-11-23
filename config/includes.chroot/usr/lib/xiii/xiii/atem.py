# OS XIII — pilotage direct d'un mélangeur Blackmagic ATEM par le réseau (protocole UDP 9910, sans le logiciel Blackmagic) :
# entrées Programme / Preview, CUT, AUTO, fondu au noir, noms des entrées, état en direct (même protocole que Tally XIII).
# Application développée par Matthieu Lamotte.
import socket, struct, threading, time

SYN, FIABLE, RENVOI, DEMANDE_RENVOI, ACK = 0x02, 0x01, 0x04, 0x08, 0x10
BONJOUR = bytes([0x10, 0x14, 0x53, 0xAB, 0, 0, 0, 0, 0, 0x3A, 0, 0, 0x01, 0, 0, 0, 0, 0, 0, 0])

class ATEM(threading.Thread):
    """Connexion à un ATEM ; rappel(etat) est appelé (depuis le fil réseau) à chaque changement."""
    def __init__(self, ip, rappel, port=9910):
        super().__init__(daemon=True)
        self.ip, self.port, self.rappel = ip, port, rappel
        self.actif = True; self.pret = False; self.session = 0x53AB; self.local = 0; self.s = None; self.verrou = threading.Lock()
        self.etat = {"connecte": False, "message": "Connexion…", "modele": "", "noms": {}, "courts": {}, "programme": None, "preview": None,
                     "transition": False, "noir": False, "entrees": [], "macros": {}, "macro_en_cours": None}

    def arreter(self): self.actif = False

    def _entete(self, drap, longueur, ack=0, local=0):
        return struct.pack(">HHHHBBH", (drap << 11) | longueur, self.session, ack, 0, 0, 0x41 if drap & ACK else 0, local)

    def envoyer(self, nom, donnees):
        """Commande fiable (l'ATEM en accuse réception) : CPgI, CPvI, DCut, DAut, FtbA…"""
        if not self.s or not self.pret: return False
        bloc = struct.pack(">HH4s", 8 + len(donnees), 0, nom.encode()) + donnees
        with self.verrou:
            self.local = (self.local + 1) & 0x7FFF
            try: self.s.sendto(self._entete(FIABLE, 12 + len(bloc), 0, self.local) + bloc, (self.ip, self.port)); return True
            except OSError: return False

    # commandes (M/E 1)
    def programme(self, src, me=0): return self.envoyer("CPgI", struct.pack(">BBH", me, 0, src))
    def preview(self, src, me=0): return self.envoyer("CPvI", struct.pack(">BBH", me, 0, src))
    def cut(self, me=0): return self.envoyer("DCut", struct.pack(">BBBB", me, 0, 0, 0))
    def auto(self, me=0): return self.envoyer("DAut", struct.pack(">BBBB", me, 0, 0, 0))
    def noir(self, me=0): return self.envoyer("FtbA", struct.pack(">BBBB", me, 0, 0, 0))
    def macro(self, index): return self.envoyer("MAct", struct.pack(">HBB", index, 0, 0))       # lancer la macro n° index
    def macro_stop(self): return self.envoyer("MAct", struct.pack(">HBB", 0xFFFF, 1, 0))

    def _maj(self, **kw):
        self.etat.update(kw)
        try: self.rappel(dict(self.etat))
        except Exception: pass

    def run(self):
        while self.actif:
            try: self._boucle()
            except Exception as e:
                self.pret = False; self._maj(connecte=False, message="ATEM injoignable (%s) — nouvel essai…" % e)
                for _ in range(30):
                    if not self.actif: return
                    time.sleep(.1)

    def _boucle(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0.5); self.s = s
        try:
            s.sendto(BONJOUR, (self.ip, self.port)); t0 = dernier = time.time(); self.pret = False; self.local = 0
            while self.actif:
                try: data, _ = s.recvfrom(8192)
                except socket.timeout:
                    if time.time() - dernier > 3: raise ConnectionError("pas de réponse")
                    if not self.pret and time.time() - t0 > 1.5: s.sendto(BONJOUR, (self.ip, self.port)); t0 = time.time()
                    continue
                if len(data) < 12: continue
                mot, sess, _, _, _, distant = struct.unpack(">HHHHHH", data[:12])
                drap, lng = mot >> 11, mot & 0x07FF; dernier = time.time()
                if drap & SYN:
                    if len(data) > 12 and data[12] == 0x03: raise ConnectionError("trop de connexions ouvertes sur l'ATEM")
                    self.session = sess; s.sendto(self._entete(ACK, 12, distant), (self.ip, self.port)); continue
                self.session = sess
                if drap & FIABLE: s.sendto(self._entete(ACK, 12, distant), (self.ip, self.port))
                charge = data[12:lng] if lng <= len(data) else data[12:]; i = 0; change = False
                while i + 8 <= len(charge):
                    l = struct.unpack(">H", charge[i:i + 2])[0]
                    if l < 8: break
                    nom, d = charge[i + 4:i + 8], charge[i + 8:i + l]; i += l
                    if nom == b"PrgI" and len(d) >= 4 and d[0] == 0: self.etat["programme"] = struct.unpack(">H", d[2:4])[0]; change = True
                    elif nom == b"PrvI" and len(d) >= 4 and d[0] == 0: self.etat["preview"] = struct.unpack(">H", d[2:4])[0]; change = True
                    elif nom == b"InPr" and len(d) >= 26:
                        src = struct.unpack(">H", d[:2])[0]
                        long_ = d[2:22].split(b"\0")[0].decode("utf-8", "replace").strip(); court = d[22:26].split(b"\0")[0].decode("utf-8", "replace").strip()
                        self.etat["noms"][src] = long_ or court; self.etat["courts"][src] = court or long_
                        # entrées « réelles » (caméras, lecteurs, couleurs, barres, noir) : on garde 0 à 40 et 1000-2002 (barres, couleurs)
                        if (src <= 40 or src in (1000, 2001, 2002, 3010, 3020)) and src not in self.etat["entrees"]: self.etat["entrees"].append(src)
                    elif nom == b"_pin": self.etat["modele"] = d.split(b"\0")[0].decode("utf-8", "replace")
                    elif nom == b"TrPs" and len(d) >= 2 and d[0] == 0: self.etat["transition"] = bool(d[1] & 1); change = True
                    elif nom == b"FtbS" and len(d) >= 3 and d[0] == 0: self.etat["noir"] = bool(d[1]); change = True
                    elif nom == b"MPrp" and len(d) >= 8:          # propriétés d'une macro : n°, utilisée, nom
                        idx, util = struct.unpack(">H", d[:2])[0], d[2]; ln = struct.unpack(">H", d[4:6])[0]
                        if util: self.etat["macros"][idx] = d[8:8 + ln].decode("utf-8", "replace") or "Macro %d" % (idx + 1)
                        else: self.etat["macros"].pop(idx, None)
                        change = True
                    elif nom == b"MRPr" and len(d) >= 4:          # macro en cours d'exécution
                        self.etat["macro_en_cours"] = struct.unpack(">H", d[2:4])[0] if d[0] & 1 else None; change = True
                    elif nom == b"InCm":
                        self.pret = True; self.etat["entrees"].sort(); self._maj(connecte=True, message="Connecté — " + (self.etat["modele"] or "ATEM")); change = False
                if change and self.pret: self._maj()
        finally:
            s.close(); self.s = None
