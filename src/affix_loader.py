import codecs
import unicodedata

def load_affixes(filepath):
    """Load affixes from a UTF-8 text file.
       Lines can contain: 'affix' or 'affix  # comment'.
       Only the affix (before '#') is kept, normalised to NFC.
    """
    affixes = []
    with codecs.open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '#' in line:
                line = line[:line.index('#')]
            line = line.strip()
            if line:
                affixes.append(unicodedata.normalize('NFC', line))
    affixes.sort(key=len, reverse=True)
    return affixes