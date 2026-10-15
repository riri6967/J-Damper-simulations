<#
Run the whole fluid-inerter project: generate CFD cases -> run OpenFOAM in WSL -> post-process
-> vehicle (suspension) studies. Run from PowerShell in the project folder:

    powershell -ExecutionPolicy Bypass -File run_all.ps1                 # everything (~1.5-2 h)
    powershell -ExecutionPolicy Bypass -File run_all.ps1 -SkipCFD        # only analysis (~5 min)
    powershell -ExecutionPolicy Bypass -File run_all.ps1 -Cores 4        # fewer CPU cores

Needs: Python 3 with numpy, scipy, matplotlib (Windows); WSL Ubuntu with OpenFOAM v2406.
Results: cfd/results/ (CFD) and python/results/ (vehicle studies). See HOW_TO_RUN.md.
#>
param(
    [switch]$SkipCFD,          # reuse existing CFD results, only post-process + vehicle studies
    [int]$Cores = 8            # CPU cores for OpenFOAM (helix cases in parallel, torus cases as parallel jobs)
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = 'python'

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Run-Py($script, [string[]]$argv = @()) {
    & $py $script @argv
    if ($LASTEXITCODE -ne 0) { throw "$script failed (exit $LASTEXITCODE)" }
}

Set-Location $root
$s = Join-Path $root 'cfd\scripts'

if (-not $SkipCFD) {
    Step '1/5  Generate meshes and OpenFOAM cases'
    Run-Py "$s\make_s01_openfoam.py"                                          # helix, medium mesh, Re 100-4000
    Run-Py "$s\make_s01_openfoam.py" @('--mesh', 'coarse', '--re', '100', '1000', '4000')
    Run-Py "$s\make_s01_openfoam.py" @('--mesh', 'fine', '--re', '100', '1000', '4000')
    Run-Py "$s\make_torus_openfoam.py"                                        # torus fine: steady + oscillatory
    Run-Py "$s\make_torus_openfoam.py" @('--mesh', 'medium', '--sets', 'steady')
    Run-Py "$s\make_demo_openfoam.py"                                        # flow-visualisation cases
    Run-Py "$s\make_chamber_openfoam.py"                                     # piston chamber + port, cavitation

    Step '2/5  Run OpenFOAM in WSL (this is the long part)'
    $runner = (wsl.exe wslpath -a ((Join-Path $root 'cfd\openfoam\run_in_wsl.sh') -replace '\\', '/')).Trim()
    $sets = 's01 gci_coarse gci_fine torus_steady torus_steady_medium torus_oscillatory torus_demo chamber chamber_transient'
    wsl.exe -e bash -c "NP=$Cores bash '$runner' $sets"
    if ($LASTEXITCODE -ne 0) { throw 'OpenFOAM runs failed - see the log.* files in cfd/openfoam/<set>/<case>/' }
}

Step '3/5  Post-process CFD'
Run-Py "$s\post_s01.py"                                   # helix friction vs Ito/White
Run-Py "$s\post_gci.py"                                   # mesh independence (GCI)
Run-Py "$s\post_torus_steady.py" @('torus_steady_medium') # pitch (torsion) effect, same mesh as S01
Run-Py "$s\post_torus_steady.py" @('torus_steady')
Run-Py "$s\post_transient.py"                             # CFD inertance and damping (T01-T10)
Run-Py "$s\post_chamber.py"                               # piston chamber: port losses, force loop, cavitation
Run-Py "$s\render_models.py"                             # pictures of the geometry, meshes and suspension models
Run-Py "$s\render_demo.py"                             # flow animation + Dean-vortex figure (~3 min)

Step '4/5  Vehicle (suspension) studies'
Push-Location (Join-Path $root 'python')
try {
    Run-Py 'analyse_inerter.py'
    Run-Py 'test_fit_rom.py'
    Run-Py 'run_quarter_car_study.py'
    Run-Py 'run_time_domain.py'
    Run-Py 'run_cfd_vehicle_study.py'
} finally { Pop-Location }

Step '5/5  Track simulator data (tracks, lap simulation, suspension tuning for each car)'
Run-Py (Join-Path $root 'sim\build_sim_data.py')
Write-Host 'Open sim\track_simulator.html in a browser. Presentation charts/GIFs: see PRESENTATION_GUIDE.md (section "Regenerating").'

Step 'Done'
Write-Host 'CFD results:     cfd\results\'
Write-Host 'Vehicle results: python\results\'
