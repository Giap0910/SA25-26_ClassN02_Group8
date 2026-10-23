
#include "after-stock_json_seclab.c"
#include <assert.h>

static int checkValid(void) {
    const char *texts[] = {"0", "-1", "2147483647", "-2147483648", "2.0", "20e-1"};
    int32_t expected[] = {0, -1, INT32_MAX, INT32_MIN, 2, 2};
    for (size_t i = 0; i < 6; ++i) {
        int32_t value = 77;
        assert(jsonInteger(texts[i], strlen(texts[i]), &value) == 1);
        assert(value == expected[i]);
    }
    char zeros[65];
    memset(zeros, '0', 64); zeros[63] = '1'; zeros[64] = 0;
    int32_t value = 77;
    assert(jsonInteger(zeros, 64, &value) == 1 && value == 1);
    assert(jsonInteger("2147483648", 10, &value) == 0);
    assert(jsonInteger("1.5", 3, &value) == 0);
    return 0;
}

static int checkBounds(void) {
    int32_t value = 77;
    assert(jsonInteger(NULL, 1, &value) == 0);
    assert(jsonInteger("", 0, &value) == 0);
    assert(jsonInteger("1", 1, NULL) == 0);
    assert(jsonInteger("1", 65, &value) == 0);
    assert(value == 77);
    return 0;
}

static int checkPublic(void) {
    char text[512], number[66];
    memset(number, '1', 65); number[65] = 0;
    snprintf(text, sizeof(text), "{\"available\":10,\"reserved\":0,"
        "\"variant_available\":10,\"variant_reserved\":0,\"action\":0,"
        "\"items\":[{\"quantity\":%s}]}", number);
    assert(stock_json(text) == 100);
    assert(stock_json_case(10, 0, 2, 0) == 0);
    assert(stock_json_case(0, 0, 1, 0) == 2);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    if (strcmp(argv[1], "valid") == 0) return checkValid();
    if (strcmp(argv[1], "bounds") == 0) return checkBounds();
    if (strcmp(argv[1], "public") == 0) return checkPublic();
    char text[66]; memset(text, '1', 65); text[65] = 0;
    int32_t value = 77;
    int result = jsonInteger(text, 65, &value);
    printf("result=%d output=%" PRId32 "\n", result, value);
    return result == 0 && value == 77 ? 0 : 1;
}
