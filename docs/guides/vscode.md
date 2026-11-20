# Open the learning workspace

[The workspace configuration](../../black-river.code-workspace) connects this checkout to VS Code tasks and the Python debugger. Open the file with **File → Open Workspace from File**. Install Python 3.12 or later, uv, and the Microsoft Python and Python Debugger extensions. Select that interpreter with **Python: Select Interpreter**.

1. Read the task's `command` and `args` together. For example, **Run Example** launches [the sample runner](../../tools/run_example.py) from this checkout.
2. Open [asset_reporting.py](../../Python_Asset_Demo/asset_reporting.py), find `analyze`, and set a breakpoint inside its row loop. In **Run and Debug**, choose **Walk through one synthetic report** and press F5. Continue to the third row to inspect an unknown cost.
3. Run **Tasks: Run Test Task** for the asset and development-tool tests and the code-map check. Use **Open Founder Demo Server** and visit `http://127.0.0.1:8765` for the responsive demo. Stop it with **Tasks: Terminate Task**. After installing the browser engines, **Replay Founder Workflows** exercises the demo independently.

The example writes only beneath `.runs/`. The web task serves the demo over the loopback interface. [Start Here](../START_HERE.md) collects the equivalent terminal commands.
