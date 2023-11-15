import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os, tempfile

class Board:
    WHITE =  -1
    BLACK =  1
    EMPTY =  0
    ROWNAMES = "abcdefgh"
    DIRECTIONS = (  ( 1, 0),    # right
                    (-1, 0),    # left
                    ( 0, 1),    # down
                    (-1, 1),    # downwards left
                    ( 1, 1),    # downwards right
                    ( 0,-1),    # up
                    (-1,-1),    # upwards left
                    ( 1,-1),    # upwards right
                )

    def __init__(self, board_state=None) -> None:
        '''Initiliaze the Othello game board with a 8x8 numpy matrix'''
        self.board = np.array([0]*8, dtype = np.int8)   # initiliasing 1D array with the first row of 8 zeroes
        self.board = self.board[np.newaxis, : ]   
        self.move = 0      # expanding 1D array to 2D array
        for _ in range(3):                              # increasing rows till 8
            self.board = np.concatenate((self.board, self.board), axis = 0)
        self.black_disc_count = self.white_disc_count = 0
        
        if not board_state:
            self.reset_board()
        else:
            self.set_board_state(board_state)
            
    
    @staticmethod
    def checkCoordRange(x: int, y: int) -> bool:
        '''Returns true if the given parameters represent an actual cell in a 8x8 matrix'''

        return (x >= 0 and y >= 0) and (x < 8 and y < 8)

    @staticmethod
    def move2coord(move:str) -> tuple:
        c = Board.ROWNAMES.index(move[0].lower())
        r = int(move[1]) - 1
        return (r,c)
    
    @staticmethod
    def coord2move(coord:tuple) -> str:
        r,c = coord
        return f"{Board.ROWNAMES[c]}{r + 1}"

    def all_legal_moves(self, PLAYER: int=None) -> set:
        '''Return all legal moves for the player'''
        if not PLAYER:
            PLAYER = self.turn
        all_legal_moves = set()
        for row in range(8):
            for col in range(8):
                if self.board[row, col] == PLAYER:
                    all_legal_moves.update(self.legal_moves(row, col))
        
        return all_legal_moves

    def legal_moves(self, r: int, c: int) -> list:
        '''Return all legal moves for the cell at the given position'''

        PLAYER = self.board[r, c]
        OPPONENT = PLAYER * -1

        legal_moves = []
        for dir in Board.DIRECTIONS:
            rowDir, colDir = dir
            row = r + rowDir
            col = c + colDir
                
            if Board.checkCoordRange(row, col) is False or self.board[row, col] != OPPONENT:
                continue
            
            row += rowDir
            col += colDir
            while (Board.checkCoordRange(row, col) is True and self.board[row, col] == OPPONENT):
                row += rowDir
                col += colDir
            if (Board.checkCoordRange(row, col) is True and self.board[row, col] == Board.EMPTY):   # possible move
                legal_moves.append((row, col))

        return legal_moves

    def flipDiscs(self, PLAYER: int, initCoords: tuple[int, int], endCoords: tuple[int, int], direction: tuple[int, int]):
        '''Flip the discs between the given two cells to the given PLAYER color.'''

        OPPONENT = PLAYER * -1
        rowDir, colDir = direction

        row, col = initCoords
        row += rowDir
        col += colDir 

        r, c = endCoords

        while (self.board[row, col] == OPPONENT) and (row != r or col != c):
            self.board[row, col] = PLAYER
            row += rowDir
            col += colDir

    def is_legal_move(self, move:str):
        move = Board.move2coord(move)
        return move in self.all_legal_moves()

    def set_discs(self, row: int, col: int, PLAYER: int=None) -> None:
        '''Set the discs on the board as per the move made on the given cell'''
        if not PLAYER:
            PLAYER = self.turn
        self.board[row, col] = PLAYER
        OPPONENT = PLAYER * - 1
        
        for dir in Board.DIRECTIONS:
            rowDir, colDir = dir
            r = row + rowDir
            c = col + colDir

            if Board.checkCoordRange(r, c) is False or self.board[r, c] != OPPONENT:
                continue
            
            r += rowDir
            c += colDir
            while (Board.checkCoordRange(r, c) is True and self.board[r, c] == OPPONENT):
                r += rowDir
                c += colDir
            if (Board.checkCoordRange(r, c) is True and self.board[r, c] == PLAYER):
                self.flipDiscs(PLAYER, (row, col), (r, c), dir) 
                
        # update disc counters
        self.black_disc_count = self.board[self.board > 0].sum()
        self.white_disc_count = -self.board[self.board < 0].sum()


    def push(self, move:str|tuple):
        if isinstance(move, str):
            x, y = Board.move2coord(move)
        elif isinstance(move, tuple):
            x, y = move
        self.set_discs(x,y,self.turn)
        self.turn *= -1
        self.move += 1

        if len(self.all_legal_moves()) == 0:
            self.turn *= -1


    def print_board(self) -> None:
        print(self.board)


    def get_board_img(self, moves=None):
        im = Image.open("./othello/othello_board.png")
        draw = ImageDraw.Draw(im)
        border_size = 34
        tile_size = 75
        tile_buffer = 3

        for r, row in enumerate(self.board):
            for c, tile in enumerate(row):
                x1 = border_size + c*tile_size + tile_buffer
                y1 = border_size + r*tile_size + tile_buffer
                x2 = border_size + (c+1)*tile_size - tile_buffer
                y2 = border_size + (r+1)*tile_size - tile_buffer
                if tile == Board.WHITE:
                    fill = "white"
                elif tile == Board.BLACK:
                    fill = "black"
                else:
                    continue
                draw.ellipse((x1, y1, x2, y2), fill = fill, outline ='black')
        if moves:
            font = ImageFont.truetype("othello/ARIAL.TTF", size=40)
            for move in moves:
                r, c = move["coord"]
                eval_str = str(int(move["eval"]))
                x1 = border_size + c*tile_size + tile_buffer
                y1 = border_size + r*tile_size + tile_buffer
                draw.text((x1,y1,x2,y2),eval_str, fill="orange", font=font)
            
        with tempfile.TemporaryDirectory() as tmpdirname:
            temp_path = os.path.join(tmpdirname, "board.png")
            im.save(temp_path)
            im_bytes = open(temp_path, "rb")
            return im_bytes, im


    def get_score(self) -> dict:
        if self.black_disc_count > self.white_disc_count:
            outcome = Board.BLACK
        elif self.black_disc_count < self.white_disc_count:
            outcome = Board.WHITE
        else:
            outcome = None
        output = {"winner": outcome, "white": self.white_disc_count, "black": self.black_disc_count}
        return output


    def reset_board(self) -> None:
        self.board.fill(Board.EMPTY)

        # initiliasing the centre squares
        self.board[3, 3] = self.board[4,4] = Board.WHITE
        self.board[3, 4] = self.board[4,3] = Board.BLACK

        self.black_disc_count = self.white_disc_count = 2
        self.turn = Board.BLACK

    def check_game_over(self) -> bool:
        possibleBlackMoves = self.all_legal_moves(Board.BLACK)
        possibleWhiteMoves = self.all_legal_moves(Board.WHITE)

        if possibleBlackMoves or possibleWhiteMoves:
            return False
        return True


    def set_board_state(self, board_state:str):
        mapping = {"b":Board.BLACK, "w":Board.WHITE, "x":Board.EMPTY}
        self.turn = mapping[board_state[-1]]
        for r in range(8):
            for c in range(8):
                tile_value = board_state[r*8+c]
                disc = mapping[tile_value]
                self.board[r,c] = disc

        self.black_disc_count = self.board[self.board > 0].sum()
        self.white_disc_count = -self.board[self.board < 0].sum()
        self.move = self.white_disc_count + self.black_disc_count - 4


    def get_board_state(self):
        mapping = {Board.BLACK:"b", Board.WHITE:"w", Board.EMPTY:"x"}
        board_state = "".join([mapping[x] for x in self.board.flatten()])
        board_state = board_state + " " + mapping[self.turn]
        return board_state

    
