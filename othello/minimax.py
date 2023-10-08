from othello.board import Board
from copy import deepcopy

def minimax(position: Board, depth: int, alpha: int, beta: int) -> int:
    if depth == 0 or position.check_game_over() is True:
        return position.evaluate_board()
    
    # maximizing player's turn - Black
    if position.turn == Board.BLACK:
        maxEval = float('-inf')
        legal_moves = position.all_legal_moves(Board.BLACK)
        for row, col in legal_moves:
            if position.board[row, col] == Board.EMPTY:
                temp_position = deepcopy(position)
                temp_position.push((row,col))

                eval = minimax(temp_position, depth - 1, alpha, beta)
                maxEval = max(maxEval, eval)

                alpha = max(alpha, eval)
                if beta <= alpha:
                    break

        return maxEval

    # else minimizing player's turn - White
    minEval = float('+inf')
    legal_moves = position.all_legal_moves(Board.WHITE)
    for row, col in legal_moves:
        if position.board[row, col] == Board.EMPTY:
            temp_position = deepcopy(position)
            temp_position.push((row,col))

            eval = minimax(temp_position, depth - 1, alpha, beta)
            minEval = min(minEval, eval)

            beta = min(beta, eval)
            if beta <= alpha:
                break

    return minEval


def find_best_moves(position: Board, n=4, depth=3) -> list:
    moves = []

    legal_moves = position.all_legal_moves(position.turn)
    
    for row, col in legal_moves:
        if position.board[row, col] == Board.EMPTY:
            temp_position = deepcopy(position)
            temp_position.push((row,col))

            currentEval = minimax(temp_position, depth, float('-inf'), float('inf'))
            moves.append({"coord":(row,col), "move": Board.coord2move((row,col)), "eval":currentEval})
        
        moves.sort(key=lambda x: x["eval"]*position.turn, reverse=True)
        moves = moves[:min(len(moves), n)]
    return moves
