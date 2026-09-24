import chess
import time

from noodlesnake import helpers
from noodlesnake.controller import PositionController
from noodlesnake.transposition import TranspositionTableEntry, EXACT, UPPER, LOWER


class _SearchStopped(Exception):
    pass


class NoodlesnakeEngine:
    __slots__ = ('controller', 'transposition', 'history', 'butterfly', 'killer', '_deadline', '_stop_event')
    def __init__(self):
        self.controller = PositionController()

        self.transposition = {}

        # Relative history heuristic
        self.history = [[[0] * 64 for _ in range(64)] for _ in range(2)]
        self.butterfly = [[[0] * 64 for _ in range(64)] for _ in range(2)]

        # Killer heuristic
        self.killer = [[None] * 20 for _ in range(2)]

    def get_move(self, board, time_limit=5, stop_event=None):
        """Return the best move given a chess board"""
        self.controller.set_board(board)
        self._stop_event = stop_event
        return self._IDS(board, time_limit=time_limit)

    def _IDS(self, board, depth_limit=10, time_limit=5):
        """
        Iterative deepening search algorithm to find 
        best chess move for specified colour within depth limit and time limit
        """
        self._deadline = time.perf_counter() + time_limit
        best_move = next(iter(board.legal_moves), None)

        for depth in range(1, depth_limit + 1):
            try:
                _, completed_move = self._negamax(board, float('-inf'), float('inf'), depth, True, root=True)
            except _SearchStopped:
                break

            if completed_move is not None:
                best_move = completed_move
        return best_move

    def _quiescence(self, depth, board):
        if depth <= 0 or board.is_game_over():
            return

    def _negamax(self, board, alpha, beta, depth, do_null, root=False):
        if time.perf_counter() >= self._deadline or (self._stop_event is not None and self._stop_event.is_set()):
            raise _SearchStopped

        alpha_orig = alpha

        outcome = board.outcome()
        if outcome is not None:
            score = 0 if outcome.winner is None else -100000 - depth
            return score, None
        can_claim_draw = board.is_fifty_moves() or board.is_repetition(3)
        use_table = not (root and can_claim_draw)

        position_key = self.controller.position_key
        entry = self.transposition.get(position_key) if use_table else None
        if entry is not None and entry.depth >= depth:
            if entry.flag == EXACT:
                return entry.score, entry.move
            elif entry.flag == LOWER:
                alpha = max(alpha, entry.score)
            elif entry.flag == UPPER:
                beta = min(beta, entry.score)

            if alpha >= beta:
                return entry.score, entry.move

        if depth <= 0:
            score = self.static_evaluation(board) - depth
            return max(0, score) if can_claim_draw and not root else score, None

        # Null move pruning
        if do_null and not board.is_check():
            self.controller.make_null_move()
            try:
                R = 2
                score = -self._negamax(board, -beta, -beta+1, depth-R, False)[0]
            finally:
                self.controller.unmake_null_move()
            
            if score >= beta:
                return score, None

        best_move = None
        best_score = 0 if can_claim_draw and not root else float('-inf')
        alpha = max(alpha, best_score)
        if alpha >= beta:
            return best_score, None

        def move_score(move):
            if entry is not None and entry.flag == EXACT and entry.move == move:
                return 10000

            # Captures
            if (capture_square := helpers.captured_piece_square(board, move)) is not None:
                piece_scores = [1, 3, 3, 5, 9, 10000]  # Pawn, Knight, Bishop, Rook, Queen, King
                capture = board.piece_at(capture_square)
                attacker = board.piece_at(move.from_square)
                exchange = piece_scores[capture.piece_type-1] - piece_scores[attacker.piece_type-1]

                # Losing captures are after killers and winning captures are first
                return 100 if exchange < 0 else (1000+exchange) * 5

            # Killer moves
            if move == self.killer[0][depth]:
                return 500
            elif move == self.killer[1][depth]:
                return 400
                
            # Quiet move, use relative history heuristic
            hh = self.history[board.turn][move.from_square][move.to_square]
            bf = self.butterfly[board.turn][move.from_square][move.to_square]
            return 0 if bf == 0 else hh / bf

        moves = list(board.legal_moves)
        moves.sort(key=move_score, reverse=True)

        for move in moves:
            self.controller.move(move)
            try:
                score = -self._negamax(board, -beta, -alpha, depth-1, True)[0]
            finally:
                self.controller.unmove()

            if score > best_score:
                best_score = score
                best_move = move

            is_capture = board.is_capture(move)
            alpha = max(alpha, best_score)
            
            if alpha >= beta:
                if not is_capture:
                    self.history[board.turn][move.from_square][move.to_square] += depth * depth
                    if self.killer[0][depth] != move:
                        self.killer[1][depth] = self.killer[0][depth]
                        self.killer[0][depth] = move
                break
            else:
                if not is_capture:
                    self.butterfly[board.turn][move.from_square][move.to_square] += depth

        if use_table:
            if best_score <= alpha_orig:
                flag = UPPER
            elif score >= beta:
                flag = LOWER
            else:
                flag = EXACT
            self.transposition[position_key] = TranspositionTableEntry(flag, depth, best_move, best_score)

        return best_score, best_move

    def static_evaluation(self, board):
        """Return the evaluation in terms of material"""
        if (outcome := board.outcome()) is not None:
            if outcome.winner is None:
                return 0
            elif board.turn == outcome.winner:
                return 100000
            else: 
                return -100000
        
        piece_scores = [1, 3, 3, 5, 9, 10000]
        white_score = 0
        black_score = 0
        
        for piece in chess.PIECE_TYPES:
            white_score += board.pieces_mask(piece, chess.WHITE).bit_count() * piece_scores[piece-1]
            black_score += board.pieces_mask(piece, chess.BLACK).bit_count() * piece_scores[piece-1]
                
        if board.turn == chess.WHITE:
            return white_score - black_score
        else:
            return black_score - white_score
