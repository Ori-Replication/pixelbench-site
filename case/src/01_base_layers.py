import math

sky = new_canvas(128, 128, '#55b9ee', name='sky')
sky.rect(0, 25, 128, 15, '#70caf2')
sky.rect(0, 40, 128, 11, '#92ddf5')
sky.circle(104, 17, 10, '#ffe88b')
sky.circle(104, 17, 8, '#fff5b7')
sky.circle(104, 17, 6, '#fffad9')

clouds = new_canvas(128, 128, name='clouds')
def cloud(x, y, w):
    clouds.rect(x, y, w, 4, '#d2edf8')
    clouds.rect(x + 2, y - 3, w - 5, 6, '#f4fbff')
    clouds.rect(x + 7, y - 6, 10, 7, '#ffffff')
    clouds.rect(x + 10, y - 8, 5, 3, '#ffffff')
    clouds.rect(x + 18, y - 3, 7, 4, '#ffffff')
    clouds.line(x + 4, y + 4, x + w - 5, y + 4, '#b0def3')
cloud(7, 20, 32)
cloud(48, 31, 27)
clouds.rect(0, 38, 14, 2, '#d2edf8')
clouds.rect(2, 36, 8, 3, '#f4fbff')
clouds.rect(114, 38, 14, 3, '#f4fbff')
clouds.rect(118, 35, 10, 4, '#ffffff')

water = new_canvas(128, 128, name='water')
water.rect(0, 50, 128, 78, '#226eb6')
water.rect(0, 54, 128, 7, '#2088c0')
water.rect(0, 61, 128, 8, '#199fbf')
water.rect(0, 69, 128, 10, '#22b9c1')
water.rect(0, 79, 128, 49, '#55cebf')
water.line(0, 50, 127, 50, '#3b92cb')
for y in range(53, 91):
    for x in range(128):
        h = (x * 71 + y * 37 + x * y * 13) % 389
        if h < 5 and x % 3 == 0:
            col = '#399bcf' if y < 61 else '#53ced7' if y < 72 else '#8be5d4'
            water.line(x, y, x + 2 + (h % 4), y, col)
for x, y, w in [(10,56,10),(34,59,8),(69,55,5),(106,59,8),(4,65,9),(42,67,10),(83,63,7),(112,68,10),(16,73,7),(57,72,8)]:
    water.line(x, y, x+w, y, '#8be5df' if y > 62 else '#58b9db')

sand = new_canvas(128, 128, name='shore')
shore = [int(93 - x * 0.13 + 2 * math.sin(x / 12)) for x in range(128)]
for x, y in enumerate(shore):
    sand.line(x, y, x, 127, '#edc775')
    sand.line(x, y + 5, x, 127, '#f6d58a')
    sand.line(x, y + 10, x, 127, '#ffdf96')
    sand.line(x, y - 2, x, y, '#d1f6df')
    sand.line(x, y - 3, x, y - 2, '#ffffff')
    if x % 9 < 4:
        sand.set(x, y + 1, '#ffffff')
    wy = y - 13 + int(math.sin(x / 9))
    water.line(x, wy, x, wy + 1, '#e9fff3')
    water.set(x, wy + 2, '#93e8d8')
    if x % 13 < 8:
        water.set(x, wy - 1, '#ffffff')
    if x % 17 < 5:
        water.set(x, y - 7, '#abecdc')
for y in range(85, 128):
    for x in range(128):
        h = (x * 43 + y * 101 + x * y * 7) % 587
        if y > shore[x] + 7 and h < 8:
            sand.line(x, y, x + (h % 2), y, '#e9bd72' if h < 4 else '#fff0b5')
scene = flatten([sky, clouds, water, sand], name='beach_base')
print(scene.stats_text())
