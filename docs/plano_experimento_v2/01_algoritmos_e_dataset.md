# 1. Algoritmos e dataset

## 1.1 Os algoritmos ✅

| Algoritmo | Família construtiva | Não-linearidade | Chave/Nonce/Tag (bits) | `len_ct` p/ PT 64KB | Implementação | Status |
|---|---|---|---|---|---|---|
| Ascon-AEAD128 | esponja/permutação (duplex) | S-box 5 bits | 128 / 128 / 128 | 65.552 | `ascon-c/crypto_aead/ascon128av13/ref` | ✅ corrigido e validado (KAT 1089/1089) |
| GIFT-COFB | cifra de bloco SPN + modo COFB | S-box 4 bits | 128 / 128 / 128 | 65.552 | `opt32` via cffi (pronto) | ✅ pronto |
| Grain-128AEAD | cifra de fluxo (LFSR+NFSR) | realimentação NFSR | 128 / **96** / **64** | **65.544** | `grain-128aead/NIST/ref` via cffi | ✅ pronto (KAT 1089/1089) |
| Sparkle (Schwaemm256-128) | esponja ARX | ARX (sem S-box) | confirmado: 128/256/128 | 65.552 | `sparkle/crypto_aead/schwaemm256128v2/ref` via cffi | ✅ pronto (KAT oficial 1089/1089) |
| AES-128-ECB | cifra de bloco, modo inseguro | S-box 8 bits | 128 / — / — | 65.552 (PKCS7 = 1 bloco cheio, pois 65.536 é múltiplo de 16) | `cryptography` (pronto) | ✅ pronto — **controle** |

**Por que estes quatro:** cada mecanismo de não-linearidade aparece só uma vez
entre os principais (S-box em duas famílias construtivas diferentes, ARX,
NFSR) — nenhum estudo da RSL testa qualquer finalista LWC do NIST nem modo
AEAD, então o conjunto inteiro preenche a lacuna identificada. Todos são
finalistas ou padrão do processo NIST LWC — nada de construção ad-hoc.

**Romulus descartado** ✅ — mesma categoria do GIFT-COFB (cifra de bloco SPN);
risco alto de reproduzir o par "idêntico e indistinguível" sem ganho de
diversidade. A ancoragem em literatura (SKINNY aparece no E20) não justificava
sozinha, pois nenhum dos outros algoritmos tem essa ancoragem — critério seria
inconsistente.

**Vigenère aposentado como controle** ✅ — substituído por AES-ECB, resposta
direta à crítica do SBSeg ("controle simples demais, usar DES ou AES"). Os
resultados Vigenère do v1 ficam como histórico.

## 1.2 Correção do Ascon ✅ (obrigatória antes de gerar qualquer dado)

O NIST SP 800-232 final (ago/2025) define "Ascon-AEAD128" com **taxa de 128
bits e capacidade de 192** — parametrização que na nomenclatura pré-padrão se
chamava "Ascon-128a". O wrapper atual aponta para `ascon128v13` (taxa 64 bits,
a "Ascon-128" original). Correção: reapontar `_ascon_cffi_build.py` para
`ascon-c/crypto_aead/ascon128av13/ref` e revalidar contra o KAT próprio dessa
pasta (`ascon128av13/LWC_AEAD_KAT_128_128.txt`). O dataset v1 fica relabelado
implicitamente como "Ascon-128 pré-padrão"; o v2 nasce correto.

## 1.3 ❌ Variante de rodadas reduzidas — REJEITADA (decisão de 2026-08-21)

Recomendação da revisão de especialista, **rejeitada pelo Nycolas** na rodada
final de decisões (C2). Registro mantido para histórico: a proposta era uma
variante do Ascon com rodadas reduzidas como ponto intermediário de calibração
entre o AES-ECB e os esquemas íntegros. Não será implementada no v2.

## 1.4 Especificação do dataset v2 ✅

| Parâmetro | Valor |
|---|---|
| Chaves | **300** (inalterado), `key_seed_offset=6000` (offsets 0–5000 já usados; colisões documentadas em `analise_completa/04_datasets.md`) |
| Slots por chave | 100 (par chave+plaintext+nonce) |
| Algoritmos por slot | 5 (encadeamento: mesma tripla para todos) |
| Total de amostras | 300 × 100 × 5 cifras = 150.000; **+30.000 do controle PRNG (C1, decisão 2026-08-21) = 180.000 no parquet** (~11,8 GB) — ver 06 Fase 4.2 |
| Plaintext | 65.536 bytes fixo |
| Nonce | contador global determinístico de 128 bits. Grain (nonce de 96 bits) usa os 12 bytes menos significativos. Sparkle/Schwaemm256-128 (nonce de 256 bits) usa o contador de 128 bits nos **128 bits menos significativos**, com os 128 bits mais significativos fixados em zero — convenção registrada no manifesto de geração (o lado do zero-padding não afeta unicidade, mas precisa estar documentado para reprodutibilidade; era o único algoritmo sem mapeamento definido). AES-ECB ignora. |
| AD | vazio |
| Split | 240 chaves trainval / 60 teste (80/20), inalterado |

Números derivados para a análise principal (4 classes, excluindo AES-ECB):
teste = 24.000 amostras; trainval = 96.000; treino por fold de CV = 76.800.
Controle binário (Ascon vs AES-ECB): 60.000 amostras, lidas do mesmo parquet.

## 1.5 Fonte de plaintext: 80% texto / 20% imagem ✅

- **Texto (80%):** corpus SPGC (Project Gutenberg), como no v1.
- **Imagem (20%):** ImageNet-1k 256×256 (Hugging Face,
  `benjamin-paine/imagenet-1k-256x256`), **split de validação** (50k imagens —
  não precisa baixar o treino de 1,28M), convertidas para tons de cinza →
  256×256×1 = exatamente 65.536 bytes. Licenças confirmadas pelo Nycolas.
- **Sorteio por amostra dentro de cada chave** (não por chave inteira): de cada
  100 slots de uma chave, ~80 texto / ~20 imagem. Garante que qualquer split
  por chave preserva a proporção automaticamente.
- ~6.000 slots de imagem no total → ≤6.000 imagens distintas necessárias.
- Coluna `plaintext_source` marca `corpus`/`imagem` — permite a análise
  secundária da CNN2D (réplica E05) restrita ao subconjunto imagem, e a
  estratificação de erro por origem.

**Por que misturar em vez de dataset separado:** o encadeamento garante que a
origem do plaintext fica balanceada igualmente entre os 5 algoritmos — não pode
virar viés diferencial. Um pipeline só serve às duas análises.

## 1.6 Comprimento do Grain e truncamento ✅ (escopo corrigido)

O parquet guarda os criptogramas **crus**: Grain sai com 65.544 bytes (tag de 8
bytes), os demais com 65.552.

**Correção de escopo:** o truncamento isola um artefato específico do
**Caminho B (CNN1D)** — o padding posicional causado pela diferença de
comprimento total — e das estatísticas de Caminho A sensíveis a comprimento
total do CT/payload (`lz_complexity`, `runs_count`, autocorrelação). Ele
**nunca** se aplica às features de tag: essas usam sempre uma janela comum de
8 bytes sobre o CT **cru**, antes de qualquer corte (ver
`02_features_e_selecao.md`). Motivo: cortar os últimos bytes do CT removeria
metade da tag dos três algoritmos com `ABYTES=16`, e a extração — que define a
fronteira da tag como "os últimos `ABYTES` bytes" — passaria a contar bytes de
payload como se fossem tag, silenciosamente, no braço pensado para ser o mais
limpo dos dois.

Dois braços: `cru` (comprimentos reais) e `controlado` (todos cortados para
65.544, removendo os 8 bytes finais do CT bruto). Detalhe em
`04_protocolo_metricas_validacao.md`.

## 1.7 RNG de geração: CTR_DRBG (NIST SP 800-90A) ✅

Substitui o NumPy PCG64 **na geração** (chaves + amostragem de plaintext):

- Mecanismo: **CTR_DRBG com AES-128**, sem função de derivação (configuração
  prevista no padrão para entrada de entropia de tamanho completo).
- Reprodutibilidade preservada: a "entropia de entrada" é a seed fixa do
  projeto — uso deliberado do *mecanismo* do padrão como PRNG determinístico,
  não como fonte de segurança (declarar isso na metodologia).
- Implementação sobre a lib `cryptography` (mesma já usada no wrapper AES-ECB),
  no padrão dos demais wrappers do projeto.
- **Validação obrigatória contra os vetores CAVP do NIST** antes de gerar
  qualquer dataset — mesmo protocolo dos KATs de Ascon/GIFT-COFB.
- Interface mínima: `.generate(n_bytes)` + funções utilitárias para sortear
  chave (16 bytes) e inteiro limitado (escolha de corpus/posição), sem imitar
  a API completa do NumPy.
- **Escopo (decisão do Claude, a confirmar):** só a geração usa DRBG. O
  bootstrap de métricas continua NumPy (`default_rng(42)`) e o treino
  torch continua `torch.manual_seed` — são usos estatísticos/de treino, não
  material criptográfico de teste; trocar mudaria resultados sem ganho de
  rigor.

Motivação: reviewer de segurança não aceita bem "NumPy" como gerador do
material criptográfico; SP 800-90A é o padrão da própria área e mantém coerência
temática (SP 800-232 = Ascon; SP 800-22 = features; SP 800-90A = geração).

## 1.8 Validação do dataset v2 ✅

Extensão do `validate_2class_60k.py` para N algoritmos heterogêneos:

1. Nonces únicos — cientes de que Grain usa 96 bits e AES-ECB não usa nonce
2. χ²/compressão — ~uniforme para os 4 principais; **desvio esperado e
   documentado** para o AES-ECB (é o controle, não é falha)
3. Decrypt spot-check por algoritmo, com as convenções de cada um
4. **Novo:** proporção texto/imagem ≈ 80/20 global e por split
5. **Novo:** encadeamento correto — mesma chave+plaintext nas 5 linhas de cada slot
6. Manifesto com SHA-256 dos binários, seeds, versão do DRBG e resultado CAVP

## 1.9 Wrappers: ordem e risco ✅ CONCLUÍDO (2026-08-21)

Ordem executada: **Ascon (correção) → CTR_DRBG → Grain-128AEAD → Sparkle** —
cada um validado por KAT/CAVP oficial. Molde: mesmo padrão cffi do GIFT-COFB.

✅ **Risco MSVC não se concretizou:** ao contrário do GIFT-COFB (que exigiu
headers customizados por usar expressões statement do GCC), tanto
Grain-128AEAD quanto Schwaemm256-128 são C/C99 portável e compilaram de
primeira, sem nenhum patch. Detalhe completo em `06_implementacao_passo_a_passo.md`
Fase 1.
