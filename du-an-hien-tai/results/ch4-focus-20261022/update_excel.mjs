import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const data = JSON.parse(await fs.readFile(new URL('./excel-content.json', import.meta.url), 'utf8'));
const workbook = Workbook.create();
const layouts = {
  ThongTin: [25, 110],
  YeuCauChucNang: [16, 100, 18, 16],
  YeuCauPhiChucNang: [16, 110, 16],
  RangBuoc: [16, 110, 16],
  TestCase: [15, 22, 38, 66, 78, 88, 16],
};

function writeSheet(name, rows) {
  const sheet = workbook.worksheets.add(name);
  const end = String.fromCharCode(64 + rows[0].length);
  const range = sheet.getRange(`A1:${end}${rows.length}`);
  range.values = rows;
  range.format.font = { name: 'Arial', size: 11, color: '#111827' };
  range.format.wrapText = true;
  range.format.verticalAlignment = 'top';
  layouts[name].forEach((width, index) => {
    sheet.getRange(`${String.fromCharCode(65 + index)}1:${String.fromCharCode(65 + index)}${rows.length}`).format.columnWidth = width;
  });
  rows.slice(1).forEach((row, index) => {
    const lines = Math.max(...row.map((value, col) => String(value ?? '').split('\n')
      .reduce((count, line) => count + Math.max(1, Math.ceil(line.length / (layouts[name][col] * 0.9))), 0)));
    sheet.getRange(`A${index + 2}:${end}${index + 2}`).format.rowHeight = Math.max(28, lines * 15 + 10);
  });
  const header = sheet.getRange(`A1:${end}1`);
  header.format.fill = '#17365D';
  header.format.font = { name: 'Arial', size: 11, bold: true, color: '#FFFFFF' };
  header.format.rowHeight = 32;
  sheet.freezePanes.freezeRows(1);
  if (name === 'TestCase') sheet.freezePanes.freezeColumns(2);
  sheet.tabColor = '#17365D';
  return sheet;
}

for (const [name, rows] of Object.entries(data)) writeSheet(name, rows);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(new URL('./badminton_spec.ch4.xlsx', import.meta.url).pathname.replace(/^\/(\w:)/, '$1'));
for (const [name, range, label] of [
  ['ThongTin', 'A1:B11', 'info'],
  ['ThongTin', 'A12:B21', 'evidence'],
  ['YeuCauChucNang', 'A1:D13', 'requirements'],
  ['YeuCauPhiChucNang', 'A1:C4', 'nonfunctional'],
  ['RangBuoc', 'A1:C9', 'constraints'],
  ['TestCase', 'A1:C7', 'cases'],
  ['TestCase', 'D51:F58', 'guard-patch'],
]) {
  const image = await workbook.render({ sheetName: name, range, scale: 1, format: 'png' });
  await fs.writeFile(new URL(`./excel-${label}.png`, import.meta.url), new Uint8Array(await image.arrayBuffer()));
}
console.log((await workbook.inspect({ kind: 'sheet', include: 'id,name', maxChars: 1800 })).ndjson);
console.log('Exported 5 sheets; 57 design cases; no project tests or fuzzing executed.');
