"""Test case SINH TỰ ĐỘNG từ fuzzing (sec_lab_framework v25) cho `stock_json_case` (C). Chế độ: characterization.
Mỗi test ghi rõ kỹ thuật fuzzing sinh ra nó."""
import math
import pytest
NAN = float('nan')   # dung so sanh nan: math.isnan
import target_wrap as w


def test_stock_json_case_boundary_1():
    # kỹ thuật: Biên / giá trị đặc biệt — +279 phần tử coverage mới
    r = w.call_isolated('stock_json_case', 1, 1, 1, 1)
    assert r["status"] == "ok"
    assert r["ret"] == 0

def test_stock_json_case_boundary_2():
    # kỹ thuật: Biên / giá trị đặc biệt — +12 phần tử coverage mới
    r = w.call_isolated('stock_json_case', 0, 1, 1, 1)
    assert r["status"] == "ok"
    assert r["ret"] == 2

def test_stock_json_case_boundary_3():
    # kỹ thuật: Biên / giá trị đặc biệt — +5 phần tử coverage mới
    r = w.call_isolated('stock_json_case', 100, 1, 1, 1)
    assert r["status"] == "ok"
    assert r["ret"] == 0

def test_stock_json_case_boundary_4():
    # kỹ thuật: Biên / giá trị đặc biệt — +4 phần tử coverage mới
    r = w.call_isolated('stock_json_case', -2147483648, 1, 1, 1)
    assert r["status"] == "ok"
    assert r["ret"] == 104

def test_stock_json_case_blackbox_5():
    # kỹ thuật: Black-box (ngẫu nhiên) — +5 phần tử coverage mới
    r = w.call_isolated('stock_json_case', -254551521, 102, 31, 43)
    assert r["status"] == "ok"
    assert r["ret"] == 100

def test_stock_json_case_blackbox_6():
    # kỹ thuật: Black-box (ngẫu nhiên) — +2 phần tử coverage mới
    r = w.call_isolated('stock_json_case', 2147483647, 10, -2811, 2)
    assert r["status"] == "ok"
    assert r["ret"] == 103

def test_stock_json_case_blackbox_7():
    # kỹ thuật: Black-box (ngẫu nhiên) — +4 phần tử coverage mới
    r = w.call_isolated('stock_json_case', 129, 190, 45, 3)
    assert r["status"] == "ok"
    assert r["ret"] == 0

def test_stock_json_case_blackbox_8():
    # kỹ thuật: Black-box (ngẫu nhiên) — +10 phần tử coverage mới
    r = w.call_isolated('stock_json_case', 119, 91, 48, 14)
    assert r["status"] == "ok"
    assert r["ret"] == 0

def test_stock_json_case_mutation_9():
    # kỹ thuật: Mutation (đột biến seed) — kết quả đại diện
    r = w.call_isolated('stock_json_case', 8194, 1, 1, 2)
    assert r["status"] == "ok"
    assert r["ret"] == 0

def test_stock_json_case_mutation_10():
    # kỹ thuật: Mutation (đột biến seed) — kết quả đại diện
    r = w.call_isolated('stock_json_case', 2, -1, 2, 1)
    assert r["status"] == "ok"
    assert r["ret"] == 104

def test_stock_json_case_mutation_11():
    # kỹ thuật: Mutation (đột biến seed) — kết quả đại diện
    r = w.call_isolated('stock_json_case', 2, 1, 0, 1)
    assert r["status"] == "ok"
    assert r["ret"] == 103

def test_stock_json_case_coverage_12():
    # kỹ thuật: Coverage-guided — +5 coverage mới
    r = w.call_isolated('stock_json_case', 2, 1, 1, 63)
    assert r["status"] == "ok"
    assert r["ret"] == 100

def test_stock_json_case_coverage_13():
    # kỹ thuật: Coverage-guided — +4 coverage mới
    r = w.call_isolated('stock_json_case', 1, 0, -1, 1)
    assert r["status"] == "ok"
    assert r["ret"] == 103
