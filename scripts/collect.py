"""Fetch each independent figure; the publisher only consumes a complete validated run."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
import sys
import sources as s

def collect(directory):
    directory.mkdir(parents=True, exist_ok=True)
    jobs={
        'job':s.jobs,'ledighed':lambda:s.star_simple('y25i03','mgrpy25i03_2','mgrpy25i03_1'),
        'alder':s.age_rates,'dimittender':lambda:s.star_simple('y01dia02','mgrpdia02_3'),
        'langtidsledighed':s.longterm,'stillinger':lambda:s.star_simple('y25i07','mgrpy25i07_3'),
        'brancher':s.branches,'udenlandske':s.foreigners,'seniorer':s.seniors,
        'udland':s.international,'varslinger':lambda:s.star_simple('y25i05','mgrpy25i05_1','mgrpy25i05_2'),
        'priser':s.prices,
    }
    failures=[]
    def save(key,data):
        (directory/(key+'.json')).write_text(json.dumps(data,ensure_ascii=False,allow_nan=False))
        print(key, max(data) if isinstance(data,dict) else data[0], flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        requests={pool.submit(fn):key for key,fn in jobs.items()}
        for future in as_completed(requests):
            key=requests[future]
            try:
                data=future.result()
                save(key,data)
                if key=='udenlandske':save('andel',s.foreign_share(data))
            except Exception as error:
                print(f'::error::{key}: {error}',flush=True);failures.append(key)
    if failures:raise SystemExit('Kilder med fejl: '+', '.join(failures))

if __name__=='__main__':collect(Path(sys.argv[1]))
