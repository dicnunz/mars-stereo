"""Fetch the exact PDS3 stereo pair, validating every byte before writing."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'data/provenance.json').read_text())
    for item in manifest['files']:
        path = ROOT / 'data' / item['name']
        if not path.exists():
            with urlopen(item['url'], timeout=60) as response:
                payload = response.read()
            if hashlib.sha256(payload).hexdigest() != item['sha256']:
                raise ValueError(f'Download hash mismatch: {path.name}')
            path.write_bytes(payload)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'Local source hash mismatch: {path.name}')
        print('Verified', path.name)


if __name__ == '__main__':
    main()
