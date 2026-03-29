from machine import Pin, SPI, ADC, PWM
import utime
import st7789py as st7789
from fonts import vga1_16x32 as font2
import urandom

# --- Display Setup ---
spi1 = SPI(1, baudrate=40000000, polarity=1)
display = st7789.ST7789(
    spi1, 240, 240,
    reset=Pin(12, Pin.OUT),
    dc=Pin(13, Pin.OUT),
    rotation=1)

# --- Buttons & Joystick ---
button  = Pin(4, Pin.IN, Pin.PULL_DOWN)
button2 = Pin(5, Pin.IN, Pin.PULL_DOWN)
button3 = Pin(1, Pin.IN, Pin.PULL_DOWN)   
button4 = Pin(2, Pin.IN, Pin.PULL_DOWN)  
xAxis   = ADC(Pin(26))
yAxis   = ADC(Pin(27))
jbutton = Pin(0, Pin.IN, Pin.PULL_UP) #PAUSE

buzzer = PWM(Pin(15))
buzzer.duty_u16(0)

# --- Non-blocking sound via Timer ---
from machine import Timer

_tone_seq   = []
_tone_timer = Timer()

def _next_tone(t):
    global _tone_seq
    if _tone_seq:
        freq, dur = _tone_seq.pop(0)
        buzzer.freq(freq)
        buzzer.duty_u16(2000)
        _tone_timer.init(mode=Timer.ONE_SHOT, period=dur, callback=_next_tone)
    else:
        buzzer.duty_u16(0)
        _tone_timer.deinit()

def play_sequence(notes):
    global _tone_seq
    _tone_seq = list(notes)
    _next_tone(None)

def play_collect():
    play_sequence([(523, 50), (659, 50), (784, 50), (1047, 50)])

def play_death():
    for freq in [400, 300, 200, 150, 100]:
        play_tone(freq, 120, duty=4000)

def play_tone(freq, duration_ms, duty=3000):
    buzzer.freq(freq)
    buzzer.duty_u16(duty)
    utime.sleep_ms(duration_ms)
    buzzer.duty_u16(0)

def play_bg_tick(score):
    freq = 220 + score * 8
    buzzer.freq(freq)
    buzzer.duty_u16(1500)
    utime.sleep_ms(18)
    buzzer.duty_u16(0)

#Game Constants
CELL   = 10
COLS   = 24
ROWS   = 24

BLACK   = st7789.BLACK
WHITE   = st7789.WHITE
GREEN   = st7789.color565(0, 200, 0)
DKGREEN = st7789.color565(0, 120, 0)
RED     = st7789.color565(220, 0, 0)
YELLOW  = st7789.color565(255, 215, 0)
GREY    = st7789.color565(150, 150, 150)

def cell_color(idx):
    return GREEN if idx % 2 == 0 else DKGREEN

def draw_cell(col, row, color):
    display.fill_rect(col * CELL, row * CELL, CELL - 1, CELL - 1, color)

def place_food(snake):
    while True:
        fc = urandom.randint(1, COLS - 2)
        fr = urandom.randint(1, ROWS - 2)
        if (fc, fr) not in snake:
            return (fc, fr)

def draw_border():
    GREY_B = st7789.color565(100, 100, 100)
    display.fill_rect(0,   0,   240, CELL, GREY_B)
    display.fill_rect(0,   230, 240, CELL, GREY_B)
    display.fill_rect(0,   0,   CELL, 240, GREY_B)
    display.fill_rect(230, 0,   CELL, 240, GREY_B)

def show_centered(text, y, color=WHITE, bg=BLACK):
    x = max(0, (240 - len(text) * 16) // 2)
    display.text(font2, text, x, y, color, bg)

def show_score_screen(score):
    display.fill(BLACK)
    show_centered("SCORE", 60, YELLOW)
    show_centered(str(score), 110, WHITE)
    show_centered("B4=RESTART", 160, GREY)
    utime.sleep(0.3)

#Returns True  = restart game; False = exit to menu
def run_game():
    display.fill(BLACK)
    draw_border()
    snake     = [(COLS//2 - i, ROWS//2) for i in range(3)]
    direction = (1, 0)
    food      = place_food(snake)
    score     = 0
    paused    = False
    game_over = False

    draw_cell(*food, RED)
    for i, seg in enumerate(snake):
        draw_cell(*seg, cell_color(i))

    while not game_over:

        #B3 pressed mid-game -> exit to menu immediately
        if button3.value():
            buzzer.duty_u16(0)
            utime.sleep_ms(300)
            return False

        #Pause toggle (joystick button)
        if not jbutton.value():
            paused = not paused
            buzzer.duty_u16(0)
            if paused:
                show_centered("PAUSED", 104, YELLOW)
            else:
                display.fill(BLACK)
                draw_border()
                draw_cell(*food, RED)
                for i, seg in enumerate(snake):
                    draw_cell(*seg, cell_color(i))
            utime.sleep(0.3)

        if paused:
            if button.value() or button2.value():
                show_score_screen(score)
                utime.sleep(0.5)
                display.fill(BLACK)
                show_centered("PAUSED", 104, YELLOW)
            utime.sleep(0.05)
            continue

        #Joystick
        xv = xAxis.read_u16()
        yv = yAxis.read_u16()
        dx, dy = direction
        if   xv <= 600   and dx == 0: direction = (-1,  0)
        elif xv >= 60000 and dx == 0: direction = ( 1,  0)
        elif yv <= 600   and dy == 0: direction = ( 0, -1)
        elif yv >= 60000 and dy == 0: direction = ( 0,  1)

        #Score display buttons
        if button.value() or button2.value():
            show_score_screen(score)
            utime.sleep(0.5)
            display.fill(BLACK)
            draw_cell(*food, RED)
            for i, seg in enumerate(snake):
                draw_cell(*seg, cell_color(i))

        #Move snake
        head = (snake[0][0] + direction[0], snake[0][1] + direction[1])

        if not (1 <= head[0] < COLS - 1 and 1 <= head[1] < ROWS - 1):
            game_over = True
            break
        if head in snake:
            game_over = True
            break

        snake.insert(0, head)

        if head == food:
            score += 1
            play_collect()
            food = place_food(snake)
            draw_cell(*food, RED)
        else:
            tail = snake.pop()
            draw_cell(*tail, BLACK)

        for i, seg in enumerate(snake):
            draw_cell(*seg, cell_color(i))

        utime.sleep_ms(100)

    #Game Over screen
    play_death()
    buzzer.duty_u16(0)
    display.fill(BLACK)
    show_centered("GAME OVER", 70, RED)
    show_centered("Score:" + str(score), 110, WHITE)
    show_centered("B4=RESTART", 150, GREY)
    show_centered("B3=MENU",    175, GREY)

    while True:
        if button4.value():
            utime.sleep_ms(300)
            return True   
        if button3.value():
            utime.sleep_ms(300)
            return False   

#Game loop (called by launcher)
#Keeps restarting until B3 is pressed, then returns to launcher.
while True:
    restart = run_game()
    if not restart:
        break   #fall back to menu_loop() in main.py