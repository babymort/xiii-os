# OS XIII — accès au runtime NDI (libndi, installé à part : licence NDI) : recherche des sources et réception vidéo.
# Utilisé par le retour plateau (xiii-retour) et, plus tard, par TALLY XIII.
# NDI® est une marque déposée de Vizrt NDI AB.
# Application développée par Matthieu Lamotte.
import ctypes, ctypes.util, os, glob

NOMS = ["libndi.so.6", "/usr/local/lib/libndi.so.6", "/usr/lib/libndi.so.6", "libndi.so.5", "/usr/local/lib/libndi.so.5", "libndi.so"]


class Source(ctypes.Structure):
    _fields_ = [("p_ndi_name", ctypes.c_char_p), ("p_url_address", ctypes.c_char_p)]


class FindCreate(ctypes.Structure):
    _fields_ = [("show_local_sources", ctypes.c_bool), ("p_groups", ctypes.c_char_p), ("p_extra_ips", ctypes.c_char_p)]


class RecvCreateV3(ctypes.Structure):
    _fields_ = [("source_to_connect_to", Source), ("color_format", ctypes.c_int), ("bandwidth", ctypes.c_int),
                ("allow_video_fields", ctypes.c_bool), ("p_ndi_recv_name", ctypes.c_char_p)]


class VideoFrameV2(ctypes.Structure):
    _fields_ = [("xres", ctypes.c_int), ("yres", ctypes.c_int), ("FourCC", ctypes.c_uint32), ("frame_rate_N", ctypes.c_int), ("frame_rate_D", ctypes.c_int),
                ("picture_aspect_ratio", ctypes.c_float), ("frame_format_type", ctypes.c_int), ("timecode", ctypes.c_int64),
                ("p_data", ctypes.POINTER(ctypes.c_uint8)), ("line_stride_in_bytes", ctypes.c_int), ("p_metadata", ctypes.c_char_p), ("timestamp", ctypes.c_int64)]


class AudioFrameV2(ctypes.Structure):
    _fields_ = [("sample_rate", ctypes.c_int), ("no_channels", ctypes.c_int), ("no_samples", ctypes.c_int), ("timecode", ctypes.c_int64),
                ("p_data", ctypes.POINTER(ctypes.c_float)), ("channel_stride_in_bytes", ctypes.c_int), ("p_metadata", ctypes.c_char_p), ("timestamp", ctypes.c_int64)]


class Tally(ctypes.Structure):
    _fields_ = [("on_program", ctypes.c_bool), ("on_preview", ctypes.c_bool)]


FRAME_AUCUNE, FRAME_VIDEO, FRAME_AUDIO, FRAME_META, FRAME_ERREUR, FRAME_CHANGEMENT = 0, 1, 2, 3, 4, 100
COULEUR_BGRX_BGRA = 0
BANDE_LEGERE, BANDE_PLEINE = 0, 100

_lib = None


def chemin_runtime():
    env = os.environ.get("NDI_RUNTIME_DIR_V6")
    cands = ([os.path.join(env, "libndi.so.6")] if env else []) + NOMS
    for n in cands:
        if n.startswith("/") and os.path.exists(n): return n
        if not n.startswith("/"):
            for d in ("/usr/local/lib", "/usr/lib", "/usr/lib/x86_64-linux-gnu"):
                if os.path.exists(os.path.join(d, n)): return os.path.join(d, n)
    return None


def disponible():
    return chemin_runtime() is not None


def version():
    try:
        return lib().NDIlib_version().decode()
    except Exception:
        return None


def lib():
    global _lib
    if _lib: return _lib
    p = chemin_runtime()
    if not p: raise OSError("Runtime NDI absent")
    L = ctypes.CDLL(p)
    L.NDIlib_initialize.restype = ctypes.c_bool
    L.NDIlib_version.restype = ctypes.c_char_p
    L.NDIlib_find_create_v2.restype = ctypes.c_void_p; L.NDIlib_find_create_v2.argtypes = [ctypes.POINTER(FindCreate)]
    L.NDIlib_find_wait_for_sources.restype = ctypes.c_bool; L.NDIlib_find_wait_for_sources.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    L.NDIlib_find_get_current_sources.restype = ctypes.POINTER(Source); L.NDIlib_find_get_current_sources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    L.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]
    L.NDIlib_recv_create_v3.restype = ctypes.c_void_p; L.NDIlib_recv_create_v3.argtypes = [ctypes.POINTER(RecvCreateV3)]
    L.NDIlib_recv_capture_v2.restype = ctypes.c_int
    L.NDIlib_recv_capture_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(VideoFrameV2), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    L.NDIlib_recv_free_video_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(VideoFrameV2)]
    L.NDIlib_recv_free_audio_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(AudioFrameV2)]
    L.NDIlib_recv_destroy.argtypes = [ctypes.c_void_p]
    L.NDIlib_recv_set_tally.restype = ctypes.c_bool; L.NDIlib_recv_set_tally.argtypes = [ctypes.c_void_p, ctypes.POINTER(Tally)]
    L.NDIlib_recv_get_no_connections.restype = ctypes.c_int; L.NDIlib_recv_get_no_connections.argtypes = [ctypes.c_void_p]
    if not L.NDIlib_initialize():
        raise OSError("Ce processeur n'est pas pris en charge par NDI")
    _lib = L
    return L


class Recherche:
    """Recherche des sources NDI du réseau (garder l'objet vivant : la liste se complète au fil du temps)."""
    def __init__(self, ips_extra=None):
        c = FindCreate(True, None, ips_extra.encode() if ips_extra else None)
        self.inst = lib().NDIlib_find_create_v2(ctypes.byref(c))

    def sources(self, attente_ms=0):
        if attente_ms: lib().NDIlib_find_wait_for_sources(self.inst, attente_ms)
        n = ctypes.c_uint32(0)
        p = lib().NDIlib_find_get_current_sources(self.inst, ctypes.byref(n))
        return [(p[i].p_ndi_name.decode("utf-8", "replace"), (p[i].p_url_address or b"").decode()) for i in range(n.value)]

    def fermer(self):
        if self.inst: lib().NDIlib_find_destroy(self.inst); self.inst = None


class Recepteur:
    """Réception d'une source : images BGRA (non prémultipliées)."""
    def __init__(self, nom, url="", leger=False, nom_recepteur="OS XIII"):
        src = Source(nom.encode(), url.encode() if url else None)
        c = RecvCreateV3(src, COULEUR_BGRX_BGRA, BANDE_LEGERE if leger else BANDE_PLEINE, False, nom_recepteur.encode())
        self.inst = lib().NDIlib_recv_create_v3(ctypes.byref(c))
        if not self.inst: raise OSError("Impossible de se connecter à la source")
        self.f = VideoFrameV2()

    def image(self, attente_ms=200):
        """(largeur, hauteur, pas, octets) ou None."""
        t = lib().NDIlib_recv_capture_v2(self.inst, ctypes.byref(self.f), None, None, attente_ms)
        if t != FRAME_VIDEO: return None
        f = self.f
        try:
            h, pas = f.yres, f.line_stride_in_bytes
            return (f.xres, h, pas, ctypes.string_at(f.p_data, pas * h))
        finally:
            lib().NDIlib_recv_free_video_v2(self.inst, ctypes.byref(f))

    def capturer(self, attente_ms=200):
        """Image et son : ("video", (l, h, pas, octets)) | ("audio", [crête dBFS par canal]) | (None, None)."""
        a = getattr(self, "a", None) or AudioFrameV2(); self.a = a
        t = lib().NDIlib_recv_capture_v2(self.inst, ctypes.byref(self.f), ctypes.byref(a), None, attente_ms)
        if t == FRAME_VIDEO:
            f = self.f
            try: return "video", (f.xres, f.yres, f.line_stride_in_bytes, ctypes.string_at(f.p_data, f.line_stride_in_bytes * f.yres))
            finally: lib().NDIlib_recv_free_video_v2(self.inst, ctypes.byref(f))
        if t == FRAME_AUDIO:
            try:
                import math, array
                n, pas = a.no_samples, a.channel_stride_in_bytes // 4; base = ctypes.cast(a.p_data, ctypes.POINTER(ctypes.c_float)); N = []
                for c in range(min(a.no_channels, 8)):
                    buf = (ctypes.c_float * n).from_address(ctypes.addressof(base.contents) + c * pas * 4)
                    pk = max((abs(x) for x in array.array("f", bytes(buf))[::4]), default=0.0)
                    N.append(20 * math.log10(pk) if pk > 1e-6 else -90.0)
                return "audio", N
            finally: lib().NDIlib_recv_free_audio_v2(self.inst, ctypes.byref(a))
        return None, None

    def tally(self, programme=False, preview=False):
        t = Tally(programme, preview); lib().NDIlib_recv_set_tally(self.inst, ctypes.byref(t))

    def connexions(self):
        return lib().NDIlib_recv_get_no_connections(self.inst)

    def fermer(self):
        if self.inst: lib().NDIlib_recv_destroy(self.inst); self.inst = None
