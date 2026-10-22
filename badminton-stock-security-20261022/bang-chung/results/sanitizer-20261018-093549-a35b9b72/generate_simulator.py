"""Sinh nghiệp vụ C từ stock_spec.json; giữ adapter nhị phân của mẫu C hiện có."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = HERE / 'stock_spec.json'
REFERENCE_BACKEND = HERE / 'reference_backend'
FIELDS = {'available', 'reserved', 'va', 'vr', 'state', 'variant'}
OPERATORS = {ast.Add: '+', ast.Sub: '-', ast.And: '&&', ast.Or: '||',
             ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=',
             ast.Eq: '==', ast.NotEq: '!='}


def expression(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        if not -2147483648 <= node.value <= 2147483647:
            raise ValueError('Hằng số nằm ngoài int32')
        return f'INT64_C({node.value})'
    if isinstance(node, ast.Name) and node.id in FIELDS | {'q', 'restore'}:
        value = f's->{node.id}' if node.id in FIELDS else node.id
        return f'((int64_t){value})'
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return f'(!{expression(node.operand)})'
    if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub):
        return f'({expression(node.left)} {OPERATORS[type(node.op)]} {expression(node.right)})'
    if isinstance(node, ast.BoolOp) and type(node.op) in OPERATORS:
        return '(' + f' {OPERATORS[type(node.op)]} '.join(map(expression, node.values)) + ')'
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in OPERATORS:
        return f'({expression(node.left)} {OPERATORS[type(node.ops[0])]} {expression(node.comparators[0])})'
    raise ValueError('Biểu thức ngoài tập con an toàn được hỗ trợ')


def translate(text):
    if not isinstance(text, str) or len(text) > 500:
        raise ValueError('Biểu thức quá dài hoặc sai kiểu')
    node = ast.parse(text, mode='eval')
    if len(list(ast.walk(node))) > 80:
        raise ValueError('Biểu thức quá phức tạp')
    return expression(node.body)


def statement(rule):
    if 'return' in rule:
        if type(rule['return']) is not int or not 0 <= rule['return'] <= 7:
            raise ValueError('Mã kết quả không hợp lệ')
        code = f"return {rule['return']};"
    else:
        field = rule['set']
        if field not in FIELDS - {'variant'}:
            raise ValueError('Trường cập nhật không hợp lệ')
        value = translate(rule['value'])
        mode = rule.get('mode', 'assign')
        if mode not in ('assign', 'java_add'):
            raise ValueError('Chế độ cập nhật không hợp lệ')
        value = f'java_add(s->{field}, (int32_t){value})' if mode == 'java_add' else value
        code = f's->{field} = (int32_t)({value});'
    return f"    if ({translate(rule['when'])}) {{ {code} }}" if 'when' in rule else '    ' + code


def load_spec(path=DEFAULT_SPEC, check_backend=True):
    spec = json.loads(Path(path).read_text(encoding='utf-8'))
    if spec.get('version') != 1 or set(spec['operations']) != {'reserve', 'settle'}:
        raise ValueError('Phiên bản hoặc tập phép toán không được hỗ trợ')
    backend = REFERENCE_BACKEND
    for name, expected in spec['backend_sha256'].items():
        if name not in ('OrderService.java', 'ProductVariantService.java'):
            raise ValueError('Tên service không hợp lệ')
        if check_backend and hashlib.sha256((backend / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Bản tham chiếu {name} đã đổi: cần đối chiếu lại đặc tả')
    for rules in spec['operations'].values():
        if not 1 <= len(rules) <= 50:
            raise ValueError('Số quy tắc không hợp lệ')
        for rule in rules:
            statement(rule)
    return spec


def generate(spec):
    adapter_path = HERE / 'reference_stock_simulator.c'
    adapter = (adapter_path if adapter_path.exists() else HERE / 'stock_simulator.c').read_text(encoding='utf-8')
    prefix = adapter[:adapter.index('static int reserve(')]
    suffix = adapter[adapter.index('static int simulate('):]
    functions = []
    for name, rules in spec['operations'].items():
        parameters = 'Stock *s, int32_t q' + (', int restore' if name == 'settle' else '')
        body = '\n'.join(statement(rule) for rule in rules)
        functions.append(f'static int {name}({parameters}) {{\n{body}\n    return 0;\n}}\n')
    digest = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    return f'/* Generated from specification SHA256 {digest}. */\n' + prefix + '\n'.join(functions) + '\n' + suffix


def guard_expression(node):
    names = {'q':'quantity','va':'variant_available','vr':'variant_reserved'}
    if isinstance(node,ast.Constant) and type(node.value) is int:
        return str(node.value)
    if isinstance(node,ast.Name) and node.id in {'available','reserved','q','variant','va','vr'}:
        return names.get(node.id,node.id)
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):
        return f'(!{guard_boolean(node.operand)})'
    if isinstance(node,ast.BoolOp) and type(node.op) in OPERATORS:
        return '('+f' {OPERATORS[type(node.op)]} '.join(map(guard_boolean,node.values))+')'
    if isinstance(node,ast.Compare) and len(node.ops)==1 and type(node.ops[0]) in OPERATORS:
        return guard_comparison(node)
    raise ValueError('Điều kiện SMT chứa phép toán chưa được hỗ trợ an toàn')


def guard_boolean(node):
    value = guard_expression(node)
    if isinstance(node,(ast.Compare,ast.BoolOp)) or (
        isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not)):
        return value
    return f'({value} != 0)'


def guard_comparison(node):
    left, right = node.left, node.comparators[0]
    if isinstance(left,ast.BinOp):
        if (ast.unparse(left) not in ('reserved + q','vr + q') or
            not isinstance(node.ops[0],ast.Gt) or not isinstance(right,ast.Constant) or
            right.value != 2147483647):
            raise ValueError('Chưa hỗ trợ chuẩn hóa phép toán SMT này')
        return f'({guard_expression(left.left)} > (2147483647 - quantity))'
    return f'({guard_expression(left)} {OPERATORS[type(node.ops[0])]} {guard_expression(right)})'


def guard_rules(spec):
    rules = spec['operations']['reserve']
    first = ast.parse(rules[0].get('when',''),mode='eval').body
    if not isinstance(first,ast.BoolOp) or not isinstance(first.op,ast.Or) or len(first.values)!=2:
        raise ValueError('Guard SMT cần kiểm tra miền quantity ở đầu')
    low, high = first.values
    if ast.dump(low) != ast.dump(ast.parse('q < 1',mode='eval').body):
        raise ValueError('Guard SMT cần quantity dương trước phép trừ giới hạn')
    if (not isinstance(high,ast.Compare) or ast.unparse(high.left)!='q' or
        len(high.ops)!=1 or not isinstance(high.ops[0],ast.Gt) or
        not isinstance(high.comparators[0],ast.Constant) or type(high.comparators[0].value) is not int or
        not 1<=high.comparators[0].value<=2147483647):
        raise ValueError('Giới hạn trên quantity chưa được hỗ trợ')
    guards = []
    for rule in rules:
        if 'set' in rule: break
        if 'return' not in rule or 'when' not in rule: raise ValueError('Guard không có điều kiện')
        statement(rule)
        guards.append(rule)
    if any('return' in rule for rule in rules[len(guards):]):
        raise ValueError('Không được tách guard khi có return sau cập nhật trạng thái')
    return guards


def generate_guard(spec):
    parameters = 'int available, int reserved, int quantity, int variant, int variant_available, int variant_reserved'
    lines = []
    for rule in guard_rules(spec):
        condition = guard_boolean(ast.parse(rule['when'],mode='eval').body)
        lines.append(f"    if ({condition}) return {rule['return']};")
    return (f'int stock_reserve_guard({parameters}) {{\n'+'\n'.join(lines)+
            '\n    return 0;\n}\n')


def generate_json(spec, library=False):
    contract = spec['json_transport']
    if contract['max_bytes'] != 16384 or contract['max_records'] != 100 or contract['number_token_bytes'] != 64:
        raise ValueError('Giới hạn JSON chưa được adapter này hỗ trợ')
    dto = REFERENCE_BACKEND / 'OrderItemRequest.java'
    if hashlib.sha256(dto.read_bytes()).hexdigest() != contract['dto_sha256']:
        raise ValueError('Backend OrderItemRequest đã đổi: cần đối chiếu lại JSON')
    source = generate(spec).split('static int simulate(')[0]
    adapter = (HERE / 'stock_json_adapter.c').read_text(encoding='utf-8')
    if library: adapter = adapter.split('#ifndef STOCK_JSON_LIBRARY')[0]
    return source + adapter + '\n' + generate_guard(spec)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--module', choices=['stock'], default='stock')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--json', action='store_true', help='Sinh target JSON tồn kho')
    parser.add_argument('--library', action='store_true', help='Bỏ main để wrap hàm C trong SecLabFramework')
    args = parser.parse_args()
    spec = load_spec(args.spec or DEFAULT_SPEC)
    source = generate_json(spec, args.library) if args.json else generate(spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
