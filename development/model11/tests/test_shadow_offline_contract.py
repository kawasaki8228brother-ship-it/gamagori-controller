"""Wholly synthetic contract/odds/PIT checks; no current or historical real data."""
from copy import deepcopy
from hashlib import sha256
import json
from itertools import permutations
import unittest
from unittest.mock import patch

from shadow_offline_v008.contract_matrix import (audit_past_sample, expanded_inventory, make_fixture,
    make_point_in_time_fixture, mutate_fixture, run_contract_matrix)
from shadow_offline_v008.odds_audit import MAX_RAW_BYTES, TICKETS, audit_odds_raw, audit_odds_snapshot
from model11.shadow_launch.sources import SourceAdapter
from model11.shadow_preparation.capture_review import required_mapping_inventory


def convert(fixture):
    return SourceAdapter(fixture['mapping']).convert(fixture['capture'])


class ContractMatrixTests(unittest.TestCase):
    def test_measured_inventory_is_264_patterns_and_all_boats_are_expanded(self):
        inventory = required_mapping_inventory()
        self.assertEqual(len(inventory), 264)
        self.assertEqual(len({item['local_target'] for item in inventory}), 264)
        expanded = expanded_inventory()
        self.assertEqual(len(expanded), 554)
        self.assertEqual(len({item['path'] for item in expanded}), 554)
        self.assertEqual(sum(item['applicability'] != 'PRESENT_IN_SYNTHETIC_FIXTURE' for item in expanded), 2)
        self.assertEqual({item['scope'] for item in inventory},
            {'ONE_CAPTURE', 'EACH_INCLUDED_BOAT', 'ONE_FULL_FIELD_TICKET', 'EACH_CAPTURE_HISTORY_ENTRY'})

    def test_full_missing_null_wrong_type_nonfinite_matrix_holds_without_imputation(self):
        report = run_contract_matrix(include_rows=True)
        self.assertEqual(report['software_check'], 'PASS', report['failures'])
        self.assertEqual(report['inventory_patterns'], 264)
        self.assertEqual(report['materialized_targets'], 554)
        self.assertEqual(report['attempts'], 2216)
        self.assertEqual(report['outcomes'], {'HOLD': 2208, 'NOT_APPLICABLE_CONDITIONAL_PROFILE': 8})
        self.assertEqual(len(report['rows']), 2216)
        self.assertTrue(report['input_unchanged'])
        self.assertEqual(report['actual_official_mapping'], 'BLOCKED_EXTERNAL')
        self.assertFalse(report['production_go'])

    def test_synthetic_profile_does_not_invent_private_review_hashes(self):
        fixture = make_fixture()
        self.assertNotIn('review_evidence', fixture['mapping'])
        conditional = [r for r in expanded_inventory(fixture) if r['applicability'].startswith('PRIVATE_REVIEW')]
        self.assertEqual(len(conditional), 2)
        self.assertTrue(all(item['path'].startswith('/mapping/review_evidence/') for item in conditional))

    def test_future_feature_times_motor_identity_and_state_absence_are_not_filled(self):
        fixture = make_fixture()
        untouched = deepcopy(fixture)
        for field in ('acquired_at', 'available_at', 'revision_at'):
            altered = mutate_fixture(fixture, '/raw/boats/0/features/st/'+field, 'replace', replacement='2099-01-01T23:59:00+09:00')
            self.assertEqual(convert(altered)['status'], 'HOLD')
        for path, value in [('/raw/boats/0/motor_identity/effective_at', '2099-01-01T23:59:00+09:00'),
                            ('/raw/boats/0/features/motor/motor_version', 'SYNTHETIC_OTHER_VERSION'),
                            ('/raw/boats/0/fl/value', 0), ('/raw/boats/0/scratched/value', None)]:
            self.assertEqual(convert(mutate_fixture(fixture, path, 'replace', replacement=value))['status'], 'HOLD')
        self.assertEqual(fixture, untouched)
        self.assertEqual(convert(mutate_fixture(fixture, '/raw/boats/0/features/motor/value', 'replace', replacement=0.0))['status'], 'READY')
        self.assertEqual(convert(fixture)['status'], 'READY')

    def test_fl_is_a_research_warning_and_active_scratch_is_a_distinct_hold(self):
        fixture=make_fixture()
        fl=convert(mutate_fixture(fixture,'/raw/boats/0/fl/value','replace',replacement=True))
        self.assertEqual(fl['status'],'READY')
        self.assertIn('FL_PRESENT_RESEARCH_INPUT',fl['source_evidence']['raw_warning_codes'])
        self.assertFalse(fl['production_go'])
        scratch=convert(mutate_fixture(fixture,'/raw/boats/0/scratched/value','replace',replacement=True))
        self.assertEqual(scratch['status'],'HOLD')
        self.assertIn('SCRATCH_ACTIVE_MISMATCH',scratch['reasons'])

    def test_adapter_and_diagnostic_perform_no_source_network_database_or_file_io(self):
        fixture = make_fixture()
        targets = expanded_inventory(fixture)
        sample = make_point_in_time_fixture()
        with patch('builtins.open', side_effect=AssertionError('NO_FILE_IO')), \
             patch('socket.socket', side_effect=AssertionError('NO_NETWORK')), \
             patch('sqlite3.connect', side_effect=AssertionError('NO_DATABASE')):
            self.assertEqual(convert(fixture)['status'], 'READY')
            self.assertEqual(audit_past_sample(sample)['software_check'], 'PASS')
            self.assertEqual(len(targets), 554)


class OddsAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = make_fixture()
        self.raw = json.loads(self.fixture['capture']['payload_bytes'])['invented_raw']
        self.snapshot = self.raw['odds_snapshot']
    def audit(self, snapshot, **kwargs):
        return audit_odds_snapshot(snapshot, prediction_at=self.raw['prediction_at'],
            deadline=self.raw['deadline']['value'], snapshot_role=kwargs.pop('snapshot_role','PRE_DEADLINE'), **kwargs)
    def test_complete_120_payout_snapshot_observes_age_without_adopting_freshness_threshold(self):
        before = deepcopy(self.snapshot)
        result = self.audit(self.snapshot)
        self.assertEqual(len(TICKETS), 120)
        self.assertEqual(result['status'], 'CONTRACT_CLAIMS_CONSISTENT_FRESHNESS_OPEN')
        self.assertTrue(result['structural_pass'])
        self.assertTrue(result['temporal_pass'])
        self.assertEqual(result['age_seconds']['acquired_at'], 30.0)
        self.assertIsNone(result['freshness_max_age_seconds'])
        self.assertEqual(result['freshness_status'], 'UNVERIFIED_NO_APPROVED_MAX_AGE')
        self.assertFalse(result['market_execution_eligible'])
        self.assertFalse(result['production_go'])
        self.assertEqual(self.snapshot, before)
    def test_all_120_missing_and_invalid_tickets_fail_and_never_use_final_odds(self):
        for ticket in TICKETS:
            missing = deepcopy(self.snapshot);del missing['odds'][ticket]
            result = self.audit(missing)
            self.assertEqual(result['status'], 'HOLD')
            self.assertIn('EXACT_DISTINCT_FULL_120_DOMAIN_REQUIRED', result['reasons'])
        for value in (None, True, False, 0, -1, float('nan'), float('inf'), '100'):
            bad = deepcopy(self.snapshot);bad['odds']['1-2-3'] = value
            self.assertEqual(self.audit(bad)['status'], 'HOLD')
        for role in (None, 'FINAL', 'POST_RACE'):
            self.assertEqual(self.audit(self.snapshot, snapshot_role=role)['status'], 'HOLD')
    def test_wrong_unit_missing_times_future_revision_and_unknown_time_hold(self):
        for field in ('acquired_at','available_at','revision_at'):
            future = deepcopy(self.snapshot);future[field] = '2099-01-01T13:01:00+09:00'
            self.assertIn('FUTURE_OR_POST_LOCK_ODDS_FORBIDDEN', self.audit(future)['reasons'])
            unknown = deepcopy(self.snapshot);unknown[field] = None
            self.assertIn('ODDS_TIME_UNKNOWN_OR_INVALID', self.audit(unknown)['reasons'])
        wrong = deepcopy(self.snapshot);wrong['unit']='probability'
        self.assertEqual(self.audit(wrong)['status'], 'HOLD')
        very_old = deepcopy(self.snapshot)
        for field in ('acquired_at','available_at','revision_at'):very_old[field]='2098-12-01T00:00:00+09:00'
        result=self.audit(very_old)
        self.assertEqual(result['freshness_status'],'UNVERIFIED_NO_APPROVED_MAX_AGE')
        self.assertGreater(result['age_seconds']['acquired_at'], 86400)
        self.assertFalse(result['market_execution_eligible'])
    def test_raw_sha_duplicate_keys_and_nonfinite_json_are_rejected_without_echo(self):
        body=json.dumps(self.snapshot,sort_keys=True,separators=(',',':')).encode()
        def audit_raw(data, expected=None):
            return audit_odds_raw(data,expected_sha256=sha256(data).hexdigest() if expected is None else expected,
                prediction_at=self.raw['prediction_at'],deadline=self.raw['deadline']['value'],snapshot_role='PRE_DEADLINE')
        self.assertEqual(audit_raw(body)['status'],'CONTRACT_CLAIMS_CONSISTENT_FRESHNESS_OPEN')
        self.assertEqual(audit_raw(body,'0'*64)['reasons'],['ORIGINAL_BYTE_SHA_MISMATCH_OR_UNKNOWN'])
        duplicate=body.replace(b'"odds":{',b'"odds":{"1-2-3":99,',1)
        self.assertEqual(audit_raw(duplicate)['status'],'HOLD')
        nonfinite=body.replace(b'"1-2-3":',b'"PRIVATE_SECRET":NaN,"1-2-3":',1)
        report=audit_raw(nonfinite)
        self.assertEqual(report['status'],'HOLD')
        self.assertNotIn('PRIVATE_SECRET',json.dumps(report))
    def test_empty_and_oversized_originals_stop_before_json_or_hash_acceptance(self):
        for raw in (b'', b'x' * (MAX_RAW_BYTES + 1)):
            report=audit_odds_raw(raw,expected_sha256='0'*64,prediction_at=self.raw['prediction_at'],
                deadline=self.raw['deadline']['value'],snapshot_role='PRE_DEADLINE')
            self.assertEqual(report['status'],'HOLD')
            self.assertEqual(report['reasons'],['ORIGINAL_BYTES_EMPTY_OR_CAPTURE_LIMIT_EXCEEDED'])
            self.assertIsNone(report['raw_sha256'])

    def test_dictionary_cannot_claim_raw_duplicate_detection_or_authenticity(self):
        report=self.audit(self.snapshot)
        self.assertEqual(report['raw_duplicate_scope'],'DICT_DOMAIN_ONLY_RAW_BYTES_REQUIRED')
        self.assertEqual(report['external_authenticity'],'UNVERIFIED')


class PastInformationTests(unittest.TestCase):
    def test_snapshot_is_valid_only_invented_candidate_and_original_unchanged(self):
        sample=make_point_in_time_fixture();before=deepcopy(sample)
        report=audit_past_sample(sample)
        self.assertEqual(report['software_check'],'PASS')
        self.assertTrue(report['feature_eligible'])
        self.assertTrue(report['market_eligible'])
        self.assertEqual(report['origin_proof'],'SELF_REPORTED_ONLY')
        self.assertEqual(report['real_input_status'],'HOLD')
        self.assertEqual(sample,before)
    def test_all_boat_feature_late_times_and_post_preservation_revisions_hold(self):
        original=make_point_in_time_fixture()
        for index in range(30):
            for field in ('acquired_at','available_at','revision_at'):
                sample=deepcopy(original);sample['features'][index][field]='2099-01-01T14:00:00+09:00'
                report=audit_past_sample(sample)
                self.assertFalse(report['feature_eligible'])
                self.assertIn('FEATURE_UPDATED_OR_AVAILABLE_AFTER_AS_OF',report['feature_reasons'])
        sample=deepcopy(original);sample['features'][0]['revision_at']='2099-01-01T12:54:50+09:00'
        self.assertIn('FEATURE_SOURCE_TIME_AFTER_SNAPSHOT_PRESERVATION',audit_past_sample(sample)['reasons'])
    def test_missing_or_final_odds_are_not_substituted_and_result_features_are_rejected(self):
        for kind in (None,'FINAL','POST_RACE'):
            sample=make_point_in_time_fixture()
            if kind is None:sample['odds']=None
            else:sample['odds']['kind']=kind
            report=audit_past_sample(sample)
            self.assertFalse(report['market_eligible'])
            self.assertFalse(report['expected_value_eligible'])
        sample=make_point_in_time_fixture();sample['features'][0]['payout_per_100']=100
        self.assertFalse(audit_past_sample(sample)['feature_eligible'])
    def test_training_labels_and_feature_times_must_be_available_before_fit(self):
        source=make_point_in_time_fixture()
        source['training_context']={'normalizer_fit_cutoff':'2098-12-31T20:00:00+09:00',
            'model_fit_cutoff':'2098-12-31T21:00:00+09:00',
            'training_rows':[{'prediction_at':'2098-12-30T12:55:00+09:00',
                'feature_available_at':'2098-12-30T12:54:00+09:00','label_available_at':'2098-12-30T13:10:00+09:00'}]}
        self.assertEqual(audit_past_sample(source)['training_context_status'],'CLAIMS_CONSISTENT')
        for kind in ('late_feature','late_label','fit_at_prediction'):
            sample=deepcopy(source);context=sample['training_context']
            if kind=='late_feature':context['training_rows'][0]['feature_available_at']='2098-12-30T13:01:00+09:00'
            elif kind=='late_label':context['training_rows'][0]['label_available_at']='2099-01-01T11:00:00+09:00'
            else:context['model_fit_cutoff']=sample['as_of']
            report=audit_past_sample(sample)
            self.assertEqual(report['status'],'HOLD')
            self.assertEqual(report['training_context_status'],'HOLD')

    def test_actual_or_inconsistent_classification_is_held_without_relabel(self):
        for classification,flag in [('PRIVATE_REAL',False),('SYNTHETIC_ONLY',False),('HQ14_PRIVATE_OFFLINE',False)]:
            sample=make_point_in_time_fixture();sample['data_classification']=classification;sample['synthetic']=flag
            report=audit_past_sample(sample)
            self.assertEqual(report['status'],'HOLD')
            self.assertFalse(report['production_go'])


if __name__ == '__main__':unittest.main()
