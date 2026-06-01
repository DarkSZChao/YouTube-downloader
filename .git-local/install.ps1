$ErrorActionPreference = 'Stop'

$repoRoot = git rev-parse --show-toplevel
Set-Location $repoRoot


git config --local --unset-all include.path '../.git-local/config' 2>$null
git config --local --add include.path '../.git-local/config'
git config --local core.hooksPath '.git-local/hooks'


$ignoreCase = git config --bool core.ignorecase
$includePath = git config --local include.path
$hooksPath = git config --local core.hooksPath
Write-Host "Repository [$repoRoot] local git config installed."
Write-Host "core.ignorecase = $ignoreCase"
Write-Host "core.includePath = $includePath"
Write-Host "core.hooksPath = $hooksPath"
Write-Host 'Git local config installation complete.'
Read-Host "Press Enter to continue..."