"""Patch « IA avec mods » de Md (Blur Map Builder, GameTweaks.cs, MIT) sur un Blur REBORN.exe d'une COPIE du jeu.

usage : python ai_mods_patch.py GameTweaks.cs "chemin\\Blur REBORN.exe" [on|off|check]
Les octets sont lus dans GameTweaks.cs (tableau AiModPatches) : rien n'est recopié à la main.
"""
import re, sys, shutil


def split_top(s):
    out, depth, cur, q = [], 0, '', False
    for ch in s:
        if ch == '"':
            q = not q
        if not q:
            if ch in '({': depth += 1
            if ch in ')}': depth -= 1
            if ch == ',' and depth == 0:
                out.append(cur.strip()); cur = ''; continue
        cur += ch
    if cur.strip(): out.append(cur.strip())
    return out


def ev(e):
    e = e.strip()
    m = re.fullmatch(r'H\((.*)\)(\.Concat\(Cc\((\d+)\)\)\.ToArray\(\))?', e, re.S)
    if m:
        b = bytes.fromhex(''.join(re.findall(r'"([0-9a-fA-F]*)"', m.group(1))))
        return b + (b'\xcc' * int(m.group(3)) if m.group(3) else b'')
    m = re.fullmatch(r'Cc\((\d+)\)', e)
    if m: return b'\xcc' * int(m.group(1))
    m = re.fullmatch(r'new byte\[(\d+)\]', e)
    if m: return bytes(int(m.group(1)))
    raise ValueError(e[:60])


def patches(cs):
    src = open(cs, encoding='utf-8').read()
    body = src[src.index('AiModPatches ='):]
    body = body[body.index('{') + 1:body.index('};')]
    body = re.sub(r'//[^\n]*', '', body)
    res = []
    for ent in split_top(body):
        f = split_top(ent.strip()[1:-1])
        res.append((int(f[0], 16), ev(f[1]), ev(f[2])))
    return res


def main():
    cs, exe, mode = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else 'check')
    ps = patches(cs)
    assert len(ps) == 7 and all(len(o) == len(n) for _, o, n in ps), 'lecture de GameTweaks.cs ratée'
    d = bytearray(open(exe, 'rb').read())
    st = ['new' if d[o:o+len(n)] == n else 'old' if d[o:o+len(old)] == old else '???' for o, old, n in ps]
    print('état :', ' '.join(f'{o:#x}={s}' for (o, _, _), s in zip(ps, st)))
    if mode == 'check': return
    if '???' in st: sys.exit('exe inconnu : rien changé')
    if mode == 'on' and 'new' not in st: shutil.copy2(exe, exe + '.avant_aimods')
    for o, old, n in ps: d[o:o+len(n)] = n if mode == 'on' else old
    open(exe, 'wb').write(d)
    print('écrit :', mode)


if __name__ == '__main__':
    main()
