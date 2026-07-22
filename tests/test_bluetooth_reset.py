from app.bluetooth_reset import AdapterState, quote_ps


def test_quote_ps_escapes_single_quotes() -> None:
    assert quote_ps("Hes's adapter") == "'Hes''s adapter'"


def test_adapter_is_enabled_only_for_ok_status() -> None:
    assert AdapterState("Bluetooth", "ABC", "OK").enabled is True
    assert AdapterState("Bluetooth", "ABC", "Error").enabled is False
