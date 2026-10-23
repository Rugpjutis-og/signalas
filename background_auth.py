"""Verify the short-lived GitHub Actions OIDC token for the background trigger.

No cross-service static secret is used. The runner can only request this token in the
specific repository workflow; Vercel validates its signature and immutable claims.
"""
import base64
import hashlib
import hmac
import json
import time
from urllib.request import Request, build_opener
from openai_check import NoRedirect

ISSUER = 'https://token.actions.githubusercontent.com'
JWKS = ISSUER + '/.well-known/jwks'
AUDIENCE = 'https://signalas-ecru.vercel.app/api/background/tick'
REPOSITORY = 'Rugpjutis-og/signalas'
REPOSITORY_ID = '1428808487'
WORKFLOW_REF = REPOSITORY + '/.github/workflows/background.yml@refs/heads/main'
DIGEST_INFO_SHA256 = bytes.fromhex('3031300d060960864801650304020105000420')


def decode(segment):
    return base64.urlsafe_b64decode(segment + '=' * (-len(segment) % 4))


def verified_claims(header, *, now=None, fetch=None):
    """Return verified claims, or None. Never log/reflect token content."""
    try:
        scheme, token = header.split(' ', 1)
        if scheme != 'Bearer' or len(token) > 12000:
            return None
        encoded_header, encoded_body, encoded_signature = token.split('.')
        if any(base64.urlsafe_b64encode(decode(part)).rstrip(b'=').decode() != part
               for part in (encoded_header, encoded_body, encoded_signature)):
            return None
        meta = json.loads(decode(encoded_header))
        claims = json.loads(decode(encoded_body))
        if meta.get('alg') != 'RS256' or not isinstance(meta.get('kid'), str):
            return None
        current = int(now if now is not None else time.time())
        if not (claims.get('iss') == ISSUER and claims.get('aud') == AUDIENCE and
                claims.get('repository') == REPOSITORY and
                str(claims.get('repository_id')) == REPOSITORY_ID and
                claims.get('ref') == 'refs/heads/main' and
                claims.get('workflow_ref') == WORKFLOW_REF and
                claims.get('event_name') in ('schedule', 'workflow_dispatch') and
                isinstance(claims.get('iat'), int) and isinstance(claims.get('exp'), int) and
                current - 300 <= claims['iat'] <= current + 60 and
                current < claims['exp'] <= current + 600):
            return None
        if fetch is None:
            req = Request(JWKS, headers={'Accept': 'application/json'})
            with build_opener(NoRedirect).open(req, timeout=10) as response:
                if response.geturl() != JWKS:
                    return None
                keyset = json.loads(response.read(65537))
        else:
            keyset = fetch()
        key = next(k for k in keyset['keys'] if k.get('kid') == meta['kid']
                   and k.get('kty') == 'RSA' and k.get('use') == 'sig'
                   and k.get('alg') in (None, 'RS256'))
        modulus = int.from_bytes(decode(key['n']), 'big')
        exponent = int.from_bytes(decode(key['e']), 'big')
        size = (modulus.bit_length() + 7) // 8
        signature = decode(encoded_signature)
        if not (256 <= size <= 1024 and 1 < exponent <= 65537 and len(signature) == size):
            return None
        block = pow(int.from_bytes(signature, 'big'), exponent, modulus).to_bytes(size, 'big')
        digest = hashlib.sha256((encoded_header + '.' + encoded_body).encode('ascii')).digest()
        expected = b'\x00\x01' + b'\xff' * (size - len(DIGEST_INFO_SHA256) - len(digest) - 3)
        expected += b'\x00' + DIGEST_INFO_SHA256 + digest
        return claims if hmac.compare_digest(block, expected) else None
    except (ValueError, TypeError, KeyError, StopIteration, OverflowError, OSError, UnicodeError,
            json.JSONDecodeError):
        return None
