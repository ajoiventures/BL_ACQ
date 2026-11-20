# Screen underwriting assumptions with CUDA

[The scenario screen](../../pilot/cuda_screen.py) returns a matrix of downside price ceilings in integer cents. Each row represents a resale assumption and each column a stress rate. Start with the final cell in the first row. Follow its stressed resale, net proceeds and deducted costs. The same rounding occurs on both backends.

Run from the repository root. The CUDA run requires a compatible NVIDIA driver and the optional CUDA 12 runtime.

```powershell
uv run --no-project python -m pilot.cuda_screen
uv run --with-requirements requirements-cuda.txt python -m pilot.cuda_screen --backend cuda --compare
```

The report includes a matrix hash and the elapsed time, including data transfer and first-use overhead. Compare the hashes to confirm parity. Screening outputs support exploration. The underwriting workflow evaluates evidence, financing and approval before granting bid readiness. See the [CuPy installation guide](https://docs.cupy.dev/en/stable/install.html).

The [CUDA dependency file](../../requirements-cuda.txt) pins the runtime and compiler wheels. On Windows without a system toolkit, the screen exposes the wheel headers and DLLs to the current process while the GPU runs.

Pass `--repeat 3` to observe warm runs. The first call includes runtime startup. A cold GPU call can cost more than the scalar CPU reference. Read the [CUDA architecture decision](../architecture/cuda-screening.md) for the performance and deployment trade-offs.
