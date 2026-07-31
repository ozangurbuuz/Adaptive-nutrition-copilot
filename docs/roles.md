# Kullanıcı Rolleri ve Yetki Sınırları

## Amaç

Bu belge Adaptive Nutrition Copilot içindeki Diyetisyen, Danışan ve Admin rollerinin yetki sınırlarını tanımlar. Sistem bir klinik karar destek ürünüdür; tanı koymaz, tedavi önermez ve diyetisyen onayının yerini almaz.

## Temel Güvenlik İlkeleri

1. Klinik sorumluluk ve nihai karar Diyetisyendedir.
2. Danışan yalnızca kendisine atanmış ve onaylanmış verilere erişebilir.
3. Admin sistem işletimini yönetir; klinik karar vermez.
4. Riskli sağlık durumları otomatik öneri akışını durdurur ve Diyetisyene yönlendirilir.
5. Besin değişim hesabını yalnızca deterministik değişim motoru yapar.
6. LLM hesaplama, tanı, tedavi veya plan onayı yapmaz; yalnızca açıklama, konuşma ve metin biçimlendirme görevlerinde kullanılır.
7. Yetkili işlemler ve öneri kararları denetlenebilir bir kayıt bırakmalıdır.

## Roller

### Diyetisyen

Yapabilir:

- Kendisine bağlı danışan profillerini oluşturabilir, görüntüleyebilir ve güncelleyebilir.
- Danışanın alerji, kısıt ve tercih kayıtlarını yönetebilir.
- Beslenme planı oluşturabilir, güncelleyebilir, onaylayabilir ve geri çekebilir.
- Besin değişim kurallarını ve toleranslarını yetkisi kapsamında tanımlayabilir.
- Danışanın değişim taleplerini, sonuçlarını ve karar gerekçelerini inceleyebilir.
- Riskli olarak işaretlenen vakaları değerlendirebilir.

Yapamaz:

- Yetkisi olmayan başka bir diyetisyenin danışanlarına erişemez.
- Kaynağı doğrulanmamış besin verisini güvenilir veri gibi sisteme ekleyemez.
- Denetim kayıtlarını değiştiremez veya silemez.

### Danışan

Yapabilir:

- Kendi profilinin izin verilen bölümünü görüntüleyebilir.
- Kendisine atanmış ve onaylanmış beslenme planlarını görüntüleyebilir.
- Onaylı bir plandaki besin için alternatif talep edebilir.
- Sistem ve diyetisyen politikası izin veriyorsa deterministik motorun ürettiği alternatifleri görüntüleyebilir veya onaya gönderebilir.
- Kendi tercihlerini bildirebilir.

Yapamaz:

- Başka bir danışanın verisine erişemez.
- Klinik kısıt, alerji veya diyetisyen kuralını tek taraflı olarak kaldıramaz.
- Beslenme planını onaylayamaz veya klinik kuralları değiştiremez.
- Risk kontrolünü atlayamaz.

### Admin

Yapabilir:

- Kullanıcı hesaplarını, rol atamalarını ve sistem erişimini yönetebilir.
- Sistem yapılandırmasını ve işletimsel durumu yönetebilir.
- Yetkili veri kaynağı ve doküman yönetimi işlemlerini gerçekleştirebilir.
- Güvenlik ve denetim kayıtlarını yetkisi kapsamında görüntüleyebilir.

Yapamaz:

- Diyetisyen rolü ayrıca verilmedikçe klinik plan oluşturamaz veya onaylayamaz.
- Besin değişim sonucunu klinik gerekçeyle değiştiremez.
- Denetim kayıtlarını değiştiremez veya silemez.
- Danışan adına klinik karar veremez.

#### Süreli Sağlık Verisi Erişimi

Admin sağlık verisine varsayılan olarak erişemez. İstisnai destek veya güvenlik erişimi için aşağıdaki koşulların tamamı zorunludur:

1. **Gerekçe:** Erişim amacı, destek/güvenlik kayıt numarası ve neden anonimleştirilmiş verinin yeterli olmadığı yazılmalıdır.
2. **Onay:** Admin kendi erişimini onaylayamaz. Yetkili bir onaylayan erişim kapsamını ve süresini onaylamalıdır.
3. **En az yetki:** Erişim belirli danışanlar, veri alanları ve izin verilen işlemlerle sınırlandırılmalıdır; varsayılan yetki salt okunurdur.
4. **Başlangıç ve bitiş:** `starts_at` ve `ends_at` UTC olarak kaydedilmelidir. Erişim başlangıçtan önce çalışmamalı ve bitişte otomatik olarak kapanmalıdır.
5. **Değişmez audit log:** Talep, onay, erişim, görüntülenen kapsam, başarısız deneme, süre uzatma, iptal ve otomatik sona erme olayları değiştirilemez denetim kaydı üretmelidir.
6. **İptal:** Yetkili kişi erişimi bitiş zamanından önce iptal edebilmelidir; iptal anında etkili olmalıdır.

Her erişim yetkisi kaydında en az şu alanlar bulunmalıdır:

| Alan | Gereksinim |
|---|---|
| `access_grant_id` | Tekil erişim yetkisi kimliği |
| `admin_user_id` | Erişim verilen Admin |
| `approved_by_user_id` | Erişimi onaylayan yetkili; Admin ile aynı kişi olamaz |
| `reason` | Açık ve denetlenebilir iş gerekçesi |
| `ticket_reference` | Destek/güvenlik talebi referansı |
| `subject_scope` | Erişilebilen danışan veya danışan kümesi |
| `data_scope` | Erişilebilen veri alanları |
| `permission_scope` | İzin verilen işlemler; varsayılan `read` |
| `starts_at` | UTC erişim başlangıcı |
| `ends_at` | UTC erişim bitişi; başlangıçtan sonra olmalı |
| `granted_at` | Onay kaydının UTC zamanı |
| `revoked_at` / `revoked_by` | Varsa erken iptal bilgisi |
| `accessed_at` | Her gerçek erişim olayının UTC zamanı |
| `outcome` | İzin verildi, reddedildi, süresi doldu veya iptal edildi |

## Yetki Matrisi

| İşlem | Diyetisyen | Danışan | Admin |
|---|---:|---:|---:|
| Kendi hesabını görüntüleme | Evet | Evet | Evet |
| Danışan oluşturma ve yönetme | Yetkili olduğu danışanlar | Hayır | Yalnızca hesap/erişim yönetimi |
| Beslenme planı oluşturma ve onaylama | Evet | Hayır | Hayır |
| Onaylı planı görüntüleme | Yetkili olduğu danışanlar | Kendi planı | Operasyonel yetki gerekiyorsa |
| Besin alternatifi talep etme | Evet | Kendi onaylı planı için | Hayır |
| Değişim kuralı/toleransı tanımlama | Evet | Hayır | Klinik rol olmadan hayır |
| Riskli vakayı klinik değerlendirme | Evet | Hayır | Klinik rol olmadan hayır |
| Kullanıcı ve rol yönetimi | Hayır | Hayır | Evet |
| Denetim kayıtlarını görüntüleme | Kendi kapsamı | Kendi işlemleriyle sınırlı | Yetkisi kapsamında |
| Denetim kayıtlarını değiştirme/silme | Hayır | Hayır | Hayır |

## LLM ve Deterministik Motor Sorumlulukları

| Sorumluluk | Deterministik Motor | LLM |
|---|---:|---:|
| Porsiyon ve besin öğesi hesabı | Evet | Hayır |
| Alerji/kısıt/kural tabanlı eleme | Evet | Hayır |
| Toleranslara göre alternatif sıralama | Evet | Hayır |
| Sağlık riski kuralını uygulama | Evet | Hayır |
| Kullanıcı mesajını açıklama ve biçimlendirme | Hayır | Evet |
| Deterministik sonucu anlaşılır dille sunma | Hayır | Evet |
| Tanı, tedavi veya klinik plan onayı | Hayır | Hayır |

## Kural Önceliği ve Uygulanabilir Karar Modeli

`danışan > plan > global` sırası yalnızca aynı güvenlik seviyesindeki kurallar arasında özgüllük önceliğidir. Daha özgül bir kural daha az güvenli bir sonuç üretmek için üst kapsamın güvenlik kuralını gevşetemez.

Karar algoritması:

1. Talep için geçerli global, plan ve danışan kurallarını topla.
2. Her kuralı `BLOCK`, `REQUIRE_DIETITIAN_APPROVAL` veya `ALLOW` olarak sınıflandır.
3. En yüksek güvenlik şiddetini seç: `BLOCK > REQUIRE_DIETITIAN_APPROVAL > ALLOW`.
4. Aynı şiddette birden fazla kural varsa en özgül kapsamı seç: `danışan > plan > global`.
5. Aynı kapsam ve şiddette çözülemeyen bir çelişki varsa güvenli varsayılan olarak `REQUIRE_DIETITIAN_APPROVAL` üret ve yapılandırma hatasını denetim kaydına yaz.

### Güvenlik Karar Tablosu

| En sıkı geçerli kural | Daha özgül kural | Nihai karar | Otomatik uygulanır mı? | Gerekçe |
|---|---|---|---:|---|
| `BLOCK` | `ALLOW` veya `REQUIRE_DIETITIAN_APPROVAL` | `BLOCK` | Hayır | Sert güvenlik ihlali özgüllükle gevşetilemez |
| `REQUIRE_DIETITIAN_APPROVAL` | `ALLOW` | `REQUIRE_DIETITIAN_APPROVAL` | Hayır | Daha sıkı güvenlik kuralı kazanır |
| `ALLOW` | `REQUIRE_DIETITIAN_APPROVAL` | `REQUIRE_DIETITIAN_APPROVAL` | Hayır | Daha özgül kural daha sıkıdır |
| `ALLOW` | `BLOCK` | `BLOCK` | Hayır | Daha özgül sert kısıt uygulanır |
| `ALLOW` | `ALLOW` | En özgül `ALLOW` kuralı | Evet | Şiddet eşit; `danışan > plan > global` uygulanır |
| Aynı şiddette çelişkili kurallar | Eşit kapsam | `REQUIRE_DIETITIAN_APPROVAL` | Hayır | Çözülemeyen çelişkide güvenli varsayılan |

### `danışan > plan > global` Örnekleri

1. Global kural izin verilen değişim toleransını geniş, plan kuralı daha dar, danışan kuralı en dar tanımlıyorsa ve üçü de aynı güvenlik seviyesindeyse danışan toleransı uygulanır.
2. Global tercih hazırlanma biçimini kısıtlamıyor, plan belirli seçenekleri tercih ediyor, danışan da bunların içinden daha özel bir tercih belirtiyorsa güvenlik kuralı ihlal edilmediği sürece danışan tercihi uygulanır.
3. Global kural bir değişimi `ALLOW`, plan kuralı aynı değişimi `REQUIRE_DIETITIAN_APPROVAL` olarak sınıflandırıyor ve danışan tercihi `ALLOW` diyorsa planın daha sıkı kararı kazanır; danışan özgüllüğü güvenliği gevşetmez.
4. Global kural bir alerjen nedeniyle `BLOCK`, plan ve danışan kuralları `ALLOW` diyorsa sonuç `BLOCK` olur; global sert güvenlik kuralı tüm özgüllük seviyelerini geçersiz kılar.

## Riskli Durum Akışı

- Risk katmanı `BLOCK` veya `REQUIRE_DIETITIAN_APPROVAL` kararı üretirse otomatik uygulama durur.
- `BLOCK` sonucunda değişim uygulanmaz; kullanıcıya güvenli bir gerekçe gösterilir ve olay inceleme için kaydedilir.
- `REQUIRE_DIETITIAN_APPROVAL` sonucunda değişim beklemeye alınır ve yetkili Diyetisyene yönlendirilir.
- LLM riski geçersiz kılamaz ve öneri üretmeye devam edemez.

### Düşük Riskli Besin Değişimi Örnekleri

Bu örnekler tıbbi kural veya besin eşdeğerliği iddiası değildir; gerçek karar güvenilir besin verisi, danışan kayıtları ve deterministik toleranslarla verilmelidir.

1. Diyetisyenin önceden onayladığı değişim kümesindeki bir besin, aynı kümedeki başka bir besinle değiştirilir; alerji/kısıt çakışması yoktur ve motor tüm toleransları karşılar. Sonuç: `ALLOW`, danışan seçebilir, işlem Diyetisyen incelemesine kaydedilir.
2. Aynı onaylı besinin yalnızca marka veya paket seçeneği değişir; doğrulanmış besin profili tolerans içindedir ve içerik kısıtları ihlal edilmez. Sonuç: `ALLOW`.
3. Onaylı plandaki bir besin, Diyetisyenin danışan için tanımladığı açık alternatifle değiştirilir; porsiyon motor tarafından hesaplanır ve hiçbir daha sıkı güvenlik kuralı yoktur. Sonuç: `ALLOW`.

### Yüksek Riskli veya Otomatik Uygulanamayan Besin Değişimi Örnekleri

1. Aday besin danışanın kayıtlı alerjeniyle eşleşir. Sonuç: `BLOCK`; Diyetisyen onayı bile sert alerji kuralını otomatik olarak geçersiz kılamaz.
2. Aday besin danışanın kayıtlı klinik/plan kısıtını ihlal eder veya güvenlik kuralı değişimi açıkça yasaklar. Sonuç: `BLOCK` ve denetim kaydı.
3. Adayın besin profili deterministik toleransların dışındadır ancak sert yasak yoktur. Sonuç: `REQUIRE_DIETITIAN_APPROVAL`; onay olmadan uygulanmaz.
4. Aday besinin kaynağı, içeriği veya besin profili eksik/doğrulanmamıştır. Sonuç: `REQUIRE_DIETITIAN_APPROVAL` veya veri politikası sert yasak koyuyorsa `BLOCK`.

## Karara Bağlanan Ürün Politikaları

1. Düşük riskli ve kurallara uygun değişimlerde Danışan alternatifi seçebilir; işlem Diyetisyenin incelemesine kaydedilir. Belirsiz veya tolerans dışı değişimler uygulanmadan önce Diyetisyen onayı gerekir. Sert güvenlik ihlalleri ise `BLOCK` olur ve yalnızca onay verilerek uygulanamaz.
2. Admin sağlık verisine varsayılan olarak erişemez. Erişim yalnızca gerekçeli, süreli ve denetim kaydı oluşturan destek/güvenlik yetkisiyle verilebilir.
3. Diyetisyen kurallarının önceliği `danışan > plan > global` şeklindedir. Ancak çelişki halinde daha sıkı güvenlik kuralı her zaman kazanır.

## Aşama 1 Kabul Kontrolü

- [x] Diyetisyen, Danışan ve Admin rolleri tanımlandı.
- [x] Rol bazlı yetki sınırları yazıldı.
- [x] LLM ile deterministik motorun sorumlulukları ayrıldı.
- [x] Riskli durumların Diyetisyene yönlendirilmesi kuralı yazıldı.
- [x] Rol ve yetki politikalarındaki açık sorular ürün sahibi tarafından karara bağlandı.
- [x] Kural önceliği örnekler ve uygulanabilir karar tablosuyla açıklandı.
- [x] Admin süreli sağlık verisi erişiminin audit, gerekçe ve zaman gereksinimleri tanımlandı.
- [x] Düşük ve yüksek riskli değişim örnekleri belgelendi.
- [x] Ürün sahibi Aşama 1 belgelerinin tamamını onayladı.
