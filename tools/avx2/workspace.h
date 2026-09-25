#ifndef BRIDCT_WIDE8_WORKSPACE_H
#define BRIDCT_WIDE8_WORKSPACE_H
#include <stddef.h>
static size_t wide8_axis_slots(int n)
{
    switch (n) {
    case 8: return 5;
    case 16: return 9;
    case 32: return 36;
    case 64: return 87;
    case 128: return 224;
    case 256: return 527;
    case 512: return 1232;
    case 1024: return 2799;
    default: return 0;
    }
}
static size_t wide8_workspace_count(int h, int w, int pad)
{
    size_t hs = wide8_axis_slots(h), ws = wide8_axis_slots(w);
    if (!hs || !ws || (pad != 0 && pad != 4)) return 0;
    size_t vectors = 2*hs > 2*(size_t)w+2*ws ? 2*hs : 2*(size_t)w+2*ws;
    return 2*(size_t)h*((size_t)w+(size_t)pad) + 7 + 8*vectors;
}
#endif
