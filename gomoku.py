"""
This is a simple gomoku game built with Streamlit

by TeddyHuang-00 (huang_nan_2019@pku.edu.cn).

Shared under MIT license
"""

import time
from copy import deepcopy
from uuid import uuid4

import numpy as np
import streamlit as slt
from scipy.signal import convolve
from streamlit import session_state
from streamlit_server_state import server_state, server_state_lock

# Page configuration
slt.set_page_config(
    page_title="Gomoku Game",
    page_icon="5️⃣",
    initial_sidebar_state="expanded",
    menu_items={
        "Report a bug": "https://github.com/TeddyHuang-00/streamlit-gomoku/issues/new/choose",
        "Get Help": "https://discuss.streamlit.io/t/pvp-gomoku-game-in-streamlit/17403",
        "About": "Welcome to this web-based Gomoku game!\n\nHave any comment? Please let me know through [this post](https://discuss.streamlit.io/t/pvp-gomoku-game-in-streamlit/17403) or [issues](https://github.com/TeddyHuang-00/streamlit-gomoku/issues/new/choose)!\n\nIf you find this interesting, please leave a star in the [GitHub repo](https://github.com/TeddyHuang-00/streamlit-gomoku)",
    },
)

# Utils
class Room:
    def __init__(self, room_id) -> None:
        self.ROOM_ID = room_id
        self.BOARD = np.zeros(shape=(15, 15), dtype=int)
        self.PLAYER = _BLACK
        self.TURN = self.PLAYER
        self.HISTORY = (0, 0)
        self.WINNER = _BLANK
        self.TIME = time.time()


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
_ROOM_COLOR = {
    True: _BLACK,
    False: _WHITE,
}
_ROOM_ANNOTATION = {
    True: "(You)",
    False: "(Opponent)",
}

# Initialize the game
if "ROOM" not in session_state:
    session_state.ROOM = Room("local")
if "OWNER" not in session_state:
    session_state.OWNER = False

# Check server health
if "ROOMS" not in server_state:
    with server_state_lock["ROOMS"]:
        server_state.ROOMS = {}

# # Layout
# Main
TITLE = slt.empty()
ROUND_INFO = slt.empty()
BOARD_PLATE = [
    [cell.empty() for cell in slt.columns([1 for _ in range(15)])] for _ in range(15)
]
WAIT_FOR_OPPONENT = slt.empty()

# Sidebar
SCORE_TAG = slt.sidebar.empty()
SCORE_PLATE = slt.sidebar.columns(2)
PLAY_MODE_INFO = slt.sidebar.container()
with slt.sidebar.expander("Remote play!", expanded=True):
    CREATE_ROOM = slt.empty()
    ROOM_INFO = slt.empty()
    ROOM_ID_INPUT = slt.empty()
    JOIN_ROOM = slt.empty()
    ROOM_ID_ERROR = slt.empty()
MULTIPLAYER_TAG = slt.sidebar.empty()
with slt.sidebar.container():
    ANOTHER_ROUND = slt.empty()
    RESTART = slt.empty()
    EXIT = slt.empty()
GAME_INFO = slt.sidebar.container()

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
        session_state.ROOM = Room(session_state.ROOM.ROOM_ID)
        if session_state.ROOM.ROOM_ID != "local":
            sync_room()

    # Continue new round
    def another_round() -> None:
        """
        Continue new round.
        """
        session_state.ROOM = deepcopy(session_state.ROOM)
        session_state.ROOM.BOARD = np.zeros(shape=(15, 15), dtype=int)
        session_state.ROOM.PLAYER = -session_state.ROOM.PLAYER
        session_state.ROOM.TURN = session_state.ROOM.PLAYER
        session_state.ROOM.WINNER = _BLANK
        if session_state.ROOM.ROOM_ID != "local":
            session_state.ROOM.TIME = time.time()
            sync_room()

    # Room status sync
    def sync_room() -> bool:
        room_id = session_state.ROOM.ROOM_ID
        if room_id not in server_state.ROOMS.keys():
            session_state.ROOM = Room("local")
            return False
        elif server_state.ROOMS[room_id].TIME == session_state.ROOM.TIME:
            return False
        elif server_state.ROOMS[room_id].TIME < session_state.ROOM.TIME:
            # Only acquire the lock when writing to the server state
            with server_state_lock["ROOMS"]:
                server_rooms = server_state.ROOMS
                server_rooms[room_id] = session_state.ROOM
                server_state.ROOMS = server_rooms
            return True
        else:
            session_state.ROOM = server_state.ROOMS[room_id]
            return True

    # Check if winner emerge from move
    def check_win() -> int:
        """
        Use convolution to check if any player wins.
        """
        vertical = convolve(
            session_state.ROOM.BOARD,
            _VERTICAL,
            mode="same",
        )
        horizontal = convolve(
            session_state.ROOM.BOARD,
            _HORIZONTAL,
            mode="same",
        )
        diagonal_up_left = convolve(
            session_state.ROOM.BOARD,
            _DIAGONAL_UP_LEFT,
            mode="same",
        )
        diagonal_up_right = convolve(
            session_state.ROOM.BOARD,
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
        if session_state.ROOM.BOARD[x][y] != _BLANK:
            pass
        elif (
            session_state.ROOM.ROOM_ID in server_state.ROOMS.keys()
            and _ROOM_COLOR[session_state.OWNER]
            != server_state.ROOMS[session_state.ROOM.ROOM_ID].TURN
        ):
            sync_room()
        elif session_state.ROOM.WINNER == _BLANK:
            session_state.ROOM = deepcopy(session_state.ROOM)
            session_state.ROOM.BOARD[x][y] = session_state.ROOM.TURN
            session_state.ROOM.TURN = -session_state.ROOM.TURN
            session_state.ROOM.WINNER = check_win()
            session_state.ROOM.HISTORY = (
                session_state.ROOM.HISTORY[0]
                + int(session_state.ROOM.WINNER == _WHITE),
                session_state.ROOM.HISTORY[1]
                + int(session_state.ROOM.WINNER == _BLACK),
            )
            session_state.ROOM.TIME = time.time()
            if session_state.ROOM.ROOM_ID != "local":
                sync_room()

    # Draw board
    def draw_board(response: bool):
        if response:
            for i, row in enumerate(session_state.ROOM.BOARD):
                for j, cell in enumerate(row):
                    BOARD_PLATE[i][j].button(
                        _PLAYER_SYMBOL[cell],
                        key=f"{i}:{j}",
                        on_click=handle_click,
                        args=(i, j),
                    )
        else:
            for i, row in enumerate(session_state.ROOM.BOARD):
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
        if len(room_id) == 0:
            ROOM_ID_ERROR.warning("Please enter a room id")
            return
        if room_id not in server_state.ROOMS.keys():
            ROOM_ID_ERROR.error("Room not found")
            return
        session_state.ROOM = server_state.ROOMS[room_id]
        session_state.OWNER = is_owner

    # Display room info
    def room_info():
        if session_state.ROOM.ROOM_ID == "local":
            ROOM_INFO.empty()
            ROOM_ID = (
                ROOM_ID_INPUT.text_input(
                    "Enter the room ID on your invitation", key="INPUT_ROOM_ID"
                )
                .upper()
                .strip()
            )
            if JOIN_ROOM.button("Join room"):
                enter_room(ROOM_ID, False)
                if session_state.ROOM.ROOM_ID != "local":
                    JOIN_ROOM.empty()
        elif session_state.OWNER:
            ROOM_INFO.write(
                f"""
            **Room created!**

            Room ID: **{session_state.ROOM.ROOM_ID}**

            Share the ID to your friend for an exciting online game!
            """
            )
        else:
            ROOM_INFO.write(
                f"""
            Room **{session_state.ROOM.ROOM_ID}** joined!
            """
            )

    # Multiplayer switch
    def switch_multiplayer():
        if session_state.ROOM.ROOM_ID == "local":
            if CREATE_ROOM.button("Create new room"):
                session_state.OWNER = True
                # Remove old room
                with server_state_lock["ROOMS"]:
                    server_state.ROOMS = {
                        room_id: room
                        for room_id, room in server_state.ROOMS.items()
                        if time.time() - room.TIME < _ROOM_TIMEOUT
                    }
                # Create if available
                if len(server_state.ROOMS) < _ROOM_LIMIT:
                    room_id = "RM" + str(uuid4()).upper()[-12:]
                    with server_state_lock["ROOMS"]:
                        server_state.ROOMS[room_id] = Room(room_id)
                    enter_room(room_id, True)
                    CREATE_ROOM.empty()
                else:
                    ROOM_INFO.warning("Server full! Please try again later")
        room_info()

    # Game process control
    def game_control():
        if session_state.ROOM.ROOM_ID != "local":
            # Handles syncing in remote play
            if session_state.ROOM.ROOM_ID not in server_state.ROOMS.keys():
                session_state.ROOM = Room("local")
                slt.experimental_rerun()
            else:
                sync_room()
            if session_state.ROOM.WINNER != _BLANK:
                draw_board(False)
            elif (
                session_state.ROOM.ROOM_ID in server_state.ROOMS.keys()
                and _ROOM_COLOR[session_state.OWNER]
                != server_state.ROOMS[session_state.ROOM.ROOM_ID].TURN
            ):
                WAIT_FOR_OPPONENT.info("Waiting for opponent...")
                draw_board(False)
            else:
                WAIT_FOR_OPPONENT.empty()
                sync_room()
                draw_board(True)
        elif session_state.ROOM.WINNER != _BLANK:
            draw_board(False)
        else:
            draw_board(True)
        if (
            session_state.ROOM.WINNER != _BLANK
            or 0 not in session_state.ROOM.BOARD
        ):
            ANOTHER_ROUND.button(
                "Another round",
                on_click=another_round,
                help="Clear board and swap first player",
            )
        if session_state.ROOM.ROOM_ID == "local" or session_state.OWNER:
            RESTART.button(
                "Restart",
                on_click=restart,
                help="Clear the board as well as the scores",
            )
        if session_state.ROOM.ROOM_ID != "local" and EXIT.button("Exit room"):
            if session_state.OWNER:
                with server_state_lock["ROOMS"]:
                    server_rooms = server_state.ROOMS
                    del server_rooms[session_state.ROOM.ROOM_ID]
                    server_state.ROOMS = server_rooms
            session_state.ROOM.ROOM_ID = "local"
            session_state.OWNER = False
            restart()
            switch_multiplayer()
            EXIT.empty()

    # Infos
    def draw_info() -> None:
        # Text information
        TITLE.subheader("**5️⃣ Gomoku Game in Streamlit**")
        PLAY_MODE_INFO.write("---\n\n**Room Control**")
        PLAY_MODE_INFO.metric(
            "Current active rooms on server:", len(server_state.ROOMS)
        )
        PLAY_MODE_INFO.write("Create or join a room to play remotely.")
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
        # History scores
        SCORE_TAG.subheader("Scores")
        SCORE_PLATE[0].metric("White", session_state.ROOM.HISTORY[0])
        SCORE_PLATE[1].metric("Black", session_state.ROOM.HISTORY[1])
        # Additional information
        if session_state.ROOM.WINNER != _BLANK:
            ROUND_INFO.write(
                f"#### **{_PLAYER_COLOR[session_state.ROOM.WINNER]} wins!**"
            )
        elif 0 not in session_state.ROOM.BOARD:
            ROUND_INFO.write("#### **Tie**")
        else:
            if session_state.ROOM.ROOM_ID != "local":
                ROUND_INFO.write(
                    f"#### **{_PLAYER_SYMBOL[session_state.ROOM.TURN]} {_PLAYER_COLOR[session_state.ROOM.TURN]}'s turn... {_ROOM_ANNOTATION[_ROOM_COLOR[session_state.OWNER] == session_state.ROOM.TURN]}**"
                )
            else:
                ROUND_INFO.write(
                    f"#### **{_PLAYER_SYMBOL[session_state.ROOM.TURN]} {_PLAYER_COLOR[session_state.ROOM.TURN]}'s turn...**"
                )

    # The main game loop
    switch_multiplayer()
    game_control()
    draw_info()


if __name__ == "__main__":
    gomoku()
