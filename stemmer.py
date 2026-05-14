import codecs
import unicodedata
import regex

from .affix_loader import load_affixes

def graphemes(text):
    return regex.findall(r'\X', unicodedata.normalize('NFC', text))

def split_into_units(text):
    clusters = graphemes(text)
    lonsum_set = set('ꯛꯜꯝꯞꯟꯠꯡꯢ')
    result = []
    for cl in clusters:
        if cl in lonsum_set and result:
            result[-1] += cl
        else:
            result.append(cl)
    return result

class ManipuriStemmer:
    def __init__(self, prefix_file, suffix_file):
        self.prefixes = load_affixes(prefix_file)
        self.suffixes = load_affixes(suffix_file)

    def remove_prefixes(self, word):
        chars = split_into_units(word)
        for p in self.prefixes:
            p_chars = split_into_units(p)
            if len(chars) >= len(p_chars) and chars[:len(p_chars)] == p_chars:
                if len(chars) == len(p_chars):
                    continue
                chars = chars[len(p_chars):]
                break
        return ''.join(chars)

    def remove_suffixes(self, word):
        chars = split_into_units(word)
        while True:
            removed = False
            for s in self.suffixes:
                s_chars = split_into_units(s)
                if len(chars) >= len(s_chars) and chars[-len(s_chars):] == s_chars:
                    if len(chars) == len(s_chars):
                        continue
                    chars = chars[:-len(s_chars)]
                    removed = True
                    break
            if not removed:
                break
        return ''.join(chars)

    def stem(self, word):
        if not word:
            return word
        w = self.remove_prefixes(word)
        w = self.remove_suffixes(w)
        return w

    def stem_iterative(self, word):
        prev = None
        w = unicodedata.normalize('NFC', word)
        while prev != w:
            prev = w
            w = self.remove_prefixes(w)
            w = self.remove_suffixes(w)
        return w