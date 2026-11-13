/* Test-only adapter: keep SGU layout and per-sample calls on the C side. */
#include <stdlib.h>
#include "sgu.h"

struct TestChip {
    struct SGU core;
    int8_t pcm[SGU_PCM_BANK_SIZE];
};
struct TestChip *test_create(void) {
    struct TestChip *chip = calloc(1, sizeof(*chip));
    if (chip) SGU_Init(&chip->core, chip->pcm, sizeof(chip->pcm));
    return chip;
}
void test_destroy(struct TestChip *chip) { free(chip); }
void test_reset(struct TestChip *chip) { SGU_Reset(&chip->core); }
void test_write(struct TestChip *chip, unsigned address, unsigned value) {
    SGU_Write(&chip->core, address, value);
}
unsigned test_read(struct TestChip *chip, unsigned channel, unsigned reg) {
    return SGU_RegRead(&chip->core, channel, reg);
}
void test_pcm(struct TestChip *chip, unsigned address, int value) {
    chip->pcm[address] = value;
}
unsigned test_flags(struct TestChip *chip) { return SGU_GetFlags(&chip->core); }
void test_render(struct TestChip *chip, unsigned count, unsigned channel,
                 int split, int32_t *output) {
    for (unsigned i = 0; i < count; ++i) {
        int32_t l = 0, r = 0;
        if (split < 0) {
            SGU_NextSample(&chip->core, &l, &r);
        } else {
            int32_t al = 0, ar = 0, bl = 0, br = 0;
            SGU_NextSample_Setup(&chip->core);
            SGU_NextSample_Channels(&chip->core, 0, split, &al, &ar);
            SGU_NextSample_Channels(&chip->core, split, SGU_CHNS, &bl, &br);
            SGU_NextSample_Finalize(&chip->core, (int64_t)al + bl,
                                   (int64_t)ar + br, &l, &r);
        }
        output[4*i] = l;
        output[4*i+1] = r;
        output[4*i+2] = chip->core.src[channel];
        output[4*i+3] = chip->core.post[channel];
    }
}
