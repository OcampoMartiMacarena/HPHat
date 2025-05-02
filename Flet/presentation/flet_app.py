import flet as ft
from flet import Icons, Colors
from .model_presenter import Presenter

class HatView(ft.Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.presenter = Presenter(self)
        self.mic_button = ft.IconButton(
            icon=Icons.MIC,
            icon_size=80,
            icon_color=Colors.WHITE,
            on_click=self.on_mic_click,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=100),
                padding=20,
                bgcolor=Colors.with_opacity(0.2, Colors.WHITE),
            )
        )

    def build(self):
        self.content = ft.SafeArea(
            ft.Container(
                bgcolor=Colors.BLACK,
                expand=True,
                alignment=ft.alignment.center,
                content=self.mic_button
            )
        )

    def on_mic_click(self, e):
        print("🟢 Mic button clicked")
        self.page.run_task(self._handle_recording)

    async def _handle_recording(self):
        try:
            self.mic_button.disabled = True
            self.mic_button.update()

            result = await self.presenter.capture_voice()
            if result:
                print("📝 Base64 del audio grabado (primeros 60 caracteres):")
                print(result[:60] + "...")

        except Exception as e:
            print(f"❌ Error en _handle_recording: {e}")
        finally:
            self.mic_button.disabled = False
            self.mic_button.update()

    def did_mount(self):
        print("✅ HatView montado")
