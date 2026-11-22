# Synthesize a short test voice using the built-in Windows speech API.
# No external speech samples or user recordings are uploaded to CI.
param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$destination = [System.IO.Path]::GetFullPath($OutputPath)
$speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $speech.Rate = 0
    $speech.Volume = 100
    $speech.SetOutputToWaveFile($destination)
    $speech.Speak('Hello, this is a speech recognition test for Cliptora. We are checking whether the video editor can understand real spoken words. This sentence is deliberately long enough for voice activity detection.')
} finally {
    $speech.Dispose()
}
if (!(Test-Path -LiteralPath $destination) -or (Get-Item -LiteralPath $destination).Length -lt 10000) {
    throw 'The synthesized speech fixture was not created.'
}
Write-Host 'Synthetic speech sample created.'
