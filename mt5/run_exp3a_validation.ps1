param(
    [Parameter(Mandatory = $true)][string]$MetaTraderRoot,
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$CompiledCleanExp1Source,
    [double]$Deposit = 10000.0,
    [string]$Leverage = "1:100"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$CandidateName = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP3A_ER"
$CandidateFile = "$CandidateName.mq5"
$CandidateId = "peakfx_exp3a_er20_035_v1_46"
$ResultsRoot = Join-Path $RepoRoot "artifacts/mt5-exp3a"
$GeneratedDir = Join-Path $ResultsRoot "generated"
$Exp2Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5"
$CandidateSource = Join-Path $GeneratedDir $CandidateFile
$Exp2Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp2_candidate.py"
$Exp3Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp3a_candidate.py"
$MetaEditor = Join-Path $MetaTraderRoot "metaeditor64.exe"
$Terminal = Join-Path $MetaTraderRoot "terminal64.exe"

foreach ($required in @($MetaEditor,$Terminal,$CompiledCleanExp1Source,$Exp2Builder,$Exp3Builder)) {
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
    param(
        [Parameter(Mandatory = $true)][string]$ReportStem,
        [Parameter(Mandatory = $true)][datetime]$StartedAt,
        [Parameter(Mandatory = $true)][string]$StageDirectory,
        [Parameter(Mandatory = $true)][string]$Mt5DataFolder
    )

    $extensions = @('.htm','.html','.xml')
    $searchRoots = @(
        $StageDirectory,
        $Mt5DataFolder,
        $MetaTraderRoot,
        (Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common')
    ) | Where-Object { $_ -and (Test-Path $_ -PathType Container) } | Select-Object -Unique

    $candidates = @()
    foreach ($root in $searchRoots) {
        foreach ($extension in $extensions) {
            $exact = Join-Path $root "$ReportStem$extension"
            if (Test-Path $exact -PathType Leaf) {
                $item = Get-Item $exact
                if ($item.LastWriteTime -ge $StartedAt.AddMinutes(-1)) { $candidates += $item }
            }
        }
        $candidates += Get-ChildItem $root -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object {
                $_.BaseName -eq $ReportStem -and
                $extensions -contains $_.Extension.ToLowerInvariant() -and
                $_.LastWriteTime -ge $StartedAt.AddMinutes(-1)
            }
    }

    return $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

New-Item -ItemType Directory -Force -Path $GeneratedDir | Out-Null
Write-Host "Generating exact EXP2 parent from compiled-clean EXP1..."
& python $Exp2Builder $CompiledCleanExp1Source $Exp2Source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Exp2Source)) { throw "EXP2 parent generation failed" }

Write-Host "Generating isolated EXP3A ER candidate from EXP2 parent..."
& python $Exp3Builder $Exp2Source $CandidateSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $CandidateSource)) { throw "EXP3A candidate generation failed" }

$ExpertsDir = Split-Path -Parent $CompiledCleanExp1Source
if (-not (Test-Path $ExpertsDir -PathType Container)) { throw "Active MT5 Experts folder not found: $ExpertsDir" }
$Mt5DataFolder = Split-Path -Parent (Split-Path -Parent $ExpertsDir)
$ExpertSubdir = Split-Path -Leaf $ExpertsDir
$DeployedSource = Join-Path $ExpertsDir $CandidateFile
Copy-Item -LiteralPath $CandidateSource -Destination $DeployedSource -Force
Write-Host "Deployed EXP3A source to active MT5 data folder: $DeployedSource"

$CompileDir = Join-Path $ResultsRoot "compile"
New-Item -ItemType Directory -Force -Path $CompileDir | Out-Null
$CompileLog = Join-Path $CompileDir "meta_compiler.log"
Write-Host "Compiling deployed EXP3A expert..."
$compileProcess = Start-Process -FilePath $MetaEditor -ArgumentList @(
    "/compile:$DeployedSource",
    "/log:$CompileLog"
) -Wait -PassThru -NoNewWindow
if (-not (Test-Path $CompileLog)) { throw "MetaEditor compile log was not created" }
$compileText = Get-Content $CompileLog -Raw
$compilePassed = (
    $compileText -match '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b' -or
    $compileText -match '(?i)\b0\s+error\(s\)\s*,\s*0\s+warning\(s\)\b'
)
if (-not $compilePassed) {
    Write-Host "----- MetaEditor compile log -----"
    Get-Content $CompileLog | ForEach-Object { Write-Host $_ }
    Write-Host "----- End compile log -----"
    throw "Compile gate failed. Required: 0 errors, 0 warnings. See $CompileLog"
}
if ($compileProcess.ExitCode -ne 0) {
    Write-Warning "MetaEditor returned exit code $($compileProcess.ExitCode), but log proves 0 errors and 0 warnings. Continuing."
}
$DeployedBinary = [System.IO.Path]::ChangeExtension($DeployedSource,'.ex5')
if (-not (Test-Path $DeployedBinary -PathType Leaf)) { throw "Clean compile but EX5 not found: $DeployedBinary" }
Write-Host "Compile gate passed: 0 errors, 0 warnings. EX5 ready: $DeployedBinary"

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
    $expertPath = "$ExpertSubdir\$CandidateName"

    $config = @"
[Tester]
Expert=$expertPath
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
    Set-Content -Path $configPath -Value $config -Encoding ASCII

    Stop-StaleMt5Processes
    $startedAt = Get-Date
    Write-Host "Running EXP3A $($stage.Name): $($stage.From) to $($stage.To)..."
    $terminalProcess = Start-Process -FilePath $Terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @(
        "/config:$configPath"
    ) -Wait -PassThru

    $foundReport = Find-Mt5Report -ReportStem $reportStem -StartedAt $startedAt -StageDirectory $stageDir -Mt5DataFolder $Mt5DataFolder
    if (-not $foundReport) {
        $journalDir = Join-Path $Mt5DataFolder 'logs'
        $latestJournal = Get-ChildItem $journalDir -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $journalHint = if ($latestJournal) { $latestJournal.FullName } else { 'none found' }
        throw "No MT5 report found for $($stage.Name). Searched stage directory, MT5 data folder, install folder, and Terminal Common. Terminal exit code: $($terminalProcess.ExitCode). Latest terminal journal: $journalHint"
    }

    $reportPath = Join-Path $stageDir $foundReport.Name
    if ($foundReport.FullName -ine $reportPath) {
        Copy-Item -LiteralPath $foundReport.FullName -Destination $reportPath -Force
    }
    if ($terminalProcess.ExitCode -ne 0) {
        Write-Warning "MT5 returned exit code $($terminalProcess.ExitCode), but a tester report was produced: $reportPath"
    }

    [ordered]@{
        candidate_id=$CandidateId
        parent='peakfx_confirmed_breakout_exp2_v1_45'
        isolated_change='Kaufman ER(20) >= 0.35 entry gate on completed H1 bars'
        stage=$stage.Name
        symbol='EURUSD'
        timeframe='H1'
        modeling='every_tick_based_on_real_ticks'
        start_date=$stage.From.Replace('.','-')
        end_date=$stage.To.Replace('.','-')
        deposit=$Deposit
        currency='USD'
        leverage=$Leverage
        demo_only=$true
        source_path=$CandidateSource
        deployed_source_path=$DeployedSource
        deployed_binary_path=$DeployedBinary
        mt5_data_folder=$Mt5DataFolder
        original_report_path=$foundReport.FullName
        report_path=$reportPath
    } | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $stageDir "$($stage.Name)_run_metadata.json") -Encoding UTF8

    Write-Host "Stage complete: $reportPath"
}

Write-Host "EXP3A smoke and 12-month screen completed. OOS remains locked. Reports: $ResultsRoot"
