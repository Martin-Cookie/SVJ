# PRD_ACCEPTANCE — Playwright test scénáře

> **Klonovací spec, část 5/5 — Testovací scénáře pro ověření regenerace.**  
> Navigace: [README](README.md) · [PRD](PRD.md) · [PRD_DATA_MODEL](PRD_DATA_MODEL.md) · [PRD_MODULES](PRD_MODULES.md) · [PRD_UI](PRD_UI.md) · **PRD_ACCEPTANCE.md**

---

## Účel

Tyto scénáře ověří, že regenerovaná aplikace odpovídá PRD. Nejsou to unit testy — jsou to **end-to-end scénáře v prohlížeči**, které projdou celým workflow.

**Nástroj**: Playwright (Python varianta nebo přímo přes Claude Code Playwright MCP) nebo pytest + playwright-python.

**Spuštění**:
```bash
# Aplikace běží na http://localhost:8000
uvicorn app.main:app --reload --port 8000 &

# Scénáře pustit sekvenčně (DB se sdílí)
pytest tests/e2e/ -v
# nebo přes Claude Code s Playwright MCP
```

---

## Seed data

Před spuštěním scénářů vytvoř demo SVJ. Skript `tests/e2e/seed.py`:

```python
from app.database import SessionLocal
from app.models import (
    SvjInfo, SvjAddress, BoardMember, CodeListItem, EmailTemplate,
    Owner, Unit, OwnerUnit, OwnerType,
    SmtpProfile,
)
from app.utils import utcnow, build_name_with_titles, strip_diacritics

def seed():
    db = SessionLocal()
    
    # 1. SvjInfo
    svj = SvjInfo(
        name="SVJ Demo Dům",
        building_type="bytový dům",
        total_shares=10000,
        unit_count=20,
        vs_prefix="1098",
    )
    db.add(svj)
    db.flush()
    
    # 2. Adresy
    db.add(SvjAddress(svj_info_id=svj.id, address="Dlouhá 123, Praha 1, 110 00", order=0))
    
    # 3. Výbor
    db.add(BoardMember(name="Jan Novák", role="předseda", email="predseda@demo.cz", group="board"))
    db.add(BoardMember(name="Petr Novotný", role="člen", email="clen@demo.cz", group="board"))
    db.add(BoardMember(name="Marie Dvořáková", role="audit", email="audit@demo.cz", group="audit"))
    
    # 4. Code lists seed už běží v lifespan, ale můžeme přidat sekce
    for idx, section in enumerate(["A", "B", "C"]):
        db.add(CodeListItem(category="section", value=section, order=idx))
    
    # 5. 20 jednotek (10× byt v sekci A, 10× v sekci B)
    units = []
    for i in range(1, 11):
        u = Unit(
            unit_number=i,
            building_number="123",
            space_type="byt",
            section="A",
            address="Dlouhá 123",
            lv_number=100,
            room_count="2+kk",
            floor_area=50.0 + i,
            podil_scd=500.0 / 10000,  # = 0.05
        )
        db.add(u)
        units.append(u)
    for i in range(11, 21):
        u = Unit(
            unit_number=i,
            building_number="123",
            space_type="byt",
            section="B",
            address="Dlouhá 123",
            lv_number=100,
            room_count="3+1",
            floor_area=70.0 + i,
            podil_scd=500.0 / 10000,
        )
        db.add(u)
        units.append(u)
    db.flush()
    
    # 6. 20 vlastníků, 1:1 s jednotkami
    owners = []
    names = [
        ("Jan", "Novák"), ("Petr", "Svoboda"), ("Jana", "Dvořáková"), ("Marie", "Nováková"),
        ("Tomáš", "Černý"), ("Pavla", "Horáková"), ("Karel", "Procházka"), ("Eva", "Kučerová"),
        ("Martin", "Veselý"), ("Lenka", "Krejčová"),
        ("Václav", "Hájek"), ("Anna", "Růžičková"), ("Josef", "Marek"), ("Hana", "Pokorná"),
        ("Michal", "Pospíšil"), ("Zuzana", "Beneš"), ("Filip", "Fiala"), ("Petra", "Urbanová"),
        ("David", "Moravec"), ("Barbora", "Jelínková"),
    ]
    for i, (first, last) in enumerate(names):
        name_full = build_name_with_titles("", first, last)
        o = Owner(
            first_name=first, last_name=last,
            name_with_titles=name_full,
            name_normalized=strip_diacritics(name_full).lower(),
            owner_type=OwnerType.PHYSICAL,
            email=f"{first.lower()}.{last.lower()}@demo.cz",
            phone=f"+420 6000000{i:02d}",
            perm_city="Praha", perm_zip="110 00",
        )
        db.add(o)
        owners.append(o)
    db.flush()
    
    # 7. OwnerUnit 1:1
    for owner, unit in zip(owners, units):
        db.add(OwnerUnit(
            owner_id=owner.id, unit_id=unit.id,
            ownership_type="Výhradní",
            share=1.0,
            votes=int(unit.podil_scd * 10000),
        ))
    
    # 8. Testovací SMTP profil
    db.add(SmtpProfile(
        name="Test Gmail",
        smtp_host="smtp.gmail.com", smtp_port=587,
        smtp_user="test@example.com",
        smtp_password_b64="",
        smtp_from_name="SVJ Demo",
        smtp_from_email="test@example.com",
        smtp_use_tls=True,
        is_default=True,
    ))
    
    db.commit()
    print("✓ Seed hotov: 20 vlastníků, 20 jednotek, 3 členové výboru, 1 SMTP profil.")

if __name__ == "__main__":
    seed()
```

---

## Pattern každého scénáře

```python
from playwright.sync_api import Page, expect

def test_SCENARIO_NAME(page: Page):
    # Arrange
    page.goto("http://localhost:8000/MODUL")
    
    # Act
    page.click("...")
    page.fill("...", "value")
    
    # Assert
    expect(page.locator("...")).to_contain_text("expected")
    expect(page).to_have_url("...")
```

---

## Modul 1: Dashboard

### T-1.1 — Dashboard se načte s statistikami

```python
def test_dashboard_loads(page: Page):
    page.goto("http://localhost:8000/")
    
    # Titulek
    expect(page.locator("h1")).to_contain_text("Přehled")
    
    # 7 stat karet viditelné
    cards = page.locator(".stat-card")
    expect(cards).to_have_count(7)
    
    # Karta "Vlastníci" ukazuje 20
    owners_card = page.locator(".stat-card:has-text('Vlastníci')")
    expect(owners_card).to_contain_text("20")
    
    # Karta "Jednotky" ukazuje 20
    units_card = page.locator(".stat-card:has-text('Jednotky')")
    expect(units_card).to_contain_text("20")
```

### T-1.2 — Klik na kartu naviguje na seznam

```python
def test_dashboard_card_click(page: Page):
    page.goto("http://localhost:8000/")
    page.click(".stat-card:has-text('Vlastníci')")
    expect(page).to_have_url("http://localhost:8000/vlastnici")
```

### T-1.3 — Porovnání podílů

```python
def test_shares_breakdown(page: Page):
    page.goto("http://localhost:8000/prehled/rozdil-podilu")
    
    # Hlavička tabulky
    expect(page.locator("thead")).to_contain_text("Jednotka")
    expect(page.locator("thead")).to_contain_text("Deklarováno")
    expect(page.locator("thead")).to_contain_text("Evidence")
    expect(page.locator("thead")).to_contain_text("Rozdíl")
    
    # Počet řádků = 20
    expect(page.locator("tbody tr")).to_have_count(20)
```

---

## Modul 2: Vlastníci

### T-2.1 — Seznam vlastníků se zobrazí

```python
def test_owners_list(page: Page):
    page.goto("http://localhost:8000/vlastnici")
    expect(page.locator("h1")).to_contain_text("Vlastníci")
    expect(page.locator("tbody tr")).to_have_count(20)
    
    # Hlavička: sortovatelné sloupce
    expect(page.locator("thead a:has-text('Jméno')")).to_be_visible()
    expect(page.locator("thead a:has-text('E-mail')")).to_be_visible()
```

### T-2.2 — Search vlastníka (diacritics-insensitive)

```python
def test_owner_search(page: Page):
    page.goto("http://localhost:8000/vlastnici")
    
    # Hledat "dvorak" najde "Dvořáková"
    page.fill("input[name='q']", "dvorak")
    page.wait_for_timeout(500)  # delay 300ms + render
    
    # Jen 1 výsledek
    expect(page.locator("tbody tr")).to_have_count(1)
    expect(page.locator("tbody tr")).to_contain_text("Dvořáková")
```

### T-2.3 — Filtrační bublina "Fyzické osoby"

```python
def test_owner_filter_physical(page: Page):
    page.goto("http://localhost:8000/vlastnici")
    page.click("a:has-text('Fyzické')")
    
    # URL obsahuje filtr
    expect(page).to_have_url(re.compile(r"typ=fyzicke"))
    
    # Všechny záznamy jsou fyzické
    expect(page.locator("tbody tr")).to_have_count(20)
```

### T-2.4 — Detail vlastníka + back URL

```python
def test_owner_detail(page: Page):
    page.goto("http://localhost:8000/vlastnici")
    page.click("tbody tr:first-child a")
    
    # URL má back param
    expect(page).to_have_url(re.compile(r"/vlastnici/\d+.*back="))
    
    # Zpětná šipka
    expect(page.locator("a:has-text('Zpět na seznam vlastníků')")).to_be_visible()
    
    # 4-sloupcová info karta
    expect(page.locator("#identity-section")).to_be_visible()
    expect(page.locator("#contact-section")).to_be_visible()
    expect(page.locator("#perm-address-section")).to_be_visible()
    expect(page.locator("#corr-address-section")).to_be_visible()
    
    # Klik na zpět se vrátí na seznam
    page.click("a:has-text('Zpět')")
    expect(page).to_have_url(re.compile(r"/vlastnici\??"))
```

### T-2.5 — Inline edit kontaktů

```python
def test_owner_edit_contact(page: Page):
    page.goto("http://localhost:8000/vlastnici/1")
    
    # Klik Upravit u kontaktů
    page.click("#contact-section button:has-text('Upravit')")
    
    # Form partial se načte
    expect(page.locator("#contact-section input[name='email']")).to_be_visible()
    
    # Uložit
    page.fill("#contact-section input[name='email']", "novyemail@test.cz")
    page.click("#contact-section button:has-text('Uložit')")
    
    # Info partial zpět s novým emailem
    expect(page.locator("#contact-section")).to_contain_text("novyemail@test.cz")
```

### T-2.6 — Export do Excelu

```python
def test_owner_export(page: Page):
    page.goto("http://localhost:8000/vlastnici")
    
    # Download listener
    with page.expect_download() as download_info:
        page.click("a:has-text('Excel')")
    download = download_info.value
    
    # Filename má správný prefix + datum
    assert download.suggested_filename.startswith("vlastnici_")
    assert download.suggested_filename.endswith(".xlsx")
```

### T-2.7 — Vytvoření nového vlastníka

```python
def test_owner_create(page: Page):
    page.goto("http://localhost:8000/vlastnici")
    page.click("button:has-text('+ Nový')")
    
    # Inline form
    page.fill("input[name='first_name']", "Testovací")
    page.fill("input[name='last_name']", "Uživatel")
    page.fill("input[name='email']", "test@test.cz")
    page.select_option("select[name='owner_type']", "physical")
    page.click("button[type='submit']:has-text('Uložit')")
    
    # Redirect na detail
    expect(page).to_have_url(re.compile(r"/vlastnici/\d+"))
    expect(page.locator("h1")).to_contain_text("Uživatel Testovací")
```

---

## Modul 3: Jednotky

### T-3.1 — Seznam jednotek se řadí numericky

```python
def test_units_sort_numeric(page: Page):
    page.goto("http://localhost:8000/jednotky")
    
    # První řádek = unit 1, ne unit 10
    first_row = page.locator("tbody tr").first
    expect(first_row).to_contain_text(" 1 ")
```

### T-3.2 — Filtrace podle sekce

```python
def test_units_filter_section(page: Page):
    page.goto("http://localhost:8000/jednotky?sekce=A")
    expect(page.locator("tbody tr")).to_have_count(10)
```

### T-3.3 — Detail jednotky ukáže vlastníky

```python
def test_unit_detail_owners(page: Page):
    page.goto("http://localhost:8000/jednotky/1")
    
    # Info karta
    expect(page.locator(".unit-info")).to_be_visible()
    
    # Sekce vlastníků
    expect(page.locator(".owners-section")).to_contain_text("Novák")
    
    # Podíl %
    expect(page.locator(".share-cell")).to_contain_text("%")
```

---

## Modul 6: Hlasování

### T-6.1 — Vytvoření hlasování bez DOCX

```python
def test_voting_create_basic(page: Page):
    page.goto("http://localhost:8000/hlasovani/nova")
    
    page.fill("input[name='title']", "Testovací hlasování")
    page.fill("textarea[name='description']", "Popis")
    page.fill("input[name='start_date']", "2026-05-01")
    page.fill("input[name='end_date']", "2026-05-15")
    page.fill("input[name='quorum_threshold']", "50")  # % v UI
    page.click("button[type='submit']")
    
    expect(page).to_have_url(re.compile(r"/hlasovani/\d+"))
    expect(page.locator("h1")).to_contain_text("Testovací hlasování")
    
    # Kvórum zobrazí 50 %
    expect(page.locator(".quorum")).to_contain_text("50")
    
    # Status = DRAFT
    expect(page.locator(".status-badge")).to_contain_text("Koncept")
```

### T-6.2 — Generování lístků

```python
def test_voting_generate_ballots(page: Page, voting_id: int):
    page.goto(f"http://localhost:8000/hlasovani/{voting_id}")
    
    # Přidat bod hlasování
    page.click("button:has-text('+ Přidat bod')")
    page.fill("input[name='title']", "Schválit rekonstrukci střechy")
    page.click("button:has-text('Uložit')")
    
    # Generovat
    page.click("button:has-text('Generovat lístky')")
    
    # Přesměruje na seznam lístků
    expect(page).to_have_url(re.compile(rf"/hlasovani/{voting_id}/listky"))
    
    # 20 lístků (1 per vlastník)
    expect(page.locator("tbody tr")).to_have_count(20)
```

### T-6.3 — Zpracování lístku

```python
def test_voting_process_ballot(page: Page, voting_id: int, ballot_id: int):
    page.goto(f"http://localhost:8000/hlasovani/{voting_id}/zpracovani")
    
    # Najít lístek
    row = page.locator(f"tr[data-ballot-id='{ballot_id}']")
    
    # Zadat hlas pro každý bod
    row.locator("select[name*='vote_']").select_option("for")
    
    page.click("button:has-text('Uložit hlasy')")
    
    # Lístek je PROCESSED
    expect(row.locator(".status-badge")).to_contain_text("Zpracováno")
```

---

## Modul 7: Rozesílání

### T-7.1 — Vytvoření TaxSession (bez reálných PDF, jen smoke)

```python
def test_tax_create_session(page: Page):
    page.goto("http://localhost:8000/rozesilani/nova")
    expect(page.locator("h1")).to_contain_text("Nové rozesílání")
    
    # Upload jednoho dummy PDF
    page.set_input_files("input[type='file']", "tests/fixtures/dummy.pdf")
    page.click("button[type='submit']")
    
    # Redirect na procesování
    expect(page).to_have_url(re.compile(r"/rozesilani/\d+/procesování"))
```

### T-7.2 — Potvrdit vše matching

```python
def test_tax_confirm_all(page: Page, session_id: int):
    page.goto(f"http://localhost:8000/rozesilani/{session_id}")
    
    # Tlačítko "Potvrdit vše"
    page.click("button:has-text('Potvrdit vše')")
    
    # Všechny AUTO_MATCHED → CONFIRMED
    auto_matched = page.locator(".match-status:has-text('Auto match')")
    expect(auto_matched).to_have_count(0)
```

---

## Modul 11: Administrace

### T-11.1 — Uložit SvjInfo

```python
def test_svj_info_save(page: Page):
    page.goto("http://localhost:8000/sprava/svj-info")
    
    page.fill("input[name='name']", "SVJ Demo Dům — upraveno")
    page.fill("input[name='total_shares']", "10000")
    page.click("button[type='submit']:has-text('Uložit')")
    
    # Flash toast
    expect(page.locator(".flash-toast")).to_contain_text("uloženo")
    
    # Reload a ověř
    page.reload()
    expect(page.locator("input[name='name']")).to_have_value("SVJ Demo Dům — upraveno")
```

### T-11.2 — Vytvoření zálohy

```python
def test_backup_create(page: Page):
    page.goto("http://localhost:8000/sprava/zalohy")
    
    # Klik vytvořit
    page.click("button:has-text('Vytvořit zálohu')")
    
    # Flash toast
    expect(page.locator(".flash-toast")).to_contain_text("vytvořena")
    
    # Nová záloha v seznamu
    expect(page.locator(".backup-row").first).to_contain_text("svj_backup_")
```

### T-11.3 — Purge s confirm

```python
def test_purge_requires_confirm(page: Page):
    page.goto("http://localhost:8000/sprava/smazat")
    
    # Vyber kategorii
    page.check("input[name='categories'][value='activity_logs']")
    
    # Submit bez confirm → error
    page.click("button[type='submit']")
    expect(page.locator(".error")).to_be_visible()
    
    # S confirm
    page.fill("input[name='confirm']", "DELETE")
    page.click("button[type='submit']")
    expect(page.locator(".flash-toast")).to_contain_text("smazáno")
```

---

## Modul 12: Nastavení

### T-12.1 — Vytvořit SMTP profil

```python
def test_smtp_create(page: Page):
    page.goto("http://localhost:8000/nastaveni")
    
    page.click("button:has-text('+ Nový SMTP profil')")
    
    # Form partial
    page.fill("input[name='name']", "Test Yahoo")
    page.fill("input[name='smtp_host']", "smtp.mail.yahoo.com")
    page.fill("input[name='smtp_port']", "465")
    page.fill("input[name='smtp_user']", "test@yahoo.com")
    page.fill("input[name='smtp_password']", "secret123")
    page.fill("input[name='smtp_from_email']", "test@yahoo.com")
    page.click("button[type='submit']:has-text('Uložit')")
    
    # Nový profil v seznamu
    expect(page.locator(".smtp-profile:has-text('Test Yahoo')")).to_be_visible()
```

### T-12.2 — Test SMTP profil odeslání

```python
def test_smtp_test_send(page: Page, profile_id: int):
    page.goto("http://localhost:8000/nastaveni")
    
    profile_card = page.locator(f".smtp-profile[data-id='{profile_id}']")
    profile_card.locator("button:has-text('Test')").click()
    
    # Modal nebo form pro test email
    page.fill("input[name='test_email']", "me@example.com")
    page.click("button:has-text('Odeslat test')")
    
    # Flash (OK nebo error)
    expect(page.locator(".flash-toast")).to_be_visible()
```

---

## Modul 13: Platby

### T-13.1 — Matice plateb

```python
def test_payments_matrix(page: Page):
    page.goto("http://localhost:8000/platby/prehled?rok=2025")
    
    # Tabulka s jednotkami a měsíci
    expect(page.locator("thead")).to_contain_text("Leden")
    expect(page.locator("thead")).to_contain_text("Prosinec")
    
    # Jeden řádek per jednotka
    expect(page.locator("tbody tr")).to_have_count_greater_than(0)
```

### T-13.2 — Import bankovního výpisu (mock)

```python
def test_bank_statement_import(page: Page):
    page.goto("http://localhost:8000/platby/vypisy/import")
    
    page.set_input_files("input[type='file']", "tests/fixtures/fio_sample.csv")
    page.click("button[type='submit']")
    
    # Redirect na detail výpisu
    expect(page).to_have_url(re.compile(r"/platby/vypisy/\d+"))
    expect(page.locator("h1")).to_contain_text("Výpis")
```

---

## Modul 14: Vodoměry

### T-14.1 — Import odečtů

```python
def test_water_import(page: Page):
    page.goto("http://localhost:8000/vodometry/import")
    
    page.set_input_files("input[type='file']", "tests/fixtures/odectyc.xlsx")
    page.click("button[type='submit']")
    
    # Step 2: mapování
    expect(page).to_have_url(re.compile(r"/vodometry/import/.*mapovani|nahled"))
```

---

## Smoke scénáře (nutno projít pro Fáze 1 MVP)

### S-1 — Aplikace nastartuje a `/` vrátí 200

```python
def test_smoke_app_starts(page: Page):
    response = page.goto("http://localhost:8000/")
    assert response.status == 200
```

### S-2 — Sidebar obsahuje všechny moduly

```python
def test_smoke_sidebar_has_modules(page: Page):
    page.goto("http://localhost:8000/")
    sidebar = page.locator("aside")
    
    modules = [
        "Přehled", "Vlastníci", "Jednotky", "Nájemci", "Prostory",
        "Hlasování", "Rozesílání", "Platby", "Vodoměry",
        "Administrace", "Nastavení",
    ]
    for mod in modules:
        expect(sidebar).to_contain_text(mod)
```

### S-3 — Dark mode toggle

```python
def test_smoke_dark_mode(page: Page):
    page.goto("http://localhost:8000/")
    
    # Default light
    expect(page.locator("html")).not_to_have_class(re.compile("dark"))
    
    # Toggle
    page.click("button[data-theme-toggle]")
    expect(page.locator("html")).to_have_class(re.compile("dark"))
    
    # Reload → persistovat
    page.reload()
    expect(page.locator("html")).to_have_class(re.compile("dark"))
```

### S-4 — HTMX boost funguje

```python
def test_smoke_htmx_boost(page: Page):
    page.goto("http://localhost:8000/")
    
    # Klik na vlastníky — HTMX nahradí main, ne celou stránku
    page.click("a[href='/vlastnici']")
    expect(page).to_have_url("http://localhost:8000/vlastnici")
    
    # Sidebar se neznovu-načítá (HTMX boost target = main)
    # Toto ověří že URL se změnila ale sidebar je stále stejný DOM node
```

### S-5 — Error 404 zobrazí error.html

```python
def test_smoke_404(page: Page):
    response = page.goto("http://localhost:8000/neexistuje")
    assert response.status == 404
    expect(page.locator("h1")).to_contain_text("404")
    expect(page.locator("a:has-text('Zpět na přehled')")).to_be_visible()
```

---

## Doporučený postup spouštění scénářů

### Pro Fázi 1 (MVP skeleton)

Spustit **S-1 až S-5** (smoke). Pokud projdou, základní struktura funguje.

### Pro Fázi 2 (MVP moduly)

Spustit **T-1.x, T-2.x, T-3.x, T-11.x, T-12.x** (modul 1, 2, 3, 11, 12).

### Pro Fázi 3 (pokročilé moduly)

Spustit **T-6.x, T-7.x, T-13.x, T-14.x** (hlasování, rozesílání, platby, vodoměry).

### Pro kompletní ověření

Všechny T-* + S-*. Očekávaná doba: 15–30 min (s `pytest -n auto` pro paralelizaci).

---

## Manuální smoke check (bez Playwrightu)

Pro rychlou verifikaci po regeneraci můžeš projít ručně:

1. **Start**: `uvicorn app.main:app` — bez chyb?
2. **`/`**: načte se dashboard? 7 stat karet?
3. **`/vlastnici`**: tabulka s 20 vlastníky? Search "novak" funguje?
4. **`/vlastnici/1`**: detail s 4-sloupcovou info kartou?
5. **Inline edit**: klik "Upravit" u kontaktů → form → Uložit?
6. **Export**: klik "Excel" stáhne soubor?
7. **`/sprava`**: stránka administrace?
8. **`/sprava/zalohy`** → vytvořit zálohu → stáhnout → restore?
9. **Dark mode**: toggle v sidebaru funguje a persistuje?
10. **`/neexistuje`**: error.html se zobrazí?

Pokud všech 10 kroků projde bez chyby → MVP je hotovo.

---

## Fixture soubory pro import testy

Vytvoř `tests/fixtures/`:

| Soubor | Obsah | Použije |
|---|---|---|
| `owners_sample.xlsx` | 5 řádků: č.jednotky, jméno, email, telefon | T-2.9 (import vlastníků) |
| `contacts_sample.xlsx` | 5 řádků: jméno, email | T-2.11 (import kontaktů) |
| `fio_sample.csv` | 10 transakcí v Fio formátu | T-13.2 (bank import) |
| `prescriptions.docx` | Tabulka s předpisy | T-13 (import předpisů) |
| `odectyc.xlsx` | 10 řádků odečtů | T-14.1 (water import) |
| `voting_results.xlsx` | 20 řádků s hlasy | T-6 (voting import) |
| `sync_sample.csv` | 20 řádků SČD | T-9 (synchronizace) |
| `dummy.pdf` | Jedno-stránkové PDF | T-7 (tax upload) |

Doporučuji vytvořit je manuálně nebo Python skriptem `tests/fixtures/generate_fixtures.py`.

---

## Kritéria přijetí PRD (kontrolní seznam)

Před prohlášením "regenerace je hotova", ověř:

- [ ] Smoke (S-1 až S-5) projde.
- [ ] Každý modul má aspoň jeden test z T-* který projde.
- [ ] DB soubor vznikne, všech 30+ tabulek existuje (`sqlite3 data/svj.db ".tables"`).
- [ ] 87+ indexů existuje (`SELECT name FROM sqlite_master WHERE type='index'`).
- [ ] `/` zobrazí dashboard s 7 stat kartami.
- [ ] Sidebar obsahuje všech 14 modulů.
- [ ] Dark mode toggle funguje.
- [ ] Export vlastníků do Excelu stáhne soubor.
- [ ] Inline edit vlastníka (kontakty) funguje.
- [ ] 404 stránka zobrazí error.html.
- [ ] CLAUDE.md a UI_GUIDE.md jsou v `docs/`.
- [ ] README.md obsahuje instrukce pro spuštění.
- [ ] `pip install -e .` + `uvicorn app.main:app` nastartuje bez chyb.

---

## Konec PRD balíčku

Úspěšně jsi prošel všech 5 PRD souborů. Pokud jsi agent, který regeneruje projekt:

1. **Přečti** `PRD.md` → `PRD_DATA_MODEL.md` → `PRD_MODULES.md` → `PRD_UI.md` → `PRD_ACCEPTANCE.md` v tomto pořadí.
2. **Implementuj** skeleton (Fáze 1) → MVP moduly (Fáze 2) → pokročilé moduly (Fáze 3).
3. **Ověřuj** Playwright scénáři z tohoto souboru.
4. **Konzultuj** `appendices/CLAUDE.md` a `appendices/UI_GUIDE.md` při potřebě detailu.

Pokud jsi lidský vývojář nebo QA:

- PRD je úplný kontrakt. Co v něm je, musí být implementováno.
- Co v něm **není** (např. ACL, portál pro vlastníky) je mimo scope.
- Otázky k implementaci → GitHub issues v originálním repozitáři.
