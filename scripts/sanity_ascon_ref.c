#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../ascon-c/crypto_aead/ascon128v13/ref/api.h"
#include "../ascon-c/tests/crypto_aead.h"

static void print_hex(const unsigned char* buf, size_t len) {
    for (size_t i = 0; i < len; i++) {
        printf("%02x", buf[i]);
    }
    printf("\n");
}

int main(void) {
    unsigned char key[CRYPTO_KEYBYTES] = {0};
    unsigned char nonce[CRYPTO_NPUBBYTES] = {0};

    const unsigned char ad[] = "header";
    const unsigned char msg[] = "teste-ascon";

    unsigned long long clen = 0;
    unsigned long long mlen = (unsigned long long)strlen((const char*)msg);

    unsigned char* cipher = (unsigned char*)malloc(mlen + CRYPTO_ABYTES);
    if (!cipher) {
        fprintf(stderr, "Erro de alocacao\n");
        return 1;
    }

    int rc = crypto_aead_encrypt(
        cipher, &clen,
        msg, mlen,
        ad, (unsigned long long)strlen((const char*)ad),
        NULL, nonce, key
    );

    if (rc != 0) {
        fprintf(stderr, "Falha na cifragem: %d\n", rc);
        free(cipher);
        return 1;
    }

    printf("mlen=%llu\n", mlen);
    printf("clen=%llu\n", clen);
    printf("ciphertext_tag=");
    print_hex(cipher, (size_t)clen);

    free(cipher);
    return 0;
}