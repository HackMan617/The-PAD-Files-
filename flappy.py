# CONTROLS
#  --------
#  Button 1 (GP4)  OR  Joystick UP  – flap
#  Button 3 (GP1)                   – return to menu
#  Button 4 (GP2)                   – restart after death
#
#  PIPE FIX
#  --------
#  Each frame the game redraws every active pipe column from
#  scratch (sky → pipe → gap → pipe) before drawing the bird
#  on top. This prevents the erase-overdraw tearing that
#  occurred when pipes were close together or overlapping the
#  bird's bounding box. (this solution has yet to yield promising results)
# =============================================================

from machine import Pin, SPI, ADC, PWM, Timer
import utime
import st7789py as st7789
from fonts import vga1_16x32 as font2

# ── Display ───────────────────────────────────────────────────
spi1 = SPI(1, baudrate=40000000, polarity=1)
display = st7789.ST7789(
    spi1, 240, 240,
    reset=Pin(12, Pin.OUT),
    dc=Pin(13, Pin.OUT),
    rotation=1)

# ── Inputs ────────────────────────────────────────────────────
button  = Pin(4, Pin.IN, Pin.PULL_DOWN)   #flap
button2 = Pin(5, Pin.IN, Pin.PULL_DOWN)
button3 = Pin(1, Pin.IN, Pin.PULL_DOWN)   #menu
button4 = Pin(2, Pin.IN, Pin.PULL_DOWN)   #restart
xAxis   = ADC(Pin(26))
yAxis   = ADC(Pin(27))

# ── Buzzer ────────────────────────────────────────────────────
buzzer = PWM(Pin(15))
buzzer.duty_u16(0)

_tone_seq   = []
_tone_timer = Timer()

def _next_tone(t):
    global _tone_seq
    if _tone_seq:
        freq, dur = _tone_seq.pop(0)
        if freq:
            buzzer.freq(freq)
            buzzer.duty_u16(2000)
        else:
            buzzer.duty_u16(0)
        _tone_timer.init(mode=Timer.ONE_SHOT, period=dur, callback=_next_tone)
    else:
        buzzer.duty_u16(0)
        _tone_timer.deinit()

def play_sequence(notes):
    global _tone_seq
    _tone_seq = list(notes)
    _next_tone(None)

def play_tone(freq, ms, duty=2500):
    buzzer.freq(freq)
    buzzer.duty_u16(duty)
    utime.sleep_ms(ms)
    buzzer.duty_u16(0)

def snd_flap():
    play_sequence([(880, 30), (660, 30)])

def snd_score():
    play_sequence([(523, 50), (784, 80)])

def snd_death():
    for f in [440, 330, 220, 150]:
        play_tone(f, 80)

#Colors
BLACK    = st7789.BLACK
WHITE    = st7789.WHITE
SKY      = st7789.color565( 80, 180, 255)
GROUND_T = st7789.color565( 90, 200,  50)
GROUND_B = st7789.color565(150, 100,  40)
PIPE_G   = st7789.color565( 50, 180,  50)
PIPE_DK  = st7789.color565( 30, 130,  30)
PIPE_LT  = st7789.color565(120, 220, 120)
YELLOW   = st7789.color565(255, 215,   0)
RED      = st7789.color565(220,  50,  50)
GREY     = st7789.color565(150, 150, 150)
DKGREY   = st7789.color565( 40,  40,  40)
ORANGE   = st7789.color565(230, 120,  30)
WHITE2   = st7789.color565(240, 240, 240)

# ── Constants ─────────────────────────────────────────────────
SW, SH        = 240, 240
GRAVITY       =  0.45
FLAP_V        = -6.0
MAX_FALL      =  8.0
BIRD_X        =  55
BIRD_W        =  17
BIRD_H        =  13
PIPE_W        =  28
PIPE_GAP      =  70
PIPE_SPEED    =  2.5
PIPE_INTERVAL =  90
GROUND_H      =  20
CEILING       =   0
PLAY_H        = SH - GROUND_H   #vertical pixels available for play

# ── Pipe column renderer ──────────────────────────────────────
# Draws one vertical pixel column (x) correctly given a pipe's
# gap position.  Called for every column of a pipe each frame
# so there is never a stale pixel left behind.

def _draw_pipe_column(x, gap_y):
    gap_bot = gap_y + PIPE_GAP

    # Determine whether this column is on the edge, inner, or body
    is_left_edge  = (x == 0)          #relative to pipe — passed as abs below
    is_right_edge = False              

    # Top pipe section  (y = 0 .. gap_y-1)
    if gap_y > 0:
        # Body fill
        display.vline(x, 0, gap_y, PIPE_G)
        # Cap row (6 px tall, full width of pipe — drawn per-column)
        cap_y = max(0, gap_y - 6)
        # Cap is slightly lighter on top, darker on bottom
        display.vline(x, cap_y, gap_y - cap_y, PIPE_G)

    # Gap section  (y = gap_y .. gap_bot-1) → sky
    display.vline(x, gap_y, PIPE_GAP, SKY)

    # Bottom pipe section  (y = gap_bot .. PLAY_H-1)
    if gap_bot < PLAY_H:
        display.vline(x, gap_bot, PLAY_H - gap_bot, PIPE_G)


def draw_pipe_full(px, gap_y):
    gap_bot = gap_y + PIPE_GAP

    #Top pipe
    if gap_y > 0:
        # Main body (inset 2px from each edge for border)
        display.fill_rect(px + 2, 0,     PIPE_W - 4, gap_y,     PIPE_G)
        # Left shadow line
        display.vline(px + 2, 0, gap_y, PIPE_DK)
        # Right highlight line
        display.vline(px + PIPE_W - 3, 0, gap_y, PIPE_LT)
        # Cap (6 px tall, full pipe width)
        cap_y = max(0, gap_y - 6)
        cap_h = gap_y - cap_y
        display.fill_rect(px,     cap_y, PIPE_W,     cap_h, PIPE_G)
        display.hline(px, cap_y,         PIPE_W,            PIPE_LT)  #top of cap
        display.hline(px, gap_y - 1,     PIPE_W,            PIPE_DK)  #bottom of cap

    #Gap (sky)
    display.fill_rect(px, gap_y, PIPE_W, PIPE_GAP, SKY)

    # ── Bottom pipe ───────────────────────────────────────────
    bot_h = PLAY_H - gap_bot
    if bot_h > 0:
        # Cap first (top of bottom pipe)
        display.fill_rect(px,     gap_bot,     PIPE_W, 6,        PIPE_G)
        display.hline(px, gap_bot,             PIPE_W,           PIPE_LT)
        display.hline(px, gap_bot + 5,         PIPE_W,           PIPE_DK)
        # Body below cap
        if bot_h > 6:
            display.fill_rect(px + 2, gap_bot + 6, PIPE_W - 4, bot_h - 6, PIPE_G)
            display.vline(px + 2,     gap_bot + 6, bot_h - 6,  PIPE_DK)
            display.vline(px + PIPE_W - 3, gap_bot + 6, bot_h - 6, PIPE_LT)


def erase_pipe_column_range(x, w):
    display.fill_rect(x, 0, w, PLAY_H, SKY)

# ── Ground ────────────────────────────────────────────────────
def draw_ground():
    y = SH - GROUND_H
    display.fill_rect(0, y,     SW, 4,            GROUND_T)
    display.fill_rect(0, y + 4, SW, GROUND_H - 4, GROUND_B)

_ground_offset = 0

def draw_ground_scroll(offset):
    y = SH - GROUND_H
    display.fill_rect(0, y + 4, SW, GROUND_H - 4, GROUND_B)
    for i in range(0, SW + 20, 20):
        dx = (i + offset) % (SW + 20) - 10
        if 0 <= dx < SW:
            display.fill_rect(dx, y + 6, 8, 3, GROUND_T)

# ── Bird ──────────────────────────────────────────────────────
def draw_bird(x, y, vel):
    bx, by = int(x), int(y)
    display.fill_rect(bx + 2, by + 3, 13, 8,  YELLOW)
    display.fill_rect(bx + 1, by + 4, 15, 6,  YELLOW)
    wing_y = by + 2 if vel < 0 else by + 7
    display.fill_rect(bx + 4, wing_y,  7, 3,  WHITE2)
    display.fill_rect(bx + 10, by + 4, 4, 4,  WHITE2)
    display.fill_rect(bx + 11, by + 5, 2, 2,  BLACK)
    display.fill_rect(bx + 14, by + 6, 4, 3,  ORANGE)
    display.fill_rect(bx + 15, by + 7, 3, 2,  ORANGE)

def erase_bird(x, y):
    bx, by = int(x), int(y)
    display.fill_rect(bx, by, BIRD_W + 2, BIRD_H + 2, SKY)

# ── HUD ───────────────────────────────────────────────────────
def draw_score_hud(score):
    s = str(score)
    x = (SW - len(s) * 16) // 2
    display.text(font2, s, x, 6, WHITE, SKY)

# ── Helpers ───────────────────────────────────────────────────
def show_centered(text, y, color=WHITE, bg=BLACK):
    x = max(0, (SW - len(text) * 16) // 2)
    display.text(font2, text, x, y, color, bg)

def draw_bg():
    display.fill(SKY)
    draw_ground()

# ── Collision ─────────────────────────────────────────────────
def check_collision(bird_x, bird_y, pipes):
    bx1 = bird_x + 2
    bx2 = bird_x + BIRD_W - 2
    by1 = bird_y + 1
    by2 = bird_y + BIRD_H - 1

    if by2 >= PLAY_H:
        return True
    if by1 <= CEILING:
        return True

    for px, gap_y, _ in pipes:
        px2 = px + PIPE_W
        if bx2 > px + 2 and bx1 < px2 - 2:
            if by1 < gap_y or by2 > gap_y + PIPE_GAP:
                return True
    return False

# ── Main game ─────────────────────────────────────────────────
def run_game():
    import urandom
    global _ground_offset

    bird_y  = float(SH // 2 - BIRD_H // 2)
    bird_vy = 0.0
    score   = 0
    tick    = 0
    dead    = False
    pipes   = []        # [x_float, gap_y, scored]

    btn_was_low = True

    #Initial draw
    draw_bg()
    draw_bird(BIRD_X, bird_y, bird_vy)
    draw_score_hud(score)

    #Wait for first tap
    show_centered("TAP TO START", SH // 2 - 8, WHITE, SKY)
    show_centered("B3=MENU",      SH // 2 + 20, GREY,  SKY)

    while True:
        yv = yAxis.read_u16()
        if button.value() or yv <= 600:
            break
        if button3.value():
            return False
        utime.sleep_ms(30)

    #Clear prompt text
    display.fill_rect(0, SH // 2 - 12, SW, 50, SKY)

    #Game loop
    while not dead:
        if button3.value():
            buzzer.duty_u16(0)
            utime.sleep_ms(300)
            return False
        yv       = yAxis.read_u16()
        flap_now = button.value() or yv <= 600
        if flap_now and btn_was_low:
            bird_vy  = FLAP_V
            btn_was_low = False
            snd_flap()
        if not flap_now:
            btn_was_low = True

        # Physics
        bird_vy = min(bird_vy + GRAVITY, MAX_FALL)
        old_y   = bird_y
        bird_y += bird_vy

        # Spawn new pipe
        tick += 1
        if tick % PIPE_INTERVAL == 0:
            gap_y = urandom.randint(30, PLAY_H - PIPE_GAP - 30)
            pipes.append([float(SW), gap_y, False])

        #Pipe updates
        erase_bird(BIRD_X, old_y)

        pipes_out = []
        for pipe in pipes:
            old_px  = int(pipe[0])
            pipe[0] -= PIPE_SPEED
            new_px   = int(pipe[0])

            if new_px + PIPE_W < 0:
                erase_pipe_column_range(0, PIPE_W)
                pipes_out.append(pipe)
                continue

            if old_px != new_px:
                #The pipe moved at least 1 pixel this tick.
                #Erase the rightmost columns that the pipe vacated,
                #then redraw the entire pipe at its new position.
                #This order means there's never a gap frame.
                vacated_x = new_px + PIPE_W
                vacated_w = old_px - new_px   # how many px were uncovered on right
                if vacated_x < SW and vacated_w > 0:
                    display.fill_rect(vacated_x, 0, vacated_w, PLAY_H, SKY)
                draw_pipe_full(new_px, pipe[1])

            if not pipe[2] and pipe[0] + PIPE_W < BIRD_X:
                pipe[2] = True
                score  += 1
                snd_score()

        for p in pipes_out:
            pipes.remove(p)
        draw_bird(BIRD_X, bird_y, bird_vy)

        _ground_offset = (_ground_offset + int(PIPE_SPEED)) % SW
        draw_ground_scroll(_ground_offset)
        draw_score_hud(score)

        if check_collision(BIRD_X, bird_y, pipes):
            dead = True
            break

        utime.sleep_ms(30)

    #Death
    snd_death()
    buzzer.duty_u16(0)

    display.fill(WHITE)
    utime.sleep_ms(120)

    #Redraw scene cleanly for death screen
    draw_bg()
    for p in pipes:
        draw_pipe_full(int(p[0]), p[1])
    draw_bird(BIRD_X, bird_y, bird_vy)
    draw_ground()

    display.fill_rect(30,  80, 180, 90, DKGREY)
    display.rect(30,       80, 180, 90, WHITE)
    show_centered("DEAD!",              95,  RED,   DKGREY)
    show_centered("Score:" + str(score),120, WHITE, DKGREY)
    show_centered("B4=RETRY",          148,  GREY,  DKGREY)
    show_centered("B3=MENU",           163,  GREY,  DKGREY)

    while True:
        if button4.value():
            utime.sleep_ms(300)
            return True
        if button3.value():
            utime.sleep_ms(300)
            return False
while True:
    restart = run_game()
    if not restart:
        break
