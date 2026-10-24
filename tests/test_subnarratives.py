import copy
import json
import unittest
from unittest.mock import Mock
from zoneinfo import ZoneInfo
import subnarratives as sub
import narrative_registry as registry_api
from narrative_projection import key,candidate_id,project as project_parents


class SubnarrativeTests(unittest.TestCase):
    def setUp(self):
        self.registry=registry_api.load()
        self.proposal={'title':'Informacijos per mažai','claim_template':'Institucijos pateikia per mažai informacijos.',
            'topic_id':'T09','evidence':'Trūksta informacijos.','novelty_reason':'Neteigiama, kad slepiama sąmoningai.', 'nearest_type_ids':['N007']}
        self.identity=candidate_id(None,self.proposal)
        self.candidate={**self.proposal,'id':self.identity,'status':'candidate','exercise_id':None}
        self.db={};self.repo=Mock();self.repo.read=lambda name,default=None:copy.deepcopy(self.db.get(name,default));self.repo.values={}
        def sql(statement,params):
            if self.db.get(params[1])!=json.loads(params[3]):return {'rows':[]}
            self.db[params[1]]=json.loads(params[2]);return {'rows':[['saved']]}
        self.repo.sql=sql
        self.record={'id':'post','source':'pod','exercise_id':None,'kind':'post','author_id':'author',
            'text':'Trūksta informacijos.','published_at':'2026-10-24T10:00:00Z','sourceUrl':'https://pod.test/posts/post'}
        self.assessment={'registry_version':self.registry['version'],'exercise_id':None,
            'result':{'narrative_analysis':{'match_status':'unmatched','matches':[],'proposals':[self.proposal],'uncertainty_reason':''}}}

    def test_explicit_approval_is_stable_and_does_not_change_registry_or_equate_claims(self):
        value=sub.approve(self.repo,[self.candidate],{self.identity:'N007'},actor='exercise administrator')
        definition=value['definitions'][self.identity]
        self.assertEqual(definition['parent_type_id'],'N007')
        self.assertFalse(definition['counts_as_parent_match'])
        self.assertEqual(len(registry_api.load(self.repo)['types']),35)
        self.assertEqual(registry_api.load(self.repo)['version'],self.registry['version'])
        self.assertEqual(sub.approve(self.repo,[self.candidate],{self.identity:'N007'},actor='exercise administrator'),value)
        with self.assertRaises(ValueError):sub.approve(self.repo,[self.candidate],{self.identity:'N022'},actor='exercise administrator')

    def test_projected_parent_and_branch_are_separate_and_source_deduplicated(self):
        value=sub.approve(self.repo,[self.candidate],{self.identity:'N007'},actor='admin')
        registry={**self.registry,'subnarratives':list(value['definitions'].values())}
        records=[self.record,copy.deepcopy(self.record)]
        analyses={key(self.record):self.assessment}
        children=sub.project(records,analyses,registry)
        self.assertEqual(children[0]['unit_count'],1)
        self.assertEqual(children[0]['evidence'][0]['sourceUrl'],self.record['sourceUrl'])
        parent_projection=project_parents(records,analyses,registry,['2026-10-24'],ZoneInfo('Europe/Vilnius'),None,None)
        self.assertEqual(parent_projection['assigned_unit_count'],0)
        parents=sub.attach(parent_projection['narratives'],children,registry,['2026-10-24'],None)
        self.assertEqual(parents[0]['id'],'N007')
        self.assertEqual(parents[0]['days'],[0])
        self.assertEqual(parents[0]['subnarratives'][0]['unit_count'],1)
        self.assertEqual(parents[0]['dailyStances'],[[0,0,0]])
        self.assertEqual(children[0]['evidence'][0]['stance'],'unknown')

    def test_payload_keeps_references_instead_of_duplicated_source_bodies(self):
        branch={'id':'branch','evidence':[{**self.record,'narrative_evidence':'Ištrauka','stance':'unknown'}]}
        public=sub.compact([branch])[0]
        self.assertNotIn('text',public['evidence'][0])
        self.assertNotIn('sourceUrl',public['evidence'][0])
        self.assertEqual(public['evidence'][0]['id'],'post')

    def test_unknown_or_unapproved_proposals_are_never_attached(self):
        self.assertEqual(sub.project([self.record],{key(self.record):self.assessment},self.registry),[])

    def test_user_approved_title_uses_stable_id_and_unchanged_claim_criteria(self):
        definition=next(t for t in self.registry['types'] if t['id']=='N007')
        self.assertEqual(definition['title'],'Sąmoningai slepiama ir nutylima tiesa')
        self.assertIn('sąmoningai',definition['claim_template'])


if __name__=='__main__':unittest.main()
