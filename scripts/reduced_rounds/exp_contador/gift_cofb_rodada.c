/*
 * GIFT-COFB com granularidade de UMA rodada, em C, para o Dia 1 do v3.
 *
 * Tradução direta da reimplementação independente em
 * tests/test_crypto_independente.py (GIFT-128 da CHES 2017 + modo COFB da
 * submissão ao NIST), que é a âncora externa do GIFT-COFB no projeto. O
 * `opt32` vendorizado é fixsliced e só reduz de 5 em 5 rodadas.
 *
 * Restrições deste build (bastam para o experimento): AD vazio ou com
 * comprimento múltiplo de 16, e mensagem com comprimento múltiplo de 16 e não
 * vazia; fora disso devolve -1.
 * GIFT_RODADAS: número de rodadas do cifrador de bloco (1 a 40), tomando as
 * PRIMEIRAS rodadas, como a reimplementação.
 *
 * Estado de 128 bits: lo = bits 0..63, hi = bits 64..127.
 */
#include <stdint.h>
#include <string.h>

#ifndef GIFT_RODADAS
#define GIFT_RODADAS 40
#endif

typedef struct { uint64_t lo, hi; } u128;

static const uint8_t GS[16] = {0x1, 0xA, 0x4, 0xC, 0x6, 0xF, 0x3, 0x9,
                               0x2, 0xD, 0xB, 0x7, 0x5, 0x0, 0x8, 0xE};
static u128 SP[16][256];
static u128 RHO[16][256];
static uint8_t RC[40];
static int pronto = 0;

static void setbit(u128 *x, int i) {
    if (i < 64) x->lo |= 1ull << i; else x->hi |= 1ull << (i - 64);
}
static int getbit(u128 x, int i) {
    return i < 64 ? (int)((x.lo >> i) & 1) : (int)((x.hi >> (i - 64)) & 1);
}
static int p128(int i) {
    return 4 * (i / 16) + 32 * ((3 * ((i % 16) / 4) + (i % 4)) % 4) + (i % 4);
}

static void inicia(void) {
    if (pronto) return;
    for (int k = 0; k < 16; k++)
        for (int v = 0; v < 256; v++) {
            int s = GS[v & 0xF] | (GS[v >> 4] << 4);
            u128 acc = {0, 0};
            for (int t = 0; t < 8; t++) if ((s >> t) & 1) setbit(&acc, p128(8 * k + t));
            SP[k][v] = acc;
            u128 r = {0, 0};
            for (int t = 0; t < 8; t++)
                if ((v >> t) & 1) {
                    int j = k / 4, i = (3 - (k % 4)) * 8 + t;
                    setbit(&r, 4 * i + j);
                }
            RHO[k][v] = r;
        }
    int c = 0;
    for (int r = 0; r < 40; r++) {
        c = ((c << 1) | (((c >> 5) & 1) ^ ((c >> 4) & 1) ^ 1)) & 0x3F;
        RC[r] = (uint8_t)c;
    }
    pronto = 1;
}

static uint16_t ror16(uint16_t x, int n) { return (uint16_t)((x >> n) | (x << (16 - n))); }

static void mascaras(const unsigned char *key, u128 *m, int rodadas) {
    uint16_t k[8];
    for (int i = 0; i < 8; i++)      /* k[i] = (K >> 16i) & 0xFFFF, K big-endian */
        k[i] = (uint16_t)((key[15 - 2 * i - 1] << 8) | key[15 - 2 * i]);
    for (int r = 0; r < rodadas; r++) {
        uint32_t u = ((uint32_t)k[5] << 16) | k[4], v = ((uint32_t)k[1] << 16) | k[0];
        u128 x = {0, 1ull << 63};
        for (int i = 0; i < 32; i++) {
            if ((u >> i) & 1) setbit(&x, 4 * i + 2);
            if ((v >> i) & 1) setbit(&x, 4 * i + 1);
        }
        for (int i = 0; i < 6; i++) if ((RC[r] >> i) & 1) setbit(&x, 4 * i + 3);
        m[r] = x;
        uint16_t n6 = ror16(k[0], 12), n7 = ror16(k[1], 2);
        for (int i = 0; i < 6; i++) k[i] = k[i + 2];
        k[6] = n6; k[7] = n7;
    }
}

static u128 nucleo(u128 b, const u128 *m, int rodadas) {
    for (int r = 0; r < rodadas; r++) {
        u128 o = {0, 0};
        for (int k = 0; k < 16; k++) {
            int v = k < 8 ? (int)((b.lo >> (8 * k)) & 0xFF) : (int)((b.hi >> (8 * (k - 8))) & 0xFF);
            o.lo |= SP[k][v].lo; o.hi |= SP[k][v].hi;
        }
        b.lo = o.lo ^ m[r].lo; b.hi = o.hi ^ m[r].hi;
    }
    return b;
}

static u128 rho_in(const unsigned char *x) {
    u128 b = {0, 0};
    for (int k = 0; k < 16; k++) { b.lo |= RHO[k][x[k]].lo; b.hi |= RHO[k][x[k]].hi; }
    return b;
}
static void rho_out(u128 b, unsigned char *out) {
    for (int j = 0; j < 4; j++) {
        uint32_t w = 0;
        for (int i = 0; i < 32; i++) w |= (uint32_t)getbit(b, 4 * i + j) << i;
        out[4 * j] = (unsigned char)(w >> 24); out[4 * j + 1] = (unsigned char)(w >> 16);
        out[4 * j + 2] = (unsigned char)(w >> 8); out[4 * j + 3] = (unsigned char)w;
    }
}

static void e(const u128 *m, const unsigned char *in, unsigned char *out) {
    rho_out(nucleo(rho_in(in), m, GIFT_RODADAS), out);
}

static uint64_t dbl(uint64_t x) { return (x >> 63) ? ((x << 1) ^ 0x1B) : (x << 1); }
static uint64_t triplo(uint64_t x) { return dbl(x) ^ x; }

/* fb = pad(blk) xor G(y) xor (ell || 0^64); blk de 16 bytes, ou vazio (n = 0) */
static void fb(const unsigned char *y, const unsigned char *blk, int n, uint64_t ell, unsigned char *out) {
    unsigned char p[16] = {0}, g[16];
    if (n == 16) memcpy(p, blk, 16); else { memcpy(p, blk, (size_t)n); p[n] = 0x80; }
    uint64_t y1 = 0;
    for (int i = 0; i < 8; i++) y1 = (y1 << 8) | y[i];
    y1 = (y1 << 1) | (y1 >> 63);
    memcpy(g, y + 8, 8);
    for (int i = 0; i < 8; i++) g[8 + i] = (unsigned char)(y1 >> (56 - 8 * i));
    for (int i = 0; i < 16; i++) out[i] = p[i] ^ g[i];
    for (int i = 0; i < 8; i++) out[i] ^= (unsigned char)(ell >> (56 - 8 * i));
}

int crypto_aead_encrypt(unsigned char *c, unsigned long long *clen,
                        const unsigned char *mp, unsigned long long mlen,
                        const unsigned char *ad, unsigned long long adlen,
                        const unsigned char *nsec, const unsigned char *npub,
                        const unsigned char *k) {
    (void)nsec;
    if (adlen % 16 || mlen == 0 || mlen % 16) return -1;
    inicia();
    u128 m[40];
    mascaras(k, m, GIFT_RODADAS);
    unsigned char y[16], t[16];
    e(m, npub, y);
    uint64_t ell = 0;
    for (int i = 0; i < 8; i++) ell = (ell << 8) | y[i];
    if (adlen == 0) {
        /* AD vazio vira um bloco de padding: 1 + [incompleto] + 2*[M vazio] = 2 triplos */
        ell = triplo(triplo(ell));
        fb(y, 0, 0, ell, t); e(m, t, y);
    } else {
        unsigned long long na = adlen / 16;
        for (unsigned long long b = 0; b + 1 < na; b++) {
            ell = dbl(ell); fb(y, ad + 16 * b, 16, ell, t); e(m, t, y);
        }
        ell = triplo(ell);           /* último bloco de AD completo, M não vazio */
        fb(y, ad + 16 * (na - 1), 16, ell, t); e(m, t, y);
    }
    unsigned long long nb = mlen / 16;
    for (unsigned long long b = 0; b < nb; b++) {
        const unsigned char *blk = mp + 16 * b;
        for (int i = 0; i < 16; i++) c[16 * b + i] = blk[i] ^ y[i];
        ell = (b + 1 < nb) ? dbl(ell) : triplo(ell);
        fb(y, blk, 16, ell, t); e(m, t, y);
    }
    memcpy(c + mlen, y, 16);
    *clen = mlen + 16;
    return 0;
}
