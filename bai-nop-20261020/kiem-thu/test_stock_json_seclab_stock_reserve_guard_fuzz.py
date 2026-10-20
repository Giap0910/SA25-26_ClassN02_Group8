"""Test case SINH TỰ ĐỘNG từ fuzzing (sec_lab_framework v25) cho `stock_reserve_guard` (C). Chế độ: characterization.
Mỗi test ghi rõ kỹ thuật fuzzing sinh ra nó."""
import math
import pytest
NAN = float('nan')   # dung so sanh nan: math.isnan
import stock_json_seclab_wrap as w


def test_stock_reserve_guard_concolic_1():
    # kỹ thuật: Concolic / white-box (SMT + hằng số) — +4 phần tử coverage mới
    r = w.call_isolated('stock_reserve_guard', 0, 0, 0, 0, 0, 0)
    assert r["status"] == "ok"
    assert r["ret"] == 1

def test_stock_reserve_guard_concolic_2():
    # kỹ thuật: Concolic / white-box (SMT + hằng số) — +4 phần tử coverage mới
    r = w.call_isolated('stock_reserve_guard', 0, 0, 1, 0, 0, 0)
    assert r["status"] == "ok"
    assert r["ret"] == 2

def test_stock_reserve_guard_concolic_3():
    # kỹ thuật: Concolic / white-box (SMT + hằng số) — +4 phần tử coverage mới
    r = w.call_isolated('stock_reserve_guard', 1, 2147483647, 1, 0, 0, 0)
    assert r["status"] == "ok"
    assert r["ret"] == 3

def test_stock_reserve_guard_concolic_4():
    # kỹ thuật: Concolic / white-box (SMT + hằng số) — +4 phần tử coverage mới
    r = w.call_isolated('stock_reserve_guard', 1, 2147483646, 1, 1, 0, 0)
    assert r["status"] == "ok"
    assert r["ret"] == 4

def test_stock_reserve_guard_concolic_5():
    # kỹ thuật: Concolic / white-box (SMT + hằng số) — +4 phần tử coverage mới
    r = w.call_isolated('stock_reserve_guard', 1, 2147483646, 1, 1, 1, 2147483647)
    assert r["status"] == "ok"
    assert r["ret"] == 5

def test_stock_reserve_guard_concolic_6():
    # kỹ thuật: Concolic / white-box (SMT + hằng số) — +2 phần tử coverage mới
    r = w.call_isolated('stock_reserve_guard', 1, 2147483646, 1, 0, 0, 2147483647)
    assert r["status"] == "ok"
    assert r["ret"] == 0
