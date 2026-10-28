import sys  
import struct
import io  
  

"""
https://android.googlesource.com/platform/system/extras/+/gingerbread/ext4_utils/sparse_format.h

typedef struct sparse_header {
  __le32 magic;          /* 0xed26ff3a */
  __le16 major_version;  /* (0x1) - reject images with higher major versions */
  __le16 minor_version;  /* (0x0) - allow images with higer minor versions */
  __le16 file_hdr_sz;    /* 28 bytes for first revision of the file format */
  __le16 chunk_hdr_sz;   /* 12 bytes for first revision of the file format */
  __le32 blk_sz;         /* block size in bytes, must be a multiple of 4 (4096) */
  __le32 total_blks;     /* total blocks in the non-sparse output image */
  __le32 total_chunks;   /* total chunks in the sparse input image */
  __le32 image_checksum; /* CRC32 checksum of the original data, counting "don't care" */
                         /* as 0. Standard 802.3 polynomial, use a Public Domain */
                         /* table implementation */
} sparse_header_t;


#define SPARSE_HEADER_MAGIC 0xed26ff3a
#define CHUNK_TYPE_RAW 0xCAC1
#define CHUNK_TYPE_FILL 0xCAC2
#define CHUNK_TYPE_DONT_CARE 0xCAC3
#define CHUNK_TYPE_CRC32 0xCAC4
typedef struct chunk_header {
  __le16 chunk_type; /* 0xCAC1 -> raw; 0xCAC2 -> fill; 0xCAC3 -> don't care */
  __le16 reserved1;
  __le32 chunk_sz; /* in blocks in output image */
  __le32 total_sz; /* in bytes of chunk input file including chunk header and data */
} chunk_header_t;

"""
class SparseHeader:  
    def __init__(self, buf):  
        self.magic, \
            self.major_version, \
            self.minor_version, \
            self.file_hdr_sz, \
            self.chunk_hdr_sz, \
            self.blk_sz, \
            self.total_blks, \
            self.total_chunks, \
            self.image_checksum, \
            = struct.unpack('<IHHHHIIII', buf)  

class ChunkHeader:  
    def __init__(self, buf):  
        self.type,\
            self.reserved,\
            self.chunk_sz,\
            self.total_sz,\
            = struct.unpack('<HHII', buf)

CHUNK_HEADER_SIZE = 12

SPARSE_HEADER_MAGIC = 0xed26ff3a
CHUNK_TYPE_RAW =  0xCAC1
CHUNK_TYPE_FILL = 0xCAC2
CHUNK_TYPE_DONT_CARE = 0xCAC3
CHUNK_TYPE_CRC32 = 0xCAC4

SPARSE_HEADER_MAJOR_VER = 1
SPARSE_HEADER_LEN = 28
CHUNK_HEADER_LEN = 12

def extract(in_f, out_f):
    buf = in_f.read(SPARSE_HEADER_LEN)  
    sparse_header = SparseHeader(buf)  

    if sparse_header.magic != SPARSE_HEADER_MAGIC:  
        raise Exception("Not a compressed ext4 fileecho")
    
    if sparse_header.major_version != SPARSE_HEADER_MAJOR_VER:  
        raise Exception(f"Unknown major version number {sparse_header.major_version}")

    if sparse_header.file_hdr_sz > SPARSE_HEADER_LEN:
		# Skip the remaining bytes in a header that is longer than
		# we expected.
        in_f.seek(sparse_header.file_hdr_sz - SPARSE_HEADER_LEN, io.SEEK_CUR)

    #print("total chunk = {}".format(sparse_header.total_chunks))
    total_blocks = 0
    for chunk_idx in range(sparse_header.total_chunks):
        buf = in_f.read(CHUNK_HEADER_SIZE)  
        chunk_header = ChunkHeader(buf)
        #print(f"{chunk_idx}/{sparse_header.total_chunks} type={chunk_header.type:0X} chunk_sz={chunk_header.chunk_sz} total_sz={chunk_header.total_sz}")
        
        if sparse_header.chunk_hdr_sz > CHUNK_HEADER_LEN:
			# Skip the remaining bytes in a header that is longer than
			# we expected.
            in_f.seek(sparse_header.chunk_hdr_sz - SPARSE_HEADER_LEN, io.SEEK_CUR)

        if chunk_header.type == CHUNK_TYPE_RAW:
            if (chunk_header.total_sz != (sparse_header.chunk_hdr_sz + (chunk_header.chunk_sz * sparse_header.blk_sz)) ):
                raise Exception(f"Bogus chunk size for chunk {chunk_idx}, type Raw");
            total_blocks += process_raw_chunk(in_f, out_f, chunk_header.chunk_sz, sparse_header.blk_sz)
        elif chunk_header.type == CHUNK_TYPE_FILL:
            total_blocks += process_fill_chunk(in_f, out_f, chunk_header.chunk_sz, sparse_header.blk_sz)
        elif chunk_header.type == CHUNK_TYPE_DONT_CARE:
            total_blocks += process_skip_chunk(out_f, chunk_header.chunk_sz, sparse_header.blk_sz);
        else:
            raise Exception(f'Unknown chunk type. type:{chunk_header.type}')

def process_raw_chunk(in_f, out_f, blocks, blk_sz):
    COPY_BUF_SIZE = 1024*1024
    length = blocks * blk_sz
    while length > 0:
        chunk_size = COPY_BUF_SIZE if length > COPY_BUF_SIZE else length
        data = in_f.read(chunk_size)
        if len(data) != chunk_size:
            raise Exception("read error copying a raw chunk")
        out_f.write(data)
        length -= len(data)
    return blocks

def process_skip_chunk(out_f, blocks, blk_sz):
    ZERO_BUF_SIZE = 1024*1024
    ZERO_BUF = b'\0' * ZERO_BUF_SIZE
    length = blocks * blk_sz

    while length > 0:
        if length > ZERO_BUF_SIZE:
            out_f.write(ZERO_BUF)
            length -= ZERO_BUF_SIZE
        else:
            out_f.write(ZERO_BUF[:length])
            break
        
    return blocks

def process_fill_chunk(in_f, out_f, blocks, blk_sz):
    pattern = in_f.read(4)
    
    fill_buf = pattern * int(blk_sz/len(pattern) + 1)
    fill_buf = fill_buf[:blk_sz]
    
    length = blocks * blk_sz
    while length > 0:
        if length > len(fill_buf):
            out_f.write(fill_buf)
            length -= len(fill_buf)
        else:
            out_f.write(fill_buf[:length])
            break
        
    return blocks


if __name__ == '__main__':
    with open(sys.argv[1], 'rb') as in_f:
        with open(sys.argv[2], 'wb') as out_f:
            extract(in_f, out_f)