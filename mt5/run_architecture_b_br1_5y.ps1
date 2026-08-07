param(
  [Parameter(Mandatory=$true)][string]$MetaTraderRoot,
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [double]$Deposit=10000.0,
  [string]$Leverage='1:100'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$baseRunner=Join-Path $RepoRoot 'mt5/run_architecture_b_baseline_5y_v2.ps1'
if(-not(Test-Path $baseRunner)){throw "Base runner missing: $baseRunner"}

$patchedRunner=Join-Path $env:TEMP 'run_architecture_b_br1_5y_patched.ps1'
$text=Get-Content $baseRunner -Raw

# Preserve the frozen strategy and change only the one predeclared B-R1 axis.
$text=$text.Replace("'artifacts/architecture-b-baseline-5y'","'artifacts/architecture-b-br1-5y'")

$oldExpert='Expert=PeakFX\PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION'
$newExpert='Expert=PeakFX\PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.ex5'
if($text-notlike "*$oldExpert*"){throw 'Expected Architecture B Expert line not found'}
$text=$text.Replace($oldExpert,$newExpert)

$oldSymbol="(Set-Line 'InpSymbol' 'EURUSD' 'EURUSD' '' 'EURUSD')"
$newSymbol="'InpSymbol=EURUSD'"
if($text-notlike "*$oldSymbol*"){throw 'Expected string symbol parameter line not found'}
$text=$text.Replace($oldSymbol,$newSymbol)

$oldTick="(Set-Line 'InpRequireTickVolume' 'false' 'false' '0' 'false')"
$newTick="(Set-Line 'InpRequireTickVolume' 'true' 'true' '0' 'true')"
if($text-notlike "*$oldTick*"){throw 'Expected baseline tick-volume parameter line not found'}
$text=$text.Replace($oldTick,$newTick)

$oldReport='Report=$reportBase'
$newReport='Report=$stem'
if($text-notlike "*$oldReport*"){throw 'Expected absolute report line not found'}
$text=$text.Replace($oldReport,$newReport)

$oldDiscovery=@'
    $report=@("$reportBase.htm","$reportBase.html","$reportBase.xml")|Where-Object{Test-Path $_}|Select-Object -First 1
    if(-not$report){throw "$cell produced no report"}
'@
$newDiscovery=@'
    $reportRoots=@($stage,$dataRoot,$MetaTraderRoot,(Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common'))|Where-Object{$_-and(Test-Path $_)}|Select-Object -Unique
    $reportCandidates=@()
    foreach($root in $reportRoots){
      $reportCandidates+=Get-ChildItem $root -File -Recurse -ErrorAction SilentlyContinue|Where-Object{
        $_.BaseName-eq$stem -and @('.htm','.html','.xml')-contains$_.Extension.ToLowerInvariant() -and $_.LastWriteTime-ge$started.AddMinutes(-1)
      }
    }
    $found=$reportCandidates|Sort-Object LastWriteTime -Descending|Select-Object -First 1
    if(-not$found){throw "$cell completed in MT5 but produced no discoverable report"}
    $report=Join-Path $stage $found.Name
    if($found.FullName-ine$report){Copy-Item $found.FullName $report -Force}
'@
if($text-notlike "*$oldDiscovery*"){throw 'Expected report discovery block not found'}
$text=$text.Replace($oldDiscovery,$newDiscovery)

$readNumberPattern='(?s)function Read-Number\(\[string\]\$Text,\[string\]\$Pattern,\[string\]\$Label\)\{.*?\n\}'
$readNumberReplacement=@'
function Read-Number([string]$Text,[string]$Pattern,[string]$Label){
  $m=[regex]::Match($Text,$Pattern,[Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if(-not$m.Success){throw "Report field missing: $Label"}
  $normalized=$m.Groups[1].Value-replace'[^0-9.\-]',''
  return [double]::Parse($normalized,[Globalization.CultureInfo]::InvariantCulture)
}
'@
$updated=[regex]::Replace($text,$readNumberPattern,$readNumberReplacement,1)
if($updated-eq$text){throw 'Read-Number function replacement failed'}
$text=$updated
$text=$text.Replace('[0-9,]+(?:\.[0-9]+)?','[0-9\s,\u00A0\u202F]+(?:\.[0-9]+)?')
$text=$text.Replace('[0-9,]+','[0-9\s,\u00A0\u202F]+')

$oldExecutionGate='if($bars-le0 -or $ticks-le0 -or $symbols-le0){throw "$Cell empty execution: bars=$bars ticks=$ticks symbols=$symbols"}'
$newExecutionGate='if($bars-le0 -or $ticks-le0){throw "$Cell empty execution: bars=$bars ticks=$ticks symbols=$symbols"}'
if($text-notlike "*$oldExecutionGate*"){throw 'Expected execution gate not found'}
$text=$text.Replace($oldExecutionGate,$newExecutionGate)

$text=$text.Replace("tick_volume_revision=`$false","tick_volume_revision=`$true")
$text=$text.Replace("revision_enabled=`$false","revision_enabled=`$true")
$text=$text.Replace("protocol='Architecture B frozen baseline'","protocol='Architecture B frozen B-R1 revision'")
$text=$text.Replace("Write-Host 'Architecture B baseline complete: 20 non-empty real-tick reports.'","Write-Host 'Architecture B B-R1 complete: 20 non-empty real-tick reports.'")

Set-Content $patchedRunner $text -Encoding UTF8
& $patchedRunner -MetaTraderRoot $MetaTraderRoot -RepoRoot $RepoRoot -Deposit $Deposit -Leverage $Leverage
