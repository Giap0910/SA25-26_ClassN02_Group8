/* Audit harness: original source is included unchanged. */
#include "../../stock_json_seclab.c"

int main(int argc, char **argv) {
    char text[66];
    int32_t output = -1;
    size_t length = argc > 1 ? (size_t)strtoul(argv[1], NULL, 10) : 65;
    if (length > 65) return 64;
    memset(text, '1', length);
    text[length] = '\0';
    int result = jsonInteger(text, length, &output);
    printf("length=%zu result=%d output=%" PRId32 "\n", length, result, output);
    return 0;
}
