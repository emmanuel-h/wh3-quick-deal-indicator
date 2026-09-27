"""Minimal tool for Total War: WARHAMMER III PFH5 packs (Python 3.14+).

usage:
    packtool.py list    <pack> [filter]
    packtool.py extract <pack> <filter> <out_dir>
    packtool.py build   <src_dir> <out.pack>

`filter` is a case-insensitive substring of the file path inside the pack.
`build` writes an uncompressed mod pack containing every file under src_dir.
"""
import os
import struct
import sys
import time

HAS_INDEX_TIMESTAMPS = 0x40
INDEX_ENCRYPTED = 0x80
HEADER_EXTENDED = 0x100
PACK_TYPE_MOD = 3


def read_index(path):
    with open(path, "rb") as f:
        head = f.read(28)
        if head[:4] != b"PFH5":
            raise SystemExit(f"{path}: unsupported format {head[:4]!r}")
        flags, _, pack_index_size, file_count, file_index_size = struct.unpack_from("<5I", head, 4)
        if flags & INDEX_ENCRYPTED:
            raise SystemExit(f"{path}: encrypted index not supported")
        offset = 28 + (20 if flags & HEADER_EXTENDED else 0)
        f.seek(offset + pack_index_size)
        index = f.read(file_index_size)

    entries = []
    pos = 0
    data_offset = offset + pack_index_size + file_index_size
    for _ in range(file_count):
        size, = struct.unpack_from("<I", index, pos)
        pos += 4
        if flags & HAS_INDEX_TIMESTAMPS:
            pos += 4
        compressed = index[pos]
        pos += 1
        end = index.index(b"\0", pos)
        entries.append((index[pos:end].decode("utf-8", "replace"), data_offset, size, compressed))
        pos = end + 1
        data_offset += size
    return entries


def decompress(raw):
    # CA format: u32 uncompressed size, then a zstd frame or an LZMA stream
    # (5 bytes of properties followed by the data).
    usize, = struct.unpack_from("<I", raw, 0)
    if raw[4:8] == b"\x28\xb5\x2f\xfd":
        from compression import zstd
        return zstd.decompress(raw[4:])[:usize]
    import lzma
    header = raw[4:9] + struct.pack("<Q", usize)
    return lzma.LZMADecompressor(lzma.FORMAT_ALONE).decompress(header + raw[9:])[:usize]


def filtered(pack, needle):
    needle = needle.lower()
    return [e for e in read_index(pack) if needle in e[0].lower()]


def cmd_list(pack, needle=""):
    entries = filtered(pack, needle)
    for name, _, size, compressed in entries:
        print(f"{size:>10} {'C' if compressed else ' '} {name}")
    print(f"{len(entries)} entries", file=sys.stderr)


def cmd_extract(pack, needle, out_dir):
    entries = filtered(pack, needle)
    with open(pack, "rb") as f:
        for name, offset, size, compressed in entries:
            f.seek(offset)
            raw = f.read(size)
            dest = os.path.join(out_dir, *name.split("\\"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as out:
                out.write(decompress(raw) if compressed else raw)
    print(f"extracted {len(entries)} files", file=sys.stderr)


def cmd_build(src_dir, out_pack):
    files = []
    for root, _, names in os.walk(src_dir):
        for name in names:
            full = os.path.join(root, name)
            files.append((os.path.relpath(full, src_dir).replace("/", "\\").lower(), full))
    files.sort()

    index = b""
    blobs = []
    for rel, full in files:
        with open(full, "rb") as f:
            data = f.read()
        blobs.append(data)
        index += struct.pack("<I", len(data)) + b"\x00" + rel.encode("utf-8") + b"\x00"

    header = b"PFH5" + struct.pack("<6I", PACK_TYPE_MOD, 0, 0, len(files), len(index), int(time.time()))
    os.makedirs(os.path.dirname(os.path.abspath(out_pack)), exist_ok=True)
    with open(out_pack, "wb") as f:
        f.write(header + index + b"".join(blobs))
    print(f"wrote {out_pack}: {len(files)} files", file=sys.stderr)


def main():
    commands = {"list": cmd_list, "extract": cmd_extract, "build": cmd_build}
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    commands[sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    main()
