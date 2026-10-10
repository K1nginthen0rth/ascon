/*
 * Laço do Dia 1 do v3 (cota de sinal em escala), inteiro em C.
 *
 * Para cada dispositivo d (chave keys[d]) e cada par j < pares_por_disp:
 *   nonces 2j e 2j+1 em big-endian nos últimos bytes do nonce (contador zero,
 *   a mesma montagem de run_floor.py), claros buf[idx[2*(d*P+j)]] e
 *   buf[idx[2*(d*P+j)+1]] (64 bytes cada), AD vazio. O XOR dos dois
 *   criptogramas (payload de 64 bytes + tag) é acumulado em:
 *     cnt_bits[k]      = quantas vezes o bit k do XOR é 1 (k = byte*8 + j,
 *                        j = 0 é o bit mais alto, como np.unpackbits);
 *     cnt_pares[i*128+l] (i < l < 128) = quantas vezes os bits i e l do bloco
 *                        de 128 bits iniciais são ambos 1.
 * Acumula por fatias de 64 pares em representação bit a bit transposta
 * (uma palavra de 64 bits por posição), com popcount.
 *
 * O cifrador vem do .c do algoritmo, compilado junto com as mesmas macros de
 * rodadas das variantes de build_variant.py.
 */
#include <stdint.h>
#include <string.h>

#ifdef _MSC_VER
#include <intrin.h>
#define POPCNT(x) ((uint64_t)__popcnt64(x))
#else
#define POPCNT(x) ((uint64_t)__builtin_popcountll(x))
#endif

int crypto_aead_encrypt(unsigned char *c, unsigned long long *clen,
                        const unsigned char *m, unsigned long long mlen,
                        const unsigned char *ad, unsigned long long adlen,
                        const unsigned char *nsec, const unsigned char *npub,
                        const unsigned char *k);

#define MSG 64
#define MAXCT (MSG + 16)
#define NPAR 128

/* Layout do contador no nonce (Dia 2):
 *   0 = big-endian nos últimos bytes (v2, padrão);
 *   1 = little-endian nos primeiros bytes;
 *   2 = big-endian terminando no byte 7 (no Ascon, a palavra x3). */
static int layout_g = 0;
static void nonce_be(unsigned char *n, int nb, uint64_t v) {
    memset(n, 0, (size_t)nb);
    if (layout_g == 1) { for (int i = 0; i < 8 && i < nb; i++) n[i] = (unsigned char)(v >> (8 * i)); return; }
    int fim = layout_g == 2 ? 8 : nb;
    for (int i = 0; i < 8 && i < fim; i++) n[fim - 1 - i] = (unsigned char)(v >> (8 * i));
}

static void despeja(const uint64_t *W, int nbits, uint64_t *cnt_bits, uint64_t *cnt_pares) {
    for (int k = 0; k < nbits; k++) cnt_bits[k] += POPCNT(W[k]);
    for (int i = 0; i < NPAR; i++) {
        uint64_t wi = W[i];
        if (!wi) continue;
        for (int l = i + 1; l < NPAR; l++) cnt_pares[i * NPAR + l] += POPCNT(wi & W[l]);
    }
}

int acumula2(const unsigned char *keys, int ndev, int pares_por_disp,
             const unsigned char *buf, const uint32_t *idx,
             int nonce_bytes, int tag_bytes, int layout,
             const unsigned char *cabecalhos, int cab_bytes,
             const unsigned char *ads, int ad_bytes,
             uint64_t *cnt_bits, uint64_t *cnt_pares, uint64_t *M);

int acumula(const unsigned char *keys, int ndev, int pares_por_disp,
            const unsigned char *buf, const uint32_t *idx,
            int nonce_bytes, int tag_bytes,
            uint64_t *cnt_bits, uint64_t *cnt_pares, uint64_t *M) {
    return acumula2(keys, ndev, pares_por_disp, buf, idx, nonce_bytes, tag_bytes, 0,
                    0, 0, 0, 0, cnt_bits, cnt_pares, M);
}

/* Dia 2: cabeçalho constante por dispositivo (cab_bytes primeiros bytes dos
 * dois claros = cabecalhos[d*16 ...]) e AD constante por dispositivo
 * (ads[d*ad_bytes ...]). */
int acumula2(const unsigned char *keys, int ndev, int pares_por_disp,
             const unsigned char *buf, const uint32_t *idx,
             int nonce_bytes, int tag_bytes, int layout,
             const unsigned char *cabecalhos, int cab_bytes,
             const unsigned char *ads, int ad_bytes,
             uint64_t *cnt_bits, uint64_t *cnt_pares, uint64_t *M) {
    unsigned char m1[MSG], m2[MSG];
    layout_g = layout;
    unsigned char n1[32], n2[32], c1[MAXCT + 16], c2[MAXCT + 16];
    unsigned long long l1, l2;
    const int ctb = MSG + tag_bytes, nbits = ctb * 8;
    uint64_t W[MAXCT * 8];
    int fatia = 0;
    memset(W, 0, sizeof(W));
    for (int d = 0; d < ndev; d++) {
        const unsigned char *k = keys + 16 * (size_t)d;
        for (int j = 0; j < pares_por_disp; j++) {
            size_t p = (size_t)d * pares_por_disp + j;
            nonce_be(n1, nonce_bytes, 2ull * j);
            nonce_be(n2, nonce_bytes, 2ull * j + 1);
            memcpy(m1, buf + (size_t)idx[2 * p] * MSG, MSG);
            memcpy(m2, buf + (size_t)idx[2 * p + 1] * MSG, MSG);
            if (cab_bytes) { memcpy(m1, cabecalhos + 16 * (size_t)d, (size_t)cab_bytes);
                             memcpy(m2, cabecalhos + 16 * (size_t)d, (size_t)cab_bytes); }
            const unsigned char *ad = ad_bytes ? ads + (size_t)ad_bytes * d : 0;
            if (crypto_aead_encrypt(c1, &l1, m1, MSG, ad, (unsigned long long)ad_bytes, 0, n1, k)) return -1;
            if (crypto_aead_encrypt(c2, &l2, m2, MSG, ad, (unsigned long long)ad_bytes, 0, n2, k)) return -1;
            if ((int)l1 != ctb || (int)l2 != ctb) return -2;
            uint64_t bit = 1ull << fatia;
            for (int b = 0; b < ctb; b++) {
                unsigned char x = c1[b] ^ c2[b];
                if (!x) continue;
                for (int jj = 0; jj < 8; jj++)
                    if (x & (0x80 >> jj)) W[b * 8 + jj] |= bit;
            }
            if (++fatia == 64) {
                despeja(W, nbits, cnt_bits, cnt_pares);
                memset(W, 0, sizeof(W));
                fatia = 0;
            }
            (*M)++;
        }
    }
    if (fatia) despeja(W, nbits, cnt_bits, cnt_pares);
    return 0;
}

/*
 * Dia 3: cubos passivos sobre os d bits baixos do contador.
 * Cada dispositivo cifra N = 2^D mensagens de 16 bytes (nonces 0..N-1,
 * contador zero, layout como em acumula2). O claro é o cabeçalho do
 * dispositivo (modelo de cabeçalho constante), ou, se cab_por_msg != 0, um
 * cabeçalho diferente por mensagem (controle: a soma dos claros vira uniforme).
 * Para cada d = 1..D, os índices em blocos consecutivos de 2^d formam cubos;
 * S_d = XOR dos 16 primeiros bytes de criptograma do cubo. Acumula
 * cnt_um[d*128 + b] = nº de cubos de dimensão d com bit b de S_d igual a 1,
 * e n_cubos[d].
 */
int cubos(const unsigned char *keys, int ndev, int D, int nonce_bytes, int layout,
          const unsigned char *cabs, int cab_por_msg,
          uint64_t *cnt_um, uint64_t *n_cubos) {
    unsigned char n1[32], c[16 + 32];
    unsigned long long l;
    int N = 1 << D;
    static unsigned char S[1 << 12][16];
    if (D > 12) return -3;
    layout_g = layout;
    for (int d = 0; d < ndev; d++) {
        const unsigned char *k = keys + 16 * (size_t)d;
        for (int i = 0; i < N; i++) {
            const unsigned char *m = cab_por_msg ? cabs + 16 * ((size_t)d * N + i) : cabs + 16 * (size_t)d;
            nonce_be(n1, nonce_bytes, (uint64_t)i);
            if (crypto_aead_encrypt(c, &l, m, 16, 0, 0, 0, n1, k)) return -1;
            memcpy(S[i], c, 16);
        }
        int len = N;
        for (int dd = 1; dd <= D; dd++) {
            len >>= 1;
            for (int q = 0; q < len; q++) {
                for (int b = 0; b < 16; b++) S[q][b] = S[2 * q][b] ^ S[2 * q + 1][b];
                for (int b = 0; b < 16; b++) {
                    unsigned char x = S[q][b];
                    if (!x) continue;
                    for (int jj = 0; jj < 8; jj++)
                        if (x & (0x80 >> jj)) cnt_um[dd * 128 + b * 8 + jj]++;
                }
            }
            n_cubos[dd] += (uint64_t)len;
        }
    }
    return 0;
}
