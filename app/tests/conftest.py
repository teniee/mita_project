import os
import sys
import types

os.environ.setdefault("FIREBASE_JSON", "{}")

dummy = types.ModuleType("firebase_admin")
dummy._apps = []
dummy.credentials = types.SimpleNamespace(ApplicationDefault=lambda: None)
dummy.initialize_app = lambda cred=None: None

dummy.firestore = types.SimpleNamespace(
    client=lambda: types.SimpleNamespace(collection=lambda *a, **k: None)
)
dummy.messaging = types.SimpleNamespace(
    Message=lambda **kw: types.SimpleNamespace(**kw),
    Notification=lambda **kw: types.SimpleNamespace(**kw),
    send=lambda msg: "ok",
)

sys.modules.setdefault("firebase_admin", dummy)
sys.modules.setdefault("firebase_admin.credentials", dummy.credentials)
sys.modules.setdefault("firebase_admin.firestore", dummy.firestore)
