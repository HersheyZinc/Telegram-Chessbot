from othello.board import Board
from copy import deepcopy
import numpy as np


def eval_endgame(board: Board):
    return board.black_disc_count - board.white_disc_count

def eval_midgame(board: Board):
    
    # coin parity heuristic
    coin_parity = (board.black_disc_count - board.white_disc_count) / (board.black_disc_count + board.white_disc_count)
    
    # mobility heuristic value
    black_mobility = len(board.all_legal_moves(Board.BLACK))
    white_mobility = len(board.all_legal_moves(Board.WHITE))
    actual_mobility = (black_mobility - white_mobility) / (black_mobility + white_mobility)


    # static weight heuristic value
    static_weights = np.array([
                    [5, -3, 2, 2, 2, 2, -3, 5],
                    [-3, -4, -1, -1, -1, -1, -4, -3],
                    [2, -1, 1, 0, 0, 1, -1, 2],
                    [2, -1, 0, 1, 1, 0, -1, 2],
                    [2, -1, 0, 1, 1, 0, -1, 2],
                    [2, -1, 1, 0, 0, 1, -1, 2],
                    [-3, -4, -1, -1, -1, -1, -4, -3],
                    [5, -3, 2, 2, 2, 2, -3, 5]
                  ]).flatten()
    black_weights = sum(value for value, coin in zip(static_weights, board.board.flatten()) if coin == Board.BLACK)
    white_weights = sum(value for value, coin in zip(static_weights, board.board.flatten()) if coin == Board.WHITE)

    if black_weights + white_weights == 0:
        weight_value = 0
    else:
        weight_value = (black_weights - white_weights) / (black_weights + white_weights)

    #return weight_value * 64
    return (coin_parity + actual_mobility*2 + weight_value*2)/5 * 64

def eval_earlygame(board:Board):
    if board.black_disc_count == 0:
        coin_parity == -1
    elif board.white_disc_count == 0:
        coin_parity == 1
    else:
        coin_parity = -(board.black_disc_count - board.white_disc_count) / (board.black_disc_count + board.white_disc_count)

    static_weights = np.array([
                    [5, -4, 1, 1, 1, 1, -4, 5],
                    [-4, -4, 0, 0, 0, 0, -4, -4],
                    [1, 0, 0, 0, 0, 0, 0, 1],
                    [1, 0, 0, 0, 0, 0, 0, 1],
                    [1, 0, 0, 0, 0, 0, 0, 1],
                    [1, 0, 0, 0, 0, 0, 0, 1],
                    [-4, -4, 0, 0, 0, 0, -4, -4],
                    [5, -4, 1, 1, 1, 1, -4, 5]
                  ]).flatten()
    black_weights = sum(value for value, coin in zip(static_weights, board.board.flatten()) if coin == Board.BLACK)
    white_weights = sum(value for value, coin in zip(static_weights, board.board.flatten()) if coin == Board.WHITE)

    if black_weights + white_weights == 0:
        weight_value = 0
    else:
        weight_value = (black_weights - white_weights) / (black_weights + white_weights)

    return (coin_parity + weight_value*3) / 4 * 64


def minimax(position: Board, depth: int, alpha: int, beta: int, eval_fun=eval_endgame) -> int:
    if position.check_game_over():
        return eval_endgame(position)
    elif depth == 0:
        return eval_fun(position)
    
    # maximizing player's turn - Black
    if position.turn == Board.BLACK:
        maxEval = float('-inf')
        legal_moves = position.all_legal_moves(Board.BLACK)
        for row, col in legal_moves:
            if position.board[row, col] == Board.EMPTY:
                temp_position = deepcopy(position)
                temp_position.push((row,col))

                eval = minimax(temp_position, depth - 1, alpha, beta, eval_fun=eval_fun)
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

            eval = minimax(temp_position, depth - 1, alpha, beta, eval_fun=eval_fun)
            minEval = min(minEval, eval)

            beta = min(beta, eval)
            if beta <= alpha:
                break

    return minEval


def find_best_moves(position: Board, n=4) -> list:
    moves = []

    legal_moves = position.all_legal_moves(position.turn)

    if position.move > 52:
        eval_function, depth = eval_endgame, 10
    elif position.move > 20:
        eval_function, depth = eval_midgame, 1
    else:
        eval_function, depth = eval_midgame, 0
    
    for row, col in legal_moves:
        if position.board[row, col] == Board.EMPTY:
            temp_position = deepcopy(position)
            temp_position.push((row,col))

            currentEval = minimax(temp_position, depth, float('-inf'), float('inf'), eval_function)
            moves.append({"coord":(row,col), "move": Board.coord2move((row,col)), "eval":currentEval*position.turn})
        
        moves.sort(key=lambda x: x["eval"], reverse=True)
        moves = moves[:min(len(moves), n)]
    return moves









