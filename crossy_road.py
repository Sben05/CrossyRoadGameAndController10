import pgzrun
import random
import math

try:
    import serial
    import serial.tools.list_ports
    HAVE_SERIAL = True
except ImportError:
    HAVE_SERIAL = False

TILE = 60
COLS = 11
WIDTH = COLS * TILE
HEIGHT = 660
TITLE = "CROSSY ROAD"

PLAYER_COL = COLS // 2
PLAYER_X = PLAYER_COL * TILE + TILE / 2
PLAYER_SCREEN_Y = HEIGHT - TILE * 3

CARW = TILE * 1.15
CARH = TILE * 0.66


def connect_pico():
    if not HAVE_SERIAL:
        return None
    try:
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            vid_ok = (p.vid == 0x2E8A)
            name_ok = ("pico" in desc) or ("usb serial" in desc) or ("uart" in desc)
            if vid_ok or name_ok:
                return serial.Serial(p.device, 115200, timeout=0)
    except Exception as e:
        print("Serial scan failed:", e)
    return None


pico = connect_pico()
if pico:
    print("Connected to Pico on", pico.port)
else:
    print("No Pico found -- using SPACE key.")

pico_alive = False

STATE_TITLE = 0
STATE_PLAY = 1
STATE_DEAD = 2

state = STATE_TITLE
clock = 0.0
dead_timer = 0.0
best_score = 0

GRASS_A = (108, 196, 92)
GRASS_B = (96, 182, 80)
ROAD_A = (66, 66, 74)
ROAD_B = (58, 58, 66)
CAR_COLORS = [(232, 64, 64), (66, 140, 240), (250, 190, 40),
              (170, 80, 230), (40, 200, 160), (250, 130, 50)]

rows = {}
max_row = 0
cam = 0.0

player_row = 0
player_disp = 0.0
hop_from = 0.0
hop_t = 1.0
HOP_TIME = 0.11

floor_row = 0
floor_timer = 0.0

score = 0
particles = []


def make_row(n):
    if n < 3:
        rows[n] = {"type": "grass"}
        return
    prev_roads = 0
    k = n - 1
    while k in rows and rows[k]["type"] == "road":
        prev_roads += 1
        k -= 1
    is_road = random.random() < 0.62 and prev_roads < 3
    if not is_road:
        rows[n] = {"type": "grass"}
        return
    direction = random.choice([-1, 1])
    speed = random.uniform(90, 190) + n * 1.5
    ncars = random.randint(2, 3)
    span = WIDTH + 240
    gap = span / ncars
    start = random.uniform(0, gap)
    cars = [start + i * gap - 120 for i in range(ncars)]
    color = random.choice(CAR_COLORS)
    rows[n] = {"type": "road", "dir": direction, "speed": speed,
               "cars": cars, "span": span, "color": color}


def ensure_rows(up_to):
    global max_row
    while max_row <= up_to:
        max_row += 1
        make_row(max_row)


def reset_game():
    global rows, max_row, cam, player_row, player_disp, hop_from, hop_t
    global floor_row, floor_timer, score, particles
    rows = {}
    max_row = -1
    cam = 0.0
    player_row = 0
    player_disp = 0.0
    hop_from = 0.0
    hop_t = 1.0
    floor_row = -6
    floor_timer = 0.0
    score = 0
    particles = []
    ensure_rows(20)


def burst(x, y, color, n=16):
    for _ in range(n):
        ang = random.uniform(0, 6.283)
        sp = random.uniform(40, 260)
        particles.append([x, y, math.cos(ang) * sp, math.sin(ang) * sp,
                          random.uniform(0.3, 0.8), color])


def hop():
    global player_row, hop_from, hop_t, score
    if hop_t < 1.0:
        return
    hop_from = player_disp
    player_row += 1
    hop_t = 0.0
    ensure_rows(player_row + 20)
    if player_row > score:
        score = player_row


def do_press():
    global state, dead_timer
    if state == STATE_TITLE:
        reset_game()
        state = STATE_PLAY
    elif state == STATE_PLAY:
        hop()
    elif state == STATE_DEAD:
        if dead_timer <= 0:
            reset_game()
            state = STATE_PLAY


def poll_serial():
    global pico_alive
    if not pico:
        return
    try:
        n = pico.in_waiting
        if n:
            data = pico.read(n).decode("utf-8", "ignore")
            for ch in data:
                if ch in "PRH":
                    pico_alive = True
                if ch == "P":
                    do_press()
    except Exception as e:
        print("Serial read error:", e)


def on_key_down(key):
    if key == keys.SPACE or key == keys.UP:
        do_press()


def die():
    global state, best_score, dead_timer
    state = STATE_DEAD
    best_score = max(best_score, score)
    dead_timer = 0.6
    burst(PLAYER_X, PLAYER_SCREEN_Y - (player_disp - cam) * TILE, (255, 255, 255), 30)


def screen_y(r):
    return PLAYER_SCREEN_Y - (r - cam) * TILE


def update(dt):
    global clock, cam, player_disp, hop_t, floor_row, floor_timer, state, dead_timer

    dt = min(dt, 0.033)
    clock += dt
    poll_serial()

    for p in particles:
        p[0] += p[2] * dt
        p[1] += p[3] * dt
        p[3] += 500 * dt
        p[4] -= dt
    particles[:] = [p for p in particles if p[4] > 0]

    if state != STATE_PLAY:
        if dead_timer > 0:
            dead_timer -= dt
        cam += (player_disp - cam) * min(1.0, dt * 8)
        return

    if hop_t < 1.0:
        hop_t = min(1.0, hop_t + dt / HOP_TIME)
        player_disp = hop_from + (player_row - hop_from) * (hop_t * (2 - hop_t))
    else:
        player_disp = player_row

    cam += (player_disp - cam) * min(1.0, dt * 9)

    floor_timer += dt
    creep = 0.45 + score * 0.012
    floor_row += creep * dt
    if floor_row > player_disp - 0.05:
        return die()

    lo = int(cam) - 3
    hi = int(cam) + 14
    for r in range(lo, hi):
        row = rows.get(r)
        if not row or row["type"] != "road":
            continue
        span = row["span"]
        d = row["dir"]
        for i in range(len(row["cars"])):
            row["cars"][i] += d * row["speed"] * dt
            x = row["cars"][i]
            if d > 0 and x > WIDTH + 120:
                row["cars"][i] = x - span
            elif d < 0 and x < -120:
                row["cars"][i] = x + span

    pr = round(player_disp)
    row = rows.get(pr)
    if row and row["type"] == "road" and hop_t >= 1.0:
        for x in row["cars"]:
            if abs((x + CARW / 2) - PLAYER_X) < (CARW + TILE * 0.5) / 2:
                burst(PLAYER_X, screen_y(player_disp), row["color"], 28)
                return die()


def draw_tile(r, base, alt):
    y = screen_y(r)
    col = base if (r % 2 == 0) else alt
    screen.draw.filled_rect(Rect(0, int(y - TILE / 2), WIDTH, TILE + 1), col)


def draw_car(x, y, color):
    rx = int(x)
    ry = int(y - CARH / 2)
    screen.draw.filled_rect(Rect(rx, ry, int(CARW), int(CARH)), color)
    dark = (max(0, color[0] - 60), max(0, color[1] - 60), max(0, color[2] - 60))
    screen.draw.filled_rect(Rect(rx + 6, ry + 6, int(CARW) - 12, int(CARH) - 18), dark)
    screen.draw.filled_circle((rx + 12, int(y + CARH / 2)), 6, (20, 20, 20))
    screen.draw.filled_circle((rx + int(CARW) - 12, int(y + CARH / 2)), 6, (20, 20, 20))


def draw_chicken(x, y, squash=0.0):
    r = TILE * 0.32
    sh_y = screen_y(round(player_disp)) + TILE * 0.32
    screen.draw.filled_circle((int(x), int(sh_y)), int(r * 0.9), (40, 130, 50))
    body = (255, 255, 255)
    rr = r * (1.0 - squash * 0.25)
    screen.draw.filled_circle((int(x), int(y)), int(rr), body)
    screen.draw.filled_circle((int(x), int(y - rr * 0.7)), int(rr * 0.7), body)
    screen.draw.filled_circle((int(x - rr * 0.25), int(y - rr * 0.8)), 3, (20, 20, 20))
    screen.draw.filled_circle((int(x + rr * 0.25), int(y - rr * 0.8)), 3, (20, 20, 20))
    screen.draw.filled_rect(Rect(int(x - 4), int(y - rr * 0.6), 8, 6), (250, 170, 30))
    screen.draw.filled_circle((int(x), int(y - rr * 1.15)), 4, (230, 40, 40))


def draw():
    screen.fill((30, 30, 40))

    lo = int(cam) - 3
    hi = int(cam) + 14
    for r in range(lo, hi):
        row = rows.get(r)
        if not row:
            continue
        if row["type"] == "grass":
            draw_tile(r, GRASS_A, GRASS_B)
        else:
            draw_tile(r, ROAD_A, ROAD_B)
            y = screen_y(r)
            for dx in range(0, WIDTH, 40):
                screen.draw.filled_rect(Rect(dx + 6, int(y) - 2, 20, 4), (210, 200, 90))

    for r in range(lo, hi):
        row = rows.get(r)
        if not row or row["type"] != "road":
            continue
        y = screen_y(r)
        for x in row["cars"]:
            draw_car(x, y, row["color"])

    fy = screen_y(floor_row)
    if fy < HEIGHT + TILE:
        screen.draw.filled_rect(Rect(0, int(fy), WIDTH, HEIGHT), (120, 30, 30, 80))
        screen.draw.filled_rect(Rect(0, int(fy) - 6, WIDTH, 6), (220, 60, 60))

    if state != STATE_DEAD:
        squash = 1.0 - hop_t if hop_t < 1.0 else 0.0
        draw_chicken(PLAYER_X, screen_y(player_disp), squash)

    for p in particles:
        a = max(0.0, min(1.0, p[4] / 0.8))
        c = (int(p[5][0] * a), int(p[5][1] * a), int(p[5][2] * a))
        screen.draw.filled_circle((int(p[0]), int(p[1])), max(1, int(4 * a)), c)

    screen.draw.text("%d" % score, topleft=(16, 12), fontsize=56,
                     color="white", owidth=1.2, ocolor=(0, 0, 0))
    screen.draw.text("BEST %d" % best_score, topright=(WIDTH - 16, 22),
                     fontsize=28, color=(240, 240, 240), owidth=1, ocolor=(0, 0, 0))

    if pico:
        link = "PICO LINKED" if pico_alive else "PICO: waiting..."
        col = (60, 230, 120) if pico_alive else (230, 190, 40)
    else:
        link = "NO PICO  -  SPACE = hop"
        col = (230, 150, 150)
    screen.draw.text(link, bottomleft=(16, HEIGHT - 12), fontsize=22,
                     color=col, owidth=0.8, ocolor=(0, 0, 0))

    if state == STATE_TITLE:
        screen.draw.filled_rect(Rect(0, HEIGHT // 2 - 120, WIDTH, 240), (0, 0, 0))
        screen.draw.text("CROSSY ROAD", center=(WIDTH / 2, HEIGHT / 2 - 60),
                         fontsize=64, color=(255, 230, 60), owidth=1, ocolor=(0, 0, 0))
        screen.draw.text("tap the button to hop forward",
                         center=(WIDTH / 2, HEIGHT / 2 + 4), fontsize=28, color="white")
        screen.draw.text("dodge the traffic - don't get left behind",
                         center=(WIDTH / 2, HEIGHT / 2 + 40), fontsize=22,
                         color=(200, 200, 210))
        screen.draw.text("PRESS TO START", center=(WIDTH / 2, HEIGHT / 2 + 96),
                         fontsize=32, color=(255, 230, 60))
    elif state == STATE_DEAD:
        screen.draw.filled_rect(Rect(0, HEIGHT // 2 - 110, WIDTH, 220), (0, 0, 0))
        screen.draw.text("SQUISHED!", center=(WIDTH / 2, HEIGHT / 2 - 50),
                         fontsize=64, color=(255, 80, 80), owidth=1, ocolor=(0, 0, 0))
        screen.draw.text("Score  %d" % score, center=(WIDTH / 2, HEIGHT / 2 + 8),
                         fontsize=38, color="white")
        screen.draw.text("Best  %d" % best_score, center=(WIDTH / 2, HEIGHT / 2 + 46),
                         fontsize=26, color=(200, 200, 210))
        if dead_timer <= 0:
            screen.draw.text("press to try again",
                             center=(WIDTH / 2, HEIGHT / 2 + 92), fontsize=28,
                             color=(255, 230, 60))


pgzrun.go()
