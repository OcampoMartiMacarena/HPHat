import flet as ft
from flet import Icons, Colors
from .model_presenter import Presenter
from Service.dialogue_generator import reset_hat_session

class HatView(ft.Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.presenter = Presenter(self)
        self.is_active = False

        self.mic_button = ft.IconButton(
            icon=Icons.MIC,
            icon_size=80,
            icon_color=Colors.WHITE,
            on_click=self.toggle_microphone,
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

    def toggle_microphone(self, e):
        if not self.is_active:
            print("🟢 Micrófono activado - Comenzando diálogo continuo")
            self.is_active = True
            self.mic_button.icon = Icons.STOP
            self.update()
            reset_hat_session()  # Reiniciamos la sesión al comenzar una nueva conversación
            self.page.run_task(self.presenter.start_conversational_loop)
        else:
            print("🔴 Micrófono detenido por el usuario")
            self.presenter.stop_loop = True
            self.reset_microphone_state()

    def reset_microphone_state(self):
        """Reset the microphone button to its initial state"""
        self.is_active = False
        self.mic_button.icon = Icons.MIC
        self.update()

    def show_verdict(self, resultado):
        """Muestra el veredicto final del Sombrero Seleccionador en consola"""
        print(f"🏆 Veredicto final: {resultado}")

    def did_mount(self):
        print("✅ HatView montado")