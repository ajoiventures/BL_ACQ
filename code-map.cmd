@echo off
setlocal
pushd "%~dp0" || exit /b 1

if /i "%~1"=="learn" goto learn
if /i "%~1"=="teach" goto teach
if /i "%~1"=="sell" goto sell
if /i "%~1"=="files" goto files
if /i "%~1"=="cuda" goto cuda
if /i "%~1"=="verify" goto verify
if /i "%~1"=="engines" goto engines
if /i "%~1"=="terms" goto terms
if /i "%~1"=="learning" goto learning
if /i "%~1"=="products" goto products
if not "%~1"=="" goto usage

echo.
echo   BLACK RIVER ^| Architecture and code map
echo.
echo   [1] Learn the architecture and trust boundaries
echo   [2] Teach the deal and restore walkthrough
echo   [3] Rehearse the CTO pitch
echo   [4] Open the file-by-file code map
echo   [5] Run the CUDA screen and compare every result
echo   [6] Verify the pilot with the CI check suite
echo   [7] Open the intelligence engine map
echo   [8] Open the Machine of Machines terminology
echo   [9] Open the architecture agent and learning workflow
echo   [P] Open the product portfolio
echo   [Q] Quit
choice /c 123456789PQ /n /m "Choose an option: "
if errorlevel 11 goto done
if errorlevel 10 goto products
if errorlevel 9 goto learning
if errorlevel 8 goto terms
if errorlevel 7 goto engines
if errorlevel 6 goto verify
if errorlevel 5 goto cuda
if errorlevel 4 goto files
if errorlevel 3 goto sell
if errorlevel 2 goto teach
if errorlevel 1 goto learn
goto done

:learn
call :open docs\CTO_ARCHITECTURE.md
goto finish

:teach
echo Follow the fixture from intake through evidence, underwriting, independent review, and founder approval.
echo The acceptance command links the fixture ledger and verifies the restored SQLite record.
call :open docs\guides\pilot_acceptance.md
uv run --no-project python -m pilot.acceptance
goto finish

:sell
echo Buyer pitch: Black River ties acquisition decisions to evidence, manual review, and a recoverable audit trail.
echo Show a specific deal, its binding limit, and the recorded review. Call the current build a synthetic pilot.
call :open docs\CTO_ARCHITECTURE.md
goto finish

:files
call :open docs\code-map.md
goto finish

:cuda
uv run --with-requirements requirements-cuda.txt python -m pilot.cuda_screen --backend cuda --compare
goto finish

:verify
uv run --with-requirements requirements-checks.txt python tools/check_pilot.py
goto finish

:engines
call :open docs\architecture\intelligence-engines.md
goto finish

:terms
call :open docs\architecture\system-of-systems.md
goto finish

:learning
call :open docs\architecture\swarm-learning.md
goto finish

:products
call :open docs\PRODUCT_PORTFOLIO.md
goto finish

:usage
echo Usage: code-map.cmd [learn ^| teach ^| sell ^| files ^| cuda ^| verify ^| engines ^| terms ^| learning ^| products]
popd
exit /b 2

:open
where code.cmd >nul 2>nul
if errorlevel 1 goto print
call code.cmd --reuse-window "%CD%\%~1"
exit /b %errorlevel%

:print
type "%~1"
exit /b %errorlevel%

:done
popd
exit /b 0

:finish
set "result=%errorlevel%"
popd
exit /b %result%
