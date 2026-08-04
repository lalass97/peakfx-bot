param(
    [Parameter(Mandatory = $true)][string]$MetaTraderRoot,
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$CompiledCleanExp1Source,
    [double]$Deposit = 10000.0,
    [string]$Leverage = "1:100"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ResultsRoot = Join-Path $RepoRoot "artifacts/mt5-exp4a"
$GeneratedDir = Join-Path $ResultsRoot "generated"
$Exp2Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5"
$Exp3Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP3A_ER.mq5"
$CandidateName = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP4A_ER_CONFIRM015"
$CandidateSource = Join-Path $GeneratedDir "$CandidateName.mq5"
$Exp2Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp2_candidate.py"
$Exp3Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp3a_candidate.py"
$Exp4Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp4a_candidate.py"
$MetaEditor = Join-Path $MetaTraderRoot "metaeditor64.exe"
$Terminal = Join-Path $MetaTraderRoot "terminal64.exe"

foreach ($required in @($MetaEditor,$Terminal,$CompiledCleanExp1Source,$Exp2Builder,$Exp3Builder,$Exp4Builder)) {
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
    param([string]$ReportStem,[datetime]$StartedAt,[string]$StageDirectory)
    $extensions = @('.htm','.html','.xml')
    $roots = @($StageDirectory,$Mt5DataFolder,$MetaTraderRoot,(Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common')) |
        Where-Object { $_ -and (Test-Path $_ -PathType Container) } | Select-Object -Unique
    $items = @()
    foreach ($root in $roots) {
        $items += Get-ChildItem $root -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.BaseName -eq $ReportStem -and $extensions -contains $_.Extension.ToLowerInvariant() -and $_.LastWriteTime -ge $StartedAt.AddMinutes(-1) }
    }
    return $items | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

New-Item -ItemType Directory -Force -Path $GeneratedDir | Out-Null
& python $Exp2Builder $CompiledCleanExp1Source $Exp2Source
if ($LASTEXITCODE -ne 0) { throw "EXP2 parent generation failed" }
& python $Exp3Builder $Exp2Source $Exp3Source
if ($LASTEXITCODE -ne 0) { throw "EXP3A parent generation failed" }
& python $Exp4Builder $Exp3Source $CandidateSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $CandidateSource)) { throw "EXP4A candidate generation failed" }

$ExpertsRoot = Split-Path -Parent $CompiledCleanExp1Source
$Mt5DataFolder = Split-Path -Parent (Split-Path -Parent $ExpertsRoot)
$ExpertSubdir = "PeakFX"
$ExpertsDir = Join-Path $ExpertsRoot $ExpertSubdir
New-Item -ItemType Directory -Force -Path $ExpertsDir | Out-Null
$DeployedSource = Join-Path $ExpertsDir "$CandidateName.mq5"
Copy-Item $CandidateSource $DeployedSource -Force

$CompileDir = Join-Path $ResultsRoot "compile"
New-Item -ItemType Directory -Force -Path $CompileDir | Out-Null
$CompileLog = Join-Path $CompileDir "meta_compiler.log"
$compileProcess = Start-Process -FilePath $MetaEditor -ArgumentList @("/compile:$DeployedSource","/log:$CompileLog") -Wait -PassThru
if (-not (Test-Path $CompileLog)) { throw "MetaEditor compile log was not created" }
$compileText = Get-Content $CompileLog -Raw
if ($compileText -notmatch '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b' -and $compileText -notmatch '(?i)\b0\s+error\(s\)\s*,\s*0\s+warning\(s\)\b') {
    Get-Content $CompileLog | ForEach-Object { Write-Host $_ }
    throw "Compile gate failed"
}
$DeployedBinary = [System.IO.Path]::ChangeExtension($DeployedSource,'.ex5')
if (-not (Test-Path $DeployedBinary)) { throw "Compiled EX5 not found: $DeployedBinary" }

$Stages = @(
    @{ Name='smoke_1m'; From='2025.06.01'; To='2025.06.30' },
    @{ Name='screen_12m'; From='2024.07.01'; To='2025.06.30' }
)
$leverageInt = [int]($Leverage.Split(':')[1])
foreach ($stage in $Stages) {
    $stageDir = Join-Path $ResultsRoot $stage.Name
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
    $reportStem = "$($stage.Name)_report"
    $configPath = Join-Path $stageDir "$($stage.Name).ini"
    $config = @"
[Tester]
Expert=$ExpertSubdir\$CandidateName
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
Report=$reportStem
ReplaceReport=1
ShutdownTerminal=1
Visual=0
"@
    Set-Content $configPath $config -Encoding ASCII
    Stop-StaleMt5Processes
    $startedAt = Get-Date
    $terminalProcess = Start-Process -FilePath $Terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @("/config:$configPath") -Wait -PassThru
    $found = Find-Mt5Report -ReportStem $reportStem -StartedAt $startedAt -StageDirectory $stageDir
    if (-not $found) { throw "No MT5 report found for $($stage.Name)" }
    $reportPath = Join-Path $stageDir $found.Name
    if ($found.FullName -ine $reportPath) { Copy-Item $found.FullName $reportPath -Force }
    [ordered]@{
        candidate_id='peakfx_exp4a_er035_confirm015_v1_47'
        parent='peakfx_exp3a_er20_035_v1_46'
        isolated_change='Breakout confirmation reduced from 0.20 ATR to 0.15 ATR; ER(20) >= 0.35 and all risk controls unchanged'
        stage=$stage.Name; symbol='EURUSD'; timeframe='H1'; modeling='every_tick_based_on_real_ticks'
        start_date=$stage.From.Replace('.','-'); end_date=$stage.To.Replace('.','-')
        deposit=$Deposit; currency='USD'; leverage=$Leverage; demo_only=$true
        source_path=$CandidateSource; deployed_source_path=$DeployedSource; deployed_binary_path=$DeployedBinary
        report_path=$reportPath; terminal_exit_code=$terminalProcess.ExitCode
    } | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $stageDir "$($stage.Name)_run_metadata.json") -Encoding UTF8
}
Write-Host "EXP4A smoke and fixed 12-month screen completed. OOS remains locked."
