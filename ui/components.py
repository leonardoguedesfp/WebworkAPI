import customtkinter as ctk

from ui.styles import (
    BG_MAIN,
    BLUE_PRIMARY,
    BTN_HOVER,
    BTN_PRIMARY_BG,
    BTN_PRIMARY_FG,
    BTN_SECONDARY_BG,
    BTN_SECONDARY_FG,
    CHECKBOX_ACCENT,
    FONT_BODY,
    FONT_HEADER_SUBTITLE,
    FONT_HEADER_TITLE,
    FONT_SMALL,
    FONT_TITLE,
    HEADER_BG,
    HEADER_FG,
    INPUT_BG,
    INPUT_BORDER,
    NEUTRAL,
    SECTION_TITLE_COLOR,
)


class HeaderFrame(ctk.CTkFrame):
    """Top header bar with branding."""

    def __init__(self, master):
        super().__init__(master, fg_color=HEADER_BG, corner_radius=0)

        title = ctk.CTkLabel(
            self,
            text="Ricardo Passos Advocacia",
            font=FONT_HEADER_TITLE,
            text_color=HEADER_FG,
        )
        title.pack(pady=(12, 0))

        subtitle = ctk.CTkLabel(
            self,
            text="WebWork Downloader",
            font=FONT_HEADER_SUBTITLE,
            text_color=HEADER_FG,
        )
        subtitle.pack(pady=(0, 10))


class SectionLabel(ctk.CTkLabel):
    """Bold section title."""

    def __init__(self, master, text):
        super().__init__(
            master,
            text=text,
            font=FONT_TITLE,
            text_color=SECTION_TITLE_COLOR,
            anchor="w",
        )


class ColaboradorCheckboxList(ctk.CTkScrollableFrame):
    """Scrollable list of collaborator checkboxes."""

    def __init__(self, master, colaboradores):
        super().__init__(
            master,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            border_width=1,
            height=160,
        )
        self.vars: list[tuple[dict, ctk.BooleanVar]] = []

        self._checkboxes: list[ctk.CTkCheckBox] = []
        for colab in colaboradores:
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                self,
                text=f"{colab['nome']}  ({colab['id']})",
                variable=var,
                font=FONT_BODY,
                text_color=BLUE_PRIMARY,
                fg_color=CHECKBOX_ACCENT,
                hover_color=BTN_HOVER,
                border_color=NEUTRAL,
            )
            cb.pack(anchor="w", padx=8, pady=2)
            self.vars.append((colab, var))
            self._checkboxes.append(cb)

    def get_selected(self) -> list[dict]:
        return [colab for colab, var in self.vars if var.get()]

    def select_all(self):
        for _, var in self.vars:
            var.set(True)

    def deselect_all(self):
        for _, var in self.vars:
            var.set(False)

    def set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for cb in self._checkboxes:
            cb.configure(state=state)


class DateEntry(ctk.CTkEntry):
    """Simple date entry with DD/MM/YYYY placeholder behavior."""

    def __init__(self, master, default_text=""):
        super().__init__(
            master,
            font=FONT_BODY,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            text_color=BLUE_PRIMARY,
            width=130,
        )
        if default_text:
            self.insert(0, default_text)
