param(
    [Parameter(Mandatory = $true)][string]$MetaTraderRoot,
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$CompiledCleanExp1Source,
    [double]$Deposit = 10000.0,
    [string]$Leverage = "1:100"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ResultsRoot = Join-Path $RepoRoot "artifacts/mt5-exp3a"
$GeneratedDir = Join-Path $ResultsRoot "generated"
$Exp2Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5"
$CandidateName = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP3A_ER"
$CandidateSource = Join-Path $GeneratedDir "$CandidateName.mq5"
$Exp2Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp2_candidate.py"
$Exp3Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp3a_candidate.py"
$MetaEditor = Join-Path $MetaTraderRoot "metaeditor64.exe"
$Terminal = Join-Path $MetaTraderRoot "terminal64.exe"

foreach ($required in @($MetaEditor,$Terminal,$CompiledCleanExp1Source,$Exp2Builder,$Exp3Builder)) {
    if (-not (Test-Path $required)) { throw "Required path not found: $required" }
}
if ($Deposit -le 0) { throw "Deposit must be positive" }
if ($Leverage -notmatch '^1:\d+$') { throw "Leverage must look like 1:100" }

New-Item -ItemType Directory -Force -Path $GeneratedDir | Out-Null
Write-Host "Generating exact EXP2 parent from compiled-clean EXP1..."
& python $Exp2Builder $CompiledCleanExp1Source $Exp2Source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Exp2Source)) { throw "EXP2 parent generation failed" }

Write-Host "Generating isolated EXP3A ER candidate from EXP2 parent..."
& python $Exp3Builder $Exp2Source $CandidateSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $CandidateSource)) { throw "EXP3A candidate generation failed" }

# Deploy beside the verified source inside the active, writable MetaQuotes data folder.
$ExpertsDir = Split-Path -Parent $CompiledCleanExp1Source
if (-not (Test-Path $ExpertsDir)) { throw "Active MT5 Experts folder not found: $ExpertsDir" }
$DeployedSource = Join-Path $ExpertsDir "$CandidateName.mq5"
Copy-Item $CandidateSource $DeployedSource -Force
Write-Host "Deployed EXP3A source to active MT5 data folder: $DeployedSource"

$CompileDir = Join-Path $ResultsRoot "compile"
New-Item -ItemType Directory -Force -Path $CompileDir | Out-Null
$CompileLog = Join-Path $CompileDir "meta_compiler.log"
Write-Host "Compiling deployed EXP3A expert..."
$compileProcess = Start-Process -FilePath $MetaEditor -ArgumentList @("/compile:$DeployedSource","/log:$CompileLog") -Wait -PassThru
if (-not (Test-Path $CompileLog)) { throw "MetaEditor compile log was not created" }
$compileText = Get-Content $CompileLog -Raw

# MetaEditor reports success as: Result: 0 errors, 0 warnings, ...
$compilePassed = $compileText -match '(?im)^Result:\s*0\s+errors,\s*0\s+warnings,'
if (-not $compilePassed) {
    Write-Host "----- MetaEditor compile log -----"
    Get-Content $CompileLog | ForEach-Object { Write-Host $_ }
    Write-Host "----- End compile log -----"
    throw "Compile gate failed. Required: 0 errors, 0 warnings. See $CompileLog"
}
Write-Host "Compile gate passed (MetaEditor exit code $($compileProcess.ExitCode)); log proves 0 errors, 0 warnings."

$Stages = @(
    @{ Name="smoke_1m"; From="2025.06.01"; To="2025.06.30" },
    @{ Name="screen_12m"; From="2024.07.01"; To="2025.06.30" }
)
$leverageInt = [int]($Leverage.Split(':')[1])
foreach ($stage in $Stages) {
    $stageDir = Join-Path $ResultsRoot $stage.Name
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
    $reportBase = Join-Path $stageDir "$($stage.Name)_report"
    $configPath = Join-Path $stageDir "$($stage.Name).ini"
    $config = @"
[Tester]
Expert=PeakFX\\$CandidateName
Symbol=EURUSD
Period=H1
Model=4
ExecutionMode=0
Optimization=0
FromDate=$($stage.From)
ToDate=$($stage.To)
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
    Write-Host "Running EXP3A $($stage.Name): $($stage.From) to $($stage.To)..."
    $terminalProcess = Start-Process -FilePath $Terminal -ArgumentList "/config:$configPath" -Wait -PassThru
    if ($terminalProcess.ExitCode -ne 0) { throw "MT5 failed for $($stage.Name) with exit code $($terminalProcess.ExitCode)" }
    $reportPath = @("$reportBase.htm","$reportBase.html","$reportBase.xml") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $reportPath) { throw "No MT5 report found for $($stage.Name) under $stageDir" }
    [ordered]@{
        candidate_id="peakfx_exp3a_er20_035_v1_46"
        parent="peakfx_confirmed_breakout_exp2_v1_45"
        isolated_change="Kaufman ER(20) >= 0.35 entry gate on completed H1 bars"
        stage=$stage.Name; symbol="EURUSD"; timeframe="H1"; modeling="every_tick_based_on_real_ticks"
        start_date=$stage.From.Replace('.','-'); end_date=$stage.To.Replace('.','-')
        deposit=$Deposit; currency="USD"; leverage=$Leverage; demo_only=$true
        source_path=$CandidateSource; report_path=$reportPath
    } | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $stageDir "$($stage.Name)_run_metadata.json") -Encoding UTF8
    Write-Host "Stage complete: $reportPath"
}
Write-Host "EXP3A smoke and 12-month screen completed. OOS remains locked. Reports: $ResultsRoot"
