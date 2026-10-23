from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
import hashlib
import re
from xml.sax.saxutils import escape
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

ROOT = Path('C:/Project/Badminton_Stock_Security')
OUT = ROOT / 'results/report-final/cover-toc-20261021'
REFERENCE = Path('C:/Users/vxg09/Downloads/ClassN01_Group-11_Project-report-1.docx')
SOURCE = OUT / 'Bao_cao_An_toan_phan_mem.before-cover-toc.pdf'
TARGET = OUT / 'Bao_cao_An_toan_phan_mem.cover-toc-20261021.pdf'
W, H = 595.28, 841.89
pdfmetrics.registerFont(TTFont('TimesVN', 'C:/Windows/Fonts/times.ttf'))
pdfmetrics.registerFont(TTFont('TimesVN-Bold', 'C:/Windows/Fonts/timesbd.ttf'))


def center(c, text, y, size=14, bold=True):
    c.setFont('TimesVN-Bold' if bold else 'TimesVN', size)
    c.drawCentredString(W/2, y, text)


def paragraph(c, text, x, top, width=480, size=11.5, bold=False):
    style = ParagraphStyle('text', fontName='TimesVN-Bold' if bold else 'TimesVN',
                           fontSize=size, leading=size*1.4)
    value = Paragraph(escape(text), style)
    _, height = value.wrap(width, H)
    value.drawOn(c, x, top-height)
    return height


def cover():
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=(W, H))
    c.setLineWidth(1.4); c.rect(24, 24, W-48, H-48)
    center(c, 'PHENIKAA UNIVERSITY', 758)
    center(c, 'PHENIKAA SCHOOL OF COMPUTING', 736)
    center(c, '***', 716, 12)
    logo = ImageReader(BytesIO(ZipFile(REFERENCE).read('word/media/image1.jpeg')))
    c.drawImage(logo, (W-160)/2, 540, 160, 162, preserveAspectRatio=True)
    center(c, 'HỌC PHẦN: AN TOÀN PHẦN MỀM', 493)
    center(c, 'ĐỀ TÀI:', 463)
    center(c, 'KIỂM THỬ MÔ HÌNH TỒN KHO BADMINTON', 433)
    center(c, 'BẰNG JSON, SANITIZER VÀ CONCOLIC', 410)
    center(c, 'TÀI LIỆU: BÁO CÁO MÔN HỌC', 376)
    cover_metadata(c)
    center(c, 'Hà Nội, tháng 10 năm 2026', 65, 12, False)
    c.save(); return PdfReader(stream)


def cover_metadata(c):
    rows = [('Mã học phần', '......................................'), ('Lớp', 'N02'),
            ('Giảng viên', 'ThS. Vũ Quang Dũng'), ('Nhóm', '11'),
            ('Thành viên / MSSV', '......................................')]
    for i, (label, value) in enumerate(rows):
        y = 318-i*30
        c.setFont('TimesVN-Bold', 13); c.drawString(100, y, label)
        c.setFont('TimesVN', 13); c.drawString(240, y, ':  '+value)
    for y in (168, 138, 108):
        c.drawString(254, y, '......................................')


def group_info(page_number):
    stream = BytesIO(); c = canvas.Canvas(stream, pagesize=(W, H))
    y = 780
    rows = [('1. Thông tin nhóm và phạm vi báo cáo', True),
            ('Học phần: An toàn phần mềm. Lớp N02, nhóm 11.', False),
            ('Thành viên / MSSV và phân công: để trống theo yêu cầu.', False),
            ('Tên đề tài đăng ký: ........................................................', False),
            ('Phạm vi nội dung: kiểm thử mô hình tồn kho badminton bằng JSON, sanitizer và concolic; tổng hợp Ch1–Ch4, tạm gác Ch5–Ch6.', False),
            ('Bằng chứng thực nghiệm được tổng hợp ngày 20/10/2026. Bìa và mục lục được cập nhật ngày 21/10/2026; không thay số liệu chạy.', False),
            ('Tài liệu hướng dẫn ghi hai mã học phần khác nhau CSE703093 và CSE703153. Mã học phần chính thức cần nhóm xác nhận nên đang để trống trên bìa.', False),
            ('Báo cáo phân biệt kết quả đã chạy với giới hạn chưa kiểm chứng; không tự xác nhận đáp ứng mọi điều kiện nộp của giảng viên.', False)]
    for text, bold in rows:
        y -= paragraph(c, text, 57, y, size=16 if bold else 11.5, bold=bold)+18
    footer(c, page_number)
    c.save(); return PdfReader(stream)


def footer(c, number):
    c.setFont('TimesVN', 9)
    c.drawString(57, 28, 'An toàn phần mềm | Mô hình tồn kho badminton | 21/10/2026')
    c.drawRightString(538, 28, str(number))


def entries(reader):
    result = [(0, '1. Thông tin nhóm và phạm vi báo cáo', 0)]
    main_titles = {'2. Tổng quan đề tài', '3. Phương pháp luận',
                   '4. Phân tích lỗ hổng & Bản vá', '5. Bảng tổng hợp before/after',
                   '6. Bằng chứng kiểm chứng', '7. Phản biện & Bài học', '8. Phụ lục'}
    for index, page in enumerate(reader.pages[1:], 2):
        lines = page.extract_text().splitlines()[2:]
        for line in lines:
            if line in main_titles:
                result.append((0, line, index))
            elif re.match(r'^(6|8)\.\d+\.', line) and '(tiếp)' not in line:
                result.append((1, line, index))
            elif line.startswith('CWE-') and ':' in line and index in range(4, 8):
                result.append((1, line, index))
            elif line.startswith('Hình 6.'):
                result.append((2, line, index))
    return result


def add_subsections(items):
    extra = {2: ['Luồng thực hiện', 'Phạm vi đầu vào', 'Những phần đã và chưa thực hiện'],
             3: ['Bước 1. Xác định hợp đồng', 'Bước 2. Sinh và kiểm tra C',
                 'Bước 3. Kiểm thử động và oracle', 'Bước 4. Kiểm tra bộ nhớ và số học',
                 'Bước 5. Concolic và chạy lại test', 'Công cụ và ngân sách'],
             8: ['Kết luận đối với mẫu báo cáo'],
             23: ['Nếu bắt đầu lại, nên thay đổi gì?', 'Điều gì chưa đủ bằng chứng?',
                  'Bài học phương pháp luận', 'Điều kiện trước khi chốt nộp']}
    labels = ['Vị trí và mô tả', 'Nguyên nhân gốc rễ', 'Bằng chứng trước',
              'Cách vá / cơ chế hiện tại', 'Bằng chứng sau']
    result = []
    for level, title, page in items:
        result.append((level, title, page))
        if level == 0:
            result.extend((1, text, page) for text in extra.get(page, []))
        if title.startswith('CWE-'):
            result.extend((2, f'{i}. {text}', page) for i, text in enumerate(labels, 1))
    return result


def toc_style(level):
    return ParagraphStyle('toc', fontName='TimesVN-Bold' if level < 2 else 'TimesVN',
                          fontSize=11.5 if level == 0 else 10.5, leading=14.5)


def paginate(items):
    pages, rows, y = [], [], 744
    for index, (level, title, target) in enumerate(items):
        style = toc_style(level)
        label = Paragraph(escape(title), style)
        _, height = label.wrap(424-level*17, H)
        needed = max(19, height+7)+(5 if level == 0 else 0)
        keep = 5*22 if title.startswith('CWE-') else (22 if level == 0 else 0)
        if y-needed-keep < 65 and rows:
            pages.append(rows); rows, y = [], 744
        rows.append((level, title, target, y, height))
        y -= needed
    if rows: pages.append(rows)
    return pages


def target_page(old_number, toc_count):
    return toc_count+2 if old_number == 0 else old_number+toc_count+1


def draw_toc_row(c, row, count):
    level, title, old, y, height = row
    x = 57+level*17
    label = Paragraph(escape(title), toc_style(level))
    width = 424-level*17
    label.wrap(width, H); label.drawOn(c, x, y-height)
    baseline = y-height+3
    last_line = label.blPara.lines[-1]
    extra = last_line[0] if isinstance(last_line, tuple) else last_line.extraSpace
    end = min(x+width-extra+7, 500)
    c.setFont('TimesVN', 10.5)
    if end < 511:
        c.drawString(end, baseline, '.'*int((512-end)/2.7))
    c.drawRightString(538, baseline, str(target_page(old, count)))


def contents(pages):
    stream = BytesIO(); c = canvas.Canvas(stream, pagesize=(W, H))
    for index, rows in enumerate(pages, 2):
        center(c, 'MỤC LỤC' if index == 2 else 'MỤC LỤC (tiếp)', 782, 17)
        for row in rows: draw_toc_row(c, row, len(pages))
        footer(c, index); c.showPage()
    c.save(); return PdfReader(stream)


def renumber(page, number):
    stream = BytesIO(); c = canvas.Canvas(stream, pagesize=(W, H))
    c.setFillColorRGB(1, 1, 1); c.rect(50, 18, 495, 26, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0); footer(c, number); c.save()
    page.merge_page(PdfReader(stream).pages[0])
    return page


def navigation(writer, pages):
    parents = {}
    for toc_index, rows in enumerate(pages, 1):
        for row in rows:
            level, title, old, y, height = row
            destination = target_page(old, len(pages))-1
            parent = parents.get(level-1)
            parents[level] = writer.add_outline_item(title, destination, parent=parent)
            writer.add_annotation(toc_index, Link(rect=(57+17*level, y-height-2, 540, y+2),
                                                 target_page_index=destination))


def main():
    reader = PdfReader(SOURCE)
    pages = paginate(add_subsections(entries(reader)))
    writer = PdfWriter()
    writer.add_page(cover().pages[0])
    writer.append(contents(pages), import_outline=False)
    writer.add_page(group_info(len(pages)+2).pages[0])
    for old, page in enumerate(reader.pages[1:], 2):
        writer.add_page(renumber(page, target_page(old, len(pages))))
    navigation(writer, pages)
    writer.add_metadata({'/Title': 'Báo cáo An toàn phần mềm - Tồn kho badminton', '/Author': ''})
    writer.write(TARGET)
    print('Output:', TARGET)
    print('Pages:', len(writer.pages), 'TOC pages:', len(pages), 'Entries:', sum(map(len, pages)))
    print('Reference SHA256:', hashlib.sha256(REFERENCE.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
