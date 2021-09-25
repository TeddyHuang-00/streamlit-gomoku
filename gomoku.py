"""
This is a simple gomoku game built with Streamlit

by TeddyHuang-00 (huang_nan_2019@pku.edu.cn).

Shared under MIT license
"""

import time
from uuid import uuid4

import numpy as np
import streamlit as slt
from scipy.signal import convolve
from streamlit_server_state import server_state, server_state_lock

# Page configuration
slt.set_page_config(
    page_title="Gomoku Game",
    page_icon="5️⃣",
    initial_sidebar_state="expanded",
)

# Utils
_BLANK = 0
_BLACK = 1
_WHITE = -1
_PLAYER_SYMBOL = {
    _WHITE: "⚪",
    _BLANK: "➕",
    _BLACK: "⚫",
}
_PLAYER_COLOR = {
    _WHITE: "White",
    _BLANK: "Blank",
    _BLACK: "Black",
}
_HORIZONTAL = np.array(
    [
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [1, 1, 1, 1, 1],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ]
)
_VERTICAL = np.array(
    [
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
    ]
)
_DIAGONAL_UP_LEFT = np.array(
    [
        [1, 0, 0, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 0, 1, 0],
        [0, 0, 0, 0, 1],
    ]
)
_DIAGONAL_UP_RIGHT = np.array(
    [
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 0, 0, 0],
        [1, 0, 0, 0, 0],
    ]
)
_ROOM_LIMIT = 10
_ROOM_TIMEOUT = 300
_PLAY_MODE = {
    True: "Local",
    False: "Remote",
}
_ROOM_COLOR = {
    True: _BLACK,
    False: _WHITE,
}
_ROOM_ANNOTATION = {
    True: "(You)",
    False: "(Opponent)",
}

# Initialize the game
if "BOARD" not in slt.session_state:
    slt.session_state.BOARD = np.zeros(shape=(15, 15), dtype=int)
if "PLAYER" not in slt.session_state:
    slt.session_state.PLAYER = _BLACK
if "TURN" not in slt.session_state:
    slt.session_state.TURN = slt.session_state.PLAYER
if "HISTORY" not in slt.session_state:
    slt.session_state.HISTORY = (0, 0)
if "WINNER" not in slt.session_state:
    slt.session_state.WINNER = _BLANK
if "LOCAL" not in slt.session_state:
    slt.session_state.LOCAL = False
if "ROOM" not in slt.session_state:
    slt.session_state.ROOM = None
if "OWNER" not in slt.session_state:
    slt.session_state.OWNER = False
if "TIME" not in slt.session_state:
    slt.session_state.TIME = time.time()

# Check server health
if "ROOMS" not in server_state:
    with server_state_lock["ROOMS"]:
        server_state.ROOMS = {}

# Layout
# Main
TITLE = slt.empty()
ROUND_INFO = slt.empty()
BOARD_PLATE = [
    [cell.empty() for cell in slt.columns([1 for _ in range(15)])] for _ in range(15)
]
BUTTON_PLATE = slt.empty()
# Sidebar
SCORE_TAG = slt.sidebar.empty()
SCORE_PLATE = slt.sidebar.columns(2)
PLAY_MODE_INFO = slt.sidebar.container()
MULTIPLAYER_PLATE = slt.sidebar.empty()
MULTIPLAYER_TAG = slt.sidebar.empty()
GAME_INFO = slt.sidebar.container()


class Room:
    def __init__(self, room_id) -> None:
        self.ROOM_ID = room_id
        self.BOARD = np.zeros(shape=(15, 15), dtype=int)
        self.PLAYER = _BLACK
        self.TURN = self.PLAYER
        self.HISTORY = (0, 0)
        self.WINNER = _BLANK
        self.TIME = time.time()


# Draw the board
def gomoku():
    """
    Draw the board.

    Handle the main logic.
    """
    # Restart the game
    def restart() -> None:
        """
        Restart the game.
        """
        slt.session_state.BOARD = np.zeros(shape=(15, 15), dtype=int)
        slt.session_state.TURN = _BLACK
        slt.session_state.WINNER = _BLANK
        slt.session_state.HISTORY = (0, 0)
        if not slt.session_state.LOCAL:
            slt.session_state.TIME = time.time()
            sync_room()

    # Continue new round
    def another_round() -> None:
        """
        Continue new round.
        """
        if (
            not slt.session_state.LOCAL
            and slt.session_state.ROOM in server_state.ROOMS.keys()
            and slt.session_state.WINNER
            != server_state.ROOMS[slt.session_state.ROOM].WINNER
        ):
            sync_room()
        slt.session_state.BOARD = np.zeros(shape=(15, 15), dtype=int)
        slt.session_state.PLAYER = -slt.session_state.PLAYER
        slt.session_state.TURN = slt.session_state.PLAYER
        slt.session_state.WINNER = _BLANK
        if not slt.session_state.LOCAL:
            slt.session_state.TIME = time.time()
            sync_room()

    # Room status sync
    def sync_room() -> bool:
        room_id = slt.session_state.ROOM
        if room_id is not None:
            if room_id not in server_state.ROOMS.keys():
                PLAY_MODE_INFO.error("Room not found, maybe time out")
                slt.experimental_rerun()
            if server_state.ROOMS[room_id].TIME == slt.session_state.TIME:
                return False
            elif server_state.ROOMS[room_id].TIME < slt.session_state.TIME:
                # Only acquire the lock when writing to the server state
                with server_state_lock["ROOMS"]:
                    server_state.ROOMS[room_id].BOARD = slt.session_state.BOARD
                    server_state.ROOMS[room_id].PLAYER = slt.session_state.PLAYER
                    server_state.ROOMS[room_id].TURN = slt.session_state.TURN
                    server_state.ROOMS[room_id].WINNER = slt.session_state.WINNER
                    server_state.ROOMS[room_id].HISTORY = slt.session_state.HISTORY
                    server_state.ROOMS[room_id].TIME = slt.session_state.TIME
                    return True
            else:
                slt.session_state.BOARD = server_state.ROOMS[room_id].BOARD
                slt.session_state.PLAYER = server_state.ROOMS[room_id].PLAYER
                slt.session_state.TURN = server_state.ROOMS[room_id].TURN
                slt.session_state.WINNER = server_state.ROOMS[room_id].WINNER
                slt.session_state.HISTORY = server_state.ROOMS[room_id].HISTORY
                slt.session_state.TIME = server_state.ROOMS[room_id].TIME
                return True
        else:
            return False

    # Infos
    def draw_info() -> None:
        TITLE.subheader("**5️⃣ Gomoku Game in Streamlit**")
        if slt.session_state.LOCAL:
            PLAY_MODE_INFO.write(
                """
                ---

                **Local play mode**

                You can play with your friend locally.
                """
            )
        else:
            PLAY_MODE_INFO.write(
                """
                ---

                **Remote play mode**

                Create or join a room to play remotely.
                """
            )
        GAME_INFO.markdown(
            """
            ---

            ## A simple Gomoku game.


            <a href="https://en.wikipedia.org/wiki/Gomoku#Freestyle_Gomoku" style="color:#FFFFFF">Freestyle Gomoku</a>

            - no restrictions
            - swap first player
            - 15 by 15 board
            - no regrets

            Enjoy!

            ##### by <a href="https://github.com/TeddyHuang-00" style="color:#FFFFFF">TeddyHuang-00</a> • <a href="https://github.com/TeddyHuang-00/streamlit-gomoku" style="color:#FFFFFF">Github repo</a>

            ##### <a href="mailto:huang_nan_2019@pku.edu.cn" style="color:#FFFFFF">Contact</a>
            """,
            unsafe_allow_html=True,
        )

    # Check if winner emerge from move
    def check_win() -> int:
        """
        Use convolution to check if any player wins.
        """
        vertical = convolve(
            slt.session_state.BOARD,
            _VERTICAL,
            mode="same",
        )
        horizontal = convolve(
            slt.session_state.BOARD,
            _HORIZONTAL,
            mode="same",
        )
        diagonal_up_left = convolve(
            slt.session_state.BOARD,
            _DIAGONAL_UP_LEFT,
            mode="same",
        )
        diagonal_up_right = convolve(
            slt.session_state.BOARD,
            _DIAGONAL_UP_RIGHT,
            mode="same",
        )
        if (
            np.max(
                [
                    np.max(vertical),
                    np.max(horizontal),
                    np.max(diagonal_up_left),
                    np.max(diagonal_up_right),
                ]
            )
            == 5 * _BLACK
        ):
            winner = _BLACK
        elif (
            np.min(
                [
                    np.min(vertical),
                    np.min(horizontal),
                    np.min(diagonal_up_left),
                    np.min(diagonal_up_right),
                ]
            )
            == 5 * _WHITE
        ):
            winner = _WHITE
        else:
            winner = _BLANK
        return winner

    # Triggers the board response on click
    def handle_click(x, y):
        """
        Controls whether to pass on / continue current board / may start new round
        """
        if slt.session_state.BOARD[x][y] != _BLANK:
            pass
        elif slt.session_state.WINNER == _BLANK:
            slt.session_state.BOARD[x][y] = slt.session_state.TURN
            slt.session_state.TURN = -slt.session_state.TURN
            slt.session_state.WINNER = check_win()
            slt.session_state.HISTORY = (
                slt.session_state.HISTORY[0] + int(slt.session_state.WINNER == _WHITE),
                slt.session_state.HISTORY[1] + int(slt.session_state.WINNER == _BLACK),
            )
            slt.session_state.TIME = time.time()
            if slt.session_state.ROOM is not None:
                sync_room()

    # Draw board
    def draw_board(response: bool):
        if response:
            for i, row in enumerate(slt.session_state.BOARD):
                for j, cell in enumerate(row):
                    BOARD_PLATE[i][j].button(
                        _PLAYER_SYMBOL[cell],
                        key=f"{i}:{j}",
                        on_click=handle_click,
                        args=(i, j),
                    )
        else:
            for i, row in enumerate(slt.session_state.BOARD):
                for j, cell in enumerate(row):
                    BOARD_PLATE[i][j].write(
                        _PLAYER_SYMBOL[cell],
                        key=f"{i}:{j}",
                    )

    # Enter room by room id
    def enter_room(room_id, is_owner):
        """
        Enter room.
        """
        if not len(room_id):
            PLAY_MODE_INFO.warning("Please enter a room id")
            return
        if room_id not in server_state.ROOMS.keys():
            PLAY_MODE_INFO.error("Room not found")
            return
        slt.session_state.ROOM = room_id
        slt.session_state.OWNER = is_owner
        sync_room()

    # Switch play mode
    def switch_play_mode():
        """
        Switch player mode.
        """
        slt.session_state.LOCAL = not slt.session_state.LOCAL
        # Clear room if previous room exists
        if slt.session_state.LOCAL:
            if slt.session_state.OWNER:
                try:
                    with server_state_lock["ROOMS"]:
                        del server_state.ROOMS[slt.session_state.ROOM]
                except KeyError:
                    # Already deleted
                    pass
                slt.session_state.ROOM = None
                slt.session_state.OWNER = False
            else:
                slt.session_state.ROOM = None
            restart()

    # Additional information
    def round_info():
        if slt.session_state.WINNER != _BLANK:
            ROUND_INFO.write(
                f"#### **{_PLAYER_COLOR[slt.session_state.WINNER]} wins!**"
            )
        elif 0 not in slt.session_state.BOARD:
            ROUND_INFO.write("#### **Tie**")
        else:
            if not slt.session_state.LOCAL and slt.session_state.ROOM is not None:
                ROUND_INFO.write(
                    f"#### **{_PLAYER_SYMBOL[slt.session_state.TURN]} {_PLAYER_COLOR[slt.session_state.TURN]}'s turn... {_ROOM_ANNOTATION[_ROOM_COLOR[slt.session_state.OWNER] == slt.session_state.TURN]}**"
                )
            else:
                ROUND_INFO.write(
                    f"#### **{_PLAYER_SYMBOL[slt.session_state.TURN]} {_PLAYER_COLOR[slt.session_state.TURN]}'s turn...**"
                )

    # Game process control
    def game_control():
        if slt.session_state.WINNER != _BLANK or 0 not in slt.session_state.BOARD:
            PLAY_MODE_INFO.button(
                "Another round",
                on_click=another_round,
                help="Clear board and swap first player",
            )
        if slt.session_state.LOCAL or slt.session_state.OWNER:
            PLAY_MODE_INFO.button(
                "Restart",
                on_click=restart,
                help="Clear the board as well as the scores",
            )

    # History scores
    def history():
        SCORE_TAG.subheader("Scores")
        SCORE_PLATE[0].metric("White", slt.session_state.HISTORY[0])
        SCORE_PLATE[1].metric("Black", slt.session_state.HISTORY[1])

    # Multiplayer switch
    def switch_multiplayer():
        MULTIPLAYER_TAG.button(
            f"Switch to {_PLAY_MODE[not slt.session_state.LOCAL]} mode",
            on_click=switch_play_mode,
            help="Switch to local or remote play mode",
        )
        if not slt.session_state.LOCAL:
            with MULTIPLAYER_PLATE.expander("Remote play!", expanded=True):
                if slt.session_state.ROOM is None:
                    if slt.button("Create new room"):
                        slt.session_state.OWNER = True
                        with server_state_lock["ROOMS"]:
                            # Remove old room
                            server_state.ROOMS = {
                                room_id: room
                                for room_id, room in server_state.ROOMS.items()
                                if time.time() - room.TIME < _ROOM_TIMEOUT
                            }
                            # Create if available
                            if len(server_state.ROOMS) < _ROOM_LIMIT:
                                room_id = str(uuid4()).lower()
                                server_state.ROOMS[room_id] = Room(room_id)
                                enter_room(room_id, True)
                            else:
                                slt.warning("Server full! Please try again later")
                if slt.session_state.ROOM is None:
                    ROOM_ID = (
                        slt.text_input("Enter the room ID on your invitation")
                        .lower()
                        .strip()
                    )
                    slt.button(
                        "Join room",
                        on_click=enter_room,
                        args=(ROOM_ID, False),
                    )
                else:
                    if slt.session_state.OWNER:
                        slt.write(
                            f"""
                        **Room created!**

                        Room ID: **{slt.session_state.ROOM}**

                        Share the ID to your friend for an exciting online game!
                        """
                        )
                    elif not slt.session_state.OWNER:
                        slt.write(
                            f"""
                        Room **{slt.session_state.ROOM}** joined!
                        """
                        )

    # The main game loop
    switch_multiplayer()
    draw_info()

    # Additional steps for remote play
    if slt.session_state.ROOM is not None:
        draw_board(False)
        round_info()
        with slt.spinner("Waiting for opponent's next move..."):
            while (
                slt.session_state.ROOM in server_state.ROOMS.keys()
                and server_state.ROOMS[slt.session_state.ROOM].WINNER == _BLANK
                and server_state.ROOMS[slt.session_state.ROOM].TURN
                != _ROOM_COLOR[slt.session_state.OWNER]
            ):
                time.sleep(1)
        sync_room()

    history()
    draw_board(True)
    round_info()
    game_control()


if __name__ == "__main__":
    gomoku()
