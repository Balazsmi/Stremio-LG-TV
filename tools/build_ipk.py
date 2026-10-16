"""Build and verify an allowlisted webOS IPK using only Python's standard library."""
import gzip
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
APP_FILES = ('appinfo.json', 'index.html', 'main.js', 'css/style.css', 'icon.png', 'LICENSE')


def tar_gz(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return gzip.compress(stream.getvalue(), mtime=0)


def ar_member(name, data):
    header = f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(data):<10}`\n'
    assert len(header) == 60
    return header.encode('ascii') + data + (b'\n' if len(data) % 2 else b'')


def read_ar(blob):
    if blob[:8] != b'!<arch>\n':
        raise ValueError('Invalid ar header')
    result = {}
    offset = 8
    while offset < len(blob):
        header = blob[offset:offset + 60]
        if len(header) != 60 or header[58:60] != b'`\n':
            raise ValueError('Invalid ar member header')
        name = header[:16].decode('ascii').strip().rstrip('/')
        size = int(header[48:58])
        start = offset + 60
        data = blob[start:start + size]
        if len(data) != size or name in result:
            raise ValueError('Truncated or duplicate ar member')
        result[name] = data
        offset = start + size + size % 2
    return result


def untar(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as archive:
        members = archive.getmembers()
        if any(not member.isfile() for member in members):
            raise ValueError('Unexpected non-file entry')
        return {member.name: archive.extractfile(member).read() for member in members}


def build(tag=None):
    manifest = json.loads((ROOT / 'appinfo.json').read_text(encoding='utf-8'))
    app_id, version = manifest['id'], manifest['version']
    if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', app_id):
        raise ValueError('Invalid app ID')
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid version')
    if tag is not None and tag != f'v{version}':
        raise ValueError(f'Release tag {tag!r} must match appinfo.json: v{version}')
    if manifest['main'] != 'index.html' or manifest['icon'] != 'icon.png':
        raise ValueError('Update the package allowlist for changed entry points')
    prefix = f'usr/palm/applications/{app_id}/'
    files = {prefix + name: (ROOT / name).read_bytes() for name in APP_FILES}
    files[f'usr/palm/packages/{app_id}/packageinfo.json'] = (
        json.dumps({'id': app_id, 'version': version, 'app': app_id}) + '\n'
    ).encode('utf-8')
    installed_kib = (sum(map(len, files.values())) + 1023) // 1024
    control = (
        f'Package: {app_id}\nVersion: {version}\nSection: misc\nPriority: optional\n'
        f'Architecture: all\nInstalled-Size: {installed_kib}\n'
        'Maintainer: Stremio-LG-TV contributors\n'
        'Description: Lightweight Stremio hosted launcher with manual recovery.\n'
        'webOS-Package-Format-Version: 2\n'
    ).encode('utf-8')
    members = {'debian-binary': b'2.0\n', 'control.tar.gz': tar_gz({'control': control}),
               'data.tar.gz': tar_gz(files)}
    blob = b'!<arch>\n' + b''.join(ar_member(name, data) for name, data in members.items())
    # Verify the actual output bytes against the exact current source files.
    unpacked = read_ar(blob)
    assert list(unpacked) == list(members)
    assert unpacked['debian-binary'] == b'2.0\n'
    assert untar(unpacked['control.tar.gz']) == {'control': control}
    assert untar(unpacked['data.tar.gz']) == files
    output = ROOT / 'dist' / f'{app_id}_{version}_all.ipk'
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(blob)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.ipk.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    print(f'Built and verified: {output.name} ({len(blob)} bytes)\nSHA256: {digest}')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', help='Require this release tag to match appinfo.json (e.g. v1.1.0)')
    args = parser.parse_args()
    build(tag=args.tag)
