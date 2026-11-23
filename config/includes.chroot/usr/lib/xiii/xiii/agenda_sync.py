# OS XIII — XIII Calendrier, comptes connectés en lecture ET écriture :
# • Google Agenda (API Google Calendar, connexion OAuth dans le navigateur)
# • Outlook / Microsoft 365 (Microsoft Graph, connexion OAuth dans le navigateur)
# • CalDAV : iCloud (mot de passe pour app), Nextcloud, Synology Calendar, Fastmail… (adresse + identifiant + mot de passe)
# Les événements sont gardés en cache (consultables hors ligne) et rafraîchis toutes les 15 minutes.
# Application développée par Matthieu Lamotte.
import os, json, time, uuid, base64, hashlib, secrets, threading, urllib.request, urllib.parse, urllib.error, http.server, socketserver, re
import datetime as dt
import xml.etree.ElementTree as ET

JETONS = os.path.expanduser("~/.local/share/xiii/agenda-comptes.json")
CACHE = os.path.expanduser("~/.cache/xiii/agenda")
OAUTH = "/usr/share/xiii/oauth.json"     # identifiants d'application OS XIII (si fournis avec l'OS)
UA = "OS-XIII"

GOOGLE = {"auth": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
          "scope": "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.readonly openid email"}
MICROSOFT = {"auth": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
             "scope": "offline_access Calendars.ReadWrite User.Read"}


# ------------------------------------------------------------------ comptes (fichier privé, lisible par l'utilisateur seul)
def comptes():
    try: return json.load(open(JETONS))
    except Exception: return []


def sauver_comptes(L):
    os.makedirs(os.path.dirname(JETONS), exist_ok=True)
    fd = os.open(JETONS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(L, f, indent=1)


def maj_compte(c):
    L = [x for x in comptes() if x["id"] != c["id"]] + [c]; sauver_comptes(L)


def identifiants():
    """Identifiants OAuth de l'application : réglés dans Paramètres du calendrier, ou fournis avec l'OS."""
    d = {}
    try: d.update(json.load(open(OAUTH)))
    except Exception: pass
    try:
        from . import config
        c = config.charger()
        for k in ("google_client_id", "google_client_secret", "microsoft_client_id"):
            if c.get(k): d[k] = c[k]
    except Exception: pass
    return d


# ------------------------------------------------------------------ HTTP
def requete(methode, url, corps=None, entetes=None, delai=30, brut=False):
    h = {"User-Agent": UA}; h.update(entetes or {})
    if isinstance(corps, (dict, list)): corps = json.dumps(corps).encode(); h.setdefault("Content-Type", "application/json")
    elif isinstance(corps, str): corps = corps.encode()
    req = urllib.request.Request(url, data=corps, headers=h, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            d = r.read(); return r.status, (d if brut else (json.loads(d) if d and "json" in (r.headers.get("Content-Type") or "") else d.decode("utf-8", "replace")))
    except urllib.error.HTTPError as e:
        d = e.read().decode("utf-8", "replace"); return e.code, d


# ------------------------------------------------------------------ OAuth (navigateur + adresse locale de retour, PKCE)
def oauth(fournisseur, ouvrir=None):
    """Ouvre la page de connexion du fournisseur dans le navigateur, attend le retour sur 127.0.0.1. → dict du compte"""
    ids = identifiants()
    if fournisseur == "google":
        P, cid, secret = GOOGLE, ids.get("google_client_id"), ids.get("google_client_secret")
    else:
        P, cid, secret = MICROSOFT, ids.get("microsoft_client_id"), None
    if not cid: raise RuntimeError("identifiant d'application manquant (voir « Préparer la connexion »)")
    verif = secrets.token_urlsafe(48); defi = base64.urlsafe_b64encode(hashlib.sha256(verif.encode()).digest()).rstrip(b"=").decode()
    etat = secrets.token_urlsafe(16); recu = {}
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if "code" in q or "error" in q: recu.update(q)
            ok = "code" in q and q.get("state") == etat
            page = ("<html><meta charset=utf-8><body style='font-family:sans-serif;background:#161412;color:#eee9e3;text-align:center;padding-top:15vh'>"
                    "<h1 style='color:#f0b378'>%s</h1><p>%s</p></body></html>") % (("Agenda connecté ✓", "Vous pouvez fermer cet onglet et revenir à XIII Calendrier.") if ok else
                                                                              ("Connexion refusée", "Revenez à XIII Calendrier pour réessayer."))
            b = page.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    srv = socketserver.TCPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
    retour = "http://127.0.0.1:%d" % port if fournisseur == "google" else "http://localhost:%d" % port
    p = {"client_id": cid, "response_type": "code", "redirect_uri": retour, "scope": P["scope"], "state": etat, "code_challenge": defi, "code_challenge_method": "S256"}
    if fournisseur == "google": p.update(access_type="offline", prompt="consent select_account")
    else: p.update(prompt="select_account")
    url = P["auth"] + "?" + urllib.parse.urlencode(p)
    (ouvrir or (lambda u: __import__("subprocess").Popen(["xdg-open", u])))(url)
    srv.timeout = 1; fin = time.time() + 300
    while not recu and time.time() < fin: srv.handle_request()
    srv.server_close()
    if recu.get("state") != etat or "code" not in recu: raise RuntimeError(recu.get("error_description") or recu.get("error") or "connexion abandonnée")
    corps = {"client_id": cid, "grant_type": "authorization_code", "code": recu["code"], "redirect_uri": retour, "code_verifier": verif}
    if secret: corps["client_secret"] = secret
    st, j = requete("POST", P["token"], urllib.parse.urlencode(corps), {"Content-Type": "application/x-www-form-urlencoded"})
    if st != 200 or not isinstance(j, dict): raise RuntimeError("jeton refusé : %s" % str(j)[:200])
    c = {"id": uuid.uuid4().hex[:10], "type": fournisseur, "acces": j["access_token"], "rafraichir": j.get("refresh_token"), "expire": time.time() + int(j.get("expires_in", 3500)) - 60}
    c["nom"] = moi(c) or ("Google Agenda" if fournisseur == "google" else "Outlook")
    c["couleur"] = "#6aa8ff" if fournisseur == "google" else "#2f9bff"
    c["agendas"] = [a for a in lister_agendas(c)]
    maj_compte(c); return c


def jeton(c):
    if c["type"] == "caldav": return None
    if time.time() < c.get("expire", 0): return c["acces"]
    ids = identifiants(); P = GOOGLE if c["type"] == "google" else MICROSOFT
    corps = {"client_id": ids.get("google_client_id" if c["type"] == "google" else "microsoft_client_id"), "grant_type": "refresh_token", "refresh_token": c.get("rafraichir")}
    if c["type"] == "google" and ids.get("google_client_secret"): corps["client_secret"] = ids["google_client_secret"]
    st, j = requete("POST", P["token"], urllib.parse.urlencode(corps), {"Content-Type": "application/x-www-form-urlencoded"})
    if st != 200: raise RuntimeError("session expirée : reconnectez le compte « %s »" % c.get("nom"))
    c["acces"] = j["access_token"]; c["expire"] = time.time() + int(j.get("expires_in", 3500)) - 60
    if j.get("refresh_token"): c["rafraichir"] = j["refresh_token"]
    maj_compte(c); return c["acces"]


def auth(c): return {"Authorization": "Bearer " + jeton(c)}


def moi(c):
    try:
        if c["type"] == "google":
            st, j = requete("GET", "https://openidconnect.googleapis.com/v1/userinfo", entetes={"Authorization": "Bearer " + c["acces"]})
            return "Google · " + j.get("email", "") if st == 200 else None
        st, j = requete("GET", "https://graph.microsoft.com/v1.0/me", entetes={"Authorization": "Bearer " + c["acces"]})
        return "Outlook · " + (j.get("mail") or j.get("userPrincipalName") or "") if st == 200 else None
    except Exception:
        return None


# ------------------------------------------------------------------ CalDAV
NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav", "cs": "http://calendarserver.org/ns/", "a": "http://apple.com/ns/ical/"}
SERVEURS = {"icloud": "https://caldav.icloud.com/", "nextcloud": "https://{hote}/remote.php/dav/", "synology": "https://{hote}:5001/caldav/", "fastmail": "https://caldav.fastmail.com/dav/"}


def _dav(c, methode, url, corps=None, prof="0", typ="application/xml; charset=utf-8"):
    tok = base64.b64encode(("%s:%s" % (c["utilisateur"], c["mdp"])).encode()).decode()
    return requete(methode, urllib.parse.urljoin(c["serveur"], url), corps, {"Authorization": "Basic " + tok, "Depth": prof, "Content-Type": typ})


def caldav_connecter(serveur, utilisateur, mdp, nom=None):
    c = {"id": uuid.uuid4().hex[:10], "type": "caldav", "serveur": serveur, "utilisateur": utilisateur, "mdp": mdp, "nom": nom or "Agenda " + urllib.parse.urlparse(serveur).hostname, "couleur": "#5fd39a"}
    st, x = _dav(c, "PROPFIND", serveur, '<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>')
    if st in (401, 403): raise RuntimeError("identifiant ou mot de passe refusé (iCloud : utilisez un « mot de passe pour app »)")
    if st >= 400: raise RuntimeError("serveur CalDAV injoignable (%s)" % st)
    princ = ET.fromstring(x).find(".//d:current-user-principal/d:href", NS).text
    st, x = _dav(c, "PROPFIND", princ, '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><c:calendar-home-set/></d:prop></d:propfind>')
    maison = ET.fromstring(x).find(".//c:calendar-home-set/d:href", NS).text
    c["maison"] = maison; c["agendas"] = lister_agendas(c)
    if not c["agendas"]: raise RuntimeError("aucun agenda trouvé sur ce compte")
    maj_compte(c); return c


# ------------------------------------------------------------------ agendas d'un compte
def lister_agendas(c):
    """[{id, nom, ecriture}]"""
    if c["type"] == "google":
        st, j = requete("GET", "https://www.googleapis.com/calendar/v3/users/me/calendarList", entetes=auth(c))
        return [{"id": a["id"], "nom": a.get("summaryOverride") or a.get("summary"), "ecriture": a.get("accessRole") in ("owner", "writer"), "principal": bool(a.get("primary"))}
                for a in (j.get("items", []) if st == 200 else []) if not a.get("hidden")]
    if c["type"] == "outlook":
        st, j = requete("GET", "https://graph.microsoft.com/v1.0/me/calendars", entetes=auth(c))
        return [{"id": a["id"], "nom": a.get("name"), "ecriture": a.get("canEdit", True), "principal": bool(a.get("isDefaultCalendar"))} for a in (j.get("value", []) if st == 200 else [])]
    st, x = _dav(c, "PROPFIND", c["maison"], '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><d:displayname/><d:resourcetype/>'
                 '<c:supported-calendar-component-set/></d:prop></d:propfind>', "1")
    L = []
    for r in ET.fromstring(x).findall("d:response", NS):
        if r.find(".//d:resourcetype/c:calendar", NS) is None: continue
        comps = [e.get("name") for e in r.findall(".//c:supported-calendar-component-set/c:comp", NS)]
        if comps and "VEVENT" not in comps: continue
        L.append({"id": r.find("d:href", NS).text, "nom": (r.find(".//d:displayname", NS).text if r.find(".//d:displayname", NS) is not None else None) or "Agenda", "ecriture": True})
    if L: L[0]["principal"] = True
    return L


# ------------------------------------------------------------------ événements
def _iso_g(e):
    if "date" in e: return dt.datetime.fromisoformat(e["date"]).replace(tzinfo=ICI()).isoformat(), True
    return dt.datetime.fromisoformat(e["dateTime"].replace("Z", "+00:00")).astimezone(ICI()).isoformat(), False


def ICI():
    from .agenda import ICI as z
    return z


def recuperer(c, debut, fin):
    """Événements du compte entre debut et fin (datetime avec fuseau)."""
    out = []
    for a in c.get("agendas") or []:
        if c["type"] == "google":
            q = urllib.parse.urlencode({"timeMin": debut.isoformat(), "timeMax": fin.isoformat(), "singleEvents": "true", "orderBy": "startTime", "maxResults": 2500})
            st, j = requete("GET", "https://www.googleapis.com/calendar/v3/calendars/%s/events?%s" % (urllib.parse.quote(a["id"], safe=""), q), entetes=auth(c))
            if st != 200: continue
            for e in j.get("items", []):
                if e.get("status") == "cancelled" or "start" not in e: continue
                d0, jr = _iso_g(e["start"]); d1, _ = _iso_g(e["end"])
                out.append({"titre": e.get("summary") or "(sans titre)", "debut": d0, "fin": d1, "journee": jr, "lieu": e.get("location") or "", "notes": (e.get("description") or "")[:400],
                            "ext": e["id"], "cal": a["id"], "compte": c["id"], "modifiable": a["ecriture"] and not e.get("recurringEventId")})
        elif c["type"] == "outlook":
            q = urllib.parse.urlencode({"startDateTime": debut.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "endDateTime": fin.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "$top": 500})
            st, j = requete("GET", "https://graph.microsoft.com/v1.0/me/calendars/%s/calendarView?%s" % (a["id"], q), entetes=dict(auth(c), Prefer='outlook.timezone="UTC"'))
            if st != 200: continue
            for e in j.get("value", []):
                if e.get("isCancelled"): continue
                z = lambda x: dt.datetime.fromisoformat(x["dateTime"][:19]).replace(tzinfo=dt.timezone.utc).astimezone(ICI()).isoformat()
                out.append({"titre": e.get("subject") or "(sans titre)", "debut": z(e["start"]), "fin": z(e["end"]), "journee": e.get("isAllDay", False),
                            "lieu": (e.get("location") or {}).get("displayName", ""), "notes": (e.get("bodyPreview") or "")[:400], "ext": e["id"], "cal": a["id"], "compte": c["id"],
                            "modifiable": a["ecriture"] and e.get("type") in ("singleInstance", None)})
        else:
            from .agenda import lire_ics
            corps = ('<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><d:getetag/><c:calendar-data/></d:prop><c:filter><c:comp-filter name="VCALENDAR">'
                     '<c:comp-filter name="VEVENT"><c:time-range start="%s" end="%s"/></c:comp-filter></c:comp-filter></c:filter></c:calendar-query>') % (
                debut.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), fin.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            st, x = _dav(c, "REPORT", a["id"], corps, "1")
            if st >= 400: continue
            for r in ET.fromstring(x).findall("d:response", NS):
                cd = r.find(".//c:calendar-data", NS)
                if cd is None or not cd.text: continue
                href = r.find("d:href", NS).text; rec = "RRULE" in cd.text
                for e in lire_ics(cd.text, debut, fin, c["nom"], c["couleur"]):
                    e.update(ext=href, cal=a["id"], compte=c["id"], modifiable=not rec); e.pop("source", None); e.pop("couleur", None); out.append(e)
    return out


def ics_evenement(e, uid):
    f = lambda x: dt.datetime.fromisoformat(x).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    esc = lambda s: (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OS XIII//Calendrier//FR", "BEGIN:VEVENT", "UID:" + uid, "DTSTAMP:" + f(dt.datetime.now(dt.timezone.utc).isoformat())]
    if e.get("journee"): L += ["DTSTART;VALUE=DATE:" + e["debut"][:10].replace("-", ""), "DTEND;VALUE=DATE:" + e["fin"][:10].replace("-", "")]
    else: L += ["DTSTART:" + f(e["debut"]), "DTEND:" + f(e["fin"])]
    L += ["SUMMARY:" + esc(e["titre"]), "LOCATION:" + esc(e.get("lieu"))]
    if e.get("rappel") is not None: L += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:" + esc(e["titre"]), "TRIGGER:-PT%dM" % int(e["rappel"]), "END:VALARM"]
    return "\r\n".join(L + ["END:VEVENT", "END:VCALENDAR"]) + "\r\n"


def enregistrer(c, cal, e, ext=None):
    """Crée (ext=None) ou modifie un événement dans l'agenda distant. → identifiant distant"""
    if c["type"] == "google":
        corps = {"summary": e["titre"], "location": e.get("lieu", ""),
                 "start": {"date": e["debut"][:10]} if e.get("journee") else {"dateTime": e["debut"]}, "end": {"date": e["fin"][:10]} if e.get("journee") else {"dateTime": e["fin"]},
                 "reminders": {"useDefault": e.get("rappel") is None, **({"overrides": [{"method": "popup", "minutes": int(e["rappel"])}]} if e.get("rappel") is not None else {})}}
        base = "https://www.googleapis.com/calendar/v3/calendars/%s/events" % urllib.parse.quote(cal, safe="")
        st, j = requete("PATCH" if ext else "POST", base + ("/" + urllib.parse.quote(ext, safe="") if ext else ""), corps, auth(c))
        if st not in (200, 201): raise RuntimeError("Google a refusé : %s" % str(j)[:200])
        return j["id"]
    if c["type"] == "outlook":
        corps = {"subject": e["titre"], "location": {"displayName": e.get("lieu", "")}, "isAllDay": bool(e.get("journee")),
                 "start": {"dateTime": dt.datetime.fromisoformat(e["debut"]).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"},
                 "end": {"dateTime": dt.datetime.fromisoformat(e["fin"]).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"},
                 "isReminderOn": e.get("rappel") is not None, "reminderMinutesBeforeStart": int(e.get("rappel") or 0)}
        if e.get("journee"):
            corps["start"] = {"dateTime": e["debut"][:10] + "T00:00:00", "timeZone": "UTC"}; corps["end"] = {"dateTime": e["fin"][:10] + "T00:00:00", "timeZone": "UTC"}
        url = ("https://graph.microsoft.com/v1.0/me/events/" + ext) if ext else "https://graph.microsoft.com/v1.0/me/calendars/%s/events" % cal
        st, j = requete("PATCH" if ext else "POST", url, corps, auth(c))
        if st not in (200, 201): raise RuntimeError("Outlook a refusé : %s" % str(j)[:200])
        return j["id"]
    uid = (os.path.basename(ext)[:-4] if ext else uuid.uuid4().hex) ; href = ext or urllib.parse.urljoin(cal if cal.endswith("/") else cal + "/", uid + ".ics")
    st, j = _dav(c, "PUT", href, ics_evenement(e, uid), typ="text/calendar; charset=utf-8")
    if st not in (200, 201, 204): raise RuntimeError("le serveur CalDAV a refusé (%s)" % st)
    return href


def supprimer(c, cal, ext):
    if c["type"] == "google": st, _ = requete("DELETE", "https://www.googleapis.com/calendar/v3/calendars/%s/events/%s" % (urllib.parse.quote(cal, safe=""), urllib.parse.quote(ext, safe="")), entetes=auth(c))
    elif c["type"] == "outlook": st, _ = requete("DELETE", "https://graph.microsoft.com/v1.0/me/events/" + ext, entetes=auth(c))
    else: st, _ = _dav(c, "DELETE", ext)
    if st not in (200, 202, 204, 404, 410): raise RuntimeError("suppression refusée (%s)" % st)


# ------------------------------------------------------------------ cache (hors ligne)
def fichier_cache(c): return os.path.join(CACHE, "compte-%s.json" % c["id"])


def synchroniser(force=False):
    """Rafraîchit le cache de chaque compte (3 mois avant, 12 mois après). → erreurs"""
    os.makedirs(CACHE, exist_ok=True); err = []
    z = ICI(); a = dt.datetime.now(z) - dt.timedelta(days=92); b = dt.datetime.now(z) + dt.timedelta(days=366)
    for c in comptes():
        f = fichier_cache(c)
        if not force and os.path.exists(f) and time.time() - os.path.getmtime(f) < 900: continue
        try:
            E = recuperer(c, a, b); json.dump(E, open(f, "w"))
        except Exception as e:
            err.append("%s : %s" % (c.get("nom"), e))
    return err


def en_cache(debut, fin):
    L = []
    for c in comptes():
        try: E = json.load(open(fichier_cache(c)))
        except Exception: continue
        for e in E:
            try:
                if dt.datetime.fromisoformat(e["debut"]) < fin and dt.datetime.fromisoformat(e["fin"]) > debut: L.append(dict(e, source=c["nom"], couleur=c.get("couleur", "#6aa8ff")))
            except Exception: pass
    return L
