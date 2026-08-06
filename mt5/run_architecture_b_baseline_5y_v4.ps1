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

$patchedRunner=Join-Path $env:TEMP 'run_architecture_b_baseline_5y_v4_patched.ps1'
$text=Get-Content $baseRunner -Raw

$oldExpert='Expert=PeakFX\PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION'
$newExpert='Expert=PeakFX\PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.ex5'
if($text-notlike "*$oldExpert*"){throw 'Expected Architecture B Expert line not found'}
$text=$text.Replace($oldExpert,$newExpert)

$oldSymbol="(Set-Line 'InpSymbol' 'EURUSD' 'EURUSD' '' 'EURUSD')"
$newSymbol="'InpSymbol=EURUSD'"
if($text-notlike "*$oldSymbol*"){throw 'Expected string symbol parameter line not found'}
$text=$text.Replace($oldSymbol,$newSymbol)

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

Set-Content $patchedRunner $text -Encoding UTF8
& $patchedRunner -MetaTraderRoot $MetaTraderRoot -RepoRoot $RepoRoot -Deposit $Deposit -Leverage $Leverage
if($LASTEXITCODE-ne0){exit $LASTEXITCODE}
