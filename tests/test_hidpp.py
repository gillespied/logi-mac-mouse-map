from logi_mouse_map.hidpp import (
    ButtonListener,
    Report,
    decode_report,
    encode_request,
    parse_diverted_buttons,
)


def test_encode_request_is_padded_long_report():
    data = encode_request(3, 5, 3, b"\x00\xc3\x03")
    assert len(data) == 20
    assert data[:4] == bytes([0x11, 3, 5, 0x3A])
    assert data[4:7] == b"\x00\xc3\x03"


def test_decode_report_splits_function_and_software_id():
    report = decode_report([0x11, 3, 5, 0x1A, 9, 9])
    assert report.function == 1
    assert report.software_id == 0xA
    assert report.params[:2] == b"\x09\x09"


def test_decode_short_data_is_none():
    assert decode_report([0x11, 1]) is None


def test_parse_diverted_buttons():
    assert parse_diverted_buttons(bytes([0x00, 0xC3, 0, 0, 0, 0, 0, 0])) == {0xC3}
    assert parse_diverted_buttons(bytes(8)) == set()
    assert parse_diverted_buttons(bytes([0x00, 0xC3, 0x00, 0x52, 0, 0, 0, 0])) == {0xC3, 0x52}


def test_listener_emits_press_and_release_once():
    events = []
    listener = ButtonListener(lambda: events.append("down"), lambda: events.append("up"))
    from logi_mouse_map.hidpp import MouseTarget

    listener._target = MouseTarget(3, 8)

    def notify(*cids):
        params = b"".join(c.to_bytes(2, "big") for c in cids).ljust(16, b"\0")
        listener._handle_report(Report(0x11, 3, 8, 0, 0, params))

    notify(0xC3)
    notify(0xC3)  # repeat while held
    notify()
    notify()
    assert events == ["down", "up"]


def test_listener_ignores_other_devices_and_features():
    events = []
    listener = ButtonListener(lambda: events.append("down"))
    from logi_mouse_map.hidpp import MouseTarget

    listener._target = MouseTarget(3, 8)
    params = b"\x00\xc3".ljust(16, b"\0")
    listener._handle_report(Report(0x11, 2, 8, 0, 0, params))
    listener._handle_report(Report(0x11, 3, 9, 0, 0, params))
    assert events == []
