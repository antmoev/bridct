param(
    [ValidateSet('Quick', 'Full', 'Verify')][string]$Profile = 'Quick',
    [ValidateRange(1, 16)][int]$Jobs = 2
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'This launcher requires native Windows x86-64 (Intel/AMD), not ARM or 32-bit PowerShell.'
}
$id = 'windows-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + $PID
$out = Join-Path $root "results\$id"
$tools = Join-Path $root '.windows-tools'
$work = Join-Path $root ".windows-work\$id"
New-Item -ItemType Directory -Path $out, "$out\logs", "$out\build-metadata" | Out-Null
$stage = 'lock'
$code = 1
$lock = $null
function Run-Step([string]$Name, [string]$Exe, [string[]]$Arguments) {
    $script:stage = $Name
    Write-Host "[$([DateTime]::UtcNow.ToString('HH:mm:ss'))] $Name"
    @{ executable = $Exe; arguments = $Arguments } | ConvertTo-Json -Compress | Add-Content "$out\commands.jsonl"
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Exe @Arguments 2>&1 | Out-File -Encoding utf8 "$out\logs\$Name.log"
    $rc = $LASTEXITCODE
    $ErrorActionPreference = $saved
    if ($rc -ne 0) {
        Get-Content "$out\logs\$Name.log" -Tail 25 | Write-Host
        throw "$Name failed with exit code $rc"
    }
}
function Download-Checked($Entry, [string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        Invoke-WebRequest -UseBasicParsing -Uri $Entry.url -OutFile "$Path.partial"
        Move-Item -LiteralPath "$Path.partial" -Destination $Path
    }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower() -ne $Entry.sha256) {
        throw "Download checksum mismatch: $Path. Remove this download and retry."
    }
}
try {
    $lock = [IO.File]::Open((Join-Path $root '.windows-run.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $stage = 'host-information'
    @{
        started_utc = [DateTime]::UtcNow.ToString('o'); profile = $Profile
        powershell = $PSVersionTable.PSVersion.ToString(); ci = ($env:GITHUB_ACTIONS -eq 'true')
        os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture
        cpu = @(Get-CimInstance Win32_Processor | Select-Object Name, Manufacturer, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed)
        ram_bytes = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
        isolation_guaranteed = $false
    } | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 "$out\host.json"
    Get-Content "$out\host.json" | Set-Content -Encoding utf8 "$out\host.txt"
    Copy-Item "$PSScriptRoot\windows-tools.json" "$out\windows-tools.json"
    Copy-Item "$root\VERSION" "$out\VERSION"
    $manifest = Get-Content "$PSScriptRoot\windows-tools.json" -Raw | ConvertFrom-Json
    New-Item -ItemType Directory -Force -Path $tools, $work | Out-Null
    $stage = 'download-tools'
    Write-Host 'Preparing private Python and MSYS2/Clang tools. First run needs Internet and several GB of free disk space.'
    Download-Checked $manifest.python "$tools\python.zip"
    Download-Checked $manifest.msys2 "$tools\msys2.exe"
    if (-not (Test-Path "$tools\python\tools\python.exe")) {
        Expand-Archive -LiteralPath "$tools\python.zip" -DestinationPath "$tools\python"
    }
    $python = "$tools\python\tools\python.exe"
    if (-not (Test-Path "$tools\msys64\usr\bin\bash.exe")) {
        Run-Step 'extract-msys2' "$tools\msys2.exe" @('-y', "-o$tools")
    }
    $bash = "$tools\msys64\usr\bin\bash.exe"
    $env:MSYSTEM = 'CLANG64'
    $env:CHERE_INVOKING = 'yes'
    $env:MSYS2_PATH_TYPE = 'inherit'
    $env:PATH = "$tools\msys64\clang64\bin;$tools\msys64\usr\bin;$env:PATH"
    $env:BRIDCT_ROOT = $root
    $env:BRIDCT_PYTHON_WINDOWS = $python
    $env:BRIDCT_OUTPUT_WINDOWS = $out
    $env:BRIDCT_WORK_WINDOWS = $work
    $env:BRIDCT_PROFILE = $Profile
    $env:BRIDCT_JOBS = "$Jobs"
    Run-Step 'initialize-msys2' $bash @('-lc', 'true')
    Run-Step 'update-msys2-core' $bash @('-lc', 'pacman --noconfirm -Syuu')
    Run-Step 'update-msys2' $bash @('-lc', 'pacman --noconfirm -Syuu')
    Run-Step 'install-compiler' $bash @('-lc', 'pacman --noconfirm --needed -S make mingw-w64-clang-x86_64-toolchain')
    Run-Step 'benchmark-pipeline' $bash @('-l', 'distribution/windows_pipeline.sh')
    $stage = 'complete'
    $code = 0
} catch {
    $_ | Out-String | Set-Content -Encoding utf8 "$out\error.txt"
    Write-Host "FAILED at $stage : $_"
} finally {
    "exit_code=$code`nlast_stage=$stage`nprofile=$Profile`nfinished_utc=$([DateTime]::UtcNow.ToString('o'))" | Set-Content -Encoding ascii "$out\status.txt"
    if (Test-Path "$work\venv\Scripts\python.exe") {
        & "$work\venv\Scripts\python.exe" "$PSScriptRoot\summarize.py" --results $out *> "$out\logs\summary.log"
    }
    try {
        Compress-Archive -LiteralPath $out -DestinationPath "$out.zip"
        Write-Host "`nReturn this archive: $out.zip"
    } catch {
        Write-Host "Archive creation failed. Keep this results directory: $out"
        $code = 1
    }
    if ($null -ne $lock) { $lock.Dispose() }
}
exit $code
