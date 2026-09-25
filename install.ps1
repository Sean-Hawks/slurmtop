# slurmtop installer for Windows (PowerShell 5.1+).
#
#   irm https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.ps1 | iex
#
# Installs slurmtop.py and a slurmtop.cmd launcher into %LOCALAPPDATA%\slurmtop
# (or the directory given as the first argument). Needs Python 3.8+ from
# python.org or the Microsoft Store. Like install.sh it does not change any
# settings: if the folder is not on PATH it prints the command to add it.
#
# credited by team-03/Hawks
$ErrorActionPreference = "Stop"

$Src = if ($env:SLURMTOP_SRC) { $env:SLURMTOP_SRC } else {
    "https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/slurmtop" }
$Dest = if ($args.Count -gt 0) { $args[0] } else { Join-Path $env:LOCALAPPDATA "slurmtop" }

# py.exe（Python 啟動器）優先，沒有再找 python.exe
$Py = Get-Command py -ErrorAction SilentlyContinue
if (-not $Py) { $Py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Py) { throw "Python 3.8+ is required: https://www.python.org/downloads/windows/" }

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$Target = Join-Path $Dest "slurmtop.py"
$Tmp = "$Target.download"

Write-Host "-> downloading slurmtop"
Invoke-WebRequest -UseBasicParsing -Uri $Src -OutFile $Tmp
& $Py.Source -c "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read())" $Tmp
if ($LASTEXITCODE -ne 0) { Remove-Item $Tmp; throw "downloaded file is not valid Python - aborting" }
Move-Item -Force $Tmp $Target

Write-Host "-> installing to $Dest"
# 讓 cmd 和 PowerShell 都能直接打 slurmtop
Set-Content -Encoding ascii -Path (Join-Path $Dest "slurmtop.cmd") `
    -Value "@`"$($Py.Source)`" `"%~dp0slurmtop.py`" %*"

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (($UserPath -split ";") -contains $Dest)) {
    Write-Host ""
    Write-Host "  $Dest is not on your PATH. Add it with:"
    Write-Host "    [Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';$Dest', 'User')"
    Write-Host "  then open a new terminal."
}

Write-Host ""
& $Py.Source $Target --version
Write-Host "done - run 'slurmtop --nodes localhost' (or --web) to start"
