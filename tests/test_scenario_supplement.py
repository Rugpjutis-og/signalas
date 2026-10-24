import io
import json
import unittest
from unittest.mock import Mock, patch

import openai_analysis
import scenario_supplement as supplement
from cloud_repository import Repository


class SupplementTests(unittest.TestCase):
    def setUp(self):
        self.context = {'initialSituation': 'Pratybos.', 'confirmedFacts': 'Faktai.', 'nameMappings': []}
        self.value = {'id': 'test-valare', 'text': 'Sintetinis scenarijaus patikslinimas.',
                      'effective_at': '2026-10-24T12:00:00Z',
                      'base_context_digest': supplement.context_digest(self.context)}
        self.unit = {'source': 'test', 'id': 'post', 'kind': 'post', 'text': 'Prašau paaiškinti.',
                     'published_at': '2026-10-24T10:00:00Z', 'media': []}
        self.repo = Mock()
        self.repo.read.side_effect = lambda key: self.value if key == supplement.STATE else self.context

    def test_only_eligible_units_receive_supplement_and_base_binding_stays_unchanged(self):
        original = json.dumps(self.context, sort_keys=True)
        self.repo.supplement_eligible.return_value = False
        self.assertEqual(supplement.for_unit(self.repo, self.unit, self.context), [])
        self.repo.supplement_eligible.return_value = True
        self.assertEqual(supplement.for_unit(self.repo, self.unit, self.context),
                         [{'id': self.value['id'], 'text': self.value['text']}])
        self.repo.supplement_eligible.assert_called_with(self.unit, self.value['effective_at'])
        self.assertEqual(json.dumps(self.context, sort_keys=True), original)
        self.repo.write.assert_not_called()
        self.assertEqual(supplement.for_unit(self.repo, self.unit, {**self.context, 'confirmedFacts': 'Kitos pratybos'}), [])
        self.assertNotIn('base_context_digest', supplement.public(self.repo)[0])

    def test_no_supplement_is_legacy_compatible(self):
        self.repo.read.return_value = None
        self.repo.read.side_effect = None
        self.assertEqual(supplement.for_unit(self.repo, self.unit, self.context), [])
        self.assertEqual(supplement.public(self.repo), [])
        self.repo.supplement_eligible.assert_not_called()

    def test_eligibility_read_is_bounded_and_includes_prior_ai_and_manual_decisions(self):
        repo = Repository({'SIGNALAS_DATABASE_URL': 'unused'})
        repo.sql = Mock(return_value={'rows': [['f']]})
        self.assertFalse(repo.supplement_eligible(self.unit, self.value['effective_at']))
        statement, params = repo.sql.call_args.args
        self.assertIn("a->>'analysis_executed'='true'", statement)
        self.assertIn('thermometer-reviews.json', statement)
        self.assertIn('timestamptz < $5', statement)
        self.assertIn("a->'exercise_id'", statement)
        self.assertNotIn('jsonb_agg', statement)
        self.assertIn(self.value['effective_at'], params)
        repo.sql.return_value = {'rows': [['t']]}
        self.assertTrue(repo.supplement_eligible(self.unit, self.value['effective_at']))

    def test_both_analysis_modes_send_clarification_but_keep_original_context_binding(self):
        normal = {'direction': 'neutral', 'reason': 'Klausimas.', 'reason_codes': ['N1'],
                  'evidence': '', 'missing_context': '', 'narrative_analysis': {
                  'match_status': 'no_narrative', 'matches': [], 'proposals': [], 'uncertainty_reason': ''}}
        for thermometer_only in (False, True):
            decoded = dict(normal)
            if thermometer_only:
                decoded.pop('narrative_analysis')
            response = {'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps(decoded)}]}]}
            values = [{'id': self.value['id'], 'text': self.value['text']}]
            with patch('scenario_supplement.for_unit', return_value=values), \
                 patch.object(openai_analysis, 'api_key', return_value='synthetic'), \
                 patch.object(openai_analysis, 'pending_claims', return_value=[]), \
                 patch.object(openai_analysis, 'build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
                result = openai_analysis.analyze(self.unit, self.context, thermometer_only=thermometer_only)
                sent = json.loads(opener.return_value.open.call_args.args[0].data)
                prepared = json.loads(sent['input'][1]['content'][0]['text'])['analysis_input']
                self.assertEqual(prepared['scenario_supplements'], values)
                self.assertEqual(result['exercise_context'], self.context)
                self.assertEqual(result['scenario_supplement_ids'], [self.value['id']])
                self.assertIn('paminėjimas, citavimas, klausimas ar paneigimas nėra jos palaikymas', sent['instructions'])
