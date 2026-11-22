# OS XIII — serveur de notifications (org.freedesktop.Notifications) : remplace mako.
# Les notifications alimentent les bulles (bas à droite) et le volet de notifications.
# Application développée par Matthieu Lamotte.
import time
from gi.repository import Gio, GLib, GdkPixbuf

XML = """<node><interface name="org.freedesktop.Notifications">
<method name="Notify"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/>
<arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="as" direction="in"/>
<arg type="a{sv}" direction="in"/><arg type="i" direction="in"/><arg type="u" direction="out"/></method>
<method name="CloseNotification"><arg type="u" direction="in"/></method>
<method name="GetCapabilities"><arg type="as" direction="out"/></method>
<method name="GetServerInformation"><arg type="s" direction="out"/><arg type="s" direction="out"/>
<arg type="s" direction="out"/><arg type="s" direction="out"/></method>
<signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
<signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal>
</interface></node>"""
CHEMIN = "/org/freedesktop/Notifications"
IFACE = "org.freedesktop.Notifications"

class Notification:
    def __init__(self, nid, app, icone, titre, corps, actions, hints, delai):
        self.id = nid; self.app = app or "Système"; self.icone = icone; self.titre = titre; self.corps = corps
        self.actions = [(actions[i], actions[i + 1]) for i in range(0, len(actions) - 1, 2)]
        self.hints = hints; self.delai = delai; self.heure = time.time()
        self.urgence = int(hints.get("urgency", 1)) if isinstance(hints.get("urgency", 1), int) else 1
        self.pixbuf = None
        data = hints.get("image-data") or hints.get("image_data") or hints.get("icon_data")
        if data:
            try:
                w, h, rs, alpha, bps, ch, px = data
                self.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(px)), GdkPixbuf.Colorspace.RGB, alpha, bps, w, h, rs)
            except Exception:
                self.pixbuf = None
        self.image = hints.get("image-path") or hints.get("image_path") or ""

class Serveur:
    """rappels : nouvelle(n, remplacee:bool), fermee(nid)"""
    def __init__(self, nouvelle, fermee):
        self.nouvelle = nouvelle; self.fermee = fermee
        self.liste = {}; self._next = 1; self.conn = None
        self.info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
        Gio.bus_own_name(Gio.BusType.SESSION, IFACE,
                         Gio.BusNameOwnerFlags.REPLACE | Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT,
                         self._acquis, None, None)

    def _acquis(self, conn, nom):
        self.conn = conn
        conn.register_object(CHEMIN, self.info, self._appel, None, None)

    def _appel(self, conn, emetteur, chemin, iface, methode, params, inv):
        try:
            if methode == "Notify":
                app, remp, icone, titre, corps, actions, hints, delai = params.unpack()
                nid = remp if remp and remp in self.liste else self._next
                if nid == self._next: self._next += 1
                n = Notification(nid, app, icone, titre, corps, list(actions), dict(hints), delai)
                self.liste[nid] = n
                self.nouvelle(n, bool(remp and remp == nid))
                if not (remp and remp == nid):
                    try:
                        from . import sons
                        h = {k: (v.unpack() if hasattr(v, "unpack") else v) for k, v in dict(hints).items()}
                        sons.pour_notification(app, icone, titre, h)
                    except Exception: pass
                inv.return_value(GLib.Variant("(u)", (nid,)))
            elif methode == "CloseNotification":
                (nid,) = params.unpack()
                self.fermer(nid, 3)
                inv.return_value(None)
            elif methode == "GetCapabilities":
                inv.return_value(GLib.Variant("(as)", (["body", "actions", "body-markup", "icon-static", "persistence"],)))
            elif methode == "GetServerInformation":
                inv.return_value(GLib.Variant("(ssss)", ("OS XIII", "Matthieu Lamotte", "1.0", "1.2")))
        except Exception as e:
            inv.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(e))

    def fermer(self, nid, raison=2):
        if self.liste.pop(nid, None) is not None:
            self._signal("NotificationClosed", GLib.Variant("(uu)", (nid, raison)))
            self.fermee(nid)

    def action(self, nid, cle):
        self._signal("ActionInvoked", GLib.Variant("(us)", (nid, cle)))
        self.fermer(nid, 2)

    def tout_effacer(self):
        for nid in list(self.liste):
            self.fermer(nid, 2)

    def _signal(self, nom, v):
        if self.conn:
            try:
                self.conn.emit_signal(None, CHEMIN, IFACE, nom, v)
            except Exception:
                pass

    def triees(self):
        return sorted(self.liste.values(), key=lambda n: -n.heure)
