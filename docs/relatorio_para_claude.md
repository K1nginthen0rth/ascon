# PROMPT — CLAUDE CODE: RELATÓRIO DE IMPLEMENTAÇÃO
# Usar após cada tarefa completada para extrair o que foi feito

---

Acabou de implementar/modificar algo no repositório. Agora me faça um **relatório técnico** do que você fez. Não escreva texto de dissertação — me dê os fatos crus.

## O QUE QUERO SABER

### 1. O que foi criado/modificado?
- Lista de arquivos criados, modificados ou deletados
- Tamanho relevante (linhas de código, tamanho de dataset, etc.)

### 2. Que decisões de design você tomou e por quê?
- Escolheu subprocess vs ctypes? Por quê?
- Escolheu um formato de saída? Qual?
- Alguma ambiguidade que você resolveu sozinho? Como?

### 3. Parâmetros e configurações
- Valores fixos usados (seeds, tamanhos, thresholds, etc.)
- Dependências adicionadas
- Paths hardcoded ou configuráveis?

### 4. Resultados concretos
- Outputs de testes (pytest, KAT, sanity checks)
- Métricas obtidas (se aplicável): tempo de execução, contagens, acurácias
- Cole os outputs relevantes do terminal

### 5. O que NÃO funcionou ou ficou pendente?
- Erros encontrados e como resolveu (ou não)
- Limitações conhecidas da implementação
- TODOs deixados no código

### 6. Como reproduzir?
- Comando exato para rodar o que você fez
- Pré-requisitos (instalar algo? compilar algo?)

## FORMATO

Responda em Markdown. Use blocos de código para outputs do terminal. Seja direto — sem floreio, sem introdução, sem conclusão motivacional. Só fatos.

## EXEMPLO DE RESPOSTA ESPERADA

```markdown
## Relatório: src/crypto/ascon_wrapper.py

### Arquivos criados
- `src/crypto/__init__.py` (vazio)
- `src/crypto/kat_parser.py` (87 linhas)
- `src/crypto/ascon_wrapper.py` (203 linhas)
- `tests/test_ascon_wrapper.py` (145 linhas)

### Decisões de design
- **subprocess** em vez de ctypes: o .exe existente já aceita args via CLI
  e `scripts/generate_ascon_variable_sizes.py` já usa esse padrão (linha 42).
  Manter consistência.
- **Formato de I/O**: hex strings via stdin/stdout, mesmo protocolo do script
  existente.

### Parâmetros
- Timeout do subprocess: 10s (hardcoded, suficiente para KAT)
- Path do executável: `ascon-c/build/ascon_cli_ref.exe` (lido de env var
  ASCON_CLI_PATH, fallback para path relativo)

### Resultados
$ pytest tests/test_ascon_wrapper.py -v
test_encrypt_decrypt_roundtrip PASSED
test_kat_validation_passes PASSED (1089/1089 vetores OK, 4.2s)
...
9 passed in 6.31s

### Pendências
- [ ] Não testei com impl opt32 (só ref)
- [ ] Timeout de 10s pode ser curto para PT muito grandes (>64KB)

### Como reproduzir
$ cd lwc-ml
$ pytest tests/test_ascon_wrapper.py -v
```