"""Minimal HID++ 2.0 client for diverting the MX Master thumb button.

The thumb ("gesture") button is not reported as a normal HID mouse button.
Instead it is a Logitech "reprogrammable control" (feature 0x1B04) that, once
diverted, is announced through HID++ notifications.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import hid

log = logging.getLogger(__name__)

LOGITECH_VENDOR_ID = 0x046D
HIDPP_USAGE_PAGE = 0xFF00
HIDPP_LONG_USAGE = 0x0002

REPORT_SHORT = 0x10
REPORT_LONG = 0x11
LONG_REPORT_LEN = 20

FEATURE_ROOT = 0x0000
FEATURE_REPROG_CONTROLS_V4 = 0x1B04

GESTURE_BUTTON_CID = 0x00C3

SOFTWARE_ID = 0x0A
RECEIVER_DEVICE_INDICES = range(1, 7)
BLUETOOTH_DEVICE_INDEX = 0xFF

REQUEST_TIMEOUT_S = 1.0
READ_TIMEOUT_MS = 1000
REAPPLY_INTERVAL_S = 60.0
RECONNECT_DELAY_S = 3.0

HIDPP1_ERROR = 0x8F
HIDPP2_ERROR = 0xFF
HIDPP1_DEVICE_CONNECTION = 0x41

DIVERT_FLAGS = 0x03  # tmpDivert (bit 0) + its "valid" bit (bit 1)


class HidppError(Exception):
    """Raised when the device rejects or fails to answer a request."""


@dataclass(frozen=True)
class Report:
    """A decoded HID++ report."""

    report_id: int
    device_index: int
    feature_index: int
    function: int
    software_id: int
    params: bytes


def decode_report(data: list[int] | bytes) -> Report | None:
    """Decode a raw HID++ report, or return None if it is too short."""
    if len(data) < 4:
        return None
    return Report(
        report_id=data[0],
        device_index=data[1],
        feature_index=data[2],
        function=data[3] >> 4,
        software_id=data[3] & 0x0F,
        params=bytes(data[4:]),
    )


def encode_request(
    device_index: int, feature_index: int, function: int, params: bytes = b""
) -> bytes:
    """Build a long HID++ 2.0 request report."""
    body = bytes([REPORT_LONG, device_index, feature_index, (function << 4) | SOFTWARE_ID])
    return (body + params).ljust(LONG_REPORT_LEN, b"\x00")


def parse_diverted_buttons(params: bytes) -> set[int]:
    """Return the set of control IDs currently held, from a divertedButtonsEvent."""
    pressed = set()
    for i in range(0, min(len(params), 8), 2):
        cid = (params[i] << 8) | params[i + 1]
        if cid == 0:
            break
        pressed.add(cid)
    return pressed


def find_hidpp_path() -> bytes | None:
    """Locate the Logitech vendor-specific HID++ interface, if present."""
    for info in hid.enumerate(LOGITECH_VENDOR_ID):
        if info["usage_page"] == HIDPP_USAGE_PAGE and info["usage"] == HIDPP_LONG_USAGE:
            return info["path"]
    return None


class HidppConnection:
    """A request/response channel to a single HID++ interface."""

    def __init__(self, path: bytes, on_report: Callable[[Report], None]) -> None:
        self._device = hid.device()
        self._device.open_path(path)
        self._on_report = on_report

    def close(self) -> None:
        self._device.close()

    def read(self, timeout_ms: int) -> Report | None:
        data = self._device.read(64, timeout_ms)
        return decode_report(data) if data else None

    def request(
        self, device_index: int, feature_index: int, function: int, params: bytes = b""
    ) -> Report:
        """Send a request and wait for its reply, forwarding other reports."""
        self._device.write(encode_request(device_index, feature_index, function, params))
        deadline = time.monotonic() + REQUEST_TIMEOUT_S
        while time.monotonic() < deadline:
            report = self.read(100)
            if report is None:
                continue
            if report.device_index == device_index and report.feature_index == HIDPP1_ERROR:
                raise HidppError(f"HID++ 1.0 error 0x{report.params[1]:02x}")
            if (
                report.device_index == device_index
                and report.feature_index == HIDPP2_ERROR
                and report.params[:1] == bytes([feature_index])
            ):
                raise HidppError(f"HID++ 2.0 error 0x{report.params[2]:02x}")
            if (
                report.device_index == device_index
                and report.feature_index == feature_index
                and report.function == function
                and report.software_id == SOFTWARE_ID
            ):
                return report
            self._on_report(report)
        raise HidppError("timed out waiting for reply")


def lookup_feature(conn: HidppConnection, device_index: int, feature_id: int) -> int:
    """Return the feature index for a feature ID using IRoot.GetFeature."""
    reply = conn.request(device_index, 0x00, 0, feature_id.to_bytes(2, "big"))
    index = reply.params[0]
    if index == 0:
        raise HidppError(f"feature 0x{feature_id:04x} not supported")
    return index


def list_control_ids(conn: HidppConnection, device_index: int, feature_index: int) -> list[int]:
    """Return every reprogrammable control ID the device exposes."""
    count = conn.request(device_index, feature_index, 0).params[0]
    cids = []
    for i in range(count):
        info = conn.request(device_index, feature_index, 1, bytes([i])).params
        cids.append((info[0] << 8) | info[1])
    return cids


def set_divert(
    conn: HidppConnection, device_index: int, feature_index: int, cid: int, divert: bool
) -> None:
    """Enable or disable diversion of a control to HID++ notifications."""
    flags = DIVERT_FLAGS if divert else 0x02
    params = cid.to_bytes(2, "big") + bytes([flags]) + cid.to_bytes(2, "big")
    conn.request(device_index, feature_index, 3, params)


@dataclass(frozen=True)
class MouseTarget:
    """The device index and feature index that expose the target button."""

    device_index: int
    feature_index: int


def find_target(conn: HidppConnection, cid: int) -> MouseTarget | None:
    """Scan the receiver slots (and direct Bluetooth) for a device with `cid`."""
    for device_index in (*RECEIVER_DEVICE_INDICES, BLUETOOTH_DEVICE_INDEX):
        try:
            feature_index = lookup_feature(conn, device_index, FEATURE_REPROG_CONTROLS_V4)
            if cid in list_control_ids(conn, device_index, feature_index):
                return MouseTarget(device_index, feature_index)
        except HidppError as exc:
            log.debug("device index %d: %s", device_index, exc)
    return None


class ButtonListener(threading.Thread):
    """Background thread that diverts a button and reports press/release.

    Reconnects automatically and re-applies the divert after the mouse wakes.
    """

    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None] | None = None,
        on_status: Callable[[bool], None] | None = None,
        cid: int = GESTURE_BUTTON_CID,
    ) -> None:
        super().__init__(daemon=True, name="hidpp-listener")
        self._on_press = on_press
        self._on_release = on_release or (lambda: None)
        self._on_status = on_status or (lambda connected: None)
        self._cid = cid
        self._stop_event = threading.Event()
        self._target: MouseTarget | None = None
        self._held = False

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._session()
            except (OSError, HidppError) as exc:
                log.warning("HID++ session ended: %s", exc)
            self._target = None
            self._on_status(False)
            self._stop_event.wait(RECONNECT_DELAY_S)

    def _session(self) -> None:
        path = find_hidpp_path()
        if path is None:
            log.debug("no Logitech HID++ interface found")
            return
        conn = HidppConnection(path, self._handle_report)
        try:
            self._target = find_target(conn, self._cid)
            if self._target is None:
                log.debug("no device with the target button found")
                return
            self._apply_divert(conn)
            self._on_status(True)
            self._read_loop(conn)
        finally:
            conn.close()

    def _apply_divert(self, conn: HidppConnection) -> None:
        assert self._target is not None
        set_divert(conn, self._target.device_index, self._target.feature_index, self._cid, True)
        log.debug("diverted CID 0x%04x on device %d", self._cid, self._target.device_index)

    def _read_loop(self, conn: HidppConnection) -> None:
        last_applied = time.monotonic()
        while not self._stop_event.is_set():
            report = conn.read(READ_TIMEOUT_MS)
            if report is not None:
                self._handle_report(report)
                if report.feature_index == HIDPP1_DEVICE_CONNECTION:
                    time.sleep(1.0)  # let the mouse finish waking up
                    self._apply_divert(conn)
                    last_applied = time.monotonic()
            if time.monotonic() - last_applied > REAPPLY_INTERVAL_S:
                self._apply_divert(conn)
                last_applied = time.monotonic()

    def _handle_report(self, report: Report) -> None:
        target = self._target
        if (
            target is None
            or report.device_index != target.device_index
            or report.feature_index != target.feature_index
            or report.function != 0
        ):
            return
        held = self._cid in parse_diverted_buttons(report.params)
        if held and not self._held:
            self._on_press()
        elif not held and self._held:
            self._on_release()
        self._held = held
