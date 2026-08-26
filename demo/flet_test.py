"""Simple Flet test to verify Flet works."""
import flet as ft

def main(page: ft.Page):
    page.title = "Flet Test"
    page.add(ft.Text("Hello from Flet!", size=20))

ft.app(target=main, view=ft.WEB_BROWSER, port=8502)
