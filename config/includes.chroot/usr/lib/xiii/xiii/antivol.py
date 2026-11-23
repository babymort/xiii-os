# OS XIII — Antivol XIII : si l'ordinateur est perdu ou volé, on lui écrit depuis son téléphone (application gratuite ntfy,
# ou simple page web), par un canal privé dont seul vous avez l'adresse (24 caractères aléatoires) :
#   « verrouiller »          verrouille la session tout de suite
#   « message <texte> »      affiche le texte en plein écran (ex. « Ce PC est perdu, appelez le 06… »)
#   « sonner »               fait sonner l'ordinateur à fond pendant 30 s
#   « localiser »            renvoie la position approximative (adresse Internet + réseaux Wi-Fi visibles) avec un lien de carte
#   « etat »                 batterie, réseau, utilisateur connecté
# Serveur : ntfy.sh (public, gratuit) ou le vôtre (ntfy auto-hébergé, sur un NAS par ex.).
# Service léger (sans GTK) lancé par le bureau quand l'antivol est activé. Application développée par Matthieu Lamotte.
import os, sys, json, time, secrets, subprocess, urllib.request, urllib.parse, socket

CONF = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "xiii", "reglages.json")
TITRE = "OS XIII - %s" % "".join(ch for ch in socket.gethostname() if ord(ch) < 128)


def cfg():
    try: return json.load(open(CONF))
    except Exception: return {}


def nouveau_canal():
    return "xiii-" + secrets.token_urlsafe(18).replace("_", "").replace("-", "")[:24]


def serveur(c=None): return ((c or cfg()).get("antivol_serveur") or "https://ntfy.sh").rstrip("/")


def envoyer(texte, c=None, titre=TITRE, prio="high", clic=None):
    c = c or cfg()
    h = {"Title": titre, "Priority": prio, "Tags": "computer", "User-Agent": "OS-XIII"}
    if clic: h["Click"] = clic
    req = urllib.request.Request("%s/%s" % (serveur(c), c["antivol_canal"]), data=texte.encode(), headers=h, method="POST")
    urllib.request.urlopen(req, timeout=20).read()


def localiser():
    L = []
    try:
        j = json.load(urllib.request.urlopen(urllib.request.Request("https://ipapi.co/json/", headers={"User-Agent": "OS-XIII"}), timeout=15))
        lien = "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=13/%s/%s" % (j.get("latitude"), j.get("longitude"), j.get("latitude"), j.get("longitude"))
        L.append("Position approximative (adresse Internet) : %s, %s, %s — opérateur %s" % (j.get("city"), j.get("region"), j.get("country_name"), j.get("org")))
        L.append("Carte : " + lien)
    except Exception as e:
        lien = None; L.append("Position par Internet indisponible (%s)" % e)
    try:
        o = subprocess.run(["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL", "device", "wifi", "list"], capture_output=True, text=True, timeout=20).stdout
        W = [l.replace("\\:", ":") for l in o.splitlines()[:8]]
        if W: L.append("Wi-Fi visibles (à donner à la police / l'assurance) : " + " · ".join(W))
    except Exception: pass
    try: L.append("Adresse locale : " + subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.strip())
    except Exception: pass
    return "\n".join(L), lien


def etat():
    L = []
    try:
        for b in os.listdir("/sys/class/power_supply"):
            if b.startswith("BAT"): L.append("Batterie : %s %% (%s)" % (open("/sys/class/power_supply/%s/capacity" % b).read().strip(), open("/sys/class/power_supply/%s/status" % b).read().strip()))
    except Exception: pass
    try: L.append("Réseau : " + subprocess.run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"], capture_output=True, text=True, timeout=10).stdout.strip().replace("\n", ", "))
    except Exception: pass
    L.append("Session : %s, allumé depuis %d min" % (os.environ.get("USER", "?"), float(open("/proc/uptime").read().split()[0]) // 60))
    return "\n".join(L)


def message_plein_ecran(t):
    code = ("import sys; sys.path.insert(0, '/usr/lib/xiii'); import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk;"
            "a = Gtk.Application(application_id='fr.xiii.antivol.message');"
            "def go(a):\n w = Gtk.ApplicationWindow(application=a); w.fullscreen(); l = Gtk.Label(label=%r, wrap=True, justify=2); l.add_css_class('title-1');"
            " w.set_child(l); w.present()\na.connect('activate', go); a.run([])") % t
    subprocess.Popen(["python3", "-c", code], start_new_session=True)


def agir(cmd):
    c = cfg(); t = cmd.strip(); k = t.lower()
    if k.startswith("verrouill") or k == "lock":
        subprocess.Popen(["swaylock", "-f"], start_new_session=True); envoyer("Session verrouillée ✓", c)
    elif k.startswith("message"):
        msg = t[7:].strip(" :") or "Cet ordinateur a été perdu. Merci de contacter son propriétaire."
        message_plein_ecran(msg); envoyer("Message affiché ✓", c)
    elif k.startswith("sonner"):
        subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"]); subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "1.0"])
        son = "/usr/share/sounds/XIII/stereo/alarm-clock-elapsed.oga"
        son = son if os.path.exists(son) else "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
        fin = time.time() + 30
        while time.time() < fin: subprocess.run(["pw-play", son], timeout=10)
        envoyer("Sonnerie terminée", c)
    elif k.startswith("locali") or k == "ou":
        txt, lien = localiser(); envoyer(txt, c, clic=lien)
    elif k.startswith("etat") or k.startswith("état"):
        envoyer(etat(), c)
    else:
        envoyer("Commandes : verrouiller · message <texte> · sonner · localiser · etat", c, prio="default")


def service():
    """Écoute le canal (connexion longue, reprise automatique)."""
    depuis = str(int(time.time()))
    while True:
        c = cfg()
        if not c.get("antivol") or not c.get("antivol_canal"): return 0
        try:
            u = "%s/%s/json?since=%s" % (serveur(c), c["antivol_canal"], depuis)
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "OS-XIII"}), timeout=600) as r:
                for l in r:
                    try: m = json.loads(l)
                    except ValueError: continue
                    if m.get("event") != "message": continue
                    depuis = m.get("id") or depuis
                    if (m.get("title") or "").startswith("OS XIII"): continue       # nos propres réponses
                    try: agir(m.get("message") or "")
                    except Exception as e:
                        try: envoyer("Erreur : %s" % e, c)
                        except Exception: pass
        except Exception:
            time.sleep(20)


def main():
    a = sys.argv[1:]
    if a[:1] == ["--canal"]: print(nouveau_canal()); return
    if a[:1] == ["--essai"]:
        envoyer("Antivol XIII actif sur %s ✓ — écrivez « etat » pour essayer." % socket.gethostname(), prio="default"); return
    sys.exit(service() or 0)
