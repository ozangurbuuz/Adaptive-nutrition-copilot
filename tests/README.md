# Tests

Unit testler PostgreSQL bağlantısı gerektirmez:

```powershell
$env:PYTHONPATH="backend"
python -m pytest -m "not integration"
```

PostgreSQL integration testleri yalnız ayrı bir test database URL'si ile çalışır:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://<user>:<password>@<host>/<test_database>"
$env:PYTHONPATH="backend"
python -m pytest -m integration tests/integration
```

Test database adı ayraçla ayrılmış `test`, `tests` veya `testing` bölümü içermeli
ve `DATABASE_URL` ile aynı database adına sahip olmamalıdır.
Integration temizliği database'i düşürmez; yalnız doğrulanmış test database içindeki
bilinen proje tablolarına dokunur.
