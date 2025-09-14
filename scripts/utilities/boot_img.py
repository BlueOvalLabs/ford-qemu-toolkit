import os

BOOT_HDR_SIZE = 0x108
FILE_HDR_BASE_SIZE = 0x68

def read_boot_header(f):
    f.seek(0)
    data = f.read(0x20)

    if data[0:4] != b'BHDR':
        raise ValueError(f"Invalid magic: {data[0:4]}")

    version = int.from_bytes(data[4:8], 'little')
    fsig_ptr = int.from_bytes(data[8:12], 'little')
    sig_algo = int.from_bytes(data[12:16], 'little')
    image_type_magic = data[20:24]
    files_cnt = int.from_bytes(data[24:26], 'little')
    files_off = int.from_bytes(data[26:28], 'little')

    return {
        'version': version,
        'fsig_ptr': fsig_ptr,
        'sig_algo': sig_algo,
        'image_type_magic': image_type_magic,
        'files_cnt': files_cnt,
        'files_off': files_off
    }

def read_file_headers(f, offset, count):
    headers = []
    f.seek(offset)

    for _ in range(count):
        base = f.read(FILE_HDR_BASE_SIZE)

        hdr_len = int.from_bytes(base[0:8], 'little')
        name = base[8:24].split(b'\x00')[0].decode(errors='ignore')
        file_off = int.from_bytes(base[24:32], 'little')
        file_size = int.from_bytes(base[32:40], 'little')
        hash_val = base[88:112]

        extra_len = hdr_len - FILE_HDR_BASE_SIZE
        extra = []
        if extra_len > 0:
            extra_data = f.read(extra_len)
            for i in range(0, extra_len, 8):
                extra.append(int.from_bytes(extra_data[i:i+8], 'little'))

        headers.append({
            'name': name,
            'offset': file_off,
            'size': file_size,
            'hash': hash_val,
            'hdr_len': hdr_len,
            'extra': extra
        })

    return headers

def extract_files(f, file_headers, outdir='extracted'):
    os.makedirs(outdir, exist_ok=True)
    for i, fh in enumerate(file_headers):
        f.seek(fh['offset'])
        data = f.read(fh['size'])
        filename = f"{i:02d}_{fh['name']}"
        with open(os.path.join(outdir, filename), 'wb') as out_f:
            out_f.write(data)
        print(f"Extracted: {filename} ({fh['size']} bytes)")

def main(filepath):
    with open(filepath, 'rb') as f:
        header = read_boot_header(f)
        print("Header:", header)

        files = read_file_headers(f, header['files_off'], header['files_cnt'])
        print(f"Found {len(files)} files")

        extract_files(f, files)

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("Usage: python boot_img.py <boot.img>")
    else:
        main(sys.argv[1])
