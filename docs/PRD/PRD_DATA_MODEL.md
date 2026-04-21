# PRD_DATA_MODEL — Datový model

> **Klonovací spec, část 2/5 — Deterministická specifikace tabulek, sloupců, enumů, relací, indexů.**  
> Navigace: [README](README.md) · [PRD](PRD.md) · **PRD_DATA_MODEL.md** · [PRD_MODULES](PRD_MODULES.md) · [PRD_UI](PRD_UI.md) · [PRD_ACCEPTANCE](PRD_ACCEPTANCE.md)

---

## Konvence

- **Framework**: SQLAlchemy 2.0 `DeclarativeBase`, legacy query API.
- **Enumy**: dědí z `(str, enum.Enum)`. Členové **UPPERCASE**, hodnoty **lowercase anglicky**. Např. `DRAFT = "draft"`.
- **Sloupce**: `String(n)` (s explicitní délkou), `Integer`, `Float`, `Boolean`, `Date`, `DateTime`, `Text`, `Enum(MyEnum)`, `JSON` (kde to dává smysl, jinak `Text` s JSON obsahem).
- **Timestamps**:
  - Editovatelné entity: `created_at` + `updated_at`. `updated_at` má `onupdate=utcnow`.
  - Logy: jen `created_at`.
  - Speciální timestamp pro upozornění: `notified_at`, `water_notified_at`, `sent_at`, `received_at`, `processed_at` — explicitně v modelu.
  - Všechny defaults a onupdate volají `utcnow` z `app.utils`.
- **FK**: `ForeignKey("table.id")`. Povinné sloupce `index=True`.
- **Cascade**: parent→child `cascade="all, delete-orphan"`. Child→parent jen `back_populates`.
- **PK**: vždy `id = Column(Integer, primary_key=True)`.

### Importní pravidla (`app/models/__init__.py`)
- **Všechny modely, enumy a funkce (`log_activity`)** re-exportovat v `__init__.py` přes `from .common import *; ...`
- Mít explicitní `__all__` list se všemi 60+ symboly.
- Routery importují z `app.models`, **nikdy** z `app.models.specific_file`.

---

## Přehled — kompletní výčet

| Kategorie | Tabulka | Model | Účel |
|---|---|---|---|
| **SVJ metadata** | `svj_info` | SvjInfo | Jedna řádka s globálními nastaveními |
| | `svj_addresses` | SvjAddress | Adresy SVJ (může jich být víc) |
| | `board_members` | BoardMember | Členové výboru / audit |
| | `code_list_items` | CodeListItem | Číselníky (space_type, section, room_count, ownership_type) |
| | `email_templates` | EmailTemplate | Šablony e-mailů |
| **Vlastníci/jednotky** | `owners` | Owner | Fyzické/právnické osoby |
| | `units` | Unit | Byty/nebytové jednotky |
| | `owner_units` | OwnerUnit | Vlastnická práva s historií (valid_from/to) |
| | `proxies` | Proxy | Plné moci pro hlasování |
| **Hlasování** | `votings` | Voting | Hlasovací sessions |
| | `voting_items` | VotingItem | Body hlasování |
| | `ballots` | Ballot | Hlasovací lístky |
| | `ballot_votes` | BallotVote | Jednotlivé hlasy |
| **Rozesílání daní** | `tax_sessions` | TaxSession | Session daňových výpisů |
| | `tax_documents` | TaxDocument | Jednotlivé PDF |
| | `tax_distributions` | TaxDistribution | Matchování PDF→vlastník + status e-mailu |
| **Synchronizace** | `sync_sessions` | SyncSession | Session porovnání CSV vs DB |
| | `sync_records` | SyncRecord | Jednotlivé záznamy srovnání |
| **Kontrola podílů** | `share_check_sessions` | ShareCheckSession | Session kontroly |
| | `share_check_records` | ShareCheckRecord | Jednotlivé záznamy |
| | `share_check_column_mappings` | ShareCheckColumnMapping | Cache mapování sloupců |
| **Platby** | `variable_symbol_mappings` | VariableSymbolMapping | VS → jednotka/prostor |
| | `unit_balances` | UnitBalance | Počáteční zůstatky per rok |
| | `prescription_years` | PrescriptionYear | Rok předpisů |
| | `prescriptions` | Prescription | Předpis per jednotka/prostor/rok |
| | `prescription_items` | PrescriptionItem | Položka předpisu (kategorie) |
| | `bank_statements` | BankStatement | Bankovní výpis |
| | `bank_statement_column_mappings` | BankStatementColumnMapping | Cache mapování |
| | `payments` | Payment | Platba z výpisu |
| | `payment_allocations` | PaymentAllocation | Rozpad platby na víc jednotek |
| | `settlements` | Settlement | Vyúčtování per jednotka-rok |
| | `settlement_items` | SettlementItem | Položka vyúčtování |
| **Prostory/nájemci** | `spaces` | Space | Nebytové prostory |
| | `tenants` | Tenant | Nájemci |
| | `space_tenants` | SpaceTenant | Nájemní vztah |
| **SMTP** | `smtp_profiles` | SmtpProfile | SMTP profily |
| **Vodoměry** | `water_meters` | WaterMeter | Vodoměr |
| | `water_readings` | WaterReading | Odečet |
| **Logování** | `email_logs` | EmailLog | Historie e-mailů |
| | `email_bounces` | EmailBounce | Vrácené e-maily |
| | `import_logs` | ImportLog | Historie importů |
| | `activity_logs` | ActivityLog | Audit log |

**Celkem**: 30 tabulek, 25 modelů (některé sdílí soubor).

---

## ERD — klíčové vazby

```
Owner 1─┐
        ├─N─ OwnerUnit ─N─┐                        ┌─ WaterMeter ─N─ WaterReading
        │                  └─ Unit 1─┐             │
        └─N─ Ballot ─N─ BallotVote   │             │
              │              │        ├─1───── Unit ┘
              │              └─ VotingItem
              └─1 Voting
        
Owner ─N─ Proxy (grantor) + Proxy (holder)
Owner ─N─ TaxDistribution ─1─ TaxDocument ─1─ TaxSession
Owner ─N─ UnitBalance (opc) ─ Unit / Space
Owner ─N─ Payment (match result) ─1─ BankStatement
Owner ─1─ Tenant (optional link) ─N─ SpaceTenant ─1─ Space

PrescriptionYear ─N─ Prescription ─N─ PrescriptionItem
                               │
                               └─ Payment (allocate)
                                      │
                                      └─ PaymentAllocation (split)
Settlement ─1─ Unit + Owner
Settlement ─N─ SettlementItem

SvjInfo ─N─ SvjAddress
SyncSession ─N─ SyncRecord
ShareCheckSession ─N─ ShareCheckRecord
```

---

## Enumy

### OwnerType (`app/models/owner.py`)
```python
class OwnerType(str, enum.Enum):
    PHYSICAL = "physical"     # fyzická osoba
    LEGAL_ENTITY = "legal"    # právnická osoba
```

### VotingStatus, VoteValue, BallotStatus (`voting.py`)
```python
class VotingStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class VoteValue(str, enum.Enum):
    FOR = "for"               # PRO
    AGAINST = "against"       # PROTI
    ABSTAIN = "abstain"       # Zdržel se
    INVALID = "invalid"

class BallotStatus(str, enum.Enum):
    GENERATED = "generated"
    SENT = "sent"
    RECEIVED = "received"
    PROCESSED = "processed"
    INVALID = "invalid"
```

### MatchStatus, SendStatus, EmailDeliveryStatus (`tax.py`)
```python
class MatchStatus(str, enum.Enum):
    AUTO_MATCHED = "auto_matched"
    CONFIRMED = "confirmed"
    MANUAL = "manual"
    UNMATCHED = "unmatched"

class SendStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    SENDING = "sending"
    PAUSED = "paused"
    COMPLETED = "completed"

class EmailDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
```

### SyncStatus, SyncResolution (`sync.py`)
```python
class SyncStatus(str, enum.Enum):
    MATCH = "match"
    NAME_ORDER = "name_order"
    DIFFERENCE = "difference"
    MISSING_CSV = "missing_csv"
    MISSING_EXCEL = "missing_excel"

class SyncResolution(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_EDIT = "manual_edit"
    EXCHANGED = "exchanged"
```

### ShareCheckStatus, ShareCheckResolution (`share_check.py`)
```python
class ShareCheckStatus(str, enum.Enum):
    MATCH = "match"
    DIFFERENCE = "difference"
    MISSING_DB = "missing_db"
    MISSING_FILE = "missing_file"

class ShareCheckResolution(str, enum.Enum):
    PENDING = "pending"
    UPDATED = "updated"
    SKIPPED = "skipped"
```

### Platby (`payment.py`)
```python
class SymbolSource(str, enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"
    LEGACY = "legacy"

class BalanceSource(str, enum.Enum):
    MANUAL = "manual"
    IMPORT = "import"
    CARRYOVER = "carryover"

class PrescriptionCategory(str, enum.Enum):
    PROVOZNI = "provozni"
    FOND_OPRAV = "fond_oprav"
    SLUZBY = "sluzby"

class ImportStatus(str, enum.Enum):
    IMPORTED = "imported"
    PROCESSED = "processed"

class PaymentDirection(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class PaymentMatchStatus(str, enum.Enum):
    AUTO_MATCHED = "auto_matched"
    SUGGESTED = "suggested"
    MANUAL = "manual"
    UNMATCHED = "unmatched"

class SettlementStatus(str, enum.Enum):
    GENERATED = "generated"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
```

### SpaceStatus (`space.py`)
```python
class SpaceStatus(str, enum.Enum):
    RENTED = "rented"
    VACANT = "vacant"
    BLOCKED = "blocked"
```

### MeterType (`water_meter.py`)
```python
class MeterType(str, enum.Enum):
    COLD = "cold"             # SV — studená voda
    HOT = "hot"               # TV — teplá voda
```

### Logování (`common.py`)
```python
class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

class BounceType(str, enum.Enum):
    HARD = "hard"
    SOFT = "soft"
    UNKNOWN = "unknown"

class ActivityAction(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    STATUS_CHANGED = "status_changed"
    IMPORTED = "imported"
    EXPORTED = "exported"
    RESTORED = "restored"
```

---

## Modely podle souborů

### `app/models/common.py`

#### EmailLog — historie e-mailů
```python
class EmailLog(Base):
    __tablename__ = "email_logs"
    id = Column(Integer, primary_key=True)
    recipient_email = Column(String(200), nullable=False)
    recipient_name = Column(String(300))
    subject = Column(String(500), nullable=False)
    body_preview = Column(Text)
    status = Column(Enum(EmailStatus), default=EmailStatus.PENDING, index=True)
    error_message = Column(Text)
    module = Column(String(50), nullable=False, index=True)
    reference_id = Column(Integer, index=True)
    attachment_paths = Column(Text)           # JSON list of paths
    name_normalized = Column(String(300), index=True)  # for diacritics-insensitive search
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)
```

#### EmailBounce — vrácené e-maily
```python
class EmailBounce(Base):
    __tablename__ = "email_bounces"
    id = Column(Integer, primary_key=True)
    recipient_email = Column(String(200), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), index=True)
    email_log_id = Column(Integer, ForeignKey("email_logs.id"), index=True)
    bounce_type = Column(Enum(BounceType), default=BounceType.UNKNOWN, index=True)
    reason = Column(Text)
    diagnostic_code = Column(String(500))
    subject = Column(String(500))
    module = Column(String(50), index=True)
    reference_id = Column(Integer, index=True)
    bounced_at = Column(DateTime, index=True)
    imap_uid = Column(String(50), index=True)
    imap_message_id = Column(String(300))
    smtp_profile_name = Column(String(100))
    created_at = Column(DateTime, default=utcnow, index=True)
    
    owner = relationship("Owner", lazy="joined")
    email_log = relationship("EmailLog", lazy="joined")
```

#### ImportLog — historie importů
```python
class ImportLog(Base):
    __tablename__ = "import_logs"
    id = Column(Integer, primary_key=True)
    filename = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    import_type = Column(String(50), nullable=False, index=True)  # "owners", "contacts", "votes", ...
    rows_total = Column(Integer, default=0)
    rows_imported = Column(Integer, default=0)
    rows_skipped = Column(Integer, default=0)
    errors = Column(Text)                     # JSON list
    created_at = Column(DateTime, default=utcnow)
```

#### ActivityLog — audit log
```python
class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True)
    action = Column(Enum(ActivityAction), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)  # "owner", "unit", "voting", ...
    entity_id = Column(Integer, index=True)
    entity_name = Column(String(300))
    description = Column(String(500))
    module = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
```

#### Funkce `log_activity`
```python
def log_activity(
    db: Session,
    action: ActivityAction,
    entity_type: str,
    module: str,
    entity_id: int | None = None,
    entity_name: str | None = None,
    description: str | None = None,
) -> ActivityLog:
    """
    Přidá ActivityLog záznam. Volající MUSÍ následně commitnout session.
    """
    log = ActivityLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        description=description,
        module=module,
    )
    db.add(log)
    return log
```

---

### `app/models/administration.py`

#### SvjInfo — globální nastavení SVJ
```python
class SvjInfo(Base):
    __tablename__ = "svj_info"
    id = Column(Integer, primary_key=True)
    name = Column(String(300))
    building_type = Column(String(100))
    total_shares = Column(Integer)                   # z prohlášení, např. 10000
    unit_count = Column(Integer)
    
    # JSON mapování sloupců pro různé typy importů (Text, serializované)
    voting_import_mapping = Column(Text)
    owner_import_mapping = Column(Text)
    contact_import_mapping = Column(Text)
    balance_import_mapping = Column(Text)
    space_import_mapping = Column(Text)
    water_meter_import_mapping = Column(Text)
    
    # Nastavení rozesílání (globální default)
    send_batch_size = Column(Integer, default=10)
    send_batch_interval = Column(Integer, default=5)  # seconds between batches
    send_confirm_each_batch = Column(Boolean, default=False)
    send_test_email_address = Column(String(200))
    
    # Stav test flags
    water_test_passed = Column(Boolean, default=False)
    
    smtp_profile_id = Column(Integer, ForeignKey("smtp_profiles.id"), index=True)
    
    # Prefix pro variabilní symboly
    vs_prefix = Column(String(10), default="1098")
    
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    addresses = relationship(
        "SvjAddress",
        back_populates="svj_info",
        order_by="SvjAddress.address",
        cascade="all, delete-orphan",
    )
```

#### SvjAddress
```python
class SvjAddress(Base):
    __tablename__ = "svj_addresses"
    id = Column(Integer, primary_key=True)
    svj_info_id = Column(Integer, ForeignKey("svj_info.id"), nullable=False, index=True)
    address = Column(String(300), nullable=False)
    order = Column(Integer, default=0)
    
    svj_info = relationship("SvjInfo", back_populates="addresses")
```

#### BoardMember
```python
class BoardMember(Base):
    __tablename__ = "board_members"
    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    role = Column(String(200))
    email = Column(String(200))
    phone = Column(String(50))
    group = Column(String(50), nullable=False, default="board", index=True)  # "board" | "audit"
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
```

#### CodeListItem
```python
class CodeListItem(Base):
    __tablename__ = "code_list_items"
    id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False, index=True)  # "space_type", "section", "room_count", "ownership_type"
    value = Column(String(200), nullable=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    
    __table_args__ = (
        UniqueConstraint("category", "value", name="ix_code_list_category_value"),
    )
```

**Seed data** (při prvním startu přes `_seed_code_lists()`):
- `space_type`: ["byt", "garážové stání", "sklep", "nebytový prostor", "ateliér", "kancelář"]
- `section`: [žádné — přidává uživatel dle svého domu]
- `room_count`: ["1+kk", "1+1", "2+kk", "2+1", "3+kk", "3+1", "4+kk", "4+1", "5+kk", "5+1"]
- `ownership_type`: ["SJM", "VL", "SJVL", "Výhradní", "Podílové", "Neuvedeno"]

#### EmailTemplate
```python
class EmailTemplate(Base):
    __tablename__ = "email_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    subject_template = Column(String(500), nullable=False)
    body_template = Column(Text, nullable=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
```

**Seed data** (při prvním startu přes `_seed_email_templates()`):
- "Daňové rozúčtování" — subject `"Daňové rozúčtování za rok {{ year }}"`, body s přílohou
- "Upozornění na nesrovnalost platby" — subject `"Nesrovnalost platby VS {{ vs }}"`, body
- "Odečty vodoměrů" — subject `"Odečty vodoměrů SV/TV {{ period }}"`, body

---

### `app/models/owner.py`

#### Owner
```python
class Owner(Base):
    __tablename__ = "owners"
    id = Column(Integer, primary_key=True)
    
    # Jméno
    first_name = Column(String(200), nullable=False, index=True)
    last_name = Column(String(200), index=True)
    title = Column(String(50))                       # "Ing.", "Mgr." atd.
    name_with_titles = Column(String(300), nullable=False, index=True)  # formát: "titul příjmení jméno"
    name_normalized = Column(String(300), nullable=False, index=True)    # bez diakritiky, lowercase
    
    owner_type = Column(Enum(OwnerType), nullable=False, default=OwnerType.PHYSICAL, index=True)
    
    # Identifikace
    birth_number = Column(String(20), index=True)    # rodné číslo (fyzická)
    company_id = Column(String(20))                  # IČO (právnická)
    
    # Trvalá adresa
    perm_street = Column(String(200))
    perm_district = Column(String(100))
    perm_city = Column(String(100), index=True)
    perm_zip = Column(String(20))
    perm_country = Column(String(50))
    
    # Korespondenční adresa
    corr_street = Column(String(200))
    corr_district = Column(String(100))
    corr_city = Column(String(100))
    corr_zip = Column(String(20))
    corr_country = Column(String(50))
    
    # Kontakty
    phone = Column(String(50), index=True)
    phone_landline = Column(String(50))
    phone_secondary = Column(String(50))
    email = Column(String(200), index=True)
    email_secondary = Column(String(200))
    email_invalid = Column(Boolean, default=False, index=True)     # hard bounce detected
    email_invalid_reason = Column(String(500))
    
    # Timestamps
    water_notified_at = Column(DateTime)             # poslední odeslané vodní upozornění
    owner_since = Column(String(50))                 # text, např. "od 2015"
    note = Column(Text)
    data_source = Column(String(50), default="excel")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    units = relationship("OwnerUnit", back_populates="owner", cascade="all, delete-orphan")
    ballots = relationship("Ballot", back_populates="owner", cascade="all, delete-orphan")
    tax_distributions = relationship("TaxDistribution", back_populates="owner", cascade="all, delete-orphan")
    given_proxies = relationship(
        "Proxy", foreign_keys="[Proxy.grantor_id]",
        back_populates="grantor", cascade="all, delete-orphan",
    )
    received_proxies = relationship(
        "Proxy", foreign_keys="[Proxy.proxy_holder_id]",
        back_populates="proxy_holder", cascade="all, delete-orphan",
    )
    
    @property
    def display_name(self) -> str:
        """Formát: titul příjmení jméno."""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.last_name:
            parts.append(self.last_name)
        if self.first_name:
            parts.append(self.first_name)
        return " ".join(parts) or self.name_with_titles
    
    @property
    def current_units(self) -> list["OwnerUnit"]:
        """Aktuální jednotky (valid_to IS NULL)."""
        return sorted(
            [ou for ou in self.units if ou.valid_to is None],
            key=lambda ou: ou.unit.unit_number if ou.unit else 0,
        )
    
    @property
    def historical_units(self) -> list["OwnerUnit"]:
        """Historické jednotky (valid_to NOT NULL)."""
        return sorted(
            [ou for ou in self.units if ou.valid_to is not None],
            key=lambda ou: ou.valid_to,
            reverse=True,
        )
```

#### Unit
```python
class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True)
    unit_number = Column(Integer, nullable=False, unique=True, index=True)
    building_number = Column(String(20), index=True)       # číslo popisné
    podil_scd = Column(Float)                              # podíl SČD (např. 0.0234)
    floor_area = Column(Float)                             # m²
    room_count = Column(String(20))                        # "2+kk" atd.
    space_type = Column(String(50), index=True)            # "byt", "garáž", ...
    section = Column(String(10), index=True)               # "A", "B", ...
    orientation_number = Column(Integer)                   # č. orientační
    address = Column(String(200))
    lv_number = Column(Integer, index=True)                # list vlastnictví
    created_at = Column(DateTime, default=utcnow)
    
    owners = relationship("OwnerUnit", back_populates="unit", cascade="all, delete-orphan")
    water_meters = relationship("WaterMeter", back_populates="unit", cascade="all, delete-orphan")
    
    @property
    def current_owners(self) -> list["OwnerUnit"]:
        return [ou for ou in self.owners if ou.valid_to is None]
    
    @property
    def historical_owners(self) -> list["OwnerUnit"]:
        return sorted(
            [ou for ou in self.owners if ou.valid_to is not None],
            key=lambda ou: ou.valid_to, reverse=True,
        )
```

#### OwnerUnit — vlastnické právo (historizované)
```python
class OwnerUnit(Base):
    __tablename__ = "owner_units"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    ownership_type = Column(String(20), index=True)       # "SJM", "VL", "SJVL", "Výhradní", "Podílové"
    share = Column(Float, nullable=False, default=1.0)    # 1.0 = 100% (výhradní), 0.5 = 50% (SJM)
    votes = Column(Integer, nullable=False, default=0)    # počet hlasů (= podíl SČD * total_shares)
    excel_row_number = Column(Integer)                    # zdrojový řádek z importu
    valid_from = Column(Date, index=True)
    valid_to = Column(Date, index=True)                   # NULL = aktuální
    
    owner = relationship("Owner", back_populates="units")
    unit = relationship("Unit", back_populates="owners")
    
    __table_args__ = (
        Index("ix_owner_unit_composite", "owner_id", "unit_id"),
    )
```

#### Proxy
```python
class Proxy(Base):
    __tablename__ = "proxies"
    id = Column(Integer, primary_key=True)
    grantor_id = Column(Integer, ForeignKey("owners.id"), nullable=False, index=True)
    proxy_holder_id = Column(Integer, ForeignKey("owners.id"), index=True)
    proxy_holder_name = Column(String(300))               # když plnomocník není v DB
    voting_id = Column(Integer, ForeignKey("votings.id"), index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=utcnow)
    
    grantor = relationship("Owner", foreign_keys=[grantor_id], back_populates="given_proxies")
    proxy_holder = relationship("Owner", foreign_keys=[proxy_holder_id], back_populates="received_proxies")
```

---

### `app/models/voting.py`

#### Voting
```python
class Voting(Base):
    __tablename__ = "votings"
    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    status = Column(Enum(VotingStatus), default=VotingStatus.DRAFT, index=True)
    template_path = Column(String(500))                   # DOCX šablona
    start_date = Column(Date)
    end_date = Column(Date)
    total_votes_possible = Column(Integer, default=0)
    quorum_threshold = Column(Float, default=0.5)         # 0.5 = 50%
    partial_owner_mode = Column(String(20), default="shared")  # "shared" | "individual"
    import_column_mapping = Column(Text)                  # JSON
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    items = relationship(
        "VotingItem", back_populates="voting",
        cascade="all, delete-orphan",
        order_by="VotingItem.order",
    )
    ballots = relationship("Ballot", back_populates="voting", cascade="all, delete-orphan")
    
    @property
    def has_processed_ballots(self) -> bool:
        return any(b.status == BallotStatus.PROCESSED for b in self.ballots)
```

#### VotingItem
```python
class VotingItem(Base):
    __tablename__ = "voting_items"
    id = Column(Integer, primary_key=True)
    voting_id = Column(Integer, ForeignKey("votings.id"), nullable=False, index=True)
    order = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    voting = relationship("Voting", back_populates="items")
    votes = relationship("BallotVote", back_populates="voting_item", cascade="all, delete-orphan")
```

#### Ballot
```python
class Ballot(Base):
    __tablename__ = "ballots"
    id = Column(Integer, primary_key=True)
    voting_id = Column(Integer, ForeignKey("votings.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False, index=True)
    status = Column(Enum(BallotStatus), default=BallotStatus.GENERATED, index=True)
    pdf_path = Column(String(500))                        # vygenerovaný PDF lístek
    scan_path = Column(String(500))                       # sken vrácený od vlastníka
    voted_by_proxy = Column(Boolean, default=False)
    proxy_holder_name = Column(String(300))
    total_votes = Column(Integer, default=0)              # počet hlasů tohoto vlastníka
    units_text = Column(String(200))                      # human-readable "12, 34"
    shared_owners_text = Column(String(500))              # pro SJM "A + B"
    sent_at = Column(DateTime)
    received_at = Column(DateTime)
    processed_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)
    
    voting = relationship("Voting", back_populates="ballots")
    owner = relationship("Owner", back_populates="ballots")
    votes = relationship("BallotVote", back_populates="ballot", cascade="all, delete-orphan")
```

#### BallotVote
```python
class BallotVote(Base):
    __tablename__ = "ballot_votes"
    id = Column(Integer, primary_key=True)
    ballot_id = Column(Integer, ForeignKey("ballots.id"), nullable=False, index=True)
    voting_item_id = Column(Integer, ForeignKey("voting_items.id"), nullable=False, index=True)
    vote = Column(Enum(VoteValue))
    votes_count = Column(Integer, default=0)              # počet hlasů za tento bod
    manually_verified = Column(Boolean, default=False)
    
    ballot = relationship("Ballot", back_populates="votes")
    voting_item = relationship("VotingItem", back_populates="votes")
```

---

### `app/models/tax.py`

#### TaxSession
```python
class TaxSession(Base):
    __tablename__ = "tax_sessions"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    year = Column(Integer)
    email_subject = Column(String(500))
    email_body = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    
    # Rozesílka settings
    send_batch_size = Column(Integer, default=10)
    send_batch_interval = Column(Integer, default=5)
    send_scheduled_at = Column(DateTime)
    send_status = Column(Enum(SendStatus), default=SendStatus.DRAFT, index=True)
    test_email_passed = Column(Boolean, default=False)
    test_email_address = Column(String)
    send_confirm_each_batch = Column(Boolean, default=False)
    smtp_profile_id = Column(Integer, ForeignKey("smtp_profiles.id"), index=True)
    
    smtp_profile = relationship("SmtpProfile")
    documents = relationship("TaxDocument", back_populates="session", cascade="all, delete-orphan")
```

#### TaxDocument
```python
class TaxDocument(Base):
    __tablename__ = "tax_documents"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("tax_sessions.id"), nullable=False, index=True)
    filename = Column(String(300), nullable=False)
    unit_number = Column(String(20))                      # pozn: STRING, ne INTEGER (z PDF metadat)
    unit_letter = Column(String(5))
    file_path = Column(String(500), nullable=False)
    extracted_owner_name = Column(String(300))
    created_at = Column(DateTime, default=utcnow)
    
    session = relationship("TaxSession", back_populates="documents")
    distributions = relationship("TaxDistribution", back_populates="document", cascade="all, delete-orphan")
```

#### TaxDistribution
```python
class TaxDistribution(Base):
    __tablename__ = "tax_distributions"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("tax_documents.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), index=True)
    match_status = Column(Enum(MatchStatus), default=MatchStatus.UNMATCHED, index=True)
    match_confidence = Column(Float)                      # 0–1
    admin_note = Column(Text)
    
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime)
    email_status = Column(Enum(EmailDeliveryStatus), default=EmailDeliveryStatus.PENDING, index=True)
    email_address_used = Column(String(200))
    email_error = Column(Text)
    
    ad_hoc_name = Column(String(300))                     # když není linked na Owner
    ad_hoc_email = Column(String(200))
    
    document = relationship("TaxDocument", back_populates="distributions")
    owner = relationship("Owner", back_populates="tax_distributions")
```

---

### `app/models/sync.py`

#### SyncSession
```python
class SyncSession(Base):
    __tablename__ = "sync_sessions"
    id = Column(Integer, primary_key=True)
    csv_filename = Column(String(300), nullable=False)
    csv_path = Column(String(500), nullable=False)
    total_records = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)
    total_name_order = Column(Integer, default=0)
    total_differences = Column(Integer, default=0)
    total_missing = Column(Integer, default=0)
    is_finalized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    
    records = relationship("SyncRecord", back_populates="session", cascade="all, delete-orphan")
```

#### SyncRecord
```python
class SyncRecord(Base):
    __tablename__ = "sync_records"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sync_sessions.id"), nullable=False, index=True)
    unit_number = Column(String(20))                      # STRING (historicky)
    csv_owner_name = Column(String(300))
    excel_owner_name = Column(String(300))
    csv_ownership_type = Column(String(50))
    excel_ownership_type = Column(String(50))
    csv_email = Column(String(200))
    csv_phone = Column(String(50))
    excel_space_type = Column(String(50))
    csv_space_type = Column(String(50))
    excel_podil_scd = Column(Float)
    csv_share = Column(Float)
    status = Column(Enum(SyncStatus), nullable=False, index=True)
    resolution = Column(Enum(SyncResolution), default=SyncResolution.PENDING, index=True)
    admin_corrected_name = Column(String(300))
    admin_note = Column(Text)
    match_details = Column(Text)                          # JSON s detaily matchingu
    
    session = relationship("SyncSession", back_populates="records")
```

---

### `app/models/share_check.py`

#### ShareCheckSession
```python
class ShareCheckSession(Base):
    __tablename__ = "share_check_sessions"
    id = Column(Integer, primary_key=True)
    filename = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    col_unit = Column(String(100))                        # název sloupce s č. jednotky
    col_share = Column(String(100))                       # název sloupce s podílem
    total_records = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)
    total_differences = Column(Integer, default=0)
    total_missing_db = Column(Integer, default=0)
    total_missing_file = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    
    records = relationship("ShareCheckRecord", back_populates="session", cascade="all, delete-orphan")
```

#### ShareCheckRecord
```python
class ShareCheckRecord(Base):
    __tablename__ = "share_check_records"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("share_check_sessions.id"), nullable=False, index=True)
    unit_number = Column(Integer)
    db_share = Column(Float)
    file_share = Column(Float)
    status = Column(Enum(ShareCheckStatus), nullable=False, index=True)
    resolution = Column(Enum(ShareCheckResolution), default=ShareCheckResolution.PENDING, index=True)
    admin_note = Column(Text)
    
    session = relationship("ShareCheckSession", back_populates="records")
```

#### ShareCheckColumnMapping — cache mapování
```python
class ShareCheckColumnMapping(Base):
    __tablename__ = "share_check_column_mappings"
    id = Column(Integer, primary_key=True)
    col_unit = Column(String(100), nullable=False)
    col_share = Column(String(100), nullable=False)
    used_count = Column(Integer, default=1)
    last_used_at = Column(DateTime, default=utcnow)
    
    __table_args__ = (
        UniqueConstraint("col_unit", "col_share", name="uq_share_check_mapping"),
    )
```

---

### `app/models/payment.py` (největší soubor)

#### VariableSymbolMapping
```python
class VariableSymbolMapping(Base):
    __tablename__ = "variable_symbol_mappings"
    id = Column(Integer, primary_key=True)
    variable_symbol = Column(String(20), nullable=False, unique=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), index=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), index=True)
    source = Column(Enum(SymbolSource), default=SymbolSource.MANUAL, index=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    unit = relationship("Unit")
    space = relationship("Space")
```

#### UnitBalance — počáteční zůstatky
```python
class UnitBalance(Base):
    __tablename__ = "unit_balances"
    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), index=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), index=True)
    year = Column(Integer, nullable=False, index=True)
    opening_amount = Column(Float, default=0.0)           # + přeplatek, - nedoplatek
    source = Column(Enum(BalanceSource), default=BalanceSource.MANUAL)
    owner_id = Column(Integer, ForeignKey("owners.id"), index=True)
    owner_name = Column(String(300))                      # snapshot pro audit
    note = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    unit = relationship("Unit")
    space = relationship("Space")
    owner = relationship("Owner")
    
    __table_args__ = (
        UniqueConstraint("unit_id", "year", name="uq_unit_balance_year"),
    )
```

#### PrescriptionYear
```python
class PrescriptionYear(Base):
    __tablename__ = "prescription_years"
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False, unique=True, index=True)
    valid_from = Column(Date)
    description = Column(Text)
    source_filename = Column(String(300))                 # uploaded DOCX
    total_units = Column(Integer, default=0)
    total_monthly = Column(Float, default=0.0)            # suma přes všechny jednotky
    created_at = Column(DateTime, default=utcnow)
    
    prescriptions = relationship("Prescription", back_populates="prescription_year", cascade="all, delete-orphan")
```

#### Prescription
```python
class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True)
    prescription_year_id = Column(Integer, ForeignKey("prescription_years.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), index=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), index=True)
    variable_symbol = Column(String(20), index=True)
    space_number = Column(Integer)                        # snapshot
    section = Column(String(10))
    space_type = Column(String(50))
    owner_name = Column(String(300))                      # snapshot
    monthly_total = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    prescription_year = relationship("PrescriptionYear", back_populates="prescriptions")
    items = relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")
    unit = relationship("Unit")
    space = relationship("Space")
```

#### PrescriptionItem
```python
class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    id = Column(Integer, primary_key=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)            # např. "Výtah", "Voda", "Úklid"
    amount = Column(Float, default=0.0)
    category = Column(Enum(PrescriptionCategory), default=PrescriptionCategory.PROVOZNI)
    order = Column(Integer, default=0)
    
    prescription = relationship("Prescription", back_populates="items")
```

#### BankStatement
```python
class BankStatement(Base):
    __tablename__ = "bank_statements"
    id = Column(Integer, primary_key=True)
    filename = Column(String(300), nullable=False)
    file_path = Column(String(500))
    bank_account = Column(String(30))                     # IBAN nebo č. účtu
    period_from = Column(Date)
    period_to = Column(Date)
    opening_balance = Column(Float)
    closing_balance = Column(Float)
    total_income = Column(Float, default=0.0)
    total_expense = Column(Float, default=0.0)
    transaction_count = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    import_status = Column(Enum(ImportStatus), default=ImportStatus.IMPORTED, index=True)
    locked_at = Column(DateTime)                          # po uzamčení nelze měnit
    discrepancy_test_passed = Column(Boolean, default=False)
    
    # Rozesílka nesrovnalostí
    send_batch_size = Column(Integer)
    send_batch_interval = Column(Integer)
    send_confirm_each_batch = Column(Boolean)
    smtp_profile_id = Column(Integer, ForeignKey("smtp_profiles.id"), index=True)
    
    created_at = Column(DateTime, default=utcnow)
    
    smtp_profile = relationship("SmtpProfile")
    payments = relationship("Payment", back_populates="statement", cascade="all, delete-orphan")
```

#### BankStatementColumnMapping
```python
class BankStatementColumnMapping(Base):
    __tablename__ = "bank_statement_column_mappings"
    id = Column(Integer, primary_key=True)
    mapping_json = Column(Text, nullable=False)
    used_count = Column(Integer, default=1)
    last_used_at = Column(DateTime, default=utcnow)
```

#### Payment
```python
class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    statement_id = Column(Integer, ForeignKey("bank_statements.id"), nullable=False, index=True)
    operation_id = Column(String(30), unique=True, index=True)   # unikátní ID transakce z banky
    date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    direction = Column(Enum(PaymentDirection), nullable=False)   # income / expense
    counter_account = Column(String(50))
    counter_account_name = Column(String(200))
    bank_code = Column(String(10))
    bank_name = Column(String(100))
    ks = Column(String(20))                               # konstantní symbol
    vs = Column(String(20), index=True)                   # variabilní symbol
    ss = Column(String(20))                               # specifický symbol
    note = Column(Text)
    message = Column(Text)                                # zpráva pro příjemce
    payment_type = Column(String(50))                     # "Platba kartou", "Příchozí platba", ...
    
    # Matching
    match_status = Column(Enum(PaymentMatchStatus), default=PaymentMatchStatus.UNMATCHED, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), index=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), index=True)
    assigned_month = Column(Integer)                      # 1–12
    
    notified_at = Column(DateTime)                        # kdy bylo odesláno upozornění na nesrovnalost
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    statement = relationship("BankStatement", back_populates="payments")
    prescription = relationship("Prescription")
    unit = relationship("Unit")
    space = relationship("Space")
    owner = relationship("Owner")
    allocations = relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")
```

#### PaymentAllocation
```python
class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), index=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), index=True)
    amount = Column(Float, nullable=False)
    
    payment = relationship("Payment", back_populates="allocations")
    unit = relationship("Unit")
    space = relationship("Space")
    owner = relationship("Owner")
    prescription = relationship("Prescription")
```

#### Settlement
```python
class Settlement(Base):
    __tablename__ = "settlements"
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), index=True)
    result_amount = Column(Float, default=0.0)            # + přeplatek, - nedoplatek
    variable_symbol = Column(String(20))
    specific_symbol = Column(String(20))
    pdf_path = Column(String(500))
    status = Column(Enum(SettlementStatus), default=SettlementStatus.GENERATED, index=True)
    penalty_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    unit = relationship("Unit")
    owner = relationship("Owner")
    items = relationship("SettlementItem", back_populates="settlement", cascade="all, delete-orphan")
```

#### SettlementItem
```python
class SettlementItem(Base):
    __tablename__ = "settlement_items"
    id = Column(Integer, primary_key=True)
    settlement_id = Column(Integer, ForeignKey("settlements.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    distribution_key = Column(String(100))                # jak se náklady rozpočítávají
    cost_building = Column(Float, default=0.0)            # náklad za celý dům
    cost_unit = Column(Float, default=0.0)                # podíl této jednotky
    paid = Column(Float, default=0.0)                     # kolik jednotka zaplatila
    result = Column(Float, default=0.0)                   # cost_unit - paid (+ přeplatek, - nedoplatek)
    
    settlement = relationship("Settlement", back_populates="items")
```

---

### `app/models/space.py`

#### Space
```python
class Space(Base):
    __tablename__ = "spaces"
    id = Column(Integer, primary_key=True)
    space_number = Column(Integer, nullable=False, unique=True, index=True)
    designation = Column(String(100), nullable=False)     # "Obchod 1", "Kancelář 2" atd.
    section = Column(String(20), index=True)
    floor = Column(Integer)
    area = Column(Float)
    status = Column(Enum(SpaceStatus), nullable=False, default=SpaceStatus.VACANT, index=True)
    blocked_reason = Column(String(200))
    note = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    tenants = relationship("SpaceTenant", back_populates="space", cascade="all, delete-orphan")
    
    @property
    def active_tenant_rel(self) -> "SpaceTenant | None":
        for st in self.tenants:
            if st.is_active:
                return st
        return None
```

#### Tenant
```python
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), index=True)  # optional link na Owner
    
    # Jméno (pokud není linked na Owner)
    first_name = Column(String(200), index=True)
    last_name = Column(String(200), index=True)
    title = Column(String(50))
    name_with_titles = Column(String(300), index=True)
    name_normalized = Column(String(300), index=True)
    tenant_type = Column(Enum(OwnerType), default=OwnerType.PHYSICAL, index=True)
    birth_number = Column(String(20), index=True)
    company_id = Column(String(20), index=True)
    
    # Adresy
    perm_street = Column(String(200))
    perm_district = Column(String(100))
    perm_city = Column(String(100))
    perm_zip = Column(String(20))
    perm_country = Column(String(50))
    corr_street = Column(String(200))
    corr_district = Column(String(100))
    corr_city = Column(String(100))
    corr_zip = Column(String(20))
    corr_country = Column(String(50))
    
    # Kontakty
    phone = Column(String(50), index=True)
    phone_landline = Column(String(50))
    phone_secondary = Column(String(50))
    email = Column(String(200), index=True)
    email_secondary = Column(String(200))
    
    is_active = Column(Boolean, default=True, index=True)
    note = Column(Text)
    data_source = Column(String(50), default="manual")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    owner = relationship("Owner")
    spaces = relationship("SpaceTenant", back_populates="tenant", cascade="all, delete-orphan")
    
    @property
    def is_linked(self) -> bool:
        return self.owner_id is not None
    
    @property
    def display_name(self) -> str:
        if self.owner:
            return self.owner.display_name
        return self._build_display_name()
    
    # resolved_* properties: pokud is_linked, berou z owner, jinak z vlastních polí
    # resolved_phone, resolved_email, resolved_type, resolved_birth_number,
    # resolved_company_id, resolved_name_normalized
```

#### SpaceTenant
```python
class SpaceTenant(Base):
    __tablename__ = "space_tenants"
    id = Column(Integer, primary_key=True)
    space_id = Column(Integer, ForeignKey("spaces.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    contract_number = Column(String(50))
    contract_start = Column(Date)
    contract_end = Column(Date)
    monthly_rent = Column(Float, nullable=False, default=0.0)
    variable_symbol = Column(String(20), index=True)
    contract_path = Column(String(500))                   # uploaded PDF/DOCX
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    note = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    space = relationship("Space", back_populates="tenants")
    tenant = relationship("Tenant", back_populates="spaces")
    
    __table_args__ = (
        Index("ix_space_tenant_composite", "space_id", "tenant_id"),
    )
```

---

### `app/models/smtp_profile.py`

```python
class SmtpProfile(Base):
    __tablename__ = "smtp_profiles"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, default=465)
    smtp_user = Column(String(255), nullable=False)
    smtp_password_b64 = Column(Text, nullable=False)      # Fernet-encrypted; legacy base64 supported
    smtp_from_name = Column(String(255), default="")
    smtp_from_email = Column(String(255), nullable=False)
    smtp_use_tls = Column(Boolean, default=True)
    imap_host = Column(String(255))
    imap_save_sent = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
```

---

### `app/models/water_meter.py`

#### WaterMeter
```python
class WaterMeter(Base):
    __tablename__ = "water_meters"
    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), index=True)
    unit_number = Column(Integer, nullable=False, index=True)  # snapshot z importu
    unit_letter = Column(String(5), default="")
    unit_suffix = Column(String(5), default="")
    meter_serial = Column(String(50), nullable=False, index=True)
    meter_type = Column(Enum(MeterType), nullable=False, index=True)
    location = Column(String(100))                        # "koupelna", "WC" atd.
    notified_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    unit = relationship("Unit", back_populates="water_meters")
    readings = relationship("WaterReading", back_populates="meter", cascade="all, delete-orphan")
```

#### WaterReading
```python
class WaterReading(Base):
    __tablename__ = "water_readings"
    id = Column(Integer, primary_key=True)
    meter_id = Column(Integer, ForeignKey("water_meters.id"), nullable=False, index=True)
    reading_date = Column(Date, index=True)
    value = Column(Float)
    import_batch = Column(String(50), index=True)         # odlišení importních batche
    created_at = Column(DateTime, default=utcnow)
    
    meter = relationship("WaterMeter", back_populates="readings")
```

---

## Indexy — `_ensure_indexes()` v `main.py`

SQLAlchemy `create_all()` přidá pouze indexy definované na nových tabulkách. Pro již existující tabulky je potřeba explicitně vytvořit indexy ručním SQL. Přidej funkci `_ensure_indexes(conn)` volanou v lifespanu po `create_all()`:

```python
_INDEXES = [
    # voting
    "CREATE INDEX IF NOT EXISTS ix_votings_status ON votings(status)",
    "CREATE INDEX IF NOT EXISTS ix_voting_items_voting_id ON voting_items(voting_id)",
    "CREATE INDEX IF NOT EXISTS ix_ballots_voting_id ON ballots(voting_id)",
    "CREATE INDEX IF NOT EXISTS ix_ballots_owner_id ON ballots(owner_id)",
    "CREATE INDEX IF NOT EXISTS ix_ballots_status ON ballots(status)",
    "CREATE INDEX IF NOT EXISTS ix_ballot_votes_ballot_id ON ballot_votes(ballot_id)",
    "CREATE INDEX IF NOT EXISTS ix_ballot_votes_voting_item_id ON ballot_votes(voting_item_id)",
    
    # administration
    "CREATE INDEX IF NOT EXISTS ix_svj_addresses_svj_info_id ON svj_addresses(svj_info_id)",
    "CREATE INDEX IF NOT EXISTS ix_board_members_group ON board_members(\"group\")",
    "CREATE INDEX IF NOT EXISTS ix_code_list_items_category ON code_list_items(category)",
    
    # tax
    "CREATE INDEX IF NOT EXISTS ix_tax_documents_session_id ON tax_documents(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_tax_distributions_document_id ON tax_distributions(document_id)",
    "CREATE INDEX IF NOT EXISTS ix_tax_distributions_owner_id ON tax_distributions(owner_id)",
    "CREATE INDEX IF NOT EXISTS ix_tax_distributions_match_status ON tax_distributions(match_status)",
    "CREATE INDEX IF NOT EXISTS ix_tax_sessions_send_status ON tax_sessions(send_status)",
    "CREATE INDEX IF NOT EXISTS ix_tax_distributions_email_status ON tax_distributions(email_status)",
    
    # sync
    "CREATE INDEX IF NOT EXISTS ix_sync_records_session_id ON sync_records(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_sync_records_status ON sync_records(status)",
    "CREATE INDEX IF NOT EXISTS ix_sync_records_resolution ON sync_records(resolution)",
    
    # common
    "CREATE INDEX IF NOT EXISTS ix_email_logs_status ON email_logs(status)",
    "CREATE INDEX IF NOT EXISTS ix_email_logs_module ON email_logs(module)",
    "CREATE INDEX IF NOT EXISTS ix_email_logs_reference_id ON email_logs(reference_id)",
    "CREATE INDEX IF NOT EXISTS ix_email_logs_name_normalized ON email_logs(name_normalized)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_recipient_email ON email_bounces(recipient_email)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_owner_id ON email_bounces(owner_id)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_email_log_id ON email_bounces(email_log_id)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_bounce_type ON email_bounces(bounce_type)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_module ON email_bounces(module)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_reference_id ON email_bounces(reference_id)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_bounced_at ON email_bounces(bounced_at)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_imap_uid ON email_bounces(imap_uid)",
    "CREATE INDEX IF NOT EXISTS ix_email_bounces_created_at ON email_bounces(created_at)",
    "CREATE INDEX IF NOT EXISTS ix_owners_email_invalid ON owners(email_invalid)",
    "CREATE INDEX IF NOT EXISTS ix_import_logs_import_type ON import_logs(import_type)",
    
    # owner
    "CREATE INDEX IF NOT EXISTS ix_owner_units_valid_from ON owner_units(valid_from)",
    "CREATE INDEX IF NOT EXISTS ix_owner_units_valid_to ON owner_units(valid_to)",
    
    # share_check
    "CREATE INDEX IF NOT EXISTS ix_share_check_records_session_id ON share_check_records(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_share_check_records_status ON share_check_records(status)",
    "CREATE INDEX IF NOT EXISTS ix_share_check_records_resolution ON share_check_records(resolution)",
    
    # activity
    "CREATE INDEX IF NOT EXISTS ix_activity_logs_action ON activity_logs(action)",
    "CREATE INDEX IF NOT EXISTS ix_activity_logs_entity_type ON activity_logs(entity_type)",
    "CREATE INDEX IF NOT EXISTS ix_activity_logs_module ON activity_logs(module)",
    "CREATE INDEX IF NOT EXISTS ix_activity_logs_created_at ON activity_logs(created_at)",
    
    # payments
    "CREATE INDEX IF NOT EXISTS ix_variable_symbol_mappings_unit_id ON variable_symbol_mappings(unit_id)",
    "CREATE INDEX IF NOT EXISTS ix_variable_symbol_mappings_source ON variable_symbol_mappings(source)",
    "CREATE INDEX IF NOT EXISTS ix_variable_symbol_mappings_space_id ON variable_symbol_mappings(space_id)",
    "CREATE INDEX IF NOT EXISTS ix_unit_balances_unit_id ON unit_balances(unit_id)",
    "CREATE INDEX IF NOT EXISTS ix_unit_balances_year ON unit_balances(year)",
    "CREATE INDEX IF NOT EXISTS ix_unit_balances_owner_id ON unit_balances(owner_id)",
    "CREATE INDEX IF NOT EXISTS ix_prescription_years_year ON prescription_years(year)",
    "CREATE INDEX IF NOT EXISTS ix_prescriptions_prescription_year_id ON prescriptions(prescription_year_id)",
    "CREATE INDEX IF NOT EXISTS ix_prescriptions_unit_id ON prescriptions(unit_id)",
    "CREATE INDEX IF NOT EXISTS ix_prescriptions_variable_symbol ON prescriptions(variable_symbol)",
    "CREATE INDEX IF NOT EXISTS ix_prescriptions_space_id ON prescriptions(space_id)",
    "CREATE INDEX IF NOT EXISTS ix_prescription_items_prescription_id ON prescription_items(prescription_id)",
    "CREATE INDEX IF NOT EXISTS ix_bank_statements_import_status ON bank_statements(import_status)",
    "CREATE INDEX IF NOT EXISTS ix_payments_statement_id ON payments(statement_id)",
    "CREATE INDEX IF NOT EXISTS ix_payments_date ON payments(date)",
    "CREATE INDEX IF NOT EXISTS ix_payments_vs ON payments(vs)",
    "CREATE INDEX IF NOT EXISTS ix_payments_match_status ON payments(match_status)",
    "CREATE INDEX IF NOT EXISTS ix_payments_unit_id ON payments(unit_id)",
    "CREATE INDEX IF NOT EXISTS ix_payments_owner_id ON payments(owner_id)",
    "CREATE INDEX IF NOT EXISTS ix_payments_prescription_id ON payments(prescription_id)",
    "CREATE INDEX IF NOT EXISTS ix_payments_space_id ON payments(space_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_allocations_payment_id ON payment_allocations(payment_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_allocations_unit_id ON payment_allocations(unit_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_allocations_owner_id ON payment_allocations(owner_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_allocations_prescription_id ON payment_allocations(prescription_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_allocations_space_id ON payment_allocations(space_id)",
    "CREATE INDEX IF NOT EXISTS ix_settlements_year ON settlements(year)",
    "CREATE INDEX IF NOT EXISTS ix_settlements_unit_id ON settlements(unit_id)",
    "CREATE INDEX IF NOT EXISTS ix_settlements_status ON settlements(status)",
    "CREATE INDEX IF NOT EXISTS ix_settlement_items_settlement_id ON settlement_items(settlement_id)",
    
    # spaces / tenants
    "CREATE INDEX IF NOT EXISTS ix_spaces_section ON spaces(section)",
    "CREATE INDEX IF NOT EXISTS ix_spaces_status ON spaces(status)",
    "CREATE INDEX IF NOT EXISTS ix_tenants_owner_id ON tenants(owner_id)",
    "CREATE INDEX IF NOT EXISTS ix_tenants_is_active ON tenants(is_active)",
    "CREATE INDEX IF NOT EXISTS ix_tenants_name_normalized ON tenants(name_normalized)",
    "CREATE INDEX IF NOT EXISTS ix_space_tenants_space_id ON space_tenants(space_id)",
    "CREATE INDEX IF NOT EXISTS ix_space_tenants_tenant_id ON space_tenants(tenant_id)",
    "CREATE INDEX IF NOT EXISTS ix_space_tenants_is_active ON space_tenants(is_active)",
    "CREATE INDEX IF NOT EXISTS ix_space_tenants_variable_symbol ON space_tenants(variable_symbol)",
]
```

**Poznámka**: Kdekoli má sloupec `index=True` v modelu, musí být i zde. Při přidání nového indexu v modelu **vždy** přidej i `CREATE INDEX IF NOT EXISTS` do `_INDEXES`.

---

## Migrace — `_ALL_MIGRATIONS` v `main.py`

Každá migrace je funkce `(conn)` s idempotentním SQL. Spouští se **při startu** (lifespan) i **po obnově zálohy** (`run_post_restore_migrations()`).

Vzor migrace:
```python
def _migrate_owners_email_invalid(conn):
    """Přidá sloupce email_invalid a email_invalid_reason k owners pokud neexistují."""
    try:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(owners)")}
        if "email_invalid" not in cols:
            conn.exec_driver_sql("ALTER TABLE owners ADD COLUMN email_invalid BOOLEAN DEFAULT 0")
        if "email_invalid_reason" not in cols:
            conn.exec_driver_sql("ALTER TABLE owners ADD COLUMN email_invalid_reason VARCHAR(500)")
    except Exception as exc:
        print(f"[migrate_owners_email_invalid] {exc}")
```

Seznam migrací (při bootstrapu nového projektu **nejsou potřeba** — `create_all()` vytvoří vše správně. Migrace jsou pro upgrade stávajících DB. Pro novou implementaci stačí **prázdný `_ALL_MIGRATIONS` list** + `_ensure_indexes()` + seedy).

Pro úplnost uvádím, co všechno originál řeší (nemusíš přenášet):
1. Fix `units.id` na INTEGER PRIMARY KEY
2. Add `owner_units.valid_from/valid_to`
3. Add send workflow cols na `tax_*`
4. `owners.phone_secondary`
5. `ballots.shared_owners_text`
6. `svj_info.voting_import_mapping`
7. `svj_info.*_import_mapping` (6 mapping cols)
8. `email_logs.name_normalized`
9. `owners.email_invalid`
10. `payment_allocations` table
11. `bank_statements.locked_at`
12. `unit_balances.owner_*` cols
13. `spaces` + `tenants` + `space_tenants` tables
14. `svj_info.send_*` cols
15. `payments.notified_at`
16. Dedupe `tenants` (merge duplicates by name_normalized)
17. `bank_statements.send_*` cols
18. `smtp_profiles` table
19. Fix `activity_logs.module` hodnoty
20. `svj_info.water_meter_import_mapping`
21. Fix `water_meters.unit_id` links
22. `water_meters.unit_suffix`
23. `water_meters.notified_at`
24. Water email template seed (v2, v3, v4 — iterace obsahu)
25. `email_bounces.smtp_profile_name`
26. SMTP password encryption (migrace legacy base64 → Fernet)

---

## Seed funkce (volané v lifespan po `create_all()`)

### `_seed_code_lists()`
```python
CODE_LIST_SEEDS = {
    "space_type": ["byt", "garážové stání", "sklep", "nebytový prostor", "ateliér", "kancelář"],
    "room_count": ["1+kk", "1+1", "2+kk", "2+1", "3+kk", "3+1", "4+kk", "4+1", "5+kk", "5+1"],
    "ownership_type": ["SJM", "VL", "SJVL", "Výhradní", "Podílové", "Neuvedeno"],
}

def _seed_code_lists(db: Session) -> None:
    for category, values in CODE_LIST_SEEDS.items():
        for idx, value in enumerate(values):
            existing = db.query(CodeListItem).filter_by(category=category, value=value).first()
            if not existing:
                db.add(CodeListItem(category=category, value=value, order=idx))
    db.commit()
```

### `_seed_email_templates()`
Vytvoří 3 default šablony pokud neexistují (podle `name`):
- **"Daňové rozúčtování"** — subject: `"Daňové rozúčtování za rok {{ year }}"`, body obsahuje oslovení, popis, podpis výboru.
- **"Upozornění na nesrovnalost platby"** — subject: `"Nesrovnalost platby VS {{ vs }}"`, body popisuje očekávanou a přijatou částku.
- **"Odečty vodoměrů"** — subject: `"Odečty vodoměrů SV/TV {{ period }}"`, body zobrazuje tabulku odečtů.

Přesné znění — uživatel si upraví. Použij vzor:
```python
DEFAULT_TEMPLATES = [
    {
        "name": "Daňové rozúčtování",
        "subject_template": "Daňové rozúčtování za rok {{ year }}",
        "body_template": """Dobrý den {{ recipient_name }},

v příloze zasíláme daňové rozúčtování za rok {{ year }}.

S pozdravem
Výbor SVJ {{ svj_name }}
""",
    },
    # ... další dvě šablony
]
```

---

## `app/models/__init__.py` — importy a `__all__`

```python
from .common import (
    EmailLog, EmailBounce, ImportLog, ActivityLog,
    EmailStatus, BounceType, ActivityAction,
    log_activity,
)
from .administration import (
    SvjInfo, SvjAddress, BoardMember, CodeListItem, EmailTemplate,
)
from .owner import (
    Owner, Unit, OwnerUnit, Proxy, OwnerType,
)
from .voting import (
    Voting, VotingItem, Ballot, BallotVote,
    VotingStatus, VoteValue, BallotStatus,
)
from .tax import (
    TaxSession, TaxDocument, TaxDistribution,
    MatchStatus, SendStatus, EmailDeliveryStatus,
)
from .sync import (
    SyncSession, SyncRecord, SyncStatus, SyncResolution,
)
from .share_check import (
    ShareCheckSession, ShareCheckRecord, ShareCheckColumnMapping,
    ShareCheckStatus, ShareCheckResolution,
)
from .payment import (
    VariableSymbolMapping, UnitBalance,
    PrescriptionYear, Prescription, PrescriptionItem,
    BankStatement, BankStatementColumnMapping,
    Payment, PaymentAllocation,
    Settlement, SettlementItem,
    SymbolSource, BalanceSource, PrescriptionCategory,
    ImportStatus, PaymentDirection, PaymentMatchStatus, SettlementStatus,
)
from .space import Space, Tenant, SpaceTenant, SpaceStatus
from .smtp_profile import SmtpProfile
from .water_meter import WaterMeter, WaterReading, MeterType

__all__ = [
    # common
    "EmailLog", "EmailBounce", "ImportLog", "ActivityLog",
    "EmailStatus", "BounceType", "ActivityAction",
    "log_activity",
    # administration
    "SvjInfo", "SvjAddress", "BoardMember", "CodeListItem", "EmailTemplate",
    # owner
    "Owner", "Unit", "OwnerUnit", "Proxy", "OwnerType",
    # voting
    "Voting", "VotingItem", "Ballot", "BallotVote",
    "VotingStatus", "VoteValue", "BallotStatus",
    # tax
    "TaxSession", "TaxDocument", "TaxDistribution",
    "MatchStatus", "SendStatus", "EmailDeliveryStatus",
    # sync
    "SyncSession", "SyncRecord", "SyncStatus", "SyncResolution",
    # share_check
    "ShareCheckSession", "ShareCheckRecord", "ShareCheckColumnMapping",
    "ShareCheckStatus", "ShareCheckResolution",
    # payment
    "VariableSymbolMapping", "UnitBalance",
    "PrescriptionYear", "Prescription", "PrescriptionItem",
    "BankStatement", "BankStatementColumnMapping",
    "Payment", "PaymentAllocation",
    "Settlement", "SettlementItem",
    "SymbolSource", "BalanceSource", "PrescriptionCategory",
    "ImportStatus", "PaymentDirection", "PaymentMatchStatus", "SettlementStatus",
    # space
    "Space", "Tenant", "SpaceTenant", "SpaceStatus",
    # smtp
    "SmtpProfile",
    # water
    "WaterMeter", "WaterReading", "MeterType",
]
```

---

## Next step

Pokračuj do [`PRD_MODULES.md`](PRD_MODULES.md) pro **user stories + acceptance criteria** per modul.
