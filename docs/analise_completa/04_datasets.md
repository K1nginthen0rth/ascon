# 4. Datasets

Todos gerados em `data/processed/` (gitignored) + manifesto JSON com SHA-256
do binário cffi, seed, parâmetros. Chaves/nonces/plaintexts brutos ficam
separados em `data/interim/`, nunca no parquet público.

## 4.1 Dataset principal (vivo)

**`keyholdout_2class_60k_v1`** — gerado por `scripts/generate_2class_50k.py`
(nome do arquivo desatualizado — a config interna (`CONFIG_50K`) gera hoje o
dataset de 60k, não 50k).

| Parâmetro | Valor |
|---|---|
| Total | 60.000 (30.000 Ascon-AEAD128 + 30.000 GIFT-COFB) |
| Plaintext | 65.536 bytes (64 KB) fixo, 100% corpus Gutenberg (SPGC) |
| Chaves | 300, seed=42, `key_seed_offset=2000` |
| Amostras/chave/algoritmo | 100 |
| AD | vazio |
| Nonce | contador global |
| Split | 240 chaves trainval / 60 chaves test (80/20), com 5-fold `GroupKFold` por `key_id` dentro do trainval nos scripts de CV |
| `len_ct` por amostra | 65.552 bytes (65.536 + 16 tag) |
| Tamanho no disco | ~3,93 GB |

Validado por `scripts/validate_2class_60k.py` (vivo).

## 4.2 Controles positivos (vivos)

| dataset_id | Composição | Gerado por | Offset |
|---|---|---|---|
| `control_vigenere_64k_v1` | 90k = 30k Ascon + 30k GIFT-COFB + 30k Vigenère-XOR, PT 64KB, 300 chaves, 3-classes | `generate_vigenere_64k.py` | 4000 |
| `vigenere_vs_random_v1` | 60k = 30k Vigenère-XOR + 30k bytes PRNG puros, PT 64KB, 300 chaves, 2-classes | `generate_vigenere_random_dataset.py` (reaproveita as linhas Vigenère de `control_vigenere_64k_v1` — precisa rodar depois) | 5000 |

## 4.3 Datasets legados (protocolo antigo — PT variável 0–2048B, 15k/22k/50k, mantidos só como histórico)

| dataset_id | Amostras | Gerado por | Observação |
|---|---|---|---|
| `ascon_aead128_pilot_v2` | 11.000 | `generate_pilot_dataset.py` | single-class, 10 chaves, 11 tamanhos de PT |
| `ascon_aead128_keyholdout_v2` | 7.500 | `generate_pilot_dataset.py` | single-class, 50 chaves, 3 tamanhos |
| `ascon_aead128_base_v1` | 10.000 | `generate_ascon_parquet.py` | 1 única chave (pré-datas a Regra de Ouro 2) |
| `ascon_aead128_variable_sizes_v1` | 11.000 | `generate_ascon_variable_sizes.py` | 1 única chave, chama `ascon_cli_ref.exe` via subprocess (não usa o wrapper cffi) |
| `pilot_2class_v1` | 22.000 | `generate_2class_dataset.py` | piloto 2-classes, 10 chaves |
| `keyholdout_2class_v1` | 15.000 | `generate_2class_dataset.py` | 50 chaves, PT 64/256/1024B — este é o **"15k"** citado em vários relatórios |
| `keyholdout_2class_50k_v1` | 100.200 | versão anterior de `generate_2class_50k.py` (editado in-place para virar o gerador do 60k) | **órfão**: existe em disco mas nenhum script atual o reproduz; validado só por `validate_2class_50k.py` |
| `control_3class_v1` | 45.090 | `generate_3class_control.py` | Ascon+GIFT+AES-ECB, PT natural (corpus) |
| `control_repetitive_3class_v1` | 45.090 | `generate_3class_repetitive.py` | idem, PT repetitivo determinístico |
| `control_vigenere_v1` | 14.850 | `generate_vigenere_control.py` | Vigenère 3-classes, protocolo antigo (PT variável) |
| `random_control_v1` | 10.000 | `generate_random_control.py` | CT = bytes aleatórios puros (não cifra nada de fato) |

## 4.4 Reuso de material de chave entre datasets legados (achado do inventário)

Como `key_seed_offset` só desloca a mesma seed base (42), datasets legados
que reutilizam o mesmo offset por coincidência geram **as mesmas chaves**,
mesmo pertencendo a experimentos distintos:

- `offset=2000`: usado tanto pela versão órfã de `keyholdout_2class_50k_v1`
  (100 chaves) quanto pela atual `keyholdout_2class_60k_v1` (300 chaves) — as
  primeiras 100 chaves do dataset vivo são idênticas às do órfão.
- `offset=3000`: `control_3class_v1` e `control_vigenere_v1` (30 chaves cada) —
  chaves idênticas entre os dois controles antigos.
- `offset=4000`: `control_repetitive_3class_v1` (30 chaves) e
  `generate_vigenere_64k.py` (300 chaves) — as 30 primeiras coincidem, apesar
  de ambos os scripts terem comentários dizendo "offset disjunto de
  0/1000/2000/3000" (nenhum viu a colisão em 4000, porque não estava na
  lista mencionada).

Não é um vazamento (os datasets não são combinados no mesmo experimento de
treino/avaliação), mas é reuso de material de chave não documentado — vale
registrar caso algum experimento futuro combine dois desses datasets.

## 4.5 Discrepância no comando de validação documentado no CLAUDE.md

`CLAUDE.md` cita `python scripts/validate_all_datasets.py` como o comando
que "checa χ², nonces, compressão, decrypt". O script real (66 linhas) só
verifica **existência de arquivo** e lê manifest/profile de dois datasets
hardcoded (`ascon_aead128_base_v1`, `ascon_aead128_variable_sizes_v1`, ambos
os mais antigos do repositório) — não implementa nenhum dos 4 checks
descritos. Quem de fato faz χ²/compressão/decrypt-spot-check são
`validate_pilot_dataset.py`, `validate_2class_60k.py` e os `validate_3class_*.py`,
cada um hardcoded para seu próprio dataset. Ver correção sugerida em
[08_achados_e_pendencias.md](08_achados_e_pendencias.md).
