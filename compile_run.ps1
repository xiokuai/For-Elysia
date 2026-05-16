param(
    [Parameter(Mandatory=$true)]
    [string]$InputFile
)

Set-Location $PSScriptRoot

if (-not (Test-Path $InputFile)) {
    Write-Host "文件不存在: $InputFile" -ForegroundColor Red
    exit 1
}

$BaseName = [System.IO.Path]::GetFileNameWithoutExtension($InputFile)
$OutputFile = "$BaseName.zab"

Write-Host "[1] 编译 $InputFile ..." -ForegroundColor Yellow
python -X utf8 -m zhiai compiler/main.za $InputFile -o $OutputFile
if ($LASTEXITCODE -ne 0) {
    Write-Host "编译失败" -ForegroundColor Red
    exit 1
}

Write-Host "[2] 执行 $OutputFile ..." -ForegroundColor Yellow
Write-Host "----------------------------------------"
python -X utf8 zhiai/vm.py $OutputFile
Write-Host "----------------------------------------"
Write-Host "完成！字节码文件: $OutputFile" -ForegroundColor Green
