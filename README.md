# 🧩 Python Sudoku Game

A desktop Sudoku game built with Python and Tkinter. Features a custom brute-force board generation algorithm and a standalone Windows executable (.exe) compiled with PyInstaller.

---

## 🛠️ Tech Stack & How It Works

* GUI Framework: Built using Python's standard tkinter library.
* Board Generation: Uses a brute-force randomized backtracking algorithm to generate and validate Sudoku puzzles.
* Packaging: Bundled into a single .exe file using PyInstaller.

---

## 🚀 Quick Download (For Players)

Want to play right away without running any code?

1. Go to the Releases Section on the right side of this repository: https://github.com/NaolTadesse/sudoku/releases
2. Download Sudoku.exe.
3. Double-click Sudoku.exe to launch and play!

---

## 💻 Running from Source Code

If you want to run or inspect the code:

### Prerequisites
* Python 3.x installed on your machine.

### Steps
1. Clone this repository:
   git clone https://github.com/NaolTadesse/sudoku.git
   cd sudoku

2. Run the program:
   python main.py

---

## 📁 Repository Structure

sudoku/
│
├── asset/             # UI assets
│   └── sudoku.ico     # Application icon
│
├── main.py            # Main Tkinter UI & Sudoku board logic
└── README.md          # Project documentation
