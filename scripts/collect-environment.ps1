# Collect environment information for bug reports
# Usage: .\collect-environment.ps1

Write-Output "⚠️  IMPORTANT: Review the output below carefully before posting in a bug report."
Write-Output "   Redact any secrets, credentials, or sensitive environment variables."
Write-Output ""
Write-Output "# Gideon Environment Information"
Write-Output ""
Write-Output "## System"
Write-Output "- **OS**: Windows $(Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object -ExpandProperty Version)"
$arch = if ((Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty Architecture) -eq 9) { 'x64' } else { 'x86' }
Write-Output "- **Architecture**: $arch"
Write-Output ""

Write-Output "## Docker"
$dockerVersion = docker --version 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Output "- **Docker version**: $dockerVersion"
}
else {
  Write-Output "- **Docker version**: Not installed"
}

$composeVersion = docker compose version 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Output "- **Docker Compose version**: $composeVersion"
}
else {
  Write-Output "- **Docker Compose version**: Not installed"
}
Write-Output ""

Write-Output "## Gideon"
if (Test-Path ".env") {
  $deploymentMode = (Select-String -Path ".env" -Pattern "^DEPLOYMENT_MODE=" | ForEach-Object { $_.Line.Split('=')[1].Trim('"') })
  if ($deploymentMode) {
    Write-Output "- **Deployment mode**: $deploymentMode"
  }
}

try {
  $gitCommit = & git rev-parse --short HEAD 2>$null
  if ($LASTEXITCODE -eq 0) {
    Write-Output "- **Git commit**: $gitCommit"
    $gitBranch = & git rev-parse --abbrev-ref HEAD 2>$null
    Write-Output "- **Git branch**: $gitBranch"
  }
}
catch {
  # Git not available or not a repo
}
Write-Output ""

Write-Output "## Python (if running outside Docker)"
$pythonVersion = python --version 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Output "- **Python version**: $pythonVersion"
}
else {
  Write-Output "- **Python version**: Not installed"
}

$uvVersion = uv --version 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Output "- **uv version**: $uvVersion"
}
Write-Output ""

Write-Output "## Docker Services Status"
try {
  $services = docker ps --format "{{.Names}}`t{{.Status}}" 2>$null
  if ($LASTEXITCODE -eq 0 -and $services) {
    Write-Output "Running services:"
    $services | ForEach-Object { Write-Output "  - $_" }
  }
  else {
    Write-Output "No running Docker services (or Docker daemon not accessible)"
  }
}
catch {
  Write-Output "Unable to check Docker services"
}
