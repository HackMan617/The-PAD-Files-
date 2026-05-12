# flappy.py - Flappy Bird for THE PAD

import time
import st7789py as st7789
import random
import gc

# --- Colors ---
BLACK  = st7789.BLACK
WHITE  = st7789.WHITE
RED    = st7789.color565(220, 30,  30)
GREEN  = st7789.color565(30,  180, 30)
YELLOW = st7789.color565(255, 220, 0)
GRAY   = st7789.color565(80,  80,  80)
DARK   = st7789.color565(20,  20,  20)

# --- Constants ---
SCREEN_W    = 240
SCREEN_H    = 240
FONT_W      = 16
FONT_H      = 32
SCORE_BAR_H = FONT_H

PLAY_TOP    = SCORE_BAR_H
PLAY_H      = SCREEN_H - SCORE_BAR_H

BIRD_W      = 16
BIRD_H      = 16
BIRD_X      = 40

PIPE_W      = 28
PIPE_GAP    = 75
PIPE_SPEED  = 2

GRAVITY     = 1.0
JUMP_VEL    = -7.0
MAX_FALL    = 7.0

# ---------------------------------------------------
# SOUND
# Uses play_sequence passed from main — non-blocking
# Blocking beeps only used for death (game already over)
# ---------------------------------------------------
def _jump_snd(play_seq):
    play_seq([(880, 35)])

def _score_snd(play_seq):
    play_seq([(1046, 50), (1318, 70)])

def _pause_snd(play_seq):
    play_seq([(440, 60)])

def _resume_snd(play_seq):
    play_seq([(523, 60)])

def _death_snd(buz):
    """Blocking — game is already over, no loop to interrupt"""
    for f, d in [(330, 100), (220, 250)]:
        buz.freq(f)
        buz.duty_u16(32768)
        time.sleep_ms(d)
    buz.duty_u16(0)

def _start_snd(play_seq):
    play_seq([(523, 100), (659, 100), (784, 150)])

# ---------------------------------------------------
# DISPLAY HELPERS
# ---------------------------------------------------
def draw_centered(tft, fnt, text, y, fg=WHITE, bg=BLACK):
    x = max(0, (SCREEN_W - len(text) * FONT_W) // 2)
    tft.text(fnt, text, x, y, fg, bg)

def draw_score_bar(tft, fnt, score):
    tft.fill_rect(0, 0, SCREEN_W, SCORE_BAR_H, BLACK)
    draw_centered(tft, fnt, f"SCORE:{score}", 0, YELLOW, BLACK)

def render_frame(tft, bird_y, pipe_x, gap_y, prev_pipe_x):
    # Erase trailing pipe edge
    trail_x = pipe_x + PIPE_W
    if 0 <= trail_x < SCREEN_W:
        tft.fill_rect(trail_x, PLAY_TOP, 1, PLAY_H, DARK)
    if prev_pipe_x != pipe_x:
        erase_x = prev_pipe_x + PIPE_W
        if 0 <= erase_x < SCREEN_W:
            tft.fill_rect(erase_x, PLAY_TOP, 2, PLAY_H, DARK)

    # Top pipe
    top_h = gap_y - PLAY_TOP
    if top_h > 0 and pipe_x < SCREEN_W and pipe_x + PIPE_W > 0:
        tft.fill_rect(max(0, pipe_x), PLAY_TOP,
                      min(PIPE_W, SCREEN_W - max(0, pipe_x)),
                      top_h, GREEN)

    # Bottom pipe
    bot_y = gap_y + PIPE_GAP
    bot_h = SCREEN_H - bot_y
    if bot_h > 0 and pipe_x < SCREEN_W and pipe_x + PIPE_W > 0:
        tft.fill_rect(max(0, pipe_x), bot_y,
                      min(PIPE_W, SCREEN_W - max(0, pipe_x)),
                      bot_h, GREEN)

    # Gap fill — prevents green bleed
    if pipe_x < SCREEN_W and pipe_x + PIPE_W > 0:
        tft.fill_rect(max(0, pipe_x), gap_y,
                      min(PIPE_W, SCREEN_W - max(0, pipe_x)),
                      PIPE_GAP, DARK)

    # Bird — always last
    bx = max(0, BIRD_X)
    by = max(PLAY_TOP, min(bird_y, SCREEN_H - BIRD_H))
    tft.fill_rect(bx, by, BIRD_W, BIRD_H, RED)

def erase_bird_trail(tft, prev_y, curr_y):
    diff = curr_y - prev_y
    if diff > 0:
        tft.fill_rect(BIRD_X, prev_y, BIRD_W, min(diff, BIRD_H), DARK)
    elif diff < 0:
        tft.fill_rect(BIRD_X, curr_y + BIRD_H,
                      BIRD_W, min(-diff, BIRD_H), DARK)

def check_collision(bird_y, pipe_x, gap_y):
    if bird_y <= PLAY_TOP or bird_y + BIRD_H >= SCREEN_H:
        return True
    if BIRD_X + BIRD_W > pipe_x and BIRD_X < pipe_x + PIPE_W:
        if bird_y < gap_y or bird_y + BIRD_H > gap_y + PIPE_GAP:
            return True
    return False

# ---------------------------------------------------
# SCREENS
# ---------------------------------------------------
def show_start(tft, fnt):
    tft.fill(BLACK)
    draw_centered(tft, fnt, "FLAPPY",   48,  RED,    BLACK)
    draw_centered(tft, fnt, "BIRD",     80,  RED,    BLACK)
    draw_centered(tft, fnt, "BTN1",     136, WHITE,  BLACK)
    draw_centered(tft, fnt, "START",    168, GRAY,   BLACK)
    draw_centered(tft, fnt, "BTN2",     200, WHITE,  BLACK)
    draw_centered(tft, fnt, "MENU",     215, GRAY,   BLACK)

def show_paused(tft, fnt):
    tft.fill(BLACK)
    draw_centered(tft, fnt, "PAUSED",   85,  YELLOW, BLACK)
    draw_centered(tft, fnt, "BTN2",     148, WHITE,  BLACK)
    draw_centered(tft, fnt, "RESUME",   180, GRAY,   BLACK)
    draw_centered(tft, fnt, "BTN1",     200, WHITE,  BLACK)
    draw_centered(tft, fnt, "MENU",     215, GRAY,   BLACK)

def show_game_over(tft, fnt, score):
    tft.fill(BLACK)
    draw_centered(tft, fnt, "GAME",     45,  RED,    BLACK)
    draw_centered(tft, fnt, "OVER",     85,  RED,    BLACK)
    draw_centered(tft, fnt, f"{score}PTS", 145, YELLOW, BLACK)
    draw_centered(tft, fnt, "BTN1",     188, WHITE,  BLACK)
    draw_centered(tft, fnt, "RETRY",    210, GRAY,   BLACK)
    draw_centered(tft, fnt, "BTN2=MENU",220, GRAY,   BLACK)

# ---------------------------------------------------
# MAIN ENTRY
# 14 parameters — matches launch_game() in main.py
# ---------------------------------------------------
def run(tft, spi, btn1, btn2, joy_sel, joy_x, joy_y,
        led1, led2, buzzer, fnt, led_override,
        play_sequence, stop_sequence):

    print(f"[flappy] run() entered. Free RAM: {gc.mem_free()}")

    high_score = 0

    # ==================================================
    # OUTER LOOP — retry without reloading module
    # ==================================================
    while True:

        # --- Start screen ---
        show_start(tft, fnt)

        while True:
            if btn1.value() == 0:
                time.sleep_ms(200)
                break                   # Start game
            if btn2.value() == 0:
                time.sleep_ms(200)
                led_override(False)
                return                  # Back to menu
            time.sleep_ms(16)

        _start_snd(play_sequence)
        time.sleep_ms(320)

        # --- Game state ---
        gc.collect()

        bird_y      = float(SCREEN_H // 2)
        bird_vel    = 0.0
        score       = 0
        scored      = False
        paused      = False

        min_gap  = PLAY_TOP + 25
        max_gap  = SCREEN_H - PIPE_GAP - 25
        pipe_x   = SCREEN_W
        gap_y    = random.randint(min_gap, max_gap)
        prev_pipe_x = pipe_x

        tft.fill(DARK)
        draw_score_bar(tft, fnt, score)
        render_frame(tft, int(bird_y), pipe_x, gap_y, pipe_x)
        prev_bird_y = int(bird_y)

        # ==================================================
        # INNER GAME LOOP
        # ==================================================
        while True:
            t0 = time.ticks_ms()

            # --- BTN2 exits to menu at any time ---
            if btn2.value() == 0:
                time.sleep_ms(200)
                stop_sequence()
                led_override(False)
                led1.value(0)
                led2.value(0)
                return

            # --- Pause toggle (SEL or BTN2 while paused) ---
            if joy_sel.value() == 0:
                if not paused:
                    paused = True
                    led2.value(1)
                    _pause_snd(play_sequence)
                    show_paused(tft, fnt)
                    while joy_sel.value() == 0:
                        time.sleep_ms(20)
                else:
                    paused = False
                    led2.value(0)
                    _resume_snd(play_sequence)
                    tft.fill(DARK)
                    draw_score_bar(tft, fnt, score)
                    render_frame(tft, int(bird_y), pipe_x,
                                 gap_y, pipe_x)
                    while joy_sel.value() == 0:
                        time.sleep_ms(20)

            # --- While paused: BTN1 returns to menu ---
            if paused:
                if btn1.value() == 0:
                    time.sleep_ms(200)
                    led_override(False)
                    led1.value(0)
                    led2.value(0)
                    return
                time.sleep_ms(16)
                continue

            # --- Jump ---
            if btn1.value() == 0:
                bird_vel = JUMP_VEL
                _jump_snd(play_sequence)
                led1.value(1)
            else:
                led1.value(0)

            # --- Physics ---
            bird_vel  = min(bird_vel + GRAVITY, MAX_FALL)
            bird_y   += bird_vel

            # --- Erase bird trail ---
            erase_bird_trail(tft, prev_bird_y, int(bird_y))

            # --- Move pipe ---
            prev_pipe_x  = pipe_x
            pipe_x      -= PIPE_SPEED

            # --- Respawn pipe ---
            if pipe_x + PIPE_W < 0:
                pipe_x  = SCREEN_W
                gap_y   = random.randint(min_gap, max_gap)
                scored  = False
                tft.fill_rect(0, PLAY_TOP, SCREEN_W, PLAY_H, DARK)

            # --- Score ---
            if not scored and pipe_x + PIPE_W < BIRD_X:
                score  += 1
                scored  = True
                _score_snd(play_sequence)
                draw_score_bar(tft, fnt, score)

            # --- Render ---
            render_frame(tft, int(bird_y), pipe_x,
                         gap_y, prev_pipe_x)
            prev_bird_y = int(bird_y)

            # --- Collision ---
            if check_collision(int(bird_y), pipe_x, gap_y):
                tft.fill_rect(BIRD_X, int(bird_y),
                              BIRD_W, BIRD_H, YELLOW)
                stop_sequence()
                _death_snd(buzzer)
                led_override(True)
                led1.value(1)
                led2.value(1)
                time.sleep(1)
                led_override(False)

                if score > high_score:
                    high_score = score

                show_game_over(tft, fnt, score)
                print(f"[flappy] Score:{score} Best:{high_score}")

                # Wait for retry or menu
                while True:
                    if btn1.value() == 0:
                        time.sleep_ms(200)
                        break           # Retry — back to outer loop
                    if btn2.value() == 0:
                        time.sleep_ms(200)
                        led_override(False)
                        return          # Back to menu
                    time.sleep_ms(16)

                break                   # Exit inner loop to retry

            # --- Frame cap ~25fps ---
            elapsed = time.ticks_diff(time.ticks_ms(), t0)
            wait    = 40 - elapsed
            if wait > 0:
                time.sleep_ms(wait)