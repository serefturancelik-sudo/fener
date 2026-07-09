from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
import json
import os
import time
from datetime import datetime, timedelta

GOLD = (0.831, 0.686, 0.216, 1)
GOLD_BRIGHT = (0.957, 0.827, 0.369, 1)
GOLD_DIM = (0.541, 0.427, 0.122, 1)
BLACK = (0.024, 0.024, 0.024, 1)
BLACK_2 = (0.09, 0.09, 0.09, 1)
RED = (0.8, 0.3, 0.3, 1)

DAILY_LIMIT = 10
AD_SECONDS = 5
DAY_SECONDS = 86400

torch_available = False
camera_manager = None
camera_id = None

try:
    from jnius import autoclass, cast
    from android.permissions import request_permissions, Permission

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')

    activity = PythonActivity.mActivity
    camera_manager = cast(
        'android.hardware.camera2.CameraManager',
        activity.getSystemService(Context.CAMERA_SERVICE)
    )
    camera_ids = camera_manager.getCameraIdList()
    if len(camera_ids) > 0:
        camera_id = camera_ids[0]
        torch_available = True
except Exception:
    torch_available = False
    camera_manager = None
    camera_id = None


def request_android_permissions():
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.CAMERA])
    except Exception:
        pass


def set_torch_state(state):
    global torch_available
    if not torch_available or camera_manager is None or camera_id is None:
        return False
    try:
        camera_manager.setTorchMode(camera_id, state)
        return True
    except Exception:
        torch_available = False
        return False


class UsageStore:
    """
    Gunluk hak sayaci artik takvim tarihine degil, epoch (1970'ten beri gecen saniye)
    tabanli sabit 24 saatlik pencerelere gore calisiyor. Telefonun tarihi/saati
    degistirilse bile sunucu tipi epoch mantigi ayni kaldigi icin sayac hakkini
    manipüle etmek date string'i degistirmekten daha zor hale geliyor.
    """
    def __init__(self):
        try:
            base_dir = App.get_running_app().user_data_dir
        except Exception:
            base_dir = "."
        self.path = os.path.join(base_dir, "cipil_fener_usage.json")
        self.data = {
            "window_start": 0,
            "count": 0,
            "pro": False,
            "free_until_epoch": 0
        }
        self.load()

    def load(self):
        try:
            with open(self.path, "r") as f:
                loaded = json.load(f)
                self.data.update(loaded)
        except Exception:
            pass
        self._check_window_reset()

    def save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f)
        except Exception:
            pass

    def _now(self):
        return time.time()

    def _check_window_reset(self):
        now = self._now()
        start = self.data.get("window_start", 0)
        if start == 0:
            self.data["window_start"] = now
            self.data["count"] = 0
            self.save()
            return
        if now - start >= DAY_SECONDS:
            periods_passed = int((now - start) // DAY_SECONDS)
            self.data["window_start"] = start + periods_passed * DAY_SECONDS
            self.data["count"] = 0
            self.save()

    def is_pro(self):
        return bool(self.data.get("pro", False))

    def set_pro(self):
        self.data["pro"] = True
        self.save()

    def has_free_day(self):
        until_epoch = self.data.get("free_until_epoch", 0)
        return self._now() < until_epoch

    def grant_free_day(self):
        self.data["free_until_epoch"] = self._now() + DAY_SECONDS
        self.save()

    def seconds_until_reset(self):
        self._check_window_reset()
        start = self.data.get("window_start", self._now())
        return max(0, int(DAY_SECONDS - (self._now() - start)))

    def remaining(self):
        self._check_window_reset()
        return max(0, DAILY_LIMIT - self.data.get("count", 0))

    def can_use(self):
        if self.is_pro() or self.has_free_day():
            return True
        return self.remaining() > 0

    def register_use(self):
        self._check_window_reset()
        self.data["count"] = self.data.get("count", 0) + 1
        self.save()


class TorchButton(Widget):
    is_on = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(220), dp(220))
        self.bind(pos=self.redraw, size=self.redraw, is_on=self.redraw)
        self.redraw()

    def redraw(self, *args):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        with self.canvas:
            if self.is_on:
                Color(*GOLD_BRIGHT, 0.20)
                Ellipse(pos=(self.x - dp(24), self.y - dp(24)),
                         size=(self.width + dp(48), self.height + dp(48)))

            fill = GOLD_BRIGHT if self.is_on else BLACK_2
            Color(*fill)
            Ellipse(pos=self.pos, size=self.size)

            Color(*(GOLD_BRIGHT if self.is_on else GOLD_DIM))
            Line(circle=(cx, cy, self.width / 2), width=1.8)

            icon_color = BLACK if self.is_on else GOLD_DIM
            Color(*icon_color)
            RoundedRectangle(pos=(cx - dp(15), cy - dp(36)), size=(dp(30), dp(48)),
                              radius=[(dp(4), dp(4))] * 4)
            RoundedRectangle(pos=(cx - dp(23), cy + dp(12)), size=(dp(46), dp(24)),
                              radius=[(dp(6), dp(6))] * 4)

            lens = GOLD_DIM if self.is_on else BLACK_2
            Color(*lens)
            Ellipse(pos=(cx - dp(11), cy + dp(22)), size=(dp(22), dp(10)))

            if self.is_on:
                Color(*BLACK)
                Line(points=[cx - dp(10), cy + dp(40), cx - dp(20), cy + dp(58)], width=dp(2))
                Line(points=[cx, cy + dp(40), cx, cy + dp(62)], width=dp(2))
                Line(points=[cx + dp(10), cy + dp(40), cx + dp(20), cy + dp(58)], width=dp(2))


class PlanCard(BoxLayout):
    selected = BooleanProperty(False)
    title_text = StringProperty("")
    price_text = StringProperty("")

    def __init__(self, title_text, price_text, on_select, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = dp(58)
        self.padding = (dp(14), dp(6))
        self.title_text = title_text
        self.price_text = price_text
        self.on_select_cb = on_select

        self.title_label = Label(text=title_text, font_size=dp(14), bold=True,
                                  color=GOLD_BRIGHT, halign='left', valign='middle')
        self.price_label = Label(text=price_text, font_size=dp(11),
                                  color=GOLD_DIM, halign='left', valign='middle')
        self.title_label.bind(size=lambda w, *a: setattr(w, 'text_size', w.size))
        self.price_label.bind(size=lambda w, *a: setattr(w, 'text_size', w.size))
        self.add_widget(self.title_label)
        self.add_widget(self.price_label)

        self.bind(pos=self.redraw, size=self.redraw, selected=self.redraw)
        self.redraw()

    def redraw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            border = GOLD_BRIGHT if self.selected else GOLD_DIM
            Color(*(0.16, 0.13, 0.04, 1) if self.selected else BLACK_2)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[(dp(10), dp(10))] * 4)
            Color(*border)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(10)),
                 width=1.4 if self.selected else 1)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.on_select_cb(self)
            return True
        return super().on_touch_down(touch)


class ProBadge(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(130), dp(38))
        self.unlocked = False
        self.bind(pos=self.redraw, size=self.redraw)
        self.label = Label(text="PRO'YA GEC", font_size=dp(12), bold=True, color=BLACK)
        self.add_widget(self.label)
        self.bind(pos=self.update_label, size=self.update_label)
        self.redraw()

    def update_label(self, *args):
        self.label.pos = self.pos
        self.label.size = self.size

    def redraw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*GOLD_BRIGHT)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[(dp(19), dp(19))] * 4)

    def set_unlocked(self):
        self.unlocked = True
        self.label.text = "PRO AKTIF"

    def set_free_day(self):
        if not self.unlocked:
            self.label.text = "UCRETSIZ GUN"


class AdPopup(Popup):
    def __init__(self, on_reward, **kwargs):
        self.on_reward = on_reward
        self.seconds_left = AD_SECONDS
        self.rewarded = False

        root = FloatLayout()
        with root.canvas.before:
            Color(*BLACK)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[(dp(14), dp(14))] * 4)
        root.bind(pos=lambda w, *a: setattr(self._bg, 'pos', w.pos),
                  size=lambda w, *a: setattr(self._bg, 'size', w.size))

        center_box = BoxLayout(orientation='vertical', spacing=dp(10),
                                size_hint=(0.9, None), height=dp(160),
                                pos_hint={'center_x': 0.5, 'center_y': 0.5})
        ad_title = Label(text="[b]REKLAM OYNUYOR[/b]", markup=True, font_size=dp(15), color=GOLD_BRIGHT)
        self.countdown_label = Label(text=str(self.seconds_left), font_size=dp(40), bold=True, color=GOLD_BRIGHT)
        ad_sub = Label(text="Odulunu almak icin bekle", font_size=dp(11), color=GOLD_DIM)
        center_box.add_widget(ad_title)
        center_box.add_widget(self.countdown_label)
        center_box.add_widget(ad_sub)
        root.add_widget(center_box)

        close_btn = Widget(size_hint=(None, None), size=(dp(36), dp(36)),
                            pos_hint={'right': 0.96, 'top': 0.94})
        with close_btn.canvas:
            Color(*GOLD_DIM)
            Line(circle=(dp(18), dp(18), dp(17)), width=1.4)
        close_label = Label(text="X", font_size=dp(16), bold=True, color=GOLD_DIM,
                             size_hint=(None, None), size=(dp(36), dp(36)))
        close_btn.add_widget(close_label)
        close_btn.bind(pos=lambda w, *a: setattr(close_label, 'pos', w.pos))
        close_btn.bind(on_touch_down=self._on_close_touch)
        root.add_widget(close_btn)

        super().__init__(title='', separator_height=0, background_color=(0, 0, 0, 0.9),
                          size_hint=(0.85, 0.5), auto_dismiss=False, content=root, **kwargs)

        self._event = Clock.schedule_interval(self._tick, 1)

    def _tick(self, dt):
        self.seconds_left -= 1
        if self.seconds_left <= 0:
            self.countdown_label.text = "0"
            self._event.cancel()
            self.rewarded = True
            self.on_reward()
            self.dismiss()
        else:
            self.countdown_label.text = str(self.seconds_left)

    def _on_close_touch(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self._event.cancel()
            self.rewarded = False
            self.dismiss()
            return True
        return False


class RootLayout(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_plan = 'yearly'
        self.store = UsageStore()
        self.torch_was_on_before_pause = False

        with self.canvas.before:
            Color(*BLACK)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self.update_bg, size=self.update_bg)

        self.add_widget(self.build_brand())

        self.pro_badge = ProBadge(pos_hint={'center_x': 0.5, 'center_y': 0.68})
        self.pro_badge.bind(on_touch_down=self._on_badge_touch)
        self.add_widget(self.pro_badge)
        if self.store.is_pro():
            self.pro_badge.set_unlocked()
        elif self.store.has_free_day():
            self.pro_badge.set_free_day()

        self.torch_btn = TorchButton(pos_hint={'center_x': 0.5, 'center_y': 0.46})
        self.add_widget(self.torch_btn)

        self.status_label = Label(
            text="KAPALI", font_size=dp(12), color=GOLD_DIM,
            size_hint=(None, None), size=(dp(260), dp(30)),
            pos_hint={'center_x': 0.5, 'y': 0.13}
        )
        self.add_widget(self.status_label)

        self.trial_label = Label(
            text="", font_size=dp(11), color=GOLD_DIM,
            size_hint=(None, None), size=(dp(280), dp(26)),
            pos_hint={'center_x': 0.5, 'y': 0.08}
        )
        self.add_widget(self.trial_label)
        self.update_trial_label()

        self.bind(on_touch_down=self._on_touch)
        Clock.schedule_once(lambda dt: request_android_permissions(), 0.5)
        Clock.schedule_interval(lambda dt: self.update_trial_label(), 30)

    def update_trial_label(self):
        if self.store.is_pro():
            self.trial_label.text = "PRO uyelik aktif - sinirsiz kullanim"
        elif self.store.has_free_day():
            self.trial_label.text = "Ucretsiz gun aktif - sinirsiz kullanim"
        else:
            saat = self.store.seconds_until_reset() // 3600
            self.trial_label.text = "Kalan hak: {}/{}  -  Yenilenmeye {} saat".format(
                self.store.remaining(), DAILY_LIMIT, saat)

    def build_brand(self):
        wrap = BoxLayout(orientation='horizontal', spacing=dp(8),
                          size_hint=(None, None), size=(dp(190), dp(40)),
                          pos_hint={'right': 0.97, 'top': 0.975})

        logo = Widget(size_hint=(None, None), size=(dp(36), dp(36)))
        with logo.canvas:
            Color(*GOLD_BRIGHT)
            Ellipse(pos=(0, 0), size=(dp(36), dp(36)))
            Color(*BLACK)
            Line(circle=(dp(18), dp(18), dp(15)), width=dp(1.4))
        logo_label = Label(text="C", font_size=dp(18), bold=True, color=BLACK,
                            size_hint=(None, None), size=(dp(36), dp(36)))
        logo.add_widget(logo_label)

        text_box = BoxLayout(orientation='vertical', size_hint=(None, None), size=(dp(150), dp(36)))
        t1 = Label(text="[b]CIPIL DEBUG[/b]", markup=True, font_size=dp(13),
                   color=GOLD_BRIGHT, halign='right', valign='bottom')
        t2 = Label(text="LEVEL XL", font_size=dp(10), color=GOLD_DIM,
                   halign='right', valign='top')
        t1.bind(size=lambda w, *a: setattr(w, 'text_size', w.size))
        t2.bind(size=lambda w, *a: setattr(w, 'text_size', w.size))
        text_box.add_widget(t1)
        text_box.add_widget(t2)

        wrap.add_widget(logo)
        wrap.add_widget(text_box)
        return wrap

    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _on_badge_touch(self, instance, touch):
        if instance.collide_point(*touch.pos):
            if not instance.unlocked:
                self.open_paywall()
            return True
        return False

    def _on_touch(self, instance, touch):
        if self.torch_btn.collide_point(*touch.pos):
            self.toggle_torch()
            return True
        return False

    def toggle_torch(self):
        new_state = not self.torch_btn.is_on

        if new_state and not self.store.can_use():
            self.status_label.text = "DENEME HAKKI BITTI"
            self.status_label.color = RED
            self.open_paywall()
            return

        ok = set_torch_state(new_state)

        if not torch_available:
            self.status_label.text = "FENER BULUNAMADI"
            self.status_label.color = RED
            return

        if ok:
            self.torch_btn.is_on = new_state
            if new_state:
                if not self.store.is_pro() and not self.store.has_free_day():
                    self.store.register_use()
                self.status_label.text = "ACIK"
                self.status_label.color = GOLD_BRIGHT
            else:
                self.status_label.text = "KAPALI"
                self.status_label.color = GOLD_DIM
            self.update_trial_label()
        else:
            self.status_label.text = "IZIN GEREKLI"
            self.status_label.color = RED

    def open_paywall(self):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))

        with content.canvas.before:
            Color(*BLACK)
            self._pw_bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[(dp(16), dp(16))] * 4)
        content.bind(pos=lambda w, *a: setattr(self._pw_bg, 'pos', w.pos),
                     size=lambda w, *a: setattr(self._pw_bg, 'size', w.size))

        title = Label(text="[b]CIPIL DEBUG LEVEL XL PRO[/b]", markup=True,
                      font_size=dp(16), color=GOLD_BRIGHT, size_hint_y=None, height=dp(26))
        subtitle = Label(text="Gunluk 10 deneme hakkin bitti", font_size=dp(11),
                          color=GOLD_DIM, size_hint_y=None, height=dp(20))
        content.add_widget(title)
        content.add_widget(subtitle)

        cards_wrap = BoxLayout(orientation='vertical', spacing=dp(8), size_hint_y=None, height=dp(198))

        buy_label_ref = {}

        def refresh_buy_label():
            lbl = buy_label_ref.get('label')
            if lbl is None:
                return
            lbl.text = "REKLAMI IZLE" if self.selected_plan == 'daily' else "SATIN AL"

        def select_plan(card):
            self.selected_plan = card.plan_id
            daily_card.selected = (card.plan_id == 'daily')
            monthly_card.selected = (card.plan_id == 'monthly')
            yearly_card.selected = (card.plan_id == 'yearly')
            refresh_buy_label()

        daily_card = PlanCard("Gunluk", "Ucretsiz - reklam izle", select_plan)
        daily_card.plan_id = 'daily'
        monthly_card = PlanCard("Aylik", "0,01 TL / ay", select_plan)
        monthly_card.plan_id = 'monthly'
        yearly_card = PlanCard("Yillik", "0,99 TL / yil - en avantajli", select_plan)
        yearly_card.plan_id = 'yearly'
        yearly_card.selected = True

        cards_wrap.add_widget(daily_card)
        cards_wrap.add_widget(monthly_card)
        cards_wrap.add_widget(yearly_card)
        content.add_widget(cards_wrap)

        buy_btn = Widget(size_hint_y=None, height=dp(48))
        with buy_btn.canvas:
            Color(*GOLD_BRIGHT)
            buy_rect = RoundedRectangle(pos=buy_btn.pos, size=buy_btn.size, radius=[(dp(12), dp(12))] * 4)
        buy_btn.bind(pos=lambda w, *a: setattr(buy_rect, 'pos', w.pos),
                     size=lambda w, *a: setattr(buy_rect, 'size', w.size))
        buy_label = Label(text="SATIN AL", font_size=dp(14), bold=True, color=BLACK)
        buy_label_ref['label'] = buy_label
        buy_btn.add_widget(buy_label)
        buy_btn.bind(pos=lambda w, *a: setattr(buy_label, 'pos', w.pos),
                     size=lambda w, *a: setattr(buy_label, 'size', w.size))

        popup = Popup(title='', separator_height=0, background_color=(0, 0, 0, 0.85),
                      size_hint=(0.86, 0.68), auto_dismiss=True, content=content)

        def grant_free_day_reward():
            self.store.grant_free_day()
            self.pro_badge.set_free_day()
            self.update_trial_label()

        def on_buy(instance, touch):
            if not buy_btn.collide_point(*touch.pos):
                return False
            if self.selected_plan == 'daily':
                popup.dismiss()
                AdPopup(on_reward=grant_free_day_reward).open()
            else:
                self.store.set_pro()
                self.pro_badge.set_unlocked()
                self.update_trial_label()
                popup.dismiss()
            return True

        buy_btn.bind(on_touch_down=on_buy)
        content.add_widget(buy_btn)

        popup.open()

    def handle_pause(self):
        self.torch_was_on_before_pause = self.torch_btn.is_on
        if self.torch_btn.is_on:
            set_torch_state(False)

    def handle_resume(self):
        global torch_available, camera_manager, camera_id
        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            activity = PythonActivity.mActivity
            camera_manager = cast(
                'android.hardware.camera2.CameraManager',
                activity.getSystemService(Context.CAMERA_SERVICE)
            )
            camera_ids = camera_manager.getCameraIdList()
            if len(camera_ids) > 0:
                camera_id = camera_ids[0]
                torch_available = True
        except Exception:
            pass

        if self.torch_was_on_before_pause:
            ok = set_torch_state(True)
            self.torch_btn.is_on = ok
            self.status_label.text = "ACIK" if ok else "KAPALI"
            self.status_label.color = GOLD_BRIGHT if ok else GOLD_DIM

        self.update_trial_label()


class FenerApp(App):
    def build(self):
        Window.clearcolor = BLACK
        self.root_layout = RootLayout()
        return self.root_layout

    def on_pause(self):
        self.root_layout.handle_pause()
        return True

    def on_resume(self):
        self.root_layout.handle_resume()

    def on_stop(self):
        set_torch_state(False)


if __name__ == '__main__':
    FenerApp().run()
