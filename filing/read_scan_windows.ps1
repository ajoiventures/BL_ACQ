param(
    [Parameter(Mandatory)][string]$ScanPath
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]

$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and
        $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1

function Receive-WinRt($Operation, [type]$ResultType) {
    $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}

$file = Get-Item -LiteralPath $ScanPath
if ($file.PSIsContainer -or $file.Extension -notin @('.png', '.jpg', '.jpeg') -or $file.Length -gt 8MB) {
    throw 'Provide a local PNG or JPEG scan of at most 8 MiB.'
}
function Get-ScanDigest($Path) {
    $hash = [System.Security.Cryptography.SHA256]::Create()
    $inputStream = [IO.File]::OpenRead($Path)
    try {
        [BitConverter]::ToString($hash.ComputeHash($inputStream)).Replace('-', '').ToLowerInvariant()
    } finally {
        $inputStream.Dispose()
        $hash.Dispose()
    }
}
$before = Get-ScanDigest $file.FullName
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) {
    throw 'Windows OCR is unavailable for the current user language.'
}
$storage = Receive-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($file.FullName)) ([Windows.Storage.StorageFile])
$stream = Receive-WinRt ($storage.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType = WindowsRuntime])
try {
    $decoder = Receive-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $limit = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
    if ($decoder.PixelWidth -gt $limit -or $decoder.PixelHeight -gt $limit) {
        throw "Scan dimensions exceed the Windows OCR limit of $limit pixels per side."
    }
    $bitmap = Receive-WinRt ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime])
    try {
        $result = Receive-WinRt ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime])
    } finally {
        $bitmap.Dispose()
    }
} finally {
    $stream.Dispose()
}
$after = Get-ScanDigest $file.FullName
if ($before -ne $after) {
    throw 'Scan bytes changed during recognition.'
}
[ordered]@{
    source_sha256 = $before
    engine = 'Windows.Media.Ocr'
    language = $engine.RecognizerLanguage.LanguageTag
    status = 'REVIEW_REQUIRED'
    text = $result.Text
} | ConvertTo-Json
