def normalize_unicode(text):
    import unicodedata
    return unicodedata.normalize('NFC', text)