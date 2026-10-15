<#
Open the project's CFD results in ParaView with all views set up (3D streamlines, cross-section with
Dean-vortex arrows, residuals chart, oscillation monitor; press Play to animate).

    powershell -ExecutionPolicy Bypass -File open_paraview.ps1

Needs ParaView for Windows (free): https://www.paraview.org/download/  (any 5.11 or newer).
The data is built automatically the first time (cfd/paraview/build_paraview_cases.py).
#>
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pv = Get-ChildItem 'C:\Program Files\ParaView*\bin\paraview.exe' -ErrorAction SilentlyContinue |
      Sort-Object FullName -Descending | Select-Object -First 1
if (-not $pv) {
    Write-Host 'ParaView was not found in C:\Program Files.' -ForegroundColor Yellow
    Write-Host 'Install it (free) from https://www.paraview.org/download/ (Windows, ParaView 5.11 or newer), then run this again.'
    exit 1
}
$data = Join-Path $root 'cfd\paraview'
if (-not (Test-Path (Join-Path $data 'oscillating_helix\case.foam'))) {
    Write-Host 'Building the ParaView data (first run, ~15 s)...'
    python (Join-Path $data 'build_paraview_cases.py')
    if ($LASTEXITCODE -ne 0) { throw 'building the ParaView data failed' }
}
if (-not (Test-Path (Join-Path $data 'device\piston.pvd'))) {
    Write-Host 'Building the 3D device model (piston, chambers, coil)...'
    python (Join-Path $data 'build_device.py')
    if ($LASTEXITCODE -ne 0) { throw 'building the device model failed' }
}
Write-Host "Starting $($pv.FullName)"
Start-Process -FilePath $pv.FullName -ArgumentList "--script=`"$(Join-Path $data 'open_in_paraview.py')`""
