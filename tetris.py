# tetris.py - Tetris for THE PAD

import time
import st7789py as st7789
import urandom
from machine import Timer

# --- Colors ---
BLACK   = st7789.BLACK
WHITE   = st7789.WHITE
GRAY    = st7789.color565(80,  80,  80)
DKGRAY  = st7789.color565(30,  30,  30)
LTGRAY  = st7789.color565(180, 180, 180)
CYAN    = st7789.color565(0,   220, 220)
BLUE    = st7789.color565(30,  80,  220)
ORANGE  = st7789.color565(220, 120, 0)
YELLOW  = st7789.color565(220, 220, 0)
GREEN   = st7789.color565(0,   200, 0)
RED     = st7789.color565(220, 0,   0)
PURPLE  = st7789.color565(160, 0,   200)
DARK    = st7789.color565(20,  20,  20)

# --- Board Geometry ---
CELL    = 11
COLS    = 10
ROWS    = 20
BOARD_X = 4
BOARD_Y = 10
PANEL_X = BOARD_X + COLS * CELL + 6

# --- Pieces ---
PIECES = [
    [[(0,1),(1,1),(2,1),(3,1)], [(2,0),(2,1),(2,2),(2,3)],
     [(0,2),(1,2),(2,2),(3,2)], [(1,0),(1,1),(1,2),(1,3)]],
    [[(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)],
     [(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)]],
    [[(1,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(2,1),(1,2)],
     [(0,1),(1,1),(2,1),(1,2)], [(1,0),(0,1),(1,1),(1,2)]],
    [[(1,0),(2,0),(0,1),(1,1)], [(1,0),(1,1),(2,1),(2,2)],
     [(1,1),(2,1),(0,2),(1,2)], [(0,0),(0,1),(1,1),(1,2)]],
    [[(0,0),(1,0),(1,1),(2,1)], [(2,0),(1,1),(2,1),(1,2)],
     [(0,1),(1,1),(1,2),(2,2)], [(1,0),(0,1),(1,1),(0,2)]],
    [[(0,0),(0,1),(1,1),(2,1)], [(1,0),(2,0),(1,1),(1,2)],
     [(0,1),(1,1),(2,1),(2,2)], [(1,0),(1,1),(0,2),(1,2)]],
    [[(2,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(1,2),(2,2)],
     [(0,1),(1,1),(2,1),(0,2)], [(0,0),(1,0),(1,1),(1,2)]],
]
PIECE_COLORS = [CYAN, YELLOW, PURPLE, GREEN, RED, BLUE, ORANGE]

LINE_SCORES = [0, 100, 300, 500, 800]

# --- Tetris Melody ---
TETRIS_MELODY = [
    (659,400),(494,200),(523,200),(587,400),
    (523,200),(494,200),(440,400),(440,200),
    (523,200),(659,400),(587,200),(523,200),
    (494,600),(523,200),(587,400),(659,400),
    (523,400),(440,400),(440,400),(0,  200),
    (587,400),(698,200),(880,400),(784,200),
    (698,200),(659,600),(523,200),(659,400),
    (587,200),(523,200),(494,600),(523,200),
    (587,400),(659,400),(523,400),(440,400),
    (440,400),(0,  200),
    (659,400),(494,200),(523,200),(587,400),
    (523,200),(494,200),(440,400),(440,200),
    (523,200),(659,400),(587,200),(523,200),
    (494,600),(523,200),(587,400),(659,400),
    (523,400),(440,400),(440,800),
    (494,400),(523,400),(587,600),(698,200),
    (698,400),(587,400),(523,600),(659,200),
    (659,400),(523,400),(494,400),(440,400),
    (659,400),(659,400),(523,400),(494,400),
    (440,400),(440,800),
]

# ---------------------------------------------------
# MUSIC ENGINE
# ---------------------------------------------------
_music_timer = Timer()
_music_idx   = 0
_music_on    = False
_buz_ref     = None

# Tracks the current note remaining duration so SFX
# can resume at the correct point in the melody
_note_start_ms = 0
_note_dur_ms   = 0

def _music_next(t):
    global _music_idx, _note_start_ms, _note_dur_ms
    if not _music_on or _buz_ref is None:
        _buz_ref.duty_u16(0)
        return
    freq, dur = TETRIS_MELODY[_music_idx]
    _note_start_ms = time.ticks_ms()
    _note_dur_ms   = dur
    if freq == 0:
        _buz_ref.duty_u16(0)
    else:
        _buz_ref.freq(freq)
        _buz_ref.duty_u16(32768)
    _music_idx = (_music_idx + 1) % len(TETRIS_MELODY)
    _music_timer.init(mode=Timer.ONE_SHOT, period=dur,
                      callback=_music_next)

def music_start(buzzer):
    global _music_on, _music_idx, _buz_ref
    _buz_ref   = buzzer
    _music_on  = True
    _music_idx = 0
    _music_next(None)

def music_stop():
    global _music_on
    _music_on = False
    _music_timer.deinit()
    if _buz_ref:
        _buz_ref.duty_u16(0)

def music_pause():
    global _music_on
    _music_on = False
    if _buz_ref:
        _buz_ref.duty_u16(0)

def music_resume():
    global _music_on
    _music_on = True
    _music_next(None)

# ---------------------------------------------------
# SFX — Non-interfering with music
#
# The music timer owns the buzzer asynchronously.
# To play SFX without cutting the melody:
#   1. Temporarily flag music off so the timer callback
#      silences itself if it fires mid-SFX
#   2. Play the SFX directly (very short — 12-30ms)
#   3. Re-flag music on and schedule the NEXT note
#      immediately — the current note's remaining time
#      is already elapsed since SFX are shorter than
#      any melody note duration
#
# This produces no audible gap because SFX durations
# (12-30ms) are far shorter than the shortest melody
# note (200ms). The music simply continues to the
# next note after the SFX finishes.
# ---------------------------------------------------
def _with_sfx(buz, freq, ms):
    global _music_on
    was_on    = _music_on
    _music_on = False           # Prevent timer callback interfering
    _music_timer.deinit()       # Cancel pending note timer

    buz.freq(freq)
    buz.duty_u16(32768)
    time.sleep_ms(ms)
    buz.duty_u16(0)

    if was_on:
        _music_on = True
        _music_next(None)       # Immediately advance to next note

# REPLACE the four sfx functions — remove move and rotate entirely,
# keep lock and clear but simplify to avoid music interruption

def sfx_move(buz):
    pass    # Removed — visual feedback from piece moving is sufficient
            # and _with_sfx was causing melody fast-forward on held joystick

def sfx_rotate(buz):
    pass    # Removed — same reason as sfx_move
            # BTN1 held was skipping melody notes on every press

def sfx_lock(buz):
    """
    Lock sound plays at a natural gameplay pause — piece has landed.
    _with_sfx still used here but only fires once per piece lock,
    never on a held input, so melody advancement is not noticeable.
    """
    _with_sfx(buz, 280, 25)

def sfx_clear(buz, lines):
    """
    Line clear is a significant game event worth a sound.
    Ascending tones — one per line cleared (max 4).
    Each _with_sfx advances melody by one note, which is
    acceptable since line clears are rare and deliberate.
    """
    freqs = [523, 659, 784, 1047][:lines]
    for f in freqs:
        _with_sfx(buz, f, 55)

def sfx_gameover(buz):
    music_stop()
    for f in [400, 350, 300, 250, 200, 150]:
        buz.freq(f)
        buz.duty_u16(32768)
        time.sleep_ms(100)
    buz.duty_u16(0)

# ---------------------------------------------------
# BOARD HELPERS
# ---------------------------------------------------
def empty_board():
    return [[0] * COLS for _ in range(ROWS)]

def piece_cells(piece_idx, rot, px, py):
    return [(px+dc, py+dr) for dc, dr in PIECES[piece_idx][rot]]

def valid(board, piece_idx, rot, px, py):
    for dc, dr in PIECES[piece_idx][rot]:
        c, r = px+dc, py+dr
        if c < 0 or c >= COLS or r >= ROWS:
            return False
        if r >= 0 and board[r][c] != 0:
            return False
    return True

def ghost_drop(board, piece_idx, rot, px, py):
    gy = py
    while valid(board, piece_idx, rot, px, gy+1):
        gy += 1
    return gy

def lock_piece(board, piece_idx, rot, px, py, color):
    for dc, dr in PIECES[piece_idx][rot]:
        c, r = px+dc, py+dr
        if 0 <= r < ROWS and 0 <= c < COLS:
            board[r][c] = color

def clear_lines(board):
    full = [r for r in range(ROWS)
            if all(board[r][c] != 0 for c in range(COLS))]
    for r in full:
        del board[r]
        board.insert(0, [0]*COLS)
    return len(full)

# ---------------------------------------------------
# DRAWING
# ---------------------------------------------------
def draw_cell(tft, col, row, color):
    x = BOARD_X + col * CELL
    y = BOARD_Y + row * CELL
    if color == 0:
        tft.fill_rect(x, y, CELL-1, CELL-1, DKGRAY)
    else:
        tft.fill_rect(x, y, CELL-1, CELL-1, color)
        tft.hline(x,        y,        CELL-2, WHITE)
        tft.vline(x,        y,        CELL-2, WHITE)
        tft.hline(x+1,      y+CELL-2, CELL-2, GRAY)
        tft.vline(x+CELL-2, y+1,      CELL-2, GRAY)

def draw_ghost_cell(tft, col, row, color):
    x = BOARD_X + col * CELL
    y = BOARD_Y + row * CELL
    tft.rect(x, y, CELL-1, CELL-1, color)

def draw_board(tft, board):
    for r in range(ROWS):
        for c in range(COLS):
            draw_cell(tft, c, r, board[r][c])

def draw_board_border(tft):
    tft.rect(BOARD_X-2, BOARD_Y-2,
             COLS*CELL+4, ROWS*CELL+4, LTGRAY)
    tft.rect(BOARD_X-1, BOARD_Y-1,
             COLS*CELL+2, ROWS*CELL+2, GRAY)

def draw_piece(tft, piece_idx, rot, px, py, erase=False):
    color = 0 if erase else PIECE_COLORS[piece_idx]
    for dc, dr in PIECES[piece_idx][rot]:
        c, r = px+dc, py+dr
        if 0 <= r < ROWS and 0 <= c < COLS:
            draw_cell(tft, c, r, color)

def draw_ghost(tft, piece_idx, rot, px, gy, board):
    color = PIECE_COLORS[piece_idx]
    for dc, dr in PIECES[piece_idx][rot]:
        c, r = px+dc, gy+dr
        if 0 <= r < ROWS and 0 <= c < COLS:
            if board[r][c] == 0:
                draw_ghost_cell(tft, c, r, color)

def erase_ghost(tft, piece_idx, rot, px, gy, board):
    for dc, dr in PIECES[piece_idx][rot]:
        c, r = px+dc, gy+dr
        if 0 <= r < ROWS and 0 <= c < COLS:
            draw_cell(tft, c, r, board[r][c])

def draw_panel(tft, fnt, score, level, lines, next_idx):
    px = PANEL_X
    tft.fill_rect(px, 0, 240-px, 240, BLACK)
    tft.text(fnt, "SCR",      px, 12,  GRAY,   BLACK)
    tft.text(fnt, str(score), px, 44,  WHITE,  BLACK)
    tft.text(fnt, "LVL",      px, 90,  GRAY,   BLACK)
    tft.text(fnt, str(level), px, 122, YELLOW, BLACK)
    tft.text(fnt, "LNS",      px, 158, GRAY,   BLACK)
    tft.text(fnt, str(lines), px, 190, CYAN,   BLACK)
    tft.text(fnt, "NXT",      px, 210, GRAY,   BLACK)

def draw_next_preview(tft, next_idx):
    px = PANEL_X
    tft.fill_rect(px, 215, 55, 25, BLACK)
    color = PIECE_COLORS[next_idx]
    for dc, dr in PIECES[next_idx][0]:
        tft.fill_rect(px + dc*6, 215 + dr*6, 5, 5, color)

def draw_centered(tft, fnt, text, y, fg=WHITE, bg=BLACK):
    x = max(0, (240 - len(text) * fnt.WIDTH) // 2)
    tft.text(fnt, text, x, y, fg, bg)

# ---------------------------------------------------
# JOYSTICK
# ---------------------------------------------------
CENTER     = 32768
DEADZONE   = 10000
MOVE_DELAY = 120

def joy_dx(joy_x):
    v = joy_x.read_u16() - CENTER
    if v >  DEADZONE: return -1
    if v < -DEADZONE: return  1
    return 0

def joy_dy(joy_y):
    v = joy_y.read_u16() - CENTER
    if v < -DEADZONE: return  1
    return 0

def calc_drop_interval(level):
    return max(80, 600 - (level-1)*50)

# ---------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------
def run(tft, spi, btn1, btn2, joy_sel, joy_x, joy_y,
        led1, led2, buzzer, fnt, led_override,
        play_sequence, stop_sequence):

    while True:

        # --- Start screen ---
        tft.fill(BLACK)
        draw_centered(tft, fnt, "TETRIS",   48,  CYAN,  BLACK)
        draw_centered(tft, fnt, "BTN1=ROT", 96,  WHITE, BLACK)
        draw_centered(tft, fnt, "SEL=PAUSE",128, GRAY,  BLACK)
        draw_centered(tft, fnt, "DN=DROP",  160, GRAY,  BLACK)
        draw_centered(tft, fnt, "BTN2=MENU",200, WHITE, BLACK)

        while True:
            if btn1.value() == 0:
                time.sleep_ms(200); break
            if btn2.value() == 0:
                time.sleep_ms(200)
                led_override(False)
                music_stop()
                return
            time.sleep_ms(16)

        # --- Init ---
        board       = empty_board()
        score       = 0
        level       = 1
        lines_total = 0
        paused      = False
        game_over   = False

        tft.fill(BLACK)
        draw_board_border(tft)
        draw_board(tft, board)

        piece_idx        = urandom.randint(0, 6)
        next_idx         = urandom.randint(0, 6)
        rotation, px, py = 0, 3, 0

        draw_panel(tft, fnt, score, level, lines_total, next_idx)
        draw_next_preview(tft, next_idx)

        last_drop   = time.ticks_ms()
        last_move   = time.ticks_ms()
        last_rotate = time.ticks_ms()
        last_pause  = time.ticks_ms()
        ROTATE_DELAY = 180

        music_start(buzzer)

        ghost_y = ghost_drop(board, piece_idx, rotation, px, py)
        draw_ghost(tft, piece_idx, rotation, px, ghost_y, board)
        draw_piece(tft, piece_idx, rotation, px, py)

        panel_dirty = False

        # --- Game loop ---
        while not game_over:
            now = time.ticks_ms()

            # BTN2 exit
            if btn2.value() == 0:
                time.sleep_ms(200)
                music_stop()
                led_override(False)
                return

            # SEL pause
            if (joy_sel.value() == 0 and
                    time.ticks_diff(now, last_pause) > 400):
                paused     = not paused
                last_pause = now
                if paused:
                    music_pause()
                    led_override(True)
                    led1.value(1)
                    led2.value(1)
                    tft.fill_rect(BOARD_X, BOARD_Y,
                                  COLS*CELL, ROWS*CELL,
                                  st7789.color565(0,0,60))
                    draw_centered(tft, fnt, "PAUSED",
                                  120-fnt.HEIGHT//2, YELLOW,
                                  st7789.color565(0,0,60))
                else:
                    music_resume()
                    led_override(False)
                    draw_board(tft, board)
                    ghost_y = ghost_drop(board, piece_idx,
                                         rotation, px, py)
                    draw_ghost(tft, piece_idx, rotation,
                               px, ghost_y, board)
                    draw_piece(tft, piece_idx, rotation, px, py)
                time.sleep_ms(50)

            if paused:
                time.sleep_ms(16)
                continue

            # Horizontal move
            dx = joy_dx(joy_x)
            if dx != 0 and time.ticks_diff(now, last_move) > MOVE_DELAY:
                new_px = px + dx
                if valid(board, piece_idx, rotation, new_px, py):
                    erase_ghost(tft, piece_idx, rotation,
                                px, ghost_y, board)
                    for c, r in piece_cells(piece_idx, rotation, px, py):
                        if 0 <= r < ROWS:
                            draw_cell(tft, c, r, board[r][c])
                    px      = new_px
                    ghost_y = ghost_drop(board, piece_idx,
                                         rotation, px, py)
                    draw_ghost(tft, piece_idx, rotation,
                               px, ghost_y, board)
                    draw_piece(tft, piece_idx, rotation, px, py)
                    sfx_move(buzzer)
                last_move = now

            # Soft drop
            drop_interval = calc_drop_interval(level)
            if joy_dy(joy_y) == 1:
                drop_interval = 50

            # Rotate CW — BTN1 only (Option A)
            if (btn1.value() == 0 and
                    time.ticks_diff(now, last_rotate) > ROTATE_DELAY):
                rotated     = (rotation + 1) % 4
                last_rotate = now
                for kick in [0, 1, -1, 2, -2]:
                    if valid(board, piece_idx, rotated, px+kick, py):
                        erase_ghost(tft, piece_idx, rotation,
                                    px, ghost_y, board)
                        for c, r in piece_cells(piece_idx,
                                                rotation, px, py):
                            if 0 <= r < ROWS:
                                draw_cell(tft, c, r, board[r][c])
                        rotation = rotated
                        px      += kick
                        ghost_y  = ghost_drop(board, piece_idx,
                                              rotation, px, py)
                        draw_ghost(tft, piece_idx, rotation,
                                   px, ghost_y, board)
                        draw_piece(tft, piece_idx, rotation, px, py)
                        sfx_rotate(buzzer)   # Music continues uninterrupted
                        break

            # Gravity
            if time.ticks_diff(now, last_drop) > drop_interval:
                last_drop = now
                if valid(board, piece_idx, rotation, px, py+1):
                    for c, r in piece_cells(piece_idx, rotation, px, py):
                        if 0 <= r < ROWS:
                            draw_cell(tft, c, r, board[r][c])
                    py += 1
                    new_ghost = ghost_drop(board, piece_idx,
                                           rotation, px, py)
                    if new_ghost != ghost_y:
                        erase_ghost(tft, piece_idx, rotation,
                                    px, ghost_y, board)
                        ghost_y = new_ghost
                        draw_ghost(tft, piece_idx, rotation,
                                   px, ghost_y, board)
                    draw_piece(tft, piece_idx, rotation, px, py)

                else:
                    sfx_lock(buzzer)
                    lock_piece(board, piece_idx, rotation,
                               px, py, PIECE_COLORS[piece_idx])
                    cleared = clear_lines(board)

                    if cleared:
                        sfx_clear(buzzer, cleared)
                        score       += LINE_SCORES[cleared] * level
                        lines_total += cleared
                        level        = lines_total // 10 + 1
                        draw_board(tft, board)
                    else:
                        for c, r in piece_cells(piece_idx,
                                                rotation, px, py):
                            if 0 <= r < ROWS:
                                draw_cell(tft, c, r, board[r][c])

                    panel_dirty = True
                    piece_idx        = next_idx
                    next_idx         = urandom.randint(0, 6)
                    rotation, px, py = 0, 3, 0

                    if not valid(board, piece_idx, rotation, px, py):
                        draw_piece(tft, piece_idx, rotation, px, py)
                        sfx_gameover(buzzer)
                        led_override(True)
                        led1.value(1)
                        led2.value(1)

                        tft.fill_rect(20, 85, 160, 80, DKGRAY)
                        tft.rect(20, 85, 160, 80, WHITE)
                        draw_centered(tft, fnt, "GAME OVER",
                                      92,  RED,   DKGRAY)
                        draw_centered(tft, fnt, f"SCR:{score}",
                                      124, WHITE, DKGRAY)
                        draw_centered(tft, fnt, "BTN1=RETRY",
                                      148, GRAY,  DKGRAY)
                        draw_centered(tft, fnt, "BTN2=MENU",
                                      156, GRAY,  DKGRAY)

                        time.sleep_ms(500)
                        led_override(False)

                        while True:
                            if btn1.value() == 0:
                                time.sleep_ms(200)
                                game_over = True
                                break
                            if btn2.value() == 0:
                                time.sleep_ms(200)
                                led_override(False)
                                return
                            time.sleep_ms(16)
                        break

                    ghost_y = ghost_drop(board, piece_idx,
                                         rotation, px, py)
                    draw_ghost(tft, piece_idx, rotation,
                               px, ghost_y, board)
                    draw_piece(tft, piece_idx, rotation, px, py)

            if panel_dirty:
                draw_panel(tft, fnt, score, level,
                           lines_total, next_idx)
                draw_next_preview(tft, next_idx)
                panel_dirty = False

            time.sleep_ms(16)