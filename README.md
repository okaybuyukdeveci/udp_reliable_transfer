# NetProbe: UDP Tabanlı Güvenilir Dosya Aktarım Platformu

Bursa Teknik Üniversitesi — Bilgisayar Ağları Dersi Dönem Projesi

## Proje Yapısı

```
network_proje/
├── src/
│   ├── protocol.py       # Paket kodlama/çözme (DATA + ACK)
│   ├── server.py         # UDP sunucusu
│   ├── client.py         # UDP istemcisi (Stop-and-Wait & Go-Back-N)
│   ├── logger.py         # Olay kayıt sistemi (CSV + JSON)
│   └── network_sim.py    # Yapay kayıp/gecikme simülatörü
├── analysis/
│   ├── metrics.py        # Performans metrikleri (throughput, goodput vb.)
│   ├── plot.py           # Grafik üretici (matplotlib)
│   ├── run_experiments.py # 4 senaryo otomatik deney koşucusu
│   └── tcp_compare.py    # TCP karşılaştırma modülü (bonus)
├── logs/                 # Çalışma zamanı log dosyaları
├── test_files/           # Deney dosyaları
├── results/              # Deney sonuçları ve grafikler
└── received_files/       # Sunucunun aldığı dosyalar
```

## Bağımlılıklar

```bash
pip install matplotlib pandas
```

Python 3.10+ gereklidir (yerleşik: `socket`, `hashlib`, `threading`, `csv`, `json`).

## Çalıştırma

### 1. Temel Kullanım

**Terminal 1 — Sunucu:**
```bash
python src/server.py --host 127.0.0.1 --port 5001
```

**Terminal 2 — İstemci:**
```bash
python src/client.py --file test_files/test_1MB.bin --host 127.0.0.1 --port 5001
```

### 2. Parametreler

| Parametre | Varsayılan | Açıklama |
|-----------|-----------|----------|
| `--chunk-size` | 1024 | Paket başına veri (byte) |
| `--timeout` | 1.0 | ACK bekleme süresi (saniye) |
| `--max-retries` | 5 | Maksimum yeniden gönderim |
| `--window-size` | 1 | 1=Stop-and-Wait, >1=Go-Back-N |
| `--loss-rate` | 0.0 | Simüle kayıp oranı (0.0–1.0) |
| `--delay-ms` | 0.0 | Simüle gecikme (ms) |

### 3. Kayıp Simülasyonu ile Test

```bash
# Sunucu tarafında %10 kayıp
python src/server.py --loss-rate 0.1

# İstemci tarafında %10 kayıp + 2s timeout
python src/client.py --file test_files/test_1MB.bin --loss-rate 0.1 --timeout 2.0
```

### 4. Go-Back-N (Sliding Window) Modu

```bash
python src/client.py --file test_files/test_1MB.bin --window-size 8
```

### 5. Tüm Deneyleri Çalıştır

```bash
python analysis/run_experiments.py
```

Sonuçlar `results/` klasörüne, grafikler PNG olarak kaydedilir.

### 6. TCP Karşılaştırması

```bash
python analysis/tcp_compare.py --file test_files/test_1MB.bin \
    --udp-summary logs/summary_client_XXXX.json
```

## Protokol Tasarımı

### Veri Paketi
```
| type(1B) | seq_num(4B) | total_pkts(4B) | payload_len(2B) | checksum(16B MD5) | payload |
```

### ACK Paketi
```
| type(1B) | ack_num(4B) | checksum(4B CRC32) |
```

## Güvenilirlik Mekanizmaları

- **Sequence number:** Her pakete sıra numarası atanır
- **ACK:** Sunucu her başarılı paketi onaylar
- **Timeout:** ACK gelmezse `--timeout` sonrası yeniden gönderim
- **Max retries:** Varsayılan 5 deneme; başarısızsa hata loglanır
- **Duplicate tespiti:** Sunucu aynı seq_num'u ikinci kez yazmaz, ACK tekrarlar
- **Checksum (MD5):** Her paketin verisi MD5 ile doğrulanır
- **Bütünlük:** Aktarım sonunda dosyanın MD5'i karşılaştırılır

## Deney Senaryoları

| # | Değişken | Sabit |
|---|---------|-------|
| 1 | Paket boyutu: 256B/512B/1KB/4KB | 1MB dosya, timeout=1s |
| 2 | Timeout: 0.1s/0.5s/1s/2s | 1MB, 1KB paket, loss=5% |
| 3 | Kayıp: 0%/5%/10%/20% | 1MB, 1KB paket, timeout=1s |
| 4 | Dosya: 10KB/100KB/1MB/10MB | 1KB paket, timeout=1s |
