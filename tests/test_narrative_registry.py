"""Contract/aggregation tests with authored assessments; not model accuracy claims."""
import copy
import json
import io
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo
import narrative_registry as reg
import narrative_projection as project
import narrative_admin as admin

NOW = datetime(2026,10,23,12,tzinfo=timezone.utc)
REG = reg.load()

def match(type_id, evidence, stance='support', place=''):
    return {'type_id':type_id,'evidence':evidence,'stance':stance,
            'instance_entities':{k:place if k=='place' else '' for k in reg.ENTITY_KEYS}}

def result(matches=None, proposals=None, status=None):
    return {'match_status':status or ('matched' if matches else 'unmatched' if proposals else 'no_narrative'),
            'matches':matches or [],'proposals':proposals or [],'uncertainty_reason':''}

def unit(i, text, author=None, thread=None, **extra):
    return {'source':'test','id':str(i),'kind':'post','text':text,'published_at':'2026-10-23T10:00:00Z',
            'exercise_id':'exercise-a','author_id':author or str(i),'thread_id':thread or str(i),
            'sourceUrl':'https://example.test/source/'+str(i),**extra}

def assessment(u, value):
    return {'registry_version':REG['version'],'exercise_id':u.get('exercise_id'),'result':{'narrative_analysis':value}}

def proposal(text):
    return {'title':'Bendruomenė atkuria pasitikėjimą','claim_template':'{bendruomenė} bendrais veiksmais atkuria pasitikėjimą.',
            'topic_id':'T10','evidence':text,'nearest_type_ids':['N031'],
            'novelty_reason':'Bendras dalyvavimas, ne vienintelė politinė gelbėtoja.'}

def packet(audience=None):
    texts=['Kaimynų savanoriška pagalba vėl suartino mūsų bendruomenę.',
           'Po talkos žmonės daugiau pasitiki vienas kitu, susitarė dirbti kartu.',
           'Bendradarbiavimas dalijant maistą grąžino tikėjimą kaimynais.']
    records=[unit(i,t) for i,t in enumerate(texts)]
    p={'exercise_id':'exercise-a','records':records,'membership_snapshots':[]}
    if audience is not None:p['membership_snapshots']=[{'exercise_id':'exercise-a','complete':True,
        'assigned_account_ids':[str(i) for i in range(audience)],'valid_from':'2026-10-01T00:00:00Z','valid_until':'2026-11-01T00:00:00Z'}]
    analyses={project.key(u):assessment(u,result(proposals=[proposal(u['text'])])) for u in records}
    return p,analyses


class RegistryTests(unittest.TestCase):
    def test_exact_catalog_and_no_silent_legacy_migration(self):
        self.assertEqual([t['id'] for t in REG['types']],['N%03d'%i for i in range(1,36)])
        old=json.loads((reg.ROOT/'data/catalog.json').read_text())
        self.assertEqual([(t['app_id'],t['name']) for t in REG['topics']],[(t['id'],t['name']) for t in old['themes']])
        self.assertTrue(all(r['action']=='reassess_not_automatic' for r in REG['legacy_crosswalk']))
        self.assertNotIn('BLUE',json.dumps(reg.prompt_registry(REG),ensure_ascii=False))
        self.assertEqual(len(REG['formulations']),41)
        for t in REG['types']:
            self.assertTrue(t['include_when'] and t['exclude_when'])

    def test_no_invented_type_and_exact_original_language_evidence(self):
        value=result([match('N004','NATO neprovokuoja karo','oppose')])
        self.assertEqual(reg.validate(value,REG,'NATO neprovokuoja karo')['matches'][0]['stance'],'oppose')
        with self.assertRaises(ValueError):reg.validate(value,REG,'NATO užtikrina kolektyvinę gynybą')
        value['matches'][0]['type_id']='N-004'
        with self.assertRaises(ValueError):reg.validate(value,REG,'NATO neprovokuoja karo')
        value=result([match('N004','НАТО не провоцирует войну','oppose')])
        self.assertEqual(reg.validate(value,REG,'НАТО не провоцирует войну'),value)

    def test_broad_tags_and_uncertainty_are_not_forced_matches(self):
        for text in ('Kas vakarienei?','MB: Bullying','MB: Hate speech','MB: Minorities','Pro-RU / Anti-IL'):
            self.assertEqual(reg.validate(result(),REG,text)['matches'],[])
        with self.assertRaises(ValueError):reg.validate(result(status='uncertain'),REG,'Neaišku')
        with self.assertRaises(ValueError):reg.validate(result(status='unmatched'),REG,'Teiginys')

    def test_multiple_claims_specificity_and_deduplicated_rollup(self):
        text='Parama atima išteklius. Teisė taikoma tik privilegijuotiems.'
        value=result([match('N030','Parama atima išteklius.'),match('N018','Teisė taikoma tik privilegijuotiems.','unknown')])
        reg.validate(value,REG,text)
        u=unit('multi',text)
        output=project.project([u],{project.key(u):assessment(u,value)},REG,['2026-10-23'],ZoneInfo('Europe/Vilnius'),None,'exercise-a')
        self.assertEqual(output['assigned_unit_count'],1)
        self.assertEqual(len(output['narratives']),2)
        self.assertEqual(output['type_rollups']['N010'],1)
        self.assertNotIn('N010',[n['id'] for n in output['narratives']])
        self.assertEqual(output['narratives'][1]['stance_coverage'],{'known':0,'unknown':1,'percent':0})
        with self.assertRaises(ValueError):reg.validate(result([match('N030',text),match('N010',text)]),REG,text)
        with self.assertRaises(ValueError):reg.validate(result([match('N030',text),match('N030',text)]),REG,text)

    def test_places_and_name_aliases_are_variants_not_new_types(self):
        us=[unit(1,'Teiginys Vilniuje'),unit(2,'Teiginys Šile'),unit(3,'Teiginys Kaune')]
        values=[result([match('N001',u['text'],place=p)]) for u,p in zip(us,['Vilnius','Šilas','Kaunas'])]
        context={'nameMappings':[{'realName':'Vilnius','exerciseName':'Šilas'}]}
        output=project.project(us,{project.key(u):assessment(u,v) for u,v in zip(us,values)},REG,['2026-10-23'],ZoneInfo('Europe/Vilnius'),context,'exercise-a')
        self.assertEqual(len(output['narratives']),1)
        self.assertEqual(len(output['narratives'][0]['variants']),2)
        self.assertEqual(output['narratives'][0]['days'],[3])
        self.assertEqual(output['narratives'][0]['evidence'][0]['instance_entities']['place'],'Vilnius')

    def test_old_registry_assessment_requires_reanalysis(self):
        u=unit(1,'Tekstas');a=assessment(u,result([match('N001','Tekstas')]))
        a['registry_version']='old'
        out=project.project([u],{project.key(u):a},REG,['2026-10-23'],ZoneInfo('Europe/Vilnius'),None,'exercise-a')
        self.assertEqual(out['narratives'],[])
        self.assertEqual(out['requires_reanalysis_count'],1)

    def test_exercise_bound_assessments_and_duplicate_source_units(self):
        u=unit(1,'Teiginys');a=assessment(u,result([match('N001','Teiginys')]))
        out=project.project([u,u],{project.key(u):a},REG,['2026-10-23'],ZoneInfo('Europe/Vilnius'),None,'exercise-a')
        self.assertEqual(out['narratives'][0]['days'],[1])
        self.assertEqual(len(out['units']),1)
        a['exercise_id']='previous-exercise'
        self.assertIsNone(project.valid_analysis(u,a,REG))

    def test_candidate_audiences_200_300_unknown_zero(self):
        for size,threshold in ((200,2),(300,3),(None,3)):
            p,a=packet(size);c=project.candidates(p,a,REG,now=NOW)
            self.assertEqual(len(c),1);self.assertEqual(c[0]['required_authors'],threshold)
            self.assertEqual(c[0]['audience'],size);self.assertEqual(c[0]['status'],'candidate')
            self.assertEqual(len(c[0]['evidence']),3)
        p,a=packet(0);self.assertEqual(project.candidates(p,a,REG,now=NOW),[])
        p,a=packet(500);self.assertEqual(project.candidates(p,a,REG,now=NOW),[])
        p,a=packet(200);p['records'][2]['author_id']='1'
        self.assertEqual(len(project.candidates(p,a,REG,now=NOW)),1)
        p['membership_snapshots'][0]['assigned_account_ids']=[str(i) for i in range(300)]
        self.assertEqual(project.candidates(p,a,REG,now=NOW),[])

    def test_copies_one_author_one_thread_reshare_old_and_other_exercise(self):
        for case in ('author','thread','copy','reshare','old','exercise'):
            p,a=packet()
            for u in p['records']:
                if case=='author':u['author_id']='same'
                if case=='thread':u['thread_id']='same'
                if case=='copy':u['text']='Tas pats kartojamas teiginys'
                if case=='reshare':u['kind']='reshare'
                if case=='old':u['published_at']='2026-10-21T10:00:00Z'
                if case=='exercise':u['exercise_id']='exercise-b'
                a[project.key(u)]=assessment(u,result(proposals=[proposal(u['text'])]))
            self.assertEqual(project.candidates(p,a,REG,now=NOW),[],case)
        p,a=packet();p['records']*=20
        c=project.candidates(p,a,REG,now=NOW)[0]
        self.assertEqual(c['unit_count'],3)
        p['exercise_started_at']='2026-10-23T11:00:00Z'
        self.assertEqual(project.candidates(p,a,REG,now=NOW),[])

    def test_missing_membership_dates_does_not_guess_audience(self):
        p,a=packet(200);del p['membership_snapshots'][0]['valid_from']
        self.assertIsNone(project.candidates(p,a,REG,now=NOW)[0]['audience'])

    def test_text_api_multi_claims_do_not_determine_thermometer_direction(self):
        import openai_analysis
        text='NATO neprovokuoja karo. Parama atima išteklius.'
        u=unit('api',text)
        v={"narrative_analysis":result([match('N004','NATO neprovokuoja karo.','oppose'),
                                       match('N030','Parama atima išteklius.')]),
           "direction":"neutral","reason":"Politinių sprendimų kritika be žalingo mechanizmo.",
           "missing_context":"","evidence":text,"reason_codes":["N1"],"verified_claim_source":None}
        raw={"status":"completed","model":"mock-model","output":[{"type":"message","content":[
            {"type":"output_text","text":json.dumps(v)}]}]}
        with patch.object(openai_analysis,'api_key',return_value='mock'), patch.object(openai_analysis,'settings',return_value={}), \
             patch.object(openai_analysis,'pending_claims',return_value=[]), patch.object(openai_analysis.monitoring,'record'), \
             patch.object(openai_analysis,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value=io.BytesIO(json.dumps(raw).encode())
            out=openai_analysis.analyze(u)
        self.assertEqual(out['result']['thermometer_category'],'neutral')
        self.assertEqual(len(out['result']['narrative_analysis']['matches']),2)
        self.assertEqual(out['model_version'],'mock-model')
        self.assertEqual(out['classified_at'],out['analyzed_at'])
        self.assertEqual(out['registry_version'],REG['version'])
        payload=json.loads(opener.return_value.open.call_args.args[0].data)
        self.assertEqual(len(json.loads(payload['input'][0]['content'][0]['text'])['narrative_registry']['types']),35)
        schema=payload['text']['format']['schema']
        def objects(rule):
            if rule.get('type')=='object':
                self.assertFalse(rule['additionalProperties'])
                self.assertEqual(set(rule['required']),set(rule['properties']))
                for child in rule['properties'].values():objects(child)
            if rule.get('type')=='array':objects(rule['items'])
        objects(schema)

    def test_admin_decisions_keep_alias_history_and_topics(self):
        p,a=packet();c=project.candidates(p,a,REG,now=NOW)[0]
        d={'title':c['title'],'claim_template':c['claim_template'],'include_when':'Bendras darbas atkuria pasitikėjimą.',
           'exclude_when':'Vienintelio politinio gelbėtojo teiginys.','topic_id':'T10'}
        value=admin.decide({},c,'approve','test-admin',definition=d)
        self.assertEqual(value['approved_types'][0]['id'],'N036')
        self.assertEqual(value['aliases'][c['id']],'N036')
        self.assertEqual(value['history'][0]['reclassification_required'],True)
        self.assertEqual(len(reg.load()['topics']),15)
        repository=Mock();repository.read.return_value=value
        loaded=reg.load(repository)
        self.assertEqual(len(loaded['types']),36)
        self.assertTrue(loaded['version'].endswith('+1'))
        self.assertEqual(loaded['topics'],REG['topics'])
        merged=admin.decide({},c,'merge','test-admin',target_id='N031')
        self.assertEqual(merged['aliases'][c['id']],'N031')
        rejected=admin.decide({},c,'reject','test-admin')
        self.assertEqual(project.candidates(p,a,REG,now=NOW,decisions=rejected['decisions']),[])
        with self.assertRaises(ValueError):admin.decide(value,c,'approve','test-admin',definition=d)
        with self.assertRaises(ValueError):admin.decide({},c,'approve','test-admin',definition={**d,'topic_id':'invented'})
        repo=Mock();repo.read.return_value=None;repo.scope='test';repo.values={};repo.sql.return_value={'rows':[]}
        with self.assertRaises(ValueError):admin.save_decision(repo,c,'reject','test-admin')
        self.assertIn('WHERE signalas_state.value=',repo.sql.call_args.args[0])

if __name__=='__main__':unittest.main()
