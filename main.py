from customtkinter import *
import time
import json
import random
import copy
import os
import sys
from PIL import Image, ImageDraw

# ---------------------------------------------------------------- settings
TOTAL_CELLS = 81                                    # 9 x 9 board
LEVELS = {"Easy": 2, "Medium": 15, "Hard": 20}      # number of EMPTY cells per level
MAX_MISTAKES = 3
HIGHLIGHT = "#2d87e1"                               # blue used to highlight cells
ALL_DIGITS = set(range(1, 10))


# ---------------------------------------------------------------- files
def resource_path(relative_path):
    """Path of a bundled, read-only file (icon, images). Works in dev and inside the .exe."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def save_path():
    """Path of the save file.
    A one-file .exe unpacks itself into a TEMP folder that is deleted when the game closes,
    so the save must live in a normal user folder or it would be lost every time."""
    folder = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "SudokuGame")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "save.json")


# ---------------------------------------------------------------- game state
cont = False                                        # True when there is a game to "Continue"
board = [[""] * 9 for _ in range(9)]                # the full answer
board2 = [[""] * 9 for _ in range(9)]               # what the player sees ("" = empty cell)
best = {"Easy": 0, "Medium": 0, "Hard": 0}          # best times in seconds (0 = none yet)
mode = ""                                           # "Easy", "Medium", "Hard" or "Custom"
num = 0                                             # number of empty cells in the current game
mistakes = 0
elapsed = 0                                         # seconds played in the current game
t = time.time()                                     # start time used to calculate `elapsed`
finished = False                                    # True once the game is won or lost
timer_id = None                                     # id of the running timer (so it can be cancelled)
clicked = ["", ""]                                  # cell the player selected
option_frame = None                                 # the difficulty menu (if open)


def format_time(seconds):
    """Turn seconds into m:ss (or h:mm:ss)."""
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def grid_to_text(grid):
    """Grid -> 81 characters ('0' = empty) so it can be saved."""
    return "".join(str(v) if v != "" else "0" for row in grid for v in row)


def text_to_grid(text):
    """81 characters -> grid ('0' becomes empty)."""
    return [[int(text[r * 9 + c]) or "" for c in range(9)] for r in range(9)]


def save_game():
    """Save the current game and the best times."""
    data = {"best": best, "playing": cont, "mode": mode, "num": num, "mistakes": mistakes,
            "elapsed": elapsed, "solution": grid_to_text(board), "puzzle": grid_to_text(board2)}
    try:
        with open(save_path(), "w") as file:
            json.dump(data, file)
    except OSError:
        pass                                        # a failed save must never crash the game


def load_game():
    """Load best times and (if there is one) the unfinished game."""
    global cont, board, board2, mode, num, mistakes, elapsed
    try:
        with open(save_path()) as file:
            data = json.load(file)
        for level in best:
            best[level] = int(data["best"].get(level, 0))
    except Exception:
        return                                      # no save yet, or unreadable: start fresh
    try:
        solution, puzzle = data["solution"], data["puzzle"]
        # the save must have 81 digits and the puzzle must agree with the solution
        ok = len(solution) == 81 and len(puzzle) == 81 and "0" not in solution
        ok = ok and all(p == "0" or p == s for s, p in zip(solution, puzzle))
        if data["playing"] and ok and (data["mode"] in LEVELS or data["mode"] == "Custom"):
            board, board2 = text_to_grid(solution), text_to_grid(puzzle)
            mode, num = data["mode"], int(data["num"])
            mistakes, elapsed = int(data["mistakes"]), int(data["elapsed"])
            cont = True
    except Exception:
        cont = False


# ---------------------------------------------------------------- sudoku logic
def checkc(grid, i, j, ran):
    """True if digit `ran` can go in row i, column j without breaking a rule."""
    sqr = i // 3 * 3
    sqc = j // 3 * 3
    for p in range(3):                              # same 3x3 box
        for w in range(3):
            if ran == grid[sqr + p][sqc + w]:
                return False
    if ran in grid[i]:                              # same row
        return False
    for r in range(9):                              # same column
        if grid[r][j] == ran:
            return False
    return True


def fill(pos):
    """Brute force: fill cell by cell with digits in random order.
    If a cell has no digit that fits, go back one cell and try its next digit."""
    if pos == TOTAL_CELLS:
        return True                                 # every cell is filled
    i, j = divmod(pos, 9)
    digits = list(range(1, 10))
    random.shuffle(digits)
    for d in digits:
        if checkc(board, i, j, d):
            board[i][j] = d
            if fill(pos + 1):
                return True
            board[i][j] = ""                        # dead end: undo and try the next digit
    return False


def gen():
    """Create a new full board (always succeeds, only 81 levels deep so no recursion error)."""
    global board
    board = [[""] * 9 for _ in range(9)]
    fill(0)


def dificulty(count):
    """Copy the board and empty exactly `count` different cells."""
    global board2
    count = max(1, min(TOTAL_CELLS, count))
    board2 = copy.deepcopy(board)
    for pos in random.sample(range(TOTAL_CELLS), count):    # sample = no cell is picked twice
        board2[pos // 9][pos % 9] = ""


def solve(grid, limit=20000):
    """Brute-force solver (tries digits, backs up on dead ends).
    Returns a finished copy of the grid, or None if it can't be finished."""
    g = copy.deepcopy(grid)
    rows = [set(row) for row in g]
    cols = [set(g[i][j] for i in range(9)) for j in range(9)]
    boxes = [set(g[b // 3 * 3 + p][b % 3 * 3 + q] for p in range(3) for q in range(3)) for b in range(9)]
    steps = 0

    def pick_cell():
        # take the empty cell with the fewest possible digits (keeps the search short)
        pick = None
        for i in range(9):
            for j in range(9):
                if g[i][j] == "":
                    options = ALL_DIGITS - rows[i] - cols[j] - boxes[i // 3 * 3 + j // 3]
                    if pick is None or len(options) < len(pick[2]):
                        pick = (i, j, options)
                        if len(options) <= 1:
                            return pick
        return pick

    def search():
        nonlocal steps
        pick = pick_cell()
        if pick is None:
            return True                             # no empty cells left = solved
        steps += 1
        if steps > limit:
            return False                            # safety stop so the window never freezes
        i, j, options = pick
        b = i // 3 * 3 + j // 3
        for d in options:
            g[i][j] = d
            rows[i].add(d)
            cols[j].add(d)
            boxes[b].add(d)
            if search():
                return True
            g[i][j] = ""
            rows[i].discard(d)
            cols[j].discard(d)
            boxes[b].discard(d)
        return False

    return g if search() else None


def accept_other(x, y, digit):
    """A puzzle with many empty cells can have more than one valid solution.
    If the player's digit is different from our answer but the puzzle can still be
    finished with it, the move is correct: switch our answer to that solution."""
    global board
    if not checkc(board2, x, y, digit):
        return False                                # breaks a sudoku rule
    trial = copy.deepcopy(board2)
    trial[x][y] = digit
    solved = solve(trial)
    if solved is None:
        return False                                # the puzzle can't be finished with this digit
    board = solved
    return True


# ---------------------------------------------------------------- window
load_game()

window = CTk()
try:
    window.iconbitmap(resource_path("sudoku.ico"))
except Exception:
    pass                                            # missing icon should not stop the game
window.title("Sudoku")


def load_trophy(filename, fallback_color):
    """Load a trophy picture (draws a simple circle if the file is missing)."""
    try:
        return Image.open(resource_path(os.path.join("images", filename)))
    except Exception:
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse((5, 5, 95, 95), fill=fallback_color)
        return img


# Trophy images (yellow = earned, grey = not earned), in two sizes
img1 = load_trophy("Designer.png", "#f5c518")
img2 = load_trophy("Designer (1).png", "#b0b0b0")
yellow = CTkImage(light_image=img1, size=(50, 50))
grey = CTkImage(light_image=img2, size=(50, 50))
yellow1 = CTkImage(light_image=img1, size=(70, 70))
grey1 = CTkImage(light_image=img2, size=(70, 70))

switchvar = StringVar(value="off")
set_appearance_mode("light")
cell = [[""] * 9 for _ in range(9)]                 # the 81 board buttons
choiceb = [""] * 9                                  # the 1-9 buttons
choicel = [""] * 9                                  # "how many left" label above each 1-9 button
mistake_label = None                                # widgets of the game page
timer_label = None
result_frame = None


def switcher():
    if switchvar.get() == "on":
        set_appearance_mode("dark")
    else:
        set_appearance_mode("light")


def cnextpage():
    """Continue the saved game: the timer picks up from the saved time."""
    global t
    t = time.time() - elapsed
    next_page()


def home():
    global option_frame
    option_frame = None
    lebel = CTkLabel(window, text="Sudoku", font=("Helvetica", 50, "bold"))
    lebel.place(x=10, y=5)
    if cont is True:
        contb = CTkButton(window, text=f"Continue {format_time(elapsed)}", width=110, command=cnextpage)
        contb.place(x=280, y=630)
    nb = CTkButton(window, text="New game", width=110, command=option)
    nb.place(x=280, y=670)
    sw = CTkSwitch(window, variable=switchvar, text="Dark mode", onvalue="on", offvalue="off", command=switcher)
    sw.place(x=530, y=670)


def option():
    """Difficulty menu: Easy / Medium / Hard / Custom."""
    global option_frame
    if option_frame is not None:
        option_frame.destroy()                      # never stack two menus
    # Fixed size (420 x 300). Its bottom edge is y=610, just above the Continue button (y=630),
    # so the extra Custom row can't overlap the buttons underneath.
    option_frame = CTkFrame(window, corner_radius=20, width=420, height=300)
    option_frame.grid_propagate(False)
    option_frame.grid_columnconfigure(0, weight=1)

    # Easy / Medium / Hard rows
    for row, level in enumerate(LEVELS):
        label = CTkLabel(option_frame, corner_radius=10, text=level, fg_color="white", text_color="black",
                         width=400, height=60, font=("", 15, "bold"))
        label.grid(row=row, padx=10, pady=3, sticky="ew")
        label.bind("<Button-1>", lambda event, level=level: game(level))

    # Custom row: name + number box + Start button
    custom = CTkFrame(option_frame, corner_radius=10, fg_color="white", width=400, height=60)
    custom.grid_propagate(False)
    custom.grid_rowconfigure(0, weight=1)
    custom.grid(row=3, padx=10, pady=3, sticky="ew")
    name = CTkLabel(custom, text="Custom", text_color="black", width=70, font=("", 15, "bold"))
    name.grid(row=0, column=0, padx=(10, 4))
    entry = CTkEntry(custom, width=70, justify="center", fg_color="white", text_color="black",
                     border_color="grey60")
    entry.grid(row=0, column=1, padx=4)
    hint = CTkLabel(custom, text=f"empty cells (1-{TOTAL_CELLS})", text_color="grey30", font=("", 12))
    hint.grid(row=0, column=2, padx=4)

    # message line under the Custom row (empty unless the input is wrong)
    error_label = CTkLabel(option_frame, text="", text_color="#d32f2f", font=("", 12), height=20)
    error_label.grid(row=4, pady=(0, 4))

    def keep_digits(event=None):
        # the number box only keeps digits, at most 2 (81 is the biggest number)
        text = "".join(ch for ch in entry.get() if ch in "0123456789")[:2]
        if text != entry.get():
            entry.delete(0, "end")
            entry.insert(0, text)

    def start_custom(event=None):
        text = entry.get().strip()
        if text.isascii() and text.isdigit() and 1 <= int(text) <= TOTAL_CELLS:
            game("Custom", int(text))
        else:
            error_label.configure(text=f"Enter a whole number from 1 to {TOTAL_CELLS}")

    start = CTkButton(custom, text="Start", width=60, command=start_custom)
    start.grid(row=0, column=3, padx=(4, 10))
    entry.bind("<KeyRelease>", keep_digits)
    entry.bind("<Return>", start_custom)
    name.bind("<Button-1>", lambda event: entry.focus())

    option_frame.place(x=115, y=310)


def game(modes, custom_count=None):
    """Start a new game. `custom_count` is only used by the Custom level."""
    global num, mode, mistakes, elapsed, t, cont
    mode = modes
    num = custom_count if mode == "Custom" else LEVELS[mode]
    mistakes, elapsed, t = 0, 0, time.time()        # reset here (not when the menu opens)
    gen()
    dificulty(num)
    cont = True
    next_page()


def stop_timer():
    global timer_id
    if timer_id is not None:
        window.after_cancel(timer_id)
        timer_id = None


def gotohome():
    stop_timer()
    save_game()
    for i in window.winfo_children():
        i.destroy()
    home()


def show_board():
    """Write the puzzle numbers into the 81 cells."""
    for i in range(9):
        for j in range(9):
            cell[i][j].configure(text=str(board2[i][j]), text_color="black", fg_color="white",
                                 font=("calibri light", 20))
            window.update()


def final():
    """Check for a win or a loss. Returns True when the game is over."""
    global cont, finished
    if finished:
        return True
    if board != board2 and mistakes < MAX_MISTAKES:
        return False
    finished = True
    cont = False                                    # nothing left to continue
    won = mistakes < MAX_MISTAKES
    if won and mode in best and (best[mode] == 0 or elapsed < best[mode]):
        best[mode] = elapsed                        # new best time for this level
    save_game()
    show_result(won)
    return True


def show_result(won):
    """Slide the result panel up and show the trophies."""
    for i in result_frame.winfo_children():         # clear the previous game's result
        i.destroy()
    for image, x, y in ((grey, 65, 30), (grey1, 115, 10), (grey, 185, 30)):
        CTkLabel(result_frame, image=image, text="").place(x=x, y=y)
    result_frame.configure(border_width=5, border_color="darkgrey", bg_color="transparent")
    y = window.winfo_screenheight()
    while y > 200:
        result_frame.place(x=166, y=y)
        y -= 15
        window.update()
        time.sleep(0.01)
    result_frame.place(x=166, y=200)

    tlebel = CTkLabel(result_frame, text=f"Mistakes :{mistakes}/{MAX_MISTAKES} \n \n \n time {format_time(elapsed)}",
                      text_color="black", font=("", 15, "bold"))
    tlebel.place(x=15, y=150)
    time.sleep(0.5)

    if not won:
        cl = CTkLabel(result_frame, text="You lose!", text_color="black", font=("impact", 35, 'bold'))
        cl.place(x=80, y=80)
        return

    cl = CTkLabel(result_frame, text="Congratulations!", text_color="black", font=("impact", 35, 'bold'))
    cl.place(x=25, y=80)
    if mode == "Custom":
        info = f"Difficulty :Custom \n \n \n {num} empty cells"       # custom games have no record
    else:
        info = f"Difficulty :{mode} \n \n \n best time {format_time(best[mode])}"
    tl = CTkLabel(result_frame, text=info, text_color="black", font=("", 15, "bold"))
    tl.place(x=150, y=150)
    CTkLabel(result_frame, image=yellow, text="").place(x=65, y=30)
    window.update()
    fast = elapsed < 15 * 60                        # finished in under 15 minutes
    if mistakes == 0 or fast:
        time.sleep(0.5)
        CTkLabel(result_frame, image=yellow1, text="").place(x=115, y=10)
        window.update()
    if mistakes == 0 and fast:
        time.sleep(0.5)
        CTkLabel(result_frame, image=yellow, text="").place(x=185, y=30)


def displaytime():
    """Runs 4 times a second: updates the clock, saves, and checks for a win/loss."""
    global elapsed, timer_id
    now = int(time.time() - t)
    if now != elapsed:
        elapsed = now
        timer_label.configure(text=format_time(elapsed))
        save_game()
    if final():
        timer_id = None                             # game over: stop the timer
        return
    timer_id = window.after(250, displaytime)


def restart():
    """New puzzle with the same difficulty."""
    global mistakes, elapsed, t, cont, finished, clicked
    stop_timer()                                    # otherwise two timers would run at once
    mistakes, elapsed, t = 0, 0, time.time()
    cont, finished, clicked = True, False, ["", ""]
    gen()
    dificulty(num)
    result_frame.place(x=166, y=768)                # hide the result panel
    mistake_label.configure(text=f"Mistakes: {mistakes}/{MAX_MISTAKES}")
    timer_label.configure(text=format_time(elapsed))
    show_board()
    checkremaning()
    save_game()
    displaytime()


def next_page():
    """The game page."""
    global cont, finished, clicked, mistake_label, timer_label, result_frame
    stop_timer()
    for i in window.winfo_children():
        i.destroy()
    cont, finished, clicked = True, False, ["", ""]

    # black frame holding the nine 3x3 boxes
    frame = CTkFrame(window, fg_color="black", width=650, height=650)
    frame.place(x=125, y=65)
    boxes = []
    for b in range(9):
        box = CTkFrame(frame, fg_color="grey70")
        box.grid(row=b // 3, column=b % 3, padx=1, pady=1)
        boxes.append(box)

    # the 81 cells, each one inside its own 3x3 box
    for i in range(9):
        for j in range(9):
            but = CTkButton(boxes[i // 3 * 3 + j // 3], fg_color="white", text="", width=40, height=40,
                            corner_radius=0, font=("calibri light", 20), text_color="black",
                            command=lambda i=i, j=j: action(i, j), hover=False)
            but.grid(row=i % 3, column=j % 3, padx=1, pady=1, sticky="ew")
            cell[i][j] = but

    # the 1-9 buttons with the "how many left" label above each
    for k in range(9):
        button = CTkButton(window, width=30, height=40, command=lambda k=k: select(k), text=str(k + 1),
                           text_color="#2d87e1", fg_color="white", font=("", 20, "bold"),
                           border_color="black", border_width=1)
        a = 100 + (50 * k)
        button.place(y=640, x=a)
        lebel = CTkLabel(window, width=30, height=30, font=("", 10), fg_color="white", text="9", text_color="black")
        lebel.place(y=600, x=a)
        choiceb[k] = button
        choicel[k] = lebel

    # mistakes + timer on top
    toplebel = CTkFrame(window, width=475, height=40, fg_color=window.cget("background"))
    toplebel.place(x=130, y=20)
    mistake_label = CTkLabel(toplebel, text=f"Mistakes: {mistakes}/{MAX_MISTAKES}")
    mistake_label.grid(row=0, column=0)
    timer_label = CTkLabel(toplebel, text=format_time(elapsed))
    timer_label.grid(row=0, column=1, padx=250)

    # result panel (starts below the window)
    result_frame = CTkFrame(window, height=300, width=300, fg_color="white", corner_radius=10,
                            bg_color=window.cget("background"))
    result_frame.place(x=166, y=window.winfo_screenheight())
    CTkButton(window, text="Restart", width=60, command=restart).place(x=10, y=10)
    CTkButton(window, text="Home", width=50, command=gotohome).place(x=590, y=10)

    show_board()
    checkremaning()
    save_game()
    displaytime()


def action(i, j):
    """The player clicked a cell."""
    global clicked
    if finished:
        return
    for k in range(9):
        for l in range(9):
            cell[k][l].configure(fg_color="white")
    value = board2[i][j]
    if value == "":
        cell[i][j].configure(fg_color=HIGHLIGHT)    # empty cell: highlight it
    else:
        for k in range(9):                          # filled cell: highlight every cell with the same number
            for l in range(9):
                if board2[k][l] == value:
                    cell[k][l].configure(fg_color=HIGHLIGHT)
    clicked = [i, j]


def select(se):
    """The player pressed a number button."""
    global clicked, mistakes
    if finished or mistakes >= MAX_MISTAKES:
        return
    se += 1
    x, y = clicked
    if x == "" or y == "":
        return
    if board2[x][y] != "":
        return                                      # cell is already filled

    if board[x][y] == se or accept_other(x, y, se):
        board2[x][y] = se                           # correct
        cell[x][y].configure(text=str(se), text_color="#2436b3", font=("", 20, "bold"))
    else:
        cell[x][y].configure(text=str(se), text_color="red", font=("", 20, "bold"), fg_color="#ff8380")
        mistakes += 1
        mistake_label.configure(text=f"Mistakes: {mistakes}/{MAX_MISTAKES}")
    save_game()
    clicked = ["", ""]
    checkremaning()


def checkremaning():
    """Update the 'how many left' number above each 1-9 button."""
    for d in range(1, 10):
        left = sum(1 for row in board2 if d not in row)     # rows that are still missing this digit
        choicel[d - 1].configure(text=str(left))


window.geometry("650x768+359+0")
home()
window.mainloop()