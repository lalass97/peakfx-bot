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

$patchedRunner=Join-Path $env:TEMP 'run_architecture_b_baseline_5y_v3_patched.ps1'
$text=Get-Content $baseRunner -Raw

$oldExpert='Expert=PeakFX\PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION'
$newExpert='Expert=PeakFX\PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.ex5'
if($text-notlike "*$oldExpert*"){throw 'Expected Architecture B Expert line not found in base runner'}
$text=$text.Replace($oldExpert,$newExpert)

# MT5 treats string inputs differently from numeric/bool optimization rows.
# The prior generic Set-Line output made the literal symbol value become
# EURUSD||EURUSD||||EURUSD||N, causing OnInit to fail because that symbol does not exist.
$oldSymbol="(Set-Line 'InpSymbol' 'EURUSD' 'EURUSD' '' 'EURUSD')"
$newSymbol="'InpSymbol=EURUSD'"
if($text-notlike "*$oldSymbol*"){throw 'Expected InpSymbol set-file row not found in base runner'}
$text=$text.Replace($oldSymbol,$newSymbol)

Set-Content $patchedRunner $text -Encoding UTF8

& $patchedRunner -MetaTraderRoot $MetaTraderRoot -RepoRoot $RepoRoot -Deposit $Deposit -Leverage $Leverage
if($LASTEXITCODE-ne0){exit $LASTEXITCODE}

$results=Join-Path $RepoRoot 'artifacts/architecture-b-baseline-5y'
$logs=Get-ChildItem $results -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match '\\logs\\' }
$combined=($logs | ForEach-Object { Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue }) -join "`n"
if($combined -and $combined-notmatch 'PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION\.ex5'){
  throw 'Fresh MT5 logs do not confirm Architecture B .ex5 execution'
}
if($combined -match 'PULLBACK_CONFIRMED_BREAKOUT_EXP8'){
  throw 'Fresh MT5 logs show stale EXP8 expert execution'
}
if($combined -match 'symbol EURUSD\|\|'){
  throw 'Fresh MT5 logs show malformed InpSymbol encoding'
}
