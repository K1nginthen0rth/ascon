import sys, cffi
src, out, inc = sys.argv[1:4]
ffi = cffi.FFI()
ffi.cdef("""int gift_rounds;
int crypto_aead_encrypt(unsigned char *c, unsigned long long *clen,
 const unsigned char *m, unsigned long long mlen, const unsigned char *ad, unsigned long long adlen,
 const unsigned char *nsec, const unsigned char *npub, const unsigned char *k);""")
ffi.set_source("_gift_oficial_rodadas", '#include "api.h"\n#include "encrypt.c"\n#include "gift128.c"\n',
               include_dirs=[src, inc])
print(ffi.compile(tmpdir=out, verbose=False))
