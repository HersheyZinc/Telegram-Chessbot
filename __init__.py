import pandas as pd
import os, requests, zstandard
import requests

# Download lichess puzzle database
PUZZLEURL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
response = requests.get(PUZZLEURL)

# Download zst file
with open("lichess_db_puzzle.csv.zst", "wb") as f:
    f.write(response.content)

# Uncompress zst file
with open("lichess_db_puzzle.csv.zst", "rb") as f:
    decomp = zstandard.ZstdDecompressor()
    with open("lichess_db_puzzle.csv", 'wb') as destination:
        decomp.copy_stream(f, destination)

# Read csv file as pandas dataframe
df = pd.read_csv("lichess_db_puzzle.csv")

# Filter puzzles by length and rating
df2 = df[df["Themes"].str.contains("short")]
df2 = df2[df2["Rating"] > 1350]

# Grab the first 1 million rows
df2 = df2.iloc[:1000000]

# Keep only FEN, moves and rating rows
df2 = df2[["FEN","Moves","Rating"]]

# Write cleaned csv file
df2.to_csv("chess_puzzles.csv")
os.remove("lichess_db_puzzle.csv")
os.remove("lichess_db_puzzle.csv.zst")


# Download stockfish from github
STOCKFISHURL = "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-ubuntu-x86-64-avx2.tar"
response = requests.get(STOCKFISHURL)

# Download tar file
with open("stockfish.tar", "wb") as f:
    f.write(response.content)

# Uncompress the tar file
os.system("tar -xvf stockfish.tar")
os.remove("stockfish.tar")