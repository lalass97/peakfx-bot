param(
    [Parameter(Mandatory = $true)][string]$MetaTraderRoot,
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$CompiledCleanExp1Source,
    [double]$Deposit = 10000.0,
    [string]$Leverage = "1:100"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ResultsRoot = Join-Path $RepoRoot "artifacts/mt5-exp7-frozen-closeout-5y"
$GeneratedDir = Join-Path $ResultsRoot "generated"
$CompileDir = Join-Path $ResultsRoot "compile"
$Exp2Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp2_candidate.py"
$Exp7Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp7_frozen_candidate.py"
$MetaEditor = Join-Path $MetaTraderRoot "metaeditor64.exe"
$Terminal = Join-Path $MetaTraderRoot "terminal64.exe"

foreach ($required in @($MetaEditor,$Terminal,$CompiledCleanExp1Source,$Exp2Builder,$Exp7Builder)) {
    if (-not (Test-Path $required)) { throw "Required path not found: $required" }
}
if ($Deposit -le 0) { throw "Deposit must be positive" }
if ($Leverage -notmatch '^1:\d+$') { throw "Leverage must look like 1:100" }

function Stop-StaleMt5Processes {
    Get-Process terminal64, metatester64 -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

function Find-Mt5Report {
    param([string]$ReportStem,[datetime]$StartedAt,[string]$StageDirectory,[string]$Mt5DataFolder)
    $extensions = @('.htm','.html','.xml')
    $roots = @($StageDirectory,$Mt5DataFolder,$MetaTraderRoot,(Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common')) |
        Where-Object { $_ -and (Test-Path $_ -PathType Container) } | Select-Object -Unique
    $items = @()
    foreach ($root in $roots) {
        $items += Get-ChildItem $root -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object {
                $_.BaseName -eq $ReportStem -and
                $extensions -contains $_.Extension.ToLowerInvariant() -and
                $_.LastWriteTime -ge $StartedAt.AddMinutes(-1)
            }
    }
    return $items | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

New-Item -ItemType Directory -Force -Path $ResultsRoot,$GeneratedDir,$CompileDir | Out-Null

$exp2Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5"
$exp7Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP7_FROZEN.mq5"
$diffPath = Join-Path $GeneratedDir "EXP2_to_EXP7_FROZEN.diff"

& python $Exp2Builder $CompiledCleanExp1Source $exp2Source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exp2Source)) { throw "EXP2 generation failed" }
& python $Exp7Builder $exp2Source $exp7Source --diff-output $diffPath
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exp7Source)) { throw "EXP7 generation failed" }

$ExpertsRoot = Split-Path -Parent $CompiledCleanExp1Source
$Mt5DataFolder = Split-Path -Parent (Split-Path -Parent $ExpertsRoot)
$ExpertSubdir = "PeakFX"
$ExpertsDir = Join-Path $ExpertsRoot $ExpertSubdir
New-Item -ItemType Directory -Force -Path $ExpertsDir | Out-Null
$deployedSource = Join-Path $ExpertsDir ([System.IO.Path]::GetFileName($exp7Source))
Copy-Item -LiteralPath $exp7Source -Destination $deployedSource -Force

$compileLog = Join-Path $CompileDir "meta_compiler.log"
$compileProcess = Start-Process -FilePath $MetaEditor -ArgumentList @("/compile:$deployedSource","/log:$compileLog") -Wait -PassThru
if (-not (Test-Path $compileLog)) { throw "Compile log missing" }
$compileText = Get-Content $compileLog -Raw
$compileClean = ($compileText -match '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b' -or
                 $compileText -match '(?i)\b0\s+error\(s\)\s*,\s*0\s+warning\(s\)\b')
if (-not $compileClean) {
    Get-Content $compileLog | ForEach-Object { Write-Host $_ }
    throw "EXP7 compile gate failed"
}
$binary = [System.IO.Path]::ChangeExtension($deployedSource,'.ex5')
if (-not (Test-Path $binary -PathType Leaf)) { throw "Compiled EXP7 EX5 missing: $binary" }

$hashes = [ordered]@{
    exp1_source_sha256 = Get-Sha256 $CompiledCleanExp1Source
    exp2_generated_sha256 = Get-Sha256 $exp2Source
    exp7_generated_sha256 = Get-Sha256 $exp7Source
    exp7_deployed_sha256 = Get-Sha256 $deployedSource
    exp7_binary_sha256 = Get-Sha256 $binary
    builder_exp2_sha256 = Get-Sha256 $Exp2Builder
    builder_exp7_sha256 = Get-Sha256 $Exp7Builder
    frozen_lower_atr = 0.5667
    frozen_upper_atr = 0.85
    further_optimization_prohibited = $true
    oos_locked = $true
}
$hashes | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $ResultsRoot 'source_hashes.json') -Encoding UTF8

$windows = @(
    [ordered]@{ id='2020_2021'; from='2020.07.01'; to='2021.06.30' },
    [ordered]@{ id='2021_2022'; from='2021.07.01'; to='2022.06.30' },
    [ordered]@{ id='2022_2023'; from='2022.07.01'; to='2023.06.30' },
    [ordered]@{ id='2023_2024'; from='2023.07.01'; to='2024.06.30' },
    [ordered]@{ id='2024_2025'; from='2024.07.01'; to='2025.06.30' }
)

$leverageInt = [int]($Leverage.Split(':')[1])
$manifestRuns = @()
foreach ($window in $windows) {
    $stageDir = Join-Path $ResultsRoot $window.id
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
    $reportStem = "exp7_frozen_$($window.id)_report"
    $configPath = Join-Path $stageDir "$reportStem.ini"
    $config = @"
[Tester]
Expert=$ExpertSubdir\PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP7_FROZEN
Symbol=EURUSD
Period=H1
Model=4
ExecutionMode=0
Optimization=0
FromDate=$($window.from)
ToDate=$($window.to)
ForwardMode=0
Deposit=$Deposit
Currency=USD
Leverage=$leverageInt
Report=$reportStem
ReplaceReport=1
ShutdownTerminal=1
Visual=0
"@
    Set-Content -Path $configPath -Value $config -Encoding ASCII
    Stop-StaleMt5Processes
    $startedAt = Get-Date
    Write-Host "Running frozen EXP7 $($window.id): $($window.from) to $($window.to)..."
    $terminalProcess = Start-Process -FilePath $Terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @("/config:$configPath") -Wait -PassThru
    $found = Find-Mt5Report -ReportStem $reportStem -StartedAt $startedAt -StageDirectory $stageDir -Mt5DataFolder $Mt5DataFolder
    if (-not $found) { throw "No MT5 report found for EXP7 $($window.id)" }
    $reportPath = Join-Path $stageDir $found.Name
    if ($found.FullName -ine $reportPath) { Copy-Item -LiteralPath $found.FullName -Destination $reportPath -Force }
    $metadata = [ordered]@{
        candidate_id='EXP7_FROZEN'
        isolated_change='Reject entries with trigger clearance in inclusive range 0.5667 through 0.85 ATR; all other EXP2 logic unchanged'
        status='validation_closeout_only'
        further_optimization_prohibited=$true
        window_id=$window.id
        symbol='EURUSD'
        timeframe='H1'
        modeling='every_tick_based_on_real_ticks'
        start_date=$window.from.Replace('.','-')
        end_date=$window.to.Replace('.','-')
        deposit=$Deposit
        currency='USD'
        leverage=$Leverage
        demo_only=$true
        oos_locked=$true
        source_path=$exp7Source
        source_sha256=Get-Sha256 $exp7Source
        deployed_binary_path=$binary
        compile_log=$compileLog
        report_path=$reportPath
        terminal_exit_code=$terminalProcess.ExitCode
    }
    $metadata | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $stageDir 'run_metadata.json') -Encoding UTF8
    $manifestRuns += $metadata
}

$manifest = [ordered]@{
    protocol='PeakFX frozen EXP7 five-year MT5 validation and archive closeout'
    candidate='EXP7_FROZEN'
    baseline='EXP2'
    frozen_rule='Reject inclusive trigger-clearance interval 0.5667 to 0.85 ATR'
    purpose='Validate offline projection against actual MT5 execution; not an optimization round'
    projected_only_reference=[ordered]@{ net_profit=888.93; trades=369; profit_factor=1.17; max_consecutive_losses=9 }
    windows=$windows
    symbol='EURUSD'
    timeframe='H1'
    modeling='every_tick_based_on_real_ticks'
    deposit=$Deposit
    currency='USD'
    leverage=$Leverage
    demo_only=$true
    oos_locked=$true
    reserved_oos_not_tested=$true
    further_exp7_optimization_prohibited=$true
    archive_after_validation=$true
    compile_clean=$true
    compile_exit_code=$compileProcess.ExitCode
    hashes=$hashes
    generated_at=(Get-Date).ToString('o')
    runs=$manifestRuns
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $ResultsRoot 'exp7_frozen_closeout_manifest.json') -Encoding UTF8
Write-Host "Frozen EXP7 five-year closeout completed. OOS remains locked. No further EXP7 optimization is authorized."
