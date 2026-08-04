param(
    [Parameter(Mandatory = $true)]
    [string]$MetaTraderRoot,

    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string]$CompiledCleanExp1Source,

    [switch]$RunOos,
    [double]$Deposit = 10000.0,
    [string]$Leverage = "1:100"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$CandidateName = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2"
$CandidateFile = "$CandidateName.mq5"
$CandidateId = "peakfx_confirmed_breakout_exp2_v1_45"
$ResultsRoot = Join-Path $RepoRoot "artifacts/mt5-exp2"
$GeneratedDir = Join-Path $ResultsRoot "generated"
$CandidateSource = Join-Path $GeneratedDir $CandidateFile
$Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp2_candidate.py"
$MetaEditor = Join-Path $MetaTraderRoot "metaeditor64.exe"
$Terminal = Join-Path $MetaTraderRoot "terminal64.exe"

foreach ($required in @($MetaEditor, $Terminal, $CompiledCleanExp1Source, $Builder)) {
    if (-not (Test-Path $required)) { throw "Required path not found: $required" }
}
if ($Deposit -le 0) { throw "Deposit must be positive" }
if ($Leverage -notmatch '^1:\d+$') { throw "Leverage must look like 1:100" }

New-Item -ItemType Directory -Force -Path $GeneratedDir | Out-Null
Write-Host "Generating exact EXP2 candidate from compiled-clean EXP1 source..."
& python $Builder $CompiledCleanExp1Source $CandidateSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $CandidateSource)) {
    throw "EXP2 candidate generation failed"
}

$CompileDir = Join-Path $ResultsRoot "compile"
New-Item -ItemType Directory -Force -Path $CompileDir | Out-Null
$CompileLog = Join-Path $CompileDir "metaeditor.log"

Write-Host "Compiling $CandidateFile..."
$compileProcess = Start-Process -FilePath $MetaEditor -ArgumentList @(
    "/compile:$CandidateSource",
    "/log:$CompileLog"
) -Wait -PassThru -NoNewWindow

# Some MetaEditor builds return exit code 1 even when the compiler log reports a
# clean build. The compiler log is therefore the authoritative compile gate.
if (-not (Test-Path $CompileLog)) {
    throw "MetaEditor compile log was not created (exit code $($compileProcess.ExitCode))"
}
$compileText = Get-Content $CompileLog -Raw
$cleanCompile = (
    $compileText -match '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b' -or
    $compileText -match '(?i)\b0\s+error\(s\)\s*,\s*0\s+warning\(s\)\b'
)
if (-not $cleanCompile) {
    throw "Compile gate failed. Required: 0 errors, 0 warnings. MetaEditor exit code: $($compileProcess.ExitCode). See $CompileLog"
}
if ($compileProcess.ExitCode -ne 0) {
    Write-Warning "MetaEditor returned exit code $($compileProcess.ExitCode), but the compile log proves 0 errors and 0 warnings. Continuing."
}
Write-Host "Compile gate passed: 0 errors, 0 warnings."

$Stages = @(
    @{ Name = "smoke_1m"; From = "2025.06.01"; To = "2025.06.30" },
    @{ Name = "screen_12m"; From = "2024.07.01"; To = "2025.06.30" }
)
if ($RunOos) {
    $Stages += @{ Name = "oos_6m"; From = "2025.07.01"; To = "2025.12.31" }
}

function Convert-LeverageToInteger([string]$Value) {
    return [int]($Value.Split(':')[1])
}

function New-TesterConfig($Stage) {
    $stageDir = Join-Path $ResultsRoot $Stage.Name
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
    $reportBase = Join-Path $stageDir "$($Stage.Name)_report"
    $configPath = Join-Path $stageDir "$($Stage.Name).ini"
    $leverageInt = Convert-LeverageToInteger $Leverage

    $config = @"
[Tester]
Expert=$CandidateName
Symbol=EURUSD
Period=H1
Model=4
ExecutionMode=0
Optimization=0
FromDate=$($Stage.From)
ToDate=$($Stage.To)
ForwardMode=0
Deposit=$Deposit
Currency=USD
Leverage=$leverageInt
Report=$reportBase
ReplaceReport=1
ShutdownTerminal=1
Visual=0
"@
    Set-Content -Path $configPath -Value $config -Encoding ASCII
    return @{ Config = $configPath; ReportBase = $reportBase; Directory = $stageDir }
}

foreach ($stage in $Stages) {
    $paths = New-TesterConfig $stage
    Write-Host "Running MT5 stage $($stage.Name): $($stage.From) to $($stage.To)..."
    $terminalProcess = Start-Process -FilePath $Terminal -ArgumentList @(
        "/config:$($paths.Config)"
    ) -Wait -PassThru
    if ($terminalProcess.ExitCode -ne 0) {
        throw "MT5 failed for $($stage.Name) with exit code $($terminalProcess.ExitCode)"
    }

    $reportCandidates = @(
        "$($paths.ReportBase).htm",
        "$($paths.ReportBase).html",
        "$($paths.ReportBase).xml"
    )
    $reportPath = $reportCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $reportPath) {
        throw "No MT5 report found for $($stage.Name) under $($paths.Directory)"
    }

    $metadata = [ordered]@{
        candidate_id = $CandidateId
        stage = $stage.Name
        symbol = "EURUSD"
        timeframe = "H1"
        modeling = "every_tick_based_on_real_ticks"
        start_date = $stage.From.Replace('.', '-')
        end_date = $stage.To.Replace('.', '-')
        deposit = $Deposit
        currency = "USD"
        leverage = $Leverage
        demo_only = $true
        source_path = $CandidateSource
        report_path = $reportPath
    }
    $metadataPath = Join-Path $paths.Directory "$($stage.Name)_run_metadata.json"
    $metadata | ConvertTo-Json -Depth 4 | Set-Content -Path $metadataPath -Encoding UTF8
    Write-Host "Stage complete: $reportPath"
}

if (-not $RunOos) {
    Write-Host "Smoke and 12-month screen completed. Do not run OOS unless the screen passes the locked evaluator gates."
} else {
    Write-Host "OOS stage completed because -RunOos was explicitly supplied."
}
Write-Host "Reports are under $ResultsRoot"
