param([string]$InputDocx, [string]$OutputPdf)
$ErrorActionPreference = 'Stop'
$reportWord = $null
$reportDocument = $null
try {
    $reportWord = New-Object -ComObject Word.Application
    $reportWord.Visible = $false
    $reportWord.DisplayAlerts = 0
    $reportWord.AutomationSecurity = 3
    $reportDocument = $reportWord.Documents.Open($InputDocx, $false, $false, $false)
    if ($reportDocument.ReadOnly) { throw 'The staging document opened read-only.' }
    $reportDocument.Repaginate()
    foreach ($reportToc in $reportDocument.TablesOfContents) { $reportToc.Update() }
    $reportDocument.Fields.Update() | Out-Null
    $reportDocument.Repaginate()
    foreach ($reportToc in $reportDocument.TablesOfContents) { $reportToc.UpdatePageNumbers() }
    $reportDocument.Save()
    $reportDocument.ExportAsFixedFormat($OutputPdf, 17)
    Write-Output ('PAGES=' + $reportDocument.ComputeStatistics(2))
} finally {
    if ($null -ne $reportDocument) { $reportDocument.Close(0) }
    if ($null -ne $reportWord) { $reportWord.Quit() }
}
