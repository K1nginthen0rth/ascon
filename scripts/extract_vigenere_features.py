from pathlib import Path
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'src' / 'crypto'))

from src.features.extractor import CiphertextFeatureExtractor

if __name__ == '__main__':
    src = REPO / 'data' / 'processed' / 'control_vigenere_v1.parquet'
    dst = REPO / 'data' / 'processed' / 'control_vigenere_v1_features.parquet'
    print('src=', src)
    print('dst=', dst)
    extractor = CiphertextFeatureExtractor()
    df = extractor.extract_dataset(src, output_path=dst, n_jobs=-1, show_progress=True)
    print('done', df.shape)
