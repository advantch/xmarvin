import os
import pathlib
import tempfile
from io import BytesIO, StringIO, UnsupportedOperation

from marvin.extensions.exceptions import SuspiciousFileOperation

__all__ = (
    "UploadedFile",
    "TemporaryUploadedFile",
    "InMemoryUploadedFile",
    "SimpleUploadedFile",
)


def validate_file_name(name, allow_relative_path=False):
    # Remove potentially dangerous names
    if os.path.basename(name) in {"", ".", ".."}:
        raise SuspiciousFileOperation("Could not derive file name from '%s'" % name)

    if allow_relative_path:
        # Ensure that name can be treated as a pure posix path, i.e. Unix
        # style (with forward slashes).
        path = pathlib.PurePosixPath(str(name).replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise SuspiciousFileOperation(
                "Detected path traversal attempt in '%s'" % name
            )
    elif name != os.path.basename(name):
        raise SuspiciousFileOperation("File name '%s' includes path elements" % name)

    return name


class cached_property:
    """
    Decorator that converts a method with a single self argument into a
    property cached on the instance.

    A cached property can be made out of an existing method:
    (e.g. ``url = cached_property(get_absolute_url)``).
    """

    name = None

    @staticmethod
    def func(instance):
        raise TypeError(
            "Cannot use cached_property instance without calling "
            "__set_name__() on it."
        )

    def __init__(self, func):
        self.real_func = func
        self.__doc__ = getattr(func, "__doc__")

    def __set_name__(self, owner, name):
        if self.name is None:
            self.name = name
            self.func = self.real_func
        elif name != self.name:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                "(%r and %r)." % (self.name, name)
            )

    def __get__(self, instance, cls=None):
        """
        Call the function and put the return value in instance.__dict__ so that
        subsequent attribute access on the instance returns the cached value
        instead of calling cached_property.__get__().
        """
        if instance is None:
            return self
        res = instance.__dict__[self.name] = self.func(instance)
        return res


class FileProxyMixin:
    """
    A mixin class used to forward file methods to an underlying file
    object.  The internal file object has to be called "file"::

        class FileProxy(FileProxyMixin):
            def __init__(self, file):
                self.file = file
    """

    encoding = property(lambda self: self.file.encoding)
    fileno = property(lambda self: self.file.fileno)
    flush = property(lambda self: self.file.flush)
    isatty = property(lambda self: self.file.isatty)
    newlines = property(lambda self: self.file.newlines)
    read = property(lambda self: self.file.read)
    readinto = property(lambda self: self.file.readinto)
    readline = property(lambda self: self.file.readline)
    readlines = property(lambda self: self.file.readlines)
    seek = property(lambda self: self.file.seek)
    tell = property(lambda self: self.file.tell)
    truncate = property(lambda self: self.file.truncate)
    write = property(lambda self: self.file.write)
    writelines = property(lambda self: self.file.writelines)

    @property
    def closed(self):
        return not self.file or self.file.closed

    def readable(self):
        if self.closed:
            return False
        if hasattr(self.file, "readable"):
            return self.file.readable()
        return True

    def writable(self):
        if self.closed:
            return False
        if hasattr(self.file, "writable"):
            return self.file.writable()
        return "w" in getattr(self.file, "mode", "")

    def seekable(self):
        if self.closed:
            return False
        if hasattr(self.file, "seekable"):
            return self.file.seekable()
        return True

    def __iter__(self):
        return iter(self.file)


class File(FileProxyMixin):
    DEFAULT_CHUNK_SIZE = 64 * 2**10

    def __init__(self, file, name=None):
        self.file = file
        if name is None:
            name = getattr(file, "name", None)
        self.name = name
        if hasattr(file, "mode"):
            self.mode = file.mode

    def __str__(self):
        return self.name or ""

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self or "None")

    def __bool__(self):
        return bool(self.name)

    def __len__(self):
        return self.size

    @cached_property
    def size(self):
        if hasattr(self.file, "size"):
            return self.file.size
        if hasattr(self.file, "name"):
            try:
                return os.path.getsize(self.file.name)
            except (OSError, TypeError):
                pass
        if hasattr(self.file, "tell") and hasattr(self.file, "seek"):
            pos = self.file.tell()
            self.file.seek(0, os.SEEK_END)
            size = self.file.tell()
            self.file.seek(pos)
            return size
        raise AttributeError("Unable to determine the file's size.")

    def chunks(self, chunk_size=None):
        """
        Read the file and yield chunks of ``chunk_size`` bytes (defaults to
        ``File.DEFAULT_CHUNK_SIZE``).
        """
        chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        try:
            self.seek(0)
        except (AttributeError, UnsupportedOperation):
            pass

        while True:
            data = self.read(chunk_size)
            if not data:
                break
            yield data

    def multiple_chunks(self, chunk_size=None):
        """
        Return ``True`` if you can expect multiple chunks.

        NB: If a particular file representation is in memory, subclasses should
        always return ``False`` -- there's no good reason to read from memory in
        chunks.
        """
        return self.size > (chunk_size or self.DEFAULT_CHUNK_SIZE)

    def __iter__(self):
        # Iterate over this file-like object by newlines
        buffer_ = None
        for chunk in self.chunks():
            for line in chunk.splitlines(True):
                if buffer_:
                    if endswith_cr(buffer_) and not equals_lf(line):
                        # Line split after a \r newline; yield buffer_.
                        yield buffer_
                        # Continue with line.
                    else:
                        # Line either split without a newline (line
                        # continues after buffer_) or with \r\n
                        # newline (line == b'\n').
                        line = buffer_ + line
                    # buffer_ handled, clear it.
                    buffer_ = None

                # If this is the end of a \n or \r\n line, yield.
                if endswith_lf(line):
                    yield line
                else:
                    buffer_ = line

        if buffer_ is not None:
            yield buffer_

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def open(self, mode=None, *args, **kwargs):
        if not self.closed:
            self.seek(0)
        elif self.name and os.path.exists(self.name):
            self.file = open(self.name, mode or self.mode, *args, **kwargs)
        else:
            raise ValueError("The file cannot be reopened.")
        return self

    def close(self):
        self.file.close()


class ContentFile(File):
    """
    A File-like object that takes just raw content, rather than an actual file.
    """

    def __init__(self, content, name=None, content_type=None):
        stream_class = StringIO if isinstance(content, str) else BytesIO
        super().__init__(stream_class(content), name=name)
        self.size = len(content)

    def __str__(self):
        return "Raw content"

    def __bool__(self):
        return True

    def open(self, mode=None):
        self.seek(0)
        return self

    def close(self):
        pass

    def write(self, data):
        self.__dict__.pop("size", None)  # Clear the computed size.
        return self.file.write(data)

    @classmethod
    def guess_content_type(cls, content: bytes) -> str:
        from magika import Magika

        magika = Magika()
        mresult = magika.identify_bytes(content)
        return mresult.output.mime_type

    @property
    def content_type(self):
        # determine content type from file name
        return self.guess_content_type(self.read())


def endswith_cr(line):
    """Return True if line (a text or bytestring) ends with '\r'."""
    return line.endswith("\r" if isinstance(line, str) else b"\r")


def endswith_lf(line):
    """Return True if line (a text or bytestring) ends with '\n'."""
    return line.endswith("\n" if isinstance(line, str) else b"\n")


def equals_lf(line):
    """Return True if line (a text or bytestring) equals '\n'."""
    return line == ("\n" if isinstance(line, str) else b"\n")


"""
Classes representing uploaded files.
"""


class UploadedFile(File):
    """
    An abstract uploaded file (``TemporaryUploadedFile`` and
    ``InMemoryUploadedFile`` are the built-in concrete subclasses).

    An ``UploadedFile`` object behaves somewhat like a file object and
    represents some file data that the user submitted with a form.
    """

    def __init__(
        self,
        file=None,
        name=None,
        content_type=None,
        size=None,
        charset=None,
        content_type_extra=None,
    ):
        super().__init__(file, name)
        self.size = size
        self.content_type = content_type
        self.charset = charset
        self.content_type_extra = content_type_extra

    def __repr__(self):
        return "<%s: %s (%s)>" % (self.__class__.__name__, self.name, self.content_type)

    def _get_name(self):
        return self._name

    def _set_name(self, name):
        # Sanitize the file name so that it can't be dangerous.
        if name is not None:
            # Just use the basename of the file -- anything else is dangerous.
            name = os.path.basename(name)

            # File names longer than 255 characters can cause problems on older OSes.
            if len(name) > 255:
                name, ext = os.path.splitext(name)
                ext = ext[:255]
                name = name[: 255 - len(ext)] + ext

            name = validate_file_name(name)

        self._name = name

    name = property(_get_name, _set_name)


class TemporaryUploadedFile(UploadedFile):
    """
    A file uploaded to a temporary location (i.e. stream-to-disk).
    """

    def __init__(self, name, content_type, size, charset, content_type_extra=None):
        _, ext = os.path.splitext(name)
        file = tempfile.NamedTemporaryFile(
            suffix=".upload" + ext,
        )
        super().__init__(file, name, content_type, size, charset, content_type_extra)

    def temporary_file_path(self):
        """Return the full path of this file."""
        return self.file.name

    def close(self):
        try:
            return self.file.close()
        except FileNotFoundError:
            # The file was moved or deleted before the tempfile could unlink
            # it. Still sets self.file.close_called and calls
            # self.file.file.close() before the exception.
            pass


class InMemoryUploadedFile(UploadedFile):
    """
    A file uploaded into memory (i.e. stream-to-memory).
    """

    def __init__(
        self,
        file,
        field_name,
        name,
        content_type,
        size,
        charset,
        content_type_extra=None,
    ):
        super().__init__(file, name, content_type, size, charset, content_type_extra)
        self.field_name = field_name

    def open(self, mode=None):
        self.file.seek(0)
        return self

    def chunks(self, chunk_size=None):
        self.file.seek(0)
        yield self.read()

    def multiple_chunks(self, chunk_size=None):
        # Since it's in memory, we'll never have multiple chunks.
        return False


class SimpleUploadedFile(InMemoryUploadedFile):
    """
    A simple representation of a file, which just has content, size, and a name.
    """

    def __init__(self, name, content, content_type="text/plain"):
        content = content or b""
        super().__init__(
            BytesIO(content), None, name, content_type, len(content), None, None
        )

    @classmethod
    def from_dict(cls, file_dict):
        """
        Create a SimpleUploadedFile object from a dictionary with keys:
           - filename
           - content-type
           - content
        """
        return cls(
            file_dict["filename"],
            file_dict["content"],
            file_dict.get("content-type", "text/plain"),
        )
