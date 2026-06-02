"""
Validar todos os datasets gerados (Parquet files).
"""
from pathlib import Path
import json

ROOT = Path(r"C:\Users\nycol\Documents\Mestrado\ascon")
PROCESSED = ROOT / "data" / "processed"

datasets = [
    ("ascon_aead128_base_v1", "Dataset original - 10k amostras, plaintext 128B fixo"),
    ("ascon_aead128_variable_sizes_v1", "Dataset novo - 11k amostras, tamanhos variáveis"),
]

print("=" * 80)
print("VALIDAÇÃO DE DATASETS".center(80))
print("=" * 80)

for dataset_id, description in datasets:
    parquet_file = PROCESSED / f"{dataset_id}.parquet"
    manifest_file = PROCESSED / f"{dataset_id}_manifest.json"
    profile_file = PROCESSED / f"{dataset_id}_profile.json"
    
    print(f"\n📊 {dataset_id}")
    print(f"   {description}")
    print("-" * 80)
    
    # Check parquet file
    if parquet_file.exists():
        size_mb = parquet_file.stat().st_size / (1024 * 1024)
        print(f"   ✅ Parquet: {parquet_file.name} ({size_mb:.1f} MB)")
    else:
        print(f"   ❌ Parquet: NÃO ENCONTRADO")
        continue
    
    # Check manifest
    if manifest_file.exists():
        with open(manifest_file) as f:
            manifest = json.load(f)
        n_samples = manifest.get("n_samples")
        print(f"   ✅ Manifest: {manifest_file.name}")
        print(f"      - Amostras: {n_samples:,}")
        
        if "plaintext_sizes" in manifest:
            sizes = manifest["plaintext_sizes"]
            print(f"      - Tamanhos PT: {sizes}")
        elif "len_pt_range_bytes" in manifest["plaintext_policy"]:
            pt_range = manifest["plaintext_policy"]["len_pt_range_bytes"]
            print(f"      - Tamanho PT: {pt_range[0]}-{pt_range[1]} bytes")
    else:
        print(f"   ⚠️  Manifest: NÃO ENCONTRADO")
    
    # Check profile
    if profile_file.exists():
        with open(profile_file) as f:
            profile = json.load(f)
        algo = profile.get("algorithm")
        impl = profile.get("implementation")
        print(f"   ✅ Profile: {profile_file.name}")
        print(f"      - Algoritmo: {algo} ({impl})")
    else:
        print(f"   ⚠️  Profile: NÃO ENCONTRADO")

print("\n" + "=" * 80)
print("FIM DA VALIDAÇÃO".center(80))
print("=" * 80)
