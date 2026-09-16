"""Read-only AC shared-memory prefixes; see README for ABI references."""

import ctypes
import sys


class TelemetryUnavailable(RuntimeError):
    """AC is absent, inactive, stale, or cannot provide a usable snapshot."""


class Physics(ctypes.LittleEndianStructure):
    _pack_ = 4
    _fields_ = [("packetId", ctypes.c_int32), ("gas", ctypes.c_float),
                ("brake", ctypes.c_float), ("fuel", ctypes.c_float),
                ("gear", ctypes.c_int32), ("rpms", ctypes.c_int32),
                ("steerAngle", ctypes.c_float), ("speedKmh", ctypes.c_float)]


class Graphics(ctypes.LittleEndianStructure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int32), ("status", ctypes.c_int32),
        ("session", ctypes.c_int32),
        ("currentTime", ctypes.c_uint16 * 15), ("lastTime", ctypes.c_uint16 * 15),
        ("bestTime", ctypes.c_uint16 * 15), ("split", ctypes.c_uint16 * 15),
        ("completedLaps", ctypes.c_int32), ("position", ctypes.c_int32),
        ("iCurrentTime", ctypes.c_int32), ("iLastTime", ctypes.c_int32),
        ("iBestTime", ctypes.c_int32), ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float), ("isInPit", ctypes.c_int32),
        ("currentSectorIndex", ctypes.c_int32), ("lastSectorTime", ctypes.c_int32),
        ("numberOfLaps", ctypes.c_int32), ("tyreCompound", ctypes.c_uint16 * 33),
        ("replayTimeMultiplier", ctypes.c_float),
        ("normalizedCarPosition", ctypes.c_float)]


class Static(ctypes.LittleEndianStructure):
    _pack_ = 4
    _fields_ = [("smVersion", ctypes.c_uint16 * 15),
                ("acVersion", ctypes.c_uint16 * 15),
                ("numberOfSessions", ctypes.c_int32), ("numCars", ctypes.c_int32),
                ("carModel", ctypes.c_uint16 * 33), ("track", ctypes.c_uint16 * 33)]


def text_field(value):
    # type: (object) -> str
    raw = ctypes.string_at(ctypes.addressof(value), ctypes.sizeof(value))
    return raw.decode("utf-16-le", errors="replace").split("\0", 1)[0]


class WindowsMapping(object):
    """Open an existing named mapping; never create or write game memory."""

    def __init__(self, name, size):
        # type: (str, int) -> None
        if sys.platform != "win32":
            raise TelemetryUnavailable("Assetto Corsa shared memory requires Windows")
        self._handle = None
        self._view = None
        self._size = size
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        api.OpenFileMappingW.restype = ctypes.c_void_p
        api.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
        api.MapViewOfFile.restype = ctypes.c_void_p
        api.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        api.UnmapViewOfFile.restype = ctypes.c_int
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        api.CloseHandle.restype = ctypes.c_int
        self._api = api
        self._handle = api.OpenFileMappingW(4, False, name)  # FILE_MAP_READ
        if not self._handle:
            raise TelemetryUnavailable("Cannot open {0} (Windows error {1}); start an AC driving session".format(
                name, ctypes.get_last_error()))
        self._view = api.MapViewOfFile(self._handle, 4, 0, 0, size)
        if not self._view:
            error = ctypes.get_last_error()
            self.close()
            raise TelemetryUnavailable("Cannot map {0} (Windows error {1})".format(name, error))

    def read(self):
        # type: () -> bytes
        if not self._view:
            raise TelemetryUnavailable("Shared memory is closed")
        return ctypes.string_at(self._view, self._size)

    def close(self):
        # type: () -> None
        if self._view:
            self._api.UnmapViewOfFile(self._view)
            self._view = None
        if self._handle:
            self._api.CloseHandle(self._handle)
            self._handle = None
