# NetProbe — Sunum Notları ve Demo Rehberi

Dönem sonu sunumuna hazırlık için slayt sırası, konuşma önerileri ve canlı demo adımları.

---

## Slayt Sırası ve Konuşma Önerileri

---

### Slayt 1 — Kapak

**Başlık:** NetProbe: UDP Tabanlı Güvenilir Dosya Aktarımı  
**Alt:** Bursa Teknik Üniversitesi — Bilgisayar Ağları Dönem Projesi

**Konuşma:** "Bugün size UDP üzerinde güvenilirlik mekanizmalarını sıfırdan tasarladığımız NetProbe platformunu sunacağız."

---

### Slayt 2 — Motivasyon: Neden UDP?

**İçerik:**
- UDP: hızlı, basit, başlık 8 byte — ama güvenilir değil
- TCP: güvenilir, ama overhead yüksek
- **Soru:** UDP üzerinde güvenilirlik nasıl sağlanır?

**Konuşma:** "UDP doğası gereği paket kaybına, sıra bozukluğuna ve yinelenen paketlere karşı kör. Peki bu sorunları uygulama katmanında kendimiz çözsek?"

---

### Slayt 3 — Proje Kapsamı

**İçerik (3 kutu):**
```
[UDP Dosya Aktarımı]    [Trafik İzleme]    [Performans Analizi]
Sequence number          Olay kaydı          Throughput
ACK mekanizması          CSV + JSON log      Goodput
Timeout + Retransmit     Timestamp           RTT, Kayıp Oranı
Checksum (MD5)           Özet istatistik     4 Deney Senaryosu
```

---

### Slayt 4 — Sistem Mimarisi

**İçerik:** Mimari diyagram (TEKNIK_RAPOR.md §3'teki ASCII şema veya temiz bir görsel)

**Konuşma:** "Sistem iki ana process'ten oluşuyor: istemci ve sunucu. Aralarındaki iletişim tamamen UDP socket üzerinden. Her iki taraf da tüm olayları logger modülüne yazar; analiz katmanı bu loglardan metrikleri çıkarır ve grafik üretir."

---

### Slayt 5 — Protokol Tasarımı: Paket Yapısı

**İçerik:** Veri paketi ve ACK paketi tablo formatında

```
DATA: | type(1B) | seq(4B) | total(4B) | len(2B) | MD5(16B) | payload |
ACK:  | type(1B) | ack(4B) | CRC32(4B) |
```

**Konuşma:** "Veri paketi 27 byte sabit başlık taşıyor. MD5 checksum ile payload bütünlüğü garanti altına alınıyor. ACK paketi ise yalnızca 9 byte — küçük tutmak gecikmeyi minimize eder."

---

### Slayt 6 — Güvenilirlik Mekanizmaları

**İçerik:**
- Sequence number → sıra takibi
- ACK → onaylama
- Timeout → kayıp tespiti
- Retransmit (max 5) → yeniden gönderim
- Duplicate tespiti → veri bütünlüğü
- MD5 hash karşılaştırma → dosya bütünlüğü

**Vurgu:** "Bu mekanizmaların hiçbirini TCP kütüphanesinden almadık. Hepsini `socket` modülü üzerine sıfırdan yazdık."

---

### Slayt 7 — Stop-and-Wait vs Go-Back-N

**İçerik:** İki zaman çizelgesi diyagramı yan yana

**Konuşma:** "Stop-and-wait her paket için ACK bekler — basit ama yavaş. Go-Back-N aynı anda window_size kadar paket gönderir. Kayıp durumunda kaybolan paketin sırasından itibaren penceredeki tüm paketler yeniden gönderilir. Sistemimiz window_size=1 ile stop-and-wait, büyük değerlerle go-back-n olarak çalışıyor."

---

### Slayt 8 — Ağ Simülatörü

**İçerik:**
```python
class SimulatedSocket:
    def sendto(self, data, addr):
        if random.random() < self.loss_rate:
            return  # Paket düşürüldü
        self._sock.sendto(data, addr)
```

**Konuşma:** "Harici araç gerektirmeden kayıp simülasyonu için gerçek UDP soketini saran SimulatedSocket sınıfı yazdık. loss_rate ve delay_ms parametreleriyle kontrol edilebilir."

---

### Slayt 9 — Loglama Sistemi

**İçerik:** Örnek CSV + JSON çıktı ekran görüntüsü

**Konuşma:** "Her aktarım iki dosya üretiyor: satır bazlı olay kaydı (CSV) ve özet istatistik (JSON). Oturum ID ile eşleştirilmiş bu dosyalar analiz ve grafik üretiminde kullanılıyor."

---

### Slayt 10 — Deney Sonuçları: Senaryo 1 (Paket Boyutu)

**İçerik:** `results/scenario1_packet_size.png` grafiği

**Konuşma:** "Paket boyutu arttıkça başlık overhead'i amortize oluyor ve throughput yükseliyor. 1KB üzerinde kazanç azalıyor çünkü MTU sınırına yaklaşılıyor."

---

### Slayt 11 — Deney Sonuçları: Senaryo 2 (Timeout)

**İçerik:** `results/scenario2_timeout.png` grafiği

**Konuşma:** "Çok küçük timeout gereksiz retransmission'a yol açıyor. Çok büyük timeout ise gerçek kayıplarda beklemeyi uzatıyor. Optimal değer ortalama RTT'nin 3-5 katı civarında."

---

### Slayt 12 — Deney Sonuçları: Senaryo 3 (Kayıp Oranı)

**İçerik:** `results/scenario3_loss_rate.png` grafiği

**Konuşma:** "Bu en kritik senaryo. Kayıp arttıkça throughput ile goodput arasındaki fark açılıyor — overhead büyüyor. %20 kayıpta stop-and-wait neredeyse kullanılamaz hale geliyor; bu noktada go-back-n'nin önemi ortaya çıkıyor."

---

### Slayt 13 — Deney Sonuçları: Senaryo 4 (Dosya Boyutu)

**İçerik:** `results/scenario4_file_size.png` grafiği

**Konuşma:** "Küçük dosyalarda başlangıç overhead'i oransal olarak büyük. Dosya büyüdükçe throughput stabilleşiyor. 10MB aktarımında Go-Back-N modu ciddi avantaj sağlıyor."

---

### Slayt 14 — UDP vs TCP Karşılaştırması (Bonus)

**İçerik:** `results/udp_vs_tcp.png` karşılaştırma grafiği

**Konuşma:** "Loopback gibi ideal ortamda TCP daha hızlı çünkü kernel seviyesinde optimize. Kayıplı ortamda ise bizim Go-Back-N implementasyonumuz TCP'ye yakın performans gösteriyor."

---

### Slayt 15 — Sonuç

**İçerik:**

✅ UDP üzerinde güvenilir dosya aktarımı  
✅ Sequence number, ACK, timeout, retransmit  
✅ Duplicate tespiti ve MD5 bütünlük doğrulama  
✅ Kapsamlı loglama ve 4 senaryo deney  
✅ Stop-and-Wait + Go-Back-N (bonus)  
✅ Ağ simülatörü (bonus)  
✅ TCP karşılaştırması (bonus)  

**Konuşma:** "NetProbe, bilgisayar ağları ders kitaplarında teorik olarak anlatılan güvenilir veri aktarım protokolünü çalışan bir sistemde somutlaştırdı. Tüm mekanizmaları sıfırdan tasarladık."

---

### Slayt 16 — Sorular

**İçerik:** "Sorularınız için teşekkürler"

---

## Canlı Demo Adımları

Sunumda canlı demo yapacaksan aşağıdaki sırayı takip et:

### Adım 1 — Temel Aktarım

```bash
# Terminal 1:
python src/server.py --port 5001

# Terminal 2:
python src/client.py --file test_files/test_1MB.bin --port 5001
```

Gösterilecek: Her iki terminalde de paket sayacı çalışıyor, aktarım sonunda MD5 eşleşiyor.

### Adım 2 — Kayıp Simülasyonu

```bash
# Terminal 1 (sunucu %10 kayıp):
python src/server.py --port 5002 --loss-rate 0.1

# Terminal 2 (istemci):
python src/client.py --file test_files/test_1MB.bin --port 5002 --timeout 0.5
```

Gösterilecek: Timeout ve retransmission logları, yine de başarılı aktarım.

### Adım 3 — Go-Back-N vs Stop-and-Wait Hız Farkı

```bash
# Stop-and-Wait:
python src/client.py --file test_files/test_1MB.bin --port 5001 --window-size 1

# Go-Back-N (aynı dosya, farklı pencere):
python src/client.py --file test_files/test_1MB.bin --port 5001 --window-size 8
```

Gösterilecek: Süre farkı.

### Adım 4 — Log Dosyalarını Göster

```bash
cat logs/summary_client_*.json | python3 -m json.tool
```

### Adım 5 — Grafikleri Aç

`results/` klasöründeki PNG dosyalarını ekran paylaşımıyla göster.

---

## Olası Soru-Cevaplar

**S: "TCP kullanmak yerine neden UDP'ye güvenilirlik eklediniz?"**  
C: "Bu projenin amacı TCP'nin altında yatan mekanizmaları anlamak ve sıfırdan uygulamak. Gerçek hayatta ses/video gibi gecikmeye duyarlı uygulamalar UDP tabanlı protokol geliştiriyor — QUIC, RTP gibi."

**S: "MD5 güvenli bir checksum mı?"**  
C: "Kriptografik güvenlik için hayır, ama veri bütünlüğü kontrolü için yeterli. Dosya aktarımında bit hatalarını yakalamak için MD5 pratik ve hızlı bir seçim. Güvenlik gerekseydi SHA-256 kullanırdık."

**S: "Go-Back-N neden Selective Repeat kadar verimli değil?"**  
C: "Go-Back-N'de kayıp paket varsa o sıra numarasından itibaren tüm pencere yeniden gönderilir. Selective Repeat'te yalnızca kayıp paket yeniden gönderilir. Yüksek kayıp oranlarında Selective Repeat çok daha verimli. Bunu gelecek geliştirme olarak not ettik."

**S: "Çoklu istemci destekliyor mu?"**  
C: "Mevcut implementasyonda sunucu seri çalışıyor — bir aktarım biter, diğerini bekler. Threading ekleyerek her bağlantı için ayrı iş parçacığı açılabilir. Mimari bunu destekleyecek şekilde modüler tasarlandı."
