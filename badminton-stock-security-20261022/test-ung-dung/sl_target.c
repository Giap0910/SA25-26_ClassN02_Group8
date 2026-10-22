/* Công dụng: Mã C đầy đủ để nạp ứng dụng thầy, fuzz JSON qua stock_json/stock_json_case và kiểm tra điều kiện bằng stock_reserve_guard; phần sinh tự động có thể bị thay khi sinh lại. */
/* Generated from specification SHA256 dfe49108182538c7b267d2e263ad5292bf8cfce595ecbf84ec5ae5c024fc1295. */
/* Công dụng: Mô hình C giữ hàng, hoàn khi hủy và tất toán tồn kho; đọc input nhị phân BDMN 28 byte và xuất kết quả để runner đối chiếu oracle. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <limits.h>

typedef struct { int32_t available, reserved, va, vr, quantity; uint32_t action; } Input;
typedef struct { int32_t available, reserved, va, vr; int state, variant; } Stock;

static int32_t java_add(int32_t a, int32_t b) {
    int64_t sum = (int64_t)a + b;
    if (sum > INT32_MAX) sum -= INT64_C(4294967296);
    if (sum < INT32_MIN) sum += INT64_C(4294967296);
    return (int32_t)sum;
}

static int reserve(Stock *s, int32_t q) {
    if (((((int64_t)q) < INT64_C(1)) || (((int64_t)q) > INT64_C(100)))) { return 1; }
    if ((((int64_t)s->available) < ((int64_t)q))) { return 2; }
    if (((((int64_t)s->reserved) + ((int64_t)q)) > INT64_C(2147483647))) { return 3; }
    if ((((int64_t)s->variant) && (((int64_t)s->va) < ((int64_t)q)))) { return 4; }
    if ((((int64_t)s->variant) && ((((int64_t)s->vr) + ((int64_t)q)) > INT64_C(2147483647)))) { return 5; }
    s->available = (int32_t)((((int64_t)s->available) - ((int64_t)q)));
    s->reserved = (int32_t)((((int64_t)s->reserved) + ((int64_t)q)));
    if (((int64_t)s->variant)) { s->va = (int32_t)((((int64_t)s->va) - ((int64_t)q))); }
    if (((int64_t)s->variant)) { s->vr = (int32_t)((((int64_t)s->vr) + ((int64_t)q))); }
    s->state = (int32_t)(INT64_C(1));
    return 0;
}

static int settle(Stock *s, int32_t q, int restore) {
    if ((((int64_t)s->state) != INT64_C(1))) { return 0; }
    if (((((int64_t)s->reserved) < ((int64_t)q)) || (((int64_t)s->variant) && (((int64_t)s->vr) < ((int64_t)q))))) { return 6; }
    if ((((int64_t)restore) && ((int64_t)s->variant) && ((((int64_t)s->va) + ((int64_t)q)) > INT64_C(2147483647)))) { return 7; }
    s->reserved = (int32_t)((((int64_t)s->reserved) - ((int64_t)q)));
    if (((int64_t)restore)) { s->available = (int32_t)(java_add(s->available, (int32_t)((int64_t)q))); }
    if (((int64_t)s->variant)) { s->vr = (int32_t)((((int64_t)s->vr) - ((int64_t)q))); }
    if ((((int64_t)s->variant) && ((int64_t)restore))) { s->va = (int32_t)((((int64_t)s->va) + ((int64_t)q))); }
    if (((int64_t)restore)) { s->state = (int32_t)(INT64_C(2)); }
    if ((!((int64_t)restore))) { s->state = (int32_t)(INT64_C(3)); }
    return 0;
}

/* Công dụng: Đọc và kiểm tra JSON về schema, kiểu, độ dài và số record; cấp phát mảng quantity, gọi nghiệp vụ rồi giải phóng; cần ghép với mã nghiệp vụ để chạy. */
/* Adapter cho fixture JSON ton kho; khong phai endpoint HTTP cua website. */
#define STOCK_JSON_MAX_BYTES 16384
#define STOCK_JSON_MAX_RECORDS 100
typedef struct { const char *data; size_t size, pos; } JsonReader;
typedef struct { Input input; int32_t *quantities; size_t count; } JsonFixture;

static int jsonPeek(JsonReader *reader) {
    return reader->pos < reader->size ? (unsigned char)reader->data[reader->pos] : -1;
}

static void jsonSpace(JsonReader *reader) {
    while (jsonPeek(reader) == ' ' || jsonPeek(reader) == '\t' ||
           jsonPeek(reader) == '\r' || jsonPeek(reader) == '\n') ++reader->pos;
}

static int jsonTake(JsonReader *reader, int expected) {
    jsonSpace(reader);
    if (jsonPeek(reader) != expected) return 0;
    ++reader->pos;
    return 1;
}

static int jsonDigit(JsonReader *reader) {
    return jsonPeek(reader) >= '0' && jsonPeek(reader) <= '9';
}

static int jsonHex(int value) {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
}

static int jsonKeyChar(JsonReader *reader) {
    int value = jsonPeek(reader); ++reader->pos;
    if (value != '\\') return value >= 32 && value < 127 ? value : -1;
    if (jsonPeek(reader) != 'u') return -1;
    ++reader->pos; value = 0;
    for (int i = 0; i < 4; ++i) {
        int digit = jsonHex(jsonPeek(reader));
        if (digit < 0) return -1;
        ++reader->pos; value = value * 16 + digit;
    }
    return value >= 32 && value < 127 ? value : -1;
}

static int jsonKey(JsonReader *reader, char key[32]) {
    size_t length = 0;
    if (!jsonTake(reader, '"')) return 0;
    while (jsonPeek(reader) != '"') {
        if (jsonPeek(reader) < 0 || length >= 31) return 0;
        int value = jsonKeyChar(reader);
        if (value < 0) return 0;
        key[length++] = (char)value;
    }
    ++reader->pos; key[length] = '\0';
    return jsonTake(reader, ':');
}

static int jsonScanNumber(JsonReader *reader, size_t start) {
    if (jsonPeek(reader) == '-') ++reader->pos;
    if (jsonPeek(reader) == '0') ++reader->pos;
    else {
        if (!jsonDigit(reader)) return 0;
        while (jsonDigit(reader)) ++reader->pos;
    }
    if (jsonPeek(reader) == '.') {
        ++reader->pos;
        if (!jsonDigit(reader)) return 0;
        while (jsonDigit(reader)) ++reader->pos;
    }
    if (jsonPeek(reader) == 'e' || jsonPeek(reader) == 'E') {
        ++reader->pos;
        if (jsonPeek(reader) == '+' || jsonPeek(reader) == '-') ++reader->pos;
        if (!jsonDigit(reader)) return 0;
        while (jsonDigit(reader)) ++reader->pos;
    }
    return reader->pos - start <= 64;
}

static int jsonExponent(const char *text, size_t size, size_t *pos, int *exponent) {
    if (*pos == size) return 1;
    ++*pos;
    int negative = text[*pos] == '-';
    if (text[*pos] == '+' || text[*pos] == '-') ++*pos;
    int value = 0;
    while (*pos < size) {
        if (value > 1000) return 0;
        value = value * 10 + text[(*pos)++] - '0';
    }
    *exponent = negative ? -value : value;
    return 1;
}

static int jsonInteger(const char *text, size_t size, int32_t *output) {
    if (!text || !output || size == 0 || size > 64) return 0;
    size_t pos = text[0] == '-', count = 0, first = 0;
    int negative = text[0] == '-', fraction = 0, afterPoint = 0, exponent = 0;
    char digits[64];
    while (pos < size && text[pos] != 'e' && text[pos] != 'E') {
        if (text[pos] == '.') afterPoint = 1;
        else { digits[count++] = text[pos]; fraction += afterPoint; }
        ++pos;
    }
    if (!jsonExponent(text, size, &pos, &exponent)) return 0;
    while (first < count && digits[first] == '0') ++first;
    if (first == count) { *output = 0; return 1; }
    int power = exponent - fraction;
    while (count > first && digits[count-1] == '0') { --count; ++power; }
    if (power < 0 || count-first > 10 || power > 10 || count-first+(size_t)power > 10) return 0;
    uint64_t value = 0;
    for (size_t i = first; i < count; ++i) value = value * 10 + (unsigned)(digits[i]-'0');
    while (power-- > 0) value *= 10;
    if (value > (negative ? UINT64_C(2147483648) : UINT64_C(2147483647))) return 0;
    *output = negative ? (int32_t)(-(int64_t)value) : (int32_t)value;
    return 1;
}

static int jsonNumber(JsonReader *reader, int32_t *output) {
    jsonSpace(reader);
    size_t start = reader->pos;
    if (!jsonScanNumber(reader, start)) return 0;
    return jsonInteger(reader->data + start, reader->pos - start, output);
}

static int jsonRecord(JsonReader *reader, int32_t *quantity) {
    char key[32];
    return jsonTake(reader, '{') && jsonKey(reader, key) && strcmp(key, "quantity") == 0 &&
           jsonNumber(reader, quantity) && jsonTake(reader, '}');
}

static int jsonItems(JsonReader *reader, JsonFixture *fixture) {
    if (!jsonTake(reader, '[')) return 0;
    jsonSpace(reader);
    if (jsonPeek(reader) == ']') { ++reader->pos; return 1; }
    do {
        int32_t quantity;
        if (!jsonRecord(reader, &quantity)) return 0;
        if (fixture->count < STOCK_JSON_MAX_RECORDS) fixture->quantities[fixture->count] = quantity;
        ++fixture->count;
        jsonSpace(reader);
        if (jsonPeek(reader) == ']') { ++reader->pos; return 1; }
    } while (jsonTake(reader, ','));
    return 0;
}

static int jsonField(const char *key) {
    const char *keys[] = {"available", "reserved", "variant_available", "variant_reserved", "action", "items"};
    for (int i = 0; i < 6; ++i) if (strcmp(key, keys[i]) == 0) return i;
    return -1;
}

static int jsonValue(JsonReader *reader, JsonFixture *fixture, int field) {
    int32_t value;
    if (field == 5) return jsonItems(reader, fixture);
    if (!jsonNumber(reader, &value)) return 0;
    if (field == 0) fixture->input.available = value;
    if (field == 1) fixture->input.reserved = value;
    if (field == 2) fixture->input.va = value;
    if (field == 3) fixture->input.vr = value;
    if (field == 4) {
        if (value < 0 || value > 15) return 0;
        fixture->input.action = (uint32_t)value;
    }
    return 1;
}

static int jsonObject(JsonReader *reader, JsonFixture *fixture) {
    unsigned seen = 0;
    if (!jsonTake(reader, '{')) return 0;
    do {
        char key[32];
        if (!jsonKey(reader, key)) return 0;
        int field = jsonField(key);
        if (field < 0 || (seen & (1u << field))) return 0;
        seen |= 1u << field;
        if (!jsonValue(reader, fixture, field)) return 0;
        jsonSpace(reader);
        if (jsonPeek(reader) == '}') {
            ++reader->pos; jsonSpace(reader);
            return seen == 63 && reader->pos == reader->size;
        }
    } while (jsonTake(reader, ','));
    return 0;
}

static int jsonQuantity(JsonFixture *fixture) {
    if (fixture->count == 0 || fixture->count > STOCK_JSON_MAX_RECORDS) return 102;
    int64_t total = 0;
    for (size_t i = 0; i < fixture->count; ++i) {
        if (fixture->quantities[i] < 1 || fixture->quantities[i] > 100) return 103;
        total += fixture->quantities[i];
    }
    if (total > 100) return 103;
    fixture->input.quantity = (int32_t)total;
    return 0;
}

static int jsonStock(Input input, Stock *output) {
    int variant = (input.action & 8u) != 0;
    Stock initial = {input.available, input.reserved, input.va, input.vr, 0, variant};
    *output = initial;
    if (initial.available < 0 || initial.reserved < 0 || (variant &&
        (initial.va < 0 || initial.vr < 0 || initial.va != initial.available || initial.vr != initial.reserved))) return 104;
    int result = reserve(output, input.quantity);
    if (!result && (input.action & 3u)) result = settle(output, input.quantity, (input.action & 3u) == 1);
    if (!result && (input.action & 4u) && (input.action & 3u))
        result = settle(output, input.quantity, (input.action & 3u) == 1);
    if (result) *output = initial;
    if (output->available < 0 || output->reserved < 0 ||
        (variant && (output->va < 0 || output->vr < 0))) return 106;
    return result;
}

static int jsonEvaluate(const char *data, size_t size, Stock *output) {
    if (!data || size > STOCK_JSON_MAX_BYTES) return 101;
    JsonReader reader = {data, size, 0};
    JsonFixture fixture = {{0}, NULL, 0};
    fixture.quantities = calloc(STOCK_JSON_MAX_RECORDS, sizeof(int32_t));
    if (!fixture.quantities) return 105;
    int code = jsonObject(&reader, &fixture) ? jsonQuantity(&fixture) : 100;
    if (!code) code = jsonStock(fixture.input, output);
    free(fixture.quantities);
    return code;
}

int stock_json(const char *json) {
    if (!json) return 101;
    size_t size = 0;
    while (size <= STOCK_JSON_MAX_BYTES && json[size]) ++size;
    Stock output = {0};
    return jsonEvaluate(json, size, &output);
}

int stock_json_case(int available, int reserved, int quantity, int action) {
    char json[256];
    int size = snprintf(json, sizeof json,
        "{\"available\":%d,\"reserved\":%d,\"variant_available\":%d,"
        "\"variant_reserved\":%d,\"action\":%d,\"items\":[{\"quantity\":%d}]}",
        available, reserved, available, reserved, action, quantity);
    if (size < 0 || (size_t)size >= sizeof json) return 101;
    return stock_json(json);
}


int stock_reserve_guard(int available, int reserved, int quantity, int variant, int variant_available, int variant_reserved) {
    if (((quantity < 1) || (quantity > 100))) return 1;
    if ((available < quantity)) return 2;
    if ((reserved > (2147483647 - quantity))) return 3;
    if (((variant != 0) && (variant_available < quantity))) return 4;
    if (((variant != 0) && (variant_reserved > (2147483647 - quantity)))) return 5;
    return 0;
}

