param(
  [Parameter(Mandatory=$true)][string]$MetaTraderRoot,
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [double]$Deposit=10000.0,
  [string]$Leverage='1:100'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$results=Join-Path $RepoRoot 'artifacts/architecture-b-baseline-5y'
$compileDir=Join-Path $results 'compile'
$source=Join-Path $RepoRoot 'mt5/PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.mq5'
$spec=Join-Path $RepoRoot 'docs/ARCHITECTURE_B_FROZEN_BASELINE_SPEC.md'
$metaEditor=Join-Path $MetaTraderRoot 'metaeditor64.exe'
$terminal=Join-Path $MetaTraderRoot 'terminal64.exe'
foreach($p in @($source,$spec,$metaEditor,$terminal)){if(-not(Test-Path $p)){throw "Required path missing: $p"}}
New-Item -ItemType Directory -Force -Path $results,$compileDir|Out-Null

$terminalRoots=Get-ChildItem "$env:APPDATA\MetaQuotes\Terminal" -Directory -ErrorAction SilentlyContinue
$dataRoot=$null
foreach($root in $terminalRoots){if(Test-Path (Join-Path $root.FullName 'MQL5\Experts')){$dataRoot=$root.FullName;break}}
if(-not$dataRoot){throw 'MT5 data folder not found'}
$expertsDir=Join-Path $dataRoot 'MQL5\Experts\PeakFX'
$testerProfiles=Join-Path $dataRoot 'MQL5\Profiles\Tester'
New-Item -ItemType Directory -Force -Path $expertsDir,$testerProfiles|Out-Null
$deployed=Join-Path $expertsDir ([IO.Path]::GetFileName($source))
Copy-Item $source $deployed -Force

$compileLog=Join-Path $compileDir 'meta_compiler.log'
$cp=Start-Process -FilePath $metaEditor -ArgumentList @("/compile:$deployed","/log:$compileLog") -Wait -PassThru
if(-not(Test-Path $compileLog)){throw 'Compile log missing'}
$compileText=Get-Content $compileLog -Raw
if($compileText-notmatch '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b'){
  Get-Content $compileLog|ForEach-Object{Write-Host $_}
  throw 'Compile gate failed'
}
$binary=[IO.Path]::ChangeExtension($deployed,'.ex5')
if(-not(Test-Path $binary)){throw 'Compiled binary missing'}
$sourceHash=(Get-FileHash $source -Algorithm SHA256).Hash.ToLowerInvariant()
$binaryHash=(Get-FileHash $binary -Algorithm SHA256).Hash.ToLowerInvariant()
$specHash=(Get-FileHash $spec -Algorithm SHA256).Hash.ToLowerInvariant()
Copy-Item $spec (Join-Path $results 'ARCHITECTURE_B_FROZEN_BASELINE_SPEC.md') -Force

function Stop-Mt5{
  Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep 2
}
function Find-Report([string]$stem,[datetime]$started,[string]$stage){
  $roots=@($stage,$dataRoot,$MetaTraderRoot,(Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common'))|Where-Object{$_-and(Test-Path $_)}|Select-Object -Unique
  $items=@()
  foreach($r in $roots){
    $items+=Get-ChildItem $r -File -Recurse -ErrorAction SilentlyContinue|Where-Object{
      $_.BaseName-eq$stem -and @('.htm','.html','.xml')-contains$_.Extension.ToLowerInvariant() -and $_.LastWriteTime-ge$started.AddMinutes(-1)
    }
  }
  return $items|Sort-Object LastWriteTime -Descending|Select-Object -First 1
}
function Set-Line([string]$name,[string]$value,[string]$start,[string]$step,[string]$stop,[string]$opt='N'){
  return "$name=$value||$start||$step||$stop||$opt"
}

$configs=@(
  @{id='B01';exp='1.50';fast='false'},
  @{id='B02';exp='2.00';fast='false'},
  @{id='B03';exp='1.50';fast='true'},
  @{id='B04';exp='2.00';fast='true'}
)
$windows=@(
  @{id='2020_2021';from='2020.07.01';to='2021.06.30'},
  @{id='2021_2022';from='2021.07.01';to='2022.06.30'},
  @{id='2022_2023';from='2022.07.01';to='2023.06.30'},
  @{id='2023_2024';from='2023.07.01';to='2024.06.30'},
  @{id='2024_2025';from='2024.07.01';to='2025.06.30'}
)
$expectedRuns=$configs.Count*$windows.Count
if($expectedRuns-ne20){throw "Frozen matrix must contain exactly 20 runs; found $expectedRuns"}
$levParts=$Leverage.Split(':')
if($levParts.Count-ne2){throw "Invalid leverage format: $Leverage"}
$lev=[int]$levParts[1]
$runs=@()

foreach($cfg in $configs){
  $setName="architecture_b_$($cfg.id.ToLower()).set"
  $setPath=Join-Path $testerProfiles $setName
  $setLines=@(
    (Set-Line 'InpSymbol' 'EURUSD' 'EURUSD' '' 'EURUSD'),
    (Set-Line 'InpRiskPercent' '0.25' '0.25' '0.01' '0.25'),
    (Set-Line 'InpDailyLossLimitPercent' '1.0' '1.0' '0.1' '1.0'),
    (Set-Line 'InpWeeklyLossLimitPercent' '2.0' '2.0' '0.1' '2.0'),
    (Set-Line 'InpAtrPeriod' '14' '14' '1' '14'),
    (Set-Line 'InpPercentileLookback' '180' '180' '1' '180'),
    (Set-Line 'InpCompressionPercentile' '0.25' '0.25' '0.01' '0.25'),
    (Set-Line 'InpMinCompressionDays' '5' '5' '1' '5'),
    (Set-Line 'InpMaxCompressionDays' '15' '15' '1' '15'),
    (Set-Line 'InpExpansionMultiplier' $cfg.exp $cfg.exp '0.10' $cfg.exp),
    (Set-Line 'InpFastFailExit' $cfg.fast $cfg.fast '0' $cfg.fast),
    (Set-Line 'InpFastFailBars' '8' '8' '1' '8'),
    (Set-Line 'InpTargetR' '2.0' '2.0' '0.1' '2.0'),
    (Set-Line 'InpMaxSpreadPips' '2.0' '2.0' '0.1' '2.0'),
    (Set-Line 'InpDeviationPoints' '10' '10' '1' '10'),
    (Set-Line 'InpRequireTickVolume' 'false' 'false' '0' 'false'),
    (Set-Line 'InpMagic' '26080602' '26080602' '1' '26080602')
  )
  $setText=($setLines -join "`r`n")+"`r`n"
  Set-Content $setPath $setText -Encoding Unicode
  $setHash=(Get-FileHash $setPath -Algorithm SHA256).Hash.ToLowerInvariant()

  foreach($w in $windows){
    $stage=Join-Path $results "$($cfg.id)\$($w.id)"
    New-Item -ItemType Directory -Force -Path $stage|Out-Null
    Copy-Item $setPath (Join-Path $stage $setName) -Force
    $stem="arch_b_$($cfg.id.ToLower())_$($w.id)_report"
    $ini=Join-Path $stage "$stem.ini"
    $text="[Tester]`r`nExpert=PeakFX\PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION`r`nExpertParameters=$setName`r`nSymbol=EURUSD`r`nPeriod=H1`r`nModel=4`r`nExecutionMode=0`r`nOptimization=0`r`nFromDate=$($w.from)`r`nToDate=$($w.to)`r`nForwardMode=0`r`nDeposit=$Deposit`r`nCurrency=USD`r`nLeverage=$lev`r`nReport=$stem`r`nReplaceReport=1`r`nShutdownTerminal=1`r`nVisual=0`r`n"
    Set-Content $ini $text -Encoding ASCII
    Stop-Mt5
    $started=Get-Date
    Write-Host "Running $($cfg.id) $($w.id) using $setName..."
    $tp=Start-Process -FilePath $terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @("/config:$ini") -Wait -PassThru
    $found=Find-Report $stem $started $stage
    if(-not$found){throw "No report for $($cfg.id) $($w.id)"}
    $dest=Join-Path $stage $found.Name
    if($found.FullName-ine$dest){Copy-Item $found.FullName $dest -Force}
    $reportHash=(Get-FileHash $dest -Algorithm SHA256).Hash.ToLowerInvariant()
    $m=[ordered]@{
      architecture='B'; configuration=$cfg.id; expansion_multiplier=[double]$cfg.exp
      fast_fail_exit=[bool]::Parse($cfg.fast); tick_volume_revision=$false
      parameter_set=$setName; parameter_set_sha256=$setHash
      frozen_spec_sha256=$specHash; window=$w.id; start=$w.from; end=$w.to
      symbol='EURUSD'; timeframe='H1'; model='real_ticks'; deposit=$Deposit; leverage=$Leverage
      source_sha256=$sourceHash; binary_sha256=$binaryHash; report=$dest; report_sha256=$reportHash
      terminal_exit_code=$tp.ExitCode; oos_locked=$true
    }
    $m|ConvertTo-Json -Depth 5|Set-Content (Join-Path $stage 'run_metadata.json') -Encoding UTF8
    $runs+=$m
  }
}
if($runs.Count-ne$expectedRuns){throw "Run count mismatch: expected $expectedRuns, produced $($runs.Count)"}
$manifest=[ordered]@{
  protocol='Architecture B frozen baseline'; expected_run_count=$expectedRuns; completed_run_count=$runs.Count
  source_sha256=$sourceHash; binary_sha256=$binaryHash; frozen_spec_sha256=$specHash
  compile_log=$compileLog; compile_exit_code=$cp.ExitCode
  parameter_loading='Explicit frozen MT5 .set files in MQL5/Profiles/Tester'
  configurations=$configs; windows=$windows; runs=$runs
  oos_locked=$true; reserved_oos_not_tested=$true
  predeclared_revision='B-R1 tick-volume confirmation'; revision_enabled=$false
  generated_at=(Get-Date).ToString('o')
}
$manifest|ConvertTo-Json -Depth 8|Set-Content (Join-Path $results 'architecture_b_manifest.json') -Encoding UTF8
Write-Host "Architecture B baseline batch complete: $($runs.Count) verified reports. OOS remains locked."
