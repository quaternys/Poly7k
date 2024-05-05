import dataclasses, time
import pygame as pg
import numpy as np


# Skin & Option

class SkinImage:
    def __init__(self, skindir="./skin"):   # pygame.init() が必要
        self.judgeline  = pg.image.load(f"{skindir}/judgeline/equalnotes.png").convert()
        self.notes = [
            pg.image.load(f"{skindir}/notes/note1357.png").convert(),
            pg.image.load(f"{skindir}/notes/note246.png" ).convert(),
            pg.image.load(f"{skindir}/notes/note1357.png").convert(),
            pg.image.load(f"{skindir}/notes/note4.png"   ).convert(),
            pg.image.load(f"{skindir}/notes/note1357.png").convert(),
            pg.image.load(f"{skindir}/notes/note246.png" ).convert(),
            pg.image.load(f"{skindir}/notes/note1357.png").convert(),
        ]
        self.keyflash = pg.image.load(f"{skindir}/keyflash/blue.png").convert_alpha()
        self.keyflash = pg.transform.scale(self.keyflash, (67*1.5, 73*1.5))
        self.bomb = pg.image.load(f"{skindir}/bomb/Kakabomb.png").convert()
        self.bomb.set_colorkey(self.bomb.get_at((0, 0)))
        self.font = pg.font.Font(f"{skindir}/07にくまるフォント.otf", skin_config.winh//20)

@dataclasses.dataclass
class SkinConfig:
    win_wh = winw, winh = (1280, 720)
    judgeline_xywh = [100, 0.85*winh, 628, 35]
    notes_xywh = [
        [100, judgeline_xywh[1], 88, 35],
        [190, judgeline_xywh[1], 88, 35],
        [280, judgeline_xywh[1], 88, 35],
        [370, judgeline_xywh[1], 88, 35],
        [460, judgeline_xywh[1], 88, 35],
        [550, judgeline_xywh[1], 88, 35],
        [640, judgeline_xywh[1], 88, 35],
    ]
    bomb_wh = bombw, bombh = (400, 300)
    keyflash_wh = (67*1.5, 73*1.5)

@dataclasses.dataclass
class PlayOption:
    notes_display = 500
    judge_range = 0.08
    judge_offset = 0
    keys = ["s", "d", "f", "space", "j", "k", "l"]

skin_config = SkinConfig()
play_option = PlayOption()


# Beatmap / Scenes
PLAY_SCENE = 2

class Beatmap:
    def __init__(self, bpm=159, keys=7, max_measures=24, maxpoly=12, minpoly=2, offset_s=3):
        self.bpm = bpm
        self.keys = keys
        self.max_measures = max_measures
        self.maxpoly = maxpoly
        self.minpoly = minpoly
        self.offset_s = offset_s

        self.sec_per_measure = 4 * 60 / bpm
        self.polys = np.random.randint(minpoly, maxpoly, (keys, max_measures//4))   # iレーンj小節 = polys[i][j]分音符
        # self.polys[:, 0] = [0, 12, 0, 6, 0, 8, 0]   # 3人協力地帯
        self.polys = np.vstack(np.tile(self.polys.T, 4).reshape(max_measures//4, -1, keys)).T   # 4小節繰り返し

        self.times = [[] for _ in range(keys)]
        for lane in range(keys):
            for measure, poly in enumerate(self.polys[lane]):
                if poly > 0:
                    t = measure * self.sec_per_measure + np.linspace(0, self.sec_per_measure, poly, endpoint=False) + offset_s
                    self.times[lane].extend(t)
        self.ptrs = [0] * self.keys # 次に鳴らすべきノーツのインデックス

    def done(self, lane):
        return self.ptrs[lane] >= len(self.times[lane])

    def latency(self, input_time, lane):
        return input_time - self.times[lane][self.ptrs[lane]] - play_option.judge_offset

class PlayScene:
    def __init__(self, beatmap: Beatmap):
        self.beatmap = beatmap
        self.start_time = time.perf_counter()
        self.sounds = [pg.mixer.Sound(f"./skin/keysound/maou_se_inst_piano2_{n}{scale}.ogg") for n, scale in enumerate(["do", "re", "mi", "fa", "so", "ra", "si"], 1)]
        for sound in self.sounds:
            sound.set_volume(0.05)

        self.combo = 0
        self.judge = None   # 0/1
        self.latest_judgetime = -999
        self.bomb_t0 = [-1] * self.beatmap.keys # ボム開始時刻

    def draw(self, win: pg.Surface, img: SkinImage, current_time: float, downkeys: list, pressed_keys: list):
        input_time = current_time - self.start_time # 再生開始からの経過時間 (s)
        self.judge_miss(input_time)
        self.keypressed(downkeys, input_time)

        # 判定ライン
        win.blit(img.judgeline, skin_config.judgeline_xywh[:2])
        # ノーツ
        for lane, times_lane in enumerate(self.beatmap.times):
            for t in times_lane[self.beatmap.ptrs[lane]:]:
                y = skin_config.judgeline_xywh[1] * (1 + (input_time - t) / (1e-3 * play_option.notes_display))
                if y < 0:
                    break
                win.blit(img.notes[lane], (skin_config.notes_xywh[lane][0], y))
        # ボム
        for lane in range(self.beatmap.keys):
            t = int(min(input_time - self.bomb_t0[lane], 0.25) * 60) % 16
            if t != 15:
                x, y, w, h = skin_config.notes_xywh[lane]
                x = x + w//2 - skin_config.bombw//2
                y = skin_config.judgeline_xywh[1] + skin_config.judgeline_xywh[3]//2 - skin_config.bombh//2
                win.blit(img.bomb, (x, y), [skin_config.bombw*t, 0, skin_config.bombw, skin_config.bombh])
        # コンボ
        if self.combo == 0:
            win.blit(img.font.render(f"{self.combo}x", True, "red"), (0.7*skin_config.winw, 0.7*skin_config.winh))
        else:
            win.blit(img.font.render(f"{self.combo}x", True, "blue"), (0.7*skin_config.winw, 0.7*skin_config.winh))
        # キーフラッシュ
        for lane, key_name in enumerate(play_option.keys):
            if pressed_keys[pg.key.key_code(key_name)]:   # 押下中
                x, y, w, h = skin_config.notes_xywh[lane]
                x = x + w//2 - skin_config.keyflash_wh[0]//2
                y = skin_config.judgeline_xywh[1] + skin_config.judgeline_xywh[3] + (0 if lane%2 else skin_config.winh//40)
                win.blit(img.keyflash, (x, y))
        # info
        measures = self.get_current_measures(input_time)
        x, y, w, h = skin_config.judgeline_xywh
        # if measures < 4:    # 3人協力地帯用
        #     win.blit(img.font.render("発狂十段はこれができます", True, "white"), (0.6*skin_config.winw, y))
        # else:
        #     win.blit(img.font.render("あなた本当に人間ですか？", True, "white"), (0.6*skin_config.winw, y))
        #     win.blit(img.font.render("(Overjoy説)", True, "white"), (0.6*skin_config.winw, y+skin_config.winh//20))
        win.blit(img.font.render(f"{measures+1} 小節", True, "white"), (0.6*skin_config.winw, 0))
        win.blit(img.font.render(f"♪= {self.beatmap.bpm}", True, "white"), (0.8*skin_config.winw, 0))
        win.blit(img.font.render(":".join(f"{p}" for p in self.beatmap.polys[:, measures]), True, "white"), (0.6*skin_config.winw, 0.1*skin_config.winh))

    def judge_miss(self, input_time):
        for lane in range(self.beatmap.keys):
            if not self.beatmap.done(lane):
                latency = self.beatmap.latency(input_time, lane)
                if latency is not None:
                    if latency > play_option.judge_range:
                        self.beatmap.ptrs[lane] += 1

                        self.combo = 0
                        self.judge = 0
                        self.latest_judgetime = input_time

    # キー押下処理
    def keypressed(self, downkeys: list, input_time: float):
        downkeys_str = [pg.key.name(key) for key in downkeys]
        for lane in range(self.beatmap.keys):
            if play_option.keys[lane] in downkeys_str:  # 打鍵
                self.bomb_t0[lane] = -999   # 押下時はとりあえずボムをリセット
                # 音を鳴らす
                self.sounds[lane].play()
                # 判定
                if not self.beatmap.done(lane):
                    latency = self.beatmap.latency(input_time, lane)    # ターゲットノーツに対して入力がlatency秒遅い
                    if latency < -play_option.judge_range:          # 早すぎ
                        pass
                    elif abs(latency) < play_option.judge_range:    # 判定区間内ならインクリ
                        self.beatmap.ptrs[lane] += 1

                        self.combo += 1
                        self.judge = 0
                        self.latest_judgetime = input_time
                        self.bomb_t0[lane] = input_time

    def get_current_measures(self, input_time: float):
        measures = int((input_time-self.beatmap.offset_s) / self.beatmap.sec_per_measure)   # 現在の小節
        measures = min(max(0, measures), self.beatmap.max_measures-1)
        return measures

class EveryScene:
    def __init__(self):
        self.done = False
        self.main_scene = PLAY_SCENE

    def draw(self, current_time: float, downkeys: list):
        if pg.K_ESCAPE in downkeys: # ESCでアプリ終了
            self.done = True


if __name__ == "__main__":
    pg.init()
    pg.display.set_caption("無限3人協力地帯")
    win = pg.display.set_mode(skin_config.win_wh)
    img = SkinImage("./skin")
    clock = pg.time.Clock()
    pg.mixer.init()
    pg.mixer.set_num_channels(128)

    beatmap = Beatmap(80, 7, offset_s=3)
    every_scene = EveryScene()
    play_scene = PlayScene(beatmap)

    keypress_from = {}  # {key定数: [時刻, 長押しカウント]}
    for framecount in range(999999):
        current_time = time.perf_counter()
        pressed_keys = pg.key.get_pressed()
        downkeys = []
        for event in pg.event.get():
            if event.type == pg.QUIT:
                every_scene.done = True
            elif event.type == pg.KEYDOWN:
                downkeys.append(event.key)

        # 描画
        win.fill((0, 0, 0))
        if every_scene.main_scene == PLAY_SCENE:
            play_scene.draw(win, img, current_time, downkeys, pressed_keys)
        every_scene.draw(current_time, downkeys)

        clock.tick()
        pg.display.update()
        if every_scene.done:    # ゲーム終了
            break
        if pg.K_q in downkeys:  # リトライ
            beatmap = Beatmap(beatmap.bpm, beatmap.keys, beatmap.max_measures, beatmap.maxpoly, beatmap.minpoly, beatmap.offset_s)
            play_scene = PlayScene(beatmap)
    pg.quit()
