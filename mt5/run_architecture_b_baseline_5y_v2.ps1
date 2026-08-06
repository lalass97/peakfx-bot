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
$frozenDir=Join-Path $results 'frozen_inputs'
$diagnosticsDir=Join-Path $results 'diagnostics'
$source=Join-Path $RepoRoot 'mt5/PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.mq5'
$spec=Join-Path $RepoRoot 'docs/ARCHITECTURE_B_FROZEN_BASELINE_SPEC.md'
$verifier=Join-Path $RepoRoot 'scripts/verify_architecture_b_artifact.py'
$metaEditor=Join-Path $MetaTraderRoot 'metaeditor64.exe'
$terminal=Join-Path $MetaTraderRoot 'terminal64.exe'
foreach($p in @($source,$spec,$verifier,$metaEditor,$terminal)){if(-not(Test-Path $p)){throw "Required path missing: $p"}}
if($Deposit-le0){throw 'Deposit must be positive'}
if(Test-Path $results){Remove-Item $results -Recurse -Force}
New-Item -ItemType Directory -Force -Path $results,$compileDir,$frozenDir,$diagnosticsDir|Out-Null

function Normalize-Path([string]$Path){
  return ([IO.Path]::GetFullPath($Path)).TrimEnd('\\').ToLowerInvariant()
}
function Resolve-TerminalDataRoot([string]$InstallRoot){
  $base=Join-Path $env:APPDATA 'MetaQuotes\Terminal'
  if(-not(Test-Path $base)){throw "MT5 terminal data base not found: $base"}
  $wanted=Normalize-Path $InstallRoot
  $matches=@()
  $inventory=@()
  foreach($root in Get-ChildItem $base -Directory -ErrorAction Stop){
    $origin=Join-Path $root.FullName 'origin.txt'
    if(-not(Test-Path $origin)){continue}
    $originText=(Get-Content $origin -Raw -ErrorAction SilentlyContinue).Trim()
    $inventory+=[ordered]@{data_root=$root.FullName;origin=$originText}
    if($originText -and (Normalize-Path $originText)-eq$wanted){$matches+=$root.FullName}
  }
  $inventory|ConvertTo-Json -Depth 4|Set-Content (Join-Path $diagnosticsDir 'terminal_data_roots.json') -Encoding UTF8
  if($matches.Count-ne1){throw "Expected exactly one MT5 data folder for '$InstallRoot'; found $($matches.Count). See diagnostics/terminal_data_roots.json"}
  return $matches[0]
}
function Stop-Mt5{
  Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
}
function Set-Line([string]$name,[string]$value,[string]$start,[string]$step,[string]$stop,[string]$opt='N'){
  return "$name=$value||$start||$step||$stop||$opt"
}
function Read-ReportText([string]$Path){
  $bytes=[IO.File]::ReadAllBytes($Path)
  if($bytes.Length-ge2 -and $bytes[0]-eq0xFF -and $bytes[1]-eq0xFE){return [Text.Encoding]::Unicode.GetString($bytes)}
  return [Text.Encoding]::UTF8.GetString($bytes)
}
function Read-Number([string]$Text,[string]$Pattern,[string]$Label){
  $m=[regex]::Match($Text,$Pattern,[Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if(-not$m.Success){throw "Report field missing: $Label"}
  return [double]::Parse(($m.Groups[1].Value-replace',',''),[Globalization.CultureInfo]::InvariantCulture)
}
function Assert-RealBacktest([string]$Report,[double]$ExpectedDeposit,[string]$From,[string]$To,[string]$Cell){
  $text=Read-ReportText $Report
  $deposit=Read-Number $text 'Initial Deposit:\s*</td>\s*<td[^>]*><b>([0-9,]+(?:\.[0-9]+)?)' 'Initial Deposit'
  $bars=Read-Number $text 'Bars:\s*</td>\s*<td[^>]*><b>([0-9,]+)' 'Bars'
  $ticks=Read-Number $text 'Ticks:\s*</td>\s*<td[^>]*><b>([0-9,]+)' 'Ticks'
  $symbols=Read-Number $text 'Symbols:\s*</td>\s*<td[^>]*><b>([0-9,]+)' 'Symbols'
  if([math]::Abs($deposit-$ExpectedDeposit)-gt0.01){throw "$Cell invalid deposit: report=$deposit expected=$ExpectedDeposit"}
  if($bars-le0 -or $ticks-le0 -or $symbols-le0){throw "$Cell empty execution: bars=$bars ticks=$ticks symbols=$symbols"}
  $fromDisplay=$From-replace'\.','.'
  $toDisplay=$To-replace'\.','.'
  if($text-notmatch[regex]::Escape($fromDisplay) -or $text-notmatch[regex]::Escape($toDisplay)){throw "$Cell report period does not contain $From to $To"}
  return [ordered]@{initial_deposit=$deposit;bars=[long]$bars;ticks=[long]$ticks;symbols=[int]$symbols}
}
function Copy-RecentLogs([datetime]$Started,[string]$CellDir,[string]$DataRoot){
  $logOut=Join-Path $CellDir 'logs'
  New-Item -ItemType Directory -Force -Path $logOut|Out-Null
  $roots=@((Join-Path $DataRoot 'logs'),(Join-Path $DataRoot 'Tester\logs'))
  foreach($r in $roots){
    if(-not(Test-Path $r)){continue}
    Get-ChildItem $r -File -ErrorAction SilentlyContinue|Where-Object{$_.LastWriteTime-ge$Started.AddMinutes(-2)}|ForEach-Object{
      Copy-Item $_.FullName (Join-Path $logOut ((Split-Path $r -Leaf)+'_'+$_.Name)) -Force
    }
  }
}

$dataRoot=Resolve-TerminalDataRoot $MetaTraderRoot
$expertsDir=Join-Path $dataRoot 'MQL5\Experts\PeakFX'
$testerProfiles=Join-Path $dataRoot 'MQL5\Profiles\Tester'
New-Item -ItemType Directory -Force -Path $expertsDir,$testerProfiles|Out-Null
$deployed=Join-Path $expertsDir ([IO.Path]::GetFileName($source))
Copy-Item $source $deployed -Force

$compileLog=Join-Path $compileDir 'meta_compiler.log'
$cp=Start-Process -FilePath $metaEditor -ArgumentList @("/compile:`"$deployed`"","/log:`"$compileLog`"") -Wait -PassThru
if(-not(Test-Path $compileLog)){throw 'Compile log missing'}
$compileText=Get-Content $compileLog -Raw
if($compileText-notmatch'(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b'){throw 'Compile gate failed'}
$binary=[IO.Path]::ChangeExtension($deployed,'.ex5')
if(-not(Test-Path $binary)){throw 'Compiled binary missing'}
$sourceHash=(Get-FileHash $source -Algorithm SHA256).Hash.ToLowerInvariant()
$binaryHash=(Get-FileHash $binary -Algorithm SHA256).Hash.ToLowerInvariant()
$specHash=(Get-FileHash $spec -Algorithm SHA256).Hash.ToLowerInvariant()
Copy-Item $source,$binary,$spec,$verifier -Destination $frozenDir -Force

$configs=@(
  @{id='B01';exp='1.50';fast='false'},@{id='B02';exp='2.00';fast='false'},
  @{id='B03';exp='1.50';fast='true'},@{id='B04';exp='2.00';fast='true'}
)
$windows=@(
  @{id='2020_2021';from='2020.07.01';to='2021.06.30'},@{id='2021_2022';from='2021.07.01';to='2022.06.30'},
  @{id='2022_2023';from='2022.07.01';to='2023.06.30'},@{id='2023_2024';from='2023.07.01';to='2024.06.30'},
  @{id='2024_2025';from='2024.07.01';to='2025.06.30'}
)
$levParts=$Leverage.Split(':');if($levParts.Count-ne2){throw "Invalid leverage: $Leverage"};$lev=[int]$levParts[1]
$runs=@()
foreach($cfg in $configs){
  $setName="architecture_b_$($cfg.id.ToLower()).set";$setPath=Join-Path $testerProfiles $setName
  $setLines=@(
    (Set-Line 'InpSymbol' 'EURUSD' 'EURUSD' '' 'EURUSD'),(Set-Line 'InpRiskPercent' '0.25' '0.25' '0.01' '0.25'),
    (Set-Line 'InpDailyLossLimitPercent' '1.0' '1.0' '0.1' '1.0'),(Set-Line 'InpWeeklyLossLimitPercent' '2.0' '2.0' '0.1' '2.0'),
    (Set-Line 'InpAtrPeriod' '14' '14' '1' '14'),(Set-Line 'InpPercentileLookback' '180' '180' '1' '180'),
    (Set-Line 'InpCompressionPercentile' '0.25' '0.25' '0.01' '0.25'),(Set-Line 'InpMinCompressionDays' '5' '5' '1' '5'),
    (Set-Line 'InpMaxCompressionDays' '15' '15' '1' '15'),(Set-Line 'InpExpansionMultiplier' $cfg.exp $cfg.exp '0.10' $cfg.exp),
    (Set-Line 'InpFastFailExit' $cfg.fast $cfg.fast '0' $cfg.fast),(Set-Line 'InpFastFailBars' '8' '8' '1' '8'),
    (Set-Line 'InpTargetR' '2.0' '2.0' '0.1' '2.0'),(Set-Line 'InpMaxSpreadPips' '2.0' '2.0' '0.1' '2.0'),
    (Set-Line 'InpDeviationPoints' '10' '10' '1' '10'),(Set-Line 'InpRequireTickVolume' 'false' 'false' '0' 'false'),
    (Set-Line 'InpMagic' '26080602' '26080602' '1' '26080602')
  )
  Set-Content $setPath (($setLines-join"`r`n")+"`r`n") -Encoding Unicode
  $setHash=(Get-FileHash $setPath -Algorithm SHA256).Hash.ToLowerInvariant();Copy-Item $setPath (Join-Path $frozenDir $setName) -Force
  foreach($w in $windows){
    $cell="$($cfg.id)/$($w.id)";$stage=Join-Path $results "$($cfg.id)\$($w.id)";New-Item -ItemType Directory -Force -Path $stage|Out-Null
    Copy-Item $setPath (Join-Path $stage $setName) -Force
    $stem="arch_b_$($cfg.id.ToLower())_$($w.id)_report";$ini=Join-Path $stage "$stem.ini";$reportBase=Join-Path $stage $stem
    $iniText="[Tester]`r`nExpert=PeakFX\PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION`r`nExpertParameters=$setName`r`nSymbol=EURUSD`r`nPeriod=H1`r`nModel=4`r`nExecutionMode=0`r`nOptimization=0`r`nFromDate=$($w.from)`r`nToDate=$($w.to)`r`nForwardMode=0`r`nDeposit=$Deposit`r`nCurrency=USD`r`nLeverage=$lev`r`nReport=$reportBase`r`nReplaceReport=1`r`nShutdownTerminal=1`r`nVisual=0`r`n"
    Set-Content $ini $iniText -Encoding ASCII
    Stop-Mt5;$started=Get-Date;Write-Host "Running $cell on data root $dataRoot"
    $tp=Start-Process -FilePath $terminal -WorkingDirectory $MetaTraderRoot -ArgumentList "/config:`"$ini`"" -Wait -PassThru
    Copy-RecentLogs $started $stage $dataRoot
    $report=@("$reportBase.htm","$reportBase.html","$reportBase.xml")|Where-Object{Test-Path $_}|Select-Object -First 1
    if(-not$report){throw "$cell produced no report"}
    $execution=Assert-RealBacktest $report $Deposit $w.from $w.to $cell
    $reportHash=(Get-FileHash $report -Algorithm SHA256).Hash.ToLowerInvariant()
    $m=[ordered]@{architecture='B';configuration=$cfg.id;window=$w.id;start=$w.from;end=$w.to;expansion_multiplier=[double]$cfg.exp;fast_fail_exit=[bool]::Parse($cfg.fast);tick_volume_revision=$false;parameter_set=$setName;parameter_set_sha256=$setHash;spec_sha256=$specHash;symbol='EURUSD';timeframe='H1';model='real_ticks';deposit=$Deposit;leverage=$Leverage;source_sha256=$sourceHash;binary_sha256=$binaryHash;report=$report;report_sha256=$reportHash;terminal_exit_code=$tp.ExitCode;oos_locked=$true;execution=$execution;terminal_data_root=$dataRoot}
    $m|ConvertTo-Json -Depth 6|Set-Content (Join-Path $stage 'run_metadata.json') -Encoding UTF8;$runs+=$m
  }
}
if($runs.Count-ne20){throw "Expected 20 valid runs, got $($runs.Count)"}
$manifest=[ordered]@{protocol='Architecture B frozen baseline';expected_run_count=20;completed_run_count=$runs.Count;source_sha256=$sourceHash;binary_sha256=$binaryHash;spec_sha256=$specHash;compile_log=$compileLog;compile_exit_code=$cp.ExitCode;terminal_data_root=$dataRoot;configurations=$configs;windows=$windows;runs=$runs;oos_locked=$true;reserved_oos_not_tested=$true;revision_enabled=$false;generated_at=(Get-Date).ToString('o')}
$manifest|ConvertTo-Json -Depth 9|Set-Content (Join-Path $results 'architecture_b_manifest.json') -Encoding UTF8
Write-Host 'Architecture B baseline complete: 20 non-empty real-tick reports.'
