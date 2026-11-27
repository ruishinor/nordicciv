import json, urllib.request, concurrent.futures
from pathlib import Path
OUT = Path(__file__).parent / 'connection_research'
OUT.mkdir(exist_ok=True)
urls = {
 'ssb': 'https://data.ssb.no/api/pxwebapi/v2/tables/03321/metadata?lang=en',
 'scb': 'https://statistikdatabasen.scb.se/api/v2/tables/TAB1830/metadata?lang=en',
 **{t:'https://api.statbank.dk/v1/tableinfo/'+t+'?format=JSON&lang=en' for t in ['PEND100','SKIB32','SKIB31','FLYV33']},
}
def get(pair):
 k,u=pair
 try:
  b=urllib.request.urlopen(u,timeout=60).read(); (OUT/(k+'.json')).write_bytes(b); d=json.loads(b)
  if 'dimension' in d:
   print(k, json.dumps({i:{'label':v['label'],'count':len(v['category']['index']),'sample':list(v['category'].get('label',{}).items())[:4]} for i,v in d['dimension'].items()}))
  else: print(k,json.dumps(d)[:16000])
 except Exception as e: print(k,type(e).__name__,str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as e: list(e.map(get,urls.items()))
