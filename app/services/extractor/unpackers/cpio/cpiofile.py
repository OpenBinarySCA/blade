#!/usr/bin/env python -3
# -*- coding: utf-8 -*-
#
# Copyright 2011 K. Richard Pixley.
# See LICENSE for details.
#
# Time-stamp: <13-Feb-2011 11:13:59 PST by rich@noir.com>

"""
Cpiofile is a library which reads and writes unix style 'cpio' format
archives.

.. todo:: open vs context manager
"""

from __future__ import unicode_literals, print_function

__docformat__ = 'restructuredtext en'

__all__ = [
    'CheckSumError',
    'CpioError',
    'CpioFile',
    'CpioMember',
    'HeaderError',
    'InvalidFileFormat',
    'InvalidFileFormatNull',
    'is_cpiofile',
    'open',
    'valid_magic',
    ]

import abc
import io
import mmap
import os
import struct

def open(name=None, mode='r', fileobj=None):
    cf = CpioFile()
    cf.open(name=name, fileobj=fileobj, mode=mode)
    return cf

class CpioError(Exception):
    pass

class CheckSumError(CpioError):
    pass

class InvalidFileFormat(CpioError):
    pass

class InvalidFileFormatNull(InvalidFileFormat):
    pass

class HeaderError(CpioError):
    pass

def valid_magic(block):
    return CpioMember._valid_magic(block)

def is_cpiofile(name):
    with io.open(name, 'rb') as f:
        return valid_magic(f.read(16))

class StructBase(object):
    __metaclass__ = abc.ABCMeta

    """
    An abstract base class representing objects which are inherently
    based on a struct.
    """

    coder = None
    """
    The :py:class:`struct.Struct` used to encode/decode this object
    into a block of memory.  This is expected to be overridden by
    subclasses.
    """

    class _Size(object):
        def __get__(self, obj, t):
            return t.coder.size

    size = _Size()
    """
    Exact size in bytes of a block of memory into which is suitable
    for packing this instance.
    """

    def unpack(self, block):
        return self.unpack_from(block)

    @abc.abstractmethod
    def unpack_from(self, block, offset=0):
        """
        Set the values of this instance from an in-memory
        representation of the struct.

        :param string block: block of memory from which to unpack
        :param int offset: optional offset into the memory block from
            which to start unpacking
        """
        raise NotImplementedError

    def pack(self):
        x = bytearray(self.size)
        self.pack_into(x)
        return x

    @abc.abstractmethod
    def pack_into(self, block, offset=0):
        """
        Store the values of this instance into an in-memory
        representation of the file.

        :param string block: block of memory into which to pack
        :param int offset: optional offset into the memory block into
            which to start packing
        """
        raise NotImplementedError

    __hash__ = None

    def __eq__(self, other):
        raise NotImplementedError

    def __ne__(self, other):
        return not self.__eq__(other)

    def close_enough(self, other):
        """
        This is a comparison similar to __eq__ except that here the
        goal is to determine whether two objects are "close enough"
        despite perhaps having been produced at different times in
        different locations in the file system.
        """
        return self == other

class CpioFile(StructBase):
    _members = []

    def __init__(self):
        self._members = []

    @property
    def members(self):
        return self._members

    @property
    def names(self):
        return [member.name for member in self.members]

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def open(self, mode='r', name=None, fileobj=None, map=None, block=None):
        """
        The open function takes some form of file identifier and creates
        an :py:class:`CpioFile` instance from it.

        :param :py:class:`str` name: a file name
        :param :py:class:`file` fileobj: if given, this overrides *name*
        :param :py:class:`mmap.mmap` map: if given, this overrides *fileobj*
        :param :py:class:`bytes` block: file contents in a block of memory, (if given, this overrides *map*)

        The file to be used can be specified in any of four different
        forms, (in reverse precedence):

        #. a file name
        #. :py:class:`file` object
        #. :py:mod:`mmap.mmap`, or
        #. a block of memory
        """

        if block is not None:
            if not name:
                name = '<unknown>'
            self.unpack_from(block)

            if fileobj:
                fileobj.close()

            return self

        if map is not None:
            block = map

        elif fileobj:
            # try:
            #     map = mmap.mmap(fileobj.fileno(), 0, mmap.MAP_SHARED, mmap.PROT_READ)
            # except:
            #     map = 0
            #     block = fileobj.read()
            map = 0
            block = fileobj.read()
        elif name:
            fileobj = io.open(os.path.normpath(os.path.expanduser(name)), 'rb')

        else:
            assert False

        return self.open(name=name,
                         fileobj=fileobj,
                         map=map,
                         block=block)

    def close(self):
        pass

    def unpack_from(self, block, offset=0):
        pointer = offset

        while 'TRAILER!!!' not in self.names:
            if pointer >= len(block):
                break
            cm = CpioMember.encodedClass(block, pointer)()
            self.members.append(cm.unpack_from(block, pointer))
            pointer += cm.size

        if len(self.members) and self.members[-1].name == 'TRAILER!!!':
            del self.members[-1]

    def pack_into(self, block, offset=0):
        pointer = offset

        for member in self.members:
            member.pack_into(block, pointer)
            pointer += member.size

        cmtype = type(self.members[0]) if self.members else CpioMemberNew
        cm = cmtype()
        cm.name = 'TRAILER!!!'
        cm.pack_into(block, pointer)

    def get_member(self, name):
        for member in self.members:
            if member.name == name:
                return member

        return None


class CpioMember(StructBase):
    coder = None

    name = None
    magic = None
    devmajor = None
    devminor = None
    ino = None
    mode = None
    uid = None
    gid = None
    nlink = None
    rdevmajor = None
    rdevminor = None
    mtime = None
    filesize = None

    @staticmethod
    def _valid_magic(block, offset=0):
        try:
            return CpioMember.encodedClass(block, offset)
        except InvalidFileFormat:
            return False

    @staticmethod
    def encodedClass(block, offset=0):
        if not block:
            raise InvalidFileFormatNull()

        for key in _magicmap:
            if block.find(key, offset, offset + len(key)) > -1:
                return _magicmap[key]
        raise InvalidFileFormat(f'{block[offset:offset+4]}')

    def unpack_from(self, block, offset=0):
        (self.magic, dev, self.ino, self.mode,
         self.uid, self.gid, self.nlink, rdev,
         mtimehigh, mtimelow, namesize, filesizehigh,
         filesizelow) = self.coder.unpack_from(block, offset)

        self.devmajor = os.major(dev)
        self.devminor = os.minor(dev)
        self.rdevmajor = os.major(rdev)
        self.rdevminor = os.minor(rdev)

        self.mtime = (mtimehigh << 16) | mtimelow
        self.filesize = (filesizehigh << 16) | filesizelow

        namestart = offset + self.coder.size
        datastart = namestart + namesize

        self.name = block[namestart:datastart - 1] # drop the null

        if isinstance(self, CpioMemberBin) and (namesize & 1):
            datastart += 1 # skip a pad byte if necessary

        self.content = block[datastart:datastart + self.filesize]

        return self

    def pack_into(self, block, offset=0):
        namesize = len(self.name)
        dev = os.makedev(self.devmajor, self.devminor)
        rdev = os.makedev(self.rdevmajor, self.rdevminor)

        mtimehigh = self.mtime >> 16
        mtimelow = self.mtime & 0xffff

        filesizehigh = self.filesize >> 16
        filesizelow = self.filesize & 0xffff

        self.coder.pack_into(block, offset, self.magic, dev,
                             self.ino, self.mode, self.uid, self.gid,
                             self.nlink, rdev, mtimehigh, mtimelow,
                             namesize, filesizehigh, filesizelow)
        
        namestart = offset + self.coder.size
        datatstart = namestart + namesize + 1

        block[namestart:datastart - 1] = self.name
        block[datastart - 1] = '\x00'

        if isinstance(self, CpioMemberBin) and (namesize & 1):
            datastart += 1
            block[datastart - 1] = '\x00'

        block[datastart:datastart + self.filesize] = self.content

        if isinstance(self, CpioMemberBin) and (self.filesize & 1):
            block[datastart + self.filesize] = '\x00'

        return self

    @property
    def size(self):
        return (self.coder.size
                + len(self.name) + 1
                + self.filesize)

    def __repr__(self):
        return (b'<{0}@{1}: coder={2}, name=\'{3}\', magic=\'{4}\', devmajor={5}, devminor={6}, ino={7}, mode={8}, uid={9}, gid={10}, nlink={11}, rdevmajor={12}, rdevmino={13}, mtime={14}, filesize={15}>'
                .format(self.__class__.__name__, hex(id(self)), self.coder, self.name,
                        self.magic, self.devmajor, self.devminor, self.ino,
                        self.mode, self.uid, self.gid, self.nlink,
                        self.rdevmajor, self.rdevminor, self.mtime, self.filesize))

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and self.coder == other.coder
                and self.magic == other.magic
                and self.devmajor == other.devmajor
                and self.devminor == other.devminor
                and self.ino == other.ino
                and self.mode == other.mode
                and self.uid == other.uid
                and self.gid == other.gid
                and self.nlink == other.nlink
                and self.rdevmajor == other.rdevmajor
                and self.rdevminor == other.rdevminor
                and self.mtime == other.mtime
                and self.filesize == other.filesize)

    close_enough = __eq__

class CpioMemberBin(CpioMember):
    @property
    def size(self):
        namesize = len(self.name) + 1 # add null

        retval = self.coder.size
        retval += namesize

        if isinstance(self, CpioMemberBin) and (namesize & 1):
            retval += 1

        retval += self.filesize

        if isinstance(self, CpioMemberBin) and (self.filesize & 1):
            retval += 1

        return retval

class CpioMember32b(CpioMemberBin):
    """
    .. todo:: need to pad after name and after content for old binary.
    """
    coder = struct.Struct(b'>2sHHHHHHHHHHHH')

class CpioMember32l(CpioMemberBin):
    coder = struct.Struct(b'<2sHHHHHHHHHHHH')

class CpioMemberODC(CpioMember):
    coder = struct.Struct(b'=6s6s6s6s6s6s6s6s11s6s11s')

    def unpack_from(self, block, offset=0):
        (self.magic, dev, ino, mode,
         uid, gid, nlink, rdev,
         mtime, namesize, filesize) = self.coder.unpack_from(block, offset)

        self.ino = int(ino,8)
        self.mode = int(mode,8)
        self.uid = int(uid,8)
        self.gid = int(gid,8)
        self.nlink = int(nlink,8)

        dev = int(dev, 8)
        rdev = int(rdev, 8)
        self.devmajor = os.major(dev)
        self.devminor = os.minor(dev)
        self.rdevmajor = os.major(rdev)
        self.rdevminor = os.minor(rdev)

        self.mtime = int(mtime,8)
        namesize = int(namesize,8)
        self.filesize = int(filesize,8)

        namestart = offset + self.coder.size
        datastart = namestart + namesize

        self.name = block[namestart:datastart - 1] # drop the null
        self.content = block[datastart:datastart + self.filesize]

        return self

    def pack_into(self, block, offset=0):
        dev = os.makedev(self.devmajor, self.devminor)
        ino = str(self.ino)
        mode = str(self.mode)
        uid = str(self.uid)
        gid = str(self.gid)
        nlink = str(self.nlink)
        rdev = os.makedev(self.rdevmajor, self.rdevminor)
        mtime = str(self.mtime)
        namesize = str(len(self.name) + 1) # add a null
        filesize = str(self.filesize)

        self.coder.pack_into(block, offset, self.magic, dev,
                             ino, mode, uid, gid,
                             nlink, rdev, mtime, namesize,
                             filesize)
        
        namesize = len(self.name) + 1

        namestart = offset + self.coder.size
        datastart = namestart + namesize

        block[namestart:datastart - 2] = self.name
        block[datastart - 1] = '\x00'
        block[datastart:datastart + self.filesize] = self.content

        return self

class CpioMemberNew(CpioMember):
    coder = struct.Struct(b'6s8s8s8s8s8s8s8s8s8s8s8s8s8s')

    @staticmethod
    def _checksum(block, offset, length):
        return 0

    def unpack_from(self, block, offset=0):
        (self.magic, ino, mode, uid,
         gid, nlink, mtime, filesize,
         devmajor, devminor, rdevmajor, rdevminor,
         namesize, check) = self.coder.unpack_from(block, offset)

        self.ino = int(ino,16)
        self.mode = int(mode,16)
        self.uid = int(uid,16)
        self.gid = int(gid,16)
        self.nlink = int(nlink,16)

        self.devmajor = int(devmajor,16)
        self.devminor = int(devminor,16)
        self.rdevmajor = int(rdevmajor,16)
        self.rdevminor = int(rdevminor,16)

        self.mtime = int(mtime,16)
        namesize = int(namesize,16)
        self.filesize = int(filesize,16)
        check = int(check,16)

        namestart = offset + self.coder.size
        nameend = namestart + namesize

        datastart = nameend + ((4 - (nameend % 4)) % 4) # pad
        dataend = datastart + self.filesize

        self.name = block[namestart:nameend - 1] # drop the null
        self.content = block[datastart:dataend]

        if check != self._checksum(self.content, 0, self.filesize):
            raise CheckSumError

        return self

    def pack_into(self, block, offset=0):
        namesize = len(self.name) + 1 # add a null
        check = self.checksum(self.content, 0, self.filesize)

        devmajor = str(self.devmajor)
        devminor = str(self.devminor)
        rdevmajor = str(self.rdevmajor)
        rdevminor = str(self.rdevminor)

        ino = str(self.ino)
        mode = str(self.mode)
        uid = str(self.uid)
        gid = str(self.gid)
        nlink = str(self.nlink)
        rdev = os.makedev(self.rdevmajor, self.rdevminor)
        mtime = str(self.mtime)
        namesize = str(len(self.name) + 1) # add a null
        filesize = str(self.filesize)

        self.coder.pack_into(block, offset, self.magic, ino,
                             mode, uid, gid, nlink,
                             mtime, filesize, devmajor, devminor,
                             rdevmajor, rdevminor, namesize, check)
        
        namestart = offset + self.coder.size
        nameend = namestart + namesize
        datastart = nameend + ((4 - (nameend % 4)) % 4) # pad
        dataend = datastart + self.filesize

        block[namestart:nameend] = self.name

        for i in range(nameend,datastart):
            block[i] = '\x00'

        block[datastart:dataend] = self.content

        padend = dataend + ((4 - (datastart % 4)) % 4) # pad
        for i in range(dataend,padend):
            block[i] = '\x00'

        return self

    @property
    def size(self):
        retval = self.coder.size
        retval += len(self.name) + 1
        retval += ((4 - (retval % 4)) % 4)
        retval += self.filesize
        retval += ((4 - (retval % 4)) % 4)
        return retval

class CpioMemberCRC(CpioMemberNew):
    @staticmethod
    def _checksum(block, offset, length):
        sum = 0

        for i in range(length):
            sum += ord(block[offset + i])

        return sum & 0xffffffff

_magicmap = {
    b'\x71\xc7': CpioMember32b,
    b'\xc7\x71': CpioMember32l,
    b'070707': CpioMemberODC,
    b'070701': CpioMemberNew,
    b'070702': CpioMemberCRC,
    }
