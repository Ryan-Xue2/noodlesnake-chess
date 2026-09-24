from dataclasses import dataclass

import chess

from noodlesnake.zobrist import Zobrist
from noodlesnake import helpers


@dataclass(frozen=True, slots=True)
class PositionKey:
    zobrist: int
    halfmove_clock: int
    repetition_counts: frozenset[tuple[int, int]]


class PositionController:
    __slots__ = ('board', 'captures', 'zobrist', '_position_counts', '_position_counts_stack')
    def __init__(self, board=None):
        self.board = None
        self.captures = []
        self.zobrist = Zobrist()
        self._position_counts = {}
        self._position_counts_stack = []
        if board is not None:
            self.set_board(board)

    def set_board(self, board):
        self.board = board
        self.captures.clear()
        self._position_counts_stack.clear()
        self.zobrist.calculate_zobrist_key(board)

        replay = board.root()
        replay_zobrist = Zobrist()
        replay_zobrist.calculate_zobrist_key(replay)
        self._position_counts = {replay_zobrist.key: 1}

        for move in board.move_stack:
            irreversible = replay.is_irreversible(move)
            replay.push(move)
            replay_zobrist.calculate_zobrist_key(replay)
            if irreversible:
                self._position_counts.clear()
            key = replay_zobrist.key
            self._position_counts[key] = self._position_counts.get(key, 0) + 1

    @property
    def position_key(self):
        return PositionKey(
            self.zobrist.key,
            self.board.halfmove_clock,
            frozenset(self._position_counts.items()),
        )

    def _record_position(self, irreversible):
        if irreversible:
            self._position_counts_stack.append(self._position_counts)
            self._position_counts = {self.zobrist.key: 1}
            return

        self._position_counts_stack.append(None)
        key = self.zobrist.key
        self._position_counts[key] = self._position_counts.get(key, 0) + 1

    def _restore_position_counts(self):
        previous_counts = self._position_counts_stack.pop()
        if previous_counts is not None:
            self._position_counts = previous_counts
            return

        key = self.zobrist.key
        count = self._position_counts[key]
        if count == 1:
            del self._position_counts[key]
        else:
            self._position_counts[key] = count - 1

    def move(self, move):
        """Make the move passed in and update the zobrist key accordingly"""
        irreversible = self.board.is_irreversible(move)
        self.zobrist.move(self.board, move)

        capture_square = helpers.captured_piece_square(self.board, move)
        if capture_square is not None:
            captured_pc = self.board.piece_at(capture_square)
        else:
            captured_pc = None
        self.captures.append((capture_square, captured_pc))

        # Update zobrist key in case of a captured piece
        if capture_square is not None:
            self.zobrist.update_capture(capture_square, captured_pc)
        # Update zobrist key in case of promotion
        if move.promotion is not None:
            self.zobrist.promote(self.board, move)
        # If the move is a castling move, update the position of the rook
        if self.board.is_castling(move):
            self.zobrist.move_rook_if_castle(self.board, move)

        # Keep track of the en passant possibilities and castling rights before moving
        ep_square_before = self.board.ep_square
        ep_available_before = self.board.has_legal_en_passant()
        castling_rights_before = self.board.castling_rights

        self.board.push(move)

        # Update the castling rights and en passant rights if necessary
        self.zobrist.update_castling_rights(self.board, castling_rights_before)
        self.zobrist.update_en_passant(self.board, ep_square_before, ep_available_before)
        self._record_position(irreversible)

    def unmove(self):
        """Undo the last move and update zobrist key accordingly"""
        self._restore_position_counts()
        move = self.board.peek()
        self.zobrist.unmove(self.board, move)

        # Uncapture the captured piece if there is one
        capture_square, captured_pc = self.captures.pop()
        if capture_square is not None:
            self.zobrist.update_capture(capture_square, captured_pc)
        # Update zobrist key in case of promotion
        if move.promotion is not None:
            self.zobrist.unpromote(self.board, move)
        
        # Keep track of the en passant possibilities and castling rights before undoing the move
        ep_square_before = self.board.ep_square
        ep_available_before = self.board.has_legal_en_passant()
        castling_rights_before = self.board.castling_rights

        self.board.pop()

        # If the move is a castling move, then update the position of the rook in the zobrist key
        if self.board.is_castling(move):
            self.zobrist.move_rook_if_castle(self.board, move)

        # Update the castling rights and en passant rights if necessary
        self.zobrist.update_castling_rights(self.board, castling_rights_before)
        self.zobrist.update_en_passant(self.board, ep_square_before, ep_available_before)

    def make_null_move(self):
        """Plays a null move, passing the turn to the other side and possibly forfeiting en passant"""
        ep_square_before = self.board.ep_square
        ep_available_before = self.board.has_legal_en_passant()

        null_move = chess.Move.null()
        irreversible = self.board.is_irreversible(null_move)
        self.board.push(null_move)

        self.zobrist.update_null_move(self.board, ep_square_before, ep_available_before)
        self._record_position(irreversible)

    def unmake_null_move(self):
        """Unplays a null move"""
        self._restore_position_counts()
        ep_square_before = self.board.ep_square
        ep_available_before = self.board.has_legal_en_passant()

        self.board.pop()
        
        self.zobrist.update_null_move(self.board, ep_square_before, ep_available_before)
