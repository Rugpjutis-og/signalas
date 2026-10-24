import copy
import unittest
from unittest.mock import Mock, patch
from scenario_supplement import context_digest
import exercise_rule as rule


class ExerciseRuleTests(unittest.TestCase):
    def setUp(self):
        self.unit = {'source': 'exercise.test', 'id': 'one', 'author_id': 'guid', 'text': 'Ateikite į mitingą.', 'exercise_id': 'training'}
        self.state = {'revision': 'test', 'source': 'exercise.test', 'exercise_id': 'training',
                      'base_context_digest': context_digest(None), 'account_ids': {'synthetic': 'guid'},
                      'scoring_rule': {'id': rule.ID, 'enabled': True, 'effective_at': '2026-10-24T18:00:00Z'}}
        self.repo = Mock()
        self.repo.read.side_effect = lambda name, default=None: copy.deepcopy(self.state) if name == 'exercise-account-context.json' else None
        self.repo.supplement_eligible.return_value = True
        self.result = {'direction': 'neutral', 'reason_codes': ['N1'], 'reason': 'Taikus kvietimas.',
                       'evidence': self.unit['text'], 'missing_context': ''}

    def test_rule_is_prospective_exact_scoped_and_disabled_for_old_review(self):
        self.assertEqual(rule.for_unit(self.repo, self.unit)['id'], rule.ID)
        for changes in ({'source': 'other'}, {'author_id': 'other'}, {'exercise_id': 'other'}):
            self.assertIsNone(rule.for_unit(self.repo, {**self.unit, **changes}))
        self.assertIsNone(rule.for_unit(self.repo, self.unit, thermometer_only=True))
        self.repo.supplement_eligible.return_value = False
        self.assertIsNone(rule.for_unit(self.repo, self.unit), 'historic AI/manual decisions are excluded')
        self.repo.supplement_eligible.assert_called_with(self.unit, self.state['scoring_rule']['effective_at'])

    def test_application_is_attributed_and_retains_independent_direction(self):
        application = rule.apply(self.result, rule.for_unit(self.repo, self.unit), rule.TRIGGERS[1], self.unit)
        self.assertEqual(self.result['direction'], 'destabilizing')
        self.assertEqual(self.result['reason_codes'], ['D5'])
        self.assertEqual(application['content_direction'], 'neutral')
        self.assertEqual(application['provenance'], 'exercise_organizer')
        self.assertIn('organizatoriaus pratybų taisyklę', self.result['reason'])

    def test_unrelated_uncertain_and_unread_media_cannot_trigger_rule(self):
        scoring = rule.for_unit(self.repo, self.unit)
        self.assertIsNone(rule.apply(self.result, scoring, 'none', self.unit))
        self.assertEqual(self.result['direction'], 'neutral')
        self.result.update(direction='needs_review', reason_codes=[])
        self.assertIsNone(rule.apply(self.result, scoring, rule.TRIGGERS[1], self.unit))
        self.assertEqual(self.result['direction'], 'needs_review')

    def test_evidence_must_be_own_text_or_own_reviewed_image(self):
        self.result['evidence'] = 'Kito autoriaus komentaras'
        self.assertIsNone(rule.apply(self.result, rule.for_unit(self.repo, self.unit), rule.TRIGGERS[1], self.unit))
        self.assertEqual(self.result['direction'], 'needs_review')
        self.assertEqual(self.result['reason_codes'], [])

    def test_normal_api_schema_detects_trigger_then_server_attributes_scenario_category(self):
        import io, json
        import openai_analysis
        unit = {**self.unit, 'kind': 'post', 'media': [], 'published_at': '2026-10-24T18:01:00Z'}
        decoded = {**self.result, 'exercise_rule_trigger': rule.TRIGGERS[1], 'narrative_analysis': {
            'match_status': 'no_narrative', 'matches': [], 'proposals': [], 'uncertainty_reason': ''}}
        response = {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(decoded)}]}]}
        with patch('exercise_rule.for_unit', return_value=rule.for_unit(self.repo, self.unit)), \
             patch('exercise_accounts.for_unit', return_value=None), patch('scenario_supplement.for_unit', return_value=[]), \
             patch.object(openai_analysis, 'pending_claims', return_value=[]), \
             patch.object(openai_analysis, 'api_key', return_value='synthetic'), \
             patch.object(openai_analysis, 'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
            result = openai_analysis.analyze(unit)
            sent = json.loads(opener.return_value.open.call_args.args[0].data)
            self.assertIn('exercise_rule_trigger', sent['text']['format']['schema']['required'])
            self.assertEqual(result['result']['thermometer_category'], 'destabilizing')
            self.assertEqual(result['result']['reason_codes'], ['D5'])
            self.assertEqual(result['exercise_rule_application']['content_direction'], 'neutral')
            self.assertNotIn('exercise_rule_trigger', result['result'])

    def test_historic_rule_requires_explicit_saved_authorization_and_exact_request(self):
        self.repo.supplement_eligible.return_value = False
        self.assertIsNone(rule.for_unit(self.repo, self.unit, thermometer_only=True, review_rule_id=rule.ID))
        self.state['scoring_rule']['historical_review_enabled'] = True
        self.assertEqual(rule.for_unit(self.repo, self.unit, thermometer_only=True, review_rule_id=rule.ID)['id'], rule.ID)
        self.assertIsNone(rule.for_unit(self.repo, self.unit, thermometer_only=True, review_rule_id='other'))
        self.assertIsNone(rule.for_unit(self.repo, {**self.unit, 'author_id': 'other'}, thermometer_only=True, review_rule_id=rule.ID))

    def test_historical_api_accepts_valid_extra_trigger_without_schema_failure(self):
        import io,json,openai_analysis
        unit={**self.unit,'kind':'post','media':[],'published_at':'2026-10-24T18:01:00Z'}
        decoded={**self.result,'exercise_rule_trigger':rule.TRIGGERS[1]}
        response={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(decoded)}]}]}
        with patch('exercise_rule.for_unit',return_value={'id':rule.ID,'provenance':'exercise_organizer'}),patch('exercise_accounts.for_unit',return_value=None),patch('scenario_supplement.for_unit',return_value=[]),patch.object(openai_analysis,'api_key',return_value='synthetic'),patch.object(openai_analysis,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value=io.BytesIO(json.dumps(response).encode())
            result=openai_analysis.analyze(unit,thermometer_only=True,scoring_rule_review=rule.ID)
            self.assertEqual(result['result']['thermometer_category'],'destabilizing')
            self.assertTrue(result['exercise_rule_application']['applied'])

    def content_rule(self):
        self.state['scoring_rule']['id'] = rule.CONTENT_RULE_ID
        return rule.for_unit(self.repo, self.unit)

    def test_new_content_rule_is_explicitly_versioned_and_does_not_replace_legacy(self):
        legacy = rule.for_unit(self.repo, self.unit)
        self.assertEqual(rule.triggers(legacy), rule.TRIGGERS)
        self.assertEqual(rule.instructions(legacy), rule.INSTRUCTIONS)
        scoring = self.content_rule()
        self.assertEqual(scoring['id'], rule.CONTENT_RULE_ID)
        self.assertEqual(rule.triggers(scoring), rule.CONTENT_TRIGGERS)
        self.assertIn('kasdien', rule.instructions(scoring))
        self.assertIsNone(rule.for_unit(self.repo, self.unit, thermometer_only=True, review_rule_id=rule.ID))
        self.state['scoring_rule']['historical_review_enabled'] = True
        self.assertIsNone(rule.for_unit(self.repo, self.unit, thermometer_only=True, review_rule_id=rule.ID))
        self.assertIsNotNone(rule.for_unit(self.repo, self.unit, thermometer_only=True, review_rule_id=rule.CONTENT_RULE_ID))

    def test_content_rule_overrides_direction_but_preserves_independent_assessment(self):
        scoring = self.content_rule()
        for original in ('neutral', 'stabilizing', 'destabilizing'):
            result = {**self.result, 'direction': original}
            application = rule.apply(result, scoring, 'not_unrelated_daily_life', self.unit)
            self.assertEqual(result['direction'], 'destabilizing')
            self.assertEqual(application['content_direction'], original)
            self.assertEqual(application['id'], rule.CONTENT_RULE_ID)
            self.assertEqual(result['reason_codes'], ['D5'])

    def test_content_rule_daily_exception_preserves_normal_assessment(self):
        scoring = self.content_rule()
        unit = {**self.unit, 'text': 'Šiandien kepiau pyragą.'}
        for original in ('neutral', 'stabilizing', 'destabilizing'):
            result = {**self.result, 'direction': original, 'evidence': unit['text']}
            before = copy.deepcopy(result)
            self.assertIsNone(rule.apply(result, scoring, 'unrelated_daily_life', unit))
            self.assertEqual(result, before)

    def test_content_rule_uncertainty_missing_media_and_foreign_evidence_do_not_force(self):
        scoring = self.content_rule()
        for trigger in ('unclear', 'none', 'unknown'):
            result = copy.deepcopy(self.result)
            self.assertIsNone(rule.apply(result, scoring, trigger, self.unit))
            self.assertEqual(result['direction'], 'needs_review')
        result = {**self.result, 'direction': 'needs_review', 'reason_codes': []}
        self.assertIsNone(rule.apply(result, scoring, 'not_unrelated_daily_life', self.unit))
        self.assertEqual(result['direction'], 'needs_review')
        result = {**self.result, 'evidence': 'Kito autoriaus politinis komentaras'}
        self.assertIsNone(rule.apply(result, scoring, 'not_unrelated_daily_life', self.unit))
        self.assertEqual(result['direction'], 'needs_review')

    def test_content_rule_does_not_expand_account_scope_or_bypass_existing_assessments(self):
        self.content_rule()
        for changes in ({'source': 'other'}, {'author_id': 'other'}, {'exercise_id': 'other'}):
            self.assertIsNone(rule.for_unit(self.repo, {**self.unit, **changes}))
        self.repo.supplement_eligible.return_value = False
        self.assertIsNone(rule.for_unit(self.repo, self.unit))

    def test_content_rule_api_uses_its_own_schema_and_attributes_override(self):
        import io, json, openai_analysis
        scoring = self.content_rule()
        unit = {**self.unit, 'text': 'Institucija paskelbė sprendimą.', 'kind': 'post',
                'media': [], 'published_at': '2026-10-25T07:00:00Z'}
        decoded = {**self.result, 'evidence': unit['text'],
                   'exercise_rule_trigger': 'not_unrelated_daily_life', 'narrative_analysis': {
                       'match_status': 'no_narrative', 'matches': [], 'proposals': [], 'uncertainty_reason': ''}}
        response = {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(decoded)}]}]}
        with patch('exercise_rule.for_unit', return_value=scoring), \
             patch('exercise_accounts.for_unit', return_value=None), \
             patch('scenario_supplement.for_unit', return_value=[]), \
             patch.object(openai_analysis, 'pending_claims', return_value=[]), \
             patch.object(openai_analysis, 'api_key', return_value='synthetic'), \
             patch.object(openai_analysis, 'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
            result = openai_analysis.analyze(unit)
            sent = json.loads(opener.return_value.open.call_args.args[0].data)
            self.assertEqual(sent['text']['format']['schema']['properties']['exercise_rule_trigger']['enum'], list(rule.CONTENT_TRIGGERS))
            self.assertIn('visas turinys', sent['instructions'])
            self.assertEqual(result['result']['thermometer_category'], 'destabilizing')
            self.assertEqual(result['exercise_rule_application']['content_direction'], 'neutral')
