<#
Live demo of the fluid inerter: run the CFD, render the flow animation, and open the results.

    powershell -ExecutionPolicy Bypass -File live_demo.ps1            # full live demo (~6 min)
    powershell -ExecutionPolicy Bypass -File live_demo.ps1 -OpenOnly  # just open the existing results (instant)

You can run this from any folder: it finds the project folder by itself.
#>
param([switch]$OpenOnly)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Open-Results {
    Step 'Opening the results'
    Invoke-Item (Join-Path $root 'cfd\results\demo\osc_X5.gif')                   # flow animation (5 mm stroke)
    Invoke-Item (Join-Path $root 'cfd\results\models')                            # pictures of every model
    Invoke-Item (Join-Path $root 'project_page.html')                             # project page; scroll to "Watch the inerter work"
    Write-Host 'Opened: the animation, the models folder and the project page.'
}

if ($OpenOnly) { Open-Results; return }

Step '1/3  Prepare the CFD cases (Python)'
python cfd\scripts\make_demo_openfoam.py
if ($LASTEXITCODE -ne 0) { throw 'case generation failed' }

Step '2/3  Run OpenFOAM in Ubuntu (WSL): 2 oscillating + 3 steady cases, ~3 min'
Write-Host 'Each line below appears when a simulation finishes.' -ForegroundColor DarkGray
Write-Host 'A live window opens: oil flow, cross-section and force loop updating as OpenFOAM computes.' -ForegroundColor DarkGray
Start-Process python -ArgumentList "`"$root\cfd\scripts\watch_live.py`"", 'osc_X5'
$runner = (wsl.exe wslpath -a ((Join-Path $root 'cfd\openfoam\run_in_wsl.sh') -replace '\\', '/')).Trim()
wsl.exe -e bash -c "NP=5 bash '$runner' torus_demo"
if ($LASTEXITCODE -ne 0) { throw 'OpenFOAM run failed - see cfd\openfoam\torus_demo\<case>\log.*' }

Step '3/3  Render the animation and pictures (~3 min)'
python cfd\scripts\render_demo.py
python cfd\scripts\render_models.py
if ($LASTEXITCODE -ne 0) { throw 'rendering failed' }

Open-Results
Step 'Done'
