#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "../ascon-c/crypto_aead/ascon128v13/ref/api.h"
#include "../ascon-c/tests/crypto_aead.h"

static int hex_value(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
    if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
    return -1;
}

static int hex_to_bytes(const char *hex, unsigned char **out, size_t *out_len) {
    size_t len = strlen(hex);
    if (len % 2 != 0) return -1;

    *out_len = len / 2;
    *out = (unsigned char *)malloc(*out_len);
    if (!*out) return -1;

    for (size_t i = 0; i < *out_len; i++) {
        int hi = hex_value(hex[2 * i]);
        int lo = hex_value(hex[2 * i + 1]);
        if (hi < 0 || lo < 0) {
            free(*out);
            return -1;
        }
        (*out)[i] = (unsigned char)((hi << 4) | lo);
    }
    return 0;
}

static void bytes_to_hex(const unsigned char *buf, size_t len) {
    for (size_t i = 0; i < len; i++) {
        printf("%02x", buf[i]);
    }
    printf("\n");
}

int main(int argc, char *argv[]) {
    if (argc != 5) {
        fprintf(stderr, "Uso: ascon_cli_ref.exe <key_hex> <nonce_hex> <ad_hex> <pt_hex>\n");
        return 1;
    }

    unsigned char *key = NULL, *nonce = NULL, *ad = NULL, *pt = NULL;
    size_t key_len = 0, nonce_len = 0, ad_len = 0, pt_len = 0;

    if (hex_to_bytes(argv[1], &key, &key_len) != 0) return 2;
    if (hex_to_bytes(argv[2], &nonce, &nonce_len) != 0) return 3;
    if (hex_to_bytes(argv[3], &ad, &ad_len) != 0) return 4;
    if (hex_to_bytes(argv[4], &pt, &pt_len) != 0) return 5;

    if (key_len != CRYPTO_KEYBYTES || nonce_len != CRYPTO_NPUBBYTES) {
        fprintf(stderr, "Erro: key e nonce devem ter 16 bytes.\n");
        free(key); free(nonce); free(ad); free(pt);
        return 6;
    }

    unsigned long long clen = 0;
    unsigned char *c = (unsigned char *)malloc(pt_len + CRYPTO_ABYTES);
    if (!c) {
        free(key); free(nonce); free(ad); free(pt);
        return 7;
    }

    int rc = crypto_aead_encrypt(
        c, &clen,
        pt, (unsigned long long)pt_len,
        ad, (unsigned long long)ad_len,
        NULL, nonce, key
    );

    if (rc != 0) {
        fprintf(stderr, "Erro na cifragem: %d\n", rc);
        free(key); free(nonce); free(ad); free(pt); free(c);
        return 8;
    }

    bytes_to_hex(c, (size_t)clen);

    free(key); free(nonce); free(ad); free(pt); free(c);
    return 0;
}