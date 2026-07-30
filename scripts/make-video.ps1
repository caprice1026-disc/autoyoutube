param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectPath,

  [Alias("VideoKeyword", "PexelsKeyword")]
  [string[]]$VisualKeyword = @(),
  [Alias("VideoKeywords", "PexelsKeywords")]
  [string]$VisualKeywords,
  [ValidateSet("append", "override", "fallback")]
  [string]$QueryMode = "append",
  [int]$PerQuery = 0,
  [int]$MaxDownloads = 0,
  [ValidateSet("portrait", "landscape", "square")]
  [string]$Orientation = "portrait",
  [ValidateSet("small", "medium", "large")]
  [string]$Size = "small",
  [ValidateSet("dry-run", "aivis")]
  [string]$VoiceMode = "aivis",
  [ValidateSet("dry-run", "ffmpeg")]
  [string]$VideoMode = "ffmpeg",
  [string]$AivisBaseUrl = "http://127.0.0.1:10101",
  [string]$FfmpegPath,
  [string]$BgmId,
  [int]$Seed = 0,
  [int]$MaxFixAttempts = 0,
  [switch]$NoAutoFix,
  [switch]$PlanOnly,
  [switch]$DryRun,
  [switch]$UploadYoutube,
  [switch]$AppendEndCta,
  [switch]$SkipFetchVisuals,
  [switch]$SkipInspect,
  [switch]$SkipEvaluate
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Test-AivisReady {
  param([string]$BaseUrl)
  try {
    Invoke-RestMethod -Uri "$BaseUrl/version" -TimeoutSec 3 | Out-Null
    return $true
  } catch {
    return $false
  }
}

if ($VoiceMode -eq "aivis" -and -not $DryRun -and -not $PlanOnly) {
  if (-not (Test-AivisReady -BaseUrl $AivisBaseUrl)) {
    Write-Host "[make-video.ps1] AivisSpeech is not ready; starting Docker service."
    docker compose --profile aivis up -d aivis-engine
  }

  $ready = $false
  for ($i = 1; $i -le 60; $i++) {
    if (Test-AivisReady -BaseUrl $AivisBaseUrl) {
      $ready = $true
      break
    }
    Start-Sleep -Seconds 2
  }

  if (-not $ready) {
    Write-Error "AivisSpeech did not become ready at $AivisBaseUrl."
    exit 40
  }
}

$argsList = @("-m", "src.main", "make-video", $ProjectPath)
foreach ($keyword in $VisualKeyword) {
  $argsList += @("--visual-keyword", $keyword)
}
if ($VisualKeywords) { $argsList += @("--visual-keywords", $VisualKeywords) }
$argsList += @("--query-mode", $QueryMode)
if ($PerQuery -gt 0) { $argsList += @("--per-query", "$PerQuery") }
if ($MaxDownloads -gt 0) { $argsList += @("--max-downloads", "$MaxDownloads") }
$argsList += @("--orientation", $Orientation, "--size", $Size)
$argsList += @("--voice-mode", $VoiceMode, "--video-mode", $VideoMode)
if ($AivisBaseUrl) { $argsList += @("--aivis-base-url", $AivisBaseUrl) }
if ($FfmpegPath) { $argsList += @("--ffmpeg-path", $FfmpegPath) }
if ($BgmId) { $argsList += @("--bgm-id", $BgmId) }
if ($Seed -gt 0) { $argsList += @("--seed", "$Seed") }
if ($MaxFixAttempts -gt 0) { $argsList += @("--max-fix-attempts", "$MaxFixAttempts") }
if ($NoAutoFix) { $argsList += "--no-auto-fix" }
if ($PlanOnly) { $argsList += "--plan-only" }
if ($DryRun) { $argsList += "--dry-run" }
if ($UploadYoutube) { $argsList += "--upload-youtube" }
if ($AppendEndCta) { $argsList += "--append-end-cta" }
if ($SkipFetchVisuals) { $argsList += "--skip-fetch-visuals" }
if ($SkipInspect) { $argsList += "--skip-inspect" }
if ($SkipEvaluate) { $argsList += "--skip-evaluate" }

& .\.venv\Scripts\python.exe @argsList
$code = $LASTEXITCODE

switch ($code) {
  0 { Write-Host "[make-video.ps1] make-video succeeded." }
  10 { Write-Host "[make-video.ps1] make-video succeeded with warnings." }
  20 { Write-Error "[make-video.ps1] auto-fix limit reached." }
  30 { Write-Error "[make-video.ps1] non-fixable quality error." }
  40 { Write-Error "[make-video.ps1] environment error." }
  50 { Write-Error "[make-video.ps1] external API error." }
  60 { Write-Error "[make-video.ps1] render error." }
  70 { Write-Error "[make-video.ps1] encoding error." }
  80 { Write-Error "[make-video.ps1] upload blocked." }
  default { Write-Error "[make-video.ps1] unknown failure: $code" }
}

exit $code
