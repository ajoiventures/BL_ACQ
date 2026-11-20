# Follow the example launcher

The VS Code **Run Example** task calls [the launcher](../../tools/run_example.py). It accepts no arguments. It uses a fixed reporting date so each run classifies the synthetic rows consistently.

1. At `mkdtemp`, inspect the directory reserved for this run under `.runs/`.
2. Step into `run` with the debugger. The input is the sample CSV. The output is a fresh report directory inside the lesson directory.
3. Step back to the print statement. Confirm that the summary contains five assets. See how an unknown cost appears in both the individual record and the exceptions file.

Read [asset_reporting.py](../../Python_Asset_Demo/asset_reporting.py) next. Its [tests](../../Python_Asset_Demo/test_asset_reporting.py) compare the outputs and check the meaning of an unknown value.
