from dataclasses import dataclass

import chess


UPPER = 0
LOWER = 1
EXACT = 2


@dataclass(slots=True)
class TranspositionTableEntry:
    flag: int
    depth: int
    move: chess.Move | None
    score: float
