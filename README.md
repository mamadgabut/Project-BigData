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

Di dashboard ini terdapat 2 DAG yang sudah berjalan otomatis:
1. **`dag_voi_bronze_pipeline`** (Collecting): Scrape berita VOI $\rightarrow$ Validasi null & duplikasi $\rightarrow$ Simpan ke tabel `bronze.articles`. Berjalan otomatis setiap **5 menit**.
2. **`dag_voi_silver_pipeline`** (Processing): Mengambil data Bronze $\rightarrow$ Pembersihan teks, filter tag & redaksi $\rightarrow$ Simpan ke tabel `silver.articles`. Berjalan otomatis setiap **10 menit**.

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
│   └── script/
│       ├── main.py             # Crawler scraper VOI
│       ├── validate_raw.py     # Validasi NULL, duplikasi & ekstraksi hash
│       ├── save_raw.py         # Ingestion data mentah ke Bronze DB
│       ├── preprocessing.py    # Transformasi & Ingestion ke Silver DB
│       └── db_connection.py    # Helper koneksi database (Docker & Host)
├── db/
│   └── init_lakehouse.sql      # Inisialisasi schema & tabel Medallion
├── docker-compose.yaml         # Orkestrator Airflow & Postgres
├── .env.example                # Template konfigurasi environment
├── .gitignore                  # File/folder yang diabaikan Git
└── README.md                   # Dokumentasi project
```

---

## 🛑 Cara Menghentikan Container
Jika selesai bekerja dan ingin menghemat RAM:
```bash
docker compose down
```
*(Data di database tetap aman tersimpan di volume Docker).*
