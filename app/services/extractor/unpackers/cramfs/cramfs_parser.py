import struct
import zlib
import stat

CRAMFS_SUPERBLOCK = "IIII16s16s16s"
CRAMFS_INODE =      "HH3sBI"
BLOCKSIZE = 1024 * 4

# uapi/linux/cramfs_fs.h
# fs/cramfs/inode.c
"""
#define CRAMFS_MAGIC        0x28cd3d45  /* some random number */
#define CRAMFS_MAGIC_WEND   0x453dcd28  /* magic number with the wrong endianess */

/*
 * Superblock information at the beginning of the FS.
 */
struct cramfs_super {
	__u32 magic;			/* 0x28cd3d45 - random number */
	__u32 size;			/* length in bytes */
	__u32 flags;			/* feature flags */
	__u32 future;			/* reserved for future use */
	__u8 signature[16];		/* "Compressed ROMFS" */
	struct cramfs_info fsid;	/* unique filesystem info */
	__u8 name[16];			/* user-defined name */
	struct cramfs_inode root;	/* root inode data */
};

struct cramfs_info {
	__u32 crc;
	__u32 edition;
	__u32 blocks;
	__u32 files;
};

/*
 * cramfs super-block data in memory
 */
struct cramfs_sb_info {
	unsigned long magic;
	unsigned long size;
	unsigned long blocks;
	unsigned long files;
	unsigned long flags;
};

#define 	CRAMFS_MODE_WIDTH   16
#define 	CRAMFS_UID_WIDTH   16
#define 	CRAMFS_SIZE_WIDTH   24
#define 	CRAMFS_GID_WIDTH   8
#define 	CRAMFS_NAMELEN_WIDTH   6
#define 	CRAMFS_OFFSET_WIDTH   26

struct cramfs_inode {
	__u32 mode:CRAMFS_MODE_WIDTH, uid:CRAMFS_UID_WIDTH;
	/* SIZE for device files is i_rdev */
	__u32 size:CRAMFS_SIZE_WIDTH, gid:CRAMFS_GID_WIDTH;
	/* NAMELEN is the length of the file name, divided by 4 and
           rounded up.  (cramfs doesn't support hard links.) */
	/* OFFSET: For symlinks and non-empty regular files, this
	   contains the offset (divided by 4) of the file data in
	   compressed form (starting with an array of block pointers;
	   see README).  For non-empty directories it is the offset
	   (divided by 4) of the inode of the first file in that
	   directory.  For anything else, offset is zero. */
	__u32 namelen:CRAMFS_NAMELEN_WIDTH, offset:CRAMFS_OFFSET_WIDTH;
};
"""
ROOT_INODE_OFFSET = 64
INODE_SIZE = 12
class INODE:
    name = b""
    uid  = 0
    gid = 0
    size = 0
    mode = 0
    namelen = 0
    offset = 0

    def __str__(self):
        return f'<INODE {self.name}>'

    @classmethod
    def parse(cls, stream, offset):
        stream.seek(offset)
        buf = stream.read(INODE_SIZE)
        mode, uid, size, gid, namelenoffset = struct.unpack("<HH3sBI", buf)
        (size,) = struct.unpack("<I", size + b'\x00')

        namelen =  (namelenoffset & 0x3F) * 4
        offset  =  (namelenoffset >> 6) * 4

        if namelen != 0:
            # Namelengths on disk are shifted by two
            # and the name padded out to 4-byte boundaries
            # with zeroes.
            name = stream.read(namelen).rstrip(b'\x00')
        else:
            name = b''
        instance = cls()
        instance.name = name
        instance.mode = mode
        instance.uid = uid
        instance.gid = gid
        instance.size = size
        instance.offset = offset
        return instance

def read_dir(stream, dir_inode) -> list:
    assert stat.S_ISDIR(dir_inode.mode)
    children = []
    if dir_inode.size == 0:
        return children
    offset = 0
    while offset < dir_inode.size:
        inode = INODE.parse(stream, dir_inode.offset + offset)
        children.append(inode)
        offset += INODE_SIZE + inode.namelen
    return children

def read_file(stream, inode):
    """
    fs/cramfs/inode.c   cramfs_readpage
    """
    blocks = []
    num_of_blocks = int((inode.size - 1) / BLOCKSIZE + 1)
    stream.seek(inode.offset)
    head_buf = stream.read( 4 * num_of_blocks )
    for block_idx in range(num_of_blocks):
        if block_idx > 0:
            (start_offset,) = struct.unpack_from('<I', head_buf, (block_idx - 1) * 4)
        else:
            start_offset = inode.offset + num_of_blocks * 4
        (compr_len, ) = struct.unpack_from('<I', head_buf, block_idx * 4)
        stream.seek(start_offset)
        buf = stream.read( compr_len )
        blocks.append(zlib.decompress(buf))
    
    return b''.join(blocks)

def get_inode_of_path(stream, path):
    root_inode = INODE.parse(stream, ROOT_INODE_OFFSET)
    if path in ('/', ''):
        return root_inode
    parts = [p for p in path.split("/") if p]
    
    inode = root_inode
    for i in range(len(parts)):
        if stat.S_ISDIR(inode.mode):
            return None
        items = read_dir(stream, inode)
        next_inode = inode.get(parts[i])
        if next_inode == None:
            return None
        inode = next_inode
    return inode


def _walk_inode(stream, inode, path = b''):
    children = read_dir(stream, inode)
    for child_inode in children:
        yield path + child_inode.name, child_inode
        if stat.S_ISDIR(child_inode.mode):
            yield from _walk_inode(stream, child_inode.mode, path + child_inode.name + b'/' )


class CramFS:
    def __init__(self, fileobj) -> None:
        self._fileobj = fileobj
        self._root_inode = INODE.parse(self._fileobj, ROOT_INODE_OFFSET)
    
    def walk(self):
        yield from _walk_inode(self._fileobj, self._root_inode)
    
    def read(self, path_or_inode):
        if isinstance(path_or_inode, INODE):
            inode = path_or_inode
        else:
            inode = get_inode_of_path(self._fileobj, path_or_inode)
            if inode is None:
                raise FileNotFoundError(f'{path_or_inode}')
        if not stat.S_ISREG(inode.mode):
            raise ValueError(f'{inode} not file')
        return read_file(self._fileobj, inode)
        