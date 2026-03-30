import os
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.consolidator import consolidate_after_download, consolidate_files
from core.date_utils import validate_dates
from core.downloader import DownloadResult, run_downloads, save_error_log
from core.token_parser import extract_token
from data.colaboradores import COLABORADORES
from ui.components import (
    ColaboradorCheckboxList,
    DateEntry,
    HeaderFrame,
    SectionLabel,
)
from ui.styles import (
    BG_MAIN,
    BLUE_PRIMARY,
    BODY_TEXT_COLOR,
    BTN_HOVER,
    BTN_PRIMARY_BG,
    BTN_PRIMARY_FG,
    BTN_REMOVE_BG,
    BTN_SECONDARY_BG,
    BTN_SECONDARY_FG,
    ERROR_COLOR,
    FONT_BODY,
    FONT_SMALL,
    FONT_TITLE,
    INPUT_BG,
    INPUT_BORDER,
    NEUTRAL,
    PROGRESS_BG,
    PROGRESS_FG,
    SUCCESS_COLOR,
    TAB_ACTIVE_BG,
    TAB_ACTIVE_FG,
    TAB_HOVER_BG,
    TAB_INACTIVE_BG,
    TAB_INACTIVE_FG,
    WARNING_COLOR,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
)


class WebWorkApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("light")

        self.title("WebWork Downloader — Ricardo Passos Advocacia")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=BG_MAIN)

        self._cancel_flag = False
        self._downloading = False
        self._active_tab = "download"

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # Header
        header = HeaderFrame(self)
        header.pack(fill="x")

        # --- Tab bar ---
        self._tab_bar = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        self._tab_bar.pack(fill="x", padx=16, pady=(8, 0))

        self._tab_download_btn = ctk.CTkButton(
            self._tab_bar,
            text="Baixar Relatórios",
            font=FONT_TITLE,
            fg_color=TAB_ACTIVE_BG,
            hover_color=TAB_HOVER_BG,
            text_color=TAB_ACTIVE_FG,
            corner_radius=6,
            width=200,
            height=36,
            command=lambda: self._switch_tab("download"),
        )
        self._tab_download_btn.pack(side="left", padx=(0, 4))

        self._tab_consolidate_btn = ctk.CTkButton(
            self._tab_bar,
            text="Consolidar Arquivos",
            font=FONT_TITLE,
            fg_color=TAB_INACTIVE_BG,
            hover_color=TAB_HOVER_BG,
            text_color=TAB_INACTIVE_FG,
            corner_radius=6,
            width=200,
            height=36,
            command=lambda: self._switch_tab("consolidate"),
        )
        self._tab_consolidate_btn.pack(side="left")

        # --- Tab content container ---
        self._tab_container = ctk.CTkFrame(self, fg_color=BG_MAIN)
        self._tab_container.pack(fill="both", expand=True, padx=0, pady=0)

        self._build_download_tab()
        self._build_consolidate_tab()

        # Show download tab by default
        self._switch_tab("download")

    # ------------------------------------------------------------------ #
    #  Download tab (Alteração 1 + 2)
    # ------------------------------------------------------------------ #

    def _build_download_tab(self):
        self._dl_frame = ctk.CTkScrollableFrame(
            self._tab_container, fg_color=BG_MAIN
        )
        main = self._dl_frame

        # --- URL Section ---
        SectionLabel(main, text="URL da Requisição").pack(
            anchor="w", pady=(8, 2)
        )
        self.url_entry = ctk.CTkEntry(
            main,
            placeholder_text="Cole aqui a URL completa do DevTools...",
            font=FONT_BODY,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            text_color=BLUE_PRIMARY,
        )
        self.url_entry.pack(fill="x", pady=(0, 8))

        # --- Colaboradores Section ---
        SectionLabel(main, text="Colaboradores").pack(anchor="w", pady=(4, 2))

        self._btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        self._btn_frame.pack(fill="x", pady=(0, 4))

        self._select_all_btn = ctk.CTkButton(
            self._btn_frame,
            text="Selecionar todos",
            font=FONT_BODY,
            fg_color=BTN_SECONDARY_BG,
            hover_color=BTN_HOVER,
            text_color=BTN_SECONDARY_FG,
            width=140,
            command=self._select_all,
        )
        self._select_all_btn.pack(side="left", padx=(0, 8))

        self._deselect_all_btn = ctk.CTkButton(
            self._btn_frame,
            text="Desmarcar todos",
            font=FONT_BODY,
            fg_color=BTN_SECONDARY_BG,
            hover_color=BTN_HOVER,
            text_color=BTN_SECONDARY_FG,
            width=140,
            command=self._deselect_all,
        )
        self._deselect_all_btn.pack(side="left")

        self.colab_list = ColaboradorCheckboxList(main, COLABORADORES)
        self.colab_list.pack(fill="x", pady=(0, 8))

        # --- Date Section ---
        SectionLabel(main, text="Período").pack(anchor="w", pady=(4, 2))

        date_frame = ctk.CTkFrame(main, fg_color="transparent")
        date_frame.pack(fill="x", pady=(0, 8))

        today = date.today()
        first_day = today.replace(day=1).strftime("%d/%m/%Y")
        today_str = today.strftime("%d/%m/%Y")

        ctk.CTkLabel(
            date_frame,
            text="De:",
            font=FONT_BODY,
            text_color=BODY_TEXT_COLOR,
        ).pack(side="left", padx=(0, 4))
        self.date_start = DateEntry(date_frame, default_text=first_day)
        self.date_start.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            date_frame,
            text="Até:",
            font=FONT_BODY,
            text_color=BODY_TEXT_COLOR,
        ).pack(side="left", padx=(0, 4))
        self.date_end = DateEntry(date_frame, default_text=today_str)
        self.date_end.pack(side="left")

        # --- Destination Folder ---
        SectionLabel(main, text="Pasta de Destino").pack(
            anchor="w", pady=(4, 2)
        )

        folder_frame = ctk.CTkFrame(main, fg_color="transparent")
        folder_frame.pack(fill="x", pady=(0, 8))

        # Default folder
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path.cwd()
        self._dest_folder = str(base / "WebWork_Downloads")

        self._choose_folder_btn = ctk.CTkButton(
            folder_frame,
            text="Escolher pasta",
            font=FONT_BODY,
            fg_color=BTN_SECONDARY_BG,
            hover_color=BTN_HOVER,
            text_color=BTN_SECONDARY_FG,
            width=130,
            command=self._choose_folder,
        )
        self._choose_folder_btn.pack(side="left", padx=(0, 8))

        self.folder_label = ctk.CTkLabel(
            folder_frame,
            text=self._dest_folder,
            font=FONT_SMALL,
            text_color=BODY_TEXT_COLOR,
            anchor="w",
        )
        self.folder_label.pack(side="left", fill="x", expand=True)

        # --- Action Button (Baixar / Cancelar — single button) ---
        action_frame = ctk.CTkFrame(main, fg_color="transparent")
        action_frame.pack(fill="x", pady=(8, 4))

        self.download_btn = ctk.CTkButton(
            action_frame,
            text="Baixar",
            font=FONT_TITLE,
            fg_color=BTN_PRIMARY_BG,
            hover_color=BTN_HOVER,
            text_color=BTN_PRIMARY_FG,
            width=160,
            height=40,
            command=self._on_main_button_click,
        )
        self.download_btn.pack(side="left", padx=(0, 8))

        # --- Progress ---
        self.progress_label = ctk.CTkLabel(
            main,
            text="",
            font=FONT_BODY,
            text_color=BODY_TEXT_COLOR,
            anchor="w",
        )
        self.progress_label.pack(fill="x", pady=(8, 2))

        self.progress_bar = ctk.CTkProgressBar(
            main,
            progress_color=PROGRESS_FG,
            fg_color=PROGRESS_BG,
            height=14,
        )
        self.progress_bar.pack(fill="x", pady=(0, 4))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            main,
            text="Pronto.",
            font=FONT_SMALL,
            text_color=BODY_TEXT_COLOR,
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(0, 4))

        # --- "Abrir pasta" button (hidden by default) ---
        self.open_folder_btn = ctk.CTkButton(
            main,
            text="Abrir pasta",
            font=FONT_BODY,
            fg_color=BTN_SECONDARY_BG,
            hover_color=BTN_HOVER,
            text_color=BTN_SECONDARY_FG,
            width=130,
            height=36,
            command=self._open_folder,
        )
        # Not packed yet — only shown after download completes

        # --- Message / Error area ---
        self.message_label = ctk.CTkLabel(
            main,
            text="",
            font=FONT_BODY,
            text_color=ERROR_COLOR,
            anchor="w",
            wraplength=660,
        )
        self.message_label.pack(fill="x", pady=(0, 2))

        # --- Warning label for truncated dates ---
        self.warning_label = ctk.CTkLabel(
            main,
            text="",
            font=FONT_BODY,
            text_color=WARNING_COLOR,
            anchor="w",
            wraplength=660,
        )
        self.warning_label.pack(fill="x", pady=(0, 2))

        # --- Error log text box (hidden by default) ---
        self.error_log_frame = ctk.CTkFrame(main, fg_color="transparent")
        self.error_log_label = ctk.CTkLabel(
            self.error_log_frame,
            text="Erros encontrados:",
            font=FONT_BODY,
            text_color=ERROR_COLOR,
            anchor="w",
        )
        self.error_log_label.pack(anchor="w")
        self.error_textbox = ctk.CTkTextbox(
            self.error_log_frame,
            font=FONT_SMALL,
            fg_color=INPUT_BG,
            text_color=ERROR_COLOR,
            border_color=INPUT_BORDER,
            border_width=1,
            height=120,
        )
        self.error_textbox.pack(fill="x")

    # ------------------------------------------------------------------ #
    #  Consolidate tab (Alteração 3)
    # ------------------------------------------------------------------ #

    def _build_consolidate_tab(self):
        self._cons_frame = ctk.CTkScrollableFrame(
            self._tab_container, fg_color=BG_MAIN
        )
        main = self._cons_frame

        SectionLabel(main, text="Selecionar Arquivos").pack(
            anchor="w", pady=(8, 2)
        )

        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 4))

        self._cons_select_btn = ctk.CTkButton(
            btn_frame,
            text="Selecionar arquivos",
            font=FONT_BODY,
            fg_color=BTN_SECONDARY_BG,
            hover_color=BTN_HOVER,
            text_color=BTN_SECONDARY_FG,
            width=180,
            command=self._cons_select_files,
        )
        self._cons_select_btn.pack(side="left")

        # File list area
        self._cons_files: list[Path] = []
        self._cons_file_list_frame = ctk.CTkScrollableFrame(
            main,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            border_width=1,
            height=140,
        )
        self._cons_file_list_frame.pack(fill="x", pady=(0, 8))

        self._cons_empty_label = ctk.CTkLabel(
            self._cons_file_list_frame,
            text="Nenhum arquivo selecionado.",
            font=FONT_SMALL,
            text_color=NEUTRAL,
        )
        self._cons_empty_label.pack(pady=8)

        # Collaborator selection
        SectionLabel(main, text="Colaborador").pack(anchor="w", pady=(4, 2))

        colab_names = [c["nome"] for c in COLABORADORES]
        self._cons_colab_var = ctk.StringVar(value="")
        self._cons_colab_dropdown = ctk.CTkOptionMenu(
            main,
            values=colab_names,
            variable=self._cons_colab_var,
            font=FONT_BODY,
            fg_color=INPUT_BG,
            button_color=BTN_SECONDARY_BG,
            button_hover_color=BTN_HOVER,
            text_color=BLUE_PRIMARY,
            dropdown_font=FONT_BODY,
            dropdown_fg_color=INPUT_BG,
            dropdown_text_color=BLUE_PRIMARY,
            dropdown_hover_color=BTN_HOVER,
            width=400,
        )
        self._cons_colab_dropdown.set("")
        self._cons_colab_dropdown.pack(anchor="w", pady=(0, 8))

        # Consolidate button
        self._cons_action_btn = ctk.CTkButton(
            main,
            text="Consolidar",
            font=FONT_TITLE,
            fg_color=BTN_PRIMARY_BG,
            hover_color=BTN_HOVER,
            text_color=BTN_PRIMARY_FG,
            width=160,
            height=40,
            command=self._cons_run,
        )
        self._cons_action_btn.pack(anchor="w", pady=(8, 4))

        # Status / result
        self._cons_status_label = ctk.CTkLabel(
            main,
            text="",
            font=FONT_BODY,
            text_color=BODY_TEXT_COLOR,
            anchor="w",
            wraplength=660,
        )
        self._cons_status_label.pack(fill="x", pady=(4, 2))

        # "Abrir pasta" button for consolidation result
        self._cons_open_folder_btn = ctk.CTkButton(
            main,
            text="Abrir pasta",
            font=FONT_BODY,
            fg_color=BTN_SECONDARY_BG,
            hover_color=BTN_HOVER,
            text_color=BTN_SECONDARY_FG,
            width=130,
            height=36,
            command=self._cons_open_folder,
        )
        # Not packed yet
        self._cons_result_path: Path | None = None

    # ------------------------------------------------------------------ #
    #  Tab switching
    # ------------------------------------------------------------------ #

    def _switch_tab(self, tab: str):
        if self._downloading and tab != self._active_tab:
            return  # don't switch tabs during download

        self._active_tab = tab

        # Update tab button styles
        if tab == "download":
            self._tab_download_btn.configure(fg_color=TAB_ACTIVE_BG, text_color=TAB_ACTIVE_FG)
            self._tab_consolidate_btn.configure(fg_color=TAB_INACTIVE_BG, text_color=TAB_INACTIVE_FG)
            self._cons_frame.pack_forget()
            self._dl_frame.pack(
                in_=self._tab_container, fill="both", expand=True, padx=16, pady=(0, 8)
            )
        else:
            self._tab_consolidate_btn.configure(fg_color=TAB_ACTIVE_BG, text_color=TAB_ACTIVE_FG)
            self._tab_download_btn.configure(fg_color=TAB_INACTIVE_BG, text_color=TAB_INACTIVE_FG)
            self._dl_frame.pack_forget()
            self._cons_frame.pack(
                in_=self._tab_container, fill="both", expand=True, padx=16, pady=(0, 8)
            )

    # ------------------------------------------------------------------ #
    #  Download tab actions
    # ------------------------------------------------------------------ #

    def _select_all(self):
        self.colab_list.select_all()

    def _deselect_all(self):
        self.colab_list.deselect_all()

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Escolher pasta de destino")
        if folder:
            self._dest_folder = folder
            self.folder_label.configure(text=folder)

    def _open_folder(self):
        folder = self._dest_folder
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        self._open_path(folder)

    @staticmethod
    def _open_path(path: str):
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _set_message(self, text, color=ERROR_COLOR):
        self.message_label.configure(text=text, text_color=color)

    def _set_warning(self, text):
        self.warning_label.configure(text=text)

    def _set_downloading(self, active: bool):
        self._downloading = active
        state = "disabled" if active else "normal"

        # Toggle main button appearance
        if active:
            self.download_btn.configure(
                text="Cancelar",
                fg_color=NEUTRAL,
                hover_color="#706c69",
            )
        else:
            self.download_btn.configure(
                text="Baixar",
                fg_color=BTN_PRIMARY_BG,
                hover_color=BTN_HOVER,
            )

        # Disable/enable input fields
        self.url_entry.configure(state=state)
        self.date_start.configure(state=state)
        self.date_end.configure(state=state)
        self._select_all_btn.configure(state=state)
        self._deselect_all_btn.configure(state=state)
        self._choose_folder_btn.configure(state=state)
        self.colab_list.set_enabled(not active)

        # Disable tab switching during download
        tab_state = "disabled" if active else "normal"
        self._tab_consolidate_btn.configure(state=tab_state)

    def _on_main_button_click(self):
        if self._downloading:
            self._cancel_download()
        else:
            self._start_download()

    def _start_download(self):
        self._set_message("")
        self._set_warning("")
        self.error_log_frame.pack_forget()
        self.open_folder_btn.pack_forget()

        # Validate URL
        url = self.url_entry.get().strip()
        if not url:
            self._set_message("Informe a URL da requisição do WebWork.")
            return
        try:
            token = extract_token(url)
        except ValueError as e:
            self._set_message(str(e))
            return

        # Validate collaborators
        selected = self.colab_list.get_selected()
        if not selected:
            self._set_message(
                "Selecione pelo menos um colaborador.", WARNING_COLOR
            )
            return

        # Validate dates
        try:
            _, date_result = validate_dates(
                self.date_start.get(), self.date_end.get()
            )
        except ValueError as e:
            self._set_message(str(e))
            return

        dates = date_result.dates

        # Show truncation warning if applicable
        if date_result.truncated and date_result.truncated_to:
            self._set_warning(
                "Datas futuras ignoradas. Downloads realizados até "
                f"{date_result.truncated_to.strftime('%d/%m/%Y')}."
            )

        dest = self._dest_folder
        os.makedirs(dest, exist_ok=True)

        self._cancel_flag = False
        self._set_downloading(True)
        self.progress_bar.set(0)
        self.progress_label.configure(text="Iniciando downloads...")
        self.status_label.configure(text="")

        def on_progress(current, total, msg):
            self.after(0, self._update_progress, current, total, msg)

        def should_cancel():
            return self._cancel_flag

        def on_colab_complete(colab_result):
            # Run consolidation for this collaborator
            if colab_result.success_dates and colab_result.colab_folder:
                self.after(
                    0,
                    self.status_label.configure,
                    {"text": f"Consolidando relatórios de {colab_result.colab_name}..."},
                )
                consolidate_after_download(
                    colab_name=colab_result.colab_name,
                    colab_folder=colab_result.colab_folder,
                    success_dates=colab_result.success_dates,
                )

        def worker():
            result = run_downloads(
                token=token,
                colaboradores=selected,
                dates=dates,
                dest_folder=dest,
                on_progress=on_progress,
                should_cancel=should_cancel,
                on_colab_complete=on_colab_complete,
            )
            self.after(0, self._on_complete, result)

        threading.Thread(target=worker, daemon=True).start()

    def _cancel_download(self):
        self._cancel_flag = True
        self.status_label.configure(text="Cancelando...")

    def _update_progress(self, current, total, msg):
        fraction = current / total if total > 0 else 0
        self.progress_bar.set(fraction)
        self.progress_label.configure(text=f"{current} de {total} arquivos")
        self.status_label.configure(text=msg)

    def _on_complete(self, result: DownloadResult):
        self._set_downloading(False)
        self.progress_bar.set(1.0)

        parts = [
            f"Baixados: {result.success}",
            f"Pulados: {result.skipped}",
            f"Erros: {len(result.errors)}",
        ]
        if result.cancelled:
            parts.append("(Cancelado pelo usuário)")
        summary = " | ".join(parts)
        self.status_label.configure(text=summary)

        if result.auth_failed:
            self._set_message(
                "Token inválido ou expirado. "
                "Faça login novamente no WebWork e capture uma nova URL."
            )

        if result.errors:
            self.error_log_frame.pack(fill="x", pady=(4, 4))
            self.error_textbox.delete("1.0", "end")
            for err in result.errors:
                self.error_textbox.insert(
                    "end",
                    f"{err['colaborador']} — {err['data']}: "
                    f"{err['motivo']}\n",
                )
            save_error_log(self._dest_folder, result.errors)

        if not result.errors and not result.cancelled:
            self.progress_label.configure(text="Concluído com sucesso!")

        # Show "Abrir pasta" button if at least 1 file was downloaded
        if result.success > 0:
            self.open_folder_btn.pack(anchor="w", pady=(4, 4))

    # ------------------------------------------------------------------ #
    #  Consolidate tab actions
    # ------------------------------------------------------------------ #

    def _cons_select_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Selecionar arquivos Excel",
            filetypes=[("Arquivos Excel", "*.xlsx")],
        )
        if not filepaths:
            return

        for fp_str in filepaths:
            fp = Path(fp_str)
            if fp not in self._cons_files and fp.suffix.lower() == ".xlsx":
                self._cons_files.append(fp)

        self._cons_refresh_file_list()

    def _cons_refresh_file_list(self):
        # Destroy all children
        for widget in self._cons_file_list_frame.winfo_children():
            widget.destroy()

        if not self._cons_files:
            self._cons_empty_label = ctk.CTkLabel(
                self._cons_file_list_frame,
                text="Nenhum arquivo selecionado.",
                font=FONT_SMALL,
                text_color=NEUTRAL,
            )
            self._cons_empty_label.pack(pady=8)
            return

        for i, fp in enumerate(self._cons_files):
            row = ctk.CTkFrame(self._cons_file_list_frame, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)

            ctk.CTkLabel(
                row,
                text=fp.name,
                font=FONT_SMALL,
                text_color=BLUE_PRIMARY,
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            remove_btn = ctk.CTkButton(
                row,
                text="✕",
                font=FONT_SMALL,
                fg_color=BTN_REMOVE_BG,
                hover_color=BTN_HOVER,
                text_color="#ffffff",
                width=28,
                height=24,
                command=lambda idx=i: self._cons_remove_file(idx),
            )
            remove_btn.pack(side="right", padx=(4, 0))

    def _cons_remove_file(self, index: int):
        if 0 <= index < len(self._cons_files):
            self._cons_files.pop(index)
            self._cons_refresh_file_list()

    def _cons_run(self):
        self._cons_status_label.configure(text="", text_color=BODY_TEXT_COLOR)
        self._cons_open_folder_btn.pack_forget()

        # Validate: need at least 2 files
        if len(self._cons_files) < 2:
            self._cons_status_label.configure(
                text="Selecione pelo menos 2 arquivos para consolidar.",
                text_color=WARNING_COLOR,
            )
            return

        # Validate: collaborator selected
        colab_name = self._cons_colab_var.get().strip()
        if not colab_name:
            self._cons_status_label.configure(
                text="Selecione um colaborador.",
                text_color=WARNING_COLOR,
            )
            return

        # Validate files exist and are valid xlsx
        valid_files: list[Path] = []
        for fp in self._cons_files:
            if fp.exists() and fp.suffix.lower() == ".xlsx":
                valid_files.append(fp)

        if len(valid_files) < 2:
            self._cons_status_label.configure(
                text="Menos de 2 arquivos válidos encontrados. Verifique os arquivos selecionados.",
                text_color=ERROR_COLOR,
            )
            return

        self._cons_status_label.configure(
            text="Consolidando...", text_color=BODY_TEXT_COLOR
        )
        self._cons_action_btn.configure(state="disabled")
        self._tab_download_btn.configure(state="disabled")

        def worker():
            try:
                result_path = consolidate_files(
                    files=valid_files,
                    colab_name=colab_name,
                )
                self.after(0, self._cons_on_complete, result_path, None)
            except Exception as e:
                self.after(0, self._cons_on_complete, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _cons_on_complete(self, result_path: Path | None, error: str | None):
        self._cons_action_btn.configure(state="normal")
        self._tab_download_btn.configure(state="normal")

        if error:
            self._cons_status_label.configure(
                text=f"Erro na consolidação: {error}",
                text_color=ERROR_COLOR,
            )
            return

        if result_path and result_path.exists():
            self._cons_result_path = result_path
            self._cons_status_label.configure(
                text=f"Consolidado gerado: {result_path.name}",
                text_color=SUCCESS_COLOR,
            )
            self._cons_open_folder_btn.pack(anchor="w", pady=(4, 4))
        else:
            self._cons_status_label.configure(
                text="Nenhum arquivo consolidado foi gerado.",
                text_color=WARNING_COLOR,
            )

    def _cons_open_folder(self):
        if self._cons_result_path and self._cons_result_path.parent.exists():
            self._open_path(str(self._cons_result_path.parent))
