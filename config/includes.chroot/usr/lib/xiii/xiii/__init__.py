# OS XIII — applications du bureau
# rapport de plantage pour toutes les applications XIII (voir rapport.py)
try:
    from . import rapport as _rapport
    _rapport.installer()
except Exception:
    pass
