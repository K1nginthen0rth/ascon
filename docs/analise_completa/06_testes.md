# 6. Suíte de testes (`tests/`)

**130 testes pytest**, 10 módulos, todos passando e alinhados com o código
atual (incluindo a mudança de semântica do Boruta, ainda não commitada —
`tests/test_selector.py` já reflete o novo comportamento). `conftest.py` (17
linhas, raiz) injeta `src/` e `src/crypto/` no `sys.path` — não é necessário
instalar o pacote para rodar os testes.

| Módulo | Linhas | Nº testes | Cobertura |
|---|---|---|---|
| `test_extractor.py` | 358 | 38 | As 6 famílias de features individualmente + orquestrador (307D, subconjunto de famílias, ausência de `Inf`, benchmark <10ms) + 2 testes condicionados à existência de `ascon_aead128_pilot_v2.parquet` (dataset legado, mas ainda presente em disco) |
| `test_gift_cofb_wrapper.py` | 193 | 16 | Roundtrip, KAT completo (`assert total==1089`), rejeição de chave/nonce/CT/tag errados, `len(ct)=len(pt)+16` para vários tamanhos |
| `test_ascon_wrapper.py` | 190 | 15 | Idem GIFT-COFB, sem o teste extra de comprimento |
| `test_aes_ecb_wrapper.py` | 115 | 12 | Controle legado: vazamento de padrão ECB (blocos repetidos → CT idêntico), determinismo, padding PKCS7 |
| `test_cnn2d.py` | 156 | 10 | Conversão CT→imagem (32×32), forward/latent shape, determinismo, treino 1 época |
| `test_vigenere_wrapper.py` | 90 | 10 | Periodicidade explícita, involução XOR, quirk dos 25 bits efetivos, `len(ct)=len(pt)` |
| `test_metrics.py` | 126 | 9 | Bootstrap CI, F1-macro, McNemar, ECE, serialização |
| `test_selector.py` | 158 | 8 | Pipeline MI→mRMR→Boruta-diagnóstico — **alinhado com a mudança pendente** (ver abaixo) |
| `test_classical.py` | 124 | 6 | Exclusão de metadados, **detecção de vazamento de chave** (`ValueError` com `"VAZAMENTO"`), Dummy/RF/SVM/XGBoost |
| `test_cnn1d.py` | 91 | 6 | Forward/latent shape, padding/truncamento, treino 1 época, `label_map` |

## 6.1 `test_selector.py` — confirmação da nova semântica do Boruta

Verificado por leitura direta do código-fonte (`src/features/selector.py`,
linhas 137–168) e do teste correspondente: o teste-chave
`test_selector_pure_noise_boruta_confirms_few` afirma
`rep["final_output"] == rep["stage2_output"]` mesmo quando o Boruta confirma
poucas/zero features em cenário de ruído puro — ou seja, o teste já cobre
exatamente a garantia que a mudança de código pretende dar (Boruta nunca
reduz o conjunto usado pelo classificador). Não há nenhuma referência
residual ao comportamento antigo (`stage3_output` como filtro, fallback
mRMR-se-Boruta-vazio). **Os testes não precisam de nenhum ajuste adicional
para acompanhar essa mudança quando ela for commitada.**

## 6.2 Testes vestigiais (não quebrados, só não fazem parte do fluxo vivo)

- `test_aes_ecb_wrapper.py` — cobre um wrapper do protocolo de controle
  antigo (hoje substituído por Vigenère), mas continua correto e passando.
- 2 testes em `test_extractor.py` (`test_extract_dataset_pilot`,
  `test_no_ciphertext_in_output`) usam `ascon_aead128_pilot_v2.parquet`
  (dataset single-class legado) em vez do dataset canônico
  `keyholdout_2class_60k_v1` — validam a mecânica de `extract_dataset()`,
  mas não contra o dataset de produção atual.

## 6.3 Scripts de teste fora de `tests/`

- `scripts/smoke_test.py` (520 linhas) — teste de integração reduzido dos
  Caminhos B/C/D (500 amostras, 2 folds, 3 épocas, alvo <10min em CPU),
  incluindo teste de checkpoint/resume. Não é pytest, é executado
  manualmente antes de rodar o experimento completo em GPU.
- `scripts/check_ml_env.py` — sanidade do ambiente (versões de libs, teste
  mínimo de `BorutaPy`/`mrmr_classif` contra quebras conhecidas em numpy 2.x).
- `scripts/test_wrapper_python.py` — vestigial, anterior ao wrapper cffi
  atual; superado por `tests/test_ascon_wrapper.py`.

## 6.4 Como rodar

```bash
pytest tests/ -v                                      # todos os 130
pytest tests/test_selector.py -v                      # um módulo
pytest tests/test_extractor.py::test_histogram_sums_to_one -v  # um teste
pytest tests/ --timeout=30
```
