#define main stock_cli_main
#include "stock_json_target.c"
#undef main

int main(int argc, char **argv) {
    if (argc < 2) return 64;
    for (int round = 0; round < 10; ++round) {
        for (int index = 1; index < argc; ++index) {
            char *call_args[] = {argv[0], argv[index]};
            int result = stock_cli_main(2, call_args);
            if (result) return result;
        }
    }
    return 0;
}
