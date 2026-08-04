param(
    [Parameter(Mandatory = $true)]
    [string]$MetaTraderRoot,

    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [string]$TerminalDataPath,
    [double]$Deposit = 10000.0,
    [string]$Leverage = "1:100"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$CandidateName = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2"
$CandidateFile = "$CandidateName.mq5"
$CandidateId = "peakfx_confirmed_breakout_exp2_v1_45"
$BranchSource = Join-Path $RepoRoot "mt5/$CandidateFile"
$ResultsRoot = Join-Path $RepoRoot "artifacts/mt5-exp2"
$MetaEditor = Join-Path $MetaTraderRoot "metaeditor64.exe"
$Terminal = Join-Path $MetaTraderRoot "terminal64.exe"

if (-not (Test-Path $MetaEditor)) { throw "metaeditor64.exe not found: $MetaEditor" }
if (-not (Test-Path $Terminal)) { throw "terminal64.exe not found: $Terminal" }
if (-not (Test-Path $BranchSource)) { throw "Candidate source not found: $BranchSource" }
if ($Deposit -le 0) { throw "Deposit must be positive" }
if ($Leverage -notmatch '^1:\d+$') { throw "Leverage must look like 1:100" }

if ([string]::IsNullOrWhiteSpace($TerminalDataPath)) {
    $TerminalDataPath = Join-Path $env:APPDATA "MetaQuotes/Terminal"
}

New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
$CompileDir = Join-Path $ResultsRoot "compile"
New-Item -ItemType Directory -Force -Path $CompileDir | Out-Null
$CompileLog = Join-Path $CompileDir "metaeditor.log"

Write-Host "Compiling $CandidateFile..."
$compileProcess = Start-Process -FilePath $MetaEditor -ArgumentList @(
    "/compile:$BranchSource",
    "/log:$CompileLog"
) -Wait -PassThru -NoNewWindow

if ($compileProcess.ExitCode -ne 0) {
    throw "MetaEditor returned exit code $($compileProcess.ExitCode). See $CompileLog"
}
if (-not (Test-Path $CompileLog)) { throw "MetaEditor compile log was not created" }
$compileText = Get-Content $CompileLog -Raw
if ($compileText -notmatch '0 error\(s\), 0 warning\(s\)') {
    throw "Compile gate failed. Required: 0 errors, 0 warnings. See $CompileLog"
}

$Stages = @(
    @{ Name = "smoke_1m"; From = "2025.06.01"; To = "2025.06.30" },
    @{ Name = "screen_12m"; From = "2024.07.01"; To = "2025.06.30" },
    @{ Name = "oos_6m"; From = "2025.07.01"; To = "2025.12.31" }
)

function Convert-LeverageToInteger([string]$Value) {
    return [int]($Value.Split(':')[1])
}

function New-TesterConfig($Stage) {
    $stageDir = Join-Path $ResultsRoot $Stage.Name
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
    $reportBase = Join-Path $stageDir "$($Stage.Name)_report"
    $configPath = Join-Path $stageDir "$($Stage.Name).ini"
    $journalPath = Join-Path $stageDir "$($Stage.Name)_terminal.log"
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
    return @{ Config = $configPath; ReportBase = $reportBase; Journal = $journalPath; Directory = $stageDir }
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
        start_date = $Stage.From.Replace('.', '-')
        end_date = $Stage.To.Replace('.', '-')
        deposit = $Deposit
        currency = "USD"
        leverage = $Leverage
        demo_only = $true
        source_path = $BranchSource
        report_path = $reportPath
    }
    $metadataPath = Join-Path $paths.Directory "$($stage.Name)_run_metadata.json"
    $metadata | ConvertTo-Json -Depth 4 | Set-Content -Path $metadataPath -Encoding UTF8
    Write-Host "Stage complete: $reportPath"
}

Write-Host "All requested MT5 stages completed. Reports are under $ResultsRoot"
