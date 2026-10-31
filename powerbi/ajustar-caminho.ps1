# Ajusta o parâmetro DataFolder para o caminho absoluto desta máquina.
# Use somente se o Power BI Desktop não ler os CSV pelo caminho relativo data/pbi.
# Não faça commit do caminho absoluto.

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$data = (Join-Path $root "data\pbi") -replace "\\", "/"
$expression = Join-Path $root "SupplyWatch.SemanticModel\definition\expressions.tmdl"
if (-not (Test-Path $expression)) {
    throw "Não encontrei expressions.tmdl. Execute este script a partir do clone do repositório."
}
$text = [System.IO.File]::ReadAllText($expression)
$updated = [regex]::Replace($text, 'expression DataFolder = ".*?"', "expression DataFolder = `"$data`"")
if ($updated -eq $text) {
    throw "Não encontrei a expressão DataFolder para substituir."
}
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($expression, $updated, $utf8)
Write-Host "DataFolder agora é $data"
Write-Host "Feche e reabra SupplyWatch.pbip. Não faça commit deste caminho."
