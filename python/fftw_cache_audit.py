"""Count successful cached-interface DCT plan creations, without wrapping cache hits.

pyFFTW's dctn and idctn interfaces both create plans through builders.dct.
Direct pyfftw.FFTW plans are intentionally outside this counter.
"""
import functools

_builders = None
_original = None
_wrapper = None
_creations = 0


def install():
    """Install once per process; a fresh installation starts the count at zero."""
    global _builders, _original, _wrapper, _creations
    if _wrapper is not None:
        if _builders.dct is not _wrapper:
            raise RuntimeError('pyFFTW builders.dct changed while the audit was installed.')
        return
    from pyfftw import builders
    original = builders.dct

    @functools.wraps(original)
    def counted(*args, **kwargs):
        global _creations
        plan = original(*args, **kwargs)
        _creations += 1
        return plan

    _creations = 0
    _builders, _original, _wrapper = builders, original, counted
    builders.dct = counted


def count():
    """Return successful builder calls since installation, including warmup/setup."""
    return _creations


def restore():
    """Restore the original builder; leave the final count readable."""
    global _builders, _original, _wrapper
    if _wrapper is None:
        return
    if _builders.dct is not _wrapper:
        raise RuntimeError('Refusing to overwrite another pyFFTW builder replacement.')
    _builders.dct = _original
    _builders = _original = _wrapper = None
