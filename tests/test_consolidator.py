from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from core.consolidator import (
    _extract_date_from_filename,
    consolidate_after_download,
    consolidate_files,
    consolidate_general,
    detect_collaborator,
    extract_collaborator_from_filename,
)


def _create_xlsx(path: Path, data: list[list] | None = None):
    """Helper: create a minimal XLSX file with optional data."""
    wb = Workbook()
    ws = wb.active
    if data:
        for row in data:
            ws.append(row)
    else:
        ws.append(["Time", "Mouse"])
        ws.append(["13:06", 10])
    wb.save(path)
    wb.close()


class TestExtractDateFromFilename:
    def test_standard_pattern(self):
        assert _extract_date_from_filename("Maria_2026-03-01.xlsx") == date(2026, 3, 1)

    def test_full_name_pattern(self):
        assert _extract_date_from_filename("Maria Isabel Carvalho_2026-12-25.xlsx") == date(2026, 12, 25)

    def test_no_date(self):
        assert _extract_date_from_filename("random_report.xlsx") is None

    def test_invalid_date(self):
        assert _extract_date_from_filename("Name_2026-13-40.xlsx") is None

    def test_date_only(self):
        assert _extract_date_from_filename("2026-03-01.xlsx") == date(2026, 3, 1)

    def test_duplicated_name_pattern(self):
        assert _extract_date_from_filename("CíntiaOliveiraPessôa_2026-03-01_CíntiaOliveiraPessôa.xlsx") == date(2026, 3, 1)
        assert _extract_date_from_filename("Ana Maria Areia Alves_2026-03-15_Ana Maria Areia Alves.xlsx") == date(2026, 3, 15)


class TestConsolidateFiles:
    def test_empty_list(self, tmp_path):
        assert consolidate_files([], "Test") is None

    def test_single_file_flat(self, tmp_path):
        f1 = tmp_path / "Test_2026-03-01.xlsx"
        _create_xlsx(f1, [["Time", "Mouse"], ["13:06", 10]])

        result = consolidate_files([f1], "Test")

        assert result is not None
        assert result.exists()
        assert result.name == "consolidado_Test_2026-03-01_2026-03-01.xlsx"

        wb = load_workbook(result)
        assert wb.sheetnames == ["Dados"]
        ws = wb["Dados"]
        # Header: Data | Time | Mouse
        assert ws.cell(1, 1).value == "Data"
        assert ws.cell(1, 2).value == "Time"
        assert ws.cell(1, 3).value == "Mouse"
        # Data row
        assert ws.cell(2, 1).value == "2026-03-01"
        assert ws.cell(2, 2).value == "13:06"
        assert ws.cell(2, 3).value == 10
        wb.close()

    def test_multiple_files_chronological_flat(self, tmp_path):
        f1 = tmp_path / "Test_2026-03-05.xlsx"
        f2 = tmp_path / "Test_2026-03-01.xlsx"
        f3 = tmp_path / "Test_2026-03-03.xlsx"
        _create_xlsx(f1, [["H"], ["Day5"]])
        _create_xlsx(f2, [["H"], ["Day1"]])
        _create_xlsx(f3, [["H"], ["Day3"]])

        result = consolidate_files([f1, f2, f3], "Test")

        assert result is not None
        wb = load_workbook(result)
        assert wb.sheetnames == ["Dados"]
        ws = wb["Dados"]
        # Header row
        assert ws.cell(1, 1).value == "Data"
        assert ws.cell(1, 2).value == "H"
        # Data in chronological order
        assert ws.cell(2, 1).value == "2026-03-01"
        assert ws.cell(2, 2).value == "Day1"
        assert ws.cell(3, 1).value == "2026-03-03"
        assert ws.cell(3, 2).value == "Day3"
        assert ws.cell(4, 1).value == "2026-03-05"
        assert ws.cell(4, 2).value == "Day5"
        wb.close()

    def test_cross_month(self, tmp_path):
        f1 = tmp_path / "Test_2026-02-28.xlsx"
        f2 = tmp_path / "Test_2026-03-01.xlsx"
        _create_xlsx(f1, [["H"], ["Feb"]])
        _create_xlsx(f2, [["H"], ["Mar"]])

        result = consolidate_files([f1, f2], "Test")
        assert result.name == "consolidado_Test_2026-02-28_2026-03-01.xlsx"

        wb = load_workbook(result)
        ws = wb["Dados"]
        assert ws.cell(2, 1).value == "2026-02-28"
        assert ws.cell(3, 1).value == "2026-03-01"
        wb.close()

    def test_filename_without_date_pattern(self, tmp_path):
        f1 = tmp_path / "random_report.xlsx"
        f2 = tmp_path / "another_file.xlsx"
        _create_xlsx(f1, [["H"], ["Data1"]])
        _create_xlsx(f2, [["H"], ["Data2"]])

        result = consolidate_files([f1, f2], "Test")

        assert result is not None
        wb = load_workbook(result)
        assert wb.sheetnames == ["Dados"]
        ws = wb["Dados"]
        # Date column is empty for undated files; sorted by name (another < random)
        assert ws.cell(2, 1).value in ("", None)
        assert ws.cell(2, 2).value == "Data2"
        assert ws.cell(3, 2).value == "Data1"
        wb.close()

    def test_output_in_specified_dir(self, tmp_path):
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        f1 = src_dir / "Test_2026-03-01.xlsx"
        _create_xlsx(f1)

        result = consolidate_files([f1], "Test", output_dir=out_dir)
        assert result.parent == out_dir

    def test_five_days_flat(self, tmp_path):
        files = []
        for day in range(1, 6):
            fp = tmp_path / f"User_2026-03-{day:02d}.xlsx"
            _create_xlsx(fp, [["H"], [f"Day{day}"]])
            files.append(fp)

        result = consolidate_files(files, "User")
        wb = load_workbook(result)
        assert wb.sheetnames == ["Dados"]
        ws = wb["Dados"]
        # 1 header + 5 data rows
        assert ws.max_row == 6
        for i in range(1, 6):
            assert ws.cell(i + 1, 1).value == f"2026-03-{i:02d}"
        wb.close()

    def test_consolidated_name_uses_real_dates(self, tmp_path):
        f1 = tmp_path / "User_2026-03-10.xlsx"
        f2 = tmp_path / "User_2026-03-15.xlsx"
        _create_xlsx(f1)
        _create_xlsx(f2)

        result = consolidate_files([f1, f2], "User")
        assert result.name == "consolidado_User_2026-03-10_2026-03-15.xlsx"

    def test_header_written_once(self, tmp_path):
        f1 = tmp_path / "T_2026-03-01.xlsx"
        f2 = tmp_path / "T_2026-03-02.xlsx"
        _create_xlsx(f1, [["Time", "Mouse"], ["13:06", 10]])
        _create_xlsx(f2, [["Time", "Mouse"], ["14:00", 5]])

        result = consolidate_files([f1, f2], "T")
        wb = load_workbook(result)
        ws = wb["Dados"]
        # Row 1 = header, rows 2-3 = data
        assert ws.max_row == 3
        assert ws.cell(1, 2).value == "Time"
        # No duplicate header
        assert ws.cell(2, 2).value == "13:06"
        assert ws.cell(3, 2).value == "14:00"
        wb.close()

    def test_header_only_file_skipped(self, tmp_path):
        """A file with only a header row (no data) should be skipped."""
        f1 = tmp_path / "T_2026-03-01.xlsx"
        f2 = tmp_path / "T_2026-03-02.xlsx"
        _create_xlsx(f1, [["Time", "Mouse"]])  # header only
        _create_xlsx(f2, [["Time", "Mouse"], ["14:00", 5]])

        result = consolidate_files([f1, f2], "T")
        wb = load_workbook(result)
        ws = wb["Dados"]
        assert ws.max_row == 2  # header + 1 data row
        assert ws.cell(2, 1).value == "2026-03-02"
        wb.close()

    def test_all_files_header_only_returns_none(self, tmp_path):
        f1 = tmp_path / "T_2026-03-01.xlsx"
        _create_xlsx(f1, [["Time"]])  # header only

        result = consolidate_files([f1], "T")
        assert result is None

    def test_summary_row_included(self, tmp_path):
        """Row 2 (day summary) should be included in the output."""
        f1 = tmp_path / "T_2026-03-01.xlsx"
        _create_xlsx(f1, [
            ["Time", "Mouse"],
            ["13:06 - 22:04 Total time worked 8h 59m", None],
            ["13:06", 10],
        ])

        result = consolidate_files([f1], "T")
        wb = load_workbook(result)
        ws = wb["Dados"]
        assert ws.max_row == 3  # header + summary + data
        assert "Total time worked" in str(ws.cell(2, 2).value)
        wb.close()


class TestConsolidateGeneral:
    def test_two_collaborators(self, tmp_path):
        # Create folders and files for two collaborators
        alice_dir = tmp_path / "Alice"
        alice_dir.mkdir()
        _create_xlsx(alice_dir / "Alice_2026-03-01.xlsx", [["H"], ["A1"]])
        _create_xlsx(alice_dir / "Alice_2026-03-02.xlsx", [["H"], ["A2"]])

        bob_dir = tmp_path / "Bob"
        bob_dir.mkdir()
        _create_xlsx(bob_dir / "Bob_2026-03-01.xlsx", [["H"], ["B1"]])

        result = consolidate_general(
            [("Alice", alice_dir), ("Bob", bob_dir)],
            tmp_path,
        )

        assert result is not None
        assert result.parent == tmp_path
        assert result.name == "consolidado_geral_2026-03-01_2026-03-02.xlsx"

        wb = load_workbook(result)
        assert wb.sheetnames == ["Dados"]
        ws = wb["Dados"]
        # Header
        assert ws.cell(1, 1).value == "Colaborador"
        assert ws.cell(1, 2).value == "Data"
        assert ws.cell(1, 3).value == "H"
        # Alice first (alphabetical), then Bob
        assert ws.cell(2, 1).value == "Alice"
        assert ws.cell(2, 2).value == "2026-03-01"
        assert ws.cell(3, 1).value == "Alice"
        assert ws.cell(3, 2).value == "2026-03-02"
        assert ws.cell(4, 1).value == "Bob"
        assert ws.cell(4, 2).value == "2026-03-01"
        wb.close()

    def test_single_collaborator_returns_none(self, tmp_path):
        alice_dir = tmp_path / "Alice"
        alice_dir.mkdir()
        _create_xlsx(alice_dir / "Alice_2026-03-01.xlsx", [["H"], ["A1"]])

        result = consolidate_general([("Alice", alice_dir)], tmp_path)
        assert result is None

    def test_excludes_consolidado_files(self, tmp_path):
        alice_dir = tmp_path / "Alice"
        alice_dir.mkdir()
        _create_xlsx(alice_dir / "Alice_2026-03-01.xlsx", [["H"], ["A1"]])
        _create_xlsx(alice_dir / "consolidado_Alice_2026-03-01_2026-03-01.xlsx", [["H"], ["C"]])

        bob_dir = tmp_path / "Bob"
        bob_dir.mkdir()
        _create_xlsx(bob_dir / "Bob_2026-03-01.xlsx", [["H"], ["B1"]])

        result = consolidate_general(
            [("Alice", alice_dir), ("Bob", bob_dir)],
            tmp_path,
        )

        wb = load_workbook(result)
        ws = wb["Dados"]
        # Should have 3 rows: header + Alice + Bob (no consolidado file)
        assert ws.max_row == 3
        wb.close()

    def test_alphabetical_order(self, tmp_path):
        z_dir = tmp_path / "Zara"
        z_dir.mkdir()
        _create_xlsx(z_dir / "Zara_2026-03-01.xlsx", [["H"], ["Z1"]])

        a_dir = tmp_path / "Ana"
        a_dir.mkdir()
        _create_xlsx(a_dir / "Ana_2026-03-01.xlsx", [["H"], ["A1"]])

        result = consolidate_general(
            [("Zara", z_dir), ("Ana", a_dir)],
            tmp_path,
        )

        wb = load_workbook(result)
        ws = wb["Dados"]
        assert ws.cell(2, 1).value == "Ana"
        assert ws.cell(3, 1).value == "Zara"
        wb.close()


class TestConsolidateAfterDownload:
    def test_no_dates(self, tmp_path):
        result = consolidate_after_download("Test", tmp_path, [])
        assert result is None

    def test_with_dates_flat(self, tmp_path):
        colab_name = "Maria"
        for day in [1, 2, 3]:
            fp = tmp_path / f"Maria_2026-03-{day:02d}.xlsx"
            _create_xlsx(fp)

        result = consolidate_after_download(
            colab_name, tmp_path, [date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)]
        )

        assert result is not None
        assert result.exists()
        assert result.name == "consolidado_Maria_2026-03-01_2026-03-03.xlsx"

        wb = load_workbook(result)
        assert wb.sheetnames == ["Dados"]
        ws = wb["Dados"]
        # header + 3 data rows (each file has header + 1 data row)
        assert ws.max_row == 4
        assert ws.cell(1, 1).value == "Data"
        assert ws.cell(2, 1).value == "2026-03-01"
        assert ws.cell(3, 1).value == "2026-03-02"
        assert ws.cell(4, 1).value == "2026-03-03"
        wb.close()

    def test_single_date(self, tmp_path):
        fp = tmp_path / "Solo_2026-03-15.xlsx"
        _create_xlsx(fp)

        result = consolidate_after_download("Solo", tmp_path, [date(2026, 3, 15)])

        assert result is not None
        wb = load_workbook(result)
        assert wb.sheetnames == ["Dados"]
        wb.close()


class TestExtractCollaboratorFromFilename:
    def test_standard_pattern(self):
        assert extract_collaborator_from_filename("Ana Maria Areia Alves_2026-03-01.xlsx") == "Ana Maria Areia Alves"

    def test_underscores_in_name(self):
        assert extract_collaborator_from_filename("Ana_Maria_Areia_Alves_2026-03-01.xlsx") == "Ana Maria Areia Alves"

    def test_no_date_pattern(self):
        assert extract_collaborator_from_filename("relatorio_março.xlsx") is None

    def test_duplicated_name_pattern(self):
        assert extract_collaborator_from_filename("Ana Maria Areia Alves_2026-03-01_Ana Maria Areia Alves.xlsx") == "Ana Maria Areia Alves"

    def test_single_word_name(self):
        assert extract_collaborator_from_filename("Ricardo_2026-03-01.xlsx") == "Ricardo"


class TestDetectCollaborator:
    KNOWN = [
        "Ana Maria Areia Alves",
        "Maria Isabel Carvalho",
        "Ricardo Passos Advocacia",
    ]

    def test_all_same_collaborator(self):
        files = [
            "Ana Maria Areia Alves_2026-03-01.xlsx",
            "Ana Maria Areia Alves_2026-03-02.xlsx",
            "Ana Maria Areia Alves_2026-03-03.xlsx",
        ]
        matched, warning = detect_collaborator(files, self.KNOWN)
        assert matched == "Ana Maria Areia Alves"
        assert warning is None

    def test_different_collaborators(self):
        files = [
            "Ana Maria Areia Alves_2026-03-01.xlsx",
            "Maria Isabel Carvalho_2026-03-02.xlsx",
        ]
        matched, warning = detect_collaborator(files, self.KNOWN)
        assert matched is None
        assert warning is not None
        assert "diferentes" in warning

    def test_no_pattern_match(self):
        files = ["relatorio_março.xlsx", "dados.xlsx"]
        matched, warning = detect_collaborator(files, self.KNOWN)
        assert matched is None
        assert warning is None

    def test_unknown_collaborator_fallback(self):
        files = ["Unknown Person_2026-03-01.xlsx"]
        matched, warning = detect_collaborator(files, self.KNOWN)
        assert matched is None
        assert warning is None

    def test_underscore_name_matches(self):
        files = ["Ana_Maria_Areia_Alves_2026-03-01.xlsx"]
        matched, warning = detect_collaborator(files, self.KNOWN)
        assert matched == "Ana Maria Areia Alves"
        assert warning is None

    def test_empty_list(self):
        matched, warning = detect_collaborator([], self.KNOWN)
        assert matched is None
        assert warning is None
