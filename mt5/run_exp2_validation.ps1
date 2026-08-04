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

function Resolve-Mt5DataFolder {
    $terminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
    if (-not (Test-Path $terminalRoot -PathType Container)) {
        throw "MT5 terminal data root not found: $terminalRoot"
    }

    $normalizedInstall = [System.IO.Path]::GetFullPath($MetaTraderRoot).TrimEnd('\\')
    $matches = @()
    foreach ($dir in Get-ChildItem $terminalRoot -Directory -ErrorAction SilentlyContinue) {
        if ($dir.Name -eq "Common") { continue }
        $origin = Join-Path $dir.FullName "origin.txt"
        $mql5 = Join-Path $dir.FullName "MQL5"
        if (-not (Test-Path $mql5 -PathType Container)) { continue }

        if (Test-Path $origin -PathType Leaf) {
            $originText = (Get-Content $origin -Raw -ErrorAction SilentlyContinue).Trim().TrimEnd('\\')
            if ($originText -and ([System.IO.Path]::GetFullPath($originText) -ieq $normalizedInstall)) {
                $matches += $dir
            }
        }
    }

    if ($matches.Count -eq 1) { return $matches[0].FullName }
    if ($matches.Count -gt 1) {
        return ($matches | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    }

    $fallback = Get-ChildItem $terminalRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "Common" -and (Test-Path (Join-Path $_.FullName "MQL5")) } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $fallback) {
        throw "No usable MT5 data folder found under $terminalRoot"
    }
    Write-Warning "Could not match origin.txt to $MetaTraderRoot; using most recently active MT5 data folder: $($fallback.FullName)"
    return $fallback.FullName
}

function Convert-LeverageToInteger([string]$Value) {
    return [int]($Value.Split(':')[1])
}

function Stop-StaleMt5Processes {
    Get-Process terminal64, metatester64 -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

function Find-Mt5Report {
    param(
        [Parameter(Mandatory = $true)][string]$ReportStem,
        [Parameter(Mandatory = $true)][datetime]$StartedAt,
        [Parameter(Mandatory = $true)][string]$StageDirectory
    )

    $extensions = @('.htm', '.html', '.xml')
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

    return $candidates |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

New-Item -ItemType Directory -Force -Path $GeneratedDir | Out-Null
Write-Host "Generating exact EXP2 candidate from compiled-clean EXP1 source..."
& python $Builder $CompiledCleanExp1Source $CandidateSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $CandidateSource)) {
    throw "EXP2 candidate generation failed"
}

$Mt5DataFolder = Resolve-Mt5DataFolder
$ExpertSubdir = "PeakFX"
$ExpertDir = Join-Path $Mt5DataFolder "MQL5\Experts\$ExpertSubdir"
New-Item -ItemType Directory -Force -Path $ExpertDir | Out-Null
$DeployedSource = Join-Path $ExpertDir $CandidateFile
Copy-Item -LiteralPath $CandidateSource -Destination $DeployedSource -Force
Write-Host "Deployed candidate source to active MT5 data folder: $DeployedSource"

$CompileDir = Join-Path $ResultsRoot "compile"
New-Item -ItemType Directory -Force -Path $CompileDir | Out-Null
$CompileLog = Join-Path $CompileDir "metaeditor.log"

Write-Host "Compiling deployed expert $DeployedSource..."
$compileProcess = Start-Process -FilePath $MetaEditor -ArgumentList @(
    "/compile:$DeployedSource",
    "/log:$CompileLog"
) -Wait -PassThru -NoNewWindow

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
$DeployedBinary = [System.IO.Path]::ChangeExtension($DeployedSource, ".ex5")
if (-not (Test-Path $DeployedBinary -PathType Leaf)) {
    throw "Compile log was clean but deployed EX5 was not found: $DeployedBinary"
}
Write-Host "Compile gate passed: 0 errors, 0 warnings. EX5 ready: $DeployedBinary"

$Stages = @(
    @{ Name = "smoke_1m"; From = "2025.06.01"; To = "2025.06.30" },
    @{ Name = "screen_12m"; From = "2024.07.01"; To = "2025.06.30" }
)
if ($RunOos) {
    $Stages += @{ Name = "oos_6m"; From = "2025.07.01"; To = "2025.12.31" }
}

function New-TesterConfig($Stage) {
    $stageDir = Join-Path $ResultsRoot $Stage.Name
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
    $reportStem = "$($Stage.Name)_report"
    $configPath = Join-Path $stageDir "$($Stage.Name).ini"
    $leverageInt = Convert-LeverageToInteger $Leverage
    $expertPath = "$ExpertSubdir\$CandidateName"

    $config = @"
[Tester]
Expert=$expertPath
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
Report=$reportStem
ReplaceReport=1
ShutdownTerminal=1
Visual=0
"@
    Set-Content -Path $configPath -Value $config -Encoding ASCII
    return @{ Config = $configPath; ReportStem = $reportStem; Directory = $stageDir }
}

foreach ($stage in $Stages) {
    $paths = New-TesterConfig $stage
    Stop-StaleMt5Processes
    $startedAt = Get-Date
    Write-Host "Running MT5 stage $($stage.Name): $($stage.From) to $($stage.To)..."
    $terminalProcess = Start-Process -FilePath $Terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @(
        "/config:$($paths.Config)"
    ) -Wait -PassThru

    $foundReport = Find-Mt5Report -ReportStem $paths.ReportStem -StartedAt $startedAt -StageDirectory $paths.Directory
    if (-not $foundReport) {
        $journalDir = Join-Path $Mt5DataFolder "logs"
        $latestJournal = Get-ChildItem $journalDir -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        $journalHint = if ($latestJournal) { $latestJournal.FullName } else { "none found" }
        throw "No MT5 report found for $($stage.Name). Searched stage directory, MT5 data folder, install folder, and Terminal Common. Terminal exit code: $($terminalProcess.ExitCode). Latest terminal journal: $journalHint"
    }

    $reportPath = Join-Path $paths.Directory $foundReport.Name
    if ($foundReport.FullName -ine $reportPath) {
        Copy-Item -LiteralPath $foundReport.FullName -Destination $reportPath -Force
    }
    if ($terminalProcess.ExitCode -ne 0) {
        Write-Warning "MT5 returned exit code $($terminalProcess.ExitCode), but a tester report was produced: $reportPath"
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
        deployed_source_path = $DeployedSource
        deployed_binary_path = $DeployedBinary
        mt5_data_folder = $Mt5DataFolder
        original_report_path = $foundReport.FullName
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
