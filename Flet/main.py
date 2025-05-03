import warnings
import os

# Suprimir warnings específicos
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*pkg_resources.*")
warnings.filterwarnings("ignore", message=".*PyType_Spec.*")

# Suprimir mensajes de pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

from presentation.flet_app import HatView
import flet as ft

def main(page: ft.Page):
    # Configure the page
    page.title = "Audio Recorder"
    page.window_width = 400
    page.window_height = 600
    page.window_resizable = True
    page.padding = 0
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    # Create and add the view
    hat_view = HatView(expand=True)
    hat_view.page = page  # para que .page esté disponible en el presenter
    hat_view.build()      # ⬅️ esta línea es clave
    page.add(hat_view)

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
