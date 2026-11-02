"""Map Builder 1.0.0 + correctifs NFS Studio (nfs_studio.patch), reproductibles depuis le zip d'origine.
usage : python setup_map_builder.py check   [ZIP] [DOSSIER]   compare une copie existante (fins de ligne ignorées)
        python setup_map_builder.py install [ZIP] [DOSSIER]   extrait + applique le correctif (dossier neuf seulement)
Par défaut : ZIP et DOSSIER de config.py (MAP_BUILDER_ZIP, MAP_BUILDER_DIR)."""
import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, "nfs_studio.patch")
SHA256 = "cc7425bd8f3cd1dd1cf6b3df3922b204103dd16f30664deb3d6fc803b1d7d171"
ROOT = "blur-map-builder-1.0.0/"


def extract(zpath, dest):
    if hashlib.sha256(open(zpath, "rb").read()).hexdigest() != SHA256:
        sys.exit("zip inattendu (sha256 différent) : " + zpath)
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            if n.startswith(ROOT) and not n.endswith("/"):
                p = os.path.join(dest, n[len(ROOT):])
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "wb").write(z.read(n))
    subprocess.run(["git", "apply", "--whitespace=nowarn", PATCH], cwd=dest, check=True)


def check(ref, dest):
    bad = []
    for d, _, fs in os.walk(ref):
        for f in fs:
            a = os.path.join(d, f)
            b = os.path.join(dest, os.path.relpath(a, ref))
            if not os.path.exists(b):
                bad.append("absent : " + b)
            elif open(a, "rb").read().replace(b"\r\n", b"\n") != open(b, "rb").read().replace(b"\r\n", b"\n"):
                bad.append("différent : " + b)
    return bad


def main():
    sys.path.insert(0, os.path.join(HERE, "..", ".."))
    import config
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    zpath = sys.argv[2] if len(sys.argv) > 2 else config.MAP_BUILDER_ZIP
    dest = sys.argv[3] if len(sys.argv) > 3 else config.MAP_BUILDER_DIR
    if mode == "install":
        if os.path.exists(dest):
            sys.exit("le dossier existe déjà, rien n'est écrasé : " + dest)
        extract(zpath, dest)
        print("installé :", dest)
    else:
        with tempfile.TemporaryDirectory() as ref:
            extract(zpath, ref)
            bad = check(ref, dest)
        print("\n".join(bad) or "OK : %s = zip d'origine + nfs_studio.patch" % dest)
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
