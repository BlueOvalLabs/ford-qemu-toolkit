import json
import os

def _find_vbf_header(data: bytes) -> tuple[int, int]:
    # A very naive implementation to find the header by looking for matching braces
    # Will choke on comments containing mismatched braces
    header_start = data.find(b'header {')
    if header_start == -1:
        raise ValueError("Header not found in the VBF file.")
    
    open_brace_count = 1
    header_end = header_start + 8  # Start after 'header {'
    while open_brace_count > 0 and header_end < len(data):
        if data[header_end] == ord('{'):
            open_brace_count += 1
        elif data[header_end] == ord('}'):
            open_brace_count -= 1
        header_end += 1
    if open_brace_count != 0:
        raise ValueError("Mismatched braces in the VBF header.")
    return header_start, header_end

def _parse_vbf_header(data: bytes) -> dict:
    # Extracts information from the header
    header = {}
    # Parse the header data
    lines = data.decode('utf-8').splitlines()
    for i in range(1, len(lines) - 1):
        line = lines[i].strip()
        if not line or line.startswith('//'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().rstrip(';')
            # if value.startswith('{') and value.endswith('}'):
            #     # Handle arrays
            #     value = [v.strip() for v in value[1:-1].split(',')]
            if value.startswith('"') and value.endswith('"'):
                # Handle strings
                value = value[1:-1]
            elif value.startswith('0x'):
                # Handle hex values
                value = int(value, 16)
            elif value.startswith('{'):
                # Special handling for arrays
                # Collect all lines until the closing brace into a single string
                concat = value + ''.join(lines[i+1:])
                concat = concat.replace('\t', '').replace(' ', '')
                open_brace_count = 1
                for j in range(1, len(concat)):
                    if concat[j] == '{':
                        open_brace_count += 1
                    elif concat[j] == '}':
                        open_brace_count -= 1
                    if open_brace_count == 0:
                        value = concat[:j+1]
                        break
                    
                value = value.replace('{', '[').replace('}', ']')
                import ast
                value = ast.literal_eval(value)
            else:
                # Handle integers
                try:
                    value = int(value)
                except ValueError:
                    pass
            header[key] = value
    return header

def _extract_blocks(data: bytes) -> dict:
    # Extracts blocks from the VBF data
    blocks = {}
    from io import BytesIO
    d = BytesIO(data)
    while True:
        addr = int.from_bytes(d.read(4), 'big')
        length = int.from_bytes(d.read(4), 'big')
        data_block = d.read(length)
        checksum = int.from_bytes(d.read(2), 'big')
        if not data_block:
            break
        blocks[addr] = {
            'length': length,
            'data': data_block,
            'checksum': checksum
        }
    return blocks

def _parse_manifest(blocks: dict) -> dict:
    if 0x1 not in blocks:
        raise ValueError("No manifest block found in the VBF file.")
    manifest_block = blocks[0x1]['data']
    manifest = json.loads(manifest_block.decode('utf-8'))
    files = manifest

    return files

def _extract_files(manifest: dict, blocks: dict) -> dict:
    files = {}
    for file in manifest.get('Files', []):
        # Copy the file object to avoid modifying the original manifest
        file = file.copy()
        addr = int(file['startAddress'], 16)
        file['data'] = blocks[addr]['data'] if addr in blocks else None
        files[file['name']] = file
    return files

def parse_vbf(data: bytes) -> dict:
    header_start, header_end = _find_vbf_header(data)
    header_info = _parse_vbf_header(data[header_start:header_end])
    blocks = _extract_blocks(data[header_end:])
    manifest = _parse_manifest(blocks) if 0x1 in blocks else None
    files = _extract_files(manifest, blocks) if manifest else None

    return {
        'header': header_info,
        'blocks': blocks,
        'manifest': manifest,
        'files': files
    }

if __name__ == "__main__":
    import argparse
    import rich

    parser = argparse.ArgumentParser(description="VBF Converter")
    parser.add_argument('file_path', type=str, help='Path to the VBF file to convert')
    parser.add_argument('-o', '--output', type=str, help='Output directory for extracted files', required=False)
    parser.add_argument('--block', type=str, help='Desired block to extract from the VBF file.')
    args = parser.parse_args()

    vbf_data = open(args.file_path, 'rb').read()
    vbf_info = parse_vbf(vbf_data)
    if "manifest" in vbf_info and vbf_info["manifest"]:
        rich.print(vbf_info["manifest"])
    else:
        rich.print(vbf_info["header"])
