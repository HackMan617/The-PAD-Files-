#CONTROLS
#  --------
#  Joystick UP / DOWN  – navigate menu
#  Button 3 (GP1)      – select / launch game
#
#  From inside a game:
#  Button 4 (GP2)      – restart
#  Button 3 (GP1)      – return to this menu
#
# =============================================================

from machine import Pin, SPI, ADC, PWM
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
button3 = Pin(1, Pin.IN, Pin.PULL_DOWN)   
yAxis   = ADC(Pin(27))

# ── Colors ───────────────────────────────────────────────────
BLACK   = st7789.BLACK
WHITE   = st7789.WHITE
YELLOW  = st7789.color565(255, 215,   0)
GREEN   = st7789.color565(  0, 200,   0)
GREY    = st7789.color565(100, 100, 100)
DKGREY  = st7789.color565( 40,  40,  40)
RED     = st7789.color565(220,  50,  50)
BLUE    = st7789.color565( 50, 100, 220)
CYAN    = st7789.color565( 80, 200, 255)
ORANGE  = st7789.color565(230, 120,  30)
PURPLE  = st7789.color565(160,   0, 200)

SW, SH = 240, 240

# ── Game list ─────────────────────────────────────────────────
GAMES = [
    {"name": "Snake",   "file": "snake.py",  "color": GREEN,  "status": "ready"},
    {"name": "Flappy",  "file": "flappy.py", "color": CYAN,   "status": "ready"},
    {"name": "Tetris",  "file": "tetris.py", "color": PURPLE, "status": "ready"},
    {"name": "Pac-Man", "file": "pacman.py", "color": YELLOW, "status": "soon"},
    {"name": "Mario",   "file": "mario.py",  "color": RED,    "status": "soon"},
]

# ── Layout constants ──────────────────────────────────────────
CARD_H      = 46
CARD_W      = 200
CARD_X      = 20
TITLE_H     = 48
FOOTER_H    = 18
CARD_GAP    = 6
MAX_VISIBLE = (SH - TITLE_H - FOOTER_H) // (CARD_H + CARD_GAP)  # = 3

# ── Drawing helpers ───────────────────────────────────────────
def show_centered(text, y, color=WHITE, bg=BLACK):
    x = max(0, (SW - len(text) * 16) // 2)
    display.text(font2, text, x, y, color, bg)

def draw_card(draw_y, game, selected):
    is_ready = game["status"] == "ready"
    bg       = DKGREY if selected else BLACK
    accent   = game["color"] if is_ready else GREY
    border   = WHITE  if selected else GREY

    display.fill_rect(CARD_X, draw_y, CARD_W, CARD_H, bg)
    display.fill_rect(CARD_X, draw_y, 6,      CARD_H, accent)
    display.rect(CARD_X,      draw_y, CARD_W, CARD_H, border)

    name_col = WHITE if is_ready else GREY
    display.text(font2, game["name"], CARD_X + 14, draw_y + 8,  name_col, bg)

    if not is_ready:
        display.text(font2, "SOON",    CARD_X + 14, draw_y + 26, GREY,   bg)
    elif selected:
        display.text(font2, "B3=PLAY", CARD_X + 14, draw_y + 26, YELLOW, bg)
    else:
        display.text(font2, "READY",   CARD_X + 14, draw_y + 26, GREEN,  bg)

def draw_scroll_arrows(scroll_top, total):
    if scroll_top > 0:
        display.text(font2, "^", SW - 18, TITLE_H + 2,        WHITE, BLACK)
    else:
        display.fill_rect(SW - 18, TITLE_H + 2, 16, 16,        BLACK)

    if scroll_top + MAX_VISIBLE < total:
        display.text(font2, "v", SW - 18, SH - FOOTER_H - 20, WHITE, BLACK)
    else:
        display.fill_rect(SW - 18, SH - FOOTER_H - 20, 16, 16, BLACK)

def draw_menu(selected, scroll_top):
    display.fill(BLACK)

    #Title bar
    display.fill_rect(0, 0, SW, TITLE_H, BLUE)
    show_centered("GAME SELECT", 4,  WHITE, BLUE)
    show_centered("v1.2",        26, GREY,  BLUE)

    #Cards
    for i in range(MAX_VISIBLE):
        game_idx = scroll_top + i
        if game_idx >= len(GAMES):
            break
        card_y = TITLE_H + i * (CARD_H + CARD_GAP)
        draw_card(card_y, GAMES[game_idx], game_idx == selected)

    draw_scroll_arrows(scroll_top, len(GAMES))

    #Footer
    display.fill_rect(0, SH - FOOTER_H, SW, FOOTER_H, DKGREY)
    show_centered("UP/DN=MOVE  B3=SELECT", SH - FOOTER_H + 2, GREY, DKGREY)

# ── Launch a game ─────────────────────────────────────────────
def launch(filename):
    try:
        with open(filename) as f:
            code = f.read()
        exec(code, {"__name__": "__main__"})
    except OSError:
        display.fill(BLACK)
        show_centered("FILE NOT", 80,  RED)
        show_centered("FOUND!",  110,  RED)
        show_centered(filename,  145,  GREY)
        utime.sleep_ms(2000)

# ── Joystick debounce ─────────────────────────────────────────
_last_joy_move = 0
JOY_DELAY = 220

def joy_direction():
    global _last_joy_move
    now = utime.ticks_ms()
    if utime.ticks_diff(now, _last_joy_move) < JOY_DELAY:
        return 0
    yv = yAxis.read_u16()
    if yv <= 600:
        _last_joy_move = now
        return -1
    elif yv >= 60000:
        _last_joy_move = now
        return 1
    return 0

# ── Main menu loop ────────────────────────────────────────────
def menu_loop():
    selected   = 0
    scroll_top = 0
    b3_was_low = False

    draw_menu(selected, scroll_top)

    while True:
        d = joy_direction()
        if d != 0:
            selected = (selected + d) % len(GAMES)
            if selected < scroll_top:
                scroll_top = selected
            elif selected >= scroll_top + MAX_VISIBLE:
                scroll_top = selected - MAX_VISIBLE + 1
            draw_menu(selected, scroll_top)

        b3_now = button3.value()
        if b3_now and not b3_was_low:
            if GAMES[selected]["status"] == "ready":
                #Flash card
                for _ in range(3):
                    card_y = TITLE_H + (selected - scroll_top) * (CARD_H + CARD_GAP)
                    display.fill_rect(CARD_X, card_y, CARD_W, CARD_H,
                                      GAMES[selected]["color"])
                    utime.sleep_ms(80)
                    draw_card(card_y, GAMES[selected], True)
                    utime.sleep_ms(80)
                utime.sleep_ms(100)

                launch(GAMES[selected]["file"])
                draw_menu(selected, scroll_top)

        b3_was_low = not b3_now
        utime.sleep_ms(30)

# ── Entry point ───────────────────────────────────────────────
menu_loop()