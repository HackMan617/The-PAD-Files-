#  CONTROLS
#  --------
#  Button 1 (GP4)  OR  Joystick UP  – flap
#  Button 3 (GP1)                   – return to menu
#  Button 4 (GP2)                   – restart after death
#
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
button  = Pin(4, Pin.IN, Pin.PULL_DOWN)   # flap
button2 = Pin(5, Pin.IN, Pin.PULL_DOWN)
button3 = Pin(1, Pin.IN, Pin.PULL_DOWN)   # menu
button4 = Pin(2, Pin.IN, Pin.PULL_DOWN)   # restart
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

# ── Colors ───────────────────────────────────────────────────
BLACK    = st7789.BLACK
WHITE    = st7789.WHITE
SKY      = st7789.color565( 80, 180, 255)
GROUND_T = st7789.color565( 90, 200,  50)   # grass top
GROUND_B = st7789.color565(150, 100,  40)   # dirt
PIPE_G   = st7789.color565( 50, 180,  50)
PIPE_DK  = st7789.color565( 30, 130,  30)
PIPE_LT  = st7789.color565(120, 220, 120)
YELLOW   = st7789.color565(255, 215,   0)
RED      = st7789.color565(220,  50,  50)
GREY     = st7789.color565(150, 150, 150)
DKGREY   = st7789.color565( 40,  40,  40)
ORANGE   = st7789.color565(230, 120,  30)
WHITE2   = st7789.color565(240, 240, 240)

# ── Screen & game constants ───────────────────────────────────
SW, SH     = 240, 240

GRAVITY    =  0.45
FLAP_V     = -6.0
MAX_FALL   =  8.0
BIRD_X     =  55          #fixed horizontal position
BIRD_W     =  17
BIRD_H     =  13

PIPE_W        = 28
PIPE_GAP      = 70        #vertical gap between top/bottom pipe
PIPE_SPEED    = 2.5
PIPE_INTERVAL = 90        #ticks between new pipes

GROUND_H   = 20           #height of ground strip at bottom
CEILING    =  0           #top boundary

# ── Bird sprite ───────────────────────────────────────────────
def draw_bird(x, y, vel):
    """Draw the bird. Wing position based on velocity."""
    bx, by = int(x), int(y)
    #Body
    display.fill_rect(bx + 2, by + 3, 13, 8,  YELLOW)
    display.fill_rect(bx + 1, by + 4, 15, 6,  YELLOW)
    #Wing (up when flapping, down when falling)
    wing_y = by + 2 if vel < 0 else by + 7
    display.fill_rect(bx + 4, wing_y, 7, 3, WHITE2)
    #Eye
    display.fill_rect(bx + 10, by + 4, 4, 4, WHITE2)
    display.fill_rect(bx + 11, by + 5, 2, 2, BLACK)
    #Beak
    display.fill_rect(bx + 14, by + 6, 4, 3, ORANGE)
    display.fill_rect(bx + 15, by + 7, 3, 2, ORANGE)

def erase_bird(x, y):
    bx, by = int(x), int(y)
    display.fill_rect(bx, by, BIRD_W + 2, BIRD_H + 2, SKY)

# ── Pipe drawing ──────────────────────────────────────────────
def draw_pipe(px, gap_y):
    ipx = int(px)

    #Top pipe body
    top_bot = gap_y
    if top_bot > 0:
        display.fill_rect(ipx + 2, 0,          PIPE_W - 4, top_bot,     PIPE_G)
        display.vline(ipx + 2,     0,           top_bot,                 PIPE_DK)
        display.vline(ipx + PIPE_W - 3, 0,      top_bot,                 PIPE_LT)
        #Cap
        cap_y = max(0, top_bot - 6)
        display.fill_rect(ipx,     cap_y,       PIPE_W,     6,           PIPE_G)
        display.hline(ipx,         cap_y,       PIPE_W,                  PIPE_LT)
        display.hline(ipx,         top_bot - 1, PIPE_W,                  PIPE_DK)

    #Bottom pipe body
    bot_top = gap_y + PIPE_GAP
    bot_h   = SH - GROUND_H - bot_top
    if bot_h > 0:
        display.fill_rect(ipx + 2, bot_top + 6, PIPE_W - 4, bot_h - 6,  PIPE_G)
        display.vline(ipx + 2,     bot_top + 6, bot_h - 6,               PIPE_DK)
        display.vline(ipx + PIPE_W - 3, bot_top + 6, bot_h - 6,          PIPE_LT)
        #Cap
        display.fill_rect(ipx,     bot_top,     PIPE_W,     6,           PIPE_G)
        display.hline(ipx,         bot_top,     PIPE_W,                  PIPE_LT)
        display.hline(ipx,         bot_top + 5, PIPE_W,                  PIPE_DK)

def erase_pipe(px, gap_y):
    ipx = int(px)
    display.fill_rect(ipx, 0, PIPE_W, SH - GROUND_H, SKY)

# ── Ground strip ──────────────────────────────────────────────
def draw_ground():
    y = SH - GROUND_H
    display.fill_rect(0, y,     SW, 4,            GROUND_T)
    display.fill_rect(0, y + 4, SW, GROUND_H - 4, GROUND_B)

# ── Scrolling ground offset dots ─────────────────────────────
_ground_offset = 0

def draw_ground_scroll(offset):
    y = SH - GROUND_H
    display.fill_rect(0, y + 4, SW, GROUND_H - 4, GROUND_B)
    for i in range(0, SW, 20):
        dx = (i + offset) % SW
        display.fill_rect(dx, y + 6, 8, 3, GROUND_T)

# ── HUD ───────────────────────────────────────────────────────
def draw_score_hud(score):
    #Transparent overlay — just write score digits in top center
    s = str(score)
    x = (SW - len(s) * 16) // 2
    display.text(font2, s, x, 6, WHITE, SKY)

# ── Collision ─────────────────────────────────────────────────
def check_collision(bird_x, bird_y, pipes):
    bx1 = bird_x + 2
    bx2 = bird_x + BIRD_W - 2
    by1 = bird_y + 1
    by2 = bird_y + BIRD_H - 1

    #Ground / ceiling
    if by2 >= SH - GROUND_H:
        return True
    if by1 <= CEILING:
        return True

    for px, gap_y, _ in pipes:
        px2 = px + PIPE_W
        if bx2 > px + 2 and bx1 < px2 - 2:
            if by1 < gap_y or by2 > gap_y + PIPE_GAP:
                return True
    return False

# ── Full background redraw ────────────────────────────────────
def draw_bg():
    display.fill(SKY)
    draw_ground()

# ── Show centred text ─────────────────────────────────────────
def show_centered(text, y, color=WHITE, bg=BLACK):
    x = max(0, (SW - len(text) * 16) // 2)
    display.text(font2, text, x, y, color, bg)

# ── Run one game session ──────────────────────────────────────
def run_game():
    import urandom

    bird_y   = float(SH // 2 - BIRD_H // 2)
    bird_vy  = 0.0
    score    = 0
    tick     = 0
    dead     = False

    #pipes: list of [x, gap_y, scored]
    pipes = []

    #Input edge detection
    btn_was_low  = True    #B1 released state
    joy_was_mid  = True    #joystick not up

    draw_bg()
    draw_bird(BIRD_X, bird_y, bird_vy)
    draw_score_hud(score)

    # ── Wait for first flap to start ─────────────────────────
    show_centered("TAP TO START", SH // 2 - 8, WHITE, SKY)
    show_centered("B3=MENU",      SH // 2 + 20, GREY,  SKY)

    while True:
        yv      = yAxis.read_u16()
        flap_now = button.value() or yv <= 600
        if flap_now:
            break
        if button3.value():
            return False   #straight to menu
        utime.sleep_ms(30)

    display.fill_rect(0, SH // 2 - 12, SW, 50, SKY) #Tap to Start Text

    # ── Main game loop ────────────────────────────────────────
    while not dead:

        # B3 - menu at any time
        if button3.value():
            buzzer.duty_u16(0)
            utime.sleep_ms(300)
            return False

        # ── Flap input (edge detect) ──────────────────────────
        yv       = yAxis.read_u16()
        flap_now = button.value() or yv <= 600

        if flap_now and btn_was_low:
            bird_vy  = FLAP_V
            btn_was_low = False
            snd_flap()
        if not flap_now:
            btn_was_low = True

        # ── Physics ───────────────────────────────────────────
        bird_vy = min(bird_vy + GRAVITY, MAX_FALL)
        old_y   = bird_y
        bird_y += bird_vy

        # ── Spawn pipes ───────────────────────────────────────
        tick += 1
        if tick % PIPE_INTERVAL == 0:
            gap_y = urandom.randint(30, SH - GROUND_H - PIPE_GAP - 30)
            pipes.append([float(SW), gap_y, False])

        # ── Move & draw pipes ─────────────────────────────────
        pipes_to_remove = []
        for i, pipe in enumerate(pipes):
            old_px = int(pipe[0])
            pipe[0] -= PIPE_SPEED
            new_px  = int(pipe[0])

            if new_px + PIPE_W < 0:
                pipes_to_remove.append(i)
                continue

            #Erase old position, draw new
            if old_px != new_px:
                erase_pipe(old_px, pipe[1])
                draw_pipe(new_px, pipe[1])

            #Score when pipe passes bird
            if not pipe[2] and pipe[0] + PIPE_W < BIRD_X:
                pipe[2] = True
                score  += 1
                snd_score()

        for i in reversed(pipes_to_remove):
            pipes.pop(i)

        # ── Erase & redraw bird ───────────────────────────────
        erase_bird(BIRD_X, old_y)
        #Restore sky behind bird in case pipe overlapped
        # (pipes are drawn first so bird appears on top)
        draw_bird(BIRD_X, bird_y, bird_vy)

        # ── Scrolling ground ──────────────────────────────────
        global _ground_offset
        _ground_offset = (_ground_offset + int(PIPE_SPEED)) % SW
        draw_ground_scroll(_ground_offset)

        # ── Score HUD ─────────────────────────────────────────
        draw_score_hud(score)

        # ── Collision check ───────────────────────────────────
        if check_collision(BIRD_X, bird_y, pipes):
            dead = True
            break

        utime.sleep_ms(30)   # ~33 fps

    # ── Death ─────────────────────────────────────────────────
    snd_death()
    buzzer.duty_u16(0)

    #Brief flash
    display.fill(WHITE)
    utime.sleep_ms(120)
    draw_bg()
    for p in pipes:
        draw_pipe(int(p[0]), p[1])
    draw_bird(BIRD_X, bird_y, bird_vy)
    draw_ground()

    #Death overlay
    display.fill_rect(30, 80, 180, 90, DKGREY)
    display.rect(30, 80, 180, 90, WHITE)
    show_centered("DEAD!",      95,  RED,    DKGREY)
    show_centered("Score:" + str(score), 120, WHITE,  DKGREY)
    show_centered("B4=RETRY",  148,  GREY,   DKGREY)
    show_centered("B3=MENU",   163,  GREY,   DKGREY)

    while True:
        if button4.value():
            utime.sleep_ms(300)
            return True    
        if button3.value():
            utime.sleep_ms(300)
            return False 

# ── Game entry point (called via exec from main.py) ──────────
while True:
    restart = run_game()
    if not restart:
        break