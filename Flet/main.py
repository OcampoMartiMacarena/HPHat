import flet as ft
from presentation.flet_app import HatView

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
    page.add(hat_view)

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")