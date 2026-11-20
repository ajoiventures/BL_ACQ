# Check what the scenario matrix means

[The test](../../tests/test_cuda_screen.py) calculates a small grid with two resale assumptions and three downside rates. In a debugger, follow the rate of 1000 basis points through both rounds of integer division. A zero resale produces a negative ceiling after costs. The financing limit remains a separate underwriting check, so changing it leaves this grid intact.

Run `python -m unittest discover -s tests -p test_cuda_screen.py` on any host. For CUDA parity, run the explicit device comparison from the [screening guide](cuda_screen.md).
