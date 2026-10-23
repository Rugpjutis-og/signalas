"""Synthetic in-memory fixture. No local/Neon data reads or writes."""
import json
from zoneinfo import ZoneInfo
from test_narrative_registry import REG, NOW, unit, result, match, assessment, packet
import narrative_projection as projection
import narrative_registry as registry

p,analyses=packet()
records=[unit('a','Šilas nepajėgus apsiginti. Parama atima išteklius.',author='Jonas'),
         unit('b','Mūsų gynyba per silpna, Šilas nepasiruošęs.',author='Ieva'),
         unit('c','NATO neprovokuoja karo.',author='Gabija'),
         unit('d','Ką reiškia teiginys, kad valstybė neapsigins?',author='Rokas',kind='comment',parent_id='a')]
values=[result([match('N001','Šilas nepajėgus apsiginti.',place='Šilas'),match('N030','Parama atima išteklius.')]),
        result([match('N001','Mūsų gynyba per silpna, Šilas nepasiruošęs.',place='Šilas')]),
        result([match('N004','NATO neprovokuoja karo.','oppose')]),
        result([match('N001','Ką reiškia teiginys, kad valstybė neapsigins?','unknown')])]
for u,v in zip(records,values):analyses[projection.key(u)]=assessment(u,v)
p['records']+=records
out=projection.project(p['records'],analyses,REG,['2026-10-23'],ZoneInfo('Europe/Vilnius'),None,'exercise-a')
print(json.dumps({**out,'candidates':projection.candidates(p,analyses,REG,now=NOW),'registry':registry.public_registry(REG),
    'candidate_policy':registry.CANDIDATE_POLICY,'mode':'live','csrf':'synthetic-test','source':'test',
    'collected_at':NOW.isoformat(),'analysis_revision':'test-1','coverage':'synthetic_browser_fixture','collection_scope':{},
    'days':['2026-10-23'],'start':'2026-10-23T00:00:00+03:00','end':'2026-10-24T00:00:00+03:00','range_saved':True,
    'context_available':False,'analysis_count':len(p['records']),'monitoring':{'state':'watching'}},ensure_ascii=False))
