param(
  [Parameter(Mandatory=$true)][string]$MetaTraderRoot,
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [Parameter(Mandatory=$true)][string]$CompiledCleanExp1Source,
  [Parameter(Mandatory=$true)][ValidateSet('2020_2021','2021_2022','2022_2023','2023_2024','2024_2025')][string]$WindowId,
  [double]$Deposit=10000.0,
  [string]$Leverage='1:100',
  [int]$WindowTimeoutMinutes=100
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$windowMap=@{
 '2020_2021'=@{from='2020.07.01';to='2021.06.30'}
 '2021_2022'=@{from='2021.07.01';to='2022.06.30'}
 '2022_2023'=@{from='2022.07.01';to='2023.06.30'}
 '2023_2024'=@{from='2023.07.01';to='2024.06.30'}
 '2024_2025'=@{from='2024.07.01';to='2025.06.30'}
}
$w=$windowMap[$WindowId]
$ResultsRoot=Join-Path $RepoRoot "artifacts/mt5-exp8-pullback-depth-$WindowId"
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
if($exp2Hash-ne'd3342cd2fd022646eade296f1dedfd4e4483ce51ce1731ffefba6e3ca0bdd287'){throw "EXP2 lineage hash mismatch: $exp2Hash"}

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
$binaryHash=(Get-FileHash $binary -Algorithm SHA256).Hash.ToLowerInvariant()

$diffPath=Join-Path $ResultsRoot 'exp2_to_exp8.diff.txt'
$psi=New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName='git.exe';$psi.Arguments="-c core.autocrlf=false diff --no-index --no-textconv -- `"$exp2`" `"$exp8`""
$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
$gp=New-Object System.Diagnostics.Process;$gp.StartInfo=$psi;[void]$gp.Start();$stdout=$gp.StandardOutput.ReadToEnd();$stderr=$gp.StandardError.ReadToEnd();$gp.WaitForExit()
$stdout|Set-Content $diffPath -Encoding UTF8
if($gp.ExitCode-gt 1){throw "Diff generation failed: $stderr"}

Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
$stage=Join-Path $ResultsRoot $WindowId;New-Item -ItemType Directory -Force -Path $stage|Out-Null
$stem="exp8_${WindowId}_report";$ini=Join-Path $stage "$stem.ini"
$lev=[int]($Leverage.Split(':')[1])
$cfg="[Tester]`r`nExpert=$ExpertSubdir\PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP8_PULLBACK_DEPTH`r`nSymbol=EURUSD`r`nPeriod=H1`r`nModel=4`r`nExecutionMode=0`r`nOptimization=0`r`nFromDate=$($w.from)`r`nToDate=$($w.to)`r`nForwardMode=0`r`nDeposit=$Deposit`r`nCurrency=USD`r`nLeverage=$lev`r`nReport=$stem`r`nReplaceReport=1`r`nShutdownTerminal=1`r`nVisual=0`r`n"
Set-Content $ini $cfg -Encoding ASCII
$started=Get-Date
Write-Host "START EXP8 $WindowId $($w.from) to $($w.to)"
$tp=Start-Process -FilePath $Terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @("/config:$ini") -PassThru
$deadline=$started.AddMinutes($WindowTimeoutMinutes)
while(-not $tp.HasExited){
 if((Get-Date)-ge$deadline){Stop-Process -Id $tp.Id -Force -ErrorAction SilentlyContinue;throw "MT5 window timeout after $WindowTimeoutMinutes minutes: $WindowId"}
 Start-Sleep -Seconds 60
 $tp.Refresh()
 Write-Host ("HEARTBEAT {0} window={1} elapsed_min={2:N1}" -f (Get-Date).ToString('o'),$WindowId,((Get-Date)-$started).TotalMinutes)
}
Write-Host "MT5 exited code=$($tp.ExitCode) window=$WindowId"

$roots=@($stage,$Mt5DataFolder,$MetaTraderRoot,(Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common'))|Where-Object{$_-and(Test-Path $_)}|Select-Object -Unique
$items=@();foreach($r in $roots){$items+=Get-ChildItem $r -File -Recurse -ErrorAction SilentlyContinue|Where-Object{$_.BaseName-eq$stem-and@('.htm','.html','.xml')-contains$_.Extension.ToLowerInvariant()-and$_.LastWriteTime-ge$started.AddMinutes(-1)}}
$found=$items|Sort-Object LastWriteTime -Descending|Select-Object -First 1
if(-not$found){throw "No report for $WindowId"}
$dest=Join-Path $stage $found.Name;if($found.FullName-ine$dest){Copy-Item $found.FullName $dest -Force}
$metadata=[ordered]@{candidate='EXP8_PULLBACK_DEPTH';window=$WindowId;start=$w.from;end=$w.to;symbol='EURUSD';timeframe='H1';model='every_tick_based_on_real_ticks';deposit=$Deposit;leverage=$Leverage;threshold_atr=0.50;applies_to_initial_and_replacement_pullbacks=$true;exp2_sha256=$exp2Hash;exp8_sha256=$exp8Hash;binary_sha256=$binaryHash;compile_log=$compileLog;diff=$diffPath;report=$dest;terminal_exit_code=$tp.ExitCode;oos_locked=$true;reserved_oos_not_tested=$true;completed_at=(Get-Date).ToString('o')}
$metadata|ConvertTo-Json -Depth 6|Set-Content (Join-Path $ResultsRoot 'run_metadata.json') -Encoding UTF8
Write-Host "COMPLETE EXP8 $WindowId report=$dest"
