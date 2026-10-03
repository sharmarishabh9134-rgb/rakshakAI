"""Offline URL structure checks. This module deliberately performs no requests."""
import ipaddress
import re
from typing import Protocol
from urllib.parse import urlsplit

OFFICIAL_DOMAINS = ('sebi.gov.in', 'rbi.org.in', 'telegram.org', 'whatsapp.com')
SUSPICIOUS_TERMS = ('secure', 'verify', 'account', 'invest', 'profit', 'official', 'sebi', 'rbi', 'bonus', 'wallet')
BLOCKED_SUFFIXES = ('.localhost', '.local', '.internal', '.test', '.invalid')

class URLRejected(ValueError):
    pass

class ReputationProvider(Protocol):
    async def check_domain(self, domain: str) -> dict: ...

class DomainMetadataProvider(Protocol):
    async def lookup_domain(self, domain: str) -> dict: ...

def _similarity(a: str, b: str) -> float:
    # Small edit-distance helper; URLs are never resolved or fetched.
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return 1 - previous[-1] / max(len(a), len(b), 1)

def analyze_url(raw: str) -> dict:
    value = raw.strip()
    candidate = value if '://' in value else 'https://' + value
    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or '').rstrip('.').lower()
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Enter a valid HTTP or HTTPS URL.') from exc
    if parsed.scheme.lower() not in ('http', 'https') or not host:
        raise ValueError('Only absolute HTTP or HTTPS URLs can be checked.')
    try:
        ascii_host = host.encode('idna').decode('ascii')
    except UnicodeError as exc:
        raise ValueError('The domain name could not be interpreted safely.') from exc
    if ascii_host in ('localhost',) or ascii_host.endswith(BLOCKED_SUFFIXES):
        raise URLRejected('Local and restricted hostnames are not accepted.')
    try:
        ip = ipaddress.ip_address(ascii_host)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        raise URLRejected('Private, loopback, link-local, and reserved IP addresses are not accepted.')
    # Reject non-standard numeric IPv4 forms (for example 127.1) as a conservative local-host guard.
    if ip is None and re.fullmatch(r'[0-9.]+', ascii_host):
        raise URLRejected('Non-standard numeric IP URLs are not accepted.')

    indicators=[]; observations=[]
    def add(code, label, evidence, observation):
        indicators.append({'code':code,'label':label,'evidence':evidence})
        observations.append(observation)
    if parsed.scheme.lower() != 'https':
        add('no_https','HTTPS is not used',parsed.scheme,'The connection scheme is HTTP, not HTTPS.')
    else:
        observations.append('The URL uses HTTPS. This does not establish that its operator is trustworthy.')
    if ip is not None:
        add('ip_address_url','The host is an IP address',ascii_host,'The URL uses a numeric IP address instead of a domain name.')
    else:
        labels=ascii_host.split('.')
        label_pattern=re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')
        if len(labels)<2 or any(not label_pattern.fullmatch(part) for part in labels) or len(ascii_host)>253:
            add('invalid_domain','Unusual domain structure',ascii_host,'The hostname does not have a typical public domain structure.')
        terms=[term for term in SUSPICIOUS_TERMS if term in ascii_host]
        if terms:
            add('keyword_domain','Finance or authority terms appear in the domain',', '.join(terms),'Words in a domain do not verify a connection to an organization.')
        if len(ascii_host)>45 or ascii_host.count('-')>=2:
            add('unusual_domain','Unusual domain formatting',ascii_host,'The hostname is long or contains several hyphens.')
        suffix='.'.join(labels[-2:])
        registrable_guess='.'.join(labels[-3:]) if suffix in ('gov.in','org.in','co.in','net.in') and len(labels)>=3 else suffix
        close=[]
        for official in OFFICIAL_DOMAINS:
            if f'.{official}.' in f'.{ascii_host}.' and not (ascii_host == official or ascii_host.endswith('.'+official)):
                close.append(official)
                continue
            official_labels=official.split('.')
            official_suffix='.'.join(official_labels[-2:])
            official_root='.'.join(official_labels[-3:]) if official_suffix in ('gov.in','org.in','co.in','net.in') and len(official_labels)>=3 else official_suffix
            if registrable_guess != official_root and _similarity(registrable_guess,official_root)>=.78:
                if official not in close:
                    close.append(official)
        if close:
            add('lookalike_domain','The domain resembles a known organization domain',', '.join(close),'A similar spelling does not establish that the website is affiliated with the named organization.')
    if parsed.username is not None or parsed.password is not None:
        add('embedded_credentials','The URL contains user information','userinfo','URLs containing a username or password can conceal the actual destination.')

    display_host=f'[{ascii_host}]' if ':' in ascii_host else ascii_host
    display_port=f':{port}' if port is not None else ''
    safe_url=f'{parsed.scheme.lower()}://{display_host}{display_port}{parsed.path or "/"}'
    risk='HIGH' if len(indicators)>=3 else 'MODERATE' if indicators else 'LOW'
    return {
        'url':safe_url,
        'risk':risk,
        'risk_phrase':'Potential risk indicators detected.' if indicators else 'No configured risk indicators were detected.',
        'indicators':indicators,
        'observations':observations,
        'what_was_checked':['URL scheme','Hostname structure','Suspicious domain terms','Known-domain spelling similarity','Whether the host is a public IP address'],
        'what_could_not_be_checked':['DNS resolution','Excessive redirects','Live content or certificates','Reputation feeds','Domain registration metadata'],
        'checks':{'https':parsed.scheme.lower()=='https','domain_structure':bool(host),'ip_address':ip is not None,'redirects':'Not checked; destination was not fetched','reputation':'Unavailable; no provider configured','domain_metadata':'Unavailable; no provider configured'},
        'verification_recommendations':['Open the organization’s official website by entering its known address yourself.','Compare the full hostname, including its ending, with an independently verified source.','Do not enter credentials or payment details based only on this URL check.'],
        'explanation':'These are technical observations about the supplied URL. They cannot establish that a website is safe or fraudulent.',
        'disclaimer':'This check does not open the URL or verify its current content.'
    }
