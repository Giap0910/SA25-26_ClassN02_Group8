#define STOCK_JSON_LIBRARY
#include "C:/Project/Badminton_Stock_Security/results/patch-audit-20261022/after-stock_json_seclab.c"
int testInput(const unsigned char *data, size_t size) {
    if (!size || size > 256) return 0;
    if (size > 1 && data[0] == '0') return 0;
    for (size_t i = 0; i < size; ++i)
        if (data[i] < '0' || data[i] > '9') return 0;
    char *text = malloc(size + 1);
    if (!text) return 0;
    memcpy(text, data, size); text[size] = 0;
    int32_t value = 77;
    volatile int result = jsonInteger(text, size, &value);
    (void)result;
    free(text);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    FILE *file = fopen(argv[1], "rb");
    if (!file) return 66;
    unsigned char data[257];
    size_t size = fread(data, 1, sizeof data, file);
    fclose(file);
    return testInput(data, size);
}
