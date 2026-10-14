$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
	if (Get-Process PantaGateChecker -ErrorAction SilentlyContinue) {
		throw "PantaGateChecker is running. Close it before building a release."
	}

	poetry run python tools\create_icon.py
	if ($LASTEXITCODE -ne 0) { throw "Icon generation failed with exit code $LASTEXITCODE" }

	poetry run pyinstaller --noconfirm --clean PantaGateChecker.spec
	if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

	$isccCommand = Get-Command iscc -ErrorAction SilentlyContinue
	$isccCandidates = @(
		$isccCommand.Source,
		(Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
		(Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
	) | Where-Object { $_ -and (Test-Path $_) }
	$isccPath = $isccCandidates | Select-Object -First 1
	if (-not $isccPath) {
		throw "Inno Setup 6 is required to build the installer. Install it with: winget install JRSoftware.InnoSetup"
	}

	& $isccPath installer.iss
	if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }

	$artifacts = @(
		"dist\PantaGateChecker.exe",
		"dist\PantaGateChecker-Setup-0.1.0.exe"
	)
	$checksums = foreach ($artifact in $artifacts) {
		$hash = Get-FileHash $artifact -Algorithm SHA256
		"$($hash.Hash)  $([IO.Path]::GetFileName($artifact))"
	}
	$checksums | Set-Content "dist\SHA256SUMS.txt"

	Write-Host "Created dist\PantaGateChecker.exe"
	Write-Host "Created dist\PantaGateChecker-Setup-0.1.0.exe"
	Write-Host "Created dist\SHA256SUMS.txt"
}
finally {
	Pop-Location
}