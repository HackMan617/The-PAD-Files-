#  CONTROLS
#  --------
#  Joystick LEFT / RIGHT  – move piece
#  Joystick DOWN          – soft drop
#  Button 1 (GP4)         – rotate clockwise
#  Button 2 (GP5)         – rotate counter-clockwise
#  Button 3 (GP1)         – return to menu
#  Button 4 (GP2)         – restart (on game over screen)
#  Joystick button (GP0)  – pause
#
#  AUDIO NOTE
#  ----------
#  The Tetris theme runs entirely on a hardware Timer so it
#  never blocks the game loop. No SFX are played during
#  gameplay — they would fight the Timer and cause audible
#  glitches / music dropouts. The only blocking audio calls
#  are the game-over descending tone (music already stopped)
#  and the short line-clear chime (music paused then resumed).
#
# =============================================================

from machine import Pin, SPI, ADC, PWM, Timer
import utime
import st7789py as st7789
from fonts import vga1_16x32 as font2

#Display
spi1 = SPI(1, baudrate=40000000, polarity=1)
display = st7789.ST7789(
    spi1, 240, 240,
    reset=Pin(12, Pin.OUT),
    dc=Pin(13, Pin.OUT),
    rotation=1)

#Inputs
button1 = Pin(4,  Pin.IN, Pin.PULL_DOWN)   #rotate CW
button2 = Pin(5,  Pin.IN, Pin.PULL_DOWN)   #rotate CCW
button3 = Pin(1,  Pin.IN, Pin.PULL_DOWN)   #menu
button4 = Pin(2,  Pin.IN, Pin.PULL_DOWN)   #restart
xAxis   = ADC(Pin(26))
yAxis   = ADC(Pin(27))
jbutton = Pin(0,  Pin.IN, Pin.PULL_UP)     #pause

#Buzzer
buzzer = PWM(Pin(15))
buzzer.duty_u16(0)

TETRIS_MELODY = [
    (659, 400), (494, 200), (523, 200), (587, 400),
    (523, 200), (494, 200), (440, 400), (440, 200),
    (523, 200), (659, 400), (587, 200), (523, 200),
    (494, 600), (523, 200), (587, 400), (659, 400),
    (523, 400), (440, 400), (440, 400), (0,   200),

    (587, 400), (698, 200), (880, 400), (784, 200),
    (698, 200), (659, 600), (523, 200), (659, 400),
    (587, 200), (523, 200), (494, 600), (523, 200),
    (587, 400), (659, 400), (523, 400), (440, 400),
    (440, 400), (0,   200),

    (659, 400), (494, 200), (523, 200), (587, 400),
    (523, 200), (494, 200), (440, 400), (440, 200),
    (523, 200), (659, 400), (587, 200), (523, 200),
    (494, 600), (523, 200), (587, 400), (659, 400),
    (523, 400), (440, 400), (440, 800),

    (494, 400), (523, 400), (587, 600), (698, 200),
    (698, 400), (587, 400), (523, 600), (659, 200),
    (659, 400), (523, 400), (494, 400), (440, 400),
    (659, 400), (659, 400), (523, 400), (494, 400),
    (440, 400), (440, 800),
]

_music_idx   = 0
_music_timer = Timer()
_music_on    = False

def _music_next(t):
    global _music_idx
    if not _music_on:
        buzzer.duty_u16(0)
        return
    freq, dur = TETRIS_MELODY[_music_idx]
    if freq == 0:
        buzzer.duty_u16(0)
    else:
        buzzer.freq(freq)
        buzzer.duty_u16(1200)
    _music_idx = (_music_idx + 1) % len(TETRIS_MELODY)
    _music_timer.init(mode=Timer.ONE_SHOT, period=dur, callback=_music_next)

def music_start():
    global _music_on, _music_idx
    _music_on  = True
    _music_idx = 0
    _music_next(None)

def music_stop():
    global _music_on
    _music_on = False
    _music_timer.deinit()
    buzzer.duty_u16(0)

def music_pause():
    global _music_on
    _music_on = False
    buzzer.duty_u16(0)
    #Don't deinit the timer — let the current note finish,

def music_resume():
    global _music_on
    _music_on = True
    _music_next(None)

def sfx_line_clear(lines):
    music_pause()
    utime.sleep_ms(30)          #let current note finish cleanly
    freqs = [523, 659, 784, 1047][:lines]
    for f in freqs:
        buzzer.freq(f)
        buzzer.duty_u16(1800)
        utime.sleep_ms(50)
        buzzer.duty_u16(0)
        utime.sleep_ms(8)
    music_resume()

def sfx_gameover():
    for f in [400, 350, 300, 250, 200, 150]:
        buzzer.freq(f)
        buzzer.duty_u16(2000)
        utime.sleep_ms(100)
    buzzer.duty_u16(0)

#Colors
BLACK   = st7789.BLACK
WHITE   = st7789.WHITE
GREY    = st7789.color565( 80,  80,  80)
DKGREY  = st7789.color565( 30,  30,  30)
LTGREY  = st7789.color565(180, 180, 180)
CYAN    = st7789.color565(  0, 220, 220)
BLUE    = st7789.color565( 30,  80, 220)
ORANGE  = st7789.color565(220, 120,   0)
YELLOW  = st7789.color565(220, 220,   0)
GREEN   = st7789.color565(  0, 200,   0)
RED     = st7789.color565(220,   0,   0)
PURPLE  = st7789.color565(160,   0, 200)

#Board geometry
CELL    = 11
COLS    = 10
ROWS    = 20
BOARD_X = 4
BOARD_Y = 10
PANEL_X = BOARD_X + COLS * CELL + 6
SW, SH  = 240, 240

#Tetrominoes
PIECES = [
    # I – cyan
    [[(0,1),(1,1),(2,1),(3,1)], [(2,0),(2,1),(2,2),(2,3)],
     [(0,2),(1,2),(2,2),(3,2)], [(1,0),(1,1),(1,2),(1,3)]],
    # O – yellow
    [[(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)],
     [(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)]],
    # T – purple
    [[(1,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(2,1),(1,2)],
     [(0,1),(1,1),(2,1),(1,2)], [(1,0),(0,1),(1,1),(1,2)]],
    # S – green
    [[(1,0),(2,0),(0,1),(1,1)], [(1,0),(1,1),(2,1),(2,2)],
     [(1,1),(2,1),(0,2),(1,2)], [(0,0),(0,1),(1,1),(1,2)]],
    # Z – red
    [[(0,0),(1,0),(1,1),(2,1)], [(2,0),(1,1),(2,1),(1,2)],
     [(0,1),(1,1),(1,2),(2,2)], [(1,0),(0,1),(1,1),(0,2)]],
    # J – blue
    [[(0,0),(0,1),(1,1),(2,1)], [(1,0),(2,0),(1,1),(1,2)],
     [(0,1),(1,1),(2,1),(2,2)], [(1,0),(1,1),(0,2),(1,2)]],
    # L – orange
    [[(2,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(1,2),(2,2)],
     [(0,1),(1,1),(2,1),(0,2)], [(0,0),(1,0),(1,1),(1,2)]],
]

PIECE_COLORS = [CYAN, YELLOW, PURPLE, GREEN, RED, BLUE, ORANGE]

#Board
def empty_board():
    return [[0] * COLS for _ in range(ROWS)]

#Drawing
def draw_cell_board(col, row, color):
    x = BOARD_X + col * CELL
    y = BOARD_Y + row * CELL
    if color == 0:
        display.fill_rect(x, y, CELL - 1, CELL - 1, DKGREY)
    else:
        display.fill_rect(x,   y,   CELL-1, CELL-1, color)
        display.hline(x,   y,        CELL-2, WHITE)
        display.vline(x,   y,        CELL-2, WHITE)
        display.hline(x+1, y+CELL-2, CELL-2, GREY)
        display.vline(x+CELL-2, y+1, CELL-2, GREY)

def draw_board(board):
    for r in range(ROWS):
        for c in range(COLS):
            draw_cell_board(c, r, board[r][c])

def draw_board_border():
    display.rect(BOARD_X - 2, BOARD_Y - 2,
                 COLS * CELL + 4, ROWS * CELL + 4, LTGREY)
    display.rect(BOARD_X - 1, BOARD_Y - 1,
                 COLS * CELL + 2, ROWS * CELL + 2, GREY)

def draw_piece(piece_idx, rotation, px, py, erase=False):
    c = 0 if erase else PIECE_COLORS[piece_idx]
    for dc, dr in PIECES[piece_idx][rotation]:
        col, row = px + dc, py + dr
        if 0 <= row < ROWS and 0 <= col < COLS:
            draw_cell_board(col, row, c)

def draw_ghost(piece_idx, rotation, px, ghost_y):
    for dc, dr in PIECES[piece_idx][rotation]:
        col, row = px + dc, ghost_y + dr
        if 0 <= row < ROWS and 0 <= col < COLS:
            x = BOARD_X + col * CELL
            y = BOARD_Y + row * CELL
            display.rect(x, y, CELL - 1, CELL - 1, GREY)

def draw_panel(score, level, lines, next_idx):
    px = PANEL_X
    display.fill_rect(px, 0, SW - px, SH, BLACK)
    display.text(font2, "SCR",          px, 12,  LTGREY, BLACK)
    display.text(font2, str(score)[:5], px, 30,  WHITE,  BLACK)
    display.text(font2, "LVL",          px, 70,  LTGREY, BLACK)
    display.text(font2, str(level),     px, 88,  YELLOW, BLACK)
    display.text(font2, "LNS",          px, 120, LTGREY, BLACK)
    display.text(font2, str(lines),     px, 138, WHITE,  BLACK)
    display.text(font2, "NXT",          px, 175, LTGREY, BLACK)
    preview_x, preview_y = px, 195
    display.fill_rect(preview_x, preview_y, 44, 44, DKGREY)
    display.rect(preview_x,      preview_y, 44, 44, GREY)
    for dc, dr in PIECES[next_idx][0]:
        display.fill_rect(preview_x + 2 + dc * 10,
                          preview_y + 2 + dr * 10, 9, 9,
                          PIECE_COLORS[next_idx])

def show_centered(text, y, color=WHITE, bg=BLACK):
    x = max(0, (SW - len(text) * 16) // 2)
    display.text(font2, text, x, y, color, bg)

#Piece logic
def piece_cells(piece_idx, rotation, px, py):
    return [(px + dc, py + dr) for dc, dr in PIECES[piece_idx][rotation]]

def valid(board, piece_idx, rotation, px, py):
    for col, row in piece_cells(piece_idx, rotation, px, py):
        if col < 0 or col >= COLS or row >= ROWS:
            return False
        if row >= 0 and board[row][col] != 0:
            return False
    return True

def ghost_drop(board, piece_idx, rotation, px, py):
    gy = py
    while valid(board, piece_idx, rotation, px, gy + 1):
        gy += 1
    return gy

def lock_piece(board, piece_idx, rotation, px, py):
    color = PIECE_COLORS[piece_idx]
    for col, row in piece_cells(piece_idx, rotation, px, py):
        if 0 <= row < ROWS and 0 <= col < COLS:
            board[row][col] = color

def clear_lines(board):
    full = [r for r in range(ROWS) if all(board[r][c] != 0 for c in range(COLS))]
    for r in full:
        del board[r]
        board.insert(0, [0] * COLS)
    return len(full)

#Input
MOVE_DELAY   = 120
ROTATE_DELAY = 180
LINE_SCORES  = [0, 100, 300, 500, 800]

def joy_x():
    v = xAxis.read_u16()
    if v <= 600:   return -1
    if v >= 60000: return  1
    return 0

def joy_y():
    return 1 if yAxis.read_u16() >= 60000 else 0

def calc_drop_interval(level):
    return max(80, 600 - (level - 1) * 50)

#Main game
def run_game():
    import urandom

    board       = empty_board()
    score       = 0
    level       = 1
    lines_total = 0
    paused      = False
    panel_dirty = False

    display.fill(BLACK)
    draw_board_border()
    draw_board(board)

    piece_idx = urandom.randint(0, 6)
    next_idx  = urandom.randint(0, 6)
    rotation, px, py = 0, 3, 0

    draw_panel(score, level, lines_total, next_idx)

    last_drop   = utime.ticks_ms()
    last_move   = utime.ticks_ms()
    last_rotate = utime.ticks_ms()
    last_pause  = utime.ticks_ms()

    music_start()

    ghost_y = ghost_drop(board, piece_idx, rotation, px, py)
    draw_ghost(piece_idx, rotation, px, ghost_y)
    draw_piece(piece_idx, rotation, px, py)

    while True:
        now = utime.ticks_ms()
        if button3.value():
            music_stop()
            utime.sleep_ms(300)
            return False

        #Pause
        if not jbutton.value() and utime.ticks_diff(now, last_pause) > 400:
            paused = not paused
            last_pause = now
            if paused:
                music_pause()
                display.fill_rect(BOARD_X, BOARD_Y,
                                  COLS * CELL, ROWS * CELL,
                                  st7789.color565(0, 0, 60))
                show_centered("PAUSED", SH // 2 - 8, YELLOW,
                              st7789.color565(0, 0, 60))
            else:
                music_resume()
                draw_board(board)
                ghost_y = ghost_drop(board, piece_idx, rotation, px, py)
                draw_ghost(piece_idx, rotation, px, ghost_y)
                draw_piece(piece_idx, rotation, px, py)
            utime.sleep_ms(50)

        if paused:
            utime.sleep_ms(30)
            continue

        #Horizontal move
        dx = joy_x()
        if dx != 0 and utime.ticks_diff(now, last_move) > MOVE_DELAY:
            new_px = px + dx
            if valid(board, piece_idx, rotation, new_px, py):
                for col, row in piece_cells(piece_idx, rotation, px, py):
                    if 0 <= row < ROWS:
                        draw_cell_board(col, row, board[row][col])
                for col, row in piece_cells(piece_idx, rotation, px, ghost_y):
                    if 0 <= row < ROWS:
                        draw_cell_board(col, row, board[row][col])
                px      = new_px
                ghost_y = ghost_drop(board, piece_idx, rotation, px, py)
                draw_ghost(piece_idx, rotation, px, ghost_y)
                draw_piece(piece_idx, rotation, px, py)
            last_move = now

        #Soft drop speed
        drop_interval = 50 if joy_y() == 1 else calc_drop_interval(level)

        #Rotate
        rotated = None
        if button1.value() and utime.ticks_diff(now, last_rotate) > ROTATE_DELAY:
            rotated     = (rotation + 1) % 4
            last_rotate = now
        elif button2.value() and utime.ticks_diff(now, last_rotate) > ROTATE_DELAY:
            rotated     = (rotation - 1) % 4
            last_rotate = now

        if rotated is not None:
            for kick in [0, 1, -1, 2, -2]:
                if valid(board, piece_idx, rotated, px + kick, py):
                    for col, row in piece_cells(piece_idx, rotation, px, py):
                        if 0 <= row < ROWS:
                            draw_cell_board(col, row, board[row][col])
                    for col, row in piece_cells(piece_idx, rotation, px, ghost_y):
                        if 0 <= row < ROWS:
                            draw_cell_board(col, row, board[row][col])
                    rotation = rotated
                    px      += kick
                    ghost_y  = ghost_drop(board, piece_idx, rotation, px, py)
                    draw_ghost(piece_idx, rotation, px, ghost_y)
                    draw_piece(piece_idx, rotation, px, py)
                    #no sfx_rotate() call — music keeps playing
                    break

        #Gravity
        if utime.ticks_diff(now, last_drop) > drop_interval:
            last_drop = now

            if valid(board, piece_idx, rotation, px, py + 1):
                for col, row in piece_cells(piece_idx, rotation, px, py):
                    if 0 <= row < ROWS:
                        draw_cell_board(col, row, board[row][col])
                py += 1
                new_ghost = ghost_drop(board, piece_idx, rotation, px, py)
                if new_ghost != ghost_y:
                    for col, row in piece_cells(piece_idx, rotation, px, ghost_y):
                        if 0 <= row < ROWS:
                            draw_cell_board(col, row, board[row][col])
                    ghost_y = new_ghost
                    draw_ghost(piece_idx, rotation, px, ghost_y)
                draw_piece(piece_idx, rotation, px, py)
                #no sfx_lock pulse — music keeps playing

            else:
                lock_piece(board, piece_idx, rotation, px, py)
                cleared = clear_lines(board)

                if cleared:
                    #Line clear chime: briefly pause music,
                    #play chime, resume. Total gap < 300ms.
                    sfx_line_clear(cleared)
                    score       += LINE_SCORES[cleared] * level
                    lines_total += cleared
                    level        = lines_total // 10 + 1
                    draw_board(board)
                else:
                    for col, row in piece_cells(piece_idx, rotation, px, py):
                        if 0 <= row < ROWS:
                            draw_cell_board(col, row, board[row][col])

                panel_dirty = True

                #Spawn next piece
                piece_idx        = next_idx
                next_idx         = urandom.randint(0, 6)
                rotation, px, py = 0, 3, 0

                if not valid(board, piece_idx, rotation, px, py):
                    draw_piece(piece_idx, rotation, px, py)
                    music_stop()
                    sfx_gameover()
                    display.fill_rect(20, 90, 160, 70, DKGREY)
                    display.rect(20,     90, 160, 70, WHITE)
                    show_centered("GAME OVER", 98,  RED,   DKGREY)
                    show_centered("SCR:" + str(score), 120, WHITE, DKGREY)
                    show_centered("B4=RETRY",  142, GREY,  DKGREY)
                    show_centered("B3=MENU",   155, GREY,  DKGREY)
                    while True:
                        if button4.value():
                            utime.sleep_ms(300)
                            return True
                        if button3.value():
                            utime.sleep_ms(300)
                            return False

                ghost_y = ghost_drop(board, piece_idx, rotation, px, py)
                draw_ghost(piece_idx, rotation, px, ghost_y)
                draw_piece(piece_idx, rotation, px, py)

        if panel_dirty:
            draw_panel(score, level, lines_total, next_idx)
            panel_dirty = False

        utime.sleep_ms(16)
        
while True:
    if not run_game():
        break
