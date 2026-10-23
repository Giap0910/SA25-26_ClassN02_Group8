from pathlib import Path
from io import BytesIO
from xml.sax.saxutils import escape
import ast
import hashlib
import json
import re
from statistics import median
from pypdf import PdfReader, PdfWriter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors

ROOT = Path('C:/Project/Badminton_Stock_Security')
BASE = ROOT/'results/report-final'
OUT = BASE/'enrich-20261021'
CH = ROOT/'results/ch123-20261018-202400-9a09dbce'
TARGET = OUT/'Bao_cao_An_toan_phan_mem.enriched-20261021.pdf'
OLD = OUT/'Bao_cao_An_toan_phan_mem.before-enrich.pdf'
SOURCE = (BASE/'build_report.py').read_text(encoding='utf-8')
NS = {}
exec(compile(SOURCE.split("p('1. Trang bìa")[0], 'report-support', 'exec'), NS)
STORY, STYLES = NS['story'], NS['styles']
FIGURES, TOC_ENTRIES, HOOKS = [], [], set()


class Region(Flowable):
    def __init__(self, path, box=None, max_height=450):
        Flowable.__init__(self)
        self.source = ImageReader(str(path))
        iw, ih = self.source.getSize()
        self.box = box or (0, 0, iw, ih)
        self.scale = min(480/self.box[2], max_height/self.box[3])
        self.width, self.height = self.box[2]*self.scale, self.box[3]*self.scale
        self.hAlign = 'CENTER'
    def draw(self):
        x, y, w, h = self.box
        iw, ih = self.source.getSize()
        self.canv.saveState()
        clip = self.canv.beginPath(); clip.rect(0, 0, self.width, self.height)
        self.canv.clipPath(clip, stroke=0)
        self.canv.drawImage(self.source, -x*self.scale, (y+h-ih)*self.scale,
                            iw*self.scale, ih*self.scale)
        self.canv.restoreState()


class Report(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if not hasattr(flowable, 'toc_item'): return
        level, title, key = flowable.toc_item
        self.canv.bookmarkPage(key)
        self.notify('TOCEntry', (level, title, self.page, key))


def clean(text):
    text = text.replace('Ch5–Ch6 được tạm gác theo yêu cầu, không ghi hoàn tất.', '')
    text = text.replace('; Ch5–Ch6 chưa được xác nhận trong bản này.', '.')
    text = text.replace('∈', 'thuộc ')
    if re.search(r'\bCh\s*[56]\b|\bChương\s*[56]\b', text, re.I):
        raise ValueError('Unexpected excluded chapter in text')
    return text


def p(text, style='BodyVN', hook=True):
    text = clean(text)
    if text.startswith('• Thông tin nhóm, tên đề tài'): return
    text = text.replace(' Thông tin nhóm vẫn để trống.', '')
    text = text.replace('Chưa tạo ZIP hay nộp bài trong lần cập nhật này.', 'Việc biên soạn PDF không đồng nghĩa đã nộp bài.')
    for old, new in [('8.4.', '8.3.'), ('8.5.', '8.4.'), ('8.6.', '8.5.'), ('8.7.', '8.6.')]:
        if text.startswith(old):
            text = new + text[len(old):]
            break
    if text.startswith('8.5. Danh mục đối chiếu'): STORY.append(PageBreak())
    paragraph = Paragraph(text, STYLES[style])
    title = re.sub('<[^>]+>', '', text).replace('&amp;', '&')
    level = 0 if re.match(r'^[1-8]\. ', title) and style == 'HeadVN' else None
    if style == 'SubVN' and re.match(r'^\d+\.\d+\.', title): level = 1
    if level is not None:
        key = 'heading-'+str(len(TOC_ENTRIES))
        paragraph.toc_item = (level, title, key)
        TOC_ENTRIES.append((level, title, key))
    STORY.append(paragraph)
    if hook: insert_hook(title)


def heading(text):
    if text.startswith('7.'):
        gui_campaign(); selected_cases(); teacher_matrix()
    STORY.append(PageBreak())
    p(text, 'HeadVN')


def table(rows, widths):
    NS['table'](rows, widths)


def figure(name, title, caption, box=None, path=None, detail=None):
    path = path or OUT/'images'/f'{name}.png'
    STORY.append(PageBreak())
    number = len(FIGURES)+1
    label = f'Hình {number}. {title}'
    para = Paragraph(escape(label), STYLES['SubVN'])
    excel = name.startswith('15') and detail is not None
    STORY.extend([para, Spacer(1, 10), Region(path, box, 270 if excel else 370 if detail else 470)])
    if detail:
        STORY.extend([Spacer(1, 10), Region(path, detail, 270 if excel else 145)])
    STORY.append(Spacer(1, 14))
    p(caption, hook=False)
    p('Nguồn: '+escape(str(path.relative_to(ROOT)).replace('\\', '/')), 'CellVN', False)
    FIGURES.append({'number': number, 'source': str(path), 'box': box, 'detail': detail})


def old_figure(file, title, caption, box, detail=None):
    path = BASE/'ch1-gui-user-20261018.png' if file == 'ch1' else CH/(file+'.png')
    figure(file, title, caption, box, path, detail)


def data_contract():
    p('Hợp đồng dữ liệu và miền giá trị', 'SubVN', False)
    table([['Trường', 'Kiểu / miền', 'Vai trò'],
           ['available, reserved', 'Số nguyên int32, trạng thái kho không âm', 'Kho tổng ban đầu do test cung cấp'],
           ['variant_available, variant_reserved', 'Số nguyên int32; nhất quán khi có biến thể', 'Kho của tối đa một biến thể'],
           ['action', 'Số nguyên 0–15', 'Mã fixture điều phối giữ/hoàn/tất toán/lặp; không phải enum HTTP'],
           ['items', 'Mảng từ 1 đến 100 record', 'Mỗi record chỉ có quantity'],
           ['quantity', 'Giá trị nguyên chính xác 1–100; tổng không quá 100', 'Parser chấp nhận biểu diễn số nguyên chính xác, không ép chuỗi/bool thành số']], [135,170,175])
    p('Giới hạn 16.384 byte áp dụng văn bản đầu vào; 64 byte áp dụng từng token số; 100 là số record tối đa. Các giới hạn này không đồng nghĩa sizeof(struct) và không phải giới hạn HTTP đã xác nhận. Khóa bắt buộc, khóa lạ/trùng và sai kiểu được kiểm tra theo hợp đồng adapter riêng.', hook=False)
    figure('14-json-spec', 'Đặc tả JSON và giới hạn đầu vào',
           'Ảnh mã nguồn stock_spec.json do Phong cung cấp ngày 21/10/2026. Tên file, phạm vi một sản phẩm và json_transport được giữ rõ; ảnh đặc tả không phải bằng chứng thực thi test.')


def methodology_evidence():
    p('Truy vết yêu cầu và quy tắc kết luận', 'SubVN', False)
    p('Mỗi ca có mã yêu cầu, input, các bước và expected result. Excel chứa 55 ca tài liệu hóa, còn các bộ thực thi có tập và thời điểm khác nhau: 41 hồi quy JSON; 40 ca DLL; 6 test xuất từ GUI. Chỉ đánh dấu kết quả thực thi khi có log tương ứng, không dùng cột expected làm actual.', hook=False)
    p('Oracle Python được dùng để đối chiếu mã trả và trạng thái cuối của C. Guard có oracle mã trả riêng. Test characterization chỉ chạy lại hành vi đã ghi nhận; vì vậy sáu test xuất GUI còn được đối chiếu với quy tắc đặc tả độc lập.', hook=False)
    figure('15a-requirements', 'Mười hai yêu cầu chức năng và an toàn',
           'Ảnh Excel thể hiện REQ-1–6 và REQ-J1–J6. Đây là hợp đồng và ma trận yêu cầu, không phải bảng kết quả PASS. Các yêu cầu JSON bổ sung giới hạn record, kiểu, bộ nhớ và đối chiếu oracle.')


def json_run_evidence():
    figure('10-json-log', 'Lượt JSON đã lưu: 100 black-box và 100 coverage-guided',
           'Ảnh xem lại current-json.log của lượt ngày 18/10/2026, do Phong cung cấp ngày 21/10/2026. Hai chế độ đều không có crash, timeout, vi phạm bất biến hay lệch oracle; số mẫu coverage của snapshot là 220 dòng và 336 nhánh.')
    p('Trong lượt ngắn seed 1 này, black-box đạt 172/220 dòng và 187/336 nhánh, cao hơn coverage-guided 162/220 và 183/336. Kết quả không mâu thuẫn lượt dài: ngân sách, seed, corpus và phiên bản khác nhau có thể đổi thứ tự. Không dùng tên “coverage-guided” để mặc định kết luận nó luôn phủ tốt hơn.', hook=False)


def guard_evidence():
    old_figure('ch3-gui-guard-tests', 'Sáu test concolic và probe của guard',
               'Ảnh GUI gốc ngày 18/10/2026: 60 input, giữ sáu test, 0 crash, 22/22 probe riêng stock_reserve_guard. Chỉ trình bày vùng console liên quan; kết quả không đại diện parser JSON.', (433,87,1470,185))
    figure('13-pytest', 'Chạy lại gói test guard đã xuất',
           'Ảnh xem lại ch3-export-pytest.log, kết quả 6 passed in 1.65s. Đây là log lượt đã lưu, không phải thời gian chạy mới ngày chụp ảnh. Sáu mã trả cũng khớp independent_spec_checks trong ch3-export-verification.json.')


def kripke_evidence():
    old_figure('ch1', 'Kiểm chứng CTL và loại trừ nhãn',
               'Ảnh GUI gốc do Phong cung cấp: bốn CTL đúng trong mô hình hữu hạn, cancelled và settled không cùng xuất hiện. Vùng hiển thị tập trung console và đồ thị; không suy ra loại trừ hai transaction backend.', (350,75,1550,950), (355,170,1250,230))


def allocation_evidence():
    p('Luồng xử lý và vòng đời vùng nhớ', 'SubVN', False)
    table([['Bước', 'Kiểm soát', 'Khi lỗi'],
           ['1. Kiểm tra đầu vào', 'NULL/độ dài được kiểm tra trước cấp phát', 'Trả 101; chưa có mảng heap'],
           ['2. Tạo reader/fixture', 'Reader theo dõi data, size, pos', 'Không đọc vượt size'],
           ['3. calloc', '100 phần tử int32_t =400 byte, khởi tạo bằng 0', 'Nếu NULL trả 105 trước dereference'],
           ['4. Parse/kiểm tra quantity', 'Số record và miền quantity kiểm tra trước sử dụng', 'Lưu code, vẫn đi qua free'],
           ['5. Áp dụng nghiệp vụ', 'Chỉ gọi jsonStock khi code còn 0', 'Mã lỗi không bỏ qua free'],
           ['6. Giải phóng/return', 'free(fixture.quantities), sau đó return code', 'Bộ đếm cấp phát kiểm tra sau mỗi ca']], [105,235,140])
    p('JsonFixture có size 40 byte trên ABI Windows x64 nhưng chỉ chứa con trỏ tới mảng quantities; 400 byte heap là vùng riêng. Con trỏ trỏ struct không có nghĩa mọi trường nằm trong cùng một allocation. Test cân bằng bộ đếm chỉ đo các allocation được instrument; kiểm tra leak bằng Dr. Memory bổ sung góc nhìn độc lập.', hook=False)
    figure('01-layout', 'Layout do compiler xác định',
           'Ảnh xem lại ch2-record-layouts.log. Các struct ẩn danh tại dòng 9,10,49,50 của stock_json_seclab.c tương ứng Input, Stock, JsonReader, JsonFixture; không nhầm với struct của thư viện chuẩn ở đầu ảnh.')
    figure('04-allocation-code', 'calloc, kiểm tra NULL và free trong jsonEvaluate',
           'Ảnh editor có tên stock_json_seclab.c và số dòng. Dòng 264 trả 105 khi calloc thất bại; sau cấp phát thành công, code parse/nghiệp vụ được thu lại rồi free ở dòng 267. Đây là mã hiện tại, không phải bản vá đối chiếu v0.')
    figure('02-memory-tests', 'Bốn nhóm test bộ nhớ đạt',
           'Ảnh xem lại log: 4 tests, 0 failures/errors/skipped. Gồm tiêm lỗi cấp phát, cân bằng cấp phát, adapter/wrap và đối chứng sanitizer. Các chương trình lỗi mẫu xác nhận công cụ hoạt động, không tính là lỗi tồn kho.')
    figure('03-sanitizer', 'ASan và UBSan: cấu hình và kết quả',
           'Ảnh xem lại log ngày 18/10/2026: 41 hồi quy, 100 mutation seed 1, 41,6319755 giây; năm chỉ số bất thường đều 0. Cờ address,undefined bật, leak_sanitizer=false và coverage_measured=false được giữ rõ.')


def static_limitations():
    old_figure('ch2-gui-struct', 'Giới hạn nhận diện typedef struct của GUI',
               'GUI báo không tìm thấy struct; đây là giới hạn nhận diện. Kết quả compiler và ảnh layout mới là bằng chứng về size/alignment.', (350,75,1550,590))
    old_figure('ch2-gui-memory-warning', 'Cảnh báo nghi leak của bộ quét tĩnh',
               'GUI nghi CWE-401 tại calloc dòng 263; đối chiếu free dòng 267 và các phép thử động để đánh giá. Không coi cảnh báo tĩnh đơn lẻ là lỗi sản phẩm đã được xác nhận.', (350,420,1550,165))


def leak_evidence():
    p('Đọc kết quả leak theo ba lớp bằng chứng', 'SubVN', False)
    p('Đối chứng bỏ free chứng minh công cụ quan sát được leak thật (123 byte). Đối chứng có free giúp nhận diện phần nhiễu cùng môi trường. Simulator không báo definite application leak trong workload đã thử, nhưng có một potential possible leak hệ thống. Ba quan sát phải trình bày cùng nhau, không chỉ trích dòng NO ERRORS FOUND.', hook=False)
    specs = [('05-leak-positive','Đối chứng bỏ free: leak 123 byte','Ảnh xem lại report PID16552. Một leak xác định 123 byte; đường stack dẫn về leak_control.c. Exit 23 là cấu hình công cụ cho đối chứng có lỗi, không phải crash mục tiêu.'),
             ('06-leak-clean','Đối chứng free đúng','Ảnh xem lại report PID21052: 0 byte definite leak, vẫn có 1 potential leak trong phần bị bộ lọc hệ thống giữ riêng. Không mô tả mọi cảnh báo bằng 0.'),
             ('07-leak-simulator','Dr. Memory trên simulator','Ảnh xem lại PID22444: 0 definite leak và 1 potential leak. 22.827 byte still-reachable không được tự đổi tên thành definite leak; vẫn giữ phần ERRORS IGNORED và mặc định suppression.'),
             ('08-leak-potential','Potential possible leak 24 byte ở ntdll/TLS','Ảnh giữ nguyên cảnh báo và stack loader/TLS. Cùng dấu vết xuất hiện ở đối chứng sạch; đó là cơ sở nghi nhiễu môi trường nhưng chưa phải kết luận loại trừ triệt để.'),
             ('09-leak-oracle','Xác nhận workload và oracle của lượt leak','Ảnh đọc leak-summary.json: 41+100 fixture, 10 vòng, 1.410 output, oracle_matches=True, exit 0, timeout=False. Không phải 1.410 input ngẫu nhiên độc lập.')]
    for name, title, caption in specs: figure(name, title, caption)


def ast_evidence():
    specs = [('ch3-gui-ast','AST và độ phức tạp ước lượng',(430,423,1080,95),'McCabe 162/nesting 3/~206 câu lệnh là ước lượng toàn file của GUI, không phải độ phức tạp riêng guard.'),
             ('ch3-gui-cfg','CFG guard ở lượt wrap ban đầu',(550,550,650,475),'Đồ thị ban đầu phủ 9/11 block (81%), return 3/5 chưa phủ. Không đồng nhất với lượt concolic sau đó đạt 22/22 probe.'),
             ('ch3-gui-sat','Nghiệm SAT của nhánh bị từ chối',(428,87,1000,75),'available=1, r=2147483647, q=1 thỏa đường đi tới nhánh từ chối tràn. Công thức được nhập thủ công; không phải crash.'),
             ('ch3-gui-unsat','UNSAT cho điều kiện tràn sau guard',(430,87,1000,75),'Điều kiện r≤2147483647−q và r+q>2147483647 mâu thuẫn trên miền đang xét. Không phải BMC toàn bộ C.')]
    for name, title, box, caption in specs:
        old_figure(name, title, 'Ảnh GUI gốc ngày 18/10/2026, chỉ hiển thị vùng kết quả liên quan. '+caption, box)


def comparison_evidence():
    p('Nhận xét định lượng và thiên lệch lấy mẫu', 'SubVN', False)
    p('Nhánh reserved tràn nằm sát INT_MAX, nên chọn đều trên miền lớn ít gặp vùng này trong ngân sách. Edge-enriched đưa giá trị biên vào với xác suất 20% mỗi trường nên tìm được cả năm seed. SMT dùng điều kiện đường đi để tạo witness rồi chỉ cần một lần gọi C xác nhận; chi phí dựng ràng buộc/solver vẫn phải tính.', hook=False)
    p('Năm seed không đủ để khái quát ưu thế cho mọi parser. Lượt uniform chưa tìm thấy là dữ liệu bị chặn bởi ngân sách, không phải thời gian vô hạn. Phải phân biệt ít lần gọi C với ít giây, và SMT giải đường đi trực tiếp với một engine concolic đầy đủ.', hook=False)
    figure('11-comparison', 'Ba phương pháp tìm cùng nhánh return 3',
           'Ảnh xem lại summary: cùng mục tiêu, ngân sách 50.000 C calls/seed và timeout SMT 5.000 ms. Bảng giữ cả các lượt found=False; không loại bỏ lượt không tìm thấy để làm đẹp kết quả.')


def gui_campaign():
    STORY.append(PageBreak()); p('6.10. Chiến dịch JSON trong GUI ngày 21/10/2026', 'SubVN', False)
    table([['Kỹ thuật', 'Input thực chạy', 'Giữ test', 'Lỗi được báo'],
           ['Boundary',70,4,0], ['Black-box',137,2,0], ['Mutation',80,2,0],
           ['Coverage-guided',150,1,0], ['Tổng',437,9,0]], [160,110,100,110])
    p('Nguồn là ảnh chiến dịch và bảng test do Phong cung cấp, không phải summary của runner terminal. Hàm stock_json, bốn kỹ thuật, ngân sách hiển thị 150/kỹ thuật, không dùng sanitizer. Console ghi 16,9 giây, sơ đồ 17,4 giây; giữ nguyên hai phép hiển thị, không chọn một số để thay số kia. Tổng 437 là số thực chạy, không suy thành 600.', hook=False)
    p('Coverage hàm hiển thị 82%; CFG wrapper 5/6 block xấp xỉ 83%, là thước đo khác. Màu “Cov mới” thể hiện phần tăng thêm tại từng giai đoạn: bằng 0 ở giai đoạn sau không có nghĩa chúng không chạy hay không phủ gì. Chưa có tập hit thô từ lượt GUI này để đối chiếu độc lập toàn bộ chỉ số.', hook=False)
    figure('12a-gui-campaign', 'Chiến dịch GUI hoàn tất với 437 input',
           'Ảnh chạy mới do Phong cung cấp ngày 21/10/2026. Vùng console và sơ đồ giữ đủ kết quả; chỉ trình bày khu vực đang phân tích. 0 lỗi/crash trong ngân sách không có nghĩa mọi input đều đúng.', (430,75,1450,920))
    figure('12b-gui-cases', 'Chín test JSON được GUI giữ lại',
           'Chín test giữ lại đều trả 100 (JSON/schema/kiểu không hợp lệ), không phải chín crash. Một số chuỗi bị rút gọn bởi GUI nên không thể tái tạo đầy đủ chỉ từ ảnh. Ảnh chưa chứng minh đường nghiệp vụ thành công; các ca hợp lệ được kiểm tra ở hồi quy độc lập.')
    p('Lượt GUI raw-string này thiên về dữ liệu bị từ chối sớm; không lấy coverage wrapper để chứng minh parser và nghiệp vụ đã phủ hết. Biện pháp bổ trợ đã có là fixture JSON hợp lệ trong golden regression và oracle so sánh đầy đủ trạng thái. Tăng ngân sách hoặc thêm seed hợp lệ là hướng cải thiện, chưa được ghi thành kết quả đã chạy.', hook=False)


def selected_cases():
    STORY.append(PageBreak()); p('6.11. Ca kiểm thử tiêu biểu và truy vết kết quả', 'SubVN', False)
    location = ROOT/'results/stock-json-20261018-093532-9d53d681/regression'
    regression = json.loads((location/'regression.json').read_text(encoding='utf-8'))
    names = ['reserve','cancel-twice','settle-twice','quantity-101','reserved-overflow','string','limit-bytes','over-limit-bytes']
    reasons = ['Giữ 2 từ kho 10: kiểm tra cập nhật, không chỉ mã trả.', 'Hủy lặp: kiểm tra hoàn đúng một lần.',
               'Tất toán lặp: không trừ khả dụng lần hai.', 'quantity=101: vượt biên nghiệp vụ.',
               'reserved=INT_MAX: chặn cộng tràn.', 'quantity chuỗi: từ chối sai kiểu, không ép số.',
               'Đúng 16.384 byte: kiểm tra biên bao gồm.', '16.385 byte: kiểm tra từ chối quá dài.']
    rows = [['Ca / mục đích','Expected code','Actual / trạng thái','Kết quả']]
    for name, reason in zip(names, reasons):
        row = next(item for item in regression if item['name']==name)
        actual = row['actual']
        state = f"code={actual['code']}; available={actual['available']}; reserved={actual['reserved']}; state={actual['state']}"
        rows.append([name+' — '+reason, row['expected_code'], state, row['outcome']])
    table(rows, [190,65,180,45])
    p('Nguồn: regression/regression.json của lượt 093532, 41 ca. “ok” trong runner là actual khớp oracle về toàn bộ mã và trạng thái, không chỉ tiến trình thoát 0. Những trường 0 trong output của lỗi parse là output khởi tạo; không diễn giải thành việc xóa tồn kho thật.', hook=False)
    p('Fixture reserve/cancel-twice/settle-twice cùng bắt đầu available=10, reserved=0, quantity=2; action tương ứng 0/5/6. Kết quả cuối lần lượt (8,2,state1), (10,0,state2), (8,0,state3). Các ca này bổ sung đường hợp lệ mà chín test GUI trả 100 chưa thể hiện.', hook=False)
    excel_evidence()


def excel_evidence():
    p('Phân biệt expected trong Excel với actual của C', 'SubVN', False)
    p('Excel giữ 55 ca và liên kết yêu cầu; ảnh cột KetQuaMongDoi không phải bảng thực thi. TC-SMT1 dùng quantity=101 ở ca cũ, gói GUI mới dùng quantity=0; cùng nhánh trả 1 nhưng không gán nhầm hai fixture. Các ảnh dưới được hiển thị theo vùng để đọc được; dữ liệu gốc không bị sửa.', hook=False)
    specs = [('15b-cases-1','Các ca nghiệp vụ và JSON đầu tiên','TC-1–6, TC-J01–12: kiểm tra số lượng, kho thiếu, giữ/hoàn/tất toán và giới hạn record.'),
             ('15c-cases-2','Các ca kiểu số và dữ liệu sai kiểu','TC-J13–28: fixture âm/không nhất quán, giá trị biên, số thập phân nguyên chính xác, số mũ và chuỗi/bool/null.'),
             ('15d-cases-3','Schema, giới hạn byte và đường lỗi cấp phát','TC-J28–43: khóa thiếu/lạ/trùng, dữ liệu UTF-8/NUL/truncated, đúng/quá biên byte, cấp phát thất bại và cân bằng.'),
             ('15e-cases-smt','Sáu ca guard và liên kết yêu cầu','TC-SMT1–6 là guard thuần số; mã 0 chỉ là qua guard, chưa cập nhật kho. Giữ chú thích khác biệt quantity của lượt cũ/mới.')]
    for name, title, caption in specs:
        image = ImageReader(str(OUT/'images'/f'{name}.png'))
        w, h = image.getSize()
        figure(name, title, 'Ảnh bảng expected/test design, không tự đánh dấu toàn bộ PASS. '+caption,
               box=(0,0,w/2,h), detail=(w/2,0,w/2,h))


def teacher_matrix():
    STORY.append(PageBreak()); p('6.12. Đối chiếu nội dung nhận xét giảng viên', 'SubVN', False)
    table([['Nội dung cần làm rõ','Cách đáp ứng / bằng chứng','Giới hạn kết luận'],
           ['Đọc JSON, kiểu dữ liệu', 'Hợp đồng trường; ảnh đặc tả; ca sai kiểu và hồi quy', 'Fixture mô hình, không phải request HTTP thật'],
           ['Size và record', '16.384 byte, token 64 byte, 1–100 record; layout compiler', 'Size struct không phải size văn bản JSON'],
           ['Cấp phát và vòng đời', 'calloc 400 byte; NULL=105; free; test bộ đếm', 'Bộ đếm chỉ theo allocation được instrument'],
           ['Crash và tràn', 'ASan/UBSan, đối chứng lỗi mẫu, guard chặn tràn', 'Không có finding trong tải đã thử, không phải chứng minh mọi đầu vào'],
           ['Leak', 'Dr. Memory đối chứng có/sạch và simulator 1.410 lần gọi', 'Không chạy LSan; còn potential 24 byte hệ thống'],
           ['White-box sinh test', 'Guard 60 input, 6 test, 22/22 probe; pytest và oracle', 'Không suy rộng parser hoặc toàn website'],
           ['So sánh phương pháp', 'Cùng nhánh return3, 5 seed, C calls và thời gian', 'SMT trực tiếp không đồng nhất full concolic'],
           ['Kết quả tái kiểm tra', 'Log, ảnh, snapshot, hash và đường dẫn từng lượt', 'Ảnh đọc log không phải thực thi mới']], [125,205,150])
    p('Bảng đối chiếu dựa trên các nội dung nhận xét người học đã cung cấp, không thay thế xác nhận chấm điểm hoặc mọi yêu cầu đăng ký đề tài. Không tạo lỗi sản phẩm hoặc cặp v0/v1 giả để điền bảng before/after.', hook=False)


def insert_hook(title):
    rules = [('Fixture chứa trạng thái', data_contract), ('LeakSanitizer không chạy', methodology_evidence),
             ('Lượt sanitizer mới results/sanitizer-20261018-093549', json_run_evidence),
             ('v = variant;', guard_evidence), ('Kiểm tra đồ thị độc lập', kripke_evidence),
             ('Bốn nhóm kiểm tra Ch2 đạt', allocation_evidence),
             ('Nguồn: results/leak-', leak_evidence), ('CFG GUI và Clang', ast_evidence),
             ('Nguồn: results/comparison-', comparison_evidence)]
    for prefix, action in rules:
        if title.startswith(prefix) and prefix not in HOOKS:
            HOOKS.add(prefix); action()
            if action is allocation_evidence: static_limitations()


def footer(c, doc):
    if doc.page == 1: return
    c.setFont('TimesVN',9)
    c.drawString(57,28,'An toàn phần mềm | Mô hình tồn kho badminton | 21/10/2026')
    c.drawRightString(538,28,str(doc.page))


def initialize():
    STORY.extend([Spacer(1,700), PageBreak()])
    STORY.append(Paragraph('MỤC LỤC', STYLES['HeadVN']))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle('toc'+str(i), fontName='TimesVN-Bold' if i<2 else 'TimesVN',
                       fontSize=11 if i==0 else 10, leading=12, leftIndent=i*16,
                       firstLineIndent=0, spaceBefore=3 if i==0 else 1) for i in range(3)]
    toc.dotsMinLevel = 0
    STORY.extend([toc, PageBreak()])
    p('1. Lời mở đầu','HeadVN',False)


def execute_body():
    tree = ast.parse(SOURCE)
    nodes = [node for node in tree.body if 91 <= node.lineno < 274
             and not 237 <= node.lineno <= 241 and node.lineno not in (260, 261)]
    NS.update(p=p, heading=heading, screenshot=lambda *args: None)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'existing-report-body','exec'),NS)


def finish():
    body = OUT/'body-with-toc.pdf'
    doc = Report(str(body),pagesize=(595.28,841.89),leftMargin=57,rightMargin=57,
                 topMargin=57,bottomMargin=52,title='Báo cáo An toàn phần mềm',author='')
    doc.multiBuild(STORY,onFirstPage=footer,onLaterPages=footer)
    result, original = PdfReader(body), PdfReader(OLD)
    writer = PdfWriter()
    writer.clone_document_from_reader(result)
    writer.pages[0].merge_page(original.pages[0])
    writer.write(TARGET)
    (OUT/'figures.json').write_text(json.dumps(FIGURES,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PDF:',TARGET,'pages:',len(writer.pages),'figures:',len(FIGURES))


if __name__ == '__main__':
    initialize(); execute_body(); finish()
