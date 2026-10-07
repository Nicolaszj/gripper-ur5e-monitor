"""Send a telemetry JSON file to the port URL without credentials."""
import argparse
import json
from pathlib import Path
import urllib.request
import uuid

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:1880/api/telemetry')
    parser.add_argument('--file', required=True)
    args = parser.parse_args()
    sample = json.loads(Path(args.file).read_text(encoding='utf-8'))
    # Each invocation is a new example sender session; preserve measurement values.
    sample['boot_id'] = 'http-' + uuid.uuid4().hex[:12]
    request = urllib.request.Request(args.url, data=json.dumps(sample, allow_nan=False).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        print(f'HTTP {response.status}: {response.read().decode()}')

if __name__ == '__main__':
    main()
