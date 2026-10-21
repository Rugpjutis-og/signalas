import unittest
from copy import deepcopy

from platform_overview import author_ranking


def posts(author, n=3, comments=0, shares=0, account_type='person', source='pod'):
    result=[]
    for i in range(n):
        result.append({'id':f'{author}-{i}','source':source,'kind':'post','author_id':author,'author_name':author,
            'text':f'{author} originalus tekstas {i}','published_at':'2026-10-19T10:00:00Z',
            'author_classification':{'type':account_type,'verified':True,'provenance':'exercise_administrator'},
            'counter_scope':'lifetime','comments_include_replies':True,'counters':{'comments':comments,'shares':shares},
            'interactions_complete':True,'interactions':[
                {'id':f'c-{i}-{j}','kind':'comment','account_id':'other'} for j in range(comments)]+[
                {'id':f's-{i}-{j}','kind':'share','account_id':'other'} for j in range(shares)],'media':[]})
    return result


class WeightedAuthorsTests(unittest.TestCase):
    def test_weighted_normalized_score_and_creation_priority(self):
        result=author_ranking(posts('creator',5,2,1)+posts('discussed',3,10,4),[])
        a,b=result['items']
        self.assertEqual(a['author_id'],'creator')
        self.assertAlmostEqual(a['score'],80+15*10/30+5*5/12)
        self.assertEqual(b['score'],48+15+5)
        self.assertEqual(a['score_components']['originals'],80)
        self.assertTrue(all(0<=x['score']<=100 for x in result['items']))

    def test_organizations_unknown_unverified_and_conflicting_types_excluded(self):
        records=posts('person')
        for kind in ['organization','business','institution','media','nonprofit','government','brand']:
            records+=posts(kind,10,100,100,kind)
        unknown=posts('unknown');unverified=posts('unverified');conflict=posts('conflict')
        for p in unknown:p.pop('author_classification');p['author_name']=None
        for p in unverified:p['author_classification']['verified']=False;p['author_name']=None
        conflict[0]['author_classification']['type']='institution'
        result=author_ranking(records+unknown+unverified+conflict)
        self.assertEqual([x['author_id'] for x in result['items']],['person'])
        self.assertEqual(result['excluded_organizations'],7)
        self.assertEqual(result['unknown_account_types'],3)
        self.assertEqual(result['normalization_maxima']['originals'],3)
        self.assertEqual(result['items'][0]['score'],80)

    def test_duplicate_content_and_duplicate_actions_do_not_add_score(self):
        records=posts('p',3,1,1)
        copy=deepcopy(records[0]);copy['id']='copy';records.append(copy)
        for p in records:p['interactions']*=3
        item=author_ranking(records)['items'][0]
        self.assertEqual((item['unique_original_posts'],item['duplicate_posts']),(3,1))
        self.assertEqual((item['received_comments'],item['received_shares']),(3,3))
        self.assertEqual(item['score'],100)

    def test_whitespace_duplicates_and_media_only_content(self):
        records=posts('p')
        records[1]['text']='  '+records[0]['text']+' \n'
        self.assertFalse(author_ranking(records)['items'])
        records=posts('p')
        for i,p in enumerate(records):
            p['text']='';p['media']=[{'kind':'image','originalUrl':f'https://pod.test/image-{i}.jpg'}]
        self.assertEqual(author_ranking(records)['items'][0]['unique_original_posts'],3)
        records[0]['media']=[]
        self.assertEqual(author_ranking(records)['status'],'missing_data')

    def test_own_actions_excluded_multiple_comments_are_actions_not_unique_people(self):
        records=posts('p',3,3,2)
        for p in records:
            p['interactions'][0]['account_id']='p'
            p['interactions'][-1]['account_id']='p'
        item=author_ranking(records)['items'][0]
        self.assertEqual((item['received_comments'],item['received_shares']),(6,3))

    def test_missing_counter_or_incomplete_action_data_not_zero(self):
        for mutation in ('missing_counter','missing_actor','truncated','missing_reply_scope'):
            records=posts('p',3,2,1)
            if mutation=='missing_counter':records[0]['counters']['comments']=None
            if mutation=='missing_actor':records[0]['interactions'][0]['account_id']=None
            if mutation=='truncated':records[0]['interactions_complete']=False
            if mutation=='missing_reply_scope':records[0]['comments_include_replies']=False
            self.assertEqual(author_ranking(records)['status'],'missing_data',mutation)
        self.assertEqual(author_ranking(posts('p'))['items'][0]['score'],80)

    def test_source_identity_isolation_and_minimum_originals(self):
        self.assertFalse(author_ranking(posts('p',2,100,100))['items'])
        records=posts('same',3,source='one')+posts('same',4,source='two')
        ranked=author_ranking(records)['items'];self.assertEqual(len(ranked),2)
        self.assertEqual(ranked[0]['source'],'two')
        comments=posts('commenter');reshares=posts('resharer')
        for p in comments:p['kind']='comment'
        for p in reshares:p['kind']='reshare'
        self.assertFalse(author_ranking(comments+reshares)['items'])

    def test_independent_comment_completeness_and_no_audience_denominator(self):
        records=posts('p',3,2,0)
        for p in records:
            p['interactions_complete']=False
            p['interaction_completeness']={'comments':True,'shares':True,'likes':False}
        self.assertEqual(author_ranking(records,[])['items'][0]['received_comments'],6)
        self.assertEqual(author_ranking(records,[])['items'],author_ranking(records,[{'count':250}])['items'])

    def test_contextual_name_rules_and_verified_overrides(self):
        from author_ranking import name_type, account_classification
        organizations = ['poptv.lt','Naujienų agentūra','Uostamiesčio kronikos','Žaliųjų partija',
            'Kauno rajono savivaldybė','Lietuvos šaulių sąjunga','Miesto kultūros centras',
            'Vaikų ligoninė','Universiteto biblioteka','Savanorių asociacija','Pagalbos fondas',
            'UAB Geras rytas','LRT','BNS','Vietos bendruomenė','Šv. Jono parapija','Sporto klubas Ąžuolas']
        for name in organizations:self.assertEqual(name_type(name)[0],'organization',name)
        for name in ['Jonas Jonaitis','Andrej Zelenych','Keleivis Pax 1','Kaunietis','Banga Ranga','Agentas 007','Mantas Šaulys']:
            self.assertEqual(name_type(name)[0],'person',name)
        self.assertEqual(name_type('pax089@diaspora.sauliai.lt')[0],'unknown')
        self.assertEqual(name_type('12345')[0],'unknown')
        record=posts('person')[0];record['author_name']='Organizacijos fondas'
        self.assertEqual(account_classification([record])['type'],'person','verified metadata overrides name heuristic')

if __name__=='__main__':unittest.main()


class MultilingualNamesTests(unittest.TestCase):
    def test_original_language_organization_indicators(self):
        from author_ranking import name_type
        for name in ['North City Council', 'Daily News', 'River Foundation',
                     'Городская газета', 'Министерство обороны', 'Благодійний фонд Допомога',
                     'Міська рада', 'Gazeta Miejska', 'Fundacja Pomoc', 'Rīgas ziņas',
                     'Stadtverwaltung Berlin', 'Universität Hamburg', 'Mairie de Lyon',
                     'Agencia de Noticias', 'Universidad Central']:
            with self.subTest(name=name):
                self.assertEqual(name_type(name)[0], 'organization')
        for name in ['John Smith', 'Jan Kowalski', 'Иван Петров', 'Олена Коваль',
                     'Jānis Bērziņš', 'Élodie Martin', 'José García', 'Berlin Wanderer']:
            with self.subTest(name=name):
                self.assertEqual(name_type(name)[0], 'person')
        self.assertEqual(name_type('未知名稱')[0], 'unknown')

    def test_original_names_and_text_are_not_translated_or_rewritten(self):
        records=posts('Иван Петров')
        for i, p in enumerate(records):
            p.pop('author_classification')
            p['text']=f'Сегодня встреча. Ačiū! {i}'
        report=author_ranking(records)
        self.assertEqual(report['items'][0]['author_name'],'Иван Петров')
        self.assertEqual(report['items'][0]['posts'][0]['text'],records[0]['text'])
