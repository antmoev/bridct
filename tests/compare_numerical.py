#!/usr/bin/env python3
"""Gate complete parent/candidate numerical evidence before runtime timing."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shlex

THRESHOLD = 2e-5
SIDES = (8,16,32,64,128,256,512,1024)
SHAPE_CASES = ('zero','impulse','random','neighbors','tiny','large')
FIELDS = ('h','w','case','domain','mode','error','finite','guards','unchanged','return_code','passed')
KEY_FIELDS = ('h','w','case','domain','mode')
ARCHIVE_SHA256 = 'f091e39ad8e2f1f9fb3325d379a6e3953f1619b3930d3a3e7241a7ed7800b7cf'


class GateError(ValueError):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def require(condition, message, **details):
    if not condition:
        raise GateError(message, **details)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def constant(value):
        raise GateError(f'Non-finite JSON constant: {value}')
    def number(value):
        result = float(value)
        require(math.isfinite(result), 'Non-finite JSON number')
        return result
    with Path(path).open() as stream:
        return json.load(stream, object_pairs_hook=pairs, parse_constant=constant, parse_float=number)


def expected_keys(manifest_path):
    manifest = json_load(manifest_path)
    require(manifest.get('archive_sha256') == ARCHIVE_SHA256,
            'Expected the frozen published verification corpus')
    require(manifest.get('sizes') == list(SIDES[:6]), 'Unexpected corpus side lengths')
    cases = manifest.get('cases')
    require(isinstance(cases,list) and len(cases) == 474, 'Expected 474 corpus inputs')
    ids = set()
    keys = {(h,w,name,'shapes',mode) for h in SIDES for w in SIDES
            for name in SHAPE_CASES for mode in range(3)}
    for case in cases:
        require(isinstance(case,dict), 'Invalid corpus case')
        name, n, domain = case.get('id'), case.get('N'), case.get('domain')
        require(isinstance(name,str) and name and name not in ids, 'Duplicate/invalid corpus input ID')
        require(type(n) is int and n in SIDES[:6], 'Invalid corpus input size')
        require(domain in ('core','range_diagnostic','subnormal_diagnostic'), 'Invalid corpus domain')
        ids.add(name)
        keys.update((n,n,name,domain,mode) for mode in range(3))
    require(len(keys) == 2574, 'Expected exactly 2574 distinct direction keys')
    require(sum(k[3] == 'core' for k in keys) == 1260, 'Expected 1260 corpus core directions')
    require(sum(k[3] not in ('core','shapes') for k in keys) == 162,
            'Expected 162 separate boundary directions')
    return keys


def integer(text, field):
    require(isinstance(text,str) and re.fullmatch(r'0|[1-9][0-9]*',text) is not None,
            f'Invalid integer in CSV field {field}: {text!r}')
    return int(text)


def boolean(text, field):
    require(text in ('True','False'), f'Invalid CSV boolean {field}: {text!r}')
    return text == 'True'


def read_evidence(directory, expected):
    directory = Path(directory)
    result = json_load(directory/'result.json')
    require(isinstance(result,dict) and result.get('status') == 'PASS',
            f'{directory}: numerical result must be PASS')
    rows = {}
    with (directory/'checks.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and len(reader.fieldnames) == len(FIELDS)
                and set(reader.fieldnames) == set(FIELDS), 'Unexpected or duplicate CSV columns')
        for raw in reader:
            require(set(raw) == set(FIELDS) and all(v is not None for v in raw.values()),
                    'Malformed CSV record')
            row = dict(raw)
            for field in ('h','w','mode','return_code'):
                row[field] = integer(raw[field],field)
            for field in ('finite','guards','unchanged','passed'):
                row[field] = boolean(raw[field],field)
            if raw['error'] == '':
                row['error'] = None
            else:
                try:
                    row['error'] = float(raw['error'])
                except ValueError as error:
                    raise GateError('Invalid numerical error in CSV') from error
                require(math.isfinite(row['error']) and row['error'] >= 0,
                        'CSV numerical errors must be finite and nonnegative')
            key = tuple(row[field] for field in KEY_FIELDS)
            require(key not in rows, 'Duplicate direction key', key=key)
            require(key in expected, 'Unexpected direction key', key=key)
            require(row['guards'] and row['unchanged'] and row['return_code'] == 0,
                    'Structural check failed', key=key)
            require(row['finite'] == (row['error'] is not None),
                    'Finite/error fields disagree', key=key)
            passed = row['finite'] and row['error'] <= THRESHOLD
            require(row['passed'] == passed, 'Passed flag disagrees with fixed threshold', key=key)
            if row['domain'] in ('core','shapes'):
                require(passed, 'Required numerical direction failed', key=key)
            rows[key] = row
    require(set(rows) == expected, 'Incomplete direction keys',
            missing=sorted(expected-set(rows)), extra=sorted(set(rows)-expected))
    required = [row for row in rows.values() if row['domain'] in ('core','shapes')]
    boundaries = [row for row in rows.values() if row['domain'] not in ('core','shapes')]
    counts = {'shapes':64, 'shape_checks':1152, 'corpus_core_checks':1260,
              'boundary_checks':162, 'boundary_failures':sum(not row['passed'] for row in boundaries),
              'required_failures':0}
    for field, value in counts.items():
        require(type(result.get(field)) is int and result[field] == value,
                f'Result count disagrees with CSV: {field}')
    require(result.get('guards_and_input_preservation') is True,
            'Result does not assert structural preservation')
    maximum = result.get('max_required_error')
    require(type(maximum) in (float,int) and math.isfinite(maximum) and maximum >= 0,
            'Invalid maximum required error')
    require(math.isclose(maximum,max(row['error'] for row in required),rel_tol=1e-12,abs_tol=0),
            'Maximum required error disagrees with CSV')
    for field in ('host','host_machine','package_version','execution'):
        require(isinstance(result.get(field),str) and result[field], f'Missing provenance: {field}')
    require(isinstance(result.get('runner_sha256'),str) and
            re.fullmatch('[0-9a-f]{64}',result['runner_sha256']) is not None,
            'Missing/invalid runner hash')
    libraries = result.get('shared_libraries')
    require(isinstance(libraries,dict) and libraries, 'Missing shared library provenance')
    require(all(isinstance(name,str) and name and isinstance(sha,str) and
                re.fullmatch('[0-9a-f]{64}',sha) for name,sha in libraries.items()),
            'Invalid shared library hash')
    return rows, result


def check_configs(parent, candidate):
    require((parent is None) == (candidate is None), 'Provide both build configs or neither')
    if parent is None:
        return {'checked':False, 'scope':'Numerical evidence only; compiler/host pairing is not established by these CSVs'}
    parent_tokens = shlex.split(Path(parent).read_text())
    candidate_tokens = shlex.split(Path(candidate).read_text())
    token = '-DBRIDCT_COMPILED_AVX2=1'
    ooura = '-DBRIDCT_COMPILED_OOURA16_ALL=1'
    require(parent_tokens and not any(t in parent_tokens for t in (token,ooura)),
            'Parent config must disable runtime AVX2 and Ooura16')
    require(candidate_tokens.count(token) == 1, 'Candidate config must enable runtime AVX2 exactly once')
    require(candidate_tokens.count(ooura) <= 1, 'Candidate Ooura16 macro duplicated')
    allowed = [token] + ([ooura] if ooura in candidate_tokens else [])
    require(parent_tokens == [value for value in candidate_tokens if value not in allowed],
            'Parent and candidate compiler/options differ beyond runtime AVX2/Ooura16 macros')
    return {'checked':True,'parent_sha256':digest(parent),'candidate_sha256':digest(candidate),
            'permitted_difference':token if len(allowed)==1 else allowed,'compiler':parent_tokens[0]}


def compare(parent, candidate, manifest, parent_config=None, candidate_config=None):
    expected = expected_keys(manifest)
    p, pm = read_evidence(parent,expected)
    c, cm = read_evidence(candidate,expected)
    for field in ('host','host_machine','package_version'):
        require(pm[field] == cm[field], f'Parent/candidate provenance differs: {field}')
    config = check_configs(parent_config,candidate_config)
    regressions = [dict(zip(KEY_FIELDS,key)) for key in sorted(expected)
                   if p[key]['passed'] and not c[key]['passed']]
    require(not regressions, 'Parent-pass to candidate-fail regression',
            parent_pass_to_candidate_fail=len(regressions), regressions=regressions)
    return {'status':'PASS','directions_per_arm':len(expected),'required_per_arm':2412,
            'boundary_per_arm':162,'threshold':THRESHOLD,
            'parent_boundary_failures':pm['boundary_failures'],
            'candidate_boundary_failures':cm['boundary_failures'],
            'parent_pass_to_candidate_fail':0,
            'candidate_recoveries':sum(not p[k]['passed'] and c[k]['passed'] for k in expected),
            'build_configuration':config,
            'host':pm['host'],'host_machine':pm['host_machine'],'package_version':pm['package_version'],
            'scope':'Complete paired numerical evidence; a matching OS description alone does not prove the same physical host. The workflow must execute both arms sequentially on one runner.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--dataset-manifest',type=Path,required=True)
    parser.add_argument('--parent-config',type=Path)
    parser.add_argument('--candidate-config',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    record = {'status':'FAILED','gate_sha256':digest(__file__)}
    code = 1
    try:
        require(not args.output.exists(), 'Choose a new output JSON file')
        record['evidence_sha256'] = {str(path.resolve()):digest(path) for path in (
            args.parent/'checks.csv',args.parent/'result.json',args.candidate/'checks.csv',
            args.candidate/'result.json',args.dataset_manifest)}
        record.update(compare(args.parent,args.candidate,args.dataset_manifest,
                              args.parent_config,args.candidate_config))
        code = 0
    except (GateError,OSError,ValueError,KeyError,TypeError) as error:
        record.update(status='FAILED',error=str(error))
        if isinstance(error,GateError):
            record.update(error.details)
    if not args.output.exists():
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(json.dumps(record,indent=2,allow_nan=False))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
