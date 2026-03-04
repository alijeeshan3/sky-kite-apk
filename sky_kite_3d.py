"""
Sky Kite: Island Odyssey  — 3D Enhanced Edition
================================================
Android + Desktop  |  Python 3.10+  |  pygame + numpy
Controls: SPACE / TAP = push DOWN (character floats UP)
          ESC / P     = Pause
          M           = Toggle music
"""

import pygame
import sys, os, math, random, json, time

# ── Android / platform detection ──────────────────────────────────────────────
ON_ANDROID = "ANDROID_ARGUMENT" in os.environ or os.path.exists("/system/build.prop")

pygame.init()
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    AUDIO_OK = True
except Exception:
    AUDIO_OK = False

# ── Display setup (auto-scale for any screen) ──────────────────────────────────
if ON_ANDROID:
    info = pygame.display.Info()
    SCREEN_W, SCREEN_H = info.current_w, info.current_h
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN | pygame.NOFRAME)
else:
    SCREEN_W, SCREEN_H = 430, 760
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)

pygame.display.set_caption("Sky Kite: Island Odyssey 3D")

# Virtual canvas — ALL game logic uses these coords
VIRT_W, VIRT_H = 400, 700
SCALE    = min(SCREEN_W / VIRT_W, SCREEN_H / VIRT_H)
CANVAS_W = int(VIRT_W * SCALE)
CANVAS_H = int(VIRT_H * SCALE)
OFF_X    = (SCREEN_W - CANVAS_W) // 2
OFF_Y    = (SCREEN_H - CANVAS_H) // 2

canvas = pygame.Surface((VIRT_W, VIRT_H))
clock  = pygame.time.Clock()
FPS    = 60

# ── Save / load ────────────────────────────────────────────────────────────────
if ON_ANDROID:
    import android  # noqa – available on-device; silently skipped on desktop
    SAVE_DIR = android.get_external_storage_path() if hasattr(android, "get_external_storage_path") else os.getcwd()
else:
    SAVE_DIR = os.getcwd()
SAVE_FILE = os.path.join(SAVE_DIR, "sky_kite_save.json")

def load_save():
    try:
        with open(SAVE_FILE) as f:
            d = json.load(f)
            d.setdefault("unlocked", ["default_skin","default_trail","default_theme"])
            d.setdefault("skin","default_skin"); d.setdefault("trail","default_trail")
            d.setdefault("theme","default_theme"); d.setdefault("coins",0); d.setdefault("highscore",0)
            return d
    except Exception:
        return {"coins":0,"highscore":0,
                "unlocked":["default_skin","default_trail","default_theme"],
                "skin":"default_skin","trail":"default_trail","theme":"default_theme"}

def write_save(d):
    try:
        with open(SAVE_FILE,"w") as f: json.dump(d, f)
    except Exception: pass

save = load_save()

# ── Palette ────────────────────────────────────────────────────────────────────
def rgb(h): r=int(h[0:2],16); g=int(h[2:4],16); b=int(h[4:6],16); return (r,g,b)
def lighten(c,f): return tuple(min(255,int(v*f)) for v in c)
def darken(c,f):  return tuple(max(0,int(v*f)) for v in c)
def blend(c1,c2,t): return tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))

WHITE=(255,255,255); BLACK=(0,0,0); CYAN=(0,220,255)
GOLD=(255,210,0); AMBER=(255,180,0); TEAL=(0,180,160); ORANGE=(255,100,20)

# ── Constants ──────────────────────────────────────────────────────────────────
FLOAT_UP   = -0.38
PUSH_DOWN  =  3.8
MAX_UP     = -4.5
MAX_DOWN   =  5.5
TILT_U, TILT_D = -18, 22
TILT_LERP  = 0.09
CHAR_SZ    = 36
MAX_LIVES  = 3
INVINC_MS  = 1900
OBS_W      = 88
HITBOX     = {"KITE":12,"DUCK":14,"AIRPLANE":13,"GLIDER":15,"PAPER_PLANE":10,"BALLOON":14,"BUTTERFLY":11}

CHARACTERS = [
    {"id":"AIRPLANE",   "name":"Airplane",       "icon":"✈"},
    {"id":"KITE",       "name":"Kite",            "icon":"◇"},
    {"id":"DUCK",       "name":"Yellow Duck",     "icon":"●"},
    {"id":"GLIDER",     "name":"Hang Glider",     "icon":"△"},
    {"id":"PAPER_PLANE","name":"Paper Plane",     "icon":"▷"},
    {"id":"BALLOON",    "name":"Hot Air Balloon", "icon":"○"},
    {"id":"BUTTERFLY",  "name":"Butterfly",       "icon":"✦"},
]
DIFFICULTIES = {
    "BEGINNER":{"speed":1.8,"spawn_ms":3200,"gap":270},
    "MEDIUM":  {"speed":2.4,"spawn_ms":2600,"gap":225},
    "HARD":    {"speed":3.2,"spawn_ms":2000,"gap":185},
}
CHAR_OBSTACLES = {
    "KITE":        ["windmill","flag","ribbon","wind_tunnel"],
    "DUCK":        ["bubble","balloon_obs","rubber_ring"],
    "AIRPLANE":    ["radar","cloud_wall"],
    "GLIDER":      ["cliff","bridge","thermal"],
    "PAPER_PLANE": ["book","letter","letter_cloud"],
    "BALLOON":     ["cloud_wall","balloon_obs","bubble"],
    "BUTTERFLY":   ["flower","vines","air_current"],
}
SHOP_ITEMS = {
    "SKINS": [
        {"id":"default_skin", "name":"Original",  "price":0},
        {"id":"neon_skin",    "name":"Neon Glow",  "price":50},
        {"id":"stealth_skin", "name":"Stealth",    "price":100},
    ],
    "TRAILS":[
        {"id":"default_trail","name":"Cloud Trail","price":0},
        {"id":"sparkle_trail","name":"Sparkles",   "price":30},
        {"id":"wind_trail",   "name":"Wind Lines",  "price":60},
    ],
    "THEMES":[
        {"id":"default_theme","name":"Tropical Day","price":0},
        {"id":"sunset_theme", "name":"Sunset Glow","price":75},
        {"id":"stormy_theme", "name":"Stormy Sky",  "price":150},
    ],
}

# ── Fonts ──────────────────────────────────────────────────────────────────────
def _f(sz, bold=True): return pygame.font.SysFont("Arial", max(8,int(sz*SCALE)), bold=bold)
_fnt = {}
def fnt(key):
    if key not in _fnt:
        sizes = {"xl":44,"lg":28,"md":20,"sm":15,"xs":12,"tiny":9}
        _fnt[key] = _f(sizes.get(key,14))
    return _fnt[key]

# Re-create fonts if window resizes
def rebuild_fonts():
    global _fnt, canvas, SCALE, CANVAS_W, CANVAS_H, OFF_X, OFF_Y
    _fnt.clear()

# ── Audio synth ────────────────────────────────────────────────────────────────
_sounds = {}
def _make_sound(freq=440, freq2=None, dur=0.12, wave="sine", vol=0.18):
    if not AUDIO_OK: return None
    try:
        import numpy as np
        sr=44100; n=int(sr*dur); f2=freq2 or freq
        t=np.linspace(0,dur,n,endpoint=False)
        fr=freq+(f2-freq)*np.linspace(0,1,n)
        if wave=="sine":      s=np.sin(2*np.pi*fr*t)
        elif wave=="square":  s=np.sign(np.sin(2*np.pi*fr*t))
        elif wave=="saw":     s=2*(fr*t % 1)-1
        elif wave=="tri":     s=2*np.abs(2*(fr*t % 1)-1)-1
        else:                 s=np.sin(2*np.pi*fr*t)
        env=np.linspace(1,0,n)**0.6
        data=(s*env*vol*32767).astype(np.int16)
        stereo=np.column_stack([data,data])
        return pygame.sndarray.make_sound(stereo)
    except Exception: return None

def _init_sounds():
    defs = [
        ("flap",    150,300,  0.10,"sine",  0.12),
        ("score",   440,880,  0.15,"tri",   0.10),
        ("hit",     100,50,   0.22,"square",0.15),
        ("gameover",200,50,   0.55,"square",0.12),
        ("near",    200,100,  0.28,"sine",  0.07),
        ("collect", 600,1200, 0.12,"sine",  0.08),
        ("rare",    880,1760, 0.22,"tri",   0.10),
        ("powerup", 440,880,  0.38,"sine",  0.10),
        ("combo",   500,700,  0.07,"sine",  0.06),
        ("mult_up",1000,2000, 0.18,"tri",   0.10),
    ]
    for name,f,f2,dur,wave,vol in defs:
        _sounds[name]=_make_sound(f,f2,dur,wave,vol)

_init_sounds()
def play(name):
    s=_sounds.get(name)
    if s:
        try: s.play()
        except Exception: pass

# ═══════════════════════════════════════════════════════════════════════════════
# ── 3D DRAW HELPERS ──────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def draw_vgradient(surf, rect, c1, c2):
    x,y,w,h = rect
    for i in range(h):
        t = i/max(h-1,1)
        pygame.draw.line(surf, blend(c1,c2,t), (x,y+i),(x+w,y+i))

def draw_circle_glow(surf, cx, cy, r, color, alpha=100):
    g = pygame.Surface((r*2+4,r*2+4), pygame.SRCALPHA)
    for i in range(r,0,-3):
        a = int(alpha*(i/r)**2)
        pygame.draw.circle(g, (*color, a), (r+2,r+2), i)
    surf.blit(g, (cx-r-2, cy-r-2), special_flags=pygame.BLEND_ALPHA_SDL2)

def draw_3d_pill(surf, x, y, w, h, front_c, is_top=True, depth=10, radius=18):
    """Draw a 3D rounded-rectangle pillar with visible side and top/bottom face."""
    side_c = darken(front_c, 0.55)
    edge_c = lighten(front_c, 1.45)
    cap_c  = lighten(front_c, 1.25)

    # --- side face (right) ---
    side_pts = [(x+w, y+radius),(x+w+depth, y+radius-depth),
                (x+w+depth, y+h-radius-depth),(x+w, y+h-radius)]
    if len(side_pts) >= 3:
        pygame.draw.polygon(surf, side_c, side_pts)

    # --- cap face (bottom of top pillar / top of bottom pillar) ---
    if is_top:
        cap_pts = [(x, y+h),(x+depth, y+h-depth),
                   (x+w+depth, y+h-depth),(x+w, y+h)]
    else:
        cap_pts = [(x, y),(x+depth, y-depth),
                   (x+w+depth, y-depth),(x+w, y)]
    pygame.draw.polygon(surf, cap_c, cap_pts)

    # --- front face ---
    pygame.draw.rect(surf, front_c, (x, y, w, h), border_radius=radius)

    # --- highlight stripe on left edge ---
    pygame.draw.line(surf, edge_c, (x+3, y+radius), (x+3, y+h-radius), 3)

def draw_gloss_rect(surf, rect, color, radius=14, alpha=255):
    """Glossy rounded rectangle with top highlight."""
    x,y,w,h = rect
    tmp = pygame.Surface((w,h), pygame.SRCALPHA)
    # Base
    pygame.draw.rect(tmp, (*color, alpha), (0,0,w,h), border_radius=radius)
    # Gloss highlight (top half, semi-transparent white)
    gh = h//2
    for i in range(gh):
        a = int(60*(1-i/gh))
        pygame.draw.line(tmp, (255,255,255,a), (radius//2,i),(w-radius//2,i))
    # Subtle bottom shadow inside
    pygame.draw.rect(tmp, (*darken(color,0.6), 80), (2,h-6,w-4,4), border_radius=4)
    surf.blit(tmp, (x,y))

def draw_3d_button(surf, rect, color, label, font_key="sm",
                   hover=False, active=False, text_color=WHITE):
    x,y,w,h = rect
    depth = 5
    pressed = active
    bc = lighten(color,1.1) if hover else color
    if pressed: bc = darken(color,0.8)
    # Shadow
    pygame.draw.rect(surf, darken(color,0.45), (x+depth,y+depth,w,h), border_radius=14)
    # Main button
    draw_gloss_rect(surf, rect, bc, radius=14)
    # Border
    pygame.draw.rect(surf, lighten(color,1.5), rect, 2, border_radius=14)
    # Label
    img = fnt(font_key).render(label, True, text_color)
    r = img.get_rect(center=(x+w//2+(1 if not pressed else 0),
                               y+h//2+(1 if not pressed else 0)))
    surf.blit(img, r)
    mx,my = _canvas_mouse()
    return x<=mx<=x+w and y<=my<=y+h

def _canvas_mouse():
    mx,my = pygame.mouse.get_pos()
    if SCALE != 0:
        return (mx-OFF_X)/SCALE, (my-OFF_Y)/SCALE
    return mx,my

def txt(surf, text, fk, color, cx, cy, anchor="center", shadow=True):
    img = fnt(fk).render(str(text), True, color)
    r = img.get_rect()
    if anchor=="center": r.center=(cx,cy)
    elif anchor=="left":  r.midleft=(cx,cy)
    elif anchor=="right": r.midright=(cx,cy)
    if shadow:
        sh = fnt(fk).render(str(text), True, (0,0,0))
        surf.blit(sh, (r.x+2, r.y+2))
    surf.blit(img, r)

# ═══════════════════════════════════════════════════════════════════════════════
# ── BACKGROUND ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def draw_sky(surf, theme, w, h):
    if theme=="sunset_theme":
        stops=[(0,(50,10,80)),(0.4,(200,60,20)),(0.7,(240,120,30)),(1,(255,180,60))]
    elif theme=="stormy_theme":
        stops=[(0,(20,30,50)),(0.4,(55,70,90)),(0.7,(80,100,115)),(1,(60,75,80))]
    else:
        stops=[(0,(30,140,160)),(0.35,(100,190,220)),(0.7,(200,230,180)),(1,(150,210,190))]
    def interp(stops,t):
        for i in range(len(stops)-1):
            t0,c0=stops[i]; t1,c1=stops[i+1]
            if t0<=t<=t1:
                f=(t-t0)/(t1-t0) if t1>t0 else 0
                return blend(c0,c1,f)
        return stops[-1][1]
    for row in range(h):
        pygame.draw.line(surf, interp(stops,row/h), (0,row),(w,row))

def draw_parallax_islands(surf, offset, char, w, h, now_ms):
    for i in range(4):
        ix = int((offset + i * 320) % (w + 320)) - 160
        iy = h - 200 + i * 20
        iw = 220 - i * 20; ihh = 70 - i * 8
        # 3D island effect: draw bottom shadow then body
        pygame.draw.ellipse(surf, (60,80,100,80), (ix-iw//2+8, iy+10, iw, ihh))
        pygame.draw.ellipse(surf, (80,110,140), (ix-iw//2, iy, iw, ihh))
        # Grass cap
        gc = (80,180,100) if char != "BUTTERFLY" else (40,160,80)
        pygame.draw.ellipse(surf, gc, (ix-iw//2-4, iy-14, iw+8, 28))
        # Butterfly: animated flower
        if char == "BUTTERFLY":
            sway = math.sin(now_ms/700 + i) * 7
            fx, fy = ix + sway, iy - 14
            pygame.draw.line(surf, (30,120,50), (fx, fy), (int(fx+sway*0.3), fy-22), 2)
            bloom = abs(math.sin(now_ms/900 + i))
            fc = (240,80,140) if i%2==0 else (180,80,220)
            r2 = int(6 + bloom*3)
            pygame.draw.circle(surf, fc, (int(fx+sway*0.3), int(fy-22)), r2)
            pygame.draw.circle(surf, (255,230,50), (int(fx+sway*0.3), int(fy-22)), max(2,r2//2))

def draw_ocean(surf, offset, char, velocity, w, h, now_ms):
    oy = h - 90
    # Perspective ocean: wider at bottom, narrower towards horizon
    ocean_c = (0,100,180)
    pygame.draw.rect(surf, ocean_c, (0, oy, w, h-oy))
    # Shimmer overlay
    shim = pygame.Surface((w, h-oy), pygame.SRCALPHA)
    for i in range(5):
        xo = int((offset*0.5 + i*120) % (w+60)) - 30
        pts = [(xo + j*28, int(6 + math.sin(now_ms/450+j+i)*4)) for j in range(8)]
        if len(pts)>1: pygame.draw.lines(shim, (255,255,255,70), False, pts, 2)
    surf.blit(shim, (0,oy))
    # Duck ripple
    if char=="DUCK":
        rs = int(18 + abs(velocity)*6)
        pygame.draw.ellipse(surf, (100,200,240), (55-rs, oy+12, rs*2, rs//2))

def draw_clouds(surf, offset, char, char_vx, w, h, now_ms):
    for i in range(5):
        dx = char_vx * 0.9 if char=="KITE" else 0
        cx2 = int((offset + i*220 + dx) % (w+180)) - 90
        cy2 = 40 + i*45
        sz = 26 - i*3
        # 3D cloud: bottom darker, top white
        for dx2, dy2, cr in [(-26,10,sz-4),(0,0,sz+4),(26,8,sz-2),(14,-12,sz),(-12,-10,sz-3)]:
            cl = blend((180,200,220),(255,255,255), max(0, 1-dy2/25))
            pygame.draw.circle(surf, cl, (cx2+dx2, cy2+dy2), cr)

# ═══════════════════════════════════════════════════════════════════════════════
# ── 3D CHARACTER DRAWING ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def draw_airplane_3d(surf, cx, cy, rot, now_ms):
    s = pygame.Surface((90,70), pygame.SRCALPHA)
    # Drop shadow
    pygame.draw.ellipse(s,(0,0,0,40),(10,58,70,12))
    # Engine nacelle (3D cylinder look)
    pygame.draw.ellipse(s,(80,80,90),(17,24,54,18))
    # Body gradient
    draw_vgradient(s, (18,22,52,18), (230,50,50),(180,20,20))
    pygame.draw.rect(s,(180,20,20),(18,22,52,18), border_radius=8)
    draw_vgradient(s, (18,22,52,9), (250,80,80),(230,50,50))
    # Cockpit
    pygame.draw.ellipse(s,(30,160,220),(38,14,24,14))
    pygame.draw.ellipse(s,(180,230,255),(40,13,10,6))
    # Wings (3D: draw bottom face first)
    pygame.draw.polygon(s,darken((220,40,40),0.6),  [(24,30),(4,8),(44,8),(38,30)])
    pygame.draw.polygon(s,(220,40,40),               [(24,28),(4,6),(44,6),(38,28)])
    pygame.draw.polygon(s,darken((200,30,30),0.6),  [(24,38),(4,58),(44,58),(38,38)])
    pygame.draw.polygon(s,(200,30,30),               [(24,36),(4,56),(44,56),(38,36)])
    # Tail
    pygame.draw.polygon(s,(190,35,35),[(14,30),(2,18),(22,30)])
    # Propeller
    pa = math.radians(now_ms/35 % 360)
    for i in range(3):
        a = pa + i*2.094
        pygame.draw.line(s,(200,200,210),(66,31),(int(66+math.cos(a)*16),int(31+math.sin(a)*16)),4)
    pygame.draw.circle(s,(60,60,70),(66,31),5)
    # Specular highlight
    pygame.draw.ellipse(s,(255,150,150,60),(24,23,20,5))
    rotated = pygame.transform.rotate(s, -rot)
    surf.blit(rotated, rotated.get_rect(center=(cx,cy)))

def draw_kite_3d(surf, cx, cy, rot, now_ms):
    s = pygame.Surface((90,90), pygame.SRCALPHA)
    # Shadow
    pygame.draw.ellipse(s,(0,0,0,35),(25,80,40,8))
    # 3D diamond panels
    pts = [(45,6),(78,45),(45,84),(12,45)]
    pygame.draw.polygon(s,darken((245,210,40),0.7), [(45,45),(78,45),(45,84)])
    pygame.draw.polygon(s,darken((225,40,50),0.7),  [(45,45),(12,45),(45,84)])
    pygame.draw.polygon(s,(245,210,40), [(45,6),(78,45),(45,45)])
    pygame.draw.polygon(s,(225,40,50),  [(45,6),(12,45),(45,45)])
    # Spars
    pygame.draw.line(s,(50,40,20,150),(12,45),(78,45),2)
    pygame.draw.line(s,(50,40,20,150),(45,6),(45,84),2)
    # Gloss
    pygame.draw.ellipse(s,(255,255,200,80),(36,12,16,22))
    # Tail bows
    for i in range(6):
        bx = int(45 - i*10 + math.sin(now_ms/180+i)*8)
        by = int(84 + i*9 + math.cos(now_ms/180+i)*5)
        fc=(225,40,50) if i%2==0 else (40,150,230)
        pygame.draw.rect(s, fc, (bx-4,by-4,8,8), border_radius=2)
    rotated = pygame.transform.rotate(s, -rot)
    surf.blit(rotated, rotated.get_rect(center=(cx,cy)))

def draw_duck_3d(surf, cx, cy, rot, now_ms, velocity):
    s = pygame.Surface((95,75), pygame.SRCALPHA)
    bob = int(math.sin(now_ms/140)*2)
    oy = 38 + bob
    # Shadow
    pygame.draw.ellipse(s,(0,0,0,40),(12,oy+16,60,10))
    # Body (3D: draw darker side first)
    pygame.draw.ellipse(s,darken((255,200,30),0.7),(16,oy-12,52,26))
    draw_vgradient(s,(14,oy-14,54,24),(255,235,80),(210,165,20))
    pygame.draw.ellipse(s,(255,225,60),(14,oy-14,54,24))
    # Head
    pygame.draw.circle(s,darken((255,220,50),0.7),(58,oy-16),14)
    pygame.draw.circle(s,(255,230,70),(58,oy-17),13)
    # Eye
    blink = math.sin(now_ms/900) > 0.94
    if not blink:
        pygame.draw.circle(s,(15,15,20),(62,oy-22),3)
        pygame.draw.circle(s,(255,255,255),(63,oy-23),1)
    else:
        pygame.draw.line(s,(15,15,20),(56,oy-22),(65,oy-22),2)
    # Beak
    pygame.draw.polygon(s,(255,140,20),[(70,oy-19),(83,oy-14),(70,oy-10)])
    # Wing (animated)
    wa = math.sin(now_ms/max(25,80-abs(velocity)*12))
    wy = int(oy + wa*9)
    pygame.draw.ellipse(s,darken((255,210,40),0.7),(10,wy-8,42,16))
    pygame.draw.ellipse(s,(255,225,60),(10,wy-9,40,14))
    # Specular
    pygame.draw.ellipse(s,(255,255,200,70),(22,oy-12,18,6))
    rotated = pygame.transform.rotate(s, -rot)
    surf.blit(rotated, rotated.get_rect(center=(cx,cy)))

def draw_glider_3d(surf, cx, cy, rot, now_ms):
    s = pygame.Surface((90,65), pygame.SRCALPHA)
    pygame.draw.ellipse(s,(0,0,0,35),(15,56,60,8))
    # Wing (3D: bottom darker)
    pygame.draw.polygon(s,darken((60,185,245),0.65),[(45,20),(2,44),(88,44),(45,50)])
    pygame.draw.polygon(s,(80,200,255), [(45,18),(2,42),(88,42),(45,48)])
    # Frame
    pygame.draw.lines(s,(50,80,100),False,[(8,42),(45,58),(82,42)],2)
    # Pilot
    pygame.draw.circle(s,(240,190,160),(45,52),6)
    pygame.draw.rect(s,(40,60,80),(42,57,6,9))
    # Wing gloss
    pygame.draw.ellipse(s,(255,255,255,50),(28,22,30,8))
    rotated = pygame.transform.rotate(s, -rot)
    surf.blit(rotated, rotated.get_rect(center=(cx,cy)))

def draw_paper_plane_3d(surf, cx, cy, rot, now_ms):
    s = pygame.Surface((75,55), pygame.SRCALPHA)
    pygame.draw.ellipse(s,(0,0,0,35),(10,46,55,8))
    # Bottom panel (shadow)
    pygame.draw.polygon(s,(180,180,190),[(58,28),(8,44),(18,28)])
    # Top-right panel
    pygame.draw.polygon(s,(230,230,240),[(58,28),(8,12),(18,28)])
    # Top-left panel
    pygame.draw.polygon(s,(210,210,225),[(58,28),(8,44),(8,12)])
    # Center fold
    pygame.draw.line(s,(150,150,165),(58,28),(8,28),1)
    # Wing crease
    pygame.draw.line(s,(160,160,175),(18,28),(8,12),1)
    # Gloss
    pygame.draw.ellipse(s,(255,255,255,70),(20,15,22,8))
    rotated = pygame.transform.rotate(s, -rot)
    surf.blit(rotated, rotated.get_rect(center=(cx,cy)))

def draw_balloon_3d(surf, cx, cy, rot, now_ms):
    s = pygame.Surface((75,90), pygame.SRCALPHA)
    sway = math.sin(now_ms/1100)*4
    # Basket shadow
    pygame.draw.ellipse(s,(0,0,0,40),(int(22+sway)+4,70,26,8))
    # Basket 3D
    pygame.draw.rect(s,darken((120,80,55),0.6),(int(22+sway)+4,58,22,14),border_radius=3)
    pygame.draw.rect(s,(140,95,65),(int(20+sway),56,22,14),border_radius=3)
    pygame.draw.line(s,(100,65,40),(int(20+sway),56),(int(20+sway)+22,56),2)
    # Ropes
    pygame.draw.line(s,(100,70,45),(int(20+sway),56),(22,40),2)
    pygame.draw.line(s,(100,70,45),(int(42+sway),56),(50,40),2)
    # Balloon 3D (right darker side)
    pygame.draw.circle(s,darken((230,50,50),0.65),(38,28),26)
    draw_circle_glow(s, 33, 22, 12, (255,100,100), 60)
    pygame.draw.circle(s,(240,55,55),(36,26),25)
    # Stripes
    for i in range(4):
        a = i*math.pi/2
        x2=int(36+math.cos(a)*18); y2=int(26+math.sin(a)*18)
        pygame.draw.line(s,(180,30,30),(36,26),(x2,y2),3)
    # Gloss
    pygame.draw.ellipse(s,(255,200,200,100),(22,12,16,14))
    rotated = pygame.transform.rotate(s, -rot)
    surf.blit(rotated, rotated.get_rect(center=(cx,cy)))

def draw_butterfly_3d(surf, cx, cy, rot, now_ms):
    s = pygame.Surface((85,75), pygame.SRCALPHA)
    flap = abs(math.sin(now_ms/115))
    pygame.draw.ellipse(s,(0,0,0,30),(35,66,15,6))
    # Body
    pygame.draw.ellipse(s,darken((30,15,40),0.5),(37,28,11,20))
    pygame.draw.ellipse(s,(45,20,55),(36,27,10,20))
    # Antennae
    pygame.draw.line(s,(40,20,50),(41,27),(int(41-8*flap),14),2)
    pygame.draw.line(s,(40,20,50),(41,27),(int(41+8*flap),14),2)
    pygame.draw.circle(s,(80,40,100),(int(41-8*flap),14),3)
    pygame.draw.circle(s,(80,40,100),(int(41+8*flap),14),3)
    # Wings (3D: draw shadow first then coloured)
    tw = int(30*flap)
    if tw>2:
        pygame.draw.ellipse(s,darken((170,50,200),0.5),(41,14,tw+4,24))
        pygame.draw.ellipse(s,darken((170,50,200),0.5),(41-tw-4,14,tw+4,24))
        pygame.draw.ellipse(s,(190,60,220),(41,14,tw,22))
        pygame.draw.ellipse(s,(190,60,220),(41-tw,14,tw,22))
        pygame.draw.circle(s,(230,200,240,180),(41+tw//2,22),max(1,tw//3))
        pygame.draw.circle(s,(230,200,240,180),(41-tw//2,22),max(1,tw//3))
    bw = int(22*flap)
    if bw>2:
        pygame.draw.ellipse(s,darken((230,30,110),0.6),(41,34,bw,18))
        pygame.draw.ellipse(s,darken((230,30,110),0.6),(41-bw,34,bw,18))
        pygame.draw.ellipse(s,(245,40,120),(41,34,bw,16))
        pygame.draw.ellipse(s,(245,40,120),(41-bw,34,bw,16))
    # Wing gloss
    if tw>4:
        pygame.draw.ellipse(s,(255,255,255,60),(43,16,tw//2,8))
    rotated = pygame.transform.rotate(s, -rot)
    surf.blit(rotated, rotated.get_rect(center=(cx,cy)))

CHAR_DRAW_3D = {
    "AIRPLANE":    lambda s,cx,cy,r,n: draw_airplane_3d(s,cx,cy,r,n),
    "KITE":        lambda s,cx,cy,r,n: draw_kite_3d(s,cx,cy,r,n),
    "DUCK":        lambda s,cx,cy,r,n: draw_duck_3d(s,cx,cy,r,n,0),
    "GLIDER":      lambda s,cx,cy,r,n: draw_glider_3d(s,cx,cy,r,n),
    "PAPER_PLANE": lambda s,cx,cy,r,n: draw_paper_plane_3d(s,cx,cy,r,n),
    "BALLOON":     lambda s,cx,cy,r,n: draw_balloon_3d(s,cx,cy,r,n),
    "BUTTERFLY":   lambda s,cx,cy,r,n: draw_butterfly_3d(s,cx,cy,r,n),
}

# ═══════════════════════════════════════════════════════════════════════════════
# ── 3D OBSTACLES ──────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def draw_obstacle_3d(surf, obs, gap, ch, now_ms):
    W = VIRT_W
    for is_top in (True, False):
        x  = int(obs["x"])
        oy = 0 if is_top else int(obs["top_h"]+gap)
        oh = int(obs["top_h"]) if is_top else int(VIRT_H - obs["top_h"] - gap)
        t  = obs["type"]
        ey = oy+oh if is_top else oy  # gap-edge y

        if oh < 2: continue

        # Choose pillar colour per type
        col_map = {
            "windmill":(140,105,90),"flag":(115,78,62),"ribbon":(140,100,190),
            "wind_tunnel":(130,100,80),"bubble":(140,200,230),"balloon_obs":(240,220,140),
            "rubber_ring":(240,210,40),"radar":(55,75,90),"cloud_wall":(210,220,230),
            "cliff":(80,100,115),"bridge":(110,80,65),"thermal":(160,180,200),
            "book":(130,155,165),"letter":(190,205,210),"letter_cloud":(200,215,225),
            "flower":(70,165,75),"vines":(55,135,60),"air_current":(180,225,200),
        }
        fc = col_map.get(t,(130,100,80))
        draw_3d_pill(surf, x, oy if is_top else oy, OBS_W, oh, fc, is_top=is_top, depth=10, radius=18)

        # ── Decorations at gap edge ──
        if t=="windmill":
            bx,by=x+OBS_W//2,ey
            angle=math.radians(now_ms/500*57.3)
            for i in range(4):
                a=angle+i*math.pi/2
                ex2=int(bx+math.cos(a)*24); ey2=int(by+math.sin(a)*24)
                pygame.draw.line(surf,(220,200,185),(bx,by),(ex2,ey2),5)
                pygame.draw.ellipse(surf,lighten(fc,1.3),(ex2-6,ey2-4,12,8))
            pygame.draw.circle(surf,(100,75,55),(bx,by),7)
            pygame.draw.circle(surf,lighten(fc,1.5),(bx,by),4)

        elif t=="flag":
            fx=x+OBS_W; fy=(ey-22) if is_top else (ey+5)
            wv=math.sin(now_ms/200)*5
            pts=[(fx,fy),(fx+24,fy+10+wv),(fx+22,fy+14+wv),(fx,fy+24)]
            pygame.draw.polygon(surf,(220,60,60),pts)
            pygame.draw.line(surf,(80,55,40),(fx,fy-4),(fx,fy+26),3)

        elif t=="ribbon":
            for i in range(9):
                rx1=x+i*10; ry1=int(ey+math.sin(now_ms/180+i)*14)
                rx2=x+(i+1)*10; ry2=int(ey+math.sin(now_ms/180+i+1)*14)
                pygame.draw.line(surf,(255,255,255,140),(rx1,ry1),(rx2,ry2),2)
            for i in range(1,6):
                pygame.draw.rect(surf,(220,60,60),(x+i*18-3,int(ey+math.sin(now_ms/180+i)*14)-3,6,6))

        elif t=="bubble":
            n=max(1,oh//45)
            for i in range(n):
                bx=x+OBS_W//2+int(math.sin(i*1.3)*9)
                by_=oy+i*45+22
                pygame.draw.circle(surf,(150,210,240,90),(bx,by_),18)
                pygame.draw.circle(surf,(200,235,255,120),(bx,by_),18,2)
                pygame.draw.circle(surf,(255,255,255,100),(bx-5,by_-5),5)

        elif t=="balloon_obs":
            bcy=(ey-24) if is_top else (ey+24)
            pygame.draw.circle(surf,darken((245,70,70),0.7),(x+OBS_W//2+4,bcy+4),22)
            pygame.draw.circle(surf,(245,70,70),(x+OBS_W//2,bcy),22)
            pygame.draw.circle(surf,(200,200,255,90),(x+OBS_W//2-6,bcy-6),8)

        elif t=="radar":
            if (now_ms//500)%2==0:
                draw_circle_glow(surf,x+OBS_W//2,ey-8 if is_top else ey+8,12,(255,30,60),140)
                pygame.draw.circle(surf,(255,30,60),(x+OBS_W//2,ey-8 if is_top else ey+8),6)

        elif t=="cloud_wall":
            n=max(1,int(oh//32))
            for i in range(n+1):
                ccx=x+OBS_W//2+(12 if i%2==0 else -10)
                ccy=oy+i*32
                pygame.draw.circle(surf,(235,242,248),(ccx+3,ccy+3),22)
                pygame.draw.circle(surf,(255,255,255),(ccx,ccy),22)

        elif t=="cliff":
            for i in range(4):
                ly=oy+int(oh//5)*(i+1)
                pygame.draw.line(surf,lighten(fc,1.4),(x+4,ly),(x+OBS_W-4,ly),2)

        elif t=="thermal":
            for i in range(5):
                a=int(30+math.sin(now_ms/500+i)*20)
                pygame.draw.rect(surf,(200,210,255,a),(x+i*10,oy,8,oh))

        elif t=="flower":
            fcy=(ey-14) if is_top else (ey+14)
            fc2=(235,60,60) if obs["var"]>0.5 else (160,50,200)
            for i in range(6):
                fa=i*math.pi/3
                fx2=int(x+OBS_W//2+math.cos(fa)*15); fy2=int(fcy+math.sin(fa)*15)
                pygame.draw.circle(surf,darken(fc2,0.7),(fx2+2,fy2+2),9)
                pygame.draw.circle(surf,fc2,(fx2,fy2),9)
            pygame.draw.circle(surf,(255,230,50),(x+OBS_W//2,fcy),7)

        elif t=="vines":
            n=max(1,int(oh//28))
            for i in range(n):
                lx=x if i%2==0 else x+OBS_W
                ly2=oy+i*28+12
                pygame.draw.ellipse(surf,(100,200,110),(lx-11,ly2-6,22,12))
                pygame.draw.ellipse(surf,(130,215,140),(lx-10,ly2-5,20,10))

        elif t=="air_current":
            acy=(ey-20) if is_top else (ey+20)
            pts=[(x+j*11,int(acy+math.sin(now_ms/280+j)*9)) for j in range(7)]
            if len(pts)>1: pygame.draw.lines(surf,(200,240,210,120),False,pts,2)
            pygame.draw.circle(surf,(248,180,210),(x+32,acy+6),5)

        elif t in ("book","letter"):
            ey2=(ey-12) if is_top else ey
            pygame.draw.rect(surf,lighten(fc,1.3),(x+4,ey2,OBS_W-8,10),border_radius=3)

        else:  # island default
            cap_y=(ey-16) if is_top else (ey-4)
            pygame.draw.rect(surf,(80,180,100),(x-4,cap_y,OBS_W+8,18),border_radius=10)
            pygame.draw.rect(surf,(60,160,80),(x-4,cap_y,OBS_W+8,9),border_radius=10)

# ═══════════════════════════════════════════════════════════════════════════════
# ── COLLECTIBLES ──────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def draw_collectible_3d(surf, col, now_ms):
    x=int(col["x"]); y=int(col["y"]+math.sin(now_ms/290+col["id"])*9)
    cat=col["category"]

    # 3D glow aura
    gr_size=30
    g=pygame.Surface((gr_size*2,gr_size*2),pygame.SRCALPHA)
    gc={"RARE":(255,210,0,90),"POWERUP":(0,220,255,90)}.get(cat,(255,255,255,55))
    pygame.draw.circle(g,gc,(gr_size,gr_size),gr_size)
    surf.blit(g,(x-gr_size,y-gr_size),special_flags=pygame.BLEND_ALPHA_SDL2)

    if cat=="RARE":
        # 3D gold coin
        pygame.draw.circle(surf,darken(GOLD,0.55),(x+3,y+3),14)
        pygame.draw.circle(surf,GOLD,(x,y),14)
        pygame.draw.circle(surf,lighten(GOLD,1.4),(x,y),14,2)
        for i in range(5):
            a=math.radians(i*72-90)
            ia=math.radians(i*72-54)
            pygame.draw.line(surf,WHITE,
                (int(x+math.cos(a)*10),int(y+math.sin(a)*10)),
                (int(x+math.cos(ia)*4),int(y+math.sin(ia)*4)),2)
        pygame.draw.circle(surf,(255,245,200),(x-4,y-4),4)

    elif cat=="POWERUP":
        st=col.get("sub_type","")
        bc={"SHIELD":(0,180,220),"SLOW":(80,180,255),"MAGNET":(220,180,0)}.get(st,CYAN)
        pygame.draw.rect(surf,darken(bc,0.5),(x-12,y-12,28,28),border_radius=8)
        draw_gloss_rect(surf,(x-14,y-14,28,28),bc,radius=8,alpha=220)
        pygame.draw.rect(surf,lighten(bc,1.6),(x-14,y-14,28,28),2,border_radius=8)
        lbl={"SHIELD":"S","SLOW":"T","MAGNET":"M"}.get(st,"?")
        img=fnt("sm").render(lbl,True,WHITE); surf.blit(img,img.get_rect(center=(x,y)))

    else:
        ctype=col["type"]
        # 3D token (shadow + highlight)
        tc=(200,200,200)
        color_map={"KITE":(50,180,240),"DUCK":(255,200,30),"AIRPLANE":(30,130,220),
                   "GLIDER":(150,150,160),"PAPER_PLANE":(220,220,230),
                   "BALLOON":(240,60,60),"BUTTERFLY":(200,80,220)}
        tc=color_map.get(ctype,tc)
        pygame.draw.circle(surf,darken(tc,0.5),(x+3,y+3),12)
        pygame.draw.circle(surf,tc,(x,y),12)
        pygame.draw.circle(surf,lighten(tc,1.5),(x,y),12,2)
        pygame.draw.circle(surf,(255,255,255,120),(x-3,y-3),4)

# ═══════════════════════════════════════════════════════════════════════════════
# ── COLLECTION EFFECTS ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def draw_effect(surf, eff, now_ms):
    prog=(now_ms-eff["t"])/500.0
    if prog>=1: return
    alpha=int(255*(1-prog))
    n=10
    for i in range(n):
        a=i/n*math.pi*2
        d=prog*40
        px=int(eff["x"]+math.cos(a)*d); py=int(eff["y"]+math.sin(a)*d)
        r=max(1,int(4*(1-prog)))
        col=(255,220,80) if eff.get("rare") else WHITE
        cc=(*col,alpha)
        circ=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
        pygame.draw.circle(circ,cc,(r+1,r+1),r)
        surf.blit(circ,(px-r-1,py-r-1))
    lbl={True:"+5"}.get(eff.get("rare",False),"+1")
    if eff.get("pup"): lbl=eff["pup"]
    ts=fnt("xs").render(lbl,True,(*GOLD,alpha) if eff.get("rare") else (255,255,255,alpha))
    ts.set_alpha(alpha)
    surf.blit(ts,ts.get_rect(center=(int(eff["x"]),int(eff["y"]-prog*38))))

# ═══════════════════════════════════════════════════════════════════════════════
# ── HUD ──────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def draw_hud_3d(surf, lives, score, coins, invincible, combo, multiplier,
                active_pups, now_ms):
    # Semi-transparent top bar
    bar=pygame.Surface((VIRT_W,52),pygame.SRCALPHA)
    bar.fill((0,0,0,60))
    surf.blit(bar,(0,0))

    # Hearts (3D-style)
    for i in range(MAX_LIVES):
        hc=(220,40,40) if i<lives else (60,60,70)
        hx=20+i*30; hy=16
        shadow=pygame.Surface((24,22),pygame.SRCALPHA)
        pygame.draw.polygon(shadow,(0,0,0,60),[(12,20),(0,8),(4,0),(12,6),(20,0),(24,8)])
        surf.blit(shadow,(hx-1,hy+2))
        pygame.draw.polygon(surf,darken(hc,0.6),[(hx+12,hy+20),(hx,hy+8),(hx+4,hy),(hx+12,hy+6),(hx+20,hy),(hx+24,hy+8)])
        pygame.draw.polygon(surf,hc,[(hx+12,hy+19),(hx-1,hy+7),(hx+3,hy-1),(hx+12,hy+5),(hx+21,hy-1),(hx+25,hy+7)])
        if i<lives:
            pygame.draw.polygon(surf,lighten(hc,1.5),[(hx+4,hy+1),(hx+12,hy+6),(hx+20,hy+1),(hx+21,hy+3),(hx+12,hy+8),(hx+3,hy+3)])

    # Score (big, centered, with depth)
    sc=str(score)
    sh=fnt("lg").render(sc,True,(0,0,0)); sh.set_alpha(80)
    si=fnt("lg").render(sc,True,WHITE)
    sr=si.get_rect(center=(VIRT_W//2,26))
    surf.blit(sh,(sr.x+3,sr.y+3)); surf.blit(si,sr)

    # Coin badge
    coin_bg=pygame.Surface((72,22),pygame.SRCALPHA)
    pygame.draw.rect(coin_bg,(0,0,0,100),(0,0,72,22),border_radius=11)
    surf.blit(coin_bg,(VIRT_W-78,6))
    img=fnt("xs").render(f"🪙 {coins}",True,GOLD)
    surf.blit(img,(VIRT_W-74,10))

    # Shield icon when invincible
    if invincible:
        draw_circle_glow(surf,14,62,10,CYAN[:3],120)
        pygame.draw.circle(surf,CYAN,(14,62),8,2)

    # Combo / multiplier above character
    if combo>0:
        txt(surf,f"{combo}×COMBO","xs",AMBER,60,VIRT_H//2-38)
        if multiplier>1:
            ml=f"{multiplier:.1f}×"
            txt(surf,ml,"sm",(255,80,80),60,VIRT_H//2-56)

    # Active power-up timers (bottom bar)
    for i,p in enumerate(active_pups):
        remaining=max(0,p["end"]-pygame.time.get_ticks())
        pc_map={"SHIELD":CYAN,"SLOW":(150,180,255),"MAGNET":AMBER}
        pc=pc_map.get(p["type"],WHITE)
        bx=8+i*70; by=VIRT_H-34
        draw_gloss_rect(surf,(bx,by,62,22),pc[:3],radius=8,alpha=180)
        lbl={"SHIELD":"🛡","SLOW":"⏱","MAGNET":"🧲"}.get(p["type"],"?")
        txt(surf,f"{lbl}{remaining//1000+1}s","tiny",(0,0,0),bx+31,by+11,shadow=False)

# ═══════════════════════════════════════════════════════════════════════════════
# ── SCREENS ──────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def draw_start_screen(surf, coins, hs, now_ms):
    # Animated sky bg
    draw_sky(surf,"default_theme",VIRT_W,VIRT_H)
    draw_parallax_islands(surf,-now_ms*0.04,"AIRPLANE",VIRT_W,VIRT_H,now_ms)
    draw_ocean(surf,now_ms*0.02,"AIRPLANE",0,VIRT_W,VIRT_H,now_ms)

    # Glass panel
    panel=pygame.Surface((340,420),pygame.SRCALPHA)
    pygame.draw.rect(panel,(255,255,255,35),(0,0,340,420),border_radius=24)
    pygame.draw.rect(panel,(255,255,255,80),(0,0,340,30),border_radius=24)
    pygame.draw.rect(panel,(255,255,255,90),(0,0,340,420),2,border_radius=24)
    surf.blit(panel,(30,110))

    # Title with 3D depth
    for dx,dy,a in [(4,5,40),(2,3,60)]:
        sh=fnt("xl").render("SKY KITE",True,(0,30,50)); sh.set_alpha(a)
        surf.blit(sh,sh.get_rect(center=(VIRT_W//2+dx,185+dy)))
    txt(surf,"SKY KITE","xl",WHITE,VIRT_W//2,185)
    txt(surf,"ISLAND ODYSSEY","md",AMBER,VIRT_W//2,225)
    txt(surf,"⛵  3D EDITION","xs",(200,240,255),VIRT_W//2,250,shadow=False)

    # Animated plane preview
    ax=int(VIRT_W//2+math.cos(now_ms/900)*35)
    ay=int(300+math.sin(now_ms/700)*14)
    draw_airplane_3d(surf,ax,ay,math.sin(now_ms/900)*8,now_ms)

    # Buttons
    ph=draw_3d_button(surf,(VIRT_W//2-70,350,140,48),(50,175,80),"▶  PLAY","md",text_color=WHITE)
    sh_=draw_3d_button(surf,(VIRT_W//2-70,412,140,42),(200,150,20),"🪙  SHOP","sm",text_color=WHITE)

    # Stats
    draw_gloss_rect(surf,(50,470,300,44),(0,0,0),radius=14,alpha=80)
    txt(surf,f"BEST: {hs}","sm",GOLD,150,492)
    txt(surf,f"🪙 {coins}","sm",AMBER,VIRT_W-120,492)

    txt(surf,"SPACE / TAP = push DOWN","tiny",(200,230,210),VIRT_W//2,530,shadow=False)
    txt(surf,"Character floats UP automatically","tiny",(180,210,190),VIRT_W//2,548,shadow=False)
    return ph, sh_

def draw_char_select(surf, selected, now_ms):
    draw_sky(surf,"default_theme",VIRT_W,VIRT_H)
    overlay=pygame.Surface((VIRT_W,VIRT_H),pygame.SRCALPHA); overlay.fill((0,0,0,70)); surf.blit(overlay,(0,0))
    txt(surf,"SELECT YOUR GLIDER","md",WHITE,VIRT_W//2,32)
    draw_3d_button(surf,(10,8,80,32),(80,90,110),"◀ BACK","tiny",text_color=WHITE)
    hovers=[]
    for i,ch in enumerate(CHARACTERS):
        x=18; y=68+i*77; w=VIRT_W-36; h=68
        is_sel=ch["id"]==selected
        bg_a=60 if is_sel else 35
        border_c=(0,220,200) if is_sel else (255,255,255)
        draw_gloss_rect(surf,(x,y,w,h),(30,50,70) if is_sel else (20,30,50),radius=16,alpha=180 if is_sel else 140)
        pygame.draw.rect(surf,border_c,(x,y,w,h),2,border_radius=16)
        # Mini character
        CHAR_DRAW_3D[ch["id"]](surf,x+42,y+34,0,now_ms)
        txt(surf,ch["name"],"sm",WHITE if is_sel else (200,220,220),x+88,y+24,anchor="left",shadow=is_sel)
        if is_sel:
            txt(surf,"SELECTED ✓","tiny",TEAL,x+88,y+44,anchor="left",shadow=False)
        mx,my=_canvas_mouse()
        hovers.append(x<=mx<=x+w and y<=my<=y+h)
    return hovers

def draw_diff_screen(surf, selected, now_ms):
    draw_sky(surf,"default_theme",VIRT_W,VIRT_H)
    overlay=pygame.Surface((VIRT_W,VIRT_H),pygame.SRCALPHA); overlay.fill((0,0,0,70)); surf.blit(overlay,(0,0))
    txt(surf,"CHOOSE DIFFICULTY","md",WHITE,VIRT_W//2,38)
    draw_3d_button(surf,(10,8,80,32),(80,90,110),"◀ BACK","tiny",text_color=WHITE)
    diffs=[("BEGINNER","Relaxed & Wide Gaps",(50,170,80)),
           ("MEDIUM",  "Standard Challenge", (220,150,20)),
           ("HARD",    "Fast & Intense",     (210,50,50))]
    hovers=[]
    for i,(d,desc,c) in enumerate(diffs):
        x=30; y=110+i*168; w=VIRT_W-60; h=150
        is_sel=d==selected
        draw_gloss_rect(surf,(x,y,w,h),darken(c,0.5) if is_sel else (25,35,55),radius=20,alpha=220 if is_sel else 160)
        pygame.draw.rect(surf,c,(x,y,w,h),3 if is_sel else 1,border_radius=20)
        txt(surf,d,"lg",c,VIRT_W//2,y+52,shadow=True)
        txt(surf,desc,"xs",(200,210,220),VIRT_W//2,y+82,shadow=False)
        diff=DIFFICULTIES[d]
        txt(surf,f"Speed {diff['speed']}  |  Gap {diff['gap']}px","tiny",(180,190,200),VIRT_W//2,y+108,shadow=False)
        if is_sel:
            draw_3d_button(surf,(x+60,y+118,w-120,28),c,"▶ SELECT","tiny",text_color=WHITE)
        mx,my=_canvas_mouse()
        hovers.append(x<=mx<=x+w and y<=my<=y+h)
    return hovers

def draw_pause(surf):
    overlay=pygame.Surface((VIRT_W,VIRT_H),pygame.SRCALPHA)
    overlay.fill((10,15,30,175)); surf.blit(overlay,(0,0))
    draw_gloss_rect(surf,(60,180,280,240),(20,30,60),radius=24,alpha=220)
    pygame.draw.rect(surf,TEAL,(60,180,280,240),2,border_radius=24)
    txt(surf,"⏸  PAUSED","lg",WHITE,VIRT_W//2,230)
    r1=draw_3d_button(surf,(VIRT_W//2-80,278,160,48),(50,175,80),"▶  RESUME","md",text_color=WHITE)
    m1=draw_3d_button(surf,(VIRT_W//2-80,340,160,44),(60,70,100),"⌂  MENU","sm",text_color=WHITE)
    txt(surf,"[ESC] to toggle","tiny",(150,160,180),VIRT_W//2,400,shadow=False)
    return r1,m1

def draw_game_over(surf, score, hs, now_ms):
    overlay=pygame.Surface((VIRT_W,VIRT_H),pygame.SRCALPHA)
    overlay.fill((10,5,20,180)); surf.blit(overlay,(0,0))
    draw_gloss_rect(surf,(40,150,VIRT_W-80,290),(15,20,50),radius=24,alpha=230)
    pygame.draw.rect(surf,ORANGE,(40,150,VIRT_W-80,290),2,border_radius=24)
    txt(surf,"JOURNEY'S END","lg",ORANGE,VIRT_W//2,195)
    pygame.draw.line(surf,(80,90,120),(70,220),(VIRT_W-70,220),1)
    txt(surf,"DISTANCE","xs",(180,190,210),VIRT_W//2-60,248,anchor="right",shadow=False)
    txt(surf,str(score),"lg",WHITE,VIRT_W//2+30,248,anchor="left")
    pygame.draw.line(surf,(60,70,100),(70,272),(VIRT_W-70,272),1)
    txt(surf,"★ BEST","xs",GOLD,VIRT_W//2-60,298,anchor="right",shadow=False)
    txt(surf,str(hs),"lg",GOLD,VIRT_W//2+30,298,anchor="left")
    r1=draw_3d_button(surf,(VIRT_W//2-95,368,190,50),(50,170,80),"↺  RESTART","md",text_color=WHITE)
    m1=draw_3d_button(surf,(VIRT_W//2-95,430,190,46),(60,70,110),"⌂  MENU","sm",text_color=WHITE)
    return r1,m1

def draw_shop(surf, coins, unlocked, a_skin, a_trail, a_theme, scroll, now_ms):
    draw_sky(surf,"default_theme",VIRT_W,VIRT_H)
    overlay=pygame.Surface((VIRT_W,VIRT_H),pygame.SRCALPHA); overlay.fill((0,0,0,120)); surf.blit(overlay,(0,0))
    # Top bar
    draw_gloss_rect(surf,(0,0,VIRT_W,56),(15,25,55),radius=0,alpha=220)
    txt(surf,"🛒  SHOP","lg",WHITE,VIRT_W//2,28)
    draw_3d_button(surf,(10,12,72,32),(80,90,110),"◀ BACK","tiny",text_color=WHITE)
    draw_gloss_rect(surf,(VIRT_W-95,12,82,28),(180,140,20),radius=12,alpha=180)
    txt(surf,f"🪙 {coins}","xs",WHITE,VIRT_W-54,26,shadow=False)

    clip=pygame.Rect(0,58,VIRT_W,VIRT_H-58)
    surf.set_clip(clip)
    actives={"SKINS":a_skin,"TRAILS":a_trail,"THEMES":a_theme}
    y0=64-scroll
    hovers=[]; total_h=60
    for cat,items in SHOP_ITEMS.items():
        # Category header
        draw_gloss_rect(surf,(16,y0,VIRT_W-32,24),(30,50,90),radius=8,alpha=160)
        txt(surf,cat,"tiny",TEAL,VIRT_W//2,y0+12,shadow=False)
        y0+=30; total_h+=30
        for item in items:
            is_owned=item["id"] in unlocked
            is_active=item["id"]==actives.get(cat,"")
            bg=(20,60,40) if is_active else (25,35,60) if is_owned else (15,20,45)
            border_c=(0,200,160) if is_active else (80,120,180) if is_owned else (50,60,90)
            draw_gloss_rect(surf,(16,y0,VIRT_W-32,52),bg,radius=14,alpha=200)
            pygame.draw.rect(surf,border_c,(16,y0,VIRT_W-32,52),2,border_radius=14)
            txt(surf,item["name"],"sm",WHITE,30,y0+26,anchor="left",shadow=is_active)
            if not is_owned:
                draw_gloss_rect(surf,(VIRT_W-95,y0+10,75,30),(160,120,20),radius=10,alpha=200)
                txt(surf,f"🪙 {item['price']}","xs",WHITE,VIRT_W-58,y0+25,shadow=False)
            elif is_active:
                txt(surf,"✓ ACTIVE","xs",TEAL,VIRT_W-70,y0+26,shadow=False)
            else:
                draw_3d_button(surf,(VIRT_W-90,y0+12,72,28),(40,80,60),"USE","tiny",text_color=WHITE)
            mx,my=_canvas_mouse()
            hovers.append((item,cat,16<=mx<=VIRT_W-16 and y0<=my<=y0+52))
            y0+=58; total_h+=58
        y0+=10; total_h+=10
    surf.set_clip(None)
    return hovers, total_h

def draw_toast(surf, msg, alpha):
    if not msg or alpha<=0: return
    w=int(len(msg)*7+32); h=34
    x=(VIRT_W-w)//2; y=60
    bg=pygame.Surface((w,h),pygame.SRCALPHA)
    pygame.draw.rect(bg,(20,20,20,min(220,alpha)),(0,0,w,h),border_radius=17)
    pygame.draw.rect(bg,(255,255,255,min(80,alpha)),(0,0,w,h),1,border_radius=17)
    surf.blit(bg,(x,y))
    img=fnt("xs").render(msg,True,(255,255,255)); img.set_alpha(alpha)
    surf.blit(img,img.get_rect(center=(VIRT_W//2,y+17)))

# ═══════════════════════════════════════════════════════════════════════════════
# ── MAIN GAME CLASS ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class Game:
    def __init__(self):
        self.state       = "START"
        self.sel_char    = "AIRPLANE"
        self.difficulty  = "MEDIUM"
        self.coins       = save["coins"]
        self.highscore   = save["highscore"]
        self.unlocked    = save["unlocked"]
        self.a_skin      = save["skin"]
        self.a_trail     = save["trail"]
        self.a_theme     = save["theme"]
        self.toast_msg   = ""
        self.toast_alpha = 0
        self.shop_scroll = 0
        self.shop_total  = 600
        self.music_on    = True
        self.running     = True
        self.reset()

    def save_game(self):
        write_save({"coins":self.coins,"highscore":self.highscore,
                    "unlocked":self.unlocked,"skin":self.a_skin,
                    "trail":self.a_trail,"theme":self.a_theme})

    def show_toast(self, msg):
        self.toast_msg=msg; self.toast_alpha=255

    def reset(self):
        self.char_y      = 330.0
        self.char_vy     = 0.0
        self.char_vx     = 0.0
        self.char_rot    = 0.0
        self.lives       = MAX_LIVES
        self.score       = 0
        self.invincible  = False
        self.invinc_end  = 0
        self.obstacles   = []
        self.collectibles= []
        self.effects     = []
        self.trail       = []
        self.active_pups = []
        self.combo       = 0
        self.multiplier  = 1.0
        self.last_obs_t  = 0
        self.last_col_t  = 0
        self.last_pup_t  = 0
        self.parallax    = {"islands":0.0,"ocean":0.0,"clouds":0.0}
        self.phys        = {"type":"NONE","str":0,"dur":0}
        self.eff_id      = 0

    def diff_cfg(self):
        b=DIFFICULTIES[self.difficulty]
        sp=min(self.score*0.02,1.2)
        sr=min(self.score*20,800)
        gd=min(self.score*0.5,40)
        return {"speed":b["speed"]+sp,"spawn_ms":b["spawn_ms"]-sr,"gap":b["gap"]-gd}

    def spawn_obs(self, now_ms, gap):
        minh=85; maxh=VIRT_H-gap-minh
        if maxh<=minh: maxh=minh+50
        top_h=random.uniform(minh,maxh)
        types=CHAR_OBSTACLES.get(self.sel_char,["island"])
        t=random.choice(types)
        self.obstacles.append({"x":float(VIRT_W),"top_h":top_h,
                                "passed":False,"near_played":False,
                                "type":t,"var":random.random()})
        self.last_obs_t=now_ms
        # Collectible
        if now_ms-self.last_col_t > self.diff_cfg()["spawn_ms"]*0.55:
            cy2=random.uniform(60,VIRT_H-120)
            r=random.random()
            if r>0.95 and now_ms-self.last_pup_t>10000:
                cat="POWERUP"; st=random.choice(["SHIELD","SLOW","MAGNET"]); ctype=st
                self.last_pup_t=now_ms
            elif r>0.86: cat="RARE"; ctype="RARE"; st=None
            else: cat="NORMAL"; ctype=self.sel_char; st=None
            self.eff_id+=1
            self.collectibles.append({"x":float(VIRT_W+90),"y":cy2,"type":ctype,
                                       "category":cat,"sub_type":st,"collected":False,
                                       "id":self.eff_id,"var":random.random()})
            self.last_col_t=now_ms

    def hit(self, now_ms):
        if self.invincible: return
        play("hit"); self.combo=0; self.multiplier=1.0; self.lives-=1
        if self.lives<=0:
            self.state="GAME_OVER"; play("gameover")
            if self.score>self.highscore:
                self.highscore=self.score; self.save_game()
        else:
            self.invincible=True; self.invinc_end=now_ms+INVINC_MS
            self.char_y=min(max(80,self.char_y),VIRT_H-120); self.char_vy=0.0

    def update(self, now_ms, dt_ms):
        if self.state!="PLAYING": return
        if self.toast_alpha>0: self.toast_alpha=max(0,self.toast_alpha-3)

        # Invincibility
        shield_on=any(p["type"]=="SHIELD" for p in self.active_pups)
        if self.invincible and not shield_on and now_ms>self.invinc_end:
            self.invincible=False
        self.active_pups=[p for p in self.active_pups if p["end"]>now_ms]
        if shield_on: self.invincible=True

        dc=self.diff_cfg(); speed=dc["speed"]; gap=dc["gap"]
        if any(p["type"]=="SLOW" for p in self.active_pups): speed*=0.68
        magnet=any(p["type"]=="MAGNET" for p in self.active_pups)

        # Physics
        self.char_vy=max(MAX_UP,min(MAX_DOWN,self.char_vy+FLOAT_UP))
        self.char_y+=self.char_vy; self.char_vx*=0.97

        # Tilt
        target_rot=TILT_U if self.char_vy<0 else TILT_D
        self.char_rot+=(target_rot-self.char_rot)*TILT_LERP

        # Trail
        if random.random()>0.68:
            self.trail.append({"x":62.0,"y":self.char_y+CHAR_SZ//2,
                                "size":random.uniform(4,13),"op":0.6})
        for p in self.trail: p["x"]-=speed; p["op"]-=0.013
        self.trail=[p for p in self.trail if p["op"]>0]

        # Boundary
        if self.char_y<0 or self.char_y>VIRT_H-CHAR_SZ: self.hit(now_ms)
        self.char_y=max(0,min(VIRT_H-CHAR_SZ,self.char_y))

        # Parallax
        self.parallax["islands"]-=speed*0.22
        self.parallax["ocean"]  -=speed*0.52
        self.parallax["clouds"] -=speed*0.82

        # Physics effect
        ph=self.phys
        if ph["dur"]>0:
            if ph["type"]=="WIND":      self.char_vx+=ph["str"]*0.5
            elif ph["type"]=="TURBULENCE": self.char_y+=math.sin(now_ms/45)*2.2
            elif ph["type"]=="UPDRAFT":    self.char_vy-=0.11
            elif ph["type"]=="SWIRL":      self.char_rot+=ph["str"]*5
            elif ph["type"]=="POLLEN":     self.char_y+=math.cos(now_ms/140)*1.2
            ph["dur"]-=1

        # Spawn
        if now_ms-self.last_obs_t>dc["spawn_ms"]:
            self.spawn_obs(now_ms, gap)
            if random.random()>0.78 and ph["dur"]<=0:
                em={"KITE":"WIND","AIRPLANE":"TURBULENCE","GLIDER":"UPDRAFT","PAPER_PLANE":"SWIRL","BUTTERFLY":"POLLEN"}
                et=em.get(self.sel_char)
                if et: self.phys={"type":et,"str":random.uniform(-1,1),"dur":130}

        hbR=HITBOX.get(self.sel_char,14)
        ccx=int(62+self.char_vx+CHAR_SZ//2); ccy=int(self.char_y+CHAR_SZ//2)

        # Obstacles
        for obs in self.obstacles:
            obs["x"]-=speed
            if not self.invincible:
                ox=obs["x"]
                in_top=(ccy-hbR<obs["top_h"]     and ccx+hbR>ox and ccx-hbR<ox+OBS_W)
                in_bot=(ccy+hbR>obs["top_h"]+gap and ccx+hbR>ox and ccx-hbR<ox+OBS_W)
                if in_top or in_bot: self.hit(now_ms)
            if not obs["near_played"] and 0<obs["x"]<160:
                if abs(ccy-(obs["top_h"]+gap/2))>gap/2-22:
                    obs["near_played"]=True; play("near")
            if not obs["passed"] and obs["x"]+OBS_W<ccx-hbR:
                obs["passed"]=True; self.score+=1; play("score")
        self.obstacles=[o for o in self.obstacles if o["x"]+OBS_W>0]

        # Collectibles
        for col in self.collectibles:
            if magnet:
                dx=ccx-col["x"]; dy=ccy-col["y"]; dist=math.hypot(dx,dy)
                if dist<160: col["x"]+=dx*0.12; col["y"]+=dy*0.12
                else: col["x"]-=speed
            else:
                col["x"]-=speed
            if not col["collected"]:
                if math.hypot(ccx-col["x"],ccy-col["y"])<hbR+16:
                    col["collected"]=True
                    rare=col["category"]=="RARE"; pts=5 if rare else 1 if col["category"]=="NORMAL" else 0
                    if col["category"]=="POWERUP" and col["sub_type"]:
                        dur={"SHIELD":3200,"SLOW":4200,"MAGNET":5200}.get(col["sub_type"],3000)
                        self.active_pups.append({"type":col["sub_type"],"end":now_ms+dur})
                        play("powerup")
                        self.eff_id+=1
                        self.effects.append({"x":col["x"],"y":col["y"],"t":now_ms,"rare":False,"pup":col["sub_type"]})
                    else:
                        self.combo+=1; play("combo")
                        old_m=self.multiplier
                        if self.combo>=15: self.multiplier=3.0
                        elif self.combo>=10: self.multiplier=2.0
                        elif self.combo>=5:  self.multiplier=1.5
                        if self.multiplier>old_m: play("mult_up")
                        final=int(pts*self.multiplier); self.score+=final
                        coins_earned=5 if rare else 1; self.coins+=coins_earned
                        play("rare" if rare else "collect")
                        self.eff_id+=1
                        self.effects.append({"x":col["x"],"y":col["y"],"t":now_ms,"rare":rare,"pup":None})
                        self.save_game()
        self.collectibles=[c for c in self.collectibles if not c["collected"] and c["x"]+60>0]
        self.effects=[e for e in self.effects if now_ms-e["t"]<500]

    def draw_game(self, surf, now_ms):
        # Sky
        draw_sky(surf, self.a_theme, VIRT_W, VIRT_H)

        # Distant islands
        draw_parallax_islands(surf, self.parallax["islands"], self.sel_char, VIRT_W, VIRT_H, now_ms)

        # Ocean
        draw_ocean(surf, self.parallax["ocean"], self.sel_char, self.char_vy, VIRT_W, VIRT_H, now_ms)

        # Clouds
        draw_clouds(surf, self.parallax["clouds"], self.sel_char, self.char_vx, VIRT_W, VIRT_H, now_ms)

        # Obstacles
        dc=self.diff_cfg(); gap=dc["gap"]
        for obs in self.obstacles:
            draw_obstacle_3d(surf, obs, gap, self.sel_char, now_ms)

        # Collectibles
        for col in self.collectibles:
            draw_collectible_3d(surf, col, now_ms)

        # Effects
        for e in self.effects: draw_effect(surf, e, now_ms)

        # Multiplier glow behind character
        ccx=int(62+self.char_vx+CHAR_SZ//2); ccy=int(self.char_y+CHAR_SZ//2)
        if self.multiplier>1:
            gc=[(255,220,60),(255,140,30),(255,50,50)][min(2,int(self.multiplier)-1)]
            draw_circle_glow(surf,ccx,ccy,42,gc,int(60+math.sin(now_ms/200)*15))

        # Power-up auras
        for p in self.active_pups:
            r=int(30+math.sin(now_ms/90)*5)
            ac={"SHIELD":CYAN,"SLOW":(150,180,255),"MAGNET":AMBER}.get(p["type"],WHITE)
            pygame.draw.circle(surf,ac,(ccx,ccy),r,3)

        # Trail
        for pt in self.trail:
            a=int(pt["op"]*255); r=max(1,int(pt["size"]*0.5))
            if self.a_trail=="sparkle_trail":
                ts=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
                pygame.draw.polygon(ts,(255,255,255,a),[(r,0),(r*2,r),(r,r*2),(0,r)])
                surf.blit(ts,(int(pt["x"])-r,int(pt["y"])-r))
            elif self.a_trail=="wind_trail":
                pygame.draw.line(surf,(255,255,255,max(0,int(a*0.4))),(int(pt["x"]),int(pt["y"])),(int(pt["x"])-22,int(pt["y"])),2)
            else:
                ts=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
                pygame.draw.circle(ts,(255,255,255,int(a*0.5)),(r,r),r)
                surf.blit(ts,(int(pt["x"])-r,int(pt["y"])-r))

        # Character
        blink=self.invincible and (now_ms//100)%2==0
        if not blink:
            if self.a_skin=="neon_skin":
                for dr in range(7,2,-2):
                    ns=pygame.Surface((100,100),pygame.SRCALPHA)
                    CHAR_DRAW_3D[self.sel_char](ns,50,50,self.char_rot,now_ms)
                    ns.set_alpha(35)
                    surf.blit(ns,(ccx-50-dr,ccy-50-dr))
            if self.sel_char=="DUCK":
                draw_duck_3d(surf,ccx,ccy,self.char_rot,now_ms,self.char_vy)
            else:
                CHAR_DRAW_3D[self.sel_char](surf,ccx,ccy,self.char_rot,now_ms)
            if self.a_skin=="stealth_skin":
                mask=pygame.Surface((100,100),pygame.SRCALPHA); mask.fill((0,0,0,120))
                surf.blit(mask,(ccx-50,ccy-50),special_flags=pygame.BLEND_RGBA_MULT)

        # Shadow on ground
        sh_a=max(15,int((0.22-(ccy/VIRT_H)*0.18)*255))
        sh=pygame.Surface((48,14),pygame.SRCALPHA)
        pygame.draw.ellipse(sh,(0,0,0,sh_a),(0,0,48,14))
        surf.blit(sh,(ccx-24,ccy+44))

        # HUD
        draw_hud_3d(surf,self.lives,self.score,self.coins,self.invincible,
                    self.combo,self.multiplier,self.active_pups,now_ms)

        # Toast
        draw_toast(surf,self.toast_msg,int(self.toast_alpha))

    def action(self):
        if self.state=="PLAYING":
            self.char_vy=PUSH_DOWN; play("flap")

    def handle_event(self, ev, now_ms):
        if ev.type==pygame.QUIT: self.running=False
        elif ev.type==pygame.VIDEORESIZE:
            global SCREEN_W,SCREEN_H,SCALE,CANVAS_W,CANVAS_H,OFF_X,OFF_Y,screen,_fnt
            SCREEN_W,SCREEN_H=ev.w,ev.h
            screen=pygame.display.set_mode((SCREEN_W,SCREEN_H),pygame.RESIZABLE)
            SCALE=min(SCREEN_W/VIRT_W,SCREEN_H/VIRT_H)
            CANVAS_W=int(VIRT_W*SCALE); CANVAS_H=int(VIRT_H*SCALE)
            OFF_X=(SCREEN_W-CANVAS_W)//2; OFF_Y=(SCREEN_H-CANVAS_H)//2
            _fnt.clear()

        elif ev.type==pygame.KEYDOWN:
            if ev.key in (pygame.K_SPACE,pygame.K_UP): self.action()
            elif ev.key in (pygame.K_ESCAPE,pygame.K_AC_BACK if hasattr(pygame,'K_AC_BACK') else pygame.K_ESCAPE):
                if self.state=="PLAYING": self.state="PAUSED"
                elif self.state=="PAUSED": self.state="PLAYING"
                elif self.state in ("CHAR_SELECT","DIFF_SELECT","SHOP"): self.state="START"
            elif ev.key==pygame.K_p:
                if self.state=="PLAYING": self.state="PAUSED"
                elif self.state=="PAUSED": self.state="PLAYING"
            elif ev.key==pygame.K_m: self.music_on=not self.music_on

        elif ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            self.action()

        # Android finger events
        elif ev.type==pygame.FINGERDOWN:
            self.action()

        elif ev.type==pygame.MOUSEWHEEL and self.state=="SHOP":
            self.shop_scroll=max(0,min(self.shop_total-VIRT_H+60,self.shop_scroll-ev.y*32))

    def click_on_canvas(self, cx, cy):
        """Call with canvas-space coordinates when a click/touch lands."""
        if self.state=="START":
            if VIRT_W//2-70<=cx<=VIRT_W//2+70 and 350<=cy<=398: self.state="CHAR_SELECT"
            elif VIRT_W//2-70<=cx<=VIRT_W//2+70 and 412<=cy<=454: self.state="SHOP"
        elif self.state=="CHAR_SELECT":
            if 10<=cx<=90 and 8<=cy<=40: self.state="START"
            for i,ch in enumerate(CHARACTERS):
                y=68+i*77
                if 18<=cx<=VIRT_W-18 and y<=cy<=y+68:
                    self.sel_char=ch["id"]; self.state="DIFF_SELECT"
        elif self.state=="DIFF_SELECT":
            if 10<=cx<=90 and 8<=cy<=40: self.state="CHAR_SELECT"
            diffs=list(DIFFICULTIES.keys())
            for i,d in enumerate(diffs):
                y=110+i*168
                if 30<=cx<=VIRT_W-30 and y<=cy<=y+150:
                    self.difficulty=d; self.reset(); self.state="PLAYING"
        elif self.state=="PAUSED":
            if VIRT_W//2-80<=cx<=VIRT_W//2+80:
                if 278<=cy<=326: self.state="PLAYING"
                elif 340<=cy<=384: self.state="START"
        elif self.state=="GAME_OVER":
            if VIRT_W//2-95<=cx<=VIRT_W//2+95:
                if 368<=cy<=418: self.reset(); self.state="PLAYING"
                elif 430<=cy<=476: self.state="START"
        elif self.state=="SHOP":
            if 10<=cx<=82 and 12<=cy<=44: self.state="START"
            else:
                actives={"SKINS":self.a_skin,"TRAILS":self.a_trail,"THEMES":self.a_theme}
                y0=64-self.shop_scroll
                for cat,items in SHOP_ITEMS.items():
                    y0+=30
                    for item in items:
                        if 16<=cx<=VIRT_W-16 and y0<=cy<=y0+52:
                            if item["id"] in self.unlocked:
                                if cat=="SKINS":  self.a_skin=item["id"]
                                elif cat=="TRAILS": self.a_trail=item["id"]
                                elif cat=="THEMES": self.a_theme=item["id"]
                                self.show_toast(f"✓ {item['name']} activated!")
                                self.save_game()
                            elif self.coins>=item["price"]:
                                self.coins-=item["price"]
                                self.unlocked.append(item["id"])
                                if cat=="SKINS":  self.a_skin=item["id"]
                                elif cat=="TRAILS": self.a_trail=item["id"]
                                elif cat=="THEMES": self.a_theme=item["id"]
                                self.show_toast(f"✅ {item['name']} unlocked!")
                                self.save_game()
                            else:
                                need=item["price"]-self.coins
                                self.show_toast(f"🪙 Need {need} more coins!")
                        y0+=58
                    y0+=10

# ═══════════════════════════════════════════════════════════════════════════════
# ── MAIN LOOP ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    game = Game()
    scaled = pygame.Surface((CANVAS_W, CANVAS_H))

    while game.running:
        now_ms = pygame.time.get_ticks()
        dt_ms  = clock.tick(FPS)

        for ev in pygame.event.get():
            game.handle_event(ev, now_ms)
            if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                mx,my=pygame.mouse.get_pos()
                cx,cy=(mx-OFF_X)/SCALE,(my-OFF_Y)/SCALE
                game.click_on_canvas(cx,cy)
            elif ev.type==pygame.FINGERDOWN:
                # Android touch
                cx=ev.x*SCREEN_W; cy=ev.y*SCREEN_H
                ccx=(cx-OFF_X)/SCALE; ccy=(cy-OFF_Y)/SCALE
                game.click_on_canvas(ccx,ccy)

        game.update(now_ms, dt_ms)
        if game.toast_alpha>0 and game.state!="PLAYING":
            game.toast_alpha=max(0,game.toast_alpha-3)

        # ── Draw to virtual canvas ──
        canvas.fill((30,40,60))

        if game.state=="START":
            ph,sh_=draw_start_screen(canvas,game.coins,game.highscore,now_ms)
        elif game.state=="CHAR_SELECT":
            draw_char_select(canvas,game.sel_char,now_ms)
        elif game.state=="DIFF_SELECT":
            draw_diff_screen(canvas,game.difficulty,now_ms)
        elif game.state in ("PLAYING","PAUSED","GAME_OVER"):
            game.draw_game(canvas,now_ms)
            if game.state=="PAUSED":
                r1,m1=draw_pause(canvas)
            elif game.state=="GAME_OVER":
                r1,m1=draw_game_over(canvas,game.score,game.highscore,now_ms)
        elif game.state=="SHOP":
            _,game.shop_total=draw_shop(canvas,game.coins,game.unlocked,
                                         game.a_skin,game.a_trail,game.a_theme,
                                         game.shop_scroll,now_ms)

        if game.state!="PLAYING":
            draw_toast(canvas,game.toast_msg,int(game.toast_alpha))

        # ── Scale canvas → screen ──
        screen.fill((15,15,25))
        if SCALE==1.0:
            screen.blit(canvas,(OFF_X,OFF_Y))
        else:
            pygame.transform.scale(canvas,(CANVAS_W,CANVAS_H),scaled)
            screen.blit(scaled,(OFF_X,OFF_Y))

        pygame.display.flip()

    game.save_game()
    pygame.quit()
    sys.exit()

if __name__=="__main__":
    main()
