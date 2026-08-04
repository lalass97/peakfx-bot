param(
    [Parameter(Mandatory = $true)][string]$MetaTraderRoot,
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$CompiledCleanExp1Source,
    [double]$Deposit = 10000.0,
    [string]$Leverage = "1:100"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ResultsRoot = Join-Path $RepoRoot "artifacts/mt5-robustness-5y"
$GeneratedDir = Join-Path $ResultsRoot "generated"
$CompileRoot = Join-Path $ResultsRoot "compile"
$Exp2Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp2_candidate.py"
$Exp3Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp3a_candidate.py"
$Exp6Builder = Join-Path $RepoRoot "research/build_confirmed_breakout_exp6a_candidate.py"
$MetaEditor = Join-Path $MetaTraderRoot "metaeditor64.exe"
$Terminal = Join-Path $MetaTraderRoot "terminal64.exe"

foreach ($required in @($MetaEditor,$Terminal,$CompiledCleanExp1Source,$Exp2Builder,$Exp3Builder,$Exp6Builder)) {
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

function Compile-Candidate {
    param([string]$CandidateId,[string]$SourcePath,[string]$ExpertsDir)
    $deployedSource = Join-Path $ExpertsDir ([System.IO.Path]::GetFileName($SourcePath))
    Copy-Item -LiteralPath $SourcePath -Destination $deployedSource -Force
    $candidateCompileDir = Join-Path $CompileRoot $CandidateId
    New-Item -ItemType Directory -Force -Path $candidateCompileDir | Out-Null
    $compileLog = Join-Path $candidateCompileDir "meta_compiler.log"
    $process = Start-Process -FilePath $MetaEditor -ArgumentList @("/compile:$deployedSource","/log:$compileLog") -Wait -PassThru
    if (-not (Test-Path $compileLog)) { throw "Compile log missing for $CandidateId" }
    $compileText = Get-Content $compileLog -Raw
    $clean = ($compileText -match '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b' -or
              $compileText -match '(?i)\b0\s+error\(s\)\s*,\s*0\s+warning\(s\)\b')
    if (-not $clean) {
        Get-Content $compileLog | ForEach-Object { Write-Host $_ }
        throw "Compile gate failed for $CandidateId"
    }
    $binary = [System.IO.Path]::ChangeExtension($deployedSource,'.ex5')
    if (-not (Test-Path $binary -PathType Leaf)) { throw "Compiled EX5 not found for $CandidateId: $binary" }
    return [ordered]@{ source=$deployedSource; binary=$binary; compile_log=$compileLog; exit_code=$process.ExitCode }
}

New-Item -ItemType Directory -Force -Path $GeneratedDir,$CompileRoot | Out-Null

$exp2Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5"
$exp3Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP3A_ER.mq5"
$exp6Source = Join-Path $GeneratedDir "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP6A_RISING_ER.mq5"

& python $Exp2Builder $CompiledCleanExp1Source $exp2Source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exp2Source)) { throw "EXP2 generation failed" }
& python $Exp3Builder $exp2Source $exp3Source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exp3Source)) { throw "EXP3A generation failed" }
& python $Exp6Builder $exp3Source $exp6Source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exp6Source)) { throw "EXP6A generation failed" }

$ExpertsRoot = Split-Path -Parent $CompiledCleanExp1Source
if (-not (Test-Path $ExpertsRoot -PathType Container)) { throw "Experts root not found: $ExpertsRoot" }
$Mt5DataFolder = Split-Path -Parent (Split-Path -Parent $ExpertsRoot)
$ExpertSubdir = "PeakFX"
$ExpertsDir = Join-Path $ExpertsRoot $ExpertSubdir
New-Item -ItemType Directory -Force -Path $ExpertsDir | Out-Null

$candidates = @(
    [ordered]@{ id='EXP2'; name='PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2'; source=$exp2Source; isolated_change='No ER gate; confirmed-breakout reference candidate' },
    [ordered]@{ id='EXP3A'; name='PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP3A_ER'; source=$exp3Source; isolated_change='Kaufman ER(20) >= 0.35' },
    [ordered]@{ id='EXP6A'; name='PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP6A_RISING_ER'; source=$exp6Source; isolated_change='ER >= 0.35 OR ER >= 0.30 and rising by at least 0.05 versus prior completed bar' }
)

$compiled = @{}
foreach ($candidate in $candidates) {
    Write-Host "Compiling $($candidate.id)..."
    $compiled[$candidate.id] = Compile-Candidate -CandidateId $candidate.id -SourcePath $candidate.source -ExpertsDir $ExpertsDir
}

$windows = @(
    [ordered]@{ id='2020_2021'; from='2020.07.01'; to='2021.06.30' },
    [ordered]@{ id='2021_2022'; from='2021.07.01'; to='2022.06.30' },
    [ordered]@{ id='2022_2023'; from='2022.07.01'; to='2023.06.30' },
    [ordered]@{ id='2023_2024'; from='2023.07.01'; to='2024.06.30' },
    [ordered]@{ id='2024_2025'; from='2024.07.01'; to='2025.06.30' }
)

$leverageInt = [int]($Leverage.Split(':')[1])
$manifestRuns = @()
foreach ($candidate in $candidates) {
    foreach ($window in $windows) {
        $stageDir = Join-Path $ResultsRoot "$($candidate.id)/$($window.id)"
        New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
        $reportStem = "$($candidate.id.ToLower())_$($window.id)_report"
        $configPath = Join-Path $stageDir "$reportStem.ini"
        $config = @"
[Tester]
Expert=$ExpertSubdir\$($candidate.name)
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
        Write-Host "Running $($candidate.id) $($window.id): $($window.from) to $($window.to)..."
        $terminalProcess = Start-Process -FilePath $Terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @("/config:$configPath") -Wait -PassThru
        $found = Find-Mt5Report -ReportStem $reportStem -StartedAt $startedAt -StageDirectory $stageDir -Mt5DataFolder $Mt5DataFolder
        if (-not $found) { throw "No MT5 report found for $($candidate.id) $($window.id)" }
        $reportPath = Join-Path $stageDir $found.Name
        if ($found.FullName -ine $reportPath) { Copy-Item -LiteralPath $found.FullName -Destination $reportPath -Force }
        $metadata = [ordered]@{
            candidate_id=$candidate.id
            isolated_change=$candidate.isolated_change
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
            source_path=$candidate.source
            deployed_source_path=$compiled[$candidate.id].source
            deployed_binary_path=$compiled[$candidate.id].binary
            compile_log=$compiled[$candidate.id].compile_log
            report_path=$reportPath
            terminal_exit_code=$terminalProcess.ExitCode
        }
        $metadataPath = Join-Path $stageDir "run_metadata.json"
        $metadata | ConvertTo-Json -Depth 6 | Set-Content $metadataPath -Encoding UTF8
        $manifestRuns += $metadata
    }
}

$manifest = [ordered]@{
    protocol='PeakFX five-year robustness comparison'
    candidates=@('EXP2','EXP3A','EXP6A')
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
    generated_at=(Get-Date).ToString('o')
    runs=$manifestRuns
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $ResultsRoot 'robustness_manifest.json') -Encoding UTF8
Write-Host "Five-year robustness comparison completed: 15 fixed tests. Reserved OOS remains locked."
