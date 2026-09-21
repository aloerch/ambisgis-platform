"""Measured same-token role propagation through the packaged resource server."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
from configured_auth_probe import wfs
from role_fixture import (AUTH_TTL_SECONDS, ROLE_TTL_MS, PROPAGATION_DEADLINE_SECONDS,
                          configuration_hashes, assert_configuration_stable, ROLE_FAILURE_DEADLINE_SECONDS, ROLE_FAILURE_CONFIRMATION_SECONDS)

DENIED = (401, 403, 404)


def exercise_roles(*, matrix, report, config, output, data_dir, mutate, issue, verify,
                   row, parse, role_client, api_auth, tokens, registry):
    frozen = configuration_hashes(data_dir)
    result = {'passed': False, 'authority': 'GeoNode native ORM membership / authenticated actual endpoints',
        'local_user_records': 'identity-only; no automatic provisioning',
        'membership_mutation': 'authorized controlled native ORM operation, not HTTP administration',
        'declared_before_measurement': {'role_cache_expire_after_write_ms': ROLE_TTL_MS,
            'authentication_expire_after_write_seconds': AUTH_TTL_SECONDS,
            'serial_cache_budget_seconds': ROLE_TTL_MS / 1000 + AUTH_TTL_SECONDS,
            'healthy_test_deadline_seconds': PROPAGATION_DEADLINE_SECONDS,
            'failure_first_transition_deadline_seconds': ROLE_FAILURE_DEADLINE_SECONDS,
            'failure_three_confirmation_deadline_seconds': ROLE_FAILURE_CONFIRMATION_SECONDS,
            'failure_deadline_basis': 'First denial: six serial role calls times 1500ms plus 3s serial caches and 3s margin; three confirmations: 3*6*1.5s+3s cache+5s margin. Not a production maximum.',
            'poll_interval_seconds': .25,
            'scope': 'single-process observed timing, not proven production maximum/SLA'},
        'transitions': [], 'failure_probes': [], 'same_token': True}
    report['role_change'] = result  # Preserve partial measurements if any later assertion fails.

    def endpoint(case, username, expected_groups=None, expected_status=(200,), membership=None, absent=False):
        response = role_client.request('GET', '/api/users/' + username, headers={'Authorization': api_auth})
        payload = parse(response)
        users = payload.get('users', [])
        groups = next((u.get('groups') for u in users if u.get('username') == username), None)
        predicate = expected_groups is None or groups == expected_groups
        if membership is not None:
            group, present = membership
            predicate = predicate and isinstance(groups, list) and (group in groups) == present
        if absent: predicate = predicate and users == []
        if not row(case, response, expected_status, predicate, detail={'payload': payload}):
            raise RuntimeError('role endpoint did not match committed membership: ' + case)
        return payload

    def valid_token(case, token):
        response = verify(token)
        if not row(case, response, (200,), tokeninfo_token=token):
            raise RuntimeError('role change unexpectedly invalidated bearer token')

    def observe(case, token, ack, allow, path=None, method='GET', body=None, headers=None, timeout=PROPAGATION_DEADLINE_SECONDS, confirmation_timeout=None):
        path = path or wfs('private_points')
        started = ack['ack_monotonic_ns'] / 1e9
        deadline = started + (confirmation_timeout or timeout)
        first_transition_deadline = started + timeout
        first_target_at = None
        samples, stable = [], 0
        while time.monotonic() < deadline:
            begin = time.monotonic()
            status, content, _ = matrix.request(case + '-' + str(len(samples)), path, token,
                method, body, headers, expected=(200, 201, *DENIED), excludes=())
            done = time.monotonic()
            permitted = status in (200, 201)
            from configured_auth_evidence import validate_geojson
            content_ok = not permitted or path != wfs('private_points') or validate_geojson(content, 'PRIVATE_WITNESS')
            if not permitted and 'PRIVATE_WITNESS' in content: content_ok = False
            samples.append({'case': matrix.rows[-1]['case'], 'request_start_after_ack_seconds': round(begin-started, 6),
                'request_end_after_ack_seconds': round(done-started, 6), 'status': status, 'content_valid': content_ok})
            if not matrix.rows[-1]['passed'] or not content_ok: raise RuntimeError('invalid propagation response')
            if permitted == allow:
                if first_target_at is None: first_target_at = done
                stable += 1
            else:
                if first_target_at is not None: raise RuntimeError('authorization regressed after first target state: ' + case)
                stable = 0
            if first_target_at is None and done >= first_transition_deadline: break
            if stable >= 3: break
            time.sleep(.25)
        passed = stable >= 3 and time.monotonic() <= deadline and first_target_at <= first_transition_deadline
        record = {'case': case, 'committed_state': ack, 'target_allowed': allow, 'first_transition_deadline_seconds': timeout, 'confirmation_deadline_seconds': confirmation_timeout or timeout,
            'first_target_response_seconds': round(first_target_at-started, 6) if first_target_at else None, 'samples': samples,
            'last_permitted_response_seconds': max((s['request_end_after_ack_seconds'] for s in samples if s['status'] in (200,201)), default=None),
            'first_denial_response_seconds': next((s['request_end_after_ack_seconds'] for s in samples if s['status'] in DENIED), None),
            'sampling_uncertainty': 'Requests sample authorization at an unknown instant within each retained start/end interval; no exact transition instant is inferred.',
            'stable_samples': stable, 'passed': passed}
        result['transitions'].append(record)
        if not passed: raise RuntimeError('role propagation exceeded declared deadline: ' + case)
        return record

    _, initial_rules, _ = matrix.request('role-rules-before', '/rest/geofence/rules', tokens['admin'],
        headers={'Accept':'application/xml'}, excludes=()); matrix.require_last()
    result['geofence_rules_before_sha256'] = hashlib.sha256(initial_rules.encode()).hexdigest()
    # Ordinary bearer/session callers have no role-service authority or mutation API.
    for label, headers in (('user-bearer', {'Authorization': 'Bearer ' + tokens['reader']}),
                           ('confidential-client-is-not-role-key', {'Authorization': 'ApiKey ' + config['client_secret']}),
                           ('legacy-global-key-is-not-service-key', {'Authorization': 'ApiKey ' + config['api_key']})):
        response = role_client.request('GET', '/api/adminRole', headers=headers)
        if not row(label, response, (401,403)): raise RuntimeError('role credential confusion')
    for method in ('POST','PUT','DELETE'):
        response = role_client.request(method, '/api/adminRole', headers={'Authorization':api_auth},
                                       form={'adminRole': 'fixture-readers'})
        if not row('read-only-role-endpoint-' + method, response, (405,)):
            raise RuntimeError('role service accepted assignment mutation')
    endpoint('unknown-role-identity', 'fixture-does-not-exist', expected_status=(200,), absent=True)
    endpoint('inactive-role-identity', 'fixture-disabled', expected_status=(200,), absent=True)
    reader_token = issue()[2].access_token
    matrix.request('authoritative-group-prime', wfs('private_points'), reader_token,
                   contains='PRIVATE_WITNESS', excludes=()); matrix.require_last()
    endpoint('group-before-removal', 'fixture-reader', membership=('fixture-readers', True))
    removed = mutate('group-remove')
    if 'fixture-readers' in removed.get('committed_groups', []): raise RuntimeError('native group removal not committed')
    # Measure immediately from committed mutation; endpoint readback is a separate actual HTTP operation.
    endpoint('group-after-removal', 'fixture-reader', membership=('fixture-readers', False))
    observe('group-removal-same-token', reader_token, removed, False)
    valid_token('same-token-valid-after-group-removal', reader_token)
    fresh_after_remove = issue()[2].access_token
    matrix.request('fresh-token-after-group-removal', wfs('private_points'), fresh_after_remove, expected=DENIED); matrix.require_last()
    for n in range(5):
        matrix.request('stable-revoked-role-' + str(n), wfs('private_points'), reader_token, expected=DENIED); matrix.require_last()
    def revoked_concurrent(n):
        admin = n % 2 == 0
        matrix.request('role-concurrent-revoked-' + str(n), wfs('private_points'),
            tokens['admin'] if admin else reader_token, expected=(200,) if admin else DENIED,
            contains='PRIVATE_WITNESS' if admin else None, excludes=() if admin else ('PRIVATE_WITNESS',))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(revoked_concurrent, range(16)))
    restored = mutate('group-add')
    if 'fixture-readers' not in restored.get('committed_groups', []): raise RuntimeError('native group restoration not committed')
    endpoint('group-after-restoration', 'fixture-reader', membership=('fixture-readers', True))
    observe('group-restoration-same-token', reader_token, restored, True)
    valid_token('same-token-valid-after-group-restoration', reader_token)
    # Same protected route, no configured URL-key filter. Query text is a nonsecret invalid key.
    for bearer in (None, tokens['outsider']):
        matrix.request('unconfigured-authkey-cannot-bypass-' + str(bearer is None),
            wfs('private_points') + '&authkey=fixture-unconfigured-key', bearer, expected=DENIED); matrix.require_last()
    # Administrators are assigned solely by GeoNode is_superuser, not role response injection.
    admin_token = tokens['admin']
    matrix.request('admin-before-demotion', '/rest/workspaces.json', admin_token, contains='fixture', excludes=()); matrix.require_last()
    demoted = mutate('admin-demote', username='fixture-admin')
    if demoted.get('committed_superuser') is not False: raise RuntimeError('native admin demotion not committed')
    endpoint('admin-role-after-demotion', 'fixture-admin', membership=('admin', False))
    observe('administrator-demotion-same-token', admin_token, demoted, False, path='/rest/workspaces.json')
    valid_token('same-token-valid-after-admin-demotion', admin_token)
    name = 'must_not_exist_after_demotion'
    matrix.request('demoted-admin-write-denied', '/rest/workspaces', admin_token, 'POST',
        '<workspace><name>' + name + '</name></workspace>', {'Content-Type':'application/xml'}, expected=DENIED); matrix.require_last()
    promoted = mutate('admin-promote', username='fixture-admin')
    if promoted.get('committed_superuser') is not True: raise RuntimeError('native admin restoration not committed')
    observe('administrator-restoration-same-token', admin_token, promoted, True, path='/rest/workspaces.json')
    matrix.request('demotion-denied-write-left-no-state', '/rest/workspaces/' + name + '.json', admin_token,
                   expected=(404,), contains=name, excludes=()); matrix.require_last()
    # Actual service-principal revocation: token verifier stays healthy and independent.
    matrix.request('service-revocation-warm-prime', wfs('private_points'), reader_token,
                   contains='PRIVATE_WITNESS', excludes=()); matrix.require_last()
    revoked = mutate('disable', username='fixture-role-service')
    response = role_client.request('GET','/api/users/fixture-reader',headers={'Authorization':api_auth})
    if not row('revoked-role-service-key', response, (401,403)): raise RuntimeError('revoked service principal accepted')
    valid_token('tokeninfo-independent-of-service-key-revocation', reader_token)
    observe('role-service-revoked-warm-cache', reader_token, revoked, False)
    matrix.request('revoked-service-fresh-token', wfs('private_points'), issue()[2].access_token, expected=DENIED); matrix.require_last()
    renewed = mutate('enable', username='fixture-role-service')
    observe('role-service-recovery-same-token', reader_token, renewed, True)
    for mode in ('missing-credential','wrong-credential','delay','truncate','short-body','malformed','duplicate-field','trailing-content'):
        # Faults affect role HTTP only; token verification uses the native endpoint unchanged.
        from run import save
        fault_file = output / 'role-transport-fault.json'
        fresh_token = issue()[2].access_token
        matrix.request('role-fault-warm-prime-' + mode, wfs('private_points'), reader_token,
                       contains='PRIVATE_WITNESS', excludes=()); matrix.require_last()
        event_log = output / 'geonode-runtime.log'
        event_start = len(event_log.read_text().splitlines())
        save(fault_file, {'mode': mode}, private=True)
        ack = {'ack_monotonic_ns': time.monotonic_ns(), 'action': 'explicit-role-transport-fault', 'mode': mode}
        try:
            valid_token('tokeninfo-independent-role-fault-' + mode, fresh_token)
            observe('role-fault-' + mode, reader_token, ack, False, timeout=ROLE_FAILURE_DEADLINE_SECONDS, confirmation_timeout=ROLE_FAILURE_CONFIRMATION_SECONDS)
            matrix.request('role-fault-fresh-token-' + mode, wfs('private_points'), fresh_token, expected=DENIED); matrix.require_last()
        finally:
            fault_file.unlink(missing_ok=True)
            if mode == 'delay': time.sleep(4)
        ack = {'ack_monotonic_ns':time.monotonic_ns(), 'action':'fault-disabled', 'mode':mode}
        observe('role-fault-recovery-' + mode, reader_token, ack, True)
        controls = []
        for line in event_log.read_text().splitlines()[event_start:]:
            try: control = json.loads(line)
            except ValueError: continue
            if control.get('event') == 'native_role_transport_fault' and control.get('mode') == mode: controls.append(control)
        expected_native = (401,403) if mode in ('missing-credential','wrong-credential') else (200,)
        proved = bool(controls) and all(c.get('native_status') in expected_native and c.get('native_body_bytes',0) > 0 for c in controls)
        result['failure_probes'].append({'mode':mode,'token_verification_independent':True,'native_controls':controls,'passed':proved})
        if not proved: raise RuntimeError('role fault did not reach expected native endpoint response')
    # Concurrent per-request identity correlation remains enforced by the main journey.
    def concurrent_request(n):
        allowed = n % 2 == 0
        matrix.request('role-concurrent-restored-' + str(n), wfs('private_points'),
            reader_token if allowed else tokens['outsider'], expected=(200,) if allowed else DENIED,
            contains='PRIVATE_WITNESS' if allowed else None, excludes=() if allowed else ('PRIVATE_WITNESS',))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(concurrent_request, range(16)))
    _, final_rules, _ = matrix.request('role-rules-after', '/rest/geofence/rules', tokens['admin'],
        headers={'Accept':'application/xml'}, excludes=()); matrix.require_last()
    result['geofence_rules_after_sha256'] = hashlib.sha256(final_rules.encode()).hexdigest()
    if initial_rules != final_rules: raise RuntimeError('fixed GeoFence rules changed during membership tests')
    result['configuration_unchanged'] = assert_configuration_stable(data_dir, frozen)
    result['passed'] = all(v['passed'] for v in result['transitions'] + result['failure_probes'])
    return result
