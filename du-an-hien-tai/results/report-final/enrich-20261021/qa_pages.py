from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

root = Path(__file__).parent
paths = sorted(root.glob('finalqa-*.png'))
for start in range(0, len(paths), 12):
    sheet = Image.new('RGB', (1200, 1320), '#dddddd')
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths[start:start+12]):
        pic = Image.open(path).convert('RGB')
        pic.thumbnail((290, 405))
        x, y = (index % 4)*300, (index//4)*440
        sheet.paste(pic, (x, y+22))
        draw.text((x+8,y+5), path.stem, fill='black')
    sheet.save(root/f'contact-{start//12+1}.png')
