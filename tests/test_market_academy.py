import pytest
from site_academy.market import arv_screen, cap_scenario, exit_bridge, overlap, price_band


def test_workbook_examples():
    assert cap_scenario(3000, .25, .03)["indicated_value"] == 900000
    assert cap_scenario(3000, .25, .05)["indicated_value"] == 540000
    assert arv_screen(550000, 10000, .09, 0, 15000, 425000)["spread"] == 50500
    assert arv_screen(155000, 5000, .09, 0, 15000, 115000)["spread"] == 6050
    assert price_band(3300, 186, 196) == [613800, 622050, 630300, 638550, 646800]
    assert overlap([10, 20], [15, 25]) == [15, 20]
    assert overlap([20, 22], [15, 19]) is None
    result = exit_bridge(241606, .06, 29784, 2946, 100, 30, .02, .03)
    assert result["estimated_margin"] == pytest.approx(26254.06)


@pytest.mark.parametrize("operation", [
    lambda: cap_scenario(1000, .2, 0), lambda: cap_scenario(1000, 1.1, .05),
    lambda: price_band(0, 100, 150), lambda: price_band(1500, 160, 150),
    lambda: overlap([50, 40], [30, 60]), lambda: arv_screen(float("nan"), 0, .09, 0, 0, 0)])
def test_invalid_inputs(operation):
    with pytest.raises(ValueError):
        operation()
