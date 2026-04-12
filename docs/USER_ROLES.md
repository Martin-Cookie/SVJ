# Uživatelské role — plán implementace

> Implementovat až budou hotové všechny moduly. Role je ortogonální vrstva — přidá se mechanicky bez předělávání existujícího kódu.

## Role

| Role | Popis | Typický uživatel |
|------|-------|------------------|
| **admin** | Plný přístup ke všemu | Předseda SVJ, správce |
| **board** | Správa dat, ne destruktivní systémové operace | Člen výboru |
| **auditor** | Read-only přístup ke všem datům | Kontrolní orgán |
| **owner** | Přístup pouze ke svým údajům a hlasování | Jednotlivý vlastník |

## Matice oprávnění

| Modul / Akce | admin | board | auditor | owner |
|--------------|-------|-------|---------|-------|
| Dashboard — přehled | celý | celý | celý | jen své jednotky |
| Vlastníci — seznam, detail | CRUD | CRUD | read | jen svůj profil |
| Jednotky — seznam, detail | CRUD | CRUD | read | jen své jednotky |
| Hlasování — správa (CRUD) | ano | ano | ne | ne |
| Hlasování — zobrazení výsledků | ano | ano | ano | jen svá hlasování |
| Hlasování — online hlas (budoucí) | — | — | — | ano |
| Hromadné rozesílání — správa | ano | ano | read | jen své dokumenty |
| Synchronizace — import/výměna | ano | ano | ne | ne |
| Evidence plateb — správa | ano | ano | read | ne |
| Kontrola podílu | ano | ano | read | ne |
| Administrace — info SVJ, výbor | ano | read | read | ne |
| Administrace — zálohy, smazání dat | ano | ne | ne | ne |
| Administrace — hromadné úpravy | ano | ano | ne | ne |
| Administrace — číselníky | ano | ano | ne | ne |
| Export dat | ano | ano | ano | ne |
| Správa uživatelů | ano | ne | ne | ne |

## Technické řešení

- **Autentizace:** session-based (cookie), `bcrypt`/`passlib` pro hesla
- **Model:** `User (id, username, password_hash, role: UserRole, owner_id: FK → Owner nullable, is_active, created_at)`
- **Autorizace:** FastAPI `Depends(get_current_user)` + helper `require_role("admin", "board")`
- **Šablony:** `current_user` v kontextu, sidebar podmíněný dle role, destruktivní tlačítka skrytá

## Nové soubory

- `app/models/user.py` — User model + UserRole enum
- `app/routers/auth.py` — login/logout/správa uživatelů
- `app/services/auth_service.py` — hash, verify, session
- `app/templates/auth/login.html`, `users.html`

## Postup implementace

1. Model `User` + migrace + seed admin účtu
2. Auth service (hash, verify, session middleware)
3. Login/logout stránky
4. `get_current_user` dependency + `require_role` helper
5. Přidat do všech routerů (mechanicky)
6. Sidebar podmíněný dle role
7. Skrýt destruktivní tlačítka v šablonách
8. Správa uživatelů (admin panel)
9. Owner self-service (volitelné, až bude potřeba)

## Pravidlo pro průběžný vývoj

- **NEPOUŽÍVAT hardcoded admin logiku** rozsekanou po šablonách (např. `{% if is_admin %}`)
- Destruktivní akce řešit přes `data-confirm` / `hx-confirm` — obojí automaticky používá custom `svjConfirm()` modal (viz [UI_GUIDE.md § 17](UI_GUIDE.md))
- Nové moduly navrhovat tak, aby šly snadno obalit `require_role()` dependency
