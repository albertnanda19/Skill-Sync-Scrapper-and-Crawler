# JobSpy (python-jobspy) — Project Context

## 1) Tujuan Project
JobSpy adalah **library Python** untuk melakukan scraping lowongan pekerjaan dari beberapa job board populer dan menggabungkannya menjadi satu output terstruktur berupa **`pandas.DataFrame`**.

Target utamanya:
- Menjalankan pencarian job di beberapa website sekaligus (concurrent).
- Menghasilkan data yang seragam antar sumber (kolom-kolom yang konsisten).
- Mendukung penggunaan proxy untuk mengurangi risiko blocking.

Repo ini berisi source package `jobspy/` dan contoh pemakaian via script (misal `run_scrape.py`).

## 2) Struktur Repo
File/folder penting:
- `pyproject.toml`
  - Metadata package (nama: `python-jobspy`).
  - Dependency utama dan constraint Python (**>= 3.10**).
- `poetry.lock`
  - Lockfile dependency (jika memakai Poetry).
- `jobspy/`
  - Package utama. Entry point fungsi untuk pemakaian umum ada di `jobspy/__init__.py`.
- `run_scrape.py`
  - Script contoh untuk menjalankan `scrape_jobs()` dari repo ini.
- `jobs.csv`
  - Contoh output hasil scraping (CSV).

Submodule scrapers (per situs) ada di:
- `jobspy/indeed/`
- `jobspy/linkedin/`
- `jobspy/ziprecruiter/`
- `jobspy/google/`
- `jobspy/glassdoor/`
- `jobspy/bayt/`
- `jobspy/naukri/`
- `jobspy/bdjobs/`

## 3) Entry Point & Alur Eksekusi
### Fungsi utama: `jobspy.scrape_jobs(...)`
Lokasi: `jobspy/__init__.py`

Peran utama `scrape_jobs`:
1. Validasi & normalisasi input.
2. Mapping `site_name` -> class scraper spesifik per situs.
3. Menjalankan scraping secara paralel menggunakan `ThreadPoolExecutor`.
4. Menggabungkan hasil job dari semua situs menjadi list DataFrame.
5. Melakukan normalisasi kolom (reorder ke urutan yang diinginkan) dan sorting.
6. Mengembalikan hasil akhir sebagai `pandas.DataFrame`.

Catatan penting:
- Karena scraping dijalankan concurrent, **jika salah satu situs melempar exception**, eksekusi `scrape_jobs` bisa gagal (thread exception di-raise ke main thread). Pada praktiknya, beberapa situs seperti Google/LinkedIn dapat memicu rate-limit (HTTP 429) dan menggagalkan run.

### Interface scrapers
- `jobspy/model.py` mendefinisikan model & tipe data (Pydantic), termasuk:
  - `ScraperInput` (parameter yang dipakai oleh semua scraper)
  - `Site` enum (nama situs)
  - `JobResponse` dan struktur job posting
- Base class `Scraper` (abstract) berkontrak `scrape(scraper_input) -> JobResponse`.

### Utilitas
Lokasi: `jobspy/util.py`

Berisi helper seperti:
- Logger / level verbosity.
- Normalisasi site name.
- Parsing gaji dari deskripsi (untuk beberapa negara/sumber).

## 4) Parameter penting untuk `scrape_jobs()`
Parameter yang umum dipakai:
- `site_name`: list atau string.
  - Contoh: `["indeed", "linkedin", "zip_recruiter"]`
- `search_term`: keyword pencarian utama (dipakai oleh sebagian besar scraper).
- `google_search_term`: khusus untuk google jobs. Biasanya perlu syntax sangat spesifik.
- `location`: lokasi pencarian (misalnya kota).
- `results_wanted`: jumlah hasil yang ingin diambil per situs.
- `hours_old`: filter berdasarkan umur posting (jam).
- `country_indeed`: diperlukan untuk Indeed/Glassdoor (contoh: `Indonesia`, `USA`).
- `proxies`: list proxy untuk rotasi (format `user:pass@host:port` atau `localhost`).
- `user_agent`: override user-agent default.
- `verbose`: 0/1/2 untuk log.
- `linkedin_fetch_description`: jika true, LinkedIn akan fetch detail tambahan (lebih lambat dan lebih banyak request).

Limitations (penting untuk konteks AI):
- **Google**: sering memunculkan 429 / captcha jika scraping terlalu cepat.
- **LinkedIn**: sangat agresif rate-limit; proxy sangat membantu.
- **Indeed**: relatif lebih stabil, tapi tetap ada batasan kombinasi filter tertentu.

## 5) Output Data
`scrape_jobs()` mengembalikan `pandas.DataFrame`.

Kolom umum yang sering ada:
- `site`
- `title`
- `company`
- `job_url`
- `location`
- `description`
- `date_posted`

Kolom kompensasi (kadang hasil parsing):
- `interval` (yearly/hourly/dll)
- `min_amount`, `max_amount`
- `currency`
- `salary_source` (direct/description)

Beberapa situs punya kolom spesifik (contoh Naukri: `skills`, `experience_range`, dll).

## 6) Cara Menjalankan di Repo Ini (Development / Editable)
### Opsi 1: venv + pip (yang kamu pakai)
1. Aktivasi venv:
   ```bash
   source .venv/bin/activate
   ```
2. Install package dalam mode editable:
   ```bash
   pip install -e .
   ```
3. Jalankan contoh:
   ```bash
   python run_scrape.py
   ```

### Opsi 2: Poetry
1. Install dependencies:
   ```bash
   poetry install
   ```
2. Run script:
   ```bash
   poetry run python run_scrape.py
   ```

## 7) Script Contoh yang Dipakai (`run_scrape.py`)
`run_scrape.py` adalah wrapper sederhana untuk memanggil `scrape_jobs` dan menyimpan output ke `jobs.csv`.

Pola yang disarankan:
- Definisikan `keyword` dan `location` sekali, lalu gunakan untuk semua situs.
- Hindari memasukkan `google` ke `site_name` jika sering kena 429.

## 8) Troubleshooting yang Umum
- Error `429 too many requests`:
  - Kurangi frekuensi scraping.
  - Kurangi `results_wanted`.
  - Pakai `proxies`.
  - Pertimbangkan menonaktifkan situs yang sering block (Google/LinkedIn) saat debugging.
- Output kosong:
  - Keyword terlalu sempit / salah format.
  - `country_indeed` tidak sesuai.
  - `google_search_term` tidak mengikuti query Google Jobs.

## 9) Ringkasan untuk “AI Context”
- Repo ini adalah **library scraper multi-job-board** dengan API utama `scrape_jobs`.
- Tiap situs memiliki scraper sendiri di subpackage `jobspy/<site>/`.
- Orkestrasi dilakukan concurrent; satu situs error bisa menggagalkan keseluruhan run.
- Output standar adalah DataFrame; user biasanya export ke CSV.
- Risiko utama operasional adalah rate-limit (429) dan pemblokiran bot.
