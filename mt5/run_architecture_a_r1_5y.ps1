param(
  [Parameter(Mandatory=$true)][string]$MetaTraderRoot,
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [double]$Deposit=10000.0,
  [string]$Leverage='1:100'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$results=Join-Path $RepoRoot 'artifacts/architecture-a-r1-5y'
$compileDir=Join-Path $results 'compile'
$source=Join-Path $RepoRoot 'mt5/PeakFX_EURUSD_ARCH_A_SESSION_BREAKOUT.mq5'
$metaEditor=Join-Path $MetaTraderRoot 'metaeditor64.exe'
$terminal=Join-Path $MetaTraderRoot 'terminal64.exe'
foreach($p in @($source,$metaEditor,$terminal)){if(-not(Test-Path $p)){throw "Required path missing: $p"}}
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
if($compileText-notmatch '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b'){Get-Content $compileLog|ForEach-Object{Write-Host $_};throw 'Compile gate failed'}
$binary=[IO.Path]::ChangeExtension($deployed,'.ex5')
if(-not(Test-Path $binary)){throw 'Compiled binary missing'}
$sourceHash=(Get-FileHash $source -Algorithm SHA256).Hash.ToLowerInvariant()
$binaryHash=(Get-FileHash $binary -Algorithm SHA256).Hash.ToLowerInvariant()

function Stop-Mt5{Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue;Start-Sleep 2}
function Find-Report([string]$stem,[datetime]$started,[string]$stage){
 $roots=@($stage,$dataRoot,$MetaTraderRoot,(Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common'))|Where-Object{$_-and(Test-Path $_)}|Select-Object -Unique
 $items=@();foreach($r in $roots){$items+=Get-ChildItem $r -File -Recurse -ErrorAction SilentlyContinue|Where-Object{$_.BaseName-eq$stem-and@('.htm','.html','.xml')-contains$_.Extension.ToLowerInvariant()-and$_.LastWriteTime-ge$started.AddMinutes(-1)}}
 return $items|Sort-Object LastWriteTime -Descending|Select-Object -First 1
}

$configs=@(
 @{id='A01';buffer='0.05';target='1.25'},@{id='A02';buffer='0.05';target='1.50'},
 @{id='A03';buffer='0.10';target='1.25'},@{id='A04';buffer='0.10';target='1.50'},
 @{id='A05';buffer='0.15';target='1.25'},@{id='A06';buffer='0.15';target='1.50'}
)
$windows=@(
 @{id='2020_2021';from='2020.07.01';to='2021.06.30'},@{id='2021_2022';from='2021.07.01';to='2022.06.30'},
 @{id='2022_2023';from='2022.07.01';to='2023.06.30'},@{id='2023_2024';from='2023.07.01';to='2024.06.30'},
 @{id='2024_2025';from='2024.07.01';to='2025.06.30'}
)
$lev=[int]($Leverage.Split(':')[1]);$runs=@()
foreach($cfg in $configs){
 $setName="architecture_a_r1_$($cfg.id.ToLower()).set"
 $setPath=Join-Path $testerProfiles $setName
 $setText="InpBreakoutBufferAtr=$($cfg.buffer)||$($cfg.buffer)||0.01||0.50||N`r`nInpTargetR=$($cfg.target)||$($cfg.target)||0.05||3.00||N`r`nInpRequireH4EmaSlope=true||true||0||true||N`r`n"
 Set-Content $setPath $setText -Encoding Unicode
 $setHash=(Get-FileHash $setPath -Algorithm SHA256).Hash.ToLowerInvariant()
 foreach($w in $windows){
  $stage=Join-Path $results "$($cfg.id)\$($w.id)";New-Item -ItemType Directory -Force -Path $stage|Out-Null
  Copy-Item $setPath (Join-Path $stage $setName) -Force
  $stem="arch_a_r1_$($cfg.id.ToLower())_$($w.id)_report";$ini=Join-Path $stage "$stem.ini"
  $text="[Tester]`r`nExpert=PeakFX\PeakFX_EURUSD_ARCH_A_SESSION_BREAKOUT`r`nExpertParameters=$setName`r`nSymbol=EURUSD`r`nPeriod=M15`r`nModel=4`r`nExecutionMode=0`r`nOptimization=0`r`nFromDate=$($w.from)`r`nToDate=$($w.to)`r`nForwardMode=0`r`nDeposit=$Deposit`r`nCurrency=USD`r`nLeverage=$lev`r`nReport=$stem`r`nReplaceReport=1`r`nShutdownTerminal=1`r`nVisual=0`r`n"
  Set-Content $ini $text -Encoding ASCII
  Stop-Mt5;$started=Get-Date;Write-Host "Running A-R1 $($cfg.id) $($w.id) using $setName..."
  $tp=Start-Process -FilePath $terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @("/config:$ini") -Wait -PassThru
  $found=Find-Report $stem $started $stage;if(-not$found){throw "No report for A-R1 $($cfg.id) $($w.id)"}
  $dest=Join-Path $stage $found.Name;if($found.FullName-ine$dest){Copy-Item $found.FullName $dest -Force}
  $m=[ordered]@{architecture='A-R1';configuration=$cfg.id;buffer_atr=[double]$cfg.buffer;target_r=[double]$cfg.target;stop_atr_floor=1.0;h4_slope_revision=$true;parameter_set=$setName;parameter_set_sha256=$setHash;window=$w.id;start=$w.from;end=$w.to;symbol='EURUSD';timeframe='M15';model='real_ticks';deposit=$Deposit;leverage=$Leverage;source_sha256=$sourceHash;binary_sha256=$binaryHash;report=$dest;terminal_exit_code=$tp.ExitCode;oos_locked=$true}
  $m|ConvertTo-Json -Depth 5|Set-Content (Join-Path $stage 'run_metadata.json') -Encoding UTF8;$runs+=$m
 }
}
$manifest=[ordered]@{protocol='Architecture A-R1 final frozen revision';isolated_change='Require H4 EMA20 slope alignment';source_sha256=$sourceHash;binary_sha256=$binaryHash;compile_log=$compileLog;compile_exit_code=$cp.ExitCode;parameter_loading='MT5 .set files in MQL5/Profiles/Tester';configurations=$configs;windows=$windows;runs=$runs;oos_locked=$true;reserved_oos_not_tested=$true;final_revision=$true;no_further_revision_permitted=$true;generated_at=(Get-Date).ToString('o')}
$manifest|ConvertTo-Json -Depth 8|Set-Content (Join-Path $results 'architecture_a_r1_manifest.json') -Encoding UTF8
Write-Host 'Architecture A-R1 final batch complete. OOS remains locked.'
