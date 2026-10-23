/* Công dụng: Include sl_target.c và xuất các hàm sl_wrap_... để Python gọi mã C qua DLL; shim sinh tự động, chú thích có thể bị thay khi wrap lại. */
/* Tệp shim SINH TỰ ĐỘNG bởi sec_lab_framework (core/c_wrapper.py) — KHÔNG sửa tay.
   Nó #include mã nguồn gốc rồi xuất các hàm sl_wrap_<tên> có C linkage để Python (ctypes)
   gọi được — kể cả hàm `static` và `main` (được đổi tên thành sl_orig_main). */
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
#define SL_EXTC extern "C"
#else
#define SL_EXTC
#endif
#ifdef _WIN32
#define SL_EXPORT SL_EXTC __declspec(dllexport)
#else
#define SL_EXPORT SL_EXTC __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" { unsigned char sl_cov_map[1]; }
#else
unsigned char sl_cov_map[1];
#endif
#define SL_HIT(n) (sl_cov_map[(n)] = 1)
#define main sl_orig_main
#include "sl_target.c"
#undef main
SL_EXPORT unsigned char *sl_cov_ptr(void) { return sl_cov_map; }
SL_EXPORT int sl_cov_size(void) { return 1; }
SL_EXPORT void sl_cov_reset(void) { for (int i = 0; i < 1; i++) sl_cov_map[i] = 0; }

SL_EXPORT int32_t sl_wrap_java_add(int32_t a, int32_t b) {
    return java_add(a, b);
}
SL_EXPORT int sl_wrap_jsonHex(int value) {
    return jsonHex(value);
}
SL_EXPORT int sl_wrap_jsonExponent(const char * text, size_t size, size_t * pos, int * exponent) {
    return jsonExponent(text, size, pos, exponent);
}
SL_EXPORT int sl_wrap_jsonInteger(const char * text, size_t size, int32_t * output) {
    return jsonInteger(text, size, output);
}
SL_EXPORT int sl_wrap_jsonField(const char * key) {
    return jsonField(key);
}
SL_EXPORT int sl_wrap_stock_json(const char * json) {
    return stock_json(json);
}
SL_EXPORT int sl_wrap_stock_json_case(int available, int reserved, int quantity, int action) {
    return stock_json_case(available, reserved, quantity, action);
}
SL_EXPORT int sl_wrap_stock_reserve_guard(int available, int reserved, int quantity, int variant, int variant_available, int variant_reserved) {
    return stock_reserve_guard(available, reserved, quantity, variant, variant_available, variant_reserved);
}
