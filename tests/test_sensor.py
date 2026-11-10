import pytest

from yarilo.sensor import SensorClient, parse


def test_parse_esphome_reply():
    body = b'{"id":"sensor/Illuminance","value":27.39,"state":"27.4 lx"}'
    assert parse(body) == pytest.approx(27.39)


def test_parse_other_field_and_number_as_text():
    assert parse(b'{"lux":"12.5"}', field="lux") == pytest.approx(12.5)
    assert parse(b'{"state":"7"}', field="state") == pytest.approx(7)


def test_parse_rejects_missing_value():
    with pytest.raises(ValueError):
        parse(b'{"id":"sensor/Illuminance","state":"NA"}')


def test_parse_rejects_nan():
    with pytest.raises(ValueError):
        parse(b'{"id":"sensor/Illuminance","value":NaN,"state":"NA"}')


def test_client_moves_working_url_first():
    calls = []

    def fetch(url):
        calls.append(url)
        if url != "b":
            raise OSError("down")
        return 12.5

    c = SensorClient(["a", "b", "c"], fetch=fetch)
    assert c.read() == 12.5
    assert calls == ["a", "b"]
    calls.clear()
    assert c.read() == 12.5
    assert calls == ["b"]


def test_client_returns_none_when_all_down():
    def fetch(url):
        raise OSError("down")

    assert SensorClient(["a", "b"], fetch=fetch).read() is None


def test_client_treats_bad_reply_as_down():
    def fetch(url):
        if url == "a":
            raise ValueError("no value")
        return 3.0

    assert SensorClient(["a", "b"], fetch=fetch).read() == 3.0


def test_page_of_the_sensor():
    c = SensorClient(["http://lux-sensor.local/sensor/Illuminance"])
    assert c.page() == "http://lux-sensor.local/"
