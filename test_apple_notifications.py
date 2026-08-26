"""Exercise the App Store Server Notification verifier with a synthetic chain.

Apple's real leaf certificates are short-lived and we cannot forge them, so the
accept-path is tested by building our own root/intermediate/leaf chain and
temporarily pinning our root. Every reject-path is tested against the real pin.
"""
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as srv

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(f'{"PASS" if cond else "FAIL"}  {name}{("  -- " + detail) if detail and not cond else ""}')


def make_cert(subject_cn, issuer_cert, issuer_key, *, ca, not_before=None, not_after=None):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject_cn)])
    issuer_name = issuer_cert.subject if issuer_cert else subject
    nb = not_before or datetime.now(timezone.utc) - timedelta(days=1)
    na = not_after or datetime.now(timezone.utc) + timedelta(days=365)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(nb)
        .not_valid_after(na)
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    )
    cert = builder.sign(issuer_key or key, hashes.SHA256())
    return cert, key


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def build_jws(payload: dict, chain, leaf_key, *, alg='ES256', tamper=False):
    header = {
        'alg': alg,
        'x5c': [base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode() for c in chain],
    }
    h = b64u(json.dumps(header).encode())
    p = b64u(json.dumps(payload).encode())
    der = leaf_key.sign(f'{h}.{p}'.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    sig = b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))
    if tamper:
        p = b64u(json.dumps({**payload, 'notificationType': 'DID_RENEW'}).encode())
    return f'{h}.{p}.{sig}'


def rejects(token, label):
    try:
        srv._apple_verify_signed_jws(token)
    except ValueError as exc:
        check(label, True)
        return str(exc)
    except Exception as exc:
        check(label, False, f'raised {type(exc).__name__} not ValueError: {exc}')
        return ''
    check(label, False, 'accepted a payload it should have rejected')
    return ''


print('--- pinned root sanity ---')
real_root = x509.load_pem_x509_certificate(srv.APPLE_ROOT_CA_G3_PEM)
check(
    'embedded PEM matches pinned fingerprint',
    real_root.fingerprint(hashes.SHA256()).hex() == srv.APPLE_ROOT_CA_G3_SHA256,
)
check(
    'pinned root is Apple Root CA - G3',
    'Apple Root CA - G3' in real_root.subject.rfc4514_string(),
)
check('pinned root still valid', real_root.not_valid_after_utc > datetime.now(timezone.utc))

print('\n--- reject paths (against the real pin) ---')
root, root_key = make_cert('Fake Root', None, None, ca=True)
inter, inter_key = make_cert('Fake Intermediate', root, root_key, ca=True)
leaf, leaf_key = make_cert('Fake Leaf', inter, inter_key, ca=False)
chain = [leaf, inter, root]
payload = {'notificationType': 'EXPIRED', 'data': {'bundleId': 'x'}}

msg = rejects(build_jws(payload, chain, leaf_key), 'rejects a chain rooted elsewhere')
check('  ...and says so clearly', 'Apple root' in msg, msg)
rejects('not-a-jws', 'rejects a malformed token')
rejects('a.b', 'rejects a two-segment token')
rejects(build_jws(payload, chain, leaf_key, alg='none'), 'rejects alg=none')
rejects(build_jws(payload, chain, leaf_key, alg='HS256'), 'rejects alg=HS256')

hdr = {'alg': 'ES256', 'x5c': []}
empty = f'{b64u(json.dumps(hdr).encode())}.{b64u(b"{}")}.{b64u(b"0" * 64)}'
rejects(empty, 'rejects an empty certificate chain')

print('\n--- accept path (temporarily pinning the synthetic root) ---')
saved_pem, saved_fp = srv.APPLE_ROOT_CA_G3_PEM, srv.APPLE_ROOT_CA_G3_SHA256
srv.APPLE_ROOT_CA_G3_PEM = root.public_bytes(serialization.Encoding.PEM)
srv.APPLE_ROOT_CA_G3_SHA256 = root.fingerprint(hashes.SHA256()).hex()
try:
    got = srv._apple_verify_signed_jws(build_jws(payload, chain, leaf_key))
    check('accepts a correctly signed chain', got.get('notificationType') == 'EXPIRED', str(got))

    rejects(build_jws(payload, chain, leaf_key, tamper=True), 'rejects a tampered payload')

    # Leaf signed by a key that is not the intermediate's.
    _, other_key = make_cert('Other', None, None, ca=True)
    rejects(build_jws(payload, chain, other_key), 'rejects a bad signature')

    # Chain where the intermediate did not issue the leaf.
    stray_inter, stray_key = make_cert('Stray Intermediate', root, root_key, ca=True)
    stray_leaf, stray_leaf_key = make_cert('Stray Leaf', stray_inter, stray_key, ca=False)
    rejects(
        build_jws(payload, [stray_leaf, inter, root], stray_leaf_key),
        'rejects a leaf the intermediate did not issue',
    )

    # Expired leaf.
    exp_leaf, exp_key = make_cert(
        'Expired Leaf', inter, inter_key, ca=False,
        not_before=datetime.now(timezone.utc) - timedelta(days=10),
        not_after=datetime.now(timezone.utc) - timedelta(days=1),
    )
    rejects(build_jws(payload, [exp_leaf, inter, root], exp_key), 'rejects an expired leaf')
finally:
    srv.APPLE_ROOT_CA_G3_PEM, srv.APPLE_ROOT_CA_G3_SHA256 = saved_pem, saved_fp

check('pin restored after test', srv.APPLE_ROOT_CA_G3_SHA256 == saved_fp)

print('\n--- notification -> status mapping ---')
NO_RENEW, RENEW_ON, RENEW_OFF = {}, {'autoRenewStatus': 1}, {'autoRenewStatus': 0}
cases = [
    ('DID_RENEW', '', {}, RENEW_ON, ('active', 0)),
    ('SUBSCRIBED', 'INITIAL_BUY', {'offerType': 1}, RENEW_ON, ('trialing', 0)),
    ('SUBSCRIBED', 'INITIAL_BUY', {'offerDiscountType': 'FREE_TRIAL'}, RENEW_ON, ('trialing', 0)),
    ('DID_RENEW', '', {}, RENEW_OFF, ('active', 1)),
    ('DID_CHANGE_RENEWAL_STATUS', 'AUTO_RENEW_DISABLED', {}, RENEW_OFF, ('active', 1)),
    ('DID_CHANGE_RENEWAL_STATUS', 'AUTO_RENEW_ENABLED', {}, RENEW_ON, ('active', 0)),
    ('DID_FAIL_TO_RENEW', 'GRACE_PERIOD', {}, RENEW_ON, ('past_due', 0)),
    ('EXPIRED', 'VOLUNTARY', {}, NO_RENEW, ('expired', 0)),
    ('GRACE_PERIOD_EXPIRED', '', {}, NO_RENEW, ('expired', 0)),
    ('REVOKE', '', {}, NO_RENEW, ('expired', 0)),
    ('REFUND', '', {}, NO_RENEW, ('refunded', 0)),
    ('DID_CHANGE_RENEWAL_PREF', 'UPGRADE', {}, RENEW_ON, ('active', 0)),
    ('CONSUMPTION_REQUEST', '', {}, NO_RENEW, None),
    ('REFUND_DECLINED', '', {}, NO_RENEW, None),
    ('TEST', '', {}, NO_RENEW, None),
    ('SOMETHING_APPLE_ADDS_LATER', '', {}, NO_RENEW, None),
]
for ntype, sub, txn, renew, expected in cases:
    got = srv._apple_notification_outcome(ntype, sub, txn, renew)
    check(f'{ntype}/{sub or "-"} -> {expected}', got == expected, f'got {got}')

print('\n--- entitlement consistency ---')
# Whatever the mapping produces must line up with the gates the rest of the app
# already applies, or a renewal could still read as locked-out.
GATE = ('active', 'trialing', 'past_due')
for ntype in ('DID_RENEW', 'SUBSCRIBED', 'DID_FAIL_TO_RENEW'):
    st = srv._apple_notification_outcome(ntype, '', {}, RENEW_ON)[0]
    check(f'{ntype} yields a status that grants access ({st})', st in GATE)
for ntype in ('EXPIRED', 'REVOKE', 'REFUND', 'GRACE_PERIOD_EXPIRED'):
    st = srv._apple_notification_outcome(ntype, '', {}, NO_RENEW)[0]
    check(f'{ntype} yields a status that revokes access ({st})', st not in GATE)

print('\n' + '=' * 60)
print(f'{len(PASS)} passed, {len(FAIL)} failed')
if FAIL:
    for f in FAIL:
        print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
