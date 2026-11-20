"""Run the sample asset report and print the location of its four output files."""

from datetime import date
from pathlib import Path
import sys
from tempfile import mkdtemp


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Python_Asset_Demo"))
from asset_reporting import run


def main():
    # 1. Keep each lesson's output in a fresh directory so it can be run again.
    runs = ROOT / ".runs"
    runs.mkdir(exist_ok=True)
    lesson = Path(mkdtemp(prefix="asset-", dir=runs))

    # 2. Step into run() to follow the same fixture through parser and report.
    sample = ROOT / "Python_Asset_Demo" / "SYNTHETIC_assets.csv"
    report = lesson / "report"
    summary = run(sample, report, date(2026, 9, 13))

    # 3. Open the records beside the summary to inspect individual decisions.
    print(f"{summary['total_assets']} assets processed. Open {report}")


if __name__ == "__main__":
    main()
