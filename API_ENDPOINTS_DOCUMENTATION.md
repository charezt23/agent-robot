## 2. Auth Routes

### POST `/api/login-by-nik`
Login menggunakan NIK untuk mendapatkan token, token otomatis tercache di Backend selama tidak diclear cache

**Request:**
- Method: `POST`
- Headers: 
  - `Content-Type: application/json`
- Body:
```json
{
  "nik": "1404151812690001"
}
```

**Response Success (200):**
```json
{
    "success": true,
    "data": {
        "token_preview": "839|fmyc3XcFAUUzPgCO27A7353V"
    },
    "message": "Login berhasil"
}

---

### POST `/api/clear-session`
Menghapus session (token) dan cache resident.

**Request:**
- Method: `POST`
- Headers: 
  - `Content-Type: application/json`
- Body:
```json
{
  "nik": "1404151812690001"
}
```

**Response Success (200):**
```json
{
    "success": true,
    "message": "Session cleared successfully"
}
```

---

### GET `/api/check-token`
Mengecek apakah token masih valid (exists).

**Request:**
- Method: `GET`
- Headers: Tidak diperlukan
- Body: Tidak ada

**Response Success (200):**
```json
{
    "success": true,
    "data": {
        "valid": false
    }
}
```

---

## 3. Resident Routes

### GET `/api/resident/:nik`
Mengambil data penduduk berdasarkan NIK dari external API.

**Request:**
- Method: `GET`
- Headers: Tidak diperlukan
- Path Parameters:
  - `nik`: string (required) - NIK penduduk

**Response Success (200):**
```json
{
    "success": true,
    "data": {
        "nik": "1404151812690001",
        "nama": "NURSODIK",
        "tempat_lahir": "CILACAP",
        "tanggal_lahir": "1969-12-18",
        "alamat": "Jl.",
        "rt": "005",
        "rw": "002",
        "jenis_kelamin": "L",
        "agama": "Islam",
        "pekerjaan": "Karyawan Swasta"
    }
}
```

---

### GET `/api/resident/:nik/cache`
Mengambil data penduduk dari cache Backend.

**Request:**
- Method: `GET`
- Headers: Tidak diperlukan
- Path Parameters:
  - `nik`: string (required) - NIK penduduk

**Response Success (200):**
```json
{
    "success": true,
    "data": {
        "name": "NURSODIK",
        "birth_place": "CILACAP",
        "birth_date": "1969-12-18T00:00:00.000000Z",
        "gender": "L",
        "age": 55,
        "address": "Jl.",
        "religion": "Islam",
        "education": "Tamat SD",
        "occupation": "Karyawan Swasta"
    }
}
```

---

## 4. KTP Routes

### POST `/api/upload-ktp`
Upload gambar KTP dan proses OCR untuk mengekstrak NIK.

**Request:**
- Method: `POST`
- Headers: 
  - `Content-Type: multipart/form-data`
- Body (FormData):
  - `ktpImage`: File (required) - File gambar KTP
    - Format yang didukung: image/jpeg, image/png, image/jpg
    - Validasi: File harus berupa gambar valid

**Response Success (200):**
```json
{
    "success": true,
    "data": {
        "nik": "1404151812690001"
    }
}

---

## 5. Letter Routes

### POST `/api/create-letter`
Membuat aplikasi surat (SKTM, dll) melalui Letter API.

**Request:**
- Method: `POST`
- Headers: 
  - `Content-Type: application/json`
- Body:
```json

SKTM
{
  "letter_type_id": 1,
  "custom_data": {
    "keterangan": "Beasiswa Anak"
  }
}

SKDP
{
  "letter_type_id": 3,
  "custom_data": {
    "keterangan": "Beasiswa Anak"
  }
}

SKU
{
  "letter_type_id": 4,
    "custom_data": {
    "nama_usaha": "Warung Sembako",
    "jenis_usaha": "Perdagangan",
    "lokasi_usaha": "Jl. Merdeka No. 1"
  }
}
```

**Response Success (200):**
```json
{
    "success": true,
    "message": "Surat berhasil diterbitkan dan siap diunduh",
    "data": {
        "letter": {
            "id": 35,
            "letter_type": {
                "id": 4,
                "name": "SKU",
                "description": "Global Template : Surat Keterangan Usaha"
            },
            "number": "2/SK/33.01.20.2003/XI/2025",
            "status": "issued",
            "application_status": "approved",
            "auto_approved": true,
            "digital_signature": "0g5scAzwFcuTTqnZTnd1F9KQaPqt30xvQ5ZUozScSYiUcxGXSARD6mfe6GR5AU3nIUwxwJJ0g2Vr8Tvz5Qv2yUXun7gjhiSk90qFpmVz6KKyJYjJ3yvJ7OC5hePqdVXJ",
            "issue_date": "2025-11-29",
            "approved_at": "2025-11-29 02:31:00",
            "created_at": "2025-11-29 02:31:00"
        },
        "download_url_pdf": "https://b26a799f93f3.ngrok-free.app/signature/0g5scAzwFcuTTqnZTnd1F9KQaPqt30xvQ5ZUozScSYiUcxGXSARD6mfe6GR5AU3nIUwxwJJ0g2Vr8Tvz5Qv2yUXun7gjhiSk90qFpmVz6KKyJYjJ3yvJ7OC5hePqdVXJ"
    }
}
```

---

### GET `/api/proxy-letter-pdf`
Proxy endpoint untuk mengambil file PDF surat dari Resident API dengan resolusi CORS. parameter url diperoleh dari body respon /api/create-letter field download_url_pdf

**Request:**
- Method: `GET`
- Headers: Tidak diperlukan
- Query Parameters:
  - `url`: string (required) - URL PDF yang sudah di-encode

**Response Success (200):**
- Content-Type: `application/pdf` atau sesuai tipe file
- Body: Binary PDF file


---


