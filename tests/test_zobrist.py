import pytest
import chess

from noodlesnake.controller import PositionController
from noodlesnake.zobrist import Zobrist
from random import choice


@pytest.fixture
def en_passant_available():
    return [
        chess.Board('rnbqkbnr/ppp2p1p/3p4/4p1pP/4P3/8/PPPP1PP1/RNBQKBNR w KQkq g6 0 4'),
        chess.Board('rnbq1bnr/1pp2k1p/3p4/4p1p1/pP2P1P1/5N2/P1PP1P2/RNBQKB1R b KQ b3 0 7'),
        chess.Board('N1bk3r/pp1pnp1p/2n2q2/5Pp1/6P1/8/P1PBB2P/R2QK2R w KQ g6 0 15')
    ]


@pytest.fixture
def capture_available():
    return [
        chess.Board('rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1'),
        chess.Board('r1bqk1nr/pppp1ppp/2n5/4p3/4P3/3PbN2/PPP2PPP/RN1QKB1R w KQkq - 0 5'),
        chess.Board('r1bqr1k1/pppp1ppp/2n5/3nP3/3P4/2N2N2/PPP3PP/R2QKB1R w KQ - 1 9')
    ]


@pytest.fixture
def promotion_available():
    return [
        chess.Board('5k2/2p4P/8/5N2/2P5/8/1P5P/4K3 w - - 1 42'),
        chess.Board('rnbqk1nr/1ppp1p1p/6pb/8/8/8/pPPP1PP1/RNBQKBNR b KQkq - 0 1'),
        chess.Board('6nr/1P1k1p1p/2n3p1/2p5/8/8/2PK1PP1/2BQ1BNR w - - 0 1')
    ]


@pytest.fixture
def castling_available():
    return [
        None
    ]


def test_zobrist_hash(en_passant_available, capture_available, promotion_available):
    for board in en_passant_available + capture_available + promotion_available:
        controller = PositionController(board)
        zobrist = Zobrist()

        for _ in range(1000):
            if board.is_game_over():
                break

            moves = list(board.legal_moves)
            move = choice(moves)
            controller.move(move)

            zobrist.calculate_zobrist_key(board)
            assert zobrist.key == controller.zobrist.key

            controller.unmove()
            zobrist.calculate_zobrist_key(board)
            assert zobrist.key == controller.zobrist.key

            controller.move(move)
