import pytest

from goldbot.indicators import atr, ema, rsi


def test_ema_constant_series():
    out = ema([5.0] * 10, 3)
    assert out[:2] == [None, None]
    assert all(v == pytest.approx(5.0) for v in out[2:])


def test_ema_known_values():
    out = ema([1, 2, 3, 4, 5], 3)
    assert out[2] == pytest.approx(2.0)  # SMA(1,2,3)
    assert out[3] == pytest.approx(3.0)  # 4*0.5 + 2*0.5
    assert out[4] == pytest.approx(4.0)


def test_rsi_extremes():
    assert rsi(list(range(1, 30)), 14)[-1] == pytest.approx(100.0)
    assert rsi(list(range(30, 1, -1)), 14)[-1] == pytest.approx(0.0)
    assert rsi([10.0] * 30, 14)[-1] == pytest.approx(50.0)


def test_rsi_range():
    vals = [100 + (i % 7) - (i % 3) * 1.5 for i in range(60)]
    for v in rsi(vals, 14):
        assert v is None or 0 <= v <= 100


def test_atr_constant_range():
    n = 30
    out = atr([11.0] * n, [9.0] * n, [10.0] * n, 14)
    assert out[13] is None
    assert out[-1] == pytest.approx(2.0)
