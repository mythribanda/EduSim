import urllib.request
import json
import sys

url = 'http://localhost:8001/api/tutor/analyze'
payload = {'query': "Explain Newton's first law with its mathematical representation and three real-life examples."}
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        res_bytes = resp.read()
        data = json.loads(res_bytes.decode('utf-8'))
        print('SUCCESS:', data.get('success'))
        print('TOP-LEVEL KEYS:', list(data.keys()))
        data_field = data.get('data', {})
        print('DATA KEYS:', list(data_field.keys()) if isinstance(data_field, dict) else type(data_field))
        if isinstance(data_field, dict):
            for k in ['explanation', 'ai_explanation', 'summary', 'formula', 'formulas', 'ragContent', 'sources', 'simulation_guide']:
                v = data_field.get(k)
                if isinstance(v, str):
                    print(f'{k} (str len={len(v)}):', v[:150].replace('\n', ' '))
                elif isinstance(v, list):
                    print(f'{k} (list len={len(v)}):', v[:2])
                elif isinstance(v, dict):
                    print(f'{k} (dict keys={list(v.keys())})')
                else:
                    print(f'{k}:', type(v), v)
        print("\n--- FULL RESPONSE JSON ---\n")
        print(json.dumps(data, indent=2)[:2000])
except Exception as e:
    print('ERROR:', e)
