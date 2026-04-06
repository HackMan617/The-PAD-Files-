#  CONTROLS
#  --------
#  Button 1 (GP4)  OR  Joystick UP  – flap
#  Button 3 (GP1)                   – return to menu
#  Button 4 (GP2)                   – restart after death
#
#  RENDERING STRATEGY  (no full-screen clears, no flash)
#  ------------------------------------------------------
#  The sky background is drawn ONCE at game start and never
#  cleared again. Each frame only touches pixels that changed:
#
#  PIPES  – When a pipe moves N pixels left, only the N-pixel
#           column vacated on its RIGHT edge is filled with sky.
#           The pipe body is then redrawn at its new x. The left
#           edge never needs clearing because the pipe always
#           moves left — it draws over itself.
#
#  BIRD   – The previous bird bounding box is filled with sky
#           (or pipe colour if the bird is passing through one).
#           The new bird is drawn on top. Only ~18×14 pixels
#           are touched rather than the whole screen.
#
#  GROUND – Drawn once; never touched again (bird can't go there
#           without dying).
#
#  SCORE  – Redrawn in-place each time it changes. The old digits
#           are overwritten because the background colour matches.
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
button  = Pin(4, Pin.IN, Pin.PULL_DOWN)
button2 = Pin(5, Pin.IN, Pin.PULL_DOWN)
button3 = Pin(1, Pin.IN, Pin.PULL_DOWN)
button4 = Pin(2, Pin.IN, Pin.PULL_DOWN)
xAxis   = ADC(Pin(26))
yAxis   = ADC(Pin(27))

#Buzzer
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
SKY      = st7789.color565(100, 190, 255)
GROUND_T = st7789.color565( 80, 190,  50)
GROUND_B = st7789.color565(140,  90,  30)
PIPE_COL = st7789.color565( 60, 170,  60)
PIPE_CAP = st7789.color565( 40, 130,  40)
PIPE_LT  = st7789.color565(100, 210, 100)
YELLOW   = st7789.color565(255, 215,   0)
ORANGE   = st7789.color565(230, 120,  30)
WHITE2   = st7789.color565(240, 240, 240)
RED      = st7789.color565(220,  50,  50)
GREY     = st7789.color565(150, 150, 150)
DKGREY   = st7789.color565( 40,  40,  40)

#Constants
SW, SH        = 240, 240
GRAVITY       =  0.45
FLAP_V        = -6.0
MAX_FALL      =  8.0
BIRD_X        =  50
BIRD_W        =  16
BIRD_H        =  13
PIPE_W        =  26
PIPE_GAP      =  72
PIPE_SPEED    =  2           #integer pixels per tick — avoids float rounding drift
PIPE_INTERVAL =  90
GROUND_H      =  20
PLAY_H        =  SH - GROUND_H 
CAP_H         =  7

#One-time background draw
def draw_background():
    display.fill_rect(0, 0,       SW, PLAY_H,       SKY)
    display.fill_rect(0, PLAY_H,  SW, 4,             GROUND_T)
    display.fill_rect(0, PLAY_H + 4, SW, GROUND_H - 4, GROUND_B)

#Pipe drawing primitives
def _pipe_col_sky(x, w):
    if x < SW and w > 0:
        display.fill_rect(max(0, x), 0, min(w, SW - x), PLAY_H, SKY)

def _draw_pipe_body(px, gap_y):
    #Top pipe
    if gap_y > 0:
        body_h = max(0, gap_y - CAP_H)
        if body_h > 0:
            display.fill_rect(px,     0,      PIPE_W,     body_h, PIPE_COL)
            display.vline(px + 2, 0, body_h, PIPE_LT)
        cap_y = max(0, gap_y - CAP_H)
        display.fill_rect(px, cap_y, PIPE_W, gap_y - cap_y, PIPE_CAP)

    #Gap/sky
    display.fill_rect(px, gap_y, PIPE_W, PIPE_GAP, SKY)

    #Bottom pipe
    bot_y = gap_y + PIPE_GAP
    bot_h = PLAY_H - bot_y
    if bot_h > 0:
        display.fill_rect(px, bot_y, PIPE_W, min(CAP_H, bot_h), PIPE_CAP)
        body_below = bot_h - CAP_H
        if body_below > 0:
            display.fill_rect(px, bot_y + CAP_H, PIPE_W, body_below, PIPE_COL)
            display.vline(px + 2, bot_y + CAP_H, body_below, PIPE_LT)

#Pipe update
def update_pipe(pipe):
    old_px = pipe[0]
    new_px = old_px - PIPE_SPEED
    pipe[0] = new_px

    if new_px + PIPE_W <= 0:
        _pipe_col_sky(0, PIPE_W)
        return False

    #Erase only the strip the pipe moved away from (right edge)
    vacated_x = new_px + PIPE_W
    if vacated_x < SW:
        _pipe_col_sky(vacated_x, PIPE_SPEED)

    #Redraw pipe at new position (clip to screen)
    draw_x = max(0, new_px)
    _draw_pipe_body(draw_x, pipe[1])
    return True

#Bird
def _bird_bg_color(bird_y, pipes):
    bx1 = BIRD_X
    bx2 = BIRD_X + BIRD_W
    by1 = int(bird_y)
    by2 = by1 + BIRD_H

    for px, gap_y, _ in pipes:
        if bx2 > px and bx1 < px + PIPE_W:
            #Bird x overlaps this pipe — fill with sky over gap, pipe colour elsewhere
            #Use sky as a safe default (the pipe will be redrawn anyway)
            return SKY
    return SKY

def erase_bird(old_y, pipes):
    by  = int(old_y)
    bx  = BIRD_X
    bw  = BIRD_W + 2
    bh  = BIRD_H + 2

    #Check if the bird position overlaps any pipe
    pipe_hit = None
    for p in pipes:
        px = p[0]
        if bx + bw > px and bx < px + PIPE_W:
            pipe_hit = p
            break

    if pipe_hit is None:
        display.fill_rect(bx, by, bw, bh, SKY)
    else:
        #Repaint the pipe columns the bird box overlaps so we don't leave a sky rectangle punched into the pipe
        px, gap_y, _ = pipe_hit
        display.fill_rect(bx, by, bw, bh, SKY)
        _draw_pipe_body(int(px), gap_y)

def draw_bird(y, vy):
    bx = BIRD_X
    by = int(y)
    #Body
    display.fill_rect(bx + 2, by + 2,  12, 8, YELLOW)
    display.fill_rect(bx + 1, by + 4,  14, 5, YELLOW)
    #Wing — up when rising, down when falling
    wing_y = by + 1 if vy < 0 else by + 7
    display.fill_rect(bx + 3, wing_y,   6, 3, WHITE2)
    #Eye
    display.fill_rect(bx + 9,  by + 3,  4, 4, WHITE2)
    display.fill_rect(bx + 10, by + 4,  2, 2, BLACK)
    #Beak
    display.fill_rect(bx + 13, by + 5,  4, 3, ORANGE)

#Score HUD
_last_score_w = 16   

def draw_score(score):
    global _last_score_w
    s   = str(score)
    sw  = len(s) * 16
    x   = (SW - sw) // 2
    #Erase previous score area (max 3 digits = 48px wide, centred)
    erase_x = (SW - _last_score_w) // 2
    display.fill_rect(erase_x, 4, _last_score_w, 16, SKY)
    display.text(font2, s, x, 4, WHITE, SKY)
    _last_score_w = sw

#Collision
def check_collision(bird_y, pipes):
    by1 = int(bird_y) + 1
    by2 = int(bird_y) + BIRD_H - 1
    bx1 = BIRD_X + 2
    bx2 = BIRD_X + BIRD_W - 2

    if by2 >= PLAY_H or by1 <= 0:
        return True

    for px, gap_y, _ in pipes:
        if bx2 > px and bx1 < px + PIPE_W:
            if by1 < gap_y or by2 > gap_y + PIPE_GAP:
                return True
    return False

#Helpers
def show_centered(text, y, color=WHITE, bg=BLACK):
    x = max(0, (SW - len(text) * 16) // 2)
    display.text(font2, text, x, y, color, bg)

#Main game
def run_game():
    import urandom
    global _last_score_w
    _last_score_w = 16

    bird_y  = float(PLAY_H // 2 - BIRD_H // 2)
    bird_vy = 0.0
    score   = 0
    tick    = 0
    pipes   = []          
    btn_was_low = True

    #Draw background once — never clear again
    draw_background()
    draw_bird(bird_y, 0)
    draw_score(0)

    show_centered("FLAPPY BIRD",  PLAY_H // 2 - 32, WHITE, SKY)
    show_centered("TAP TO START", PLAY_H // 2 - 10, WHITE, SKY)
    show_centered("B3 = MENU",    PLAY_H // 2 + 12, GREY,  SKY)

    while True:
        yv = yAxis.read_u16()
        if button.value() or yv <= 600:
            break
        if button3.value():
            return False
        utime.sleep_ms(30)

    #Clear the prompt text without blanking the whole screen
    display.fill_rect(0, PLAY_H // 2 - 36, SW, 60, SKY)
    draw_bird(bird_y, 0)
    draw_score(score)

    #Game loop
    while True:

        if button3.value():
            buzzer.duty_u16(0)
            utime.sleep_ms(300)
            return False

        #Flap input (rising edge)
        yv       = yAxis.read_u16()
        flap_now = button.value() or yv <= 600
        if flap_now and btn_was_low:
            bird_vy     = FLAP_V
            btn_was_low = False
            snd_flap()
        if not flap_now:
            btn_was_low = True

        bird_vy = min(bird_vy + GRAVITY, MAX_FALL)
        old_y   = bird_y
        bird_y += bird_vy

        #Spawn pipe
        tick += 1
        if tick % PIPE_INTERVAL == 0:
            gap_y = urandom.randint(30, PLAY_H - PIPE_GAP - 30)
            pipes.append([SW, gap_y, False])

        #Move pipes
        #Pipes are moved BEFORE the bird is erased/drawn so that when we erase the bird we can correctly detect whether it overlaps a pipe at its NEW position.
        surviving = []
        for p in pipes:
            if update_pipe(p):
                surviving.append(p)
            #Score when pipe passes bird
            if not p[2] and p[0] + PIPE_W < BIRD_X:
                p[2] = True
                score += 1
                snd_score()
                draw_score(score)
        pipes = surviving

        erase_bird(old_y, pipes)
        draw_bird(bird_y, bird_vy)

        if check_collision(bird_y, pipes):
            break

        utime.sleep_ms(30)

    snd_death()
    buzzer.duty_u16(0)

    #Brief white flash without clearing the scene
    display.fill_rect(0, 0, SW, PLAY_H, WHITE)
    utime.sleep_ms(80)

    #Redraw scene cleanly at death position
    draw_background()
    for p in pipes:
        _draw_pipe_body(int(p[0]), p[1])
    draw_bird(bird_y, bird_vy)

    #Death overlay
    display.fill_rect(30,  88, 180, 80, DKGREY)
    display.rect(30,       88, 180, 80, WHITE)
    show_centered("DEAD!",               100, RED,   DKGREY)
    show_centered("Score:" + str(score), 122, WHITE, DKGREY)
    show_centered("B4 = RETRY",          144, GREY,  DKGREY)
    show_centered("B3 = MENU",           158, GREY,  DKGREY)

    while True:
        if button4.value():
            utime.sleep_ms(300)
            return True
        if button3.value():
            utime.sleep_ms(300)
            return False
while True:
    if not run_game():
        break
