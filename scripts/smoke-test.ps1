# Phase 1 smoke checks for Windows / PowerShell hosts
param(
  [string]$HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$Api = "http://${HostAddress}:8001"

Write-Host "== health =="
Invoke-RestMethod -Uri "$Api/health" | ConvertTo-Json -Depth 5

Write-Host "`n== website =="
foreach ($path in @("/", "/login", "/admin", "/dashboard")) {
  $code = (Invoke-WebRequest -Uri "http://${HostAddress}:8080$path" -UseBasicParsing).StatusCode
  Write-Host "GET $path -> $code"
}

Write-Host "`n== event =="
$body = @{ service = "test"; event = "SMOKE TEST"; ip = $HostAddress } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$Api/events" -ContentType "application/json" -Body $body | ConvertTo-Json

Write-Host "`n== mysql =="
docker exec honeypot-mysql mysql -u admin -padmin123 -e "SELECT 1 AS ok;" corporate

Write-Host "`nSmoke test finished."
