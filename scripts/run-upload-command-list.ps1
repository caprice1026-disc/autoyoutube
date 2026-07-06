param(
  [string]$CommandFile = (Join-Path $PSScriptRoot "..\commands\upload_commands.txt"),
  [switch]$DryRun,
  [switch]$RequireUploadYoutube
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$makeVideoPs1 = Join-Path $PSScriptRoot "make-video.ps1"

if (-not (Test-Path $CommandFile)) {
  Write-Error "[runner] command file not found: $CommandFile"
  exit 1
}

$logDir = Join-Path $repoRoot "logs\upload-command-runner"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "run_$timestamp.log"

function Write-RunnerLog {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Write-Host $line
  Add-Content -Path $logFile -Value $line
}

function Get-QuotedValue {
  param(
    [string]$Command,
    [string]$Pattern
  )
  $match = [regex]::Match($Command, $Pattern)
  if ($match.Success) { return $match.Groups[1].Value }
  return ""
}

function Quote-ForPowerShell {
  param([string]$Value)
  return '"' + ($Value -replace '"', '\"') + '"'
}

function Invoke-ConvertedCommand {
  param([string]$Command)

  $projectPath = Get-QuotedValue -Command $Command -Pattern '^scripts/make-video\.sh\s+("[^"]+"|[^\s]+)'
  if ($projectPath.StartsWith('"') -and $projectPath.EndsWith('"')) {
    $projectPath = $projectPath.Trim('"')
  }
  if (-not $projectPath) {
    throw "Could not parse project path from command: $Command"
  }

  $videoKeywords = @()
  foreach ($match in [regex]::Matches($Command, '--video-keyword\s+"([^"]*)"')) {
    $videoKeywords += $match.Groups[1].Value
  }

  $queryMode = Get-QuotedValue -Command $Command -Pattern '--query-mode\s+(append|override|fallback)'
  $perQuery = Get-QuotedValue -Command $Command -Pattern '--per-query\s+(\d+)'
  $maxDownloads = Get-QuotedValue -Command $Command -Pattern '--max-downloads\s+(\d+)'
  $orientation = Get-QuotedValue -Command $Command -Pattern '--orientation\s+(portrait|landscape|square)'
  $size = Get-QuotedValue -Command $Command -Pattern '--size\s+(small|medium|large)'
  $voiceMode = Get-QuotedValue -Command $Command -Pattern '--voice-mode\s+(dry-run|aivis)'
  $videoMode = Get-QuotedValue -Command $Command -Pattern '--video-mode\s+(dry-run|ffmpeg)'
  $aivisBaseUrl = Get-QuotedValue -Command $Command -Pattern '--aivis-base-url\s+"?([^"\s]+)"?'
  $ffmpegPath = Get-QuotedValue -Command $Command -Pattern '--ffmpeg-path\s+"?([^"\s]+)"?'
  $bgmId = Get-QuotedValue -Command $Command -Pattern '--bgm-id\s+"?([^"\s]+)"?'
  $seed = Get-QuotedValue -Command $Command -Pattern '--seed\s+(\d+)'
  $maxFixAttempts = Get-QuotedValue -Command $Command -Pattern '--max-fix-attempts\s+(\d+)'

  $psArgsText = @(
    '-ProjectPath ' + (Quote-ForPowerShell $projectPath)
  )
  if ($videoKeywords.Count -gt 0) {
    $psArgsText += '-VisualKeywords ' + (Quote-ForPowerShell ($videoKeywords -join ','))
  }
  if ($queryMode) { $psArgsText += '-QueryMode ' + (Quote-ForPowerShell $queryMode) }
  if ($perQuery) { $psArgsText += '-PerQuery ' + (Quote-ForPowerShell $perQuery) }
  if ($maxDownloads) { $psArgsText += '-MaxDownloads ' + (Quote-ForPowerShell $maxDownloads) }
  if ($orientation) { $psArgsText += '-Orientation ' + (Quote-ForPowerShell $orientation) }
  if ($size) { $psArgsText += '-Size ' + (Quote-ForPowerShell $size) }
  if ($voiceMode) { $psArgsText += '-VoiceMode ' + (Quote-ForPowerShell $voiceMode) }
  if ($videoMode) { $psArgsText += '-VideoMode ' + (Quote-ForPowerShell $videoMode) }
  if ($aivisBaseUrl) { $psArgsText += '-AivisBaseUrl ' + (Quote-ForPowerShell $aivisBaseUrl) }
  if ($ffmpegPath) { $psArgsText += '-FfmpegPath ' + (Quote-ForPowerShell $ffmpegPath) }
  if ($bgmId) { $psArgsText += '-BgmId ' + (Quote-ForPowerShell $bgmId) }
  if ($seed) { $psArgsText += '-Seed ' + (Quote-ForPowerShell $seed) }
  if ($maxFixAttempts) { $psArgsText += '-MaxFixAttempts ' + (Quote-ForPowerShell $maxFixAttempts) }
  if ($Command -match '--no-auto-fix') { $psArgsText += '-NoAutoFix' }
  if ($Command -match '--plan-only') { $psArgsText += '-PlanOnly' }
  if ($Command -match '--dry-run') { $psArgsText += '-DryRun' }
  if ($Command -match '--upload-youtube') { $psArgsText += '-UploadYoutube' }
  if ($Command -match '--skip-fetch-visuals') { $psArgsText += '-SkipFetchVisuals' }
  if ($Command -match '--skip-inspect') { $psArgsText += '-SkipInspect' }
  if ($Command -match '--skip-evaluate') { $psArgsText += '-SkipEvaluate' }

  $commandText = '-ExecutionPolicy Bypass -File ' + (Quote-ForPowerShell $makeVideoPs1) + ' ' + ($psArgsText -join ' ')
  Write-RunnerLog "[runner] translated project: $projectPath"
  Write-RunnerLog "[runner] translated keywords: $($videoKeywords.Count)"
  Write-RunnerLog "[runner] translated args: $commandText"

  $process = Start-Process -FilePath "powershell" -ArgumentList $commandText -Wait -PassThru -NoNewWindow
  return [int]$process.ExitCode
}

$commands = Get-Content $CommandFile |
  ForEach-Object { $_.Trim() } |
  Where-Object { $_ -and -not $_.StartsWith("#") }

if ($commands.Count -eq 0) {
  Write-RunnerLog "[runner] no commands found."
  exit 1
}

Write-RunnerLog "[runner] command file: $CommandFile"
Write-RunnerLog "[runner] commands: $($commands.Count)"
Write-RunnerLog "[runner] log file: $logFile"

if ($DryRun) {
  Write-RunnerLog "[runner] dry-run mode. commands will not be executed."
}

Write-Host ""

$failedCommands = 0

for ($i = 0; $i -lt $commands.Count; $i++) {
  $command = $commands[$i]
  $number = $i + 1

  Write-Host "============================================================"
  Write-RunnerLog "[runner] start [$number/$($commands.Count)]"
  Write-RunnerLog "[runner] command: $command"
  Write-Host "============================================================"

  if ($RequireUploadYoutube -and ($command -notmatch "--upload-youtube")) {
    Write-RunnerLog "[runner] stopped. command does not include --upload-youtube."
    Write-RunnerLog "[runner] failed command [$number/$($commands.Count)]"
    exit 1
  }

  if ($DryRun) {
    Write-RunnerLog "[runner] skipped by dry-run [$number/$($commands.Count)]"
    Write-Host ""
    continue
  }

  try {
    $global:LASTEXITCODE = 0
    $exitCode = Invoke-ConvertedCommand -Command $command
    if ($exitCode -eq 10) {
      Write-RunnerLog "[runner] done with warnings [$number/$($commands.Count)]"
      Write-Host ""
      continue
    }
    if ($exitCode -ne 0) {
      Write-RunnerLog "[runner] failed with exit code: $exitCode"
      Write-RunnerLog "[runner] skipped and continued [$number/$($commands.Count)]"
      $failedCommands++
      Write-Host ""
      continue
    }

    Write-RunnerLog "[runner] done [$number/$($commands.Count)]"
    Write-Host ""
  }
  catch {
    Write-RunnerLog "[runner] exception occurred."
    Write-RunnerLog "[runner] $($_.Exception.Message)"
    Write-RunnerLog "[runner] skipped and continued [$number/$($commands.Count)]"
    $failedCommands++
    Write-Host ""
  }
}

Write-RunnerLog "[runner] all commands completed."
if ($failedCommands -gt 0) {
  Write-RunnerLog "[runner] completed with $failedCommands hard failure(s)."
  exit 1
}
exit 0
