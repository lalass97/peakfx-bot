param(
  [Parameter(Mandatory=$true)][string]$MetaTraderRoot,
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [Parameter(Mandatory=$true)][string]$CompiledCleanExp1Source,
  [double]$Deposit=10000.0,
  [string]$Leverage='1:100'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$ResultsRoot=Join-Path $RepoRoot 'artifacts/mt5-exp8-pullback-depth-5y'
$GeneratedDir=Join-Path $ResultsRoot 'generated'
$CompileDir=Join-Path $ResultsRoot 'compile'
$Builder=Join-Path $RepoRoot 'research/build_exp8_pullback_depth_candidate.py'
$Exp2Builder=Join-Path $RepoRoot 'research/build_confirmed_breakout_exp2_candidate.py'
$MetaEditor=Join-Path $MetaTraderRoot 'metaeditor64.exe'
$Terminal=Join-Path $MetaTraderRoot 'terminal64.exe'
foreach($p in @($MetaEditor,$Terminal,$CompiledCleanExp1Source,$Builder,$Exp2Builder)){if(-not(Test-Path $p)){throw "Required path not found: $p"}}
New-Item -ItemType Directory -Force -Path $GeneratedDir,$CompileDir|Out-Null

$exp2=Join-Path $GeneratedDir 'PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5'
$exp8=Join-Path $GeneratedDir 'PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP8_PULLBACK_DEPTH.mq5'
& python $Exp2Builder $CompiledCleanExp1Source $exp2
if($LASTEXITCODE-ne 0){throw 'EXP2 generation failed'}
& python $Builder $exp2 $exp8
if($LASTEXITCODE-ne 0){throw 'EXP8 generation failed'}

$exp2Hash=(Get-FileHash $exp2 -Algorithm SHA256).Hash.ToLowerInvariant()
$exp8Hash=(Get-FileHash $exp8 -Algorithm SHA256).Hash.ToLowerInvariant()
$expectedExp2='d3342cd2'
if(-not $exp2Hash.StartsWith($expectedExp2)){throw "EXP2 lineage hash mismatch: $exp2Hash"}

$ExpertsRoot=Split-Path -Parent $CompiledCleanExp1Source
$Mt5DataFolder=Split-Path -Parent (Split-Path -Parent $ExpertsRoot)
$ExpertSubdir='PeakFX'
$ExpertsDir=Join-Path $ExpertsRoot $ExpertSubdir
New-Item -ItemType Directory -Force -Path $ExpertsDir|Out-Null
$deployed=Join-Path $ExpertsDir ([IO.Path]::GetFileName($exp8))
Copy-Item $exp8 $deployed -Force
$compileLog=Join-Path $CompileDir 'meta_compiler.log'
$cp=Start-Process -FilePath $MetaEditor -ArgumentList @("/compile:$deployed","/log:$compileLog") -Wait -PassThru
if(-not(Test-Path $compileLog)){throw 'Compile log missing'}
$ct=Get-Content $compileLog -Raw
if($ct-notmatch '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b'){Get-Content $compileLog|ForEach-Object{Write-Host $_};throw 'Compile gate failed'}
$binary=[IO.Path]::ChangeExtension($deployed,'.ex5')
if(-not(Test-Path $binary)){throw 'EXP8 binary missing'}

$diffPath=Join-Path $ResultsRoot 'exp2_to_exp8.diff.txt'
& git diff --no-index -- $exp2 $exp8 2>$null | Set-Content $diffPath -Encoding UTF8
if($LASTEXITCODE -gt 1){throw 'Diff generation failed'}

function Stop-Mt5 { Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue;Start-Sleep 2 }
function Find-Report([string]$stem,[datetime]$started,[string]$stage){
  $roots=@($stage,$Mt5DataFolder,$MetaTraderRoot,(Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common'))|Where-Object{$_-and(Test-Path $_)}|Select-Object -Unique
  $items=@();foreach($r in $roots){$items+=Get-ChildItem $r -File -Recurse -ErrorAction SilentlyContinue|Where-Object{$_.BaseName-eq$stem-and@('.htm','.html','.xml')-contains$_.Extension.ToLowerInvariant()-and$_.LastWriteTime-ge$started.AddMinutes(-1)}}
  return $items|Sort-Object LastWriteTime -Descending|Select-Object -First 1
}

$windows=@(
 @{id='2020_2021';from='2020.07.01';to='2021.06.30'},
 @{id='2021_2022';from='2021.07.01';to='2022.06.30'},
 @{id='2022_2023';from='2022.07.01';to='2023.06.30'},
 @{id='2023_2024';from='2023.07.01';to='2024.06.30'},
 @{id='2024_2025';from='2024.07.01';to='2025.06.30'}
)
$lev=[int]($Leverage.Split(':')[1]);$runs=@()
foreach($w in $windows){
 $stage=Join-Path $ResultsRoot $w.id;New-Item -ItemType Directory -Force -Path $stage|Out-Null
 $stem="exp8_$($w.id)_report";$ini=Join-Path $stage "$stem.ini"
 $cfg="[Tester]`r`nExpert=$ExpertSubdir\PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP8_PULLBACK_DEPTH`r`nSymbol=EURUSD`r`nPeriod=H1`r`nModel=4`r`nExecutionMode=0`r`nOptimization=0`r`nFromDate=$($w.from)`r`nToDate=$($w.to)`r`nForwardMode=0`r`nDeposit=$Deposit`r`nCurrency=USD`r`nLeverage=$lev`r`nReport=$stem`r`nReplaceReport=1`r`nShutdownTerminal=1`r`nVisual=0`r`n"
 Set-Content $ini $cfg -Encoding ASCII
 Stop-Mt5;$started=Get-Date;Write-Host "Running EXP8 $($w.id)..."
 $tp=Start-Process -FilePath $Terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @("/config:$ini") -Wait -PassThru
 $found=Find-Report $stem $started $stage;if(-not$found){throw "No report for $($w.id)"}
 $dest=Join-Path $stage $found.Name;if($found.FullName-ine$dest){Copy-Item $found.FullName $dest -Force}
 $m=[ordered]@{candidate='EXP8_PULLBACK_DEPTH';window=$w.id;start=$w.from;end=$w.to;symbol='EURUSD';timeframe='H1';model='every_tick_based_on_real_ticks';deposit=$Deposit;leverage=$Leverage;threshold_atr=0.50;applies_to_initial_and_replacement_pullbacks=$true;exp2_sha256=$exp2Hash;exp8_sha256=$exp8Hash;report=$dest;terminal_exit_code=$tp.ExitCode;oos_locked=$true}
 $m|ConvertTo-Json -Depth 5|Set-Content (Join-Path $stage 'run_metadata.json') -Encoding UTF8;$runs+=$m
}
$manifest=[ordered]@{protocol='EXP8 frozen pullback depth 0.50 ATR';isolated_change='Require wick depth >=0.50 ATR in shared pullback functions';replacement_behavior='criterion intentionally applies to replacement pullbacks';exp2_sha256=$exp2Hash;exp8_sha256=$exp8Hash;compile_log=$compileLog;compile_exit_code=$cp.ExitCode;windows=$windows;runs=$runs;oos_locked=$true;reserved_oos_not_tested=$true;further_threshold_search_prohibited=$true;generated_at=(Get-Date).ToString('o')}
$manifest|ConvertTo-Json -Depth 8|Set-Content (Join-Path $ResultsRoot 'exp8_manifest.json') -Encoding UTF8
Write-Host 'EXP8 five-year batch complete. OOS remains locked.'
