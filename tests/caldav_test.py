# Test aller-retour CalDAV de XIII Calendrier contre un serveur Radicale local (sans authentification).
import sys, datetime as dt
sys.path.insert(0, "/usr/lib/xiii")
from xiii import agenda_sync as A, agenda as G
A.JETONS = "/tmp/radi/comptes.json"; A.CACHE = "/tmp/radi/cache"
c = A.caldav_connecter("http://127.0.0.1:5232/", "zz", "x", "Radicale")
cal = c["agendas"][0]["id"]; z = G.ICI; d0 = dt.datetime(2026, 11, 26, 14, 0, tzinfo=z)
a, b = dt.datetime(2026, 11, 1, tzinfo=z), dt.datetime(2026, 12, 31, tzinfo=z)
href = A.enregistrer(c, cal, {"titre": "Repérage, Lyon", "debut": d0.isoformat(), "fin": (d0 + dt.timedelta(hours=2)).isoformat(), "journee": False, "lieu": "Halle", "rappel": 15})
L = A.recuperer(c, a, b); ok1 = [e["titre"] for e in L] == ["Repérage, Lyon"]
A.enregistrer(c, cal, {"titre": "Repérage déplacé", "debut": (d0 + dt.timedelta(days=1)).isoformat(), "fin": (d0 + dt.timedelta(days=1, hours=1)).isoformat(), "journee": False, "lieu": "", "rappel": None}, href)
L = A.recuperer(c, a, b); ok2 = len(L) == 1 and L[0]["titre"] == "Repérage déplacé" and L[0]["debut"].startswith("2026-11-27T14:00")
A.supprimer(c, cal, href); ok3 = A.recuperer(c, a, b) == []
print(("OK        " if ok1 and ok2 and ok3 else "ÉCHEC     ") + "CalDAV (Radicale) : %d agenda(s), création %s, modification %s, suppression %s" % (len(c["agendas"]), ok1, ok2, ok3))
