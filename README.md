# 📰 Project Pipeline Data Engineering: VOI News Lakehouse

Pipeline otomatisasi ingestion dan pemrosesan data berita VOI.id menggunakan **Apache Airflow** dan **PostgreSQL** dengan konsep **Medallion Architecture (Bronze -> Silver -> Gold)**.

---

## 🛠️ Prasyarat (Prerequisites)

Sebelum menjalankan project, pastikan teman-teman sudah menginstal:
1. **[Git](https://git-scm.com/)**
2. **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (Pastikan sudah terinstal dan statusnya **Running**)
3. **[DBeaver Community](https://dbeaver.io/)** (Opsional, untuk melihat isi tabel database)

---

## 🚀 Panduan Memulai Cepat (Quickstart)

### 1. Clone Repository
```bash
git clone <URL_REPOSITORY_GITHUB_KAMU>
cd project-bigdata
```

### 2. Siapkan File Environment (`.env`)
Salin file `.env.example` menjadi `.env`:
* **Di Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
* **Di Linux / macOS / Git Bash:**
  ```bash
  cp .env.example .env
  ```

### 3. Nyalakan Seluruh Sistem dengan Docker
Pastikan **Docker Desktop** sudah menyala, lalu jalankan:
```bash
docker compose up -d
```
> 💡 *Catatan: Saat pertama kali dijalankan, sistem akan otomatis mengunduh image Airflow dan PostgreSQL, menginisialisasi database metadata, dan mengeksekusi `init_lakehouse.sql` untuk membuat schema `bronze`, `silver`, dan `gold`.*

---

## 🌐 Akses Layanan

### 1. Apache Airflow Dashboard
* **URL:** [http://localhost:8085](http://localhost:8085)
* **Username:** `admin`
* **Password:** `admin`

Di dashboard ini terdapat 3 DAG yang sudah berjalan otomatis:
1. **`dag_voi_bronze_pipeline`** (`dag1_Collecting.py`): Scrape berita VOI $\rightarrow$ Validasi null & duplikasi $\rightarrow$ Simpan ke tabel `bronze.articles`. Berjalan otomatis setiap **5 menit**.
2. **`dag_voi_silver_pipeline`** (`dag2_Processing.py`): Mengambil data Bronze $\rightarrow$ Pembersihan teks, filter tag & redaksi $\rightarrow$ Simpan ke tabel `silver.articles`. Berjalan otomatis setiap **10 menit**.
3. **`dag_voi_gold_warehouse`** (`dag3_Warehouse.py`): Memproses data Silver menjadi Star Schema (`dim_*`, `fact_article`) dan analytics views di schema `gold`. Berjalan otomatis setiap **5 menit**.

### 2. Database Lakehouse (DBeaver / pgAdmin)
Hubungkan database client kamu dengan konfigurasi berikut:

| Parameter | Nilai |
| :--- | :--- |
| **Host** | `localhost` |
| **Port** | `5434` |
| **Database** | `project_bigdata_db` |
| **Username** | `postgres` |
| **Password** | `postgrespassword` |

Di dalam database terdapat 3 schema:
* **`bronze`** $\rightarrow$ `articles` (Data mentah asli dari web)
* **`silver`** $\rightarrow$ `articles` (Data bersih, tag tanpa href, redaksi tanpa href, teks tanpa iklan)
* **`gold`** $\rightarrow$ `daily_article_metrics`, `editor_team_productivity`, `v_recent_articles_dashboard` (Siap visualisasi)

---

## 📁 Struktur Direktori
```text
project-bigdata/
├── dags/
│   ├── dag1_Collecting.py      # DAG 1: Scrape & Ingest ke Bronze
│   ├── dag2_Processing.py      # DAG 2: Preprocessing Bronze ke Silver
│   ├── dag3_Warehouse.py       # DAG 3: Load Silver ke Gold Star Schema
│   └── script/
│       ├── main.py             # Crawler scraper VOI
│       ├── validate_raw.py     # Validasi NULL, duplikasi & ekstraksi hash
│       ├── save_raw.py         # Ingestion data mentah ke Bronze DB
│       ├── preprocessing.py    # Transformasi & Ingestion ke Silver DB
│       ├── gold_warehouse.py   # Transformasi & Load ke Gold Warehouse
│       └── db_connection.py    # Helper koneksi database (Docker & Host)
├── db/
│   └── init_lakehouse.sql      # Inisialisasi schema & tabel Medallion
├── docker-compose.yaml         # Orkestrator Airflow & Postgres
├── .env.example                # Template konfigurasi environment
├── .gitignore                  # File/folder yang diabaikan Git
└── README.md                   # Dokumentasi project
```

---

## 🔄 Memperbarui Perubahan File di Docker

Project ini menggunakan image bawaan (`apache/airflow:3.3.2` dan `postgres:17-alpine`) tanpa custom `Dockerfile`, sehingga **tidak perlu** menjalankan `docker compose build`. Langkah yang perlu dilakukan tergantung jenis file yang diubah atau ditambahkan:

### 1. Perubahan / Penambahan File `.py` (`dags/` atau `dags/script/`)
Folder `./dags` sudah terhubung langsung (*bind mount*) ke `/opt/airflow/dags` di dalam container.
* **Tidak perlu** `docker compose build` maupun `docker compose up -d` ulang.
* Airflow (`airflow-dag-processor`) akan mendeteksi file baru atau perubahan kode secara otomatis dalam beberapa detik.
* Jika ingin perubahan langsung terbaca tanpa menunggu atau ada perubahan pada modul helper di `dags/script/`, jalankan:
  ```bash
  docker compose restart airflow-dag-processor airflow-scheduler airflow-worker
  ```

### 2. Perubahan / Penambahan File `.sql` (`db/init_lakehouse.sql`)
File `db/init_lakehouse.sql` hanya dieksekusi **satu kali** oleh PostgreSQL saat volume database pertama kali dibuat (masih kosong). Menjalankan `docker compose up -d` saja **tidak akan** menjalankan ulang script `.sql` tersebut.
* **Opsi A — Tanpa menghapus data yang sudah ada (Disarankan):**
  Jalankan query SQL tambahan langsung lewat DBeaver, atau eksekusi file `.sql` ke container yang sedang berjalan:
  ```powershell
  Get-Content db/init_lakehouse.sql | docker exec -i postgres-lakehouse psql -U postgres -d project_bigdata_db
  ```
  *(Atau ganti dengan file `.sql` baru/migrasi yang ingin dijalankan).*
* **Opsi B — Reset total database dari awal (Menghapus semua data di volume!):**
  ```bash
  docker compose down -v
  docker compose up -d
  ```

### 3. Perubahan `.env`, `docker-compose.yaml`, atau Library Python (`_PIP_ADDITIONAL_REQUIREMENTS`)
Jika mengubah environment variable, port, atau menambah library di `_PIP_ADDITIONAL_REQUIREMENTS` pada `.env`:
```bash
docker compose up -d
```
Docker Compose akan otomatis membuat ulang (*recreate*) container yang konfigurasinya berubah.

---

## 🛑 Cara Menghentikan Container
Jika selesai bekerja dan ingin menghemat RAM:
```bash
docker compose down
```
*(Data di database tetap aman tersimpan di volume Docker. Gunakan `docker compose down -v` hanya jika ingin menghapus seluruh data volume).*
