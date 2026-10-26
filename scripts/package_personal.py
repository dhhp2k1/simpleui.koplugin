"""Build a reproducible installable ZIP with no development files or user data."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
def build():
    out=ROOT/"dist";out.mkdir(exist_ok=True)
    sources=[ROOT/n for n in ("main.lua","_meta.lua","LICENSE","THIRD_PARTY_NOTICES.md")]
    for n in ("engines","features","fonts","icons","infra","locale","modules","screens"):
        sources.extend(p for p in (ROOT/n).rglob("*") if p.is_file())
    target=out/"simpleui.koplugin.zip";entries={}
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(sources,key=lambda p:p.relative_to(ROOT).as_posix()):
            rel=p.relative_to(ROOT).as_posix()
            if "__pycache__" in p.parts or p.suffix in {".pyc",".bak"}:continue
            data=p.read_bytes()
            if p.suffix.lower() in {".lua",".po",".pot",".md",".txt",".svg"}:
                data=data.replace(b"\r\n",b"\n")
            info=zipfile.ZipInfo("simpleui.koplugin/"+rel,(2026,10,26,0,0,0))
            info.create_system=3
            info.external_attr=0o100644<<16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
            entries[rel]=hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert "simpleui.koplugin/main.lua" in names
        assert "simpleui.koplugin/_meta.lua" in names
        assert len(names)==len(set(names))
        assert not any("/sui_ai" in n or "/sui_news" in n or "/.git/" in n or n.endswith(".py") for n in names)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (out/"SHA256SUMS").write_text(digest+"  simpleui.koplugin.zip\n",encoding="utf8")
    (out/"file-hashes.json").write_text(json.dumps(entries,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(f"Built {target.name}: {len(entries)} files, {target.stat().st_size} bytes; ZIP CRC and layout verified.")
if __name__=="__main__":build()
