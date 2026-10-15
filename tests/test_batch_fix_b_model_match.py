from bay_procedure import match_model_level


def _row(title):
    return {"title": title, "excerpt": "x", "page": 1}


def test_facr14_drops_facr08_book_when_covering_manual_present():
    rows = [
        _row("Furrion FACR08 Instruction Manual CCD-0008666"),
        _row("Furrion FACT12SA2-PS 8K Electronic Control IM CCD-0008666"),
        _row("Furrion Chill Rooftop AC Instruction Manual - FACR13/14/15 + FACT12 ADB + FACW12 Thermostat"),
    ]
    out = match_model_level(rows, "FACR14SA-BL")
    assert [r["title"] for r in out] == [rows[2]["title"]]


def test_no_covering_manual_keeps_pages():
    rows = [_row("Furrion FACR08 Instruction Manual CCD-0008666")]
    assert match_model_level(rows, "FACR14SA-BL") == rows


def test_facr08_job_keeps_facr08_book():
    rows = [
        _row("Furrion FACR08 Instruction Manual CCD-0008666"),
        _row("Furrion Chill Rooftop AC Instruction Manual - FACR13/14/15 + FACT12 ADB + FACW12 Thermostat"),
    ]
    out = match_model_level(rows, "FACR08HESA2-BL")
    assert out == [rows[0]]
