# snake.py - Snake Game for THE PAD

import time
import st7789py as st7789
import urandom
from machine import Timer

# --- Colors ---
BLACK   = st7789.BLACK
WHITE   = st7789.WHITE
GREEN   = st7789.color565(0,   200, 0)
DKGREEN = st7789.color565(0,   120, 0)
RED     = st7789.color565(220, 0,   0)
YELLOW  = st7789.color565(255, 215, 0)
GRAY    = st7789.color565(150, 150, 150)
BLUE    = st7789.color565(30,  80,  220)
DARK    = st7789.color565(20,  20,  20)

# --- Constants ---
CELL    = 10
COLS    = 23
ROWS    = 20
SCORE_H = 36

# ---------------------------------------------------
# NON-BLOCKING BUZZER
# Receives play_sequence from main so no re-init needed
# ---------------------------------------------------
def make_sound_fns(play_sequence):
    def collect():
        play_sequence([(523,40),(659,40),(784,40),(1047,60)])

    def death():
        play_sequence([(400,120),(300,140),(200,160),(100,200)])

    def start():
        play_sequence([(659,80),(784,80),(1046,150)])

    def pause_snd():
        play_sequence([(440, 60)])

    def resume_snd():
        play_sequence([(523, 60)])

    return collect, death, start, pause_snd, resume_snd

# ---------------------------------------------------
# DRAWING
# ---------------------------------------------------
def cell_color(idx):
    return GREEN if idx % 2 == 0 else DKGREEN

def draw_cell(tft, col, row, color):
    tft.fill_rect(col * CELL,
                  SCORE_H + row * CELL,
                  CELL - 1, CELL - 1, color)

def draw_border(tft):
    BORDER = st7789.color565(60, 60, 160)
    tft.fill_rect(0, SCORE_H, 240, CELL, BORDER)
    tft.fill_rect(0, SCORE_H + (ROWS-1)*CELL, 240, CELL, BORDER)
    tft.fill_rect(0, SCORE_H, CELL, ROWS*CELL, BORDER)
    tft.fill_rect((COLS-1)*CELL, SCORE_H, CELL, ROWS*CELL, BORDER)

def draw_score(tft, fnt, score, high):
    tft.fill_rect(0, 0, 240, SCORE_H, BLUE)
    s_str = f"S:{score}"
    h_str = f"HI:{high}"
    sy = (SCORE_H - fnt.HEIGHT) // 2
    tft.text(fnt, s_str, 6,  sy, YELLOW, BLUE)
    tft.text(fnt, h_str, 240 - len(h_str) * fnt.WIDTH - 6, sy, WHITE, BLUE)

def draw_centered(tft, fnt, text, y, fg=WHITE, bg=BLACK):
    x = max(0, (240 - len(text) * fnt.WIDTH) // 2)
    tft.text(fnt, text, x, y, fg, bg)

def place_food(snake):
    while True:
        fc = urandom.randint(1, COLS - 2)
        fr = urandom.randint(1, ROWS - 2)
        if (fc, fr) not in snake:
            return (fc, fr)

# ---------------------------------------------------
# JOYSTICK
# ---------------------------------------------------
CENTER   = 32768
DEADZONE = 10000

def get_snake_dir(joy_x, joy_y):
    """Returns (dx,dy) or None if centered. Axes inverted for PAD."""
    x  = joy_x.read_u16()
    y  = joy_y.read_u16()
    dx = x - CENTER
    dy = y - CENTER
    if abs(dx) < DEADZONE and abs(dy) < DEADZONE:
        return None
    if abs(dx) >= abs(dy):
        return (-1, 0) if dx > 0 else (1, 0)
    else:
        return (0, -1) if dy > 0 else (0, 1)

# ---------------------------------------------------
# FRAME SPEED
# ---------------------------------------------------
def frame_ms(score):
    return max(60, 150 - score * 4)

# ---------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------
def run(tft, spi, btn1, btn2, joy_sel, joy_x, joy_y,
        led1, led2, buzzer, fnt, led_override, play_sequence):

    collect, death, start, pause_snd, resume_snd = \
        make_sound_fns(play_sequence)

    high_score = 0

    # ==================================================
    # OUTER LOOP — returns here after each game over
    # ==================================================
    while True:

        # --- Start screen ---
        tft.fill(BLACK)
        draw_centered(tft, fnt, "SNAKE",  56,  GREEN,  BLACK)
        draw_centered(tft, fnt, "BTN1",   112, WHITE,  BLACK)
        draw_centered(tft, fnt, "START",  144, GRAY,   BLACK)
        draw_centered(tft, fnt, "BTN2",   196, WHITE,  BLACK)
        draw_centered(tft, fnt, "MENU",   212, GRAY,   BLACK)

        while True:
            if btn1.value() == 0:
                time.sleep_ms(200)
                break
            if btn2.value() == 0:
                time.sleep_ms(200)
                led_override(False)
                return
            time.sleep_ms(16)

        start()
        time.sleep_ms(320)   # Let start chime begin before game draws

        # --- Game init ---
        tft.fill(BLACK)
        draw_border(tft)

        snake     = [(COLS//2 - i, ROWS//2) for i in range(3)]
        direction = (1, 0)
        food      = place_food(snake)
        score     = 0
        paused    = False
        game_over = False

        draw_score(tft, fnt, score, high_score)
        draw_cell(tft, *food, RED)
        for i, seg in enumerate(snake):
            draw_cell(tft, *seg, cell_color(i))

        prev_joy  = None

        # ==================================================
        # INNER GAME LOOP
        # ==================================================
        while not game_over:
            t0 = time.ticks_ms()

            # BTN2 — exit to menu
            if btn2.value() == 0:
                time.sleep_ms(200)
                led_override(False)
                return

            # BTN1 or SEL — pause toggle
            if btn1.value() == 0 or joy_sel.value() == 0:
                paused = not paused
                time.sleep_ms(300)

                if paused:
                    # Manual LED control during pause
                    led_override(True)
                    led1.value(1)
                    led2.value(1)
                    pause_snd()
                    # Dim overlay
                    draw_centered(tft, fnt, "PAUSED", 104, YELLOW, BLACK)
                    draw_centered(tft, fnt, "BTN1",   144, WHITE,  BLACK)
                    draw_centered(tft, fnt, "RESUME",  176, GRAY,   BLACK)
                else:
                    led_override(False)   # Return LEDs to button mirroring
                    resume_snd()
                    # Full board redraw on unpause
                    tft.fill(BLACK)
                    draw_border(tft)
                    draw_score(tft, fnt, score, high_score)
                    draw_cell(tft, *food, RED)
                    for i, seg in enumerate(snake):
                        draw_cell(tft, *seg, cell_color(i))

            if paused:
                time.sleep_ms(16)
                continue

            # --- Joystick ---
            joy = get_snake_dir(joy_x, joy_y)
            if joy is not None and joy != prev_joy:
                ndx, ndy = joy
                cdx, cdy = direction
                # Block direct reversal
                if (ndx, ndy) != (-cdx, -cdy):
                    direction = (ndx, ndy)
            prev_joy = joy

            # --- Move ---
            head = (snake[0][0] + direction[0],
                    snake[0][1] + direction[1])

            # Wall check
            if not (1 <= head[0] < COLS-1 and
                    1 <= head[1] < ROWS-1):
                game_over = True
                break

            # Self check
            if head in snake:
                game_over = True
                break

            snake.insert(0, head)

            if head == food:
                score += 1
                if score > high_score:
                    high_score = score

                # Non-blocking collect sound — game loop continues instantly
                collect()

                # Score bar update only — no full redraw
                draw_score(tft, fnt, score, high_score)

                food = place_food(snake)
                draw_cell(tft, *food, RED)
            else:
                tail = snake.pop()
                draw_cell(tft, *tail, BLACK)

            for i, seg in enumerate(snake):
                draw_cell(tft, *seg, cell_color(i))

            # --- Frame timing ---
            elapsed = time.ticks_diff(time.ticks_ms(), t0)
            wait    = frame_ms(score) - elapsed
            if wait > 0:
                time.sleep_ms(wait)

        # ==================================================
        # GAME OVER
        # ==================================================
        death()

        led_override(True)
        led1.value(1)
        led2.value(1)

        tft.fill(BLACK)
        draw_centered(tft, fnt, "GAME",       48,  RED,    BLACK)
        draw_centered(tft, fnt, "OVER",       80,  RED,    BLACK)
        draw_centered(tft, fnt, f"S:{score}", 128, WHITE,  BLACK)
        draw_centered(tft, fnt, f"HI:{high_score}", 160, YELLOW, BLACK)
        draw_centered(tft, fnt, "BTN1=RETRY", 200, WHITE,  BLACK)
        draw_centered(tft, fnt, "BTN2=MENU",  215, GRAY,   BLACK)

        time.sleep_ms(800)
        led_override(False)

        while True:
            if btn1.value() == 0:
                time.sleep_ms(200)
                break           # Retry — back to outer loop
            if btn2.value() == 0:
                time.sleep_ms(200)
                led_override(False)
                return          # Back to launcher
            time.sleep_ms(16)