param(
    [Parameter(Mandatory=$true)][string]$MetaTraderRoot,
    [Parameter(Mandatory=$true)][string]$RepoRoot,
    [Parameter(Mandatory=$true)][string]$CompiledCleanExp1Source,
    [double]$Deposit=10000.0,
    [string]$Leverage="1:100"
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=Join-Path $RepoRoot "artifacts/mt5-exp5-diagnostic"
$generated=Join-Path $root "generated"
New-Item -ItemType Directory -Force -Path $generated | Out-Null

$exp2=Join-Path $generated "PeakFX_EXP2.mq5"
$exp3a=Join-Path $generated "PeakFX_EXP3A.mq5"
$candidateName="PeakFX_EURUSD_H1_EXP5_DIAGNOSTIC"
$candidate=Join-Path $generated "$candidateName.mq5"

& python (Join-Path $RepoRoot "research/build_confirmed_breakout_exp2_candidate.py") $CompiledCleanExp1Source $exp2
if($LASTEXITCODE-ne 0){throw "EXP2 generation failed"}
& python (Join-Path $RepoRoot "research/build_confirmed_breakout_exp3a_candidate.py") $exp2 $exp3a
if($LASTEXITCODE-ne 0){throw "EXP3A generation failed"}
& python (Join-Path $RepoRoot "research/build_exp5_diagnostic_candidate.py") $exp3a $candidate
if($LASTEXITCODE-ne 0){throw "EXP5 diagnostic generation failed"}

$meta=Join-Path $MetaTraderRoot "metaeditor64.exe"
$terminal=Join-Path $MetaTraderRoot "terminal64.exe"
foreach($p in @($meta,$terminal,$candidate)){if(-not(Test-Path $p)){throw "Missing required path: $p"}}

$expertsRoot=Split-Path -Parent $CompiledCleanExp1Source
$mt5Data=Split-Path -Parent (Split-Path -Parent $expertsRoot)
$deployDir=Join-Path $expertsRoot "PeakFX"
New-Item -ItemType Directory -Force -Path $deployDir | Out-Null
$deployed=Join-Path $deployDir "$candidateName.mq5"
Copy-Item $candidate $deployed -Force

$compileDir=Join-Path $root "compile"
New-Item -ItemType Directory -Force -Path $compileDir | Out-Null
$compileLog=Join-Path $compileDir "meta_compiler.log"
$p=Start-Process $meta -ArgumentList @("/compile:$deployed","/log:$compileLog") -Wait -PassThru
if(-not(Test-Path $compileLog)){throw "Compile log not created"}
$compileText=Get-Content $compileLog -Raw
if($compileText-notmatch '(?i)\b0\s+errors?\s*,\s*0\s+warnings?\b'){Get-Content $compileLog;throw "Compile gate failed"}
$binary=[IO.Path]::ChangeExtension($deployed,".ex5")
if(-not(Test-Path $binary)){throw "EX5 missing after clean compile"}
Write-Host "Compile gate passed: 0 errors, 0 warnings"

function Stop-Mt5 { Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep 2 }
function Find-Report([string]$stem,[datetime]$started,[string]$stageDir){
  $roots=@($stageDir,$mt5Data,$MetaTraderRoot,(Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common'))|Where-Object{$_-and(Test-Path $_)}|Select-Object -Unique
  $all=@(); foreach($r in $roots){$all+=Get-ChildItem $r -File -Recurse -ErrorAction SilentlyContinue|Where-Object{$_.BaseName-eq$stem-and$_.Extension-match '^\.html?$|^\.xml$'-and$_.LastWriteTime-ge$started.AddMinutes(-1)}}
  return $all|Sort-Object LastWriteTime -Descending|Select-Object -First 1
}

$commonDiag=Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files\PeakFX\exp5_diagnostic_summary.csv"
$stages=@(
  @{Name="smoke_1m";From="2025.06.01";To="2025.06.30"},
  @{Name="screen_12m";From="2024.07.01";To="2025.06.30"}
)
$lev=[int]($Leverage.Split(':')[1])
foreach($s in $stages){
  $dir=Join-Path $root $s.Name; New-Item -ItemType Directory -Force -Path $dir|Out-Null
  if(Test-Path $commonDiag){Remove-Item $commonDiag -Force}
  $stem="$($s.Name)_report"; $ini=Join-Path $dir "$($s.Name).ini"
  @"
[Tester]
Expert=PeakFX\$candidateName
Symbol=EURUSD
Period=H1
Model=4
ExecutionMode=0
Optimization=0
FromDate=$($s.From)
ToDate=$($s.To)
ForwardMode=0
Deposit=$Deposit
Currency=USD
Leverage=$lev
Report=$stem
ReplaceReport=1
ShutdownTerminal=1
Visual=0
"@ | Set-Content $ini -Encoding ASCII
  Stop-Mt5; $started=Get-Date
  $tp=Start-Process $terminal -WorkingDirectory $MetaTraderRoot -ArgumentList @("/config:$ini") -Wait -PassThru
  $report=Find-Report $stem $started $dir
  if(-not$report){throw "No report found for $($s.Name), terminal exit $($tp.ExitCode)"}
  $dest=Join-Path $dir $report.Name; if($report.FullName-ine$dest){Copy-Item $report.FullName $dest -Force}
  if(-not(Test-Path $commonDiag)){throw "Diagnostic summary missing after $($s.Name): $commonDiag"}
  Copy-Item $commonDiag (Join-Path $dir "$($s.Name)_diagnostic_summary.csv") -Force
  [ordered]@{
    candidate_id="peakfx_exp5_diagnostic_v1_47"; parent="peakfx_exp3a_er20_035_v1_46";
    isolated_change="diagnostic rejection counters only; trading decisions unchanged";
    stage=$s.Name; start_date=$s.From.Replace('.','-'); end_date=$s.To.Replace('.','-');
    symbol="EURUSD"; timeframe="H1"; modeling="every_tick_based_on_real_ticks";
    deposit=$Deposit; leverage=$Leverage; report_path=$dest;
    diagnostic_summary_path=(Join-Path $dir "$($s.Name)_diagnostic_summary.csv"); oos_locked=$true
  }|ConvertTo-Json -Depth 4|Set-Content (Join-Path $dir "$($s.Name)_run_metadata.json") -Encoding UTF8
  Write-Host "Completed $($s.Name): $dest"
}
Write-Host "EXP5 diagnostic completed. Trading logic unchanged; OOS remains locked."
