import machine
import time
import st7789py as st7789
import vga1_16x32 as font
from machine import ADC

# --- Pin Configuration ---
CS_PIN  = machine.Pin(5,  machine.Pin.OUT)
DC_PIN  = machine.Pin(6,  machine.Pin.OUT)
RST_PIN = machine.Pin(7,  machine.Pin.OUT)
BL_PIN  = machine.Pin(8,  machine.Pin.OUT)
SPI_SCK = machine.Pin(2)
SPI_SDA = machine.Pin(3)

# --- Inputs ---
btn1    = machine.Pin(20, machine.Pin.IN, machine.Pin.PULL_UP)
btn2    = machine.Pin(21, machine.Pin.IN, machine.Pin.PULL_UP)
joy_sel = machine.Pin(22, machine.Pin.IN, machine.Pin.PULL_UP)
joy_x   = ADC(machine.Pin(26))
joy_y   = ADC(machine.Pin(27))

# --- LEDs ---
led1 = machine.Pin(14, machine.Pin.OUT)
led2 = machine.Pin(15, machine.Pin.OUT)
led1.value(0)
led2.value(0)

# --- Buzzer ---
buzzer = machine.PWM(machine.Pin(18))

# --- Display ---
BL_PIN.value(1)
spi = machine.SPI(0, baudrate=2_000_000, polarity=1, phase=1,
                  sck=SPI_SCK, mosi=SPI_SDA)
tft = st7789.ST7789(spi, 240, 240, reset=RST_PIN, dc=DC_PIN,
                    cs=CS_PIN, backlight=BL_PIN, rotation=1)

# --- Colors ---
BLACK  = st7789.BLACK
WHITE  = st7789.WHITE
RED    = st7789.color565(220, 30,  30)
GREEN  = st7789.color565(30,  180, 30)
BLUE   = st7789.color565(30,  80,  220)
YELLOW = st7789.color565(255, 220, 0)
ORANGE = st7789.color565(255, 140, 0)
PURPLE = st7789.color565(180, 30,  180)
GRAY   = st7789.color565(80,  80,  80)

FONT_W = font.WIDTH    # 16
FONT_H = font.HEIGHT   # 32

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------
def beep(freq=440, ms=80):
    buzzer.freq(freq)
    buzzer.duty_u16(32768)
    time.sleep_ms(ms)
    buzzer.duty_u16(0)

def startup_chime():
    beep(523, 100); time.sleep_ms(30)
    beep(659, 100); time.sleep_ms(30)
    beep(784, 150); time.sleep_ms(30)
    beep(1046, 200)

def pass_chime():
    beep(784, 80);  time.sleep_ms(20)
    beep(1046, 150)

def draw_centered(text, y, fg=WHITE, bg=BLACK):
    x = max(0, (240 - len(text) * FONT_W) // 2)
    tft.text(font, text, x, y, fg, bg)

def fill_screen(color, label, fg=WHITE):
    tft.fill(color)
    draw_centered(label, 104, fg, color)

def wait_release_all():
    """Wait until all buttons are released"""
    while btn1.value() == 0 or btn2.value() == 0 or joy_sel.value() == 0:
        time.sleep_ms(20)

def wait_btn1():
    while btn1.value() != 0: time.sleep_ms(20)
    while btn1.value() == 0: time.sleep_ms(20)

# ---------------------------------------------------
# STAGE 1 — DISPLAY FLASH TEST
# ---------------------------------------------------
def test_display():
    tft.fill(BLACK)
    draw_centered("DISPLAY", 88,  WHITE, BLACK)
    draw_centered("TEST",    120, WHITE, BLACK)
    time.sleep(1)

    colors = [
        (RED,    "RED",    WHITE),
        (GREEN,  "GREEN",  WHITE),
        (BLUE,   "BLUE",   WHITE),
        (YELLOW, "YELLOW", BLACK),
        (WHITE,  "WHITE",  BLACK),
    ]
    tones = [440, 523, 659, 784, 1046]

    for i, (color, label, fg) in enumerate(colors):
        fill_screen(color, label, fg)
        beep(tones[i], 120)
        time.sleep(0.6)

    tft.fill(BLACK)
    draw_centered("DISPLAY", 88,  GREEN, BLACK)
    draw_centered("PASS",    120, GREEN, BLACK)
    pass_chime()
    time.sleep(1)

# ---------------------------------------------------
# STAGE 2 — BUZZER TEST
# ---------------------------------------------------
def test_buzzer():
    tft.fill(BLACK)
    draw_centered("BUZZER",  88,  YELLOW, BLACK)
    draw_centered("TEST",    120, YELLOW, BLACK)
    time.sleep(0.5)

    notes = [262, 330, 392, 523, 659, 784, 1046, 1318]
    labels = ["C4","E4","G4","C5","E5","G5","C6","E6"]

    for i, (note, label) in enumerate(zip(notes, labels)):
        tft.fill(BLACK)
        draw_centered("NOTE",   88,  YELLOW, BLACK)
        draw_centered(label,    120, WHITE,  BLACK)
        beep(note, 200)
        time.sleep(0.1)

    tft.fill(BLACK)
    draw_centered("BUZZER",  88,  GREEN, BLACK)
    draw_centered("PASS",    120, GREEN, BLACK)
    pass_chime()
    time.sleep(1)

# ---------------------------------------------------
# STAGE 3 — BUTTON TEST
# ---------------------------------------------------
def test_buttons():
    # --- Button 1 ---
    tft.fill(BLACK)
    draw_centered("PRESS",   72,  WHITE,  BLACK)
    draw_centered("BTN 1",   104, YELLOW, BLACK)
    draw_centered("TO TEST", 136, GRAY,   BLACK)

    while btn1.value() != 0:
        time.sleep_ms(20)

    led1.value(1)
    tft.fill(GREEN)
    draw_centered("BTN 1",  88,  WHITE, GREEN)
    draw_centered("PASS",   120, WHITE, GREEN)
    beep(880, 100)
    time.sleep(0.8)
    led1.value(0)

    while btn1.value() == 0:
        time.sleep_ms(20)
    time.sleep_ms(200)

    # --- Button 2 ---
    tft.fill(BLACK)
    draw_centered("PRESS",   72,  WHITE,  BLACK)
    draw_centered("BTN 2",   104, YELLOW, BLACK)
    draw_centered("TO TEST", 136, GRAY,   BLACK)

    while btn2.value() != 0:
        time.sleep_ms(20)

    led2.value(1)
    tft.fill(GREEN)
    draw_centered("BTN 2",  88,  WHITE, GREEN)
    draw_centered("PASS",   120, WHITE, GREEN)
    beep(880, 100)
    time.sleep(0.8)
    led2.value(0)

    while btn2.value() == 0:
        time.sleep_ms(20)
    time.sleep_ms(200)

    # --- SEL Button ---
    tft.fill(BLACK)
    draw_centered("PRESS",   72,  WHITE,  BLACK)
    draw_centered("SEL",     104, YELLOW, BLACK)
    draw_centered("TO TEST", 136, GRAY,   BLACK)

    while joy_sel.value() != 0:
        time.sleep_ms(20)

    tft.fill(GREEN)
    draw_centered("SEL",    88,  WHITE, GREEN)
    draw_centered("PASS",   120, WHITE, GREEN)
    beep(880, 100)
    time.sleep(0.8)

    while joy_sel.value() == 0:
        time.sleep_ms(20)
    time.sleep_ms(200)

    tft.fill(BLACK)
    draw_centered("BUTTONS", 88,  GREEN, BLACK)
    draw_centered("PASS",    120, GREEN, BLACK)
    pass_chime()
    time.sleep(1)

# ---------------------------------------------------
# STAGE 4 — JOYSTICK TEST
# ---------------------------------------------------
def test_joystick():
    """
    Asks user to move joystick in all 4 directions.
    Each direction must be detected before moving on.
    Raw ADC values printed to serial for calibration.
    Deadzone is intentionally small here for testing.
    """
    DEADZONE  = 5000
    CENTER    = 32768

    def get_direction():
        x = joy_x.read_u16()
        y = joy_y.read_u16()
        dx = x - CENTER
        dy = y - CENTER
        if abs(dx) < DEADZONE and abs(dy) < DEADZONE:
            return "CENTER", x, y
        if abs(dx) >= abs(dy):
            return ("LEFT" if dx > 0 else "RIGHT"), x, y   # Flipped LEFT/RIGHT
        else:
            return ("UP"   if dy > 0 else "DOWN"),  x, y   # Flipped UP/DOWN

    directions_needed = ["UP", "DOWN", "LEFT", "RIGHT"]
    colors = {
        "UP"    : BLUE,
        "DOWN"  : RED,
        "LEFT"  : ORANGE,
        "RIGHT" : PURPLE,
        "CENTER": GRAY,
    }
    tones = {
        "UP"    : 659,
        "DOWN"  : 440,
        "LEFT"  : 523,
        "RIGHT" : 784,
    }

    for target in directions_needed:
        detected = False

        while not detected:
            direction, rx, ry = get_direction()

            # Update screen showing what direction is needed
            tft.fill(BLACK)
            draw_centered("MOVE",    56,  WHITE,  BLACK)
            draw_centered(target,    88,  YELLOW, BLACK)
            draw_centered("JOYSTICK",120, GRAY,   BLACK)

            # Show raw ADC values at bottom for debugging
            tft.text(font, f"X{rx:5}", 0,   192, GRAY, BLACK)
            tft.text(font, f"Y{ry:5}", 120, 192, GRAY, BLACK)

            print(f"Waiting for {target} | X={rx} Y={ry} | "
                  f"Direction={direction}")

            if direction == target:
                detected = True
                bg = colors[target]
                tft.fill(bg)
                draw_centered(target, 88,  WHITE, bg)
                draw_centered("PASS", 120, WHITE, bg)
                beep(tones[target], 150)
                time.sleep(0.8)

            time.sleep_ms(100)

    tft.fill(BLACK)
    draw_centered("JOYSTICK", 88,  GREEN, BLACK)
    draw_centered("PASS",     120, GREEN, BLACK)
    pass_chime()
    time.sleep(1)

# ---------------------------------------------------
# STAGE 5 — ALL PASS SCREEN
# ---------------------------------------------------
def show_all_pass():
    tft.fill(BLACK)
    draw_centered("ALL",     56,  GREEN,  BLACK)
    draw_centered("TESTS",   88,  GREEN,  BLACK)
    draw_centered("PASSED",  120, GREEN,  BLACK)
    draw_centered("THE PAD", 168, YELLOW, BLACK)

    # Victory chime
    notes = [523, 659, 784, 1046, 784, 1046]
    for note in notes:
        beep(note, 100)
        time.sleep_ms(30)

    led1.value(1)
    led2.value(1)
    time.sleep(2)
    led1.value(0)
    led2.value(0)

# ---------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------
print("THE PAD - IO TEST")
print("=================")

# Startup
tft.fill(BLACK)
draw_centered("THE PAD",  72,  YELLOW, BLACK)
draw_centered("IO TEST",  120, WHITE,  BLACK)
startup_chime()
time.sleep(1)

tft.fill(BLACK)
draw_centered("PRESS",   88,  WHITE, BLACK)
draw_centered("BTN 1",   120, GRAY,  BLACK)
wait_btn1()

# Run all stages
print("\n--- STAGE 1: DISPLAY ---")
test_display()

print("\n--- STAGE 2: BUZZER ---")
test_buzzer()

print("\n--- STAGE 3: BUTTONS ---")
test_buttons()

print("\n--- STAGE 4: JOYSTICK ---")
test_joystick()

print("\n--- ALL TESTS COMPLETE ---")
show_all_pass()
