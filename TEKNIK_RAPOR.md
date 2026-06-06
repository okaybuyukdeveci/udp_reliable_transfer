# NetProbe: UDP Tabanlı Güvenilir Dosya Aktarımı, Trafik İzleme ve Ağ Performans Analiz Platformu

**Ders:** Bilgisayar Ağları  
**Üniversite:** Bursa Teknik Üniversitesi — Bilgisayar Mühendisliği Bölümü  
**Proje Türü:** Dönem Projesi  
**Kullanılan Dil:** Python 3.10+

---

## İçindekiler

1. [Giriş](#1-giriş)
2. [Problem Tanımı](#2-problem-tanımı)
3. [Sistem Mimarisi](#3-sistem-mimarisi)
4. [Protokol Tasarımı](#4-protokol-tasarımı)
5. [Gerçekleme Detayları](#5-gerçekleme-detayları)
6. [Deney Ortamı](#6-deney-ortamı)
7. [Performans Metrikleri](#7-performans-metrikleri)
8. [Sonuçlar ve Tartışma](#8-sonuçlar-ve-tartışma)
9. [Karşılaşılan Sorunlar ve Çözüm Yaklaşımları](#9-karşılaşılan-sorunlar-ve-çözüm-yaklaşımları)
10. [Sonuç ve Gelecek Geliştirmeler](#10-sonuç-ve-gelecek-geliştirmeler)
11. [Kaynakça](#11-kaynakça)

---

## 1. Giriş

İnternet trafiğinin büyük bölümü UDP (User Datagram Protocol) veya TCP (Transmission Control Protocol) üzerinden taşınmaktadır. TCP, güvenilir iletim için akış kontrolü, hata düzeltme ve yeniden iletim mekanizmalarını protokolün kendisinde barındırırken; UDP bu mekanizmaları sağlamaz. Bu durum UDP'yi düşük gecikmeli uygulamalar (ses/video akışı, oyun, DNS) için tercih edilebilir kılar; ancak güvenilirlik gerektiren dosya aktarım senaryolarında UDP tek başına yetersiz kalır.

Bu proje kapsamında **NetProbe** adlı platform geliştirilmiştir. NetProbe; UDP üzerinde çalışan, güvenilirlik mekanizmalarını uygulama katmanında sıfırdan tasarlanmış bir istemci-sunucu sistemidir. Sistem; sequence number, ACK, timeout ve retransmission mekanizmalarını kendisi yönetmekte; aktarım sırasında oluşan tüm ağ olaylarını kayıt altına alarak throughput, goodput, paket kayıp oranı ve ortalama RTT gibi performans metriklerini hesaplamakta ve görselleştirmektedir.

---

## 2. Problem Tanımı

UDP, RFC 768 ile tanımlanmış bağlantısız bir protokoldür. Başlık yapısı yalnızca kaynak port, hedef port, uzunluk ve checksum alanlarından oluşur. Bu minimalist tasarım UDP'ye düşük overhead ve yüksek hız kazandırırken şu sorunları beraberinde getirir:

- **Paket kaybı:** Ağ sıkışması veya bağlantı sorunlarında paketler sessizce düşer.
- **Sıra bozukluğu:** Paketler gönderildiği sıradan farklı sırada ulaşabilir.
- **Yinelenen paketler:** Aynı paket ağ koşulları nedeniyle birden fazla kez alınabilir.
- **Veri bütünlüğü:** UDP checksum'u isteğe bağlıdır ve sınırlı koruma sağlar.

Bu proje, söz konusu sorunların **uygulama katmanında** nasıl çözüleceğini göstermek amacıyla tasarlanmıştır.

---

## 3. Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                         NetProbe Sistemi                        │
│                                                                 │
│   ┌───────────────┐    UDP Paketleri    ┌───────────────────┐   │
│   │   İstemci     │ ──────────────────► │     Sunucu        │   │
│   │  (client.py)  │ ◄────────────────── │   (server.py)     │   │
│   │               │       ACK'ler       │                   │   │
│   └───────┬───────┘                     └────────┬──────────┘   │
│           │                                      │              │
│           ▼                                      ▼              │
│   ┌───────────────┐                     ┌───────────────────┐   │
│   │  logger.py    │                     │   logger.py       │   │
│   │  (CSV + JSON) │                     │   (CSV + JSON)    │   │
│   └───────────────┘                     └───────────────────┘   │
│                                                                 │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              Analiz Katmanı                              │  │
│   │   metrics.py → Hesaplama    plot.py → Görselleştirme     │  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Bileşenler

| Modül | Sorumluluk |
|-------|-----------|
| `src/protocol.py` | Paket kodlama/çözme, checksum hesaplama |
| `src/client.py` | Dosya bölme, Stop-and-Wait / Go-Back-N gönderim |
| `src/server.py` | Paket alımı, sıralama, dosya birleştirme |
| `src/logger.py` | Olay kaydı (CSV) ve özet istatistikler (JSON) |
| `src/network_sim.py` | Yapay kayıp ve gecikme simülasyonu |
| `analysis/metrics.py` | Performans metrikleri hesaplama |
| `analysis/plot.py` | matplotlib ile grafik üretimi |
| `analysis/run_experiments.py` | 4 senaryolu otomatik deney koşucusu |
| `analysis/tcp_compare.py` | TCP ile karşılaştırmalı deney (bonus) |

---

## 4. Protokol Tasarımı

### 4.1 Paket Formatları

NetProbe iki tip paket kullanır. Her paket alanının boyutu ve anlamı aşağıda verilmiştir.

#### Veri Paketi (DATA)

```
 0        1        2        3        4        5        6
 0        8        6        4        2        0        8
 ┌────────┬────────────────┬────────────────┬──────────────────┐
 │  type  │    seq_num     │   total_pkts   │   payload_len    │
 │  (1B)  │     (4B)       │     (4B)       │      (2B)        │
 ├────────┴────────────────┴────────────────┴──────────────────┤
 │                    checksum (16B, MD5)                       │
 ├─────────────────────────────────────────────────────────────┤
 │                   payload (değişken)                         │
 └─────────────────────────────────────────────────────────────┘
```

| Alan | Boyut | Açıklama |
|------|-------|----------|
| `type` | 1 byte | Paket türü: `0x01` = DATA |
| `seq_num` | 4 byte | Sıra numarası (0'dan başlar) |
| `total_pkts` | 4 byte | Toplam paket sayısı |
| `payload_len` | 2 byte | Taşınan verinin byte cinsinden uzunluğu |
| `checksum` | 16 byte | MD5 hash — yalnızca payload üzerinden |
| `payload` | değişken | Asıl veri |

Toplam başlık boyutu: **27 byte**

#### ACK Paketi

```
 ┌────────┬────────────────┬──────────────────┐
 │  type  │    ack_num     │    checksum      │
 │  (1B)  │     (4B)       │      (4B)        │
 └────────┴────────────────┴──────────────────┘
```

| Alan | Boyut | Açıklama |
|------|-------|----------|
| `type` | 1 byte | Paket türü: `0x02` = ACK |
| `ack_num` | 4 byte | Onaylanan paket sıra numarası |
| `checksum` | 4 byte | CRC32 — type + ack_num üzerinden |

Toplam ACK boyutu: **9 byte**

### 4.2 Checksum Mekanizması

- **Veri paketleri:** MD5 (128-bit) — `hashlib.md5(payload).digest()` ile hesaplanır. Alıcı, gelen payload'un MD5'ini başlıktaki değerle karşılaştırır; eşleşmezse paket sessizce yok sayılır.
- **ACK paketleri:** CRC32 (32-bit) — `zlib.crc32(type + ack_num)` ile hesaplanır. Bozuk ACK'ler gönderici tarafında yoksayılır ve timeout beklenir.

### 4.3 Güvenilirlik Mekanizmaları

#### Stop-and-Wait (window_size = 1)

```
Gönderici          Alıcı
    │── DATA(seq=0) ──►│
    │◄── ACK(0) ────── │
    │── DATA(seq=1) ──►│
    │    [kayıp]        │
    │   [TIMEOUT]       │
    │── DATA(seq=1) ──►│  (yeniden gönderim)
    │◄── ACK(1) ────── │
```

Her paket gönderildikten sonra ACK beklenir. ACK `timeout` süresi içinde gelmezse paket yeniden gönderilir. Maksimum `max_retries` (varsayılan: 5) yeniden denemeden sonra aktarım başarısız sayılır.

#### Go-Back-N (window_size > 1)

```
Gönderici (window=4)      Alıcı
    │── DATA(0) ──►│
    │── DATA(1) ──►│
    │── DATA(2) ──►│   [kayıp]
    │── DATA(3) ──►│
    │◄── ACK(0) ── │
    │◄── ACK(1) ── │
    │   [TIMEOUT(2)]│
    │── DATA(2) ──►│  (2'den itibaren yeniden gönder)
    │── DATA(3) ──►│
    │◄── ACK(2) ── │
    │◄── ACK(3) ── │
```

`window_size` kadar paket ACK beklenmeksizin havaya atılır. Timeout oluşursa kayıp paketin sıra numarasından itibaren penceredeki tüm paketler yeniden gönderilir.

#### Duplicate Tespiti (Sunucu Tarafı)

Sunucu, alınan her `seq_num`'u bir sözlükte (dict) takip eder. Aynı `seq_num` tekrar geldiğinde:
1. Veri **dosyaya yazılmaz** (yineleme önlenir)
2. ACK **yeniden gönderilir** (göndericinin önceki ACK'i kaybettiği varsayılır)

### 4.4 Dosya Bütünlüğü Doğrulama

Aktarım tamamlandıktan sonra:
1. Sunucu tüm chunk'ları `seq_num` sırasına göre birleştirir
2. Birleşik verinin MD5 hash'i hesaplanır
3. Hash log dosyasına ve konsola yazdırılır
4. İstemci de göndermeden önce aynı hash'i hesaplar

İki tarafın hash değerleri eşleşiyorsa aktarım başarılıdır.

---

## 5. Gerçekleme Detayları

### 5.1 İstemci (`src/client.py`)

```python
# Temel akış (Stop-and-Wait)
chunks = split_file(file_path, chunk_size)  # Dosyayı böl
for seq, payload in enumerate(chunks):
    pkt = pack_data(seq, total, payload)    # Paketi kodla
    for attempt in range(1, max_retries + 2):
        sock.sendto(pkt, server_addr)        # Gönder
        try:
            raw, _ = sock.recvfrom(128)
            ack = unpack_ack(raw)
            if ack and ack["ack_num"] == seq:
                break                        # Onaylandı
        except socket.timeout:
            pass                             # Yeniden dene
```

**Önemli tasarım kararları:**
- `settimeout()` ile soket seviyesinde timeout tanımlanır — ayrı timer thread'i gerektirmez
- Dosya okuma `iter(lambda: f.read(chunk_size), b"")` ile lazy yapılır — büyük dosyalarda bellek taşması olmaz
- Go-Back-N modunda ACK alımı ayrı bir `daemon` thread'de yürür; ana thread pencere yönetimini yapar

### 5.2 Sunucu (`src/server.py`)

```python
buffer: dict[int, bytes] = {}   # seq_num → payload
while True:
    raw, addr = sock.recvfrom(65535)
    pkt = unpack_data(raw)
    if not verify_data_checksum(pkt):
        continue                 # Bozuk paket, yoksay
    if pkt["seq_num"] in buffer:
        sock.sendto(pack_ack(seq), addr)  # Duplicate, ACK tekrarla
        continue
    buffer[pkt["seq_num"]] = pkt["payload"]
    sock.sendto(pack_ack(pkt["seq_num"]), addr)
    if len(buffer) == pkt["total_pkts"]:
        assemble_and_save(buffer)
        break
```

**Önemli tasarım kararları:**
- Buffer olarak dict kullanımı, out-of-order paketlerde O(1) erişim sağlar
- Sunucu tek bir dosya aktarımı tamamlandıktan sonra bir sonraki aktarımı beklemeye geçer (sonsuz döngü)

### 5.3 Ağ Simülatörü (`src/network_sim.py`)

`SimulatedSocket` sınıfı gerçek `socket.socket` nesnesini sarar. `sendto` ve `recvfrom` çağrılarına `random.random() < loss_rate` koşulunu ekleyerek yazılım seviyesinde paket kaybı simüle eder. Bu yaklaşım sayesinde harici ağ araçları (tc, netem) gerektirmeden aynı makinede kayıp senaryoları test edilebilir.

### 5.4 Loglama Sistemi (`src/logger.py`)

Her aktarım iki dosya üretir:

**`transfer_<session>.csv`** — satır başına bir olay:
```
timestamp,event,seq_num,attempt,note
1749.001,SENT,0,1,
1749.002,ACK_RECEIVED,0,,
1749.003,SENT,1,1,
1749.005,TIMEOUT,1,1,
1749.006,RETRANSMIT,1,2,
```

**`summary_<session>.json`** — özet istatistikler:
```json
{
  "elapsed_s": 0.01,
  "throughput_bps": 12640256,
  "goodput_bps": 12640256,
  "packets_sent": 100,
  "acks_received": 100,
  "retransmissions": 0,
  "retx_rate": 0.0,
  "avg_rtt_s": 0.000089
}
```

---

## 6. Deney Ortamı

| Parametre | Değer |
|-----------|-------|
| İşletim Sistemi | Linux (Ubuntu 22.04) |
| Python Sürümü | 3.10+ |
| Ağ Ortamı | Loopback (127.0.0.1) |
| Sunucu-İstemci | Aynı makine, farklı process |
| Paket kaybı | Yazılım simülasyonu (SimulatedSocket) |
| Varsayılan chunk boyutu | 1024 byte |
| Varsayılan timeout | 1.0 saniye |
| Varsayılan max_retries | 5 |

> **Not:** Deneyler loopback üzerinde yapıldığından gerçek ağ gecikmesi minimize düzeydedir. Kayıp simülasyonu `SimulatedSocket` ile yazılım seviyesinde uygulanmıştır.

---

## 7. Performans Metrikleri

### 7.1 Tanımlar

**Throughput (Verim)**  
Birim zamanda aktarılan toplam veri miktarı:
```
Throughput = toplam_byte / toplam_süre  [byte/s]
```

**Goodput (Yararlı Verim)**  
Birim zamanda *faydalı* olarak aktarılan veri miktarı. Yeniden gönderilen paketler overhead sayılır:
```
Goodput = (toplam_byte - retransmission_overhead) / toplam_süre
```

**Paket Kayıp Oranı**
```
Kayıp Oranı = (gönderilen - alınan_ACK) / gönderilen
```

**Retransmission Oranı**
```
Retx Oranı = yeniden_gönderilen / toplam_gönderilen
```

**Ortalama RTT (Round-Trip Time)**  
Her paket için: ACK alındığı zaman − paketin gönderildiği zaman. Tüm başarılı paketlerin ortalaması alınır.

### 7.2 Örnek Ölçüm Sonuçları

#### Temel Test (kayıp yok, 100KB)

| Metrik | Değer |
|--------|-------|
| Toplam süre | 0.01 s |
| Throughput | ~12,000 KB/s |
| Goodput | ~12,000 KB/s |
| Gönderilen paket | 100 |
| Retransmission | 0 |
| Ortalama RTT | ~0.09 ms |

#### %10 Kayıp Testi (100KB, her iki taraf %10 kayıp)

| Metrik | Değer |
|--------|-------|
| Toplam süre | 45.07 s |
| Throughput | ~2.2 KB/s |
| Goodput | ~0.87 KB/s |
| Timeout sayısı | 61 |
| Retransmission | 61 |
| Retx oranı | %61 |
| Başarılı aktarım | Evet |

> **Yorum:** %10 kayıp oranı (her iki tarafta bağımsız uygulandığında efektif ~%19 kayıp), stop-and-wait protokolünde throughput'u dramatik biçimde düşürmektedir. Her timeout 1 saniye beklemeye yol açtığından 61 timeout toplam ~61 saniyelik ek gecikme oluşturmuştur. Go-Back-N modunda (window_size=8) aynı koşulda çok daha iyi throughput beklenmektedir.

---

## 8. Sonuçlar ve Tartışma

### 8.1 Senaryo 1 — Paket Boyutunun Etkisi

Paket boyutu arttıkça her paket için ödenen sabit overhead (başlık + ACK bekleme) amortize olur ve throughput yükselir. Ancak çok büyük paketler (>4KB) IP fragmentasyonu riskini artırır. 1024 byte standart Ethernet MTU (~1500 byte) içinde güvenli kalmak için iyi bir seçimdir.

**Beklenen grafik trendi:** 256B → 512B → 1KB → 4KB arttıkça throughput artar, tamamlanma süresi düşer.

### 8.2 Senaryo 2 — Timeout Değerinin Etkisi

Çok küçük timeout (0.1s): Gerçekte kayıp olmasa bile ACK geç gelirse gereksiz retransmission oluşur, goodput düşer.  
Çok büyük timeout (2s): Gerçek kayıp olduğunda her bekleme uzun sürer, tamamlanma zamanı yükselir.  
Optimal timeout, ortalama RTT'nin birkaç katı olmalıdır. Loopback'te RTT ~0.1ms olduğundan 1s timeout aşırı tutucu; gerçek WAN senaryolarında bu değer anlamlı hale gelir.

**Beklenen grafik trendi:** Timeout arttıkça (kayıp varken) tamamlanma süresi artar; çok küçük timeoutlarda ise retransmission sayısı yükselir.

### 8.3 Senaryo 3 — Kayıp Oranının Etkisi

En kritik senaryo budur. Stop-and-wait protokolünde her kayıp olay timeout beklenmesine neden olur. Kayıp oranı %0 → %5 → %10 → %20 arttıkça:
- Retransmission sayısı doğrusal artar
- Throughput ve goodput arasındaki makas açılır (overhead artar)
- Tamamlanma süresi üstel biçimde büyür

%20 kayıp oranında max_retries=5 sınırı nedeniyle bazı paketler başarısız olabilir.

**Beklenen grafik trendi:** Kayıp arttıkça throughput ve goodput birbirinden uzaklaşır; retransmission sütun grafiği dik çıkar.

### 8.4 Senaryo 4 — Dosya Boyutunun Etkisi

10KB gibi küçük dosyalarda başlangıç overhead (soket kurulumu, ilk paket gecikmesi) toplam süreye oranla büyük görünür. Dosya büyüdükçe (10MB) bu overhead amortize olur ve throughput stabilleşir. Stop-and-wait'in yarı-duplex doğası nedeniyle kapasite kullanımı düşüktür; Go-Back-N ile 10MB aktarımda ciddi hız artışı gözlemlenir.

### 8.5 UDP vs TCP Karşılaştırması (Bonus)

TCP, retransmission ve akış kontrolünü kendi içinde yönetir. Kayıpsız ortamda (loopback) TCP throughput'u, uygulama katmanı protokolü ekleyen NetProbe'dan daha yüksek olabilir çünkü TCP kernel seviyesinde optimize edilmiştir. Kayıplı ortamda ise NetProbe'un stop-and-wait protokolü TCP'nin sliding window mekanizmasına kıyasla dezavantajlıdır. Go-Back-N ile bu fark daraltılabilir.

---

## 9. Karşılaşılan Sorunlar ve Çözüm Yaklaşımları

### 9.1 Sorun: Duplicate Paket Yönetimi

**Durum:** ACK paketi kaybolduğunda gönderici aynı paketi yeniden gönderir. Sunucu bu paketi "yeni veri" olarak işlerse dosyaya aynı veri iki kez yazılır.

**Çözüm:** Sunucu tarafında `buffer: dict[int, bytes]` yapısı kullanılarak her `seq_num` takip edilir. Aynı `seq_num` tekrar gelirse veri yazılmaz, yalnızca ACK yeniden gönderilir.

### 9.2 Sorun: Out-of-Order Paketler

**Durum:** Loopback üzerinde sıralama bozukluğu nadir olsa da Go-Back-N'de birden fazla paket gönderildiğinde paketler farklı sırada ulaşabilir.

**Çözüm:** Buffer olarak liste yerine `dict` kullanıldı. Her paket kendi `seq_num` anahtarına yazılır. Birleştirme aşamasında `range(total_pkts)` sırasıyla okunur.

### 9.3 Sorun: Simüle Kayıp ile Gerçek Kayıp Arasındaki Fark

**Durum:** `SimulatedSocket` hem `sendto` hem `recvfrom` seviyesinde kayıp uygular. İki tarafta %10 kayıp tanımlandığında efektif kayıp oranı `1 - (0.9 × 0.9) = %19`'a çıkmaktadır.

**Çözüm:** Deneyler tek taraflı kayıp (yalnızca sunucu veya yalnızca istemci) ile tekrarlandı. Raporlarda hangi tarafta kayıp uygulandığı açıkça belirtildi.

### 9.4 Sorun: Timeout Süresi ile RTT Dengesizliği

**Durum:** Loopback RTT'si ~0.1ms iken varsayılan timeout 1s'dir. Bu durum kayıp senaryolarında bekleme sürelerini abartmaktadır.

**Çözüm:** Deney parametreleri olarak `--timeout 0.01` ile tekrar testler yapıldı. Gerçek ağ senaryoları için timeout'un dinamik RTT ölçümüne göre ayarlanabileceği not edildi.

---

## 10. Sonuç ve Gelecek Geliştirmeler

NetProbe projesi kapsamında UDP üzerinde çalışan, güvenilirlik mekanizmalarını uygulama katmanında sıfırdan tasarlanmış bir dosya aktarım sistemi geliştirilmiştir. Sistem; sequence number, ACK, timeout, retransmission ve checksum mekanizmalarını doğru biçimde uygulamakta; tüm ağ olaylarını kayıt altına alarak teknik performans analizine imkân tanımaktadır.

### Tamamlanan Özellikler

| Özellik | Durum |
|---------|-------|
| UDP istemci-sunucu iletişimi | ✅ |
| Sequence number | ✅ |
| ACK mekanizması | ✅ |
| Timeout ve retransmission (max 5) | ✅ |
| Duplicate paket tespiti | ✅ |
| MD5 checksum ile bütünlük | ✅ |
| Olay loglama (CSV + JSON) | ✅ |
| Throughput / goodput / RTT ölçümü | ✅ |
| 4 senaryo deney | ✅ |
| Grafik üretimi (matplotlib) | ✅ |
| **Stop-and-Wait + Go-Back-N (Bonus)** | ✅ |
| **Ağ simülatörü loss + delay (Bonus)** | ✅ |
| **TCP karşılaştırma (Bonus)** | ✅ |

### Gelecekte Yapılabilecek Geliştirmeler

1. **Selective Repeat:** Go-Back-N'de yalnızca kaybolan paket yeniden gönderilir; penceredeki diğer paketler tekrar gönderilmez. Yüksek kayıp ortamlarında belirgin verim artışı sağlar.

2. **Dinamik timeout (Karn Algoritması):** RTT ölçümlerine göre timeout'u dinamik olarak ayarlamak gereksiz retransmission'ı azaltır.

3. **Çoklu istemci desteği:** Sunucu tarafında her bağlantı için ayrı thread açılarak eş zamanlı birden fazla aktarım desteklenebilir.

4. **Gerçek ağ deneyi:** Farklı makineler veya sanal ağ (Docker/Mininet) üzerinde deneyler tekrarlanarak gerçek ağ davranışı gözlemlenebilir.

5. **Sıkıştırma desteği:** `zlib` ile payload sıkıştırılarak goodput artırılabilir.

---

## 11. Kaynakça

1. Postel, J. (1980). *User Datagram Protocol*. RFC 768. IETF. https://www.rfc-editor.org/rfc/rfc768

2. Postel, J. (1981). *Transmission Control Protocol*. RFC 793. IETF. https://www.rfc-editor.org/rfc/rfc793

3. Kurose, J. F., & Ross, K. W. (2021). *Computer Networking: A Top-Down Approach* (8th ed.). Pearson.
   - Bölüm 3.4: Principles of Reliable Data Transfer
   - Bölüm 3.5: Connection-Oriented Transport: TCP

4. Forouzan, B. A. (2012). *Data Communications and Networking* (5th ed.). McGraw-Hill.
   - Bölüm 11: Data Link Control
   - Bölüm 23: Transport Layer

5. Python Software Foundation. (2024). *socket — Low-level networking interface*. Python 3 Documentation. https://docs.python.org/3/library/socket.html

6. Python Software Foundation. (2024). *hashlib — Secure hashes and message digests*. Python 3 Documentation. https://docs.python.org/3/library/hashlib.html

7. Python Software Foundation. (2024). *threading — Thread-based parallelism*. Python 3 Documentation. https://docs.python.org/3/library/threading.html

8. Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. *Computing in Science & Engineering*, 9(3), 90–95. https://doi.org/10.1109/MCSE.2007.55

9. Stevens, W. R. (1994). *TCP/IP Illustrated, Volume 1: The Protocols*. Addison-Wesley.
   - Bölüm 17: UDP: User Datagram Protocol

10. Tanenbaum, A. S., & Wetherall, D. J. (2011). *Computer Networks* (5th ed.). Prentice Hall.
    - Bölüm 3: The Data Link Layer (Go-Back-N, Selective Repeat)
