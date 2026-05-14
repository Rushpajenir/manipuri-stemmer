import pandas as pd

# Read and remove duplicates
df = pd.read_csv("C://Users/heisn/manipuri-stemmer-grapheme/data/corpus/to_annotate.csv")
df = df.drop_duplicates(subset=['word'], keep='first').reset_index(drop=True)

# Save back to same file
df.to_csv("C://Users/heisn/manipuri-stemmer-grapheme/data/corpus/to_annotate.csv", index=False)

print(f"Dataset now has {len(df)} unique words")