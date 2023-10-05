from othello.board import Board

def minimax(position: Board, depth: int, alpha: int, beta: int, isMaximizingPlayer: bool) -> int:
    if depth == 0 or position.check_game_over() is True:
        return position.evaluate_board()

    if isMaximizingPlayer == Board.BLACK:
        maxEval = float('-inf')
        legal_moves = position.all_legal_moves(Board.BLACK)
        for row, col in legal_moves:
            if position.board[row, col] == Board.EMPTY:
                position.board[row, col] = Board.BLACK

                opponents_moves = position.all_legal_moves(Board.WHITE)
                eval = minimax(position, depth - 1, alpha, beta, len(opponents_moves) == 0)
                maxEval = max(maxEval, eval)

                alpha = max(alpha, eval)
                position.board[row, col] = Board.EMPTY
                if beta <= alpha:
                    break

                return maxEval

    # else minimizing player's turn
    minEval = float('+inf')
    legal_moves = position.all_legal_moves(Board.WHITE)
    for row, col in legal_moves:
        if position.board[row, col] == Board.EMPTY:
            position.board[row, col] = Board.WHITE

            opponents_moves = position.all_legal_moves(Board.BLACK)
            eval = minimax(position, depth - 1, alpha, beta, len(opponents_moves) != 0)
            minEval = min(minEval, eval)

            beta = min(beta, eval)
            position.board[row, col] = Board.EMPTY
            if beta <= alpha:
                break

    return minEval


def find_best_moves(position: Board, n=4, depth=3) -> list:
    moves = []

    legal_moves = position.all_legal_moves(position.turn)
    
    for row, col in legal_moves:
        if position.board[row, col] == Board.EMPTY:
            position.board[row, col] = position.turn
            
            isMaximizingPlayer = True if position.turn == Board.WHITE else False
            currentEval = minimax(position, depth, float('-inf'), float('inf'), isMaximizingPlayer)
            
            position.board[row, col] = Board.EMPTY

            moves.append({"move":(row,col), "eval":currentEval})
        
        moves.sort(key=lambda x: x["eval"]*position.turn, reverse=True)
        moves = moves[:min(len(moves), n)]
    return moves
