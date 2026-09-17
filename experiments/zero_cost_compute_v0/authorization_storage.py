from __future__ import annotations

import ctypes
import json
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from authorization_core import AuthorizationRecord, AuthorizationState


class MemoryCredentialVault:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def put(self, name: str, secret: str) -> str:
        if not name or not secret:
            raise ValueError("credential name and secret are required")
        ref = f"memvault:{uuid.uuid4().hex}"
        self._values[ref] = secret
        return ref

    def get(self, ref: str) -> str:
        try:
            return self._values[ref]
        except KeyError as exc:
            raise KeyError("credential reference not found") from exc

    def delete(self, ref: str) -> None:
        self._values.pop(ref, None)

    def exists(self, ref: str) -> bool:
        return ref in self._values


class JsonAuthorizationRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("authorization registry must contain an object")
        return data

    def _serialize(self, record: AuthorizationRecord) -> dict[str, Any]:
        data = asdict(record)
        data["state"] = record.state.value
        data["scopes"] = list(record.scopes)
        return data

    def _deserialize(self, data: dict[str, Any]) -> AuthorizationRecord:
        values = dict(data)
        values["state"] = AuthorizationState(values["state"])
        values["scopes"] = tuple(values.get("scopes", ()))
        return AuthorizationRecord(**values)

    def get(self, provider_id: str) -> AuthorizationRecord | None:
        data = self._read().get(provider_id)
        if data is None:
            return None
        if not isinstance(data, dict):
            raise ValueError("authorization registry record must contain an object")
        return self._deserialize(data)

    def put(self, record: AuthorizationRecord) -> None:
        data = self._read()
        data[record.provider_id] = self._serialize(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.path)


class WindowsCredentialVault:
    """Windows Credential Manager-backed vault for production secrets.

    Construction is cross-platform so remote Linux tests can validate wiring.
    Actual credential operations fail closed outside Windows.
    """

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    def __init__(self, prefix: str = "maibao-auth") -> None:
        if not prefix:
            raise ValueError("credential prefix is required")
        self.prefix = prefix.rstrip("/")

    def _require_windows(self) -> None:
        if os.name != "nt":
            raise RuntimeError("Windows Credential Manager is only available on Windows")

    def _target_from_name(self, name: str) -> str:
        if not name:
            raise ValueError("credential name is required")
        return f"{self.prefix}/{name.lstrip('/')}"

    def _target_from_ref(self, ref: str) -> str:
        prefix = "wincred:"
        if not ref.startswith(prefix):
            raise ValueError("invalid Windows credential reference")
        target = ref[len(prefix):]
        if not target.startswith(self.prefix + "/"):
            raise ValueError("credential reference belongs to a different vault")
        return target

    @staticmethod
    def _credential_types():
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class CREDENTIALW(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        return wintypes, CREDENTIALW

    def _api(self):
        self._require_windows()
        wintypes, credential_type = self._credential_types()
        advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        cred_write = advapi32.CredWriteW
        cred_write.argtypes = [ctypes.POINTER(credential_type), wintypes.DWORD]
        cred_write.restype = wintypes.BOOL
        cred_read = advapi32.CredReadW
        cred_read.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(credential_type)),
        ]
        cred_read.restype = wintypes.BOOL
        cred_delete = advapi32.CredDeleteW
        cred_delete.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        cred_delete.restype = wintypes.BOOL
        cred_free = advapi32.CredFree
        cred_free.argtypes = [ctypes.c_void_p]
        cred_free.restype = None
        return credential_type, cred_write, cred_read, cred_delete, cred_free

    def put(self, name: str, secret: str) -> str:
        self._require_windows()
        if not secret:
            raise ValueError("credential secret is required")
        target = self._target_from_name(name)
        credential_type, cred_write, _, _, _ = self._api()
        encoded = secret.encode("utf-16-le")
        blob = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
        credential = credential_type()
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.CredentialBlobSize = len(encoded)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "maibao"
        if not cred_write(ctypes.byref(credential), 0):
            raise OSError(ctypes.get_last_error(), "CredWriteW failed")
        return f"wincred:{target}"

    def get(self, ref: str) -> str:
        self._require_windows()
        target = self._target_from_ref(ref)
        credential_type, _, cred_read, _, cred_free = self._api()
        pointer = ctypes.POINTER(credential_type)()
        if not cred_read(target, self.CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == self.ERROR_NOT_FOUND:
                raise KeyError("credential reference not found")
            raise OSError(error, "CredReadW failed")
        try:
            credential = pointer.contents
            raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return raw.decode("utf-16-le")
        finally:
            cred_free(pointer)

    def delete(self, ref: str) -> None:
        self._require_windows()
        target = self._target_from_ref(ref)
        _, _, _, cred_delete, _ = self._api()
        if not cred_delete(target, self.CRED_TYPE_GENERIC, 0):
            error = ctypes.get_last_error()
            if error != self.ERROR_NOT_FOUND:
                raise OSError(error, "CredDeleteW failed")

    def exists(self, ref: str) -> bool:
        try:
            self.get(ref)
            return True
        except KeyError:
            return False
