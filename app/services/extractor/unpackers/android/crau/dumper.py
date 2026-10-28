import os
import sys
import tempfile
import struct
import hashlib
import bz2
import lzma
from . import update_metadata_pb2 as update_metadata

flatten = lambda l: [item for sublist in l for item in sublist]

def u32(x):
    return struct.unpack('>I', x)[0]

def u64(x):
    return struct.unpack('>Q', x)[0]

def verify_contiguous(exts):
    blocks = 0

    for ext in exts:
        if ext.start_block != blocks:
            return False

        blocks += ext.num_blocks

    return True

def data_for_op(f_in, data_offset, op):
    f_in.seek(data_offset + op.data_offset)
    data = f_in.read(op.data_length)

    assert hashlib.sha256(data).digest() == op.data_sha256_hash, 'operation data hash mismatch'

    if op.type == op.REPLACE_XZ:
        dec = lzma.LZMADecompressor()
        data = dec.decompress(data) 
    elif op.type == op.REPLACE_BZ:
        dec = bz2.BZ2Decompressor()
        data = dec.decompress(data) 

    return data


def extract(f_in, temp_dir, logger):
    magic = f_in.read(4)
    magic == b'CrAU'

    file_format_version = u64(f_in.read(8))
    assert file_format_version == 2

    manifest_size = u64(f_in.read(8))

    metadata_signature_size = 0

    if file_format_version > 1:
        metadata_signature_size = u32(f_in.read(4))

    manifest = f_in.read(manifest_size)
    metadata_signature = f_in.read(metadata_signature_size)

    data_offset = f_in.tell()

    dam = update_metadata.DeltaArchiveManifest()
    dam.ParseFromString(manifest)

    for part in dam.partitions:
        for op in part.operations:
            assert op.type in (op.REPLACE, op.REPLACE_BZ, op.REPLACE_XZ), \
                    'unsupported op'

        extents = flatten([op.dst_extents for op in part.operations])
        assert verify_contiguous(extents), 'operations do not span full image'

        fd, temp_file_path = tempfile.mkstemp(prefix=part.partition_name+'-', dir=temp_dir)
        os.close(fd)
        logger.debug('<extract> writing "%s" to "%s"', part.partition_name, temp_file_path)
        with open(temp_file_path, 'wb+') as out_f:
            h = hashlib.sha256()
            for op in part.operations:
                data = data_for_op(f_in, data_offset, op)
                h.update(data)
                out_f.write(data)
            assert h.digest() == part.new_partition_info.hash, 'partition hash mismatch'
        yield part.partition_name, temp_file_path
        logger.debug('<extract> delete "%s" at "%s"', part.partition_name, temp_file_path)
        os.remove(temp_file_path)