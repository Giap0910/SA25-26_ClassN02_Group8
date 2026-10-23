from pathlib import Path
from PIL import Image, ImageDraw
from pypdf import PdfReader
from docx import Document

root = Path(__file__).parent
pages = PdfReader(root/'Baocao.checked.pdf').pages
print('Page 33 tail:', pages[32].extract_text()[-600:])
print('Group table visible:', any('Mức độ hoàn thành' in p.extract_text() for p in pages))
doc = Document(root/'Baocao.checked.docx')
for p in doc.paragraphs:
    if p.text.startswith('6.10'): print(p._p.xml[-2200:])
paths = sorted(root.glob('ready-*.png'))
for start in range(0,len(paths),8):
    sheet = Image.new('RGB',(1500,2240),'#dddddd')
    draw = ImageDraw.Draw(sheet)
    for index,path in enumerate(paths[start:start+8]):
        pic=Image.open(path).convert('RGB'); pic.thumbnail((365,1080))
        x,y=(index%4)*375,(index//4)*1120
        sheet.paste(pic,(x,y+25)); draw.text((x+5,y+5),path.stem,fill='black')
    sheet.save(root/f'contact-{start//8+1}.png')
