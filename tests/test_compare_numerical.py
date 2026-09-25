#!/usr/bin/env python3
"""Synthetic complete-evidence fixtures; no NumPy, compilation or transforms."""
import argparse
import copy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gate',ROOT/'compare_numerical.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
MANIFEST = None


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bridct-runtime-gate-')
        self.root = Path(self.tmp.name)
        self.parent = self.root/'parent';self.parent.mkdir()
        self.candidate = self.root/'candidate';self.candidate.mkdir()
        self.manifest = self.root/'manifest.json'
        self.manifest.write_bytes(MANIFEST.read_bytes())
        self.rows = []
        boundary = 0
        for key in sorted(gate.expected_keys(self.manifest)):
            row = dict(zip(gate.KEY_FIELDS,key))
            fail = False
            if row['domain'] not in ('core','shapes'):
                fail = boundary < 90
                boundary += 1
            row.update(error=None if fail else 1e-7,finite=not fail,guards=True,
                       unchanged=True,return_code=0,passed=not fail)
            self.rows.append(row)
        self.summary = dict(status='PASS',host='fixture-host',host_machine='x86_64',
            package_version='0.2.0-dev.3',execution='Synthetic fixture, not measured evidence',
            shapes=64,shape_checks=1152,corpus_core_checks=1260,boundary_checks=162,
            boundary_failures=90,required_failures=0,max_required_error=1e-7,
            guards_and_input_preservation=True,runner_sha256='1'*64,
            shared_libraries={'library.so':'2'*64})
        self.write(self.parent);self.write(self.candidate)
        self.parent_config=self.root/'parent.config'
        self.candidate_config=self.root/'candidate.config'
        self.parent_config.write_text('clang -std=c11 -O3 -march=x86-64 -mno-avx -mno-fma\n')
        self.candidate_config.write_text('clang -std=c11 -DBRIDCT_COMPILED_AVX2=1 -O3 -march=x86-64 -mno-avx -mno-fma\n')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self,directory,rows=None,summary=None):
        with (directory/'checks.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=gate.FIELDS)
            writer.writeheader();writer.writerows(self.rows if rows is None else rows)
        (directory/'result.json').write_text(json.dumps(self.summary if summary is None else summary)+'\n')

    def run_gate(self):
        return gate.compare(self.parent,self.candidate,self.manifest,self.parent_config,self.candidate_config)

    def rejected(self,pattern):
        with self.assertRaisesRegex(gate.GateError,pattern):self.run_gate()

    def test_valid_complete_pair(self):
        result=self.run_gate()
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['directions_per_arm'],2574)
        self.assertTrue(result['build_configuration']['checked'])

    def test_ooura_runtime_pair(self):
        self.candidate_config.write_text(self.candidate_config.read_text().replace('-O3','-DBRIDCT_COMPILED_OOURA16_ALL=1 -O3'))
        result=self.run_gate()
        self.assertEqual(result['build_configuration']['permitted_difference'],['-DBRIDCT_COMPILED_AVX2=1','-DBRIDCT_COMPILED_OOURA16_ALL=1'])

    def test_ooura_duplicate_rejected(self):
        self.candidate_config.write_text(self.candidate_config.read_text().replace('-O3','-DBRIDCT_COMPILED_OOURA16_ALL=1 -DBRIDCT_COMPILED_OOURA16_ALL=1 -O3'))
        self.rejected('Ooura16 macro duplicated')

    def test_unknown_runtime_macro_rejected(self):
        self.candidate_config.write_text(self.candidate_config.read_text().replace('-O3','-DBRIDCT_COMPILED_UNKNOWN=1 -O3'))
        self.rejected('compiler/options differ')

    def test_new_boundary_error_stops(self):
        row=next(r for r in self.rows if r['domain'] not in ('core','shapes') and r['passed'])
        row.update(error=1e-3,passed=False)
        self.summary['boundary_failures']=91;self.write(self.candidate)
        self.rejected('Parent-pass to candidate-fail')

    def test_new_boundary_overflow_stops(self):
        row=next(r for r in self.rows if r['domain'] not in ('core','shapes') and r['passed'])
        row.update(error=None,finite=False,passed=False)
        self.summary['boundary_failures']=91;self.write(self.candidate)
        self.rejected('Parent-pass to candidate-fail')

    def test_boundary_recovery_allowed(self):
        row=next(r for r in self.rows if not r['passed'])
        row.update(error=1e-7,finite=True,passed=True)
        self.summary['boundary_failures']=89;self.write(self.candidate)
        self.assertEqual(self.run_gate()['candidate_recoveries'],1)

    def test_core_error_stops(self):
        row=next(r for r in self.rows if r['domain']=='core')
        row.update(error=1e-3,passed=False);self.write(self.candidate)
        self.rejected('Required numerical direction failed')

    def test_missing_key(self):
        self.write(self.candidate,self.rows[:-1]);self.rejected('Incomplete direction')

    def test_duplicate_key(self):
        self.write(self.candidate,self.rows+[self.rows[0]]);self.rejected('Duplicate direction')

    def test_unknown_key(self):
        self.rows[0]['case']='invented';self.write(self.candidate);self.rejected('Unexpected direction')

    def test_bad_boolean(self):
        self.rows[0]['passed']='true';self.write(self.candidate);self.rejected('Invalid CSV boolean')

    def test_nan_error(self):
        self.rows[0]['error']='nan';self.write(self.candidate);self.rejected('finite and nonnegative')

    def test_infinite_error(self):
        self.rows[0]['error']='1e999';self.write(self.candidate);self.rejected('finite and nonnegative')

    def test_missing_error_on_finite_result(self):
        self.rows[0]['error']=None;self.write(self.candidate);self.rejected('Finite/error fields')

    def test_false_pass_flag(self):
        self.rows[0]['passed']=False;self.write(self.candidate);self.rejected('Passed flag disagrees')

    def test_structural_failure(self):
        self.rows[0]['guards']=False;self.write(self.candidate);self.rejected('Structural check failed')

    def test_parent_rejected(self):
        self.summary['status']='FAILED';self.write(self.parent);self.rejected('must be PASS')

    def test_candidate_count_mismatch(self):
        self.summary['boundary_checks']=90;self.write(self.candidate);self.rejected('count disagrees')

    def test_maximum_mismatch(self):
        self.summary['max_required_error']=1e-8;self.write(self.candidate);self.rejected('Maximum required error disagrees')

    def test_nonfinite_json(self):
        self.summary['max_required_error']=float('nan');self.write(self.candidate);self.rejected('Non-finite JSON')

    def test_duplicate_json_key(self):
        path=self.candidate/'result.json';path.write_text('{"status":"PASS",'+path.read_text()[1:])
        self.rejected('Duplicate JSON key')

    def test_compiler_options_mismatch(self):
        self.candidate_config.write_text(self.candidate_config.read_text().replace('-O3','-O2'))
        self.rejected('compiler/options differ')

    def test_parent_runtime_enabled(self):
        self.parent_config.write_bytes(self.candidate_config.read_bytes())
        self.rejected('Parent config must disable')

    def test_candidate_runtime_disabled(self):
        self.candidate_config.write_bytes(self.parent_config.read_bytes())
        self.rejected('Candidate config must enable')

    def test_host_mismatch(self):
        self.summary['host']='different-host';self.write(self.candidate);self.rejected('provenance differs')

    def test_unrecognized_dataset(self):
        manifest=json.loads(self.manifest.read_text());manifest['archive_sha256']='3'*64
        self.manifest.write_text(json.dumps(manifest));self.rejected('frozen published')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-manifest',type=Path,required=True)
    args, remaining=parser.parse_known_args();MANIFEST=args.dataset_manifest.resolve()
    unittest.main(argv=[__file__,*remaining])
