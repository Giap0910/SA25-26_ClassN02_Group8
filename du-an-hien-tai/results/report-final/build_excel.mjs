import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';

const root='C:/Project/Badminton_Stock_Security';
const output=path.join(root,'results/report-final');
const python='C:/Users/vxg09/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(output,'badminton_spec.xlsx.before-20261020')));
const mode=process.argv[2]||'preview';

async function render(sheetName,range,name){
  const blob=await workbook.render({sheetName,range,scale:1.4,format:'png'});
  await fs.writeFile(path.join(output,name),new Uint8Array(await blob.arrayBuffer()));
}

if(mode==='preview'){
  console.log((await workbook.inspect({kind:'sheet',include:'id,name',maxChars:3500})).ndjson);
  await render('ThongTin','A14:B18','20261020-excel-before.png');
  await render('TestCase','D51:F52','20261020-cases-before.png');
}else if(mode==='edit'){
  const info=workbook.worksheets.getItem('ThongTin');
  info.getRange('A14:B18').values=[
    ['gui_smt','Ch3 GUI: 60 input, giữ 6 test, 0 crash, 22/22 probe (100%) riêng stock_reserve_guard. Ảnh và gói xuất: results/ch123-20261018-202400-9a09dbce/. Không suy rộng toàn parser.'],
    ['pytest_guard','Gói GUI Ch3: 6/6 PASS, 1,65 giây; ch3-export-pytest.log/XML. TC-SMT1 trong Excel giữ biên quantity=101 của lượt cũ; bản xuất mới dùng quantity=0, cùng nhánh trả 1.'],
    ['guard_scope','Ch1: 5 trạng thái, 4 công thức CTL đúng; cancelled/settled loại trừ nhau. Ch3: 6 nhánh guard SAT và chạy lại C đúng; điều kiện tràn sau guard UNSAT. Không phải chứng minh toàn website; tạm gác Ch5–Ch6.'],
    ['sanitizer_scope','ASan+UBSan: 41 hồi quy + 100 mutation, seed 1, 0 finding (lượt ch123). Dr. Memory: 141 input lặp 10 vòng = 1.410 lần gọi, 0 definite leak; còn possible 24 byte ntdll/TLS giống đối chứng sạch. Đối chứng leak bắt 123 byte. Không chạy LSan.'],
    ['comparison_result','Cùng nhánh guard trả 3; 5 seed, tối đa 50.000 lần gọi/seed. Uniform tìm 0/5; edge-enriched 5/5 (32,2,4,16,21 lần gọi); SMT trực tiếp 5/5 (1 lần gọi/seed). results/comparison-20261018-110108-14dd28b3/summary.json. Không khẳng định SMT luôn nhanh hơn.']
  ];
  info.getRange('B13').values=[['Ch2 GUI không nhận typedef struct và cảnh báo leak nghi vấn dòng 263; đối chiếu thấy free dòng 267. ABI Windows x64: Input/Stock 24 byte, JsonReader 24 byte, JsonFixture 40 byte; heap quantity 400 byte riêng. GCC -fanalyzer không phát cảnh báo. Đây không phải kiểm chứng Ch6.']];
  info.getRange('A13:B18').format.rowHeight=100;
  info.getRange('A13:B18').format.wrapText=true;
  workbook.worksheets.getItem('TestCase').getRange('F51').values=[['Trả 1 với quantity=101 (biên trên, lượt cũ); gói GUI Ch3 mới dùng quantity=0 (biên dưới), cũng trả 1. Hai fixture khác nhau, không coi là cùng ca đã chạy.']];
  workbook.recalculate();
  console.log((await workbook.inspect({kind:'region',sheetId:'ThongTin',range:'A14:B18',maxChars:4000})).ndjson);
  await render('ThongTin','A13:B18','20261020-excel-after.png');
  await render('TestCase','D51:F52','20261020-cases-after.png');
  console.log((await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},maxChars:1500})).ndjson);
  const file=await SpreadsheetFile.exportXlsx(workbook);
  await file.save(path.join(output,'badminton_spec.updated-20261020.xlsx'));
}else{
  throw new Error('Unknown mode');
}
