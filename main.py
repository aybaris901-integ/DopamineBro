import flet as ft

def main(page: ft.Page):
    page.title = 'Sinapster'
    page.window.bgcolor = ft.Colors.TRANSPARENT
    page.bgcolor = ft.Colors.TRANSPARENT
    page.window.frameless = True
    page.window.always_on_top = True
    page.window.resizable = False
    page.window.width = 300
    page.window.height = 100

    content = ft.Container(
        content=ft.Text('Hello bro', size=20, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
        padding=20,
        border_radius=20,

    )
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.END

    page.add(content)
    page.add()
    page.update()

page.update()