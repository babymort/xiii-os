# OS XIII — zone de notification (StatusNotifierItem) : icônes de Steam, Discord, Companion… dans la barre des tâches.
# Hôte + surveillant org.kde.StatusNotifierWatcher, menus com.canonical.dbusmenu.
# Application développée par Matthieu Lamotte.
from gi.repository import Gio, GLib, Gtk, Gdk, GdkPixbuf
from .ui import *

WATCHER_XML = """<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
<method name="RegisterStatusNotifierHost"><arg type="s" direction="in"/></method>
<property name="RegisteredStatusNotifierItems" type="as" access="read"/>
<property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
<property name="ProtocolVersion" type="i" access="read"/>
<signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
<signal name="StatusNotifierItemUnregistered"><arg type="s"/></signal>
<signal name="StatusNotifierHostRegistered"/>
</interface></node>"""

class Zone:
    """rappel() appelé quand la liste change ; .items = {cle: dict(bus, chemin, titre, icone, pixbuf, menu)}"""
    def __init__(self, rappel):
        self.rappel = rappel; self.items = {}; self.conn = None
        self.info = Gio.DBusNodeInfo.new_for_xml(WATCHER_XML).interfaces[0]
        Gio.bus_own_name(Gio.BusType.SESSION, "org.kde.StatusNotifierWatcher", Gio.BusNameOwnerFlags.REPLACE | Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT,
                         self._acquis, None, None)

    def _acquis(self, conn, nom):
        self.conn = conn
        conn.register_object("/StatusNotifierWatcher", self.info, self._appel, self._prop, None)
        conn.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged", "/org/freedesktop/DBus", None,
                              Gio.DBusSignalFlags.NONE, self._proprio, None)
        self._signal("StatusNotifierHostRegistered", None)

    def _signal(self, nom, v):
        try: self.conn.emit_signal(None, "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher", nom, v)
        except Exception: pass

    def _prop(self, conn, emetteur, chemin, iface, nom):
        if nom == "RegisteredStatusNotifierItems": return GLib.Variant("as", list(self.items))
        if nom == "IsStatusNotifierHostRegistered": return GLib.Variant("b", True)
        if nom == "ProtocolVersion": return GLib.Variant("i", 0)

    def _appel(self, conn, emetteur, chemin, iface, methode, params, inv):
        if methode == "RegisterStatusNotifierItem":
            (svc,) = params.unpack()
            bus, obj = (emetteur, svc) if svc.startswith("/") else (svc, "/StatusNotifierItem")
            cle = bus + obj
            if cle not in self.items:
                self.items[cle] = dict(bus=bus, chemin=obj, titre="", icone=None, pixbuf=None, menu=None)
                self._lire(cle)
                self._signal("StatusNotifierItemRegistered", GLib.Variant("(s)", (cle,)))
                conn.signal_subscribe(bus, "org.kde.StatusNotifierItem", None, obj, None, Gio.DBusSignalFlags.NONE,
                                      lambda *a, c=cle: self._lire(c), None)
        inv.return_value(None)

    def _proprio(self, conn, em, ch, iface, sig, params, *_):
        nom, ancien, nouveau = params.unpack()
        if nouveau: return
        for cle in [k for k, v in self.items.items() if v["bus"] == nom]:
            self.items.pop(cle, None); self._signal("StatusNotifierItemUnregistered", GLib.Variant("(s)", (cle,)))
        self.rappel()

    def _lire(self, cle):
        it = self.items.get(cle)
        if not it: return
        def fini(c, res):
            try:
                v = c.call_finish(res).unpack()[0]
            except Exception:
                return
            it["titre"] = v.get("Title") or v.get("Id") or ""
            it["sid"] = v.get("Id") or v.get("Title") or it.get("bus", "")
            it["icone"] = v.get("IconName") or None
            it["theme"] = v.get("IconThemePath") or ""
            it["menu"] = v.get("Menu")
            it["statut"] = v.get("Status", "Active")
            pm = v.get("IconPixmap")
            it["pixbuf"] = None
            if pm:
                w, h, data = max(pm, key=lambda p: p[0])
                data = bytes(data)
                rgba = bytearray(len(data))
                rgba[0::4] = data[1::4]; rgba[1::4] = data[2::4]; rgba[2::4] = data[3::4]; rgba[3::4] = data[0::4]   # ARGB → RGBA
                try:
                    it["pixbuf"] = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(rgba)), GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)
                except Exception:
                    pass
            self.rappel()
        self.conn.call(it["bus"], it["chemin"], "org.freedesktop.DBus.Properties", "GetAll", GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)),
                       GLib.VariantType.new("(a{sv})"), Gio.DBusCallFlags.NONE, 3000, None, fini)

    # ------------------------------------------------------------ actions
    def activer(self, cle):
        it = self.items.get(cle)
        if it: self.conn.call(it["bus"], it["chemin"], "org.kde.StatusNotifierItem", "Activate", GLib.Variant("(ii)", (0, 0)), None, Gio.DBusCallFlags.NONE, 2000, None, None)

    def menu(self, cle, parent):
        it = self.items.get(cle)
        if not it: return
        if not it.get("menu"):
            self.conn.call(it["bus"], it["chemin"], "org.kde.StatusNotifierItem", "ContextMenu", GLib.Variant("(ii)", (0, 0)), None, Gio.DBusCallFlags.NONE, 2000, None, None)
            return
        def fini(c, res):
            try:
                rev, (rid, props, enfants) = c.call_finish(res).unpack()
            except Exception:
                return
            items = []
            def ajouter(liste, prof=0):
                for e in liste:
                    i, p, sous = e
                    if not p.get("visible", True): continue
                    if p.get("type") == "separator": items.append(None); continue
                    t = (p.get("label") or "").replace("_", "")
                    if sous and prof < 2:
                        ajouter(sous, prof + 1); continue
                    if t:
                        items.append(("chevron-right" if prof else "circle-dot" if p.get("toggle-state") == 1 else "dot", ("    " * prof) + t,
                                      (lambda i=i: self.conn.call(it["bus"], it["menu"], "com.canonical.dbusmenu", "Event",
                                                                  GLib.Variant("(isvu)", (i, "clicked", GLib.Variant("s", ""), 0)), None, Gio.DBusCallFlags.NONE, 2000, None, None))))
            ajouter(enfants)
            if items: popover_menu(parent, items)
        self.conn.call(it["bus"], it["menu"], "com.canonical.dbusmenu", "AboutToShow", GLib.Variant("(i)", (0,)), None, Gio.DBusCallFlags.NONE, 1000, None, None)
        self.conn.call(it["bus"], it["menu"], "com.canonical.dbusmenu", "GetLayout", GLib.Variant("(iias)", (0, -1, [])),
                       GLib.VariantType.new("(u(ia{sv}av))"), Gio.DBusCallFlags.NONE, 3000, None, fini)

    def bouton(self, cle, taille=18):
        it = self.items[cle]
        b = Gtk.Button(); b.add_css_class("tb"); b.add_css_class("tb-notif"); b.set_tooltip_text(it.get("titre") or "")
        if it.get("pixbuf"):
            im = Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(it["pixbuf"]))
        elif it.get("icone"):
            if it.get("theme"):
                Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(it["theme"])
            im = Gtk.Image.new_from_icon_name(it["icone"])
        else:
            im = Gtk.Image.new_from_icon_name("application-x-executable")
        im.set_pixel_size(taille); b.set_child(im)
        b.connect("clicked", lambda *_: self.activer(cle))
        clic_droit(b, lambda: self.menu(cle, b))
        return b
