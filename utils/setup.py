import pandas as pd
import os, requests, zstandard, logging

PUZZLEURL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
PUZZLE_PATH = "./data/chess_puzzles.csv" # Hardcoded path

STOCKFISHURL = "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-ubuntu-x86-64-avx2.tar"
STOCKFISH_PATH = "./stockfish/stockfish-ubuntu-x86-64-avx2" # Hardcoded path
#STOCKFISH_PATH = "./stockfish/stockfish-windows-x86-64-avx2" # Hardcoded path

def download_chess_puzzles(rating_lower=None, rating_upper=None, count=1000000, overwrite=False):
    """
    Downloads Lichess puzzle database and uncompresses it.
    Performs simple cleaning to reduce file size.
    """
    logging.info("Downloading Lichess puzzle database")
    if os.path.isfile(PUZZLE_PATH) and not overwrite:
        logging.info("Lichess CSV file already exists! Skipping...")
        return
    
    # Download lichess puzzle database
    
    response = requests.get(PUZZLEURL, timeout=60)

    # # Download zst file
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
    if rating_lower:
        df2 = df2[df2["Rating"] >= rating_lower]
    if rating_upper:
        df2 = df2[df2["Rating"] <= rating_upper]

    # Grab the first 1 million rows
    df2 = df2.iloc[:count]

    # Keep only FEN, moves and rating rows
    df2 = df2[["FEN","Moves","Rating"]]

    # Write cleaned csv file
    df2.to_csv(PUZZLE_PATH,index=False)
    os.remove("lichess_db_puzzle.csv")
    os.remove("lichess_db_puzzle.csv.zst")


def download_stockfish():
    """
    Downloads stockfish engine
    """
    logging.info("Downloading Stockfish 16")
    if os.path.isdir("stockfish"):
        logging.info("Stockfish already exists! Skipping...")
        return
    
    # Download stockfish from github
    response = requests.get(STOCKFISHURL, timeout=60)

    # Download tar file
    with open("stockfish.tar", "wb") as f:
        f.write(response.content)

    # Uncompress the tar file
    os.system("tar -xvf stockfish.tar")
    os.remove("stockfish.tar")


def setup():
    """
    Downloads and formats necessary files needed for chessbot to function
    """
    logging.info("Downloading database and chess engines...")
    os.makedirs("./data", exist_ok=True)
    download_chess_puzzles(rating_lower=1450)
    download_stockfish()
    logging.info("Download complete!")


if __name__ == "__main__":
    download_chess_puzzles(rating_lower=1800)