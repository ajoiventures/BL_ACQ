# Run the pilot checks

[GitHub Actions](../../.github/workflows/checks.yml) verifies a pull request with read-only repository permissions. Install [the pinned check tools](../../requirements-checks.txt) with `python -m pip install -r requirements-checks.txt`. Follow the workflow top to bottom to reproduce the same checks. The storage tests execute migrations and competing claim scenarios on temporary databases.

The CUDA screen is optional on the workstation. Its CPU tests cover the budget arithmetic during CI. A compatible workstation can run the device comparison in the [CUDA screening guide](cuda_screen.md).
