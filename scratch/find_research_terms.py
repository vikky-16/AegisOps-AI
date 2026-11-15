import os

search_terms = [
    'one_shot', 'validation_only', 'closed_loop', 'strategy a', 
    'strategy b', 'strategy c', 'metrics_calculator', 'benchmark_runner', 
    '12345', 'smoke_run', 'smoke run', 'rsr', 'frr', 'farr', 'err', 'ara', 'ser'
]

hits = {term: [] for term in search_terms}

for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['venv', 'node_modules', '.git', '__pycache__', 'report_audit']):
        continue
    for f in files:
        if not f.endswith(('.py', '.json', '.md', '.ts', '.tsx', '.sh', '.txt')):
            continue
        p = os.path.join(root, f)
        try:
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
            c_lower = content.lower()
            for term in search_terms:
                if term in c_lower:
                    hits[term].append(p)
        except Exception:
            pass

for term, files in hits.items():
    print(f'Term "{term}": {len(files)} files')
    for f in files[:8]:
        print(f'   {f}')

