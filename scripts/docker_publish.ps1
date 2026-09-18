# Build and publish Docker fallback image for organizers.
# Image: nishadmahmud/elec_bup:v1
#
# Prerequisites: Docker Desktop running + `docker login`

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$image = "nishadmahmud/elec_bup:v1"

Write-Host "Building $image ..."
docker build -t $image .

Write-Host "Pushing $image ..."
docker push $image

Write-Host ""
Write-Host "Verify locally (uses OPENAI_API_KEY from your environment):"
Write-Host "  docker run --rm -p 8000:8000 -e OPENAI_API_KEY=`$env:OPENAI_API_KEY -e OPENAI_MODEL=gpt-4o-mini $image"
Write-Host "  curl http://127.0.0.1:8000/health"
Write-Host ""
Write-Host "Organizer fallback:"
Write-Host "  docker pull $image"
Write-Host "  docker run --rm -p 8000:8000 -e OPENAI_API_KEY=<KEY> -e OPENAI_MODEL=gpt-4o-mini $image"
