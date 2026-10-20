#include <stdlib.h>
#include <string.h>

static void *volatile block;

static void allocate_block(void) {
    unsigned char *memory = malloc(123);
    if (!memory) exit(2);
    memory[0] = 42;
    block = memory;
}

int main(int argc, char **argv) {
    allocate_block();
    if (argc == 2 && strcmp(argv[1], "clean") == 0) free(block);
    block = NULL;
    return 0;
}
