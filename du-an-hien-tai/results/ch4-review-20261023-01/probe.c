/* Ca cố định bổ trợ Ch4; giữ nguyên nguồn đích và tách khỏi coverage JSON CLI. */
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
static int failAllocation, liveBlocks;
static void *reviewCalloc(size_t count, size_t size) {
    if (failAllocation) return NULL;
    void *pointer = calloc(count, size);
    if (pointer) ++liveBlocks;
    return pointer;
}
static void reviewFree(void *pointer) {
    if (pointer) --liveBlocks;
    free(pointer);
}
#define calloc reviewCalloc
#define free reviewFree
#define STOCK_JSON_LIBRARY
#include "stock_json_target.c"
#undef calloc
#undef free

static void integerBounds(void) {
    int32_t output = 77;
    char digits[66];
    memset(digits, '1', 65); digits[65] = '\0';
    assert(jsonInteger(NULL, 1, &output) == 0);
    assert(jsonInteger("1", 1, NULL) == 0);
    assert(jsonInteger("", 0, &output) == 0);
    assert(jsonInteger(digits, 65, &output) == 0);
    assert(output == 77);
    memset(digits, '0', 63); digits[63] = '1';
    assert(jsonInteger(digits, 64, &output) == 1 && output == 1);
}

static void entryPaths(void) {
    Stock output = {0};
    assert(jsonEvaluate(NULL, 0, &output) == 101);
    assert(stock_json(NULL) == 101);
    assert(stock_json("{}") == 100 && liveBlocks == 0);
    for (int action = 0; action < 16; ++action)
        assert(stock_json_case(10, 0, 2, action) == 0 && liveBlocks == 0);
    assert(stock_json_case(10, 0, 0, 0) == 103 && liveBlocks == 0);
    assert(stock_json_case(0, 0, 1, 0) == 2 && liveBlocks == 0);
    assert(stock_json_case(10, INT32_MAX, 1, 0) == 3 && liveBlocks == 0);
    failAllocation = 1;
    assert(stock_json_case(10, 0, 2, 0) == 105 && liveBlocks == 0);
    failAllocation = 0;
}

static void lengthPaths(void) {
    char data[STOCK_JSON_MAX_BYTES + 2];
    memset(data, ' ', sizeof data); data[sizeof data - 1] = '\0';
    assert(stock_json(data) == 101);
    data[STOCK_JSON_MAX_BYTES] = '\0';
    assert(stock_json(data) == 100 && liveBlocks == 0);
}

int main(void) {
    integerBounds();
    entryPaths();
    lengthPaths();
    puts("PASS: integer bounds; NULL; 16 actions; domain guards; allocation failure; byte limits; liveBlocks=0");
    return 0;
}
