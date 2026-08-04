param(
    [Parameter(Mandatory = $true)]
    [string]$MetaTraderRoot,

    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,

    [Parameter(Mandatory = $true)]
    [string]$SourceEA,

    [string]$Symbol = "EURUSD",
    [string]$Period = "H1",
    [double]$Deposit = 10000.0,
    [int]$Leverage = 100,
    [int]$FixedSpreadPoints = 15,
    [ValidateSet("Quiet", "Normal", "Verbose")]
    [string]$LogLevel = "Normal",
    [string]$OutputDir,
    [string]$LogPath,
    [switch]$RunOos,
    [string]$GatekeeperDecisionPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($Symbol -ne "EURUSD") { throw "EXP2 is locked to EURUSD" }
if ($Period -ne "H1") { throw "EXP2 is locked to H1" }
if ($Deposit -le 0) { throw "Deposit must be positive" }
if ($Leverage -le 0) { throw "Leverage must be positive" }
if ($FixedSpreadPoints -lt 0) { throw "FixedSpreadPoints cannot be negative" }

foreach ($required in @($MetaTraderRoot, $RepoRoot, $ConfigPath, $SourceEA)) {
    if (-not (Test-Path $required)) { throw "Required path not found: $required" }
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $RepoRoot "artifacts/runs/run_$timestamp"
}
if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $RepoRoot "artifacts/logs/mt5_execution_$timestamp.log"
}

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDir)
$resolvedLog = [System.IO.Path]::GetFullPath($LogPath)
if (Test-Path $resolvedOutput) {
    throw "OutputDir already exists; refusing to overwrite prior evidence: $resolvedOutput"
}
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $resolvedLog -Parent) | Out-Null

function Write-PipelineLog([string]$Message) {
    $line = "$(Get-Date -Format o) $Message"
    Add-Content -Path $resolvedLog -Value $line -Encoding UTF8
    if ($LogLevel -ne "Quiet") { Write-Host $line }
}

$rules = Get-Content $ConfigPath -Raw | ConvertFrom-Json
if ($null -eq $rules.stage2_screening_rules -or $null -eq $rules.stage3_oos_qualification_rules) {
    throw "Gatekeeper config is missing required rule groups"
}

$runOosAuthorized = $false
if ($RunOos) {
    if ([string]::IsNullOrWhiteSpace($GatekeeperDecisionPath)) {
        throw "-RunOos requires -GatekeeperDecisionPath; manual OOS override is not allowed"
    }
    if (-not (Test-Path $GatekeeperDecisionPath)) {
        throw "Gatekeeper decision not found: $GatekeeperDecisionPath"
    }
    $decision = Get-Content $GatekeeperDecisionPath -Raw | ConvertFrom-Json
    $runOosAuthorized = ($decision.decision -eq "UNLOCK_OOS" -and $decision.passed -eq $true)
    if (-not $runOosAuthorized) {
        throw "OOS remains locked because the supplied gatekeeper decision did not authorize UNLOCK_OOS"
    }
}

$manifest = [ordered]@{
    started_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    symbol = $Symbol
    period = $Period
    deposit = $Deposit
    leverage = $Leverage
    requested_spread_floor_points = $FixedSpreadPoints
    spread_floor_status = "recorded_not_silently_assumed"
    source_ea = [System.IO.Path]::GetFullPath($SourceEA)
    gatekeeper_config = [System.IO.Path]::GetFullPath($ConfigPath)
    output_dir = $resolvedOutput
    log_path = $resolvedLog
    oos_requested = [bool]$RunOos
    oos_authorized = $runOosAuthorized
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $resolvedOutput "pipeline_manifest.json") -Encoding UTF8

Write-PipelineLog "Starting EXP2 MT5 pipeline. OOS authorized: $runOosAuthorized"
Write-PipelineLog "Requested spread floor: $FixedSpreadPoints points. This value is recorded for audit and must be verified against the chosen MT5 modeling method; it is not silently claimed as enforced."

$runner = Join-Path $RepoRoot "mt5/run_exp2_validation.ps1"
if (-not (Test-Path $runner)) { throw "Underlying MT5 runner not found: $runner" }

$runnerArgs = @{
    MetaTraderRoot = $MetaTraderRoot
    RepoRoot = $RepoRoot
    CompiledCleanExp1Source = $SourceEA
    Deposit = $Deposit
    Leverage = "1:$Leverage"
}
if ($runOosAuthorized) { $runnerArgs.RunOos = $true }

try {
    & $runner @runnerArgs *>&1 | Tee-Object -FilePath $resolvedLog -Append
    if ($LASTEXITCODE -ne 0) { throw "Underlying MT5 runner failed with exit code $LASTEXITCODE" }
    Write-PipelineLog "Pipeline command completed. Review compile and tester artifacts before accepting any profitability claim."
}
catch {
    Write-PipelineLog "PIPELINE_FAILED: $($_.Exception.Message)"
    throw
}
