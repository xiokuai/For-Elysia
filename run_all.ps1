[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ZhiAi Language - Bootstrap Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "[1/5] Run demo (interpreter mode)" -ForegroundColor Yellow
Write-Host "----------------------------------------"
& python -X utf8 -m zhiai demo.za
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Interpreter error" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

Write-Host "[2/5] Compile demo to bytecode" -ForegroundColor Yellow
Write-Host "----------------------------------------"
& python -X utf8 -m zhiai compiler/main.za demo.za -o demo.zab
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Compile error" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

Write-Host "[3/5] Run bytecode with VM" -ForegroundColor Yellow
Write-Host "----------------------------------------"
& python -X utf8 zhiai/vm.py demo.zab
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] VM error" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

Write-Host "[4/5] Self-hosting: compile the compiler" -ForegroundColor Yellow
Write-Host "----------------------------------------"
& python -X utf8 -m zhiai compiler/main.za compiler/main.za -o compiler.zab
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Self-hosting compile error" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

Write-Host "[5/5] Run more tests" -ForegroundColor Yellow
Write-Host "----------------------------------------"
Write-Host "--- test_func.za ---"
& python -X utf8 -m zhiai compiler/main.za examples/test_func.za -o examples/test_func.zab
& python -X utf8 zhiai/vm.py examples/test_func.zab
Write-Host ""

Write-Host "--- test_recur.za ---"
& python -X utf8 -m zhiai compiler/main.za examples/test_recur.za -o test_recur.zab
& python -X utf8 zhiai/vm.py test_recur.zab
Write-Host ""

Write-Host "--- bootstrap_test.za ---"
& python -X utf8 -m zhiai compiler/main.za examples/bootstrap_test.za -o bootstrap_test.zab
& python -X utf8 zhiai/vm.py bootstrap_test.zab
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "  All tests passed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Generated files:"
Write-Host "  demo.zab           - demo bytecode"
Write-Host "  compiler.zab       - self-hosted compiler bytecode"
Write-Host "  test_recur.zab     - recursion test bytecode"
Write-Host "  bootstrap_test.zab - bootstrap test bytecode"
Write-Host ""
Read-Host "Press Enter to exit"
